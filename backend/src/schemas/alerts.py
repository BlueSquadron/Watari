"""Alert schemas — OCSF 1.8.0 Detection Finding class.

Watari's public alert API speaks the Open Cybersecurity Schema Framework
(OCSF) Detection Finding class (class_uid 2004, category_uid 2) at
schema version 1.8.0. Producers send a Detection Finding document and
receive one back.

See: https://schema.ocsf.io/1.8.0/classes/detection_finding

Watari enforces the following subset of the spec:

REQUIRED by OCSF (enforced at ingest):
    - activity_id          (integer enum, must be 1/2/3/99)
    - category_uid         (must be 2)
    - class_uid            (must be 2004)
    - severity_id          (integer enum 0-6 or 99)
    - metadata             (object with `version` and `product`)
    - finding_info         (object with `uid` and recommended `title`)
    - time                 (epoch milliseconds)

RECOMMENDED by OCSF (accepted when provided):
    - type_uid             (auto-computed if absent: class_uid*100 + activity_id)
    - is_alert             (boolean; Watari defaults to true)
    - confidence_id        (0=Unknown, 1=Low, 2=Medium, 3=High, 99=Other)
    - status_id            (Watari sets this based on its workflow)
    - observables[]        (name/type_id/value tuples)
    - message              (human-readable description)
    - attacks[]            (MITRE ATT&CK attributions)

WATARI EXTENSIONS (added to `unmapped` or surfaced explicitly):
    - dedup_key            (string, used for pending-state deduplication;
                            if absent, Watari falls back to finding_info.uid_alt
                            then to finding_info.uid)
"""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

# ---- OCSF enums -------------------------------------------------------

# Detection Finding is class_uid 2004 in category 2 (Findings).
OCSF_CLASS_UID_DETECTION_FINDING = 2004
OCSF_CATEGORY_UID_FINDINGS = 2


class OCSFActivityId(IntEnum):
    """Detection Finding `activity_id` per OCSF 1.8.0."""

    UNKNOWN = 0
    CREATE = 1
    UPDATE = 2
    CLOSE = 3
    OTHER = 99


class OCSFSeverityId(IntEnum):
    """`severity_id` per OCSF base event (shared across all classes)."""

    UNKNOWN = 0
    INFORMATIONAL = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5
    FATAL = 6
    OTHER = 99


class OCSFStatusId(IntEnum):
    """`status_id` per OCSF Detection Finding 1.8.0."""

    UNKNOWN = 0
    NEW = 1
    IN_PROGRESS = 2
    SUPPRESSED = 3
    RESOLVED = 4
    ARCHIVED = 5
    DELETED = 6
    OTHER = 99


class OCSFConfidenceId(IntEnum):
    UNKNOWN = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    OTHER = 99


class OCSFObservableTypeId(IntEnum):
    """OCSF observable `type_id` — the subset Watari recognises.

    These are the IDs Watari both emits from its UI and can round-trip
    to internal observables when an alert is promoted. Unknown types are
    still accepted and stored verbatim.
    """

    UNKNOWN = 0
    HOSTNAME = 1
    IP_ADDRESS = 2
    MAC_ADDRESS = 3
    USER_NAME = 4
    EMAIL_ADDRESS = 5
    URL_STRING = 6
    FILE_NAME = 7
    HASH = 8
    PROCESS_NAME = 9
    RESOURCE_UID = 10
    ENDPOINT = 20
    USER = 21
    EMAIL = 22
    URL = 23
    FILE = 24
    PROCESS = 25
    GEO_LOCATION = 26
    CONTAINER = 27
    REGISTRY_KEY = 28
    REGISTRY_VALUE = 29
    FINGERPRINT = 30
    OTHER = 99


# ---- Watari-internal status (mirrors a subset of OCSFStatusId) --------


class AlertStatus(StrEnum):
    """Watari workflow state, persisted as a string for readable SQL.

    Maps 1:1 onto a subset of OCSFStatusId:
        PENDING   <-> OCSFStatusId.NEW         (1)
        PROMOTED  <-> OCSFStatusId.IN_PROGRESS (2)
        DISMISSED <-> OCSFStatusId.SUPPRESSED  (3)
    """

    PENDING = "pending"
    PROMOTED = "promoted"
    DISMISSED = "dismissed"


_ALERT_STATUS_TO_OCSF: dict[str, OCSFStatusId] = {
    AlertStatus.PENDING.value: OCSFStatusId.NEW,
    AlertStatus.PROMOTED.value: OCSFStatusId.IN_PROGRESS,
    AlertStatus.DISMISSED.value: OCSFStatusId.SUPPRESSED,
}

_OCSF_STATUS_ID_TO_CAPTION: dict[OCSFStatusId, str] = {
    OCSFStatusId.UNKNOWN: "Unknown",
    OCSFStatusId.NEW: "New",
    OCSFStatusId.IN_PROGRESS: "In Progress",
    OCSFStatusId.SUPPRESSED: "Suppressed",
    OCSFStatusId.RESOLVED: "Resolved",
    OCSFStatusId.ARCHIVED: "Archived",
    OCSFStatusId.DELETED: "Deleted",
    OCSFStatusId.OTHER: "Other",
}

_OCSF_SEVERITY_ID_TO_CAPTION: dict[int, str] = {
    0: "Unknown",
    1: "Informational",
    2: "Low",
    3: "Medium",
    4: "High",
    5: "Critical",
    6: "Fatal",
    99: "Other",
}


def ocsf_status_caption(status_id: int) -> str:
    return _OCSF_STATUS_ID_TO_CAPTION.get(OCSFStatusId(status_id), "Other")


def ocsf_severity_caption(severity_id: int) -> str:
    return _OCSF_SEVERITY_ID_TO_CAPTION.get(severity_id, "Other")


def watari_status_to_ocsf(status: str) -> OCSFStatusId:
    return _ALERT_STATUS_TO_OCSF.get(status, OCSFStatusId.OTHER)


# ---- Nested OCSF objects ---------------------------------------------


class OCSFProduct(BaseModel):
    """`metadata.product` — identifies the system that emitted the finding."""

    name: str = Field(min_length=1, max_length=255)
    vendor_name: str | None = Field(default=None, max_length=255)
    version: str | None = Field(default=None, max_length=100)
    uid: str | None = Field(default=None, max_length=255)


class OCSFMetadata(BaseModel):
    """`metadata` — required on every OCSF event."""

    model_config = ConfigDict(extra="allow")

    version: str = Field(
        default="1.8.0",
        description="OCSF schema version; Watari accepts 1.8.x only",
    )
    product: OCSFProduct
    log_level: str | None = None
    event_code: str | None = None
    original_time: str | None = None
    processed_time: str | None = None


class OCSFFindingInfo(BaseModel):
    """`finding_info` — the identity of the finding."""

    model_config = ConfigDict(extra="allow")

    uid: str = Field(
        min_length=1,
        max_length=500,
        description="Unique identifier assigned by the producer",
    )
    uid_alt: str | None = Field(
        default=None,
        max_length=500,
        description="Alternative identifier, e.g. the producer's rule hit id",
    )
    title: str | None = Field(default=None, max_length=500)
    desc: str | None = Field(default=None, description="Longer description")
    types: list[str] | None = None
    analytic: dict[str, Any] | None = Field(
        default=None,
        description="The analytic rule that produced this finding",
    )
    product_uid: str | None = None
    src_url: str | None = None


class OCSFObservable(BaseModel):
    """OCSF observable — a `{name, type, type_id, value}` tuple."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(
        default="alert.observable",
        max_length=255,
        description="Dotted path within the event where the observable was seen",
    )
    type: str | None = None
    type_id: int = Field(
        default=OCSFObservableTypeId.OTHER.value,
        description="OCSF observable type enum value",
    )
    value: str = Field(min_length=1, max_length=10000)
    reputation: dict[str, Any] | None = None


class OCSFAttack(BaseModel):
    """MITRE ATT&CK attribution carried on an OCSF event."""

    model_config = ConfigDict(extra="allow")

    tactic: dict[str, Any] | None = None
    technique: dict[str, Any] | None = None
    sub_technique: dict[str, Any] | None = None
    version: str | None = None


# ---- Top-level Detection Finding: ingest ------------------------------


class DetectionFindingIngest(BaseModel):
    """OCSF 1.8.0 Detection Finding — ingest-side validation.

    This is what external producers POST to ``/api/v1/tenants/{tenant_id}/alerts``.
    Watari enforces the OCSF-required fields and the OCSF-recommended
    fields that drive its workflow (`is_alert`, `message`). All other
    fields are accepted and round-tripped.
    """

    model_config = ConfigDict(extra="allow")

    # --- Classification (required) ---
    activity_id: OCSFActivityId = Field(
        default=OCSFActivityId.CREATE,
        description="1=Create, 2=Update, 3=Close, 99=Other",
    )
    activity_name: str | None = None
    category_uid: Literal[2] = Field(
        default=OCSF_CATEGORY_UID_FINDINGS,
        description="Must be 2 (Findings)",
    )
    category_name: str | None = "Findings"
    class_uid: Literal[2004] = Field(
        default=OCSF_CLASS_UID_DETECTION_FINDING,
        description="Must be 2004 (Detection Finding)",
    )
    class_name: str | None = "Detection Finding"
    type_uid: int | None = Field(
        default=None,
        description="class_uid * 100 + activity_id; auto-computed if absent",
    )
    type_name: str | None = None

    severity_id: OCSFSeverityId = Field(
        description="1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal"
    )
    severity: str | None = None

    # --- Required objects ---
    metadata: OCSFMetadata
    finding_info: OCSFFindingInfo
    time: int = Field(
        description="Event time as epoch milliseconds",
        gt=0,
    )
    time_dt: datetime | None = None

    # --- Recommended ---
    is_alert: bool = True
    message: str | None = Field(default=None, max_length=5000)
    status_id: OCSFStatusId | None = None
    status: str | None = None

    confidence_id: OCSFConfidenceId | None = None
    confidence: str | None = None
    confidence_score: int | None = Field(default=None, ge=0, le=100)

    observables: list[OCSFObservable] = Field(default_factory=list)
    attacks: list[OCSFAttack] = Field(default_factory=list)

    raw_data: str | None = None

    # --- Watari extensions ---
    dedup_key: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Watari-specific: dedup key for pending-state collapse. "
            "If absent, Watari derives it from finding_info.uid_alt "
            "then finding_info.uid."
        ),
    )

    # --- Validators ---
    @model_validator(mode="after")
    def _populate_computed_fields(self) -> DetectionFindingIngest:
        # type_uid = class_uid*100 + activity_id
        if self.type_uid is None:
            self.type_uid = self.class_uid * 100 + self.activity_id.value
        # severity caption mirrors severity_id
        if not self.severity:
            self.severity = ocsf_severity_caption(self.severity_id.value)
        if self.activity_name is None:
            self.activity_name = self.activity_id.name.title()
        return self


# ---- Promote / dismiss payloads (Watari-workflow, not OCSF) ----------


class AlertPromote(BaseModel):
    """Promote a Watari alert into a case. Not an OCSF concept."""

    case_id: UUID | None = Field(
        default=None,
        description="If provided, merge into existing case; else create new case",
    )
    new_case_title: str | None = Field(default=None, description="Required if case_id is None")


class AlertDismiss(BaseModel):
    """Dismiss a Watari alert. Sets status_id to SUPPRESSED (3)."""

    reason: str = Field(min_length=1, max_length=255)


# ---- Response envelope -----------------------------------------------


class AlertResponse(BaseModel):
    """Alert as returned by Watari — a full OCSF Detection Finding
    document plus a small envelope of Watari-workflow fields."""

    model_config = ConfigDict(extra="allow")

    # --- OCSF Detection Finding (faithful round-trip of the ingested payload) ---
    activity_id: int
    activity_name: str
    category_uid: int
    category_name: str
    class_uid: int
    class_name: str
    type_uid: int
    type_name: str | None

    severity_id: int
    severity: str

    metadata: OCSFMetadata
    finding_info: OCSFFindingInfo
    time: int
    time_dt: datetime

    is_alert: bool
    message: str | None
    status_id: int
    status: str

    confidence_id: int | None
    confidence: str | None
    confidence_score: int | None

    observables: list[OCSFObservable]
    attacks: list[OCSFAttack]

    raw_data: str | None

    # --- Watari workflow envelope (not part of OCSF) ---
    watari: WatariAlertEnvelope


class WatariAlertEnvelope(BaseModel):
    """Watari-specific workflow fields carried alongside the OCSF payload."""

    id: UUID
    tenant_id: UUID
    workflow_status: AlertStatus = Field(
        description="pending / promoted / dismissed (Watari-internal)"
    )
    dismiss_reason: str | None = None
    promoted_to_case_id: UUID | None = None
    dedup_key: str | None = None
    created_at: datetime
    updated_at: datetime


AlertResponse.model_rebuild()


# ---- Filters ----------------------------------------------------------


class AlertListFilters(BaseModel):
    """Filter inputs for the list endpoint. Uses OCSF-style numeric IDs
    but also accepts the Watari workflow status for backwards familiarity."""

    workflow_status: AlertStatus | None = None
    severity_id: Annotated[int | None, Field(ge=0, le=99)] = None
    product_name: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


__all__ = [
    "AlertStatus",
    "OCSFActivityId",
    "OCSFSeverityId",
    "OCSFStatusId",
    "OCSFConfidenceId",
    "OCSFObservableTypeId",
    "OCSFProduct",
    "OCSFMetadata",
    "OCSFFindingInfo",
    "OCSFObservable",
    "OCSFAttack",
    "DetectionFindingIngest",
    "AlertPromote",
    "AlertDismiss",
    "AlertResponse",
    "WatariAlertEnvelope",
    "AlertListFilters",
    "ocsf_severity_caption",
    "ocsf_status_caption",
    "watari_status_to_ocsf",
    "OCSF_CLASS_UID_DETECTION_FINDING",
    "OCSF_CATEGORY_UID_FINDINGS",
]

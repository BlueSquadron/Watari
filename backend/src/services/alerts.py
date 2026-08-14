"""Alert service: OCSF 1.8.0 Detection Finding ingestion, triage, promotion.

Responsibilities:
    - Validate incoming OCSF Detection Finding payloads.
    - Persist both the full OCSF document (in ``ocsf_payload`` JSONB) and
      the denormalized hot fields used by the UI.
    - Deduplicate pending alerts by ``dedup_key``. If the producer did
      not supply one, fall back to ``finding_info.uid_alt`` then
      ``finding_info.uid`` so that re-sending the same Detection Finding
      collapses into a single pending row.
    - Promote an alert to a case, copying OCSF observables into the
      target case's observables table.
    - Dismiss an alert, setting status to SUPPRESSED (OCSF 3).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Alert, Case
from src.schemas.alerts import (
    AlertDismiss,
    AlertListFilters,
    AlertPromote,
    AlertResponse,
    AlertStatus,
    DetectionFindingIngest,
    OCSFObservableTypeId,
    OCSFStatusId,
    WatariAlertEnvelope,
    ocsf_severity_caption,
    ocsf_status_caption,
    watari_status_to_ocsf,
)
from src.schemas.cases import CaseCreate, CaseSeverity
from src.schemas.observables import TLP, ObservableCreate, ObservableType

from . import cases as case_service
from . import observables as observable_service
from .timeline_recorder import record_event

# ---- Dedup ------------------------------------------------------------


def _derive_dedup_key(payload: DetectionFindingIngest) -> str | None:
    """Return the effective dedup key for an incoming Detection Finding.

    Precedence: explicit ``dedup_key`` extension > ``finding_info.uid_alt``
    > ``finding_info.uid``. Returns ``None`` only if the caller explicitly
    sent an empty ``dedup_key`` and no finding_info uid is present, which
    the ingest schema normally prevents because ``uid`` is required.
    """
    if payload.dedup_key:
        return payload.dedup_key
    if payload.finding_info.uid_alt:
        return payload.finding_info.uid_alt
    return payload.finding_info.uid


def is_duplicate_payload(payload: DetectionFindingIngest, other: Alert) -> bool:
    """Pure predicate: would this ingest match an existing pending alert?"""
    if other.status != AlertStatus.PENDING.value:
        return False
    incoming_key = _derive_dedup_key(payload)
    return bool(incoming_key) and incoming_key == other.dedup_key


# ---- DB helpers -------------------------------------------------------


async def _get_alert_or_404(db: AsyncSession, alert_id: UUID) -> Alert:
    alert = (
        await db.execute(select(Alert).where(Alert.id == alert_id))
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Alert {alert_id} not found")
    return alert


# ---- Ingest -----------------------------------------------------------


async def ingest_alert(
    db: AsyncSession, tenant_id: UUID, payload: DetectionFindingIngest
) -> tuple[Alert, bool]:
    """Ingest an OCSF Detection Finding. Returns ``(alert, was_duplicate)``.

    If a pending alert with the same effective dedup key already exists
    in the tenant, return that existing row without creating a new one.
    """
    dedup_key = _derive_dedup_key(payload)
    if dedup_key:
        existing = (
            await db.execute(
                select(Alert).where(
                    Alert.tenant_id == tenant_id,
                    Alert.dedup_key == dedup_key,
                    Alert.status == AlertStatus.PENDING.value,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, True

    # Serialize the validated OCSF payload to a plain dict for storage
    ocsf_payload = payload.model_dump(mode="json", exclude_none=False)

    alert = Alert(
        tenant_id=tenant_id,
        severity_id=payload.severity_id.value,
        source_product=payload.metadata.product.name,
        finding_uid=payload.finding_info.uid,
        title=payload.finding_info.title or (payload.message or payload.finding_info.uid),
        message=payload.message,
        ocsf_payload=ocsf_payload,
        status=AlertStatus.PENDING.value,
        dedup_key=dedup_key,
    )
    db.add(alert)
    await db.flush()
    await db.refresh(alert)

    # Fire platform event for modules
    from src.modules.base import PlatformEvent

    from . import events as _events

    await _events.fire(
        db,
        tenant_id=tenant_id,
        event=PlatformEvent.ALERT_INGESTED,
        payload={
            "alert_id": str(alert.id),
            "product": alert.source_product,
            "severity_id": alert.severity_id,
            "finding_uid": alert.finding_uid,
        },
        actor_id=None,
    )
    return alert, False


# ---- List / filter ----------------------------------------------------


async def list_alerts(
    db: AsyncSession,
    tenant_id: UUID,
    filters: AlertListFilters,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Alert], int]:
    base = select(Alert).where(Alert.tenant_id == tenant_id)
    if filters.workflow_status:
        base = base.where(Alert.status == filters.workflow_status.value)
    if filters.severity_id is not None:
        base = base.where(Alert.severity_id == filters.severity_id)
    if filters.product_name:
        base = base.where(Alert.source_product == filters.product_name)
    if filters.created_after:
        base = base.where(Alert.created_at >= filters.created_after)
    if filters.created_before:
        base = base.where(Alert.created_at <= filters.created_before)
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        await db.execute(
            base.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return list(rows), int(total)


# ---- Dismiss / promote ------------------------------------------------


async def dismiss_alert(
    db: AsyncSession, alert_id: UUID, payload: AlertDismiss
) -> Alert:
    alert = await _get_alert_or_404(db, alert_id)
    alert.status = AlertStatus.DISMISSED.value
    alert.dismiss_reason = payload.reason
    # Mirror the status onto the OCSF payload so consumers see it
    _apply_status_to_payload(alert, OCSFStatusId.SUPPRESSED, status_detail=payload.reason)
    await db.flush()
    await db.refresh(alert)
    return alert


async def promote_alert(
    db: AsyncSession,
    alert_id: UUID,
    payload: AlertPromote,
    *,
    actor_id: UUID,
) -> tuple[Alert, Case]:
    alert = await _get_alert_or_404(db, alert_id)

    if payload.case_id is not None:
        case = (
            await db.execute(select(Case).where(Case.id == payload.case_id))
        ).scalar_one_or_none()
        if case is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Target case not found")
        if case.tenant_id != alert.tenant_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Cannot merge alert into a case from another tenant",
            )
    else:
        if not payload.new_case_title:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Either case_id or new_case_title must be provided",
            )
        case = await case_service.create_case(
            db,
            tenant_id=alert.tenant_id,
            created_by=actor_id,
            payload=CaseCreate(
                title=payload.new_case_title,
                description=alert.message,
                severity=_severity_id_to_case_severity(alert.severity_id),
            ),
        )

    # Copy OCSF observables from the stored payload onto the target case
    for ocsf_obs_raw in alert.ocsf_payload.get("observables", []) or []:
        obs_create = _ocsf_to_observable_create(ocsf_obs_raw)
        if obs_create is None:
            continue  # type not mappable to a Watari observable type — skip
        try:
            await observable_service.create_observable(
                db, case_id=case.id, created_by=actor_id, payload=obs_create
            )
        except HTTPException:
            # Invalid value format (per Watari's strict validators) — skip
            continue

    alert.status = AlertStatus.PROMOTED.value
    alert.promoted_to_case_id = case.id
    _apply_status_to_payload(alert, OCSFStatusId.IN_PROGRESS)

    await record_event(
        db,
        tenant_id=alert.tenant_id,
        case_id=case.id,
        event_type="alert_promoted",
        description=f"Alert '{alert.title}' promoted to this case",
        category="alert",
        actor_id=actor_id,
        metadata={
            "alert_id": str(alert.id),
            "product": alert.source_product,
            "finding_uid": alert.finding_uid,
        },
    )
    await db.flush()
    await db.refresh(alert)
    return alert, case


# ---- Serialization: DB row -> AlertResponse --------------------------


def alert_to_response(alert: Alert) -> AlertResponse:
    """Rebuild a full OCSF Detection Finding plus Watari envelope from a row.

    The DB's ``ocsf_payload`` is the source of truth for every OCSF field.
    We override ``status_id`` / ``status`` with the current Watari
    workflow state so promoted/dismissed alerts show the right status
    even if the original producer sent something different.
    """
    payload = dict(alert.ocsf_payload) if alert.ocsf_payload else {}

    # Current workflow status takes precedence
    workflow_status_id = watari_status_to_ocsf(alert.status)
    payload["status_id"] = workflow_status_id.value
    payload["status"] = ocsf_status_caption(workflow_status_id.value)

    # Ensure the response has classification fields (defensive — ingest
    # validator already enforces these, but belt-and-braces for rows
    # inserted by the seed script / raw SQL)
    payload.setdefault("class_uid", 2004)
    payload.setdefault("class_name", "Detection Finding")
    payload.setdefault("category_uid", 2)
    payload.setdefault("category_name", "Findings")
    payload.setdefault("activity_id", 1)
    payload.setdefault("activity_name", "Create")
    payload.setdefault("type_uid", payload["class_uid"] * 100 + payload["activity_id"])

    # Severity caption should match severity_id
    sev_id = payload.get("severity_id", alert.severity_id)
    payload["severity_id"] = sev_id
    payload["severity"] = ocsf_severity_caption(sev_id)

    # time / time_dt
    if "time_dt" not in payload or payload.get("time_dt") is None:
        payload["time_dt"] = alert.created_at
    if "time" not in payload or payload.get("time") is None:
        payload["time"] = int(alert.created_at.timestamp() * 1000)

    # observables / attacks default to empty lists
    payload.setdefault("observables", [])
    payload.setdefault("attacks", [])

    # Watari envelope is a sibling, NOT part of the OCSF document
    envelope = WatariAlertEnvelope(
        id=alert.id,
        tenant_id=alert.tenant_id,
        workflow_status=AlertStatus(alert.status),
        dismiss_reason=alert.dismiss_reason,
        promoted_to_case_id=alert.promoted_to_case_id,
        dedup_key=alert.dedup_key,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )
    return AlertResponse(**payload, watari=envelope)


# ---- Internal helpers -------------------------------------------------


def _apply_status_to_payload(
    alert: Alert, status_id: OCSFStatusId, *, status_detail: str | None = None
) -> None:
    """Mirror the new workflow status onto the stored OCSF payload so
    subsequent reads of ``ocsf_payload`` reflect the current state."""
    payload = dict(alert.ocsf_payload) if alert.ocsf_payload else {}
    payload["status_id"] = status_id.value
    payload["status"] = ocsf_status_caption(status_id.value)
    if status_detail is not None:
        payload["status_detail"] = status_detail
    alert.ocsf_payload = payload


_SEVERITY_ID_TO_CASE_SEVERITY: dict[int, CaseSeverity] = {
    1: CaseSeverity.INFORMATIONAL,
    2: CaseSeverity.LOW,
    3: CaseSeverity.MEDIUM,
    4: CaseSeverity.HIGH,
    5: CaseSeverity.CRITICAL,
    6: CaseSeverity.CRITICAL,  # map "Fatal" to critical on case creation
}


def _severity_id_to_case_severity(severity_id: int) -> CaseSeverity:
    return _SEVERITY_ID_TO_CASE_SEVERITY.get(severity_id, CaseSeverity.MEDIUM)


# OCSF observable type_id -> Watari observable type. IDs not in this
# map cannot be round-tripped into a case observable and are skipped
# during promotion.
_OCSF_TO_WATARI_OBSERVABLE: dict[int, ObservableType] = {
    OCSFObservableTypeId.HOSTNAME.value: ObservableType.HOSTNAME,
    OCSFObservableTypeId.IP_ADDRESS.value: ObservableType.IP,
    OCSFObservableTypeId.EMAIL_ADDRESS.value: ObservableType.EMAIL,
    OCSFObservableTypeId.URL_STRING.value: ObservableType.URL,
    OCSFObservableTypeId.URL.value: ObservableType.URL,
    OCSFObservableTypeId.EMAIL.value: ObservableType.EMAIL,
    OCSFObservableTypeId.FILE_NAME.value: ObservableType.FILENAME,
    OCSFObservableTypeId.REGISTRY_KEY.value: ObservableType.REGISTRY_KEY,
}


def _ocsf_to_observable_create(raw: dict[str, Any]) -> ObservableCreate | None:
    """Convert an OCSF observable dict to a Watari ObservableCreate.

    Returns ``None`` if the OCSF type_id doesn't map to a Watari observable
    type, or if the value is missing.
    """
    if not isinstance(raw, dict):
        return None
    value = raw.get("value")
    if not value or not isinstance(value, str):
        return None

    type_id = raw.get("type_id")
    watari_type: ObservableType | None = None

    # Hashes need special handling: OCSF uses a single type_id=8 "Hash"
    # for all hash algorithms. Infer from value length.
    if type_id == OCSFObservableTypeId.HASH.value:
        length = len(value)
        if length == 32:
            watari_type = ObservableType.HASH_MD5
        elif length == 40:
            watari_type = ObservableType.HASH_SHA1
        elif length == 64:
            watari_type = ObservableType.HASH_SHA256
    elif isinstance(type_id, int):
        watari_type = _OCSF_TO_WATARI_OBSERVABLE.get(type_id)

    if watari_type is None:
        return None

    # OCSF doesn't carry TLP / IOC natively. Watari extensions sometimes
    # do — honour them if present, otherwise default.
    tlp_raw = raw.get("tlp")
    tlp_enum: TLP | None = None
    if isinstance(tlp_raw, str):
        try:
            tlp_enum = TLP(tlp_raw.lower())
        except ValueError:
            tlp_enum = None

    return ObservableCreate(
        type=watari_type,
        value=value,
        tlp=tlp_enum,
        is_ioc=bool(raw.get("is_ioc", False)),
    )


__all__ = [
    "ingest_alert",
    "list_alerts",
    "dismiss_alert",
    "promote_alert",
    "alert_to_response",
    "is_duplicate_payload",
]

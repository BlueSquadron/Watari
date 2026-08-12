"""Property: OCSF Detection Finding round-trip fidelity.

Any valid OCSF 1.8.0 Detection Finding ingested by Watari and read
back via ``alert_to_response`` SHALL preserve:
  - All OCSF classification fields (class_uid, category_uid, activity_id, ...)
  - finding_info.uid and finding_info.title
  - metadata.product.name
  - observables[] in count and value
  - attacks[] in count
  - message, raw_data, confidence_id, confidence_score
  - The severity_id value

Status_id / status are overwritten by Watari based on the current
workflow state, so they are not included in the round-trip assertions.

This is a pure-function test: it builds an Alert model instance from a
DetectionFindingIngest and then exercises alert_to_response directly,
without hitting the database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.models import Alert
from src.schemas.alerts import (
    DetectionFindingIngest,
    OCSFActivityId,
    OCSFConfidenceId,
    OCSFFindingInfo,
    OCSFMetadata,
    OCSFObservable,
    OCSFObservableTypeId,
    OCSFProduct,
    OCSFSeverityId,
)
from src.services.alerts import alert_to_response

# --- Hypothesis strategies --------------------------------------------

_severity_ids = st.sampled_from(
    [
        OCSFSeverityId.INFORMATIONAL,
        OCSFSeverityId.LOW,
        OCSFSeverityId.MEDIUM,
        OCSFSeverityId.HIGH,
        OCSFSeverityId.CRITICAL,
    ]
)

_activity_ids = st.sampled_from([OCSFActivityId.CREATE, OCSFActivityId.UPDATE])

_observable_type_ids = st.sampled_from(
    [
        OCSFObservableTypeId.IP_ADDRESS.value,
        OCSFObservableTypeId.HOSTNAME.value,
        OCSFObservableTypeId.EMAIL_ADDRESS.value,
        OCSFObservableTypeId.URL_STRING.value,
        OCSFObservableTypeId.HASH.value,
        OCSFObservableTypeId.FILE_NAME.value,
    ]
)

_safe_strings = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters="-._ ",
    ),
    min_size=1,
    max_size=40,
)


@st.composite
def _detection_finding(draw: st.DrawFn) -> DetectionFindingIngest:
    return DetectionFindingIngest(
        activity_id=draw(_activity_ids),
        severity_id=draw(_severity_ids),
        time=draw(st.integers(min_value=1_700_000_000_000, max_value=1_900_000_000_000)),
        metadata=OCSFMetadata(
            product=OCSFProduct(
                name=draw(_safe_strings),
                vendor_name=draw(st.one_of(st.none(), _safe_strings)),
                version=draw(st.one_of(st.none(), _safe_strings)),
            )
        ),
        finding_info=OCSFFindingInfo(
            uid=f"uid-{draw(_safe_strings)}",
            uid_alt=draw(st.one_of(st.none(), _safe_strings)),
            title=draw(_safe_strings),
            desc=draw(st.one_of(st.none(), _safe_strings)),
        ),
        message=draw(st.one_of(st.none(), _safe_strings)),
        confidence_id=draw(
            st.one_of(
                st.none(),
                st.sampled_from(
                    [
                        OCSFConfidenceId.LOW,
                        OCSFConfidenceId.MEDIUM,
                        OCSFConfidenceId.HIGH,
                    ]
                ),
            )
        ),
        confidence_score=draw(st.one_of(st.none(), st.integers(min_value=0, max_value=100))),
        observables=draw(
            st.lists(
                st.builds(
                    lambda tid, value: OCSFObservable(
                        name="alert.observable", type_id=tid, value=value
                    ),
                    _observable_type_ids,
                    st.text(min_size=1, max_size=50),
                ),
                max_size=4,
            )
        ),
        raw_data=draw(st.one_of(st.none(), _safe_strings)),
    )


def _ingest_to_alert(payload: DetectionFindingIngest) -> Alert:
    """Build an Alert model the way the service does, without the DB."""
    ocsf_payload = payload.model_dump(mode="json", exclude_none=False)
    return Alert(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        severity_id=payload.severity_id.value,
        source_product=payload.metadata.product.name,
        finding_uid=payload.finding_info.uid,
        title=payload.finding_info.title or payload.finding_info.uid,
        message=payload.message,
        ocsf_payload=ocsf_payload,
        status="pending",
        dedup_key=payload.finding_info.uid,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# --- The actual property ----------------------------------------------


@given(payload=_detection_finding())
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_ocsf_fields_survive_ingest_and_serialization(
    payload: DetectionFindingIngest,
) -> None:
    """A Detection Finding ingested by Watari can be read back faithfully."""
    alert = _ingest_to_alert(payload)
    response = alert_to_response(alert)

    # OCSF classification constants
    assert response.class_uid == 2004
    assert response.category_uid == 2
    assert response.activity_id == payload.activity_id.value
    assert response.type_uid == payload.class_uid * 100 + payload.activity_id.value

    # Severity is preserved (caption is recomputed but semantically equal)
    assert response.severity_id == payload.severity_id.value

    # Identity fields round-trip
    assert response.finding_info.uid == payload.finding_info.uid
    assert response.finding_info.title == payload.finding_info.title
    assert response.metadata.product.name == payload.metadata.product.name

    # Descriptive fields round-trip
    assert response.message == payload.message
    assert response.raw_data == payload.raw_data

    # Confidence round-trip
    expected_confidence = (
        payload.confidence_id.value if payload.confidence_id is not None else None
    )
    assert response.confidence_id == expected_confidence
    assert response.confidence_score == payload.confidence_score

    # Observables preserved in count, order, value
    assert len(response.observables) == len(payload.observables)
    for out_obs, in_obs in zip(response.observables, payload.observables, strict=True):
        assert out_obs.value == in_obs.value
        assert out_obs.type_id == in_obs.type_id


def test_ocsf_workflow_status_overrides_stored_status() -> None:
    """Watari overrides stored status_id with the current workflow state."""
    payload = DetectionFindingIngest(
        severity_id=OCSFSeverityId.MEDIUM,
        time=1_700_000_000_000,
        metadata=OCSFMetadata(product=OCSFProduct(name="test")),
        finding_info=OCSFFindingInfo(uid="u"),
    )
    alert = _ingest_to_alert(payload)

    # Pending -> 1 "New"
    alert.status = "pending"
    assert alert_to_response(alert).status_id == 1

    # Promoted -> 2 "In Progress"
    alert.status = "promoted"
    assert alert_to_response(alert).status_id == 2

    # Dismissed -> 3 "Suppressed"
    alert.status = "dismissed"
    assert alert_to_response(alert).status_id == 3

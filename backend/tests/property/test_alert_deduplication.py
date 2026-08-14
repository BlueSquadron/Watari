"""Property 13: Alert Deduplication Matching.

For any two alerts, the deduplication function SHALL identify them as
duplicates if and only if their fields match according to the configured
dedup rules. Alerts with different dedup keys SHALL never be identified
as duplicates.

Feature: watari-case-management, Property 13: Alert Deduplication Matching
**Validates: Requirements 9.7**

Watari's dedup precedence (for OCSF Detection Findings):
    explicit dedup_key extension > finding_info.uid_alt > finding_info.uid

Pure predicate test — no database required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import Alert
from src.schemas.alerts import (
    DetectionFindingIngest,
    OCSFFindingInfo,
    OCSFMetadata,
    OCSFProduct,
    OCSFSeverityId,
)
from src.services.alerts import _derive_dedup_key, is_duplicate_payload


def _make_ingest(
    *,
    uid: str = "finding-uid-1",
    uid_alt: str | None = None,
    dedup_key: str | None = None,
) -> DetectionFindingIngest:
    return DetectionFindingIngest(
        severity_id=OCSFSeverityId.LOW,
        metadata=OCSFMetadata(product=OCSFProduct(name="test-product")),
        finding_info=OCSFFindingInfo(uid=uid, uid_alt=uid_alt),
        time=int(datetime.now(UTC).timestamp() * 1000),
        dedup_key=dedup_key,
    )


def _make_existing_alert(dedup_key: str | None, status: str = "pending") -> Alert:
    return Alert(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        severity_id=2,
        source_product="test-product",
        finding_uid="existing-uid",
        title="existing",
        message=None,
        ocsf_payload={},
        status=status,
        dedup_key=dedup_key,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---- _derive_dedup_key: precedence rules ------------------------------


def test_derive_prefers_explicit_dedup_key() -> None:
    ingest = _make_ingest(uid="u", uid_alt="ua", dedup_key="explicit")
    assert _derive_dedup_key(ingest) == "explicit"


def test_derive_falls_back_to_uid_alt() -> None:
    ingest = _make_ingest(uid="u", uid_alt="ua")
    assert _derive_dedup_key(ingest) == "ua"


def test_derive_falls_back_to_uid() -> None:
    ingest = _make_ingest(uid="u")
    assert _derive_dedup_key(ingest) == "u"


# ---- is_duplicate_payload: matching semantics -------------------------


@given(
    key_a=st.text(min_size=1, max_size=32),
    key_b=st.one_of(st.none(), st.text(min_size=1, max_size=32)),
)
@settings(max_examples=200)
def test_dedup_iff_keys_match_and_existing_is_pending(key_a: str, key_b: str | None) -> None:
    """Two alerts dedup iff the effective keys are equal AND the existing
    alert is still in the ``pending`` state."""
    ingest = _make_ingest(uid="never-used", dedup_key=key_a)
    existing_pending = _make_existing_alert(key_b, status="pending")

    expected = key_b is not None and key_a == key_b
    assert is_duplicate_payload(ingest, existing_pending) is expected


def test_never_dedup_against_non_pending_alerts() -> None:
    """Promoted or dismissed alerts do not dedup with new findings,
    even if the keys match — re-detection creates a new alert."""
    ingest = _make_ingest(uid="u", dedup_key="same-key")
    for status in ("promoted", "dismissed"):
        existing = _make_existing_alert("same-key", status=status)
        assert not is_duplicate_payload(ingest, existing)


def test_existing_without_dedup_key_never_matches() -> None:
    """An existing alert that was stored without a dedup_key never dedups,
    even if the incoming finding does have one."""
    ingest = _make_ingest(uid="u", dedup_key="x")
    existing = _make_existing_alert(None, status="pending")
    assert not is_duplicate_payload(ingest, existing)

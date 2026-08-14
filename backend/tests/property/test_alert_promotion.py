"""Property 12: Alert Promotion Data Preservation.

For any OCSF Detection Finding promoted to a case (new or existing),
ALL observables from the alert that map to Watari observable types
SHALL appear on the target case. The alert's severity SHALL be
preserved on the resulting case (via the OCSF severity_id -> Watari
CaseSeverity mapping).

Feature: watari-case-management, Property 12: Alert Promotion Data Preservation
**Validates: Requirements 9.4, 9.5**

Requires a live PostgreSQL database.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Observable
from src.schemas.alerts import (
    AlertPromote,
    DetectionFindingIngest,
    OCSFFindingInfo,
    OCSFMetadata,
    OCSFObservable,
    OCSFObservableTypeId,
    OCSFProduct,
    OCSFSeverityId,
)
from src.schemas.cases import CaseSeverity
from src.services import alerts as alert_service

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None and os.getenv("DATABASE_URL") is None,
    reason="Requires PostgreSQL test database",
)


@pytest.mark.asyncio
@settings(
    max_examples=10,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    deadline=None,
)
@given(
    obs_values=st.lists(
        st.tuples(
            st.integers(min_value=1, max_value=254),
            st.integers(min_value=1, max_value=254),
            st.integers(min_value=1, max_value=254),
            st.integers(min_value=1, max_value=254),
        ),
        min_size=0,
        max_size=5,
        unique=True,
    ),
)
async def test_promotion_transfers_all_observables_to_new_case(
    obs_values: list[tuple[int, int, int, int]],
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=str(tenant.id))
    )

    ip_values = [f"{a}.{b}.{c}.{d}" for a, b, c, d in obs_values]

    alert, _dupe = await alert_service.ingest_alert(
        db_session,
        tenant.id,
        DetectionFindingIngest(
            severity_id=OCSFSeverityId.HIGH,
            metadata=OCSFMetadata(product=OCSFProduct(name="test-product")),
            finding_info=OCSFFindingInfo(uid="suspicious-ips-1", title="Suspicious IPs"),
            time=int(datetime.now(UTC).timestamp() * 1000),
            message="Triage this",
            observables=[
                OCSFObservable(
                    name="src_endpoint.ip",
                    type_id=OCSFObservableTypeId.IP_ADDRESS.value,
                    value=v,
                    is_ioc=True,
                )
                for v in ip_values
            ],
        ),
    )

    _promoted, case = await alert_service.promote_alert(
        db_session,
        alert.id,
        AlertPromote(new_case_title="From alert"),
        actor_id=user.id,
    )

    # All IP observable values appear on the target case
    case_obs = (
        await db_session.execute(
            select(Observable.value).where(Observable.case_id == case.id)
        )
    ).scalars().all()
    assert sorted(case_obs) == sorted(ip_values)

    # Case metadata preserved
    assert case.title == "From alert"
    # severity_id=4 (High) maps to Watari CaseSeverity.HIGH
    assert case.severity == CaseSeverity.HIGH.value

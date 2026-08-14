"""Property 14: Full-Text Search Correctness.

For any search query against case titles, descriptions, comments,
observable values, and note content within a tenant, the result set
SHALL contain only items whose searchable text matches the query terms,
and SHALL NOT include items from other tenants.

Feature: watari-case-management, Property 14: Full-Text Search Correctness
**Validates: Requirements 11.1**

The pure filter predicate is checked in memory; the DB-backed
`search()` service is exercised against PostgreSQL below, one case per
entity type, because a wrong column name there is invisible until the
branch actually runs.
"""

from __future__ import annotations

import os

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Alert
from src.schemas.assets import AssetCreate, AssetType
from src.schemas.cases import CaseCreate, CaseSeverity
from src.schemas.notes import NoteCreate
from src.schemas.observables import ObservableCreate, ObservableType
from src.schemas.search import SearchEntityType, SearchRequest
from src.services import assets as asset_service
from src.services import cases as case_service
from src.services import notes as note_service
from src.services import observables as observable_service
from src.services import search as search_service
from src.services.search import filter_match


@given(
    haystack=st.text(min_size=1, max_size=200),
    needle=st.text(min_size=1, max_size=20),
)
def test_filter_match_substring(haystack: str, needle: str) -> None:
    """filter_match SHALL accept iff needle is a case-insensitive substring."""
    expected = needle.lower() in haystack.lower()
    assert filter_match(haystack, query=needle) == expected


@given(
    haystack=st.text(min_size=1, max_size=100),
)
def test_empty_query_always_accepts(haystack: str) -> None:
    assert filter_match(haystack) is True
    assert filter_match(haystack, query=None) is True


def test_multiple_filters_compose() -> None:
    assert filter_match(
        "malware incident", query="malware", status="open", status_field="open"
    )
    # One mismatching field blocks the hit
    assert not filter_match(
        "malware incident", query="malware", status="open", status_field="closed"
    )


# --- DB-backed: every entity branch of search() must actually execute -------

db_required = pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None and os.getenv("DATABASE_URL") is None,
    reason="Requires PostgreSQL test database",
)


@db_required
@pytest.mark.asyncio
async def test_search_returns_a_hit_from_every_entity_type(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """Regression for #2.

    The alert branch queried `Alert.description`, `Alert.source` and
    `Alert.severity`, none of which exist on the model, so every search
    raised `AttributeError` before returning. A wrong attribute name in any
    branch is only visible once that branch runs against real rows, so this
    asserts a hit for all five entity types.
    """
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(
            tid=str(tenant.id)
        )
    )

    term = "zzsearchable"

    case = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        payload=CaseCreate(
            title=f"Case {term}",
            description=f"about {term}",
            severity=CaseSeverity.LOW,
            tags=[],
            custom_fields={},
        ),
    )
    await observable_service.create_observable(
        db_session,
        case_id=case.id,
        created_by=user.id,
        payload=ObservableCreate(type=ObservableType.HOSTNAME, value=f"{term}.example.com"),
    )
    await asset_service.create_asset(
        db_session,
        case_id=case.id,
        created_by=user.id,
        payload=AssetCreate(name=f"host-{term}", type=AssetType.SERVER),
    )
    await note_service.create_note(
        db_session,
        case.id,
        user.id,
        NoteCreate(title=f"Note {term}", content=f"body mentioning {term}"),
    )
    db_session.add(
        Alert(
            tenant_id=tenant.id,
            severity_id=4,
            source_product="Regression Suite",
            finding_uid=f"uid-{term}",
            title=f"Alert {term}",
            message=f"alert message mentioning {term}",
            ocsf_payload={},
        )
    )
    await db_session.flush()

    response = await search_service.search(
        db_session, tenant.id, SearchRequest(query=term)
    )

    found = {hit.entity_type for hit in response.hits}
    assert found == set(SearchEntityType), f"missing hits for {set(SearchEntityType) - found}"
    assert response.total_hits == len(response.hits)


@db_required
@pytest.mark.asyncio
async def test_search_matches_alert_message_not_just_title(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """The alert branch searches title OR message, and reports real columns."""
    tenant = await tenant_factory()
    await user_factory(tenant.id)
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(
            tid=str(tenant.id)
        )
    )

    db_session.add(
        Alert(
            tenant_id=tenant.id,
            severity_id=5,
            source_product="CrowdStrike Falcon",
            finding_uid="uid-body-only",
            title="Nothing notable in this title",
            message="the searchable token is qqbodyonly",
            ocsf_payload={},
        )
    )
    await db_session.flush()

    response = await search_service.search(
        db_session,
        tenant.id,
        SearchRequest(query="qqbodyonly", entity_types=[SearchEntityType.ALERT]),
    )

    assert len(response.hits) == 1
    hit = response.hits[0]
    assert hit.snippet == "the searchable token is qqbodyonly"
    assert hit.extra["source_product"] == "CrowdStrike Falcon"
    assert hit.extra["severity_id"] == 5
    assert hit.extra["severity"] == "Critical"
    assert hit.extra["status"] == "pending"

"""Property 4: Template Application Completeness.

For any case template containing tasks, custom fields, tags, and default
severity, creating a case from that template SHALL produce a case where
ALL template-defined attributes are present and match the template.

Feature: watari-case-management, Property 4: Template Application Completeness
**Validates: Requirements 3.7, 4.3**

Requires a live PostgreSQL database.
"""

from __future__ import annotations

import os

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Task
from src.models.template import CaseTemplate
from src.schemas.cases import CaseCreate, CaseSeverity
from src.services import cases as case_service

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
    template_tags=st.lists(
        st.text(alphabet="abcdef", min_size=1, max_size=10),
        min_size=0,
        max_size=5,
        unique=True,
    ),
    template_task_titles=st.lists(
        st.text(alphabet="abcdef ", min_size=1, max_size=20),
        min_size=0,
        max_size=5,
    ),
    template_severity=st.sampled_from(["critical", "high", "medium", "low", "informational"]),
)
async def test_case_created_from_template_inherits_attributes(
    template_tags: list[str],
    template_task_titles: list[str],
    template_severity: str,
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """Case created from a template contains all tags, tasks and the default severity."""
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=str(tenant.id))
    )

    template = CaseTemplate(
        tenant_id=tenant.id,
        name="tpl",
        default_severity=template_severity,
        default_tags=list(template_tags),
        tasks=[{"title": t} for t in template_task_titles],
        custom_fields={"platform": "watari"},
        created_by=user.id,
    )
    db_session.add(template)
    await db_session.flush()

    case = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        payload=CaseCreate(
            title="From template",
            severity=CaseSeverity.MEDIUM,  # will be overridden if template.default_severity is set
            template_id=template.id,
            tags=[],
            custom_fields={},
        ),
    )

    # Tags: every template tag appears on the case
    case_tag_set = set(case.tags or [])
    assert set(template_tags).issubset(case_tag_set), (
        f"Template tags {template_tags} not all present on case: {case_tag_set}"
    )

    # Custom fields: template defaults present
    assert case.custom_fields.get("platform") == "watari"

    # Severity: template default wins when payload specified "medium"
    assert case.severity == template_severity

    # Tasks: one per template task entry
    task_titles = (
        (
            await db_session.execute(
                select(Task.title).where(Task.case_id == case.id).order_by(Task.sort_order.asc())
            )
        )
        .scalars()
        .all()
    )
    assert list(task_titles) == template_task_titles

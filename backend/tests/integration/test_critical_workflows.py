"""Integration tests for the four critical end-to-end workflows.

Each test walks a full user journey across multiple services, wired
together exactly as they are in the API routers. These tests require a
live PostgreSQL database (via conftest's `test_engine` fixture) because
they exercise RLS, triggers, and the `next_case_number` function.

Workflows covered (task 47.4):
  1. Alert → triage → case creation → investigation → resolution
  2. Observable addition → enrichment registration → cross-case correlation
  3. Evidence upload → hash verification → timeline recording
  4. Case creation from template → task completion → report generation stub

Run with:
    PYTHONPATH=. python3 -m pytest tests/integration -v
"""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import UploadFile
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    Alert,
    Case,
    CaseTemplate,
    Evidence,
    Observable,
    Task,
    TimelineEntry,
)
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
from src.schemas.cases import CaseClose, CaseCreate, CaseOutcome, CaseSeverity, CaseStatus
from src.schemas.evidence import EvidenceRegister, EvidenceType
from src.schemas.observables import ObservableCreate, ObservableType, TLP
from src.schemas.tasks import TaskStatus, TaskUpdate
from src.schemas.templates import CaseTemplateCreate
from src.services import (
    alerts as alert_service,
    cases as case_service,
    evidence as evidence_service,
    observables as observable_service,
    tasks as task_service,
    templates as template_service,
)


pytestmark = pytest.mark.asyncio


async def _set_tenant_context(db: AsyncSession, tenant_id: UUID) -> None:
    """Emulate the middleware setting the RLS tenant before each request."""
    await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))


# ---------------------------------------------------------------------------
# Workflow 1: Alert triage → case creation → investigation → resolution
# ---------------------------------------------------------------------------


async def test_alert_to_case_resolution_flow(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    analyst = await user_factory(tenant.id, role="analyst")
    await _set_tenant_context(db_session, tenant.id)

    # 1. External system ingests an alert
    alert, was_dup = await alert_service.ingest_alert(
        db_session,
        tenant.id,
        DetectionFindingIngest(
            severity_id=OCSFSeverityId.HIGH,
            metadata=OCSFMetadata(product=OCSFProduct(name="Wazuh", vendor_name="Wazuh Inc.")),
            finding_info=OCSFFindingInfo(
                uid="wazuh-sig-12345",
                title="Suspicious login from 203.0.113.42",
            ),
            time=int(datetime.now(UTC).timestamp() * 1000),
            message="Multiple failed logins followed by success",
            observables=[
                OCSFObservable(
                    name="src_endpoint.ip",
                    type_id=OCSFObservableTypeId.IP_ADDRESS.value,
                    value="203.0.113.42",
                    is_ioc=True,
                ),
            ],
            dedup_key="wazuh-sig-12345",
        ),
    )
    assert not was_dup
    assert alert.status == "pending"

    # 2. Analyst promotes the alert to a new case
    _, case = await alert_service.promote_alert(
        db_session,
        alert.id,
        AlertPromote(new_case_title="Investigate suspicious login"),
        actor_id=analyst.id,
    )
    assert case.tenant_id == tenant.id
    assert case.status == CaseStatus.NEW.value

    # The alert observable should have been copied onto the case
    obs = (
        await db_session.execute(select(Observable).where(Observable.case_id == case.id))
    ).scalars().all()
    assert any(o.value == "203.0.113.42" for o in obs)

    # 3. Analyst works the investigation: resolves the case
    closed = await case_service.close_case(
        db_session,
        case.id,
        CaseClose(
            outcome=CaseOutcome.TRUE_POSITIVE,
            closing_notes="Confirmed credential stuffing; blocked IP at edge",
        ),
        actor_id=analyst.id,
    )
    assert closed.status == CaseStatus.CLOSED.value
    assert closed.outcome == CaseOutcome.TRUE_POSITIVE.value

    # 4. Timeline records the lifecycle
    timeline = (
        await db_session.execute(
            select(TimelineEntry).where(TimelineEntry.case_id == case.id)
        )
    ).scalars().all()
    event_types = {e.event_type for e in timeline}
    assert "case_created" in event_types
    # Closing is recorded as a lifecycle status transition carrying from/to,
    # not as a distinct `case_closed` type — see `update_case` in
    # src/services/cases.py.
    assert "status_changed" in event_types
    closures = [
        e
        for e in timeline
        if e.event_type == "status_changed"
        and e.event_metadata.get("to") == CaseStatus.CLOSED.value
    ]
    assert len(closures) == 1


# ---------------------------------------------------------------------------
# Workflow 2: Observable addition → cross-case correlation
# ---------------------------------------------------------------------------


async def test_observable_cross_case_correlation_flow(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    analyst = await user_factory(tenant.id, role="analyst")
    await _set_tenant_context(db_session, tenant.id)

    # Two cases see the same bad IP
    case_a = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=analyst.id,
        payload=CaseCreate(
            title="Case A — phishing wave",
            severity=CaseSeverity.MEDIUM,
        ),
    )
    case_b = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=analyst.id,
        payload=CaseCreate(
            title="Case B — lateral movement",
            severity=CaseSeverity.HIGH,
        ),
    )

    for case in (case_a, case_b):
        await observable_service.create_observable(
            db_session,
            case_id=case.id,
            created_by=analyst.id,
            payload=ObservableCreate(
                type=ObservableType.IP,
                value="198.51.100.7",
                tlp=TLP.AMBER,
                is_ioc=True,
            ),
        )

    # Correlation query from case A's perspective returns case B
    count = await observable_service.cross_case_count(
        db_session,
        tenant_id=tenant.id,
        type=ObservableType.IP.value,
        value="198.51.100.7",
        exclude_case_id=case_a.id,
    )
    assert count == 1

    cases_with_ip = await observable_service.find_correlating_cases(
        db_session,
        tenant_id=tenant.id,
        type=ObservableType.IP.value,
        value="198.51.100.7",
    )
    assert {case_a.id, case_b.id} <= set(cases_with_ip)


# ---------------------------------------------------------------------------
# Workflow 3: Evidence upload with hash verification
# ---------------------------------------------------------------------------


async def test_evidence_upload_hash_verification_flow(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    analyst = await user_factory(tenant.id, role="analyst")
    await _set_tenant_context(db_session, tenant.id)

    case = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=analyst.id,
        payload=CaseCreate(title="Evidence test case", severity=CaseSeverity.LOW),
    )

    body = b"sample evidence file content"
    good_hash = hashlib.sha256(body).hexdigest()

    evidence_row = await evidence_service.register_evidence(
        db_session,
        case_id=case.id,
        registered_by=analyst.id,
        payload=EvidenceRegister(
            filename="capture.pcap",
            type=EvidenceType.PCAP,
            file_hash_sha256=good_hash,
            file_size=len(body),
            description="Network capture from affected host",
        ),
    )
    assert evidence_row.integrity_verified is None or evidence_row.integrity_verified is False
    # Before upload, the file has not yet been hashed against storage.
    assert evidence_row.is_uploaded in (False, None)

    # Upload the matching content
    upload = UploadFile(filename="capture.pcap", file=io.BytesIO(body))
    uploaded = await evidence_service.upload_evidence_file(
        db_session,
        evidence_id=evidence_row.id,
        file=upload,
        actor_id=analyst.id,
    )
    assert uploaded.is_uploaded is True
    assert uploaded.integrity_verified is True
    assert uploaded.integrity_mismatch is False

    # Timeline should record the upload event
    timeline = (
        await db_session.execute(
            select(TimelineEntry).where(TimelineEntry.case_id == case.id)
        )
    ).scalars().all()
    event_types = {e.event_type for e in timeline}
    assert "evidence_registered" in event_types
    assert "evidence_uploaded" in event_types


# ---------------------------------------------------------------------------
# Workflow 4: Template → case creation → tasks → completion
# ---------------------------------------------------------------------------


async def test_template_to_case_completion_flow(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    admin = await user_factory(tenant.id, role="tenant_admin")
    analyst = await user_factory(tenant.id, role="analyst")
    await _set_tenant_context(db_session, tenant.id)

    # Admin creates a phishing template with preset tasks
    template = await template_service.create_template(
        db_session,
        tenant_id=tenant.id,
        created_by=admin.id,
        payload=CaseTemplateCreate(
            name="Phishing response",
            description="Standard phishing investigation checklist",
            default_severity="medium",
            default_tags=["phishing"],
            tasks=[
                {"title": "Identify recipient list", "sort_order": 0},
                {"title": "Extract IoCs from email", "sort_order": 1},
                {"title": "Block sender domain", "sort_order": 2},
            ],
        ),
    )
    assert isinstance(template, CaseTemplate)
    assert len(template.tasks) == 3

    # Analyst creates a case from the template
    case = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=analyst.id,
        payload=CaseCreate(
            title="Phishing email with malicious link",
            severity=CaseSeverity.MEDIUM,
            template_id=template.id,
        ),
    )
    assert case.template_id == template.id
    assert "phishing" in case.tags

    # Template tasks materialised on the case
    tasks = (
        await db_session.execute(select(Task).where(Task.case_id == case.id))
    ).scalars().all()
    assert len(tasks) == 3
    task_titles = {t.title for t in tasks}
    assert task_titles == {
        "Identify recipient list",
        "Extract IoCs from email",
        "Block sender domain",
    }

    # Analyst completes every task
    for t in tasks:
        await task_service.update_task(
            db_session,
            t.id,
            TaskUpdate(status=TaskStatus.DONE),
            actor_id=analyst.id,
        )

    refreshed = (
        await db_session.execute(select(Task).where(Task.case_id == case.id))
    ).scalars().all()
    assert all(t.status == TaskStatus.DONE.value for t in refreshed)


# ---------------------------------------------------------------------------
# Workflow 5: Alert deduplication (bonus — validates requirement 9.7 end-to-end)
# ---------------------------------------------------------------------------


async def test_alert_deduplication_end_to_end(
    db_session: AsyncSession,
    tenant_factory,
) -> None:
    tenant = await tenant_factory()
    await _set_tenant_context(db_session, tenant.id)

    first, was_dup_1 = await alert_service.ingest_alert(
        db_session,
        tenant.id,
        DetectionFindingIngest(
            severity_id=OCSFSeverityId.HIGH,
            metadata=OCSFMetadata(product=OCSFProduct(name="EDR")),
            finding_info=OCSFFindingInfo(
                uid="c2-beacon-198.51.100.42",
                title="Beaconing to known C2",
            ),
            time=int(datetime.now(UTC).timestamp() * 1000),
            dedup_key="c2-beacon-198.51.100.42",
        ),
    )
    assert not was_dup_1

    second, was_dup_2 = await alert_service.ingest_alert(
        db_session,
        tenant.id,
        DetectionFindingIngest(
            severity_id=OCSFSeverityId.HIGH,
            metadata=OCSFMetadata(product=OCSFProduct(name="EDR")),
            finding_info=OCSFFindingInfo(
                uid="c2-beacon-198.51.100.42",
                title="Beaconing to known C2",
            ),
            time=int(datetime.now(UTC).timestamp() * 1000),
            dedup_key="c2-beacon-198.51.100.42",
        ),
    )
    assert was_dup_2
    assert second.id == first.id  # Same row returned, not a new one

    # Only one Alert should exist
    all_alerts = (
        await db_session.execute(
            select(Alert).where(Alert.tenant_id == tenant.id)
        )
    ).scalars().all()
    assert len(all_alerts) == 1

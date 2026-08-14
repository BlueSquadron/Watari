"""Populate the database with a rich set of realistic sample data.

Run via ``make db-seed`` or ``python -m scripts.seed`` from the
``backend/`` directory. The script is idempotent: running it a second
time detects existing tenants by slug and skips the full flow.

What it creates
---------------
- Two tenants (Acme Corp Security, GlobalBank CSIRT)
- Per tenant:
    * 1 tenant admin, 3 analysts, 1 read-only viewer, 1 API service account
    * 3 case templates (Phishing, Malware, Data Breach)
    * 15+ cases spanning every status + severity, some from templates
    * 50+ observables (IPs with geolocation, domains, hashes, URLs, emails)
    * Assets, evidence items with registered SHA256 hashes, notes, tasks
    * Timeline entries (both automatic — from the services — and manual)
    * Enrichment sources (mock VirusTotal / AbuseIPDB / Shodan) and
      results including lat/long so the geospatial view has markers
    * ATT&CK mappings covering Initial Access, Execution, Persistence,
      Credential Access, Lateral Movement, Exfiltration
    * Alerts in pending / promoted / dismissed states
    * Sample report templates
- One platform admin account across the whole install
- Audit log entries reflecting every action taken by the seed script
  (recorded automatically by the service layer)

Default credentials (DO NOT use in production):
    Platform admin: admin / admin
    Tenant admin:   <tenant-slug>-admin / password (e.g. acme-admin)
    Analyst:        <tenant-slug>-analyst1..3 / password
    Read-only:      <tenant-slug>-viewer / password
"""

from __future__ import annotations

import asyncio
import hashlib
import pathlib
import random
import sys
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Make ``src`` importable when this file is run directly
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.auth import Role, generate_api_key, hash_api_key, hash_password
from src.db import admin_session_factory
from src.models import (
    Alert,
    Asset,
    AttackMapping,
    AttackReference,
    Case,
    CaseTemplate,
    EnrichmentResult,
    EnrichmentSource,
    Evidence,
    Note,
    NoteFolder,
    Observable,
    ReportTemplate,
    Tenant,
    User,
)
from src.services.timeline_recorder import record_event

SAMPLE_DIR = pathlib.Path(__file__).resolve().parent / "sample_data"


def _naive_utcnow() -> datetime:
    """Return a timezone-aware UTC ``datetime``.

    Schema columns are ``TIMESTAMP WITH TIME ZONE``, so we pass an
    aware datetime. The function name is kept for historical reasons
    (previous schema required naive values) but now returns tz-aware.
    """
    return datetime.now(UTC)


async def set_platform_admin(session: AsyncSession) -> None:
    """Bypass RLS for the duration of this session (platform-admin seed mode)."""
    await session.execute(text("SET LOCAL app.is_platform_admin = 'true'"))


async def seed_attack_reference(session: AsyncSession) -> None:
    existing = (
        await session.execute(select(AttackReference).limit(1))
    ).scalar_one_or_none()
    if existing is not None:
        return

    techniques = [
        ("T1566", "TA0001", "Phishing", False, None),
        ("T1566.001", "TA0001", "Spearphishing Attachment", True, "T1566"),
        ("T1078", "TA0001", "Valid Accounts", False, None),
        ("T1078.003", "TA0001", "Local Accounts", True, "T1078"),
        ("T1059", "TA0002", "Command and Scripting Interpreter", False, None),
        ("T1059.001", "TA0002", "PowerShell", True, "T1059"),
        ("T1059.004", "TA0002", "Unix Shell", True, "T1059"),
        ("T1053", "TA0002", "Scheduled Task/Job", False, None),
        ("T1547", "TA0003", "Boot or Logon Autostart Execution", False, None),
        ("T1098", "TA0003", "Account Manipulation", False, None),
        ("T1110", "TA0006", "Brute Force", False, None),
        ("T1003", "TA0006", "OS Credential Dumping", False, None),
        ("T1003.001", "TA0006", "LSASS Memory", True, "T1003"),
        ("T1021", "TA0008", "Remote Services", False, None),
        ("T1021.004", "TA0008", "SSH", True, "T1021"),
        ("T1041", "TA0010", "Exfiltration Over C2 Channel", False, None),
        ("T1567", "TA0010", "Exfiltration Over Web Service", False, None),
        ("T1486", "TA0040", "Data Encrypted for Impact", False, None),
    ]
    for technique_id, tactic_id, name, is_sub, parent in techniques:
        session.add(
            AttackReference(
                technique_id=technique_id,
                tactic_id=tactic_id,
                name=name,
                description=f"MITRE ATT&CK reference for {name}",
                is_subtechnique=is_sub,
                parent_technique_id=parent,
            )
        )
    await session.flush()


async def seed_platform_admin(session: AsyncSession, platform_tenant: Tenant) -> User:
    """The platform admin is a user rooted in the first tenant."""
    admin = (
        await session.execute(
            select(User).where(User.username == "admin")
        )
    ).scalar_one_or_none()
    if admin:
        return admin
    admin = User(
        tenant_id=platform_tenant.id,
        username="admin",
        email="admin@watari.local",
        display_name="Platform Administrator",
        role=Role.PLATFORM_ADMIN.value,
        password_hash=hash_password("admin"),
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    return admin


async def seed_tenant(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
) -> tuple[Tenant, dict[str, User], User]:
    """Create a tenant and its baseline users.

    Returns (tenant, user_map, api_service_account).
    """
    existing = (
        await session.execute(select(Tenant).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if existing is not None:
        # Re-seed is a no-op once the tenant exists; just return it.
        users = {
            u.username: u
            for u in (
                await session.execute(select(User).where(User.tenant_id == existing.id))
            )
            .scalars()
            .all()
        }
        svc = next(
            (u for u in users.values() if u.is_service_account), None
        )
        return existing, users, svc  # type: ignore[return-value]

    tenant = Tenant(name=name, slug=slug, settings={}, custom_fields_schema=[])
    session.add(tenant)
    await session.flush()

    users: dict[str, User] = {}
    admin_username = f"{slug}-admin"
    users[admin_username] = User(
        tenant_id=tenant.id,
        username=admin_username,
        email=f"{admin_username}@watari.local",
        display_name=f"{name} Tenant Admin",
        role=Role.TENANT_ADMIN.value,
        password_hash=hash_password("password"),
    )
    for i in range(1, 4):
        uname = f"{slug}-analyst{i}"
        users[uname] = User(
            tenant_id=tenant.id,
            username=uname,
            email=f"{uname}@watari.local",
            display_name=f"Analyst {i}",
            role=Role.ANALYST.value,
            password_hash=hash_password("password"),
        )
    viewer = f"{slug}-viewer"
    users[viewer] = User(
        tenant_id=tenant.id,
        username=viewer,
        email=f"{viewer}@watari.local",
        display_name=f"{name} Read-only Viewer",
        role=Role.READ_ONLY.value,
        password_hash=hash_password("password"),
    )
    for u in users.values():
        session.add(u)

    api_key_plain = generate_api_key()
    svc = User(
        tenant_id=tenant.id,
        username=f"{slug}-svc",
        email=f"{slug}-svc@service.invalid",
        display_name="Automation service account",
        role=Role.API_SERVICE_ACCOUNT.value,
        is_service_account=True,
        api_key_hash=hash_api_key(api_key_plain),
    )
    session.add(svc)
    await session.flush()

    # Stash the plaintext key in the tenant's settings so the README /
    # seed report can surface it (for demo / testing only — real
    # deployments would display this once and never persist it).
    tenant.settings = {
        "seed": {
            "service_account_username": svc.username,
            "service_account_api_key": api_key_plain,
        }
    }
    await session.flush()
    return tenant, users, svc


async def seed_templates(
    session: AsyncSession, tenant: Tenant, creator: User
) -> list[CaseTemplate]:
    """Three starter case templates per tenant."""
    templates = [
        CaseTemplate(
            tenant_id=tenant.id,
            name="Phishing investigation",
            description="Standard phishing triage workflow",
            default_severity="high",
            default_tags=["phishing", "email"],
            tasks=[
                {"title": "Extract sender / headers", "sort_order": 0},
                {"title": "Retrieve suspicious attachment(s)", "sort_order": 1},
                {"title": "Analyse links with sandbox / VirusTotal", "sort_order": 2},
                {"title": "Check mailbox rules and audit logs", "sort_order": 3},
                {"title": "Reset affected credentials", "sort_order": 4},
            ],
            custom_fields={"reporter": ""},
            created_by=creator.id,
        ),
        CaseTemplate(
            tenant_id=tenant.id,
            name="Malware on endpoint",
            description="Endpoint compromise investigation",
            default_severity="high",
            default_tags=["malware", "endpoint"],
            tasks=[
                {"title": "Isolate endpoint from network", "sort_order": 0},
                {"title": "Collect memory + disk image", "sort_order": 1},
                {"title": "Identify persistence mechanisms", "sort_order": 2},
                {"title": "Scope lateral movement", "sort_order": 3},
                {"title": "Reimage host", "sort_order": 4},
            ],
            custom_fields={},
            created_by=creator.id,
        ),
        CaseTemplate(
            tenant_id=tenant.id,
            name="Data breach response",
            description="Suspected data exfiltration or unauthorised access",
            default_severity="critical",
            default_tags=["breach", "exfiltration"],
            tasks=[
                {"title": "Identify affected data", "sort_order": 0},
                {"title": "Notify legal + privacy team", "sort_order": 1},
                {"title": "Assess regulatory obligations", "sort_order": 2},
                {"title": "Prepare customer communication", "sort_order": 3},
            ],
            custom_fields={"records_affected": 0},
            created_by=creator.id,
        ),
    ]
    for t in templates:
        session.add(t)
    await session.flush()
    return templates


async def seed_enrichment_sources(
    session: AsyncSession, tenant: Tenant
) -> list[EnrichmentSource]:
    sources = [
        EnrichmentSource(
            tenant_id=tenant.id,
            name="VirusTotal",
            type="virustotal",
            config={"api_key": "stub-replace-me"},
            supported_observable_types=[
                "ip",
                "domain",
                "url",
                "hash_md5",
                "hash_sha1",
                "hash_sha256",
            ],
            is_enabled=True,
        ),
        EnrichmentSource(
            tenant_id=tenant.id,
            name="AbuseIPDB",
            type="abuseipdb",
            config={"api_key": "stub-replace-me"},
            supported_observable_types=["ip"],
            is_enabled=True,
        ),
        EnrichmentSource(
            tenant_id=tenant.id,
            name="Shodan",
            type="shodan",
            config={"api_key": "stub-replace-me"},
            supported_observable_types=["ip", "domain"],
            is_enabled=True,
        ),
    ]
    for s in sources:
        session.add(s)
    await session.flush()
    return sources



# ---------------------------------------------------------------
# Case + children seeding
# ---------------------------------------------------------------

# (type, value, tlp, is_ioc, optional_geo)
ObservableSpec = tuple[str, str, str | None, bool, dict[str, Any] | None]


def _next_case_number(n: int) -> int:
    return n  # simple monotonic counter for seeding


# Representative external IPs with realistic lat/lng for the map
GEO_IPS: list[tuple[str, dict[str, Any]]] = [
    ("203.0.113.42", {"country_code": "US", "city": "New York", "latitude": 40.7128, "longitude": -74.0060}),
    ("198.51.100.77", {"country_code": "RU", "city": "Moscow", "latitude": 55.7558, "longitude": 37.6173}),
    ("192.0.2.14", {"country_code": "CN", "city": "Shanghai", "latitude": 31.2304, "longitude": 121.4737}),
    ("45.33.32.156", {"country_code": "DE", "city": "Berlin", "latitude": 52.5200, "longitude": 13.4050}),
    ("185.220.101.19", {"country_code": "NL", "city": "Amsterdam", "latitude": 52.3676, "longitude": 4.9041}),
    ("91.219.236.52", {"country_code": "BR", "city": "São Paulo", "latitude": -23.5505, "longitude": -46.6333}),
    ("104.244.78.122", {"country_code": "FR", "city": "Paris", "latitude": 48.8566, "longitude": 2.3522}),
    ("208.67.222.222", {"country_code": "SG", "city": "Singapore", "latitude": 1.3521, "longitude": 103.8198}),
]


async def _seed_one_case(
    session: AsyncSession,
    *,
    tenant: Tenant,
    sources: list[EnrichmentSource],
    case_number: int,
    title: str,
    status: str,
    severity: str,
    outcome: str | None,
    assignee: User,
    creator: User,
    tags: list[str],
    observables: list[ObservableSpec],
    asset_names: list[tuple[str, str, bool]],
    evidence_files: list[tuple[str, str, bytes]],
    notes: list[tuple[str, str]],
    attack_techniques: list[tuple[str, str]],
    age_days: int,
    template_id: UUID | None = None,
) -> Case:
    now = _naive_utcnow() - timedelta(days=age_days)

    case = Case(
        tenant_id=tenant.id,
        case_number=case_number,
        title=title,
        description=(
            f"Seed case '{title}' demonstrating the {severity} severity, "
            f"{status} status workflow."
        ),
        status=status,
        severity=severity,
        outcome=outcome,
        assignee_id=assignee.id,
        tags=tags,
        custom_fields={},
        template_id=template_id,
        created_by=creator.id,
        created_at=now,
        updated_at=now,
        resolved_at=now + timedelta(days=1) if status in {"resolved", "closed"} else None,
        closed_at=now + timedelta(days=2) if status == "closed" else None,
    )
    session.add(case)
    await session.flush()

    # Observables (with optional geolocation results)
    for obs_type, value, tlp, is_ioc, geo in observables:
        obs = Observable(
            tenant_id=tenant.id,
            case_id=case.id,
            type=obs_type,
            value=value,
            tlp=tlp,
            is_ioc=is_ioc,
            tags=[],
            created_by=creator.id,
        )
        session.add(obs)
        await session.flush()
        if geo and obs_type == "ip":
            # Attach an enrichment result with a geo payload
            vt_source = next((s for s in sources if s.type == "virustotal"), sources[0])
            session.add(
                EnrichmentResult(
                    tenant_id=tenant.id,
                    observable_id=obs.id,
                    source_id=vt_source.id,
                    status="success",
                    result_data={
                        "geo": geo,
                        "reputation": "malicious" if is_ioc else "neutral",
                        "last_seen": now.isoformat(),
                    },
                )
            )

    # Assets
    asset_instances: list[Asset] = []
    for asset_name, asset_type, compromised in asset_names:
        a = Asset(
            tenant_id=tenant.id,
            case_id=case.id,
            name=asset_name,
            type=asset_type,
            ip_address=f"10.0.{case_number}.{len(asset_instances) + 1}",
            is_compromised=compromised,
            created_by=creator.id,
        )
        session.add(a)
        asset_instances.append(a)
    await session.flush()

    # Evidence
    for filename, ev_type, content in evidence_files:
        session.add(
            Evidence(
                tenant_id=tenant.id,
                case_id=case.id,
                filename=filename,
                type=ev_type,
                file_hash_sha256=hashlib.sha256(content).hexdigest(),
                file_size=len(content),
                description=f"Collected as part of case {case_number}",
                is_uploaded=False,
                registered_by=creator.id,
            )
        )

    # Notes (one folder + one note per entry)
    folder = NoteFolder(
        tenant_id=tenant.id,
        case_id=case.id,
        name="Triage",
        sort_order=0,
    )
    session.add(folder)
    await session.flush()
    for title_text, content in notes:
        session.add(
            Note(
                tenant_id=tenant.id,
                case_id=case.id,
                folder_id=folder.id,
                title=title_text,
                content=content,
                author_id=assignee.id,
            )
        )

    # ATT&CK mappings
    for tactic, technique in attack_techniques:
        session.add(
            AttackMapping(
                tenant_id=tenant.id,
                case_id=case.id,
                tactic_id=tactic,
                technique_id=technique,
                created_by=creator.id,
            )
        )

    # Timeline entries: automatic recordings around the case lifecycle
    await record_event(
        session,
        tenant_id=tenant.id,
        case_id=case.id,
        event_type="case_created",
        description=f"Case {case_number}: {title}",
        category="lifecycle",
        actor_id=creator.id,
        event_timestamp=now,
    )
    if status in {"in_progress", "resolved", "closed"}:
        await record_event(
            session,
            tenant_id=tenant.id,
            case_id=case.id,
            event_type="status_changed",
            description="Status changed from new to in_progress",
            category="lifecycle",
            actor_id=assignee.id,
            event_timestamp=now + timedelta(hours=2),
            metadata={"from": "new", "to": "in_progress"},
        )
    if status in {"resolved", "closed"}:
        await record_event(
            session,
            tenant_id=tenant.id,
            case_id=case.id,
            event_type="status_changed",
            description="Status changed from in_progress to resolved",
            category="lifecycle",
            actor_id=assignee.id,
            event_timestamp=now + timedelta(days=1),
            metadata={"from": "in_progress", "to": "resolved"},
        )

    # Small burst of in-window events to exercise temporal clustering
    for i in range(3):
        await record_event(
            session,
            tenant_id=tenant.id,
            case_id=case.id,
            event_type="observable_added",
            description=f"Observable #{i + 1} captured during initial triage",
            category="observable",
            actor_id=assignee.id,
            event_timestamp=now + timedelta(minutes=i * 2),
        )

    return case


async def seed_cases(
    session: AsyncSession,
    *,
    tenant: Tenant,
    users: dict[str, User],
    templates: list[CaseTemplate],
    sources: list[EnrichmentSource],
    tenant_seed: int,
) -> list[Case]:
    """Create a realistic spread of cases for the tenant."""
    rng = random.Random(tenant_seed)
    analysts = [u for k, u in users.items() if "analyst" in k]
    creator = next(u for k, u in users.items() if k.endswith("-admin"))

    phishing_tpl = templates[0]
    malware_tpl = templates[1]
    breach_tpl = templates[2]

    statuses = ["new", "in_progress", "pending", "resolved", "closed"]
    severities = ["critical", "high", "medium", "low", "informational"]
    outcomes = ["true_positive", "false_positive", "indeterminate"]

    cases: list[Case] = []
    for n in range(1, 17):  # 16 cases per tenant
        status = statuses[n % len(statuses)]
        severity = severities[n % len(severities)]
        outcome = outcomes[n % len(outcomes)] if status == "closed" else None
        assignee = analysts[n % len(analysts)]
        template = None
        tags = []
        title = f"Investigation #{n}"
        obs_specs: list[ObservableSpec] = []
        asset_specs: list[tuple[str, str, bool]] = []
        evidence_specs: list[tuple[str, str, bytes]] = []
        note_specs: list[tuple[str, str]] = []
        attack_specs: list[tuple[str, str]] = []

        if n % 3 == 0:
            # Phishing case
            template = phishing_tpl
            title = f"Phishing campaign targeting {tenant.slug} — wave {n}"
            tags = ["phishing", "email"]
            obs_specs = [
                ("email", f"attacker{n}@badactor.example", "amber", True, None),
                ("domain", f"support-{n}.login-verify.example", "amber", True, None),
                ("url", f"https://login-verify.example/portal/{n}", "amber", True, None),
                ("hash_sha256", hashlib.sha256(f"malicious-{n}".encode()).hexdigest(), "red", True, None),
            ]
            asset_specs = [
                (f"user-{n}-mailbox", "other", False),
                (f"soc-sandbox-0{n}", "server", False),
            ]
            evidence_specs = [
                (
                    "phishing_email.eml",
                    "document",
                    f"From: attacker{n}@badactor.example\nSubject: Re: wire transfer request\n\n...".encode(),
                )
            ]
            note_specs = [
                (
                    "Initial triage",
                    pathlib.Path(SAMPLE_DIR / "incident_notes.txt").read_text(),
                ),
            ]
            attack_specs = [
                ("TA0001", "T1566"),
                ("TA0001", "T1566.001"),
            ]
        elif n % 3 == 1:
            # Malware case — these also get geolocated IPs
            template = malware_tpl
            title = f"Malware outbreak on prod-web-0{n}"
            tags = ["malware", "endpoint"]
            ip_a, geo_a = GEO_IPS[n % len(GEO_IPS)]
            ip_b, geo_b = GEO_IPS[(n + 1) % len(GEO_IPS)]
            obs_specs = [
                ("ip", ip_a, "amber", True, geo_a),
                ("ip", ip_b, "amber", True, geo_b),
                ("hash_sha256", hashlib.sha256(f"beacon-{n}".encode()).hexdigest(), "red", True, None),
                ("domain", f"c2-{n}.hosts.example", "amber", True, None),
            ]
            asset_specs = [
                (f"prod-web-0{n}", "server", True),
                (f"prod-db-0{n}", "server", False),
                (f"analyst-ws-{n}", "workstation", False),
            ]
            evidence_specs = [
                (
                    "suspicious_login.log",
                    "log_export",
                    pathlib.Path(SAMPLE_DIR / "suspicious_login.log").read_bytes(),
                ),
                (
                    f"capture-{n}.pcap",
                    "pcap",
                    pathlib.Path(
                        SAMPLE_DIR / "capture.pcap.placeholder"
                    ).read_bytes(),
                ),
            ]
            note_specs = [
                (
                    "Recon summary",
                    "# Reconnaissance\n\nAttacker attempted brute force then valid-account login. See timeline.",
                ),
            ]
            attack_specs = [
                ("TA0001", "T1078"),
                ("TA0001", "T1078.003"),
                ("TA0006", "T1110"),
                ("TA0008", "T1021.004"),
            ]
        else:
            # Data breach case
            template = breach_tpl
            title = f"Suspected data exfiltration — event {n}"
            tags = ["breach", "exfiltration"]
            ip_a, geo_a = GEO_IPS[(n + 2) % len(GEO_IPS)]
            obs_specs = [
                ("ip", ip_a, "red", True, geo_a),
                ("domain", f"exfil-{n}.badactor.example", "red", True, None),
                ("filename", f"customers-{n}.csv", "red", True, None),
            ]
            asset_specs = [
                (f"data-warehouse-{n}", "server", True),
            ]
            evidence_specs = [
                (
                    f"memory-{n}.raw",
                    "memory_dump",
                    pathlib.Path(
                        SAMPLE_DIR / "memory_snapshot.placeholder"
                    ).read_bytes(),
                ),
            ]
            note_specs = [
                (
                    "Privacy assessment",
                    "Impact assessment pending — see [[asset:data-warehouse]]",
                ),
            ]
            attack_specs = [
                ("TA0010", "T1041"),
                ("TA0010", "T1567"),
                ("TA0002", "T1059.001"),
            ]

        case = await _seed_one_case(
            session,
            tenant=tenant,
            sources=sources,
            case_number=n,
            title=title,
            status=status,
            severity=severity,
            outcome=outcome,
            assignee=assignee,
            creator=creator,
            tags=tags,
            observables=obs_specs,
            asset_names=asset_specs,
            evidence_files=evidence_specs,
            notes=note_specs,
            attack_techniques=attack_specs,
            age_days=rng.randint(0, 30),
            template_id=template.id if template else None,
        )
        cases.append(case)
    return cases


async def seed_alerts(
    session: AsyncSession,
    *,
    tenant: Tenant,
    cases: list[Case],
) -> None:
    """Seed alerts as OCSF 1.8.0 Detection Findings.

    Each row stores the full OCSF document in ``ocsf_payload`` and
    denormalized hot fields for fast listing.
    """
    now = _naive_utcnow()
    statuses = ["pending", "promoted", "dismissed"]
    # Severity 4=High (OCSF). 5=Critical every 5th alert.
    products = [
        ("Wazuh", "Wazuh Inc."),
        ("Falcon", "CrowdStrike"),
        ("Suricata", "OISF"),
        ("Proofpoint", "Proofpoint"),
    ]
    for i in range(10):
        st = statuses[i % len(statuses)]
        promoted_to = cases[i % len(cases)].id if st == "promoted" else None
        product_name, vendor = products[i % len(products)]
        severity_id = 5 if i % 5 == 0 else 4  # 5=Critical, 4=High
        severity_caption = "Critical" if severity_id == 5 else "High"
        status_id = {"pending": 1, "promoted": 2, "dismissed": 3}[st]
        status_caption = {
            "pending": "New",
            "promoted": "In Progress",
            "dismissed": "Suppressed",
        }[st]
        finding_uid = f"{product_name.lower()}-sig-{1000 + i}"
        created_at = now - timedelta(hours=i * 3)
        time_ms = int(created_at.timestamp() * 1000)

        # Build the OCSF Detection Finding document
        ocsf_payload: dict = {
            "activity_id": 1,
            "activity_name": "Create",
            "category_uid": 2,
            "category_name": "Findings",
            "class_uid": 2004,
            "class_name": "Detection Finding",
            "type_uid": 200401,
            "type_name": "Detection Finding: Create",
            "severity_id": severity_id,
            "severity": severity_caption,
            "status_id": status_id,
            "status": status_caption,
            "is_alert": True,
            "time": time_ms,
            "time_dt": created_at.isoformat(),
            "message": (
                "Automated detection matched a high-confidence rule. "
                f"Signature: {finding_uid}. Affected host: srv-{i:02d}.corp.{tenant.slug}.example."
            ),
            "metadata": {
                "version": "1.8.0",
                "product": {
                    "name": product_name,
                    "vendor_name": vendor,
                    "version": "stub-0.0",
                },
                "log_level": "WARN",
                "event_code": f"R-{1000 + i}",
            },
            "finding_info": {
                "uid": finding_uid,
                "uid_alt": f"rule:{1000 + i}",
                "title": f"Alert #{i + 1}: suspicious activity detected",
                "desc": (
                    "Rule matched on repeated failed authentications followed by a "
                    "successful login from an unusual geolocation."
                ),
                "types": ["Intrusion Detection"],
                "analytic": {
                    "name": f"{product_name} rule {1000 + i}",
                    "category": "signature",
                },
            },
            "observables": [
                {
                    "name": "src_endpoint.ip",
                    "type": "IP Address",
                    "type_id": 2,
                    "value": "203.0.113.1",
                    "is_ioc": True,
                },
                {
                    "name": "file.hashes[].value",
                    "type": "Hash",
                    "type_id": 8,
                    "value": hashlib.sha256(f"alert-{i}".encode()).hexdigest(),
                    "is_ioc": True,
                },
            ],
            "attacks": [
                {
                    "tactic": {"name": "Credential Access", "uid": "TA0006"},
                    "technique": {"name": "Brute Force", "uid": "T1110"},
                    "version": "14.1",
                }
            ],
            "confidence_id": 3,
            "confidence": "High",
            "confidence_score": 85,
            "raw_data": (
                f'{{"rule_id": "R-{1000 + i}", "signature": "{finding_uid}", '
                f'"seen_at": "{created_at.isoformat()}"}}'
            ),
        }
        if st == "dismissed":
            ocsf_payload["status_detail"] = "false_positive"

        session.add(
            Alert(
                tenant_id=tenant.id,
                severity_id=severity_id,
                source_product=product_name,
                finding_uid=finding_uid,
                title=ocsf_payload["finding_info"]["title"],
                message=ocsf_payload["message"],
                ocsf_payload=ocsf_payload,
                status=st,
                dismiss_reason=("false_positive" if st == "dismissed" else None),
                promoted_to_case_id=promoted_to,
                dedup_key=finding_uid,
                created_at=created_at,
            )
        )


async def seed_report_templates(
    session: AsyncSession, tenant: Tenant, creator: User
) -> None:
    investigation_tpl = """# Investigation report: {{ case.title }}

Case #{{ case.case_number }} · Severity: {{ case.severity }} · Status: {{ case.status }}

## Summary

{{ case.description }}

## Observables

{% for o in observables %}
- **{{ o.type }}**: `{{ o.value }}` (TLP:{{ o.tlp }}, IOC: {{ o.is_ioc }})
{% endfor %}

## Assets

{% for a in assets %}
- {{ a.name }} ({{ a.type }}){% if a.is_compromised %} — COMPROMISED{% endif %}
{% endfor %}

## Timeline

{% for t in timeline %}
- {{ t.event_timestamp }} — {{ t.event_type }}: {{ t.description }}
{% endfor %}

## ATT&CK mapping

{% for m in attack %}
- {{ m.tactic }} / {{ m.technique }}
{% endfor %}
"""

    activity_tpl = """# Activity log: {{ case.title }}

Case #{{ case.case_number }}

{% for e in audit_entries %}
- {{ e.created_at }}: {{ e.action }} by {{ e.user_id }}
{% endfor %}
"""

    session.add(
        ReportTemplate(
            tenant_id=tenant.id,
            name="Investigation Report",
            type="investigation",
            format="markdown",
            template_content=investigation_tpl,
            tag_schema=[],
            created_by=creator.id,
        )
    )
    session.add(
        ReportTemplate(
            tenant_id=tenant.id,
            name="Activity Report",
            type="activity",
            format="markdown",
            template_content=activity_tpl,
            tag_schema=[],
            created_by=creator.id,
        )
    )


async def main() -> None:
    async with admin_session_factory() as session:
        await set_platform_admin(session)
        await seed_attack_reference(session)

        tenants_spec = [
            ("Acme Corp Security", "acme"),
            ("GlobalBank CSIRT", "globalbank"),
        ]
        first_tenant: Tenant | None = None
        for i, (name, slug) in enumerate(tenants_spec):
            tenant, users, _svc = await seed_tenant(
                session, name=name, slug=slug
            )
            if first_tenant is None:
                first_tenant = tenant

            # Check whether this tenant already had seed data by counting cases.
            existing_cases = (
                await session.execute(
                    select(Case).where(Case.tenant_id == tenant.id).limit(1)
                )
            ).scalar_one_or_none()
            if existing_cases is not None:
                print(f"→ Tenant {slug} already seeded; skipping child data")
                continue

            admin = users[f"{slug}-admin"]
            templates = await seed_templates(session, tenant, admin)
            sources = await seed_enrichment_sources(session, tenant)
            cases = await seed_cases(
                session,
                tenant=tenant,
                users=users,
                templates=templates,
                sources=sources,
                tenant_seed=i + 1,
            )
            await seed_alerts(session, tenant=tenant, cases=cases)
            await seed_report_templates(session, tenant, admin)
            print(
                f"→ Seeded {tenant.name}: "
                f"{len(cases)} cases, {len(templates)} templates, "
                f"{len(sources)} enrichment sources"
            )

        if first_tenant is not None:
            await seed_platform_admin(session, first_tenant)

        await session.commit()
        print("✓ Seed complete.")
        print()
        print("Login credentials (development only):")
        print("  Platform admin: admin / admin")
        for _, slug in tenants_spec:
            print(
                f"  Tenant admin:   {slug}-admin / password  (tenant slug: {slug})"
            )
            print(f"  Analyst:        {slug}-analyst1 / password")
            print(f"  Read-only:      {slug}-viewer / password")


if __name__ == "__main__":
    asyncio.run(main())

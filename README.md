# Watari

**Collaborative Case Management Platform for Cybersecurity Teams**

Named after the faithful butler from *Death Note*, Watari serves as the quiet, reliable backbone behind every investigation — handling the operational complexity so analysts can focus on solving cases.

---

## What is Watari?

Watari is an open-source incident response and case management platform built for SOC analysts, CSIRTs, and CERTs. It provides a modern, real-time collaborative environment for managing security incidents across multiple customers (tenants), with deep support for observable enrichment, timeline reconstruction, and visual investigation tools.

### Core Capabilities

- **Case Management** — Full lifecycle from alert triage through investigation to resolution, with templates, tasks, and outcome classification
- **Multi-Tenancy** — Strict data isolation per customer using PostgreSQL Row-Level Security, with tenant-specific configuration for fields, templates, and enrichment sources
- **Observable Tracking** — Manage IPs, domains, hashes, emails, URLs, and more with format validation, TLP classification, and cross-case correlation
- **Observable Enrichment** — Query configurable external intelligence sources (VirusTotal, AbuseIPDB, MISP, Shodan) with async execution and failure isolation
- **Asset & Evidence Management** — Track compromised systems, register forensic artifacts with SHA256 integrity verification, and maintain chain-of-custody documentation
- **Case Timeline** — Automatic and manual event recording with swimlane visualization, temporal clustering, and asset-to-event linking
- **Real-Time Collaboration** — WebSocket-powered live updates, presence indicators, activity feeds, and instant notifications
- **Investigation Visualizations** — Interactive entity relationship graphs, MITRE ATT&CK heatmaps, geospatial IP mapping, and swimlane timelines
- **Report Generation** — Templated investigation and activity reports in DOCX, Markdown, and HTML
- **Module Extensibility** — Plugin architecture with pipeline modules (evidence processing) and processor modules (event-driven automation)
- **Structured Notes** — Markdown-based investigation notes with folder organization, embedded images, and internal entity linking
- **Comprehensive API** — Versioned REST API with OpenAPI documentation, API key authentication for service accounts, and full CRUD coverage

---

## Why Watari?

### Compared to Existing Tools

| Capability | TheHive | DFIR-IRIS | FIR | Catalyst | Watari |
|---|---|---|---|---|---|
| Multi-tenant isolation | Limited | Customer field | No | No | **PostgreSQL RLS** |
| **OCSF native ingest** | No | No | No | No | **OCSF 1.8.0 Detection Finding** |
| Real-time collaboration | No | No | No | No | **WebSocket live updates** |
| Swimlane timeline | No | List view | No | No | **Visual swimlane with clustering** |
| Entity relationship graph | No | Basic | No | No | **Interactive Cytoscape.js graph** |
| MITRE ATT&CK heatmap | No | No | No | No | **Built-in heatmap visualization** |
| Geospatial IP mapping | No | No | No | No | **Leaflet world map** |
| Observable enrichment | Via Cortex | Via modules | No | No | **Built-in async enrichment** |
| Evidence integrity | No | Basic | No | No | **SHA256 verification + encryption** |
| Report generation | No | Yes | No | No | **Multi-format templates** |
| Plugin system | Cortex | Python modules | No | Playbooks | **Pipeline + processor modules** |
| Command palette | No | No | No | No | **Cmd+K quick navigation** |
| Dark mode | No | No | No | No | **Default dark theme** |
| Modern stack | Scala/Play | Python/Flask | Python/Django | Go | **FastAPI + React 18** |

### Design Philosophy

Watari is built around the "faithful servant" principle:

- **Anticipatory** — The command palette, smart suggestions, and contextual actions are always ready before you ask
- **Unobtrusive** — Clean typography, generous whitespace, muted color palette with sharp accents only for critical information
- **Efficient** — Keyboard-first workflows, sub-500ms page transitions, sub-3-second search across 100K+ cases
- **Transparent** — Complete audit trail, TLP enforcement, chain-of-custody tracking

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client Layer                         │
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │   React 18 SPA      │  │  API Clients / Service   │  │
│  │   TypeScript        │  │  Accounts                │  │
│  │   Tailwind + Radix  │  │                          │  │
│  └─────────┬───────────┘  └────────────┬─────────────┘  │
└────────────┼───────────────────────────┼────────────────┘
             │                           │
             ▼                           ▼
┌─────────────────────────────────────────────────────────┐
│                  Application Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  FastAPI     │  │  WebSocket   │  │  Celery       │  │
│  │  REST API    │  │  Hub         │  │  Workers      │  │
│  │  + OpenAPI   │  │(Redis PubSub)│  │  (async jobs) │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘  │
└─────────┼─────────────────┼─────────────────┼───────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────┐
│                     Data Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ PostgreSQL 16│  │  Redis 7     │  │ S3 / MinIO    │  │
│  │ + RLS        │  │  Cache +     │  │ Evidence      │  │
│  │ + FTS        │  │  PubSub      │  │ Storage       │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Celery, Authlib (OIDC/SAML)

**Frontend:** React 18, TypeScript, Tailwind CSS, Radix UI, @visx (timeline), Cytoscape.js (graph), @nivo (charts/heatmap), react-leaflet (maps)

**Data:** PostgreSQL 16 (RLS + FTS), Redis 7, S3-compatible storage (MinIO / AWS S3)

**Testing:** pytest, Hypothesis (property-based testing), 29 formal correctness properties

---

## Quick Start

### Prerequisites

- Docker and Docker Compose (Finch also works on macOS)
- Make (optional, for convenience commands)
- Python 3.12 and Node 20+ (only if you want to run tests or linters outside containers)

### Run Locally

```bash
# Clone the repository
git clone https://github.com/your-org/watari.git
cd watari

# Copy environment configuration
cp .env.example .env

# (optional) Install local dev dependencies for tests and linters
make setup

# Start all services (API, worker, Postgres, Redis, MinIO, frontend)
make dev

# Run database migrations
make db-migrate

# Seed with sample data (2 tenants, users, cases, observables, enrichment data)
make db-seed

# Open in browser
# Frontend:  http://localhost:5173
# API docs:  http://localhost:8000/docs
# MinIO:     http://localhost:9001 (minioadmin / minioadmin)
```

### Default Credentials (Development Only)

After `make db-seed`, the following accounts are available:

| User | Password | Role |
|------|----------|------|
| `admin` | `admin` | Platform Administrator (sees every tenant) |
| `acme-admin` | `password` | Tenant Administrator (Acme Corp Security) |
| `acme-analyst1` · `-analyst2` · `-analyst3` | `password` | Analyst (Acme Corp Security) |
| `acme-viewer` | `password` | Read-Only (Acme Corp Security) |
| `globalbank-admin` · `-analyst1..3` · `-viewer` | `password` | Same roles for GlobalBank CSIRT |

### Available Make Commands

```bash
make help            # Show all available commands with descriptions
make setup           # Install backend + frontend dependencies locally
make dev             # Start the dev stack
make stop            # Stop all containers
make reset           # Full reset (containers + volumes) and rebuild
make rebuild         # Clear build cache and force-recreate containers (preserves volumes)
make logs            # Tail logs from every container
make db-migrate      # Apply Alembic migrations
make db-seed         # Populate with sample data
make db-reset        # Drop, re-migrate, and re-seed (destructive!)
make shell-db        # psql shell into the dev database
make shell-api       # Bash shell inside the API container
make test            # Run every test
make test-unit       # Backend unit tests
make test-property   # Hypothesis property tests
make test-integration # Backend integration tests (requires live Postgres)
make lint            # Ruff + mypy + TypeScript checks
make format          # Auto-format backend (Ruff) + frontend (Prettier)
make build           # Build production Docker images
make docs            # Open API documentation in a browser
```

---

## API Overview

Watari exposes a versioned REST API at `/api/v1/`. All endpoints require authentication via JWT token or API key. Full interactive documentation is available at http://localhost:8000/docs once the stack is running.

### Endpoint Structure

```
/api/v1/auth/login | /refresh | /me                    # Session authentication
/api/v1/admin/tenants                                   # Tenant administration (platform admin)
/api/v1/admin/modules                                   # Installed modules (platform admin)
/api/v1/tenants/{tenant_id}/users                       # User CRUD within a tenant
/api/v1/tenants/{tenant_id}/cases                       # Case lifecycle
/api/v1/tenants/{tenant_id}/cases/{case_id}/tasks       # Tasks
/api/v1/tenants/{tenant_id}/cases/{case_id}/observables # Observables (+ enrichment trigger)
/api/v1/tenants/{tenant_id}/cases/{case_id}/assets      # Assets
/api/v1/tenants/{tenant_id}/cases/{case_id}/evidence    # Evidence (register + upload)
/api/v1/tenants/{tenant_id}/cases/{case_id}/notes       # Notes and folders
/api/v1/tenants/{tenant_id}/cases/{case_id}/timeline    # Timeline entries + clusters
/api/v1/tenants/{tenant_id}/cases/{case_id}/reports     # Report generation
/api/v1/tenants/{tenant_id}/case-templates              # Reusable case templates
/api/v1/tenants/{tenant_id}/enrichment-sources          # External intelligence sources
/api/v1/tenants/{tenant_id}/enrichment                  # Trigger enrichment
/api/v1/tenants/{tenant_id}/alerts                      # Alert ingestion & triage
/api/v1/tenants/{tenant_id}/attack-mappings             # ATT&CK tactic/technique tagging
/api/v1/attack-reference                                # ATT&CK technique catalogue (platform)
/api/v1/tenants/{tenant_id}/search                      # Full-text search
/api/v1/tenants/{tenant_id}/dashboard                   # Metrics & widgets
/api/v1/tenants/{tenant_id}/audit-logs                  # Audit trail
/api/v1/ws                                              # WebSocket real-time channel
```

See [`backend/API_COVERAGE.md`](backend/API_COVERAGE.md) for the per-endpoint HTTP method matrix.

### Authentication

**Interactive users:** JWT tokens obtained via `/api/v1/auth/login` (username/password) or OIDC/SAML flow.

**Service accounts:** API key passed via `X-API-Key` header. Service accounts can have Analyst or Read-Only permissions but cannot access the web UI or WebSocket endpoints.

### Response Format

All responses follow a consistent envelope:

```json
{
  "data": { ... },
  "meta": {
    "page": 1,
    "page_size": 25,
    "total_count": 142,
    "total_pages": 6
  }
}
```

Errors return structured details:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Invalid observable format",
  "details": [
    { "field": "value", "message": "Not a valid IPv4 or IPv6 address", "code": "invalid_format" }
  ],
  "request_id": "req_abc123"
}
```

### Alert Ingestion Example

Watari's alert API speaks [OCSF 1.8.0 Detection Finding](https://schema.ocsf.io/1.8.0/classes/detection_finding). Any OCSF-compliant producer (AWS Security Hub, Splunk, CrowdStrike, custom detectors) can POST findings directly:

```bash
curl -X POST http://localhost:8000/api/v1/tenants/{tenant_id}/alerts \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "activity_id": 1,
    "category_uid": 2,
    "class_uid": 2004,
    "severity_id": 4,
    "time": 1777189013919,
    "message": "8 failed SSH logins followed by a success from 203.0.113.42",
    "metadata": {
      "version": "1.8.0",
      "product": { "name": "Wazuh", "vendor_name": "Wazuh Inc." }
    },
    "finding_info": {
      "uid": "wazuh-5763-203.0.113.42",
      "title": "Brute force SSH detected"
    },
    "observables": [
      { "name": "src_endpoint.ip", "type_id": 2, "value": "203.0.113.42", "is_ioc": true },
      { "name": "dst_endpoint.hostname", "type_id": 1, "value": "prod-web-01" }
    ],
    "attacks": [
      { "tactic": { "uid": "TA0006" }, "technique": { "uid": "T1110" } }
    ],
    "dedup_key": "ssh-brute-203.0.113.42"
  }'
```

For step-by-step walkthroughs of creating alerts, running enrichment, promoting to cases, and generating reports, see the [integration guide](docs/integration.md).

---

## Integration

### Alert Sources

Watari accepts alerts from any tool that can make HTTP POST requests. Common integrations:

- **Wazuh** — Forward alerts via webhook or custom integration script
- **Suricata / Snort** — Pipe alerts through a log shipper to Watari's alert API
- **SIEM (Splunk, Elastic, QRadar)** — Use alert actions or webhooks to push to Watari
- **Email** — Build a lightweight email-to-alert bridge using the REST API

### Enrichment Sources

Configure per-tenant enrichment sources that Watari queries when analysts request observable enrichment:

- **VirusTotal** — IP, domain, hash, URL reputation
- **AbuseIPDB** — IP abuse reports and confidence scores
- **Shodan** — IP service/port information
- **MISP** — Threat intelligence sharing platform correlation
- **IntelOwl** — Multi-analyzer observable analysis
- **Custom** — Any HTTP-based intelligence API via the module system

### SOAR Integration

Watari complements SOAR platforms rather than replacing them:

- **Shuffle** — Use Watari's API to create cases from Shuffle workflows, push enrichment results back
- **Tracecat** — Trigger Watari case creation from Tracecat playbooks
- **n8n** — Build automation workflows that interact with Watari's full API

### Identity Providers

- **OIDC** — Keycloak, Okta, Azure AD, Google Workspace
- **SAML** — Any SAML 2.0 compliant IdP

### Module Development

Extend Watari with custom Python modules:

```python
from watari.modules import BaseModule, ModuleAPI

class MyEnrichmentModule(BaseModule):
    async def execute(self, context: ModuleAPI, config: dict, payload: dict) -> dict:
        observable = payload["observable"]
        # Query your internal threat intel platform
        result = await self.query_internal_tip(observable["value"])
        # Write enrichment result back to the case
        await context.add_timeline_entry(
            payload["case_id"],
            {"event_type": "enrichment", "description": f"Internal TIP: {result['verdict']}"}
        )
        return {"status": "success", "data": result}
```

---

## User Roles

| Role | Scope | Capabilities |
|------|-------|-------------|
| Platform Administrator | All tenants | Manage tenants, platform settings, modules, all data access |
| Tenant Administrator | Single tenant | Manage users, templates, enrichment sources, dashboards within tenant |
| Analyst | Single tenant | Create/manage cases, tasks, observables, assets, evidence, notes, run enrichment, generate reports |
| Read-Only Viewer | Single tenant | View cases, dashboards, reports — no modifications |
| API Service Account | Single tenant | API-only access (no UI), Analyst or Read-Only permissions, for automation |

---

## Visualizations

### Swimlane Timeline
Events plotted on a time axis, grouped into lanes by asset, analyst, or event category. Zoom, pan, and temporal cluster highlighting help analysts spot bursts of activity.

### Entity Relationship Graph
Interactive force-directed graph showing connections between observables, assets, and timeline events. Cross-case correlation reveals shared IOCs across investigations.

### MITRE ATT&CK Heatmap
Color-coded matrix mapping cases to ATT&CK tactics and techniques. Click any cell to see linked cases and observables. Filter by date, severity, or status.

### Geospatial Map
World map plotting IP and domain observables using enrichment geolocation data. Geographic clustering at low zoom levels, with marker color/size reflecting TLP, IOC status, or threat score.

### Dashboard
Configurable widgets: open cases by severity, cases by status, MTTR trends, analyst workload, outcome distribution. All filterable by date range.

---

## Project Structure

```
watari/
├── backend/
│   ├── src/
│   │   ├── api/            # FastAPI routes and middleware
│   │   │   └── routers/    # Route modules per entity
│   │   ├── auth/           # JWT, RBAC, OIDC, SAML, API keys
│   │   ├── models/         # SQLAlchemy 2.0 models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic
│   │   ├── realtime/       # WebSocket hub
│   │   ├── worker/         # Celery tasks
│   │   ├── modules/        # Plugin system
│   │   └── utils/          # Shared utilities
│   ├── alembic/            # Database migrations
│   ├── tests/              # pytest + Hypothesis
│   ├── scripts/            # Seed data, utilities
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   │   ├── layout/     # App shell, sidebar, topbar
│   │   │   ├── cases/      # Case-specific components
│   │   │   ├── visualizations/ # Timeline, graph, heatmap, map
│   │   │   └── common/     # Shared UI components
│   │   ├── pages/          # Route pages
│   │   ├── api/            # API client and React Query hooks
│   │   ├── stores/         # Zustand state stores
│   │   ├── hooks/          # Custom React hooks
│   │   ├── realtime/       # WebSocket client
│   │   └── types/          # TypeScript type definitions
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

---

## License

TBD

---

## Documentation

- [Integration guide](docs/integration.md) — end-to-end walkthroughs: authentication, alert ingestion, enrichment, case promotion, evidence upload, report generation, WebSocket streaming
- [API coverage reference](backend/API_COVERAGE.md) — every endpoint with its HTTP method and expected behavior
- Swagger UI — live OpenAPI explorer at http://localhost:8000/docs when the stack is running
- ReDoc — alternative API reference at http://localhost:8000/redoc
- [Design doc](.kiro/specs/watari-case-management/design.md) — architectural decisions and the 29 correctness properties
- [Requirements](.kiro/specs/watari-case-management/requirements.md) — 23 functional requirements
- [Implementation plan](.kiro/specs/watari-case-management/tasks.md) — 51-task build plan showing what's implemented

---

## Acknowledgments

Watari draws inspiration from these excellent projects:

- [TheHive](https://strangebee.com/thehive/) — The original open-source security incident response platform
- [Cortex](https://github.com/TheHive-Project/Cortex) — Observable analysis and active response engine
- [DFIR-IRIS](https://dfir-iris.org/) — Collaborative incident response platform with timeline and evidence management
- [FIR](https://github.com/certsocietegenerale/FIR) — Fast Incident Response by CERT Société Générale

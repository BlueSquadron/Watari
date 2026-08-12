# Watari Integration Guide

This guide walks through integrating external systems with Watari using the REST API. Every example uses `curl` for clarity, but the same calls work from any HTTP client (Python `httpx`, `requests`, Node `fetch`, PowerShell `Invoke-RestMethod`, etc.).

All examples assume a local stack running on `http://localhost:8000`. Replace the host with your production URL in real deployments.

## Table of contents

1. [Authentication](#1-authentication)
2. [Service accounts and API keys](#2-service-accounts-and-api-keys)
3. [Ingesting alerts](#3-ingesting-alerts)
4. [Reading and filtering alerts](#4-reading-and-filtering-alerts)
5. [Deduplication](#5-deduplication)
6. [Triaging alerts: promote or dismiss](#6-triaging-alerts-promote-or-dismiss)
7. [Working with cases](#7-working-with-cases)
8. [Observables and enrichment](#8-observables-and-enrichment)
9. [Uploading evidence](#9-uploading-evidence)
10. [Generating reports](#10-generating-reports)
11. [Full-text search](#11-full-text-search)
12. [Real-time updates over WebSocket](#12-real-time-updates-over-websocket)
13. [Common errors and how to read them](#13-common-errors-and-how-to-read-them)
14. [End-to-end scripted example](#14-end-to-end-scripted-example)

---

## 1. Authentication

Watari supports two authentication modes:

| Mode | Who | Header | How to obtain |
|---|---|---|---|
| JWT bearer | Human users, long-running session-based clients | `Authorization: Bearer <token>` | `POST /api/v1/auth/login` |
| API key | Service accounts, automation | `X-API-Key: <key>` | Created by a tenant admin (see §2) |

### Logging in with username/password

```bash
curl -sS -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

Successful response:

```json
{
  "data": {
    "access_token": "eyJhbGc...",
    "refresh_token": "eyJhbGc...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "aed5523f-...",
      "tenant_id": "f221f552-...",
      "username": "admin",
      "role": "platform_admin",
      "...": "..."
    }
  },
  "meta": null
}
```

Capture the `access_token` and use it on every subsequent request:

```bash
export TOKEN="eyJhbGc..."
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me
```

The access token expires after 60 minutes by default. Exchange the refresh token for a new access token:

```bash
curl -sS -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}"
```

### Getting the current tenant

The tenant ID is embedded in every JWT and returned in `data.user.tenant_id` at login. Platform admins belong to a "platform" tenant but can access every tenant they choose. The full tenant list is at:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/admin/tenants
```

---

## 2. Service accounts and API keys

Service accounts are API-only users suited to automation. They cannot log into the web UI or connect to WebSockets. Create one from the UI (Admin → Users → New service account) or with the REST API:

```bash
curl -sS -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/users/service-accounts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "wazuh-ingest",
    "display_name": "Wazuh alert ingester",
    "role": "analyst"
  }'
```

The response contains the API key **exactly once**. Store it securely:

```json
{
  "data": {
    "user": { "id": "...", "username": "wazuh-ingest", "is_service_account": true },
    "api_key": "wtr_sk_Z8f9...X0"
  }
}
```

Use it on every subsequent request:

```bash
curl -H "X-API-Key: wtr_sk_Z8f9...X0" http://localhost:8000/api/v1/tenants/$TENANT_ID/alerts
```

If the key is lost, rotate it:

```bash
curl -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/users/$USER_ID/rotate-api-key" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 3. Ingesting alerts

Watari's alert API speaks **OCSF 1.8.0 Detection Finding** (`class_uid` 2004, `category_uid` 2). Producers POST a Detection Finding document; Watari validates, stores, and returns the same shape enriched with a small `watari` envelope for workflow state.

Reference: https://schema.ocsf.io/1.8.0/classes/detection_finding

`POST /api/v1/tenants/{tenant_id}/alerts` creates a new finding in Watari-workflow state `pending` (OCSF `status_id: 1 "New"`).

### Minimal valid Detection Finding

These seven fields are the absolute minimum Watari will accept:

```bash
curl -sS -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/alerts" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "activity_id": 1,
    "category_uid": 2,
    "class_uid": 2004,
    "severity_id": 4,
    "time": 1777189013919,
    "metadata": {
      "version": "1.8.0",
      "product": { "name": "Wazuh", "vendor_name": "Wazuh Inc." }
    },
    "finding_info": {
      "uid": "wazuh-5763-203.0.113.42",
      "title": "Brute force SSH detected"
    }
  }'
```

### Production-grade Detection Finding

A realistic payload from a detection system:

```bash
curl -sS -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/alerts" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "activity_id": 1,
    "activity_name": "Create",
    "category_uid": 2,
    "category_name": "Findings",
    "class_uid": 2004,
    "class_name": "Detection Finding",
    "type_uid": 200401,
    "type_name": "Detection Finding: Create",
    "severity_id": 4,
    "severity": "High",
    "time": 1777189013919,
    "time_dt": "2026-04-26T10:16:53.919Z",
    "is_alert": true,
    "message": "8 failed SSH logins in 30 seconds on prod-web-01 from 203.0.113.42",
    "metadata": {
      "version": "1.8.0",
      "product": {
        "name": "Wazuh",
        "vendor_name": "Wazuh Inc.",
        "version": "4.7.0"
      },
      "log_level": "WARN",
      "event_code": "5763"
    },
    "finding_info": {
      "uid": "wazuh-5763-203.0.113.42-20260426",
      "uid_alt": "rule:5763",
      "title": "Brute force SSH from 203.0.113.42",
      "desc": "Authentication rule threshold exceeded from external IP",
      "types": ["Intrusion Detection"],
      "analytic": {
        "name": "Wazuh rule 5763",
        "category": "signature",
        "version": "1.0"
      }
    },
    "confidence_id": 3,
    "confidence": "High",
    "confidence_score": 92,
    "observables": [
      {
        "name": "src_endpoint.ip",
        "type": "IP Address",
        "type_id": 2,
        "value": "203.0.113.42",
        "is_ioc": true,
        "tlp": "amber"
      },
      {
        "name": "dst_endpoint.hostname",
        "type": "Hostname",
        "type_id": 1,
        "value": "prod-web-01"
      }
    ],
    "attacks": [
      {
        "tactic": { "name": "Credential Access", "uid": "TA0006" },
        "technique": { "name": "Brute Force", "uid": "T1110" },
        "version": "14.1"
      }
    ],
    "raw_data": "Apr 26 10:16:53 prod-web-01 sshd[4812]: Failed password for invalid user admin from 203.0.113.42 port 41234 ssh2",
    "dedup_key": "ssh-brute-203.0.113.42"
  }'
```

### Required fields (OCSF spec enforced by Watari)

| Field | Type | Notes |
|---|---|---|
| `activity_id` | integer enum | `1`=Create, `2`=Update, `3`=Close, `99`=Other |
| `category_uid` | integer | must be `2` (Findings) |
| `class_uid` | integer | must be `2004` (Detection Finding) |
| `severity_id` | integer enum | `0`=Unknown · `1`=Informational · `2`=Low · `3`=Medium · `4`=High · `5`=Critical · `6`=Fatal · `99`=Other |
| `time` | integer | event timestamp in epoch **milliseconds** |
| `metadata` | object | must contain `version` and `product.name` |
| `finding_info` | object | must contain `uid` (unique identifier from the producer) |

Watari auto-populates `type_uid`, `activity_name`, and the `severity` caption if they're omitted.

### Recommended fields (accepted, surfaced in the UI)

| Field | Type | Why |
|---|---|---|
| `message` | string | Long-form description, shown in the UI |
| `is_alert` | boolean | Watari assumes `true`; use `false` for informational records |
| `finding_info.title` | string | The short label rendered in the queue |
| `finding_info.uid_alt` | string | Alternative producer id; used for dedup if `dedup_key` absent |
| `confidence_id` | integer | `0`=Unknown · `1`=Low · `2`=Medium · `3`=High · `99`=Other |
| `confidence_score` | integer 0–100 | Producer's own score |
| `observables[]` | array | See observable type map below |
| `attacks[]` | array | MITRE ATT&CK attributions — Watari auto-creates case mappings on promotion |
| `raw_data` | string | Raw event from the producer, verbatim |

### Watari extensions

| Field | Purpose |
|---|---|
| `dedup_key` | String used for pending-state deduplication. See §5. |

### OCSF observable `type_id` enum

Watari accepts all OCSF observable type IDs but only maps the ones below to internal observable types when an alert is promoted to a case:

| OCSF `type_id` | OCSF name | Watari type |
|---|---|---|
| `1` | Hostname | `hostname` |
| `2` | IP Address | `ip` |
| `5` | Email Address | `email` |
| `6` | URL String | `url` |
| `7` | File Name | `filename` |
| `8` | Hash | `hash_md5` / `hash_sha1` / `hash_sha256` (inferred from length) |
| `23` | URL | `url` |
| `22` | Email | `email` |
| `28` | Registry Key | `registry_key` |

Observables with unmapped type_ids are still stored on the finding and visible in the UI, but they're skipped during the promote-to-case copy (there's no internal type to map them to).

### Non-OCSF observable fields Watari honours

Watari's UI understands two extra fields on each observable — `is_ioc: bool` and `tlp: "red"|"amber"|"green"|"clear"` — that OCSF doesn't define. Include them if you want the resulting case observable to carry the IOC/TLP flags.

---

## 4. Reading and filtering alerts

```bash
# All alerts for a tenant
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/alerts"

# Pending alerts only (Watari workflow status)
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/alerts?status=pending"

# High-severity findings (OCSF severity_id = 4) from Wazuh in the last week
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/alerts?severity_id=4&product=Wazuh&created_after=2026-04-20T00:00:00Z"

# A single alert (full OCSF Detection Finding plus Watari envelope)
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/alerts/$ALERT_ID"
```

### Response shape

The response for both list and get is a full OCSF 1.8.0 Detection Finding with an extra `watari` object holding workflow state:

```json
{
  "data": {
    "activity_id": 1, "activity_name": "Create",
    "category_uid": 2, "category_name": "Findings",
    "class_uid": 2004, "class_name": "Detection Finding",
    "type_uid": 200401,
    "severity_id": 4, "severity": "High",
    "status_id": 1, "status": "New",
    "time": 1777189013919,
    "metadata": { "version": "1.8.0", "product": { "name": "Wazuh" } },
    "finding_info": { "uid": "...", "title": "..." },
    "observables": [ ... ],
    "attacks": [ ... ],
    "message": "...",
    "watari": {
      "id": "aed5523f-...",
      "tenant_id": "f221f552-...",
      "workflow_status": "pending",
      "dismiss_reason": null,
      "promoted_to_case_id": null,
      "dedup_key": "ssh-brute-203.0.113.42",
      "created_at": "2026-04-26T10:16:53Z",
      "updated_at": "2026-04-26T10:16:53Z"
    }
  }
}
```

Watari overwrites `status_id` / `status` based on the current workflow state: `pending` → `1 "New"`, `promoted` → `2 "In Progress"`, `dismissed` → `3 "Suppressed"`.

### Filter parameters

| Parameter | Values |
|---|---|
| `status` | Watari workflow status: `pending` · `promoted` · `dismissed` |
| `severity_id` | OCSF severity: `1`=Informational … `5`=Critical … `99`=Other |
| `product` | OCSF `metadata.product.name`, exact match |
| `created_after` / `created_before` | ISO 8601 timestamps |
| `page` · `page_size` | integers; default page 1, 25 per page |

Pagination metadata is returned in `meta` on every list endpoint.

---

## 5. Deduplication

When an incoming Detection Finding matches an existing `pending` alert for the same tenant on **effective dedup key**, Watari returns the existing row instead of creating a new one. Promoted or dismissed alerts never dedup — re-detection after triage creates a fresh alert.

**Effective dedup key** (first non-null wins):

1. `dedup_key` (Watari extension)
2. `finding_info.uid_alt`
3. `finding_info.uid`

Because `finding_info.uid` is required in OCSF, dedup is always active — repeatedly POSTing the same Detection Finding collapses into one pending alert automatically.

Override the default when you want a coarser bucket. For example, to dedup on the attacker IP rather than the rule-hit UID:

```json
{
  "finding_info": { "uid": "wazuh-5763-20260426-12345" },
  "dedup_key": "ssh-brute-203.0.113.42"
}
```

Typical dedup strategies:

- `{source}-{rule_id}-{target_ip}` — Wazuh / EDR signature + target
- `{hash}` — malware hash pinning
- `{user}-{event_type}-{hour}` — collapse repeated activity bursts

---

## 6. Triaging alerts: promote or dismiss

Every pending alert ends in one of two states.

### Promote to a new case

```bash
curl -sS -X POST \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/alerts/$ALERT_ID/promote" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"new_case_title":"Investigate SSH brute force on prod-web-01"}'
```

The response is the newly created `Case`. All observables on the alert are copied onto the case. The alert's status becomes `promoted` and its `promoted_to_case_id` points at the new case.

### Promote into an existing case

If an alert looks related to an in-flight investigation, merge rather than create:

```bash
curl -sS -X POST \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/alerts/$ALERT_ID/promote" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"case_id\":\"$EXISTING_CASE_ID\"}"
```

### Dismiss with a reason

```bash
curl -sS -X POST \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/alerts/$ALERT_ID/dismiss" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"false_positive"}'
```

Any string ≤ 255 chars is accepted as a reason. The UI suggests five canonical values — `duplicate`, `false_positive`, `known_behavior`, `insufficient_context`, `other` — but you can use anything meaningful to your workflow.

---

## 7. Working with cases

### Creating a case from scratch

```bash
curl -sS -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Phishing campaign against finance team",
    "description": "Multiple users reported spoofed invoice emails",
    "severity": "high",
    "tags": ["phishing", "finance"]
  }'
```

### Creating a case from a template

First list available templates:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/case-templates"
```

Then reference the template's UUID at creation time:

```bash
curl -sS -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"Phishing wave — April\",
    \"severity\": \"medium\",
    \"template_id\": \"$TEMPLATE_ID\"
  }"
```

Applying a template auto-creates the template's task list on the new case and merges any default tags and custom fields.

### Updating status, severity, and assignee

```bash
curl -X PATCH "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"in_progress","assignee_id":"..."}'
```

### Closing a case

```bash
curl -X POST "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/close" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"outcome":"true_positive","closing_notes":"Credential stuffing confirmed. IP blocked at edge."}'
```

Valid outcomes: `true_positive`, `false_positive`, `indeterminate`, `not_applicable`.

---

## 8. Observables and enrichment

### Adding an observable to a case

```bash
curl -sS -X POST \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/observables" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ip",
    "value": "198.51.100.7",
    "tlp": "amber",
    "is_ioc": true
  }'
```

### Bulk add

```bash
curl -sS -X POST \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/observables/bulk" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "observables": [
      {"type": "ip", "value": "198.51.100.7"},
      {"type": "hash_sha256", "value": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
    ]
  }'
```

Invalid observables in a bulk call are returned per-entry so you can retry only the bad ones.

### Running enrichment

Trigger enrichment across all configured sources for one or more observables:

```bash
curl -sS -X POST \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/enrichment/trigger" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"observable_ids\": [\"$OBS_ID_1\", \"$OBS_ID_2\"]
  }"
```

Enrichment runs asynchronously via Celery. Read the results back from:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/observables/$OBS_ID/enrichment"
```

A result per source is stored with a timestamp, status (`success` · `error` · `timeout`), and the raw data the source returned. Failures don't block success from other sources.

### Cross-case correlation

Find every case in the tenant that references the same observable value:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/observables/$OBS_ID/correlations"
```

---

## 9. Uploading evidence

Evidence is a two-step flow: register the metadata (including the expected SHA256), then upload the binary payload. Watari computes the hash on upload and flags integrity mismatches.

### Step 1: register

```bash
curl -sS -X POST \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/evidence" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "capture.pcap",
    "type": "pcap",
    "file_hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "file_size": 524288,
    "description": "Network capture from affected host"
  }'
```

Valid `type` values: `disk_image`, `memory_dump`, `log_export`, `pcap`, `document`, `other`.

The response contains an `evidence_id` to use in the next call.

### Step 2: upload

```bash
curl -sS -X POST \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/evidence/$EVIDENCE_ID/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./capture.pcap"
```

The response includes `integrity_verified: true/false`. If the uploaded content's SHA256 doesn't match what was declared at registration, a timeline entry records the mismatch and the evidence is flagged in the UI.

### Uploading password-protected evidence

Add a form field `password`:

```bash
curl -X POST \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/evidence/$EVIDENCE_ID/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./memory.dmp" \
  -F "password=topsecret"
```

The content is encrypted at rest and can only be downloaded with the same password.

### Downloading

```bash
curl -L -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/evidence/$EVIDENCE_ID/download" \
  -o capture.pcap
```

For encrypted files append `?password=topsecret`.

---

## 10. Generating reports

Reports combine templates (Markdown, DOCX, or HTML) with case data. Templates live at the tenant level; reports belong to a case.

### List templates

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/report-templates"
```

### Generate a report

```bash
curl -sS -X POST \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/reports/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"template_id\": \"$TEMPLATE_ID\",
    \"format\": \"docx\"
  }"
```

Generation runs asynchronously via Celery. Poll the report:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/reports/$REPORT_ID"
```

Once `storage_path` is populated the file is ready. Download:

```bash
curl -L -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/cases/$CASE_ID/reports/$REPORT_ID/download" \
  -o report.docx
```

Templates use [Jinja2](https://jinja.palletsprojects.com/) syntax. The case, its observables, assets, timeline, notes, tasks, and ATT&CK mappings are exposed as template variables.

---

## 11. Full-text search

```bash
curl -sS -X POST \
  "http://localhost:8000/api/v1/tenants/$TENANT_ID/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"phishing invoice","entity_types":["case","note","observable"]}'
```

Search is powered by PostgreSQL full-text search with `pg_trgm` fuzzy matching. Results include entity type, title, snippet, and the ID of the containing case so the frontend can navigate directly.

---

## 12. Real-time updates over WebSocket

Watari pushes case and tenant events over WebSocket in near real time. Connect at `ws://localhost:8000/api/v1/ws?token=<JWT>`.

```js
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws?token=${accessToken}`);

ws.onopen = () => {
  // Subscribe to a case channel
  ws.send(JSON.stringify({ type: "subscribe", channel: `case:${caseId}` }));

  // Or a tenant-wide activity feed
  ws.send(JSON.stringify({ type: "subscribe", channel: `tenant:${tenantId}` }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  // msg.type: case_updated | observable_added | task_completed | evidence_uploaded | ...
  // msg.data: entity-specific payload
  // msg.actor: { user_id, display_name }
  // msg.timestamp: ISO 8601
  console.log(msg);
};
```

WebSocket is **not** available to service accounts — use polling instead (a short GET on the case endpoint combined with `updated_at` comparison works well for lightweight change detection).

---

## 13. Common errors and how to read them

Every error response follows the same envelope:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Invalid observable format",
  "details": [
    {"field": "value", "message": "Not a valid IPv4 address", "code": "invalid_format"}
  ],
  "request_id": "a3c1f8de-..."
}
```

| HTTP | `code` | What it means | What to do |
|---|---|---|---|
| 400 | `VALIDATION_ERROR` | Missing or malformed field | Check `details` for the offending field |
| 401 | `UNAUTHORIZED` | Missing/invalid token or API key | Refresh or re-authenticate |
| 403 | `FORBIDDEN` | Token is valid but role lacks permission, or you're addressing another tenant | Verify the user role; check the tenant in the URL matches your token |
| 404 | `NOT_FOUND` | Resource doesn't exist or is filtered out by RLS | Check IDs; make sure the token's tenant matches |
| 409 | `CONFLICT` | Uniqueness violation (e.g. duplicate asset name in a case) | Use a different identifier |
| 422 | `VALIDATION_ERROR` | Pydantic validation (wrong type, out-of-range, enum mismatch) | Check `details` |
| 429 | `RATE_LIMITED` | Too many requests | Respect the `Retry-After` header |
| 500 | `INTERNAL_ERROR` | Unexpected server error | Capture `request_id` and share it with support |

The `request_id` is unique per request and also appears in the `X-Request-ID` response header. Server logs join on it.

---

## 14. End-to-end scripted example

This script demonstrates the full ingest → triage → investigate → close flow from a shell:

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE="http://localhost:8000/api/v1"

# 1. Log in as a tenant admin
LOGIN=$(curl -sS -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"acme-admin","password":"password"}')
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
TENANT=$(echo "$LOGIN" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['user']['tenant_id'])")
AUTH_HEADER="Authorization: Bearer $TOKEN"

# 2. Ingest an OCSF Detection Finding from our "detector"
NOW_MS=$(python3 -c "import time; print(int(time.time()*1000))")
ALERT=$(curl -sS -X POST "$BASE/tenants/$TENANT/alerts" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d "{
    \"activity_id\": 1,
    \"category_uid\": 2,
    \"class_uid\": 2004,
    \"severity_id\": 4,
    \"time\": $NOW_MS,
    \"message\": \"Outbound connection to known C2\",
    \"metadata\": {
      \"version\": \"1.8.0\",
      \"product\": { \"name\": \"sample-script\", \"vendor_name\": \"Watari docs\" }
    },
    \"finding_info\": {
      \"uid\": \"sample-script-c2-203.0.113.42\",
      \"title\": \"Suspicious outbound connection\"
    },
    \"observables\": [
      { \"name\": \"dst_endpoint.ip\", \"type_id\": 2, \"value\": \"203.0.113.42\", \"is_ioc\": true }
    ],
    \"attacks\": [
      { \"tactic\": { \"name\": \"Command and Control\", \"uid\": \"TA0011\" },
        \"technique\": { \"name\": \"Application Layer Protocol\", \"uid\": \"T1071\" } }
    ],
    \"dedup_key\": \"sample-script-c2-203.0.113.42\"
  }")
ALERT_ID=$(echo "$ALERT" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['watari']['id'])")
echo "Alert ingested: $ALERT_ID"

# 3. Promote the alert to a new case
PROMOTED=$(curl -sS -X POST "$BASE/tenants/$TENANT/alerts/$ALERT_ID/promote" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"new_case_title":"Investigate outbound connection to 203.0.113.42"}')
CASE_ID=$(echo "$PROMOTED" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['id'])")
echo "Case created:   $CASE_ID"

# 4. Add a second observable and request enrichment
OBS=$(curl -sS -X POST "$BASE/tenants/$TENANT/cases/$CASE_ID/observables" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"type":"domain","value":"malicious.example.com","is_ioc":true}')
OBS_ID=$(echo "$OBS" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['id'])")
echo "Observable added: $OBS_ID"

curl -sS -X POST "$BASE/tenants/$TENANT/enrichment/trigger" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d "{\"observable_ids\":[\"$OBS_ID\"]}" > /dev/null
echo "Enrichment triggered"

# 5. Close the case
curl -sS -X POST "$BASE/tenants/$TENANT/cases/$CASE_ID/close" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{"outcome":"true_positive","closing_notes":"C2 activity confirmed. Egress rule deployed."}' > /dev/null
echo "Case closed"

# 6. Show the final case
curl -sS "$BASE/tenants/$TENANT/cases/$CASE_ID" -H "$AUTH_HEADER" | python3 -m json.tool
```

Save as `watari-smoke.sh`, `chmod +x`, and run it after `make db-seed`. You should see an alert promoted, a case created with the original observable copied plus a new one added, enrichment queued, and the case closed as a true positive — all in a few seconds.

---

## Further reading

- [`backend/API_COVERAGE.md`](../backend/API_COVERAGE.md) — endpoint-by-endpoint reference
- Live Swagger UI at http://localhost:8000/docs
- [`.kiro/specs/watari-case-management/design.md`](../.kiro/specs/watari-case-management/design.md) — architectural rationale, RLS model, 29 correctness properties
- [`.kiro/specs/watari-case-management/requirements.md`](../.kiro/specs/watari-case-management/requirements.md) — 23 functional requirements in EARS/Given-When-Then form

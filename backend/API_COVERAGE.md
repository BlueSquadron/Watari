# Watari API — Endpoint Coverage Reference

All endpoints use the `/api/v1/` prefix. Responses follow the standard envelope:
- Success: `{ "data": T, "meta"?: PaginationMeta }`
- Error: `{ "error": { "code": string, "message": string, "details": object, "request_id": string } }`

Authentication: JWT bearer in `Authorization` header for interactive users, `X-API-Key` header for service accounts.

Tenant scoping: Every tenant-scoped path includes `/tenants/{tenant_id}/` — Row-Level Security enforces isolation at the database layer, and the routers additionally check that `auth.tenant_id == tenant_id` unless the caller is a platform admin.

Auto-generated OpenAPI documentation is available at runtime: http://localhost:8000/docs (Swagger UI) and http://localhost:8000/redoc (ReDoc).

## Authentication (`/api/v1/auth`)
- `POST /login` — username+password → access + refresh token pair
- `POST /refresh` — refresh token → new access token
- `POST /logout` — invalidate current session
- `GET /me` — current `AuthContext` (user_id, tenant_id, roles, permissions)
- `GET /oidc/login`, `GET /oidc/callback` — OIDC SSO flow
- `POST /saml/acs` — SAML assertion consumer

## Platform administration

### Tenants (`/api/v1/admin/tenants`, platform admin only)
- `GET` — list tenants (paginated)
- `POST` — create tenant
- `GET /{tenant_id}` — read tenant (tenant admins may read their own)
- `PATCH /{tenant_id}` — update tenant settings / custom fields
- `DELETE /{tenant_id}` — remove tenant (cascade)

### Modules (`/api/v1/admin/modules`, platform admin only)
- `GET` — list installed modules
- `POST` — register a new module
- `PATCH /{module_id}` — enable/disable, update config
- `DELETE /{module_id}` — remove module
- `GET /{module_id}/executions` — execution history

## Tenant-scoped resources

All paths below are prefixed `/api/v1/tenants/{tenant_id}`.

### Users (`/users`)
- `GET /` — list users
- `POST /` — create user (tenant admin)
- `GET /{user_id}` — read
- `PATCH /{user_id}` — update
- `DELETE /{user_id}` — deactivate
- `POST /service-accounts` — create service account (returns API key once)
- `POST /{user_id}/rotate-api-key` — rotate key

### Cases (`/cases`)
- `GET /` — list (filters: status, severity, assignee, tag, search)
- `POST /` — create (applies template if `template_id` present)
- `GET /{case_id}` — detail
- `PATCH /{case_id}` — update
- `POST /{case_id}/close` — close with outcome classification
- `POST /{case_id}/merge` — merge source cases into target
- `DELETE /{case_id}` — delete

### Case templates (`/case-templates`)
- `GET /` — list templates
- `POST /` — create template
- `GET /{template_id}` — read
- `PATCH /{template_id}` — update
- `DELETE /{template_id}` — delete

### Tasks (`/cases/{case_id}/tasks`)
- `GET /` — list tasks
- `POST /` — create
- `PATCH /{task_id}` — update (status, assignee, notes)
- `DELETE /{task_id}` — delete
- `POST /reorder` — bulk reorder

### Observables (`/observables`)
- `GET /` — list (filters: type, ioc, tlp, case_id)
- `POST /` — create
- `POST /bulk` — bulk create with validation
- `PATCH /{observable_id}` — update (TLP, IOC flag, tags)
- `DELETE /{observable_id}` — delete
- `GET /{observable_id}/correlations` — cross-case correlation

### Assets (`/cases/{case_id}/assets`)
- `GET /` — list
- `POST /` — create (409 on duplicate name within case)
- `PATCH /{asset_id}` — update (compromise status change recorded in timeline)
- `DELETE /{asset_id}` — delete
- `POST /{asset_id}/link-timeline/{entry_id}` — link to timeline entry

### Evidence (`/cases/{case_id}/evidence`)
- `GET /` — list
- `POST /` — register evidence metadata
- `POST /{evidence_id}/upload` — upload file with hash verification
- `GET /{evidence_id}/download` — download (password-protected if encrypted)
- `PATCH /{evidence_id}` — update tags/metadata
- `DELETE /{evidence_id}` — delete

### Timeline (`/cases/{case_id}/timeline`)
- `GET /` — list (filters: event_type, date range, actor, ordering)
- `POST /` — manual timeline entry
- `GET /clusters` — temporal clusters
- `DELETE /{entry_id}` — delete manual entry (system entries immutable)

### Alerts (`/alerts`)
- `GET /` — list (filters: status, source, severity)
- `POST /` — ingest alert
- `GET /{alert_id}` — read
- `POST /{alert_id}/promote` — promote to new case
- `POST /{alert_id}/merge` — merge into existing case
- `POST /{alert_id}/dismiss` — dismiss with reason

### Notes (`/cases/{case_id}/notes`)
- `GET /folders` / `POST /folders` / `PATCH /folders/{id}` / `DELETE /folders/{id}`
- `GET /` — list notes
- `POST /` — create note
- `PATCH /{note_id}` — update
- `DELETE /{note_id}` — delete

### Enrichment (`/enrichment-sources`, `/enrichment/trigger`, `/enrichment/results`)
- `GET /enrichment-sources` — list configured sources
- `POST /enrichment-sources` — register source
- `PATCH /enrichment-sources/{id}` — update (enable/disable, config)
- `DELETE /enrichment-sources/{id}` — remove
- `POST /enrichment/trigger` — trigger enrichment (sync or async via Celery)
- `GET /enrichment/results` — list results with filters

### ATT&CK (`/attack-mappings`, `/attack-reference`)
- `GET /attack-mappings` — list mappings for cases/observables/timeline
- `POST /attack-mappings` — tag with tactic/technique
- `DELETE /attack-mappings/{id}` — remove mapping
- `GET /attack-reference` — list technique metadata (platform-wide)
- `GET /attack-reference/heatmap` — aggregated frequency + severity per tactic/technique

### Reports (`/report-templates`, `/reports`)
- `GET /report-templates` — list
- `POST /report-templates` — create
- `PATCH /report-templates/{id}` — update
- `DELETE /report-templates/{id}` — delete
- `POST /reports/generate` — generate DOCX/Markdown/HTML (async via Celery)
- `GET /reports/{report_id}/download` — download generated report
- `GET /reports` — list generated reports for a case

### Search (`/search`)
- `POST /search` — full-text search across cases, observables, assets, notes, alerts

### Audit (`/audit-logs`)
- `GET /audit-logs` — filterable log (user, action, resource, date range)

### Dashboard (`/dashboard`)
- `GET /dashboard` — aggregated metrics (cached 5 minutes)

## Real-time (`/api/v1/realtime`)
- `WS /ws` — WebSocket endpoint; subscribes to case or tenant channels; event fan-out via Redis pub/sub

## Health
- `GET /health` — liveness probe

## Status codes

- `200 OK` — success with body
- `201 Created` — resource created
- `204 No Content` — successful delete / action with no body
- `400 Bad Request` — validation failure
- `401 Unauthorized` — missing/invalid token
- `403 Forbidden` — authenticated but not authorized (RBAC deny, cross-tenant access)
- `404 Not Found` — resource missing or filtered by RLS
- `409 Conflict` — unique constraint violation (e.g. duplicate asset name in case)
- `422 Unprocessable Entity` — Pydantic validation failure
- `429 Too Many Requests` — rate limit exceeded
- `500 Internal Server Error` — unexpected failure (traced via `request_id`)

## Authentication test matrix

| Auth type             | Can call UI endpoints | Can call WebSocket | Can call admin APIs      |
|-----------------------|-----------------------|--------------------|--------------------------|
| JWT (platform admin)  | yes                   | yes                | yes (all tenants)        |
| JWT (tenant admin)    | yes                   | yes                | yes (own tenant)         |
| JWT (analyst)         | yes                   | yes                | no                       |
| JWT (read-only)       | yes (read only)       | yes                | no                       |
| API key (service acct)| yes (REST only)       | **no**             | no                       |

All API endpoints enforce permission checks via the `require_permission(Resource, Action)` FastAPI dependency, backed by the static `PERMISSION_MATRIX` in `src/auth/rbac.py`.

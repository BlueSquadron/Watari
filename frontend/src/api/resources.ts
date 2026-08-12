// Thin wrappers around the REST API, one per domain. Each returns the
// ApiResponse envelope so callers can read `data` / `meta` directly.

import type {
  Alert,
  ApiResponse,
  Asset,
  AttackHeatmapCell,
  AttackMapping,
  AuditLog,
  Case,
  DashboardMetrics,
  EnrichmentResult,
  EnrichmentSource,
  Evidence,
  Module,
  Note,
  NoteFolder,
  Observable,
  ReportTemplate,
  SearchResponse,
  Task,
  Tenant,
  TimelineEntry,
  TimelineSwimlane,
  User,
  UUID,
} from "@/types/api";
import { request } from "./client";

// ---- Cases ----

export const casesApi = {
  list: (tenantId: UUID, params?: Record<string, unknown>) =>
    request<ApiResponse<Case[]>>({
      url: `/v1/tenants/${tenantId}/cases`,
      params,
    }),
  get: (tenantId: UUID, caseId: UUID) =>
    request<ApiResponse<Case>>({
      url: `/v1/tenants/${tenantId}/cases/${caseId}`,
    }),
  create: (tenantId: UUID, body: Partial<Case>) =>
    request<ApiResponse<Case>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases`,
      data: body,
    }),
  update: (tenantId: UUID, caseId: UUID, body: Partial<Case>) =>
    request<ApiResponse<Case>>({
      method: "PATCH",
      url: `/v1/tenants/${tenantId}/cases/${caseId}`,
      data: body,
    }),
  close: (tenantId: UUID, caseId: UUID, body: { outcome: string }) =>
    request<ApiResponse<Case>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/close`,
      data: body,
    }),
  merge: (tenantId: UUID, caseId: UUID, sourceCaseIds: UUID[]) =>
    request<ApiResponse<Case>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/merge`,
      data: { source_case_ids: sourceCaseIds },
    }),
  remove: (tenantId: UUID, caseId: UUID) =>
    request<void>({
      method: "DELETE",
      url: `/v1/tenants/${tenantId}/cases/${caseId}`,
    }),
};

// ---- Tasks ----

export const tasksApi = {
  list: (tenantId: UUID, caseId: UUID) =>
    request<ApiResponse<Task[]>>({
      url: `/v1/tenants/${tenantId}/cases/${caseId}/tasks`,
    }),
  create: (tenantId: UUID, caseId: UUID, body: Partial<Task>) =>
    request<ApiResponse<Task>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/tasks`,
      data: body,
    }),
  update: (tenantId: UUID, caseId: UUID, taskId: UUID, body: Partial<Task>) =>
    request<ApiResponse<Task>>({
      method: "PATCH",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/tasks/${taskId}`,
      data: body,
    }),
  remove: (tenantId: UUID, caseId: UUID, taskId: UUID) =>
    request<void>({
      method: "DELETE",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/tasks/${taskId}`,
    }),
};

// ---- Observables ----

export const observablesApi = {
  list: (tenantId: UUID, caseId: UUID) =>
    request<ApiResponse<Observable[]>>({
      url: `/v1/tenants/${tenantId}/cases/${caseId}/observables`,
    }),
  create: (tenantId: UUID, caseId: UUID, body: Partial<Observable>) =>
    request<ApiResponse<Observable>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/observables`,
      data: body,
    }),
  bulk: (tenantId: UUID, caseId: UUID, observables: Partial<Observable>[]) =>
    request<ApiResponse<Observable[]>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/observables/bulk`,
      data: { observables },
    }),
  update: (
    tenantId: UUID,
    caseId: UUID,
    observableId: UUID,
    body: Partial<Observable>,
  ) =>
    request<ApiResponse<Observable>>({
      method: "PATCH",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/observables/${observableId}`,
      data: body,
    }),
  remove: (tenantId: UUID, caseId: UUID, observableId: UUID) =>
    request<void>({
      method: "DELETE",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/observables/${observableId}`,
    }),
  enrichmentResults: (tenantId: UUID, caseId: UUID, observableId: UUID) =>
    request<ApiResponse<EnrichmentResult[]>>({
      url: `/v1/tenants/${tenantId}/cases/${caseId}/observables/${observableId}/enrichment`,
    }),
};

// ---- Assets ----

export const assetsApi = {
  list: (tenantId: UUID, caseId: UUID) =>
    request<ApiResponse<Asset[]>>({
      url: `/v1/tenants/${tenantId}/cases/${caseId}/assets`,
    }),
  create: (tenantId: UUID, caseId: UUID, body: Partial<Asset>) =>
    request<ApiResponse<Asset>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/assets`,
      data: body,
    }),
  update: (
    tenantId: UUID,
    caseId: UUID,
    assetId: UUID,
    body: Partial<Asset>,
  ) =>
    request<ApiResponse<Asset>>({
      method: "PATCH",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/assets/${assetId}`,
      data: body,
    }),
  remove: (tenantId: UUID, caseId: UUID, assetId: UUID) =>
    request<void>({
      method: "DELETE",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/assets/${assetId}`,
    }),
};

// ---- Evidence ----

export const evidenceApi = {
  list: (tenantId: UUID, caseId: UUID) =>
    request<ApiResponse<Evidence[]>>({
      url: `/v1/tenants/${tenantId}/cases/${caseId}/evidence`,
    }),
  register: (tenantId: UUID, caseId: UUID, body: Partial<Evidence>) =>
    request<ApiResponse<Evidence>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/evidence`,
      data: body,
    }),
  upload: (
    tenantId: UUID,
    caseId: UUID,
    evidenceId: UUID,
    file: File,
    password?: string,
  ) => {
    const form = new FormData();
    form.append("file", file);
    if (password) form.append("password", password);
    return request<
      ApiResponse<{
        evidence: Evidence;
        integrity_verified: boolean;
        integrity_mismatch: boolean;
      }>
    >({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/evidence/${evidenceId}/upload`,
      data: form,
    });
  },
  downloadUrl: (tenantId: UUID, caseId: UUID, evidenceId: UUID) =>
    `/api/v1/tenants/${tenantId}/cases/${caseId}/evidence/${evidenceId}/download`,
  remove: (tenantId: UUID, caseId: UUID, evidenceId: UUID) =>
    request<void>({
      method: "DELETE",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/evidence/${evidenceId}`,
    }),
};

// ---- Timeline ----

export const timelineApi = {
  list: (tenantId: UUID, caseId: UUID, params?: Record<string, unknown>) =>
    request<ApiResponse<TimelineEntry[]>>({
      url: `/v1/tenants/${tenantId}/cases/${caseId}/timeline`,
      params,
    }),
  addManual: (tenantId: UUID, caseId: UUID, body: Partial<TimelineEntry>) =>
    request<ApiResponse<TimelineEntry>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/timeline`,
      data: body,
    }),
  swimlane: (tenantId: UUID, caseId: UUID, thresholdSeconds = 300) =>
    request<ApiResponse<TimelineSwimlane>>({
      url: `/v1/tenants/${tenantId}/cases/${caseId}/timeline/swimlane`,
      params: { cluster_threshold_seconds: thresholdSeconds },
    }),
};

// ---- Notes ----

export const notesApi = {
  listFolders: (tenantId: UUID, caseId: UUID) =>
    request<ApiResponse<NoteFolder[]>>({
      url: `/v1/tenants/${tenantId}/cases/${caseId}/notes/folders`,
    }),
  createFolder: (
    tenantId: UUID,
    caseId: UUID,
    body: Partial<NoteFolder>,
  ) =>
    request<ApiResponse<NoteFolder>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/notes/folders`,
      data: body,
    }),
  list: (tenantId: UUID, caseId: UUID, folderId?: UUID) =>
    request<ApiResponse<Note[]>>({
      url: `/v1/tenants/${tenantId}/cases/${caseId}/notes`,
      params: folderId ? { folder_id: folderId } : undefined,
    }),
  create: (tenantId: UUID, caseId: UUID, body: Partial<Note>) =>
    request<ApiResponse<Note>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/notes`,
      data: body,
    }),
  update: (
    tenantId: UUID,
    caseId: UUID,
    noteId: UUID,
    body: Partial<Note>,
  ) =>
    request<ApiResponse<Note>>({
      method: "PATCH",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/notes/${noteId}`,
      data: body,
    }),
  remove: (tenantId: UUID, caseId: UUID, noteId: UUID) =>
    request<void>({
      method: "DELETE",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/notes/${noteId}`,
    }),
};

// ---- Alerts ----

export const alertsApi = {
  list: (tenantId: UUID, params?: Record<string, unknown>) =>
    request<ApiResponse<Alert[]>>({
      url: `/v1/tenants/${tenantId}/alerts`,
      params,
    }),
  get: (tenantId: UUID, alertId: UUID) =>
    request<ApiResponse<Alert>>({
      url: `/v1/tenants/${tenantId}/alerts/${alertId}`,
    }),
  ingest: (tenantId: UUID, body: Partial<Alert>) =>
    request<ApiResponse<Alert>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/alerts`,
      data: body,
    }),
  dismiss: (tenantId: UUID, alertId: UUID, reason: string) =>
    request<ApiResponse<Alert>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/alerts/${alertId}/dismiss`,
      data: { reason },
    }),
  promote: (
    tenantId: UUID,
    alertId: UUID,
    body: { case_id?: UUID | null; new_case_title?: string },
  ) =>
    request<ApiResponse<Case>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/alerts/${alertId}/promote`,
      data: body,
    }),
};

// ---- Enrichment ----

export const enrichmentApi = {
  listSources: (tenantId: UUID) =>
    request<ApiResponse<EnrichmentSource[]>>({
      url: `/v1/tenants/${tenantId}/enrichment-sources`,
    }),
  createSource: (tenantId: UUID, body: Partial<EnrichmentSource>) =>
    request<ApiResponse<EnrichmentSource>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/enrichment-sources`,
      data: body,
    }),
  trigger: (tenantId: UUID, observableIds: UUID[], sourceIds?: UUID[]) =>
    request<ApiResponse<{ queued_job_ids: string[] }>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/enrichment`,
      data: { observable_ids: observableIds, source_ids: sourceIds ?? null },
    }),
};

// ---- ATT&CK ----

export const attackApi = {
  createMapping: (tenantId: UUID, body: Partial<AttackMapping>) =>
    request<ApiResponse<AttackMapping>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/attack-mappings`,
      data: body,
    }),
  heatmap: (tenantId: UUID, params?: Record<string, unknown>) =>
    request<ApiResponse<{ cells: AttackHeatmapCell[] }>>({
      url: `/v1/tenants/${tenantId}/attack-mappings/heatmap`,
      params,
    }),
  reference: () =>
    request<
      ApiResponse<
        Array<{
          technique_id: string;
          tactic_id: string;
          name: string;
          description: string | null;
          is_subtechnique: boolean;
          parent_technique_id: string | null;
        }>
      >
    >({ url: "/v1/attack-reference" }),
};

// ---- Reports ----

export const reportsApi = {
  templates: (tenantId: UUID) =>
    request<ApiResponse<ReportTemplate[]>>({
      url: `/v1/tenants/${tenantId}/report-templates`,
    }),
  createTemplate: (tenantId: UUID, body: Partial<ReportTemplate>) =>
    request<ApiResponse<ReportTemplate>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/report-templates`,
      data: body,
    }),
  generate: (
    tenantId: UUID,
    caseId: UUID,
    templateId: UUID,
    format?: "docx" | "markdown" | "html",
  ) =>
    request<
      ApiResponse<{
        id: UUID;
        format: string;
        storage_path: string | null;
      }>
    >({
      method: "POST",
      url: `/v1/tenants/${tenantId}/cases/${caseId}/reports`,
      data: { template_id: templateId, format: format ?? null },
    }),
  preview: (tenantId: UUID, caseId: UUID, templateId: UUID) =>
    request<string>({
      url: `/v1/tenants/${tenantId}/cases/${caseId}/reports/preview`,
      params: { template_id: templateId },
      responseType: "text",
    }),
};

// ---- Search ----

export const searchApi = {
  search: (
    tenantId: UUID,
    query: string,
    entityTypes?: SearchResponse["hits"][number]["entity_type"][],
  ) =>
    request<ApiResponse<SearchResponse>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/search`,
      data: {
        query,
        entity_types: entityTypes ?? [
          "case",
          "observable",
          "asset",
          "note",
          "alert",
        ],
      },
    }),
};

// ---- Dashboard ----

export const dashboardApi = {
  metrics: (tenantId: UUID, params?: Record<string, unknown>) =>
    request<ApiResponse<DashboardMetrics>>({
      url: `/v1/tenants/${tenantId}/dashboard`,
      params,
    }),
};

// ---- Audit ----

export const auditApi = {
  list: (tenantId: UUID, params?: Record<string, unknown>) =>
    request<ApiResponse<AuditLog[]>>({
      url: `/v1/tenants/${tenantId}/audit-logs`,
      params,
    }),
};

// ---- Users & Tenants ----

export const usersApi = {
  list: (tenantId: UUID) =>
    request<ApiResponse<User[]>>({
      url: `/v1/tenants/${tenantId}/users`,
    }),
  create: (tenantId: UUID, body: Partial<User> & { password?: string }) =>
    request<ApiResponse<User>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/users`,
      data: body,
    }),
  update: (tenantId: UUID, userId: UUID, body: Partial<User>) =>
    request<ApiResponse<User>>({
      method: "PATCH",
      url: `/v1/tenants/${tenantId}/users/${userId}`,
      data: body,
    }),
  deactivate: (tenantId: UUID, userId: UUID) =>
    request<void>({
      method: "DELETE",
      url: `/v1/tenants/${tenantId}/users/${userId}`,
    }),
  createServiceAccount: (
    tenantId: UUID,
    body: { username: string; display_name: string; role: string },
  ) =>
    request<
      ApiResponse<{
        user: User;
        api_key: string;
      }>
    >({
      method: "POST",
      url: `/v1/tenants/${tenantId}/users/service-accounts`,
      data: body,
    }),
};

export const tenantsApi = {
  list: () =>
    request<ApiResponse<Tenant[]>>({ url: "/v1/admin/tenants" }),
  get: (tenantId: UUID) =>
    request<ApiResponse<Tenant>>({
      url: `/v1/admin/tenants/${tenantId}`,
    }),
  create: (body: Partial<Tenant>) =>
    request<ApiResponse<Tenant>>({
      method: "POST",
      url: "/v1/admin/tenants",
      data: body,
    }),
  update: (tenantId: UUID, body: Partial<Tenant>) =>
    request<ApiResponse<Tenant>>({
      method: "PATCH",
      url: `/v1/admin/tenants/${tenantId}`,
      data: body,
    }),
};

export const modulesApi = {
  list: () => request<ApiResponse<Module[]>>({ url: "/v1/admin/modules" }),
  update: (moduleId: UUID, body: Partial<Module>) =>
    request<ApiResponse<Module>>({
      method: "PATCH",
      url: `/v1/admin/modules/${moduleId}`,
      data: body,
    }),
};

export const authApi = {
  me: () => request<ApiResponse<User>>({ url: "/v1/auth/me" }),
  logout: () => request<void>({ method: "POST", url: "/v1/auth/logout" }),
};

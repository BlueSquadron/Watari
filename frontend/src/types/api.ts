// Shared API types mirroring the Pydantic schemas on the backend.

export type UUID = string;

export interface ApiError {
  code: string;
  message: string;
  details?: Array<{ field: string; message: string; code: string }>;
  request_id: string;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
}

export interface ApiResponse<T> {
  data: T;
  meta?: PaginationMeta;
}

export type Role =
  | "platform_admin"
  | "tenant_admin"
  | "analyst"
  | "read_only"
  | "api_service_account";

export interface User {
  id: UUID;
  tenant_id: UUID;
  username: string;
  email: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  is_service_account: boolean;
  last_login_at: string | null;
  inactivity_timeout_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export type CaseStatus =
  | "new"
  | "in_progress"
  | "pending"
  | "resolved"
  | "closed";

export type CaseSeverity =
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "informational";

export type CaseOutcome =
  | "true_positive"
  | "false_positive"
  | "indeterminate"
  | "not_applicable";

export interface Case {
  id: UUID;
  tenant_id: UUID;
  case_number: number;
  title: string;
  description: string | null;
  status: CaseStatus;
  severity: CaseSeverity;
  outcome: CaseOutcome | null;
  assignee_id: UUID | null;
  template_id: UUID | null;
  tags: string[];
  custom_fields: Record<string, unknown>;
  merged_from: UUID[] | null;
  created_by: UUID;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  closed_at: string | null;
}

export type TaskStatus = "todo" | "in_progress" | "done" | "cancelled";

export interface Task {
  id: UUID;
  tenant_id: UUID;
  case_id: UUID;
  title: string;
  description: string | null;
  status: TaskStatus;
  assignee_id: UUID | null;
  sort_order: number;
  created_by: UUID;
  created_at: string;
  updated_at: string;
}

export type ObservableType =
  | "ip"
  | "domain"
  | "hostname"
  | "url"
  | "hash_md5"
  | "hash_sha1"
  | "hash_sha256"
  | "email"
  | "filename"
  | "registry_key";

export type TLP = "red" | "amber" | "green" | "clear";

export interface Observable {
  id: UUID;
  tenant_id: UUID;
  case_id: UUID;
  type: ObservableType;
  value: string;
  tlp: TLP | null;
  is_ioc: boolean;
  tags: string[];
  description: string | null;
  created_by: UUID;
  created_at: string;
  updated_at: string;
  seen_in_cases_count?: number | null;
}

export type AssetType =
  | "workstation"
  | "server"
  | "network_device"
  | "mobile_device"
  | "cloud_resource"
  | "other";

export interface Asset {
  id: UUID;
  tenant_id: UUID;
  case_id: UUID;
  name: string;
  type: AssetType;
  ip_address: string | null;
  domain: string | null;
  is_compromised: boolean;
  description: string | null;
  custom_attributes: Record<string, unknown>;
  created_by: UUID;
  created_at: string;
  updated_at: string;
}

export type EvidenceType =
  | "disk_image"
  | "memory_dump"
  | "log_export"
  | "pcap"
  | "document"
  | "other";

export interface Evidence {
  id: UUID;
  tenant_id: UUID;
  case_id: UUID;
  filename: string;
  type: EvidenceType;
  file_hash_sha256: string;
  file_size: number;
  description: string | null;
  storage_path: string | null;
  is_uploaded: boolean;
  is_encrypted: boolean;
  integrity_verified: boolean | null;
  integrity_mismatch: boolean;
  tags: string[];
  registered_by: UUID;
  registered_at: string;
  updated_at: string;
}

export interface TimelineEntry {
  id: UUID;
  tenant_id: UUID;
  case_id: UUID;
  event_type: string;
  event_timestamp: string;
  description: string;
  category: string | null;
  actor_id: UUID | null;
  is_automatic: boolean;
  metadata: Record<string, unknown>;
  linked_asset_ids: UUID[];
  created_at: string;
}

export interface TemporalCluster {
  start: string;
  end: string;
  entry_ids: UUID[];
}

export interface TimelineSwimlane {
  entries: TimelineEntry[];
  clusters: TemporalCluster[];
  lanes: Record<string, UUID[]>;
}

// OCSF 1.8.0 workflow statuses we care about in the UI
export type AlertStatus = "pending" | "promoted" | "dismissed";

/** OCSF 1.8.0 Metadata object (subset Watari surfaces). */
export interface OCSFProduct {
  name: string;
  vendor_name?: string | null;
  version?: string | null;
  uid?: string | null;
}

export interface OCSFMetadata {
  version: string;
  product: OCSFProduct;
  log_level?: string | null;
  event_code?: string | null;
  [key: string]: unknown;
}

/** OCSF 1.8.0 Finding Information object. */
export interface OCSFFindingInfo {
  uid: string;
  uid_alt?: string | null;
  title?: string | null;
  desc?: string | null;
  types?: string[] | null;
  analytic?: Record<string, unknown> | null;
  src_url?: string | null;
  [key: string]: unknown;
}

/** OCSF 1.8.0 Observable object (the subset Watari recognises). */
export interface OCSFObservable {
  name: string;
  type?: string | null;
  type_id: number;
  value: string;
  is_ioc?: boolean;
  tlp?: string | null;
  [key: string]: unknown;
}

/** MITRE ATT&CK attribution carried on a Detection Finding. */
export interface OCSFAttack {
  tactic?: { name?: string; uid?: string } | null;
  technique?: { name?: string; uid?: string } | null;
  sub_technique?: { name?: string; uid?: string } | null;
  version?: string | null;
  [key: string]: unknown;
}

/** Watari-specific workflow envelope carried alongside the OCSF payload. */
export interface WatariAlertEnvelope {
  id: UUID;
  tenant_id: UUID;
  workflow_status: AlertStatus;
  dismiss_reason: string | null;
  promoted_to_case_id: UUID | null;
  dedup_key: string | null;
  created_at: string;
  updated_at: string;
}

/** Full Alert: an OCSF 1.8.0 Detection Finding plus Watari envelope. */
export interface Alert {
  // OCSF classification
  activity_id: number;
  activity_name: string;
  category_uid: number; // always 2 (Findings)
  category_name: string;
  class_uid: number; // always 2004 (Detection Finding)
  class_name: string;
  type_uid: number;
  type_name: string | null;

  // OCSF severity (integer + caption)
  severity_id: number; // 0..6 or 99
  severity: string;

  // OCSF required objects
  metadata: OCSFMetadata;
  finding_info: OCSFFindingInfo;
  time: number; // epoch ms
  time_dt: string;

  // OCSF recommended
  is_alert: boolean;
  message: string | null;
  status_id: number;
  status: string;

  confidence_id: number | null;
  confidence: string | null;
  confidence_score: number | null;

  observables: OCSFObservable[];
  attacks: OCSFAttack[];
  raw_data: string | null;

  // Watari workflow (not part of OCSF)
  watari: WatariAlertEnvelope;
}

export interface Note {
  id: UUID;
  tenant_id: UUID;
  case_id: UUID;
  folder_id: UUID | null;
  title: string;
  content: string;
  author_id: UUID;
  created_at: string;
  updated_at: string;
}

export interface NoteFolder {
  id: UUID;
  tenant_id: UUID;
  case_id: UUID;
  parent_id: UUID | null;
  name: string;
  sort_order: number;
  created_at: string;
}

export interface EnrichmentSource {
  id: UUID;
  tenant_id: UUID;
  name: string;
  type: string;
  config: Record<string, unknown>;
  supported_observable_types: string[];
  is_enabled: boolean;
  timeout_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface EnrichmentResult {
  id: UUID;
  tenant_id: UUID;
  observable_id: UUID;
  source_id: UUID;
  source_name?: string | null;
  status: "success" | "error" | "timeout";
  result_data: Record<string, unknown> | null;
  error_message: string | null;
  queried_at: string;
}

export interface AttackMapping {
  id: UUID;
  tenant_id: UUID;
  case_id: UUID | null;
  observable_id: UUID | null;
  timeline_entry_id: UUID | null;
  tactic_id: string;
  technique_id: string;
  sub_technique_id: string | null;
  created_by: UUID;
  created_at: string;
}

export interface AttackHeatmapCell {
  tactic_id: string;
  technique_id: string;
  case_count: number;
  max_severity: CaseSeverity | null;
  linked_case_ids: UUID[];
}

export interface AuditLog {
  id: UUID;
  tenant_id: UUID;
  user_id: UUID;
  action: string;
  resource_type: string;
  resource_id: UUID | null;
  details: Record<string, unknown>;
  source_ip: string | null;
  user_agent: string | null;
  is_service_account: boolean;
  created_at: string;
}

export interface Module {
  id: UUID;
  name: string;
  version: string;
  type: "pipeline" | "processor";
  description: string | null;
  config_schema: Record<string, unknown>;
  entry_point: string;
  is_enabled: boolean;
  supported_evidence_types: string[] | null;
  subscribed_events: string[] | null;
  installed_at: string;
  updated_at: string;
}

export interface Tenant {
  id: UUID;
  name: string;
  slug: string;
  settings: Record<string, unknown>;
  custom_fields_schema: Array<Record<string, unknown>>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DashboardMetrics {
  open_cases_by_severity: Array<{ severity: string; count: number }>;
  cases_by_status: Array<{ status: string; count: number }>;
  cases_by_outcome: Array<{ outcome: string; count: number }>;
  mean_time_to_resolution_hours: number | null;
  cases_created_over_time: Array<{ timestamp: string; value: number }>;
  analyst_workload: Array<{
    analyst_id: string;
    analyst_name: string;
    open_cases: number;
    resolved_cases_7d: number;
  }>;
}

export interface SearchHit {
  entity_type: "case" | "observable" | "asset" | "note" | "alert";
  entity_id: UUID;
  case_id: UUID | null;
  title: string;
  snippet: string;
  extra: Record<string, unknown>;
  score: number;
}

export interface SearchResponse {
  query: string;
  total_hits: number;
  hits: SearchHit[];
}

export interface CaseTemplate {
  id: UUID;
  tenant_id: UUID | null;
  name: string;
  description: string | null;
  default_severity: string | null;
  default_tags: string[];
  tasks: Array<Record<string, unknown>>;
  custom_fields: Record<string, unknown>;
  created_by: UUID;
  created_at: string;
  updated_at: string;
}

export interface ReportTemplate {
  id: UUID;
  tenant_id: UUID | null;
  name: string;
  type: "investigation" | "activity";
  format: "docx" | "markdown" | "html";
  template_content: string;
  tag_schema: Array<Record<string, unknown>>;
  created_by: UUID;
  created_at: string;
  updated_at: string;
}

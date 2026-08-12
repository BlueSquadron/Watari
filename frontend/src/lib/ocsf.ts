/**
 * Helpers for displaying OCSF 1.8.0 Detection Finding values in the UI.
 *
 * OCSF uses integer enums with captions (e.g. `severity_id: 4` and
 * `severity: "High"`). Watari's design system uses lowercase string
 * variants of severity. These helpers bridge the two so Alert pages
 * can reuse existing components like `SeverityBadge`.
 */

import type { Alert, AlertStatus, CaseSeverity, OCSFObservable } from "@/types/api";

/** OCSF `severity_id` -> Watari `CaseSeverity` enum member. */
export function ocsfSeverityToCaseSeverity(severityId: number): CaseSeverity {
  switch (severityId) {
    case 1:
      return "informational";
    case 2:
      return "low";
    case 3:
      return "medium";
    case 4:
      return "high";
    case 5:
    case 6:
      return "critical";
    default:
      return "informational";
  }
}

/** Watari workflow status derived from the OCSF envelope. */
export function workflowStatus(alert: Alert): AlertStatus {
  return alert.watari.workflow_status;
}

/** Human-readable "title" for an alert — prefers finding_info.title, then message. */
export function alertTitle(alert: Alert): string {
  return (
    alert.finding_info?.title?.trim() ||
    alert.message?.split("\n")[0]?.slice(0, 120) ||
    alert.finding_info?.uid ||
    "Unnamed finding"
  );
}

/** Product name (source), from metadata.product.name. */
export function alertProduct(alert: Alert): string {
  return alert.metadata?.product?.name ?? "unknown";
}

/** Short display label for an OCSF observable type_id. */
export function ocsfObservableTypeLabel(obs: OCSFObservable): string {
  if (obs.type) return obs.type;
  const labels: Record<number, string> = {
    0: "Unknown",
    1: "Hostname",
    2: "IP",
    3: "MAC",
    4: "Username",
    5: "Email",
    6: "URL",
    7: "Filename",
    8: "Hash",
    9: "Process",
    20: "Endpoint",
    21: "User",
    22: "Email",
    23: "URL",
    24: "File",
    25: "Process",
    26: "Location",
    27: "Container",
    28: "Registry Key",
    29: "Registry Value",
    30: "Fingerprint",
    99: "Other",
  };
  return labels[obs.type_id] ?? `type_id ${obs.type_id}`;
}

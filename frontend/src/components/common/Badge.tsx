import { clsx } from "clsx";
import type { ReactNode } from "react";
import type { CaseSeverity, CaseStatus, TLP } from "@/types/api";

const severityClasses: Record<CaseSeverity, string> = {
  critical: "bg-severity-critical/15 text-severity-critical",
  high: "bg-severity-high/15 text-severity-high",
  medium: "bg-severity-medium/15 text-severity-medium",
  low: "bg-severity-low/15 text-severity-low",
  informational: "bg-severity-informational/15 text-severity-informational",
};

const statusClasses: Record<CaseStatus, string> = {
  new: "bg-status-new/15 text-status-new",
  in_progress: "bg-status-in_progress/15 text-status-in_progress",
  pending: "bg-status-pending/15 text-status-pending",
  resolved: "bg-status-resolved/15 text-status-resolved",
  closed: "bg-status-closed/15 text-status-closed",
};

const tlpClasses: Record<TLP, string> = {
  red: "bg-severity-critical text-white",
  amber: "bg-severity-high text-white",
  green: "bg-severity-resolved text-white",
  clear: "bg-watari-bg-dark-tertiary text-watari-text-dark-primary",
};

export function SeverityBadge({ severity }: { severity: CaseSeverity }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium uppercase tracking-wide",
        severityClasses[severity],
      )}
    >
      {severity}
    </span>
  );
}

export function StatusBadge({ status }: { status: CaseStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium uppercase tracking-wide",
        statusClasses[status],
      )}
    >
      {status.replace("_", " ")}
    </span>
  );
}

export function TLPBadge({ tlp }: { tlp: TLP }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
        tlpClasses[tlp],
      )}
    >
      TLP:{tlp}
    </span>
  );
}

export function Badge({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full bg-watari-bg-dark-tertiary px-2 py-0.5 text-xs font-medium text-watari-text-dark-primary",
        className,
      )}
    >
      {children}
    </span>
  );
}

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { alertsApi } from "@/api/resources";
import { SeverityBadge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Dialog } from "@/components/common/Dialog";
import { Field, Select, TextInput } from "@/components/common/Field";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import {
  TD,
  TH,
  THead,
  TR,
  Table,
  TableEmpty,
} from "@/components/common/Table";
import {
  alertProduct,
  alertTitle,
  ocsfSeverityToCaseSeverity,
  workflowStatus,
} from "@/lib/ocsf";
import { useTenantStore } from "@/stores/tenant";
import type { Alert, AlertStatus, UUID } from "@/types/api";

const STATUSES: (AlertStatus | "")[] = ["", "pending", "promoted", "dismissed"];

export function AlertQueue() {
  const tenantId = useTenantStore((s) => s.activeTenantId);
  const navigate = useNavigate();
  const [status, setStatus] = useState<AlertStatus | "">("pending");
  const [search, setSearch] = useState("");
  const [promoting, setPromoting] = useState<Alert | null>(null);
  const [dismissing, setDismissing] = useState<Alert | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["alerts", tenantId, status],
    queryFn: () => alertsApi.list(tenantId!, status ? { status } : undefined),
    enabled: !!tenantId,
  });

  if (!tenantId)
    return (
      <p className="text-sm text-watari-text-dark-secondary">No active tenant.</p>
    );

  const filtered = (data?.data ?? []).filter((a) => {
    if (!search.trim()) return true;
    const needle = search.trim().toLowerCase();
    return [
      alertTitle(a),
      a.message ?? "",
      alertProduct(a),
      a.finding_info?.uid ?? "",
    ].some((txt) => txt.toLowerCase().includes(needle));
  });

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-2xl font-semibold">Alerts</h2>
        <p className="text-sm text-watari-text-dark-secondary">
          OCSF 1.8.0 Detection Findings awaiting triage
        </p>
      </header>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <TextInput
          placeholder="Search title / message / product / finding UID…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value as AlertStatus | "")}
        >
          {STATUSES.map((s) => (
            <option key={s || "all"} value={s}>
              {s || "All statuses"}
            </option>
          ))}
        </Select>
      </div>

      {isLoading ? (
        <LoadingOverlay label="Loading alerts" />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH className="w-40">Product</TH>
              <TH>Title</TH>
              <TH className="w-28">Severity</TH>
              <TH className="w-32">Status</TH>
              <TH className="w-44">Received</TH>
              <TH className="w-52">Actions</TH>
            </TR>
          </THead>
          <tbody>
            {filtered.length === 0 ? (
              <TableEmpty colSpan={6}>No alerts.</TableEmpty>
            ) : (
              filtered.map((a) => {
                const status = workflowStatus(a);
                return (
                  <TR
                    key={a.watari.id}
                    onClick={() => navigate(`/alerts/${a.watari.id}`)}
                  >
                    <TD className="text-watari-text-dark-secondary">
                      {alertProduct(a)}
                    </TD>
                    <TD>
                      <div className="font-medium text-watari-text-dark-primary">
                        {alertTitle(a)}
                      </div>
                      {a.message ? (
                        <div className="truncate text-xs text-watari-text-dark-secondary">
                          {a.message}
                        </div>
                      ) : null}
                      {a.watari.dedup_key ? (
                        <div className="mt-1 inline-block rounded bg-watari-bg-dark-tertiary px-1.5 py-0.5 text-[10px] text-watari-text-dark-secondary">
                          dedup: {a.watari.dedup_key}
                        </div>
                      ) : null}
                    </TD>
                    <TD>
                      <SeverityBadge
                        severity={ocsfSeverityToCaseSeverity(a.severity_id)}
                      />
                    </TD>
                    <TD>
                      <AlertStatusBadge status={status} />
                    </TD>
                    <TD className="text-watari-text-dark-secondary">
                      {new Date(a.watari.created_at).toLocaleString()}
                    </TD>
                    <TD onClick={(e) => e.stopPropagation()}>
                      {status === "pending" ? (
                        <div className="flex gap-1">
                          <Button size="sm" onClick={() => setPromoting(a)}>
                            Promote
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setDismissing(a)}
                          >
                            Dismiss
                          </Button>
                        </div>
                      ) : a.watari.promoted_to_case_id ? (
                        <a
                          href={`/cases/${a.watari.promoted_to_case_id}`}
                          className="text-xs text-watari-gold hover:underline"
                        >
                          View case →
                        </a>
                      ) : (
                        <span className="text-xs text-watari-text-dark-secondary">
                          {a.watari.dismiss_reason ?? "—"}
                        </span>
                      )}
                    </TD>
                  </TR>
                );
              })
            )}
          </tbody>
        </Table>
      )}

      {promoting ? (
        <PromoteDialog
          alert={promoting}
          tenantId={tenantId}
          onClose={() => setPromoting(null)}
        />
      ) : null}
      {dismissing ? (
        <DismissDialog
          alert={dismissing}
          tenantId={tenantId}
          onClose={() => setDismissing(null)}
        />
      ) : null}
    </div>
  );
}

function AlertStatusBadge({ status }: { status: AlertStatus }) {
  const classes: Record<AlertStatus, string> = {
    pending: "bg-status-new/15 text-status-new",
    promoted: "bg-status-resolved/15 text-status-resolved",
    dismissed: "bg-status-closed/15 text-status-closed",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${classes[status]}`}
    >
      {status}
    </span>
  );
}

function PromoteDialog({
  alert,
  tenantId,
  onClose,
}: {
  alert: Alert;
  tenantId: UUID;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [title, setTitle] = useState(alertTitle(alert));

  const promote = useMutation({
    mutationFn: () =>
      alertsApi.promote(tenantId, alert.watari.id, {
        new_case_title: title.trim() || alertTitle(alert),
      }),
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ["alerts", tenantId] });
      qc.invalidateQueries({ queryKey: ["cases", tenantId] });
      onClose();
      navigate(`/cases/${response.data.id}`);
    },
  });

  return (
    <Dialog
      open
      onOpenChange={(o) => (o ? null : onClose())}
      title="Promote alert to case"
      description={`${alertProduct(alert)}: ${alertTitle(alert)}`}
    >
      <div className="space-y-3">
        <Field label="New case title" required>
          <TextInput
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={alertTitle(alert)}
          />
        </Field>
        <div className="rounded-md bg-watari-bg-dark-tertiary p-2 text-xs text-watari-text-dark-secondary">
          {alert.observables.length} observable(s) will be copied onto the new
          case.
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={promote.isPending} onClick={() => promote.mutate()}>
            Create case
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function DismissDialog({
  alert,
  tenantId,
  onClose,
}: {
  alert: Alert;
  tenantId: UUID;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("duplicate");

  const dismiss = useMutation({
    mutationFn: () => alertsApi.dismiss(tenantId, alert.watari.id, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts", tenantId] });
      onClose();
    },
  });

  return (
    <Dialog
      open
      onOpenChange={(o) => (o ? null : onClose())}
      title="Dismiss alert"
      description={alertTitle(alert)}
    >
      <div className="space-y-3">
        <Field label="Reason" required>
          <Select value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="duplicate">Duplicate of existing alert</option>
            <option value="false_positive">False positive</option>
            <option value="known_behavior">Known / authorised behaviour</option>
            <option value="insufficient_context">Insufficient context</option>
            <option value="other">Other</option>
          </Select>
        </Field>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={dismiss.isPending}
            onClick={() => dismiss.mutate()}
          >
            Dismiss
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

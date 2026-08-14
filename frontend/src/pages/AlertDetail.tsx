import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { alertsApi } from "@/api/resources";
import { SeverityBadge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Dialog } from "@/components/common/Dialog";
import { Field, Select, TextInput } from "@/components/common/Field";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import {
  alertProduct,
  alertTitle,
  ocsfObservableTypeLabel,
  ocsfSeverityToCaseSeverity,
  workflowStatus,
} from "@/lib/ocsf";
import { useTenantStore } from "@/stores/tenant";
import type { Alert, AlertStatus, UUID } from "@/types/api";

/**
 * Alert detail view — renders a full OCSF 1.8.0 Detection Finding so an
 * analyst can make an informed triage decision. Shows classification,
 * finding info, metadata, observables, ATT&CK attributions, and the
 * raw payload verbatim. Promote and Dismiss actions live here too.
 */
export function AlertDetail() {
  const { alertId } = useParams<{ alertId: UUID }>();
  const tenantId = useTenantStore((s) => s.activeTenantId);
  const navigate = useNavigate();
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [dismissOpen, setDismissOpen] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["alert", tenantId, alertId],
    queryFn: () => alertsApi.get(tenantId!, alertId!),
    enabled: !!tenantId && !!alertId,
  });

  if (!tenantId)
    return (
      <p className="text-sm text-watari-text-dark-secondary">
        No active tenant.
      </p>
    );
  if (isLoading || !data) return <LoadingOverlay label="Loading alert" />;
  if (isError)
    return (
      <p className="text-sm text-severity-critical">
        Could not load this alert.
      </p>
    );

  const alert = data.data;
  const status = workflowStatus(alert);

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <button
            type="button"
            onClick={() => navigate("/alerts")}
            className="mb-2 text-xs text-watari-text-dark-secondary hover:text-watari-gold"
          >
            ← Back to alert queue
          </button>
          <h2 className="text-2xl font-semibold">{alertTitle(alert)}</h2>
          <p className="mt-1 text-sm text-watari-text-dark-secondary">
            Detection Finding from{" "}
            <span className="font-medium">{alertProduct(alert)}</span>
            {alert.metadata.product.vendor_name
              ? ` (${alert.metadata.product.vendor_name})`
              : ""}{" "}
            · Received {new Date(alert.watari.created_at).toLocaleString()}
          </p>
          <p className="mt-1 text-xs text-watari-text-dark-secondary">
            OCSF {alert.metadata.version} · class_uid {alert.class_uid} (
            {alert.class_name}) · type_uid {alert.type_uid}
          </p>
        </div>
        <div className="flex shrink-0 items-start gap-2">
          <SeverityBadge
            severity={ocsfSeverityToCaseSeverity(alert.severity_id)}
          />
          <AlertStatusBadge status={status} />
        </div>
      </header>

      {status === "pending" ? (
        <div className="flex gap-2">
          <Button onClick={() => setPromoteOpen(true)}>Promote to case</Button>
          <Button variant="ghost" onClick={() => setDismissOpen(true)}>
            Dismiss
          </Button>
        </div>
      ) : status === "promoted" && alert.watari.promoted_to_case_id ? (
        <Button
          onClick={() => navigate(`/cases/${alert.watari.promoted_to_case_id}`)}
        >
          View resulting case →
        </Button>
      ) : status === "dismissed" ? (
        <div className="rounded-md border border-watari-bg-dark-tertiary bg-watari-bg-dark-secondary p-3 text-sm text-watari-text-dark-secondary">
          Dismissed{" "}
          {alert.watari.dismiss_reason
            ? `: ${alert.watari.dismiss_reason}`
            : ""}
        </div>
      ) : null}

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <InfoCard title="Message">
          {alert.message ? (
            <p className="whitespace-pre-wrap text-sm text-watari-text-dark-primary">
              {alert.message}
            </p>
          ) : (
            <p className="text-sm italic text-watari-text-dark-secondary">
              No message provided
            </p>
          )}
          {alert.finding_info.desc ? (
            <p className="mt-2 border-t border-watari-bg-dark-tertiary pt-2 text-sm text-watari-text-dark-secondary">
              {alert.finding_info.desc}
            </p>
          ) : null}
        </InfoCard>

        <InfoCard title="Finding info">
          <dl className="grid grid-cols-[120px_1fr] gap-y-2 text-sm">
            <dt className="text-watari-text-dark-secondary">UID</dt>
            <dd className="truncate font-mono text-xs">
              {alert.finding_info.uid}
            </dd>
            {alert.finding_info.uid_alt ? (
              <>
                <dt className="text-watari-text-dark-secondary">Alt UID</dt>
                <dd className="truncate font-mono text-xs">
                  {alert.finding_info.uid_alt}
                </dd>
              </>
            ) : null}
            {alert.finding_info.types?.length ? (
              <>
                <dt className="text-watari-text-dark-secondary">Types</dt>
                <dd className="flex flex-wrap gap-1">
                  {alert.finding_info.types.map((t) => (
                    <span
                      key={t}
                      className="rounded-full bg-watari-bg-dark-tertiary px-2 py-0.5 text-xs"
                    >
                      {t}
                    </span>
                  ))}
                </dd>
              </>
            ) : null}
            {alert.finding_info.analytic?.name ? (
              <>
                <dt className="text-watari-text-dark-secondary">Analytic</dt>
                <dd>{String(alert.finding_info.analytic.name)}</dd>
              </>
            ) : null}
            {alert.confidence_id !== null ? (
              <>
                <dt className="text-watari-text-dark-secondary">Confidence</dt>
                <dd>
                  {alert.confidence ?? "—"}
                  {alert.confidence_score !== null
                    ? ` (${alert.confidence_score}/100)`
                    : ""}
                </dd>
              </>
            ) : null}
          </dl>
        </InfoCard>
      </section>

      <InfoCard title="Metadata">
        <dl className="grid grid-cols-[140px_1fr] gap-y-2 text-sm">
          <dt className="text-watari-text-dark-secondary">Product</dt>
          <dd>
            {alert.metadata.product.name}
            {alert.metadata.product.version
              ? ` v${alert.metadata.product.version}`
              : ""}
          </dd>
          {alert.metadata.product.vendor_name ? (
            <>
              <dt className="text-watari-text-dark-secondary">Vendor</dt>
              <dd>{alert.metadata.product.vendor_name}</dd>
            </>
          ) : null}
          <dt className="text-watari-text-dark-secondary">OCSF version</dt>
          <dd className="font-mono text-xs">{alert.metadata.version}</dd>
          {alert.metadata.event_code ? (
            <>
              <dt className="text-watari-text-dark-secondary">Event code</dt>
              <dd className="font-mono text-xs">{alert.metadata.event_code}</dd>
            </>
          ) : null}
          <dt className="text-watari-text-dark-secondary">Tenant</dt>
          <dd className="font-mono text-xs">{alert.watari.tenant_id}</dd>
          <dt className="text-watari-text-dark-secondary">Alert ID</dt>
          <dd className="font-mono text-xs">{alert.watari.id}</dd>
          <dt className="text-watari-text-dark-secondary">Dedup key</dt>
          <dd className="font-mono text-xs">{alert.watari.dedup_key ?? "—"}</dd>
          <dt className="text-watari-text-dark-secondary">Event time</dt>
          <dd>{new Date(alert.time_dt).toLocaleString()}</dd>
          <dt className="text-watari-text-dark-secondary">Last updated</dt>
          <dd>{new Date(alert.watari.updated_at).toLocaleString()}</dd>
        </dl>
      </InfoCard>

      <InfoCard title={`Observables (${alert.observables.length})`}>
        {alert.observables.length === 0 ? (
          <p className="text-sm italic text-watari-text-dark-secondary">
            No observables attached.
          </p>
        ) : (
          <ul className="divide-y divide-watari-bg-dark-tertiary">
            {alert.observables.map((obs, idx) => (
              <li
                key={`${obs.name}-${idx}`}
                className="flex items-center justify-between py-2"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-watari-bg-dark-tertiary px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide">
                      {ocsfObservableTypeLabel(obs)}
                    </span>
                    <code className="truncate text-sm">{obs.value}</code>
                  </div>
                  <div className="mt-0.5 text-[10px] text-watari-text-dark-secondary">
                    path: <code>{obs.name}</code> · type_id {obs.type_id}
                  </div>
                </div>
                <div className="flex shrink-0 gap-1">
                  {obs.is_ioc ? (
                    <span className="rounded-full bg-severity-critical/15 px-2 py-0.5 text-[10px] font-medium uppercase text-severity-critical">
                      IOC
                    </span>
                  ) : null}
                  {obs.tlp ? (
                    <span className="rounded-full bg-watari-gold/20 px-2 py-0.5 text-[10px] font-medium uppercase text-watari-gold">
                      TLP: {obs.tlp}
                    </span>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </InfoCard>

      {alert.attacks.length > 0 ? (
        <InfoCard title={`MITRE ATT&CK (${alert.attacks.length})`}>
          <ul className="space-y-1 text-sm">
            {alert.attacks.map((a, idx) => (
              <li key={idx} className="flex gap-2">
                {a.tactic?.uid ? (
                  <span className="rounded bg-watari-bg-dark-tertiary px-2 py-0.5 font-mono text-xs">
                    {a.tactic.uid}
                  </span>
                ) : null}
                {a.tactic?.name ? <span>{a.tactic.name}</span> : null}
                <span className="text-watari-text-dark-secondary">→</span>
                {a.technique?.uid ? (
                  <span className="rounded bg-watari-gold/20 px-2 py-0.5 font-mono text-xs text-watari-gold">
                    {a.technique.uid}
                  </span>
                ) : null}
                {a.technique?.name ? <span>{a.technique.name}</span> : null}
                {a.sub_technique?.uid ? (
                  <span className="text-watari-text-dark-secondary">
                    / {a.sub_technique.uid} {a.sub_technique.name}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </InfoCard>
      ) : null}

      <InfoCard title="Raw OCSF document">
        <pre className="max-h-[500px] overflow-auto rounded bg-watari-bg-dark px-3 py-2 text-xs text-watari-text-dark-primary">
          {JSON.stringify(alert, null, 2)}
        </pre>
      </InfoCard>

      {promoteOpen ? (
        <PromoteDialog
          alert={alert}
          tenantId={tenantId}
          onClose={() => setPromoteOpen(false)}
        />
      ) : null}
      {dismissOpen ? (
        <DismissDialog
          alert={alert}
          tenantId={tenantId}
          onClose={() => setDismissOpen(false)}
        />
      ) : null}
    </div>
  );
}

function InfoCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark-secondary p-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-watari-text-dark-secondary">
        {title}
      </h3>
      {children}
    </section>
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
      qc.invalidateQueries({ queryKey: ["alert", tenantId, alert.watari.id] });
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
          case (subject to OCSF → Watari type mapping).
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
      qc.invalidateQueries({ queryKey: ["alert", tenantId, alert.watari.id] });
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

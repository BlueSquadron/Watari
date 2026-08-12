import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { casesApi } from "@/api/resources";
import { SeverityBadge, StatusBadge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Dialog } from "@/components/common/Dialog";
import { Field, Select } from "@/components/common/Field";
import { useTenantStore } from "@/stores/tenant";
import type { Case, CaseOutcome } from "@/types/api";

const OUTCOMES: { value: CaseOutcome; label: string }[] = [
  { value: "true_positive", label: "True positive" },
  { value: "false_positive", label: "False positive" },
  { value: "indeterminate", label: "Indeterminate" },
  { value: "not_applicable", label: "Not applicable" },
];

export function CaseHeader({ case: c }: { case: Case }) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;
  const qc = useQueryClient();
  const [closing, setClosing] = useState(false);
  const [outcome, setOutcome] = useState<CaseOutcome>("true_positive");

  const closeMutation = useMutation({
    mutationFn: () => casesApi.close(tenantId, c.id, { outcome }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case", c.id] });
      qc.invalidateQueries({ queryKey: ["cases", tenantId] });
      setClosing(false);
    },
  });

  const progressMutation = useMutation({
    mutationFn: (status: Case["status"]) =>
      casesApi.update(tenantId, c.id, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case", c.id] });
      qc.invalidateQueries({ queryKey: ["cases", tenantId] });
    },
  });

  return (
    <header className="rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-mono text-watari-text-dark-secondary">
            Case #{c.case_number}
          </p>
          <h2 className="mt-1 text-2xl font-semibold text-watari-text-dark-primary">
            {c.title}
          </h2>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <SeverityBadge severity={c.severity} />
            <StatusBadge status={c.status} />
            {c.outcome ? (
              <span className="rounded-full bg-watari-bg-dark-tertiary px-2 py-0.5 text-xs uppercase tracking-wider text-watari-text-dark-primary">
                {c.outcome.replace("_", " ")}
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {c.status === "new" ? (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => progressMutation.mutate("in_progress")}
              loading={progressMutation.isPending}
            >
              Start investigation
            </Button>
          ) : null}
          {c.status === "in_progress" ? (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => progressMutation.mutate("resolved")}
              loading={progressMutation.isPending}
            >
              Mark resolved
            </Button>
          ) : null}
          {c.status !== "closed" ? (
            <Button size="sm" onClick={() => setClosing(true)}>
              Close case
            </Button>
          ) : null}
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <DescItem label="Created" value={new Date(c.created_at).toLocaleString()} />
        <DescItem
          label="Resolved"
          value={c.resolved_at ? new Date(c.resolved_at).toLocaleString() : "—"}
        />
        <DescItem
          label="Closed"
          value={c.closed_at ? new Date(c.closed_at).toLocaleString() : "—"}
        />
        <DescItem
          label="Assignee"
          value={c.assignee_id ? c.assignee_id.slice(0, 8) : "Unassigned"}
        />
      </dl>

      <Dialog
        open={closing}
        onOpenChange={setClosing}
        title="Close case"
        description="Select the outcome classification for this case"
      >
        <div className="space-y-4">
          <Field label="Outcome" required>
            <Select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value as CaseOutcome)}
            >
              {OUTCOMES.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setClosing(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => closeMutation.mutate()}
              loading={closeMutation.isPending}
            >
              Close case
            </Button>
          </div>
        </div>
      </Dialog>
    </header>
  );
}

function DescItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wider text-watari-text-dark-secondary">
        {label}
      </dt>
      <dd className="text-watari-text-dark-primary">{value}</dd>
    </div>
  );
}

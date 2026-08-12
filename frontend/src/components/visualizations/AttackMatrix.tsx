import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { attackApi } from "@/api/resources";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { Select } from "@/components/common/Field";
import { useTenantStore } from "@/stores/tenant";
import type { AttackHeatmapCell, CaseSeverity } from "@/types/api";

const SEVERITY_COLOR: Record<CaseSeverity, string> = {
  critical: "bg-severity-critical",
  high: "bg-severity-high",
  medium: "bg-severity-medium",
  low: "bg-severity-low",
  informational: "bg-severity-informational",
};

/**
 * MITRE ATT&CK heatmap.
 *
 * Columns = tactics (kill chain phases). Cells within each column =
 * techniques mapped to cases in this tenant. Colour + opacity encode
 * `case_count` (frequency) and `max_severity`.
 *
 * We render as a CSS grid — no chart library needed for this shape —
 * which keeps it fast, responsive, and accessible.
 */
export function AttackMatrix() {
  const tenantId = useTenantStore((s) => s.activeTenantId);
  const [severityFilter, setSeverityFilter] = useState<CaseSeverity | "">("");
  const [selected, setSelected] = useState<AttackHeatmapCell | null>(null);

  const { data: heatmap, isLoading } = useQuery({
    queryKey: [
      "attack-heatmap",
      tenantId,
      { case_severity: severityFilter || undefined },
    ],
    queryFn: () =>
      attackApi.heatmap(tenantId!, {
        case_severity: severityFilter || undefined,
      }),
    enabled: !!tenantId,
  });

  const { data: reference } = useQuery({
    queryKey: ["attack-reference"],
    queryFn: () => attackApi.reference(),
  });

  const tacticColumns = useMemo(() => {
    if (!heatmap?.data?.cells) return [];
    const byTactic = new Map<string, AttackHeatmapCell[]>();
    for (const cell of heatmap.data.cells) {
      const list = byTactic.get(cell.tactic_id) ?? [];
      list.push(cell);
      byTactic.set(cell.tactic_id, list);
    }
    return Array.from(byTactic.entries()).map(([tacticId, cells]) => ({
      tacticId,
      tacticName: tacticDisplayName(tacticId, reference?.data ?? []),
      cells: cells.sort((a, b) => b.case_count - a.case_count),
    }));
  }, [heatmap, reference]);

  if (!tenantId)
    return <p className="text-sm text-watari-text-dark-secondary">No tenant.</p>;
  if (isLoading || !heatmap)
    return <LoadingOverlay label="Loading ATT&CK heatmap" />;

  const maxCount = Math.max(
    1,
    ...heatmap.data.cells.map((c) => c.case_count),
  );

  if (heatmap.data.cells.length === 0) {
    return (
      <div className="space-y-4">
        <Header
          severity={severityFilter}
          onSeverityChange={setSeverityFilter}
          cellCount={0}
        />
        <div className="rounded-md border border-dashed border-watari-bg-dark-tertiary p-8 text-center text-sm text-watari-text-dark-secondary">
          No ATT&amp;CK mappings yet. Map observables or timeline entries to
          tactics/techniques from a case detail view and they&apos;ll appear here.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Header
        severity={severityFilter}
        onSeverityChange={setSeverityFilter}
        cellCount={heatmap.data.cells.length}
      />

      <div className="overflow-x-auto rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-3">
        <div
          className="grid gap-3"
          style={{
            gridTemplateColumns: `repeat(${tacticColumns.length}, minmax(140px, 1fr))`,
          }}
        >
          {tacticColumns.map((col) => (
            <div key={col.tacticId}>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-watari-text-dark-secondary">
                {col.tacticName}
                <span className="ml-1 text-watari-gold-muted">
                  ({col.tacticId})
                </span>
              </div>
              <div className="flex flex-col gap-1">
                {col.cells.map((cell) => (
                  <Cell
                    key={cell.technique_id}
                    cell={cell}
                    reference={reference?.data ?? []}
                    maxCount={maxCount}
                    selected={selected?.technique_id === cell.technique_id}
                    onSelect={() => setSelected(cell)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {selected ? (
        <div className="rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark-secondary p-4">
          <h4 className="text-sm font-semibold text-watari-text-dark-primary">
            {techniqueDisplayName(
              selected.technique_id,
              reference?.data ?? [],
            )}{" "}
            <span className="font-mono text-xs text-watari-gold-muted">
              {selected.technique_id}
            </span>
          </h4>
          <p className="mt-1 text-xs text-watari-text-dark-secondary">
            Mapped across <span className="font-semibold text-watari-gold">
              {selected.case_count}
            </span>{" "}
            case(s).{" "}
            {selected.max_severity ? (
              <>
                Highest severity:{" "}
                <span className="uppercase">{selected.max_severity}</span>.
              </>
            ) : null}
          </p>
          {selected.linked_case_ids.length > 0 ? (
            <ul className="mt-2 flex flex-wrap gap-1">
              {selected.linked_case_ids.map((cid) => (
                <li key={cid}>
                  <a
                    href={`/cases/${cid}`}
                    className="rounded bg-watari-bg-dark-tertiary px-2 py-1 font-mono text-[11px] hover:bg-watari-bg-dark"
                  >
                    {cid.slice(0, 8)}
                  </a>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Header({
  severity,
  onSeverityChange,
  cellCount,
}: {
  severity: CaseSeverity | "";
  onSeverityChange: (s: CaseSeverity | "") => void;
  cellCount: number;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h2 className="text-2xl font-semibold">ATT&amp;CK Matrix</h2>
        <p className="text-sm text-watari-text-dark-secondary">
          {cellCount} technique(s) mapped across this tenant.
        </p>
      </div>
      <Select
        value={severity}
        onChange={(e) => onSeverityChange(e.target.value as CaseSeverity | "")}
        className="!mt-0 !w-40"
      >
        <option value="">All severities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
        <option value="informational">Informational</option>
      </Select>
    </div>
  );
}

function Cell({
  cell,
  reference,
  maxCount,
  selected,
  onSelect,
}: {
  cell: AttackHeatmapCell;
  reference: Array<{ technique_id: string; name: string }>;
  maxCount: number;
  selected: boolean;
  onSelect: () => void;
}) {
  // Opacity scales monotonically with case_count; colour anchors to severity.
  const opacity = 0.35 + 0.65 * (cell.case_count / maxCount);
  const color =
    cell.max_severity && cell.max_severity in SEVERITY_COLOR
      ? SEVERITY_COLOR[cell.max_severity as CaseSeverity]
      : "bg-watari-gold-muted";
  const name = techniqueDisplayName(cell.technique_id, reference);
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`rounded-md border px-2 py-1.5 text-left text-[11px] transition-colors ${
        selected
          ? "border-watari-gold"
          : "border-transparent hover:border-watari-bg-dark-tertiary"
      }`}
      title={`${name} — ${cell.case_count} case(s), ${
        cell.max_severity ?? "no severity"
      }`}
    >
      <div
        className={`mb-1 h-1.5 rounded-full ${color}`}
        style={{ opacity }}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-watari-text-dark-primary">
          {name}
        </span>
        <span className="font-mono text-[10px] text-watari-gold">
          {cell.case_count}
        </span>
      </div>
      <div className="mt-0.5 font-mono text-[10px] text-watari-text-dark-secondary">
        {cell.technique_id}
        {cell.max_severity ? ` · ${cell.max_severity}` : ""}
      </div>
    </button>
  );
}

function techniqueDisplayName(
  techniqueId: string,
  reference: Array<{ technique_id: string; name: string }>,
): string {
  const entry = reference.find((r) => r.technique_id === techniqueId);
  return entry?.name ?? techniqueId;
}

function tacticDisplayName(tacticId: string, _reference: unknown): string {
  // Fall back to a static table if the reference doesn't provide tactic names.
  const TACTIC_NAMES: Record<string, string> = {
    TA0001: "Initial Access",
    TA0002: "Execution",
    TA0003: "Persistence",
    TA0004: "Privilege Escalation",
    TA0005: "Defense Evasion",
    TA0006: "Credential Access",
    TA0007: "Discovery",
    TA0008: "Lateral Movement",
    TA0009: "Collection",
    TA0010: "Exfiltration",
    TA0011: "Command and Control",
    TA0040: "Impact",
  };
  return TACTIC_NAMES[tacticId] ?? tacticId;
}

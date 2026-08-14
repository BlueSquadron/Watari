import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { modulesApi } from "@/api/resources";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import {
  TD,
  TH,
  THead,
  TR,
  Table,
  TableEmpty,
} from "@/components/common/Table";
import { useAuthStore } from "@/stores/auth";
import type { Module, UUID } from "@/types/api";

export function ModuleManagement() {
  const user = useAuthStore((s) => s.user);
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["modules"],
    queryFn: () => modulesApi.list(),
    enabled: user?.role === "platform_admin",
  });

  const [selected, setSelected] = useState<Module | null>(null);

  const toggle = useMutation({
    mutationFn: (args: { id: UUID; enabled: boolean }) =>
      modulesApi.update(args.id, { is_enabled: args.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["modules"] }),
  });

  if (user?.role !== "platform_admin") {
    return (
      <p className="text-sm text-watari-text-dark-secondary">
        Platform administrator role required.
      </p>
    );
  }
  if (isLoading || !data) return <LoadingOverlay label="Loading modules" />;

  const modules = data.data;

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-2xl font-semibold">Modules</h2>
        <p className="text-sm text-watari-text-dark-secondary">
          Manage installed pipeline and processor modules
        </p>
      </header>

      <Table>
        <THead>
          <TR>
            <TH>Name</TH>
            <TH className="w-28">Version</TH>
            <TH className="w-28">Type</TH>
            <TH className="w-32">Status</TH>
            <TH className="w-48">Subscribed events</TH>
            <TH className="w-40">Actions</TH>
          </TR>
        </THead>
        <tbody>
          {modules.length === 0 ? (
            <TableEmpty colSpan={6}>No modules installed.</TableEmpty>
          ) : (
            modules.map((m) => (
              <TR key={m.id}>
                <TD>
                  <div className="font-medium text-watari-text-dark-primary">
                    {m.name}
                  </div>
                  {m.description ? (
                    <div className="text-xs text-watari-text-dark-secondary">
                      {m.description}
                    </div>
                  ) : null}
                </TD>
                <TD className="font-mono text-xs">{m.version}</TD>
                <TD>
                  <Badge
                    className={
                      m.type === "pipeline"
                        ? "bg-severity-low/15 text-severity-low"
                        : "bg-watari-gold-muted/15 text-watari-gold"
                    }
                  >
                    {m.type}
                  </Badge>
                </TD>
                <TD>
                  {m.is_enabled ? (
                    <span className="rounded-full bg-status-resolved/15 px-2 py-0.5 text-xs font-medium text-status-resolved">
                      Enabled
                    </span>
                  ) : (
                    <span className="rounded-full bg-status-closed/15 px-2 py-0.5 text-xs font-medium text-status-closed">
                      Disabled
                    </span>
                  )}
                </TD>
                <TD>
                  {m.subscribed_events && m.subscribed_events.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {m.subscribed_events.slice(0, 3).map((ev) => (
                        <span
                          key={ev}
                          className="rounded bg-watari-bg-dark-tertiary px-1.5 py-0.5 font-mono text-[10px] text-watari-text-dark-secondary"
                        >
                          {ev}
                        </span>
                      ))}
                      {m.subscribed_events.length > 3 ? (
                        <span className="text-[10px] text-watari-text-dark-secondary">
                          +{m.subscribed_events.length - 3} more
                        </span>
                      ) : null}
                    </div>
                  ) : (
                    <span className="text-xs text-watari-text-dark-secondary">
                      —
                    </span>
                  )}
                </TD>
                <TD>
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setSelected(m)}
                    >
                      Details
                    </Button>
                    <Button
                      size="sm"
                      variant={m.is_enabled ? "ghost" : "secondary"}
                      onClick={() =>
                        toggle.mutate({ id: m.id, enabled: !m.is_enabled })
                      }
                    >
                      {m.is_enabled ? "Disable" : "Enable"}
                    </Button>
                  </div>
                </TD>
              </TR>
            ))
          )}
        </tbody>
      </Table>

      {selected ? (
        <div className="rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-4">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-semibold">{selected.name}</h3>
              <p className="font-mono text-xs text-watari-text-dark-secondary">
                {selected.entry_point}
              </p>
            </div>
            <Button size="sm" variant="ghost" onClick={() => setSelected(null)}>
              ×
            </Button>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <h4 className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
                Config schema
              </h4>
              <pre className="mt-2 overflow-x-auto rounded bg-watari-bg-dark-tertiary p-2 text-[11px]">
                {JSON.stringify(selected.config_schema, null, 2)}
              </pre>
            </div>
            <div>
              <h4 className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
                Metadata
              </h4>
              <dl className="mt-2 space-y-1 text-xs">
                <InfoRow label="Installed">
                  {new Date(selected.installed_at).toLocaleString()}
                </InfoRow>
                <InfoRow label="Updated">
                  {new Date(selected.updated_at).toLocaleString()}
                </InfoRow>
                {selected.supported_evidence_types?.length ? (
                  <InfoRow label="Evidence types">
                    {selected.supported_evidence_types.join(", ")}
                  </InfoRow>
                ) : null}
              </dl>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function InfoRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-2">
      <dt className="text-watari-text-dark-secondary">{label}</dt>
      <dd className="text-watari-text-dark-primary">{children}</dd>
    </div>
  );
}

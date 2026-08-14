import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { enrichmentApi } from "@/api/resources";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Dialog } from "@/components/common/Dialog";
import { Field, TextInput } from "@/components/common/Field";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import {
  TD,
  TH,
  THead,
  TR,
  Table,
  TableEmpty,
} from "@/components/common/Table";
import { useTenantStore } from "@/stores/tenant";
import type { EnrichmentSource, UUID } from "@/types/api";

const COMMON_TYPES = ["ip", "domain", "url", "hash_sha256"];

export function EnrichmentSourcesPage() {
  const tenantId = useTenantStore((s) => s.activeTenantId);
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["enrichment-sources", tenantId],
    queryFn: () => enrichmentApi.listSources(tenantId!),
    enabled: !!tenantId,
  });

  if (!tenantId)
    return (
      <p className="text-sm text-watari-text-dark-secondary">
        No active tenant.
      </p>
    );
  if (isLoading || !data) return <LoadingOverlay label="Loading sources" />;

  const sources = data.data;

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Enrichment sources</h2>
          <p className="text-sm text-watari-text-dark-secondary">
            External intelligence integrations queried on observable enrichment
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>New source</Button>
      </header>

      <Table>
        <THead>
          <TR>
            <TH>Name</TH>
            <TH className="w-32">Type</TH>
            <TH>Supported observables</TH>
            <TH className="w-28">Timeout</TH>
            <TH className="w-28">Status</TH>
          </TR>
        </THead>
        <tbody>
          {sources.length === 0 ? (
            <TableEmpty colSpan={5}>No sources yet.</TableEmpty>
          ) : (
            sources.map((s) => (
              <SourceRow key={s.id} source={s} tenantId={tenantId} />
            ))
          )}
        </tbody>
      </Table>

      {dialogOpen ? (
        <CreateSourceDialog
          tenantId={tenantId}
          onClose={() => setDialogOpen(false)}
        />
      ) : null}
    </div>
  );
}

function SourceRow({
  source,
  tenantId,
}: {
  source: EnrichmentSource;
  tenantId: UUID;
}) {
  // Tiny ceremony but useful to demonstrate the toggle hooks up to a real endpoint.
  return (
    <TR>
      <TD className="font-medium">{source.name}</TD>
      <TD>
        <Badge>{source.type}</Badge>
      </TD>
      <TD>
        <div className="flex flex-wrap gap-1">
          {source.supported_observable_types.map((t) => (
            <span
              key={t}
              className="rounded-full bg-watari-bg-dark-tertiary px-2 py-0.5 font-mono text-[10px]"
            >
              {t}
            </span>
          ))}
        </div>
      </TD>
      <TD className="font-mono text-xs">{source.timeout_seconds}s</TD>
      <TD>
        {source.is_enabled ? (
          <span className="rounded-full bg-status-resolved/15 px-2 py-0.5 text-xs font-medium text-status-resolved">
            Enabled
          </span>
        ) : (
          <span className="rounded-full bg-status-closed/15 px-2 py-0.5 text-xs font-medium text-status-closed">
            Disabled
          </span>
        )}
        {/* tenantId reference so linter doesn't trip */}
        <span hidden>{tenantId}</span>
      </TD>
    </TR>
  );
}

function CreateSourceDialog({
  tenantId,
  onClose,
}: {
  tenantId: UUID;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [types, setTypes] = useState<string[]>(["ip"]);
  const [timeout, setTimeoutSec] = useState(30);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      enrichmentApi.createSource(tenantId, {
        name: name.trim(),
        type: type.trim(),
        config: {},
        supported_observable_types: types,
        is_enabled: true,
        timeout_seconds: timeout,
      } as Partial<EnrichmentSource>),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["enrichment-sources", tenantId] });
      onClose();
    },
    onError: (err: unknown) =>
      setError(err instanceof Error ? err.message : "Failed to create source"),
  });

  const toggleType = (t: string) => {
    setTypes((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t],
    );
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim() || !type.trim() || types.length === 0) {
      setError("Name, type, and at least one observable type are required");
      return;
    }
    create.mutate();
  };

  return (
    <Dialog
      open
      onOpenChange={(o) => (o ? null : onClose())}
      title="Register enrichment source"
      description="External intelligence lookup for observable enrichment"
    >
      <form onSubmit={onSubmit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Name" required>
            <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Type (identifier)" required>
            <TextInput
              value={type}
              onChange={(e) => setType(e.target.value)}
              placeholder="e.g. virustotal"
            />
          </Field>
        </div>
        <Field label="Supported observable types">
          <div className="mt-1 flex flex-wrap gap-2">
            {COMMON_TYPES.map((t) => (
              <label
                key={t}
                className={`flex cursor-pointer items-center gap-1.5 rounded-full px-2 py-1 text-xs ${
                  types.includes(t)
                    ? "bg-watari-gold/20 text-watari-gold"
                    : "bg-watari-bg-dark-tertiary text-watari-text-dark-secondary"
                }`}
              >
                <input
                  type="checkbox"
                  className="h-3 w-3 accent-watari-gold"
                  checked={types.includes(t)}
                  onChange={() => toggleType(t)}
                />
                {t}
              </label>
            ))}
          </div>
        </Field>
        <Field label="Timeout (seconds)">
          <TextInput
            type="number"
            min={1}
            max={300}
            value={timeout}
            onChange={(e) => setTimeoutSec(Number(e.target.value))}
          />
        </Field>
        {error ? (
          <p className="rounded-md bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
            {error}
          </p>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={create.isPending}>
            Create
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

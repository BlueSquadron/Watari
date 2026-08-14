import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { enrichmentApi, observablesApi } from "@/api/resources";
import { Badge, TLPBadge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
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
import { EnrichmentResults } from "@/components/cases/EnrichmentResults";
import { useTenantStore } from "@/stores/tenant";
import type { ObservableType, TLP, UUID } from "@/types/api";

const TYPES: ObservableType[] = [
  "ip",
  "domain",
  "hostname",
  "url",
  "hash_md5",
  "hash_sha1",
  "hash_sha256",
  "email",
  "filename",
  "registry_key",
];

const TLPS: (TLP | "")[] = ["", "red", "amber", "green", "clear"];

export function ObservableList({ caseId }: { caseId: UUID }) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;
  const qc = useQueryClient();
  const [type, setType] = useState<ObservableType>("ip");
  const [value, setValue] = useState("");
  const [tlp, setTlp] = useState<TLP | "">("");
  const [isIoc, setIsIoc] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<UUID | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["case", caseId, "observables"],
    queryFn: () => observablesApi.list(tenantId, caseId),
  });

  const create = useMutation({
    mutationFn: () =>
      observablesApi.create(tenantId, caseId, {
        type,
        value: value.trim(),
        tlp: tlp || null,
        is_ioc: isIoc,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case", caseId, "observables"] });
      setValue("");
      setTlp("");
      setIsIoc(false);
      setError(null);
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Failed to add observable");
    },
  });

  const triggerEnrichment = useMutation({
    mutationFn: (ids: UUID[]) => enrichmentApi.trigger(tenantId, ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case", caseId, "observables"] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: UUID) => observablesApi.remove(tenantId, caseId, id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["case", caseId, "observables"] }),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!value.trim()) return;
    create.mutate();
  };

  if (isLoading) return <LoadingOverlay label="Loading observables" />;
  const observables = data?.data ?? [];

  return (
    <div className="space-y-4">
      <form
        onSubmit={onSubmit}
        className="grid grid-cols-1 gap-3 rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-4 md:grid-cols-6"
      >
        <Field label="Type" required>
          <Select
            value={type}
            onChange={(e) => setType(e.target.value as ObservableType)}
          >
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Value" required>
          <TextInput
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="e.g. 203.0.113.42"
            className="md:col-span-3"
          />
        </Field>
        <Field label="TLP">
          <Select
            value={tlp}
            onChange={(e) => setTlp(e.target.value as TLP | "")}
          >
            {TLPS.map((t) => (
              <option key={t || "none"} value={t}>
                {t || "(none)"}
              </option>
            ))}
          </Select>
        </Field>
        <div className="flex items-end gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isIoc}
              onChange={(e) => setIsIoc(e.target.checked)}
              className="h-4 w-4 accent-watari-gold"
            />
            IOC
          </label>
          <Button type="submit" loading={create.isPending}>
            Add
          </Button>
        </div>
        {error ? (
          <p className="md:col-span-6 rounded-md bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
            {error}
          </p>
        ) : null}
      </form>

      {observables.length > 0 ? (
        <div className="flex justify-end">
          <Button
            size="sm"
            variant="secondary"
            onClick={() =>
              triggerEnrichment.mutate(observables.map((o) => o.id))
            }
            loading={triggerEnrichment.isPending}
          >
            Run enrichment on all
          </Button>
        </div>
      ) : null}

      <Table>
        <THead>
          <TR>
            <TH className="w-32">Type</TH>
            <TH>Value</TH>
            <TH className="w-28">TLP</TH>
            <TH className="w-24">IOC</TH>
            <TH className="w-32">Seen in</TH>
            <TH className="w-40">Actions</TH>
          </TR>
        </THead>
        <tbody>
          {observables.length === 0 ? (
            <TableEmpty colSpan={6}>No observables yet.</TableEmpty>
          ) : (
            observables.flatMap((o) => {
              const isExpanded = expanded === o.id;
              return [
                <TR key={o.id}>
                  <TD>
                    <Badge>{o.type}</Badge>
                  </TD>
                  <TD className="font-mono">{o.value}</TD>
                  <TD>{o.tlp ? <TLPBadge tlp={o.tlp} /> : "—"}</TD>
                  <TD>
                    {o.is_ioc ? (
                      <span className="rounded bg-severity-critical/15 px-1.5 py-0.5 text-xs font-medium text-severity-critical">
                        IOC
                      </span>
                    ) : (
                      "—"
                    )}
                  </TD>
                  <TD className="text-watari-text-dark-secondary">
                    {o.seen_in_cases_count
                      ? `${o.seen_in_cases_count} case(s)`
                      : "—"}
                  </TD>
                  <TD>
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setExpanded(isExpanded ? null : o.id)}
                      >
                        {isExpanded ? "Hide" : "Results"}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => triggerEnrichment.mutate([o.id])}
                      >
                        Enrich
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => remove.mutate(o.id)}
                        aria-label="Delete observable"
                      >
                        ×
                      </Button>
                    </div>
                  </TD>
                </TR>,
                isExpanded ? (
                  <TR key={`${o.id}-results`}>
                    <TD className="bg-watari-bg-dark-secondary">{null}</TD>
                    <td
                      colSpan={5}
                      className="bg-watari-bg-dark-secondary px-4 py-3"
                    >
                      <EnrichmentResults caseId={caseId} observableId={o.id} />
                    </td>
                  </TR>
                ) : null,
              ];
            })
          )}
        </tbody>
      </Table>
    </div>
  );
}

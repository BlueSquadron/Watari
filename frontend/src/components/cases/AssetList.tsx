import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { assetsApi } from "@/api/resources";
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
import { useTenantStore } from "@/stores/tenant";
import type { AssetType, UUID } from "@/types/api";

const TYPES: AssetType[] = [
  "workstation",
  "server",
  "network_device",
  "mobile_device",
  "cloud_resource",
  "other",
];

export function AssetList({ caseId }: { caseId: UUID }) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [type, setType] = useState<AssetType>("workstation");
  const [ip, setIp] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["case", caseId, "assets"],
    queryFn: () => assetsApi.list(tenantId, caseId),
  });

  const create = useMutation({
    mutationFn: () =>
      assetsApi.create(tenantId, caseId, {
        name: name.trim(),
        type,
        ip_address: ip.trim() || null,
        is_compromised: false,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case", caseId, "assets"] });
      setName("");
      setIp("");
      setError(null);
    },
    onError: (err: unknown) =>
      setError(err instanceof Error ? err.message : "Failed to add asset"),
  });

  const toggleCompromise = useMutation({
    mutationFn: (args: { id: UUID; compromised: boolean }) =>
      assetsApi.update(tenantId, caseId, args.id, {
        is_compromised: args.compromised,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case", caseId, "assets"] }),
  });

  const remove = useMutation({
    mutationFn: (id: UUID) => assetsApi.remove(tenantId, caseId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case", caseId, "assets"] }),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    create.mutate();
  };

  if (isLoading) return <LoadingOverlay label="Loading assets" />;
  const assets = data?.data ?? [];
  const compromised = assets.filter((a) => a.is_compromised).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-watari-text-dark-secondary">
          Assets
        </h3>
        {assets.length > 0 ? (
          <span className="text-sm text-watari-text-dark-secondary">
            <span className="text-severity-critical">{compromised}</span>{" "}
            compromised of {assets.length}
          </span>
        ) : null}
      </div>

      <form
        onSubmit={onSubmit}
        className="grid grid-cols-1 gap-3 rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-4 md:grid-cols-4"
      >
        <Field label="Name" required>
          <TextInput
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="prod-web-01"
          />
        </Field>
        <Field label="Type">
          <Select value={type} onChange={(e) => setType(e.target.value as AssetType)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="IP address">
          <TextInput
            value={ip}
            onChange={(e) => setIp(e.target.value)}
            placeholder="10.0.0.42"
          />
        </Field>
        <div className="flex items-end">
          <Button type="submit" loading={create.isPending}>
            Add asset
          </Button>
        </div>
        {error ? (
          <p className="md:col-span-4 rounded-md bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
            {error}
          </p>
        ) : null}
      </form>

      <Table>
        <THead>
          <TR>
            <TH>Name</TH>
            <TH className="w-40">Type</TH>
            <TH className="w-40">IP address</TH>
            <TH className="w-40">Compromised</TH>
            <TH className="w-20" />
          </TR>
        </THead>
        <tbody>
          {assets.length === 0 ? (
            <TableEmpty colSpan={5}>No assets yet.</TableEmpty>
          ) : (
            assets.map((a) => (
              <TR key={a.id}>
                <TD className="font-medium">{a.name}</TD>
                <TD className="text-watari-text-dark-secondary">
                  {a.type.replace("_", " ")}
                </TD>
                <TD className="text-watari-text-dark-secondary">
                  {a.ip_address ? (
                    <span className="font-mono">{a.ip_address}</span>
                  ) : (
                    "—"
                  )}
                </TD>
                <TD>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={a.is_compromised}
                      onChange={(e) =>
                        toggleCompromise.mutate({
                          id: a.id,
                          compromised: e.target.checked,
                        })
                      }
                      className="h-4 w-4 accent-severity-critical"
                    />
                    <span
                      className={
                        a.is_compromised
                          ? "text-severity-critical"
                          : "text-watari-text-dark-secondary"
                      }
                    >
                      {a.is_compromised ? "Compromised" : "Clean"}
                    </span>
                  </label>
                </TD>
                <TD>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => remove.mutate(a.id)}
                    aria-label="Delete asset"
                  >
                    ×
                  </Button>
                </TD>
              </TR>
            ))
          )}
        </tbody>
      </Table>
    </div>
  );
}

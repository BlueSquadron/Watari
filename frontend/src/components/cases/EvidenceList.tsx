import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { evidenceApi } from "@/api/resources";
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
import type { EvidenceType, UUID } from "@/types/api";

const TYPES: EvidenceType[] = [
  "disk_image",
  "memory_dump",
  "log_export",
  "pcap",
  "document",
  "other",
];

async function sha256Hex(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const hash = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export function EvidenceList({ caseId }: { caseId: UUID }) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [type, setType] = useState<EvidenceType>("log_export");
  const [description, setDescription] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["case", caseId, "evidence"],
    queryFn: () => evidenceApi.list(tenantId, caseId),
  });

  const uploadFlow = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Select a file first");
      setError(null);
      const hash = await sha256Hex(file);
      const registered = await evidenceApi.register(tenantId, caseId, {
        filename: file.name,
        type,
        file_hash_sha256: hash,
        file_size: file.size,
        description: description.trim() || null,
      });
      const evidenceId = registered.data.id;
      const uploaded = await evidenceApi.upload(
        tenantId,
        caseId,
        evidenceId,
        file,
        password || undefined,
      );
      return uploaded.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case", caseId, "evidence"] });
      setFile(null);
      setDescription("");
      setPassword("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    onError: (err: unknown) =>
      setError(err instanceof Error ? err.message : "Upload failed"),
  });

  const remove = useMutation({
    mutationFn: (id: UUID) => evidenceApi.remove(tenantId, caseId, id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["case", caseId, "evidence"] }),
  });

  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (file) uploadFlow.mutate();
  };

  if (isLoading) return <LoadingOverlay label="Loading evidence" />;
  const items = data?.data ?? [];

  return (
    <div className="space-y-4">
      <form
        onSubmit={onSubmit}
        className="grid grid-cols-1 gap-3 rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-4 md:grid-cols-4"
      >
        <Field label="File" required>
          <input
            ref={fileInputRef}
            type="file"
            onChange={onFile}
            className="mt-1 w-full text-sm text-watari-text-dark-primary file:mr-3 file:rounded-md file:border-0 file:bg-watari-bg-dark-tertiary file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-watari-text-dark-primary hover:file:bg-watari-bg-dark-secondary"
          />
        </Field>
        <Field label="Type">
          <Select
            value={type}
            onChange={(e) => setType(e.target.value as EvidenceType)}
          >
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Password (optional)">
          <TextInput
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="encrypt file at rest"
          />
        </Field>
        <Field label="Description">
          <TextInput
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
        <div className="md:col-span-4 flex items-center justify-between">
          <p className="text-xs text-watari-text-dark-secondary">
            SHA-256 is computed client-side and verified server-side on upload.
          </p>
          <Button type="submit" loading={uploadFlow.isPending} disabled={!file}>
            Register &amp; upload
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
            <TH>Filename</TH>
            <TH className="w-28">Type</TH>
            <TH className="w-24">Size</TH>
            <TH className="w-44">Hash</TH>
            <TH className="w-36">Integrity</TH>
            <TH className="w-36">Actions</TH>
          </TR>
        </THead>
        <tbody>
          {items.length === 0 ? (
            <TableEmpty colSpan={6}>No evidence yet.</TableEmpty>
          ) : (
            items.map((ev) => (
              <TR key={ev.id}>
                <TD className="font-medium">{ev.filename}</TD>
                <TD className="text-watari-text-dark-secondary">
                  {ev.type.replace("_", " ")}
                </TD>
                <TD className="text-watari-text-dark-secondary">
                  {formatBytes(ev.file_size)}
                </TD>
                <TD className="font-mono text-xs" title={ev.file_hash_sha256}>
                  {ev.file_hash_sha256.slice(0, 16)}…
                </TD>
                <TD>
                  {integrityBadge(ev.integrity_verified, ev.integrity_mismatch)}
                </TD>
                <TD>
                  <div className="flex gap-1">
                    {ev.is_uploaded ? (
                      <a
                        href={evidenceApi.downloadUrl(tenantId, caseId, ev.id)}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-md bg-watari-bg-dark-tertiary px-3 py-1 text-xs font-medium text-watari-text-dark-primary hover:bg-watari-bg-dark-secondary"
                      >
                        Download
                      </a>
                    ) : null}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => remove.mutate(ev.id)}
                    >
                      ×
                    </Button>
                  </div>
                </TD>
              </TR>
            ))
          )}
        </tbody>
      </Table>
    </div>
  );
}

function integrityBadge(verified: boolean | null, mismatch: boolean) {
  if (mismatch) {
    return (
      <span className="rounded bg-severity-critical/15 px-2 py-0.5 text-xs font-medium text-severity-critical">
        MISMATCH
      </span>
    );
  }
  if (verified) {
    return (
      <span className="rounded bg-severity-low/15 px-2 py-0.5 text-xs font-medium text-severity-low">
        VERIFIED
      </span>
    );
  }
  return (
    <span className="text-xs text-watari-text-dark-secondary">pending</span>
  );
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024)
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

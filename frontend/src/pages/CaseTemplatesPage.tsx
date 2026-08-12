import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "@/api/client";
import { Button } from "@/components/common/Button";
import { Dialog } from "@/components/common/Dialog";
import { Field, Select, TextArea, TextInput } from "@/components/common/Field";
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
import type { ApiResponse, CaseSeverity, CaseTemplate, UUID } from "@/types/api";

const templatesApi = {
  list: (tenantId: UUID) =>
    request<ApiResponse<CaseTemplate[]>>({
      url: `/v1/tenants/${tenantId}/case-templates`,
    }),
  create: (tenantId: UUID, body: Partial<CaseTemplate>) =>
    request<ApiResponse<CaseTemplate>>({
      method: "POST",
      url: `/v1/tenants/${tenantId}/case-templates`,
      data: body,
    }),
  update: (tenantId: UUID, id: UUID, body: Partial<CaseTemplate>) =>
    request<ApiResponse<CaseTemplate>>({
      method: "PATCH",
      url: `/v1/tenants/${tenantId}/case-templates/${id}`,
      data: body,
    }),
  remove: (tenantId: UUID, id: UUID) =>
    request<void>({
      method: "DELETE",
      url: `/v1/tenants/${tenantId}/case-templates/${id}`,
    }),
};

const SEVERITIES: CaseSeverity[] = [
  "critical",
  "high",
  "medium",
  "low",
  "informational",
];

export function CaseTemplatesPage() {
  const tenantId = useTenantStore((s) => s.activeTenantId);
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["case-templates", tenantId],
    queryFn: () => templatesApi.list(tenantId!),
    enabled: !!tenantId,
  });

  const remove = useMutation({
    mutationFn: (id: UUID) => templatesApi.remove(tenantId!, id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["case-templates", tenantId] }),
  });

  if (!tenantId)
    return (
      <p className="text-sm text-watari-text-dark-secondary">No active tenant.</p>
    );
  if (isLoading || !data) return <LoadingOverlay label="Loading templates" />;

  const templates = data.data;

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Case templates</h2>
          <p className="text-sm text-watari-text-dark-secondary">
            Standardise case creation for common incident types
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>New template</Button>
      </header>

      <Table>
        <THead>
          <TR>
            <TH>Name</TH>
            <TH className="w-32">Default severity</TH>
            <TH>Default tags</TH>
            <TH className="w-20">Tasks</TH>
            <TH className="w-20" />
          </TR>
        </THead>
        <tbody>
          {templates.length === 0 ? (
            <TableEmpty colSpan={5}>No templates yet.</TableEmpty>
          ) : (
            templates.map((t) => (
              <TR key={t.id}>
                <TD>
                  <div className="font-medium text-watari-text-dark-primary">
                    {t.name}
                  </div>
                  {t.description ? (
                    <div className="text-xs text-watari-text-dark-secondary">
                      {t.description}
                    </div>
                  ) : null}
                </TD>
                <TD>
                  {t.default_severity ? (
                    <span className="rounded-full bg-watari-bg-dark-tertiary px-2 py-0.5 text-xs uppercase tracking-wide">
                      {t.default_severity}
                    </span>
                  ) : (
                    "—"
                  )}
                </TD>
                <TD>
                  <div className="flex flex-wrap gap-1">
                    {t.default_tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full bg-watari-bg-dark-tertiary px-2 py-0.5 text-xs"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </TD>
                <TD className="text-watari-text-dark-secondary">
                  {t.tasks.length}
                </TD>
                <TD>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => remove.mutate(t.id)}
                  >
                    ×
                  </Button>
                </TD>
              </TR>
            ))
          )}
        </tbody>
      </Table>

      {dialogOpen ? (
        <CreateTemplateDialog
          tenantId={tenantId}
          onClose={() => setDialogOpen(false)}
        />
      ) : null}
    </div>
  );
}

function CreateTemplateDialog({
  tenantId,
  onClose,
}: {
  tenantId: UUID;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<CaseSeverity>("medium");
  const [tags, setTags] = useState("");
  const [tasksText, setTasksText] = useState(
    "Identify scope\nCollect evidence\nAnalyse findings\nRemediate",
  );
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      templatesApi.create(tenantId, {
        name: name.trim(),
        description: description.trim() || null,
        default_severity: severity,
        default_tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        tasks: tasksText
          .split("\n")
          .map((l) => l.trim())
          .filter(Boolean)
          .map((title, idx) => ({ title, sort_order: idx })),
        custom_fields: {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case-templates", tenantId] });
      onClose();
    },
    onError: (err: unknown) =>
      setError(err instanceof Error ? err.message : "Failed to create template"),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) return setError("Name is required");
    create.mutate();
  };

  return (
    <Dialog
      open
      onOpenChange={(o) => (o ? null : onClose())}
      title="Create case template"
      description="Define a reusable case structure for common incident types"
    >
      <form onSubmit={onSubmit} className="space-y-3">
        <Field label="Name" required>
          <TextInput value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Description">
          <TextInput
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Default severity">
            <Select
              value={severity}
              onChange={(e) => setSeverity(e.target.value as CaseSeverity)}
            >
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Default tags (comma-separated)">
            <TextInput value={tags} onChange={(e) => setTags(e.target.value)} />
          </Field>
        </div>
        <Field label="Tasks (one per line)">
          <TextArea
            rows={6}
            value={tasksText}
            onChange={(e) => setTasksText(e.target.value)}
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

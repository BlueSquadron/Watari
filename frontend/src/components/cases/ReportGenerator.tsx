import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { reportsApi } from "@/api/resources";
import { Button } from "@/components/common/Button";
import { Field, Select } from "@/components/common/Field";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { useTenantStore } from "@/stores/tenant";
import type { UUID } from "@/types/api";

const FORMATS = [
  { value: "markdown", label: "Markdown" },
  { value: "html", label: "HTML" },
  { value: "docx", label: "DOCX" },
] as const;

type FormatValue = (typeof FORMATS)[number]["value"];

/**
 * Report generation UI.
 *
 * Lets the user pick a template + format, preview the rendered Markdown
 * in-page, then trigger generation. Generated reports come back with a
 * `storage_path` — the UI surfaces the path so a user can retrieve the
 * file from the datastore (download endpoint would be added later).
 */
export function ReportGenerator({ caseId }: { caseId: UUID }) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;

  const templatesQuery = useQuery({
    queryKey: ["report-templates", tenantId],
    queryFn: () => reportsApi.templates(tenantId),
  });

  const [templateId, setTemplateId] = useState<UUID | null>(null);
  const [format, setFormat] = useState<FormatValue>("markdown");
  const [preview, setPreview] = useState<string>("");
  const [previewing, setPreviewing] = useState(false);
  const [generated, setGenerated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const templates = templatesQuery.data?.data ?? [];

  useEffect(() => {
    if (templates.length > 0 && !templateId) {
      setTemplateId(templates[0].id);
    }
  }, [templates, templateId]);

  const selectedTemplate = useMemo(
    () => templates.find((t) => t.id === templateId) ?? null,
    [templateId, templates],
  );

  const loadPreview = useMutation({
    mutationFn: async () => {
      if (!templateId) throw new Error("Select a template first");
      setError(null);
      setPreviewing(true);
      try {
        const markdown = await reportsApi.preview(tenantId, caseId, templateId);
        setPreview(markdown);
      } finally {
        setPreviewing(false);
      }
    },
    onError: (err: unknown) =>
      setError(err instanceof Error ? err.message : "Preview failed"),
  });

  const generate = useMutation({
    mutationFn: async () => {
      if (!templateId) throw new Error("Select a template first");
      setError(null);
      const result = await reportsApi.generate(
        tenantId,
        caseId,
        templateId,
        format,
      );
      return result.data;
    },
    onSuccess: (data) => {
      setGenerated(data.storage_path ?? null);
    },
    onError: (err: unknown) =>
      setError(err instanceof Error ? err.message : "Generation failed"),
  });

  if (templatesQuery.isLoading) return <LoadingOverlay label="Loading templates" />;

  if (templates.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-watari-bg-dark-tertiary p-6 text-center text-sm text-watari-text-dark-secondary">
        No report templates configured yet. A tenant administrator can create
        one from <span className="font-mono">Admin → Templates</span>.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-4 md:grid-cols-3">
        <Field label="Template" required>
          <Select
            value={templateId ?? ""}
            onChange={(e) => setTemplateId(e.target.value)}
          >
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.type})
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Format">
          <Select
            value={format}
            onChange={(e) => setFormat(e.target.value as FormatValue)}
          >
            {FORMATS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </Select>
        </Field>
        <div className="flex items-end gap-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => loadPreview.mutate()}
            loading={previewing}
            disabled={!templateId}
          >
            Preview
          </Button>
          <Button
            type="button"
            onClick={() => generate.mutate()}
            loading={generate.isPending}
            disabled={!templateId}
          >
            Generate
          </Button>
        </div>
        {selectedTemplate ? (
          <p className="md:col-span-3 text-xs text-watari-text-dark-secondary">
            {selectedTemplate.type === "investigation"
              ? "Investigation reports include case metadata, observables, assets, timeline, notes, evidence, and ATT&CK mappings."
              : "Activity reports summarise the audit trail for this case."}
          </p>
        ) : null}
        {error ? (
          <p className="md:col-span-3 rounded-md bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
            {error}
          </p>
        ) : null}
        {generated ? (
          <div className="md:col-span-3 rounded-md bg-severity-resolved/10 px-3 py-2 text-sm text-severity-resolved">
            Report stored at{" "}
            <span className="font-mono text-xs">{generated}</span>
          </div>
        ) : null}
      </div>

      {preview ? (
        <div className="rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-4">
          <h4 className="mb-2 text-xs uppercase tracking-wider text-watari-text-dark-secondary">
            Preview (rendered Markdown)
          </h4>
          <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap rounded-md bg-watari-bg-dark-secondary p-3 text-xs text-watari-text-dark-primary">
            {preview}
          </pre>
        </div>
      ) : null}
    </div>
  );
}

import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { casesApi } from "@/api/resources";
import { Button } from "@/components/common/Button";
import { Dialog } from "@/components/common/Dialog";
import { Field, Select, TextArea, TextInput } from "@/components/common/Field";
import { useTenantStore } from "@/stores/tenant";
import type { Case, CaseSeverity } from "@/types/api";

const SEVERITIES: CaseSeverity[] = [
  "critical",
  "high",
  "medium",
  "low",
  "informational",
];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (c: Case) => void;
}

export function CreateCaseDialog({ open, onOpenChange, onCreated }: Props) {
  const tenantId = useTenantStore((s) => s.activeTenantId);
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<CaseSeverity>("medium");
  const [tags, setTags] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      casesApi.create(tenantId!, {
        title: title.trim(),
        description: description.trim() || null,
        severity,
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      }),
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ["cases", tenantId] });
      onOpenChange(false);
      setTitle("");
      setDescription("");
      setSeverity("medium");
      setTags("");
      onCreated?.(response.data);
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Failed to create case");
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    mutation.mutate();
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Create case"
      description="Record a new security case for this tenant"
    >
      <form onSubmit={onSubmit} className="space-y-3">
        <Field label="Title" required>
          <TextInput
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Suspicious login activity from 203.0.113.42"
            maxLength={500}
          />
        </Field>

        <Field label="Description">
          <TextArea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
          />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Severity" required>
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
          <Field label="Tags (comma-separated)">
            <TextInput
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="phishing, exfil"
            />
          </Field>
        </div>

        {error ? (
          <p className="rounded-md bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
            {error}
          </p>
        ) : null}

        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={mutation.isPending}
          >
            Cancel
          </Button>
          <Button type="submit" loading={mutation.isPending}>
            Create
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { timelineApi } from "@/api/resources";
import { Button } from "@/components/common/Button";
import { Field, Select, TextArea, TextInput } from "@/components/common/Field";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { useTenantStore } from "@/stores/tenant";
import type { UUID } from "@/types/api";

export function CaseTimeline({ caseId }: { caseId: UUID }) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;
  const qc = useQueryClient();
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [eventType, setEventType] = useState("note");
  const [description, setDescription] = useState("");
  const [timestamp, setTimestamp] = useState(() =>
    new Date().toISOString().slice(0, 16),
  );

  const { data, isLoading } = useQuery({
    queryKey: ["case", caseId, "timeline", order],
    queryFn: () => timelineApi.list(tenantId, caseId, { order }),
  });

  const addManual = useMutation({
    mutationFn: () =>
      timelineApi.addManual(tenantId, caseId, {
        event_type: eventType,
        event_timestamp: new Date(timestamp).toISOString(),
        description,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case", caseId, "timeline"] });
      setDescription("");
    },
  });

  const entries = useMemo(() => data?.data ?? [], [data]);

  if (isLoading) return <LoadingOverlay label="Loading timeline" />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-watari-text-dark-secondary">
          {entries.length} timeline entries
        </h3>
        <Select
          value={order}
          onChange={(e) => setOrder(e.target.value as "asc" | "desc")}
          className="!mt-0 !w-40"
        >
          <option value="asc">Oldest first</option>
          <option value="desc">Newest first</option>
        </Select>
      </div>

      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          if (description.trim()) addManual.mutate();
        }}
        className="grid grid-cols-1 gap-3 rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-4 md:grid-cols-4"
      >
        <Field label="Event type">
          <TextInput
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            placeholder="note"
          />
        </Field>
        <Field label="Timestamp">
          <TextInput
            type="datetime-local"
            value={timestamp}
            onChange={(e) => setTimestamp(e.target.value)}
          />
        </Field>
        <Field label="Description" required>
          <TextArea
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What happened at this time?"
          />
        </Field>
        <div className="flex items-end">
          <Button
            type="submit"
            loading={addManual.isPending}
            disabled={!description.trim()}
          >
            Add manual entry
          </Button>
        </div>
      </form>

      <ol className="space-y-3">
        {entries.length === 0 ? (
          <li className="rounded-md border border-dashed border-watari-bg-dark-tertiary p-6 text-center text-sm text-watari-text-dark-secondary">
            No timeline entries yet.
          </li>
        ) : (
          entries.map((e) => (
            <li
              key={e.id}
              className="flex gap-3 rounded-md border border-watari-bg-dark-tertiary bg-watari-bg-dark px-3 py-2"
            >
              <span
                className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ${
                  e.is_automatic ? "bg-watari-gold-muted" : "bg-watari-gold"
                }`}
                aria-hidden
              />
              <div className="flex-1">
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="text-xs font-medium uppercase tracking-wider text-watari-text-dark-secondary">
                    {e.event_type}
                  </span>
                  <span className="text-xs text-watari-text-dark-secondary">
                    {new Date(e.event_timestamp).toLocaleString()}
                  </span>
                  {!e.is_automatic ? (
                    <span className="rounded bg-watari-bg-dark-tertiary px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-watari-text-dark-secondary">
                      manual
                    </span>
                  ) : null}
                </div>
                <p className="mt-0.5 text-sm text-watari-text-dark-primary">
                  {e.description}
                </p>
              </div>
            </li>
          ))
        )}
      </ol>
    </div>
  );
}

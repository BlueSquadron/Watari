import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { tasksApi } from "@/api/resources";
import { Button } from "@/components/common/Button";
import { Select, TextInput } from "@/components/common/Field";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { useTenantStore } from "@/stores/tenant";
import type { TaskStatus, UUID } from "@/types/api";

const STATUSES: TaskStatus[] = ["todo", "in_progress", "done", "cancelled"];

export function TaskList({ caseId }: { caseId: UUID }) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["case", caseId, "tasks"],
    queryFn: () => tasksApi.list(tenantId, caseId),
  });

  const [title, setTitle] = useState("");
  const create = useMutation({
    mutationFn: () =>
      tasksApi.create(tenantId, caseId, { title: title.trim() }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case", caseId, "tasks"] });
      setTitle("");
    },
  });
  const update = useMutation({
    mutationFn: (args: { id: UUID; status: TaskStatus }) =>
      tasksApi.update(tenantId, caseId, args.id, { status: args.status }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["case", caseId, "tasks"] }),
  });
  const remove = useMutation({
    mutationFn: (id: UUID) => tasksApi.remove(tenantId, caseId, id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["case", caseId, "tasks"] }),
  });

  const tasks = data?.data ?? [];
  const completed = tasks.filter(
    (t) => t.status === "done" || t.status === "cancelled",
  ).length;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (title.trim()) create.mutate();
  };

  if (isLoading) return <LoadingOverlay label="Loading tasks" />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-watari-text-dark-secondary">
          Tasks ({completed}/{tasks.length})
        </h3>
        <div className="h-1.5 w-40 overflow-hidden rounded-full bg-watari-bg-dark-tertiary">
          <div
            className="h-full bg-watari-gold"
            style={{
              width: tasks.length
                ? `${(completed / tasks.length) * 100}%`
                : "0%",
            }}
          />
        </div>
      </div>

      <form onSubmit={onSubmit} className="flex gap-2">
        <TextInput
          placeholder="Add a task…"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="!mt-0 flex-1"
        />
        <Button
          type="submit"
          loading={create.isPending}
          disabled={!title.trim()}
        >
          Add
        </Button>
      </form>

      <ul className="space-y-1">
        {tasks.length === 0 ? (
          <li className="rounded-md border border-dashed border-watari-bg-dark-tertiary p-6 text-center text-sm text-watari-text-dark-secondary">
            No tasks yet.
          </li>
        ) : (
          tasks.map((t) => (
            <li
              key={t.id}
              className="flex items-center gap-3 rounded-md border border-watari-bg-dark-tertiary bg-watari-bg-dark px-3 py-2"
            >
              <Select
                value={t.status}
                onChange={(e) =>
                  update.mutate({
                    id: t.id,
                    status: e.target.value as TaskStatus,
                  })
                }
                className="!mt-0 !w-36"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.replace("_", " ")}
                  </option>
                ))}
              </Select>
              <span
                className={
                  t.status === "done" || t.status === "cancelled"
                    ? "flex-1 text-sm text-watari-text-dark-secondary line-through"
                    : "flex-1 text-sm text-watari-text-dark-primary"
                }
              >
                {t.title}
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => remove.mutate(t.id)}
                aria-label="Delete task"
              >
                ×
              </Button>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { auditApi } from "@/api/resources";
import { Badge } from "@/components/common/Badge";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { Select, TextInput } from "@/components/common/Field";
import {
  TD,
  TH,
  THead,
  TR,
  Table,
  TableEmpty,
} from "@/components/common/Table";
import { useTenantStore } from "@/stores/tenant";

const RESOURCE_TYPES = [
  "",
  "case",
  "task",
  "observable",
  "asset",
  "evidence",
  "note",
  "alert",
  "user",
  "module",
  "report",
];

export function AuditLogViewer() {
  const tenantId = useTenantStore((s) => s.activeTenantId);
  const [resourceType, setResourceType] = useState("");
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["audit-logs", tenantId, resourceType, action, page],
    queryFn: () =>
      auditApi.list(tenantId!, {
        page,
        page_size: 50,
        resource_type: resourceType || undefined,
        action: action || undefined,
      }),
    enabled: !!tenantId,
  });

  if (!tenantId)
    return (
      <p className="text-sm text-watari-text-dark-secondary">No active tenant.</p>
    );

  const logs = data?.data ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-2xl font-semibold">Audit log</h2>
        <p className="text-sm text-watari-text-dark-secondary">
          Complete trail of user and service-account actions
        </p>
      </header>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <Select
          value={resourceType}
          onChange={(e) => {
            setPage(1);
            setResourceType(e.target.value);
          }}
        >
          {RESOURCE_TYPES.map((t) => (
            <option key={t || "any"} value={t}>
              {t || "Any resource type"}
            </option>
          ))}
        </Select>
        <TextInput
          placeholder="Filter by action (e.g. POST /api/v1/...)"
          value={action}
          onChange={(e) => {
            setPage(1);
            setAction(e.target.value);
          }}
        />
      </div>

      {isLoading ? (
        <LoadingOverlay label="Loading audit log" />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH className="w-44">Timestamp</TH>
              <TH className="w-40">User</TH>
              <TH>Action</TH>
              <TH className="w-28">Resource</TH>
              <TH className="w-36">Source IP</TH>
            </TR>
          </THead>
          <tbody>
            {logs.length === 0 ? (
              <TableEmpty colSpan={5}>No audit entries match.</TableEmpty>
            ) : (
              logs.map((log) => (
                <TR key={log.id}>
                  <TD className="font-mono text-xs text-watari-text-dark-secondary">
                    {new Date(log.created_at).toLocaleString()}
                  </TD>
                  <TD>
                    <div className="font-mono text-xs">
                      {log.user_id.slice(0, 8)}
                    </div>
                    {log.is_service_account ? (
                      <span className="inline-block rounded bg-watari-gold-muted/20 px-1 py-0.5 text-[10px] font-medium text-watari-gold">
                        SVC
                      </span>
                    ) : null}
                  </TD>
                  <TD className="font-mono text-xs">{log.action}</TD>
                  <TD>
                    <Badge>{log.resource_type}</Badge>
                  </TD>
                  <TD className="font-mono text-xs text-watari-text-dark-secondary">
                    {log.source_ip ?? "—"}
                  </TD>
                </TR>
              ))
            )}
          </tbody>
        </Table>
      )}

      {meta ? (
        <div className="flex items-center justify-between text-xs text-watari-text-dark-secondary">
          <span>
            Page {meta.page} of {meta.total_pages} · {meta.total_count} total entries
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-md border border-watari-bg-dark-tertiary px-3 py-1 hover:bg-watari-bg-dark-tertiary disabled:opacity-50"
              disabled={page <= 1 || isFetching}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              ← Prev
            </button>
            <button
              type="button"
              className="rounded-md border border-watari-bg-dark-tertiary px-3 py-1 hover:bg-watari-bg-dark-tertiary disabled:opacity-50"
              disabled={page >= (meta.total_pages ?? 1) || isFetching}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

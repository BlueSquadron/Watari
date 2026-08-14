import { useQuery } from "@tanstack/react-query";
import { observablesApi } from "@/api/resources";
import { useTenantStore } from "@/stores/tenant";
import type { UUID } from "@/types/api";

export function EnrichmentResults({
  caseId,
  observableId,
}: {
  caseId: UUID;
  observableId: UUID;
}) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;
  const { data, isLoading } = useQuery({
    queryKey: ["enrichment-results", observableId],
    queryFn: () =>
      observablesApi.enrichmentResults(tenantId, caseId, observableId),
  });

  if (isLoading) {
    return (
      <p className="text-xs text-watari-text-dark-secondary">
        Loading results…
      </p>
    );
  }

  const results = data?.data ?? [];
  if (results.length === 0) {
    return (
      <p className="text-xs text-watari-text-dark-secondary">
        No enrichment results yet. Click{" "}
        <span className="font-medium">Enrich</span> to trigger a lookup.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {results.map((r) => (
        <li
          key={r.id}
          className="rounded-md border border-watari-bg-dark-tertiary bg-watari-bg-dark px-3 py-2 text-xs"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium text-watari-text-dark-primary">
              {r.source_name ?? r.source_id.slice(0, 8)}
            </span>
            <span
              className={
                r.status === "success"
                  ? "rounded bg-severity-low/15 px-1.5 py-0.5 text-severity-low"
                  : "rounded bg-severity-critical/15 px-1.5 py-0.5 text-severity-critical"
              }
            >
              {r.status}
            </span>
          </div>
          <p className="mt-1 text-watari-text-dark-secondary">
            {new Date(r.queried_at).toLocaleString()}
          </p>
          {r.result_data ? (
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded bg-watari-bg-dark-tertiary p-2 text-[11px] text-watari-text-dark-primary">
              {JSON.stringify(r.result_data, null, 2)}
            </pre>
          ) : null}
          {r.error_message ? (
            <p className="mt-2 text-severity-critical">{r.error_message}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

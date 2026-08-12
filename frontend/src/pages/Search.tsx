import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { searchApi } from "@/api/resources";
import { Button } from "@/components/common/Button";
import { TextInput } from "@/components/common/Field";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { useTenantStore } from "@/stores/tenant";
import type { SearchResponse } from "@/types/api";

const ENTITY_LABELS: Record<string, string> = {
  case: "Case",
  observable: "Observable",
  asset: "Asset",
  note: "Note",
  alert: "Alert",
};

/**
 * Full-text search page. Queries the backend /search endpoint and
 * groups results by entity type. Clicking a hit navigates to the best
 * contextual destination (case detail for case/observable/asset/note;
 * alert queue for alerts).
 */
export function SearchPage() {
  const tenantId = useTenantStore((s) => s.activeTenantId);
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  const search = useMutation({
    mutationFn: async () => {
      if (!tenantId) throw new Error("No active tenant");
      const response = await searchApi.search(tenantId, query.trim());
      return response.data;
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim().length < 2) return;
    search.mutate();
  };

  const grouped = groupByEntityType(search.data);

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-2xl font-semibold">Search</h2>
        <p className="text-sm text-watari-text-dark-secondary">
          Full-text search across cases, observables, assets, notes, and alerts
        </p>
      </header>

      <form onSubmit={onSubmit} className="flex gap-2">
        <TextInput
          autoFocus
          placeholder="Search query (min 2 characters)…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="!mt-0 flex-1"
        />
        <Button type="submit" loading={search.isPending} disabled={query.trim().length < 2}>
          Search
        </Button>
      </form>

      {search.isPending ? <LoadingOverlay label="Searching" /> : null}

      {search.data && search.data.hits.length === 0 ? (
        <p className="rounded-md border border-dashed border-watari-bg-dark-tertiary p-6 text-center text-sm text-watari-text-dark-secondary">
          No results for &ldquo;{search.data.query}&rdquo;.
        </p>
      ) : null}

      {search.data && search.data.hits.length > 0 ? (
        <div className="space-y-3">
          <p className="text-xs text-watari-text-dark-secondary">
            {search.data.total_hits} result{search.data.total_hits === 1 ? "" : "s"} for &ldquo;{search.data.query}&rdquo;
          </p>
          {Object.entries(grouped).map(([entityType, hits]) => (
            <div
              key={entityType}
              className="rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark"
            >
              <h3 className="border-b border-watari-bg-dark-tertiary px-4 py-2 text-xs font-semibold uppercase tracking-wider text-watari-text-dark-secondary">
                {ENTITY_LABELS[entityType] ?? entityType} ({hits.length})
              </h3>
              <ul>
                {hits.map((hit) => (
                  <li
                    key={`${hit.entity_type}:${hit.entity_id}`}
                    className="border-b border-watari-bg-dark-tertiary last:border-none"
                  >
                    <button
                      type="button"
                      onClick={() => {
                        if (hit.case_id) navigate(`/cases/${hit.case_id}`);
                        else if (hit.entity_type === "alert") navigate("/alerts");
                        else navigate("/cases");
                      }}
                      className="w-full px-4 py-3 text-left hover:bg-watari-bg-dark-tertiary"
                    >
                      <div className="font-medium text-watari-text-dark-primary">
                        {hit.title}
                      </div>
                      <div className="mt-0.5 truncate text-xs text-watari-text-dark-secondary">
                        {hit.snippet}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function groupByEntityType(
  response: SearchResponse | undefined,
): Record<string, SearchResponse["hits"]> {
  const grouped: Record<string, SearchResponse["hits"]> = {};
  if (!response) return grouped;
  for (const hit of response.hits) {
    (grouped[hit.entity_type] ??= []).push(hit);
  }
  return grouped;
}

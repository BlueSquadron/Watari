import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import CytoscapeComponent from "react-cytoscapejs";
import type { Core, ElementDefinition } from "cytoscape";
import { assetsApi, observablesApi, timelineApi } from "@/api/resources";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { Select } from "@/components/common/Field";
import { useTenantStore } from "@/stores/tenant";
import type { UUID } from "@/types/api";

type NodeType = "case" | "observable" | "asset" | "timeline_entry";

const NODE_COLORS: Record<NodeType, string> = {
  case: "#c4a35a",
  observable: "#3b82f6",
  asset: "#ef4444",
  timeline_entry: "#9b9a97",
};

/**
 * Entity relationship graph rendered with Cytoscape.js via react-cytoscapejs.
 *
 * Nodes: the case + every observable + every asset + every timeline entry
 * linked to one of them.
 * Edges:
 *   case → observable (contains)
 *   case → asset (contains)
 *   asset ↔ timeline_entry (linked)
 *   observable ↔ observable (cross-case correlation, shown when
 *   `seen_in_cases_count > 0`)
 */
export function CaseGraph({ caseId }: { caseId: UUID }) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;
  const [includeCrossCase, setIncludeCrossCase] = useState(true);
  const [filterType, setFilterType] = useState<"all" | NodeType>("all");

  const observablesQuery = useQuery({
    queryKey: ["case", caseId, "observables"],
    queryFn: () => observablesApi.list(tenantId, caseId),
  });
  const assetsQuery = useQuery({
    queryKey: ["case", caseId, "assets"],
    queryFn: () => assetsApi.list(tenantId, caseId),
  });
  const timelineQuery = useQuery({
    queryKey: ["case", caseId, "timeline-graph"],
    queryFn: () => timelineApi.list(tenantId, caseId, { order: "asc" }),
  });

  const elements = useMemo<ElementDefinition[]>(() => {
    if (
      !observablesQuery.data ||
      !assetsQuery.data ||
      !timelineQuery.data
    ) {
      return [];
    }
    const observables = observablesQuery.data.data;
    const assets = assetsQuery.data.data;
    const timeline = timelineQuery.data.data;

    const typeFilter = filterType === "all" ? null : filterType;
    const nodes: ElementDefinition[] = [];
    const edges: ElementDefinition[] = [];

    // Case node (central hub)
    if (!typeFilter || typeFilter === "case") {
      nodes.push({
        data: {
          id: `case:${caseId}`,
          label: `Case ${caseId.slice(0, 8)}`,
          type: "case",
        },
        classes: "type-case",
      });
    }

    // Observables
    if (!typeFilter || typeFilter === "observable") {
      for (const o of observables) {
        nodes.push({
          data: {
            id: `obs:${o.id}`,
            label: `${o.type}\n${o.value.slice(0, 20)}`,
            type: "observable",
            crossCase: o.seen_in_cases_count ?? 0,
          },
          classes: `type-observable${o.is_ioc ? " ioc" : ""}`,
        });
        if (!typeFilter || filterType === "all") {
          edges.push({
            data: {
              id: `case-obs:${o.id}`,
              source: `case:${caseId}`,
              target: `obs:${o.id}`,
              label: "contains",
            },
            classes: "edge-contains",
          });
        }
        // Cross-case correlation edges
        if (includeCrossCase && (o.seen_in_cases_count ?? 0) > 0) {
          nodes.push({
            data: {
              id: `xcase:${o.id}`,
              label: `${o.seen_in_cases_count} other case(s)`,
              type: "case",
            },
            classes: "type-case cross-case",
          });
          edges.push({
            data: {
              id: `xcorr:${o.id}`,
              source: `obs:${o.id}`,
              target: `xcase:${o.id}`,
              label: "correlates",
            },
            classes: "edge-correlates",
          });
        }
      }
    }

    // Assets
    if (!typeFilter || typeFilter === "asset") {
      for (const a of assets) {
        nodes.push({
          data: {
            id: `asset:${a.id}`,
            label: a.name,
            type: "asset",
            compromised: a.is_compromised,
          },
          classes: `type-asset${a.is_compromised ? " compromised" : ""}`,
        });
        if (!typeFilter || filterType === "all") {
          edges.push({
            data: {
              id: `case-asset:${a.id}`,
              source: `case:${caseId}`,
              target: `asset:${a.id}`,
              label: "contains",
            },
            classes: "edge-contains",
          });
        }
      }
    }

    // Timeline entries + asset links
    if (!typeFilter || typeFilter === "timeline_entry") {
      for (const t of timeline) {
        if (!t.linked_asset_ids || t.linked_asset_ids.length === 0) continue;
        nodes.push({
          data: {
            id: `tl:${t.id}`,
            label: t.event_type,
            type: "timeline_entry",
          },
          classes: "type-timeline",
        });
        for (const assetId of t.linked_asset_ids) {
          edges.push({
            data: {
              id: `tl-asset:${t.id}:${assetId}`,
              source: `tl:${t.id}`,
              target: `asset:${assetId}`,
              label: "linked",
            },
            classes: "edge-linked",
          });
        }
      }
    }

    return [...nodes, ...edges];
  }, [
    observablesQuery.data,
    assetsQuery.data,
    timelineQuery.data,
    caseId,
    filterType,
    includeCrossCase,
  ]);

  if (
    observablesQuery.isLoading ||
    assetsQuery.isLoading ||
    timelineQuery.isLoading
  ) {
    return <LoadingOverlay label="Building graph" />;
  }

  const nodeCount = elements.filter((e) => !e.data.source).length;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
          Entity graph ({nodeCount} nodes)
        </h4>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={includeCrossCase}
              onChange={(e) => setIncludeCrossCase(e.target.checked)}
              className="h-3.5 w-3.5 accent-watari-gold"
            />
            Cross-case correlations
          </label>
          <Select
            value={filterType}
            onChange={(e) =>
              setFilterType(e.target.value as "all" | NodeType)
            }
            className="!mt-0 !w-48"
          >
            <option value="all">All node types</option>
            <option value="observable">Observables only</option>
            <option value="asset">Assets only</option>
            <option value="timeline_entry">Timeline events only</option>
          </Select>
        </div>
      </div>

      <div className="h-[560px] overflow-hidden rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark">
        {elements.length > 0 ? (
          <CytoscapeComponent
            elements={elements}
            cy={(cy: Core) => {
              cy.on("tap", "node", (evt) => {
                const node = evt.target;
                node.select();
              });
            }}
            layout={{
              name: "cose",
              idealEdgeLength: () => 120,
              nodeOverlap: 16,
              animate: true,
              animationDuration: 600,
              gravity: 0.7,
              componentSpacing: 80,
            }}
            stylesheet={[
              {
                selector: "node",
                style: {
                  label: "data(label)",
                  color: "#e8e6e1",
                  "text-wrap": "wrap",
                  "text-max-width": "140px",
                  "font-size": 10,
                  "text-valign": "bottom",
                  "text-margin-y": 8,
                  "background-color": "#9b9a97",
                  width: 28,
                  height: 28,
                  "border-width": 2,
                  "border-color": "#0f1117",
                },
              },
              {
                selector: "node.type-case",
                style: {
                  "background-color": NODE_COLORS.case,
                  shape: "round-rectangle",
                  width: 60,
                  height: 32,
                },
              },
              {
                selector: "node.type-observable",
                style: { "background-color": NODE_COLORS.observable },
              },
              {
                selector: "node.type-observable.ioc",
                style: {
                  "border-color": "#ef4444",
                  "border-width": 3,
                },
              },
              {
                selector: "node.type-asset",
                style: {
                  "background-color": NODE_COLORS.asset,
                  shape: "diamond",
                  width: 32,
                  height: 32,
                },
              },
              {
                selector: "node.type-asset.compromised",
                style: {
                  "border-color": "#ef4444",
                  "border-width": 3,
                },
              },
              {
                selector: "node.type-timeline",
                style: {
                  "background-color": NODE_COLORS.timeline_entry,
                  shape: "triangle",
                  width: 20,
                  height: 20,
                },
              },
              {
                selector: "node.cross-case",
                style: {
                  opacity: 0.6,
                  "background-color": "#242836",
                  color: "#9b9a97",
                },
              },
              {
                selector: "edge",
                style: {
                  width: 1.5,
                  "line-color": "#242836",
                  "target-arrow-color": "#242836",
                  "target-arrow-shape": "triangle",
                  "curve-style": "bezier",
                  label: "data(label)",
                  "font-size": 8,
                  color: "#5c5c5c",
                  "text-rotation": "autorotate",
                  "text-background-color": "#0f1117",
                  "text-background-opacity": 0.8,
                  "text-background-padding": 2,
                },
              },
              {
                selector: "edge.edge-correlates",
                style: {
                  "line-style": "dashed",
                  "line-color": "#c4a35a",
                  "target-arrow-color": "#c4a35a",
                },
              },
              {
                selector: "node:selected",
                style: {
                  "border-color": "#c4a35a",
                  "border-width": 4,
                },
              },
            ]}
            style={{ width: "100%", height: "100%" }}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-watari-text-dark-secondary">
            Nothing to show yet. Add observables or assets and the graph will
            populate.
          </div>
        )}
      </div>
    </div>
  );
}

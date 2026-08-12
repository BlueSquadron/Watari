import { useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AxisTop } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleTime } from "@visx/scale";
import { Zoom } from "@visx/zoom";
import { timelineApi } from "@/api/resources";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { useTenantStore } from "@/stores/tenant";
import type { TemporalCluster, UUID } from "@/types/api";

const MARGIN = { top: 40, right: 24, bottom: 24, left: 180 };
const LANE_HEIGHT = 38;
const MIN_WIDTH = 800;

/**
 * Swimlane timeline backed by @visx.
 *
 * - Horizontal time axis spans from earliest to latest event in the case.
 * - Events are grouped into lanes (by asset, actor, or event category).
 *   Each lane is a horizontal row.
 * - Events render as filled circles at their timestamp.
 * - Temporal clusters (consecutive events with sub-threshold gaps) are
 *   drawn as translucent bands so bursts of activity jump off the page.
 * - Zoom / pan are wired to the `Zoom` primitive — scroll-wheel zooms,
 *   drag pans.
 *
 * Coordinates:
 *   x = time (scaleTime)
 *   y = lane index × LANE_HEIGHT
 */
export function SwimlaneTimeline({ caseId }: { caseId: UUID }) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredId, setHoveredId] = useState<UUID | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["case", caseId, "swimlane"],
    queryFn: () => timelineApi.swimlane(tenantId, caseId, 300),
  });

  const prepared = useMemo(() => {
    if (!data?.data) return null;
    const { entries, lanes, clusters } = data.data;
    if (entries.length === 0)
      return { entries, lanes: [] as LaneRow[], clusters, domain: null };

    const times = entries
      .map((e) => new Date(e.event_timestamp).getTime())
      .filter((t) => Number.isFinite(t));
    const min = Math.min(...times);
    const max = Math.max(...times);
    // Pad by 2% on each side so points never sit flush against the edge
    const pad = Math.max((max - min) * 0.02, 60_000);

    // Sort lanes by earliest event so related lanes stay visually near each other.
    const laneEntries = Object.entries(lanes).map(([key, ids]) => {
      const firstTime = Math.min(
        ...ids
          .map((id) => entries.find((e) => e.id === id)?.event_timestamp)
          .filter((t): t is string => !!t)
          .map((t) => new Date(t).getTime()),
      );
      return { key, ids, firstTime };
    });
    laneEntries.sort((a, b) => a.firstTime - b.firstTime);

    return {
      entries,
      lanes: laneEntries as LaneRow[],
      clusters,
      domain: [new Date(min - pad), new Date(max + pad)] as [Date, Date],
    };
  }, [data]);

  if (isLoading || !prepared) return <LoadingOverlay label="Loading timeline" />;

  const width = Math.max(MIN_WIDTH, containerRef.current?.clientWidth ?? MIN_WIDTH);
  const innerWidth = width - MARGIN.left - MARGIN.right;
  const height = MARGIN.top + MARGIN.bottom + prepared.lanes.length * LANE_HEIGHT;

  if (prepared.entries.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-watari-bg-dark-tertiary p-8 text-center text-sm text-watari-text-dark-secondary">
        No timeline entries yet. Events recorded during the investigation will
        appear here on an interactive swimlane.
      </div>
    );
  }

  const xScale = scaleTime({
    domain: prepared.domain!,
    range: [0, innerWidth],
  });

  const hoveredEntry =
    hoveredId !== null
      ? prepared.entries.find((e) => e.id === hoveredId) ?? null
      : null;

  return (
    <div
      ref={containerRef}
      className="rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-3"
    >
      <div className="flex items-center justify-between px-2 pb-2">
        <h4 className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
          Swimlane ({prepared.entries.length} events, {prepared.lanes.length}{" "}
          lanes, {prepared.clusters.length} clusters)
        </h4>
        <p className="text-[11px] text-watari-text-dark-secondary">
          scroll = zoom · drag = pan
        </p>
      </div>

      <Zoom<SVGSVGElement>
        width={width}
        height={height}
        scaleXMin={0.25}
        scaleXMax={10}
        scaleYMin={1}
        scaleYMax={1}
      >
        {(zoom) => (
          <svg
            width={width}
            height={height}
            onWheel={zoom.handleWheel}
            onMouseDown={zoom.dragStart}
            onMouseMove={zoom.dragMove}
            onMouseUp={zoom.dragEnd}
            onMouseLeave={() => {
              if (zoom.isDragging) zoom.dragEnd();
              setHoveredId(null);
            }}
            className={zoom.isDragging ? "cursor-grabbing" : "cursor-grab"}
          >
            <Group left={MARGIN.left} top={MARGIN.top}>
              <AxisTop
                scale={scaleTime({
                  domain: [
                    zoom.applyInverseToPoint({ x: 0, y: 0 }).x < 0
                      ? xScale.invert(0)
                      : xScale.invert(
                          zoom.applyInverseToPoint({ x: 0, y: 0 }).x,
                        ),
                    xScale.invert(
                      Math.max(
                        zoom.applyInverseToPoint({ x: innerWidth, y: 0 }).x,
                        1,
                      ),
                    ),
                  ],
                  range: [0, innerWidth],
                })}
                stroke="#242836"
                tickStroke="#242836"
                tickLabelProps={() => ({
                  fill: "#9b9a97",
                  fontSize: 10,
                  textAnchor: "middle",
                })}
              />
            </Group>

            {/* Lane labels — rendered outside the zoomed area so they stay anchored */}
            <Group top={MARGIN.top}>
              {prepared.lanes.map((lane, i) => (
                <g key={lane.key} transform={`translate(0, ${i * LANE_HEIGHT})`}>
                  <rect
                    x={0}
                    y={0}
                    width={MARGIN.left}
                    height={LANE_HEIGHT}
                    fill={i % 2 === 0 ? "#1a1d27" : "#0f1117"}
                  />
                  <text
                    x={12}
                    y={LANE_HEIGHT / 2 + 4}
                    fill="#e8e6e1"
                    fontSize={11}
                    className="font-mono"
                  >
                    {prettyLaneKey(lane.key)}
                  </text>
                </g>
              ))}
            </Group>

            <Group left={MARGIN.left} top={MARGIN.top}>
              {/* Lane stripes */}
              {prepared.lanes.map((_, i) => (
                <rect
                  key={`lane-bg-${i}`}
                  x={0}
                  y={i * LANE_HEIGHT}
                  width={innerWidth}
                  height={LANE_HEIGHT}
                  fill={i % 2 === 0 ? "#1a1d27" : "#0f1117"}
                />
              ))}

              {/* Apply zoom transform to the content layer */}
              <Group transform={zoom.toString()}>
                {/* Cluster bands */}
                {prepared.clusters.map((cluster, i) => (
                  <ClusterBand
                    key={`cluster-${i}`}
                    cluster={cluster}
                    xScale={xScale}
                    laneCount={prepared.lanes.length}
                  />
                ))}

                {/* Event dots */}
                {prepared.lanes.flatMap((lane, laneIdx) =>
                  lane.ids.map((id) => {
                    const e = prepared.entries.find((x) => x.id === id);
                    if (!e) return null;
                    const x = xScale(new Date(e.event_timestamp));
                    const y = laneIdx * LANE_HEIGHT + LANE_HEIGHT / 2;
                    const isHovered = hoveredId === e.id;
                    return (
                      <g key={`${lane.key}-${e.id}`}>
                        <circle
                          cx={x}
                          cy={y}
                          r={isHovered ? 7 : 5}
                          fill={e.is_automatic ? "#8b7340" : "#c4a35a"}
                          stroke="#0f1117"
                          strokeWidth={1.5}
                          style={{ cursor: "pointer" }}
                          onMouseEnter={() => setHoveredId(e.id)}
                          onMouseLeave={() => setHoveredId(null)}
                        />
                      </g>
                    );
                  }),
                )}
              </Group>
            </Group>
          </svg>
        )}
      </Zoom>

      {hoveredEntry ? (
        <div className="mt-2 rounded-md border border-watari-bg-dark-tertiary bg-watari-bg-dark-secondary p-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="rounded bg-watari-gold-muted/30 px-1.5 py-0.5 font-medium uppercase tracking-wider text-watari-gold">
              {hoveredEntry.event_type}
            </span>
            <span className="text-watari-text-dark-secondary">
              {new Date(hoveredEntry.event_timestamp).toLocaleString()}
            </span>
          </div>
          <p className="mt-1 text-watari-text-dark-primary">
            {hoveredEntry.description}
          </p>
        </div>
      ) : null}
    </div>
  );
}

interface LaneRow {
  key: string;
  ids: UUID[];
  firstTime: number;
}

function ClusterBand({
  cluster,
  xScale,
  laneCount,
}: {
  cluster: TemporalCluster;
  xScale: ReturnType<typeof scaleTime<number>>;
  laneCount: number;
}) {
  const x0 = xScale(new Date(cluster.start));
  const x1 = xScale(new Date(cluster.end));
  const width = Math.max(x1 - x0, 2);
  return (
    <rect
      x={x0 - 1}
      y={0}
      width={width + 2}
      height={laneCount * LANE_HEIGHT}
      fill="#c4a35a"
      opacity={0.08}
      rx={3}
    />
  );
}

function prettyLaneKey(key: string): string {
  if (key.startsWith("asset:")) return `asset ${key.slice(6, 14)}`;
  if (key.startsWith("user:")) return `user ${key.slice(5, 13)}`;
  if (key.startsWith("category:")) return key.slice(9);
  return key;
}

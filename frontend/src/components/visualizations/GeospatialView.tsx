import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { observablesApi } from "@/api/resources";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { useTenantStore } from "@/stores/tenant";
import type { Observable, UUID } from "@/types/api";

/* Leaflet's default marker icon uses image paths that Vite can't resolve
 * out of the box, so we point it at the CDN copy. */
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl:
    "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:
    "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-shadow.png",
});

interface GeoMarker {
  observable: Observable;
  latitude: number;
  longitude: number;
  country?: string;
  city?: string;
}

/**
 * Geospatial observable visualisation.
 *
 * v1 consumes enrichment `result_data.geo` entries shaped as:
 *   { latitude, longitude, country_code?, city? }
 * Each observable with usable coordinates becomes a Leaflet marker.
 * Multiple observables at the same coordinate are NOT manually clustered
 * here — Leaflet clusters at render time via the `markercluster` plugin;
 * with the relatively small dataset the demo will carry we keep the
 * single-marker path to avoid pulling in a large plugin for v1.
 */
export function GeospatialView({ caseId }: { caseId: UUID }) {
  const tenantId = useTenantStore((s) => s.activeTenantId)!;

  const { data: observables, isLoading } = useQuery({
    queryKey: ["case", caseId, "observables"],
    queryFn: () => observablesApi.list(tenantId, caseId),
  });

  const enrichmentQueries = useQueries(
    observables?.data
      .filter((o) => o.type === "ip" || o.type === "domain")
      .map((o) => o.id) ?? [],
    tenantId,
    caseId,
  );

  const markers = useMemo<GeoMarker[]>(() => {
    const results: GeoMarker[] = [];
    for (const e of enrichmentQueries) {
      if (!e.ok) continue;
      for (const r of e.results) {
        const geo = (r.result_data as { geo?: Record<string, unknown> } | null)
          ?.geo;
        if (!geo) continue;
        const lat = Number((geo as { latitude?: number }).latitude);
        const lng = Number((geo as { longitude?: number }).longitude);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
        const obs = observables?.data.find((o) => o.id === e.observableId);
        if (!obs) continue;
        results.push({
          observable: obs,
          latitude: lat,
          longitude: lng,
          country: (geo as { country_code?: string }).country_code,
          city: (geo as { city?: string }).city,
        });
      }
    }
    return results;
  }, [enrichmentQueries, observables]);

  if (isLoading) return <LoadingOverlay label="Loading map" />;

  const defaultCenter: [number, number] =
    markers.length > 0
      ? [markers[0].latitude, markers[0].longitude]
      : [30, 0];
  const defaultZoom = markers.length > 0 ? 3 : 2;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
          Geospatial ({markers.length} placeable observable
          {markers.length === 1 ? "" : "s"})
        </h4>
        {markers.length === 0 ? (
          <p className="text-[11px] text-watari-text-dark-secondary">
            Run enrichment on IP / domain observables to populate the map.
          </p>
        ) : null}
      </div>

      <div className="h-[500px] overflow-hidden rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark">
        <MapContainer
          center={defaultCenter}
          zoom={defaultZoom}
          className="h-full w-full"
          scrollWheelZoom
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {markers.map((m) => (
            <Marker
              key={`${m.observable.id}:${m.latitude}:${m.longitude}`}
              position={[m.latitude, m.longitude]}
            >
              <Popup>
                <div className="text-xs">
                  <div className="font-mono text-watari-gold">
                    {m.observable.type}: {m.observable.value}
                  </div>
                  {m.city || m.country ? (
                    <div className="mt-1 text-watari-text-dark-secondary">
                      {[m.city, m.country].filter(Boolean).join(", ")}
                    </div>
                  ) : null}
                  <div className="mt-1 text-watari-text-dark-secondary">
                    {m.latitude.toFixed(4)}, {m.longitude.toFixed(4)}
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------
 * useQueries wrapper: one enrichment-results query per observable
 * ---------------------------------------------------------------
 *
 * We deliberately re-use React Query's batch API instead of building a
 * single mega-query so cache invalidation stays per-observable and
 * realtime updates still propagate granularly.
 */

import { useQueries as useReactQueries } from "@tanstack/react-query";
import type { EnrichmentResult } from "@/types/api";

interface EnrichmentQueryResult {
  observableId: UUID;
  ok: boolean;
  results: EnrichmentResult[];
}

function useQueries(
  observableIds: UUID[],
  tenantId: UUID,
  caseId: UUID,
): EnrichmentQueryResult[] {
  const queries = useReactQueries({
    queries: observableIds.map((oid) => ({
      queryKey: ["enrichment-results", oid],
      queryFn: () =>
        observablesApi.enrichmentResults(tenantId, caseId, oid),
      staleTime: 60_000,
    })),
  });
  return observableIds.map((oid, i) => {
    const q = queries[i];
    return {
      observableId: oid,
      ok: q.isSuccess,
      results: q.data?.data ?? [],
    };
  });
}

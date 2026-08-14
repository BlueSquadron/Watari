import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/auth";
import type { UUID } from "@/types/api";

export interface RealtimeEvent {
  type: string;
  case_id: string | null;
  tenant_id: string;
  payload: Record<string, unknown>;
  actor: { user_id: string; display_name: string | null } | null;
  timestamp: string;
}

const WS_BASE =
  import.meta.env.VITE_API_BASE_URL?.replace(/^http/, "ws") ?? "/api";

function connect(
  url: string,
  onMessage: (ev: RealtimeEvent) => void,
): WebSocket {
  const ws = new WebSocket(url);
  ws.addEventListener("message", (event) => {
    try {
      const data = JSON.parse(event.data as string) as RealtimeEvent;
      onMessage(data);
    } catch {
      // ignore non-JSON messages (pong, keepalives)
    }
  });
  return ws;
}

/**
 * Subscribe to a case-scoped realtime channel. The hook automatically
 * reconnects on disconnect and invalidates relevant React Query caches
 * when events arrive so the UI stays fresh.
 */
export function useCaseRealtime(tenantId: UUID, caseId: UUID): void {
  const qc = useQueryClient();
  const ref = useRef<WebSocket | null>(null);

  useEffect(() => {
    const token = useAuthStore.getState().accessToken;
    if (!token) return;
    const url = `${WS_BASE.replace(/^\/api$/, "/api")}/v1/realtime/cases/${caseId}?token=${token}`;
    let cancelled = false;
    let reconnectDelay = 1000;
    let reconnectTimer: number | null = null;
    let pingTimer: number | null = null;

    const open = () => {
      if (cancelled) return;
      const ws = connect(url, () => {
        // Invalidate queries tied to the case so fresh data is fetched.
        qc.invalidateQueries({ queryKey: ["case", caseId] });
        qc.invalidateQueries({ queryKey: ["case", caseId, "timeline"] });
        qc.invalidateQueries({ queryKey: ["case", caseId, "observables"] });
        qc.invalidateQueries({ queryKey: ["case", caseId, "assets"] });
        qc.invalidateQueries({ queryKey: ["case", caseId, "evidence"] });
        qc.invalidateQueries({ queryKey: ["case", caseId, "notes"] });
        qc.invalidateQueries({ queryKey: ["case", caseId, "tasks"] });
        qc.invalidateQueries({ queryKey: ["cases", tenantId] });
        // Tenant-level activity feed gets a nudge too
        qc.invalidateQueries({ queryKey: ["tenant", tenantId, "activity"] });
      });

      ref.current = ws;

      ws.addEventListener("open", () => {
        reconnectDelay = 1000;
        // Periodic ping to keep presence fresh
        pingTimer = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send("ping");
        }, 15000);
      });

      ws.addEventListener("close", () => {
        if (pingTimer) window.clearInterval(pingTimer);
        if (cancelled) return;
        reconnectDelay = Math.min(reconnectDelay * 2, 30000);
        reconnectTimer = window.setTimeout(open, reconnectDelay);
      });

      ws.addEventListener("error", () => {
        ws.close();
      });
    };

    open();

    return () => {
      cancelled = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      if (pingTimer) window.clearInterval(pingTimer);
      ref.current?.close();
      ref.current = null;
    };
  }, [tenantId, caseId, qc]);
}

/**
 * Subscribe to tenant-wide activity feed events. Invalidates the activity
 * feed cache when events arrive.
 */
export function useTenantRealtime(tenantId: UUID | null): void {
  const qc = useQueryClient();

  useEffect(() => {
    if (!tenantId) return;
    const token = useAuthStore.getState().accessToken;
    if (!token) return;
    const url = `${WS_BASE.replace(/^\/api$/, "/api")}/v1/realtime/tenants/${tenantId}?token=${token}`;
    let cancelled = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;

    const open = () => {
      if (cancelled) return;
      ws = connect(url, () => {
        qc.invalidateQueries({ queryKey: ["tenant", tenantId, "activity"] });
        qc.invalidateQueries({ queryKey: ["cases", tenantId] });
        qc.invalidateQueries({ queryKey: ["alerts", tenantId] });
        qc.invalidateQueries({ queryKey: ["dashboard", tenantId] });
      });
      ws.addEventListener("close", () => {
        if (cancelled) return;
        reconnectTimer = window.setTimeout(open, 2000);
      });
    };

    open();
    return () => {
      cancelled = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [tenantId, qc]);
}

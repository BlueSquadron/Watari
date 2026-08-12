import { type ReactNode } from "react";
import { Outlet } from "react-router-dom";
import { CommandPalette } from "@/components/CommandPalette";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useTenantRealtime } from "@/realtime/useWebSocket";
import { useTenantStore } from "@/stores/tenant";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children?: ReactNode }) {
  const toggle = useCommandPaletteStore((s) => s.toggle);
  const activeTenantId = useTenantStore((s) => s.activeTenantId);

  useKeyboardShortcut({ key: "k", meta: true, handler: toggle });
  useKeyboardShortcut({ key: "k", ctrl: true, handler: toggle });

  useTenantRealtime(activeTenantId);

  return (
    <div className="flex h-screen bg-watari-bg-dark text-watari-text-dark-primary">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto bg-watari-bg-dark-secondary p-6">
          {children ?? <Outlet />}
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}

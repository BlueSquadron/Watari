import { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import Fuse from "fuse.js";
import { useNavigate } from "react-router-dom";
import { searchApi } from "@/api/resources";
import { useCommandPaletteStore } from "@/stores/commandPalette";
import { useTenantStore } from "@/stores/tenant";
import type { SearchHit, UUID } from "@/types/api";

interface PaletteAction {
  id: string;
  label: string;
  category: "navigation" | "action" | "search";
  keywords: string;
  shortcut?: string;
  execute: () => void | Promise<void>;
}

function buildNavigationActions(
  navigate: ReturnType<typeof useNavigate>,
): PaletteAction[] {
  return [
    {
      id: "nav:dashboard",
      label: "Go to Dashboard",
      category: "navigation",
      keywords: "dashboard metrics home",
      execute: () => navigate("/dashboard"),
    },
    {
      id: "nav:cases",
      label: "Go to Cases",
      category: "navigation",
      keywords: "cases investigations",
      execute: () => navigate("/cases"),
    },
    {
      id: "nav:alerts",
      label: "Go to Alerts",
      category: "navigation",
      keywords: "alerts triage",
      execute: () => navigate("/alerts"),
    },
    {
      id: "nav:search",
      label: "Go to Search",
      category: "navigation",
      keywords: "search find query",
      execute: () => navigate("/search"),
    },
    {
      id: "nav:attack",
      label: "Go to ATT&CK Matrix",
      category: "navigation",
      keywords: "mitre attack heatmap tactics techniques",
      execute: () => navigate("/attack"),
    },
    {
      id: "nav:templates",
      label: "Go to Case Templates",
      category: "navigation",
      keywords: "templates presets",
      execute: () => navigate("/admin/templates"),
    },
    {
      id: "nav:enrichment",
      label: "Go to Enrichment Sources",
      category: "navigation",
      keywords: "enrichment virustotal misp shodan",
      execute: () => navigate("/admin/enrichment"),
    },
    {
      id: "nav:users",
      label: "Go to Users",
      category: "navigation",
      keywords: "users analysts admin accounts",
      execute: () => navigate("/admin/users"),
    },
    {
      id: "action:create-case",
      label: "Create new case",
      category: "action",
      keywords: "new case create incident",
      shortcut: "⌘N",
      execute: () => navigate("/cases/new"),
    },
  ];
}

export function CommandPalette() {
  const { isOpen, close, query, setQuery } = useCommandPaletteStore();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const activeTenantId = useTenantStore((s) => s.activeTenantId);
  const [remoteHits, setRemoteHits] = useState<SearchHit[]>([]);
  const [selected, setSelected] = useState(0);

  const staticActions = useMemo(() => buildNavigationActions(navigate), [
    navigate,
  ]);

  const fuse = useMemo(
    () =>
      new Fuse(staticActions, {
        keys: ["label", "keywords"],
        threshold: 0.35,
      }),
    [staticActions],
  );

  const filteredActions = useMemo<PaletteAction[]>(() => {
    if (!query.trim()) return staticActions;
    return fuse.search(query).map((r) => r.item);
  }, [fuse, query, staticActions]);

  // Fetch remote search hits for the active tenant on open.
  useEffect(() => {
    if (!isOpen || !activeTenantId || !query.trim() || query.length < 2) {
      setRemoteHits([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await qc.fetchQuery({
          queryKey: ["search", activeTenantId, query],
          queryFn: () => searchApi.search(activeTenantId, query),
        });
        setRemoteHits(response.data.hits);
      } catch {
        setRemoteHits([]);
      }
    }, 200);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [isOpen, activeTenantId, query, qc]);

  const allItems = useMemo(() => {
    const searchItems: PaletteAction[] = remoteHits.map((hit) => ({
      id: `hit:${hit.entity_type}:${hit.entity_id}`,
      label: `${hit.entity_type}: ${hit.title}`,
      category: "search",
      keywords: hit.snippet,
      execute: () => {
        if (hit.case_id) {
          navigate(`/cases/${hit.case_id}`);
        } else if (hit.entity_type === "alert") {
          navigate("/alerts");
        } else {
          navigate("/search");
        }
      },
    }));
    return [...filteredActions, ...searchItems];
  }, [filteredActions, remoteHits, navigate]);

  useEffect(() => {
    setSelected(0);
  }, [query, isOpen]);

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelected((i) => Math.min(i + 1, allItems.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelected((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const item = allItems[selected];
      if (item) {
        void item.execute();
        close();
      }
    }
  };

  const grouped = useMemo(() => {
    const groups: Record<string, { items: PaletteAction[]; indexes: number[] }> =
      {};
    allItems.forEach((item, idx) => {
      const bucket = (groups[item.category] ??= { items: [], indexes: [] });
      bucket.items.push(item);
      bucket.indexes.push(idx);
    });
    return groups;
  }, [allItems]);

  return (
    <Dialog.Root
      open={isOpen}
      onOpenChange={(open) => (open ? null : close())}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" />
        <Dialog.Content
          className={clsx(
            "fixed left-1/2 top-[15%] z-50 w-full max-w-2xl -translate-x-1/2",
            "rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark-secondary shadow-2xl",
          )}
          onKeyDown={onKeyDown}
          aria-label="Command palette"
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Dialog.Description className="sr-only">
            Navigate, search and act using keyboard
          </Dialog.Description>
          <div className="flex items-center gap-3 border-b border-watari-bg-dark-tertiary px-4 py-3">
            <span className="text-watari-gold-muted">⌕</span>
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search cases, observables, or jump to…"
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-watari-text-dark-secondary"
            />
            <kbd className="rounded bg-watari-bg-dark px-1.5 py-0.5 font-mono text-[10px] text-watari-text-dark-secondary">
              ESC
            </kbd>
          </div>

          <div className="max-h-[60vh] overflow-y-auto py-2">
            {allItems.length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-watari-text-dark-secondary">
                No results for “{query}”
              </p>
            ) : (
              (["action", "navigation", "search"] as const).map((cat) => {
                const bucket = grouped[cat];
                if (!bucket || bucket.items.length === 0) return null;
                return (
                  <div key={cat}>
                    <p className="px-4 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider text-watari-text-dark-secondary">
                      {cat}
                    </p>
                    <ul>
                      {bucket.items.map((item, i) => {
                        const idx = bucket.indexes[i];
                        return (
                          <li key={item.id}>
                            <button
                              type="button"
                              onMouseEnter={() => setSelected(idx)}
                              onClick={() => {
                                void item.execute();
                                close();
                              }}
                              className={clsx(
                                "flex w-full items-center justify-between px-4 py-2 text-sm transition-colors",
                                selected === idx
                                  ? "bg-watari-bg-dark-tertiary text-watari-gold"
                                  : "text-watari-text-dark-primary hover:bg-watari-bg-dark-tertiary",
                              )}
                            >
                              <span className="truncate">{item.label}</span>
                              {item.shortcut ? (
                                <kbd className="rounded bg-watari-bg-dark px-1.5 py-0.5 font-mono text-[10px] text-watari-text-dark-secondary">
                                  {item.shortcut}
                                </kbd>
                              ) : null}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                );
              })
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

interface SearchRowProps {
  hit: SearchHit;
  onSelect: (hit: SearchHit) => void;
  caseId?: UUID;
}

export function SearchRow({ hit, onSelect }: SearchRowProps) {
  return (
    <button
      type="button"
      className="flex w-full flex-col px-4 py-2 text-left hover:bg-watari-bg-dark-tertiary"
      onClick={() => onSelect(hit)}
    >
      <span className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
        {hit.entity_type}
      </span>
      <span className="truncate text-sm text-watari-text-dark-primary">
        {hit.title}
      </span>
    </button>
  );
}

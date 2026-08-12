import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { tenantsApi } from "@/api/resources";
import { useAuthStore } from "@/stores/auth";
import { useTenantStore } from "@/stores/tenant";

interface NavItem {
  label: string;
  to: string;
  icon: string;
}

const CORE_NAV: NavItem[] = [
  { label: "Dashboard", to: "/dashboard", icon: "▦" },
  { label: "Cases", to: "/cases", icon: "◫" },
  { label: "Alerts", to: "/alerts", icon: "◆" },
  { label: "Search", to: "/search", icon: "⌕" },
  { label: "ATT&CK", to: "/attack", icon: "⚑" },
];

const ADMIN_NAV: NavItem[] = [
  { label: "Users", to: "/admin/users", icon: "◉" },
  { label: "Tenants", to: "/admin/tenants", icon: "◈" },
  { label: "Templates", to: "/admin/templates", icon: "◱" },
  { label: "Enrichment", to: "/admin/enrichment", icon: "⚗" },
  { label: "Modules", to: "/admin/modules", icon: "⚙" },
  { label: "Audit", to: "/admin/audit", icon: "◷" },
];

export function Sidebar() {
  const user = useAuthStore((s) => s.user);
  const activeTenantId = useTenantStore((s) => s.activeTenantId);
  const canAdmin =
    user?.role === "platform_admin" || user?.role === "tenant_admin";

  // Fetch the tenant name. Platform admins see the "switch tenant" view
  // via /admin/tenants; for everyone else the active tenant is their own,
  // and we just render the slug/name for context.
  const { data: tenant } = useQuery({
    queryKey: ["tenant-current", activeTenantId],
    queryFn: () => tenantsApi.get(activeTenantId!),
    enabled: !!activeTenantId,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <aside className="flex w-60 flex-col border-r border-watari-bg-dark-tertiary bg-watari-bg-dark">
      <div className="px-5 py-6">
        <h1 className="flex items-baseline gap-2 text-2xl font-semibold tracking-tight text-watari-gold">
          Watari
          <span className="text-xs font-normal uppercase tracking-[0.2em] text-watari-text-dark-secondary">
            Case Mgmt
          </span>
        </h1>
      </div>

      <nav className="flex-1 px-3">
        <SectionLabel>Core</SectionLabel>
        <ul className="mt-1 space-y-0.5">
          {CORE_NAV.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  clsx(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                    "hover:bg-watari-bg-dark-tertiary",
                    isActive
                      ? "bg-watari-bg-dark-tertiary text-watari-gold"
                      : "text-watari-text-dark-primary",
                  )
                }
              >
                <span className="w-4 text-center text-watari-gold-muted">
                  {item.icon}
                </span>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>

        {canAdmin ? (
          <>
            <SectionLabel className="mt-6">Administration</SectionLabel>
            <ul className="mt-1 space-y-0.5">
              {ADMIN_NAV.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      clsx(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                        "hover:bg-watari-bg-dark-tertiary",
                        isActive
                          ? "bg-watari-bg-dark-tertiary text-watari-gold"
                          : "text-watari-text-dark-primary",
                      )
                    }
                  >
                    <span className="w-4 text-center text-watari-gold-muted">
                      {item.icon}
                    </span>
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </nav>

      <div className="border-t border-watari-bg-dark-tertiary px-5 py-4">
        <p className="text-xs uppercase tracking-wide text-watari-text-dark-secondary">
          Tenant
        </p>
        <p className="truncate font-medium text-watari-text-dark-primary">
          {tenant?.data.name ?? (activeTenantId ? "…" : "—")}
        </p>
        {tenant?.data.slug ? (
          <p className="truncate font-mono text-[11px] text-watari-text-dark-secondary">
            {tenant.data.slug}
          </p>
        ) : null}
      </div>
    </aside>
  );
}

function SectionLabel({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <p
      className={clsx(
        "px-3 text-[11px] font-semibold uppercase tracking-[0.15em] text-watari-text-dark-secondary",
        className,
      )}
    >
      {children}
    </p>
  );
}

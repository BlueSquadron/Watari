import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { AttackMatrix } from "@/components/visualizations/AttackMatrix";
import { AlertDetail } from "@/pages/AlertDetail";
import { AlertQueue } from "@/pages/AlertQueue";
import { AuditLogViewer } from "@/pages/AuditLogViewer";
import { CaseDetail } from "@/pages/CaseDetail";
import { CaseList } from "@/pages/CaseList";
import { CaseTemplatesPage } from "@/pages/CaseTemplatesPage";
import { Dashboard } from "@/pages/Dashboard";
import { EnrichmentSourcesPage } from "@/pages/EnrichmentSourcesPage";
import { Login } from "@/pages/Login";
import { ModuleManagement } from "@/pages/ModuleManagement";
import { SearchPage } from "@/pages/Search";
import { TenantManagement } from "@/pages/TenantManagement";
import { UserManagement } from "@/pages/UserManagement";
import { useAuthStore } from "@/stores/auth";
import { useThemeStore } from "@/stores/theme";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

function RequireAuth({ children }: { children: ReactNode }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const location = useLocation();
  if (!accessToken) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <>{children}</>;
}

function AlreadyAuthenticatedRedirect({ children }: { children: ReactNode }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  if (accessToken) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

export default function App() {
  // Apply persisted theme on mount
  const theme = useThemeStore((s) => s.theme);
  if (typeof document !== "undefined") {
    if (theme === "dark") document.documentElement.classList.add("dark");
    else document.documentElement.classList.remove("dark");
  }

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              <AlreadyAuthenticatedRedirect>
                <Login />
              </AlreadyAuthenticatedRedirect>
            }
          />

          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route
              path="/cases"
              element={<CaseList />}
            />
            <Route
              path="/cases/new"
              element={<Navigate to="/cases" replace />}
            />
            <Route
              path="/cases/:caseId"
              element={<CaseDetail />}
            />
            <Route
              path="/alerts"
              element={<AlertQueue />}
            />
            <Route
              path="/alerts/:alertId"
              element={<AlertDetail />}
            />
            <Route
              path="/search"
              element={<SearchPage />}
            />
            <Route
              path="/attack"
              element={<AttackMatrix />}
            />
            <Route
              path="/admin/users"
              element={<UserManagement />}
            />
            <Route
              path="/admin/tenants"
              element={<TenantManagement />}
            />
            <Route
              path="/admin/templates"
              element={<CaseTemplatesPage />}
            />
            <Route
              path="/admin/enrichment"
              element={<EnrichmentSourcesPage />}
            />
            <Route
              path="/admin/modules"
              element={<ModuleManagement />}
            />
            <Route
              path="/admin/audit"
              element={<AuditLogViewer />}
            />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

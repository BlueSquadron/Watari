import { useQuery } from "@tanstack/react-query";
import { ResponsiveBar } from "@nivo/bar";
import { ResponsiveLine } from "@nivo/line";
import { ResponsivePie } from "@nivo/pie";
import { dashboardApi } from "@/api/resources";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { useTenantStore } from "@/stores/tenant";
import type { DashboardMetrics } from "@/types/api";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#3b82f6",
  informational: "#6b7280",
};

const STATUS_COLORS: Record<string, string> = {
  new: "#3b82f6",
  in_progress: "#f59e0b",
  pending: "#a855f7",
  resolved: "#22c55e",
  closed: "#6b7280",
};

const NIVO_THEME = {
  axis: {
    ticks: {
      text: { fill: "#9b9a97", fontSize: 10 },
    },
    legend: { text: { fill: "#9b9a97" } },
  },
  legends: {
    text: { fill: "#e8e6e1", fontSize: 11 },
  },
  tooltip: {
    container: {
      background: "#1a1d27",
      color: "#e8e6e1",
      fontSize: 12,
      borderRadius: 6,
    },
  },
  grid: {
    line: { stroke: "#242836", strokeWidth: 1 },
  },
} as const;

export function Dashboard() {
  const tenantId = useTenantStore((s) => s.activeTenantId);
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", tenantId],
    queryFn: () => dashboardApi.metrics(tenantId!),
    enabled: !!tenantId,
  });

  if (!tenantId)
    return (
      <p className="text-sm text-watari-text-dark-secondary">
        No active tenant.
      </p>
    );
  if (isLoading || !data) return <LoadingOverlay label="Loading dashboard" />;

  const metrics = data.data;
  const openCount = metrics.open_cases_by_severity.reduce(
    (acc, p) => acc + p.count,
    0,
  );
  const totalCount = metrics.cases_by_status.reduce(
    (acc, p) => acc + p.count,
    0,
  );

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold">Dashboard</h2>
        <p className="text-sm text-watari-text-dark-secondary">
          Live metrics for your tenant
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Open cases" value={openCount} />
        <MetricCard label="Total cases" value={totalCount} />
        <MetricCard
          label="Mean time to resolution (h)"
          value={
            metrics.mean_time_to_resolution_hours != null
              ? metrics.mean_time_to_resolution_hours.toFixed(1)
              : "—"
          }
        />
        <MetricCard
          label="Active analysts"
          value={metrics.analyst_workload.length}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Open cases by severity">
          <SeverityBarChart data={metrics.open_cases_by_severity} />
        </Card>
        <Card title="Cases by status">
          <StatusPieChart data={metrics.cases_by_status} />
        </Card>
        <Card title="Cases over time" className="xl:col-span-2">
          <CreatedLineChart data={metrics.cases_created_over_time} />
        </Card>
        <Card title="Analyst workload" className="xl:col-span-2">
          <AnalystWorkloadChart data={metrics.analyst_workload} />
        </Card>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-4">
      <p className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
        {label}
      </p>
      <p className="mt-2 text-3xl font-semibold text-watari-gold">{value}</p>
    </div>
  );
}

function Card({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-4 ${
        className ?? ""
      }`}
    >
      <h3 className="text-xs font-semibold uppercase tracking-wider text-watari-text-dark-secondary">
        {title}
      </h3>
      <div className="mt-3 h-60">{children}</div>
    </div>
  );
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center text-sm text-watari-text-dark-secondary">
      {label}
    </div>
  );
}

function SeverityBarChart({
  data,
}: {
  data: DashboardMetrics["open_cases_by_severity"];
}) {
  if (data.length === 0) return <EmptyChart label="No open cases." />;
  const ordered = ["critical", "high", "medium", "low", "informational"];
  const sorted = [...data].sort(
    (a, b) => ordered.indexOf(a.severity) - ordered.indexOf(b.severity),
  );
  return (
    <ResponsiveBar
      data={sorted.map((p) => ({ severity: p.severity, count: p.count }))}
      keys={["count"]}
      indexBy="severity"
      margin={{ top: 10, right: 10, bottom: 40, left: 40 }}
      padding={0.3}
      colors={(d) => SEVERITY_COLORS[d.indexValue as string] ?? "#c4a35a"}
      theme={NIVO_THEME}
      axisLeft={{
        tickSize: 4,
        tickPadding: 4,
        tickValues: 5,
      }}
      axisBottom={{ tickSize: 4, tickPadding: 4 }}
      enableLabel={false}
      borderRadius={3}
    />
  );
}

function StatusPieChart({
  data,
}: {
  data: DashboardMetrics["cases_by_status"];
}) {
  if (data.length === 0) return <EmptyChart label="No cases yet." />;
  return (
    <ResponsivePie
      data={data.map((p) => ({
        id: p.status,
        label: p.status,
        value: p.count,
      }))}
      margin={{ top: 10, right: 10, bottom: 20, left: 10 }}
      innerRadius={0.55}
      padAngle={1.5}
      cornerRadius={3}
      colors={(d) => STATUS_COLORS[d.id as string] ?? "#c4a35a"}
      theme={NIVO_THEME}
      activeOuterRadiusOffset={6}
      borderWidth={1}
      borderColor="#0f1117"
      arcLabel={(d) => `${d.value}`}
      arcLabelsTextColor="#e8e6e1"
      arcLinkLabel={(d) => `${d.id}`.replace("_", " ")}
      arcLinkLabelsTextColor="#9b9a97"
      arcLinkLabelsColor="#9b9a97"
    />
  );
}

function CreatedLineChart({
  data,
}: {
  data: DashboardMetrics["cases_created_over_time"];
}) {
  if (data.length === 0) return <EmptyChart label="No timeline data yet." />;
  return (
    <ResponsiveLine
      data={[
        {
          id: "cases",
          data: data.map((p) => ({
            x: new Date(p.timestamp).toLocaleDateString(),
            y: p.value,
          })),
        },
      ]}
      margin={{ top: 10, right: 10, bottom: 40, left: 40 }}
      xScale={{ type: "point" }}
      yScale={{ type: "linear", min: 0 }}
      axisBottom={{ tickSize: 4, tickPadding: 4, tickRotation: -30 }}
      axisLeft={{ tickSize: 4, tickPadding: 4 }}
      enablePoints
      pointSize={6}
      pointColor="#c4a35a"
      colors={["#c4a35a"]}
      lineWidth={2}
      useMesh
      theme={NIVO_THEME}
    />
  );
}

function AnalystWorkloadChart({
  data,
}: {
  data: DashboardMetrics["analyst_workload"];
}) {
  if (data.length === 0)
    return <EmptyChart label="No analyst workload data." />;
  return (
    <ResponsiveBar
      data={data.map((p) => ({
        analyst: p.analyst_name,
        open: p.open_cases,
        resolved: p.resolved_cases_7d,
      }))}
      keys={["open", "resolved"]}
      indexBy="analyst"
      groupMode="grouped"
      margin={{ top: 10, right: 80, bottom: 50, left: 40 }}
      padding={0.25}
      colors={["#c4a35a", "#22c55e"]}
      theme={NIVO_THEME}
      axisBottom={{ tickSize: 4, tickPadding: 4, tickRotation: -20 }}
      axisLeft={{ tickSize: 4, tickPadding: 4 }}
      enableLabel={false}
      legends={[
        {
          dataFrom: "keys",
          anchor: "top-right",
          direction: "column",
          translateX: 60,
          itemWidth: 80,
          itemHeight: 18,
          symbolSize: 12,
          itemTextColor: "#9b9a97",
        },
      ]}
    />
  );
}

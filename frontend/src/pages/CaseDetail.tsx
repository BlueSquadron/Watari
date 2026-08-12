import { useQuery } from "@tanstack/react-query";
import * as Tabs from "@radix-ui/react-tabs";
import { clsx } from "clsx";
import { useParams } from "react-router-dom";
import { casesApi } from "@/api/resources";
import { AssetList } from "@/components/cases/AssetList";
import { CaseHeader } from "@/components/cases/CaseHeader";
import { CaseTimeline } from "@/components/cases/CaseTimeline";
import { EvidenceList } from "@/components/cases/EvidenceList";
import { NotesEditor } from "@/components/cases/NotesEditor";
import { ObservableList } from "@/components/cases/ObservableList";
import { ReportGenerator } from "@/components/cases/ReportGenerator";
import { TaskList } from "@/components/cases/TaskList";
import { AttackMatrix } from "@/components/visualizations/AttackMatrix";
import { CaseGraph } from "@/components/visualizations/CaseGraph";
import { GeospatialView } from "@/components/visualizations/GeospatialView";
import { SwimlaneTimeline } from "@/components/visualizations/SwimlaneTimeline";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { useTenantStore } from "@/stores/tenant";
import { useCaseRealtime } from "@/realtime/useWebSocket";

const TABS = [
  { value: "overview", label: "Overview" },
  { value: "timeline", label: "Timeline" },
  { value: "swimlane", label: "Swimlane" },
  { value: "graph", label: "Graph" },
  { value: "map", label: "Map" },
  { value: "attack", label: "ATT&CK" },
  { value: "observables", label: "Observables" },
  { value: "assets", label: "Assets" },
  { value: "evidence", label: "Evidence" },
  { value: "notes", label: "Notes" },
  { value: "tasks", label: "Tasks" },
  { value: "reports", label: "Reports" },
];

export function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const tenantId = useTenantStore((s) => s.activeTenantId);

  useCaseRealtime(tenantId ?? "", caseId ?? "");

  const { data, isLoading } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => casesApi.get(tenantId!, caseId!),
    enabled: !!tenantId && !!caseId,
  });

  if (!tenantId || !caseId) return null;
  if (isLoading || !data) return <LoadingOverlay label="Loading case" />;

  const c = data.data;

  return (
    <div className="space-y-6">
      <CaseHeader case={c} />

      <Tabs.Root defaultValue="overview">
        <Tabs.List className="flex gap-1 border-b border-watari-bg-dark-tertiary">
          {TABS.map((t) => (
            <Tabs.Trigger
              key={t.value}
              value={t.value}
              className={clsx(
                "border-b-2 border-transparent px-4 py-2 text-sm text-watari-text-dark-secondary transition-colors",
                "data-[state=active]:border-watari-gold data-[state=active]:text-watari-text-dark-primary",
                "hover:text-watari-text-dark-primary",
              )}
            >
              {t.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="overview" className="pt-4">
          <Overview description={c.description} tags={c.tags} />
        </Tabs.Content>
        <Tabs.Content value="timeline" className="pt-4">
          <CaseTimeline caseId={caseId} />
        </Tabs.Content>
        <Tabs.Content value="swimlane" className="pt-4">
          <SwimlaneTimeline caseId={caseId} />
        </Tabs.Content>
        <Tabs.Content value="graph" className="pt-4">
          <CaseGraph caseId={caseId} />
        </Tabs.Content>
        <Tabs.Content value="map" className="pt-4">
          <GeospatialView caseId={caseId} />
        </Tabs.Content>
        <Tabs.Content value="attack" className="pt-4">
          <AttackMatrix />
        </Tabs.Content>
        <Tabs.Content value="observables" className="pt-4">
          <ObservableList caseId={caseId} />
        </Tabs.Content>
        <Tabs.Content value="assets" className="pt-4">
          <AssetList caseId={caseId} />
        </Tabs.Content>
        <Tabs.Content value="evidence" className="pt-4">
          <EvidenceList caseId={caseId} />
        </Tabs.Content>
        <Tabs.Content value="notes" className="pt-4">
          <NotesEditor caseId={caseId} />
        </Tabs.Content>
        <Tabs.Content value="tasks" className="pt-4">
          <TaskList caseId={caseId} />
        </Tabs.Content>
        <Tabs.Content value="reports" className="pt-4">
          <ReportGenerator caseId={caseId} />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}

function Overview({
  description,
  tags,
}: {
  description: string | null;
  tags: string[];
}) {
  return (
    <div className="max-w-3xl space-y-4 rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark p-4">
      <section>
        <h3 className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
          Description
        </h3>
        <p className="mt-2 whitespace-pre-wrap text-sm text-watari-text-dark-primary">
          {description || (
            <span className="text-watari-text-dark-secondary">
              No description.
            </span>
          )}
        </p>
      </section>
      <section>
        <h3 className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
          Tags
        </h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {tags.length > 0 ? (
            tags.map((t) => (
              <span
                key={t}
                className="rounded-full bg-watari-bg-dark-tertiary px-2.5 py-0.5 text-xs text-watari-text-dark-primary"
              >
                {t}
              </span>
            ))
          ) : (
            <span className="text-sm text-watari-text-dark-secondary">
              No tags.
            </span>
          )}
        </div>
      </section>
    </div>
  );
}

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { casesApi } from "@/api/resources";
import { Button } from "@/components/common/Button";
import { SeverityBadge, StatusBadge } from "@/components/common/Badge";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import { Select, TextInput } from "@/components/common/Field";
import {
  TD,
  TH,
  THead,
  TR,
  Table,
  TableEmpty,
} from "@/components/common/Table";
import { CreateCaseDialog } from "@/components/cases/CreateCaseDialog";
import { useTenantStore } from "@/stores/tenant";
import type { CaseSeverity, CaseStatus } from "@/types/api";

const STATUSES: (CaseStatus | "")[] = [
  "",
  "new",
  "in_progress",
  "pending",
  "resolved",
  "closed",
];
const SEVERITIES: (CaseSeverity | "")[] = [
  "",
  "critical",
  "high",
  "medium",
  "low",
  "informational",
];

export function CaseList() {
  const tenantId = useTenantStore((s) => s.activeTenantId);
  const navigate = useNavigate();
  const [status, setStatus] = useState<CaseStatus | "">("");
  const [severity, setSeverity] = useState<CaseSeverity | "">("");
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);

  const params = useMemo(() => {
    const p: Record<string, string> = {};
    if (status) p.status = status;
    if (severity) p.severity = severity;
    if (search.trim()) p.search = search.trim();
    return p;
  }, [status, severity, search]);

  const { data, isLoading } = useQuery({
    queryKey: ["cases", tenantId, params],
    queryFn: () => casesApi.list(tenantId!, params),
    enabled: !!tenantId,
  });

  if (!tenantId)
    return (
      <p className="text-sm text-watari-text-dark-secondary">
        No active tenant.
      </p>
    );

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Cases</h2>
          <p className="text-sm text-watari-text-dark-secondary">
            Filterable list of security cases
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>New case</Button>
      </header>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <TextInput
          placeholder="Search title or description…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value as CaseStatus | "")}
        >
          {STATUSES.map((s) => (
            <option key={s || "any"} value={s}>
              {s ? s.replace("_", " ") : "Any status"}
            </option>
          ))}
        </Select>
        <Select
          value={severity}
          onChange={(e) => setSeverity(e.target.value as CaseSeverity | "")}
        >
          {SEVERITIES.map((s) => (
            <option key={s || "any"} value={s}>
              {s || "Any severity"}
            </option>
          ))}
        </Select>
      </div>

      {isLoading ? (
        <LoadingOverlay label="Loading cases" />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH className="w-20">#</TH>
              <TH>Title</TH>
              <TH className="w-32">Severity</TH>
              <TH className="w-32">Status</TH>
              <TH className="w-40">Created</TH>
            </TR>
          </THead>
          <tbody>
            {data?.data.length ? (
              data.data.map((c) => (
                <TR key={c.id} onClick={() => navigate(`/cases/${c.id}`)}>
                  <TD className="font-mono text-watari-text-dark-secondary">
                    #{c.case_number}
                  </TD>
                  <TD className="font-medium">{c.title}</TD>
                  <TD>
                    <SeverityBadge severity={c.severity} />
                  </TD>
                  <TD>
                    <StatusBadge status={c.status} />
                  </TD>
                  <TD className="text-watari-text-dark-secondary">
                    {new Date(c.created_at).toLocaleString()}
                  </TD>
                </TR>
              ))
            ) : (
              <TableEmpty colSpan={5}>No cases match your filters.</TableEmpty>
            )}
          </tbody>
        </Table>
      )}

      <CreateCaseDialog
        open={open}
        onOpenChange={setOpen}
        onCreated={(created) => navigate(`/cases/${created.id}`)}
      />
    </div>
  );
}

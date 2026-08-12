import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { tenantsApi } from "@/api/resources";
import { Button } from "@/components/common/Button";
import { Dialog } from "@/components/common/Dialog";
import { Field, TextInput } from "@/components/common/Field";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import {
  TD,
  TH,
  THead,
  TR,
  Table,
  TableEmpty,
} from "@/components/common/Table";
import { useAuthStore } from "@/stores/auth";
import { useTenantStore } from "@/stores/tenant";

export function TenantManagement() {
  const user = useAuthStore((s) => s.user);
  const activeTenantId = useTenantStore((s) => s.activeTenantId);
  const setActive = useTenantStore((s) => s.setActive);
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["tenants"],
    queryFn: () => tenantsApi.list(),
    enabled: user?.role === "platform_admin",
  });

  if (user?.role !== "platform_admin") {
    return (
      <p className="text-sm text-watari-text-dark-secondary">
        Platform administrator role required.
      </p>
    );
  }
  if (isLoading || !data) return <LoadingOverlay label="Loading tenants" />;

  const tenants = data.data;

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Tenants</h2>
          <p className="text-sm text-watari-text-dark-secondary">
            Manage tenant organizations on this platform
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>New tenant</Button>
      </header>

      <Table>
        <THead>
          <TR>
            <TH>Name</TH>
            <TH className="w-44">Slug</TH>
            <TH className="w-28">Status</TH>
            <TH className="w-40">Created</TH>
            <TH className="w-32">Actions</TH>
          </TR>
        </THead>
        <tbody>
          {tenants.length === 0 ? (
            <TableEmpty colSpan={5}>No tenants yet.</TableEmpty>
          ) : (
            tenants.map((t) => (
              <TR key={t.id}>
                <TD>
                  <div className="font-medium text-watari-text-dark-primary">
                    {t.name}
                  </div>
                  <div className="font-mono text-xs text-watari-text-dark-secondary">
                    {t.id.slice(0, 8)}
                  </div>
                </TD>
                <TD className="font-mono text-xs">{t.slug}</TD>
                <TD>
                  {t.is_active ? (
                    <span className="rounded-full bg-status-resolved/15 px-2 py-0.5 text-xs font-medium text-status-resolved">
                      Active
                    </span>
                  ) : (
                    <span className="rounded-full bg-status-closed/15 px-2 py-0.5 text-xs font-medium text-status-closed">
                      Disabled
                    </span>
                  )}
                </TD>
                <TD className="text-watari-text-dark-secondary">
                  {new Date(t.created_at).toLocaleString()}
                </TD>
                <TD>
                  {activeTenantId === t.id ? (
                    <span className="text-xs text-watari-gold">Current</span>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setActive(t.id)}
                    >
                      Switch to
                    </Button>
                  )}
                </TD>
              </TR>
            ))
          )}
        </tbody>
      </Table>

      {dialogOpen ? (
        <CreateTenantDialog onClose={() => setDialogOpen(false)} />
      ) : null}
    </div>
  );
}

function CreateTenantDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      tenantsApi.create({
        name: name.trim(),
        slug: slug.trim(),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tenants"] });
      onClose();
    },
    onError: (err: unknown) =>
      setError(err instanceof Error ? err.message : "Failed to create tenant"),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim() || !slug.trim()) {
      setError("Name and slug are required");
      return;
    }
    if (!/^[a-z0-9][a-z0-9-]*$/.test(slug.trim())) {
      setError(
        "Slug must start with a letter or digit and contain only lowercase letters, digits, and hyphens.",
      );
      return;
    }
    create.mutate();
  };

  return (
    <Dialog
      open
      onOpenChange={(o) => (o ? null : onClose())}
      title="Create tenant"
      description="Provision a new isolated tenant on this platform"
    >
      <form onSubmit={onSubmit} className="space-y-3">
        <Field label="Name" required>
          <TextInput
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              if (!slug) {
                setSlug(
                  e.target.value
                    .toLowerCase()
                    .replace(/[^a-z0-9]+/g, "-")
                    .replace(/^-+|-+$/g, ""),
                );
              }
            }}
            placeholder="Acme Corp Security"
          />
        </Field>
        <Field label="Slug" required>
          <TextInput
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="acme-corp-security"
          />
        </Field>
        {error ? (
          <p className="rounded-md bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
            {error}
          </p>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={create.isPending}>
            Create tenant
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usersApi } from "@/api/resources";
import { Button } from "@/components/common/Button";
import { Dialog } from "@/components/common/Dialog";
import { Field, Select, TextInput } from "@/components/common/Field";
import { LoadingOverlay } from "@/components/common/LoadingOverlay";
import {
  TD,
  TH,
  THead,
  TR,
  Table,
  TableEmpty,
} from "@/components/common/Table";
import { useTenantStore } from "@/stores/tenant";
import type { Role, UUID, User } from "@/types/api";

const ROLES: { value: Role; label: string }[] = [
  { value: "tenant_admin", label: "Tenant administrator" },
  { value: "analyst", label: "Analyst" },
  { value: "read_only", label: "Read-only viewer" },
];

export function UserManagement() {
  const tenantId = useTenantStore((s) => s.activeTenantId);
  const qc = useQueryClient();
  const [showUserDialog, setShowUserDialog] = useState(false);
  const [showServiceAccountDialog, setShowServiceAccountDialog] =
    useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["users", tenantId],
    queryFn: () => usersApi.list(tenantId!),
    enabled: !!tenantId,
  });

  const deactivate = useMutation({
    mutationFn: (userId: UUID) => usersApi.deactivate(tenantId!, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users", tenantId] }),
  });

  if (!tenantId)
    return (
      <p className="text-sm text-watari-text-dark-secondary">
        No active tenant.
      </p>
    );
  if (isLoading || !data) return <LoadingOverlay label="Loading users" />;

  const users = data.data;

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Users</h2>
          <p className="text-sm text-watari-text-dark-secondary">
            Manage users and service accounts for this tenant
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => setShowServiceAccountDialog(true)}
          >
            New API service account
          </Button>
          <Button onClick={() => setShowUserDialog(true)}>New user</Button>
        </div>
      </header>

      <Table>
        <THead>
          <TR>
            <TH>Username</TH>
            <TH>Email / Account</TH>
            <TH className="w-40">Role</TH>
            <TH className="w-28">Status</TH>
            <TH className="w-40">Last login</TH>
            <TH className="w-28">Actions</TH>
          </TR>
        </THead>
        <tbody>
          {users.length === 0 ? (
            <TableEmpty colSpan={6}>No users yet.</TableEmpty>
          ) : (
            users.map((u) => (
              <TR key={u.id}>
                <TD>
                  <div className="font-medium text-watari-text-dark-primary">
                    {u.display_name}
                  </div>
                  <div className="font-mono text-xs text-watari-text-dark-secondary">
                    {u.username}
                  </div>
                </TD>
                <TD className="text-watari-text-dark-secondary">
                  {u.is_service_account ? (
                    <span className="rounded bg-watari-gold-muted/20 px-1.5 py-0.5 font-mono text-[10px] text-watari-gold">
                      SERVICE ACCOUNT
                    </span>
                  ) : (
                    u.email
                  )}
                </TD>
                <TD>
                  <span className="rounded-full bg-watari-bg-dark-tertiary px-2 py-0.5 text-xs uppercase tracking-wider">
                    {u.role.replace("_", " ")}
                  </span>
                </TD>
                <TD>
                  {u.is_active ? (
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
                  {u.last_login_at
                    ? new Date(u.last_login_at).toLocaleString()
                    : "—"}
                </TD>
                <TD>
                  {u.is_active ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => deactivate.mutate(u.id)}
                    >
                      Disable
                    </Button>
                  ) : (
                    "—"
                  )}
                </TD>
              </TR>
            ))
          )}
        </tbody>
      </Table>

      {showUserDialog ? (
        <CreateUserDialog
          tenantId={tenantId}
          onClose={() => setShowUserDialog(false)}
        />
      ) : null}
      {showServiceAccountDialog ? (
        <CreateServiceAccountDialog
          tenantId={tenantId}
          onClose={() => setShowServiceAccountDialog(false)}
        />
      ) : null}
    </div>
  );
}

function CreateUserDialog({
  tenantId,
  onClose,
}: {
  tenantId: UUID;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<Role>("analyst");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      usersApi.create(tenantId, {
        username: username.trim(),
        email: email.trim(),
        display_name: displayName.trim() || username.trim(),
        role,
        password,
      } as Partial<User> & { password?: string }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users", tenantId] });
      onClose();
    },
    onError: (err: unknown) =>
      setError(err instanceof Error ? err.message : "Failed to create user"),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!username.trim() || !email.trim() || !password || password.length < 8) {
      setError("Username, email, and password (min 8 chars) are required");
      return;
    }
    create.mutate();
  };

  return (
    <Dialog
      open
      onOpenChange={(o) => (o ? null : onClose())}
      title="Create user"
      description="Add a new analyst, tenant admin, or read-only viewer"
    >
      <form onSubmit={onSubmit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Username" required>
            <TextInput
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="off"
            />
          </Field>
          <Field label="Role">
            <Select
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label="Display name">
          <TextInput
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Will default to username"
          />
        </Field>
        <Field label="Email" required>
          <TextInput
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label="Password" required>
          <TextInput
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            autoComplete="new-password"
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
            Create user
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function CreateServiceAccountDialog({
  tenantId,
  onClose,
}: {
  tenantId: UUID;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<"analyst" | "read_only">("analyst");
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      usersApi.createServiceAccount(tenantId, {
        username: username.trim(),
        display_name: displayName.trim() || username.trim(),
        role,
      }),
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ["users", tenantId] });
      setCreatedKey(response.data.api_key);
    },
    onError: (err: unknown) =>
      setError(
        err instanceof Error ? err.message : "Failed to create service account",
      ),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!username.trim()) {
      setError("Username is required");
      return;
    }
    create.mutate();
  };

  if (createdKey) {
    return (
      <Dialog
        open
        onOpenChange={(o) => (o ? null : onClose())}
        title="API key generated"
        description="Copy this key now — it cannot be retrieved later"
      >
        <div className="space-y-3">
          <pre className="overflow-x-auto rounded-md bg-watari-bg-dark p-3 font-mono text-xs text-watari-gold">
            {createdKey}
          </pre>
          <p className="rounded-md bg-severity-high/10 p-3 text-xs text-severity-high">
            This is the only time the API key will be shown. Store it securely.
          </p>
          <div className="flex justify-end">
            <Button onClick={onClose}>Done</Button>
          </div>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog
      open
      onOpenChange={(o) => (o ? null : onClose())}
      title="Create API service account"
      description="Non-interactive account authenticated via X-API-Key header"
    >
      <form onSubmit={onSubmit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Username" required>
            <TextInput
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. wazuh-ingest"
            />
          </Field>
          <Field label="Permissions">
            <Select
              value={role}
              onChange={(e) =>
                setRole(e.target.value as "analyst" | "read_only")
              }
            >
              <option value="analyst">Analyst (read/write)</option>
              <option value="read_only">Read-only</option>
            </Select>
          </Field>
        </div>
        <Field label="Display name">
          <TextInput
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
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
            Generate API key
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

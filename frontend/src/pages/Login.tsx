import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/common/Button";
import { useAuthStore } from "@/stores/auth";
import { useTenantStore } from "@/stores/tenant";

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const login = useAuthStore((s) => s.login);
  const loading = useAuthStore((s) => s.loading);
  const error = useAuthStore((s) => s.error);
  const setActiveTenant = useTenantStore((s) => s.setActive);
  const navigate = useNavigate();

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await login(username, password);
    const user = useAuthStore.getState().user;
    if (user) {
      setActiveTenant(user.tenant_id);
      navigate("/dashboard");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-watari-bg-dark text-watari-text-dark-primary">
      <div className="w-full max-w-sm rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark-secondary p-8 shadow-2xl">
        <h1 className="text-3xl font-semibold tracking-tight text-watari-gold">
          Watari
        </h1>
        <p className="mt-1 text-sm text-watari-text-dark-secondary">
          Sign in to your case management workspace
        </p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <label className="block">
            <span className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
              Username
            </span>
            <input
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="mt-1 w-full rounded-md border border-watari-bg-dark-tertiary bg-watari-bg-dark px-3 py-2 text-sm outline-none focus:border-watari-gold"
            />
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-wider text-watari-text-dark-secondary">
              Password
            </span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-watari-bg-dark-tertiary bg-watari-bg-dark px-3 py-2 text-sm outline-none focus:border-watari-gold"
            />
          </label>

          {error ? (
            <p className="rounded-md bg-severity-critical/10 px-3 py-2 text-sm text-severity-critical">
              {error}
            </p>
          ) : null}

          <Button type="submit" loading={loading} className="w-full">
            Sign in
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-watari-text-dark-secondary">
          Default dev credentials: <code>admin</code> / <code>admin</code>
        </p>
      </div>
    </div>
  );
}

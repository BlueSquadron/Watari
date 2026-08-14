#!/usr/bin/env bash
#
# Watari — one-command bootstrap.
#
#   ./bootstrap.sh
#
# Brings up the whole stack (Postgres, Redis, MinIO, API, worker, frontend),
# applies migrations, loads the demo dataset, and prints where to log in.
#
# Safe to re-run: the seed script is idempotent and skips tenants that
# already exist. Pass --reset to wipe volumes and start from zero.

set -euo pipefail

COMPOSE=${COMPOSE:-docker compose}
RESET=0
SKIP_SEED=0

for arg in "$@"; do
  case "$arg" in
    --reset)     RESET=1 ;;
    --no-seed)   SKIP_SEED=1 ;;
    -h|--help)
      cat <<'USAGE'
Watari — one-command bootstrap.

  ./bootstrap.sh [--reset] [--no-seed]

Brings up the whole stack (Postgres, Redis, MinIO, API, worker, frontend),
applies migrations, loads the demo dataset, and prints where to log in.

Safe to re-run: the seed script is idempotent and skips tenants that
already exist.

Options:
  --reset     Delete all containers AND volumes first (destroys local data)
  --no-seed   Start the stack and migrate, but skip the demo dataset
  -h, --help  Show this message
USAGE
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)" >&2
      exit 1
      ;;
  esac
done

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
info() { printf '  \033[36m→\033[0m %s\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$1" >&2; exit 1; }

cd "$(dirname "$0")"

# --------------------------------------------------------------------------
bold "Watari bootstrap"
echo

# 1. Preflight ------------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "Docker is not installed. See https://docs.docker.com/get-docker/"
$COMPOSE version >/dev/null 2>&1 || die "Docker Compose v2 is not available. Update Docker, or set COMPOSE=\"docker-compose\"."
docker info >/dev/null 2>&1 || die "Docker is installed but not running. Start Docker Desktop (or OrbStack/Colima) and retry."
ok "Docker is running"

# 2. Environment file -----------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  ok "Created .env from .env.example"
else
  ok ".env already present (left untouched)"

  # An .env written before Row-Level Security landed will still point
  # DATABASE_URL at the superuser that owns the schema. Everything appears to
  # work — and tenant isolation is silently not enforced. Fail loudly instead.
  missing=""
  for key in APP_DB_USER APP_DB_PASSWORD ADMIN_DATABASE_URL; do
    grep -q "^${key}=" .env || missing="${missing} ${key}"
  done

  owner=$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2- || true)
  owner_on_request_path=0
  if [ -n "$owner" ] && grep -qE "^DATABASE_URL=.*//${owner}:" .env; then
    owner_on_request_path=1
  fi

  if [ -n "$missing" ] || [ "$owner_on_request_path" -eq 1 ]; then
    echo
    bold "Your .env predates the Row-Level Security change."
    echo
    [ -n "$missing" ] && echo "  Missing keys:$missing"
    [ "$owner_on_request_path" -eq 1 ] && \
      echo "  DATABASE_URL still connects as '${owner}', which owns the schema and"
    [ "$owner_on_request_path" -eq 1 ] && \
      echo "  bypasses every RLS policy — tenant isolation would not be enforced."
    echo
    echo "  Add to .env:"
    echo
    echo "    APP_DB_USER=watari_app"
    echo "    APP_DB_PASSWORD=watari_app_dev_password"
    echo "    ADMIN_DATABASE_URL=postgresql+asyncpg://${owner:-watari}:<password>@postgres:5432/watari"
    echo
    echo "  and point DATABASE_URL at the unprivileged role:"
    echo
    echo "    DATABASE_URL=postgresql+asyncpg://watari_app:watari_app_dev_password@postgres:5432/watari"
    echo
    echo "  Compare against .env.example, which has the full annotated set."
    die "Refusing to start with a configuration that disables tenant isolation."
  fi
  ok "Environment has the roles this release needs"
fi

# 3. Optional reset -------------------------------------------------------
if [ "$RESET" -eq 1 ]; then
  info "Removing existing containers and volumes…"
  $COMPOSE down -v --remove-orphans >/dev/null 2>&1 || true
  ok "Clean slate"
fi

# 4. Start the stack ------------------------------------------------------
info "Starting services (first run pulls images and builds — this can take a few minutes)…"
$COMPOSE up -d
ok "Containers up"

# 5. Wait for the API -----------------------------------------------------
info "Waiting for the API to become healthy…"
for i in $(seq 1 90); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    ok "API is healthy (http://localhost:8000)"
    break
  fi
  if [ "$i" -eq 90 ]; then
    echo
    die "API did not come up within 90s. Inspect the logs with: $COMPOSE logs api"
  fi
  sleep 1
done

# 6. Migrate --------------------------------------------------------------
info "Applying database migrations…"
$COMPOSE exec -T api alembic upgrade head >/dev/null
ok "Schema is up to date"

# 7. Seed -----------------------------------------------------------------
if [ "$SKIP_SEED" -eq 0 ]; then
  info "Loading the demo dataset (2 tenants, 13 users, 32 cases, alerts, observables)…"
  $COMPOSE exec -T api python -m scripts.seed >/dev/null
  ok "Demo data loaded"
else
  info "Skipping demo data (--no-seed)"
fi

# 8. Wait for the frontend ------------------------------------------------
info "Waiting for the frontend dev server…"
for i in $(seq 1 120); do
  if curl -fsS http://localhost:5173 >/dev/null 2>&1; then
    ok "Frontend is serving (http://localhost:5173)"
    break
  fi
  [ "$i" -eq 120 ] && info "Frontend still starting — it installs npm packages on first run. Check: $COMPOSE logs -f frontend"
  sleep 1
done

# --------------------------------------------------------------------------
echo
bold "Watari is ready."
echo
echo "  Web UI      http://localhost:5173"
echo "  API docs    http://localhost:8000/docs"
echo "  MinIO       http://localhost:9001   (minioadmin / minioadmin)"
echo
if [ "$SKIP_SEED" -eq 0 ]; then
  bold "Sign in with"
  echo
  echo "  acme-admin      / password    Tenant admin, best starting point"
  echo "  acme-analyst1   / password    Analyst"
  echo "  acme-viewer     / password    Read-only"
  echo "  admin           / admin       Platform admin (sees every tenant)"
  echo
  echo "  These are development credentials. Never deploy them."
  echo
fi
echo "Stop everything with:  $COMPOSE down"
echo "Start again with:      $COMPOSE up -d"
echo

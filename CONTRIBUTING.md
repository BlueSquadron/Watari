# Contributing to Watari

Thanks for being here. Watari is early — v0.1.0, alpha — which means almost
anything you touch will be an improvement, and a first-time contributor can land
something meaningful in an afternoon.

- [Get set up](#get-set-up)
- [Known gaps & good first issues](#known-gaps--good-first-issues)
- [Running the tests](#running-the-tests)
- [Code style](#code-style)
- [Working with the database](#working-with-the-database)
- [Submitting a change](#submitting-a-change)
- [Where things live](#where-things-live)

---

## Get set up

You need Docker. Everything else runs in containers.

```bash
git clone https://github.com/BlueSquadron/Watari.git
cd Watari
./bootstrap.sh
```

Both the API and the frontend hot-reload — `backend/` and `frontend/` are
bind-mounted into their containers, so edit a file on your machine and the change
takes effect immediately. No rebuild needed for ordinary code changes.

Rebuild only when you change dependencies:

```bash
docker compose build api worker   # after editing backend/pyproject.toml
docker compose restart frontend   # after editing frontend/package.json
```

Useful day-to-day:

```bash
docker compose logs -f api      # tail the API
docker compose exec api bash    # shell inside the API container
make shell-db                   # psql into the dev database
make help                       # every Makefile target
./bootstrap.sh --reset          # nuke everything and start clean
```

### Optional: local Python and Node

Only needed if you want to run linters or tests outside the containers, or want
editor autocomplete.

```bash
# Backend — use a virtualenv, don't install into your system Python
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Frontend
cd frontend && npm install
```

---

## Known gaps & good first issues

These are real, reproducible, and currently unfixed. Each one is a genuinely
useful contribution. Please check the
[issue tracker](https://github.com/BlueSquadron/Watari/issues) first in case
someone got there ahead of you.

### 🐛 `GET /timeline` returns 500 whenever a case has entries — [#1](https://github.com/BlueSquadron/Watari/issues/1)

**Impact: high.** This breaks the Timeline tab, the Swimlane view, *and* the
entity Graph (the graph component waits on all three of its queries, so a
timeline failure leaves it showing zero nodes). Three headline features are dark
because of one line.

Reproduce:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"acme-admin","password":"password"}' | jq -r .data.access_token)
# any seeded case with timeline entries
curl -s "http://localhost:8000/api/v1/tenants/$TENANT/cases/$CASE/timeline" \
  -H "Authorization: Bearer $TOKEN"
```

```
pydantic_core.ValidationError: 1 validation error for TimelineEntryResponse
metadata
  Input should be a valid dictionary [input_value=MetaData(), input_type=MetaData]
```

Cause: `TimelineEntryResponse` declares `event_metadata: dict = Field(alias="metadata")`
(`backend/src/schemas/timeline.py:42`). The ORM model maps the same column as
`event_metadata` (`backend/src/models/timeline.py:42`), so when
`_response_with_links` calls `model_validate(entry)`
(`backend/src/api/routers/timeline.py:37`) Pydantic resolves the `metadata`
alias against the SQLAlchemy declarative `MetaData` class attribute instead of
the JSONB column.

Fix direction: validate from the ORM attribute name rather than the alias, or
rename the response field so it stops colliding with `Base.metadata`. Please add
a regression test — `backend/tests/property/test_timeline_ordering.py` is the
natural home.

### 🐛 `POST /search` returns 500 — [#2](https://github.com/BlueSquadron/Watari/issues/2) · good first issue

**Impact: high.** Full-text search is a headline feature and the Search page
returns nothing.

```
AttributeError: type object 'Alert' has no attribute 'description'
  backend/src/services/search.py:139
```

The alert branch of the search query filters on `Alert.description`, which
doesn't exist on the model. Check what the field is actually called and whether
the other branches (cases, observables, assets, notes) have the same problem.

### 🔒 Row-Level Security is enabled but never enforced — [#4](https://github.com/BlueSquadron/Watari/issues/4)

**Impact: high.** This is the platform's headline security property, and right
now tenant isolation rests entirely on the service layer's explicit
`WHERE tenant_id = ...` predicates. Any query that forgets one silently returns
another tenant's rows.

The policies in `0002_row_level_security.py` are correct. Two things stop them
from ever applying:

1. The app connects as `watari`, which is a **superuser** — superusers bypass
   RLS unconditionally.
2. The tables are `ENABLE ROW LEVEL SECURITY` but not `FORCE`, so the table
   owner — also `watari` — bypasses them too.

See for yourself, with one tenant in context:

```console
$ docker compose exec -T postgres psql -U watari -d watari \
  -c "BEGIN;
      SELECT set_config('app.current_tenant','<acme-tenant-uuid>',true);
      SELECT count(DISTINCT tenant_id) AS tenants_visible FROM cases;
      ROLLBACK;"

 tenants_visible
-----------------
               2
```

`backend/tests/property/test_tenant_isolation.py` catches this — its two
isolation tests are marked `xfail(strict=True)`, so they become hard failures
the moment it's fixed.

This is a **big** one, not a starter task. It needs a non-superuser application
role, a `FORCE ROW LEVEL SECURITY` migration, and a fix to the dependency
ordering that stops `get_db` from ever seeing the auth context — landed
together. Any one alone either changes nothing or takes the application down.
The issue has the full write-up.

### 🧹 Hypothesis cache is committed to the repo

154 of the 403 tracked files are `backend/.hypothesis/constants/*` — local test
cache that shouldn't be in version control. Add `.hypothesis/` to `.gitignore`
and `git rm -r --cached backend/.hypothesis`.

### 🎨 Smaller things

- Leaflet marker icons 404 on the case Map tab (the default icon asset isn't bundled by Vite — a well-known Leaflet + bundler papercut).
- The dashboard's "open cases by severity" bars render as hairlines at some viewport widths.
- The audit log page is empty after seeding, even though the seed script's docstring says it records audit entries.
- There is no CI. A GitHub Actions workflow running ruff, mypy, `tsc --noEmit`, and pytest would catch all of the above.

Found something else? [Open an issue](https://github.com/BlueSquadron/Watari/issues/new/choose).

---

## Running the tests

The test dependencies aren't in the API image yet, so run them from a local
virtualenv (see "Optional: local Python and Node" above). Everything lives
under `backend/tests/`.

### The quick loop

Most of the property suites need no database at all — clustering, OCSF
round-tripping, pagination, hash verification, TLP rules, geolocation:

```bash
cd backend
source .venv/bin/activate

PYTHONPATH=. pytest tests/property -q
```

Without `TEST_DATABASE_URL` set, the DB-backed suites skip themselves and the
remaining 116 tests run in a couple of seconds.

### The full suite

Point it at a **dedicated** database. The session fixture runs
`alembic downgrade base` on teardown, which drops every table — so the
fixture refuses to start unless the database name contains `test`.

```bash
# once
docker compose exec postgres createdb -U watari watari_test

cd backend
TEST_DATABASE_URL=postgresql+asyncpg://watari:watari_dev_password@localhost:5432/watari_test \
S3_ENDPOINT_URL=http://localhost:9000 \
  PYTHONPATH=. pytest tests/ -q
```

`S3_ENDPOINT_URL` is only needed for the integration tests: the default points
at `minio:9000`, which resolves inside the Compose network but not from your
host.

Expect **145 passed, 2 xfailed**. The two expected failures are the
Row-Level Security isolation tests — the policies exist but nothing enforces
them today, tracked in [#4](https://github.com/BlueSquadron/Watari/issues/4).
They're marked `strict=True`, so they will turn into hard failures the moment
that's fixed, which is the signal to delete the marker.

### What the property tests are

Watari has 29 [Hypothesis](https://hypothesis.readthedocs.io/) suites asserting
correctness properties rather than examples — tenant isolation, RBAC, TLP
enforcement, evidence hash verification, OCSF round-tripping, pagination,
case-number sequencing, module failure isolation, and more. They're the most
valuable tests in the repo and the best place to add coverage.

### Frontend

```bash
cd frontend
npx tsc --noEmit    # type check
npm run lint
```

### Everything

```bash
make test    # unit + property + integration
make lint    # ruff + mypy + tsc
make format  # ruff format + prettier
```

---

## Code style

Formatting is not a matter of taste here — run the formatters and move on.

**Python** — [Ruff](https://docs.astral.sh/ruff/) (line length 100, target
py312, rules `E,F,I,N,W,UP`) and mypy in strict mode. Type annotations are
required on new functions.

```bash
cd backend && ruff format src tests && ruff check src tests && mypy src
```

**TypeScript** — Prettier and ESLint. Strict TypeScript; avoid `any`.

```bash
cd frontend && npx prettier --write "src/**/*.{ts,tsx,css}" && npm run lint
```

**Conventions worth matching**

- Business logic lives in `backend/src/services/`, not in routers. Routers
  validate, authorise, delegate, and shape the response.
- Every tenant-scoped query goes through the RLS-aware session. If you find
  yourself writing `WHERE tenant_id = ...` by hand, check whether you've
  bypassed the isolation layer.
- API responses use the `ApiResponse` envelope with `data` and `meta`.
- New endpoints need an entry in [`backend/API_COVERAGE.md`](backend/API_COVERAGE.md).
- Frontend data fetching goes through React Query hooks in `frontend/src/api/`.

---

## Working with the database

Schema changes need an Alembic migration:

```bash
docker compose exec api alembic revision --autogenerate -m "add widget table"
docker compose exec api alembic upgrade head
```

Review the generated migration before committing — autogenerate misses RLS
policies, index details, and enum changes. See
`backend/alembic/versions/0002_row_level_security.py` for how tenant isolation
policies are declared.

Reload the demo dataset at any time:

```bash
make db-seed     # idempotent; skips tenants that already exist
make db-reset    # drop, migrate, re-seed (destructive)
```

The seed script is `backend/scripts/seed.py`. If you add a feature that has a
visible UI surface, seeding a realistic example of it is a genuine kindness to
everyone who runs the demo — and it makes your screenshots better.

---

## Submitting a change

1. **Open an issue first** for anything non-trivial, so we can agree on the
   approach before you spend an evening on it. Typos and obvious bugs don't
   need one.
2. **Branch** from `main`: `git checkout -b fix/timeline-metadata-alias`.
3. **Keep it focused.** One logical change per PR. Drive-by reformatting of
   unrelated files makes review much harder.
4. **Add a test.** Bug fix → regression test. New behaviour → property test if
   you can express it as an invariant, example test otherwise.
5. **Run the checks**: `make lint` and the unit suite, at minimum.
6. **Write a real commit message** — what changed and why, not just what.
7. **Open the PR** and fill in the template. Screenshots for UI changes, please.

There's no CLA. By contributing you agree your work is licensed under
[Apache 2.0](LICENSE).

### Review

Maintainers are volunteers. Expect a first response within a week; ping the PR
if it's been longer. Review comments are about the code, never about you — and
the same goes in the other direction. See the
[Code of Conduct](CODE_OF_CONDUCT.md).

---

## Where things live

```
backend/src/
├── api/routers/     one module per entity — routes, validation, authorisation
├── api/middleware/  request ID, error handling, CORS
├── auth/            JWT, RBAC, OIDC, SAML, API keys, sessions
├── models/          SQLAlchemy 2.0 declarative models
├── schemas/         Pydantic request/response schemas
├── services/        business logic — the interesting part
├── realtime/        WebSocket hub over Redis PubSub
├── worker/          Celery tasks
├── modules/         plugin system (BaseModule, ModuleAPI)
└── utils/

frontend/src/
├── pages/           one per route
├── components/
│   ├── layout/          app shell, sidebar, topbar, command palette
│   ├── cases/           case-specific components
│   ├── visualizations/  AttackMatrix, CaseGraph, GeospatialView, SwimlaneTimeline
│   └── common/
├── api/             API client + React Query hooks
├── stores/          Zustand (auth, theme)
└── realtime/        WebSocket client
```

**Reference material**

- [Integration guide](docs/integration.md) — how the API is meant to be used, end to end
- [API coverage](backend/API_COVERAGE.md) — every endpoint and method
- Swagger UI at http://localhost:8000/docs, ReDoc at http://localhost:8000/redoc

---

Questions are welcome in
[issues](https://github.com/BlueSquadron/Watari/issues). Thanks for helping. 🕴️

# Security Policy

Watari is incident response tooling. It holds evidence, indicators, and details
of live investigations across multiple tenants, so we take reports seriously and
would rather hear about a problem early.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x (`main`) | ✅ |
| Anything older | ❌ |

Watari is alpha software. There are no maintained release branches yet — fixes
land on `main`.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through
[GitHub Security Advisories](https://github.com/BlueSquadron/Watari/security/advisories/new),
which creates a private thread with the maintainers.

Helpful things to include:

- What the issue is and what an attacker gains
- Steps to reproduce, ideally against a `./bootstrap.sh` install
- Affected component (API endpoint, model, frontend route, module)
- The commit you tested
- Any proof of concept

### What to expect

| | |
|---|---|
| Acknowledgement | within 5 working days |
| Initial assessment | within 10 working days |
| Fix or mitigation plan | agreed with you, based on severity |
| Credit | in the advisory, unless you'd rather stay anonymous |

Watari is maintained by volunteers and there is no bug bounty. We will be honest
with you about timelines rather than optimistic.

Please give us reasonable time to ship a fix before disclosing publicly. If you
disagree with our assessment of severity, say so — we'd rather argue about it
than have you sit on a real issue.

## Areas we care most about

If you're looking for somewhere to point your attention:

- **Tenant isolation.** Any cross-tenant read or write is critical. Isolation is
  enforced by PostgreSQL Row-Level Security; a path that bypasses the RLS-aware
  session is a bug even if you can't yet prove data leaks through it.
- **Authentication and session handling.** JWT issuance and validation, refresh
  token handling, OIDC/SAML assertion processing, API key comparison.
- **Authorisation.** Role enforcement across the API — particularly read-only
  and service-account roles reaching write paths.
- **Evidence handling.** Storage access control, hash verification, encryption at
  rest, and anything that lets a user reach an object they don't own.
- **TLP enforcement.** Observables marked TLP:RED escaping their intended
  audience.
- **The module system.** Modules run project-supplied Python; sandbox escapes or
  privilege escalation through `ModuleAPI` are in scope.
- **Injection.** SQL, template injection in report generation, XSS through
  Markdown notes or observable values rendered in the UI.

## Out of scope

- The seeded development credentials (`admin`/`admin`, `*-analyst1`/`password`)
  and the placeholder secrets in `.env.example`. These are demo data, documented
  as such, and are not a vulnerability.
- Findings that require a `docker-compose.yml` dev stack to be exposed to the
  internet. The dev stack binds Postgres, Redis, and MinIO to the host with
  default credentials and is not a deployment target.
- Missing hardening headers or TLS on the local dev server.
- Automated scanner output without a demonstrated impact.

## Deploying Watari

Watari has not been hardened for production and has not had an external security
audit. If you deploy it anyway:

- Replace every secret in `.env` — `JWT_SECRET_KEY`, database credentials, S3
  keys. The defaults are public.
- Delete or disable the seeded accounts, starting with `admin`/`admin`.
- Never run the seed script against a real deployment.
- Terminate TLS in front of the API and frontend.
- Don't expose Postgres, Redis, or MinIO beyond the application network.
- Set `APP_ENV=production` and `APP_DEBUG=false` — debug mode returns full
  tracebacks in HTTP responses.
- Back up the database and the evidence bucket together; evidence metadata and
  objects need to stay consistent.

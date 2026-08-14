<!--
Thanks for contributing to Watari.

New here? CONTRIBUTING.md covers setup, tests, and code style:
https://github.com/BlueSquadron/Watari/blob/main/CONTRIBUTING.md
-->

## What does this change?

<!-- A sentence or two. What's different after this PR? -->

## Why?

<!-- The problem this solves. Link the issue: "Fixes #123" / "Part of #123" -->

## How?

<!-- Anything a reviewer needs to know to read the diff: approach taken,
     trade-offs, alternatives rejected, anything you're unsure about. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change (API, schema, or config)
- [ ] Documentation
- [ ] Tests / tooling / CI
- [ ] Refactor (no behaviour change)

## Testing

<!-- How did you verify this? Be specific — "ran the tests" is less useful than
     "added a regression test that fails on main and passes here". -->

- [ ] Added or updated tests
- [ ] Unit tests pass (`cd backend && PYTHONPATH=. pytest tests/ --ignore=tests/integration --ignore=tests/property -q`)
- [ ] Linters pass (`make lint`)
- [ ] Verified by hand against a `./bootstrap.sh` install

## Screenshots

<!-- Required for UI changes. Before/after is ideal. -->

## Checklist

- [ ] Focused on one logical change
- [ ] Follows the conventions in CONTRIBUTING.md (business logic in services, `ApiResponse` envelope, RLS-aware sessions)
- [ ] New or changed endpoints are recorded in `backend/API_COVERAGE.md`
- [ ] Schema changes include an Alembic migration, and I reviewed what autogenerate produced
- [ ] Documentation updated if behaviour or setup changed
- [ ] No secrets, credentials, or real incident data in the diff

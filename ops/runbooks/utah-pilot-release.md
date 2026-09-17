# Utah pilot atomic release

This runbook makes the approved units reversible. It does not rotate the database password, contact customers, charge money, or authorize a production release by itself.

## Base

- Rollback tag: `jetty-pre-utah-pilot-2026-09-16`
- Base commit: `6ed9ab9c759ed5ce452da7c620c6842f97da823a`

## Unit order

1. Security secret boundary (`3aa5348`). Do not rotate the live credential; use the separate sit-down runbook.
2. Quality gates (`4a8668c`). Require the workflow to pass before later merges.
3. CORS default (`b70e34b`). Set the exact production/preview origins before deploy.
4. Capability foundation (`35f5690`).
5. Gesture adapter (`6e89103`), after capability foundation.
6. Utah positioning (`2e315bb`).
7. Hero startup (`25499de`).
8. Backend auth (`ea1d97e`) and client auth (`722f189`) in one release window, after Supabase values are configured.

## Pre-deploy gate

- [ ] All selected PR checks pass on their rebased heads.
- [ ] Record the production commit and create a database backup.
- [ ] Confirm `VERONIKA_PG_DSN` exists in the managed secret store. Do not display it.
- [ ] Confirm `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and backend-only `SUPABASE_JWT_SECRET` are configured.
- [ ] Confirm `ALLOWED_ORIGINS` names the actual Vercel production and preview origins.
- [ ] Confirm `JETTY_REQUIRE_AUTH=true` only when both auth PRs are present.
- [ ] Confirm no generated frontend file contains `SUPABASE_JWT_SECRET` or the database DSN.

## Release proof

- Public `/` returns 200 while signed out.
- `/api/health` returns 200 while signed out.
- Private API returns 401 without a token.
- `/app` shows sign-in while signed out.
- Signed-in user can capture, retrieve, and delete a test note.
- A second test tenant cannot read the first tenant's note. If this test cannot pass, no real customer data enters Jetty.
- Desktop and mobile hero screenshots show static UI with moving water.
- Reduced-motion mode displays a stable hero.
- Directory and wellness demo data are labeled sample data.

## One-move rollback

For one unit, revert that PR's merge commit and redeploy. For the paired auth release, revert both merge commits in one rollback branch and redeploy with the former environment state. For the full release, redeploy `jetty-pre-utah-pilot-2026-09-16`; restore a database backup only after checking whether post-release customer data would be lost.

Never roll back by restoring the exposed database password. If credential work has started, follow `database-credential-rotation.md`.

## Stop conditions

Stop and roll back if private data is visible without auth, tenant isolation fails, the app cannot sign in, the private API and client auth are out of sync, hero UI moves with the water, or production secrets appear in generated assets/logs.

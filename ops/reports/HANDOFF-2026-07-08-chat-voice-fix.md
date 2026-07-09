# Jetty Handoff - Chat and Voice Recovery

Date: 2026-07-08
Repo: `C:\Users\execu\Documents\New project\veronika-jetty-second-brain`
Branch: `main`
Starting commit before this fix: `4503fd9`

## What was broken

- Production frontend at `https://veronika-jetty-second-brain.vercel.app` loaded correctly.
- Production `/api/*` calls timed out.
- VPS backend was healthy locally on `127.0.0.1:4700`, but public traffic to `31.220.58.212:4700` was not reachable from outside.
- Result: chat failed in production, and voice input looked broken because the mic path ultimately calls the same chat API.

## What was changed

### Repo changes

- `frontend/assets/app.js`
  - Changed API fallback behavior so production uses same-origin `/api` when no explicit API base is injected.
  - Local and `file:` usage now falls back to `http://localhost:4700`.

- `scripts/build-frontend.mjs`
  - Removed the baked-in `http://localhost:4700` default from generated `config.js`.
  - Production builds now emit an empty API base unless one is explicitly provided, which lets same-origin `/api` work cleanly.

- `vercel.json`
  - Changed the external rewrite target from blocked port `4700` on the raw VPS IP to:
  - `http://jetty-api.31.220.58.212.sslip.io/api/:path*`

### VPS changes

- Added nginx public origin:
  - Remote file: `/etc/nginx/sites-available/jetty-api`
  - Symlinked in: `/etc/nginx/sites-enabled/jetty-api`
- Public origin now proxies:
  - `http://jetty-api.31.220.58.212.sslip.io/api/*`
  - to `http://127.0.0.1:4700/api/*`
- Reloaded nginx successfully after config validation.

## Verified working

- Public API health:
  - `https://veronika-jetty-second-brain.vercel.app/api/health`
  - returned `ok: true`

- Public production chat:
  - `https://veronika-jetty-second-brain.vercel.app/api/chat`
  - returned `live chat ok` during smoke test

- Public API origin health:
  - `http://jetty-api.31.220.58.212.sslip.io/api/health`
  - returned `ok: true`

- Direct public API chat:
  - `http://jetty-api.31.220.58.212.sslip.io/api/chat`
  - returned a valid assistant answer

- Current production `config.js`:
  - `apiBaseUrl` is `/api`

## Voice status

- No backend voice service was required for this fix.
- Browser voice input is still the native Web Speech path in `frontend/assets/app.js`.
- Because production chat now works again, the most likely voice failure mode was the downstream chat timeout.
- Browser-mic permissions were not re-verified in an interactive browser during this pass.

## Remaining follow-up worth doing

1. Open the live app in a browser and test the mic button with permission granted on HTTPS.
2. Decide whether to keep `sslip.io` as the permanent Jetty API origin or replace it with a first-party subdomain.
3. Mirror the nginx config into infrastructure docs or deployment scripts so the VPS change is reproducible.
4. If desired, add stronger user-facing mic error copy for denied permissions and unsupported browsers.

## Files changed in repo

- `frontend/assets/app.js`
- `scripts/build-frontend.mjs`
- `vercel.json`
- `.beads/issues.jsonl`
- `.beads/.migration-hint-ts`

## Deployments and live endpoints

- Production site:
  - `https://veronika-jetty-second-brain.vercel.app`

- Vercel deployment from this pass:
  - `https://veronika-jetty-second-brain-b4e83na2t-the-pauli-effect.vercel.app`

- Public VPS API origin:
  - `http://jetty-api.31.220.58.212.sslip.io`

## Notes for the next model

- The VPS backend container `jetty-tm` was already healthy before the fix.
- The real issue was public reachability, not missing env keys or a broken model provider.
- `ANTHROPIC`, `OPENAI`, `GROQ`, `DEEPSEEK`, and `SYNTHIA` were all reporting available in `/api/health` during verification.
- If production chat breaks again, check in this order:
  1. `https://veronika-jetty-second-brain.vercel.app/api/health`
  2. `http://jetty-api.31.220.58.212.sslip.io/api/health`
  3. `ssh root@31.220.58.212 "curl -sS http://127.0.0.1:4700/api/health"`
  4. `ssh root@31.220.58.212 "nginx -t && systemctl status nginx --no-pager"`

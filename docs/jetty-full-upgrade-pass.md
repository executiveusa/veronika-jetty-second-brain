# JETTY™ — Full Upgrade Pass
**Target repo:** `executiveusa/veronika-jetty-second-brain`

This is a task list, not a narrative — work top to bottom, verify before claiming done.

---

## 0. Context load — do this before changing anything

```bash
cat README.md
cat vercel.json 2>/dev/null
cat docker-compose.yml
cat backend/main.py
cat frontend/assets/app.js
cat package.json
ls notes/ frontend/assets/
cat openapi.json 2>/dev/null | head -100
```

Confirm, in writing, before proceeding:
- Is the FastAPI backend deployed to Vercel as a serverless function, or does Vercel only serve the static frontend while the backend stays on the Hostinger VPS and the frontend calls it by IP/domain?
- What 3D library is actually powering the knowledge galaxy? Confirm from `frontend/assets/app.js` / `package.json` rather than assuming.
- Does a PWA manifest or service worker already exist? Check `frontend/` for `manifest.json` / `sw.js` before creating new ones.

Do not proceed on assumption where the repo can tell you the answer.

---

## 1. Supabase Auth

Full spec: `docs/jetty-supabase-auth-integration.md`.

Implement it adapted to the real `main.py` route names and `app.js` fetch calls, not generic placeholders.

After wiring auth, re-test every existing feature end to end: chat, notes save, voice, vision mode, galaxy render, Composio actions. The JWT needs to ride along on every `/api/*` call.

---

## 2. Vercel — make deployment production-ready

- Confirm serverless backend vs. VPS-backed frontend and make sure `vercel.json` routes match reality.
- Add `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` to Vercel Production and Preview environments.
- If backend is Vercel serverless, check max execution duration against model calls.
- Confirm `DAILY_COST_LIMIT_USD` and `RATE_LIMIT_PER_MINUTE` are enforced in `main.py`.
- Do a real deploy and hit the live URL before marking done.

---

## 3. Feature completeness — verify deployed build

- [ ] Chat bar responds using configured `MODEL_PROVIDER`
- [ ] Voice input/output functions
- [ ] "Remember that..." creates a note and a new galaxy star
- [ ] 3D galaxy renders; stars clickable; connections draw correctly
- [ ] Vision Mode: camera access, business card/contact flow, whiteboard transcription
- [ ] Composio actions actually fire
- [ ] Model switcher changes active provider

Anything broken: fix it or flag it explicitly.

---

## 4. Mobile readiness

- [ ] Manifest with icons, standalone display, theme/background colors
- [ ] Service worker caches app shell only, not fresh API responses
- [ ] Viewport uses `viewport-fit=cover`
- [ ] Touch targets minimum 44x44px
- [ ] 3D galaxy mobile frame rate checked; star/particle counts reduced if needed
- [ ] Touch controls verified
- [ ] Render loop pauses on `visibilitychange`
- [ ] Mobile voice permission behavior checked

---

## 5. Completion report

Write `ops/reports/full-upgrade-pass.md`:

```md
## What changed
- [list actual commits/files touched]

## What was verified working on live deploy
- [ ] ...

## What's still broken or incomplete
- [ ] ...

## Env vars added
- SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET — set in Vercel [Production/Preview] and VPS .env

## Known limitations
- ...
```

Do not report the pass as complete if any Step 3 or Step 4 item is unverified on the actual live deploy.

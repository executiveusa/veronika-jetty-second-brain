# Acceptance

## Must Pass
- Frontend loads from the static build output
- `/config.js` is present in the frontend deployment
- Backend `/api/health` returns `ok: true`
- Groq chat requests return a normal answer
- DeepSeek requests do not break the app when the DeepSeek account is unavailable
- Voice selector and model selector still work

## Rollback Proof
- A previous Vercel deployment can be restored
- A previous VPS backend revision can be restored
- The rollback path is recorded in Beads

## Verification
- Local Python syntax check
- Local frontend build
- Backend smoke test for health and chat
- Browser check after deployment

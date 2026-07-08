# Design

## Frontend
- Static output with `index.html`, `app.html`, assets, and a generated `config.js`
- Browser config must carry the backend API base URL
- Keep public landing and private app separated by route

## Backend
- Python API on the VPS
- Default provider should be Groq
- DeepSeek should be supported and fail over to Groq when the key is underfunded or unavailable
- Hermes config should be available through env and config routes

## Routing
- `/` -> landing page
- `/app` and `/brain` -> private app
- `/api/*` -> backend
- `/config.js` -> deployment-time browser config

## Rollback
- Frontend rollback is Vercel deployment rollback
- Backend rollback is previous VPS image or git revision
- Env rollback is the previous allowed env snapshot only

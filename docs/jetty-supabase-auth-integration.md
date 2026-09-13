# JETTY™ — Supabase Auth Integration

Locks `/app` behind email+password. Signups stay open (share the link), but no password = no entry.

## 1. Supabase dashboard (5 min)

1. Create or open your Supabase project.
2. **Authentication → Providers → Email** — make sure Email is enabled.
3. **Authentication → Settings** — leave "Allow new users to sign up" **ON** (that's the open-invite part).
4. **Project Settings → API** — copy three values:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_ANON_KEY`
   - `JWT Secret` (under "JWT Settings") → `SUPABASE_JWT_SECRET`

## 2. Add to `.env.example` and your real `.env`

```env
# ============================================================
# SUPABASE AUTH
# ============================================================
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_JWT_SECRET=
```

`SUPABASE_JWT_SECRET` is backend-only — never ship it to the frontend. `SUPABASE_URL` and `SUPABASE_ANON_KEY` are safe client-side.

If secrets are kept in Infisical, these three go in the vault like the rest — this file just documents what needs to exist.

## 3. Backend — `backend/auth.py`

Drop this next to `main.py`. It verifies the Supabase-issued JWT locally using the JWT secret.

```python
import os
import jwt
from fastapi import Header, HTTPException

SUPABASE_JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    return {"id": payload["sub"], "email": payload.get("email")}
```

Add `pyjwt` to `requirements.txt` if it is not already there.

## 4. Wire it into `main.py`

Import the dependency and add it to routes that serve `/app` and protected `/api/*` endpoints:

```python
from auth import get_current_user
from fastapi import Depends

@app.get("/app")
def serve_app(user: dict = Depends(get_current_user)):
    ...

# repeat Depends(get_current_user) on any /api/* route that should require login
```

Anything left without `Depends(get_current_user)` stays public — that keeps `/` public.

## 5. Frontend — login gate

Add `frontend/assets/login.js`, loaded before `app.js` on the `/app` shell:

```html
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<script src="/assets/login.js"></script>
```

```javascript
const SUPABASE_URL = "__SUPABASE_URL__";
const SUPABASE_ANON_KEY = "__SUPABASE_ANON_KEY__";
const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function requireSession() {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) {
    renderLoginForm();
    return null;
  }
  return session;
}

function renderLoginForm() {
  document.body.innerHTML = `
    <div style="max-width:340px;margin:15vh auto;font-family:sans-serif;">
      <h2>JETTY™</h2>
      <input id="email" placeholder="Email" style="width:100%;margin-bottom:8px;padding:10px;">
      <input id="password" type="password" placeholder="Password" style="width:100%;margin-bottom:8px;padding:10px;">
      <button id="signIn" style="width:100%;padding:10px;margin-bottom:6px;">Sign in</button>
      <button id="signUp" style="width:100%;padding:10px;">Create account</button>
      <p id="err" style="color:#e85d8f;font-size:13px;"></p>
    </div>`;
  document.getElementById('signIn').onclick = async () => {
    const { error } = await supabase.auth.signInWithPassword({
      email: document.getElementById('email').value,
      password: document.getElementById('password').value,
    });
    if (error) document.getElementById('err').textContent = error.message;
    else location.reload();
  };
  document.getElementById('signUp').onclick = async () => {
    const { error } = await supabase.auth.signUp({
      email: document.getElementById('email').value,
      password: document.getElementById('password').value,
    });
    if (error) document.getElementById('err').textContent = error.message;
    else document.getElementById('err').textContent = "Check your email to confirm, then sign in.";
  };
}

requireSession().then(session => {
  if (session) window.JETTY_ACCESS_TOKEN = session.access_token;
});
```

In `app.js`, wherever it calls `/api/*`, add:

```javascript
headers: { Authorization: `Bearer ${window.JETTY_ACCESS_TOKEN}` }
```

## 6. Deploy

- **Vercel**: add `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` as environment variables in the project settings, then redeploy.
- **Hostinger VPS**: add the same three to `.env`, `docker compose up --build -d`.

## What this gets you

- Anyone with the URL can create an account, but every session needs a real password.
- You can revoke the previous unrestricted user in Supabase: Authentication → Users → delete or ban their row.
- `/` marketing page stays public. `/app` and its API are gated.

## What is not done by this doc

This doc is a drop-in spec. It is not proof that auth is live until the actual repo routes, fetch calls, environment variables, and live deployment are verified.

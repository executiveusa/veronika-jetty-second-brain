"""Jetty V6 — the TOOL ARMORY bay.

Gives Jetty first-class tools: a registry of official remote MCP servers (Canva, Notion,
Linear, GitHub…), an OAuth 2.1 client (discovery + dynamic client registration + PKCE +
refresh) so ANY spec-compliant server connects with zero per-app code, a paste-a-token path
for the rest, auto-detection of the MCPs already attached to Claude Code (the "agent shelf"),
search over the official MCP registry, and a CONFIRM-GATED install flow ("find me a tool for
X" → "do it"). Connected tools ride the Anthropic MCP connector (mcp_servers +
mcp_toolset, beta mcp-client-2025-11-20) inside the fast conversational brain.

Plug-in bay contract (same as missions.py): server.py soft-imports this module, routes
/tools* + /api/tools + /oauth/callback through handle(), and calls init() at boot. A missing
or broken tools.py can never hurt the core viewer/server. State lives in jetty-tools.json
(gitignored — it holds OAuth tokens; never ship it).
"""

import base64, hashlib, json, os, re, secrets, subprocess, threading, time, urllib.parse, urllib.request

CTX = {}                      # init() fills: cfg, root, port, raise_card, jpersona
STATE_LOCK = threading.Lock()
STATE = {"custom": [], "conn": {}, "disabled": [], "hidden": []}
PENDING_AUTH = {}             # oauth state nonce -> {tool_id, verifier, token_endpoint, client_id, resource, ts}
PENDING_INSTALL = {}          # pending_id -> candidate dict (package installs wait for "do it")

MCP_BETA = "mcp-client-2025-11-20"
REGISTRY_API = "https://registry.modelcontextprotocol.io/v0/servers"

# ---------- the curated shelf: official remote MCP servers (public, hosted by the vendor) ----------
# auth: oauth = standard MCP OAuth (discovery+DCR+PKCE) · token = paste a key/PAT ·
#       url = paste a personal server URL (aggregators) · google = needs a Google OAuth client (phase 2) · none = open
CURATED = [
    # top row (user-ordered): Canva · Zapier · Notion
    {"id": "canva",      "name": "Canva",           "url": "https://mcp.canva.com/mcp",                "auth": "oauth",  "slug": "canva",          "blurb": "generate designs, autofill templates, export PDF/PNG/MP4"},
    {"id": "zapier",     "name": "Zapier",          "url": "",                                          "auth": "url",    "slug": "zapier",         "blurb": "the wildcard — paste your personal MCP URL from mcp.zapier.com for 9,000+ apps", "hint": "https://mcp.zapier.com/api/mcp/…"},
    {"id": "notion",     "name": "Notion",          "url": "https://mcp.notion.com/mcp",               "auth": "oauth",  "slug": "notion",         "blurb": "search, read and create pages and databases"},
    # one-click OAuth shelf (every URL verified live — same click-and-approve flow as Canva/Notion)
    {"id": "figma",      "name": "Figma",           "url": "https://mcp.figma.com/mcp",                "auth": "oauth",  "slug": "figma",          "blurb": "read designs, components, styles"},
    {"id": "webflow",    "name": "Webflow",         "url": "https://mcp.webflow.com/sse",              "auth": "oauth",  "slug": "webflow",        "blurb": "sites, CMS items, publishing"},
    {"id": "wix",        "name": "Wix",             "url": "https://mcp.wix.com/sse",                  "auth": "oauth",  "slug": "wix",            "blurb": "site content, bookings, store"},
    {"id": "airtable",   "name": "Airtable",        "url": "https://mcp.airtable.com/mcp",             "auth": "oauth",  "slug": "airtable",       "blurb": "bases, tables, records"},
    {"id": "monday",     "name": "monday.com",      "url": "https://mcp.monday.com/sse",               "auth": "oauth",  "slug": "mondaydotcom",   "blurb": "boards, items, workflows"},
    {"id": "clickup",    "name": "ClickUp",         "url": "https://mcp.clickup.com/mcp",              "auth": "oauth",  "slug": "clickup",        "blurb": "tasks, docs, goals"},
    {"id": "dropbox",    "name": "Dropbox",         "url": "https://mcp.dropbox.com/mcp",              "auth": "oauth",  "slug": "dropbox",        "blurb": "files, folders, sharing"},
    {"id": "vercel",     "name": "Vercel",          "url": "https://mcp.vercel.com/",                  "auth": "oauth",  "slug": "vercel",         "blurb": "deployments, projects, logs"},
    {"id": "netlify",    "name": "Netlify",         "url": "https://netlify-mcp.netlify.app/mcp",      "auth": "oauth",  "slug": "netlify",        "blurb": "deploys, sites, forms"},
    {"id": "cloudinary", "name": "Cloudinary",      "url": "https://asset-management.mcp.cloudinary.com/sse", "auth": "oauth", "slug": "cloudinary", "blurb": "media assets — upload, transform, search"},
    {"id": "linear",     "name": "Linear",          "url": "https://mcp.linear.app/mcp",               "auth": "oauth",  "slug": "linear",         "blurb": "issues, projects, cycles"},
    {"id": "paypal",     "name": "PayPal",          "url": "https://mcp.paypal.com/mcp",               "auth": "oauth",  "slug": "paypal",         "blurb": "invoices, orders, payouts"},
    {"id": "square",     "name": "Square",          "url": "https://mcp.squareup.com/sse",             "auth": "oauth",  "slug": "square",         "blurb": "payments, customers, catalog"},
    {"id": "github",     "name": "GitHub",          "url": "https://api.githubcopilot.com/mcp/",       "auth": "token",  "slug": "github",         "blurb": "repos, issues, PRs — paste a personal access token", "hint": "GitHub PAT (github.com/settings/tokens)"},
    {"id": "stripe",     "name": "Stripe",          "url": "https://mcp.stripe.com",                   "auth": "token",  "slug": "stripe",         "blurb": "customers, payments, products — paste a restricted key", "hint": "Stripe restricted key (rk_…)"},
    {"id": "huggingface","name": "Hugging Face",    "url": "https://huggingface.co/mcp",               "auth": "token",  "slug": "huggingface",    "blurb": "models, datasets, spaces", "hint": "HF token (hf_…)"},
    {"id": "cfdocs",     "name": "Cloudflare docs", "url": "https://docs.mcp.cloudflare.com/sse",      "auth": "none",   "slug": "cloudflare",     "blurb": "search Cloudflare documentation"},
    {"id": "gmail",      "name": "Gmail",           "url": "https://gmailmcp.googleapis.com/mcp/v1",   "auth": "google", "slug": "gmail",          "blurb": "search mail, read threads, write drafts",
     "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.compose"},
    {"id": "gcal",       "name": "Google Calendar", "url": "https://calendarmcp.googleapis.com/mcp/v1","auth": "google", "slug": "googlecalendar", "blurb": "calendars, events, free/busy",
     "scope": ("https://www.googleapis.com/auth/calendar.calendarlist.readonly "
               "https://www.googleapis.com/auth/calendar.events.freebusy "
               "https://www.googleapis.com/auth/calendar.events.readonly")},
]

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"

def google_creds():
    g = (CTX.get("cfg") or {}).get("google") or {}
    cid, sec = (g.get("client_id") or "").strip(), (g.get("client_secret") or "").strip()
    if not cid or cid.startswith("PUT-") or not sec or sec.startswith("PUT-"):
        return None, None
    return cid, sec

GOOGLE_SETUP_MSG = ("Gmail and Calendar use YOUR OWN free Google OAuth client (one-time, ~15 min): "
                    "console.cloud.google.com → APIs & Services → OAuth consent screen (External, add yourself "
                    "as a test user, add the Gmail/Calendar scopes) → Credentials → Create OAuth client ID → "
                    "Web application → add redirect URI http://127.0.0.1:4719/oauth/callback → paste the "
                    "client_id + client_secret into config.json under \"google\" and restart the server.")

def start_google(tool):
    """Google OAuth (bring-your-own client). Returns ({auth_url}, err-or-setup-dict)."""
    cid, sec = google_creds()
    if not cid:
        return None, {"setup": True, "msg": GOOGLE_SETUP_MSG}
    verifier, challenge = pkce_pair()
    state = secrets.token_hex(16)
    PENDING_AUTH[state] = {"kind": "google", "tool_id": tool["id"], "verifier": verifier,
                           "client_id": cid, "token_endpoint": GOOGLE_TOKEN, "resource": "", "ts": time.time()}
    q = {"response_type": "code", "client_id": cid, "redirect_uri": _redirects()[0],
         "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
         "scope": tool.get("scope", ""), "access_type": "offline", "prompt": "consent"}
    return {"auth_url": GOOGLE_AUTH + "?" + urllib.parse.urlencode(q)}, None

# ---------- state ----------

def _state_file():
    return os.path.join(CTX.get("root", "."), "jetty-tools.json")

def load_state():
    global STATE
    try:
        with open(_state_file()) as f:
            s = json.load(f)
        STATE = {"custom": s.get("custom") or [], "conn": s.get("conn") or {},
                 "disabled": s.get("disabled") or [], "hidden": s.get("hidden") or []}
    except Exception:
        pass

def save_state():
    with STATE_LOCK:
        tmp = _state_file() + ".tmp"
        with open(tmp, "w") as f:
            json.dump(STATE, f, indent=1)
        os.replace(tmp, _state_file())

def registry():
    """Curated + user-installed entries. Custom entries override curated on id collision."""
    seen, out = set(), []
    for t in (STATE["custom"] + CURATED):
        if t["id"] in seen: continue
        seen.add(t["id"]); out.append(t)
    return out

def find_tool(tid):
    for t in registry():
        if t["id"] == tid: return t
    return None

# ---------- tiny HTTP ----------

def http_json(url, data=None, headers=None, method=None, timeout=20):
    """Returns (status, parsed-json-or-None, raw headers dict). Never raises."""
    h = {"accept": "application/json", "user-agent": "jetty-brain-studio/1.0"}
    h.update(headers or {})
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        h.setdefault("content-type", "application/json")
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try: parsed = json.loads(raw) if raw else None
            except Exception: parsed = None
            return r.status, parsed, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = b""
        try: raw = e.read()
        except Exception: pass
        try: parsed = json.loads(raw) if raw else None
        except Exception: parsed = None
        return e.code, parsed, dict(e.headers or {})
    except Exception as e:
        return 0, {"error": str(e)}, {}

# ---------- OAuth 2.1 for MCP: discovery → DCR → PKCE → tokens ----------

def pkce_pair():
    v = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    c = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    return v, c

def well_known_urls(base_url, kind):
    """RFC 8414 path-aware well-known candidates for a server URL, most specific first."""
    u = urllib.parse.urlparse(base_url)
    origin = f"{u.scheme}://{u.netloc}"
    path = u.path.rstrip("/")
    urls = []
    if path:
        urls.append(f"{origin}/.well-known/{kind}{path}")
    urls.append(f"{origin}/.well-known/{kind}")
    return urls

def _www_auth_resource(headers):
    """Pull resource_metadata="…" out of a WWW-Authenticate header, if present."""
    wa = headers.get("WWW-Authenticate") or headers.get("www-authenticate") or ""
    m = re.search(r'resource_metadata="([^"]+)"', wa)
    return m.group(1) if m else None

def discover(server_url):
    """Find the authorization server for an MCP server. Returns (meta dict, err).
    meta: {authorization_endpoint, token_endpoint, registration_endpoint?, resource}"""
    # 1) poke the server unauthenticated — a spec server 401s with resource metadata
    st, _, hdrs = http_json(server_url, data={"jsonrpc": "2.0", "id": 0, "method": "initialize",
                                              "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                         "clientInfo": {"name": "jetty", "version": "1.0"}}},
                            headers={"accept": "application/json, text/event-stream"})
    rm_urls = []
    rm = _www_auth_resource(hdrs)
    if rm: rm_urls.append(rm)
    rm_urls += well_known_urls(server_url, "oauth-protected-resource")
    auth_servers = []
    for u in rm_urls:
        st2, meta, _ = http_json(u)
        if st2 == 200 and isinstance(meta, dict) and meta.get("authorization_servers"):
            auth_servers = meta["authorization_servers"]; break
    if not auth_servers:                      # legacy MCP servers: the MCP origin IS the auth server
        pu = urllib.parse.urlparse(server_url)
        auth_servers = [f"{pu.scheme}://{pu.netloc}"]
    last = "no authorization server metadata found"
    for asrv in auth_servers:
        cands = (well_known_urls(asrv, "oauth-authorization-server") +
                 well_known_urls(asrv, "openid-configuration"))
        for u in cands:
            st3, m, _ = http_json(u)
            if st3 == 200 and isinstance(m, dict) and m.get("authorization_endpoint") and m.get("token_endpoint"):
                m["resource"] = server_url
                return m, None
            last = f"{u} -> {st3}"
    return None, f"couldn't discover OAuth metadata ({last})"

def dcr(meta, redirects):
    """Dynamic client registration (public client). Returns (client_id, err)."""
    reg = meta.get("registration_endpoint")
    if not reg:
        return None, "server doesn't support dynamic client registration"
    st, resp, _ = http_json(reg, data={
        "client_name": "JETTY — Second Brain", "redirect_uris": redirects,
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
        "token_endpoint_auth_method": "none"})
    if st in (200, 201) and isinstance(resp, dict) and resp.get("client_id"):
        return resp["client_id"], None
    return None, f"client registration failed ({st}): {json.dumps(resp)[:200]}"

def _redirects():
    port = CTX.get("port", 4719)
    return [f"http://127.0.0.1:{port}/oauth/callback", f"http://localhost:{port}/oauth/callback"]

def start_connect(tool):
    """Kick off the OAuth dance. Returns ({auth_url}, err)."""
    meta, err = discover(tool["url"])
    if err: return None, err
    client_id, err = dcr(meta, _redirects())
    if err: return None, err
    verifier, challenge = pkce_pair()
    state = secrets.token_hex(16)
    PENDING_AUTH[state] = {"tool_id": tool["id"], "verifier": verifier, "client_id": client_id,
                           "token_endpoint": meta["token_endpoint"], "resource": meta["resource"],
                           "ts": time.time()}
    for k in [k for k, v in PENDING_AUTH.items() if time.time() - v["ts"] > 600]:
        PENDING_AUTH.pop(k, None)
    q = {"response_type": "code", "client_id": client_id, "redirect_uri": _redirects()[0],
         "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
         "resource": meta["resource"]}
    scopes = meta.get("scopes_supported")
    if scopes: q["scope"] = " ".join(scopes[:12])
    return {"auth_url": meta["authorization_endpoint"] + "?" + urllib.parse.urlencode(q)}, None

def finish_callback(state, code):
    """Exchange the code, store tokens. Returns (tool name, err)."""
    pend = PENDING_AUTH.pop(state, None)
    if not pend: return None, "unknown or expired authorization state"
    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": _redirects()[0],
            "client_id": pend["client_id"], "code_verifier": pend["verifier"]}
    if pend.get("kind") == "google":
        _cid, sec = google_creds()
        form["client_secret"] = sec or ""
    else:
        form["resource"] = pend["resource"]
    st, tok, _ = http_json(pend["token_endpoint"], data=urllib.parse.urlencode(form).encode(),
                           headers={"content-type": "application/x-www-form-urlencoded"})
    if st != 200 or not isinstance(tok, dict) or not tok.get("access_token"):
        return None, f"token exchange failed ({st}): {json.dumps(tok)[:200]}"
    STATE["conn"][pend["tool_id"]] = {
        "status": "connected", "kind": pend.get("kind") or "oauth", "access": tok["access_token"],
        "refresh": tok.get("refresh_token", ""), "client_id": pend["client_id"],
        "token_endpoint": pend["token_endpoint"], "resource": pend["resource"],
        "expires_at": time.time() + int(tok.get("expires_in") or 3600), "since": int(time.time())}
    save_state()
    t = find_tool(pend["tool_id"])
    return (t["name"] if t else pend["tool_id"]), None

def access_token(tid):
    """Current bearer for a connected tool, refreshing when < 60s left. '' = authless."""
    c = STATE["conn"].get(tid)
    if not c: return None
    if c.get("kind") in ("token", "url", "none"):
        return c.get("access", "")
    if time.time() < c.get("expires_at", 0) - 60:
        return c.get("access")
    if not c.get("refresh"):
        c["status"] = "attention"; save_state(); return None
    fields = {"grant_type": "refresh_token", "refresh_token": c["refresh"], "client_id": c["client_id"]}
    if c.get("kind") == "google":
        _cid, sec = google_creds()
        fields["client_secret"] = sec or ""
    else:
        fields["resource"] = c.get("resource", "")
    form = urllib.parse.urlencode(fields).encode()
    st, tok, _ = http_json(c["token_endpoint"], data=form,
                           headers={"content-type": "application/x-www-form-urlencoded"})
    if st == 200 and isinstance(tok, dict) and tok.get("access_token"):
        c["access"] = tok["access_token"]
        c["refresh"] = tok.get("refresh_token", c["refresh"])
        c["expires_at"] = time.time() + int(tok.get("expires_in") or 3600)
        c["status"] = "connected"; save_state()
        return c["access"]
    c["status"] = "attention"; save_state()
    return None

# ---------- the agent shelf: MCPs already attached to Claude Code ----------

def cc_mcps():
    """Names of MCP servers configured in Claude Code (user + this project). Read-only."""
    found = {}
    def take(d, scope):
        for name, spec in (d or {}).items():
            if name not in found:
                kind = "http" if (spec or {}).get("url") or (spec or {}).get("type") in ("http", "sse") else "stdio"
                found[name] = {"name": name, "kind": kind, "scope": scope}
    try:
        with open(os.path.expanduser("~/.claude.json")) as f:
            cc = json.load(f)
        take(cc.get("mcpServers"), "user")
        for proj in (cc.get("projects") or {}).values():
            take((proj or {}).get("mcpServers"), "project")
    except Exception:
        pass
    try:
        with open(os.path.join(os.path.expanduser("~/Documents/Claude Code"), ".mcp.json")) as f:
            take((json.load(f) or {}).get("mcpServers"), "project")
    except Exception:
        pass
    return sorted(found.values(), key=lambda x: x["name"].lower())

# ---------- discovery: the official MCP registry ----------

def search_registry(q, limit=8):
    """Search registry.modelcontextprotocol.io. Returns (candidates, err)."""
    st, data, _ = http_json(REGISTRY_API + "?" + urllib.parse.urlencode({"search": q, "limit": limit}))
    if st != 200 or not isinstance(data, dict):
        return None, f"registry search failed ({st})"
    out = []
    for row in (data.get("servers") or []):
        s = row.get("server") if isinstance(row.get("server"), dict) else row
        name = s.get("name") or ""
        cand = {"name": name.split("/")[-1] or name, "full_name": name,
                "description": (s.get("description") or "")[:220], "url": "", "package": "", "runner": ""}
        for r in (s.get("remotes") or []):
            if r.get("url"):
                cand["url"] = r["url"]; break
        for p in (s.get("packages") or []):
            reg = (p.get("registry_name") or p.get("registryName") or p.get("registry_type") or "").lower()
            ident = p.get("identifier") or p.get("name") or ""
            if reg in ("npm", "pypi") and ident:
                cand["package"], cand["runner"] = ident, ("npx" if reg == "npm" else "uvx")
                break
        if cand["url"] or cand["package"]:
            out.append(cand)
    return out, None

def stage_install(cand):
    """Queue a candidate. Remote URLs install instantly (just a registry entry — connecting is
    a separate, visible step). Package installs (npx/uvx into Claude Code) wait for 'do it'."""
    if cand.get("url"):
        tid = re.sub(r"[^a-z0-9]+", "-", (cand.get("name") or "tool").lower()).strip("-")[:24] or "tool"
        if find_tool(tid): tid += "-" + secrets.token_hex(2)
        entry = {"id": tid, "name": cand.get("name") or tid, "url": cand["url"], "auth": "oauth",
                 "slug": "", "blurb": (cand.get("description") or "")[:120], "installed": int(time.time())}
        STATE["custom"].insert(0, entry); save_state()
        return {"installed": True, "id": tid, "name": entry["name"],
                "say": f"{entry['name']} is on the shelf, sir — click it (or say connect {entry['name']}) to sign in."}
    if cand.get("package"):
        pid = secrets.token_hex(6)
        PENDING_INSTALL[pid] = cand
        return {"pending_id": pid, "name": cand.get("name"),
                "say": (f"{cand.get('name')} installs into Claude Code as a local package "
                        f"({cand['runner']} {cand['package']}). Say 'do it' and I'll install it, sir.")}
    return {"error": "candidate has neither a remote URL nor a package"}

def confirm_install(pid):
    """'do it' → claude mcp add (user scope). The ONLY place tools.py touches Claude Code config."""
    cand = PENDING_INSTALL.pop(pid, None)
    if not cand: return None, "nothing pending by that id, sir"
    name = re.sub(r"[^a-zA-Z0-9_-]+", "-", cand.get("name") or "tool")[:32]
    cmd = ["claude", "mcp", "add", "-s", "user", name, "--", cand["runner"], "-y", cand["package"]]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except FileNotFoundError:
        return None, "claude CLI not found on PATH"
    except subprocess.TimeoutExpired:
        return None, "install timed out"
    if r.returncode != 0:
        return None, (r.stderr or r.stdout or "install failed").strip()[:300]
    return {"installed": True, "name": name, "shelf": "agent",
            "say": f"{name} is installed, sir — it lives on the Claude Code shelf, ready for missions."}, None

# ---------- the fast brain: Anthropic MCP connector ----------

def connected_servers():
    """[{name, url, token}] for every connected+enabled direct tool with a live token."""
    out = []
    for t in registry():
        c = STATE["conn"].get(t["id"])
        if not c or c.get("status") != "connected" or t["id"] in STATE["disabled"]: continue
        url = c.get("url_override") or t.get("url")
        if not url: continue
        tok = access_token(t["id"])
        if tok is None and c.get("kind") == "oauth": continue
        out.append({"name": re.sub(r"[^a-zA-Z0-9_-]", "-", t["id"]), "url": url, "token": tok or ""})
    return out

def chat(msgs, system, max_iters=4):
    """One tool-enabled turn on the Claude brain. Returns ({answer, tools_used}, err)."""
    cfgm = (CTX.get("cfg") or {}).get("model") or {}
    key = cfgm.get("api_key", "")
    base = (cfgm.get("base_url") or "").strip().rstrip("/")
    provider = (cfgm.get("provider") or "anthropic").strip().lower()
    if provider != "anthropic" or (base and "api.anthropic.com" not in base):
        return None, "tools run on the Claude brain — config.json's model block isn't Anthropic"
    if not key or key.startswith("PUT-"):
        return None, "model not configured — add your API key to config.json"
    servers = connected_servers()
    if not servers:
        return None, "no tools connected yet, sir — open the toolbox and connect one"
    mcp = [{"type": "url", "url": s["url"], "name": s["name"],
            **({"authorization_token": s["token"]} if s["token"] else {})} for s in servers]
    toolsets = [{"type": "mcp_toolset", "mcp_server_name": s["name"]} for s in servers]
    # tool EXECUTOR runs a fast tier by default — the takeover-speed-tier pattern: the chat brain
    # (Opus 4.8) made a 30s calendar check take 80s+. Override via config.json {"tools":{"model":…}}.
    tmodel = ((CTX.get("cfg") or {}).get("tools") or {}).get("model") or "claude-sonnet-5"
    body = {"model": tmodel, "max_tokens": 1500, "system": system,
            "messages": list(msgs), "mcp_servers": mcp, "tools": toolsets}
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01",
               "anthropic-beta": MCP_BETA, "content-type": "application/json"}
    used, calls, errs, data = set(), [], 0, {}
    for _ in range(max_iters):
        # 100s per iteration, NOT 150: the client gives up at 160s, so a slow spell must fail
        # HERE with margin left to speak the graceful line (seen live 2026-07-14: a 150s stall
        # outlived the client and read as a dead hang)
        st, data, _h = http_json("https://api.anthropic.com/v1/messages", data=body, headers=headers, timeout=100)
        if st != 200 or not isinstance(data, dict):
            # error bodies arrive as dicts, strings, or raw text (seen live 2026-07-13 when Zapier
            # ran out of tasks) — never assume a shape, or the handler itself crashes
            e = data.get("error") if isinstance(data, dict) else data
            emsg = (e.get("message") if isinstance(e, dict) else e) or f"HTTP {st}"
            return None, f"tool call failed: {str(emsg)[:240]}"
        for b in data.get("content", []):
            bt = b.get("type")
            if bt in ("mcp_tool_use", "server_tool_use"):
                used.add((b.get("server_name") or b.get("name") or "tool").replace("_", " "))
                n = b.get("name") or ""
                if n and n not in calls: calls.append(n)          # receipts: which tools ACTUALLY ran
            elif bt == "mcp_tool_result" and b.get("is_error"):
                errs += 1                                          # failed calls must be visible, never smoothed over
        if data.get("stop_reason") != "pause_turn": break
        body["messages"] = body["messages"] + [{"role": "assistant", "content": data.get("content", [])}]
    txt = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    return {"answer": txt or "(the tools came back empty, sir)", "tools_used": sorted(used),
            "tool_calls": calls, "tool_errors": errs}, None

# ---------- brand logos: server-side proxy + disk cache (client CDNs proved flaky) ----------

LOGO_MEM = {}

# simple-icons is monochrome by design — these are the official brand hexes we paint them with
BRAND = {"canva": "00C4CC", "notion": "FFFFFF", "linear": "5E6AD2", "asana": "F06A6A",
         "jira": "0052CC", "intercom": "286EFA", "paypal": "003087", "square": "3E4348",
         "sentry": "362D59", "github": "E8EAED", "stripe": "635BFF", "huggingface": "FFD21E",
         "cloudflare": "F38020", "zapier": "FF4F00", "gmail": "EA4335", "googlecalendar": "4285F4",
         "figma": "F24E1E", "webflow": "4353FF", "wix": "8A9BFF", "airtable": "18BFFF",
         "mondaydotcom": "FF3D57", "clickup": "7B68EE", "dropbox": "0061FF",
         "vercel": "EDEDED", "netlify": "00C7B7", "cloudinary": "3448C5"}

def logo_bytes(slug):
    """Brand-colored SVG for a simple-icons slug, cached in memory + on disk. None = no logo.
    cdn.simple-icons.org doesn't resolve on this network — jsDelivr/unpkg serve the same
    package (monochrome), and we inject the brand fill ourselves."""
    if not re.fullmatch(r"[a-z0-9-]{1,40}", slug or ""): return None
    if slug in LOGO_MEM: return LOGO_MEM[slug]
    cache_dir = os.path.join(CTX.get("root", "."), ".logo-cache")
    fp = os.path.join(cache_dir, slug + ".svg")
    try:
        with open(fp, "rb") as f:
            LOGO_MEM[slug] = f.read(); return LOGO_MEM[slug]
    except Exception:
        pass
    for base in ("https://cdn.jsdelivr.net/npm/simple-icons@15/icons/",
                 "https://unpkg.com/simple-icons@15/icons/"):
        try:
            req = urllib.request.Request(base + slug + ".svg",
                                         headers={"user-agent": "jetty-brain-studio/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
            if data[:200].lstrip()[:4] != b"<svg": continue
            fill = BRAND.get(slug, "5f6368")
            data = data.replace(b"<svg ", b'<svg fill="#' + fill.encode() + b'" ', 1)
            os.makedirs(cache_dir, exist_ok=True)
            with open(fp, "wb") as f: f.write(data)
            LOGO_MEM[slug] = data
            return data
        except Exception:
            continue
    return None

# ---------- HTTP surface ----------

def _tiles():
    direct = []
    hidden = set(STATE.get("hidden") or [])
    g_ready = google_creds()[0] is not None
    for t in registry():
        if t["id"] in hidden:                       # user hid this tile — off the shelf until restored
            continue
        c = STATE["conn"].get(t["id"]) or {}
        status = c.get("status") or ("setup" if (t["auth"] == "google" and not g_ready) else "available")
        host = re.sub(r"^https?://([^/]+).*", r"\1", (c.get("url_override") or t.get("url") or "")) or "—"
        direct.append({"id": t["id"], "name": t["name"], "slug": t.get("slug", ""), "auth": t["auth"],
                       "blurb": t.get("blurb", ""), "hint": t.get("hint", ""), "status": status, "host": host,
                       "enabled": t["id"] not in STATE["disabled"], "custom": bool(t.get("installed") or t.get("custom"))})
    return {"direct": direct, "agent": cc_mcps(), "hidden": len(hidden),
            "connected": sum(1 for d in direct if d["status"] == "connected" and d["enabled"])}

def handle(handler, method, raw_path, payload):
    """True = handled. server.py routes /api/tools, /tools*, /tool_chat-adjacent and /oauth/callback here."""
    path = raw_path.split("?")[0]
    p = payload or {}

    if method == "GET" and path == "/api/tools":
        handler._json(_tiles()); return True

    if method == "GET" and path.startswith("/tool_logo/"):
        data = logo_bytes(path.rsplit("/", 1)[-1])
        if not data:
            handler.send_response(404); handler.end_headers(); return True
        handler.send_response(200)
        handler.send_header("Content-Type", "image/svg+xml")
        handler.send_header("Cache-Control", "max-age=86400")      # logos may cache — they never change
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers(); handler.wfile.write(data)
        return True

    if method == "GET" and path == "/oauth/callback":
        q = urllib.parse.parse_qs(urllib.parse.urlparse(raw_path).query)
        state = (q.get("state") or [""])[0]; code = (q.get("code") or [""])[0]
        err = (q.get("error") or [""])[0]
        name, xerr = (None, err or "missing code") if (err or not code) else finish_callback(state, code)
        ok = name is not None
        if ok and CTX.get("raise_card"):
            try: CTX["raise_card"]("notify", f"🔌 {name} connected", f"{name} is online and available to Jetty.", source="tools", speak=False)
            except Exception: pass
        page = ("<html><body style='background:#0b1210;color:#e8eceb;font-family:monospace;display:flex;"
                "align-items:center;justify-content:center;height:100vh'><div style='text-align:center'>"
                + (f"<h2 style='color:#34d399'>✓ {name} connected</h2><p>You can close this tab — Jetty has it from here.</p>"
                   if ok else f"<h2 style='color:#fb7185'>✗ connection failed</h2><p>{(xerr or '')[:200]}</p>")
                + "</div></body></html>").encode()
        handler.send_response(200); handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Length", str(len(page))); handler.end_headers(); handler.wfile.write(page)
        return True

    if method != "POST" or not path.startswith("/tools"):
        return False

    if path == "/tools_custom":            # add YOUR OWN tool: name + MCP URL → probed, then shelved
        name = (p.get("name") or "").strip()[:40]
        url = (p.get("url") or "").strip()
        if not name or not url.startswith("https://"):
            handler._json({"error": "need a name and an https:// MCP URL"}, 400); return True
        tid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "custom"
        if any(t["id"] == tid for t in registry()):
            handler._json({"error": f"'{name}' is already on the shelf, sir"}, 409); return True
        st, _d, _h = http_json(url, data={"jsonrpc": "2.0", "id": 0, "method": "initialize",
                                          "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                     "clientInfo": {"name": "jetty", "version": "1.0"}}},
                               headers={"accept": "application/json, text/event-stream"})
        if st in (200, 202):
            auth = "none"                  # open server — connect is instant
        elif st in (401, 403):
            auth = "oauth"                 # gated — the one-OAuth-engine handles it like Canva/Notion
        else:
            handler._json({"error": f"that URL didn't answer as an MCP server (HTTP {st})"}, 502); return True
        STATE["custom"].append({"id": tid, "name": name, "url": url, "auth": auth,
                                "slug": "", "blurb": "custom MCP server", "custom": True})
        save_state()
        handler._json({"added": True, "id": tid, "name": name, "auth": auth}); return True

    if path == "/tools_custom_remove":     # take a custom tool off the shelf (and forget its tokens)
        tid = (p.get("id") or "").strip()
        before = len(STATE["custom"])
        STATE["custom"] = [t for t in STATE["custom"] if t["id"] != tid]
        STATE["conn"].pop(tid, None)
        save_state()
        handler._json({"removed": len(STATE["custom"]) < before}); return True

    if path == "/tools_hide":              # remove a CURATED tile from the shelf (reversible — "show hidden")
        tid = (p.get("id") or "").strip()
        STATE["conn"].pop(tid, None)       # hiding also forgets any half-done connection
        if tid not in STATE.setdefault("hidden", []):
            STATE["hidden"].append(tid)
        save_state(); handler._json({"hidden": True}); return True

    if path == "/tools_unhide":            # bring every hidden curated tile back
        STATE["hidden"] = []
        save_state(); handler._json({"restored": True}); return True

    if path == "/tools_connect":
        t = find_tool((p.get("id") or "").strip())
        if not t: handler._json({"error": "unknown tool"}, 404); return True
        if t["auth"] == "oauth":
            res, err = start_connect(t)
            if err:                                   # some registry finds are open servers — probe before failing
                st, _d, _h = http_json(t["url"], data={"jsonrpc": "2.0", "id": 0, "method": "initialize",
                                                       "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                                  "clientInfo": {"name": "jetty", "version": "1.0"}}},
                                       headers={"accept": "application/json, text/event-stream"})
                if st == 200:
                    STATE["conn"][t["id"]] = {"status": "connected", "kind": "none", "access": "", "since": int(time.time())}
                    save_state(); handler._json({"connected": True, "name": t["name"]}); return True
            handler._json({"error": err}, 502) if err else handler._json(res); return True
        if t["auth"] == "token":
            tok = (p.get("token") or "").strip()
            if not tok: handler._json({"error": "paste a token first", "hint": t.get("hint", "")}, 400); return True
            STATE["conn"][t["id"]] = {"status": "connected", "kind": "token", "access": tok, "since": int(time.time())}
            save_state(); handler._json({"connected": True, "name": t["name"]}); return True
        if t["auth"] == "url":
            url = (p.get("url") or "").strip()
            if not url.startswith("https://"): handler._json({"error": "paste your personal https:// MCP URL", "hint": t.get("hint", "")}, 400); return True
            # probe BEFORE marking connected — a mistyped URL should fail HERE, not mid-conversation
            st, _d, _h = http_json(url, data={"jsonrpc": "2.0", "id": 0, "method": "initialize",
                                              "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                         "clientInfo": {"name": "jetty", "version": "1.0"}}},
                                   headers={"accept": "application/json, text/event-stream"})
            if st not in (200, 202):
                handler._json({"error": f"that URL didn't answer as an MCP server (HTTP {st}) — "
                                        "re-copy it from the provider (e.g. mcp.zapier.com)"}, 502); return True
            STATE["conn"][t["id"]] = {"status": "connected", "kind": "url", "access": "", "url_override": url, "since": int(time.time())}
            save_state(); handler._json({"connected": True, "name": t["name"]}); return True
        if t["auth"] == "none":
            STATE["conn"][t["id"]] = {"status": "connected", "kind": "none", "access": "", "since": int(time.time())}
            save_state(); handler._json({"connected": True, "name": t["name"]}); return True
        if t["auth"] == "google":
            res, err = start_google(t)
            if err: handler._json(err if isinstance(err, dict) else {"error": err}, 200 if isinstance(err, dict) else 502)
            else: handler._json(res)
            return True
        handler._json({"error": "unknown auth kind"}, 400); return True

    if path == "/tools_disconnect":
        tid = (p.get("id") or "").strip()
        STATE["conn"].pop(tid, None)
        STATE["custom"] = [c for c in STATE["custom"] if c["id"] != tid or not p.get("remove")]
        save_state(); handler._json({"ok": True}); return True

    if path == "/tools_toggle":
        tid = (p.get("id") or "").strip()
        if tid in STATE["disabled"]: STATE["disabled"].remove(tid)
        else: STATE["disabled"].append(tid)
        save_state(); handler._json({"enabled": tid not in STATE["disabled"]}); return True

    if path == "/tools_search":
        res, err = search_registry((p.get("q") or "").strip() or "tools")
        handler._json({"error": err}, 502) if err else handler._json({"results": res}); return True

    if path == "/tools_install":
        handler._json(stage_install(p.get("candidate") or p)); return True

    if path == "/tools_install_confirm":
        res, err = confirm_install((p.get("pending_id") or "").strip())
        handler._json({"error": err}, 502) if err else handler._json(res); return True

    return False

def init(ctx):
    CTX.update(ctx or {})
    load_state()
    n = sum(1 for c in STATE["conn"].values() if c.get("status") == "connected")
    print(f"[tools] armory online — {len(registry())} on the shelf, {n} connected, {len(cc_mcps())} via Claude Code")

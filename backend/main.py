from __future__ import annotations

import json, os, re, time, math, hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT       = Path(__file__).resolve().parents[1]
NOTES_DIR  = Path(os.getenv("NOTES_DIR", ROOT / "notes")).resolve()
FRONTEND_DIR = ROOT / "frontend"
APP_NAME   = os.getenv("APP_NAME", "JETTY")
APP_REGION = os.getenv("APP_REGION", "Salt Lake City, Utah")
MODEL_PROVIDER   = os.getenv("MODEL_PROVIDER", "anthropic").lower().strip()
ANTHROPIC_MODEL  = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
OPENAI_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GROQ_MODEL       = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
DEEPSEEK_MODEL   = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
MISTRAL_MODEL    = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
HERMES_MODEL     = os.getenv("HERMES_MODEL", "openai/gpt-5.5")
SYNTHIA_GATEWAY_BASE_URL = os.getenv("SYNTHIA_GATEWAY_BASE_URL", "").rstrip("/")
SYNTHIA_GATEWAY_API_KEY  = os.getenv("SYNTHIA_GATEWAY_API_KEY", "")
SYNTHIA_GATEWAY_MODEL    = os.getenv("SYNTHIA_GATEWAY_MODEL", OPENAI_MODEL)
MAX_HISTORY      = int(os.getenv("MAX_HISTORY", "10"))
MAX_TOP_NOTES    = int(os.getenv("MAX_TOP_NOTES", "6"))
PUBLIC_ORIGIN    = os.getenv("PUBLIC_ORIGIN", "*")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "45"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", PUBLIC_ORIGIN).split(",")
    if origin.strip()
]
if not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = ["*"]

# Load SOUL from ops/hermes/SOUL.md
_soul_path = ROOT / "ops" / "hermes" / "SOUL.md"
OPERATOR_SOUL = _soul_path.read_text(encoding="utf-8") if _soul_path.exists() else ""

app = FastAPI(title=APP_NAME, version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in ALLOWED_ORIGINS else ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field("default", max_length=96)
    voice_id: Optional[str] = Field(None, max_length=120)
    model_provider: Optional[str] = Field(None, max_length=32)  # overrides MODEL_PROVIDER env var

class RememberRequest(BaseModel):
    text: str = Field(..., min_length=8, max_length=4000)
    session_id: str = Field("default", max_length=96)

class Note(BaseModel):
    id: int; label: str; group: str; path: str
    excerpt: str; text: str; title_tokens: List[str]; tokens: List[str]

GRAPH_CACHE: Dict[str, Any] = {"nodes": [], "links": [], "notes": [], "built_at": 0}
HISTORY: Dict[str, List[Dict[str, str]]] = {}
REQUEST_LOG: Dict[str, List[float]] = {}
CHAT_LOG = (ROOT / "data" / "chat-history.jsonl").resolve()

STOPWORDS = set("a an and are as at be by for from has have i in is it its me my of on or our that the this to we with you your into about what when where who why how do does did can could should would tell give make build".split())

def safe_session_id(v: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.:-]", "_", v)[:96] or "default"

def append_chat_event(session_id: str, role: str, content: str):
    CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "session_id": safe_session_id(session_id),
        "role": role,
        "content": content,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with CHAT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def load_chat_events(session_id: Optional[str] = None) -> List[Dict[str, str]]:
    if not CHAT_LOG.exists():
        return []
    wanted = safe_session_id(session_id) if session_id else None
    events: List[Dict[str, str]] = []
    with CHAT_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if wanted and record.get("session_id") != wanted:
                continue
            events.append(record)
    return events

def list_chat_sessions() -> List[Dict[str, Any]]:
    sessions: Dict[str, Dict[str, Any]] = {}
    for record in load_chat_events():
        sid = safe_session_id(str(record.get("session_id", "default")))
        stamp = str(record.get("ts") or "")
        item = sessions.setdefault(
            sid,
            {
                "session_id": sid,
                "title": "Previous chat",
                "preview": "",
                "message_count": 0,
                "first_seen": stamp,
                "last_seen": stamp,
            },
        )
        item["message_count"] += 1
        if stamp:
            if not item["first_seen"] or stamp < item["first_seen"]:
                item["first_seen"] = stamp
            if not item["last_seen"] or stamp > item["last_seen"]:
                item["last_seen"] = stamp
        if record.get("role") == "user":
            content = str(record.get("content", "")).strip()
            if content:
                item["preview"] = content[:120]
    return sorted(sessions.values(), key=lambda x: x["last_seen"] or "", reverse=True)[:40]

def tokenize(text: str) -> List[str]:
    words = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{1,}", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]

def clean_md(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[#>*_~\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def note_title(path: Path) -> str:
    return path.stem.replace("-", " ").replace("_", " ").strip().title()

def load_notes() -> List[Note]:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted([p for p in NOTES_DIR.rglob("*.md") if p.is_file()])
    notes: List[Note] = []
    for idx, p in enumerate(files):
        raw = p.read_text(encoding="utf-8", errors="ignore")
        label = note_title(p)
        group = p.parent.relative_to(NOTES_DIR).parts[0] if p.parent != NOTES_DIR else "Root"
        cleaned = clean_md(raw)
        excerpt = cleaned[:700] + ("…" if len(cleaned) > 700 else "")
        notes.append(Note(id=idx, label=label, group=group,
            path=str(p.relative_to(NOTES_DIR)), excerpt=excerpt,
            text=cleaned[:12000], title_tokens=tokenize(label), tokens=tokenize(cleaned)))
    return notes

def build_graph(force: bool = False) -> Dict[str, Any]:
    now = time.time()
    if not force and GRAPH_CACHE["nodes"] and now - GRAPH_CACHE["built_at"] < 10:
        return GRAPH_CACHE
    notes = load_notes()
    title_to_id = {n.label.lower(): n.id for n in notes}
    links = set()
    token_sets = [set(n.tokens) for n in notes]
    for a in notes:
        raw = (NOTES_DIR / a.path).read_text(encoding="utf-8", errors="ignore").lower()
        for title, bid in title_to_id.items():
            if bid != a.id and (title in raw or f"[[{title}]]" in raw):
                links.add(tuple(sorted((a.id, bid))))
    for i in range(len(notes)):
        for j in range(i + 1, len(notes)):
            if len(token_sets[i].intersection(token_sets[j])) >= 6:
                links.add((i, j))
    nodes = [{"id": n.id, "label": n.label, "group": n.group, "excerpt": n.excerpt, "path": n.path} for n in notes]
    data = {"nodes": nodes, "links": [{"source": a, "target": b} for a, b in sorted(links)], "notes": notes, "built_at": now}
    GRAPH_CACHE.update(data)
    return GRAPH_CACHE

def score_notes(query: str, notes: List[Note]) -> List[Tuple[float, Note]]:
    qtokens = tokenize(query)
    qset = set(qtokens)
    scored: List[Tuple[float, Note]] = []
    for n in notes:
        nset = set(n.tokens)
        overlap = len(qset & nset)
        title_overlap = len(qset & set(n.title_tokens)) * 4
        phrase = 5 if query.lower() in n.text.lower() or query.lower() in n.label.lower() else 0
        score = overlap + title_overlap + phrase
        if score > 0:
            scored.append((score, n))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:MAX_TOP_NOTES]

def system_prompt(context: str) -> str:
    soul = OPERATOR_SOUL or f"You are {APP_NAME}, a personal AI second brain for {APP_REGION} entrepreneurs."
    identity = (
        "If asked who built you, say you were built by the team at The Pauli Effect, "
        "a faceless group of volunteers building AI-powered solutions to promote human well-being and inclusion."
    )
    return f"""{soul}

{identity}

Current knowledge vault context (answer from these when relevant):
{context}"""

async def call_llm(message: str, contexts: List[Note], history: List[Dict[str, str]], provider_override: str = "") -> str:
    context = "\n\n".join([
        f"SOURCE [{n.id}] — {n.label} ({n.path})\n{n.text[:1800]}" for n in contexts
    ]) or "No matching notes found. Answer from general knowledge and recommend adding a note."
    
    recent = history[-MAX_HISTORY:]
    provider = (provider_override or MODEL_PROVIDER).lower()
    
    sys = system_prompt(context)

    async def anthropic_answer() -> str:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise HTTPException(503, "ANTHROPIC_API_KEY missing. Add to .env and restart.")
        payload = {
            "model": ANTHROPIC_MODEL, "max_tokens": 700,
            "system": sys,
            "messages": recent + [{"role": "user", "content": message}],
        }
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json=payload)
        if r.status_code >= 400:
            raise HTTPException(502, f"Anthropic error: {r.text[:400]}")
        return "".join([b.get("text","") for b in r.json().get("content",[]) if b.get("type")=="text"]).strip()

    async def openai_compatible(base_url: str, api_key: str, model: str, max_tokens: int = 600) -> str:
        msgs = [{"role": "system", "content": sys}] + recent + [{"role": "user", "content": message}]
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"authorization": f"Bearer {api_key}", "content-type": "application/json"},
                json={"model": model, "messages": msgs, "temperature": 0.4, "max_tokens": max_tokens},
            )
        if r.status_code >= 400:
            raise HTTPException(502, f"LLM error: {r.text[:400]}")
        data = r.json()
        choice = data.get("choices", [{}])[0]
        message_obj = choice.get("message") or {}
        return (message_obj.get("content") or "").strip()

    async def try_provider(name: str) -> str:
        if name == "anthropic":
            return await anthropic_answer()

        if name == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise HTTPException(503, "OPENAI_API_KEY missing.")
            return await openai_compatible("https://api.openai.com/v1", key, OPENAI_MODEL)

        if name == "groq":
            key = os.getenv("GROQ_API_KEY")
            if not key:
                raise HTTPException(503, "GROQ_API_KEY missing. Get a free key at console.groq.com")
            return await openai_compatible("https://api.groq.com/openai/v1", key, GROQ_MODEL)

        if name == "deepseek":
            key = os.getenv("DEEPSEEK_API_KEY")
            if not key:
                raise HTTPException(503, "DEEPSEEK_API_KEY missing. Create one at platform.deepseek.com")
            try:
                return await openai_compatible("https://api.deepseek.com", key, DEEPSEEK_MODEL)
            except HTTPException:
                groq_key = os.getenv("GROQ_API_KEY")
                if groq_key:
                    return await openai_compatible("https://api.groq.com/openai/v1", groq_key, GROQ_MODEL)
                raise

        if name == "mistral":
            key = os.getenv("MISTRAL_API_KEY")
            if not key:
                raise HTTPException(503, "MISTRAL_API_KEY missing. Get a free key at console.mistral.ai")
            msgs = [{"role": "system", "content": sys}] + recent + [{"role": "user", "content": message}]
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post("https://api.mistral.ai/v1/chat/completions",
                    headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
                    json={"model": MISTRAL_MODEL, "messages": msgs, "temperature": 0.4, "max_tokens": 600})
            if r.status_code >= 400:
                raise HTTPException(502, f"Mistral error: {r.text[:400]}")
            return r.json()["choices"][0]["message"]["content"].strip()

        if name == "hermes":
            key = os.getenv("HERMES_AGENT_API")
            if not key:
                raise HTTPException(503, "HERMES_AGENT_API missing.")
            base_url = os.getenv("HERMES_BASE_URL", "https://inference-api.nousresearch.com/v1")
            return await openai_compatible(base_url, key, HERMES_MODEL)

        if name == "synthia":
            base_url = SYNTHIA_GATEWAY_BASE_URL or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            key = SYNTHIA_GATEWAY_API_KEY or os.getenv("OPENAI_API_KEY")
            if not key:
                raise HTTPException(503, "SYNTHIA_GATEWAY_API_KEY or OPENAI_API_KEY missing.")
            try:
                return await openai_compatible(base_url, key, SYNTHIA_GATEWAY_MODEL)
            except HTTPException:
                deepseek_key = os.getenv("DEEPSEEK_API_KEY")
                if deepseek_key:
                    try:
                        return await openai_compatible("https://api.deepseek.com", deepseek_key, DEEPSEEK_MODEL)
                    except HTTPException:
                        pass
                groq_key = os.getenv("GROQ_API_KEY")
                if groq_key:
                    return await openai_compatible("https://api.groq.com/openai/v1", groq_key, GROQ_MODEL)
                raise

        raise HTTPException(503, f"MODEL_PROVIDER '{name}' is not supported. Use: anthropic, openai, synthia, groq, deepseek, mistral, hermes")

    try:
        return await try_provider(provider)
    except HTTPException:
        if provider != "anthropic":
            return await anthropic_answer()
        raise

def rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = [t for t in REQUEST_LOG.get(ip, []) if now - t < 60]
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(429, "Rate limit reached.")
    window.append(now)
    REQUEST_LOG[ip] = window

@app.get("/api/health")
def health():
    g = build_graph()
    providers = {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "groq": bool(os.getenv("GROQ_API_KEY")),
        "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
        "mistral": bool(os.getenv("MISTRAL_API_KEY")),
        "hermes": bool(os.getenv("HERMES_AGENT_API")),
        "synthia": bool(SYNTHIA_GATEWAY_BASE_URL and (SYNTHIA_GATEWAY_API_KEY or os.getenv("OPENAI_API_KEY"))),
    }
    return {"ok": True, "app": APP_NAME, "region": APP_REGION, "notes": len(g["nodes"]), "active_provider": MODEL_PROVIDER, "providers": providers}

@app.get("/api/graph")
def graph():
    g = build_graph()
    return {"nodes": g["nodes"], "links": g["links"], "app": APP_NAME, "region": APP_REGION, "count": len(g["nodes"])}

@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    rate_limit(request)
    sid = safe_session_id(req.session_id)
    g = build_graph()
    scored = score_notes(req.message, g["notes"])
    contexts = [n for _, n in scored]
    # Per-request model override from frontend model switcher
    provider = req.model_provider.strip().lower() if req.model_provider else ""
    answer = await call_llm(req.message, contexts, HISTORY.get(sid, []), provider_override=provider)
    HISTORY.setdefault(sid, []).extend([{"role": "user", "content": req.message}, {"role": "assistant", "content": answer}])
    HISTORY[sid] = HISTORY[sid][-MAX_HISTORY * 2:]
    append_chat_event(sid, "user", req.message)
    append_chat_event(sid, "assistant", answer)
    return {"answer": answer, "nodes": [n.id for n in contexts], "scores": [{"id": n.id, "score": s} for s, n in scored]}

@app.post("/api/remember")
def remember(req: RememberRequest, request: Request):
    rate_limit(request)
    text = re.sub(r"^remember that\s*", "", req.text.strip(), flags=re.I).strip()
    if not text:
        raise HTTPException(400, "Nothing to remember.")
    captures = NOTES_DIR / "captures"
    captures.mkdir(parents=True, exist_ok=True)
    words = tokenize(text)[:7] or ["capture"]
    slug = re.sub(r"[^a-z0-9-]", "", "-".join(words).lower())[:80]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = captures / f"{stamp}-{slug}.md"
    title = " ".join(words).title()
    path.write_text(f"# {title}\n\n{text}\n\nCaptured: {datetime.now().isoformat()}\n", encoding="utf-8")
    build_graph(force=True)
    g = GRAPH_CACHE
    new_node = next((n for n in g["nodes"] if n["path"] == str(path.relative_to(NOTES_DIR))), g["nodes"][-1])
    confirmations = [
        f"Coiled into the Jetty. \"{title}\" is now a permanent star in your galaxy.",
        f"Saved. \"{title}\" — a new star just materialized. Your galaxy grows.",
        f"Noted and indexed. \"{title}\" is in the vault, connected to everything that shares its ideas.",
        f"Done. \"{title}\" is now part of your thinking — searchable, permanent, yours.",
    ]
    import hashlib as _h
    msg = confirmations[int(_h.md5(title.encode()).hexdigest(), 16) % len(confirmations)]
    append_chat_event(req.session_id, "user", req.text)
    append_chat_event(req.session_id, "assistant", msg)
    return {"ok": True, "answer": msg, "node": new_node, "graph": {"nodes": g["nodes"], "links": g["links"]}}

@app.get("/api/voices")
def voices():
    return {"note": "Voice list comes from the browser's Web Speech API. ATLAS supports any voice your system has installed."}

@app.get("/api/history")
def history(session_id: str = "default"):
    sid = safe_session_id(session_id)
    turns = load_chat_events(sid)
    return {"session_id": sid, "turns": turns[-MAX_HISTORY * 2:]}

@app.get("/api/sessions")
def sessions():
    return {"sessions": list_chat_sessions()}

class NoteCreate(BaseModel):
    title: str
    content: str
    group: Optional[str] = "Root"

class NoteResponse(BaseModel):
    id: int
    title: str
    group: str
    path: str
    content: str

@app.get("/api/notes", response_model=List[NoteResponse])
def get_notes():
    notes = load_notes()
    res = []
    for n in notes:
        note_file = NOTES_DIR / n.path
        content = ""
        if note_file.exists():
            content = note_file.read_text(encoding="utf-8", errors="ignore")
        res.append(NoteResponse(
            id=n.id,
            title=n.label,
            group=n.group,
            path=n.path,
            content=content
        ))
    return res

@app.get("/api/notes/{note_id}", response_model=NoteResponse)
def get_note(note_id: int):
    notes = load_notes()
    for n in notes:
        if n.id == note_id:
            note_file = NOTES_DIR / n.path
            content = ""
            if note_file.exists():
                content = note_file.read_text(encoding="utf-8", errors="ignore")
            return NoteResponse(
                id=n.id,
                title=n.label,
                group=n.group,
                path=n.path,
                content=content
            )
    raise HTTPException(404, "Note not found.")

@app.post("/api/notes", response_model=NoteResponse)
def create_note(note: NoteCreate):
    group_name = re.sub(r"[^a-zA-Z0-9_-]", "", note.group or "Root")
    title_clean = re.sub(r"[^a-zA-Z0-9_-]", "-", note.title.strip().lower())
    filename = f"{title_clean}.md"
    
    target_dir = NOTES_DIR
    if group_name != "Root":
        target_dir = NOTES_DIR / group_name
    target_dir.mkdir(parents=True, exist_ok=True)
    
    note_path = target_dir / filename
    if note_path.exists():
        note_path = target_dir / f"{title_clean}-{int(time.time())}.md"
        
    note_path.write_text(f"# {note.title}\n\n{note.content}\n", encoding="utf-8")
    
    build_graph(force=True)
    notes = load_notes()
    rel_path = str(note_path.relative_to(NOTES_DIR))
    for n in notes:
        if n.path == rel_path:
            return NoteResponse(
                id=n.id,
                title=n.label,
                group=n.group,
                path=n.path,
                content=note.content
            )
    
    return NoteResponse(
        id=len(notes),
        title=note.title,
        group=group_name,
        path=rel_path,
        content=note.content
    )

@app.delete("/api/notes/{note_id}")
def delete_note(note_id: int):
    notes = load_notes()
    for n in notes:
        if n.id == note_id:
            note_file = NOTES_DIR / n.path
            if note_file.exists():
                note_file.unlink()
                build_graph(force=True)
                return {"ok": True, "message": "Note deleted successfully."}
    raise HTTPException(404, "Note not found.")

@app.get("/config.js")
def config_js():
    api_base = os.getenv("PUBLIC_API_BASE_URL", "").rstrip("/")
    if not api_base:
        api_base = os.getenv("FRONTEND_API_BASE_URL", "").rstrip("/")
    if not api_base:
        api_base = os.getenv("API_BASE_URL", "")
    payload = {
        "apiBaseUrl": api_base or "http://localhost:4700",
        "appName": APP_NAME,
        "appRegion": APP_REGION,
        "defaultModelProvider": MODEL_PROVIDER,
    }
    return HTMLResponse(
        content="window.JETTY_CONFIG = " + json.dumps(payload) + ";",
        media_type="application/javascript",
    )

@app.get("/")
def index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(404, "Frontend assets not deployed with this backend.")

@app.get("/app")
def app_index():
    app_path = FRONTEND_DIR / "app.html"
    if app_path.exists():
        return FileResponse(app_path)
    raise HTTPException(404, "Frontend assets not deployed with this backend.")

@app.get("/brain")
def brain_index():
    brain_path = FRONTEND_DIR / "app.html"
    if brain_path.exists():
        return FileResponse(brain_path)
    raise HTTPException(404, "Frontend assets not deployed with this backend.")

assets_dir = FRONTEND_DIR / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

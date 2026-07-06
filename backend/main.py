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
APP_NAME   = os.getenv("APP_NAME", "JETTY™")
APP_REGION = os.getenv("APP_REGION", "Salt Lake City, Utah")
MODEL_PROVIDER   = os.getenv("MODEL_PROVIDER", "anthropic").lower().strip()
ANTHROPIC_MODEL  = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
OPENAI_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GROQ_MODEL       = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MISTRAL_MODEL    = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
MAX_HISTORY      = int(os.getenv("MAX_HISTORY", "10"))
MAX_TOP_NOTES    = int(os.getenv("MAX_TOP_NOTES", "6"))
PUBLIC_ORIGIN    = os.getenv("PUBLIC_ORIGIN", "*")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "45"))

# Load SOUL from ops/hermes/SOUL.md
_soul_path = ROOT / "ops" / "hermes" / "SOUL.md"
OPERATOR_SOUL = _soul_path.read_text(encoding="utf-8") if _soul_path.exists() else ""

app = FastAPI(title=APP_NAME, version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[PUBLIC_ORIGIN] if PUBLIC_ORIGIN != "*" else ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
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

STOPWORDS = set("a an and are as at be by for from has have i in is it its me my of on or our that the this to we with you your into about what when where who why how do does did can could should would tell give make build".split())

def safe_session_id(v: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.:-]", "_", v)[:96] or "default"

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
    return f"""{soul}

Current knowledge vault context (answer from these when relevant):
{context}"""

async def call_llm(message: str, contexts: List[Note], history: List[Dict[str, str]], provider_override: str = "") -> str:
    context = "\n\n".join([
        f"SOURCE [{n.id}] — {n.label} ({n.path})\n{n.text[:1800]}" for n in contexts
    ]) or "No matching notes found. Answer from general knowledge and recommend adding a note."
    
    recent = history[-MAX_HISTORY:]
    provider = (provider_override or MODEL_PROVIDER).lower()
    
    sys = system_prompt(context)

    if provider == "anthropic":
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

    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise HTTPException(503, "OPENAI_API_KEY missing.")
        msgs = [{"role": "system", "content": sys}] + recent + [{"role": "user", "content": message}]
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions",
                headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
                json={"model": OPENAI_MODEL, "messages": msgs, "temperature": 0.4})
        if r.status_code >= 400:
            raise HTTPException(502, f"OpenAI error: {r.text[:400]}")
        return r.json()["choices"][0]["message"]["content"].strip()

    if provider == "groq":
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise HTTPException(503, "GROQ_API_KEY missing. Get a free key at console.groq.com")
        msgs = [{"role": "system", "content": sys}] + recent + [{"role": "user", "content": message}]
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
                json={"model": GROQ_MODEL, "messages": msgs, "temperature": 0.4, "max_tokens": 600})
        if r.status_code >= 400:
            raise HTTPException(502, f"Groq error: {r.text[:400]}")
        return r.json()["choices"][0]["message"]["content"].strip()

    if provider == "mistral":
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

    raise HTTPException(503, f"MODEL_PROVIDER '{provider}' is not supported. Use: anthropic, openai, groq, mistral")

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
        "mistral": bool(os.getenv("MISTRAL_API_KEY")),
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
    return {"ok": True, "answer": msg, "node": new_node, "graph": {"nodes": g["nodes"], "links": g["links"]}}

@app.get("/api/voices")
def voices():
    return {"note": "Voice list comes from the browser's Web Speech API. ATLAS supports any voice your system has installed."}

@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/app")
def app_index():
    return FileResponse(FRONTEND_DIR / "app.html")

@app.get("/brain")
def brain_index():
    return FileResponse(FRONTEND_DIR / "app.html")

app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

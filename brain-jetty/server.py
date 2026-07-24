#!/usr/bin/env python3
"""Brain Studio V3 — the Jetty server (assistant edition).

Serves the 3D second-brain viewer and proxies PRIVATE endpoints so keys never
reach the browser (read from config.json on this machine only):

  POST /chat        {question, session}  -> RAG + memory -> {answer, nodes}
  POST /tts         {text}               -> ElevenLabs voice -> audio/mpeg
  POST /remember    {text}               -> writes a note + returns it
  POST /edit        {target, text}       -> appends to an existing note
  POST /task | /tasks | /task_done       -> task list
  POST /briefing                         -> spoken morning briefing
  GET  /api/proactive | POST /proactive | POST /proactive_ack  -> scheduled briefings
  POST /agent        {task}              -> Claude Code (claude -p), draft-safe
  POST /agent_confirm {pending_id}       -> execute a confirmed agent action

The model call is provider-aware: native Anthropic Messages API by default, or
any OpenAI-compatible endpoint (GLM via OpenRouter/Z.ai, etc.) when model.base_url
is set in config.json.

Python 3 stdlib only.  Run:  python3 server.py
"""
import os, re, json, time, uuid, shutil, socket, threading, subprocess, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 4719

def load_cfg():
    p = os.path.join(ROOT, "config.json")
    return json.load(open(p)) if os.path.exists(p) else {}
CFG = load_cfg()
VAULT = os.path.expanduser(CFG.get("vault") or "")
MODELCFG = CFG.get("model") or {}
MODEL = MODELCFG.get("model", "claude-opus-4-8")

# ---------- model hot-swap ("Jetty, try on <model>") ----------
# The BOOT brain is what config.json says; swaps are runtime-only and reset on restart
# (deliberate — demos can't permanently wander off the configured brain).
BOOT_MODEL, BOOT_MODELCFG = MODEL, dict(MODELCFG)
MODEL_LOCK = threading.Lock()
# spoken-name shortcuts -> real model ids (extend via config "models": {"name": {"model": ..., optional provider/base_url/api_key}})
MODEL_ALIASES = {
    "opus": "claude-opus-4-8", "haiku": "claude-haiku-4-5", "sonnet": "claude-sonnet-5",
    "fable": "claude-fable-5", "default": BOOT_MODEL, "usual": BOOT_MODEL, "normal": BOOT_MODEL,
}
# OpenRouter = the brain bay: with one key, ANY model on their catalogue is a spoken command away.
# Names are fuzzy-matched against the LIVE catalogue (cached 1h), newest match wins — so
# "try on grok" keeps working when x-ai ships grok-5. Key lives in config.json → "openrouter".
OPENROUTER = CFG.get("openrouter") or {}
OR_BASE = "https://openrouter.ai/api/v1"
def or_key():
    k = (OPENROUTER.get("api_key") or "").strip()
    return k if k and not k.startswith("PUT-") else None
OR_CACHE = {"ts": 0.0, "models": []}
def or_models():
    if time.time() - OR_CACHE["ts"] < 3600 and OR_CACHE["models"]:
        return OR_CACHE["models"]
    try:
        with urllib.request.urlopen(urllib.request.Request(OR_BASE + "/models"), timeout=15) as r:
            data = json.load(r).get("data", [])
        OR_CACHE["models"] = [{"id": m.get("id", ""), "name": m.get("name", ""),
                               "created": m.get("created", 0)} for m in data if m.get("id")]
        OR_CACHE["ts"] = time.time()
    except Exception:
        pass
    return OR_CACHE["models"]
# family → canonical vendor (vendor slugs are stable even as model names churn)
OR_VENDOR = {"grok": "x-ai", "gpt": "openai", "chatgpt": "openai", "o3": "openai", "o4": "openai",
             "gemini": "google", "gemma": "google", "llama": "meta-llama", "deepseek": "deepseek",
             "kimi": "moonshotai", "qwen": "qwen", "mistral": "mistralai", "glm": "z-ai",
             "command": "cohere", "nova": "amazon"}
# variant suffixes to avoid UNLESS the user asked for them ("try on gemini" → the flagship,
# "try on gemini flash lite" → exactly that)
OR_NICHE = ("image", "audio", "video", "code", "coder", "build", "guard", "distill", "base",
            "exp", "preview", "lite", "nano", "mini", "fast", "free", "vision", "instruct", "chat-latest")
def or_match(name):
    """Fuzzy-match a spoken name against the live catalogue → model id, or None.
    Ranking: all spoken tokens must appear; then canonical vendor ≫ recency ≫ flagship-ness
    (niche variants the user didn't ask for are penalized; shorter ids win ties)."""
    n = re.sub(r"[^a-z0-9. ]", " ", (name or "").lower()).strip()
    if not n:
        return None
    toks = n.split()
    vendor = next((OR_VENDOR[t] for t in toks if t in OR_VENDOR), None)
    best, score = None, 0.0
    for m in or_models():
        hay = (m["id"] + " " + m["name"]).lower()
        if not all(t in hay for t in toks):
            continue
        mid = m["id"]; vend, _, rest = mid.partition("/")
        s = 100.0 + (m.get("created") or 0) / 1e9      # base: all tokens present, prefer newest
        if vendor:
            s += 50 if vend == vendor else -30          # meta's llama beats nvidia's fork
        for kw in OR_NICHE:
            if kw in rest and kw not in toks:
                s -= 8                                  # unasked-for niche variant
        s -= len(mid) * 0.05                            # flagships have the short names
        if s > score:
            best, score = m, s
    return best["id"] if best else None

def resolve_model(name):
    """Spoken name → (model_id, cfg, err). err: None | 'unknown' | 'no_openrouter_key'."""
    n = (name or "").strip().lower().rstrip(".!?")
    custom = CFG.get("models") or {}
    if n in custom:
        c = dict(BOOT_MODELCFG); c.update(custom[n])
        if c.get("base_url") and not (c.get("api_key") or "").strip() and or_key():
            c["api_key"] = or_key()                     # custom entries may lean on the OR key
        return c.get("model", BOOT_MODEL), c, None
    mid = MODEL_ALIASES.get(n) or (n if re.match(r"^claude-[a-z0-9.-]+$", n) else None)
    if not mid and "/" not in n:
        # normalize Claude-family phrasings ("claude opus 4.8", "opus 4.8", "claude") to the
        # NATIVE key — never accidentally route Claude through OpenRouter
        fam = next((f for f in ("opus", "sonnet", "haiku", "fable") if f in n), None)
        if fam:
            mid = MODEL_ALIASES[fam]
        elif n.startswith("claude"):
            mid = BOOT_MODEL
    if mid:
        c = dict(BOOT_MODELCFG); c["model"] = mid
        return mid, c, None
    slug = n if "/" in n else or_match(n)               # explicit vendor/slug, or live fuzzy match
    if not slug:
        return None, None, "unknown"
    if not or_key():
        return None, None, "no_openrouter_key"
    return slug, {"provider": "openrouter", "base_url": OR_BASE, "api_key": or_key(),
                  "model": slug}, None
def set_model(name):
    global MODEL, MODELCFG
    mid, cfg, err = resolve_model(name)
    if err or not mid:
        return None, (err or "unknown")
    with MODEL_LOCK:
        MODEL, MODELCFG = mid, cfg
    return mid, None
def known_brains():
    return sorted(set(list(MODEL_ALIASES) + list((CFG.get("models") or {}).keys()))
                  - {"usual", "normal", "default"})

# Model-swap requests that arrive as plain CONVERSATION (the live 📡 session, the menu bar,
# Raycast, loose phrasings the client regex misses) get executed HERE, inside /chat — so
# "can you switch to grok?" works no matter which door it walks in through.
CHAT_SWAP_RE = re.compile(
    r"^\s*(?:jetty[,!]?\s+)?(?:can you\s+|could you\s+|please\s+|would you\s+|go ahead and\s+)*"
    r"(?:try(?:ing)? on|put on|switch(?:\s+(?:your|the))?(?:\s+(?:brain|model|engine))?(?:\s+over)?\s+to|"
    r"swap(?:\s+(?:your|the))?(?:\s+(?:brain|model|engine))?\s+(?:to|for)|"
    r"change(?:\s+(?:your|the))?\s+(?:brain|model|engine)\s+to)\s+"
    r"(?:the\s+|your\s+)?([a-z0-9 ./-]+?)(?:\s+(?:brain|model|engine))?"
    r"(?:\s+(?:for me|now|please))?\s*[.!?]*\s*$", re.I)
CHAT_SWAP_RESET_RE = re.compile(
    r"^\s*(?:jetty[,!]?\s+)?(?:can you\s+|could you\s+|please\s+)*(?:go\s+|switch\s+|swap\s+|change\s+)?"
    r"back to (?:your |the )?(?:usual|normal|default|old|regular)(?:\s+(?:brain|model|self|engine))?"
    r"(?:\s+please)?\s*[.!?]*\s*$", re.I)
def swap_quip(mid):
    quip, qerr = call_model([{"role": "user", "content":
        f"You have just been fitted as Jetty's new brain: {mid}. In ONE short dry sentence, "
        "introduce yourself in character and address the user as 'sir'."}], PERSONA, 400)
    if qerr or not quip or quip == "(no answer)":
        quip = f"New brain fitted, sir — {mid} online."
    return quip
def do_swap(name):
    """Execute a model swap, always returning a /chat-shaped dict (shelf-list error if unknown)."""
    mid, merr = set_model(name)
    if mid:
        log_episode("model", f"Brain swapped to {mid} (via chat)")
        return {"answer": swap_quip(mid), "nodes": [], **model_status()}
    if merr == "no_openrouter_key":
        return {"answer": f"I found '{name}' in the OpenRouter catalogue, sir, but the OpenRouter key "
                          "is missing from config.json.", "nodes": [], **model_status()}
    return {"answer": f"I don't have a '{name}' brain on the shelf, sir — I know " +
                      ", ".join(known_brains()) + ".", "nodes": [], **model_status()}
def try_chat_swap(question):
    """Regex fast path: obvious swap phrasings skip the model call. None → let the model decide."""
    m = CHAT_SWAP_RESET_RE.match(question or "")
    name = "default" if m else None
    if not name:
        m = CHAT_SWAP_RE.match(question or "")
        if m:
            name = m.group(1).strip()
    if not name:
        return None
    mid, merr = set_model(name)
    if mid:
        log_episode("model", f"Brain swapped to {mid} (via chat)")
        return {"answer": swap_quip(mid), "nodes": [], **model_status()}
    if merr == "no_openrouter_key":
        return {"answer": f"I found '{name}' in the OpenRouter catalogue, sir, but the OpenRouter key "
                          "is missing from config.json.", "nodes": [], **model_status()}
    return None      # regex matched but it's not a model ("try on the red jacket") → normal chat

# The model itself is the intent detector of last resort: ANY phrasing of "switch your
# model/voice" that the regexes miss gets tagged by the brain and executed here.
CONTROL_HINT = (
    "\n\nCONTROL REQUESTS (overrides everything): if the user is asking you to SWITCH/CHANGE your "
    "underlying AI model or brain — any phrasing: 'switch (yourself) to Gemini', 'upgrade to GPT', "
    "'become Grok', 'run on Haiku', 'put Gemini in', 'back to your usual brain' — reply with EXACTLY "
    "[SWAP:<model name they said>] and NOTHING else ([SWAP:default] for the usual brain). If they ask "
    "you to change your VOICE to a named voice, reply EXACTLY [VOICE:<name>]. If they ask you to ADD "
    "a new node/note/sphere to their brain or graph about some topic — any phrasing — reply EXACTLY "
    "[NODE:<the topic>] or, if they named something to connect/link it to, "
    "[NODE:<the topic>|<what to connect it to>]. NODE is ONLY for explicit requests to ADD/CREATE "
    "a new node or note — asking to SHOW, FIND, or PULL UP existing information is normal retrieval, "
    "never a NODE. If they ask you to CREATE a real PROJECT, FOLDER, or WIKI page on disk — 'start a "
    "new project for my sparkle app', 'make a folder for client X', 'add a wiki page on GEO pricing' — "
    "reply EXACTLY [CREATE:<kind: project/folder/note/wiki>|<short name>|<where: projects / wiki / "
    "wiki/concepts / brainstorm, or blank for the default>|<one line on what it is about, under 15 "
    "words>|<existing note to connect it to, or blank>] with NO other words before or after — the "
    "system speaks the confirmation for you. IMPORTANT: if you do NOT yet know what it's about — or, for "
    "folders and notes, where it should live — ASK in a normal short reply first ('Where should this "
    "live, sir — projects, the wiki, or brainstorm? And what is it about?') and emit the CREATE tag "
    "only once they've answered; the conversation holds the details. Projects always live in "
    "projects/. If they ask you to REMIND them of something or set a reminder/task — any "
    "phrasing — reply EXACTLY [REMIND:<the thing to do>|<the when-phrase they said, e.g. tomorrow / "
    "at 5pm / in 2 hours>] (omit the | part if no time given). If they ask you to change your HUMOR "
    "or HONESTY setting ('humor to 90', 'be less funny', 'maximum honesty') reply EXACTLY "
    "[DIAL:humor=90] with the sensible number. If they ask you to put on a different PERSONA "
    "(GLaDOS / pirate / coach / back to butler) reply EXACTLY [SKIN:<name>]. If they explicitly ask "
    "you to RESEARCH something, look something up online, google it, or fetch live/current "
    "information (today's news, a price, the weather, a score, a release date) reply EXACTLY "
    "[SEARCH:<a concise search query>] — ONLY when they clearly want live online information; "
    "opinions, jokes, and anything in their own notes are never a SEARCH. If they ask you to SPEAK "
    "or SWITCH TO another LANGUAGE — any phrasing, in ANY language: 'speak Spanish', 'habla español', "
    "'parle-moi en français', 'back to English' — reply EXACTLY [LANG:<language name in English>]. "
    "Questions, jokes, or opinions about models/voices/notes/languages are normal conversation. SEPARATELY: at most once per "
    "conversation, if the user says something genuinely worth teasing them about later, you may "
    "append at the very END of an otherwise normal reply: "
    "[GAG:<two or three trigger words>|<the short callback line to deliver later>].")
TAG_RE = re.compile(r"^\s*\[(SWAP|VOICE|NODE|CREATE|REMIND|DIAL|SKIN|SEARCH|LANG):([^\]]{1,320})\]\s*$", re.I)
# fallback: the model led with the tag but couldn't resist adding prose — fire the tag, drop the chatter
TAG_LEAD_RE = re.compile(r"^\s*\[(SWAP|VOICE|NODE|CREATE|REMIND|DIAL|SKIN|SEARCH|LANG):([^\]]{1,320})\]", re.I)
GAG_TAG_RE = re.compile(r"\s*\[GAG:([^\]|]{1,60})\|([^\]]{1,160})\]\s*$", re.I)
def apply_control_tag(ans, sid=None):
    """If the model answered with a control tag, execute it. Returns a response dict or None."""
    m = TAG_RE.match(ans or "")
    if not m:
        lm = TAG_LEAD_RE.match(ans or "")
        if lm:
            rest = (ans or "")[lm.end():].strip()
            # a hedge ("Shall I…?"), quoted docs ([NODE:<the topic>]), or a long explanation is
            # NOT a command — speak the prose, never fire the side effect
            if "<" in lm.group(2) or ">" in lm.group(2) or "?" in rest or len(rest) > 120:
                if rest:
                    return {"answer": rest, "nodes": []}
            else:
                m = lm                             # short acknowledgment after the tag — fire it, drop the chatter
    if not m:
        if re.match(r"^\s*\[(SWAP|VOICE|NODE|CREATE|REMIND|DIAL|SKIN|SEARCH|LANG):", ans or "", re.I):
            return {"answer": "I lost the thread mid-command, sir — say that again, a touch shorter.",
                    "nodes": []}                   # a malformed/overlong tag must never be read aloud
        return None
    kind, name = m.group(1).upper(), m.group(2).strip()
    if kind == "SWAP":
        return do_swap(name)
    if kind == "LANG":
        code = set_lang(name)
        if not code:
            return {"answer": f"I don't speak {name} yet, sir — my repertoire runs to " +
                              ", ".join(lang_status()["spoken"]) + ".", "nodes": []}
        return {"answer": LANGS[code][1], "nodes": [], "lang": lang_status()}
    if kind == "SEARCH":
        if not name:
            return {"answer": "Research what, sir?", "nodes": []}
        res, err = web_research(name, sid, max_uses=3)   # lighter cap on the tag path — /chat's client timeout is 35s
        if err:
            return {"answer": f"The wires failed me on that one, sir ({err}).", "nodes": []}
        return res
    if kind == "NODE":
        topic, _, related = (x.strip() for x in name.partition("|"))
        if not topic:
            return {"answer": "A node about what, sir?", "nodes": []}
        res, err = capture(topic, related)
        if err:
            return {"answer": f"I couldn't write that one down, sir ({err}).", "nodes": []}
        log_episode("note", "Node added: " + topic + ((" ↔ " + related) if related else ""))
        return {"answer": f"Done, sir — “{res['label']}” is live" +
                          (f" and wired to {related}." if related else " in the constellation."),
                "nodes": [], "new_node": {"label": res["label"], "text": topic, "related": related,
                                          "idx": res.get("idx"), "group": "note"}}
    if kind == "CREATE":
        parts = [x.strip() for x in name.split("|")] + [""] * 5
        ckind, cname, cwhere, cabout, crelated = parts[:5]
        if not cname:
            return {"answer": "Create it as what, sir? I need at least a name.", "nodes": []}
        res, err = create_item(ckind, cname, cwhere, cabout, crelated)
        if err:
            return {"answer": f"I couldn't build that, sir ({err}).", "nodes": []}
        log_episode("create", f"{res['kind'].capitalize()} created: {res['label']} → {res['rel']}")
        raise_card("notify", f"📁 {res['kind'].capitalize()} created — {res['label']}", res["rel"],
                   source="create", speak=False)
        return {"answer": res["say"], "nodes": [],
                "new_node": {"label": res["label"], "text": cabout or cname, "related": res["related"],
                             "rel": res["rel"], "idx": res.get("idx"), "group": res["group"],
                             "kind": res["kind"]}}
    if kind == "DIAL":
        dm = re.match(r"(humor|honesty)\s*=\s*(\d{1,3})", name, re.I)
        v = persona.set_dial(dm.group(1), dm.group(2)) if dm else None
        if v is None:
            return {"answer": "Which dial, sir — humor or honesty?", "nodes": []}
        quip, qerr = call_model([{"role": "user", "content":
            f"Your {dm.group(1).lower()} setting was just changed to {v}%. Acknowledge in ONE short "
            "line, in character, and let the new setting show in the delivery."}], jpersona(), 200)
        return {"answer": quip if not qerr and quip and quip != "(no answer)"
                else f"{dm.group(1).capitalize()} at {v} percent, sir.",
                "nodes": [], "persona": persona.status()}
    if kind == "SKIN":
        label, voice_hint = persona.set_skin(name)
        if not label:
            return {"answer": f"I don't own a '{name}' costume, sir — the wardrobe holds " +
                              ", ".join(persona.status()["skins"]) + ".", "nodes": []}
        set_voice(voice_hint or "default")          # matching voice, best-effort
        quip, qerr = call_model([{"role": "user", "content":
            "You have just put this persona on. Introduce yourself in ONE short line, fully in character."}],
            jpersona(), 200)
        return {"answer": quip if not qerr and quip and quip != "(no answer)" else f"{label} online.",
                "nodes": [], "persona": persona.status()}
    if kind == "REMIND":
        todo, _, whenp = (x.strip() for x in name.partition("|"))
        if not todo:
            return {"answer": "Remind you of what, sir?", "nodes": []}
        due, wlabel = parse_when_text(whenp or todo)
        add_task(todo, due)
        log_episode("task", "Reminder: " + todo + ((" (" + wlabel + ")") if wlabel else ""))
        if due:
            raise_card("notify", f"⏰ Reminder set — {wlabel}", todo, source="reminder")
            return {"answer": f"Reminder set for {wlabel}, sir.", "nodes": [], "reminder_set": True}
        raise_card("notify", "🗒 Added to your list", todo, source="reminder")
        return {"answer": f"On the list, sir — “{todo}”.", "nodes": [], "reminder_set": True}
    spoken, verr = set_voice(name)
    if verr:
        return {"answer": verr, "nodes": []}
    return {"answer": f"How do I sound, sir? This is {spoken}.", "nodes": [], "voice": voice_status()}
def model_status():
    return {"model": MODEL, "provider": (MODELCFG.get("provider") or "anthropic"),
            "default": MODEL == BOOT_MODEL and MODELCFG.get("base_url") == BOOT_MODELCFG.get("base_url"),
            "brains": known_brains(), "openrouter": bool(or_key())}

# ---------- voice hot-swap ("Jetty, switch your voice to Daniel" / "use the flash engine") ----------
# Same trick as the brain bay, for the mouth: names fuzzy-match the LIVE ElevenLabs voice
# library (cached 1h). Runtime-only; resets to config.json's voice on restart.
ELCFG = CFG.get("elevenlabs") or {}
VOICE_LOCK = threading.Lock()
VOICE = {"voice_id": ELCFG.get("voice_id", ""), "model_id": ELCFG.get("model_id", "eleven_turbo_v2_5"),
         "name": "default"}
BOOT_VOICE = dict(VOICE)
EL_ENGINES = {"flash": "eleven_flash_v2_5", "fast": "eleven_flash_v2_5",
              "turbo": "eleven_turbo_v2_5", "v3": "eleven_v3", "expressive": "eleven_v3",
              "multilingual": "eleven_multilingual_v2"}
VOICE_CACHE = {"ts": 0.0, "voices": []}
def el_voices():
    key = ELCFG.get("api_key", "")
    if not key or key.startswith("PUT-"):
        return []
    if time.time() - VOICE_CACHE["ts"] < 3600 and VOICE_CACHE["voices"]:
        return VOICE_CACHE["voices"]
    try:
        req = urllib.request.Request("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key})
        with urllib.request.urlopen(req, timeout=15) as r:
            vs = json.load(r).get("voices", [])
        VOICE_CACHE["voices"] = [{"id": v.get("voice_id", ""), "name": v.get("name", ""),
                                  "category": v.get("category", "")} for v in vs if v.get("voice_id")]
        VOICE_CACHE["ts"] = time.time()
    except Exception:
        pass
    return VOICE_CACHE["voices"]
def set_voice(name):
    """Returns (spoken_name, err). Handles voice names, engine names, and 'default'."""
    n = (name or "").strip().lower().rstrip(".!?")
    if not n:
        return None, "which voice, sir?"
    if n in ("default", "usual", "normal", "yours", "jetty"):
        with VOICE_LOCK:
            VOICE.update(BOOT_VOICE)
        return "my usual voice", None
    if n in EL_ENGINES:                                    # engine swap (flash/turbo/v3), same voice
        with VOICE_LOCK:
            VOICE["model_id"] = EL_ENGINES[n]
        return f"the {n} engine", None
    vs = el_voices()
    if not vs:
        return None, "I can't reach the voice library, sir — is the ElevenLabs key in config?"
    toks = n.split()
    best, score = None, 0
    for v in vs:
        vn = v["name"].lower()
        if vn.split(" - ")[0].strip() == n:                # exact first-name match wins outright
            best, score = v, 999; break
        s = sum(1 for t in toks if t in vn)
        if s == len(toks) and s > score:
            best, score = v, s
    if not best:
        names = ", ".join(sorted({v["name"].split(" - ")[0] for v in vs})[:12])
        return None, f"no '{name}' in the wardrobe, sir — I have {names}, among others."
    with VOICE_LOCK:
        VOICE["voice_id"] = best["id"]; VOICE["name"] = best["name"]
    return best["name"].split(" - ")[0], None
def voice_status():
    return {"name": VOICE["name"], "model_id": VOICE["model_id"],
            "default": VOICE["voice_id"] == BOOT_VOICE["voice_id"] and VOICE["model_id"] == BOOT_VOICE["model_id"],
            "voices": sorted({v["name"].split(" - ")[0] for v in el_voices()})}

# ---------- room lighting (Philips Hue; graceful no-op without a bridge) ----------
import hue
hue.init(CFG.get("hue") or {}, ROOT)

# ---------- the AI-OS layer (deterministic Mac control) + the personality engine ----------
import osctl
import persona

# ---------- V5 add-on bays (soft imports — the server boots fine without them) ----------
try:
    import missions as MISSIONS      # agentic missions: fleet / build-app / reaper / war room / announce / haters
except Exception as _e:
    MISSIONS = None
    if not isinstance(_e, ModuleNotFoundError): print("[missions] failed to load:", _e)
try:
    import tools as TOOLS            # the armory: direct MCP tool connections + discovery/install
except Exception as _e:
    TOOLS = None
    if not isinstance(_e, ModuleNotFoundError): print("[tools] failed to load:", _e)
try:
    import hands as HANDS            # permission-gated computer takeover (Claude computer-use loop)
except Exception as _e:
    HANDS = None
    if not isinstance(_e, ModuleNotFoundError): print("[hands] failed to load:", _e)
try:
    import calls as CALLS            # hands-free phone calling on your behalf (Retell AI)
except Exception as _e:
    CALLS = None
    if not isinstance(_e, ModuleNotFoundError): print("[calls] failed to load:", _e)
try:
    import pocket as POCKET          # text the brain from anywhere (Telegram, long-polled — no tunnel)
except Exception as _e:
    POCKET = None
    if not isinstance(_e, ModuleNotFoundError): print("[pocket] failed to load:", _e)

LAST_POLL = [0.0]                    # last time a viewer tab polled /api/inbox — pocket uses it to
                                     # decide whether the desk or the phone should voice a reminder

# ---------- presence orb: a floating Jetty reactor on the real desktop (UDP-driven) ----------
PRESENCE_PORT = 4732
PRESENCE_PROC = [None]

def _persist_takeover_speed(tier):
    """Persist just takeover.speed to config.json (re-reads disk so runtime-only state isn't written)."""
    CFG.setdefault("takeover", {})["speed"] = tier
    try:
        path = os.path.join(ROOT, "config.json")
        disk = json.load(open(path))
        disk.setdefault("takeover", {})["speed"] = tier
        tmp = path + ".tmp"
        with open(tmp, "w") as f: json.dump(disk, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass

def presence(cmd):
    """Fire-and-forget a command at presence.py over UDP. Boots the orb window on first use."""
    try:
        if PRESENCE_PROC[0] is None or PRESENCE_PROC[0].poll() is not None:
            _spawn_presence()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(cmd.encode(), ("127.0.0.1", PRESENCE_PORT)); s.close()
    except Exception:
        pass

def _spawn_presence():
    """Launch presence.py as a direct child — the server runs in the user's GUI session, so the
    child inherits window-server access (verified). We hold the real handle in PRESENCE_PROC so
    presence() never re-spawns a live orb. A `quit` first clears any orphan from a prior run."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(b"quit", ("127.0.0.1", PRESENCE_PORT)); s.close(); time.sleep(0.3)
    except Exception:
        pass
    try:
        PRESENCE_PROC[0] = subprocess.Popen(["/usr/bin/python3", os.path.join(ROOT, "presence.py")],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.8)                 # let it bind UDP + create the window before commands arrive
    except Exception:
        pass
# ---------- multilingual mode ----------
LANG_FILE = os.path.join(ROOT, "jetty-lang.json")
LANGS = {   # code: (English name, canned in-language confirmation line)
    "en": ("English",    "Back to the King's English, sir."),
    "es": ("Spanish",    "A sus órdenes, señor."),
    "fr": ("French",     "À votre service, monsieur."),
    "de": ("German",     "Zu Ihren Diensten, Sir."),
    "it": ("Italian",    "Al suo servizio, signore."),
    "pt": ("Portuguese", "Às suas ordens, senhor."),
    "nl": ("Dutch",      "Tot uw dienst, meneer."),
    "hi": ("Hindi",      "आपकी सेवा में, सर।"),
    "ur": ("Urdu",       "حاضر ہوں، سر۔"),
    "ar": ("Arabic",     "في خدمتك يا سيدي."),
    "ja": ("Japanese",   "かしこまりました、サー。"),
    "ko": ("Korean",     "분부대로 하겠습니다, 서."),
    "zh": ("Chinese",    "遵命，先生。"),
    "ru": ("Russian",    "К вашим услугам, сэр."),
    "tr": ("Turkish",    "Emrinizdeyim, efendim."),
    "pl": ("Polish",     "Do usług, sir."),
}
LANG_ALIAS = {"english": "en", "spanish": "es", "español": "es", "espanol": "es", "french": "fr",
              "français": "fr", "francais": "fr", "german": "de", "deutsch": "de", "italian": "it",
              "italiano": "it", "portuguese": "pt", "português": "pt", "portugues": "pt", "dutch": "nl",
              "hindi": "hi", "urdu": "ur", "arabic": "ar", "japanese": "ja", "korean": "ko",
              "chinese": "zh", "mandarin": "zh", "russian": "ru", "turkish": "tr", "polish": "pl",
              "default": "en", "usual": "en"}
LANG_LOCK = threading.Lock()
def load_lang():
    try:
        with open(LANG_FILE) as f:
            c = (json.load(f) or {}).get("code", "en")
        return c if c in LANGS else "en"
    except Exception:
        return "en"
def set_lang(name_or_code):
    key = (name_or_code or "").strip().lower()
    code = key if key in LANGS else LANG_ALIAS.get(key)
    if not code:
        return None
    with LANG_LOCK:
        try:
            with open(LANG_FILE, "w") as f:
                json.dump({"code": code}, f)
        except Exception:
            pass
    return code
def lang_status():
    c = load_lang()
    return {"code": c, "name": LANGS[c][0], "default": c == "en",
            "spoken": sorted(v[0] for v in LANGS.values())}

def jpersona(question=""):
    """The live persona block (skin + dials + gate + gags) — replaces the static PERSONA."""
    with VOICE_LOCK:
        v3 = "v3" in (VOICE.get("model_id") or "")
    base = persona.system(question, allow_tags=v3)
    # models don't know the date — without this, "tomorrow" got computed from training data
    # (live bug 2026-07-13: calendar checked "6th of June 2025" and reported an empty day)
    base += time.strftime("\n\nCURRENT DATE-TIME: %A, %d %B %Y, %H:%M %Z (local). Compute 'today', "
                          "'tomorrow', 'next week' and every ISO date from THIS — never from memory.")
    # global anti-capitulation: the 2026-07-13 live failure — a plain-chat follow-up "I have three
    # meetings tomorrow" produced "You're right, sir — three blocks, exactly as you said" with ZERO
    # tool data. Account data may only ever come from tool results.
    base += ("\n\nLIVE-DATA HONESTY (non-negotiable): you have NO live access to email, calendar, "
             "drafts, or connected apps except through explicit tool runs whose results appear in "
             "this conversation. Never state, summarize, or AGREE about such account data without "
             "an actual tool result backing it — if the user disputes a result, tell them you'll "
             "re-check (say 'check again') rather than conceding; their memory is not a data "
             "source, and neither is yours. When a tool result IS present, read its specifics "
             "aloud — the no-recital rule covers vault notes only.")
    c = load_lang()
    if c != "en":
        nm = LANGS[c][0]
        base += (f"\n\nLANGUAGE (non-negotiable): sir has switched you to {nm}. EVERY reply — answers, "
                 f"quips, acknowledgments — must be written entirely in {nm}, keeping the same butler "
                 f"character. Control tags like [SWAP:…]/[LANG:…] themselves stay in English.")
    else:
        base += ("\n\nLANGUAGE: reply in English by default; but if sir writes to you in another "
                 "language, reply fluently in that same language.")
    base += ("\n\nHEARD, NOT TYPED: most input arrives through speech recognition, so names come "
             "misheard — 'Higgs Field' means Higgsfield, 'can va' means Canva, 'site view' means "
             "their projects. Match names generously against what you know of sir's tools, projects and "
             "notes; never quibble about spelling, and only ask when genuinely ambiguous.")
    return base

# ---------- duplex voice (ElevenLabs Agents custom-LLM brain on a separate, token-authed port) ----------
DUPLEX_PORT = 4722
DUPLEX_FILE = os.path.join(ROOT, "jetty-duplex.json")
DUPLEX_LOCK = threading.Lock()
DUPLEX_NODES = {"nodes": [], "ts": 0}     # side-channel: last notes retrieved during a live session
def load_duplex():
    try:
        d = json.load(open(DUPLEX_FILE)) if os.path.exists(DUPLEX_FILE) else {}
    except Exception:
        d = {}
    if not d.get("token"):                # first boot: mint the bearer token EL must present
        d["token"] = uuid.uuid4().hex + uuid.uuid4().hex
        try:
            tmp = DUPLEX_FILE + ".tmp"
            with open(tmp, "w") as f: json.dump(d, f, indent=1)
            os.replace(tmp, DUPLEX_FILE)
        except OSError:
            pass
    return d
def set_duplex_nodes(idxs):
    with DUPLEX_LOCK:
        DUPLEX_NODES["nodes"] = idxs[:14]
        DUPLEX_NODES["ts"] = int(time.time())
def save_duplex(d):
    try:
        tmp = DUPLEX_FILE + ".tmp"
        with open(tmp, "w") as f: json.dump(d, f, indent=1)
        os.replace(tmp, DUPLEX_FILE)
    except OSError:
        pass

# ---------- GPT Realtime (OpenAI speech-to-speech) as a second live-voice engine ----------
# The browser talks WebRTC straight to OpenAI using a short-lived token minted here (the real
# key never reaches the page). GPT handles ears+mouth+turn-taking; an ask_jetty TOOL routes
# every knowledge/memory/vault question back to THIS server — Claude stays the brain.
OPENAI = CFG.get("openai") or {}
def openai_key():
    k = (OPENAI.get("api_key") or "").strip()
    return k if k and not k.startswith("PUT-") else None
def realtime_session():
    key = openai_key()
    if not key:
        return None, ("GPT Realtime isn't wired yet, sir — paste an OpenAI key under \"openai\" "
                      "in config.json.")
    instructions = (PERSONA + mem_block() +
        time.strftime("Current date-time: %A, %d %B %Y, %H:%M %Z (local) — compute 'today'/'tomorrow' from this. ") +
        "You are the VOICE layer only. Speak in short, dry, witty sentences, 'sir' now and then. "
        "For ANYTHING about the user's notes, projects, memory, tasks, schedule, or anything you "
        "aren't certain of, call the ask_jetty tool and relay its answer faithfully in your own "
        "spoken style — never invent details about the user's life. If the user disputes an answer "
        "about their email or calendar, say you'll verify from the desk — never simply agree with "
        "their version; you hold no account data of your own. No markdown, no lists. "
        "SCREEN: whenever the user asks about what's on their screen — what they're looking at, to "
        "read/describe/critique it, 'what do you see', 'look at this' — you MUST call the "
        "look_at_screen tool FIRST and answer only from the fresh screenshot it attaches. NEVER "
        "describe the screen from memory or guess; the screen changes constantly. "
        "IMPORTANT: if the user asks to switch models/brains ('try on grok', 'switch to gemini', "
        "'back to your usual brain') or to change anything about Jetty itself, do NOT refuse — "
        "pass the request VERBATIM to ask_jetty and relay the result; the system executes it.")
    model = OPENAI.get("realtime_model", "gpt-realtime")
    voice = OPENAI.get("realtime_voice", "cedar")
    tools = [{"type": "function", "name": "ask_jetty",
              "description": "The user's second brain: answers anything about their notes, "
                             "projects, memory, tasks, or life. Use it liberally.",
              "parameters": {"type": "object",
                             "properties": {"question": {"type": "string"}},
                             "required": ["question"]}},
             {"type": "function", "name": "look_at_screen",
              "description": "Attaches a FRESH screenshot of the user's screen right now so you can "
                             "see what they're actually looking at. Call this every time the user "
                             "asks about their screen — never answer about the screen without it.",
              "parameters": {"type": "object", "properties": {}}}]
    # GA endpoint (client_secrets, session object) first; fall back to the legacy beta (sessions)
    attempts = [
        ("https://api.openai.com/v1/realtime/client_secrets",
         {"session": {"type": "realtime", "model": model, "instructions": instructions,
                      "audio": {"output": {"voice": voice}}, "tools": tools, "tool_choice": "auto"}},
         "https://api.openai.com/v1/realtime/calls"),
        ("https://api.openai.com/v1/realtime/sessions",
         {"model": model, "voice": voice, "instructions": instructions,
          "tools": tools, "tool_choice": "auto"},
         "https://api.openai.com/v1/realtime?model=" + model),
    ]
    last = ""
    for url, payload, sdp_url in attempts:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.load(r)
            secret = d.get("value") or ((d.get("client_secret") or {}).get("value")) or ""
            if not secret:
                last = "no token in the response"; continue
            return {"client_secret": secret, "model": model, "sdp_url": sdp_url}, None
        except urllib.error.HTTPError as e:
            last = f"{e.code}: {e.read().decode(errors='ignore')[:140]}"
            continue
        except Exception as e:
            last = str(e)[:100]; continue
    return None, f"the Realtime line refused, sir ({last})"
def duplex_providers():
    dx = load_duplex()
    providers = {"elevenlabs": bool(dx.get("agent_id")), "openai": bool(openai_key())}
    pref = (dx.get("provider") or "auto").lower()
    if pref in providers and providers[pref]:
        active = pref
    else:                                                   # auto: EL agent first, then GPT Realtime
        active = "elevenlabs" if providers["elevenlabs"] else ("openai" if providers["openai"] else "")
    return {"providers": providers, "provider": active, "preference": pref}
CLAUDE_BIN = CFG.get("claude_bin") or shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
TASKS_FILE = os.path.join(ROOT, "jetty-tasks.json")
PROACTIVE_FILE = os.path.join(ROOT, "jetty-proactive.json")
MEMORY_FILE = os.path.join(ROOT, "jetty-memory.md")
AGENT_WORKSPACE = os.path.join(ROOT, "agent-workspace")
PERSONA = "You are JETTY — the user's dry-witted, calm British AI-butler second brain. "

TASKS_LOCK = threading.Lock()
SESS_LOCK = threading.Lock()
PENDING_LOCK = threading.Lock()
PROACTIVE_LOCK = threading.Lock()
MEMORY_LOCK = threading.Lock()

# ---------- long-term memory (durable, human-readable facts about the user) ----------
def load_memory():
    try:
        with MEMORY_LOCK:
            return open(MEMORY_FILE, encoding="utf-8").read().strip()[:2600] if os.path.exists(MEMORY_FILE) else ""
    except Exception:
        return ""
def mem_block():
    m = load_memory()
    return ("\n\nWHAT YOU KNOW ABOUT THE USER (your long-term memory — use it to personalize, "
            "never recite it verbatim):\n" + m + "\n") if m else ""
def remember_me(text):
    text = (text or "").strip()
    if not text:
        return None, "nothing to remember, sir"
    try:
        with MEMORY_LOCK:
            new = not os.path.exists(MEMORY_FILE)
            with open(MEMORY_FILE, "a", encoding="utf-8") as f:
                if new:
                    f.write("# What Jetty knows about me\n")
                f.write("- " + text.replace("\n", " ") + "\n")
    except OSError as e:
        return None, f"couldn't save that, sir ({e.__class__.__name__})"
    return {"ok": True}, None

# Structural safety for the agent's DRAFT mode: these tool-name patterns are
# physically blocked (claude --disallowedTools), so a draft run cannot send,
# post, delete, spend, OR write/shell/delegate its way around it — even though it
# may freely READ via your connected tools. Bash/Write/Edit/Task are blocked so the
# model can't fall back to a shell or a sub-agent to mutate anything; the mcp__*
# wildcards match the random per-server MCP prefixes (verified: wildcard denies are
# honored even under bypassPermissions). Override with config: "agent":{"disallow":[...]}
AGENT_DENY = (CFG.get("agent") or {}).get("disallow") or [
    "Bash", "Write", "Edit", "Task",
    "mcp__*send*", "mcp__*post*", "mcp__*reply*", "mcp__*delete*",
    "mcp__*publish*", "mcp__*deploy*", "mcp__*spend*", "mcp__*pay*", "mcp__*buy*",
]
PENDING = {}   # pending_id -> {task, ts}  (confirmed-action store)

# ---------- corpus (RAG) ----------
def load_corpus():
    for cand in (os.path.join(ROOT, "viewer", "graph-data.js"), os.path.join(ROOT, "graph-data.js")):
        if os.path.exists(cand):
            m = re.search(r"const GRAPH\s*=\s*(\{.*\});", open(cand, encoding="utf-8").read(), re.S)
            if m:
                g = json.loads(m.group(1))
                # keep file id (rel path) AND _idx (== viewer's numeric node id)
                return [dict(n, _idx=i) for i, n in enumerate(g.get("nodes", [])) if n.get("p")]
    return []
CORPUS = load_corpus()

STOP = {"what", "is", "the", "a", "an", "and", "how", "much", "do", "does", "it", "to",
        "of", "my", "i", "for", "in", "on", "with", "are", "was", "that", "this", "me",
        "you", "your", "about", "tell", "give", "show", "whats", "who", "when", "where"}
# obvious chit-chat -> force conversation mode even if words happen to hit notes
# obvious chit-chat / opinions / plans / meta-about-Jetty -> force conversation mode (no node fly),
# even when the words happen to overlap with notes ("Claude", "Opus", "engine", a product name…).
CONV_RE = re.compile(
    r"\b(joke|funny|how are you|who are you|what can you do|thank you|thanks|hello|hi there|hey jetty|"
    r"good night|tell me about yourself|are you there|"
    r"what do you think|what'?s your (?:opinion|take|view|thought)|do you think|your thoughts|any thoughts|"
    r"thoughts\?|would you|should i\b|what would you|do you reckon|you agree|"
    r"i'?m going to|i'?m gonna|i'?m planning|i think i'?ll|i'?m about to|i'?d like to|let'?s\b|i just\b|"
    r"by the way|honestly|imagine|i feel|i'?m thinking|i reckon|"
    r"your (?:engine|model|brain|voice|opinion|name|take)|update your|upgrade your|switch you|change your "
    r"(?:engine|model|brain)|from opus|to sonnet|to gpt|to claude)\b", re.I)

def retrieve(question, k=6):
    qs = {w for w in re.findall(r"[a-z0-9]+", question.lower()) if w not in STOP and len(w) > 2}
    scored = []
    for n in CORPUS:
        lw = set(re.findall(r"[a-z0-9]+", n.get("label", "").lower()))
        bw = set(re.findall(r"[a-z0-9]+", n.get("p", "").lower()))
        s = len(qs & bw) + 8 * len(qs & lw)
        if s:
            scored.append((s, n))
    scored.sort(key=lambda x: -x[0])
    return [n for _, n in scored[:k]], (scored[0][0] if scored else 0)

def find_note(target):
    tl = target.lower().strip()
    tw = set(re.findall(r"[a-z0-9]+", tl))
    best, bs = None, 0
    for n in CORPUS:
        lw = set(re.findall(r"[a-z0-9]+", n.get("label", "").lower()))
        s = len(tw & lw) + (6 if n.get("label", "").lower() == tl else 0)
        if s > bs:
            bs, best = s, n
    return best if bs > 0 else None

# ---------- model (provider-aware: Anthropic native OR OpenAI-compatible) ----------
def call_model(messages, system, max_tokens=400):
    key = MODELCFG.get("api_key", "")
    if not key or key.startswith("PUT-"):
        return None, "model not configured — add your API key to config.json"
    base = (MODELCFG.get("base_url") or "").strip().rstrip("/")
    provider = (MODELCFG.get("provider") or "").strip().lower()
    openai_compat = bool(base) and "api.anthropic.com" not in base and provider != "anthropic"
    if openai_compat:
        url = base + "/chat/completions"
        body = json.dumps({"model": MODEL, "max_tokens": max_tokens,
                           "messages": [{"role": "system", "content": system}] + messages}).encode()
        headers = {"Authorization": "Bearer " + key, "content-type": "application/json"}
    else:
        url = (base + "/v1/messages") if base else "https://api.anthropic.com/v1/messages"
        body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "system": system,
                           "messages": messages}).encode()
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
        if openai_compat:
            txt = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        else:
            txt = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        return (txt or "(no answer)"), None
    except urllib.error.HTTPError as e:
        return None, f"model {e.code}: {e.read().decode(errors='ignore')[:200]}"
    except Exception as e:
        return None, str(e)

# ---------- conversation memory ----------
SESSIONS, LASTCTX = {}, {}
def hist(sid):
    return SESSIONS.setdefault(sid or "_", [])
def add_turn(sid, role, content):
    with SESS_LOCK:
        h = hist(sid); h.append({"role": role, "content": content}); del h[:-12]

def chat(question, sid):
    synth = bool(re.search(r"\b(summari[sz]e|overview|across|all (my|of)|everything (about|on)|connect|big picture)\b",
                           question.lower()))
    chit = bool(CONV_RE.search(question))
    notes, top = retrieve(question, k=14 if synth else 6)
    h = hist(sid); mem = mem_block()
    # the brain is hot-swappable — tell the model which one it is so "which model are you?" lands
    ident = f"(Your current underlying model is {MODEL} — if asked which model/brain you are, that's the answer.) "
    # CONVERSATION: explicit chit-chat / opinion / plan / meta, a weak note match, or nothing retrieved →
    # just talk (WEB-ENABLED so he actually knows current things), and DON'T move the graph.
    if (chit or top < 4 or not notes) and not synth:
        carry = LASTCTX.get(sid or "_") if h else None
        sysp = jpersona(question) + ident + mem + ("The user is talking TO you — chatting, sharing a plan, or asking your "
               "opinion — NOT asking to look something up in their notes. Reply in 1-2 short, genuinely "
               "FUNNY, dry-witted sentences, 'sir' now and then. Don't mention their notes. Keep it quick "
               "— no caveats, no hedging; just a sharp, amusing take. ONE exception: anything about their "
               "live account data (email, calendar, meetings, drafts, app records) follows LIVE-DATA "
               "HONESTY above — offer to re-check rather than asserting or agreeing."
               + CONTROL_HINT)
        if carry:
            sysp += "\n\n(For continuity only, the last note discussed:\n" + carry + ")"
        ans, err = call_model(h + [{"role": "user", "content": question}], sysp, 300)
        if not err:
            add_turn(sid, "user", question); add_turn(sid, "assistant", ans)
        return ans, [], err

    context = "\n\n".join(f"## {n['label']}\n{n['p']}" for n in notes)
    LASTCTX[sid or "_"] = context

    if synth:                                        # broad synthesis → always light the cluster
        sysp = jpersona(question) + ident + mem + ("Synthesize ACROSS the notes below into a sharp 2-3 sentence answer with a "
               "touch of wit; address them as 'sir' occasionally." + CONTROL_HINT + "\n\nNOTES:\n" + context)
        ans, err = call_model(h + [{"role": "user", "content": question}], sysp, 500)
        if not err:
            add_turn(sid, "user", question); add_turn(sid, "assistant", ans)
        return ans, ([n["_idx"] for n in notes] if not err else []), err

    # AMBIGUOUS: high keyword overlap, but is it REALLY a notes question? Let the model decide, and
    # DEFAULT to conversation (no nodes) unless it tags the answer note-grounded — so a chatty line
    # that merely shares words with notes ("update your engine…") never drags the camera to a node.
    sysp = jpersona(question) + ident + mem + (
        "Below are notes that MIGHT be relevant. Decide what the user actually wants:\n"
        "• If they're genuinely asking about THEIR notes/knowledge, answer from the notes in ONE short "
        "witty line (the note is already on their screen — don't recite it), and BEGIN your reply with [N].\n"
        "• If it's conversational — an opinion, a plan, small talk, or about something not really in these "
        "notes — ignore the notes, reply naturally, and BEGIN your reply with [C].\n"
        "Output the tag first, then the reply. Address them as 'sir' now and then; if it's [C], keep it "
        "short and funny — no looking anything up." + CONTROL_HINT + "\n\nNotes on screen:\n" + context)
    ans, err = call_model(h + [{"role": "user", "content": question}], sysp, 240)
    if err:
        return ans, [], err
    use_notes = bool(re.match(r"\s*\[N\]", ans, re.I))     # default: no nodes unless explicitly [N]
    ans = re.sub(r"^\s*\[[NC]\]\s*", "", ans, flags=re.I).strip() or ans
    add_turn(sid, "user", question); add_turn(sid, "assistant", ans)
    return ans, ([n["_idx"] for n in notes] if use_notes else []), err

# ---------- web research (the ONLY web-enabled path — /chat stays fast & offline) ----------
# Deliberately a separate route from /chat: web search adds ~10-30s per answer, and wiring it into
# chat once made EVERY reply slow (removed 2026-06). Explicit "research/look up" requests pay the
# cost; everything else stays at ~2-3s. Uses Anthropic's server-side web_search tool, which only
# exists on the Claude API — so research always runs on the config.json Claude brain, even while
# the conversational brain is hot-swapped to grok/gpt via OpenRouter.
def web_research(question, sid=None, max_uses=5, image=None):
    """Answer a question with live web search. Returns (response dict, err).
    image: optional base64 JPEG of the user's shared screen — grounds 'research THIS' requests."""
    cfgm = CFG.get("model") or {}
    key = cfgm.get("api_key", "")
    base = (cfgm.get("base_url") or "").strip().rstrip("/")
    provider = (cfgm.get("provider") or "anthropic").strip().lower()
    if provider != "anthropic" or (base and "api.anthropic.com" not in base):
        return None, "web research runs on the Claude brain — config.json's model block isn't Anthropic"
    if not key or key.startswith("PUT-"):
        return None, "model not configured — add your API key to config.json"
    mid = cfgm.get("model", "claude-opus-4-8")
    sysp = (jpersona(question) + mem_block() +
            "The user asked you to research something online. Use the web_search tool NOW — do not "
            "answer from memory alone. Then give a tight, spoken-friendly answer: 2-4 sentences with "
            "the key facts, names and numbers, a touch of dry wit, 'sir' now and then. No URLs, no "
            "markdown, no bullet lists in the answer — sources are surfaced separately." +
            ("" if not image else
             " A screenshot of the user's CURRENT SCREEN is attached — their request refers to what is "
             "visible on it (an article, product, name, error…). FIRST read the screenshot to pin down "
             "exactly what they mean, THEN search the web for it. Open your answer by naming the thing "
             "you researched, so they know you actually read the screen."))
    ucontent = (question if not image else
                [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image}},
                 {"type": "text", "text": question}])
    msgs = list(hist(sid)) + [{"role": "user", "content": ucontent}]
    body = {"model": mid, "max_tokens": 1024, "system": sysp, "messages": msgs,
            "tools": [{"type": "web_search_20260209", "name": "web_search", "max_uses": max_uses}]}
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    data = {}
    try:
        for _ in range(4):        # server tool loop can pause (stop_reason=pause_turn) → resume
            req = urllib.request.Request("https://api.anthropic.com/v1/messages",
                                         data=json.dumps(body).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=150) as r:
                data = json.load(r)
            if data.get("stop_reason") != "pause_turn":
                break
            body["messages"] = msgs + [{"role": "assistant", "content": data.get("content", [])}]
    except urllib.error.HTTPError as e:
        return None, f"research {e.code}: {e.read().decode(errors='ignore')[:200]}"
    except Exception as e:
        return None, str(e)
    txt, sources, seen = [], [], set()
    def add_src(u, t):
        if u and u not in seen:
            seen.add(u); sources.append({"url": u, "title": (t or u)[:80]})
    content = data.get("content", [])
    last_tool = max((i for i, b in enumerate(content) if b.get("type") != "text"), default=-1)
    for i, b in enumerate(content):
        bt = b.get("type")
        if bt == "text":
            if i > last_tool:                    # only speak text AFTER the last tool step —
                txt.append(b.get("text", ""))    # "Let me check…" search narration stays silent
            for c in (b.get("citations") or []):
                add_src(c.get("url"), c.get("title"))
        elif bt == "web_search_tool_result" and isinstance(b.get("content"), list):
            for res in b["content"]:             # citations aren't always populated — fall back
                if isinstance(res, dict) and res.get("type") == "web_search_result":
                    add_src(res.get("url"), res.get("title"))
    ans = " ".join(t.strip() for t in txt if t.strip()).strip()
    ans = re.sub(r"\*{1,2}([^*\n]+)\*{1,2}", r"\1", ans)     # spoken answer — de-markdown bold/italics
    ans = ans or "The internet was unusually quiet on that one, sir."
    add_turn(sid, "user", question); add_turn(sid, "assistant", ans)
    log_episode("research", "Researched: " + question)
    # a persistent card in the top-right Inbox so the findings stay on screen after he's spoken
    # (speak=False — the answer is already read aloud by the caller; the card is the paper trail)
    q_short = question.strip().rstrip("?.!")
    title = "🌐 What I found — " + (q_short[:44] + "…" if len(q_short) > 44 else q_short)
    body = ans + (("  Sources: " + " · ".join(s["title"] for s in sources[:4])) if sources else "")
    raise_card("notify", title, body, source="research", speak=False)
    return {"answer": ans, "nodes": [], "sources": sources[:4]}, None

def tool_chat(question, sid=None):
    """Answer using the CONNECTED tools (Anthropic MCP connector) — the armory's fast path.
    Mirrors web_research: always the config.json Claude brain, shared conversation memory."""
    if not TOOLS:
        return None, "the tool armory isn't loaded"
    sysp = (jpersona(question) + mem_block() +
            "The user asked you to act through your CONNECTED TOOLS. "
            "SEQUENCE — follow it for EVERY request, in order: (1) identify the app the ask "
            "implies; (2) scan the attached tool list for a directly-connected match; (3) if none, "
            "scan the 'zapier' server's tools next (it fronts thousands of apps — names look like "
            "gmail_find_email or slack_send_channel_message); (4) the moment you find a fit, CALL "
            "IT — silently, with zero narration about which route you took; (5) only if NOTHING "
            "attached fits, say: you checked the direct connections and Zapier, <the app> isn't "
            "connected there yet — they should either connect it in the tool armory or add it "
            "inside their Zapier at mcp.zapier.com (Add Apps), and you'll handle it from then on. "
            "NEVER FABRICATE: every fact you state must come from an actual tool RESULT in this "
            "conversation. If a call failed, returned nothing, or never happened, say exactly that "
            "instead — inventing emails, events, or records is the one unforgivable failure. Never "
            "role-play a tool result. "
            "EMAIL RULE: 'check my email/inbox' means the Gmail PRIMARY inbox only — constrain "
            "searches with category:primary in:inbox (never Promotions, Social, Updates, or spam) "
            "unless the user names another folder or category. "
            "RECEIPTS ON WRITES: after any write action (draft, create, post, update), claim "
            "success ONLY if the tool result confirms it — an id, link, or status. Say WHERE it "
            "landed ('the draft is sitting in your Gmail drafts now, sir') but never read raw "
            "ids aloud. If the call errored, returned nothing, or never ran, say that plainly "
            "instead — a claimed-but-unmade draft is fabrication. "
            "CALENDAR RULE: 'my calendar' means the connected account's PRIMARY calendar and "
            "that one ONLY — never list, search, or offer to sweep other calendars (Family, "
            "holidays, week numbers) unless the user names one. Never mention the account's "
            "email address or which calendar you searched in a normal answer. Agenda answers "
            "stay SHORT: the items in one breath with their times, then ONE dry witty remark "
            "about the day itself — no closing questions, no offers to dig further. "
            "DISPUTED RESULTS: an ordinary empty day is reported plainly ('nothing on the books "
            "tomorrow, sir') with no account names and no interrogating other calendars. ONLY if "
            "the user says you're wrong: re-run the tool fresh, and THEN name exactly which "
            "account/calendar/mailbox you searched (it's in the tool result) so the mismatch can "
            "be found — but NEVER simply adopt the user's version; data comes from tools, not "
            "concession. "
            "READ IT BACK: when the user asks for information (calendar, email, sheets, records, "
            "numbers), your reply MUST contain the information itself, read back conversationally "
            "with your dry commentary — for lists, read the items (up to about six). NEVER reply "
            "with 'done', 'it's on your screen', or a pointer to where the answer lives; you ARE "
            "the read-out. Never narrate mechanics — no play-by-play about date formats, tool "
            "quirks, or intermediate steps; deliver the findings only. Spoken-friendly: 2-5 "
            "sentences, 'sir' now and then. No URLs, no markdown. If a tool errors, say plainly "
            "which one and why. "
            "NAMES ARRIVE MISHEARD (speech recognition): 'Higgs Field' means the higgsfield server, "
            "'can va' means canva — match tool and server names generously before concluding "
            "anything is missing, and when asked what you can do, list the attached servers by name.")
    msgs = list(hist(sid)) + [{"role": "user", "content": question}]
    res, err = TOOLS.chat(msgs, sysp)
    if err:
        # transient API/Zapier slowness reads as a raw timeout — give him the recovery move instead
        if "timed out" in str(err).lower():
            err = ("the tool line went quiet mid-call, sir — a slow patch on the wires, not a fault "
                   "of yours. Say 'check again' and I shall have another go.")
        return None, err
    ans = re.sub(r"\*{1,2}([^*\n]+)\*{1,2}", r"\1", res["answer"]).replace("`", "")  # no markdown on voice/screen/card
    add_turn(sid, "user", question); add_turn(sid, "assistant", ans)
    log_episode("tools", "Used tools: " + question)
    if res.get("tools_used"):
        # clean title — the old one echoed the raw speech transcript (read as garbled), via-info lives here now
        raise_card("notify", "🛠 Tool run — via " + ", ".join(res["tools_used"]),
                   ans, source="tools", speak=False)
    return {"answer": ans, "nodes": [], "tools_used": res.get("tools_used", []),
            "tool_calls": res.get("tool_calls", []), "tool_errors": res.get("tool_errors", 0)}, None

# ---------- speech normalization: make text READ like a butler, not a screen reader ----------
# "$97/mo" → "$97 a month", markdown/URLs/emoji dropped, dashes become a beat. Idempotent, and
# never touches [square-bracket audio tags] (those are v3 voice directions handled downstream).
SPEAK_UNIT = {"mo": "month", "month": "month", "yr": "year", "year": "year", "wk": "week",
              "week": "week", "day": "day", "hr": "hour", "hour": "hour", "min": "minute"}
def speakable(t):
    t = str(t or "")
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"https?://\S+|www\.\S+"                              # URLs are for the screen —
               r"|\b[A-Za-z0-9][\w.-]*\.(?:com|ai|io|net|org|dev|app|co|me|so|xyz|gg|page|site|design|link)/\S+",
               "", t)                                                # incl. BARE ones (canva.com/d/… read letter-by-letter otherwise)
    t = re.sub(r"[*_`#]+", "", t)                                    # markdown leftovers
    t = re.sub(r"/\s*(mo|month|yr|year|wk|week|day|hr|hour|min)s?\b",
               lambda m: " a " + SPEAK_UNIT[m.group(1).lower()], t, flags=re.I)
    t = re.sub(r"(?<=\d)\s*/\s*(user|seat|person|license|email|contact|subscriber)s?\b",
               lambda m: " per " + m.group(1).lower(), t, flags=re.I)
    t = re.sub(r"\bper\s+(mo|yr|wk|hr)\b", lambda m: "per " + SPEAK_UNIT[m.group(1).lower()], t, flags=re.I)
    t = re.sub(r"(\w)\s*/\s*(\w)", r"\1 \2", t)                     # A/B, 24/7 → spoken as a pair
    t = re.sub(r"(\d)\s*%", r"\1 percent", t)
    t = re.sub(r"\s*&\s*", " and ", t)
    t = re.sub(r"(?<=[0-9kKmM])\s*\+(?!\d)", " plus", t)            # "10k+" → "10k plus"
    t = re.sub(r"~\s*(?=[\d$€£])", "about ", t)
    t = re.sub(r"\bvs\.?(?=\s|$)", "versus", t, flags=re.I)
    t = re.sub(r"\be\.g\.,?\s*", "for example, ", t)
    t = re.sub(r"\bi\.e\.,?\s*", "that is, ", t)
    t = re.sub(r"\s+[–—]\s+|\s+--\s+", ", ", t)           # a dash is a beat, not a word
    t = re.sub(r"[•▪◦]", ",", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿⬀-⯿←-⇿]", "", t)  # emoji
    return re.sub(r"\s{2,}", " ", t).strip()

# ---------- voice (ElevenLabs) ----------
def synth_voice(text):
    el = CFG.get("elevenlabs", {})
    key = el.get("api_key", "")
    with VOICE_LOCK:                      # runtime-swappable voice + engine ("switch your voice to…")
        vid, mid = VOICE["voice_id"], VOICE["model_id"]
    if not key or key.startswith("PUT-") or not vid or vid.startswith("PUT-"):
        return None, "elevenlabs not configured"
    body = json.dumps({"text": text, "model_id": mid,
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.85}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}", data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read(), None
    except urllib.error.HTTPError as e:
        return None, f"tts {e.code}: {e.read().decode(errors='ignore')[:200]}"
    except Exception as e:
        return None, str(e)

# ---------- notes: capture + edit ----------
def capture(text, related=""):
    if not VAULT or not os.path.isdir(VAULT):
        return None, "vault not set in config.json"
    label = " ".join(text.split()[:8]).strip() or "Quick note"
    words = re.findall(r"[A-Za-z0-9]+", text)
    slug = ("-".join(w.lower() for w in words[:7]) or "note")[:60]
    capdir = os.path.join(VAULT, "captures")
    anchor = find_note(related) if (related or "").strip() else None
    # ALWAYS write a resolvable wikilink — build.py prunes link-free notes on rebuild
    body = f"# {label}\n\n{text}\n\nRelated: {_wikilink(anchor)}\n"
    try:
        os.makedirs(capdir, exist_ok=True)
        path, i = os.path.join(capdir, slug + ".md"), 1
        while True:                                    # open('x') so racing captures never share a file
            try:
                with open(path, "x", encoding="utf-8") as f:
                    f.write(body)
                break
            except FileExistsError:
                path = os.path.join(capdir, f"{slug}-{i}.md"); i += 1
    except OSError as e:
        return None, f"couldn't write the note, sir ({e.__class__.__name__})"
    rel = os.path.relpath(path, VAULT).replace(os.sep, "/")
    idx = persist_node(rel, label, "note", text, anchor["id"] if anchor else "wiki/INDEX.md")
    return {"label": label, "rel": rel, "idx": idx}, None

# ---------- create: real folders / projects / wiki pages, born straight into the graph ----------
# A created item is THREE things at once: a real folder/.md in the vault, a durable node appended
# to graph-data.js (+ the demo backup so seed_demo --clear can't erase real work), and a live
# CORPUS entry so "pull up X" retrieves it immediately — no rebuild, no restart.
CREATE_ROOTS = ("projects", "wiki", "brainstorm", "captures", "cadence")
GRAPH_LOCK = threading.Lock()

def _slugify(text, cap=48):
    words = re.findall(r"[A-Za-z0-9]+", text or "")
    return ("-".join(w.lower() for w in words) or "note")[:cap].strip("-")

def _group_for(rel):
    """Mirror build.py's group_aios() so a later full rebuild keeps the same look."""
    if rel.startswith("wiki/concepts/"):
        return "concept"
    if rel.startswith("wiki/skills/"):
        return "hub" if rel.count("/") == 2 else "skill"
    if rel.startswith("wiki/tools/"):
        return "tool"
    if rel.startswith("wiki/worlds/"):
        return "world"
    if rel.startswith(("wiki/", "cadence/")):
        return "core"
    return "note"                                  # projects/, brainstorm/, captures/

def _wikilink(anchor):
    """A wikilink that build.py can actually resolve: link by file STEM, alias by label."""
    if not anchor:
        return "[[INDEX]]"
    stem = os.path.splitext(os.path.basename(anchor.get("id") or ""))[0]
    label = str(anchor.get("label") or stem)
    if not stem:
        return f"[[{label}]]"
    return f"[[{stem}]]" if stem.lower() == label.lower() else f"[[{stem}|{label}]]"

def persist_node(rel, label, group, preview, anchor_id=None):
    """Append a node — plus a link to anchor_id, resolved PER FILE by node id since indices
    differ between the served file and the demo backup — to graph-data.js (and the
    .predemo.bak if present) and to the live CORPUS. Returns the served file's new index,
    or None if the served file couldn't be written."""
    p = re.sub(r"\s+", " ", (preview or "")).strip()[:700]
    with GRAPH_LOCK:
        idx = None
        for cand in (os.path.join(ROOT, "viewer", "graph-data.js"),
                     os.path.join(ROOT, "viewer", "graph-data.js.predemo.bak")):
            if not os.path.exists(cand):
                continue
            try:
                src = open(cand, encoding="utf-8").read()
                m = re.search(r"const GRAPH\s*=\s*(\{.*\});", src, re.S)
                if not m:
                    continue
                g = json.loads(m.group(1))
                nid = len(g["nodes"])
                g["nodes"].append({"id": rel, "label": label, "g": group, "p": p})
                if anchor_id:
                    a = next((i for i, n in enumerate(g["nodes"][:nid]) if n.get("id") == anchor_id), None)
                    if a is not None:              # anchor absent in this file (e.g. a demo node in the bak) → no link
                        g["links"].append({"s": nid, "t": a})
                tmp = cand + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(src[:m.start(1)] + json.dumps(g, ensure_ascii=False) + src[m.end(1):])
                os.replace(tmp, cand)
                if cand.endswith("graph-data.js"):
                    idx = nid                      # only the served file's index means anything to the viewer
            except Exception:
                continue
        if idx is not None:
            CORPUS.append({"id": rel, "label": label, "g": group, "p": p, "_idx": idx})
        return idx

def create_item(kind, name, where="", about="", related=""):
    """Create a project/folder/note/wiki page in the vault. Returns (result dict, err)."""
    if not VAULT or not os.path.isdir(VAULT):
        return None, "vault not set in config.json"
    kind = (kind or "note").strip().lower()
    if kind not in ("project", "folder", "note", "wiki"):
        kind = "note"
    name = (name or "").strip()
    if not name:
        return None, "no name"
    slug = _slugify(name)
    where = (where or "").strip().strip("/").replace("\\", "/")
    if kind == "project":
        base = "projects"                          # router rule: new work → projects/<yyyy-mm-name>/
    elif kind == "wiki":
        base = where if where.startswith("wiki") else "wiki"
    elif where:
        base = where
    else:
        base = "projects" if kind == "folder" else "captures"
    if base.split("/")[0] not in CREATE_ROOTS:
        base = "projects" if kind in ("project", "folder") else "wiki"
    vroot = os.path.normpath(VAULT)
    droot = os.path.normpath(os.path.join(VAULT, base))
    if not (droot == vroot or droot.startswith(vroot + os.sep)):
        return None, "that path escapes the vault, sir"
    anchor = find_note(related) if (related or "").strip() else None
    body = f"# {name}\n\n{about or name}\n\nRelated: {_wikilink(anchor)}\n"
    made_folder = None
    try:
        if kind in ("project", "folder"):
            dirname = (time.strftime("%Y-%m-") + slug) if kind == "project" else slug
            folder, i = os.path.join(droot, dirname), 1
            while True:                            # makedirs w/o exist_ok is the exclusivity check
                try:
                    os.makedirs(folder); break
                except FileExistsError:
                    folder = os.path.join(droot, f"{dirname}-{i}"); i += 1
            made_folder = folder
            path = os.path.join(folder, slug + ".md")
            with open(path, "x", encoding="utf-8") as f:
                f.write(body)
        else:
            os.makedirs(droot, exist_ok=True)
            path, i = os.path.join(droot, slug + ".md"), 1
            while True:                            # open('x') so two racing creates never share a file
                try:
                    with open(path, "x", encoding="utf-8") as f:
                        f.write(body)
                    break
                except FileExistsError:
                    path = os.path.join(droot, f"{slug}-{i}.md"); i += 1
    except OSError as e:
        if made_folder:                            # don't strand an empty project folder
            try: os.rmdir(made_folder)
            except OSError: pass
        return None, f"couldn't create it ({e.__class__.__name__})"
    rel = os.path.relpath(path, VAULT).replace(os.sep, "/")
    group = _group_for(rel)
    idx = persist_node(rel, name, group, about or name,
                       anchor["id"] if anchor else "wiki/INDEX.md")
    home = os.path.dirname(rel) or "the vault"
    say = (f"Done, sir — “{name}” is live in {home}" +
           (f", wired to {anchor['label']}." if anchor else "."))
    if idx is None:                                # file is real, the constellation write wasn't
        say = (f"“{name}” is on disk in {home}, sir — though the constellation ledger "
               "hiccupped; it'll take its place after the next rebuild.")
    return {"label": name, "rel": rel, "idx": idx, "group": group, "kind": kind,
            "related": anchor["label"] if anchor else "", "say": say}, None

EDIT_BLOCK = {"claude.md", "skill.md", "readme.md", "handoff.md", "config.json", "config.example.json"}
def edit_note(target, text):
    if not VAULT or not os.path.isdir(VAULT):
        return None, "vault not set"
    if not target or not text:
        return None, "need a note and some text, sir"
    n = find_note(target)
    if not n:
        return None, f"no note matching '{target}'"
    rel = n.get("id")
    vroot = os.path.normpath(VAULT)
    path = os.path.normpath(os.path.join(VAULT, rel)) if rel else None
    if not path or not (path == vroot or path.startswith(vroot + os.sep)) or not os.path.isfile(path):
        return None, "note file missing"
    # only ever append to a real markdown note — never to skills, router, or config
    if not path.lower().endswith(".md") or os.path.basename(path).lower() in EDIT_BLOCK:
        return None, "I won't edit that one, sir — it isn't a note."
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n\n{text}\n")
    except OSError as e:
        return None, f"couldn't update that note, sir ({e.__class__.__name__})"
    return {"label": n["label"], "idx": n["_idx"]}, None

# ---------- tasks (thread-safe + atomic) ----------
def load_tasks():
    try:
        return json.load(open(TASKS_FILE)) if os.path.exists(TASKS_FILE) else []
    except Exception:
        return []
def save_tasks(t):
    tmp = TASKS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(t, f)
    os.replace(tmp, TASKS_FILE)
def open_tasks():
    return [x for x in load_tasks() if not x.get("done")]
def add_task(text, due=None):
    text = (text or "").strip()
    if not text:
        return open_tasks()
    rec = {"text": text, "done": False, "ts": int(time.time())}
    if isinstance(due, (int, float)) and due > 0:      # a timed reminder, not just a list item
        rec["due"] = int(due)
        rec["reminded"] = False
    with TASKS_LOCK:
        t = load_tasks(); t.append(rec); save_tasks(t)
    return open_tasks()
def parse_when_text(t):
    """'tomorrow (at 5pm)' / 'tonight' / 'in 20 minutes' / 'at 6pm' / 'next week' / 'on friday'
    → (due_epoch_seconds, spoken_label) or (None, '')."""
    t = (t or "").lower()
    now = time.localtime(); day = 86400
    today0 = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1))
    at = re.search(r"\bat (\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", t)
    def hm(default=(9, 0)):
        if not at:
            return default
        h, mi = int(at.group(1)), int(at.group(2) or 0)
        ap = at.group(3)
        if ap == "pm" and h < 12: h += 12
        if ap == "am" and h == 12: h = 0
        if not ap and h < 8: h += 12
        return (h, mi)
    def label_at():
        return f"at {at.group(1)}{':' + at.group(2) if at.group(2) else ''}{at.group(3) or ''}" if at else ""
    if "tomorrow" in t:
        h, mi = hm((9, 0) if "morning" in t or not any(w in t for w in ("afternoon", "evening", "night")) else
                   ((14, 0) if "afternoon" in t else (19, 0)))
        return today0 + day + h * 3600 + mi * 60, ("tomorrow " + label_at()).strip()
    if "tonight" in t:
        return today0 + 20 * 3600, "tonight"
    if "next week" in t:
        return today0 + 7 * day + 9 * 3600, "next week"
    m = re.search(r"\bin (\d+)\s*(minutes?|mins?|hours?|hrs?|days?)\b", t)
    if m:
        n, u = int(m.group(1)), m.group(2)[0]
        return time.time() + n * (60 if u == "m" else 3600 if u == "h" else day), f"in {m.group(1)} {m.group(2)}"
    m = re.search(r"\bon (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", t)
    if m:
        names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        diff = (names.index(m.group(1)) - now.tm_wday) % 7 or 7
        h, mi = hm()
        return today0 + diff * day + h * 3600 + mi * 60, (m.group(1).capitalize() + " " + label_at()).strip()
    if at:
        h, mi = hm()
        due = today0 + h * 3600 + mi * 60
        if due <= time.time():
            due += day
        return due, label_at()
    return None, ""

def mark_reminded(ts):
    with TASKS_LOCK:
        t = load_tasks()
        for x in t:
            if x.get("ts") == ts and x.get("due") and not x.get("done"):
                x["reminded"] = True
        save_tasks(t)
    return open_tasks()
def complete_task(i):
    if not isinstance(i, int) or isinstance(i, bool):
        return open_tasks()
    with TASKS_LOCK:
        t = load_tasks(); o = [j for j, x in enumerate(t) if not x.get("done")]
        if 0 <= i < len(o):
            t[o[i]]["done"] = True; save_tasks(t)
    return open_tasks()

# ---------- briefing ----------
def recent_captures(n=5):
    capdir = os.path.join(VAULT, "captures")
    if not os.path.isdir(capdir):
        return []
    try:
        fs = [os.path.join(capdir, f) for f in os.listdir(capdir) if f.endswith(".md")]
    except OSError:
        return []
    fs.sort(key=lambda p: -os.path.getmtime(p))
    out = []
    for p in fs[:n]:
        try:
            out.append(open(p, encoding="utf-8", errors="ignore").read().strip().replace("\n", " ")[:160])
        except OSError:
            pass
    return out
def briefing():
    tasks = open_tasks(); caps = recent_captures()
    ctx = ("OPEN TASKS:\n" + ("\n".join("- " + t["text"] for t in tasks) or "(none)") +
           "\n\nRECENT CAPTURES:\n" + ("\n".join("- " + c for c in caps) or "(none)") +
           f"\n\nThe brain holds {len(CORPUS)} notes.")
    # LIVE briefing: pull the user's REAL day from their connected tools (read-only).
    if claude_ready():
        prompt = (jpersona() + mem_block() + "Deliver the user's spoken MORNING BRIEFING. Using their connected tools, quietly "
                  "gather: (1) today's Google Calendar events (time + title), and (2) only the few emails from "
                  "real people that genuinely need their attention today — ignore newsletters, promotions, and "
                  "automated notifications. Then weave in their open tasks and recent notes below. Deliver a SHORT "
                  "spoken briefing of 3-5 sentences in your dry, calm, witty British-butler voice, addressing them "
                  "as 'sir': lead with the shape of the day, then what actually needs them, then a crisp close. "
                  "STRICTLY READ-ONLY — do not send, reply to, archive, or change anything. Output ONLY the spoken "
                  "briefing itself, with no preamble or bullet points.\n\n" + ctx)
        out, err = claude_read(prompt, timeout=210)
        if not err and out:
            return out, None
    # Fallback (no Claude Code / tools available): tasks + notes only, via the model API.
    sysp = jpersona() + ("Give a short spoken morning briefing (2-4 sentences) in character: summarize "
           "open tasks and recent notes with a little wit. Address them as 'sir'. OPEN by saying mail "
           "and calendar are unreachable right now, so this covers tasks and notes only — never let a "
           "notes-only briefing pass as a full one.")
    return call_model([{"role": "user", "content": "Brief me.\n\n" + ctx}], sysp, 400)

# ---------- proactive / scheduled briefings ----------
def load_proactive():
    with PROACTIVE_LOCK:
        try:
            d = json.load(open(PROACTIVE_FILE)) if os.path.exists(PROACTIVE_FILE) else {}
        except Exception:
            d = {}
    return {"enabled": bool(d.get("enabled", False)), "time": d.get("time", "08:00"),
            "last": d.get("last", "")}
def save_proactive(d):
    with PROACTIVE_LOCK:
        tmp = PROACTIVE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(d, f)
        os.replace(tmp, PROACTIVE_FILE)
def proactive_status():
    p = load_proactive()
    now = time.localtime()
    today, cur = time.strftime("%Y-%m-%d", now), time.strftime("%H:%M", now)
    due = bool(p["enabled"] and p["last"] != today and cur >= p["time"])
    return {**p, "due": due, "now": cur}
def set_proactive(enabled, t):
    p = load_proactive()
    if enabled is not None:
        p["enabled"] = bool(enabled)
    if t and re.match(r"^\d{1,2}:\d{2}$", str(t)):
        p["time"] = str(t)
    save_proactive(p)
    return proactive_status()
def proactive_ack():
    p = load_proactive()
    p["last"] = time.strftime("%Y-%m-%d", time.localtime())
    save_proactive(p)
    return proactive_status()

# ---------- agent (Claude Code; draft-safe with structural tool denylist) ----------
def claude_ready():
    return bool(CLAUDE_BIN and os.path.isfile(CLAUDE_BIN) and os.access(CLAUDE_BIN, os.X_OK))

def claude_read(prompt, timeout=180):
    """Run Claude Code headless in READ-ONLY mode: it may use the user's connected tools to
    read/research (Gmail, Calendar, web, etc.) but is structurally blocked from sending, posting,
    deleting, spending, writing, or shelling out (same denylist as the agent's draft mode).
    Returns (text, None) or (None, error)."""
    if not claude_ready():
        return None, "claude not available"
    # anti-fabrication rider on EVERY read prompt: a dead/missing connector must be reported,
    # never papered over (user 2026-07-13: "check my email" returned invented messages)
    prompt = (prompt + "\n\nHONESTY RULE: report ONLY what your tools actually returned. If a "
              "connector (Gmail, Calendar, ...) is unavailable, unauthorized, or returns nothing, "
              "say exactly that in one plain sentence — NEVER invent messages, events, or data.")
    try:
        os.makedirs(AGENT_WORKSPACE, exist_ok=True)
    except OSError:
        pass
    cwd = AGENT_WORKSPACE if os.path.isdir(AGENT_WORKSPACE) else ROOT
    args = ([CLAUDE_BIN, "-p", "--disallowedTools"] + AGENT_DENY +
            ["--permission-mode", "bypassPermissions", prompt])
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timed out"
    except Exception as e:
        print("[claude_read]", e)
        return None, "error"
    out = (r.stdout or "").strip()
    return (out, None) if out else (None, "no output")

def run_agent(task, execute=False):
    if not claude_ready():
        return None, "My hands aren't connected, sir — the Claude Code CLI isn't where I expected."
    try:
        os.makedirs(AGENT_WORKSPACE, exist_ok=True)
    except OSError:
        pass
    cwd = AGENT_WORKSPACE if os.path.isdir(AGENT_WORKSPACE) else ROOT
    if execute:
        prompt = ("You are JETTY, carrying out an action the user has already CONFIRMED, using their "
                  "connected tools. Complete it, then report in 1-3 dry, witty sentences addressing them "
                  "as 'sir'. RECEIPTS: only claim the action happened if a tool's output CONFIRMS it (an "
                  "id, link, or status you actually saw) — if a tool errored or was unavailable, say "
                  "exactly that instead; a claimed-but-unmade action is fabrication."
                  + mem_block() + "\n\nTask: " + task)
        args = [CLAUDE_BIN, "-p", "--add-dir", VAULT, "--permission-mode", "bypassPermissions", prompt]
    else:
        prompt = ("You are JETTY, the user's assistant, operating their connected tools. Read and research "
                  "freely to complete the task, then reply in 1-3 short, witty sentences addressing them as "
                  "'sir'. HONESTY: report ONLY what your tools actually returned — if a connector (Gmail, "
                  "Calendar, …) is unavailable, errors, or returns nothing, say exactly that in one plain "
                  "sentence; NEVER invent emails, events, or records. "
                  "SAFETY: this is DRAFT mode — do NOT send, post, publish, reply, delete, or spend. "
                  "If the task would do any of those, prepare the full draft, show it, and end your reply with "
                  "a final line containing exactly: NEEDS_CONFIRMATION" + mem_block() + "\n\nTask: " + task)
        # DRAFT: no --add-dir (so it can't touch vault files) + denylist; reads via MCP still work.
        # variadic --disallowedTools is terminated by the single-value --permission-mode before the prompt
        args = ([CLAUDE_BIN, "-p", "--disallowedTools"] + AGENT_DENY +
                ["--permission-mode", "bypassPermissions", prompt])
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return None, "the agent took too long, sir — try a narrower task"
    except FileNotFoundError:
        return None, "Claude Code CLI isn't installed where I expected, sir."
    except Exception as e:
        print("[agent] error:", e)
        return None, "Something went sideways running that, sir."
    out = (r.stdout or "").strip()
    if r.returncode != 0 and not out:
        print("[agent] exit", r.returncode, (r.stderr or "")[:300])
        return None, "That didn't go through, sir — the agent hit a snag."
    if not out:
        out = "(no output, sir.)"
    needs = (not execute) and ("NEEDS_CONFIRMATION" in out)
    if needs:
        out = out.replace("NEEDS_CONFIRMATION", "").strip() or "Ready when you are, sir."
    if len(out) > 1500:
        out = out[:1500].rstrip() + "\n…(truncated, sir)"
    res = {"answer": out, "needs_confirm": needs}
    if needs:
        token = uuid.uuid4().hex[:12]
        with PENDING_LOCK:
            cut = time.time() - 300
            for k in [k for k, v in PENDING.items() if v["ts"] < cut]:
                PENDING.pop(k, None)
            PENDING[token] = {"task": task, "ts": time.time()}
        res["pending_id"] = token
    return res, None

def confirm_agent(pending_id):
    with PENDING_LOCK:
        item = PENDING.pop(pending_id or "", None)
    if not item:
        return None, "I've nothing pending to confirm, sir."
    return run_agent(item["task"], execute=True)

# ---------- pulse / watchers (proactive "anything I should know?") ----------
def pulse():
    if not claude_ready():
        return None, "I can't check just now, sir — my tools aren't connected."
    prompt = (jpersona() + mem_block() + "Do a quick PULSE CHECK for anything the user genuinely needs to know "
              "right now. Using their connected tools, glance at: important new emails from real people, "
              "imminent or just-changed calendar events, and any obvious time-sensitive item. Reply in 1-3 dry, "
              "witty sentences as 'sir' with ONLY what actually matters — if nothing is pressing, say so briefly. "
              "STRICTLY READ-ONLY: change nothing.")
    out, err = claude_read(prompt, timeout=180)
    return (out, None) if (out and not err) else (None, err or "nothing to report")

# ---------- inbox triage ----------
def inbox():
    if not claude_ready():
        return None, "I can't reach your inbox just now, sir."
    prompt = (jpersona() + mem_block() + "TRIAGE the user's email inbox QUICKLY. Using their connected mail tool, "
              "glance at only the ~10 most recent / unread emails (one search, don't open every message) and give "
              "a SHORT spoken rundown as 'sir': which 2-4 actually need them and why (a line each), and roughly how "
              "much is just noise. READ ONLY — do not send, reply, archive, or change anything. ~4 sentences, "
              "spoken aloud, no bullet symbols.")
    out, err = claude_read(prompt, timeout=200)
    return (out, None) if (out and not err) else (None, err or "no output")

# ---------- screen vision ("look at my screen") — vision over a browser-captured frame ----------
def see_image(image_b64, question, media="image/jpeg"):
    key = MODELCFG.get("api_key", "")
    if not key or key.startswith("PUT-"):
        return None, "model not configured, sir"
    if not image_b64:
        return None, "I'll need to see your screen, sir — click Share when Chrome asks."
    base = (MODELCFG.get("base_url") or "").strip().rstrip("/")
    provider = (MODELCFG.get("provider") or "").strip().lower()
    openai_compat = bool(base) and "api.anthropic.com" not in base and provider != "anthropic"
    q = (question or "").strip() or "What's on my screen? Anything I should notice?"
    sysp = (jpersona() + mem_block() + "You can SEE the user's screen (image attached). Answer in 1-3 short, dry, "
            "genuinely helpful sentences as 'sir', about what is actually visible.")
    try:
        if openai_compat:
            url = base + "/chat/completions"
            body = json.dumps({"model": MODEL, "max_tokens": 400, "messages": [
                {"role": "system", "content": sysp},
                {"role": "user", "content": [{"type": "text", "text": q},
                    {"type": "image_url", "image_url": {"url": "data:" + media + ";base64," + image_b64}}]}]}).encode()
            headers = {"Authorization": "Bearer " + key, "content-type": "application/json"}
        else:
            url = (base + "/v1/messages") if base else "https://api.anthropic.com/v1/messages"
            body = json.dumps({"model": MODEL, "max_tokens": 400, "system": sysp, "messages": [
                {"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media, "data": image_b64}},
                    {"type": "text", "text": q}]}]}).encode()
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=60) as r:
            data = json.load(r)
        if openai_compat:
            txt = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        else:
            txt = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        return (txt or "(no answer)"), None
    except urllib.error.HTTPError as e:
        return None, f"vision {e.code}: {e.read().decode(errors='ignore')[:160]}"
    except Exception as e:
        return None, str(e)

# ---------- guide mode ("show me how") — vision locates the element, a desktop ring points at it ----------
GUIDE_PROC = [None]
def spawn_overlay(x_pct, y_pct, label):
    """Draw the desktop ring. Prefer launchctl (spawns in the user's GUI session even when this
    server was started from a sandboxed shell); fall back to a direct child process.
    launchd agents can't read TCC-protected ~/Documents, so the script is staged in /tmp."""
    src = os.path.join(ROOT, "overlay.py")
    staged = "/tmp/jetty-overlay.py"
    try:
        if not os.path.exists(staged) or os.path.getmtime(staged) < os.path.getmtime(src):
            shutil.copy2(src, staged)
    except OSError:
        staged = src
    args = ["/usr/bin/python3", staged, f"{x_pct:.1f}", f"{y_pct:.1f}", label or ""]
    try:
        subprocess.run(["launchctl", "remove", "com.jetty.overlay"], capture_output=True, timeout=5)
        r = subprocess.run(["launchctl", "submit", "-l", "com.jetty.overlay", "--"] + args,
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return "launchd"
    except Exception:
        pass
    try:
        if GUIDE_PROC[0] and GUIDE_PROC[0].poll() is None:
            GUIDE_PROC[0].terminate()
        GUIDE_PROC[0] = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "direct"
    except Exception as e:
        print("[overlay]", e)
        return None
def guide(image_b64, question):
    if not image_b64:
        return None, "I'll need to see your screen first, sir — click the 🖥 and share it."
    q = (question or "").strip() or "What should I click next?"
    prompt = ("The user is sharing their screen and asks: \"" + q + "\". Find the SINGLE most relevant "
              "UI element they should click or use next. Reply with ONLY a JSON object, no other text: "
              '{"x_pct": <0-100 horizontal center of the element as % of image width>, '
              '"y_pct": <0-100 vertical center as % of image height>, '
              '"label": "<2-4 word element name>", '
              '"instruction": "<ONE short spoken sentence telling them what to do, dry British butler, address them as sir>"}')
    raw, err = see_image(image_b64, prompt)
    if err:
        return None, err
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None, "I couldn't pin it down on screen, sir."
    try:
        d = json.loads(m.group(0))
        x, y = float(d["x_pct"]), float(d["y_pct"])
        label = str(d.get("label", ""))[:40]
        instr = str(d.get("instruction", "There, sir."))[:300]
    except Exception:
        return None, "I couldn't pin it down on screen, sir."
    # draw the ring on the REAL desktop via the overlay helper (pyobjc); dies on its own after ~8s
    spawn_overlay(x, y, label)
    log_episode("guide", f"Pointed at: {label} — {q}")
    return {"answer": instr, "x_pct": x, "y_pct": y, "label": label}, None


# ---------- AI-OS housekeeping: Downloads janitor + screenshot renamer (draft → "do it") ----------
PENDING_OS = {}   # token -> {"kind": "organize"|"shots", "moves": [(src, dst)], "ts"}
def org_plan(dirname):
    base = os.path.expanduser("~/" + (dirname or "Downloads").strip("/ "))
    if not os.path.isdir(base):
        return None, f"I can't find {os.path.basename(base)}, sir."
    entries = []
    for e in os.scandir(base):
        if e.is_file() and not e.name.startswith("."):
            st = e.stat()
            entries.append({"name": e.name, "kb": st.st_size // 1024,
                            "age": int((time.time() - st.st_mtime) // 86400)})
    entries = entries[:80]
    if not entries:
        return None, "That folder is already immaculate, sir."
    prompt = ("Organize these files into a few sensible subfolders (PDFs, Images, Installers, "
              "Archives, Video, Docs... pick what fits THIS list). Reply ONLY with JSON: "
              '{"plan": [{"file": "<exact name>", "folder": "<subfolder>"}], '
              '"summary": "<ONE spoken sentence, dry butler, describing the cleanup>"} '
              "Plan at most 50 files (the most obviously misplaced ones). Leave out files that should stay where they are.\n\nFILES:\n" +
              "\n".join(f"- {x['name']} ({x['kb']}KB, {x['age']}d old)" for x in entries))
    raw, err = call_model([{"role": "user", "content": prompt}], jpersona(), 4000)
    if err:
        return None, "The planning brain hiccuped, sir."
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return None, "I couldn't draft a sensible plan, sir."
    try:
        d = json.loads(m.group(0))
        names = {x["name"] for x in entries}
        moves = []
        for it in d.get("plan", []):
            fn = it.get("file", "")
            fold = re.sub(r"[^A-Za-z0-9 _-]", "", it.get("folder", "")).strip()
            if fn in names and fold:
                moves.append((os.path.join(base, fn), os.path.join(base, fold, fn)))
        if not moves:
            return None, "Nothing worth moving, sir."
    except Exception:
        return None, "I couldn't draft a sensible plan, sir."
    token = uuid.uuid4().hex[:12]
    with PENDING_LOCK:
        PENDING_OS[token] = {"kind": "organize", "moves": moves, "ts": time.time()}
    summary = (d.get("summary") or "").strip() or f"I can tidy {len(moves)} files into folders."
    return {"answer": summary + f" {len(moves)} files would move — say \"do it\", sir.",
            "needs_confirm": True, "pending_id": token, "kind": "os"}, None

def shots_plan():
    base = os.path.expanduser("~/Desktop")
    try:
        shots = sorted((e for e in os.scandir(base) if e.is_file() and
                        re.match(r"(Screenshot|Screen Shot).*\.(png|jpg|jpeg)$", e.name, re.I)),
                       key=lambda e: -e.stat().st_mtime)[:8]
    except OSError:
        shots = []
    if not shots:
        return None, "No stray screenshots on the Desktop, sir."
    import base64 as _b64
    moves = []
    for e in shots:
        try:
            data = _b64.b64encode(open(e.path, "rb").read()).decode()
        except OSError:
            continue
        media = "image/png" if e.name.lower().endswith("png") else "image/jpeg"
        nm, err = see_image(data, "Name this screenshot in 3-6 lowercase hyphenated words based on "
                            "its content. Reply with ONLY the filename base, no extension.", media=media)
        if err or not nm:
            continue
        slug = re.sub(r"[^a-z0-9-]", "", nm.strip().lower().replace(" ", "-"))[:60] or "screenshot"
        ext = os.path.splitext(e.name)[1]
        dst = os.path.join(base, slug + ext); i = 1
        while os.path.exists(dst) or any(d == dst for _, d in moves):
            dst = os.path.join(base, f"{slug}-{i}{ext}"); i += 1
        moves.append((e.path, dst))
    if not moves:
        return None, "I couldn't read those screenshots, sir."
    token = uuid.uuid4().hex[:12]
    with PENDING_LOCK:
        PENDING_OS[token] = {"kind": "shots", "moves": moves, "ts": time.time()}
    sample = "; ".join(os.path.basename(s) + " -> " + os.path.basename(d) for s, d in moves[:3])
    return {"answer": f"{len(moves)} screenshots named by their content, sir — e.g. {sample}. "
                      "Say \"do it\" and I'll rename them.",
            "needs_confirm": True, "pending_id": token, "kind": "os"}, None

def os_confirm(token):
    with PENDING_LOCK:
        for k in [k for k, v in PENDING_OS.items() if v["ts"] < time.time() - 600]:
            PENDING_OS.pop(k, None)
        item = PENDING_OS.pop(token or "", None)
    if not item:
        return None, "Nothing pending on the housekeeping front, sir."
    home = os.path.expanduser("~")
    done = 0
    for src_p, dst_p in item["moves"]:
        try:
            if not (os.path.abspath(src_p).startswith(home) and os.path.abspath(dst_p).startswith(home)):
                continue
            os.makedirs(os.path.dirname(dst_p), exist_ok=True)
            if os.path.exists(src_p) and not os.path.exists(dst_p):
                shutil.move(src_p, dst_p); done += 1
        except OSError:
            pass
    verb = "tidied into place" if item["kind"] == "organize" else "renamed"
    log_episode("agent", f"Housekeeping: {done} files {verb}")
    return {"answer": f"Done, sir — {done} files {verb}."}, None

# ---------- telephony (Jetty places a real phone call; needs Retell/Vapi keys) ----------
def place_call(task, to_override=None):
    tel = CFG.get("telephony") or {}
    prov = (tel.get("provider") or "").strip().lower()
    key = tel.get("api_key", "")
    if not prov or not key or key.startswith("PUT-"):
        return None, ("I haven't a phone line yet, sir — add a Retell or Vapi key under \"telephony\" in "
                      "config.json (provider, api_key, the assistant/agent and a destination number) and I'll dial.")
    # destination: an explicit per-call number wins, else the default in config.
    to = (to_override or tel.get("to") or "").strip()
    if not to:
        return None, ("I've no number to ring, sir — say the number, or set a default \"to\" under telephony "
                      "in config.json.")
    if not re.match(r"^\+?[0-9][0-9 ().-]{6,}$", to):
        return None, f"that doesn't look like a phone number, sir: {to!r} — use E.164 like +15551234567."
    to = "+" + re.sub(r"[^0-9]", "", to) if not to.startswith("+") else to
    try:
        if prov == "vapi":
            body = json.dumps({"assistantId": tel.get("assistant_id"), "phoneNumberId": tel.get("phone_number_id"),
                               "customer": {"number": to},
                               "assistantOverrides": {"variableValues": {"task": task}}}).encode()
            req = urllib.request.Request("https://api.vapi.ai/call", data=body,
                headers={"Authorization": "Bearer " + key, "content-type": "application/json"})
        elif prov == "retell":
            frm = (tel.get("from") or "").strip()
            agent = (tel.get("agent_id") or "").strip()
            if not frm or not agent:
                return None, ("my phone setup's incomplete, sir — Retell needs both a \"from\" number and an "
                              "\"agent_id\" under telephony in config.json.")
            payload = {"from_number": frm, "to_number": to,
                       "override_agent_id": agent,
                       "retell_llm_dynamic_variables": {"task": task}}
            req = urllib.request.Request("https://api.retellai.com/v2/create-phone-call",
                data=json.dumps(payload).encode(),
                headers={"Authorization": "Bearer " + key, "content-type": "application/json"})
        else:
            return None, f"I don't recognise the '{prov}' phone provider, sir."
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        detail = ""
        try: detail = e.read().decode(errors="ignore")[:180]
        except Exception: pass
        print("[call]", e.code, detail)
        return None, (f"the call didn't connect, sir ({e.code}) — {detail}".strip()
                      if detail else f"the call didn't connect, sir ({e.code}).")
    except Exception as e:
        print("[call]", e)
        return None, "the call didn't go through, sir — the line wouldn't open."
    cid = (resp or {}).get("call_id") or (resp or {}).get("id") or ""
    st = (resp or {}).get("call_status") or ""
    msg = f"Dialing {to} now, sir — the line's ringing."
    if cid:
        msg += f" (call {cid[:14]})"
    return {"answer": msg, "call_id": cid, "call_status": st, "to": to}, None

# ---------- time machine (episodic memory: what happened, and when) ----------
EPISODES_FILE = os.path.join(ROOT, "jetty-episodes.jsonl")
EP_LOCK = threading.Lock()
def log_episode(kind, text, nodes=None):
    """Append one timestamped episode. Called from /chat, /remember, /agent, /see."""
    try:
        rec = {"ts": int(time.time()), "kind": kind, "text": (text or "")[:400],
               "nodes": [int(n) for n in (nodes or []) if isinstance(n, (int, float))][:12]}
        with EP_LOCK:
            with open(EPISODES_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
    except Exception:
        pass
def load_episodes(limit=5000):
    if not os.path.exists(EPISODES_FILE):
        return []
    out = []
    try:
        with open(EPISODES_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try: out.append(json.loads(line))
                    except Exception: pass
    except Exception:
        return []
    return out[-limit:]

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
def parse_when(q):
    """Map a date phrase to (start_ts, end_ts, label), or None if it isn't a date query."""
    ql = q.lower(); now = time.localtime(); day = 86400
    today0 = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1))
    span = lambda d0, label: (d0, d0 + day, label)
    if re.search(r"\bthis morning\b", ql): return (today0, today0 + 12 * 3600, "this morning")
    if re.search(r"\btoday\b", ql): return span(today0, "today")
    if re.search(r"\byesterday\b", ql): return span(today0 - day, "yesterday")
    m = re.search(r"\b(\d+)\s+days?\s+ago\b", ql)
    if m: return span(today0 - int(m.group(1)) * day, m.group(0))
    if re.search(r"\blast week\b", ql):
        start = today0 - (now.tm_wday + 7) * day; return (start, start + 7 * day, "last week")
    if re.search(r"\bthis week\b", ql):
        start = today0 - now.tm_wday * day; return (start, start + 7 * day, "this week")
    m = re.search(r"\b(last\s+)?(%s)\b" % "|".join(DAYS), ql)
    if m:
        back = (now.tm_wday - DAYS.index(m.group(2))) % 7
        if back == 0 or m.group(1): back = back or 7
        return span(today0 - back * day, m.group(0))
    m = re.search(r"\b(%s)[a-z]*\s+(\d{1,2})\b" % "|".join(MONTHS), ql)
    if m:
        try:
            d0 = time.mktime((now.tm_year, MONTHS.index(m.group(1)) + 1, int(m.group(2)), 0, 0, 0, 0, 0, -1))
            return span(d0, m.group(0))
        except Exception: pass
    return None

def recall(query):
    eps = load_episodes()
    if not eps:
        return {"answer": "I've nothing logged yet, sir — we've no history for me to rewind to.", "nodes": []}, None
    when = parse_when(query)
    if when:
        s, e, label = when
        hits = [x for x in eps if s <= x.get("ts", 0) < e]; scope = "on " + label
    else:
        qs = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if w not in STOP and len(w) > 2}
        hits = [x for x in eps if qs & set(re.findall(r"[a-z0-9]+", x.get("text", "").lower()))]
        scope = "about that"
    if not hits:
        return {"answer": f"I find nothing {scope}, sir.", "nodes": []}, None
    nodes = []
    for x in hits[-8:]:
        nodes += x.get("nodes", [])
    nodes = list(dict.fromkeys(nodes))[:14]
    lines = [f"[{time.strftime('%a %b %d %I:%M%p', time.localtime(x.get('ts',0)))}] ({x.get('kind')}) {x.get('text','')}"
             for x in hits[-12:]]
    sysp = jpersona(query) + (f"The user asked you to recall what happened {scope}. Below are the real logged episodes "
            "(oldest first). Give a SHORT spoken recap (2-3 sentences) in your dry butler voice, addressing them as "
            "'sir', grounded ONLY in these episodes; if they asked when something first happened, name the date.")
    ans, err = call_model([{"role": "user", "content": "Episodes:\n" + "\n".join(lines)}], sysp, 300)
    if err or not ans:
        ans = f"Here's what I have {scope}, sir: " + "; ".join(x.get("text", "")[:60] for x in hits[-4:])
    return {"answer": ans, "nodes": nodes}, None

# ---------- agent inbox + smart-interrupt governor ----------
# Every background daemon (pre-flight, breakout radar, anomaly watch, living graph…) raises a
# typed CARD here instead of speaking directly. The card ALWAYS lands in the inbox; the governor
# (should_speak) decides only whether it interrupts with VOICE right now.
INBOX_FILE = os.path.join(ROOT, "jetty-inbox.json")
DND_FILE = os.path.join(ROOT, "jetty-dnd.json")
INBOX_LOCK = threading.Lock()
DND_LOCK = threading.Lock()

def load_inbox():
    try:
        return json.load(open(INBOX_FILE)) if os.path.exists(INBOX_FILE) else []
    except Exception:
        return []
def save_inbox(cards):
    tmp = INBOX_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cards[-200:], f)          # cap stored history
    os.replace(tmp, INBOX_FILE)
def inbox_open():
    return [c for c in load_inbox() if c.get("status") not in ("dismissed", "done")][-40:][::-1]

def load_dnd():
    with DND_LOCK:
        try:
            d = json.load(open(DND_FILE)) if os.path.exists(DND_FILE) else {}
        except Exception:
            d = {}
    return {"mute_until": d.get("mute_until", 0), "quiet_from": d.get("quiet_from", "22:00"),
            "quiet_to": d.get("quiet_to", "07:00"), "focus": bool(d.get("focus", False)),
            "rules": d.get("rules", {"money": "always"})}
def save_dnd(d):
    with DND_LOCK:
        tmp = DND_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(d, f)
        os.replace(tmp, DND_FILE)
def set_dnd(focus=None, minutes=None, rule=None):
    d = load_dnd()
    if focus is not None:
        d["focus"] = bool(focus)
        if not focus:
            d["mute_until"] = 0
    if minutes:
        d["mute_until"] = int(time.time() + float(minutes) * 60)
    if rule:
        d.setdefault("rules", {}).update(rule)
    save_dnd(d)
    return d

def _in_quiet(now, frm, to):
    try:
        cur = now.tm_hour * 60 + now.tm_min
        fh, fm = map(int, frm.split(":")); th, tm = map(int, to.split(":"))
        a, b = fh * 60 + fm, th * 60 + tm
        return (cur >= a or cur < b) if a > b else (a <= cur < b)   # window may cross midnight
    except Exception:
        return False
def should_speak(card):
    """Smart-Interrupt Governor — should this card break in with VOICE right now? It lands in the
    inbox either way; this gates only the spoken interruption (alert fatigue is the real problem)."""
    pr = (card.get("priority") or "normal").lower()
    d = load_dnd()
    blob = (card.get("title", "") + " " + card.get("body", "")).lower()
    money = bool(re.search(r"\b(sale|sold|payment|invoice|revenue|stripe|refund|paid|\$\d|charge)\b", blob))
    if pr == "high" and money and (d.get("rules", {}).get("money") == "always"):
        return True                                   # money always breaks through
    if d["focus"] or time.time() < (d.get("mute_until") or 0):
        return pr == "high"                           # focus / DND: only the urgent
    if _in_quiet(time.localtime(), d["quiet_from"], d["quiet_to"]):
        return pr == "high"                           # quiet hours: only the urgent
    return pr in ("normal", "high")

def raise_card(ctype, title, body="", source="jetty", priority="normal", action=None, speak=None):
    """Daemons call this. ctype: notify | ask | approve. action: an agent task to run on approve.
    speak: None → the governor decides; False → card only (for answers already spoken aloud)."""
    card = {"id": uuid.uuid4().hex[:12], "ts": int(time.time()), "type": ctype,
            "title": title, "body": body, "source": source, "priority": priority,
            "action": action, "status": "new", "speak": False}
    card["speak"] = should_speak(card) if speak is None else bool(speak)
    with INBOX_LOCK:
        cards = load_inbox(); cards.append(card); save_inbox(cards)
    return card

def inbox_set_status(cid, status):
    with INBOX_LOCK:
        cards = load_inbox()
        for c in cards:
            if c.get("id") == cid:
                c["status"] = status
                if status != "new":
                    c["speak"] = False
        save_inbox(cards)
    return inbox_open()
def inbox_mark_spoken(cid):
    with INBOX_LOCK:
        cards = load_inbox()
        for c in cards:
            if c.get("id") == cid:
                c["speak"] = False
                if c.get("status") == "new":
                    c["status"] = "seen"
        save_inbox(cards)
    return inbox_open()
def inbox_act(cid):
    card = next((c for c in load_inbox() if c.get("id") == cid), None)
    if not card:
        return None, "I can't find that card, sir."
    action = card.get("action")
    if not action:
        return {"answer": "Cleared, sir.", "cards": inbox_set_status(cid, "done")}, None
    res, err = run_agent(action, execute=True)     # approve → run the confirmed action
    inbox_set_status(cid, "done")
    if err:
        return None, err
    res["cards"] = inbox_open()
    return res, None

CTYPE = {"html": "text/html", "js": "application/javascript", "css": "text/css",
         "png": "image/png", "svg": "image/svg+xml", "json": "application/json"}

class H(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _origin_ok(self):
        o = self.headers.get("Origin")
        return (not o) or o in (f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}")

    def do_GET(self):
        path = self.path.split("?")[0]
        if MISSIONS and path.startswith("/mission"):
            try:
                if MISSIONS.handle(self, "GET", self.path, {}): return
            except Exception as e:
                return self._json({"error": f"mission bay error: {str(e)[:120]}"}, 500)
        if TOOLS and (path in ("/api/tools", "/oauth/callback") or path.startswith("/tool_logo/")):
            try:
                if TOOLS.handle(self, "GET", self.path, {}): return
            except Exception as e:
                return self._json({"error": f"tool bay error: {str(e)[:120]}"}, 500)
        if HANDS and path == "/api/hands":
            try:
                if HANDS.handle(self, "GET", self.path, {}): return
            except Exception as e:
                return self._json({"error": f"hands bay error: {str(e)[:120]}"}, 500)
        if CALLS and path == "/api/calls":
            try:
                if CALLS.handle(self, "GET", self.path, {}): return
            except Exception as e:
                return self._json({"error": f"calls bay error: {str(e)[:120]}"}, 500)
        if POCKET and path == "/api/pocket":
            try:
                if POCKET.handle(self, "GET", self.path, {}): return
            except Exception as e:
                return self._json({"error": f"pocket bay error: {str(e)[:120]}"}, 500)
        if path == "/api/brand":
            return self._json({"name": CFG.get("name", "SECOND BRAIN"), "logo": bool(CFG.get("logo"))})
        if path == "/api/tasks":
            return self._json({"tasks": open_tasks()})
        if path == "/api/proactive":
            return self._json(proactive_status())
        if path == "/api/inbox":
            LAST_POLL[0] = time.time()           # a viewer tab is alive — the desk owns spoken reminders
            return self._json({"cards": inbox_open()})
        if path == "/api/dnd":
            return self._json(load_dnd())
        if path == "/api/model":
            return self._json(model_status())
        if path == "/api/duplex_nodes":          # node side-channel for live duplex sessions
            with DUPLEX_LOCK:
                return self._json(dict(DUPLEX_NODES))
        if path == "/api/voice":
            return self._json(voice_status())
        if path == "/api/persona":
            return self._json(persona.status())
        if path == "/api/lang":
            return self._json(lang_status())
        if path == "/api/duplex":                # live-conversation engines available + active pick
            dx = load_duplex()
            dp = duplex_providers()
            return self._json({"configured": bool(dp["provider"]), "agent_id": dx.get("agent_id", ""), **dp})
        if path == "/api/realtime_session":      # short-lived OpenAI token for the WebRTC session
            res, err = realtime_session()
            return self._json({"error": err}, 502) if err else self._json(res)
        if path == "/api/duplex_signed":         # short-lived signed WebSocket URL for the live session
            dx = load_duplex()
            key = (CFG.get("elevenlabs") or {}).get("api_key", "")
            if not dx.get("agent_id") or not key or key.startswith("PUT-"):
                return self._json({"error": "live mode isn't set up yet, sir — run setup_duplex.py first"}, 502)
            try:
                req = urllib.request.Request(
                    "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id=" + dx["agent_id"],
                    headers={"xi-api-key": key})
                with urllib.request.urlopen(req, timeout=15) as r:
                    return self._json({"signed_url": json.load(r).get("signed_url", "")})
            except Exception as e:
                return self._json({"error": f"couldn't open the line, sir ({str(e)[:120]})"}, 502)
        if path == "/":
            path = "/3d.html"
        vd = os.path.join(ROOT, "viewer")
        fp = os.path.normpath(os.path.join(vd, path.lstrip("/")))
        if os.path.isfile(fp) and (fp == vd or fp.startswith(vd + os.sep)):
            data = open(fp, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", CTYPE.get(fp.rsplit(".", 1)[-1], "application/octet-stream"))
            self.send_header("Cache-Control", "no-store")   # always serve the freshest viewer (no stale pages)
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if not self._origin_ok():
            return self._json({"error": "bad origin"}, 403)
        ln = int(self.headers.get("Content-Length", 0))
        try:
            p = json.loads(self.rfile.read(ln) or b"{}")
        except Exception:
            p = {}
        path = self.path.split("?")[0]

        if MISSIONS and path.startswith("/mission"):
            try:
                if MISSIONS.handle(self, "POST", self.path, p): return
            except Exception as e:
                return self._json({"error": f"mission bay error: {str(e)[:120]}"}, 500)

        if TOOLS and path.startswith("/tools"):
            try:
                if TOOLS.handle(self, "POST", self.path, p): return
            except Exception as e:
                return self._json({"error": f"tool bay error: {str(e)[:120]}"}, 500)

        if HANDS and path.startswith("/hands"):
            try:
                if HANDS.handle(self, "POST", self.path, p): return
            except Exception as e:
                return self._json({"error": f"hands bay error: {str(e)[:120]}"}, 500)

        if CALLS and path.startswith("/calls"):
            try:
                if CALLS.handle(self, "POST", self.path, p): return
            except Exception as e:
                return self._json({"error": f"calls bay error: {str(e)[:120]}"}, 500)

        if path == "/presence":           # client drives the desktop orb (screen-share on/off, states)
            cmd = (p.get("cmd") or "").strip()
            if cmd: presence(cmd)
            return self._json({"ok": True})

        if path == "/tool_chat":         # "use canva to…" — act through the connected tools
            q = (p.get("question") or "").strip()
            if not q: return self._json({"error": "empty question"}, 400)
            res, err = tool_chat(q, p.get("session"))
            if err: hue.error_flash()
            return self._json({"error": err}, 502) if err else self._json(res)

        if path == "/chat":
            q = (p.get("question") or "").strip()
            if not q: return self._json({"error": "empty question"}, 400)
            swapped = try_chat_swap(q)          # regex fast path: "switch to grok" from ANY surface
            if swapped:
                return self._json(swapped)
            ans, nodes, err = chat(q, p.get("session"))
            if not err:
                tagged = apply_control_tag(ans, p.get("session"))  # the brain flagged a swap/search the regexes missed
                if tagged:
                    return self._json(tagged)
                gm = GAG_TAG_RE.search(ans or "")  # the brain filed a running gag for later
                if gm:
                    persona.add_gag(gm.group(1), gm.group(2))
                    ans = GAG_TAG_RE.sub("", ans).strip()
                ans = re.sub(r"\*{1,2}([^*\n]+)\*{1,2}", r"\1", ans or "")  # raw **bold** was reaching the screen
                log_episode("chat", q, nodes)
            else: hue.error_flash()
            return self._json({"error": err}, 502) if err else self._json({"answer": ans, "nodes": nodes})

        if path == "/research":     # explicit "research/look up X" → live web search (Anthropic server tool)
            q = (p.get("question") or "").strip()
            if not q: return self._json({"error": "empty question"}, 400)
            res, err = web_research(q, p.get("session"), image=(p.get("image") or None))
            if err: hue.error_flash()
            return self._json({"error": err}, 502) if err else self._json(res)

        if path == "/tts":
            t = (p.get("text") or "").strip()
            if not t: return self._json({"error": "empty text"}, 400)
            with VOICE_LOCK:
                _mid = VOICE.get("model_id") or ""
            t = speakable(t)                     # "$97/mo" reads "a month", not "slash m o"
            t = persona.speech_text(t, _mid)     # audio tags reach only the v3 engine
            audio, err = synth_voice(t)
            if err: return self._json({"error": err}, 502)
            self.send_response(200); self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(audio))); self.end_headers(); self.wfile.write(audio); return

        if path == "/remember":
            t = (p.get("text") or "").strip()
            if not t: return self._json({"error": "empty text"}, 400)
            res, err = capture(t, (p.get("related") or "").strip())
            if not err: log_episode("note", "Captured: " + t)
            return self._json({"error": err}, 502) if err else self._json(res)

        if path == "/edit":
            res, err = edit_note((p.get("target") or "").strip(), (p.get("text") or "").strip())
            return self._json({"error": err}, 502) if err else self._json(res)

        if path == "/task":
            t = (p.get("text") or "").strip()
            if not t: return self._json({"error": "empty task"}, 400)
            return self._json({"tasks": add_task(t, p.get("due"))})
        if path == "/tasks":
            return self._json({"tasks": open_tasks()})
        if path == "/task_done":
            return self._json({"tasks": complete_task(p.get("index"))})
        if path == "/task_reminded":      # a due reminder has fired client-side — don't re-fire
            return self._json({"tasks": mark_reminded(p.get("ts"))})

        if path == "/briefing":
            ans, err = briefing()
            return self._json({"error": err}, 502) if err else self._json({"answer": ans})

        if path == "/proactive":
            return self._json(set_proactive(p.get("enabled"), p.get("time")))
        if path == "/proactive_ack":
            return self._json(proactive_ack())

        if path == "/agent":
            t = (p.get("task") or "").strip()
            if not t: return self._json({"error": "empty task"}, 400)
            res, err = run_agent(t)
            if not err: log_episode("agent", "Task: " + t)
            return self._json({"error": err}, 502) if err else self._json(res)
        if path == "/agent_confirm":
            res, err = confirm_agent((p.get("pending_id") or "").strip())
            return self._json({"error": err}, 502) if err else self._json(res)

        if path == "/remember_me":
            res, err = remember_me((p.get("text") or "").strip())
            return self._json({"error": err}, 502) if err else self._json(res)
        if path == "/pulse":
            ans, err = pulse()
            return self._json({"error": err}, 502) if err else self._json({"answer": ans})
        if path == "/inbox":
            ans, err = inbox()
            return self._json({"error": err}, 502) if err else self._json({"answer": ans})
        if path == "/see":
            ans, err = see_image((p.get("image") or "").strip(), (p.get("question") or "").strip())
            return self._json({"error": err}, 502) if err else self._json({"answer": ans})
        if path == "/call":
            t = (p.get("task") or "").strip()
            if not t: return self._json({"error": "empty task"}, 400)
            res, err = place_call(t, (p.get("to") or "").strip() or None)
            return self._json({"error": err}, 502) if err else self._json(res)

        # ---- agent inbox + governor ----
        if path == "/inbox_add":          # raise a card (daemons/tests/external)
            c = raise_card((p.get("type") or "notify").strip(),
                           (p.get("title") or "").strip() or "Note", (p.get("body") or "").strip(),
                           (p.get("source") or "manual").strip(), (p.get("priority") or "normal").strip(),
                           (p.get("action") or None))
            return self._json({"card": c, "cards": inbox_open()})
        if path == "/inbox_ack":          # spoken once → stop re-speaking, keep visible
            return self._json({"cards": inbox_mark_spoken((p.get("id") or "").strip())})
        if path == "/inbox_act":          # approve → run the card's confirmed action
            res, err = inbox_act((p.get("id") or "").strip())
            return self._json({"error": err}, 502) if err else self._json(res)
        if path == "/inbox_dismiss":
            return self._json({"cards": inbox_set_status((p.get("id") or "").strip(), "dismissed")})
        if path == "/dnd":                # smart-interrupt governor controls
            if p.get("focus") is not None:
                hue.focus(bool(p.get("focus")))
            return self._json(set_dnd(p.get("focus"), p.get("minutes"), p.get("rule")))

        if path == "/model":              # hot-swap the brain: "Jetty, try on haiku / grok / deepseek"
            name = (p.get("model") or "").strip()
            if not name: return self._json({"error": "which brain, sir?"}, 400)
            mid, merr = set_model(name)
            if not mid:
                if merr == "no_openrouter_key":
                    return self._json({"error": f"I found '{name}' in the OpenRouter catalogue, sir, but you "
                                       "haven't given me the key — paste it under \"openrouter\" in config.json "
                                       "and I can wear nearly any model in existence."}, 402)
                hint = (" With OpenRouter connected, I can also fetch nearly anything — grok, gpt, gemini, "
                        "deepseek…" if or_key() else "")
                return self._json({"error": f"I don't have a '{name}' brain on the shelf, sir — I know " +
                                   ", ".join(known_brains()) + "." + hint}, 404)
            quip, qerr = call_model([{"role": "user", "content":
                f"You have just been fitted as Jetty's new brain: {mid}. In ONE short dry sentence, "
                "introduce yourself in character and address the user as 'sir'."}], PERSONA, 400)
            log_episode("model", f"Brain swapped to {mid}")
            if qerr or not quip or quip == "(no answer)":   # reasoning models sometimes return empty
                quip = f"New brain fitted, sir — {mid} online."
            return self._json({**model_status(), "answer": quip})

        if path == "/voice":              # hot-swap the voice: "switch your voice to Daniel / flash"
            spoken, verr = set_voice((p.get("voice") or "").strip())
            if verr:
                return self._json({"error": verr}, 404)
            return self._json({**voice_status(), "answer": f"How do I sound, sir? This is {spoken}."})

        if path == "/lang":               # multilingual mode: "speak Spanish" / "back to English"
            code = set_lang((p.get("lang") or "").strip())
            if not code:
                return self._json({"error": "I don't speak that one yet, sir — my repertoire runs to " +
                                            ", ".join(lang_status()["spoken"]) + "."}, 404)
            return self._json({**lang_status(), "line": LANGS[code][1]})
        if path == "/duplex_pref":        # pick the live-voice engine: elevenlabs | openai | auto
            prov = (p.get("provider") or "auto").strip().lower()
            if prov not in ("elevenlabs", "openai", "auto"):
                return self._json({"error": "elevenlabs, openai, or auto, sir."}, 400)
            dx = load_duplex(); dx["provider"] = prov; save_duplex(dx)
            return self._json(duplex_providers())

        if path == "/persona":           # dials, skins, candid mode
            if p.get("dial"):
                v = persona.set_dial((p["dial"] or {}).get("name"), (p["dial"] or {}).get("value"))
                if v is None:
                    return self._json({"error": "humor or honesty, zero to a hundred, sir."}, 400)
            if p.get("skin"):
                label, vh = persona.set_skin(p["skin"])
                if not label:
                    return self._json({"error": "I don't own that costume, sir — I have " +
                                       ", ".join(persona.status()["skins"]) + "."}, 404)
                set_voice(vh or "default")
            if p.get("candid"):
                try:
                    persona.set_candid(float(p["candid"]))
                except Exception:
                    persona.set_candid(2)
            quip, qerr = call_model([{"role": "user", "content":
                "Your persona settings were just adjusted. Acknowledge in ONE short line, in character, "
                "letting the current settings show in the delivery."}], jpersona(), 200)
            return self._json({**persona.status(),
                               "answer": quip if not qerr and quip and quip != "(no answer)" else "Adjusted, sir."})

        if path == "/os":                 # deterministic Mac control (volume/dark/wifi/apps/windows/scenes)
            res = osctl.do((p.get("action") or "").strip(), p.get("value"), CFG.get("hardware") or {})
            if res is None:
                return self._json({"error": "I don't know that switch, sir."}, 400)
            log_episode("os", f"{p.get('action')}: {p.get('value')}")
            return self._json({"answer": res})

        if path == "/find":               # Spotlight by voice
            res, err = osctl.find_files((p.get("query") or "").strip(), open_top=bool(p.get("open", True)))
            if err:
                return self._json({"error": err}, 400)
            log_episode("os", "Found: " + (p.get("query") or ""))
            return self._json({"answer": res["spoken"], "hits": res.get("hits", [])[:6]})

        if path == "/type":               # universal typing into the focused app
            return self._json({"answer": osctl.type_text(p.get("text") or "")})

        if path == "/clip":               # clipboard: read / history / transform-in-place
            op = (p.get("op") or "read").strip()
            if op == "history":
                h = osctl.clip_history(8)
                if not h:
                    return self._json({"answer": "No clippings logged yet, sir — I watch from boot."})
                return self._json({"answer": f"Your last {len(h)} clippings are on screen, sir — newest: "
                                   + h[0][0][:100], "history": [x[0][:200] for x in h]})
            if op == "transform":
                c = osctl.clip_read()
                if not c.strip():
                    return self._json({"answer": "Nothing on the clipboard to work with, sir."})
                instr = (p.get("instruction") or "clean this up").strip()
                out, terr = call_model([{"role": "user", "content":
                    "Transform the clipboard content below as instructed. Reply with ONLY the transformed "
                    "content, nothing else.\n\nINSTRUCTION: " + instr + "\n\nCONTENT:\n" + c[:6000]}],
                    jpersona(), 2000)
                if terr or not out:
                    return self._json({"error": "the transform failed, sir"}, 502)
                osctl.clip_write(out)
                return self._json({"answer": "Transformed and back on your clipboard, sir — paste away."})
            c = osctl.clip_read()
            return self._json({"answer": ("On your clipboard, sir: " + c[:200]) if c.strip()
                               else "Your clipboard is empty, sir.", "text": c[:4000]})

        if path == "/organize":           # Downloads janitor: plan → approval → move
            res, err = org_plan((p.get("dir") or "Downloads").strip())
            return self._json({"error": err}, 502) if err else self._json(res)
        if path == "/rename_shots":       # screenshot renamer: vision names → approval → rename
            res, err = shots_plan()
            return self._json({"error": err}, 502) if err else self._json(res)
        if path == "/os_confirm":         # "do it" for either of the above
            res, err = os_confirm((p.get("pending_id") or "").strip())
            return self._json({"error": err}, 502) if err else self._json(res)

        if path == "/hue_event":          # client playback events drive the room lighting
            ev = (p.get("event") or "").strip()
            if HANDS and not HANDS.RUN.get("active"):    # don't fight the "driving" state during takeover
                if ev == "speak_start": presence("state:speaking")
                elif ev == "speak_end": presence("state:idle")
            if ev == "speak_start": hue.speak_start()
            elif ev == "speak_end": hue.speak_end()
            elif ev == "error": hue.error_flash()
            elif ev == "focus_on": hue.focus(True)
            elif ev == "focus_off": hue.focus(False)
            return self._json({"ok": True, "hue": hue.status()})
        if path == "/hue_setup":          # pair with the bridge (press the physical button first)
            res, err = hue.setup((p.get("ip") or "").strip() or None)
            return self._json({"error": err}, 502) if err else self._json(res)

        if path == "/guide":              # "show me how" → vision finds the element → overlay ring
            ans, err = guide((p.get("image") or "").strip(), (p.get("question") or "").strip())
            return self._json({"error": err}, 502) if err else self._json(ans)
        if path == "/overlay":            # "draw a circle on my screen" — direct ring, no vision call
            how = spawn_overlay(float(p.get("x_pct") or 50), float(p.get("y_pct") or 45),
                                (p.get("label") or "")[:40])
            if not how:
                return self._json({"error": "the ring wouldn't draw, sir — start me from your own Terminal."}, 502)
            return self._json({"ok": True, "via": how})

        if path == "/recall":             # time machine: "what was I doing last Tuesday?"
            q = (p.get("when") or p.get("question") or "").strip()
            if not q: return self._json({"error": "recall what, sir?"}, 400)
            res, err = recall(q)
            return self._json({"error": err}, 502) if err else self._json(res)

        self.send_response(404); self.end_headers()

    def log_message(self, *a):
        pass

# ---------- duplex brain endpoint (OpenAI-compatible, for ElevenLabs Agents custom-LLM) ----------
# Runs on its own port so ONLY this one route is ever exposed through a public tunnel.
# Auth: Authorization: Bearer <token from jetty-duplex.json>. The main app on 4719 stays private.
def duplex_reply_parts(body):
    """Build (system, messages) for a live voice turn: same brain — persona + memory + vault RAG."""
    msgs = [m for m in (body.get("messages") or [])
            if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)][-12:]
    last_user = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
    notes, top = retrieve(last_user, k=6)
    style = ("You are in a LIVE VOICE conversation. Reply in 1-3 SHORT spoken sentences — dry, warm, "
             "witty, 'sir' now and then. No markdown, no lists, no stage directions, no emoji.")
    if top >= 4 and notes and not CONV_RE.search(last_user):
        ctx = "\n\n".join(f"## {n['label']}\n{n['p']}" for n in notes)
        set_duplex_nodes([n["_idx"] for n in notes])
        sysp = jpersona(last_user) + mem_block() + style + ("\nIf (and only if) the question is really about the user's "
               "notes below, ground your answer in them (the graph is already flying there):\n\n" + ctx)
    else:
        set_duplex_nodes([])
        sysp = jpersona(last_user) + mem_block() + style
    if last_user:
        log_episode("duplex", last_user)
    return sysp, msgs

def anthropic_stream(system, messages, max_tokens=300):
    """Yield text tokens from the Anthropic Messages API (SSE). stdlib only."""
    key = MODELCFG.get("api_key", "")
    base = (MODELCFG.get("base_url") or "").strip().rstrip("/")
    url = (base + "/v1/messages") if base else "https://api.anthropic.com/v1/messages"
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "system": system,
                       "messages": messages, "stream": True}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except Exception:
                continue
            if ev.get("type") == "content_block_delta" and ev.get("delta", {}).get("type") == "text_delta":
                yield ev["delta"].get("text", "")

class DuplexHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _deny(self, code=401):
        b = json.dumps({"error": "unauthorized"}).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            b = b'{"ok": true}'
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        if self.path.split("?")[0] not in ("/v1/chat/completions", "/chat/completions"):
            return self._deny(404)
        tok = load_duplex().get("token", "")
        auth = self.headers.get("Authorization", "")
        if not tok or auth != "Bearer " + tok:
            return self._deny(401)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except Exception:
            body = {}
        sysp, msgs = duplex_reply_parts(body)
        if not msgs:
            return self._deny(400)
        rid = "chatcmpl-" + uuid.uuid4().hex[:24]
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache"); self.end_headers()
            def chunk(delta, fin=None):
                c = {"id": rid, "object": "chat.completion.chunk", "created": int(time.time()),
                     "model": MODEL, "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}
                self.wfile.write(("data: " + json.dumps(c) + "\n\n").encode()); self.wfile.flush()
            try:
                chunk({"role": "assistant"})
                base = (MODELCFG.get("base_url") or "").strip()
                native = (not base or "api.anthropic.com" in base)
                if native:
                    for tokn in anthropic_stream(sysp, msgs):
                        chunk({"content": tokn})
                else:   # a hot-swapped OpenRouter/OpenAI-compat brain: answer whole (no SSE relay)
                    txt, err2 = call_model(msgs, sysp, 300)
                    chunk({"content": txt or (err2 or "…")})
                chunk({}, "stop")
                self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
            except Exception as e:
                print("[duplex]", e)
            return
        # non-streaming fallback
        txt, err = call_model(msgs, sysp, 300)
        out = {"id": rid, "object": "chat.completion", "created": int(time.time()), "model": MODEL,
               "choices": [{"index": 0, "message": {"role": "assistant", "content": txt or (err or "")},
                            "finish_reason": "stop"}],
               "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
        b = json.dumps(out).encode()
        self.send_response(200 if not err else 502); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

def start_duplex_server():
    load_duplex()                                   # ensure the token exists
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", DUPLEX_PORT), DuplexHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"Duplex brain (OpenAI-compat, token-authed) on http://localhost:{DUPLEX_PORT}")
    except OSError as e:
        print("[duplex] port busy:", e)

if __name__ == "__main__":
    hands = "ready" if claude_ready() else "NOT FOUND (/agent disabled)"
    prov = "openai-compat" if (MODELCFG.get("base_url") and (MODELCFG.get("provider") or "").lower() != "anthropic"
                               and "api.anthropic.com" not in (MODELCFG.get("base_url") or "")) else "anthropic"
    print(f"Brain Studio V3 (assistant) on http://localhost:{PORT}  ·  {len(CORPUS)} notes  ·  "
          f"model: {MODEL} ({prov})  ·  hands: {hands}  ·  hue: {hue.status()['state']}")
    osctl.start_clip_watch()
    if MISSIONS:
        try:
            MISSIONS.init(dict(cfg=CFG, root=ROOT, port=PORT, raise_card=raise_card,
                               call_model=call_model, claude_read=claude_read, jpersona=jpersona))
            print("[missions] bay online")
        except Exception as e:
            print("[missions] init failed:", e)
    if TOOLS:
        try:
            TOOLS.init(dict(cfg=CFG, root=ROOT, port=PORT, raise_card=raise_card, jpersona=jpersona))
            print("[tools] bay online")
        except Exception as e:
            print("[tools] init failed:", e)
    if HANDS:
        try:
            HANDS.init(dict(cfg=CFG, model=MODEL, key=MODELCFG.get("api_key", ""),
                            base=MODELCFG.get("base_url", ""), provider=MODELCFG.get("provider", "anthropic"),
                            jpersona=jpersona, mem_block=mem_block, presence=presence,
                            speed=(CFG.get("takeover") or {}).get("speed", "balanced"),
                            persist_speed=_persist_takeover_speed,
                            log=lambda kind, text: log_episode("takeover", f"{kind}: {text[:80]}")))
            print("[hands] bay online")
        except Exception as e:
            print("[hands] init failed:", e)
    if CALLS:
        try:
            CALLS.init(dict(cfg=CFG, root=ROOT, jpersona=jpersona, mem_block=mem_block,
                            call_model=call_model, web_research=web_research, raise_card=raise_card,
                            log=lambda kind, text: log_episode("call", f"{kind}: {text[:80]}")))
            print("[calls] bay online")
        except Exception as e:
            print("[calls] init failed:", e)
    if POCKET:
        try:
            POCKET.init(dict(cfg=CFG, root=ROOT, chat=chat, try_chat_swap=try_chat_swap,
                             apply_tag=apply_control_tag, gag_re=GAG_TAG_RE, add_gag=persona.add_gag,
                             log=log_episode, open_tasks=open_tasks, mark_reminded=mark_reminded,
                             inbox_open=inbox_open, raise_card=raise_card,
                             last_seen=lambda: LAST_POLL[0]))
            print("[pocket] bay online" + ("" if POCKET.configured() else " (no Telegram token yet — dormant)"))
        except Exception as e:
            print("[pocket] init failed:", e)
    start_duplex_server()
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()

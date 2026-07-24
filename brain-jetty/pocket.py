"""Jetty POCKET — text your second brain from anywhere (Telegram).

The community ask (Luke): "get him on our phones — ideas come up away from the desk, and
everything still saves so you can continue back at your desk." This bay long-polls a private
Telegram bot FROM the Mac — no public server, no tunnel, no exposed port. Messages ride the
SAME brain as the desk: conversation memory, control tags (reminders, note captures, project
creation, even brain swaps) all work by text, every exchange lands in the Time Machine, and
captures/creations persist into the graph waiting at the desk. Jetty also PUSHES the other
way: due reminders and high-priority inbox cards reach the phone even with no browser open
(the desk keeps them when a viewer tab has polled recently).

Plug-in bay contract (like calls/tools/hands): server.py soft-imports `pocket as POCKET`,
routes GET /api/pocket through handle(), init() at boot. Needs config.json → "telegram":
{"bot_token": "..."} (make one in 2 minutes with @BotFather). Graceful no-op until then.
SECURITY: the bot answers ONLY paired chats — pairing requires the 6-digit code minted at
boot (ask at the desk: "Jetty, pocket code"), so a stranger finding the bot gets a butler
brush-off, never the brain. Paired chats persist in jetty-pocket.json (gitignored).
"""
import json, os, random, threading, time, urllib.error, urllib.parse, urllib.request

CTX = {}                          # init() fills: cfg, root, chat, try_chat_swap, apply_tag, gag_re,
                                  # add_gag, log, open_tasks, mark_reminded, inbox_open, raise_card, last_seen
STATE = {"chats": [], "names": {}, "offset": 0, "pushed": []}
LOCK = threading.Lock()
CODE = f"{random.randint(0, 999999):06d}"          # fresh every boot; spoken at the desk on request
API = "https://api.telegram.org/bot"
DESK_FRESH_S = 90                 # a viewer tab polled within this window → the desk owns reminders
_started = False


def _cfg():
    return (CTX.get("cfg") or {}).get("telegram") or {}

def token():
    t = (_cfg().get("bot_token") or "").strip()
    return "" if not t or t.startswith("PUT-") else t

def configured():
    return bool(token())

def _state_file():
    return os.path.join(CTX.get("root") or ".", "jetty-pocket.json")

def load_state():
    global STATE
    try:
        if os.path.exists(_state_file()):
            d = json.load(open(_state_file()))
            if isinstance(d, dict):
                STATE = {"chats": list(d.get("chats") or []), "names": dict(d.get("names") or {}),
                         "offset": int(d.get("offset") or 0), "pushed": list(d.get("pushed") or [])}
    except Exception:
        pass

def save_state():
    tmp = _state_file() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(STATE, f)
    os.replace(tmp, _state_file())


def _api(method, data=None, timeout=20):
    """One Telegram Bot API call. Returns the parsed dict, or {} on any failure."""
    if not configured():
        return {}
    url = API + token() + "/" + method
    body = urllib.parse.urlencode(data or {}).encode()
    req = urllib.request.Request(url, data=body)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return {}

def _chunks(text, cap=3800):
    """Telegram hard-caps messages at 4096 chars — split long reports on sentence-ish seams."""
    text = (text or "").strip()
    if len(text) <= cap:
        return [text] if text else []
    parts, cur = [], ""
    for seg in text.replace("\r", "").split("\n"):
        seg += "\n"
        while len(seg) > cap:                      # a single monster line — hard split
            parts.append((cur + seg[:cap]).strip()); cur, seg = "", seg[cap:]
        if cur and len(cur) + len(seg) > cap:
            parts.append(cur.strip()); cur = seg
        else:
            cur += seg
    if cur.strip():
        parts.append(cur.strip())
    return parts

def send(chat_id, text):
    for part in _chunks(text):
        _api("sendMessage", {"chat_id": chat_id, "text": part})


# ---------- inbound: the phone talks to the desk brain ----------
def _handle_msg(m):
    chat = (m.get("chat") or {}).get("id")
    text = (m.get("text") or "").strip()
    if not chat or not text:
        return
    user = (m.get("from") or {}).get("username") or (m.get("from") or {}).get("first_name") or "someone"
    with LOCK:
        paired = chat in STATE["chats"]
    if not paired:
        if CODE in text:                            # the code can arrive alone or inside a sentence
            with LOCK:
                if chat not in STATE["chats"]:
                    STATE["chats"].append(chat)
                STATE["names"][str(chat)] = user
                save_state()
            send(chat, "Paired, sir. The brain at the desk is listening — ask me anything, "
                       "set reminders, capture notes. It all lands in the graph at home.")
            try:
                CTX["raise_card"]("notify", f"📱 Pocket paired — @{user}",
                                  "Telegram is now a surface. Texts ride the desk brain.",
                                  source="pocket", speak=None)
            except Exception:
                pass
            return
        send(chat, "This is a private butler, I'm afraid. If you're my principal: ask at the "
                   "desk for the pocket code (“Jetty, pocket code”) and text it here.")
        return
    if text in ("/start", "/help"):
        send(chat, "At your service, sir. Text me anything — questions ride your vault, "
                   "“remind me to…” sets reminders, “remember that…” files notes into the "
                   "graph, “create a project for…” builds it on disk. Due reminders and urgent "
                   "cards get pushed here when you're away from the desk.")
        return
    sid = f"pocket-{chat}"
    try:
        swapped = CTX["try_chat_swap"](text)        # "switch to grok" works from the beach too
        if swapped:
            send(chat, swapped.get("answer") or "Done, sir.")
            return
        ans, nodes, err = CTX["chat"](text, sid)
        if err:
            send(chat, f"The brain hit a snag, sir ({err}).")
            return
        tagged = CTX["apply_tag"](ans, sid)         # reminders/captures/creates fire exactly like the desk
        if tagged:
            ans = tagged.get("answer") or ans
        else:
            gm = CTX["gag_re"].search(ans or "")
            if gm:
                try: CTX["add_gag"](gm.group(1), gm.group(2))
                except Exception: pass
                ans = CTX["gag_re"].sub("", ans).strip()
            try: CTX["log"]("pocket", text, nodes)
            except Exception: pass
        send(chat, ans or "(no answer)")
    except Exception as e:
        send(chat, f"Something snapped in the wiring, sir ({str(e)[:80]}).")

def _poll_loop():
    while True:
        if not configured():
            time.sleep(30); continue
        try:
            with LOCK:
                off = STATE["offset"]
            r = _api("getUpdates", {"timeout": 50, "offset": off + 1}, timeout=70)
            for u in (r.get("result") or []):
                with LOCK:
                    STATE["offset"] = max(STATE["offset"], int(u.get("update_id") or 0))
                    save_state()
                _handle_msg(u.get("message") or {})
        except Exception:
            time.sleep(5)


# ---------- outbound: the desk pushes to the phone ----------
def _desk_is_live():
    try:
        return (time.time() - float(CTX["last_seen"]())) < DESK_FRESH_S
    except Exception:
        return False

def _push_once():
    """One sweep: due reminders (only when the desk is closed) + high-priority cards → the phone."""
    if not configured():
        return
    with LOCK:
        chats = list(STATE["chats"])
    if not chats:
        return
    # due reminders — ONLY when no viewer tab is around to speak them (the desk wins at the desk)
    if not _desk_is_live():
        now = time.time()
        for t in (CTX["open_tasks"]() or []):
            if t.get("due") and not t.get("reminded") and t["due"] <= now:
                CTX["mark_reminded"](t.get("ts"))
                for c in chats:
                    send(c, "⏰ It's time, sir — " + (t.get("text") or "your reminder."))
    # high-priority cards go to the pocket regardless — they're rare and they matter
    for card in (CTX["inbox_open"]() or []):
        if card.get("priority") == "high" and card.get("id") not in STATE["pushed"]:
            with LOCK:
                STATE["pushed"] = (STATE["pushed"] + [card["id"]])[-100:]
                save_state()
            for c in chats:
                send(c, f"🔔 {card.get('title','')}\n{card.get('body','')}".strip())

def _push_loop():
    while True:
        time.sleep(20)
        try:
            _push_once()
        except Exception:
            pass


# ---------- HTTP surface ----------
def handle(handler, method, raw_path, payload):
    path = raw_path.split("?")[0]
    if method == "GET" and path == "/api/pocket":
        with LOCK:
            chats, names = list(STATE["chats"]), dict(STATE["names"])
        handler._json({"configured": configured(), "paired": len(chats),
                       "who": [names.get(str(c), "?") for c in chats],
                       "code": (CODE if configured() and not chats else "")})
        return True
    return False


def init(ctx):
    global _started
    CTX.update(ctx or {})
    load_state()
    if _started:
        return
    _started = True
    threading.Thread(target=_poll_loop, daemon=True).start()
    threading.Thread(target=_push_loop, daemon=True).start()

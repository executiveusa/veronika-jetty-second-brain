"""Jetty HANDS-FREE CALLING — Jetty rings real phone numbers on your behalf (Retell AI).

"Jetty, call Luigi's and book a table for four at seven tonight" → Jetty finds the number
(web search if you didn't give one), turns your ask into a clean brief for the calling agent,
asks permission ("Shall I ring them, sir?"), places the call through Retell, watches it live,
and when it ends he reads the transcript and tells you what happened ("Booked, sir — 7:15,
patio, under your name."). Every call is logged.

Plug-in bay contract (like tools/hands/missions): server.py soft-imports `calls as CALLS`,
routes /calls* + /api/calls through handle(), and calls init() at boot. Needs a Retell key +
number + agent_id in config.json → "telephony"; graceful, no-op message until then. A real
call NEVER fires without an in-conversation "do it" (rule 4 — outward actions are confirmed).
"""
import json, os, re, threading, time, urllib.error, urllib.parse, urllib.request

CTX = {}                         # init() fills: cfg, jpersona, mem_block, call_model, web_research, raise_card, log
PENDING = {}                     # confirm_id -> {callee, number, brief, task, need_number}
LIVE = {}                        # call_id -> {status, callee, number, brief, started, summary, outcome, done}
LOCK = threading.Lock()

RETELL_CREATE = "https://api.retellai.com/v2/create-phone-call"
RETELL_GET = "https://api.retellai.com/v2/get-call/"
# never let Jetty autonomously complete these over the phone — book/ask, but stop before committing money
MONEY = ("pay", "purchase", "buy", "deposit", "charge my card", "credit card number", "wire", "prepay")


def _tel():
    return (CTX.get("cfg") or {}).get("telephony") or {}

def configured():
    t = _tel()
    key = (t.get("api_key") or "").strip()
    return bool(key) and not key.startswith("PUT-") and bool(t.get("from")) and bool(t.get("agent_id"))

def _http(url, data=None, method=None, timeout=20):
    t = _tel()
    headers = {"Authorization": "Bearer " + (t.get("api_key") or ""), "content-type": "application/json"}
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {}), None
    except urllib.error.HTTPError as e:
        raw = b""
        try: raw = e.read()
        except Exception: pass
        return e.code, {}, (raw.decode(errors="ignore")[:200] or f"HTTP {e.code}")
    except Exception as e:
        return 0, {}, str(e)[:160]

# ---------- phone numbers ----------

def to_e164(s):
    """Normalize a US/intl number to +E.164, or None. '(415) 555-0134' -> '+14155550134'."""
    s = (s or "").strip()
    if s.startswith("+"):
        digits = "+" + re.sub(r"\D", "", s[1:])
        return digits if 8 <= len(digits) - 1 <= 15 else None
    d = re.sub(r"\D", "", s)
    if len(d) == 10: return "+1" + d
    if len(d) == 11 and d[0] == "1": return "+" + d
    if 8 <= len(d) <= 15: return "+" + d
    return None

def find_number_in(text):
    for m in re.findall(r"\+?\d[\d\s().-]{7,}\d", text or ""):
        e = to_e164(m)
        if e: return e
    return None

def lookup_number(callee, sid=None):
    """Web-search for a business's phone number. Returns (e164 or None, spoken_note)."""
    wr = CTX.get("web_research")
    if not wr: return None, ""
    q = (f"What is the phone number for {callee}? Reply with ONLY the phone number in "
         f"the format +1XXXXXXXXXX, nothing else.")
    res, err = wr(q, sid, 3)
    if err or not res: return None, ""
    ans = res.get("answer", "")
    num = find_number_in(ans)
    return num, ans

# ---------- triage: pick the right scripted agent + extract only its real fields ----------
# Each call TYPE maps to a purpose-built Retell agent with a detailed step-by-step script.
# We pass ONLY that type's fields (with defaults, so an unfilled variable is never literal
# "{{brackets}}"). No vague catch-all task blob — the script does the work.
FIELD_DEFAULTS = {
    "booking": {"party_or_service": "the booking", "datetime": "the requested time", "name": "the caller", "notes": "none"},
    "inquiry": {"question": "the question"},
    "general": {"objective": "the request"},
}

def agent_for(kind):
    ag = _tel().get("agents") or {}
    return ag.get(kind) or _tel().get("agent_id")

def variables_for(kind, fields):
    v = dict(FIELD_DEFAULTS.get(kind, FIELD_DEFAULTS["general"]))
    for k in list(v.keys()):
        val = (fields or {}).get(k)
        if val not in (None, ""):
            v[k] = str(val).strip()
    return v

def classify_call(task, sid=None):
    """Claude triages the ask → {type, callee, fields, say}. Falls back to a general call."""
    fb = {"type": "general", "callee": _guess_callee(task), "fields": {"objective": task},
          "say": f"call {_guess_callee(task)} and {task}"}
    cm = CTX.get("call_model")
    if not cm:
        return fb
    callback = (_tel().get("callback") or _tel().get("to") or "").strip()
    sysp = (CTX["jpersona"]() + CTX["mem_block"]() +
            "Triage a phone call the user wants their assistant to make. Return STRICT JSON ONLY:\n"
            '{"type":"booking|inquiry|general","callee":"<who to call, short>","fields":{...},'
            '"say":"<one short butler line back to the user confirming what you\'ll do, ending '
            'with \'Shall I ring them, sir?\'>"}\n'
            "type meanings and their fields (include ONLY the chosen type's fields):\n"
            "- booking = reserving a table/appointment/slot. fields: "
            '{"party_or_service","datetime","name","notes"}. name defaults to the caller if unspecified; '
            'notes = "none" if there are none.\n'
            "- inquiry = getting one piece of info (hours, price, availability, stock). "
            'fields: {"question"} — phrase it as the exact question to ask.\n'
            "- general = anything else (cancel, reschedule, follow up, complaint, custom). "
            'fields: {"objective"} — a clear, specific instruction.\n'
            "Keep field values concise and literal. Never invent specifics the user didn't give.")
    txt, err = cm([{"role": "user", "content": task}], sysp, 500)
    if err or not txt:
        return fb
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return fb
    try:
        d = json.loads(m.group(0))
    except Exception:
        return fb
    kind = d.get("type") if d.get("type") in FIELD_DEFAULTS else "general"
    return {"type": kind, "callee": (d.get("callee") or _guess_callee(task)).strip(),
            "fields": d.get("fields") or {}, "say": d.get("say") or fb["say"]}

# ---------- placing + tracking the call ----------

def place(callee, number, agent_id, variables):
    """Fire the Retell call on the chosen scripted agent. Returns (call_id, err)."""
    t = _tel()
    payload = {"from_number": t["from"], "to_number": number, "override_agent_id": agent_id,
               "retell_llm_dynamic_variables": variables,
               "metadata": {"source": "jetty", "callee": callee}}
    st, data, err = _http(RETELL_CREATE, payload)
    if err or st not in (200, 201) or not data.get("call_id"):
        return None, err or f"Retell said no ({st})"
    cid = data["call_id"]
    with LOCK:
        LIVE[cid] = {"status": data.get("call_status", "registered"), "callee": callee, "number": number,
                     "variables": variables, "started": time.time(), "summary": "", "outcome": "", "done": False}
    _log("call_placed", f"Calling {callee} at {number}: {json.dumps(variables)[:100]}")
    threading.Thread(target=_watch, args=(cid, callee), daemon=True).start()
    return cid, None

def _watch(cid, callee, sid=None):
    """Poll get-call until the call ends, then summarize the transcript into a spoken outcome."""
    deadline = time.time() + 600
    while time.time() < deadline:
        time.sleep(4)
        st, data, err = _http(RETELL_GET + cid, method="GET")
        if err or st != 200:
            continue
        status = data.get("call_status", "")
        with LOCK:
            if cid in LIVE: LIVE[cid]["status"] = status
        if status in ("ended", "error", "not_connected"):
            transcript = data.get("transcript", "") or ""
            summary, outcome = _summarize(callee, transcript, status,
                                          (data.get("call_analysis") or {}), data.get("disconnection_reason", ""))
            rec = (data.get("recording_url") or "")
            with LOCK:
                if cid in LIVE:
                    LIVE[cid].update(status=status, summary=summary, outcome=outcome, done=True, recording=rec)
            if CTX.get("raise_card"):
                try:
                    CTX["raise_card"]("notify", f"📞 Call to {callee} — {outcome}", summary,
                                      source="calls", speak=False)
                except Exception: pass
            _log("call_ended", f"{callee}: {outcome} — {summary[:100]}")
            return
    with LOCK:
        if cid in LIVE: LIVE[cid].update(done=True, outcome="timed out",
                                         summary=f"The call to {callee} ran long, sir — I stopped watching.")

def _summarize(callee, transcript, status, analysis, disconnect):
    """Claude reads the transcript → (spoken summary, one-word outcome). Falls back gracefully."""
    if status == "not_connected":
        return f"{callee} didn't pick up, sir.", "no answer"
    if status == "error":
        return f"The call to {callee} errored out, sir ({disconnect or 'unknown'}).", "error"
    cm = CTX.get("call_model")
    if not transcript:
        base = (analysis.get("call_summary") or "").strip()
        return (base or f"{callee} answered, sir — I've no transcript to read back."), "done"
    if not cm:
        return (analysis.get("call_summary") or f"Call to {callee} finished, sir."), "done"
    sysp = (CTX["jpersona"]() +
            "You just made a phone call for the user. Read the transcript and report back in 1-2 short "
            "spoken sentences to 'sir' — did it succeed, and the key details (time booked, price quoted, "
            "confirmation, or why it failed). Then on a new line write OUTCOME: <two or three words> "
            "(e.g. 'booked', 'declined', 'voicemail left', 'no answer', 'call back needed').")
    txt, err = cm([{"role": "user", "content": f"Callee: {callee}\nTranscript:\n{transcript[:6000]}"}], sysp, 400)
    if err or not txt:
        return (analysis.get("call_summary") or f"Call to {callee} finished, sir."), "done"
    outcome = "done"
    mo = re.search(r"OUTCOME:\s*(.+)", txt)
    if mo:
        outcome = mo.group(1).strip()[:24]
        txt = txt[:mo.start()].strip()
    return txt.strip(), outcome

def _log(kind, text):
    if CTX.get("log"):
        try: CTX["log"](kind, text)
        except Exception: pass
    try:
        with open(os.path.join(CTX.get("root", "."), "jetty-calls.jsonl"), "a") as f:
            f.write(json.dumps({"ts": int(time.time()), "kind": kind, "text": text}) + "\n")
    except Exception:
        pass

# ---------- HTTP surface ----------

def handle(handler, method, raw_path, payload):
    path = raw_path.split("?")[0]
    p = payload or {}

    if method == "GET" and path == "/api/calls":
        q = urllib.parse.parse_qs(urllib.parse.urlparse(raw_path).query)
        cid = (q.get("id") or [""])[0]
        with LOCK:
            handler._json(dict(LIVE.get(cid, {"status": "unknown"})) if cid
                          else {"live": [dict(v, id=k) for k, v in LIVE.items() if not v.get("done")]})
        return True

    if method != "POST" or not path.startswith("/calls"):
        return False

    if path == "/calls_prepare":
        task = (p.get("task") or "").strip()
        if not task:
            handler._json({"error": "who should I call, sir, and what for?"}, 400); return True
        if not configured():
            handler._json({"error": "no phone line yet, sir — add your Retell key, number and agent_id "
                                    "under \"telephony\" in config.json, then restart me."}, 400); return True
        c = classify_call(task, p.get("session"))
        callee = (p.get("callee") or "").strip() or c["callee"]
        kind = c["type"]
        variables = variables_for(kind, c["fields"])
        agent_id = agent_for(kind)
        number = to_e164(p.get("number") or "") or find_number_in(task)
        if not number:
            number, _note = lookup_number(callee, p.get("session"))
        cid = os.urandom(5).hex()
        PENDING[cid] = {"callee": callee, "number": number, "agent_id": agent_id, "variables": variables,
                        "kind": kind, "task": task, "need_number": not number}
        if not number:
            handler._json({"confirm_id": cid, "callee": callee, "kind": kind, "need_number": True,
                           "ask": f"I couldn't find a number for {callee}, sir — what number shall I ring?"})
            return True
        pretty = _pretty(number)
        handler._json({"confirm_id": cid, "callee": callee, "number": number, "pretty": pretty,
                       "kind": kind, "ask": f"{c['say']}  I'll ring {pretty}."})
        return True

    if path == "/calls_number":                      # user supplies a number the lookup missed
        pend = PENDING.get((p.get("confirm_id") or "").strip())
        if not pend: handler._json({"error": "nothing pending, sir"}, 400); return True
        num = to_e164(p.get("number") or "")
        if not num: handler._json({"error": "that's not a number I can dial, sir"}, 400); return True
        pend["number"] = num; pend["need_number"] = False
        handler._json({"number": num, "pretty": _pretty(num),
                       "ask": f"Ring {pend['callee']} at {_pretty(num)} and {pend['task']}? Say 'do it', sir."})
        return True

    if path == "/calls_go":
        pend = PENDING.pop((p.get("confirm_id") or "").strip(), None)
        if not pend: handler._json({"error": "nothing to dial, sir"}, 400); return True
        if not pend.get("number"): handler._json({"error": "I still need a number, sir"}, 400); return True
        if not configured(): handler._json({"error": "phone line not configured, sir"}, 400); return True
        cid, err = place(pend["callee"], pend["number"], pend["agent_id"], pend["variables"])
        if err: handler._json({"error": f"the line wouldn't connect, sir: {err}"}, 502); return True
        handler._json({"call_id": cid, "callee": pend["callee"], "number": pend["number"],
                       "pretty": _pretty(pend["number"]),
                       "say": f"Ringing {pend['callee']} now, sir — I'll report back the moment they're done."})
        return True

    if path == "/calls_cancel":
        PENDING.clear()
        handler._json({"ok": True}); return True

    return False

def _pretty(e164):
    if e164 and e164.startswith("+1") and len(e164) == 12:
        return f"({e164[2:5]}) {e164[5:8]}-{e164[8:]}"
    return e164 or ""

_CALLV = r"(?:call(?:\s+up)?|ring(?:\s+up)?|phone|dial|give\s+(?:\w+\s+)?a\s+(?:call|ring))"

def _guess_callee(task):
    m = re.search(_CALLV + r"\s+(?:the\s+)?([A-Z][\w'&.\- ]{1,40}?)(?:\s+(?:and|to|at|about|for|,)|$)", task)
    if m: return m.group(1).strip()
    m = re.search(_CALLV + r"\s+(?:the\s+)?([\w'&.\- ]{2,40}?)(?:\s+(?:and|to|at|about|for|,)|$)", task, re.I)
    return (m.group(1).strip() if m else "them")

def init(ctx):
    CTX.update(ctx or {})
    print(f"[calls] hands-free calling online — {'Retell configured' if configured() else 'awaiting Retell key in config.json'}")

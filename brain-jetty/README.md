# Jetty — Voice Second Brain (Brain Studio V3)

Talk to your second brain. Speak or type a question → Claude (or GLM) answers from your
own markdown notes → the 3D knowledge galaxy flies to and lights the source node → the
answer is spoken back in your own **ElevenLabs "Jetty" voice.**

Plus: conversation memory, tasks & reminders, a morning briefing, voice note capture &
editing, cross-note synthesis, a hands-free wake word, **proactive scheduled briefings**,
and an agentic **"hands"** mode (`claude -p`) that uses your connected tools — draft-safe,
with a confirm step before anything is sent.

**An AI Workshop exclusive.**

## Install (one time)

**Let Claude do it:** open Claude Code and say
> Install the skill from ~/Downloads/brain-jetty-skill.zip

**Or one command:**
```bash
unzip -o ~/Downloads/brain-jetty-skill.zip -d ~/.claude/skills
```

You'll have `~/.claude/skills/brain-jetty/` with `server.py`, `build.py`, the viewers,
and `config.example.json`. No dependencies beyond Python 3 (already on every Mac), a
browser, and — for the agent — the `claude` CLI.

## Set up your brain (3 steps)

```bash
cd ~/.claude/skills/brain-jetty

# 1) Build the galaxy from YOUR vault (writes viewer/graph-data.js)
python3 build.py --vault "/path/to/your/notes" --out ./viewer

# 2) Add your keys (stays local; never shipped, never sent to the browser)
cp config.example.json config.json
#   edit config.json: vault, model.api_key/model, elevenlabs.api_key/voice_id

# 3) Run + open in Chrome
python3 server.py            # → http://localhost:4719
```

The brain runs on **Claude** (`claude-opus-4-8`) or any **OpenAI-compatible** model
(e.g. **GLM 5.2** via OpenRouter/Z.ai — just set `model.base_url`). **Voice is free by default:**
Jetty speaks in your **browser's own built-in voice** with no key needed. Want the cinematic
"Jetty" voice? Add your own ElevenLabs `api_key` + `voice_id` to `config.json` — that's the only
voice setup, and it's entirely optional.

## Talk to it

- **Ask** — "What is X?" → answers from your notes, flies to + lights the node, speaks it.
- **Follow up** — "and what does it cost?" → resolved from conversation memory.
- **Synthesize** — "summarize everything about X across my notes" → reasons over many notes, lights the whole cluster.
- **Navigate** — "show me X" → flies the galaxy to that node.
- **Capture** — "remember that …" → writes a real `.md` and grows the graph live.
- **Edit** — "add to my X note: …" → appends to that note.
- **Tasks** — "remind me to …" / "what's on my list?" → tasks panel (top-right).
- **Briefing** — "good morning" → spoken rundown of your **real** day (Gmail + Calendar, read-only) + tasks.
- **Proactive** — 🔔 or "brief me every morning" → greets you each morning with your actual day, unprompted.
- **Pulse / watch** — "anything I should know?" / "what's new?" → a quick scan of email + calendar for what's pressing.
- **Inbox triage** — "what's in my inbox?" / "triage my email" → reads your inbox (read-only) and tells you what actually needs you.
- **See your screen** — "look at my screen" → shares your screen (you pick a window) and Claude's vision tells you what it sees / helps.
- **Remember me** — "remember about me …" / "from now on …" → long-term memory (`jetty-memory.md`) that personalizes every reply.
- **Agent Inbox** — "what needs me?" → a command deck (top-right) where Jetty drops cards he raises in the background — *notify / ask / approve*. Approve one with **"do it"**.
- **Focus mode** — "focus mode" / "do not disturb" → the smart-interrupt governor holds everything but the genuinely urgent (money/high-priority still breaks through); "focus off" to resume.
- **Time Machine** — "what was I doing last Tuesday?" / "when did I first mention X?" → a spoken recap while the graph **rewinds** to those nodes.
- **Web research (new in V4)** — "research X" / "look up Y" / "what's the weather right now?" → live internet search, a tight spoken answer, and a 🌐 **"What I found"** card (with sources) that stays on screen until you dismiss it.
- **Brain hot-swap (new in V4)** — "Jetty, try on grok / gpt / gemini / haiku…" → swaps his underlying model on the spot (one OpenRouter key unlocks the whole catalogue); "back to your usual brain" restores. "What brains do you have?" lists the shelf.
- **Voice wardrobe & personas (new in V4)** — "switch your voice to George", "GLaDOS mode" / "pirate" / "coach", "humor to 90", "be less funny" → TARS-style dials; "back to your usual voice" restores.
- **Mac control (new in V4)** — "volume to 40", "dark mode", "open Chrome", "evening mode", "find my invoice PDF", "clean up my downloads" → deterministic macOS control; anything that moves files shows a plan first and waits for **"do it"**.
- **Timed reminders (new in V4)** — "remind me to call the bank tomorrow at 5pm" → a ⏰ card slides in and he speaks up when it's due.
- **Agent hands** — "what's on my calendar?", "draft an email to …", "turn this video into posts", "open Chrome and …" → runs Claude Code with your connected tools (Gmail, Calendar, Semrush, vidIQ, Blotato social, computer use, GEO/SEO skills…).
- **Phone calls** — "call …" / "book a table for 4" → places a real call in your voice (needs a `telephony` provider in config; asks you to confirm first).
- **Confirm** — drafted sends/posts/calls wait for you to say **"do it"** (or "cancel").
- **Barge-in** — while hands-free, say "Jetty…" (or "stop / wait / hold on") to cut him off mid-sentence. Random room noise can't — interrupts must be addressed to him.
- **Strict mode (new in V4)** — "strict mode" / "require your name" → he only ever responds to the wake word (no follow-up window); "relaxed mode" restores it.

**Buttons:** 🎙 push-to-talk · 👂 hands-free wake word ("Jetty, …") · 🔔 proactive briefings.
Graph: drag = orbit · scroll = zoom · click = focus · shift-click = path · I = isolate · esc = clear.

## Endpoints (the server proxies these so keys never reach the browser)

`POST /chat` · `/tts` · `/remember` · `/edit` · `/task` `/tasks` `/task_done` · `/briefing`
· `/pulse` · `/inbox` · `/see` · `/call` · `/remember_me` · `/recall` (time machine) · `/agent`
`/agent_confirm` · agent-inbox `/inbox_add` `/inbox_ack` `/inbox_act` `/inbox_dismiss` `/dnd`
· `GET /api/proactive` `/api/inbox` `/api/dnd` `/api/tasks` `/api/brand`. The server binds
`127.0.0.1` only and rejects cross-origin POSTs.

## Safety

The agent (`/agent`) shells out to **`claude -p`**, so Claude Code must be installed and
logged in. **Draft mode is enforced at the process boundary** — the subprocess is launched
with `Bash/Write/Edit/Task` and every `*send*/*post*/*delete*/*spend*` MCP tool **disallowed**,
so a draft can read & research but cannot send, post, delete, spend, or write. Anything that
would take such an action is **drafted and held**; it only executes after you say **"do it"**.
Tune `config.json` → `agent.disallow`.

## White-label it (sell it to clients)

Set the brand in `config.json` (`"name"`, optional `"logo"`), rebuild the galaxy from the
client's docs, and you have *their* company as a talking brain — a strong pitch for the AIOS.

## Manual / advanced

```bash
# regenerate the galaxy any time your notes change
python3 build.py --vault "/path/to/your/notes" --out ./viewer
```
`config.json`, `jetty-memory.md`, and the `jetty-*.json` / `jetty-episodes.jsonl` state
(tasks, proactive, inbox, dnd, episodes) plus `agent-workspace/` are **local** — keep them out of
any shared zip (the bundled `.gitignore` already excludes them all).

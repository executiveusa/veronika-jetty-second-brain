---
name: brain-jetty
description: Jetty — a voice-driven AI second brain. Talk to your markdown vault out loud; Claude (or GLM) answers from your notes, the 3D knowledge galaxy flies to and lights the source node, and the answer is spoken back in your own ElevenLabs "Jetty" voice. Adds tasks & reminders, a morning briefing, voice note capture/editing, cross-note synthesis, a hands-free wake word, proactive scheduled briefings, and an agentic "hands" mode that runs Claude Code (claude -p) with your connected tools — draft-safe, with a confirm step before anything is sent. Use when the user says "jetty", "voice second brain", "talk to my notes", "AI butler", "voice assistant for my vault", or wants to add a talking assistant to a Brain Studio galaxy.
---

# Jetty — Voice Second Brain (/brain-jetty)

Turn a markdown vault into a **talking, 3D second brain.** Speak or type → the brain
answers from your notes → the galaxy flies to and lights the source node → the answer
is spoken back in your ElevenLabs voice. Built on the Brain Studio graph viewer.

This is the **V3 assistant**. (V1/V2 was the static graph viewer — `build.py` + the
2D/3D viewers still ship for generating the galaxy; Jetty adds the voice + assistant
layer on top via `server.py`.)

## Setup (once)

1. **Generate the galaxy** from a markdown vault (any Obsidian vault / notes folder):
   ```bash
   python3 build.py --vault "/path/to/your/vault" --out ./viewer
   ```
   This writes `viewer/graph-data.js`. (A small demo `graph-data.js` ships so it works
   out of the box — regenerate it against your own vault to make it *your* brain.)

2. **Add your keys.** Copy the template and fill it in — `config.json` stays on your
   machine, is never served to the browser, and is excluded from any shared zip:
   ```bash
   cp config.example.json config.json
   ```
   In `config.json` set:
   - `vault` — absolute path to the same folder you built from (for voice capture/edit).
   - `model.api_key` + `model.model` — the brain. Native **Claude** (`claude-opus-4-8`,
     no `base_url`), or any **OpenAI-compatible** endpoint (e.g. **GLM 5.2** via
     OpenRouter/Z.ai) by setting `model.base_url`.
   - `elevenlabs.api_key` + `elevenlabs.voice_id` — **optional.** Leave empty and Jetty
     speaks in your **browser's built-in voice** (free, no key, works out of the box). Fill in
     your own ElevenLabs key + voice_id only for the premium cinematic "Jetty" voice.
   - `claude_bin` (optional) — path to the `claude` CLI for the agent (`/agent`); auto-detected otherwise.

3. **Run it** and open in **Chrome** (Web Speech + audio need Chrome/Edge):
   ```bash
   python3 server.py        # → http://localhost:4719
   ```

## What you can say

| Say… | Jetty… |
|---|---|
| "What is X?" / "How does Y work?" | answers from your notes, flies to + lights the source node, speaks the reply |
| "and what does it cost?" | follows up using conversation **memory** |
| "summarize everything about X across my notes" | **synthesizes across many notes** and lights the whole cluster |
| "show me X" / "go to X" | navigates the galaxy to that node |
| "remember that …" | **captures** a new note (writes a real `.md`, grows the graph live) |
| "add to my X note: …" | **appends** to an existing note |
| "remind me to …" / "what's on my list?" | adds / lists **tasks** (right-side panel) |
| "good morning" / "brief me" | spoken **morning briefing** (open tasks + recent captures) |
| "brief me every morning" / 🔔 button | **proactive scheduled briefing** — greets you each morning unprompted |
| "research X" / "look up Y" / "what's the weather right now?" | **live web research** — searches the internet, speaks a tight answer, sources on screen |
| "what's on my calendar?" / "draft an email to …" | **agent hands** via `claude -p` with your connected tools |
| "do it" / "cancel" | **confirms or cancels** a drafted send/post action |
| "what needs me?" | reads the **Agent Inbox** — cards Jetty raised in the background (notify / ask / approve) |
| "focus mode" / "focus off" | the **smart-interrupt governor** holds all but the urgent, then resumes |
| "what was I doing last Tuesday?" / "when did I first mention X?" | **Time Machine** — spoken recall while the graph rewinds to those nodes |
| "try on grok / gpt / haiku" · "back to your usual brain" | **hot-swaps the brain** (one OpenRouter key = the whole model catalogue) |
| "switch your voice to George" / "GLaDOS mode" / "humor to 90" | **voice wardrobe, personas, TARS dials** |
| "volume to 40" / "open Chrome" / "find my invoice PDF" / "clean up my downloads" | **Mac control by voice** (file moves show a plan → "do it") |
| "strict mode" / "relaxed mode" | only respond to the wake word ↔ allow no-name follow-ups |

**Voice controls:** 🎙 push-to-talk · 👂 hands-free wake word ("Jetty, …") · 🔔 proactive briefings.

## Safety model (read before using the agent)

`/agent` runs **Claude Code headless** with your connected MCP tools and skills.
- **Draft mode is the default and is enforced at the process boundary**, not just by a
  prompt: `claude -p` is launched with `Bash`, `Write`, `Edit`, `Task`, and all
  `*send*/*post*/*delete*/*spend*` MCP tools **disallowed**, so a draft can *read and
  research* but physically **cannot** send, post, delete, spend, write files, or shell out.
- Anything that would send/post/spend is **prepared as a draft** and held; Jetty asks
  you to confirm. Only when you say **"do it"** does it re-run with execution allowed.
- The agent runs in a scoped `agent-workspace/`, never with write access to your vault
  unless you confirm an action. Tune the blocklist via `config.json` → `agent.disallow`.

## Distribution

Ship the zip (see README) — it **excludes** `config.json`, your task/proactive state,
and your personal `graph-data.js`. Each member brings their own keys and builds their
own galaxy. Free tier = browser speech; paid = the ElevenLabs Jetty voice.

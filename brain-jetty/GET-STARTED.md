🧠 AI Second Brain **V4** — talk to your entire brain, out loud (meet JETTY)
This is the full system from the video. Set it up once, then talk to your whole knowledge vault any time — by voice. Ask a question and Jetty answers from *your* notes, flies the 3D galaxy to the exact source, lights it up, and speaks the answer back in a voice that's yours. No typing, no searching, no dashboards.

✨ **What's new in V4**

* 🌐 **Live web research** — "Jetty, research X" / "what's the weather right now?" → he searches the internet, speaks a tight answer, and drops a **"What I found" card** (with sources) that stays on screen until you dismiss it.
* 🧠 **Brain hot-swap** — "Jetty, try on grok / gpt / gemini / haiku" swaps his underlying AI on the spot. One OpenRouter key (optional, `config.json`) unlocks the whole catalogue. "Back to your usual brain" restores.
* 🎭 **Voice wardrobe + personas** — "switch your voice to George", "GLaDOS mode", "pirate", "humor to 90", "be less funny" — TARS-style dials.
* 🍎 **Mac control by voice** — "volume to 40", "dark mode", "open Chrome", "evening mode", "find my invoice PDF", "clean up my downloads" (file moves show a plan first; you say "do it").
* ⏰ **Timed reminders that actually fire** — "remind me to call the bank tomorrow at 5pm" → a card slides in and he speaks up when it's due.
* 📡 **A second live-voice engine** — GPT Realtime speech-to-speech for the 📡 button (optional OpenAI key); Claude + your vault stay the brain either way.
* 💡 **Philips Hue** — the room pulses while he speaks (optional; say "set up the lights").
* 🎙 **A calmer, smarter mic** — background noise can't cut him off or trigger random replies anymore; jokes get straight answers (no "one moment, sir" on banter); prices read naturally ("$97/mo" → "97 dollars a month"); and **"strict mode"** makes him respond only to his name.

Step 1 — Install (one time, ~30 sec)
Download `brain-jetty-skill-v4.zip` (attached below). Then either:
Easiest — let Claude do it. Open Claude Code and type:

```
Install the skill from my Downloads — brain-jetty-skill-v4.zip
```

Or one Terminal command:

```
unzip -o ~/Downloads/brain-jetty-skill-v4.zip -d ~/.claude/skills
```

You should now have `~/.claude/skills/brain-jetty/`. Done — you never do this again.

Step 2 — Set up your brain (one time, ~3 min)
Open Claude Code in that folder and type:

```
/brain-jetty
```

…and it walks you through pointing at your notes and adding your key. Or do it yourself in Terminal:

```
cd ~/.claude/skills/brain-jetty
python3 build.py --vault "/path/to/your/notes" --out ./viewer   # turn YOUR notes into the galaxy
cp config.example.json config.json                               # then open config.json and add your model key
python3 server.py                                                # → http://localhost:4719
```

Open **http://localhost:4719** in **Chrome**. Your brain is live. 🎉
🧠 Point it at *any* folder of notes — Obsidian, plain markdown, anything. Only two things go in `config.json`: your notes folder + one AI key (Claude `claude-opus-4-8`, or GLM/any OpenAI-compatible model). It all stays on your computer.

Step 3 — Talk to it (every time)
Open the page in Chrome, click 🎙 (or 👂 for hands-free) and just talk:

```
"What is [anything in your notes]?"      → answers + flies to the source, spoken
"Summarize everything about X"           → reasons across many notes, lights the cluster
"Remember about me, I …"                 → long-term memory, personalizes every reply
"Good morning"                           → your real day: calendar + the emails that need you
"Remind me to …" / "What's on my list?"  → tasks
"What's in my inbox?"                     → triage: what needs you vs. noise
"Look at my screen"                       → shares your screen, tells you what it sees
"Research the best X" / "look up Y"      → live web search + a "What I found" card
"Try on grok" / "back to your usual brain" → hot-swap his underlying AI
"Volume to 40" / "open Chrome"            → Mac control by voice
"Strict mode"                              → only respond when you say "Jetty"
"Draft an email to …"                     → agent hands (asks before sending anything)
```

Jetty will: ① find the answer in *your* notes, ② fly to + light the source node, ③ speak it back in your voice, ④ remember what matters, and ⑤ do real work for you — always asking before it sends or posts. 🎉
🖥 Want it to see your screen? Click the 🖥 button, pick **Entire Screen**, then say "look at my screen." 📞 Want it to make real phone calls? Add a Vapi/Retell key in `config.json` (optional).

🎙️ The voice is yours — and different for everyone
By default Jetty speaks in your **browser's own built-in voice** — free, no account, works instantly (it grabs a British-butler voice if your system has one, so it sounds a little different for each person — that's *your* Jetty). Want the **cinematic movie-Jetty voice**? Add your own **ElevenLabs** `api_key` + `voice_id` to `config.json` (ElevenLabs → Voices → the `⋯` menu → **Copy Voice ID**, or clone your own voice). Every voice_id is unique, so **Jetty sounds different for each of us** — change it to any voice you like, anytime. No key = browser voice, and nothing breaks.

🔄 How to update to a new version
When a new version drops here: download the new zip (this one is `brain-jetty-skill-v4.zip`) and unzip it over the folder (choose **Replace**). Your existing `config.json` keeps working as-is — the new V4 blocks (`openrouter`, `openai`, `hue`, `models`) are all optional; copy them from the fresh `config.example.json` only if you want those features. Your `config.json` (keys) and `jetty-memory.md` (what Jetty knows about you) are **never in the zip, so they're safe.** Then re-run `python3 build.py --vault "/path/to/your/notes" --out ./viewer` to bring your own galaxy back, and **hard-reload** Chrome (Cmd/Ctrl + Shift + R). Your keys, voice, and memory carry straight over.

📎 On this page
`brain-jetty-skill-v4.zip` · `GET-STARTED.md` (the full guide — also lives inside the zip)

🛠️ Troubleshooting

* Page looks old / a feature's missing → **hard-reload** (Cmd/Ctrl + Shift + R).
* No voice → use **Chrome**, and click the page once (browsers block audio until you interact).
* "Look at my screen" just says *tap 🖥* → click the **🖥** button first, pick **Entire Screen**, then ask.
* Briefing / inbox say "no access" → those read your **Gmail/Calendar** — connect (and re-authorize) those tools. Everything else works without them.
* "Agent hands" (email / research / posting) do nothing → the agent needs **Claude Code** installed + logged in. Notes / voice / briefing don't.
* `/brain-jetty` does nothing → confirm `~/.claude/skills/brain-jetty/` has `SKILL.md` inside, then restart Claude Code.
* Stuck? Post a screenshot in the community.

📂 Files to attach to the lesson (ready now)
| File | Location |
|---|---|
| `brain-jetty-skill-v4.zip` (the install — everything in one) | `~/Downloads` |
| `GET-STARTED.md` (the full guide, also bundled inside the zip) | project root |

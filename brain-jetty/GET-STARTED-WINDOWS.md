# 🤖 JETTY V5 (Tools Edition) — Get Started on Windows

Welcome! In about 10 minutes you will have a voice assistant running on your own computer that talks back, remembers your notes, checks your email and calendar, and connects to thousands of apps.

Everything runs locally on YOUR machine with YOUR keys.

---

## ✅ What you need

1. Windows 10 or 11
2. Python 3: download from python.org and during install CHECK THE BOX "Add python.exe to PATH" (this matters!)
3. Google Chrome (for the microphone and voice)
4. An Anthropic API key. Get one at console.anthropic.com (Billing: add a few dollars of credit). This is the ONLY required key.

Optional extras: ElevenLabs key (cinematic voice), OpenRouter key (swap brains to Grok or GPT by voice), an MCP bridge account such as Zapier if you want everyday apps like email and calendar (optional).

---

## 🚀 Install (5 steps)

1. Unzip this folder anywhere, for example Documents.

2. In the folder, COPY the file `config.example.json` and rename the copy to `config.json`.

3. Open `config.json` in Notepad. Find this line and paste your Anthropic key:
   `"api_key": "PUT-YOUR-MODEL-API-KEY-HERE"`

4. Double click `START-JETTY.bat`. A black window appears and stays open. That window IS the server, leave it running. (If Windows SmartScreen warns you, click More info, then Run anyway.)

5. Open Chrome and go to: `http://localhost:4719`

You should see the galaxy and hear a greeting. Say hi!

---

## 🗣 Talking to Jetty

- Type in the bottom bar, or click the 🎙 button and speak
- Click the 👂 button for hands free mode, then just say "Jetty" followed by anything
- While he is talking, just start speaking. He pauses instantly and listens
- Say "that's okay, just get back to me when it's done" during long tasks and he works silently
- Say "you don't have to read it, I'll read it myself" and answers go to the screen only

Hover over any round button at the bottom to see what it does.

---

## 🔌 The Tool Armory

Click the 🔌 plug button. This is where Jetty gets real hands. Two ways to add tools:

**1. One click tiles.** Canva, Notion, GitHub, Figma, Airtable and more connect with a single click and a normal sign in.

**2. Bring your own MCP server.** Click "Add your own tool", give it a name, and paste any MCP server URL. Jetty probes it, handles the sign in if one is needed, and shelves it like any other tile. Any service that publishes an MCP endpoint works.


**Everyday apps like email and calendar:** most of them do not publish MCP endpoints yet, so any MCP bridge service can fill the gap. One popular option is a free Zapier account: at mcp.zapier.com you can create your own MCP server, choose which apps and actions it exposes (tip: for email choose Create Draft, never Send), and paste its URL into the Zapier tile. Similar bridges work the same way. This is entirely optional.

Then try: "check my email" or "what's on my calendar tomorrow". Jetty shows a receipt under every answer naming exactly which tool ran, and if something is not connected he says so honestly instead of making things up.

---

## 🧠 Swap brains by voice

- "Jetty, try on sonnet" or "try on haiku" or "try on fable"
- "Back to your default brain"
- With an OpenRouter key in config.json: "try on grok", "try on gpt", "try on gemini"
- "What brains do you have?"

---

## 📝 Your own notes (optional but magical)

The zip ships with a small demo brain. To load YOUR markdown notes:

1. In `config.json`, set `"vault"` to the folder that holds your .md files (use forward slashes, for example `C:/Users/you/Documents/notes`)
2. In Command Prompt inside the brain-jetty folder, run: `python build.py --vault "C:/path/to/your/vault" --out viewer`
3. Restart Jetty

---


## ⚠️ Windows notes (honest list)

Everything above works on Windows: voice chat, the Tool Armory, Zapier, brain swaps, web research, reminders, languages.

A few Mac only extras simply stay off on Windows: the floating desktop orb, Mac control voice commands (volume, windows, scenes), the menu bar app, and Raycast shortcuts. You are not missing anything core.

---

## 🔧 If something is not working

- "python is not recognized": reinstall Python from python.org and CHECK "Add python.exe to PATH"
- Page will not load: is the black server window still open? Double click `START-JETTY.bat` again
- No voice: Jetty uses your browser voice for free. For the cinematic voice, add an ElevenLabs key
- Mic blocked: click the padlock in Chrome's address bar and allow the microphone
- Weird page after an update: hard reload with Ctrl Shift R
- Tool answers time out: say "check again"


### A connected tool suddenly stopped working

Almost never broken code. Walk this list in order:

1. Say "check again". Slow patches happen; a fresh run fixes most of them
2. Check your bridge credits. Bridge services meter usage: on Zapier, open your usage page. Each JETTY tool call spends about two tasks, and when the plan runs out every call quietly fails or comes back empty. Worked this morning, dead this afternoon? This is the culprit nine times out of ten
3. Look at the tile in the armory: still connected, or paused? If the provider regenerated your server URL, paste the new one into the tile
4. Check the actions on the bridge side: if you never exposed an email action, JETTY will honestly say email is not connected. Add the app and actions in the bridge dashboard
5. Restart the server and hard reload the Chrome tab

The receipt under every answer names exactly which tool ran. No receipt means no tool call happened, which points at connection or credits, not the tool.

### The last resort that almost always works

You have an AI coding assistant, use it. Screenshot the error (or copy the text from the server window), open Claude Code inside your brain-jetty folder, paste the screenshot and say: "JETTY is not working. Here is the error. Read this folder and fix it." It usually repairs it in one pass.

Have fun, and post what you build in the community! 🚀

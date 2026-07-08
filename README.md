# JETTY™
## Your AI Second Brain — Salt Lake City
### The Pauli Effect | Emerald Tablets™

> *"Your thinking, coiled."*

Named for Robert Smithson's **Spiral Jetty** (1970) — a 1,500-foot coil of black basalt on the north shore of the Great Salt Lake. Every Salt Lake City resident knows this place. JETTY™ is named for its form: ideas coiled together, each connected to every other.

---

## WHAT IS JETTY™

JETTY™ is a personal AI second brain that runs on your own server. You talk to it. It answers from your notes. Every idea you save becomes a star in a 3D knowledge galaxy. The stars connect automatically based on what they share.

It is not a chatbot. It is not a generic AI assistant. It is a system that learns your business and speaks like it knows you — because it does.

**It does three things:**
1. **Remembers everything** — notes, contacts, ideas, decisions
2. **Answers from your notes** — not from the internet, from what you've saved
3. **Executes actions** — sends emails, adds calendar events, saves contacts (via Composio)

---

## QUICKSTART (30 MINUTES)

### Prerequisites
- Docker installed
- At least one AI API key (Groq is free — see below)

### 1. Configure environment
```bash
cp .env.example .env
nano .env   # Add at least one API key
```

### 2. Start
```bash
docker compose up --build -d
open http://localhost:4700
```

### 3. Talk to JETTY™
- Type or speak anything in the chat bar at the bottom
- Say **"remember that I'm looking for ops roles in Silicon Slopes"**
- Watch a new star appear in your galaxy

---

## FREE API KEYS (Zero cost to start)

| Provider | Cost | Get Key | Best For |
|----------|------|---------|---------|
| **Groq** | Free | [console.groq.com](https://console.groq.com) | Fast queries, daily use |
| **Mistral** | Free tier | [console.mistral.ai](https://console.mistral.ai) | Writing, analysis |
| Anthropic | Paid | [console.anthropic.com](https://console.anthropic.com) | Best reasoning |
| OpenAI | Paid | [platform.openai.com](https://platform.openai.com) | GPT-4o access |

**Start with Groq.** It's free, fast, and handles most queries perfectly. Switch to Claude for complex reasoning when you need it.

---

## ADDING YOUR NOTES

Drop any `.md` (Markdown) or `.txt` file into the `notes/` folder.
JETTY™ indexes it within seconds. Your galaxy grows automatically.

**What to add first:**
1. Your résumé (plain text)
2. Your job search goals
3. Key clients or contacts
4. Ideas you don't want to lose
5. Meeting notes and decisions

**Pre-loaded notes (SLC-specific):**
- `notes/silicon-slopes/About-Silicon-Slopes.md` — SLC tech scene 2026
- `notes/job-search/Cover-Letter-Formula.md` — P.A.S.S. cover letter method
- `notes/ai-tools/Free-AI-Tools-Guide.md` — When to use each free tool
- `notes/ai-tools/How-to-Export-Your-AI-Data.md` — Export from ChatGPT, Claude, etc.

---

## HOSTINGER VPS DEPLOYMENT

```bash
# On your Hostinger VPS (Ubuntu 22.04+)
apt update && apt install -y docker.io docker-compose-v2
git clone [your-repo] jetty && cd jetty
cp .env.example .env && nano .env
docker compose up --build -d

# JETTY™ is live at http://YOUR_SERVER_IP:4700
```

For HTTPS: point your domain to the VPS and add an Nginx reverse proxy with Let's Encrypt.

---

## VISION MODE (VisionClaw Integration)

JETTY™ includes a Vision Mode powered by VisionClaw + Gemini Live. When active, your phone camera becomes a note-taker:

- **Business cards** → auto-saved contact + draft follow-up email
- **Whiteboards** → transcribed and saved to vault
- **Job postings** → read and matched to your notes
- **Documents** → extracted and connected to existing knowledge

Vision mode requires a **Gemini API key** (free at [aistudio.google.com](https://aistudio.google.com)).

---

## FILE STRUCTURE

```
jetty-tm/
├── .emerald-tablets/
│   └── EMERALD_TABLETS.md     ← prime directive (installed first, always)
├── tokens/
│   └── design-tokens.css      ← full Spiral Jetty color token system
├── design-system/
│   └── JETTY_DESIGN_SPEC.md   ← complete UI/UX specification
├── frontend/
│   ├── index.html             ← full app shell
│   └── assets/
│       ├── style.css          ← Spiral Jetty visual system
│       └── app.js             ← galaxy, chat, voice, model switcher
├── backend/
│   └── main.py                ← FastAPI, 4-model support, SOUL.md loader
├── ops/
│   ├── hermes/
│   │   └── SOUL.md            ← JETTY™ agent persona (SLC-specific)
│   └── reports/               ← machine-readable completion files
├── notes/                     ← knowledge vault (put files here)
│   ├── silicon-slopes/
│   ├── job-search/
│   ├── ai-tools/
│   └── captures/              ← auto-created "remember that" saves
├── .env.example               ← copy to .env
├── docker-compose.yml
└── README.md
```

---

## EMERALD TABLETS™ COMPLIANCE

| Gate | Specification | Status |
|------|--------------|--------|
| UDEC Floor | 8.5/10 minimum on all code | ✅ Enforced |
| Secret Safety | All keys in .env, never in code | ✅ |
| Blast Radius | Max 3 services per automated action | ✅ |
| Feedback Loops | Quality gate + cost guard + learning | ✅ |
| One Agent | HERMES™ orchestrator + Neo4j graph | ✅ |
| Plain Language | Non-technical UI throughout | ✅ |
| Spiral Identity | All visual decisions traceable to Spiral Jetty | ✅ |

---

## SUPPORT

Files in `ops/reports/` contain machine-readable completion status.
Agent handoff is zero-context: any agent can read this README + ops/reports/ and continue without starting over.

---

*JETTY™ v1.0 | The Pauli Effect*
*Emerald Tablets™ Quality Floor: UDEC 9.0/10*
*"Your thinking, coiled."*

---

## v1.1 Waves Landing

This package adds a public cinematic landing page at `/` using the generated Spiral Jetty sunset image with animated wave shimmer, click ripples, custom cursor, Earendil-inspired dropdown behavior, bottom appearance toggle, and a direct handoff into the private second-brain app at `/app`.

Public/private separation:

- `/` — public Jetty™ marketing/demo page
- `/app` — private second-brain UI
- `/api/*` — server-side agent endpoints

The landing page uses `/frontend/assets/landing.css`, `/frontend/assets/landing.js`, and `/frontend/assets/jetty-hero.png`. The private app keeps its own stylesheet at `/frontend/assets/app-style.css` and keeps the existing `/frontend/assets/app.js` behavior.

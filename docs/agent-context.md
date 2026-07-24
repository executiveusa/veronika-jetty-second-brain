# Agent Context & System Memory

## Repo Purpose
JETTY WELLNESS™ (formerly JETTY™) is a personal AI second brain and outcome-based operations platform designed specifically for non-technical wellness founders in Utah (yoga studio owners, natural health practitioners, retreat organizers). It features a dual-mode architecture: a clean, calming Wellness Mode dashboard as the default experience, and an optional 3D visual Knowledge Galaxy and voice assistant.

## Stack
- **Frontend**: Vanilla HTML5, CSS3 (Sage/Gold design tokens), Three.js (3D galaxy visualization), Google Fonts (Poppins & Inter)
- **Backend**: FastAPI (Python 3.10+), asyncpg (PostgreSQL memory via Supabase), httpx
- **Sidecar**: `brain-jetty` (V5 Tools Edition) running locally on port 4719
- **Database**: PostgreSQL / Supabase (`veronika_jetty` schema with `chat_sessions`, `chat_messages`, `businesses`, `clients`, `appointments`, `transactions`, and `automations` tables, with fallback in-memory stores)

## Directory Structure
- `/backend`: FastAPI server, database adapters, LLM routing logic, voice proxy, and Wellness API endpoints
- `/frontend`: Web application assets (`wellness.html`, `index.html`, `app.html`, `wellness.css`, `wellness.js`)
- `/brain-jetty`: Standalone V5 sidecar engine, local UI (`viewer/`), tools, and prompt skills
- `/notes`: Markdown vault indexed into the knowledge graph
- `/ops`: Operational scripts, database migrations, and HERMES soul context
- `/docs`: Architecture specs (`JETTY_WELLNESS_SPEC.md`), task memory, and agent context

## Important Conventions & Rules
- Brand/Persona: Jetty Wellness™ (Utah Founder Edition).
- Dual Mode: `/app` serves `wellness.html` (Wellness Mode), `/app/brain` or `/brain` serves `app.html` (3D Galaxy).
- Plain-Language Rule: UI copy must avoid technical terms like "agent", "schema", "API", or "credits". Use "Your Assistant", "Automations", "Connections".
- Sidecar Port: Exposes `http://localhost:4719`.
- Main App Port: Default `http://localhost:4700`.

## Recent Decisions & Changes
- Implemented Jetty Wellness Phase 1 MVP (`commit 197e20a`).
- Created `docs/JETTY_WELLNESS_SPEC.md` documenting strategic redesign.
- Added database tables (`businesses`, `clients`, `appointments`, `transactions`, `automations`) and REST APIs.
- Built responsive Wellness Mode frontend with sage/gold design system, onboarding wizard, Home dashboard, Clients CRM, Appointments, Money, Automations Hub, Connections, and Second Brain mode switch.

## Test & Build Commands
- Run backend: `python -m uvicorn backend.main:app --port 4700`
- Run sidecar: `cd brain-jetty && python server.py`
- Validate Python syntax: `Get-ChildItem -Path "backend", "brain-jetty" -Filter "*.py" | ForEach-Object { python -m py_compile $_.FullName }`

## Next Steps
- Add Stripe & Google OAuth callback handlers for live production credentials.
- Deploy to Vercel/VPS production instance.

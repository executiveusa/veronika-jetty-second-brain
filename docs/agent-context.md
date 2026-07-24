# Agent Context & System Memory

## Repo Purpose
JETTY™ is a personal 3D AI second brain and multi-agent operating system tailored for Salt Lake City, Utah entrepreneurs and digital studios. It combines a 3D visual knowledge galaxy, voice assistant sidecar, and multi-model backend integration.

## Stack
- **Frontend**: Vanilla HTML5, Three.js (3D galaxy visualization), CSS3, JavaScript (ES6 Modules)
- **Backend**: FastAPI (Python 3.10+), asyncpg (PostgreSQL memory via Supabase), httpx
- **Sidecar**: `brain-jetty` (V5 Tools Edition) running locally on port 4719 with python sidecar engine (`server.py`, `missions.py`, `pocket.py`, `tools.py`)
- **Database**: PostgreSQL / Supabase (`veronika_jetty` schema with `chat_sessions` and `chat_messages` tables)

## Directory Structure
- `/backend`: FastAPI server, database adapters, LLM routing logic, voice proxy
- `/frontend`: Web application assets (`index.html`, `app.html`, 3D visualizer script, styles)
- `/brain-jetty`: Standalone V5 sidecar engine, local UI (`viewer/`), tools, and prompt skills
- `/notes`: Markdown vault indexed into the knowledge graph
- `/ops`: Operational scripts, database migrations, and HERMES soul context
- `/docs`: Architecture, task memory, and agent context

## Important Conventions & Rules
- Brand/Persona: JETTY™ (formerly Jarvis). Do not revert branding in code or user-facing strings.
- Sidecar Port: Exposes `http://localhost:4719`.
- Main App Port: Default `http://localhost:4700`.

## Recent Decisions & Changes
- Merged V5 sidecar upgrade into `main` branch (`commit 5b8df69`).
- Custom transformation script converted all V5 "Jarvis" defaults and files to "Jetty" while retaining new V5 features (`missions.py`, `tools.py`, `pocket.py`, `presence.py`).
- Pre-compiled and validated Python codebase; zero syntax errors.

## Test & Build Commands
- Run backend: `uvicorn backend.main:app --port 4700`
- Run sidecar: `cd brain-jetty && python server.py` (or double click `START-jetty.bat`)
- Validate Python syntax: `Get-ChildItem -Path "brain-jetty" -Filter "*.py" | ForEach-Object { python -m py_compile $_.FullName }`

## Next Steps
- Verify live Vercel/VPS production deployment.
- Configure local `config.json` with user Anthropic/OpenAI API keys if running sidecar locally.

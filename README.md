# StrategAI

StrategAI is a Civilization-style strategy game prototype with a deterministic
Python engine, a FastAPI backend, and a Next.js frontend. The backend owns game
state, rules, AI goal execution, and HTTP APIs. The frontend renders the game
map and player controls.

## Repository Layout

```text
.
├── backend/              FastAPI app, game engine, tests, and scripts
│   ├── app/api/          HTTP routes, schemas, action validation, game store
│   ├── app/engine/       Pure game rules and turn-resolution logic
│   ├── scripts/          Headless playthrough utilities
│   └── tests/            Pytest suite
├── frontend/             Next.js app and Pixi-based map UI
├── ARCHITECTURE.md       Detailed backend architecture notes
├── GAME_BACKLOG.md       Game design and implementation backlog
└── TIER1_PLAN.md         Planning notes for the current milestone
```

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- npm

## Environment

The backend can use OpenAI for AI-generated strategic goals. Create a root
`.env` file if you want that integration enabled:

```bash
touch .env
```

Add:

```bash
OPENAI_API_KEY=sk-your-key-here
```

Do not commit `.env`.

## Run The Backend

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The API runs at:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/health
```

## Run The Frontend

In a second terminal, from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

By default, the frontend talks to the backend at `http://localhost:8000`. To use
a different backend URL, create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Restart the frontend dev server after changing `.env.local`.

## Tests And Checks

Backend:

```bash
cd backend
source .venv/bin/activate
pytest
```

Frontend:

```bash
cd frontend
npm run typecheck
npm run build
```

## Useful Scripts

Run a headless backend playthrough:

```bash
cd backend
source .venv/bin/activate
python scripts/run_playthrough.py
```

## More Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) explains the backend engine, API boundary,
  and AI goal execution model.
- [GAME_BACKLOG.md](GAME_BACKLOG.md) tracks planned gameplay work.
- [TIER1_PLAN.md](TIER1_PLAN.md) captures the current milestone plan.

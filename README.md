# AI Civ Frontend

Next.js frontend for the AI Civilization game. The frontend talks to the FastAPI backend on `http://localhost:8000` by default.

## Prerequisites

- Node.js 20 or newer
- npm
- Python 3.11 or newer for the backend

## Add the OpenAI API Key

The OpenAI key is used by the backend, not the frontend.

Create a `.env` file in the project root, one level above `frontend` and `backend`:

```bash
cd ..
touch .env
```

Add this line to `.env`:

```bash
OPENAI_API_KEY=sk-your-key-here
```

Do not commit `.env`.

## Run the Backend

From the `backend` directory:

```bash
cd ../backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The backend should now be running at:

```text
http://localhost:8000
```

## Run the Frontend

From the `frontend` directory:

```bash
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## Optional Frontend Environment

If the backend is running somewhere other than `http://localhost:8000`, create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Restart the frontend dev server after changing `.env.local`.

## Useful Commands

```bash
npm run typecheck
npm run build
npm run start
```

Backend tests:

```bash
cd ../backend
source .venv/bin/activate
pytest
```

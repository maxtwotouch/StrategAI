# Backend Configuration Reference

Complete reference for all environment variables, hardcoded parameters, and
configuration details in the StrategAI backend.

---

## Table of Contents

- [Environment Variables](#environment-variables)
- [How Configuration Is Loaded](#how-configuration-is-loaded)
- [Hardcoded Parameters](#hardcoded-parameters)
- [Configuration Flow](#configuration-flow)
- [Troubleshooting](#troubleshooting)

---

## Environment Variables

All environment variables are read via `os.getenv()` / `os.environ.get()`.
The `python-dotenv` library is used to load a `.env` file at startup.

| Variable | Required | Default | Used In | Description |
|----------|----------|---------|---------|-------------|
| `OPENAI_API_KEY` | **Yes** | *(none)* | `app/engine/openai_goals.py:477`<br>`app/api/routers/audio.py:24` | OpenAI API key for GPT model access. Without it, AI civilizations fall back to `RandomGoalSource` (deterministic stub) and the `/audio/intro` endpoint returns HTTP 503. |
| `OPENAI_TTS_MODEL` | No | `gpt-4o-mini-tts` | `app/api/routers/audio.py:27` | OpenAI TTS model for intro narration voiceover. Must be a TTS-capable model. |
| `OPENAI_TTS_VOICE` | No | `cedar` | `app/api/routers/audio.py:28` | Voice preset for intro narration. Supported voices: `alloy`, `ash`, `cedar`, `coral`, `echo`, `fable`, `onyx`, `nova`, `sage`, `shimmer`. |

### `OPENAI_API_KEY` — Required

```bash
OPENAI_API_KEY=sk-proj-...
```

- **Purpose**: Authenticates with the OpenAI API for two backend features:
  1. **AI Civilization Goal Sources** — Each AI-controlled civ gets its own
     `OpenAIGoalSource` instance that calls the OpenAI Chat Completions API
     with tool-use (9 intent tools) to make strategic decisions.
  2. **Audio Narration** — The `POST /audio/intro` endpoint uses the OpenAI
     TTS API to generate an epic narrated intro for the game.
- **Failure mode**: If the key is missing or invalid:
  - AI civs silently fall back to `RandomGoalSource` (a deterministic stub
    that makes random-but-legal decisions). A warning is logged.
  - The `/audio/intro` endpoint returns HTTP 503 with `"OPENAI_API_KEY is
    not configured"`.
  - Human players can still play normally.
- **Source file**: `app/engine/openai_goals.py` line 477 — the constructor
  raises `ValueError("OPENAI_API_KEY must be set...")` if the key is absent
  and not passed via the `api_key=` argument.

### `OPENAI_TTS_MODEL` — Optional

```bash
OPENAI_TTS_MODEL=gpt-4o-mini-tts
```

- **Purpose**: Specifies which OpenAI TTS model to use for intro narration.
- **Default**: `gpt-4o-mini-tts`
- **Source file**: `app/api/routers/audio.py` line 27

### `OPENAI_TTS_VOICE` — Optional

```bash
OPENAI_TTS_VOICE=nova
```

- **Purpose**: Selects the voice character for the intro narration.
- **Default**: `cedar`
- **Valid values**: `alloy`, `ash`, `cedar`, `coral`, `echo`, `fable`,
  `onyx`, `nova`, `sage`, `shimmer` (OpenAI TTS voice presets)
- **Source file**: `app/api/routers/audio.py` line 28

---

## How Configuration Is Loaded

1. **`load_dotenv()`** is called at module level in
   `backend/app/engine/openai_goals.py` (line 61). This reads key-value
   pairs from a `.env` file in the **current working directory** (the
   directory from which you run `uvicorn`).

2. **The `.env` file** should be placed at `backend/.env` and is
   gitignored. An example template is provided at `backend/.env.example`.

3. **`os.environ.get("OPENAI_API_KEY")`** is read directly in the
   `OpenAIGoalSource.__init__` constructor (line 477). If the key is not
   found and not passed as an argument, a `ValueError` is raised.

4. **`os.getenv()`** is used in `audio.py` to check for the key and read
   TTS model/voice settings. Missing optional vars fall back to their
   defaults.

### Loading Order

```
load_dotenv()          # .env file in CWD → os.environ
    ↓
os.environ.get(...)    # also picks up system env vars, Docker secrets, etc.
    ↓
constructor defaults   # used if env var is absent and no argument passed
```

---

## Hardcoded Parameters

The following game and LLM parameters are **not configurable via environment
variables**. To change them, edit the source files directly.

### LLM Configuration (`app/engine/openai_goals.py`)

| Parameter | Default Value | Location | Description |
|-----------|--------------|----------|-------------|
| `model` | `"gpt-5.4-mini"` | Line 472 (`__init__` default) | OpenAI model used for AI civ decisions. Supports any Chat Completions model with tool-use. |
| `temperature` | `0.7` | Line 474 (`__init__` default) | LLM sampling temperature. Not applied to reasoning models (`gpt-5`, `o1`, `o3`, `o4` prefixes). |
| `memory_turns` | `8` | Line 472 | Number of past turns of intent history injected into the LLM prompt. |
| `_MEMORY_ACTIONS` | `32` | Line 471 (module constant) | Maximum number of remembered intents and diplomatic messages. Older entries are discarded. |

### Game Defaults (`app/api/game_factory.py`)

| Parameter | Default Value | Location | Description |
|-----------|--------------|----------|-------------|
| `radius` | `8` | Line 143 (`new_game` default) | Default map radius in hex tiles. Passed by `CreateGameRequest` from the frontend. |
| `num_civs` | `4` | Line 145 (`new_game` default) | Default number of civilizations (clamped to 1–4). |
| `STARTING_GOLD` | `20` | Line 103 (module constant) | Gold each civ starts with. |
| Civ roster | 4 civs | Lines 36–70 | Hardcoded roster (Athens, Mongolia, Egypt, India). See `game_factory.py` for persona prompts. |

### Other Hardcoded Constants

| Parameter | Value | Location | Description |
|-----------|-------|----------|-------------|
| `_MEMORY_TURNS` | `8` | `openai_goals.py:470` | Same as `memory_turns` constructor default. |
| CORS origins | `["*"]` | `main.py:13` | All origins allowed. Change in `app/main.py` for production. |
| Server host/port | None set | Entry point | Controlled by `uvicorn` command-line arguments (`--host`, `--port`). Default: `127.0.0.1:8000`. |

---

## Configuration Flow

```
┌─────────────────────────────────────────────────────┐
│                  Frontend Request                     │
│  POST /games { radius, seed, human_name }            │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  game_factory.py: new_game()                         │
│  • Uses radius, seed from request (or defaults)      │
│  • Uses hardcoded civ roster, STARTING_GOLD          │
│  • Generates map, places civs, creates starting units│
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  game_factory.py: build_goal_sources()               │
│  • Human civ → QueueHumanSource                      │
│  • AI civ → OpenAIGoalSource(persona=...)            │
│    └─ reads OPENAI_API_KEY from env                  │
│    └─ falls back to RandomGoalSource if key missing  │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Each turn: OpenAIGoalSource.decide(view, civ_id)    │
│  • Sends fog-filtered view + intent history to LLM   │
│  • Uses hardcoded model ("gpt-5.4-mini") and         │
│    temperature (0.7)                                 │
│  • Parses tool calls → Intents → Goals               │
└─────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### AI civs aren't making smart decisions (or seem random)

**Symptom**: AI civilizations just move units randomly or do nothing
strategic.

**Cause**: `OPENAI_API_KEY` is missing or invalid. The backend silently
falls back to `RandomGoalSource`.

**Fix**:
1. Check that `backend/.env` exists and contains a valid key:
   ```bash
   cat backend/.env | grep OPENAI_API_KEY
   ```
2. Check the backend logs for:
   ```
   OPENAI_API_KEY missing; falling back to RandomGoalSource for civ X
   ```
3. Verify the key works:
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

### "OPENAI_API_KEY must be set" error on startup

**Symptom**: Backend raises `ValueError` on import.

**Cause**: `OpenAIGoalSource` is instantiated (e.g., in a test or script)
without the env var set and without passing `api_key=` explicitly.

**Fix**:
1. Create `backend/.env` from the example template:
   ```bash
   cp backend/.env.example backend/.env
   ```
2. Edit `.env` and add your key.
3. Ensure you're running from the `backend/` directory.

### Audio intro returns HTTP 503

**Symptom**: `POST /audio/intro` returns `{"detail": "OPENAI_API_KEY is
not configured"}`.

**Cause**: `OPENAI_API_KEY` is not set in the environment.

**Fix**: Same as above — set `OPENAI_API_KEY` in `backend/.env`.

### Audio intro returns HTTP 502

**Symptom**: `POST /audio/intro` returns `{"detail": "voice generation
failed: ..."}`.

**Cause**: The OpenAI TTS API call failed. Possible reasons:
- Invalid or expired API key
- Insufficient account credits
- `OPENAI_TTS_MODEL` is set to an invalid model name
- Network connectivity issue

**Fix**:
1. Verify your API key has access to the TTS model.
2. Check the `OPENAI_TTS_MODEL` value (default: `gpt-4o-mini-tts`).
3. Check backend logs for the full OpenAI error.

### How to change the LLM model for AI civs

The model is hardcoded in `app/engine/openai_goals.py` line 472:

```python
def __init__(
    self,
    model: str = "gpt-5.4-mini",  # ← change this default
    ...
```

Edit this line and restart the backend. The model must support the OpenAI
Chat Completions API with tool-use (function calling).

### How to change the LLM temperature

The temperature is hardcoded in `app/engine/openai_goals.py` line 474:

```python
temperature: float = 0.7,  # ← change this default
```

Note: Temperature is **not applied** to reasoning models (those with
prefixes `gpt-5`, `o1`, `o3`, `o4`). See the `decide()` method logic:

```python
if not self._model.startswith(("gpt-5", "o1", "o3", "o4")):
    request_kwargs["temperature"] = self._temperature
```

### `.env` file is ignored

**Symptom**: Variables in `.env` don't take effect.

**Causes and fixes**:

1. **Wrong working directory**: `load_dotenv()` looks for `.env` in the
   current working directory. Run uvicorn from `backend/`:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. **Variables already set in shell**: `load_dotenv()` does not override
   existing environment variables by default. Unset them first or use
   `override=True`.

3. **Syntax errors in `.env`**: No spaces around `=`, no quotes needed
   for simple values:
   ```bash
   # CORRECT
   OPENAI_API_KEY=sk-abc123
   # WRONG
   OPENAI_API_KEY = "sk-abc123"
   ```

---

## See Also

- [DEVELOPMENT.md](DEVELOPMENT.md) — Full development setup guide
- [ARCHITECTURE.md](ARCHITECTURE.md) — Backend engine layers and LLM
  integration design
- [GAMEPLAY.md](GAMEPLAY.md) — Game mechanics reference
- `backend/.env.example` — Environment variable template

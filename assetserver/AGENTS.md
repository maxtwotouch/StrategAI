# Asset Server — AI Agent System

This subproject contains the generative pixel-art service using ComfyUI + FLUX2 Klein 4B Distilled (DiT model).

## Architecture

FastAPI microservice that generates top-down medieval pixel-art game assets on-demand. 6 asset families with 33 REST endpoints, 3 generation modes (comfyui, static, placeholder).

## Directory Structure

| Path | Contents |
|------|----------|
| `src/main.py` | FastAPI routes and lifespan (33 endpoints) |
| `src/leader/` | Leader generation engine (3-stage pipeline: splash→profile→action) |
| `src/tile/` | Tile engines (structure, object, sprite, background) |
| `src/unit/` | Unit generation engine |
| `src/comfyui_client.py` | ComfyUI HTTP/WebSocket client |
| `src/comfyui_loadbalancer.py` | Multi-node load balancer |
| `src/database.py` | SQLAlchemy ORM models (7 tables) |
| `src/config.py` | Pydantic settings (YAML + env) |
| `src/prompt_templates.py` | Template loader from `config/prompt_templates.json` |
| `src/static_catalog.py` | Static tile catalog |
| `config/` | YAML config + prompt templates |
| `workflows/` | ComfyUI workflow JSONs (txt2img, background_tile, leader) |
| `tests/` | pytest suite (~345 tests) |
| `migrations/` | Alembic migrations |
| `static_tiles/` | Pre-made PNG assets |
| `generated_assets/` | Runtime-generated assets (LRU cache + atomic writes) |

## AI Technology (Course Relevance)

**Diffusion Transformer (DiT)**: FLUX2 Klein 4B Distilled — a 4B parameter DiT model for image generation.

**Key architectural decisions**:
- **3 generation modes**: `comfyui` (real DiT inference), `static` (pre-made PNGs), `placeholder` (PIL-generated) — graceful degradation
- **4-layer prompt assembly**: Workflow JSON → Jinja2 templates → enum injection maps → engine logic
- **Positive prompts only**: FLUX2 Klein 4B Distilled doesn't use negative prompts
- **LRU cache + atomic writes**: In-memory cache with temp file + `os.rename` for persistence
- **Load balancing**: Multi-node ComfyUI support via `comfyui_loadbalancer.py`

## Asset Families

| Family | Endpoints | Purpose |
|--------|-----------|---------|
| **Leader** | POST/GET/DELETE `/leader` | Leader portraits (3-stage: splash→profile→action) |
| **Structure** | POST/GET/DELETE `/structure` | Buildings (barracks, temple, etc.) |
| **Nature Object** | POST/GET/DELETE `/nature_object` | Trees, rocks, etc. |
| **Character Sprite** | POST/GET/DELETE `/character_sprite` | Unit sprites |
| **Background Tile** | POST/GET/DELETE `/background_tile` | Terrain tiles |
| **Unit** | POST/GET/DELETE `/unit` | Military units |

## Conventions

- **Seeds**: `secrets.randbits(31)` — never `random`
- **DB sessions**: `with SessionLocal() as db:` — always context manager; add, commit, refresh
- **Atomic writes**: temp file + `os.rename` for all image saves
- **Orphan cleanup**: call `_try_remove_asset()` on DB persist failure
- **Async**: no blocking calls in async context
- **Config**: `config.yaml` for defaults, `.env` for overrides (nested via `__` delimiter)
- **Tests**: mirror `src/` structure in `tests/`, use `conftest.py` fixtures, `@pytest.mark.asyncio` for async
- **Prompts**: templates in `config/prompt_templates.json`, enum prose in `src/*/prompts.py`
- **Workflows**: JSON node graphs in `workflows/`; validate node types at startup

## Agent Roster

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| **Orchestrator** | Multi-step feature coordination | 6-phase workflow (intake→research→implement→test→review→docs) |
| **Implementation** | Code changes, bug fixes | Endpoint implementation, config editing |
| **API Designer** | REST endpoint design | Pydantic models, response contracts |
| **Planner** | Feature planning | Architecture design, roadmaps |
| **Research** | Codebase exploration | Read-only investigation (sub-agent only) |
| **Test Engineer** | Test writing | Coverage analysis, regression detection |
| **Code Reviewer** | Pattern compliance | Bug detection, style consistency |
| **Documentation Engineer** | Docs, docstrings | README, architecture docs |
| **Database Architect** | Schema design | Alembic migrations, ORM models |
| **Workflow Engineer** | ComfyUI workflows | Workflow JSON, prompt templates |
| **Security Auditor** | Vulnerability scanning | Input validation, secrets |

## Testing

```bash
python -m pytest tests/ -x --tb=short
```

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn src.main:app --reload --port 8001
```

## Cross-Project Context

- **Frontend consumes**: Asset manifest via `NEXT_PUBLIC_ASSET_API_URL`, endpoints in `frontend/lib/assetManifest.ts`
- **Dataset/Training shares**: ComfyUI infrastructure, FLUX2 Klein 4B Distilled model, LoRA weights applied at inference
- **Root orchestrator**: For cross-project tasks, delegate to root `.github/agents/orchestrator.agent.md`

## Documentation

- `docs/project-report.md` — **Main student technical report** (read this first)
- `docs/INDEX.md` — Documentation hub
- `docs/pipeline/image-generation-pipeline.md` — DiT mechanics, workflow deep-dive
- `docs/architecture/` — System architecture docs

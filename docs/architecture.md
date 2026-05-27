# Image Diffusion Service: Production Architecture

## 1. System Overview
The Medieval Pixel Art Image Service is a decoupled, highly scalable web service that provides on-demand generative AI assets, acting as the dynamic engine behind the game's terrain, structures, and storytelling.

The web server is a lightweight orchestrator — it never loads model weights. All image generation is delegated to an external **ComfyUI** server via its HTTP + WebSocket API. Static/pre-made assets are served from a folder structure with zero configuration.

## 2. Core Operational Flow
1. **Request Intake**: `FastAPI` validates incoming payloads (`GenerationRequest`, `SplashRequest`, `LeaderRequest`) using strict Pydantic schemas.
2. **Mode Resolution**: The factory (`get_generator`) delegates based on `asset_family` and the environment-configured generation mode (`comfyui`, `static`, or `random`).
3. **Asset Processing**:
   - **ComfyUI**: Loads a workflow JSON template, patches in the prompt and seed, uploads any input images (for inpainting or img2img), submits to ComfyUI, polls via WebSocket, downloads the result.
   - **Static**: Serves pre-made PNGs from `static_tiles/` directory. Falls back to procedural placeholder if no static PNG is available.
   - **Random**: Coin-flip per request between `comfyui` and `static`.
   - **Copy-on-Write (CoW)**: For inpainting, the system loads the `base_image_id`, iteratively creates masks for each bounding box, and runs sequential inpainting passes through ComfyUI.
4. **Caching & Delivery**: The final asset is stored in an in-memory LRU cache for fast serving, persisted to disk, and indexed in SQLite. The asset URL is returned to the client.

## 3. Component Architecture

### A. API Layer (`main.py` & `models.py`)
- **FastAPI**: Handles high-concurrency requests with CORS middleware.
- **Pydantic**: Guarantees typed, structural contracts for`asset_family`, `tile_type`, `structure_subtype`, CoW references, and leader pipeline parameters.
- **ThreadPoolExecutor**: Runs blocking ComfyUI calls without blocking the async event loop.

### B. Storage Layer (`storage.py`)
- **AssetStore**: In-memory LRU cache (OrderedDict, default 1000 entries) for zero-latency serving. Transparent disk fallback for cache misses.

### C. Compute Layer (`generators.py` & `comfyui_client.py`)
- **ComfyUIClient**: Blocking HTTP + WebSocket client. Handles workflow submission, image upload, progress polling, result download, prompt cancellation, and health checks.
- **ComfyUIGenerator**: Wraps ComfyUIClient for the standard asset pipeline. Handles txt2img, story, splash, and sequential CoW inpainting.
- **StaticTileGenerator**: Serves pre-made PNGs from `static_tiles/`. Falls back to procedural placeholders for families without static assets.
- **_PlaceholderGenerator**: Procedural coloured rectangle with text label — always-available fallback.

### D. Static Catalog (`static_catalog.py`)
- Scans `static_tiles/` at startup and builds an in-memory lookup by family and subtype.
- Powers `GET /catalog` discovery endpoint and static asset resolution.

### E. Feature Engineering (`inpainting.py`)
- Calculates precise A/B bounds binary masks with optional Gaussian blur.
- Manages an internal vocabulary mapping (`get_inpaint_prompt`) to decouple game logic ("water") from prompt engineering ("sparkling blue pixel art river water texture, seamless, top-down 2d game").

### F. Leader Pipeline (`leader_engine.py`, `leader_models.py`, `leader_prompts.py`, `leader_registry.py`)
- **Three-stage generation**: splash (txt2img, establishes canonical visual identity) → profile (img2img, close-crop portrait using splash as reference, denoise=0.30) → action (img2img, new scene preserving character, denoise=0.60).
- **Structured prompt injection**: clients select from enum values (archetype, culture, time_of_day, mood, action_category). The server maps these to rich, hand-crafted prose via `leader_prompts.py`.
- **Seed anchoring**: splash seed is stored in `leader_records` and re-used for profile/action to maximize img2img consistency.
- **Reference image**: splash art is copied to `leader_references/ref_{leader_id}.png` and re-uploaded to ComfyUI before each profile/action generation.
- **SQLite-backed**: `LeaderRecord` table tracks all leaders alongside `AssetRecord`.

### G. Persistence (`database.py`)
- **SQLite** via SQLAlchemy. No external database dependency.
- **AssetRecord**: tracks every generated asset: id, family, tile_type, structure_subtype, inpainting data, generation mode.
- **LeaderRecord**: tracks leader identity: canonical splash image, seed, prompt, profile/action image IDs, reference filename.

## 4. Workflow JSON Templates

Seven ComfyUI workflows stored in `src/workflows/`, exported in API format:

| Workflow | Purpose | Key injection points |
|---|---|---|
| `txt2img.json` | Structures, nature objects, character sprites | Positive/negative prompt, seed |
| `inpaint.json` | Background tiles with CoW inpainting | Base image, mask image, fill prompt, seed |
| `story.json` | 16:9 cinematic concept art | Positive prompt, seed |
| `splash.json` | Leader portrait (legacy /splash endpoint) | Positive prompt (built from style/outfit/weapon fields), seed |
| `leader/leader_splash.json` | Leader splash (txt2img, 1920×1088) | Positive prompt, negative prompt, seed |
| `leader/leader_profile.json` | Leader profile (img2img, 1024×1024, denoise=0.30) | Positive prompt, negative prompt, seed, reference image filename |
| `leader/leader_action.json` | Leader action (img2img, 1920×1088, denoise=0.60) | Positive prompt, negative prompt, seed, reference image filename |

Resolution, steps, CFG, sampler, scheduler, denoise, model paths, LoRA strength, and output filename prefix are baked into the workflow JSONs and do not vary per request.

## 5. Generation Modes (Per-Family)

| Mode | Behaviour | When to use |
|---|---|---|
| `comfyui` | Always calls ComfyUI. 503 if unreachable. | Full AI generation |
| `static` | Serves from `static_tiles/`. Falls back to placeholder. | Offline dev, deterministic assets |
| `random` | Coin-flip per request (`RANDOM_GENERATION_PROBABILITY`). | A/B testing, gradual rollout |

All controlled via `.env` — ops-level control with zero code changes.

## 6. Path to Scaled Execution (Future)

- **Task Queues**: Implement **Celery + Redis** for non-blocking generation at scale.
- **Object Storage**: Swap in-memory/disk cache with **AWS S3 / Cloudflare R2** for multi-node deployments.
- **Async Client**: Replace blocking `requests` + `websocket` with `httpx` + `websockets` for true async ComfyUI communication.
- **GPU Cloud**: Separate web server hosting from GPU inference nodes.

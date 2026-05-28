# Image Diffusion Service: Production Architecture

## 1. System Overview
The Medieval Pixel Art Image Service is a decoupled, highly scalable web service that provides on-demand generative AI assets, acting as the dynamic engine behind the game's terrain, structures, and storytelling.

The web server is a lightweight orchestrator — it never loads model weights. All image generation is delegated to an external **ComfyUI** server via its HTTP + WebSocket API. Static/pre-made assets are served from a folder structure with zero configuration. A **placeholder** mode provides always-available procedural fallbacks for testing and development.

## 2. Core Operational Flow
1. **Request Intake**: `FastAPI` validates incoming payloads (`GenerationRequest`, `SplashRequest`, `LeaderRequest`) using strict Pydantic schemas.
2. **Mode Resolution**: The factory (`get_generator`) delegates based on `asset_family` and the configured generation mode (`comfyui`, `static`, `placeholder`, or `random`).
3. **Asset Processing**:
   - **ComfyUI**: Loads a workflow JSON template, patches in the prompt and seed, uploads any input images (for inpainting or img2img), submits to ComfyUI, polls via WebSocket, downloads the result.
   - **Static**: Serves pre-made PNGs from `static_tiles/` directory. Falls back to procedural placeholder if no static PNG is available.
   - **Placeholder**: Always returns a procedural coloured rectangle with text label — zero external dependencies, always available.
   - **Random**: Coin-flip per request between `comfyui` and `static`.
   - **Copy-on-Write (CoW)**: For inpainting, the system loads the `base_image_id`, iteratively creates masks for each bounding box, and runs sequential inpainting passes through ComfyUI.
4. **Caching & Delivery**: The final asset is stored in an in-memory LRU cache for fast serving, persisted to disk, and indexed in SQLite. The asset URL is returned to the client.

## 3. Component Architecture

### A. API Layer (`main.py` & `models.py`)
- **FastAPI**: Handles high-concurrency requests with CORS middleware. Endpoints: `POST /generate`, `POST /splash`, `POST /leader`, `GET /leader`, `GET /leader/{id}`, `DELETE /leader/{id}`, `POST /structure`, `POST /object`, `POST /terrain`, `POST /unit`, `GET /unit`, `GET /unit/{unit_id}`, `DELETE /unit/{unit_id}`, `GET /health`, `GET /modes`, `GET /catalog`, `GET /assets/{filename}`.
- **Pydantic**: Guarantees typed, structural contracts for `asset_family`, `tile_type`, `structure_subtype`, CoW references, and leader pipeline parameters.
- **Fully async**: Generation runs directly on the asyncio event loop via `httpx` + `websockets`. No thread-pool required.

### B. Storage Layer (`storage.py`)
- **AssetStore**: In-memory LRU cache (OrderedDict, default 1000 entries) for zero-latency serving. Transparent disk fallback for cache misses.

### C. Compute Layer (`generators.py` & `comfyui_client.py`)
- **ComfyUIClient**: Async HTTP + WebSocket client. Handles workflow submission, image upload, progress polling, result download, prompt cancellation, and health checks.
- **ComfyUIGenerator**: Wraps ComfyUIClient for the standard asset pipeline. Handles txt2img, story, splash, and sequential CoW inpainting.
- **StaticTileGenerator**: Serves pre-made PNGs from `static_tiles/`. Falls back to procedural placeholders for families without static assets.
- **_PlaceholderGenerator**: Procedural coloured rectangle with text label — always-available fallback for testing and development.

### D. Static Catalog (`static_catalog.py`)
- Scans `static_tiles/` at startup and builds an in-memory lookup by family and subtype.
- Powers `GET /catalog` discovery endpoint and static asset resolution.

### E. Feature Engineering (`inpainting.py`)
- Calculates precise A/B bounds binary masks with optional Gaussian blur.
- Manages an internal vocabulary mapping (`get_inpaint_prompt`) to decouple game logic ("water") from prompt engineering ("sparkling blue pixel art river water texture, seamless, top-down 2d game").

### F. Leader Pipeline (`leader_engine.py`, `leader_models.py`, `leader_prompts.py`, `leader_registry.py`)
- **Three-stage generation**: splash (txt2img, establishes canonical visual identity) → profile (img2img, close-crop portrait using splash as reference, denoise=0.30) → action.
- **Single-leader action**: img2img using the leader's reference image (denoise=0.60), preserving character identity while placing them in a new scene.
- **Multi-leader action**: txt2img with a composite prompt that weaves together all leaders' physical descriptions and names via `build_multi_action_prompt()`. No reference image is used because ComfyUI can only accept one reference image for img2img, but a multi-leader scene needs to depict multiple distinct faces. Triggered by providing `leader_ids` (list) in the request body alongside `asset_type: "action"`.
- **Structured prompt injection**: clients select from enum values (archetype, culture, time_of_day, mood, action_category). The server maps these to rich, hand-crafted prose via `leader_prompts.py`.
- **Seed anchoring**: splash seed is stored in `leader_records` and re-used for profile/action to maximize img2img consistency.
- **Reference image**: splash art is copied to `leader_references/ref_{leader_id}.png` and re-uploaded to ComfyUI before each profile and single-leader action generation.
- **SQLite-backed**: `LeaderRecord` table tracks all leaders alongside `AssetRecord`.

### G. Unit Pipeline (`unit_engine.py`, `unit_models.py`, `unit_prompts.py`, `unit_registry.py`)
- **Directional sprite generation**: each unit type (archer, scout, settler, warrior) generates up to 4 cardinal-facing sprites (south/north/east/west) as separate 512×512 images.
- **Single-direction fast path**: clients can request a single direction (e.g. `"s"`) for ~4× faster iteration. The south-facing sprite is canonical.
- **Enum-driven prompt assembly**: `unit_prompts.py` maps `unit_type` + `direction` to rich pixel-art prose, combined with the client's free-form `description`.
- **Static fallback with direction resolution**: `StaticUnitEngine` resolves sprites from `static_tiles/unit/{type}_{direction}.png`, falling back to the south sprite for any missing direction.
- **SQLite-backed**: `UnitRecord` table stores all four directional image IDs per unit.

### H. Persistence (`database.py`)
- **SQLite** via SQLAlchemy. No external database dependency.
- **AssetRecord**: tracks every generated asset: id, family, tile_type, structure_subtype, inpainting data, generation mode.
- **LeaderRecord**: tracks leader identity: canonical splash image, seed, prompt, profile/action image IDs, reference filename.

## 4. Workflow JSON Templates

Seven ComfyUI workflows stored in `workflows/`, exported in API format:

| Workflow | Purpose | Key injection points |
|---|---|---|
| `txt2img.json` | Structures, objects, terrain, unit sprites | Positive/negative prompt, seed |
| `inpaint.json` | Background tiles with CoW inpainting | Base image, mask image, fill prompt, seed |
| `story.json` | 16:9 cinematic concept art | Positive prompt, seed |
| `splash.json` | Leader portrait (legacy /splash endpoint) | Positive prompt (built from style/outfit/weapon fields), seed |
| `leader/leader_splash.json` | Leader splash (txt2img, 1920×1088) | Positive prompt, negative prompt, seed |
| `leader/leader_profile.json` | Leader profile (img2img, 1024×1024, denoise=0.30) | Positive prompt, negative prompt, seed, reference image filename |
| `leader/leader_action.json` | Leader action (1920×1088, denoise=0.60). Single-leader: img2img with reference image. Multi-leader: txt2img with composite prompt. | Positive prompt, negative prompt, seed, reference image filename (single-leader only) |

Resolution, steps, CFG, sampler, scheduler, denoise, model paths, LoRA strength, and output filename prefix are baked into the workflow JSONs and do not vary per request.

## 5. Generation Modes (Per-Family)

| Mode | Behaviour | When to use |
|---|---|---|
| `comfyui` | Always calls ComfyUI. 503 if unreachable. | Full AI generation |
| `static` | Serves from `static_tiles/`. Falls back to placeholder. | Offline dev, deterministic assets |
| `placeholder` | Always returns procedural coloured placeholder. | Testing, CI, zero-dependency demos |
| `random` | Coin-flip per request (`GENERATION__RANDOM_PROBABILITY`). | A/B testing, gradual rollout |

Controlled via `config.yaml` (version-controlled) with `.env` overrides using `__` delimiter — ops-level control with zero code changes.

## 6. Path to Scaled Execution (Future)

- **Task Queues**: Implement **Celery + Redis** for non-blocking generation at scale.
- **Object Storage**: Swap in-memory/disk cache with **AWS S3 / Cloudflare R2** for multi-node deployments.
- **GPU Cloud**: Separate web server hosting from GPU inference nodes.

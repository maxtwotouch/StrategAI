# Medieval Pixel Art Image Service

An on-demand generative AI microservice that produces pixel art game assets for a top-down medieval game. Built with **FastAPI**, **HuggingFace Diffusers**, and a **mock-first** architecture so the game client can integrate immediately — before GPU compute is provisioned.

---

## What It Does

The service accepts structured requests describing *what* to generate and returns a public URL pointing to the finished PNG asset.

| Asset Family | Example | Description |
|---|---|---|
| `structure` | castle, blacksmith | Buildings and constructed objects |
| `nature_object` | tree, boulder | Organic world decorations |
| `background_tile` | grass, dirt, water | Repeatable terrain tiles |
| `character_sprite` | knight, archer | Animated-sprite sheets (placeholder) |
| `story` | "The dragon attacks" | Epic 16:9 cinematic concept art |
| `splash` | "King Aldric" | Leader portrait / profile card |

It also supports **Copy-on-Write inpainting**: take an existing background tile, specify a bounding box (e.g., a river cutting across the tile), and the service fills only that region — leaving the rest of the tile untouched.

---

## Architecture

```
Game Client
    │
    ▼
┌──────────────────────────────────────────┐
│  FastAPI (main.py)                       │
│  POST /generate   POST /splash           │
│  GET  /assets/... GET /health            │
├──────────────────────────────────────────┤
│  Pydantic Models (models.py)             │
│  GenerationRequest, SplashRequest, etc.  │
├──────────────┬───────────────────────────┤
│  Generator   │  Factory                  │
│  (generators.py)                         │
│  ├─ MockGenerator      ← mock_mode=True  │
│  ├─ Flux2Generator     ← terrain/chars   │
│  ├─ ZImageTurboGenerator ← story scenes  │
│  └─ SplashGenerator    ← portraits       │
├──────────────┴───────────────────────────┤
│  Inpainting Engine (inpainting.py)       │
│  Mask creation + prompt translation      │
├──────────────────────────────────────────┤
│  AssetStore (storage.py)                 │
│  In-memory LRU cache + disk fallback     │
├──────────────────────────────────────────┤
│  SQLite DB (database.py)                 │
│  AssetRecord: id, family, inpaints, etc. │
└──────────────────────────────────────────┘
```

### Mock Mode vs Production Mode

The entire service starts in **mock mode** (`mock_mode=True` in `.env`). Every endpoint returns procedurally generated placeholder images (coloured rectangles with text overlays) so the game client can integrate end-to-end without any GPU.

Flip `mock_mode=False` and the service loads real diffusion models:

- **Stable Diffusion Inpainting** (`runwayml/stable-diffusion-inpainting`) for terrain tile editing
- **SDXL Turbo** (`stabilityai/sdxl-turbo`) for fast text-to-image generation of characters, structures, and story art

---

## Project Structure

```
.
├── src/
│   ├── main.py           # FastAPI application, endpoints, CORS, lifecycle
│   ├── models.py         # Pydantic request/response schemas
│   ├── generators.py     # ImageGenerator ABC + concrete generators
│   ├── inpainting.py     # Mask creation, prompt mapping, mock inpainting
│   ├── storage.py        # AssetStore: in-memory LRU cache + disk I/O
│   ├── database.py       # SQLAlchemy + SQLite AssetRecord table
│   └── config.py         # Pydantic Settings (mock_mode, paths, ports)
├── requirements.txt      # Python dependencies
├── architecture.md       # Detailed architecture documentation
├── inpainting_workflow.md # ComfyUI prototyping → diffusers production guide
├── next_steps.md         # Checklist for going from mock → live AI
├── generated_assets/     # Output directory for generated PNGs
├── mock_assets/          # Pre-made mock tiles (optional)
└── splash_assets/        # Output directory for splash portraits
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- (Optional) CUDA-capable GPU for production mode

### Install

```bash
cd TopDownMedievalPixelArt-Prod
pip install -r requirements.txt
```

### Run (Mock Mode — No GPU Required)

```bash
# Create .env file
echo "mock_mode=true" > .env

# Start the server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

The service is now live at `http://localhost:8000`.

### Run (Production Mode — Requires GPU)

```bash
echo "mock_mode=false" > .env
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

On first launch, the service downloads ~10 GB of model weights from HuggingFace.

---

## API Reference

### `GET /health`

Returns service status and current mode.

```json
{ "status": "ok", "mock_mode": true }
```

### `POST /generate`

Generate a new game asset.

**Request:**

```json
{
  "asset_family": "background_tile",
  "prompt": "medieval village grass with flowers",
  "base_image_id": null,
  "inpaints": [
    {
      "point_a": { "x": 100, "y": 200 },
      "point_b": { "x": 400, "y": 300 },
      "fill_type": "water"
    }
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `asset_family` | ✅ | One of: `structure`, `nature_object`, `background_tile`, `character_sprite`, `story`, `splash` |
| `prompt` | — | Text description for text-to-image generation |
| `base_image_id` | — | UUID of an existing tile to apply Copy-on-Write inpainting to |
| `inpaints` | — | List of bounding-box regions to inpaint with a fill type |

**Fill types:** `water`, `gravel_road`, `grass`, `dirt`, `stone_floor`, `lava`

**Response:**

```json
{
  "url": "/assets/a1b2c3d4-...png",
  "asset_family": "background_tile",
  "status": "completed"
}
```

### `POST /splash`

Generate a character portrait / splash art.

**Request:**

```json
{
  "character_name": "King Aldric",
  "title": "King",
  "description": "Grizzled veteran in ornate plate armor",
  "style": "pixel_art",
  "outfit": "ornate golden plate armor with crimson cape",
  "weapon": "flaming longsword",
  "background": "banner"
}
```

**Response:**

```json
{
  "url": "/assets/b2c3d4e5-..._splash.png",
  "character_name": "King Aldric",
  "status": "completed"
}
```

### `GET /assets/{filename}`

Download a previously generated asset. Returns `image/png`.

---

## How Inpainting Works

1. The game client sends a `base_image_id` (an existing tile UUID) plus a list of `inpaints`
2. Each inpaint specifies a bounding box (`point_a` → `point_b`) and a `fill_type` like `"water"`
3. The service loads the base image (Copy-on-Write — the original is never mutated)
4. A binary mask is created from the bounding box (with optional Gaussian blur for softer edges)
5. The `fill_type` is translated to a rich diffusion prompt (e.g., `"water"` → `"sparkling blue pixel art river water texture, seamless, top-down 2d game"`)
6. In production mode, `stable-diffusion-inpainting` fills the masked region; in mock mode, a solid colour overlay is applied
7. Each inpaint is applied sequentially to the same canvas
8. The final image is saved and its URL returned

---

## Design Decisions

- **Mock-first**: The game client integrates immediately. GPU costs only kick in when you flip `mock_mode=false`.
- **In-memory caching**: `AssetStore` uses an LRU-backed `OrderedDict` for zero-latency asset serving. Falls back to disk reads transparently.
- **SQLite**: No external database dependency. `AssetRecord` tracks every generation for future tile-map integration.
- **Prompt enrichment happens server-side**: The game client says `"water"`; the service handles making it sound good to the diffusion model.
- **Copy-on-Write**: Inpainting never mutates the original asset, enabling safe concurrent modifications.

---

## Roadmap

See [`next_steps.md`](next_steps.md) for the detailed checklist. High-level priorities:

- [ ] Integrate real HuggingFace diffusers pipelines (replace `time.sleep()` stubs)
- [ ] Add LRU cap and background disk flushing to `AssetStore`
- [ ] Expand `AssetRecord` with world-grid coordinates for full tile-map DB integration
- [ ] Phase 2: Celery + Redis task queue for non-blocking generation at scale
- [ ] Phase 2: S3/R2 object storage for multi-node deployments

---

## Documentation

| File | Purpose |
|---|---|
| [`architecture.md`](architecture.md) | Full system architecture, component breakdown, and scaling strategy |
| [`inpainting_workflow.md`](inpainting_workflow.md) | Guide for prototyping inpainting with ComfyUI and deploying with diffusers |
| [`next_steps.md`](next_steps.md) | Checklist for transitioning from mock to production AI microservice |

---

## License

*To be determined.*


# Next Steps: Production & Future Roadmap

> **Last updated: May 30, 2026** — reflects all work completed through the production-readiness implementation.

---

## 1. ✅ Completed (as of May 30, 2026)

### Core Infrastructure
- [x] ComfyUI HTTP + WebSocket client (`comfyui_client.py`)
- [x] Per-family generation modes (comfyui / static / placeholder) via `config.yaml` + `.env`
- [x] Static asset injection via `static_catalog.py` + `static_tiles/`
- [x] In-memory LRU cache with MB-based eviction + disk fallback (`AssetStore` in `src/storage.py`)
- [x] SQLite database with 7 tables: AssetRecord, LeaderRecord, StructureRecord, ObjectRecord, TerrainRecord, UnitRecord, BackgroundTileRecord
- [x] **Alembic migrations**: Auto-run at startup (`alembic upgrade head`). `DATABASE_RESET=true` for schema recovery.
- [x] Atomic file writes (`_atomic_write()` with temp file + `os.rename`)
- [x] Orphaned asset cleanup (`try_remove_asset()`) on DB persist failure
- [x] `python-dotenv>=1.0.0` for `.env` file support
- [x] `DeleteResponse` model (`{status, id, asset_type}`) on all 6 DELETE endpoints

### Flux2 Klein Migration
- [x] All 5 workflow JSONs regenerated for Flux2 Klein (UNETLoader, CLIPLoader, VAELoader, CFGGuider, Flux2Scheduler, KSamplerSelect, SamplerCustomAdvanced)
- [x] No negative prompt nodes (Flux2 doesn't use them)
- [x] `<tdp>` trigger phrase corrected in all 4 tile/unit templates
- [x] SDXL references purged from src/, workflows/, config/
- [x] `_patch_workflow()` extended with cfg_guidance, steps, denoise, sampler params

### Leader Pipeline
- [x] Leader pipeline: splash → profile → action with img2img consistency
- [x] Multi-leader action scene generation via `leader_ids` list
- [x] Multi-leader action images linked to all participating leaders
- [x] Leader registry: SQLite-backed CRUD (`src/leader/registry.py`)
- [x] Prompt engine: structured enum → rich prose injection
- [x] Seed generation uses `secrets.randbits(31)` throughout
- [x] All `self.http` → `await self.get_http()` race condition fixed

### Tile & Unit Pipelines
- [x] Structure, Object, Terrain engines (3 modes each)
- [x] Background tile engine with independent registry, models, and CRUD endpoints
- [x] `BackgroundTileRecord` ORM model + `BackgroundTileRegistry`
- [x] `description` field added to StructureResponse, ObjectResponse, TerrainResponse
- [x] Static/placeholder engines use atomic DB transactions
- [x] Unit engine (3 modes) with enum-driven prompts

### API & Pagination
- [x] All 6 GET list endpoints support `?limit=` (1–200, default 50) and `?offset=` (≥0)
- [x] `GET /catalog` discovery endpoint
- [x] `GET /health` with ComfyUI status and registered counts
- [x] `GET /modes` endpoint returning per-family active mode
- [x] `server:` section added to config.yaml (cors_origins, cache settings, body size limit)
- [x] Request body size limit middleware (configurable max_request_body_mb)
- [x] CORS defaults to `["http://localhost:3000"]`

### Code Quality
- [x] **Directory restructuring**: Flat `src/` → `src/leader/`, `src/tile/`, `src/unit/`
- [x] All engine files use `with SessionLocal() as db:` consistently
- [x] All seed generation uses `secrets` (never `random`)
- [x] Prompt template validation at startup (`validate_all_templates()`)
- [x] Database connectivity verified at startup

### Testing
- [x] 345 tests passing (pytest)
- [x] Concurrency tests (mixed families, leader, read-during-write)
- [x] Response consistency tests (cross-family shape/type/format)
- [x] Background tile endpoint tests (7 CRUD tests)
- [x] Regression tests for resolution/timing/seed fields

---

## 2. Near-Term (Remaining)

- [ ] **Job status pattern**: Add `POST /leader/async` and `GET /leader/job/{job_id}` for non-blocking generation.
- [ ] **Exponential backoff on timeout**: Retry failed generations with doubled timeout.
- [ ] **Reference image TTL cleanup**: Startup task to remove `ref_*.png` files for deleted leaders.
- [ ] **Prompt validation**: Strip forbidden style words from client descriptions. Warn but don't reject.
- [ ] **Watermark/preview endpoint**: `GET /leader/{leader_id}/preview` for thumbnail of splash art.
- [ ] **Batch generation**: `POST /leader/batch` for multiple assets in one call.

---

## 3. Integration Tests

- [ ] Unit tests for prompt builders with mock ComfyUIClient
- [ ] End-to-end smoke tests: one request per family in each generation mode
- [ ] Performance benchmarks for generation latency

---

## 4. Future: Distributed Scaling

- [ ] **Celery + Redis task queue**: Non-blocking generation at scale
- [ ] **S3 / R2 object storage**: Replace in-memory/disk AssetStore for multi-node deployments
- [ ] **Separate GPU nodes**: Web server on CPU instances, ComfyUI on GPU instances
- [ ] **PostgreSQL migration**: Replace SQLite for concurrent production workloads

---

## 5. Asset Quality

- [ ] Fine-tune workflow JSONs with actual ComfyUI testing (steps, CFG, denoise)
- [ ] Expand static tile catalog with hand-crafted pixel art PNGs
- [ ] Investigate post-processing pipeline (background removal, palette reduction)

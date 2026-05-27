# Next Steps: Production & Future Roadmap

This document tracks remaining work after the ComfyUI migration and leader pipeline implementation.

---

## 1. ✅ Completed

- [x] ComfyUI HTTP + WebSocket client (`comfyui_client.py`)
- [x] Per-family generation modes (comfyui / static / random) via `.env`
- [x] Static asset injection via `static_catalog.py` + `static_tiles/`
- [x] Copy-on-Write inpainting via ComfyUI
- [x] Seven workflow JSONs exported (txt2img, inpaint, story, splash, leader_splash, leader_profile, leader_action)
- [x] Leader pipeline: splash → profile → action with img2img consistency
- [x] Leader registry: SQLite-backed CRUD (`leader_registry.py`)
- [x] Prompt engine: structured enum → rich prose injection (`leader_prompts.py`)
- [x] In-memory LRU cache with disk fallback (`AssetStore`)
- [x] SQLite database for `AssetRecord` and `LeaderRecord`
- [x] `GET /catalog` discovery endpoint
- [x] `GET /health` with ComfyUI status and leader count
- [x] `.env.example` with all settings documented
- [x] Async ComfyUI client: replaced blocking `requests` + `websocket-client` with `async` `httpx` + `websockets`. Generation runs on the asyncio event loop — no `ThreadPoolExecutor` required. Removed `requests` and `websocket-client` from `requirements.txt`. Added `close_comfyui_client()` shutdown hook.

---

## 2. Near-Term (Phase 8 — Production Polish)

- [ ] **Job status pattern**: Add `POST /leader/async` and `GET /leader/job/{job_id}` for non-blocking generation. Useful for FLUX models with 60-120s generation times.
- [ ] **Exponential backoff on timeout**: Retry failed generations with doubled timeout, especially for action scenes.
- [ ] **Reference image TTL cleanup**: Startup task to remove `ref_*.png` files for deleted leaders.
- [ ] **Prompt validation**: Strip forbidden style words (8K, masterpiece, cinematic, etc.) from client `leader_description` and `action_description` fields. Warn but don't reject.
- [ ] **Watermark/preview endpoint**: `GET /leader/{leader_id}/preview` for 512px thumbnail of splash art.
- [ ] **Batch generation**: `POST /leader/batch` to generate multiple assets for one leader in a single call.

---

## 3. Integration Tests

- [ ] `tests/test_leader_pipeline.py`: Unit tests for prompt builders, registry CRUD, and engine with mock ComfyUIClient.
- [ ] `tests/test_generators.py`: Test ComfyUIGenerator, StaticTileGenerator, and mode routing.
- [ ] End-to-end smoke tests: one request per family in each generation mode.

---

## 4. Phase 2: Distributed Scaling (Optional)

- [ ] **Celery + Redis task queue**: Non-blocking generation at scale.
- [ ] **S3 / R2 object storage**: Replace in-memory/disk AssetStore for multi-node deployments.
- [ ] **Separate GPU nodes**: Web server on CPU instances, ComfyUI on GPU instances.
- [ ] **Model hot-swapping**: Support multiple ComfyUI backends with different models (SDXL for fast tiles, FLUX for leaders).

---

## 5. Asset Quality

- [ ] Fine-tune workflow JSONs with actual ComfyUI testing (steps, CFG, denoise).
- [ ] Add LoRA support for pixel-art-specific styles in the tile workflows.
- [ ] Expand fill types in `get_inpaint_prompt()` (forest, swamp, snow, castle_floor, etc.).
- [ ] Expand static tile catalog with hand-crafted pixel art PNGs.

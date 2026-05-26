# Next Steps: Lightweight Target Environment

This document defines the exact checklist needed to transition the current structurally complete architecture from a mock environment into a live AI microservice, while prioritizing simplicity, zero setup overhead, and an in-memory execution strategy.

---

## 1. Integrate HuggingFace `diffusers`
The foundational contract is complete. To process real images instead of simulated solids:
- [ ] Install `torch`, `diffusers`, `transformers`, and `accelerate`.
- [ ] In `generators.py`, replace the `time.sleep()` pseudo-code inside `Flux2Generator` and `ZImageTurboGenerator`.
- [ ] Load your models at the global module level (or app startup event) so they stay in VRAM: `pipeline = AutoPipelineForInpainting.from_pretrained(...)`.
- [ ] Map the `mask` and `img` buffers passed through `apply_inpaint` directly into the initialized `diffusers` pipeline.

## 2. In-Memory Asset Storage Scaling
The project currently uses a highly efficient in-memory dictionary cache (`AssetStore` in `storage.py`) that falls back to localized disk persistence. To tune this:
- [ ] Add an LRU (Least Recently Used) cap to `_memory_cache` in `storage.py` to ensure long-running services don't trigger Out-Of-Memory (OOM) crashes as generations increase.
- [ ] Add periodic background flushing to ensure disk writes don't block the FastAPI event loop under heavy generation load.

## 3. Tile Map Database Integration
You mentioned keeping a tilemap for generated assets. 
- [ ] Introduce a lightweight file-based DB initially (like `SQLite` via `SQLAlchemy`) to avoid heavy Postgres container setup overhead.
- [ ] Create an `AssetRecord` table storing the `base_image_id`, the coordinates within the game world, and a JSON block of the applied `inpaints`.
- [ ] Ensure that when a CoW action occurs, the new generated `UUID` is updated in the game's World State DB.

---

## Phase 2: Distributed Cloud Scaling (Optional)
If user concurrency dramatically expands, bypass the in-memory setup and spin up network infrastructures:
- [ ] Implement `Celery` & `Redis` queue to handle non-blocking generation tasks.
- [ ] Refactor `AssetStore` to upload generated `io.BytesIO()` streams directly to **AWS S3 / R2 Bucket** instead of caching in RAM.

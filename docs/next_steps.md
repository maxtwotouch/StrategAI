# Next Steps: Production & Future Roadmap

> **Last updated: May 30, 2026** — reflects all work completed through the production-readiness implementation.

---

## 1. ✅ Completed (as of May 30, 2026)

All Phases 1–8 of the production-readiness plan are complete. 523 tests pass
at 82% coverage. See the [changelog](/memories/repo/changelog-2026-05-30.md)
for full details.

Key highlights: Flux2 Klein migration, BackgroundTileRecord with independent
CRUD, pagination on all 6 list endpoints, Alembic auto-migrations, MB-based
cache eviction, `DeleteResponse` on all DELETE endpoints, atomic file writes,
orphaned asset cleanup, `python-dotenv` support, CORS defaults, request body
size limits, and 38 new tests (307 → 345).

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
- [ ] **Database hardening**: Tune SQLite WAL settings and connection pool for load

---

## 5. Asset Quality

- [ ] Fine-tune workflow JSONs with actual ComfyUI testing (steps, CFG, denoise)
- [ ] Expand static tile catalog with hand-crafted pixel art PNGs
- [ ] Investigate post-processing pipeline (background removal, palette reduction)

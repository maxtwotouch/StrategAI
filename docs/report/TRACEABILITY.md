# Report Claim Traceability Matrix

> **Purpose**: Every quantitative or technical claim in `IEEE_REPORT.md` must be verifiable by following references down to subproject source files. This document maps claims → canonical sources.

**How to use**: For any claim in the report, find its row below. Follow the "Verifiable Artifact" to confirm the claim is accurate. If a claim lacks a verifiable artifact, it should be qualified or removed.

---

## Quantitative Claims

| # | Claim | Report Section | Canonical Source | Verifiable Artifact |
|---|-------|---------------|------------------|---------------------|
| 1 | "339 tests" (backend) | §VIII.B | `backend/tests/` | `cd backend && ./.venv/bin/python -m pytest --collect-only -q` |
| 2 | "547 tests" (asset server) | §VIII.B | `assetserver/docs/architecture/testing-plan.md` | Documented test-suite count; local collection requires assetserver dev deps |
| 3 | "9 intent types" (Expand, Scout, Engage, Reinforce, Speak, AdjustStance, Build, Research, Improve) | §IV | `backend/app/engine/intents.py` | Count `@dataclass` intent classes |
| 4 | "6 asset families" (leader, unit, structure, object, terrain, background_tile) | §V | `assetserver/src/main.py` | Count endpoint groups and registries |
| 5 | "35 REST endpoints" | §III.A, §V | `assetserver/docs/guides/server-api.md` | Count documented endpoints |
| 6 | "8.4 GB FP8 inference footprint" | §I, §III.C, §V | `assetserver/docs/pipeline/image-generation-pipeline.md` | Model footprint table and setup guide |
| 7 | "16 backend endpoints total; 14 game endpoints" | Appendix B | `backend/app/main.py`, `backend/app/api/routers/*.py` | Count FastAPI route decorators |
| 8 | "128×128 current game asset output" | §V | `assetserver/src/tile/engine.py`, `assetserver/src/unit/engine.py`, `assetserver/src/tile/background_engine.py` | `GAME_ASSET_SIZE = 128` |
| 9 | "FLUX.2 Klein 4B Distilled — 4-billion parameter DiT" | §I, §III.C | `dataset-gen-train/docs/MODEL_CARD.md` | Model card documents base model |
| 10 | "100-image curated synthetic dataset; 97 structures, 2 vegetation, 1 terrain" | §I, §VI | `dataset-gen-train/docs/ DATASET_CARD.md` | Dataset statistics table |
| 11 | "6-experiment matrix" (caption detail × rank, with ultra-low outlier) | §VI | `dataset-gen-train/docs/experiment-design.md` | Experiment matrix table |
| 12 | "No persistent frontend asset manifest cache" | §VII | `frontend/lib/assetManifest.ts` | Top-of-file comment and old-key cleanup |
| 13 | "No frontend test runner configured" | §VIII.B | `frontend/package.json` | Scripts contain `typecheck`, no test script |
| 14 | "3 AI civilizations" | §I | `backend/app/api/game_factory.py` — `_AI_ROSTER` | Count entries in roster |
| 15 | "`gpt-5.4-mini` default model string" | §III.C | `backend/app/engine/openai_goals.py` | `OpenAIGoalSource.__init__` default |
| 16 | "8-turn, 32-intent, 32-message LLM memory bounds" | §III.C, §IX.E | `backend/app/engine/openai_goals.py` | Memory filtering logic |
| 17 | "3 generation modes" (comfyui, static, placeholder) | §III.A, §V | `assetserver/src/config.py` | Enum or config values |
| 18 | "4-layer prompt architecture" | §I, §V | `assetserver/docs/architecture/architecture.md` §3 | Documented in prompt architecture section |
| 19 | "3-stage leader portrait pipeline" | §I, §V | `assetserver/docs/guides/leader-prompt-guide.md` | Pipeline stages documented there |
| 20 | "8 leader archetypes" | §V | `assetserver/src/leader/models.py` | Count `Archetype` enum values |
| 21 | "12 cultures" | §V | `assetserver/src/leader/models.py` | Count `Culture` enum values |
| 22 | "Published LoRA variants range from 89 MB to 353 MB" | §VI | `dataset-gen-train/docs/MODEL_CARD.md` | Model variants table |
| 23 | "35 training-pipeline tests" | §VIII.B | `dataset-gen-train/README.md` | README testing section |
| 24 | "Non-commercial dataset and LoRA license chain" | §IX.D | `dataset-gen-train/docs/ DATASET_CARD.md`, `dataset-gen-train/docs/MODEL_CARD.md` | License frontmatter and license sections |
| 25 | "LoRA — 0.1-1% of base model size" | §II.C | `dataset-gen-train/docs/experiment-design.md` | LoRA rank × hidden dim calculation |
| 26 | "`secrets.randbits(32)` for generated asset seeds" | §IX.E | `assetserver/src/*/engine.py`, `assetserver/src/comfyui_client.py` | Search for `secrets.randbits(32)` |

## Architectural Claims

| # | Claim | Report Section | Canonical Source | Verifiable Artifact |
|---|-------|---------------|------------------|---------------------|
| A1 | "LLM never touches GameState directly" | §I, §III | `docs/ARCHITECTURE.md` §1 | `backend/app/engine/serialize.py` — serialized views only |
| A2 | "Three-layer architecture: Strategic → Tactical → Validator" | §III | `docs/ARCHITECTURE.md` §1 | `backend/app/engine/openai_goals.py` (strategic), `operations.py` (tactical), `actions.py` (validator) |
| A3 | "Pure functional engine with frozen dataclasses" | §III.A | `docs/ARCHITECTURE.md` | `backend/app/engine/models.py` — all `@dataclass(frozen=True)` |
| A4 | "Microservices architecture: 4 primary components" | §III | `docs/ARCHITECTURE.md` | Four subproject directories: backend/, frontend/, assetserver/, dataset-gen-train/ |
| A5 | "ComfyUI WebSocket + HTTP lifecycle" | §V | `assetserver/docs/architecture/comfyui-protocol.md` | Protocol documented there |
| A6 | "Multi-node load balancer with health checks" | §V | `assetserver/docs/architecture/load-balancer.md` | `assetserver/src/comfyui_loadbalancer.py` |
| A7 | "Graceful fallback: colors, glyphs, initials" | §VII | `docs/ASSET_INTEGRATION.md` | `frontend/lib/hex.ts` — glyph tables, `frontend/lib/assetManifest.ts` — null resolution |
| A8 | "Separation of concerns: Asset Server colocated with GPU, separated from Game Server" | §III | `docs/SEPARATION_OF_CONCERNS.md` | Documented rationale |

## Qualitative / Design Claims

| # | Claim | Report Section | Canonical Source |
|---|-------|---------------|------------------|
| Q1 | "Per-leader personas drive strategic behavior" | §IV | `backend/app/api/game_factory.py` — `_AI_ROSTER` with persona prompts |
| Q2 | "Rolling memory: recent turn outcomes on every LLM call" | §IV | `backend/app/engine/openai_goals.py` — message construction |
| Q3 | "Self-correcting: validation errors returned as machine-readable codes" | §IV | `backend/app/api/actions.py` — `Result.error.code` |
| Q4 | "Diplomatic chat with in-character AI leader replies" | §IV | `backend/app/engine/diplomacy.py` |
| Q5 | "Knowledge distillation: FLUX.2 [dev] 12B teacher → FLUX.2 Klein 4B student" | §VI | `dataset-gen-train/docs/generation.md` |
| Q6 | "Trigger token `<tdp>` + angle phrase for consistent perspective" | §VI | `dataset-gen-train/docs/training.md` |
| Q7 | "Background removal + palette quantization post-processing" | §V | `assetserver/docs/pipeline/image-generation-pipeline.md` |

---

## How to Verify a Claim

1. **Locate the claim** in `IEEE_REPORT.md` by section number
2. **Find its row** in this matrix
3. **Read the canonical source** file
4. **Run the verifiable artifact** (if a command is listed)
5. **If the claim doesn't match**: update either the claim or the source

## Traceability Chain

```
IEEE_REPORT.md  (Layer 3 — Academic claims)
    ↓ cites
TRACEABILITY.md  (this file — claim → source mapping)
    ↓ points to
docs/ARCHITECTURE.md, GAMEPLAY.md, etc.  (Layer 2 — Cross-cutting synthesis)
    ↓ references
backend/docs/, frontend/docs/, assetserver/docs/, dataset-gen-train/docs/  (Layer 1 — Subproject source of truth)
    ↓ documents
backend/app/engine/*.py, assetserver/src/*.py, etc.  (Source code — ground truth)
```

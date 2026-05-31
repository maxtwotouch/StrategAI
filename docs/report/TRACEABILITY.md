# Report Claim Traceability Matrix

> **Purpose**: Every quantitative or technical claim in `IEEE_REPORT.md` must be verifiable by following references down to subproject source files. This document maps claims → canonical sources.

**How to use**: For any claim in the report, find its row below. Follow the "Verifiable Artifact" to confirm the claim is accurate. If a claim lacks a verifiable artifact, it should be qualified or removed.

---

## Quantitative Claims

| # | Claim | Report Section | Canonical Source | Verifiable Artifact |
|---|-------|---------------|------------------|---------------------|
| 1 | "339+ tests" (backend) | §III.A | `docs/ARCHITECTURE.md` §1 | `cd backend && python -m pytest --co` |
| 2 | "547 tests" (asset server) | §V | `AGENTS.md` (Testing section) | `cd assetserver && python -m pytest --co` |
| 3 | "9 intent types" (Expand, Scout, Engage, Reinforce, Develop, Turtle, Diplomacy, Research, Idle) | §I, §IV | `backend/app/engine/intents.py` | Count `@dataclass` classes in the file |
| 4 | "6 asset families" (leader, unit, structure, terrain, background_tile, nature_object) | §V | `assetserver/src/main.py` — router mounts | Count `app.include_router` calls |
| 5 | "35 REST endpoints" | §III.A, §V | `assetserver/docs/guides/server-api.md` | Count documented endpoints |
| 6 | "2.5-6 seconds per image on Blackwell RTX 6000" | §I, §III.C | `assetserver/docs/pipeline/workflow-design-justification.md` | Benchmark measurements documented there |
| 7 | "3.5-7 seconds on RTX 3090" | §I | `assetserver/docs/pipeline/workflow-design-justification.md` | Benchmark measurements documented there |
| 8 | "14-16 GB VRAM with FP8" | §I, §III.C | `assetserver/docs/pipeline/workflow-design-justification.md` | Model size calculation: 4B params × 2 bytes (FP8) ≈ 8 GB + overhead |
| 9 | "FLUX.2 Klein 4B Distilled — 4-billion parameter DiT" | §I, §III.C | `dataset-gen-train/docs/MODEL_CARD.md` | Model card documents base model |
| 10 | "100-image curated dataset" | §I, §VI | `dataset-gen-train/docs/DATASET_CARD.md` | Dataset card documents image count |
| 11 | "6-experiment matrix" (caption density × learning rate × rank) | §I, §VI | `dataset-gen-train/docs/experiment-design.md` | Experiment matrix documented there |
| 12 | "22 engine modules" | §I | `docs/ARCHITECTURE.md` | `ls backend/app/engine/*.py | wc -l` |
| 13 | "21-node tech tree" | §IV | `backend/app/engine/tech_tree.py` | Count TechNode definitions |
| 14 | "3 AI civilizations" | §I | `backend/app/api/game_factory.py` — `_AI_ROSTER` | Count entries in roster |
| 15 | "GPT-5.4-mini" | §I, §III.C | `backend/app/engine/openai_goals.py` | Model string used in OpenAI client |
| 16 | "128K tokens context window" | §III.C | `backend/app/engine/openai_goals.py` | Model capability from OpenAI docs |
| 17 | "3 generation modes" (comfyui, static, placeholder) | §III.A, §V | `assetserver/src/config.py` | Enum or config values |
| 18 | "4-layer prompt architecture" | §I, §V | `assetserver/docs/architecture/architecture.md` §3 | Documented in prompt architecture section |
| 19 | "3-stage leader portrait pipeline" | §I, §V | `assetserver/docs/guides/leader-prompt-guide.md` | Pipeline stages documented there |
| 20 | "8 leader archetypes" | §IV | `backend/app/api/game_factory.py` — `LEADER_ARCHETYPES` | Count archetype entries |
| 21 | "12 cultural prompts" | §IV | `backend/app/api/game_factory.py` — `CULTURES` | Count culture entries |
| 22 | "FP8 quantization reduces VRAM from 16 GB to ~8.4 GB" | §II.C | `dataset-gen-train/docs/comfyui-workflows.md` | Quantization config documented |
| 23 | "315 backend tests" (Tier 1 benchmark) | — | `docs/archive/TIER1_PLAN.md` | Historical test count at Tier 1 completion |
| 24 | "~$9 per 100-turn game" (LLM API cost) | — | `docs/archive/BENCHMARK_CLAIM_ORIGINS.md` | Cost estimate methodology |
| 25 | "LoRA — 0.1-1% of base model size" | §II.C | `dataset-gen-train/docs/experiment-design.md` | LoRA rank × hidden dim calculation |
| 26 | "Apache 2.0 license" | §III.C | HuggingFace model page for FLUX.2 Klein 4B | License field on model card |

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

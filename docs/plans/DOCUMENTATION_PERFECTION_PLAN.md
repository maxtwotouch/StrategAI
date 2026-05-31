# Implementation Plan: StrategAI Documentation & Report Perfection

## Goal
Bring all StrategAI documentation, academic report, and AI showcase to a defensible, publication-quality standard for INF-3600 final submission.

## Scope
- **4 subprojects** affected (backend, frontend, assetserver, dataset-gen-train)
- **~35 tasks** across 6 phases
- **Estimated complexity**: High — requires coordination across all subprojects, content creation, and careful fact-checking

## Key Decisions
1. **Fix the LaTeX report first** — the `.tex` file is ~60% incomplete and is the actual submission format
2. **Remove or qualify all unsupported claims** — every performance metric, test count, and behavioral claim must be backed by evidence or explicitly marked as estimated
3. **Make AI visible in the frontend** — add AI decision logging, asset metadata display, and LoRA showcase
4. **Resolve all documentation discrepancies** — the 3-vs-9 intent tools, gold economy, entry point, and test count conflicts must be reconciled

---

## Phase 0: Clarification (BLOCKER — requires team input)

### Task 0.1 — **[Team]** Answer Questions Document
- **Files**: `docs/plans/QUESTIONS_FOR_TEAM.md`
- **Dependencies**: None
- **Description**: The team must answer all 10 sections of questions before we can finalize the report. Every unsupported claim needs either evidence or retraction.
- **Validation**: All questions answered, evidence provided where available

---

## Phase 1: Report Foundation (Critical Path)

### Task 1.1 — **[Report Writer]** Complete the LaTeX Report (Sections V–X + References + Appendices)
- **Files**: `docs/IEEE_REPORT_COMPLETE.tex`
- **Dependencies**: Task 0.1 (need answers to qualify claims)
- **Description**: The `.tex` file stops at Section V. Port all remaining content from `IEEE_REPORT.md` into proper IEEE LaTeX prose (not bullet points). Sections needed:
  - V: Diffusion Transformer Asset Pipeline (complete)
  - VI: LoRA Fine-Tuning
  - VII: Frontend Integration
  - VIII: Evaluation
  - IX: Discussion and Limitations
  - X: Conclusion
  - References (all 22+)
  - Appendix A, B, C
- **Agent**: Report Writer
- **Validation**: `pdflatex` compiles without errors, all sections present

### Task 1.2 — **[Report Writer]** Add Ethical Considerations Section
- **Files**: `docs/IEEE_REPORT_COMPLETE.tex`, `docs/IEEE_REPORT.md`
- **Dependencies**: Task 0.1 (Q8 answers)
- **Description**: Add a new subsection (likely §IX.B or standalone) covering:
  - Bias in generated assets (cultural representation, stereotypes)
  - Environmental cost of GPU inference
  - LLM-generated content moderation
  - Copyright/licensing of AI-generated images
  - Training data provenance (OpenGameArt CC licenses)
- **Agent**: Report Writer
- **Validation**: Section present in both `.md` and `.tex`, cites at least 2 relevant works

### Task 1.3 — **[Report Writer]** Fix All Unsupported Claims
- **Files**: `docs/IEEE_REPORT_COMPLETE.tex`, `docs/IEEE_REPORT.md`
- **Dependencies**: Task 0.1 (need actual numbers)
- **Description**: For each unsupported claim, either:
  - Provide evidence (logs, measurements, screenshots), OR
  - Qualify the claim ("estimated", "observed in informal testing"), OR
  - Remove the claim entirely
- **Specific claims to fix**:
  - RTX 5090 → correct GPU name
  - 1.2–4s generation time → cite source or mark as estimated
  - 80% cache hit rate → describe methodology or remove
  - 932 tests → run actual count and report real number
  - Emergent coalition formation → provide game log examples or soften language
  - $0.03/turn cost → cite API usage data or remove
  - 60 FPS rendering → cite profiling data or remove
  - LoRA generalization to cars/spaceships → provide images or remove
- **Agent**: Report Writer
- **Validation**: Every quantitative claim has a citation or qualifier

### Task 1.4 — **[Report Writer]** Fix FLUX.2 Model Relationship Explanation
- **Files**: `docs/IEEE_REPORT_COMPLETE.tex`, `docs/IEEE_REPORT.md`
- **Dependencies**: Task 0.1 (Q3.4 answer)
- **Description**: The report mentions FLUX.2 [dev] (12B) for dataset generation and FLUX.2 Klein 4B Distilled (4B) for inference but never explains why. Add a clear paragraph explaining:
  - Why a larger model was used for dataset generation (quality)
  - Why a smaller model is used for inference (speed, VRAM)
  - How LoRA weights transfer between architectures (or if they don't, explain the actual relationship)
- **Agent**: Report Writer
- **Validation**: Clear explanation present, technically accurate

### Task 1.5 — **[Report Writer]** Strengthen Related Work Section
- **Files**: `docs/IEEE_REPORT_COMPLETE.tex`
- **Dependencies**: None
- **Description**: Add missing citations:
  - Peebles & Xie (2023) — "Scalable Diffusion Models with Transformers" (DiT)
  - Park et al. (2023) — "Generative Agents" (LLM agents)
  - Wang et al. (2023) — "Voyager" (LLM tool-use in games)
  - Hu et al. (2021) — "LoRA: Low-Rank Adaptation" (original LoRA paper)
  - Any additional DiT/rectified flow papers
- **Agent**: Report Writer
- **Validation**: At least 25 references, all properly formatted IEEE style

### Task 1.6 — **[Report Writer]** Add Reproducibility Statement
- **Files**: `docs/IEEE_REPORT_COMPLETE.tex`, `docs/IEEE_REPORT.md`
- **Dependencies**: Task 0.1 (Q9 answers)
- **Description**: Add a subsection documenting:
  - Exact model versions used (GPT-4 snapshot, FLUX.2 checkpoint, LoRA adapter IDs)
  - Random seed strategy (`secrets.randbits(31)`)
  - Environment setup (Python versions, Node.js version, CUDA version)
  - How to reproduce a specific game session
- **Agent**: Report Writer
- **Validation**: Reproducibility section present with specific version numbers

---

## Phase 2: Documentation Fixes (Parallel with Phase 1)

### Task 2.1 — **[Backend]** Fix ARCHITECTURE.md Discrepancies
- **Files**: `docs/ARCHITECTURE.md`
- **Dependencies**: Task 0.1 (Q6 answers)
- **Description**: Update to match current code:
  - Fix 3-tool → 9-intent description (§10)
  - Update test count from 151 to actual current count
  - Update "What's Not Built Yet" (§14) to reflect shipped features
  - Fix `INF-3600/` → `StrategAI/` folder references
  - Add `intents.py` and `operations.py` to module listing
- **Agent**: Backend
- **Validation**: All descriptions match current code

### Task 2.2 — **[Backend]** Create Backend API Reference
- **Files**: New file `docs/API_REFERENCE.md`
- **Dependencies**: None
- **Description**: Formal API documentation for all 14 backend endpoints:
  - Method, path, parameters (with types), response shape, error codes
  - Example request/response for each endpoint
  - DTO definitions from `backend/app/api/schemas.py`
- **Agent**: Backend
- **Validation**: All 14 endpoints documented with examples

### Task 2.3 — **[Backend]** Create Backend Configuration Reference
- **Files**: New file `docs/BACKEND_CONFIG.md` or section in `DEVELOPMENT.md`
- **Dependencies**: None
- **Description**: Document all backend environment variables:
  - `OPENAI_API_KEY` — required
  - Model selection, temperature, and any other configurable parameters
  - Create `backend/.env.example`
- **Agent**: Backend
- **Validation**: `.env.example` exists, all vars documented

### Task 2.4 — **[Backend]** Fix Entry Point Discrepancy
- **Files**: `AGENTS.md`, `docs/DEVELOPMENT.md`
- **Dependencies**: Task 0.1 (Q6.3 answer)
- **Description**: Reconcile `app.main:app` vs `app.api.main:app` — make both docs consistent with the actual code
- **Agent**: Backend
- **Validation**: Both files show the same correct entry point

### Task 2.5 — **[Backend]** Fix GAMEPLAY.md Gold Economy Discrepancy
- **Files**: `docs/GAMEPLAY.md`
- **Dependencies**: Task 0.1 (Q6.2 answer)
- **Description**: Reconcile flat +5 gold/turn vs. full economy with upkeep/bankruptcy. Update to match actual implemented behavior.
- **Agent**: Backend
- **Validation**: GAMEPLAY.md matches actual engine behavior

### Task 2.6 — **[Frontend]** Create Frontend Architecture Document
- **Files**: New file `docs/FRONTEND_ARCHITECTURE.md`
- **Dependencies**: None
- **Description**: Document:
  - Component hierarchy (page.tsx structure, SquareMap, drawers/overlays)
  - State management approach (useState + useRef + useMemo)
  - API integration layer (`lib/api.ts`)
  - Asset resolution pipeline (`lib/assetManifest.ts`)
  - Hex map rendering (SVG layers, camera system)
- **Agent**: Frontend
- **Validation**: Document covers all major frontend subsystems

### Task 2.7 — **[Integration]** Create Cross-Project Integration Guide
- **Files**: New file `docs/INTEGRATION_GUIDE.md`
- **Dependencies**: Tasks 2.2, 2.6
- **Description**: Document:
  - Frontend ↔ Backend contract (DTOs, endpoints, error handling)
  - Frontend ↔ Asset Server contract (manifest resolution, POST endpoints)
  - How to run all services together (startup order, port assignments)
  - Common integration issues and troubleshooting
- **Agent**: Integration Tester
- **Validation**: A new developer can follow the guide to get all services running together

---

## Phase 3: AI Showcase Enhancement (Critical for Grades)

### Task 3.1 — **[Backend]** Add AI Decision Logging Endpoint
- **Files**: `backend/app/api/routers/`, `backend/app/engine/openai_goals.py`
- **Dependencies**: None
- **Description**: Expose AI decision logs via the API:
  - Store each AI civ's last N tool calls (intent name, arguments, timestamp)
  - Add endpoint `GET /api/games/{id}/ai-log` returning structured decision history
  - Include: civ_id, turn, intent_name, intent_args, reasoning_summary (if available from LLM response)
- **Agent**: Backend
- **Validation**: Endpoint returns structured JSON of AI decisions

### Task 3.2 — **[Frontend]** Add AI Intent Log Panel
- **Files**: `frontend/app/page.tsx` or new component `frontend/components/AIIntentLog.tsx`
- **Dependencies**: Task 3.1
- **Description**: Add a visible panel/tab showing AI decisions:
  - Display last tool call per AI civ with icon + intent name + arguments
  - Show persona snippets on leader hover
  - Color-code by intent type (military=red, diplomatic=blue, economic=green, research=purple)
  - Make it clear these are LLM-generated decisions
- **Agent**: Frontend
- **Validation**: AI decisions visible in game UI, clearly labeled as AI-generated

### Task 3.3 — **[Frontend]** Add "AI-Generated" Badges to Assets
- **Files**: `frontend/app/page.tsx`, `frontend/components/`
- **Dependencies**: None
- **Description**: Add subtle indicators that assets are AI-generated:
  - Small "AI" badge on leader portraits (toggleable)
  - Tooltip on hover showing generation model + prompt excerpt
  - "Conjuring world art" loading screen expanded to show model name and asset type
- **Agent**: Frontend
- **Validation**: Generated assets clearly marked as AI-generated

### Task 3.4 — **[Frontend]** Add Diplomacy AI Indicators
- **Files**: `frontend/app/page.tsx`
- **Dependencies**: None
- **Description**: In the diplomacy panel:
  - Add "🤖 AI-generated" badge on AI civ messages
  - Show relationship trend (simple text like "Improving ↗" or "Deteriorating ↘")
  - Display AI leader mood based on relationship score
- **Agent**: Frontend
- **Validation**: Diplomacy messages clearly identified as AI-generated

### Task 3.5 — **[Frontend]** Create AI Showcase / "About" Section
- **Files**: New component `frontend/components/AIShowcase.tsx` or new page
- **Dependencies**: None
- **Description**: Create a dedicated section (accessible from main menu or settings) showing:
  - The 4 AI technologies used (LLM civs, diplomacy chat, generative art, LoRA)
  - Brief explanation of each with links to HuggingFace models
  - The `<tdp>` trigger token explanation
  - Links to published dataset and model cards
- **Agent**: Frontend
- **Validation**: Showcase section present, links work, content accurate

---

## Phase 4: Report Figures & Visual Assets

### Task 4.1 — **[AI Showcase]** Create Architecture Diagrams (Figures 1–5)
- **Files**: `docs/figures/` (new directory)
- **Dependencies**: Task 1.1
- **Description**: Create the 5 most critical diagrams:
  - **Fig. 1**: System Architecture Overview (all 4 subprojects, data flow)
  - **Fig. 2**: Intent-Based Abstraction Layer (LLM → intents → goals → actions)
  - **Fig. 3**: Four-Layer Prompt Architecture (workflow → template → enum → assembly)
  - **Fig. 4**: Three-Stage Leader Pipeline (splash → profile → action with identity preservation)
  - **Fig. 5**: LoRA Experiment Matrix (3×2 grid with caption detail × rank)
- **Format**: Mermaid diagrams in markdown, or draw.io exports for LaTeX
- **Agent**: AI Showcase
- **Validation**: All 5 diagrams present, referenced in report, technically accurate

### Task 4.2 — **[AI Showcase]** Create Evaluation Figures (Figures 6–8)
- **Files**: `docs/figures/`
- **Dependencies**: Task 0.1 (need actual data)
- **Description**:
  - **Fig. 6**: Performance benchmarks chart (generation time, API latency, cache hit rate)
  - **Fig. 7**: Test coverage summary (bar chart by subproject)
  - **Fig. 8**: AI behavior distribution (intent type frequency per civilization)
- **Agent**: AI Showcase
- **Validation**: Charts present with real data

### Task 4.3 — **[AI Showcase]** Create Example Output Figures (Figures 9–12)
- **Files**: `docs/figures/`
- **Dependencies**: Task 0.1 (need example images)
- **Description**:
  - **Fig. 9**: Generated asset gallery (leaders, structures, units, terrain)
  - **Fig. 10**: LoRA before/after comparison (base model vs. LoRA-enhanced)
  - **Fig. 11**: Game screenshot (map view with AI civs, generated assets visible)
  - **Fig. 12**: Diplomacy chat screenshot (showing AI-generated messages)
- **Agent**: AI Showcase
- **Validation**: All example images present, properly captioned

### Task 4.4 — **[Report Writer]** Add Inline AI Output Examples to Report
- **Files**: `docs/IEEE_REPORT_COMPLETE.tex`, `docs/IEEE_REPORT.md`
- **Dependencies**: Tasks 4.1–4.3, Task 0.1
- **Description**: Add to the report:
  - Example LLM prompt sent to GPT-4 (the serialized game state)
  - Example LLM response (tool call with intent + arguments)
  - Example generated asset with its full prompt
  - Example diplomatic exchange (AI-generated message)
- **Agent**: Report Writer
- **Validation**: At least 4 inline examples in the report

---

## Phase 5: Code Quality & Testing Gaps

### Task 5.1 — **[Frontend]** Add Basic Frontend Test Suite
- **Files**: `frontend/__tests__/` (new directory), `frontend/package.json`
- **Dependencies**: None
- **Description**: Add minimal but meaningful tests:
  - Install Vitest + React Testing Library
  - Test API client functions (mocked fetch)
  - Test hex math utilities
  - Test asset manifest resolution
  - Test key component rendering (map, diplomacy panel)
  - Target: 15–20 tests covering critical paths
- **Agent**: Frontend
- **Validation**: `npm run test` passes, coverage report generated

### Task 5.2 — **[Backend]** Update Test Counts and Generate Coverage Report
- **Files**: `backend/` (run pytest with coverage)
- **Dependencies**: None
- **Description**:
  - Run `pytest --collect-only` to get actual test count
  - Run `pytest --cov=app --cov-report=html` for coverage
  - Update all documentation with real numbers
- **Agent**: Backend
- **Validation**: Actual numbers documented, coverage report saved

### Task 5.3 — **[Asset Server]** Update Test Counts and Generate Coverage Report
- **Files**: `assetserver/` (run pytest with coverage)
- **Dependencies**: None
- **Description**: Same as 5.2 but for asset server
- **Agent**: Backend (assetserver specialist)
- **Validation**: Actual numbers documented

### Task 5.4 — **[Backend]** Add AI Behavior Integration Tests
- **Files**: `backend/tests/test_ai_behavior.py` (new)
- **Dependencies**: None
- **Description**: Tests that validate AI decision-making quality:
  - Test that each persona produces different intent distributions (statistical test over N turns)
  - Test that rolling memory works correctly (old memories evicted)
  - Test that fog-of-war filtering works for LLM input
  - Test that invalid tool calls are handled gracefully
- **Agent**: Backend
- **Validation**: New tests pass, AI behavior is validated

### Task 5.5 — **[Integration]** Add Cross-Service Contract Tests
- **Files**: `scripts/contract_tests.py` (new) or extend `scripts/asset_api_smoke.py`
- **Dependencies**: None
- **Description**: Automated tests verifying:
  - Frontend DTO types match backend schemas
  - Asset manifest keys match asset server endpoints
  - All documented endpoints are reachable and return expected shapes
- **Agent**: Integration Tester
- **Validation**: Contract tests pass

---

## Phase 6: Polish & Final Review

### Task 6.1 — **[Report Writer]** Final Report Proofread & Consistency Check
- **Files**: `docs/IEEE_REPORT_COMPLETE.tex`, `docs/IEEE_REPORT.md`
- **Dependencies**: All Phase 1–4 tasks
- **Description**: Final pass checking:
  - All figure references resolve to actual figures
  - All citations are properly formatted IEEE style
  - No TODO comments remain
  - No placeholder text
  - Consistent terminology throughout
  - Abstract matches actual content
  - All claims are defensible
- **Agent**: Report Writer
- **Validation**: Zero issues found in final review

### Task 6.2 — **[Oral Presentation]** Update Presentation with Final Data
- **Files**: `docs/PRESENTATION_OUTLINE.md`
- **Dependencies**: Tasks 1.3, 5.2, 5.3
- **Description**: Update presentation with:
  - Correct test counts and coverage numbers
  - Correct performance metrics
  - Correct GPU references
  - Updated Q&A preparation based on final report content
- **Agent**: Oral Presentation
- **Validation**: Presentation consistent with final report

### Task 6.3 — **[Orchestrator]** Final Cross-Project Consistency Audit
- **Files**: All documentation files
- **Dependencies**: All previous tasks
- **Description**: Final audit ensuring:
  - All test counts consistent across all documents
  - All architecture descriptions match current code
  - All API references match actual endpoints
  - No stale references to old project name (INF-3600 folder)
  - All links work
- **Agent**: Integration Tester
- **Validation**: Zero discrepancies found

### Task 6.4 — **[AI Showcase]** Create Demo Video Script
- **Files**: `docs/DEMO_SCRIPT.md` (new)
- **Dependencies**: Tasks 3.1–3.5
- **Description**: Write a step-by-step demo script showing:
  1. Game startup → AI-generated world art loading
  2. AI civilizations making strategic decisions (show intent log)
  3. Diplomatic exchange with AI leader (show AI-generated messages)
  4. Asset generation in action (show prompt → image pipeline)
  5. LoRA style consistency across generated assets
  6. Link to HuggingFace models and dataset
- **Agent**: AI Showcase
- **Validation**: Script can be followed to demonstrate all 4 AI components in <5 minutes

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Team cannot provide benchmark data** | High — performance claims must be removed | Qualify all claims as "estimated" or remove them; focus on architectural quality over metrics |
| **LaTeX compilation issues** | Medium — delays submission | Use Overleaf for collaborative editing; test compilation after each section added |
| **Frontend changes break existing UI** | Medium — game becomes unplayable | Make all UI additions optional/toggleable; test after each change |
| **Generated asset examples look poor** | Medium — weakens AI showcase | Curate best examples; honestly discuss limitations in report |
| **Test counts are lower than claimed** | High — undermines credibility | Report actual numbers honestly; emphasize test quality over quantity |
| **LoRA was community-sourced, not custom** | High — weakens training contribution | Be transparent in report; emphasize curation, adaptation, and experiment design as the contribution |

---

## Validation Checklist

- [ ] `pdflatex IEEE_REPORT_COMPLETE.tex` compiles without errors
- [ ] All 12 figures present and referenced in report
- [ ] Every quantitative claim has a citation or qualifier
- [ ] All 4 AI components visible in the frontend UI
- [ ] All documentation discrepancies resolved
- [ ] Backend tests pass: `cd backend && python -m pytest tests/ -x --tb=short`
- [ ] Asset server tests pass: `cd assetserver && python -m pytest tests/ -x --tb=short`
- [ ] Frontend type check passes: `cd frontend && npx tsc --noEmit`
- [ ] Frontend tests pass: `cd frontend && npm run test`
- [ ] Integration smoke test passes: `python scripts/asset_api_smoke.py`
- [ ] Demo script can be followed in <5 minutes
- [ ] No TODO comments in any documentation file
- [ ] All links in documentation are valid
- [ ] Ethical considerations section present
- [ ] Reproducibility statement present
- [ ] At least 25 properly formatted IEEE references

---

## Execution Order

```
Phase 0 (BLOCKER)
    └─ Q&A from team
         │
         ├─ Phase 1 (Report Foundation) ──────────────────┐
         │    ├─ 1.1 Complete LaTeX                        │
         │    ├─ 1.2 Ethics section                        │
         │    ├─ 1.3 Fix unsupported claims                │
         │    ├─ 1.4 FLUX.2 explanation                   │
         │    ├─ 1.5 Strengthen references                 │
         │    └─ 1.6 Reproducibility statement             │
         │                                                 │
         ├─ Phase 2 (Documentation Fixes) ────────────────┤
         │    ├─ 2.1 Fix ARCHITECTURE.md                   │
         │    ├─ 2.2 Backend API reference                 │
         │    ├─ 2.3 Backend config reference              │
         │    ├─ 2.4 Fix entry point discrepancy           │
         │    ├─ 2.5 Fix gold economy discrepancy          │
         │    ├─ 2.6 Frontend architecture doc             │
         │    └─ 2.7 Integration guide                     │
         │                                                 │
         ├─ Phase 3 (AI Showcase) ────────────────────────┤
         │    ├─ 3.1 AI decision logging endpoint          │
         │    ├─ 3.2 AI intent log panel                   │
         │    ├─ 3.3 AI-generated badges                   │
         │    ├─ 3.4 Diplomacy AI indicators               │
         │    └─ 3.5 AI showcase section                   │
         │                                                 │
         ├─ Phase 4 (Figures) ────────────────────────────┤
         │    ├─ 4.1 Architecture diagrams (Fig 1-5)       │
         │    ├─ 4.2 Evaluation figures (Fig 6-8)          │
         │    ├─ 4.3 Example outputs (Fig 9-12)            │
         │    └─ 4.4 Inline examples in report             │
         │                                                 │
         ├─ Phase 5 (Code Quality) ───────────────────────┤
         │    ├─ 5.1 Frontend test suite                   │
         │    ├─ 5.2 Backend coverage report               │
         │    ├─ 5.3 Asset server coverage report          │
         │    ├─ 5.4 AI behavior tests                     │
         │    └─ 5.5 Contract tests                        │
         │                                                 │
         └─ Phase 6 (Polish) ─────────────────────────────┘
              ├─ 6.1 Final proofread
              ├─ 6.2 Update presentation
              ├─ 6.3 Final consistency audit
              └─ 6.4 Demo script
```

Phases 1–5 can run largely in parallel once Phase 0 is unblocked. Phase 6 depends on all previous phases.

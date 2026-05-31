# Documentation Reorganization Plan: Bottom-Up Architecture

**Created:** May 31, 2026  
**Status:** Awaiting Approval  
**Estimated Effort:** ~40 file operations (moves, deletes, link fixes)

---

## Goal

Restructure StrategAI's documentation (~122 markdown files) into a **bottom-up, three-layer hierarchy** where subproject docs are the authoritative source of truth, cross-cutting docs synthesize facts, and the academic report draws traceable claims from both — eliminating all duplication and historical clutter.

## Problem Statement

| Issue | Count | Impact |
|-------|-------|--------|
| **Verbatim duplicates** across layers | 8 files | Inconsistent updates, confusion about which is canonical |
| **Misplaced domain docs** at top level | 4 files | Frontend/backend docs in `docs/` instead of subproject `docs/` |
| **Historical planning clutter** | ~20 files | One-time artifacts in root, `docs/plans/`, and `docs/` masquerading as permanent docs |
| **Report artifacts scattered** | 3 locations | Report files split across `docs/`, `docs/report/`, `docs/figures/` |
| **No traceability from report → facts** | systemic | Academic claims can't be verified by following references downward |

## Proposed Architecture

```
                           ┌──────────────────────────┐
                           │   LAYER 3: ACADEMIC       │
                           │   docs/report/            │
                           │   IEEE_REPORT.{md,tex}    │
                           │   FIGURE_DESCRIPTIONS.md  │
                           │   PRESENTATION_OUTLINE.md │
                           │   figures/                │
                           └──────────┬───────────────┘
                                      │ draws verified facts from
                           ┌──────────▼───────────────┐
                           │   LAYER 2: SYNTHESIS      │
                           │   docs/ (top-level)       │
                           │   ARCHITECTURE.md         │
                           │   GAMEPLAY.md             │
                           │   DEVELOPMENT.md          │
                           │   ASSET_INTEGRATION.md    │
                           │   DEPLOYMENT.md           │
                           │   SEPARATION_OF_CONCERNS  │
                           └──────────┬───────────────┘
                                      │ synthesizes & references
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────────┐
   │ LAYER 1:         │   │ LAYER 1:         │   │ LAYER 1:             │
   │ backend/docs/    │   │ frontend/docs/   │   │ assetserver/docs/    │
   │ (API, config)    │   │ (architecture,   │   │ (INDEX, arch,        │
   │                  │   │  UI guide)       │   │  guides, pipeline)   │
   └──────────────────┘   └──────────────────┘   └──────────────────────┘
                              ┌──────────────────────┐
                              │ LAYER 1:             │
                              │ dataset-gen-train/   │
                              │ docs/                │
                              │ (cards, experiments, │
                              │  training, gen)      │
                              └──────────────────────┘
```

### Layer 1: Subproject Docs — Authoritative Source of Truth

Each subproject owns its domain documentation. No top-level file duplicates subproject facts. Cross-cutting docs link downward.

| Subproject | Docs | Status |
|-----------|------|--------|
| **backend/** | `API_REFERENCE.md`, `BACKEND_CONFIG.md` | ✅ Clean (2 files) |
| **frontend/** | `FRONTEND_ARCHITECTURE.md`, `UI_GUIDE.md` | ⚠️ UI_GUIDE needs move from `docs/` |
| **assetserver/** | `INDEX.md` + 16 files in `architecture/`, `guides/`, `pipeline/`, `project/` | ✅ Already well-organized |
| **dataset-gen-train/** | 6 files (DATASET_CARD, MODEL_CARD, etc.) | ✅ Clean |

### Layer 2: Cross-Cutting Synthesis — 6 Files

These synthesize facts from subprojects into coherent system-level narratives. They **reference** subproject docs; they do **not** duplicate them.

| File | Purpose | Draws From |
|------|---------|------------|
| `ARCHITECTURE.md` | System design, layers, data flow | All subprojects |
| `GAMEPLAY.md` | Game mechanics reference | `backend/` engine |
| `DEVELOPMENT.md` | Dev setup, workflow, testing | All subprojects |
| `ASSET_INTEGRATION.md` | Asset pipeline integration | `assetserver/`, `frontend/`, `dataset-gen-train/` |
| `DEPLOYMENT.md` | Production deployment | All subprojects |
| `SEPARATION_OF_CONCERNS.md` | Architectural rationale | All subprojects |

### Layer 3: Academic Report — 4 Files + Figures

Draws verified, traceable claims from Layers 1 & 2. Every technical claim should be verifiable by following links down to the subproject source.

| File | Purpose |
|------|---------|
| `IEEE_REPORT.md` | Markdown master report |
| `IEEE_REPORT_COMPLETE.tex` | LaTeX submission file |
| `FIGURE_DESCRIPTIONS.md` | All figure captions and descriptions |
| `PRESENTATION_OUTLINE.md` | Oral exam presentation |
| `figures/` | Generated PNG/SVG figures |

### Archive: Historical & Planning Artifacts

One-time planning documents, completion summaries, and historical artifacts move to `docs/archive/`. These are preserved for reference but clearly separated from living documentation.

---

## Tasks

### Phase 1: Eliminate Duplicates (Delete 8 redundant files)

These files are **verbatim duplicates** of subproject docs. Delete the top-level copy; the subproject copy is the canonical source.

1. **Delete `docs/API_REFERENCE.md`** — verbatim duplicate of `backend/docs/API_REFERENCE.md`
   - Validation: `backend/docs/API_REFERENCE.md` remains, no broken links
2. **Delete `docs/BACKEND_CONFIG.md`** — verbatim duplicate of `backend/docs/BACKEND_CONFIG.md`
   - Validation: `backend/docs/BACKEND_CONFIG.md` remains, no broken links
3. **Delete `docs/FRONTEND_ARCHITECTURE.md`** — verbatim duplicate of `frontend/docs/FRONTEND_ARCHITECTURE.md`
   - Validation: `frontend/docs/FRONTEND_ARCHITECTURE.md` remains
4. **Delete `docs/IEEE_REPORT.md`** — verbatim duplicate of `docs/report/IEEE_REPORT.md`
   - Validation: `docs/report/IEEE_REPORT.md` remains
5. **Delete `docs/FIGURE_DESCRIPTIONS.md`** — verbatim duplicate of `docs/report/FIGURE_DESCRIPTIONS.md`
   - Validation: `docs/report/FIGURE_DESCRIPTIONS.md` remains
6. **Delete `docs/PRESENTATION_OUTLINE.md`** — duplicate of `docs/report/PRESENTATION_OUTLINE.md`
   - Validation: `docs/report/PRESENTATION_OUTLINE.md` remains
7. **Delete `docs/REPORT_ENHANCEMENTS.md`** — historical, content absorbed into report
   - Validation: Report is complete without it
8. **Delete `docs/REPORT_HANDOFF.md`** — historical handoff note, no longer needed
   - Validation: No broken references

### Phase 2: Move Domain Docs to Subprojects (4 moves)

These files are domain-specific but live at the wrong level.

9. **Move `docs/UI_GUIDE.md` → `frontend/docs/UI_GUIDE.md`**
   - Dependencies: None
   - Validation: `frontend/docs/UI_GUIDE.md` exists, update all cross-references
10. **Move `docs/PROJECT_COMPLETION_GUIDE.md` → `docs/archive/PROJECT_COMPLETION_GUIDE.md`**
    - Dependencies: None
    - Validation: File in archive, no living docs reference it
11. **Move `docs/STRUCTURAL_IMPROVEMENTS_SUMMARY.md` → `docs/archive/STRUCTURAL_IMPROVEMENTS_SUMMARY.md`**
    - Dependencies: None
    - Validation: File in archive

### Phase 3: Consolidate Report Artifacts (3 operations)

All report-related files should live under `docs/report/`.

12. **Move `docs/IEEE_REPORT.tex` → `docs/report/IEEE_REPORT.tex`**
    - Note: Check if `docs/report/` already has a `.tex` file; if so, keep the more complete one
13. **Move `docs/IEEE_REPORT_COMPLETE.tex` → `docs/report/IEEE_REPORT_COMPLETE.tex`**
    - Validation: LaTeX compiles from new location
14. **Delete `docs/IEEE_REPORT_COMPLETE.tex.bak`** — backup file, not needed
    - Validation: No `.bak` files remain in docs

### Phase 4: Consolidate Historical Planning (3 operations)

Move root-level planning docs and consolidate `docs/plans/`.

15. **Move root `GAME_BACKLOG.md` → `docs/archive/GAME_BACKLOG.md`**
16. **Move root `TIER1_PLAN.md` → `docs/archive/TIER1_PLAN.md`**
17. **Move root `planning.md` → `docs/archive/planning.md`**

### Phase 5: Clean Up docs/plans/ (archive or delete)

The `docs/plans/` directory has 14 files. Many are one-time artifacts.

18. **Keep & move to `docs/archive/`:** Files with lasting reference value:
    - `DOCUMENTATION_REORGANIZATION.md` → `docs/archive/`
    - `TIER1_PLAN.md` → `docs/archive/` (if not already moved from root)
    - `GAME_BACKLOG.md` → `docs/archive/` (if not already moved)
    - `planning.md` → `docs/archive/` (if not already moved)
    - `AI_BEHAVIOR_TEST_RECOMMENDATIONS.md` → `docs/archive/`
    - `BENCHMARK_CLAIM_ORIGINS.md` → `docs/archive/`
    - `FIGURES_RECOMMENDATION.md` → `docs/archive/`
    - `FIGURES_NEED_INPUT.md` → `docs/archive/`

19. **Delete** one-time completion/status artifacts (no lasting value):
    - `COMPLETION_SUMMARY.md` — status snapshot, now stale
    - `FINAL_REVIEW_REPORT.md` — one-time review, now stale
    - `PROJECT_COMPLETION_GUIDE.md` — already moved to archive
    - `QUESTIONS_FOR_TEAM.md` — answered, no longer actionable
    - `REPORT_REVISION_PLAN.md` — executed, no longer needed
    - `DOCUMENTATION_PERFECTION_PLAN.md` — executed, content absorbed

20. **Delete `docs/plans/` directory** after consolidation
    - Validation: `docs/plans/` no longer exists

### Phase 6: Fix Cross-References (critical)

Every moved or deleted file breaks links. Systematically fix them.

21. **Update `docs/DEVELOPMENT.md`** — references to moved files
    - Replace `../frontend/docs/UI_GUIDE.md` → `../frontend/docs/UI_GUIDE.md` (verify path)
    - Replace references to `API_REFERENCE.md` → `../backend/docs/API_REFERENCE.md`
22. **Update `docs/ARCHITECTURE.md`** — references to moved backend/frontend docs
23. **Update `docs/ASSET_INTEGRATION.md`** — references to UI_GUIDE
24. **Update `docs/GAMEPLAY.md`** — references to backend docs
25. **Update `docs/DEPLOYMENT.md`** — references to SEPARATION_OF_CONCERNS
26. **Update `assetserver/docs/INDEX.md`** — references to top-level DEPLOYMENT, SECURITY
27. **Update all AGENTS.md files** — any doc path references
28. **Update `README.md`** — doc directory references
29. **Update `docs/report/IEEE_REPORT.md`** — ensure all technical claims link to verifiable sources in subproject docs

### Phase 7: Add Bottom-Up Traceability (new content)

This is the key structural improvement. Add explicit traceability so report claims are verifiable.

30. **Add "Fact Sources" section to `docs/report/IEEE_REPORT.md`**
    - For each major claim (performance numbers, test counts, architecture facts), add a footnote or parenthetical citing the exact subproject doc and line/section
    - Example: "Asset generation takes 2.5-6s on RTX 6000 [^1]" → `[^1]: assetserver/docs/pipeline/workflow-design-justification.md §Performance`

31. **Add "Where to Find Details" sections to each Layer 2 doc**
    - `ARCHITECTURE.md`: Link to `backend/docs/`, `frontend/docs/`, `assetserver/docs/architecture/`
    - `GAMEPLAY.md`: Link to `backend/docs/API_REFERENCE.md` for actions, `backend/app/engine/models.py` for data structures
    - `ASSET_INTEGRATION.md`: Link to `assetserver/docs/guides/server-api.md`, `frontend/lib/assetManifest.ts`
    - `DEVELOPMENT.md`: Link to each subproject's README and docs

32. **Create `docs/report/TRACEABILITY.md`** — a one-page mapping from every quantitative claim in the report to its source file and section
    - Column 1: Claim (e.g., "339+ backend tests")
    - Column 2: Source file (e.g., `docs/ARCHITECTURE.md §1`)
    - Column 3: Verifiable artifact (e.g., `cd backend && python -m pytest --co`)

---

## Final Structure

```
StrategAI/
├── README.md
├── AGENTS.md
│
├── docs/                              # 6 cross-cutting files + 2 subdirs
│   ├── ARCHITECTURE.md
│   ├── GAMEPLAY.md
│   ├── DEVELOPMENT.md
│   ├── ASSET_INTEGRATION.md
│   ├── DEPLOYMENT.md
│   ├── SEPARATION_OF_CONCERNS.md
│   │
│   ├── report/                        # 4 files + figures/
│   │   ├── IEEE_REPORT.md
│   │   ├── IEEE_REPORT_COMPLETE.tex
│   │   ├── FIGURE_DESCRIPTIONS.md
│   │   ├── PRESENTATION_OUTLINE.md
│   │   ├── TRACEABILITY.md            # NEW: claim → source mapping
│   │   └── figures/
│   │
│   └── archive/                       # Historical artifacts (~12 files)
│       ├── GAME_BACKLOG.md
│       ├── TIER1_PLAN.md
│       ├── planning.md
│       ├── PROJECT_COMPLETION_GUIDE.md
│       ├── STRUCTURAL_IMPROVEMENTS_SUMMARY.md
│       ├── DOCUMENTATION_REORGANIZATION.md
│       ├── AI_BEHAVIOR_TEST_RECOMMENDATIONS.md
│       ├── BENCHMARK_CLAIM_ORIGINS.md
│       ├── FIGURES_RECOMMENDATION.md
│       └── FIGURES_NEED_INPUT.md
│
├── backend/docs/                      # 2 files
│   ├── API_REFERENCE.md
│   └── BACKEND_CONFIG.md
│
├── frontend/docs/                     # 2 files
│   ├── FRONTEND_ARCHITECTURE.md
│   └── UI_GUIDE.md                    # ← moved from docs/
│
├── assetserver/docs/                  # ~17 files (unchanged)
│   ├── INDEX.md
│   ├── project-report.md
│   ├── architecture/
│   ├── guides/
│   ├── pipeline/
│   └── project/
│
└── dataset-gen-train/docs/            # 6 files (unchanged)
    ├── DATASET_CARD.md
    ├── MODEL_CARD.md
    ├── experiment-design.md
    ├── generation.md
    ├── training.md
    └── comfyui-workflows.md
```

**Net reduction:** ~122 files → ~55 files (55% reduction), zero information loss.

| Metric | Before | After |
|--------|--------|-------|
| Top-level `docs/` files | 18 | 6 |
| Duplicated files | 8 pairs | 0 |
| Report locations | 3 | 1 |
| Root .md files | 5 | 2 |
| `docs/plans/` files | 14 | 0 (archived or deleted) |

---

## Risks

- **Risk 1: Broken internal links** after moves/deletes → **Mitigation**: Phase 6 systematically audits all cross-references; `grep` for `](` patterns across all remaining docs
- **Risk 2: LaTeX compilation breaks** after moving `.tex` files → **Mitigation**: Test `pdflatex` compilation immediately after move; keep `.bak` until verified
- **Risk 3: Deleting a file someone still references** → **Mitigation**: All deleted content is either (a) verbatim duplicate, (b) one-time status snapshot, or (c) content absorbed into surviving docs
- **Risk 4: Asset server docs INDEX.md references stale paths** → **Mitigation**: Phase 6 audits and fixes

## Validation

- [ ] No duplicate files remain (verified by `diff` on suspected pairs)
- [ ] All cross-references resolve (run `grep -r '](.*\.md)' docs/` and verify each target exists)
- [ ] `pdflatex docs/report/IEEE_REPORT_COMPLETE.tex` compiles without errors
- [ ] `docs/` contains exactly 6 top-level .md files + 2 subdirectories
- [ ] Root contains exactly 2 .md files (`README.md`, `AGENTS.md`)
- [ ] Every quantitative claim in `IEEE_REPORT.md` has a traceable source in `TRACEABILITY.md`
- [ ] `assetserver/docs/INDEX.md` links all resolve

---

## Execution Order

```
Phase 1 (deletes) → Phase 2 (moves) → Phase 5 (plans cleanup)
    → Phase 3 (report consolidation) → Phase 4 (root cleanup)
    → Phase 6 (fix cross-refs) → Phase 7 (traceability)
```

Phases 1-2 are independent of each other. Phases 3-4 depend on Phase 2 (directories must exist). Phase 6 depends on all prior phases. Phase 7 is additive (new content) and can run in parallel with Phase 6.

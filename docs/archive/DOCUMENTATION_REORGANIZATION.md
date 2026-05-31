# Documentation Reorganization Plan

**Created:** May 31, 2026  
**Status:** Proposal - Awaiting Team Review  
**Estimated Effort:** ~25 file operations (moves, updates, link fixes)

---

## Executive Summary

This document proposes a cleaner, more professional documentation structure for StrategAI. The current state has too many files at the root level, mixed API references, and domain-specific docs scattered across locations. The reorganization follows these principles:

- **Root should be minimal** (3-5 files max)
- **docs/ should be organized by topic**, not flat
- **Subprojects own their domain-specific docs**
- **Root docs/ focuses on cross-cutting concerns** (architecture, deployment, report)
- **No duplication** - link instead of copy
- **Clear navigation hierarchy**

---

## 1. Current State Audit

### 1.1 Root Level (7 files)

| File | Purpose | Issue |
|------|---------|-------|
| `README.md` | Main project README | ✅ Keep |
| `AGENTS.md` | Agent system documentation | ✅ Keep |
| `GAME_BACKLOG.md` | Game design backlog | ❌ Planning doc, should move to `docs/plans/` |
| `TIER1_PLAN.md` | Implementation plan | ❌ Planning doc, should move to `docs/plans/` |
| `planning.md` | Original concept doc | ❌ Planning doc, should move to `docs/plans/` |
| `.impeccable.md` | Design context (hidden) | ✅ Keep (hidden file) |

**Problem:** 3 planning documents clutter the root. These are historical/planning artifacts, not primary navigation targets.

### 1.2 docs/ Level (18 files + 2 subdirs)

| File | Purpose | Issue |
|------|---------|-------|
| `API_REFERENCE.md` | Backend API reference | ❌ Backend-specific, should move to `backend/docs/` |
| `ARCHITECTURE.md` | System architecture | ✅ Keep (cross-cutting) |
| `ASSET_INTEGRATION.md` | Asset service integration | ✅ Keep (cross-cutting) |
| `BACKEND_CONFIG.md` | Backend configuration | ❌ Backend-specific, should move to `backend/docs/` |
| `DEPLOYMENT.md` | System deployment guide | ✅ Keep (cross-cutting) |
| `DEVELOPMENT.md` | Development guide | ✅ Keep (cross-cutting) |
| `FIGURE_DESCRIPTIONS.md` | Report figures | ⚠️ Move to `docs/report/` |
| `FRONTEND_ARCHITECTURE.md` | Frontend architecture | ❌ Frontend-specific, should move to `frontend/docs/` |
| `GAMEPLAY.md` | Gameplay reference | ✅ Keep (cross-cutting) |
| `IEEE_REPORT.md` | IEEE report | ✅ Keep (report) |
| `IEEE_REPORT.tex` | LaTeX version | ✅ Keep (report) |
| `IEEE_REPORT_COMPLETE.tex` | Complete LaTeX | ✅ Keep (report) |
| `PRESENTATION_OUTLINE.md` | Presentation | ✅ Keep (report) |
| `PROJECT_COMPLETION_GUIDE.md` | Project status | ⚠️ Move to `docs/plans/` |
| `REPORT_ENHANCEMENTS.md` | Report enhancements | ⚠️ Move to `docs/report/` |
| `REPORT_HANDOFF.md` | Report handoff | ⚠️ Move to `docs/report/` |
| `SEPARATION_OF_CONCERNS.md` | Architecture rationale | ⚠️ Move to `docs/architecture/` |
| `UI_GUIDE.md` | UI guide | ❌ Frontend-specific, should move to `frontend/docs/` |

**docs/figures/** (6 files) - ✅ Well organized, keep  
**docs/plans/** (4 files) - ✅ Well organized, keep and expand

**Problem:** Flat structure with 18 files makes navigation difficult. Backend and frontend docs are mixed with cross-cutting concerns.

### 1.3 Subproject Documentation

#### backend/
- `AGENTS.md` ✅
- No `docs/` directory ❌ (should have one)

#### frontend/
- `AGENTS.md` ✅
- `public/audio/ATTRIBUTION.md` ✅
- No `docs/` directory ❌ (should have one)

#### assetserver/
- `AGENTS.md` ✅
- `README.md` ✅
- `DEPLOYMENT.md` ✅ (assetserver-specific)
- `SECURITY.md` ✅
- `docs/` ✅ (well organized: `architecture/`, `guides/`, `pipeline/`, `project/`)

#### dataset-gen-train/
- `AGENTS.md` ✅
- `README.md` ✅
- `docs/` ✅ (organized: `experiment-design.md`, `generation.md`, `training.md`, etc.)

**Problem:** Backend and frontend lack dedicated docs directories, forcing their docs into root `docs/`.

---

## 2. Proposed New Structure

### 2.1 Root Level (Minimal - 3 files)

```
StrategAI/
├── README.md              # Main project README (keep)
├── AGENTS.md              # Agent system documentation (keep)
└── .impeccable.md         # Design context (keep, hidden)
```

**Rationale:** Root should only contain files needed for immediate project orientation. All planning docs move to `docs/plans/`.

### 2.2 docs/ Structure (Organized by Topic)

```
docs/
├── ARCHITECTURE.md                    # System-wide architecture (keep)
├── ASSET_INTEGRATION.md               # Cross-cutting asset integration (keep)
├── DEPLOYMENT.md                      # System-wide deployment (keep)
├── DEVELOPMENT.md                     # System-wide development guide (keep)
├── GAMEPLAY.md                        # Game mechanics reference (keep)
│
├── architecture/                      # NEW: Architecture deep-dives
│   └── SEPARATION_OF_CONCERNS.md     # Moved from docs/
│
├── figures/                           # Keep as-is
│   ├── README.md
│   ├── fig1_system_architecture.md
│   ├── fig2_intent_abstraction.md
│   ├── fig3_prompt_architecture.md
│   ├── fig4_leader_pipeline.md
│   └── fig5_lora_matrix.md
│
├── plans/                             # Expand with moved files
│   ├── AI_BEHAVIOR_TEST_RECOMMENDATIONS.md  # Keep
│   ├── COMPLETION_SUMMARY.md                # Keep
│   ├── DOCUMENTATION_PERFECTION_PLAN.md     # Keep
│   ├── QUESTIONS_FOR_TEAM.md                # Keep
│   ├── GAME_BACKLOG.md                      # Moved from root
│   ├── TIER1_PLAN.md                        # Moved from root
│   ├── planning.md                          # Moved from root
│   └── PROJECT_COMPLETION_GUIDE.md          # Moved from docs/
│
├── report/                            # NEW: Report-related docs
│   ├── IEEE_REPORT.md                 # Moved from docs/
│   ├── IEEE_REPORT.tex                # Moved from docs/
│   ├── IEEE_REPORT_COMPLETE.tex       # Moved from docs/
│   ├── PRESENTATION_OUTLINE.md        # Moved from docs/
│   ├── REPORT_HANDOFF.md              # Moved from docs/
│   ├── REPORT_ENHANCEMENTS.md         # Moved from docs/
│   └── FIGURE_DESCRIPTIONS.md         # Moved from docs/
│
└── DOCUMENTATION_REORGANIZATION.md    # This file (keep in plans/)
```

**Rationale:**
- **Top-level docs/** contains only cross-cutting, frequently-accessed files
- **architecture/** groups architectural deep-dives
- **plans/** consolidates all planning and backlog documents
- **report/** groups all IEEE report and presentation materials
- **figures/** remains unchanged (already well organized)

### 2.3 Backend Documentation (NEW)

```
backend/
├── AGENTS.md                          # Keep
└── docs/                              # NEW directory
    ├── API_REFERENCE.md               # Moved from docs/
    └── BACKEND_CONFIG.md              # Moved from docs/
```

**Rationale:** Backend-specific API and configuration docs belong in the backend subproject. Root `docs/` will link to these.

### 2.4 Frontend Documentation (NEW)

```
frontend/
├── AGENTS.md                          # Keep
├── public/audio/ATTRIBUTION.md        # Keep
└── docs/                              # NEW directory
    ├── FRONTEND_ARCHITECTURE.md       # Moved from docs/
    └── UI_GUIDE.md                    # Moved from docs/
```

**Rationale:** Frontend-specific architecture and UI docs belong in the frontend subproject. Root `docs/` will link to these.

### 2.5 Asset Server Documentation (No Changes)

```
assetserver/
├── AGENTS.md                          # Keep
├── README.md                          # Keep
├── DEPLOYMENT.md                      # Keep (assetserver-specific)
├── SECURITY.md                        # Keep
└── docs/                              # Already well organized
    ├── INDEX.md
    ├── project-report.md
    ├── architecture/                  # 11 files
    ├── guides/                        # 7 files
    ├── pipeline/                      # 2 files
    └── project/                       # 1 file
```

**Rationale:** Asset server docs are already well organized. No changes needed.

### 2.6 Dataset/Training Documentation (No Changes)

```
dataset-gen-train/
├── AGENTS.md                          # Keep
├── README.md                          # Keep
└── docs/                              # Already organized
    ├── experiment-design.md
    ├── generation.md
    ├── training.md
    ├── comfyui-workflows.md
    ├── MODEL_CARD.md
    └── DATASET_CARD.md
```

**Rationale:** Dataset/training docs are already well organized. No changes needed.

---

## 3. Migration Plan

### 3.1 File Moves (17 operations)

#### From Root to docs/plans/ (3 moves)
1. `GAME_BACKLOG.md` → `docs/plans/GAME_BACKLOG.md`
2. `TIER1_PLAN.md` → `docs/plans/TIER1_PLAN.md`
3. `planning.md` → `docs/plans/planning.md`

#### From docs/ to docs/architecture/ (1 move)
4. `docs/SEPARATION_OF_CONCERNS.md` → `docs/architecture/SEPARATION_OF_CONCERNS.md`

#### From docs/ to docs/plans/ (1 move)
5. `docs/PROJECT_COMPLETION_GUIDE.md` → `docs/plans/PROJECT_COMPLETION_GUIDE.md`

#### From docs/ to docs/report/ (7 moves)
6. `docs/IEEE_REPORT.md` → `docs/report/IEEE_REPORT.md`
7. `docs/IEEE_REPORT.tex` → `docs/report/IEEE_REPORT.tex`
8. `docs/IEEE_REPORT_COMPLETE.tex` → `docs/report/IEEE_REPORT_COMPLETE.tex`
9. `docs/PRESENTATION_OUTLINE.md` → `docs/report/PRESENTATION_OUTLINE.md`
10. `docs/REPORT_HANDOFF.md` → `docs/report/REPORT_HANDOFF.md`
11. `docs/REPORT_ENHANCEMENTS.md` → `docs/report/REPORT_ENHANCEMENTS.md`
12. `docs/FIGURE_DESCRIPTIONS.md` → `docs/report/FIGURE_DESCRIPTIONS.md`

#### From docs/ to backend/docs/ (2 moves)
13. `docs/API_REFERENCE.md` → `backend/docs/API_REFERENCE.md`
14. `docs/BACKEND_CONFIG.md` → `backend/docs/BACKEND_CONFIG.md`

#### From docs/ to frontend/docs/ (2 moves)
15. `docs/FRONTEND_ARCHITECTURE.md` → `frontend/docs/FRONTEND_ARCHITECTURE.md`
16. `docs/UI_GUIDE.md` → `frontend/docs/UI_GUIDE.md`

#### Directory Creation (1 operation)
17. Create `docs/architecture/` directory

### 3.2 Files to Delete (0 operations)

**No files need deletion.** All identified documents serve a purpose and should be relocated, not removed.

### 3.3 Files to Merge (0 operations)

**No merges recommended at this time.** While some report-related files overlap (e.g., `REPORT_HANDOFF.md`, `REPORT_ENHANCEMENTS.md`), they serve distinct purposes in the report-writing workflow. Merging would reduce clarity for agents working on specific report sections.

**Future consideration:** After the June 1 deadline, consider merging report docs into a single comprehensive guide.

---

## 4. Cross-Reference Updates

### 4.1 README.md Updates

**Current links that will break:**
- None (README.md doesn't link to moved files directly)

**Recommended additions:**
- Add link to `docs/DEVELOPMENT.md` for getting started
- Add link to `docs/architecture/` for system design
- Add links to subproject docs: `backend/docs/`, `frontend/docs/`, `assetserver/docs/`

### 4.2 AGENTS.md Updates

**Current links that will break:**
- Line referencing `docs/ARCHITECTURE.md` ✅ (not moved)
- Line referencing `docs/DEVELOPMENT.md` ✅ (not moved)
- Line referencing `docs/GAMEPLAY.md` ✅ (not moved)
- Line referencing `docs/ASSET_INTEGRATION.md` ✅ (not moved)
- Line referencing `docs/UI_GUIDE.md` ❌ (moved to `frontend/docs/UI_GUIDE.md`)
- Line referencing `assetserver/docs/project-report.md` ✅ (not moved)

**Required update:**
```markdown
# OLD
- `docs/UI_GUIDE.md` — Frontend lifecycle, panel breakdown, audio plumbing

# NEW
- `frontend/docs/UI_GUIDE.md` — Frontend lifecycle, panel breakdown, audio plumbing
```

### 4.3 docs/DEVELOPMENT.md Updates

**Current links that will break:**
- `[GAMEPLAY.md](GAMEPLAY.md)` ✅ (not moved)
- `[UI_GUIDE.md](UI_GUIDE.md)` ❌ (moved to `frontend/docs/UI_GUIDE.md`)
- `[ASSET_INTEGRATION.md](ASSET_INTEGRATION.md)` ✅ (not moved)

**Required update:**
```markdown
# OLD
For game mechanics see [GAMEPLAY.md](GAMEPLAY.md); for UI structure see
[UI_GUIDE.md](UI_GUIDE.md); for asset service integration see
[ASSET_INTEGRATION.md](ASSET_INTEGRATION.md).

# NEW
For game mechanics see [GAMEPLAY.md](GAMEPLAY.md); for UI structure see
[../frontend/docs/UI_GUIDE.md](../frontend/docs/UI_GUIDE.md); for asset service integration see
[ASSET_INTEGRATION.md](ASSET_INTEGRATION.md).
```

### 4.4 docs/ASSET_INTEGRATION.md Updates

**Current links that will break:**
- `[GAMEPLAY.md](GAMEPLAY.md)` ✅ (not moved)
- `[UI_GUIDE.md](UI_GUIDE.md)` ❌ (moved to `frontend/docs/UI_GUIDE.md`)

**Required update:**
```markdown
# OLD
For the game-side mechanics see [GAMEPLAY.md](GAMEPLAY.md); for UI surfaces
see [UI_GUIDE.md](UI_GUIDE.md).

# NEW
For the game-side mechanics see [GAMEPLAY.md](GAMEPLAY.md); for UI surfaces
see [../frontend/docs/UI_GUIDE.md](../frontend/docs/UI_GUIDE.md).
```

### 4.5 docs/DEPLOYMENT.md Updates

**Current links that will break:**
- `[SEPARATION_OF_CONCERNS.md](SEPARATION_OF_CONCERNS.md)` ❌ (moved to `architecture/SEPARATION_OF_CONCERNS.md`)

**Required update:**
```markdown
# OLD
See [SEPARATION_OF_CONCERNS.md](SEPARATION_OF_CONCERNS.md) for the architectural rationale.

# NEW
See [architecture/SEPARATION_OF_CONCERNS.md](architecture/SEPARATION_OF_CONCERNS.md) for the architectural rationale.
```

### 4.6 Moved Files - Internal Link Updates

#### backend/docs/API_REFERENCE.md
- No internal links to update (standalone reference doc)

#### backend/docs/BACKEND_CONFIG.md
- No internal links to update (standalone reference doc)

#### frontend/docs/FRONTEND_ARCHITECTURE.md
- No internal links to update (standalone reference doc)

#### frontend/docs/UI_GUIDE.md
**Current links that will break:**
- `[GAMEPLAY.md](GAMEPLAY.md)` ❌ (now at `../../docs/GAMEPLAY.md`)
- `[ASSET_INTEGRATION.md](ASSET_INTEGRATION.md)` ❌ (now at `../../docs/ASSET_INTEGRATION.md`)

**Required update:**
```markdown
# OLD
For game rules see [GAMEPLAY.md](GAMEPLAY.md); for asset integration see
[ASSET_INTEGRATION.md](ASSET_INTEGRATION.md).

# NEW
For game rules see [../../docs/GAMEPLAY.md](../../docs/GAMEPLAY.md); for asset integration see
[../../docs/ASSET_INTEGRATION.md](../../docs/ASSET_INTEGRATION.md).
```

#### docs/plans/GAME_BACKLOG.md
- No internal links to update

#### docs/plans/TIER1_PLAN.md
- No internal links to update

#### docs/plans/planning.md
- No internal links to update

#### docs/architecture/SEPARATION_OF_CONCERNS.md
- No internal links to update

#### docs/report/*.md files
- No internal links to update (standalone report sections)

### 4.7 Subproject README Updates

#### backend/README.md (if exists)
**Recommended addition:**
```markdown
## Documentation

- [API Reference](docs/API_REFERENCE.md) - Complete REST API documentation
- [Backend Configuration](docs/BACKEND_CONFIG.md) - Environment variables and configuration
```

#### frontend/README.md (if exists)
**Recommended addition:**
```markdown
## Documentation

- [Frontend Architecture](docs/FRONTEND_ARCHITECTURE.md) - Component structure and state management
- [UI Guide](docs/UI_GUIDE.md) - UI components and lifecycle
```

### 4.8 Root docs/ Navigation

**Create or update `docs/README.md`** (optional but recommended):

```markdown
# StrategAI Documentation

## Getting Started
- [Development Guide](DEVELOPMENT.md) - Setup, environment, workflows
- [Gameplay Reference](GAMEPLAY.md) - Complete game mechanics

## Architecture
- [System Architecture](ARCHITECTURE.md) - High-level design
- [Separation of Concerns](architecture/SEPARATION_OF_CONCERNS.md) - Deployment rationale
- [Asset Integration](ASSET_INTEGRATION.md) - Asset service contract

## Subproject Documentation
- [Backend API & Configuration](../backend/docs/)
- [Frontend Architecture & UI](../frontend/docs/)
- [Asset Server](../assetserver/docs/INDEX.md)
- [Dataset & Training](../dataset-gen-train/docs/)

## Deployment
- [Deployment Guide](DEPLOYMENT.md) - Production deployment

## Report & Presentation
- [IEEE Report](report/IEEE_REPORT.md)
- [Presentation Outline](report/PRESENTATION_OUTLINE.md)
- [Report Handoff](report/REPORT_HANDOFF.md)

## Planning & Backlog
- [Game Backlog](plans/GAME_BACKLOG.md)
- [Tier 1 Plan](plans/TIER1_PLAN.md)
- [Project Completion Guide](plans/PROJECT_COMPLETION_GUIDE.md)
```

---

## 5. Execution Checklist

### Phase 1: Directory Creation (1 operation)
- [ ] Create `docs/architecture/` directory
- [ ] Create `docs/report/` directory
- [ ] Create `backend/docs/` directory
- [ ] Create `frontend/docs/` directory

### Phase 2: File Moves (16 operations)
- [ ] Move 3 files from root to `docs/plans/`
- [ ] Move 1 file from `docs/` to `docs/architecture/`
- [ ] Move 1 file from `docs/` to `docs/plans/`
- [ ] Move 7 files from `docs/` to `docs/report/`
- [ ] Move 2 files from `docs/` to `backend/docs/`
- [ ] Move 2 files from `docs/` to `frontend/docs/`

### Phase 3: Link Updates (6 operations)
- [ ] Update `AGENTS.md` (1 link)
- [ ] Update `docs/DEVELOPMENT.md` (1 link)
- [ ] Update `docs/ASSET_INTEGRATION.md` (1 link)
- [ ] Update `docs/DEPLOYMENT.md` (1 link)
- [ ] Update `frontend/docs/UI_GUIDE.md` (2 links)
- [ ] Create `docs/README.md` (optional navigation hub)

### Phase 4: Verification (1 operation)
- [ ] Run link checker or manually verify all internal links
- [ ] Update root `README.md` with new doc structure (optional)
- [ ] Update subproject READMEs with doc links (optional)

**Total Estimated Operations:** ~25

---

## 6. Benefits of This Reorganization

### 6.1 Cleaner Root Level
- **Before:** 7 files (3 planning docs cluttering root)
- **After:** 3 files (only essential orientation docs)
- **Impact:** Easier project navigation, more professional appearance

### 6.2 Better Topic Organization
- **Before:** 18 flat files in `docs/`
- **After:** 5 top-level files + 4 organized subdirectories
- **Impact:** Faster discovery of relevant documentation

### 6.3 Domain-Specific Ownership
- **Before:** Backend/frontend docs mixed in root `docs/`
- **After:** Each subproject owns its domain-specific docs
- **Impact:** Clearer responsibility, easier maintenance

### 6.4 Improved Cross-Cutting Documentation
- **Before:** Cross-cutting docs buried in flat structure
- **After:** Top-level `docs/` focuses on system-wide concerns
- **Impact:** Better separation of concerns in documentation

### 6.5 Scalable Structure
- **Before:** Adding new docs increases clutter
- **After:** Clear placement guidelines for new documentation
- **Impact:** Sustainable documentation growth

---

## 7. Risks and Mitigations

### 7.1 Broken Links
**Risk:** Moving files breaks internal links  
**Mitigation:** Comprehensive link update checklist (Section 4)  
**Verification:** Manual link check or automated link checker after migration

### 7.2 Agent Confusion
**Risk:** AI agents may reference old paths  
**Mitigation:** Update `AGENTS.md` with new paths; agents will adapt  
**Verification:** Test agent queries after migration

### 7.3 Report Citations
**Risk:** IEEE report may reference moved files  
**Mitigation:** Check `IEEE_REPORT.md` and `.tex` files for file references  
**Verification:** Review report for broken citations

### 7.4 Team Familiarity
**Risk:** Team members accustomed to old structure  
**Mitigation:** Clear documentation of new structure; gradual transition  
**Verification:** Team review and approval before execution

---

## 8. Alternative Approaches Considered

### 8.1 Keep Flat Structure with Better Naming
**Approach:** Rename files with prefixes (e.g., `backend-api-reference.md`)  
**Rejected because:** Doesn't solve navigation problem; still 18+ files in one directory

### 8.2 Move All Docs to Subprojects
**Approach:** Move everything to `backend/docs/`, `frontend/docs/`, etc.  
**Rejected because:** Cross-cutting docs (architecture, deployment) don't belong in single subproject

### 8.3 Create Separate Documentation Site
**Approach:** Use MkDocs, Docusaurus, or similar  
**Rejected because:** Overkill for project scope; adds build complexity; June 1 deadline

### 8.4 Merge Redundant Documents
**Approach:** Combine overlapping report docs  
**Rejected because:** Docs serve distinct purposes in report workflow; merging reduces clarity

---

## 9. Future Improvements

### 9.1 Post-Deadline Cleanup
After June 1 deadline, consider:
- Merging report docs into single comprehensive guide
- Archiving planning docs that are no longer relevant
- Creating documentation style guide

### 9.2 Automated Link Checking
Add CI/CD step to verify all internal links remain valid after changes.

### 9.3 Documentation Search
Consider adding full-text search across all documentation (e.g., MkDocs with search plugin).

### 9.4 Versioned Documentation
For long-term maintenance, consider versioning docs alongside code releases.

---

## 10. Approval and Next Steps

### 10.1 Review Checklist
- [ ] Team reviews proposed structure
- [ ] Verify no critical links will break
- [ ] Confirm subproject ownership of domain docs
- [ ] Approve file moves and link updates

### 10.2 Execution Plan
1. **Approval:** Team reviews and approves this plan
2. **Backup:** Create git branch for documentation reorganization
3. **Execution:** Perform file moves and link updates (Section 5)
4. **Verification:** Test all internal links
5. **Communication:** Notify team of new structure
6. **Merge:** PR to main branch after verification

### 10.3 Rollback Plan
If issues arise:
- Revert git branch to restore old structure
- Investigate and fix issues
- Re-execute with corrections

---

## Summary

This reorganization reduces root-level clutter from 7 to 3 files, organizes 18 flat docs into 4 logical subdirectories, and establishes clear ownership of domain-specific documentation. The migration requires ~25 operations (17 moves, 6 link updates, 2 directory creations) and poses minimal risk with proper verification.

**Key Principles Achieved:**
✅ Root is minimal (3 files)  
✅ docs/ is organized by topic (5 top-level + 4 subdirs)  
✅ Subprojects own domain-specific docs  
✅ Cross-cutting concerns in root docs/  
✅ No duplication (link instead of copy)  
✅ Clear navigation hierarchy  

**Next Step:** Team review and approval before execution.

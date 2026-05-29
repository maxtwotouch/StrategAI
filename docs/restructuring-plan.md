# Project Restructuring Plan: Directory Segmentation by Category

**Date:** 2026-05-29
**Status:** Planning
**Author:** Copilot (GitHub Copilot)

---

## 1. Problem Statement

The `src/` directory is a flat list of 20+ Python modules with no organizational hierarchy. As the project grows, this becomes a readability and navigability bottleneck. The code naturally falls into **four vertical slices** (pipelines), and the directory structure should reflect that.

---

## 2. Proposed New Directory Structure

```
src/
├── __init__.py                          # Re-export public API (unchanged)
├── config.py                            # Core configuration (stays at root)
├── database.py                          # Core database engine (stays at root)
├── storage.py                           # Core asset store (stays at root)
├── models.py                            # Shared/base models (stays at root)
├── comfyui_client.py                    # Shared ComfyUI client (stays at root)
├── generators.py                        # Shared generator ABC + factory (stays at root)
├── inpainting.py                        # Shared inpainting utilities (stays at root)
├── static_catalog.py                    # Shared static catalog (stays at root)
├── main.py                              # FastAPI app entry point (stays at root)
│
├── leader/                              # NEW: Leader pipeline slice
│   ├── __init__.py
│   ├── engine.py          ← leader_engine.py
│   ├── models.py          ← leader_models.py
│   ├── prompts.py         ← leader_prompts.py
│   └── registry.py        ← leader_registry.py
│
├── tile/                                # NEW: Tile pipeline slice
│   ├── __init__.py
│   ├── engine.py          ← tile_engine.py
│   ├── models.py          ← tile_models.py
│   ├── prompts.py         ← tile_prompts.py
│   └── registry.py        ← tile_registry.py
│
└── unit/                                # NEW: Unit pipeline slice
    ├── __init__.py
    ├── engine.py          ← unit_engine.py
    ├── models.py          ← unit_models.py
    ├── prompts.py         ← unit_prompts.py
    └── registry.py        ← unit_registry.py
```

**Key decisions:**
- **Shared infrastructure stays at `src/` root.** Files like `config.py`, `database.py`, `storage.py`, `models.py`, `comfyui_client.py`, `generators.py`, `inpainting.py`, `static_catalog.py`, and `main.py` are used across multiple pipelines and don't belong to a single category.
- **Each pipeline gets its own package** (`leader/`, `tile/`, `unit/`) with `__init__.py` for clean imports.
- **Files are renamed to `engine.py`** inside each package since the filename prefix (`leader_`, `tile_`, `unit_`) becomes redundant with the directory name.

---

## 3. Import Path Changes Required

Every file that currently does `from src.leader_*` or `from src.tile_*` or `from src.unit_*` needs updating. Here is the complete mapping:

### 3.1 Old → New module paths

| Old import | New import |
|---|---|
| `src.leader_engine` | `src.leader.engine` |
| `src.leader_models` | `src.leader.models` |
| `src.leader_prompts` | `src.leader.prompts` |
| `src.leader_registry` | `src.leader.registry` |
| `src.tile_engine` | `src.tile.engine` |
| `src.tile_models` | `src.tile.models` |
| `src.tile_prompts` | `src.tile.prompts` |
| `src.tile_registry` | `src.tile.registry` |
| `src.unit_engine` | `src.unit.engine` |
| `src.unit_models` | `src.unit.models` |
| `src.unit_prompts` | `src.unit.prompts` |
| `src.unit_registry` | `src.unit.registry` |

### 3.2 Files requiring import updates

| File | Imports to update |
|---|---|
| `src/main.py` | All 12 pipeline imports |
| `src/generators.py` | `src.comfyui_client`, `src.config`, `src.inpainting`, `src.models`, `src.static_catalog`, `src.storage` (no pipeline imports — OK) |
| `src/leader/engine.py` | `src.comfyui_client`, `src.config`, `src.database`, `src.leader.models`, `src.leader.prompts`, `src.leader.registry`, `src.storage` |
| `src/tile/engine.py` | `src.comfyui_client`, `src.config`, `src.database`, `src.tile.models`, `src.tile.prompts`, `src.tile.registry`, `src.static_catalog`, `src.storage` |
| `src/unit/engine.py` | `src.comfyui_client`, `src.config`, `src.database`, `src.unit.models`, `src.unit.prompts`, `src.unit.registry`, `src.static_catalog`, `src.storage` |
| All test files | Corresponding test imports (see §5) |

### 3.3 Intra-pipeline imports (within the new packages)

Within `leader/`:
- `engine.py` imports from `.models`, `.prompts`, `.registry`
- `prompts.py` imports from `.models` (for type hints) and `src.config`

Within `tile/`:
- `engine.py` imports from `.models`, `.prompts`, `.registry`
- `prompts.py` imports from `.models`

Within `unit/`:
- `engine.py` imports from `.models`, `.prompts`, `.registry`
- `prompts.py` imports from `.models`

---

## 4. Documentation Updates

| Doc file | What to update |
|---|---|
| `docs/architecture.md` | Add a section or diagram showing the new 4-slice structure. Update any module dependency diagrams. |
| `docs/leader-pipeline-reference.md` | Update import paths in code examples. Add note about new `src/leader/` package. |
| `docs/tile-prompt-guide.md` | Update import paths if any code snippets reference old module paths. |
| `docs/unit-prompt-guide.md` | Same as above for unit. |
| `docs/next_steps.md` | Add the restructuring as a completed/referenced milestone. |
| `docs/testing-plan.md` | Update test discovery notes — pytest must be configured to find tests in the new structure (see §5). |
| `README.md` | Update any "how to run" or "project structure" sections. |
| `config/prompt_templates.json` | No changes needed (path is computed dynamically via `os.path.dirname`). |

---

## 5. Testing Strategy

### 5.1 Test file restructuring

Test files should mirror the new structure:

```
tests/
├── __init__.py
├── conftest.py                              # Already at root — OK
├── test_config.py                           # Core — stays at root
├── test_database.py                         # Core — stays at root
├── test_comfyui_client.py                   # Core — stays at root
├── test_generators.py                       # Core — stays at root
├── test_inpainting.py                       # Core — stays at root
├── test_static_catalog.py                   # Core — stays at root
├── test_storage.py                          # Core — stays at root
├── test_models.py                           # Core — stays at root
├── test_main.py                             # Core — stays at root
├── test_doc_code_consistency.py             # Core — stays at root
│
├── leader/
│   ├── __init__.py
│   ├── test_leader_engine.py    ← from test_leader_engine.py
│   ├── test_leader_models.py    ← from test_leader_models.py
│   ├── test_leader_prompts.py   ← from test_leader_prompts.py
│   └── test_leader_registry.py  ← extracted from test_leader_engine.py
│
├── tile/
│   ├── __init__.py
│   ├── test_tile_engine.py     ← from test_tile_engine.py
│   ├── test_tile_models.py     ← from test_tile_models.py
│   ├── test_tile_prompts.py    ← from test_tile_prompts.py
│   └── test_tile_registry.py   ← extracted from test_tile_engine.py
│
└── unit/
    ├── __init__.py
    ├── test_unit_engine.py     ← from test_unit_engine.py
    ├── test_unit_models.py     ← from test_unit_models.py
    ├── test_unit_prompts.py    ← from test_unit_prompts.py
    └── test_unit_registry.py   ← extracted from test_unit_engine.py
```

**Note on registry tests:** Currently there is no dedicated `test_tile_registry.py` or `test_unit_registry.py` — tests for registry functions are embedded in `test_tile_engine.py` and `test_unit_engine.py`. During migration, extract those tests into their own files for proper separation of concerns.

### 5.2 `conftest.py` updates

The existing `conftest.py` at `tests/` root should still work since it provides fixtures used by all tests. No structural changes needed unless we want per-pipeline conftest files (recommended: keep it at root for shared fixtures).

### 5.3 `pytest.ini` verification

Ensure `pytest.ini` has recursive test discovery enabled (default behavior). If it uses explicit `testpaths`, add the new subdirectories:

```ini
[tool.pytest.ini_options]
testpaths = ["tests", "tests/leader", "tests/tile", "tests/unit"]
```

Or simply rely on the default: `pytest` discovers `test_*.py` and `*_test.py` files recursively.

### 5.4 Test execution order

1. **Core tests first** — these have no import path changes and validate the foundation.
2. **Pipeline tests** — after the code migration is complete, run the full suite.

---

## 6. Migration Steps (Ordered)

The order is designed to keep the project runnable after each step.

### Phase 1: Scaffold new directories (no code changes yet)

1. Create `src/leader/`, `src/tile/`, `src/unit/` directories with `__init__.py` files.
2. Create `tests/leader/`, `tests/tile/`, `tests/unit/` directories with `__init__.py` files.
3. Verify the project still runs (`python -c "import src.main"`).

### Phase 2: Move leader pipeline files

4. Move `src/leader_engine.py` → `src/leader/engine.py`.
5. Move `src/leader_models.py` → `src/leader/models.py`.
6. Move `src/leader_prompts.py` → `src/leader/prompts.py`.
7. Move `src/leader_registry.py` → `src/leader/registry.py`.
8. Update all imports in the moved files (intra-package imports become relative: `.models`, `.prompts`, `.registry`).
9. Update `src/main.py` imports to use new paths.
10. Move corresponding test files to `tests/leader/` and update their imports.
11. **Run tests** — `pytest tests/leader/ tests/test_main.py -x`.

### Phase 3: Move tile pipeline files

12. Move `src/tile_engine.py` → `src/tile/engine.py`.
13. Move `src/tile_models.py` → `src/tile/models.py`.
14. Move `src/tile_prompts.py` → `src/tile/prompts.py`.
15. Move `src/tile_registry.py` → `src/tile/registry.py`.
16. Update all imports in the moved files.
17. Update `src/main.py` imports to use new paths.
18. Move corresponding test files to `tests/tile/` and update their imports.
19. **Run tests** — `pytest tests/tile/ tests/test_main.py -x`.

### Phase 4: Move unit pipeline files

20. Move `src/unit_engine.py` → `src/unit/engine.py`.
21. Move `src/unit_models.py` → `src/unit/models.py`.
22. Move `src/unit_prompts.py` → `src/unit/prompts.py`.
23. Move `src/unit_registry.py` → `src/unit/registry.py`.
24. Update all imports in the moved files.
25. Update `src/main.py` imports to use new paths.
26. Move corresponding test files to `tests/unit/` and update their imports.
27. **Run tests** — `pytest tests/unit/ tests/test_main.py -x`.

### Phase 5: Cleanup and documentation

28. Delete the old flat files from `src/` (they've been moved).
29. Update `docs/architecture.md` with the new structure diagram.
30. Update all other documentation files per §4.
31. Update `README.md` project structure section.
32. Run the **full test suite**: `pytest`.
33. Verify `pip install -e .` and `uvicorn src.main:app --reload` still work.

---

## 7. Risk Mitigation

| Risk | Mitigation |
|---|---|
| Circular imports after restructuring | Each pipeline package only imports from `src.*` (shared) and its own siblings (`.models`, `.prompts`, `.registry`). No cross-pipeline imports exist today. |
| `pyproject.toml` package discovery breaks | `[tool.setuptools.packages.find]` uses `include = ["src*"]` which matches `src.leader`, `src.tile`, `src.unit` automatically. |
| Test discovery fails | Verify `pytest.ini` or use `pytest --collect-only` before running. |
| Forgotten import update causes runtime error | Run `python -c "import src.main"` after each phase. Also: `grep -r "from src\.leader_" src/ tests/` to catch stragglers. |
| `config/prompt_templates.json` path breaks | The path is computed as `Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "config" / "prompt_templates.json"` — this resolves from `src/` root, which doesn't change for any pipeline file. |

---

## 8. Post-Migration Verification Checklist

- [ ] `pytest` passes with 0 failures
- [ ] `python -c "from src.leader.engine import LeaderEngine"` works
- [ ] `python -c "from src.tile.engine import TileEngine"` works
- [ ] `python -c "from src.unit.engine import UnitEngine"` works
- [ ] `python -c "from src.main import app"` works
- [ ] `pip install -e .` succeeds
- [ ] `uvicorn src.main:app --reload` starts without errors
- [ ] All doc files reference correct import paths
- [ ] No leftover flat files in `src/` (only `__init__.py` + shared modules + 3 subdirectories)
- [ ] `git diff --stat` shows only moves and import changes (no logic changes)
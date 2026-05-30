
Now I have a thorough understanding of the entire codebase. Let me compile the comprehensive testing plan.
 
Comprehensive Testing Suite Plan
Test Architecture Overview
The test suite should follow pytest conventions, live in a tests/ directory at the project root, and use fixtures, parametrization, and mocking patterns consistent with FastAPI + SQLAlchemy best practices. Tests are organized into layers: unit → integration → API.
 
1. Test Infrastructure & Dependencies
1.1 New dependencies (requirements-dev.txt or added to requirements.txt)
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.27                  # Async test client for FastAPI
pytest-cov>=5.0              # Coverage
pytest-mock>=3.14            # Mocking
aiosqlite>=0.20              # In-memory SQLite for async tests
Pillow>=10.0                 # Already present — for image assertions
1.2 Test fixtures (tests/conftest.py)
Fixture
Scope
Purpose
tmp_project_root
function
Temp dir with full project skeleton (static_tiles/, generated_assets/, config.yaml, etc.)
test_settings
function
Settings instance pointing at temp dirs
test_db
function
In-memory SQLite engine + create-all, yield, drop-all
db_session
function
SQLAlchemy session from test_db
test_store
function
AssetStore pointed at temp output dir
test_catalog
function
StaticCatalog scanning a controlled static_tiles/ tree
async_client
function
httpx.AsyncClient against a FastAPI TestClient with lifespan
mock_comfyui_client
function
AsyncMock wrapping ComfyUIClient
sample_requests
session
Dict of valid StructureRequest, ObjectRequest, TerrainRequest, LeaderRequest, UnitRequest
sample_png
session
A minimal 16×16 RGBA PIL Image
 
2. Unit Tests
2.1 Configuration (tests/test_config.py)
Test
What It Verifies
test_default_modes_all_present
All 10 families have entries in generation.modes defaults
test_get_mode_known_family
settings.get_mode("structure") returns "comfyui"
test_get_mode_unknown_family_falls_back_to_default
Unknown family returns generation.default_mode
test_yaml_override
config.yaml values override defaults
test_env_var_override
COMFYUI__BASE_URL env var wins over yaml
test_derived_paths_exist
workflow_dir, leader_workflow_dir resolve correctly
test_modes_dict_is_mutable
You can set settings.generation.modes["structure"] = "placeholder" at runtime
2.2 Data Models — Validation (tests/test_models.py, tests/test_tile_models.py, tests/test_leader_models.py, tests/test_unit_models.py)
Test
What It Verifies
test_structure_request_valid
All 4 enum fields + description ≥20 chars → passes
test_structure_request_invalid_category
Unknown category → ValidationError
test_structure_request_description_too_short
10-char description → ValidationError
test_structure_request_description_too_long
500-char description → ValidationError
test_structure_request_seed_optional
Missing seed → valid, seed is None
(Same pattern for ObjectRequest, TerrainRequest)

test_leader_request_splash_valid
asset_type="splash" without leader_id → valid
test_leader_request_profile_requires_leader_id
asset_type="profile" without leader_id → valid (enforced at engine level)
test_leader_request_action_requires_category
asset_type="action" requires action_category
test_unit_request_valid
unit_type="archer", description≥20 → passes
test_unit_request_invalid_type
unit_type="dragon" → ValidationError (note: currently not constrained — this test exposes a gap)
test_unit_directions_all_fields_required
Missing n → ValidationError
test_unit_response_construction
Full UnitResponse with UnitDirections
test_generation_request_tile_type_required_for_background
asset_family="background_tile" without tile_type → valid (note: schema allows it but engine should reject)
test_generation_request_inpaint_coordinates
Coordinate(x=-1, y=0) — schema allows negatives (is that desired?)
2.3 Database Models (tests/test_database.py)
Test
What It Verifies
test_all_tables_created
All 7 tables exist in SQLite after Base.metadata.create_all
test_asset_record_insert_and_query
Insert + query by ID
test_asset_record_defaults
created_at auto-set, asset_family defaults to "unknown"
test_leader_record_insert
Full insert with all columns
test_leader_record_action_ids_json
action_image_ids stored/retrieved as list
test_structure_record_constraints
image_id NOT NULL — insert without it raises
test_object_record_constraints
Same
test_terrain_record_constraints
Same
test_unit_record_constraints
image_id NOT NULL — insert without it raises
test_get_db_context_manager
get_db() yields a session and closes it
2.4 Storage — AssetStore (tests/test_storage.py)
Test
What It Verifies
test_save_and_retrieve_bytes
Save PIL Image, get bytes back → same PNG binary
test_save_and_retrieve_pil
Save, get_image_pil() → same dimensions + mode
test_get_nonexistent_returns_none
get_image_bytes("nope.png") → None
test_get_nonexistent_pil_raises
get_image_pil("nope.png") → FileNotFoundError
test_memory_cache_hit
Second retrieval returned from memory, no disk read
test_lru_eviction
Insert 1001 items at max_cache_size=1000, first item evicted
test_lru_reorder_on_access
Access an old item → it moves to end, survives eviction
test_save_from_path
save_from_path() copies a file into the store
test_memory_cache_move_to_end
Access moves item to end (OrderedDict behaviour)
test_disk_fallback_after_cache_miss
Item on disk but not in cache → loads from disk, enters cache
2.5 Static Catalog (tests/test_static_catalog.py)
Test
What It Verifies
test_scan_background_tile
water.png, grass_1.png, grass_2.png → list_tile_types() = ["grass", "water"]
test_resolve_tile_random
resolve_tile("grass") returns a path containing grass
test_resolve_tile_nonexistent
resolve_tile("lava") → None
test_resolve_tile_multiple_variants
grass_1.png + grass_2.png → both reachable via resolve_tile
test_scan_structure_with_subtypes
fortification/castle.png, production/mill.png → list_structure_subtypes() = ["fortification", "production"]
test_resolve_structure_with_subtype
resolve_random("structure", "fortification") → only returns fortification PNGs
test_resolve_structure_without_subtype
resolve_random("structure", None) → returns from any subtype
test_scan_nature_object_flat
Any PNG in nature_object/ → has_any("nature_object") = True
test_scan_character_sprite_flat
Same pattern
test_has_any_empty_family
has_any("terrain") → False (no static_tiles/terrain/)
test_scan_unit_flat_naming
archer_s.png, archer_n.png, scout_s.png → cataloged correctly
test_resolve_unit_exact_direction
resolve_unit("archer", "n") → returns the north sprite
test_resolve_unit_s_fallback
resolve_unit("scout", "e") when no east PNG → returns south sprite
test_resolve_unit_no_s_fallback
resolve_unit("warrior", "s") with no warrior PNGs → None
test_list_unit_types
Only types with at least a south PNG appear
test_has_unit_type
has_unit_type("archer") with archer_s.png → True
test_invalid_direction_ignored
archer_x.png not cataloged (x not in _VALID_UNIT_DIRECTIONS)
test_empty_root_dir
No crash, empty catalog
test_nonexistent_root_dir
No crash, empty catalog
test_numeric_suffix_stripping
water_3.png → keyed as "water"
test_multiple_pngs_same_tile_type
Both grass_1.png and grass_v2.png → both mapped to "grass" key
2.6 Prompt Builders
Leader prompts (tests/test_leader_prompts.py)
Test
What It Verifies
test_build_splash_prompt_contains_all_enums
Output contains archetype prose, culture prose, time_of_day prose, mood prose, SPLASH_TAIL
test_build_profile_prompt
Contains "close-up portrait", "face filling the frame", mood, PROFILE_TAIL
test_build_action_prompt
Contains action_description, action_category prose, culture, time_of_day, mood, ACTION_TAIL
test_build_prompt_dispatcher
build_prompt() routes to correct builder based on asset_type
test_splash_prompt_ends_with_tail
Final comma-separated segment matches SPLASH_TAIL
test_leader_description_included
The leader_description field appears verbatim
Tile prompts (tests/test_tile_prompts.py)
Test
What It Verifies
test_build_structure_prompt_injection
Each enum value's prose appears in output
test_build_object_prompt_injection
Category, biome, season prose all present
test_build_terrain_prompt_injection
Category, scale, material prose all present
test_template_wrapping
Output starts with <tdp> prefix from prompt_templates.json
test_description_appears_last
User's free-form description appears verbatim
test_load_template_key_error
Invalid key raises KeyError
test_template_lazy_loading
_load_templates() only reads file once (cache hit)
Unit prompts (tests/test_unit_prompts.py)
Test
What It Verifies
test_build_unit_prompt_archer_south
Contains "medieval archer", "facing camera", "front view"
test_build_unit_prompt_warrior_east
Contains "medieval warrior", "facing right", "side profile"
test_build_unit_prompt_settler_north
Contains "medieval settler", "facing away", "back view"
test_build_unit_prompt_scout_west
Contains "medieval scout", "facing left"
test_unknown_unit_type_graceful
build_unit_prompt("dragon", "s", "desc") → uses "medieval character sprite" fallback
test_unknown_direction_graceful
build_unit_prompt("archer", "x", "desc") → uses "front view" fallback
test_description_included
User description appears in output
test_transparent_background_always_present
Output contains "isolated on transparent background"
test_crisp_edges_always_present
Output contains "crisp pixel edges"
2.7 Registries (tests/test_registries.py)
Leader Registry
Test
What It Verifies
test_register_leader
Insert → get → fields match
test_register_copies_reference_image
ref_{leader_id}.png exists in reference dir
test_generate_leader_id_deterministic
Same name → same slug, different uuid
test_generate_leader_id_slugging
"Cleopatra VII" → slug contains cleopatra_vii
test_get_nonexistent_returns_none

test_exists_true
After register → exists() = True
test_exists_false
Unknown ID → False
test_list_all_ordering
Newest first
test_record_profile
After record_profile() → profile_image_id set
test_record_action_appends
Two calls → action_image_ids length = 2
test_record_action_preserves_existing
Existing actions retained on append
test_delete_cleans_reference
delete() removes ref_{leader_id}.png
test_delete_returns_false_for_missing
Unknown ID → False
Tile Registries (Structure, Object, Terrain)
Test
What It Verifies
test_structure_register_and_get
Full round-trip all fields
test_structure_list_all
Multiple inserts → all returned
test_structure_delete
Delete → get() returns None
test_object_register_and_get
Full round-trip
test_terrain_register_and_get
Full round-trip
test_generate_structure_id_format
Starts with struct_, contains category slug
test_generate_object_id_format
Starts with object_
test_generate_terrain_id_format
Starts with terrain_
Unit Registry
Test
What It Verifies
test_unit_register_and_get
Full round-trip all 4 directional image IDs
test_unit_list_all
Multiple units returned
test_unit_delete
Delete → get() returns None
test_unit_delete_returns_false
Unknown ID → False
test_generate_unit_id_format
Starts with unit_, contains type, 6-char hex suffix
2.8 Inpainting (tests/test_inpainting.py)
Test
What It Verifies
test_create_mask_dimensions
Output size matches input
test_create_mask_mode
Output is "L" (grayscale)
test_create_mask_white_region
Pixels inside bbox are 255
test_create_mask_black_region
Pixels outside bbox are 0
test_create_mask_point_ordering
point_a > point_b → bbox still correct (min/max)
test_create_mask_blur
blur_radius=3 → edge pixels are between 0 and 255
test_get_inpaint_prompt_known
"water" → "sparkling blue pixel art"
test_get_inpaint_prompt_unknown
"magma" → "pixel art magma, detailed, top-down 2d game asset"
2.9 ComfyUI Workflow Patching (tests/test_comfyui_client.py)
Test
What It Verifies
test_patch_clip_text_encode_positive
Node with title containing "positive" → inputs["text"] set
test_patch_clip_text_encode_negative
Node with title containing "negative" → inputs["text"] set
test_patch_ksampler_seed
inputs["seed"] set
test_patch_empty_latent_image
inputs["width"], inputs["height"] set
test_patch_load_image_uploaded
Node ID in uploaded_filenames → inputs["image"] set
test_patch_load_image_reference
_meta.title contains "reference" + ref_image_filename → inputs["image"] set
test_patch_extra_overrides
Arbitrary node_id → inputs updated
test_patch_random_seed_when_none
seed=None → random seed generated
test_patch_preserves_unrelated_nodes
Non-targeted nodes unchanged
2.10 Generators (tests/test_generators.py)
Test
What It Verifies
test_get_generator_comfyui_mode
mode="comfyui" → returns ComfyUIGenerator
test_get_generator_static_mode
mode="static" → returns StaticTileGenerator
test_get_generator_placeholder_mode
mode="placeholder" → returns _PlaceholderGenerator
test_get_generator_random_mode
mode="static" → falls back to placeholder if no static PNG available
test_get_generator_comfyui_unreachable_raises
No client → RuntimeError
test_static_generator_background_tile
tile_type="water" with water.png → serves it
test_static_generator_background_tile_missing_falls_to_placeholder
Unknown tile type → placeholder returned
test_static_generator_structure_with_subtype
structure_subtype="fortification" → resolves from that subtype
test_static_generator_structure_no_static_falls_to_placeholder
No PNGs → placeholder
test_static_generator_splash_falls_to_placeholder
StaticTileGenerator + SplashRequest → _PlaceholderSplash
test_placeholder_generator_creates_image
Returns a valid PNG filename in AssetStore
test_placeholder_generator_label_present
Image contains family label text
test_placeholder_splash_border_and_name
Splash placeholder has border, character name
test_comfyui_generator_positive_prompt
Prompt built from request
test_comfyui_generator_splash_resize
512×512 splash resized to 256×256
test_comfyui_generator_inpaint_sequential
Multiple inpaints processed in order
test_comfyui_generator_inpaint_no_base_creates_blank
No base_image_id → starts from grey canvas
2.11 Placeholder Tile Engine (tests/test_tile_engine.py)
Test
What It Verifies
test_placeholder_structure_response_fields
Response contains asset_id, url, generation_mode="placeholder", all request fields echoed
test_placeholder_object_response_fields
Same pattern for object
test_placeholder_terrain_response_fields
Same pattern for terrain
test_placeholder_structure_registers_in_db
StructureRegistry.get(asset_id) returns a record
test_placeholder_creates_asset_record
AssetRecord inserted
test_placeholder_image_has_correct_dimensions
512×512
test_placeholder_image_label_readable
Text drawn on image
2.12 Placeholder Unit Engine (tests/test_unit_engine.py)
Test
What It Verifies
test_placeholder_unit_creates_4_images
4 AssetRecords + 4 files in store
test_placeholder_unit_response_directions
UnitDirections with 4 distinct URLs
test_placeholder_unit_color_per_type
Archer → greenish, Warrior → reddish
test_placeholder_unit_registers_in_db
UnitRegistry.get(unit_id) returns record with all 4 image_ids
test_placeholder_unit_fallback_s_reuse
Not applicable for placeholder (always generates all 4)
2.13 Static Unit Engine (tests/test_unit_engine.py)
With a controlled static catalog containing archer_s.png only (no n/e/w):
Test
What It Verifies
test_static_unit_with_all_directions
archer_s.png + archer_n.png + archer_e.png + archer_w.png → 4 distinct image IDs
test_static_unit_s_fallback
Only archer_s.png → n/e/w all reuse the same image_id as s
test_static_unit_no_south_falls_to_placeholder
No sprite for unit_type → placeholder generated
test_static_unit_fallback_optimization
S PNG loaded once, filename reused for fallback directions
2.14 Leader Engine — Static Mode (tests/test_leader_engine.py)
Test
What It Verifies
test_static_splash_generates_and_registers
Returns LeaderResponse with leader_id
test_static_splash_registers_leader
LeaderRegistry.get(leader_id) → not None
test_static_profile_requires_leader_id
Missing → ValueError
test_static_profile_requires_existing_leader
Unknown leader_id → ValueError
test_static_profile_updates_registry
profile_image_id set after _generate_profile
test_static_action_requires_leader_id_and_category_and_description
Missing any → ValueError
test_static_action_appends_to_registry
action_image_ids length increases
test_static_splash_placeholder_image_dimensions
1920×1088
test_static_action_colors_per_category
Different action_category → different bg_color
 
3. Integration Tests
3.1 API Endpoints — Happy Path (tests/test_api.py)
Using httpx.AsyncClient against the FastAPI app with placeholder mode:
Health & Meta
Test
What It Verifies
test_health_returns_200
/health → 200, status: "ok"
test_health_includes_all_modes
Response modes has all 10 families
test_health_includes_unit_mode
modes.unit present
test_health_includes_leader_count
leaders_registered is an int
test_health_includes_unit_count
units_registered is an int
test_modes_returns_all_families
/modes → dict with all 10 families + valid_modes
test_catalog_returns_tile_types_and_structures
/catalog structure correct
test_catalog_includes_unit_info
Currently NOT included — this test documents the gap
Asset Serving
Test
What It Verifies
test_get_asset_valid
/assets/{filename} → 200, image/png
test_get_asset_404
Unknown filename → 404
Legacy /generate Endpoint
Test
What It Verifies
test_generate_background_tile_placeholder
Returns GenerationResponse with url, asset_family, tile_type
test_generate_background_tile_missing_tile_type
Still succeeds (schema doesn't enforce)
test_generate_structure_placeholder
Returns image
test_generate_creates_db_record
AssetRecord exists after generation
/splash Endpoint
Test
What It Verifies
test_splash_placeholder
Returns SplashResponse with url, character_name
test_splash_creates_db_record
AssetRecord with asset_family="splash"
Leader Endpoints
Test
What It Verifies
test_leader_splash_creates_leader
POST /leader with asset_type="splash" → 200, LeaderResponse with leader_id
test_leader_profile_chains
POST splash → POST profile with returned leader_id → 200
test_leader_action_chains
Splash → action → 200
test_leader_profile_missing_leader_id
400
test_leader_get_list
GET /leader → list of LeaderInfo
test_leader_get_single
GET /leader/{id} → 200
test_leader_get_404
Unknown ID → 404
test_leader_delete
DELETE /leader/{id} → 200, subsequent GET → 404
test_leader_delete_404
Unknown ID → 404
Structure Endpoints
Test
What It Verifies
test_structure_generate_placeholder
POST /structure → 200, StructureResponse
test_structure_list
GET /structure → list
test_structure_get_single
GET /structure/{id} → 200
test_structure_get_404
404
test_structure_delete
DELETE → 200, then 404
test_structure_catalog
GET /structure/catalog → enums
Object Endpoints — same pattern as Structure
Terrain Endpoints — same pattern as Structure
Unit Endpoints
Test
What It Verifies
test_unit_generate_placeholder
POST /unit → 200, UnitResponse with 4 directions
test_unit_all_four_direction_urls_accessible
Each direction URL → 200, valid PNG
test_unit_list
GET /unit → list
test_unit_get_single
GET /unit/{id} → 200, 4 directions
test_unit_get_404
Unknown ID → 404
test_unit_delete
DELETE → 200, then 404
test_unit_catalog
GET /unit/catalog → UnitCatalog with types + directions
test_unit_invalid_type
POST with unit_type="dragon" → 400 (if validated) or 422
3.2 End-to-End Pipeline Flows (tests/test_pipelines.py)
Test
What It Verifies
test_leader_full_pipeline
Splash → profile → action → list → delete → 404 — all in sequence
test_structure_full_crud_cycle
Create → get → list → delete → 404
test_unit_static_fallback_chain
With archer_s.png only → all 4 directions served, n/e/w reuse S image
3.3 Error Handling (tests/test_errors.py)
Test
What It Verifies
test_comfyui_unreachable_503
Engine None → 503
test_invalid_json_422
Malformed body → 422
test_global_exception_handler_500
Unexpected error → 500 with "Internal server error"
 
4. Mock-Heavy ComfyUI Integration Tests (tests/test_comfyui_integration.py)
These mock the HTTP and WebSocket layers to test the full ComfyUI client lifecycle without a real server:
Test
What It Verifies
test_upload_image
Mock HTTP POST → returns filename
test_queue_workflow
Mock POST → returns prompt_id
test_queue_workflow_node_errors_raises
Response with node_errors → ValueError
test_wait_via_ws_success
Mock WebSocket messages → returns True
test_wait_via_ws_execution_error
execution_error message → returns False
test_wait_via_ws_falls_back_to_polling
WS fails → polling succeeds
test_wait_via_polling_success
History endpoint returns prompt_id
test_wait_via_polling_timeout
Never appears → False after timeout
test_download_image
Mock GET → returns bytes
test_health_check_ok
/system_stats → 200
test_health_check_fail
Connection error → False
test_cancel_prompt
POST /queue with delete → True
test_generate_full_cycle
Upload → queue → wait → download → PIL Image
test_close_releases_client
close() → _http is None
 
5. Edge Cases & Regression Tests
5.1 Concurrent/Repeated Operations
Test
What It Verifies
test_duplicate_leader_name
Two splashes with same name → different leader_id
test_rapid_unit_generation
5 units generated sequentially → all registered, no collisions
test_registry_list_empty
list_all() on empty table → []
test_delete_then_recreate
Delete → create same type → new ID, no stale data
5.2 Static Catalog Edge Cases
Test
What It Verifies
test_unit_filename_with_underscores
city_settler_s.png → parses as type=city_settler, direction=s (rsplit with 1)
test_structure_subtype_not_in_valid_set
Folder unknown/ under structure/ → ignored
test_non_png_files_ignored
.DS_Store, thumbs.db → ignored
test_empty_subtype_folder
fortification/ with no PNGs → not listed
5.3 Prompt Edge Cases
Test
What It Verifies
test_empty_description_handling
description="" — prompt built without trailing comma issue
test_description_with_special_chars
Quotes, commas, unicode → not broken
test_leader_description_min_length_enforcement
30 chars → ValidationError (min_length=50)
 
6. File & Directory Structure
tests/
├── __init__.py
├── conftest.py                          # All fixtures
├── test_config.py
├── test_models.py                       # GenerationRequest, SplashRequest, etc.
├── test_database.py
├── test_storage.py
├── test_static_catalog.py
├── test_inpainting.py
├── test_comfyui_client.py               # _patch_workflow unit tests
├── test_comfyui_integration.py          # Mocked HTTP/WS integration
├── test_generators.py
├── test_main.py                         # All endpoint integration tests
├── test_doc_code_consistency.py
├── leader/
│   ├── __init__.py
│   ├── test_leader_engine.py            # StaticLeaderEngine
│   ├── test_leader_models.py            # LeaderRequest, LeaderResponse
│   ├── test_leader_prompts.py           # Prompt builders
│   └── test_leader_registry.py          # CRUD + ID generation
├── tile/
│   ├── __init__.py
│   ├── test_tile_engine.py              # Placeholder + Static tile engine
│   ├── test_tile_models.py              # Structure/Object/Terrain request/response
│   ├── test_tile_prompts.py             # Prompt builders
│   └── test_tile_registry.py            # CRUD + ID generation
└── unit/
    ├── __init__.py
    ├── test_unit_engine.py              # Placeholder + StaticUnitEngine
    ├── test_unit_models.py              # UnitRequest, UnitResponse, UnitDirections
    ├── test_unit_prompts.py             # Prompt builders
    └── test_unit_registry.py            # CRUD + ID generation
    ├── sample_workflow.json
    └── static_tiles_tree/               # Controlled directory trees for catalog tests
        ├── background_tile/
        │   ├── water.png
        │   ├── grass_1.png
        │   └── grass_2.png
        ├── structure/
        │   ├── fortification/
        │   │   └── castle.png
        │   └── production/
        │       └── mill.png
        ├── nature_object/
        │   └── tree.png
        └── unit/
            ├── archer_s.png
            ├── archer_n.png
            └── scout_s.png
 
7. Test Configuration (pyproject.toml or pytest.ini)
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-v --cov=src --cov-report=term-missing --cov-report=html"
 
8. Prioritized Implementation Order
Phase
Files
Effort
Rationale
1. Foundation
conftest.py, test_storage.py, test_database.py, test_config.py
Low
No dependencies — pure unit tests, highest confidence-to-effort ratio
2. Models & Validation
test_models.py, test_tile_models.py, test_unit_models.py, test_leader_models.py
Low
Pydantic-only, no IO
3. Prompts
test_tile_prompts.py, test_leader_prompts.py, test_unit_prompts.py
Low
Pure functions, deterministic
4. Inpainting + Workflow Patching
test_inpainting.py, test_comfyui_client.py
Low
Pure functions
5. Static Catalog
test_static_catalog.py
Medium
Requires controlled directory fixtures
6. Registries
test_registries.py
Medium
Requires DB fixtures
7. Engines
test_tile_engine.py, test_leader_engine.py, test_unit_engine.py, test_generators.py
Medium
Requires DB + catalog + store fixtures
8. API Integration
test_api.py, test_pipelines.py, test_errors.py
High
Full app, requires all engines initialized
9. ComfyUI Mock Integration
test_comfyui_integration.py
High
Complex mock setup for HTTP + WebSocket
 
9. Gaps Discovered During Analysis
While analyzing the codebase for test planning, I identified these potential issues worth addressing:
UnitRequest.unit_type has no Pydantic validation — it's a plain str with just a description. A POST /unit with unit_type: "dragon" would pass Pydantic validation and only fail downstream in the prompt builder (which falls back silently). Consider adding a Literal or AfterValidator.
/catalog endpoint missing unit info — The endpoint returns background_tile, structure, nature_object, and character_sprite but has no unit section with available unit types or directions.
/health endpoint: leaders_registered and units_registered exist but no structures_registered — Inconsistency across families.
GenerationRequest.tile_type is Optional — A POST /background_tile without a tile_type would pass validation but produce a prompt with "pixel art grass tile" (hardcoded fallback), which is surprising. Should enforce at the schema or engine level.
UnitRegistry.has_static() always returns True — This method is a stub. It's never called by the engine (which checks the static catalog directly), so it's dead code.
StaticUnitEngine.generate() S-fallback optimization has a subtle bug: When resolve_unit returns the S PNG for a non-S direction, it checks resolved_direction == "s" by parsing the filename. But if a non-S PNG happens to have _s in its filename (e.g., archer_s_variant.png → base="archer_s_variant" → split gives ("archer_s", "variant") → resolved_direction = "variant"), the optimization won't trigger. The path-based check is more reliable since resolve_unit already guarantees it returned the S path.
Would you like me to begin implementing the test suite, or would you prefer to discuss/modify the plan first?
from __future__ import annotations

import logging
import os
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.config import settings, DeploymentMode
from src.database import SessionLocal, AssetRecord, LeaderRecord, verify_db_connectivity, verify_schema_health, reset_database
from src.comfyui_client import close_comfyui_client, get_comfyui_loadbalancer
from src.leader.engine import LeaderEngine, StaticLeaderEngine
from src.leader.models import LeaderRequest, LeaderResponse, LeaderInfo
from src.leader.registry import LeaderRegistry
from src.static_catalog import catalog as static_catalog
from src.storage import store
from src.tile.engine import TileEngine, StaticTileEngine
from src.tile.models import (
    StructureRequest, StructureResponse,
    ObjectRequest, ObjectResponse,
    TerrainRequest, TerrainResponse,
    StructureCatalog, ObjectCatalog, TerrainCatalog,
    StructureCategory, StructureStyle, StructureCondition, StructureScale,
    ObjectCategory, Biome, Season,
    TerrainCategory, TerrainScale, TerrainMaterial,
)
from src.tile.registry import StructureRegistry, ObjectRegistry, TerrainRegistry
from src.tile.background_engine import (
    BackgroundTileEngine, StaticBackgroundTileEngine, BackgroundTileResult,
    GAME_ASSET_SIZE as BG_ASSET_SIZE,
)
from src.tile.background_registry import BackgroundTileRegistry
from src.tile.background_models import (
    BackgroundTileRequest, BackgroundTileResponse, BackgroundTileCatalog,
)
from src.unit.engine import UnitEngine, StaticUnitEngine
from src.unit.models import (
    UnitRequest, UnitResponse, UnitCatalog,
    UnitType,
)
from src.unit.registry import UnitRegistry
from src.prompt_templates import validate_all_templates

# Setup production logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Shared response models
# ---------------------------------------------------------------------------


class DeleteResponse(BaseModel):
    """Standard response for all DELETE endpoints."""
    status: str = "deleted"
    id: str
    asset_type: str


class HealthResponse(BaseModel):
    """GET /health response."""
    status: str
    components: dict[str, str]
    comfyui_nodes: int
    modes: dict[str, str]
    registered: dict[str, int]


class ModesResponse(BaseModel):
    """GET /modes response."""
    modes: dict[str, str]
    valid_modes: list[str]


class CatalogResponse(BaseModel):
    """GET /catalog response — available static asset families and types."""
    background_tile: dict
    structure: dict
    nature_object: dict
    character_sprite: dict
    unit: dict


# Leader engine (initialized in lifespan — comfyui or static mode)
leader_engine: LeaderEngine | StaticLeaderEngine | None = None

# Database schema health flag — set during lifespan startup.
# When False, all asset-persistence endpoints return 503.
_db_schema_ok: bool = True

# Tile engine (initialized in lifespan)
tile_engine: TileEngine | StaticTileEngine | None = None

# Unit engine (initialized in lifespan)
unit_engine: UnitEngine | StaticUnitEngine | None = None

# Background tile engine (initialized in lifespan)
background_tile_engine: BackgroundTileEngine | StaticBackgroundTileEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle hooks."""
    global leader_engine, tile_engine, unit_engine, background_tile_engine

    # --- Production safety checks ---
    if settings.mode == DeploymentMode.PRODUCTION:
        if settings.server.cors_origins == ["*"] or settings.server.cors_origins == ["http://localhost:3000"]:
            logger.critical(
                "PRODUCTION mode but CORS origins are too permissive: %s. "
                "Set SERVER__CORS_ORIGINS to your actual domain(s).",
                settings.server.cors_origins,
            )
        if "sqlite" in str(getattr(settings, "database_url", "") or "").lower():
            logger.info(
                "PRODUCTION mode with SQLite — WAL journal mode is active "
                "for concurrent access safety."
            )

    # --- Startup validation ---
    # Validate prompt templates
    from src.database import BASE_DIR as _project_root

    template_errors = validate_all_templates()
    if template_errors:
        logger.critical(
            "Prompt template validation FAILED — %d error(s). "
            "The service will start but generation may fail.",
            len(template_errors),
        )
        for err in template_errors:
            logger.critical("  • %s", err)
        if settings.mode == DeploymentMode.PRODUCTION:
            raise RuntimeError(
                f"Prompt template validation failed with {len(template_errors)} "
                f"error(s).  Refusing to start in PRODUCTION mode.  Fix the "
                f"templates in config/prompt_templates.json and restart."
            )

    # Verify all workflow JSON files exist (fail fast in production)
    _workflow_files = {
        "txt2img": os.path.join(_project_root, "workflows", "txt2img.json"),
        "background_tile": os.path.join(_project_root, "workflows", "background_tile.json"),
        "leader_splash": os.path.join(_project_root, "workflows", "leader", "leader_splash.json"),
        "leader_profile": os.path.join(_project_root, "workflows", "leader", "leader_profile.json"),
        "leader_action": os.path.join(_project_root, "workflows", "leader", "leader_action.json"),
    }
    _missing_wf = [name for name, path in _workflow_files.items() if not os.path.isfile(path)]
    if _missing_wf:
        msg = f"Missing workflow JSON files: {', '.join(_missing_wf)}"
        if settings.mode == DeploymentMode.PRODUCTION:
            logger.critical(msg + " — refusing to start in PRODUCTION mode.")
            raise RuntimeError(msg)
        else:
            logger.warning(msg + " — generation will fail for these families.")

    # Verify each workflow JSON contains required node class_types
    _workflow_required_nodes: dict[str, list[str]] = {
        "txt2img": [
            "CLIPTextEncode", "SamplerCustomAdvanced", "EmptyLatentImage",
            "BasicScheduler", "FluxGuidance", "SaveImage",
            "ImageResizeKJv2", "Image Remove Background (rembg)",
        ],
        "background_tile": [
            "CLIPTextEncode", "SamplerCustomAdvanced", "EmptyLatentImage",
            "BasicScheduler", "FluxGuidance", "SaveImage", "ImageResizeKJv2",
        ],
        "leader_splash": [
            "CLIPTextEncode", "SamplerCustomAdvanced", "EmptyLatentImage",
            "BasicScheduler", "FluxGuidance", "SaveImage",
        ],
        "leader_profile": [
            "CLIPTextEncode", "SamplerCustomAdvanced",
            "BasicScheduler", "FluxGuidance", "SaveImage", "LoadImage",
            "ImageResizeKJv2", "VAEEncode",
        ],
        "leader_action": [
            "CLIPTextEncode", "SamplerCustomAdvanced",
            "BasicScheduler", "FluxGuidance", "SaveImage", "LoadImage",
            "ImageResizeKJv2", "ImageStitch", "VAEEncode",
        ],
    }
    _missing_nodes: list[str] = []
    for wf_name, wf_path in _workflow_files.items():
        required = _workflow_required_nodes.get(wf_name, [])
        if not required:
            continue
        try:
            with open(wf_path, "r") as fh:
                import json as _json  # local import — not needed elsewhere at module level
                wf = _json.load(fh)
            present = {node.get("class_type", "") for node in wf.values()}
            missing = [n for n in required if n not in present]
            if missing:
                _missing_nodes.append(f"{wf_name}: {', '.join(missing)}")
        except Exception as exc:
            _missing_nodes.append(f"{wf_name}: failed to parse JSON ({exc})")

    if _missing_nodes:
        msg = (
            f"Workflow JSONs missing required node types: {'; '.join(_missing_nodes)}"
        )
        if settings.mode == DeploymentMode.PRODUCTION:
            logger.critical(msg + " — refusing to start in PRODUCTION mode.")
            raise RuntimeError(msg)
        else:
            logger.warning(msg + " — generation may fail for these workflows.")

    # Verify leader_action.json LoadImage nodes use sentinel values (not stale hardcoded filenames)
    try:
        import json as _json  # local import — needed for this validation block
        la_path = _workflow_files["leader_action"]
        if os.path.isfile(la_path):
            with open(la_path, "r") as fh:
                la_wf = _json.load(fh)
            la_load_nodes = {
                nid: node for nid, node in la_wf.items()
                if node.get("class_type") == "LoadImage"
            }
            for nid in ("35", "36"):
                node = la_load_nodes.get(nid)
                if node is None:
                    logger.warning(
                        "leader_action.json: node %s (LoadImage) is missing; "
                        "multi-leader action generation will fail.", nid
                    )
                else:
                    image_val = node.get("inputs", {}).get("image", "")
                    if image_val not in ("__LEADER_REF_1__", "__LEADER_REF_2__"):
                        logger.warning(
                            "leader_action.json: node %s has hardcoded filename '%s' "
                            "instead of sentinel '__LEADER_REF_%s__'. "
                            "Engine may silently use stale/wrong reference images.",
                            nid, image_val, nid,
                        )
    except Exception as exc:
        logger.warning("leader_action.json: failed to validate LoadImage nodes: %s", exc)

    # --- Workflow ↔ Prompt-template LoRA pairing validation ---
    # Templates containing <tdp> trigger a top-down LoRA.  The workflow used
    # for those families MUST include a LoraLoaderModelOnly node; conversely,
    # families whose templates do NOT use <tdp> MUST use a workflow without one.
    # This is a quality guard, not a hard startup failure — mismatches produce
    # degraded output but do not crash the service.
    _template_to_workflow: dict[str, str] = {
        "structure":       "txt2img",
        "object":          "txt2img",
        "terrain":         "txt2img",
        "unit":            "txt2img",
        "background_tile": "background_tile",
        "leader_splash":   "leader_splash",
        "leader_profile":  "leader_profile",
        "leader_action":   "leader_action",
    }
    try:
        _tpl_path = os.path.join(_project_root, "config", "prompt_templates.json")
        with open(_tpl_path, "r") as fh:
            _tpl_data = _json.load(fh)
        _templates = _tpl_data.get("templates", {})

        for _family, _wf_name in _template_to_workflow.items():
            _tpl_text = _templates.get(_family, {}).get("template", "")
            _tpl_has_tdp = "<tdp>" in _tpl_text

            _wf_path = _workflow_files.get(_wf_name)
            if not _wf_path or not os.path.isfile(_wf_path):
                continue  # already reported as missing above

            with open(_wf_path, "r") as fh:
                _wf_data = _json.load(fh)
            _wf_has_lora = any(
                node.get("class_type") == "LoraLoaderModelOnly"
                for node in _wf_data.values()
            )

            if _tpl_has_tdp and not _wf_has_lora:
                logger.critical(
                    "Workflow–template mismatch: '%s' template contains <tdp> "
                    "LoRA trigger token, but workflow '%s.json' has no "
                    "LoraLoaderModelOnly node.  Output quality will be degraded.",
                    _family, _wf_name,
                )
            elif not _tpl_has_tdp and _wf_has_lora:
                logger.critical(
                    "Workflow–template mismatch: '%s' template does NOT contain "
                    "<tdp> LoRA trigger token, but workflow '%s.json' HAS a "
                    "LoraLoaderModelOnly node.  Output quality will be degraded.",
                    _family, _wf_name,
                )
    except Exception as _exc:
        logger.warning(
            "Failed to validate workflow–template LoRA pairing: %s", _exc
        )

    # --- Database initialisation ---
    global _db_schema_ok

    # --- Run database migrations (Alembic) ---
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_command
    from src.database import DATABASE_URL, BASE_DIR

    alembic_cfg = AlembicConfig(os.path.join(BASE_DIR, "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    try:
        alembic_command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully")
    except Exception as exc:
        logger.critical("Database migration failed: %s", exc)
        _db_schema_ok = False
        raise

    # Optional full reset (escape hatch when schema has diverged)
    # Refuse to reset in production — a misconfigured .env could destroy
    # all data on the next deployment.
    if os.environ.get("DATABASE_RESET", "").lower() in ("1", "true", "yes"):
        if settings.mode == DeploymentMode.PRODUCTION:
            logger.critical(
                "DATABASE_RESET=true is NOT allowed in PRODUCTION mode. "
                "Remove DATABASE_RESET from the environment and restart."
            )
        else:
            logger.info("DATABASE_RESET=true — dropping and recreating all tables.")
            reset_database()

    # Verify database connectivity
    db_ok = verify_db_connectivity()
    if not db_ok:
        logger.critical(
            "Database connectivity check FAILED — asset persistence will not work."
        )
        _db_schema_ok = False
    else:
        # Verify that the on-disk schema matches the current model definitions
        schema_ok, schema_mismatches = verify_schema_health()
        _db_schema_ok = schema_ok

    # --- Orphaned asset cleanup (non-blocking, logged) ---
    # Clean up leader reference images for leaders no longer in the database
    if _db_schema_ok:
        _leader_ref_dir = os.path.join(BASE_DIR, settings.paths.leader_reference_dir)
        if os.path.isdir(_leader_ref_dir):
            _ref_cleaned = 0
            try:
                with SessionLocal() as _db:
                    _existing_ids = {
                        row[0] for row in _db.query(LeaderRecord.leader_id).all()
                    }
                    for _entry in os.listdir(_leader_ref_dir):
                        if not _entry.startswith("ref_leader_") or not _entry.endswith(".png"):
                            continue
                        # Extract leader_id: ref_leader_<id>.png → <id>
                        _lid = _entry[len("ref_leader_"):-len(".png")]
                        if _lid not in _existing_ids:
                            _path = os.path.join(_leader_ref_dir, _entry)
                            try:
                                os.unlink(_path)
                                logger.info("Cleaned up orphaned leader reference: %s", _entry)
                                _ref_cleaned += 1
                            except OSError as _exc:
                                logger.warning(
                                    "Failed to delete orphaned reference %s: %s", _entry, _exc
                                )
                if _ref_cleaned > 0:
                    logger.info("Cleaned up %d orphaned leader reference file(s)", _ref_cleaned)
            except Exception as _exc:
                logger.warning("Leader reference cleanup skipped — %s", _exc)

        # Clean up generated_assets/ PNGs with no matching AssetRecord
        try:
            with SessionLocal() as _db:
                from src.storage import cleanup_orphaned_assets
                _asset_cleaned = cleanup_orphaned_assets(_db)
                if _asset_cleaned > 0:
                    logger.info("Cleaned up %d orphaned generated asset(s)", _asset_cleaned)
        except Exception as _exc:
            logger.warning("Generated asset cleanup skipped — %s", _exc)

    # --- Startup advisory: splash_assets/ is empty ---
    _splash_dir = os.path.join(BASE_DIR, settings.paths.splash_dir)
    if os.path.isdir(_splash_dir) and not any(
        f.lower().endswith(".png") for f in os.listdir(_splash_dir)
    ):
        logger.warning(
            "splash_assets/ directory is empty — no static splash assets available. "
            "Populate it with PNG files to enable static splash serving, or use "
            "comfyui/placeholder mode for leader generation."
        )

    # --- Engine initialization ---
    # For single-node configs this is equivalent to a plain ComfyUIClient.
    lb = get_comfyui_loadbalancer()
    lb_reachable = await lb.health_check() if lb else False

    leader_mode = settings.get_mode("leader")

    if leader_mode in ("static", "placeholder"):
        leader_engine = StaticLeaderEngine()
        logger.info("Leader engine initialized (%s mode)", leader_mode)
    elif lb is not None and lb_reachable:
        leader_engine = LeaderEngine(lb)
        logger.info("Leader engine initialized (comfyui mode, %d nodes)", len(lb._nodes))
    else:
        logger.warning(
            "ComfyUI unreachable -- leader endpoints will return 503"
        )

    # Initialize tile engine — check all three tile families independently.
    # If any family needs comfyui mode and the load-balancer is reachable,
    # use TileEngine; if all are static/placeholder, use StaticTileEngine.
    tile_families = ["structure", "object", "terrain"]
    tile_modes = {f: settings.get_mode(f) for f in tile_families}
    any_tile_comfyui = any(m == "comfyui" for m in tile_modes.values())
    all_tile_static = all(m in ("static", "placeholder") for m in tile_modes.values())

    if all_tile_static:
        tile_engine = StaticTileEngine()
        logger.info("Tile engine initialized (static/placeholder mode) — modes: %s", tile_modes)
    elif lb is not None and any_tile_comfyui:
        tile_engine = TileEngine(lb)
        logger.info("Tile engine initialized (comfyui mode, %d nodes) — modes: %s", len(lb._nodes), tile_modes)
    elif lb is not None and lb_reachable:
        # LB is reachable but no tile family explicitly set to comfyui
        tile_engine = TileEngine(lb)
        logger.info("Tile engine initialized (comfyui mode, default) — modes: %s", tile_modes)
    else:
        logger.warning("Tile engine: ComfyUI unreachable, tile endpoints will return 503")

    # Initialize unit engine
    unit_mode = settings.get_mode("unit")

    if unit_mode in ("static", "placeholder"):
        unit_engine = StaticUnitEngine()
        logger.info("Unit engine initialized (%s mode)", unit_mode)
    elif lb is not None:
        unit_engine = UnitEngine(lb)
        logger.info("Unit engine initialized (comfyui mode)")
    else:
        logger.warning("Unit engine: ComfyUI unreachable, unit endpoints will return 503")

    # Initialize background tile engine
    bg_tile_mode = settings.get_mode("background_tile")

    if bg_tile_mode in ("static", "placeholder"):
        background_tile_engine = StaticBackgroundTileEngine()
        logger.info("Background tile engine initialized (%s mode)", bg_tile_mode)
    elif lb is not None:
        background_tile_engine = BackgroundTileEngine(lb)
        logger.info("Background tile engine initialized (comfyui mode)")
    else:
        logger.warning("Background tile engine: ComfyUI unreachable, background_tile endpoints will return 503")

    logger.info(
        "Application started.  Modes: %s",
        {f: settings.get_mode(f) for f in [
            "structure", "object", "terrain", "background_tile", "leader", "unit",
        ]},
    )
    logger.info(
        "Static catalog: %d tile types, %d structure subtypes, %d unit types",
        len(static_catalog.list_tile_types()),
        len(static_catalog.list_structure_subtypes()),
        len(static_catalog.list_unit_types()),
    )
    yield
    await close_comfyui_client()
    logger.info("Application shutting down.")


app = FastAPI(
    title="Medieval Pixel Art Image Service",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
#  Request ID middleware — injects a correlation ID for production tracing
# ---------------------------------------------------------------------------

from fastapi import Request as FastAPIRequest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as StarletteJSONResponse


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique request ID into every request for log correlation.

    Reads the ``X-Request-ID`` header if the client provides one;
    otherwise generates a UUID4.  The ID is stored in
    ``request.state.request_id`` and echoed in the ``X-Request-ID``
    response header.
    """

    async def dispatch(self, request: FastAPIRequest, call_next):
        import uuid as _uuid
        request_id = request.headers.get("X-Request-ID", str(_uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)


# ---------------------------------------------------------------------------
#  API key authentication middleware (optional — disabled when api_key is "")
# ---------------------------------------------------------------------------

class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate the ``X-API-Key`` header against the configured key.

    When ``server.api_key`` is empty (the default), authentication is
    **disabled** and all requests pass through.  Set a non-empty key to
    require every request to include ``X-API-Key: <your-key>``.

    The ``/health`` endpoint is always exempt from authentication.
    """

    async def dispatch(self, request: FastAPIRequest, call_next):
        api_key = settings.server.api_key
        # Skip auth if no key configured, or if path is /health or /assets
        if not api_key or request.url.path == "/health" or request.url.path.startswith("/assets/"):
            return await call_next(request)
        if request.headers.get("X-API-Key") != api_key:
            return StarletteJSONResponse(
                {"detail": "Invalid or missing API key"},
                status_code=401,
            )
        return await call_next(request)


app.add_middleware(APIKeyMiddleware)

# CORS middleware — configure origins via config.yaml → server.cors_origins
# or env var SERVER__CORS_ORIGINS (JSON array).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.server.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)

# Request body size limit to prevent DOS


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds the configured maximum."""

    async def dispatch(self, request: FastAPIRequest, call_next):
        max_bytes = settings.server.max_request_body_mb * 1024 * 1024
        content_length = request.headers.get("content-length")
        # Only enforce Content-Length on methods that typically carry a body
        if request.method in ("POST", "PUT", "PATCH"):
            if content_length is None:
                return StarletteJSONResponse(
                    {"detail": "Content-Length header is required"},
                    status_code=411,
                )
            if int(content_length) > max_bytes:
                return StarletteJSONResponse(
                    {"detail": f"Request body exceeds {settings.server.max_request_body_mb} MB limit"},
                    status_code=413,
                )
        return await call_next(request)


app.add_middleware(RequestSizeLimitMiddleware)


# ---------------------------------------------------------------------------
#  Rate limiting (token-bucket, no external dependencies)
# ---------------------------------------------------------------------------

import time as _time_module
import threading as _threading

class _TokenBucket:
    """Thread-safe token bucket for rate limiting."""

    def __init__(self, rate: float, burst: int) -> None:
        self._rate = rate          # tokens per second
        self._burst = burst        # max tokens
        self._tokens = float(burst)
        self._last_refill = _time_module.monotonic()
        self._lock = _threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate-limited."""
        with self._lock:
            now = _time_module.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_refill = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Global token-bucket rate limiter for POST and GET endpoints.

    Checks ``settings.rate_limit.enabled`` at request time so tests can
    disable rate limiting by mutating the settings singleton.
    """

    def __init__(self, app, post_rps: float, get_rps: float, burst: int):
        super().__init__(app)
        self._post_bucket = _TokenBucket(post_rps, burst)
        self._get_bucket = _TokenBucket(get_rps, burst * 10)

    async def dispatch(self, request: FastAPIRequest, call_next):
        # Check enabled at request time so tests can toggle it
        if not settings.rate_limit.enabled:
            return await call_next(request)
        bucket = self._post_bucket if request.method in ("POST", "PUT", "PATCH") else self._get_bucket
        if not bucket.consume():
            return StarletteJSONResponse(
                {"detail": "Rate limit exceeded. Slow down."},
                status_code=429,
            )
        return await call_next(request)


app.add_middleware(
    RateLimitMiddleware,
    post_rps=settings.rate_limit.post_rps,
    get_rps=settings.rate_limit.get_rps,
    burst=settings.rate_limit.burst_size,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        content={"detail": "Internal server error"},
        status_code=500,
    )


def _require_db() -> None:
    """Raise 503 if the database schema is out of sync with the models.

    Call at the top of any endpoint that reads or writes the database.
    """
    if not _db_schema_ok:
        raise HTTPException(
            status_code=503,
            detail="Database schema mismatch — restart with DATABASE_RESET=true or delete tilemap.db",
        )


def _paginated_response(items: list, *, total_count: int, limit: int, offset: int) -> JSONResponse:
    """Wrap a list with pagination headers (additive — does not change JSON body).

    Adds ``X-Total-Count`` and ``X-Has-More`` response headers so clients
    can discover pagination state without changing the response shape.
    """
    has_more = (offset + limit) < total_count
    return JSONResponse(
        content=jsonable_encoder(items),
        headers={
            "X-Total-Count": str(total_count),
            "X-Has-More": "true" if has_more else "false",
        },
    )


from fastapi.encoders import jsonable_encoder


# ---------------------------------------------------------------------------
#  Assets
# ---------------------------------------------------------------------------


@app.get("/assets/{filename}")
async def get_asset(filename: str):
    data = store.get_image_bytes(filename)
    if not data:
        raise HTTPException(status_code=404, detail="Asset not found")
    return Response(content=data, media_type="image/png")


# ---------------------------------------------------------------------------
#  Catalog
# ---------------------------------------------------------------------------


@app.get("/catalog", response_model=CatalogResponse)
async def get_catalog():
    """Return available tile types, structure subtypes, and unit types from static_tiles/."""
    return {
        "background_tile": {
            "tile_types": static_catalog.list_tile_types(),
        },
        "structure": {
            "subtypes": static_catalog.list_structure_subtypes(),
        },
        "nature_object": {
            "available": static_catalog.has_any("nature_object"),
        },
        "character_sprite": {
            "available": static_catalog.has_any("character_sprite"),
        },
        "unit": {
            "unit_types": static_catalog.list_unit_types(),
        },
    }


# ---------------------------------------------------------------------------
#  Health
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Report per-component service status — always returns 200.

    Returns component-level health so monitoring tools can set alert
    thresholds without the endpoint itself being taken out of rotation.
    """
    # Database status (don't use _require_db() — that would 503 the endpoint)
    db_status = "ok" if _db_schema_ok else "unhealthy"

    # ComfyUI status
    lb = get_comfyui_loadbalancer()
    comfyui_ok = False
    comfyui_status = "unreachable"
    if lb is not None:
        try:
            comfyui_ok = await lb.health_check()
            comfyui_status = "ok" if comfyui_ok else "unhealthy"
        except Exception:
            comfyui_status = "unreachable"

    # Template status
    template_errors = validate_all_templates()
    template_status = "ok" if not template_errors else "error"

    return {
        "status": "ok" if (db_status == "ok" and comfyui_ok) else "degraded",
        "components": {
            "database": db_status,
            "comfyui": comfyui_status,
            "templates": template_status,
        },
        "comfyui_nodes": len(lb._nodes) if lb else 0,
        "modes": {
            "structure": settings.get_mode("structure"),
            "object": settings.get_mode("object"),
            "terrain": settings.get_mode("terrain"),
            "background_tile": settings.get_mode("background_tile"),
            "leader": settings.get_mode("leader"),
            "unit": settings.get_mode("unit"),
        },
        "registered": {
            "leaders": len(LeaderRegistry.list_all()),
            "structures": len(StructureRegistry.list_all()),
            "objects": len(ObjectRegistry.list_all()),
            "terrains": len(TerrainRegistry.list_all()),
            "units": len(UnitRegistry.list_all()),
        },
    }


# ---------------------------------------------------------------------------
#  Modes
# ---------------------------------------------------------------------------


@app.get("/modes", response_model=ModesResponse)
async def get_modes():
    """Return the active generation mode for every asset family.

    Clients can use this to discover whether the server is running in
    'comfyui', 'static', or 'placeholder' mode without reading config.
    """
    families = [
        "structure", "object", "terrain", "background_tile", "leader", "unit",
    ]
    return {
        "modes": {f: settings.get_mode(f) for f in families},
        "valid_modes": ["comfyui", "static", "placeholder"],
    }


# ---------------------------------------------------------------------------
#  Leader pipeline
# ---------------------------------------------------------------------------


@app.post("/leader", response_model=LeaderResponse)
async def generate_leader(request: LeaderRequest):
    """Generate a leader asset: splash, profile, or action scene.

    Pipeline order:
      1. POST /leader {asset_type: "splash", ...}     → returns leader_id
      2. POST /leader {asset_type: "profile", leader_id: "...", ...}
      3. POST /leader {asset_type: "action", leader_id: "...", action_category: "...", ...}

    Multi-leader action (txt2img — no reference image):
      POST /leader {asset_type: "action", leader_ids: ["id1","id2"], action_category: "...", ...}

    When leader_ids is provided for action, the engine generates a single
    composite scene depicting all listed leaders via a combined prompt.
    """
    logger.info("Received leader request for type: %s", request.asset_type)
    _require_db()

    if leader_engine is None:
        raise HTTPException(503, "Leader generation not available (ComfyUI unreachable)")

    try:
        # --- Multi-leader action scene ---
        if request.asset_type == "action" and request.leader_ids is not None:
            if len(request.leader_ids) < 1:
                raise HTTPException(
                    status_code=400,
                    detail="leader_ids must contain at least one leader_id for multi-leader action scenes.",
                )
            if not request.action_category:
                raise HTTPException(
                    status_code=400,
                    detail="action_category is required for action assets.",
                )
            if not request.action_description:
                raise HTTPException(
                    status_code=400,
                    detail="action_description is required for action assets.",
                )
            return await leader_engine.generate_multi_action(request, request.leader_ids)

        # --- Single-leader action ---
        response: LeaderResponse = await leader_engine.generate(request)
        logger.info(
            "Leader %s generated: %s (%.1fs)",
            getattr(response, "leader_name", "unknown"),
            response.asset_type,
            (response.generation_time_ms or 0) / 1000,
        )
        return response

    except ValueError as e:
        logger.warning("Leader validation error: %s", e)
        raise HTTPException(400, detail=str(e))
    except HTTPException:
        raise  # re-raise HTTP exceptions unchanged
    except RuntimeError as e:
        logger.error("Leader runtime error: %s", e)
        raise HTTPException(503, detail="Generation failed. Please try again.")
    except Exception as e:
        logger.error("Leader generation error: %s", e)
        raise HTTPException(500, detail="Internal server error")


@app.get("/leader", responses={200: {"description": "List of registered leaders"}})
async def list_leaders(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10000),
):
    """Return all registered leaders. Parallels GET /catalog."""
    _require_db()
    records = LeaderRegistry.list_all(limit=limit, offset=offset)
    total = LeaderRegistry.count_all()
    items = [
        LeaderInfo(
            leader_id=r.leader_id,
            leader_name=r.leader_name,
            archetype=r.archetype,
            culture=r.culture,
            splash_url=f"/assets/{r.splash_image_id}" if r.splash_image_id else None,
            profile_url=f"/assets/{r.profile_image_id}" if r.profile_image_id else None,
            action_urls=[f"/assets/{aid}" for aid in (r.action_image_ids or [])],
            splash_seed=r.splash_seed,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in records
    ]
    return _paginated_response(items, total_count=total, limit=limit, offset=offset)


@app.get("/leader/{leader_id}", response_model=LeaderInfo)
async def get_leader(leader_id: str):
    """Get a specific leader's info + asset URLs."""
    _require_db()
    leader = LeaderRegistry.get(leader_id)
    if not leader:
        raise HTTPException(404, f"Leader '{leader_id}' not found")
    return LeaderInfo(
        leader_id=leader.leader_id,
        leader_name=leader.leader_name,
        archetype=leader.archetype,
        culture=leader.culture,
        splash_url=f"/assets/{leader.splash_image_id}" if leader.splash_image_id else None,
        profile_url=f"/assets/{leader.profile_image_id}" if leader.profile_image_id else None,
        action_urls=[f"/assets/{aid}" for aid in (leader.action_image_ids or [])],
        splash_seed=leader.splash_seed,
        created_at=leader.created_at.isoformat() if leader.created_at else None,
    )


@app.delete("/leader/{leader_id}", response_model=DeleteResponse)
async def delete_leader(leader_id: str):
    """Remove a leader and all their generated assets from disk."""
    _require_db()
    deleted = LeaderRegistry.delete(leader_id)
    if not deleted:
        raise HTTPException(404, f"Leader '{leader_id}' not found")
    return DeleteResponse(status="deleted", id=leader_id, asset_type="leader")


# ---------------------------------------------------------------------------
#  Tile pipelines — Structure, Object, Terrain
# ---------------------------------------------------------------------------


@app.post("/structure", response_model=StructureResponse)
async def generate_structure(request: StructureRequest):
    """Generate a structure tile (fortification, production, housing, sacred)."""
    logger.info("Received structure request: category=%s style=%s", request.category, request.style)
    _require_db()

    if tile_engine is None:
        raise HTTPException(503, "Tile generation not available (ComfyUI unreachable)")

    try:
        response: StructureResponse = await tile_engine.generate_structure(request)
        logger.info("Structure generated: %s (%.1fs)", response.asset_id,
                     (response.generation_time_ms or 0) / 1000)
        return response
    except ValueError as e:
        logger.warning("Structure validation error: %s", e)
        raise HTTPException(400, detail=str(e))
    except RuntimeError as e:
        logger.error("Structure runtime error: %s", e)
        raise HTTPException(503, detail="Generation failed. Please try again.")
    except Exception as e:
        logger.error("Structure generation error: %s", e)
        raise HTTPException(500, detail="Internal server error")


@app.get("/structure", responses={200: {"description": "List of generated structures"}})
async def list_structures(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10000),
):
    """Return all generated structures."""
    _require_db()
    records = StructureRegistry.list_all(limit=limit, offset=offset)
    total = StructureRegistry.count_all()
    items = [
        StructureResponse(
            url=f"/assets/{r.image_id}",
            asset_id=r.structure_id,
            category=r.category,
            style=r.style,
            condition=r.condition,
            scale=r.scale,
            description=r.description,
            seed=r.seed,
            generation_mode=r.generation_mode or "unknown",
            prompt_used=r.prompt_used,
        )
        for r in records
    ]
    return _paginated_response(items, total_count=total, limit=limit, offset=offset)


@app.get("/structure/catalog", response_model=StructureCatalog)
async def structure_catalog():
    """Return available enum values for structure generation."""
    return StructureCatalog(
        categories=sorted(e.value for e in StructureCategory),
        styles=sorted(e.value for e in StructureStyle),
        conditions=sorted(e.value for e in StructureCondition),
        scales=sorted(e.value for e in StructureScale),
    )


@app.get("/structure/{structure_id}", response_model=StructureResponse)
async def get_structure(structure_id: str):
    """Get a specific structure by ID."""
    _require_db()
    record = StructureRegistry.get(structure_id)
    if not record:
        raise HTTPException(404, f"Structure '{structure_id}' not found")
    return StructureResponse(
        url=f"/assets/{record.image_id}",
        asset_id=record.structure_id,
        category=record.category,
        style=record.style,
        condition=record.condition,
        scale=record.scale,
        description=record.description,
        seed=record.seed,
        generation_mode=record.generation_mode or "unknown",
        prompt_used=record.prompt_used,
    )


@app.delete("/structure/{structure_id}", response_model=DeleteResponse)
async def delete_structure(structure_id: str):
    """Remove a structure record and its generated asset from disk."""
    _require_db()
    deleted = StructureRegistry.delete(structure_id)
    if not deleted:
        raise HTTPException(404, f"Structure '{structure_id}' not found")
    return DeleteResponse(status="deleted", id=structure_id, asset_type="structure")


@app.post("/object", response_model=ObjectResponse)
async def generate_object(request: ObjectRequest):
    """Generate an object tile (vegetation, geological, rural/urban props, debris)."""
    logger.info("Received object request: category=%s biome=%s", request.category, request.biome)
    _require_db()

    if tile_engine is None:
        raise HTTPException(503, "Tile generation not available (ComfyUI unreachable)")

    try:
        response: ObjectResponse = await tile_engine.generate_object(request)
        logger.info("Object generated: %s (%.1fs)", response.asset_id,
                     (response.generation_time_ms or 0) / 1000)
        return response
    except ValueError as e:
        logger.warning("Object validation error: %s", e)
        raise HTTPException(400, detail=str(e))
    except RuntimeError as e:
        logger.error("Object runtime error: %s", e)
        raise HTTPException(503, detail="Generation failed. Please try again.")
    except Exception as e:
        logger.error("Object generation error: %s", e)
        raise HTTPException(500, detail="Internal server error")


@app.get("/object", responses={200: {"description": "List of generated objects"}})
async def list_objects(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10000),
):
    """Return all generated objects."""
    _require_db()
    records = ObjectRegistry.list_all(limit=limit, offset=offset)
    total = ObjectRegistry.count_all()
    items = [
        ObjectResponse(
            url=f"/assets/{r.image_id}",
            asset_id=r.object_id,
            category=r.category,
            biome=r.biome,
            season=r.season,
            description=r.description,
            seed=r.seed,
            generation_mode=r.generation_mode or "unknown",
            prompt_used=r.prompt_used,
        )
        for r in records
    ]
    return _paginated_response(items, total_count=total, limit=limit, offset=offset)


@app.get("/object/catalog", response_model=ObjectCatalog)
async def object_catalog():
    """Return available enum values for object generation."""
    return ObjectCatalog(
        categories=sorted(e.value for e in ObjectCategory),
        biomes=sorted(e.value for e in Biome),
        seasons=sorted(e.value for e in Season),
    )


@app.get("/object/{object_id}", response_model=ObjectResponse)
async def get_object(object_id: str):
    """Get a specific object by ID."""
    _require_db()
    record = ObjectRegistry.get(object_id)
    if not record:
        raise HTTPException(404, f"Object '{object_id}' not found")
    return ObjectResponse(
        url=f"/assets/{record.image_id}",
        asset_id=record.object_id,
        category=record.category,
        biome=record.biome,
        season=record.season,
        description=record.description,
        seed=record.seed,
        generation_mode=record.generation_mode or "unknown",
        prompt_used=record.prompt_used,
    )


@app.delete("/object/{object_id}", response_model=DeleteResponse)
async def delete_object(object_id: str):
    """Remove an object record and its generated asset from disk."""
    _require_db()
    deleted = ObjectRegistry.delete(object_id)
    if not deleted:
        raise HTTPException(404, f"Object '{object_id}' not found")
    return DeleteResponse(status="deleted", id=object_id, asset_type="object")


@app.post("/terrain", response_model=TerrainResponse)
async def generate_terrain(request: TerrainRequest):
    """Generate a terrain tile (hill, slope, cliff, ridge, depression)."""
    logger.info("Received terrain request: category=%s material=%s", request.category, request.material)
    _require_db()

    if tile_engine is None:
        raise HTTPException(503, "Tile generation not available (ComfyUI unreachable)")

    try:
        response: TerrainResponse = await tile_engine.generate_terrain(request)
        logger.info("Terrain generated: %s (%.1fs)", response.asset_id,
                     (response.generation_time_ms or 0) / 1000)
        return response
    except ValueError as e:
        logger.warning("Terrain validation error: %s", e)
        raise HTTPException(400, detail=str(e))
    except RuntimeError as e:
        logger.error("Terrain runtime error: %s", e)
        raise HTTPException(503, detail="Generation failed. Please try again.")
    except Exception as e:
        logger.error("Terrain generation error: %s", e)
        raise HTTPException(500, detail="Internal server error")


@app.get("/terrain", responses={200: {"description": "List of generated terrain tiles"}})
async def list_terrains(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10000),
):
    """Return all generated terrains."""
    _require_db()
    records = TerrainRegistry.list_all(limit=limit, offset=offset)
    total = TerrainRegistry.count_all()
    items = [
        TerrainResponse(
            url=f"/assets/{r.image_id}",
            asset_id=r.terrain_id,
            category=r.category,
            scale=r.scale,
            material=r.material,
            description=r.description,
            seed=r.seed,
            generation_mode=r.generation_mode or "unknown",
            prompt_used=r.prompt_used,
        )
        for r in records
    ]
    return _paginated_response(items, total_count=total, limit=limit, offset=offset)


@app.get("/terrain/catalog", response_model=TerrainCatalog)
async def terrain_catalog():
    """Return available enum values for terrain generation."""
    return TerrainCatalog(
        categories=sorted(e.value for e in TerrainCategory),
        scales=sorted(e.value for e in TerrainScale),
        materials=sorted(e.value for e in TerrainMaterial),
    )


@app.get("/terrain/{terrain_id}", response_model=TerrainResponse)
async def get_terrain(terrain_id: str):
    """Get a specific terrain by ID."""
    _require_db()
    record = TerrainRegistry.get(terrain_id)
    if not record:
        raise HTTPException(404, f"Terrain '{terrain_id}' not found")
    return TerrainResponse(
        url=f"/assets/{record.image_id}",
        asset_id=record.terrain_id,
        category=record.category,
        scale=record.scale,
        material=record.material,
        description=record.description,
        seed=record.seed,
        generation_mode=record.generation_mode or "unknown",
        prompt_used=record.prompt_used,
    )


@app.delete("/terrain/{terrain_id}", response_model=DeleteResponse)
async def delete_terrain(terrain_id: str):
    """Remove a terrain record and its generated asset from disk."""
    _require_db()
    deleted = TerrainRegistry.delete(terrain_id)
    if not deleted:
        raise HTTPException(404, f"Terrain '{terrain_id}' not found")
    return DeleteResponse(status="deleted", id=terrain_id, asset_type="terrain")


@app.post("/unit", response_model=UnitResponse)
async def generate_unit(request: UnitRequest):
    """Generate a single south-facing unit sprite (front view).

    Returns a UnitResponse with the sprite URL.  The south-facing
    (front view) sprite is the canonical game-facing direction.
    """
    logger.info("Received unit request: type=%s", request.unit_type)
    _require_db()

    if unit_engine is None:
        raise HTTPException(503, "Unit generation not available (ComfyUI unreachable)")

    try:
        response: UnitResponse = await unit_engine.generate(request)
        logger.info(
            "Unit %s generated: %s (%.1fs)",
            response.unit_type,
            response.unit_id,
            (response.generation_time_ms or 0) / 1000,
        )
        return response

    except ValueError as e:
        logger.warning("Unit validation error: %s", e)
        raise HTTPException(400, detail=str(e))
    except RuntimeError as e:
        logger.error("Unit runtime error: %s", e)
        raise HTTPException(503, detail="Generation failed. Please try again.")
    except Exception as e:
        logger.error("Unit generation error: %s", e)
        raise HTTPException(500, detail="Internal server error")


@app.get("/unit", responses={200: {"description": "List of generated unit sprites"}})
async def list_units(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10000),
):
    """Return all generated units."""
    _require_db()
    records = UnitRegistry.list_all(limit=limit, offset=offset)
    total = UnitRegistry.count_all()
    items = [
        UnitResponse(
            url=f"/assets/{r.image_id}",
            unit_id=r.unit_id,
            unit_type=r.unit_type,
            description=r.description or "",
            seed=r.seed,
            generation_mode=r.generation_mode or "unknown",
            prompt_used=r.prompt_used,
        )
        for r in records
    ]
    return _paginated_response(items, total_count=total, limit=limit, offset=offset)


@app.get("/unit/catalog", response_model=UnitCatalog)
async def unit_catalog():
    """Return available unit types."""
    return UnitCatalog(
        unit_types=sorted(e.value for e in UnitType),
    )


@app.get("/unit/{unit_id}", response_model=UnitResponse)
async def get_unit(unit_id: str):
    """Get a specific unit by ID."""
    _require_db()
    record = UnitRegistry.get(unit_id)
    if not record:
        raise HTTPException(404, f"Unit '{unit_id}' not found")
    return UnitResponse(
        url=f"/assets/{record.image_id}",
        unit_id=record.unit_id,
        unit_type=record.unit_type,
        description=record.description or "",
        seed=record.seed,
        generation_mode=record.generation_mode or "unknown",
        prompt_used=record.prompt_used,
    )


@app.delete("/unit/{unit_id}", response_model=DeleteResponse)
async def delete_unit(unit_id: str):
    """Remove a unit record and its generated asset from disk."""
    _require_db()
    deleted = UnitRegistry.delete(unit_id)
    if not deleted:
        raise HTTPException(404, f"Unit '{unit_id}' not found")
    return DeleteResponse(status="deleted", id=unit_id, asset_type="unit")


# ---------------------------------------------------------------------------
#  Background tile pipeline
# ---------------------------------------------------------------------------


@app.post("/background_tile", response_model=BackgroundTileResponse)
async def generate_background_tile(request: BackgroundTileRequest):
    """Generate a seamless repeating background tile texture.

    Supported tile types: water, grass, sand, stone, dirt.
    Returns a 128×128 seamless PNG suitable for tiling on a game map.
    """
    logger.info("Received background_tile request: type=%s", request.tile_type)
    _require_db()

    if background_tile_engine is None:
        raise HTTPException(503, "Background tile generation not available (ComfyUI unreachable)")

    try:
        t0 = time.time()
        result: BackgroundTileResult = await background_tile_engine.generate(
            request.tile_type, request.seed
        )

        elapsed = result.elapsed_ms or int((time.time() - t0) * 1000)
        logger.info("Background tile '%s' generated in %dms → %s",
                     request.tile_type, elapsed, result.filename)

        return BackgroundTileResponse(
            url=f"/assets/{result.filename}",
            background_tile_id=result.bg_tile_id,
            tile_type=request.tile_type,
            seed=result.seed,
            generation_mode=result.generation_mode,
            prompt_used=result.prompt_used,
            resolution=f"{BG_ASSET_SIZE}x{BG_ASSET_SIZE}",
            generation_time_ms=elapsed,
        )

    except ValueError as e:
        logger.warning("Background tile validation error: %s", e)
        raise HTTPException(400, detail=str(e))
    except RuntimeError as e:
        logger.error("Background tile runtime error: %s", e)
        raise HTTPException(503, detail="Generation failed. Please try again.")
    except Exception as e:
        logger.error("Background tile generation error: %s", e)
        raise HTTPException(500, detail="Internal server error")


@app.get("/background_tile", responses={200: {"description": "List of generated background tiles"}})
async def list_background_tiles(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10000),
):
    """Return all generated background tiles (paginated)."""
    _require_db()
    records = BackgroundTileRegistry.list_all(limit=limit, offset=offset)
    total = BackgroundTileRegistry.count_all()

    # Batch-fetch generation_mode from AssetRecord (avoid N+1 queries)
    image_ids = [r.image_id for r in records]
    asset_mode_map: dict[str, str] = {}
    if image_ids:
        with SessionLocal() as db:
            assets = db.query(AssetRecord).filter(AssetRecord.id.in_(image_ids)).all()
            asset_mode_map = {a.id: (a.generation_mode or "unknown") for a in assets}

    results = [
        BackgroundTileResponse(
            url=f"/assets/{r.image_id}",
            background_tile_id=r.background_tile_id,
            tile_type=r.tile_type,
            seed=r.seed,
            generation_mode=asset_mode_map.get(r.image_id, "unknown"),
        )
        for r in records
    ]
    return _paginated_response(results, total_count=total, limit=limit, offset=offset)


@app.get("/background_tile/catalog", response_model=BackgroundTileCatalog)
async def background_tile_catalog():
    """Return available background tile types."""
    return BackgroundTileCatalog(
        tile_types=sorted(static_catalog.list_tile_types()),
    )


@app.get("/background_tile/{background_tile_id}", response_model=BackgroundTileResponse)
async def get_background_tile(background_tile_id: str):
    """Get a specific background tile by ID."""
    _require_db()
    record = BackgroundTileRegistry.get(background_tile_id)
    if not record:
        raise HTTPException(404, f"Background tile '{background_tile_id}' not found")
    # Get generation_mode from AssetRecord (single query, fine for get-by-ID)
    generation_mode = "unknown"
    with SessionLocal() as db:
        asset = db.query(AssetRecord).filter(AssetRecord.id == record.image_id).first()
        if asset and asset.generation_mode:
            generation_mode = asset.generation_mode
    return BackgroundTileResponse(
        url=f"/assets/{record.image_id}",
        background_tile_id=record.background_tile_id,
        tile_type=record.tile_type,
        seed=record.seed,
        generation_mode=generation_mode,
    )


@app.delete("/background_tile/{background_tile_id}", response_model=DeleteResponse)
async def delete_background_tile(background_tile_id: str):
    """Remove a background tile record and its generated asset from disk."""
    _require_db()
    deleted = BackgroundTileRegistry.delete(background_tile_id)
    if not deleted:
        raise HTTPException(404, f"Background tile '{background_tile_id}' not found")
    return DeleteResponse(status="deleted", id=background_tile_id, asset_type="background_tile")

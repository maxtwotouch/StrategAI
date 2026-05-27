import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import SessionLocal, AssetRecord
from .generators import close_comfyui_client, get_generator, _get_comfyui_client
from .leader_engine import LeaderEngine, StaticLeaderEngine
from .leader_models import LeaderRequest, LeaderResponse, LeaderInfo
from .leader_registry import LeaderRegistry
from .models import GenerationRequest, GenerationResponse, SplashRequest, SplashResponse
from .static_catalog import catalog as static_catalog
from .storage import store

# Setup production logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Leader engine (initialized in lifespan — comfyui or static mode)
leader_engine: LeaderEngine | StaticLeaderEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle hooks."""
    global leader_engine

    leader_mode = settings.get_mode("leader")

    if leader_mode in ("static", "placeholder"):
        leader_engine = StaticLeaderEngine()
        logger.info("Leader engine initialized (%s mode)", leader_mode)
    else:
        client = _get_comfyui_client()
        if client is not None:
            reachable = await client.health_check()
            if reachable:
                leader_engine = LeaderEngine(client)
                logger.info("Leader engine initialized (comfyui mode)")
            else:
                logger.warning(
                    "ComfyUI server unreachable at %s -- leader endpoints will return 503",
                    client.base_url,
                )

    logger.info(
        "Application started.  Modes: %s",
        {f: settings.get_mode(f) for f in [
            "structure", "nature_object", "background_tile",
            "character_sprite", "story", "splash", "leader",
        ]},
    )
    logger.info(
        "Static catalog: %d tile types, %d structure subtypes",
        len(static_catalog.list_tile_types()),
        len(static_catalog.list_structure_subtypes()),
    )
    yield
    await close_comfyui_client()
    logger.info("Application shutting down.")


app = FastAPI(
    title="Medieval Pixel Art Image Service",
    lifespan=lifespan,
)

# CORS middleware for production cross-origin access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        content={"detail": f"Internal server error: {str(exc)}"},
        status_code=500,
    )


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
#  Generate
# ---------------------------------------------------------------------------


@app.post("/generate", response_model=GenerationResponse)
async def generate_image(request: GenerationRequest):
    logger.info("Received generation request for family: %s", request.asset_family)
    try:
        # Resolve generation mode (for logging + DB)
        mode = settings.get_mode(request.asset_family)

        # Run generation directly (async -- no thread-pool needed)
        generator = get_generator(request.asset_family, request)
        filename: str = await generator.generate(request)

        # Persist to database
        with SessionLocal() as db:
            record = AssetRecord(
                id=filename,
                asset_family=request.asset_family,
                base_image_id=request.base_image_id,
                inpaints=[patch.model_dump() for patch in request.inpaints] if request.inpaints else [],
                tile_type=request.tile_type,
                structure_subtype=request.structure_subtype,
                generation_mode=mode,
            )
            db.add(record)
            db.commit()

        url = f"/assets/{filename}"
        logger.info("Successfully generated asset at %s (mode=%s)", url, mode)
        return GenerationResponse(
            url=url,
            asset_family=request.asset_family,
            tile_type=request.tile_type,
            generation_mode=mode,
        )
    except ValueError as e:
        logger.warning("Validation error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error("Runtime error generating asset: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Error generating asset: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
#  Splash
# ---------------------------------------------------------------------------


@app.post("/splash", response_model=SplashResponse)
async def generate_splash(request: SplashRequest):
    """Generate a splash art (leader profile portrait)."""
    logger.info("Received splash request for character: %s", request.character_name)
    try:
        mode = settings.get_mode("splash")
        generator = get_generator("splash", request)
        filename: str = await generator.generate(request)

        # Persist to database
        with SessionLocal() as db:
            record = AssetRecord(
                id=filename,
                asset_family="splash",
                base_image_id=None,
                inpaints=[],
                character_name=request.character_name,
                generation_mode=mode,
            )
            db.add(record)
            db.commit()

        url = f"/assets/{filename}"
        logger.info("Successfully generated splash art at %s (mode=%s)", url, mode)
        return SplashResponse(
            url=url,
            character_name=request.character_name,
        )
    except Exception as e:
        logger.error("Error generating splash art: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
#  Catalog
# ---------------------------------------------------------------------------


@app.get("/catalog")
async def get_catalog():
    """Return available tile types and structure subtypes from static_tiles/."""
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
    }


# ---------------------------------------------------------------------------
#  Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check():
    """Report service status including ComfyUI connectivity."""
    client = _get_comfyui_client()
    comfyui_ok = (client is not None) and await client.health_check() if client else False
    return {
        "status": "ok",
        "comfyui_connected": comfyui_ok,
        "modes": {
            "background_tile": settings.get_mode("background_tile"),
            "structure": settings.get_mode("structure"),
            "nature_object": settings.get_mode("nature_object"),
            "character_sprite": settings.get_mode("character_sprite"),
            "story": settings.get_mode("story"),
            "splash": settings.get_mode("splash"),
            "leader": settings.get_mode("leader"),
        },
        "leaders_registered": len(LeaderRegistry.list_all()),
    }


# ---------------------------------------------------------------------------
#  Modes
# ---------------------------------------------------------------------------


@app.get("/modes")
async def get_modes():
    """Return the active generation mode for every asset family.

    Clients can use this to discover whether the server is running in
    'comfyui', 'static', or 'placeholder' mode without reading config.
    """
    families = [
        "background_tile", "structure", "nature_object",
        "character_sprite", "story", "splash", "leader",
    ]
    return {
        "modes": {f: settings.get_mode(f) for f in families},
        "valid_modes": ["comfyui", "static", "placeholder", "random"],
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
    """
    logger.info("Received leader request for type: %s", request.asset_type)

    if leader_engine is None:
        raise HTTPException(503, "Leader generation not available (ComfyUI unreachable)")

    try:
        response: LeaderResponse = await leader_engine.generate(request)
        logger.info(
            "Leader %s generated: %s (%.1fs)",
            response.leader_name,
            response.asset_type,
            (response.generation_time_ms or 0) / 1000,
        )
        return response

    except ValueError as e:
        logger.warning("Leader validation error: %s", e)
        raise HTTPException(400, detail=str(e))
    except RuntimeError as e:
        logger.error("Leader runtime error: %s", e)
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        logger.error("Leader generation error: %s", e)
        raise HTTPException(500, detail=str(e))


@app.get("/leader", response_model=list[LeaderInfo])
async def list_leaders():
    """Return all registered leaders. Parallels GET /catalog."""
    records = LeaderRegistry.list_all()
    return [
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


@app.get("/leader/{leader_id}", response_model=LeaderInfo)
async def get_leader(leader_id: str):
    """Get a specific leader's info + asset URLs."""
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


@app.delete("/leader/{leader_id}")
async def delete_leader(leader_id: str):
    """Remove a leader and their reference image. Generated assets remain on disk."""
    deleted = LeaderRegistry.delete(leader_id)
    if not deleted:
        raise HTTPException(404, f"Leader '{leader_id}' not found")
    return {"status": "deleted", "leader_id": leader_id}

import logging
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import SessionLocal, AssetRecord
from .generators import get_generator
from .models import GenerationRequest, GenerationResponse, SplashRequest, SplashResponse
from .static_catalog import catalog as static_catalog
from .storage import store

# Setup production logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Thread pool for blocking ComfyUI calls (generation is synchronous/blocking)
_executor = ThreadPoolExecutor(max_workers=4)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle hooks."""
    logger.info(
        "Application started.  Modes: %s",
        {f: settings.get_mode(f) for f in [
            "structure", "nature_object", "background_tile",
            "character_sprite", "story", "splash",
        ]},
    )
    logger.info("Static catalog: %d tile types, %d structure subtypes",
                len(static_catalog.list_tile_types()),
                len(static_catalog.list_structure_subtypes()))
    yield
    _executor.shutdown(wait=True)
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

        # Run blocking generation in a thread
        generator = get_generator(request.asset_family, request)
        loop = __import__("asyncio").get_event_loop()
        filename: str = await loop.run_in_executor(_executor, generator.generate, request)

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
        loop = __import__("asyncio").get_event_loop()
        filename: str = await loop.run_in_executor(_executor, generator.generate, request)

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
def health_check():
    from .generators import _get_comfyui_client
    client = _get_comfyui_client()
    return {
        "status": "ok",
        "comfyui_connected": client is not None,
        "modes": {
            "background_tile": settings.get_mode("background_tile"),
            "structure": settings.get_mode("structure"),
            "nature_object": settings.get_mode("nature_object"),
            "character_sprite": settings.get_mode("character_sprite"),
            "story": settings.get_mode("story"),
            "splash": settings.get_mode("splash"),
        },
    }

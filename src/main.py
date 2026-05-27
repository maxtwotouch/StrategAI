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
from .tile_engine import TileEngine, StaticTileEngine
from .tile_models import (
    StructureRequest, StructureResponse,
    ObjectRequest, ObjectResponse,
    TerrainRequest, TerrainResponse,
    StructureCatalog, ObjectCatalog, TerrainCatalog,
    StructureCategory, StructureStyle, StructureCondition, StructureScale,
    ObjectCategory, Biome, Season,
    TerrainCategory, TerrainScale, TerrainMaterial,
)
from .tile_registry import StructureRegistry, ObjectRegistry, TerrainRegistry
from .unit_engine import UnitEngine, StaticUnitEngine
from .unit_models import (
    UnitRequest, UnitResponse, UnitCatalog,
    UnitType, Direction,
)
from .unit_registry import UnitRegistry

# Setup production logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Leader engine (initialized in lifespan — comfyui or static mode)
leader_engine: LeaderEngine | StaticLeaderEngine | None = None

# Tile engine (initialized in lifespan)
tile_engine: TileEngine | StaticTileEngine | None = None

# Unit engine (initialized in lifespan)
unit_engine: UnitEngine | StaticUnitEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle hooks."""
    global leader_engine, tile_engine, unit_engine

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

    # Initialize tile engine based on structure/object/terrain mode
    # (all three share the same client; mode determines instance type)
    tile_families = ["structure", "object", "terrain"]
    tile_mode = settings.get_mode("structure")  # representative — all three share config

    if tile_mode in ("static", "placeholder"):
        tile_engine = StaticTileEngine()
        logger.info("Tile engine initialized (%s mode)", tile_mode)
    else:
        client = _get_comfyui_client()
        if client is not None:
            tile_engine = TileEngine(client)
            logger.info("Tile engine initialized (comfyui mode)")
        else:
            logger.warning("Tile engine: ComfyUI unreachable, tile endpoints will return 503")

    # Initialize unit engine
    unit_mode = settings.get_mode("unit")

    if unit_mode in ("static", "placeholder"):
        unit_engine = StaticUnitEngine()
        logger.info("Unit engine initialized (%s mode)", unit_mode)
    else:
        client = _get_comfyui_client()
        if client is not None:
            unit_engine = UnitEngine(client)
            logger.info("Unit engine initialized (comfyui mode)")
        else:
            logger.warning("Unit engine: ComfyUI unreachable, unit endpoints will return 503")

    logger.info(
        "Application started.  Modes: %s",
        {f: settings.get_mode(f) for f in [
            "structure", "nature_object", "background_tile",
            "character_sprite", "story", "splash", "leader", "unit",
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
            "object": settings.get_mode("object"),
            "terrain": settings.get_mode("terrain"),
            "nature_object": settings.get_mode("nature_object"),
            "character_sprite": settings.get_mode("character_sprite"),
            "story": settings.get_mode("story"),
            "splash": settings.get_mode("splash"),
            "leader": settings.get_mode("leader"),
            "unit": settings.get_mode("unit"),
        },
        "leaders_registered": len(LeaderRegistry.list_all()),
        "units_registered": len(UnitRegistry.list_all()),
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
        "background_tile", "structure", "object", "terrain",
        "nature_object", "character_sprite", "story", "splash", "leader", "unit",
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


# ---------------------------------------------------------------------------
#  Tile pipelines — Structure, Object, Terrain
# ---------------------------------------------------------------------------


@app.post("/structure", response_model=StructureResponse)
async def generate_structure(request: StructureRequest):
    """Generate a structure tile (fortification, production, housing, sacred)."""
    logger.info("Received structure request: category=%s style=%s", request.category, request.style)

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
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        logger.error("Structure generation error: %s", e)
        raise HTTPException(500, detail=str(e))


@app.get("/structure", response_model=list[StructureResponse])
async def list_structures():
    """Return all generated structures."""
    records = StructureRegistry.list_all()
    return [
        StructureResponse(
            url=f"/assets/{r.image_id}",
            asset_id=r.structure_id,
            category=r.category,
            style=r.style,
            condition=r.condition,
            scale=r.scale,
            seed=r.seed,
            generation_mode=r.generation_mode or "unknown",
            prompt_used=r.prompt_used,
        )
        for r in records
    ]


@app.get("/structure/{structure_id}", response_model=StructureResponse)
async def get_structure(structure_id: str):
    """Get a specific structure by ID."""
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
        seed=record.seed,
        generation_mode=record.generation_mode or "unknown",
        prompt_used=record.prompt_used,
    )


@app.delete("/structure/{structure_id}")
async def delete_structure(structure_id: str):
    """Remove a structure record. Generated asset remains on disk."""
    deleted = StructureRegistry.delete(structure_id)
    if not deleted:
        raise HTTPException(404, f"Structure '{structure_id}' not found")
    return {"status": "deleted", "structure_id": structure_id}


@app.get("/structure/catalog", response_model=StructureCatalog)
async def structure_catalog():
    """Return available enum values for structure generation."""
    return StructureCatalog(
        categories=sorted(StructureCategory.ALL),
        styles=sorted(StructureStyle.ALL),
        conditions=sorted(StructureCondition.ALL),
        scales=sorted(StructureScale.ALL),
    )


# ---------------------------------------------------------------------------


@app.post("/object", response_model=ObjectResponse)
async def generate_object(request: ObjectRequest):
    """Generate an object tile (vegetation, geological, rural/urban props, debris)."""
    logger.info("Received object request: category=%s biome=%s", request.category, request.biome)

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
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        logger.error("Object generation error: %s", e)
        raise HTTPException(500, detail=str(e))


@app.get("/object", response_model=list[ObjectResponse])
async def list_objects():
    """Return all generated objects."""
    records = ObjectRegistry.list_all()
    return [
        ObjectResponse(
            url=f"/assets/{r.image_id}",
            asset_id=r.object_id,
            category=r.category,
            biome=r.biome,
            season=r.season,
            seed=r.seed,
            generation_mode=r.generation_mode or "unknown",
            prompt_used=r.prompt_used,
        )
        for r in records
    ]


@app.get("/object/{object_id}", response_model=ObjectResponse)
async def get_object(object_id: str):
    """Get a specific object by ID."""
    record = ObjectRegistry.get(object_id)
    if not record:
        raise HTTPException(404, f"Object '{object_id}' not found")
    return ObjectResponse(
        url=f"/assets/{record.image_id}",
        asset_id=record.object_id,
        category=record.category,
        biome=record.biome,
        season=record.season,
        seed=record.seed,
        generation_mode=record.generation_mode or "unknown",
        prompt_used=record.prompt_used,
    )


@app.delete("/object/{object_id}")
async def delete_object(object_id: str):
    """Remove an object record. Generated asset remains on disk."""
    deleted = ObjectRegistry.delete(object_id)
    if not deleted:
        raise HTTPException(404, f"Object '{object_id}' not found")
    return {"status": "deleted", "object_id": object_id}


@app.get("/object/catalog", response_model=ObjectCatalog)
async def object_catalog():
    """Return available enum values for object generation."""
    return ObjectCatalog(
        categories=sorted(ObjectCategory.ALL),
        biomes=sorted(Biome.ALL),
        seasons=sorted(Season.ALL),
    )


# ---------------------------------------------------------------------------


@app.post("/terrain", response_model=TerrainResponse)
async def generate_terrain(request: TerrainRequest):
    """Generate a terrain tile (hill, slope, cliff, ridge, depression)."""
    logger.info("Received terrain request: category=%s material=%s", request.category, request.material)

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
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        logger.error("Terrain generation error: %s", e)
        raise HTTPException(500, detail=str(e))


@app.get("/terrain", response_model=list[TerrainResponse])
async def list_terrains():
    """Return all generated terrains."""
    records = TerrainRegistry.list_all()
    return [
        TerrainResponse(
            url=f"/assets/{r.image_id}",
            asset_id=r.terrain_id,
            category=r.category,
            scale=r.scale,
            material=r.material,
            seed=r.seed,
            generation_mode=r.generation_mode or "unknown",
            prompt_used=r.prompt_used,
        )
        for r in records
    ]


@app.get("/terrain/{terrain_id}", response_model=TerrainResponse)
async def get_terrain(terrain_id: str):
    """Get a specific terrain by ID."""
    record = TerrainRegistry.get(terrain_id)
    if not record:
        raise HTTPException(404, f"Terrain '{terrain_id}' not found")
    return TerrainResponse(
        url=f"/assets/{record.image_id}",
        asset_id=record.terrain_id,
        category=record.category,
        scale=record.scale,
        material=record.material,
        seed=record.seed,
        generation_mode=record.generation_mode or "unknown",
        prompt_used=record.prompt_used,
    )


@app.delete("/terrain/{terrain_id}")
async def delete_terrain(terrain_id: str):
    """Remove a terrain record. Generated asset remains on disk."""
    deleted = TerrainRegistry.delete(terrain_id)
    if not deleted:
        raise HTTPException(404, f"Terrain '{terrain_id}' not found")
    return {"status": "deleted", "terrain_id": terrain_id}


@app.get("/terrain/catalog", response_model=TerrainCatalog)
async def terrain_catalog():
    """Return available enum values for terrain generation."""
    return TerrainCatalog(
        categories=sorted(TerrainCategory.ALL),
        scales=sorted(TerrainScale.ALL),
        materials=sorted(TerrainMaterial.ALL),
    )

# ---------------------------------------------------------------------------
#  Unit pipeline  — Archer, Scout, Settler, Warrior
# ---------------------------------------------------------------------------


@app.post("/unit", response_model=UnitResponse)
async def generate_unit(request: UnitRequest):
    """Generate unit sprites for all 4 cardinal directions.

    Returns a UnitResponse with ``directions`` mapping ``s``/``n``/``e``/``w``
    to asset URLs.  The south-facing sprite is canonical.
    """
    logger.info("Received unit request: type=%s", request.unit_type)

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
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        logger.error("Unit generation error: %s", e)
        raise HTTPException(500, detail=str(e))


@app.get("/unit", response_model=list[UnitResponse])
async def list_units():
    """Return all generated units."""
    records = UnitRegistry.list_all()
    return [
        UnitResponse(
            url=f"/assets/{r.image_id_s}",
            unit_id=r.unit_id,
            unit_type=r.unit_type,
            directions=UnitDirections(
                s=f"/assets/{r.image_id_s}",
                n=f"/assets/{r.image_id_n}",
                e=f"/assets/{r.image_id_e}",
                w=f"/assets/{r.image_id_w}",
            ),
            seed=r.seed,
            generation_mode=r.generation_mode or "unknown",
            prompt_used=r.prompt_used,
        )
        for r in records
    ]


@app.get("/unit/{unit_id}", response_model=UnitResponse)
async def get_unit(unit_id: str):
    """Get a specific unit by ID."""
    record = UnitRegistry.get(unit_id)
    if not record:
        raise HTTPException(404, f"Unit '{unit_id}' not found")
    return UnitResponse(
        url=f"/assets/{record.image_id_s}",
        unit_id=record.unit_id,
        unit_type=record.unit_type,
        directions=UnitDirections(
            s=f"/assets/{record.image_id_s}",
            n=f"/assets/{record.image_id_n}",
            e=f"/assets/{record.image_id_e}",
            w=f"/assets/{record.image_id_w}",
        ),
        seed=record.seed,
        generation_mode=record.generation_mode or "unknown",
        prompt_used=record.prompt_used,
    )


@app.delete("/unit/{unit_id}")
async def delete_unit(unit_id: str):
    """Remove a unit record. Generated assets remain on disk."""
    deleted = UnitRegistry.delete(unit_id)
    if not deleted:
        raise HTTPException(404, f"Unit '{unit_id}' not found")
    return {"status": "deleted", "unit_id": unit_id}


@app.get("/unit/catalog", response_model=UnitCatalog)
async def unit_catalog():
    """Return available unit types and directions."""
    return UnitCatalog(
        unit_types=sorted(UnitType.ALL),
        directions=sorted(Direction.ALL),
    )

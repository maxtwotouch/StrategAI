"""Tile generation orchestrator.

Routes structure/object/terrain requests through the appropriate generator
based on the per-family generation mode (comfyui, static, placeholder, random).

Unlike the leader pipeline, tiles are single-shot txt2img — no multi-stage
dependencies, no reference images, no seed anchoring.
"""

import logging
import random
import time
import uuid
import os
from typing import Union

from PIL import Image, ImageDraw, ImageFont

from .comfyui_client import ComfyUIClient
from .config import settings
from .database import SessionLocal, AssetRecord
from .tile_models import (
    StructureRequest, StructureResponse,
    ObjectRequest, ObjectResponse,
    TerrainRequest, TerrainResponse,
)
from .tile_prompts import (
    build_structure_prompt,
    build_object_prompt,
    build_terrain_prompt,
)
from .tile_registry import (
    generate_structure_id, generate_object_id, generate_terrain_id,
    StructureRegistry, ObjectRegistry, TerrainRegistry,
)
from .static_catalog import catalog as static_catalog
from .storage import store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

_TILE_WIDTH, _TILE_HEIGHT = 512, 512

# Colour palette for placeholder tiles
_PLACEHOLDER_COLORS = {
    "structure": (139, 90, 43, 255),
    "object": (34, 139, 34, 255),
    "terrain": (100, 100, 80, 255),
}

_FONT: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None


def _get_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    global _FONT
    if _FONT is None:
        try:
            _FONT = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14
            )
        except (OSError, IOError):
            _FONT = ImageFont.load_default()
    return _FONT


# ===========================================================================
#  Tile Engine  (comfyui mode)
# ===========================================================================

class TileEngine:
    """Orchestrates generation for structure, object, and terrain assets."""

    def __init__(self, client: ComfyUIClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    #  Public entry points
    # ------------------------------------------------------------------

    async def generate_structure(self, req: StructureRequest) -> StructureResponse:
        return await self._generate(
            req=req,
            build_prompt=build_structure_prompt,
            generate_id=generate_structure_id,
            registry_register=StructureRegistry.register,
            response_cls=StructureResponse,
            family="structure",
        )

    async def generate_object(self, req: ObjectRequest) -> ObjectResponse:
        return await self._generate(
            req=req,
            build_prompt=build_object_prompt,
            generate_id=generate_object_id,
            registry_register=ObjectRegistry.register,
            response_cls=ObjectResponse,
            family="object",
        )

    async def generate_terrain(self, req: TerrainRequest) -> TerrainResponse:
        return await self._generate(
            req=req,
            build_prompt=build_terrain_prompt,
            generate_id=generate_terrain_id,
            registry_register=TerrainRegistry.register,
            response_cls=TerrainResponse,
            family="terrain",
        )

    # ------------------------------------------------------------------
    #  Shared generation core
    # ------------------------------------------------------------------

    async def _generate(
        self,
        req,
        build_prompt,
        generate_id,
        registry_register,
        response_cls,
        family: str,
    ):
        """Single-shot txt2img pipeline common to all three tile families."""
        # 1. Build prompt
        prompt = build_prompt(req)

        # 2. Generate ID
        asset_id = generate_id(req.category)

        # 3. Seed
        seed = req.seed or random.randint(10**14, 10**15 - 1)

        # 4. Run ComfyUI
        start = time.time()
        img = await self._client.generate(
            os.path.join(settings.workflow_dir, "txt2img.json"),
            positive_prompt=prompt,
            width=_TILE_WIDTH,
            height=_TILE_HEIGHT,
            seed=seed,
        )

        # 5. Save to AssetStore
        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, img)

        # 6. Persist AssetRecord
        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family=family,
                generation_mode="comfyui",
            ))
            db.commit()

        # 7. Register in tile-specific table
        _register_tile(
            registry_register,
            asset_id=asset_id,
            req=req,
            image_id=filename,
            seed=seed,
            prompt_used=prompt,
            generation_mode="comfyui",
        )

        elapsed = int((time.time() - start) * 1000)

        # 8. Build response dynamically
        kwargs: dict = {
            "url": f"/assets/{filename}",
            "asset_id": asset_id,
            "seed": seed,
            "generation_mode": "comfyui",
            "prompt_used": prompt,
            "resolution": f"{img.width}x{img.height}",
            "generation_time_ms": elapsed,
        }
        # Inject request-specific fields (skip seed — already set above)
        for field_name in type(req).model_fields:
            if field_name == "seed":
                continue
            kwargs[field_name] = getattr(req, field_name)

        return response_cls(**kwargs)


# ===========================================================================
#  Static Tile Engine  (serves from static_tiles/)
# ===========================================================================

class StaticTileEngine:
    """Serves pre-made PNGs from static_tiles/ for tile pipelines."""

    async def generate_structure(self, req: StructureRequest) -> StructureResponse:
        prompt = build_structure_prompt(req)
        asset_id = generate_structure_id(req.category)

        path = static_catalog.resolve_random("structure", req.category)
        if path:
            filename = _load_and_save(path)
            _register_tile(
                StructureRegistry.register,
                asset_id=asset_id,
                req=req,
                image_id=filename,
                seed=req.seed or 0,
                prompt_used=prompt,
                generation_mode="static",
            )
            return _build_response(StructureResponse, req, asset_id, filename,
                                   prompt, "static")

        # Fall through to placeholder
        return await _PlaceholderTileEngine().generate_structure(req)

    async def generate_object(self, req: ObjectRequest) -> ObjectResponse:
        prompt = build_object_prompt(req)
        asset_id = generate_object_id(req.category)

        path = static_catalog.resolve_random("nature_object")
        if path:
            filename = _load_and_save(path)
            _register_tile(
                ObjectRegistry.register,
                asset_id=asset_id,
                req=req,
                image_id=filename,
                seed=req.seed or 0,
                prompt_used=prompt,
                generation_mode="static",
            )
            return _build_response(ObjectResponse, req, asset_id, filename,
                                   prompt, "static")

        return await _PlaceholderTileEngine().generate_object(req)

    async def generate_terrain(self, req: TerrainRequest) -> TerrainResponse:
        prompt = build_terrain_prompt(req)
        asset_id = generate_terrain_id(req.category)

        # Terrain has no static folder yet — go straight to placeholder
        return await _PlaceholderTileEngine().generate_terrain(req)


# ===========================================================================
#  Placeholder Tile Engine  (procedural coloured rectangle)
# ===========================================================================

class _PlaceholderTileEngine:
    """Produces a labelled coloured rectangle for each tile family."""

    async def generate_structure(self, req: StructureRequest) -> StructureResponse:
        return await self._generate_placeholder(
            req=req,
            build_prompt=build_structure_prompt,
            generate_id=generate_structure_id,
            registry_register=StructureRegistry.register,
            response_cls=StructureResponse,
            family="structure",
            label=f"STRUCTURE\n{req.category}",
        )

    async def generate_object(self, req: ObjectRequest) -> ObjectResponse:
        return await self._generate_placeholder(
            req=req,
            build_prompt=build_object_prompt,
            generate_id=generate_object_id,
            registry_register=ObjectRegistry.register,
            response_cls=ObjectResponse,
            family="object",
            label=f"OBJECT\n{req.category}",
        )

    async def generate_terrain(self, req: TerrainRequest) -> TerrainResponse:
        return await self._generate_placeholder(
            req=req,
            build_prompt=build_terrain_prompt,
            generate_id=generate_terrain_id,
            registry_register=TerrainRegistry.register,
            response_cls=TerrainResponse,
            family="terrain",
            label=f"TERRAIN\n{req.category}",
        )

    async def _generate_placeholder(
        self, req, build_prompt, generate_id, registry_register,
        response_cls, family: str, label: str,
    ):
        prompt = build_prompt(req)
        asset_id = generate_id(req.category)
        seed = req.seed or random.randint(10**14, 10**15 - 1)

        start = time.time()

        color = _PLACEHOLDER_COLORS.get(family, (128, 128, 128, 255))
        img = Image.new("RGBA", (_TILE_WIDTH, _TILE_HEIGHT), color)
        draw = ImageDraw.Draw(img)
        font = _get_font()

        # Border
        draw.rectangle([4, 4, _TILE_WIDTH - 5, _TILE_HEIGHT - 5],
                       outline=(255, 255, 255, 255), width=2)

        # Label (supports embedded newlines)
        for i, line in enumerate(label.split("\n")):
            text_w = draw.textlength(line, font=font)
            draw.text(
                ((_TILE_WIDTH - text_w) // 2, (_TILE_HEIGHT // 2) + (i * 20) - 10),
                line, fill=(255, 255, 255, 255), font=font,
            )

        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, img)

        _register_tile(
            registry_register,
            asset_id=asset_id, req=req,
            image_id=filename, seed=seed,
            prompt_used=prompt,
            generation_mode="placeholder",
        )

        elapsed = int((time.time() - start) * 1000)
        return _build_response(response_cls, req, asset_id, filename,
                               prompt, "placeholder", elapsed, f"{img.width}x{img.height}")


# ===========================================================================
#  Helpers
# ===========================================================================

def _register_tile(registry_register, asset_id: str, req, image_id: str,
                   seed: int, prompt_used: str, generation_mode: str) -> None:
    """Call the appropriate Registry.register() with the right kwargs."""
    # Extract relevant fields from the request based on what register() expects
    kwargs: dict = {
        "image_id": image_id,
        "seed": seed,
        "prompt_used": prompt_used,
        "generation_mode": generation_mode,
    }
    for field_name in type(req).model_fields:
        if field_name == "seed":
            continue  # seed already set above, don't overwrite with req.seed (may be None)
        if hasattr(req, field_name):
            kwargs[field_name] = getattr(req, field_name)

    # Prepend asset_id as first positional
    registry_register(asset_id, **kwargs)


def _build_response(response_cls, req, asset_id: str, filename: str,
                    prompt: str, mode: str, elapsed: int | None = None,
                    resolution: str | None = None):
    """Construct a response object with request fields + server metadata."""
    kwargs: dict = {
        "url": f"/assets/{filename}",
        "asset_id": asset_id,
        "seed": req.seed or 0,
        "generation_mode": mode,
        "prompt_used": prompt,
    }
    if resolution:
        kwargs["resolution"] = resolution
    if elapsed is not None:
        kwargs["generation_time_ms"] = elapsed

    for field_name in type(req).model_fields:
        if field_name == "seed":
            continue
        kwargs[field_name] = getattr(req, field_name)

    return response_cls(**kwargs)


def _load_and_save(src_path: str) -> str:
    """Open a PNG from disk, save to AssetStore, return the UUID filename."""
    filename = f"{uuid.uuid4()}.png"
    img = Image.open(src_path).convert("RGBA")
    store.save_image(filename, img)
    logger.info("Served static tile asset %s → %s", src_path, filename)
    return filename

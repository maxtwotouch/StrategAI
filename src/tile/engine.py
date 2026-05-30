"""Tile generation orchestrator.

Routes structure/object/terrain requests through the appropriate generator
based on the per-family generation mode (comfyui, static, placeholder).

Unlike the leader pipeline, tiles are single-shot txt2img — no multi-stage
dependencies, no reference images, no seed anchoring.

Uses ``workflows/txt2img.json`` which is intended for top-down game assets
(structures, objects, terrain, units).  The ``<tdp>`` LoRA trigger in the
prompt templates activates a LoRA that enforces top-down camera angle with
medieval pixel-art styling.  Background tiles use a separate workflow
(``background_tile.json``) without this LoRA.

Resolution (1024→128) and all sampling parameters are baked into the
workflow JSON.  The engine only injects: positive_prompt, seed.
"""
from __future__ import annotations
import asyncio
import logging
import os
import secrets
import time
import uuid
from typing import Union

from PIL import Image, ImageDraw

from src.comfyui_client import ComfyUIClient
from src.config import settings
from src.database import SessionLocal, AssetRecord, _execute_with_busy_retry
from .models import (
    StructureRequest, StructureResponse,
    ObjectRequest, ObjectResponse,
    TerrainRequest, TerrainResponse,
)
from .prompts import (
    build_structure_prompt,
    build_object_prompt,
    build_terrain_prompt,
)
from .registry import (
    generate_structure_id, generate_object_id, generate_terrain_id,
    StructureRegistry, ObjectRegistry, TerrainRegistry,
)
from src.static_catalog import catalog as static_catalog
from src.storage import store, try_remove_asset

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

# Game asset target resolution — must match the ComfyUI Image Resize node
# in workflows/txt2img.json (128×128 output from 1024×1024 generation).
GAME_ASSET_SIZE = 128

# Colour palette for placeholder tiles
_PLACEHOLDER_COLORS = {
    "structure": (139, 90, 43, 255),
    "object": (34, 139, 34, 255),
    "terrain": (100, 100, 80, 255),
}

from src.font_utils import get_font as _get_font


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
        seed = req.seed if req.seed is not None else secrets.randbits(32)

        # 4. Run ComfyUI
        start = time.time()
        try:
            img = await asyncio.wait_for(
                self._client.generate(
                    os.path.join(settings.workflow_dir, "txt2img.json"),
                    positive_prompt=prompt,
                    seed=seed,
                ),
                timeout=getattr(self._client, 'timeout', 300) + 60,
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Generation timed out")

        # 5. Save to AssetStore
        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, img)

        # 6. Persist AssetRecord + specialized registry record in one transaction
        try:
            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family=family,
                    generation_mode="comfyui",
                ))
                _register_tile(
                    registry_register,
                    asset_id=asset_id,
                    req=req,
                    image_id=filename,
                    seed=seed,
                    prompt_used=prompt,
                    generation_mode="comfyui",
                    session=db,
                )
                _execute_with_busy_retry(db, db.commit)
        except Exception:
            try_remove_asset(filename)
            raise

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
            start = time.time()
            filename = _load_and_save(path)
            elapsed = int((time.time() - start) * 1000)
            static_seed = req.seed if req.seed is not None else secrets.randbits(32)
            try:
                with SessionLocal() as db:
                    db.add(AssetRecord(
                        id=filename,
                        asset_family="structure",
                        generation_mode="static",
                    ))
                    _register_tile(
                        StructureRegistry.register,
                        asset_id=asset_id,
                        req=req,
                        image_id=filename,
                        seed=static_seed,
                        prompt_used=prompt,
                        generation_mode="static",
                        session=db,
                    )
                    _execute_with_busy_retry(db, db.commit)
            except Exception:
                try_remove_asset(filename)
                raise
            return _build_response(StructureResponse, req, asset_id, filename,
                                   prompt, "static", elapsed, f"{GAME_ASSET_SIZE}x{GAME_ASSET_SIZE}",
                                   seed=static_seed)

        # Fall through to placeholder
        return await _PlaceholderTileEngine().generate_structure(req)

    async def generate_object(self, req: ObjectRequest) -> ObjectResponse:
        prompt = build_object_prompt(req)
        asset_id = generate_object_id(req.category)

        # NOTE: static_catalog.resolve_random("nature_object") ignores
        # req.category — an ObjectRequest(category="debris") may return a
        # vegetation PNG.  Category-aware resolution requires catalog support.
        logger.debug("Static object resolution ignores category=%s", req.category)
        path = static_catalog.resolve_random("nature_object")
        if path:
            start = time.time()
            filename = _load_and_save(path)
            elapsed = int((time.time() - start) * 1000)
            static_seed = req.seed if req.seed is not None else secrets.randbits(32)
            try:
                with SessionLocal() as db:
                    db.add(AssetRecord(
                        id=filename,
                        asset_family="object",
                        generation_mode="static",
                    ))
                    _register_tile(
                        ObjectRegistry.register,
                        asset_id=asset_id,
                        req=req,
                        image_id=filename,
                        seed=static_seed,
                        prompt_used=prompt,
                        generation_mode="static",
                        session=db,
                    )
                    _execute_with_busy_retry(db, db.commit)
            except Exception:
                try_remove_asset(filename)
                raise
            return _build_response(ObjectResponse, req, asset_id, filename,
                                   prompt, "static", elapsed, f"{GAME_ASSET_SIZE}x{GAME_ASSET_SIZE}",
                                   seed=static_seed)

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
        seed = req.seed if req.seed is not None else secrets.randbits(32)

        start = time.time()

        color = _PLACEHOLDER_COLORS.get(family, (128, 128, 128, 255))
        img = Image.new("RGBA", (GAME_ASSET_SIZE, GAME_ASSET_SIZE), color)
        draw = ImageDraw.Draw(img)
        font = _get_font(14)

        # Border
        draw.rectangle([4, 4, GAME_ASSET_SIZE - 5, GAME_ASSET_SIZE - 5],
                       outline=(255, 255, 255, 255), width=2)

        # Label (supports embedded newlines)
        for i, line in enumerate(label.split("\n")):
            text_w = draw.textlength(line, font=font)
            draw.text(
                ((GAME_ASSET_SIZE - text_w) // 2, (GAME_ASSET_SIZE // 2) + (i * 20) - 10),
                line, fill=(255, 255, 255, 255), font=font,
            )

        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, img)

        try:
            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family=family,
                    generation_mode="static",
                ))
                _register_tile(
                    registry_register,
                    asset_id=asset_id, req=req,
                    image_id=filename, seed=seed,
                    prompt_used=prompt,
                    generation_mode="static",
                    session=db,
                )
                _execute_with_busy_retry(db, db.commit)
        except Exception:
            try_remove_asset(filename)
            raise

        elapsed = int((time.time() - start) * 1000)
        return _build_response(response_cls, req, asset_id, filename,
                               prompt, "static", elapsed, f"{img.width}x{img.height}",
                               seed=seed)


# ===========================================================================
#  Helpers
# ===========================================================================

def _register_tile(registry_register, asset_id: str, req, image_id: str,
                   seed: int, prompt_used: str, generation_mode: str,
                   session=None) -> None:
    """Call the appropriate Registry.register() with the right kwargs."""
    # Extract relevant fields from the request based on what register() expects
    kwargs: dict = {
        "image_id": image_id,
        "seed": seed,
        "prompt_used": prompt_used,
        "generation_mode": generation_mode,
        "session": session,
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
                    resolution: str | None = None, seed: int | None = None):
    """Construct a response object with request fields + server metadata."""
    # Seed is always generated before reaching this point; use req.seed as
    # a safety fallback only if the caller passes None (which should not happen).
    actual_seed = seed if seed is not None else req.seed
    if actual_seed is None:
        actual_seed = 0
        logger.warning(
            "_build_response: seed was None for asset %s — falling back to 0. "
            "This indicates a bug in the calling code.",
            asset_id,
        )
    kwargs: dict = {
        "url": f"/assets/{filename}",
        "asset_id": asset_id,
        "seed": actual_seed,
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
    """Open a PNG from disk, save to AssetStore, return the UUID filename.

    Raises ``FileNotFoundError`` if the source path doesn't exist, and
    ``ValueError`` if the file can't be opened as an image.
    """
    if not os.path.isfile(src_path):
        raise FileNotFoundError(f"Static tile asset not found: {src_path}")
    try:
        img = Image.open(src_path).convert("RGBA")
    except Exception as exc:
        raise ValueError(
            f"Failed to open image at {src_path}: {exc}"
        ) from exc
    filename = f"{uuid.uuid4()}.png"
    store.save_image(filename, img)
    logger.info("Served static tile asset %s → %s", src_path, filename)
    return filename
"""Unit generation orchestrator.

Routes unit sprite generation requests through the appropriate generator
based on the per-family generation mode (comfyui, static, placeholder).

Each unit generates a single south-facing (front view) sprite.

Uses ``workflows/txt2img.json`` — the top-down tile asset workflow.  The
``<tdp>`` LoRA trigger in the prompt template (``config/prompt_templates.json
→ unit``) activates a LoRA that enforces top-down camera angle with medieval
pixel-art styling.

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

from PIL import Image, ImageDraw

from src.comfyui_client import ComfyUIClient
from src.config import settings
from src.database import SessionLocal, AssetRecord, _execute_with_busy_retry
from .models import UnitRequest, UnitResponse, UnitType
from .prompts import build_unit_prompt
from .registry import generate_unit_id, UnitRegistry
from src.static_catalog import catalog as static_catalog
from src.storage import store, try_remove_asset

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

# Game asset target resolution — must match the ComfyUI Image Resize node
# in workflows/txt2img.json (128×128 output from 1024×1024 generation).
GAME_ASSET_SIZE = 128

# Colour palette for placeholder unit sprites
_UNIT_COLORS: dict[str, tuple[int, int, int, int]] = {
    UnitType.ARCHER:  (60, 140, 80, 255),    # greenish
    UnitType.SCOUT:   (60, 100, 180, 255),    # bluish
    UnitType.SETTLER: (160, 130, 70, 255),    # brownish
    UnitType.WARRIOR: (180, 50, 50, 255),     # reddish
}

from src.font_utils import get_font as _get_font


# ===========================================================================
#  Unit Engine  (comfyui mode)
# ===========================================================================

class UnitEngine:
    """Generates a single south-facing unit sprite via ComfyUI."""

    def __init__(self, client: ComfyUIClient) -> None:
        self._client = client

    async def generate(self, req: UnitRequest) -> UnitResponse:
        """Generate a single south-facing sprite for a unit type."""
        prompt = build_unit_prompt(req.unit_type, req.description)
        unit_id = generate_unit_id(req.unit_type)
        seed = req.seed if req.seed is not None else secrets.randbits(32)

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
        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, img)

        # Persist AssetRecord + UnitRecord in one transaction
        try:
            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family="unit",
                    generation_mode="comfyui",
                ))
                UnitRegistry.register(
                    unit_id=unit_id,
                    unit_type=req.unit_type,
                    description=req.description,
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

        return UnitResponse(
            url=f"/assets/{filename}",
            unit_id=unit_id,
            unit_type=req.unit_type,
            description=req.description,
            seed=seed,
            generation_mode="comfyui",
            prompt_used=prompt,
            resolution=f"{GAME_ASSET_SIZE}x{GAME_ASSET_SIZE}",
            generation_time_ms=elapsed,
        )


# ===========================================================================
#  Static Unit Engine  (serves from static_tiles/unit/)
# ===========================================================================

class StaticUnitEngine:
    """Serves a pre-made south-facing PNG from static_tiles/unit/."""

    async def generate(self, req: UnitRequest) -> UnitResponse:
        """Resolve a unit sprite from static_tiles/unit/, falling back to placeholder."""
        prompt = build_unit_prompt(req.unit_type, req.description)
        unit_id = generate_unit_id(req.unit_type)
        seed = req.seed if req.seed is not None else secrets.randbits(32)

        start = time.time()

        # Resolve from static catalog — expects {type}.png naming
        path = static_catalog.resolve_unit(req.unit_type)
        if path is None:
            return await _PlaceholderUnitEngine().generate(req)

        filename = f"{uuid.uuid4()}.png"
        with Image.open(path) as img_src:
            img = img_src.convert("RGBA")
        store.save_image(filename, img)

        try:
            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family="unit",
                    generation_mode="static",
                ))
                UnitRegistry.register(
                    unit_id=unit_id,
                    unit_type=req.unit_type,
                    description=req.description,
                    image_id=filename,
                    seed=seed,
                    prompt_used=prompt,
                    generation_mode="static",
                    session=db,
                )
                _execute_with_busy_retry(db, db.commit)
        except Exception:
            try_remove_asset(filename)
            raise

        elapsed = int((time.time() - start) * 1000)

        return UnitResponse(
            url=f"/assets/{filename}",
            unit_id=unit_id,
            unit_type=req.unit_type,
            description=req.description,
            seed=seed,
            generation_mode="static",
            prompt_used=prompt,
            resolution=f"{GAME_ASSET_SIZE}x{GAME_ASSET_SIZE}",
            generation_time_ms=elapsed,
        )


# ===========================================================================
#  Placeholder Unit Engine  (procedural coloured rectangle)
# ===========================================================================

class _PlaceholderUnitEngine:
    """Produces a labelled coloured rectangle for each unit type."""

    async def generate(self, req: UnitRequest) -> UnitResponse:
        prompt = build_unit_prompt(req.unit_type, req.description)
        unit_id = generate_unit_id(req.unit_type)
        seed = req.seed if req.seed is not None else secrets.randbits(32)

        start = time.time()

        color = _UNIT_COLORS.get(req.unit_type, (128, 128, 128, 255))
        font = _get_font(16)

        img = Image.new("RGBA", (GAME_ASSET_SIZE, GAME_ASSET_SIZE), color)
        draw = ImageDraw.Draw(img)

        # Border
        draw.rectangle(
            [4, 4, GAME_ASSET_SIZE - 5, GAME_ASSET_SIZE - 5],
            outline=(255, 255, 255, 255), width=2,
        )

        # Unit type label
        unit_label = req.unit_type.upper()
        unit_w = draw.textlength(unit_label, font=font)
        draw.text(
            ((GAME_ASSET_SIZE - unit_w) // 2, GAME_ASSET_SIZE // 2 - 12),
            unit_label, fill=(255, 255, 255, 255), font=font,
        )

        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, img)

        try:
            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family="unit",
                    generation_mode="static",
                ))
                UnitRegistry.register(
                    unit_id=unit_id,
                    unit_type=req.unit_type,
                    description=req.description,
                    image_id=filename,
                    seed=seed,
                    prompt_used=prompt,
                    generation_mode="static",
                    session=db,
                )
                _execute_with_busy_retry(db, db.commit)
        except Exception:
            try_remove_asset(filename)
            raise

        elapsed = int((time.time() - start) * 1000)

        return UnitResponse(
            url=f"/assets/{filename}",
            unit_id=unit_id,
            unit_type=req.unit_type,
            description=req.description,
            seed=seed,
            generation_mode="static",
            prompt_used=prompt,
            resolution=f"{GAME_ASSET_SIZE}x{GAME_ASSET_SIZE}",
            generation_time_ms=elapsed,
        )
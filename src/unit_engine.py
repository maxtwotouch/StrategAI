"""Unit generation orchestrator.

Routes unit sprite generation requests through the appropriate generator
based on the per-family generation mode (comfyui, static, placeholder).

Each unit spans 4 directional facings (s/n/e/w) — generated as separate
images.  Where a direction-specific PNG is unavailable (static mode), the
south-facing sprite is used as the universal fallback.

Mirrors the tile engine pattern: UnitEngine / StaticUnitEngine / _PlaceholderUnitEngine.
"""

import logging
import random
import time
import uuid
import os

from PIL import Image, ImageDraw, ImageFont

from .comfyui_client import ComfyUIClient
from .config import settings
from .database import SessionLocal, AssetRecord
from .unit_models import (
    UnitRequest, UnitResponse, UnitDirections,
    UnitType, Direction,
)
from .unit_prompts import build_unit_prompt
from .unit_registry import generate_unit_id, UnitRegistry
from .static_catalog import catalog as static_catalog
from .storage import store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

_SPRITE_WIDTH, _SPRITE_HEIGHT = 512, 512

# Colour palette for placeholder unit sprites
_UNIT_COLORS: dict[str, tuple[int, int, int, int]] = {
    UnitType.ARCHER:  (60, 140, 80, 255),    # greenish
    UnitType.SCOUT:   (60, 100, 180, 255),    # bluish
    UnitType.SETTLER: (160, 130, 70, 255),    # brownish
    UnitType.WARRIOR: (180, 50, 50, 255),     # reddish
}

# Direction indicators for placeholder sprites
_DIRECTION_INDICATORS: dict[str, str] = {
    Direction.SOUTH: "FRONT\n(v)",
    Direction.NORTH: "BACK\n(^)",
    Direction.EAST:  "RIGHT\n(>)",
    Direction.WEST:  "LEFT\n(<)",
}

_ALL_DIRECTIONS = [Direction.SOUTH, Direction.NORTH, Direction.EAST, Direction.WEST]

_FONT: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None


def _get_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    global _FONT
    if _FONT is None:
        try:
            _FONT = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16
            )
        except (OSError, IOError):
            _FONT = ImageFont.load_default()
    return _FONT


# ===========================================================================
#  Unit Engine  (comfyui mode)
# ===========================================================================

class UnitEngine:
    """Generates unit sprites via ComfyUI — 4 directional facings per unit."""

    def __init__(self, client: ComfyUIClient) -> None:
        self._client = client

    async def generate(self, req: UnitRequest) -> UnitResponse:
        """Generate all 4 direction sprites for a unit type."""
        prompt = build_unit_prompt(req.unit_type, Direction.SOUTH, req.description)
        unit_id = generate_unit_id(req.unit_type)
        seed = req.seed or random.randint(10**14, 10**15 - 1)

        start = time.time()

        # Generate each direction — reuse the same seed for visual consistency
        image_ids: dict[str, str] = {}
        for direction in _ALL_DIRECTIONS:
            dir_prompt = build_unit_prompt(req.unit_type, direction, req.description)
            img = await self._client.generate(
                os.path.join(settings.workflow_dir, "txt2img.json"),
                positive_prompt=dir_prompt,
                width=_SPRITE_WIDTH,
                height=_SPRITE_HEIGHT,
                seed=seed,
            )
            filename = f"{uuid.uuid4()}.png"
            store.save_image(filename, img)

            # Persist AssetRecord for each direction
            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family="unit",
                    generation_mode="comfyui",
                ))
                db.commit()

            image_ids[direction] = filename

        # Register unit with all 4 directional image IDs
        UnitRegistry.register(
            unit_id=unit_id,
            unit_type=req.unit_type,
            description=req.description,
            image_id_s=image_ids[Direction.SOUTH],
            image_id_n=image_ids[Direction.NORTH],
            image_id_e=image_ids[Direction.EAST],
            image_id_w=image_ids[Direction.WEST],
            seed=seed,
            prompt_used=prompt,
            generation_mode="comfyui",
        )

        elapsed = int((time.time() - start) * 1000)

        return UnitResponse(
            url=f"/assets/{image_ids[Direction.SOUTH]}",
            unit_id=unit_id,
            unit_type=req.unit_type,
            directions=UnitDirections(
                s=f"/assets/{image_ids[Direction.SOUTH]}",
                n=f"/assets/{image_ids[Direction.NORTH]}",
                e=f"/assets/{image_ids[Direction.EAST]}",
                w=f"/assets/{image_ids[Direction.WEST]}",
            ),
            seed=seed,
            generation_mode="comfyui",
            prompt_used=prompt,
            resolution=f"{_SPRITE_WIDTH}x{_SPRITE_HEIGHT}",
            generation_time_ms=elapsed,
        )


# ===========================================================================
#  Static Unit Engine  (serves from static_tiles/unit/)
# ===========================================================================

class StaticUnitEngine:
    """Serves pre-made directional PNGs from static_tiles/unit/."""

    async def generate(self, req: UnitRequest) -> UnitResponse:
        """Resolve unit sprites from static_tiles/unit/, falling back to placeholder."""
        prompt = build_unit_prompt(req.unit_type, Direction.SOUTH, req.description)
        unit_id = generate_unit_id(req.unit_type)
        seed = req.seed or 0

        start = time.time()

        # Resolve each direction from static catalog (with S-fallback)
        image_ids: dict[str, str] = {}
        south_filename: str | None = None

        for direction in _ALL_DIRECTIONS:
            path = static_catalog.resolve_unit(req.unit_type, direction)
            if path is None:
                # No static sprite at all for this unit type — fall through to placeholder
                return await _PlaceholderUnitEngine().generate(req)

            # If this direction resolved to the S-facing PNG via fallback,
            # and we've already loaded the S sprite, just reuse the same filename
            base = os.path.splitext(os.path.basename(path))[0]
            parts = base.rsplit("_", 1)
            resolved_direction = parts[-1] if len(parts) == 2 else "s"

            if resolved_direction == "s" and south_filename is not None:
                # Already loaded S — reuse for this fallback direction
                image_ids[direction] = south_filename
                continue

            filename = f"{uuid.uuid4()}.png"
            img = Image.open(path).convert("RGBA")
            store.save_image(filename, img)

            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family="unit",
                    generation_mode="static",
                ))
                db.commit()

            image_ids[direction] = filename
            if direction == Direction.SOUTH:
                south_filename = filename

        # Register unit
        UnitRegistry.register(
            unit_id=unit_id,
            unit_type=req.unit_type,
            description=req.description,
            image_id_s=image_ids[Direction.SOUTH],
            image_id_n=image_ids[Direction.NORTH],
            image_id_e=image_ids[Direction.EAST],
            image_id_w=image_ids[Direction.WEST],
            seed=seed,
            prompt_used=prompt,
            generation_mode="static",
        )

        elapsed = int((time.time() - start) * 1000)

        return UnitResponse(
            url=f"/assets/{image_ids[Direction.SOUTH]}",
            unit_id=unit_id,
            unit_type=req.unit_type,
            directions=UnitDirections(
                s=f"/assets/{image_ids[Direction.SOUTH]}",
                n=f"/assets/{image_ids[Direction.NORTH]}",
                e=f"/assets/{image_ids[Direction.EAST]}",
                w=f"/assets/{image_ids[Direction.WEST]}",
            ),
            seed=seed,
            generation_mode="static",
            prompt_used=prompt,
            resolution=f"{_SPRITE_WIDTH}x{_SPRITE_HEIGHT}",
            generation_time_ms=elapsed,
        )


# ===========================================================================
#  Placeholder Unit Engine  (procedural coloured rectangle)
# ===========================================================================

class _PlaceholderUnitEngine:
    """Produces a labelled coloured rectangle per direction for each unit type."""

    async def generate(self, req: UnitRequest) -> UnitResponse:
        prompt = build_unit_prompt(req.unit_type, Direction.SOUTH, req.description)
        unit_id = generate_unit_id(req.unit_type)
        seed = req.seed or random.randint(10**14, 10**15 - 1)

        start = time.time()

        color = _UNIT_COLORS.get(req.unit_type, (128, 128, 128, 255))
        font = _get_font()

        image_ids: dict[str, str] = {}

        for direction in _ALL_DIRECTIONS:
            img = Image.new("RGBA", (_SPRITE_WIDTH, _SPRITE_HEIGHT), color)
            draw = ImageDraw.Draw(img)

            # Border
            draw.rectangle(
                [4, 4, _SPRITE_WIDTH - 5, _SPRITE_HEIGHT - 5],
                outline=(255, 255, 255, 255), width=2,
            )

            # Unit type label
            unit_label = req.unit_type.upper()
            unit_w = draw.textlength(unit_label, font=font)
            draw.text(
                ((_SPRITE_WIDTH - unit_w) // 2, _SPRITE_HEIGHT // 2 - 30),
                unit_label, fill=(255, 255, 255, 255), font=font,
            )

            # Direction indicator
            dir_label = _DIRECTION_INDICATORS.get(direction, direction.upper())
            for i, line in enumerate(dir_label.split("\n")):
                line_w = draw.textlength(line, font=font)
                draw.text(
                    ((_SPRITE_WIDTH - line_w) // 2, _SPRITE_HEIGHT // 2 + (i * 20)),
                    line, fill=(220, 220, 220, 255), font=font,
                )

            filename = f"{uuid.uuid4()}.png"
            store.save_image(filename, img)

            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family="unit",
                    generation_mode="placeholder",
                ))
                db.commit()

            image_ids[direction] = filename

        UnitRegistry.register(
            unit_id=unit_id,
            unit_type=req.unit_type,
            description=req.description,
            image_id_s=image_ids[Direction.SOUTH],
            image_id_n=image_ids[Direction.NORTH],
            image_id_e=image_ids[Direction.EAST],
            image_id_w=image_ids[Direction.WEST],
            seed=seed,
            prompt_used=prompt,
            generation_mode="placeholder",
        )

        elapsed = int((time.time() - start) * 1000)

        return UnitResponse(
            url=f"/assets/{image_ids[Direction.SOUTH]}",
            unit_id=unit_id,
            unit_type=req.unit_type,
            directions=UnitDirections(
                s=f"/assets/{image_ids[Direction.SOUTH]}",
                n=f"/assets/{image_ids[Direction.NORTH]}",
                e=f"/assets/{image_ids[Direction.EAST]}",
                w=f"/assets/{image_ids[Direction.WEST]}",
            ),
            seed=seed,
            generation_mode="placeholder",
            prompt_used=prompt,
            resolution=f"{_SPRITE_WIDTH}x{_SPRITE_HEIGHT}",
            generation_time_ms=elapsed,
        )

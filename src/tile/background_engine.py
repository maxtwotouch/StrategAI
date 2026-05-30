"""Background tile generation orchestrator.

Background tiles are the base ground layer — seamless repeating textures
(water, grass, sand, stone) that form the floor of the game map.  Unlike
structure/object/terrain tiles, background tiles fill the entire frame
with no white background isolation.

Uses ``workflows/background_tile.json`` — a Flux2 Klein txt2img workflow
without the top-down pixel-art LoRA.  The prompt template for background
tiles (``config/prompt_templates.json → background_tile``) also omits the
``<tdp>`` LoRA trigger phrase.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
import uuid

from PIL import Image, ImageDraw

from src.comfyui_client import ComfyUIClient
from src.config import settings
from src.database import SessionLocal, AssetRecord
from src.prompt_templates import render as _render
from src.static_catalog import catalog as static_catalog
from src.storage import store, try_remove_asset
from src.tile.background_registry import BackgroundTileRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

# Must match the ComfyUI Image Resize node in workflows/background_tile.json
GAME_ASSET_SIZE = 128

# Valid background tile types
TILE_TYPES = {"water", "grass", "sand", "stone", "dirt"}

# Placeholder colour for each tile type
_PLACEHOLDER_COLORS: dict[str, tuple[int, int, int, int]] = {
    "water": (60, 120, 200, 255),
    "grass": (80, 160, 60, 255),
    "sand":  (220, 200, 140, 255),
    "stone": (140, 140, 140, 255),
    "dirt":  (140, 100, 60, 255),
}

from src.font_utils import get_font as _get_font

# ---------------------------------------------------------------------------
#  Result type
# ---------------------------------------------------------------------------

class BackgroundTileResult:
    """Structured return from all background tile engines.

    Replaces the raw ``(filename, bg_tile_id, seed)`` tuple so the HTTP
    layer doesn't need to know engine internals or re-render the prompt.
    """

    __slots__ = ("filename", "bg_tile_id", "seed", "prompt_used",
                 "generation_mode", "elapsed_ms")

    def __init__(
        self,
        filename: str,
        bg_tile_id: str,
        seed: int,
        prompt_used: str,
        generation_mode: str,
        elapsed_ms: int,
    ) -> None:
        self.filename = filename
        self.bg_tile_id = bg_tile_id
        self.seed = seed
        self.prompt_used = prompt_used
        self.generation_mode = generation_mode
        self.elapsed_ms = elapsed_ms


def _generate_bg_tile_id(tile_type: str) -> str:
    """Generate a unique background_tile_id."""
    short = uuid.uuid4().hex[:8]
    return f"bg_{tile_type}_{short}"


# ===========================================================================
#  Background Tile Engine  (comfyui mode)
# ===========================================================================

class BackgroundTileEngine:
    """Generates a single seamless background tile texture via ComfyUI."""

    def __init__(self, client: ComfyUIClient) -> None:
        self._client = client

    async def generate(self, tile_type: str, seed: int | None = None) -> BackgroundTileResult:
        """Generate a background tile and return a structured result.

        Parameters
        ----------
        tile_type : str
            One of ``"water"``, ``"grass"``, ``"sand"``, ``"stone"``, ``"dirt"``.
        seed : int | None
            Deterministic seed for reproducibility.

        Returns
        -------
        BackgroundTileResult
        """
        if tile_type not in TILE_TYPES:
            raise ValueError(
                f"Unknown tile_type '{tile_type}'. Valid: {sorted(TILE_TYPES)}"
            )

        prompt = _render("background_tile", tile_type=tile_type)
        seed = seed if seed is not None else secrets.randbits(31)
        bg_tile_id = _generate_bg_tile_id(tile_type)

        start = time.time()

        img = await self._client.generate(
            os.path.join(settings.workflow_dir, "background_tile.json"),
            positive_prompt=prompt,
            seed=seed,
        )

        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, img)

        # Atomic: AssetRecord + BackgroundTileRegistry in one transaction
        try:
            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family="background_tile",
                    generation_mode="comfyui",
                    tile_type=tile_type,
                ))
                BackgroundTileRegistry.register(
                    background_tile_id=bg_tile_id,
                    tile_type=tile_type,
                    seed=seed,
                    image_filename=filename,
                    session=db,
                )
                db.commit()
        except Exception:
            try_remove_asset(filename)
            raise

        elapsed = int((time.time() - start) * 1000)
        logger.info(
            "Background tile '%s' generated in %dms (%s)",
            tile_type, elapsed, filename,
        )
        return BackgroundTileResult(
            filename=filename,
            bg_tile_id=bg_tile_id,
            seed=seed,
            prompt_used=prompt,
            generation_mode="comfyui",
            elapsed_ms=elapsed,
        )


# ===========================================================================
#  Static Background Tile Engine  (serves from static_tiles/)
# ===========================================================================

class StaticBackgroundTileEngine:
    """Serves pre-made background tile PNGs from static_tiles/background_tile/."""

    async def generate(self, tile_type: str, seed: int | None = None) -> BackgroundTileResult:
        if tile_type not in TILE_TYPES:
            raise ValueError(
                f"Unknown tile_type '{tile_type}'. Valid: {sorted(TILE_TYPES)}"
            )
        seed = seed if seed is not None else secrets.randbits(31)
        bg_tile_id = _generate_bg_tile_id(tile_type)

        # Try static catalog first
        path = static_catalog.resolve_tile(tile_type)
        if path:
            filename = _load_and_save(path)
            try:
                with SessionLocal() as db:
                    db.add(AssetRecord(
                        id=filename,
                        asset_family="background_tile",
                        generation_mode="static",
                        tile_type=tile_type,
                    ))
                    BackgroundTileRegistry.register(
                        background_tile_id=bg_tile_id,
                        tile_type=tile_type,
                        seed=seed,
                        image_filename=filename,
                        session=db,
                    )
                    db.commit()
            except Exception:
                try_remove_asset(filename)
                raise
            logger.info("Served static background tile '%s' → %s", tile_type, filename)
            return BackgroundTileResult(
                filename=filename,
                bg_tile_id=bg_tile_id,
                seed=seed,
                prompt_used=_render("background_tile", tile_type=tile_type),
                generation_mode="static",
                elapsed_ms=0,
            )

        # Fall through to placeholder
        return await _PlaceholderBackgroundTileEngine().generate(tile_type, seed)


# ===========================================================================
#  Placeholder Background Tile Engine
# ===========================================================================

class _PlaceholderBackgroundTileEngine:
    """Produces a coloured rectangle labelled with the tile type."""

    async def generate(self, tile_type: str, seed: int | None = None) -> BackgroundTileResult:
        color = _PLACEHOLDER_COLORS.get(tile_type, (128, 128, 128, 255))
        font = _get_font(12)
        seed = seed if seed is not None else secrets.randbits(31)
        bg_tile_id = _generate_bg_tile_id(tile_type)

        img = Image.new("RGBA", (GAME_ASSET_SIZE, GAME_ASSET_SIZE), color)
        draw = ImageDraw.Draw(img)

        draw.rectangle(
            [2, 2, GAME_ASSET_SIZE - 3, GAME_ASSET_SIZE - 3],
            outline=(255, 255, 255, 255), width=1,
        )

        label = tile_type.upper()
        text_w = draw.textlength(label, font=font)
        draw.text(
            ((GAME_ASSET_SIZE - text_w) // 2, GAME_ASSET_SIZE // 2 - 6),
            label, fill=(255, 255, 255, 255), font=font,
        )

        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, img)

        try:
            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family="background_tile",
                    generation_mode="placeholder",
                    tile_type=tile_type,
                ))
                BackgroundTileRegistry.register(
                    background_tile_id=bg_tile_id,
                    tile_type=tile_type,
                    seed=seed,
                    image_filename=filename,
                    session=db,
                )
                db.commit()
        except Exception:
            try_remove_asset(filename)
            raise

        logger.info("Placeholder background tile '%s' → %s", tile_type, filename)
        return BackgroundTileResult(
            filename=filename,
            bg_tile_id=bg_tile_id,
            seed=seed,
            prompt_used=_render("background_tile", tile_type=tile_type),
            generation_mode="placeholder",
            elapsed_ms=0,
        )


# ===========================================================================
#  Helper
# ===========================================================================


def _load_and_save(src_path: str) -> str:
    """Open a PNG from disk, save to AssetStore, return the UUID filename."""
    filename = f"{uuid.uuid4()}.png"
    img = Image.open(src_path).convert("RGBA")
    if img.size != (GAME_ASSET_SIZE, GAME_ASSET_SIZE):
        img = img.resize((GAME_ASSET_SIZE, GAME_ASSET_SIZE), Image.LANCZOS)
    store.save_image(filename, img)
    return filename

"""Background tile generation orchestrator.

Background tiles are the base ground layer — seamless repeating textures
(water, grass, sand, stone) that form the floor of the game map.  Unlike
structure/object/terrain tiles, background tiles fill the entire frame
with no white background isolation.

Uses the same ``txt2img.json`` workflow as other game assets (1024→128).
"""

import logging
import random
import time
import uuid
import os

from PIL import Image, ImageDraw, ImageFont

from src.comfyui_client import ComfyUIClient
from src.config import settings
from src.database import SessionLocal, AssetRecord
from src.prompt_templates import assemble as _assemble
from src.static_catalog import catalog as static_catalog
from src.storage import store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

# Must match the ComfyUI Image Resize node in workflows/txt2img.json
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

_FONT: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None


def _get_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    global _FONT
    if _FONT is None:
        try:
            _FONT = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12
            )
        except (OSError, IOError):
            _FONT = ImageFont.load_default()
    return _FONT


# ===========================================================================
#  Background Tile Engine  (comfyui mode)
# ===========================================================================

class BackgroundTileEngine:
    """Generates a single seamless background tile texture via ComfyUI."""

    def __init__(self, client: ComfyUIClient) -> None:
        self._client = client

    async def generate(self, tile_type: str, seed: int | None = None) -> str:
        """Generate a background tile and return the asset filename.

        Parameters
        ----------
        tile_type : str
            One of ``"water"``, ``"grass"``, ``"sand"``, ``"stone"``, ``"dirt"``.
        seed : int | None
            Deterministic seed for reproducibility.

        Returns
        -------
        str
            The UUID filename in the asset store.
        """
        if tile_type not in TILE_TYPES:
            raise ValueError(
                f"Unknown tile_type '{tile_type}'. Valid: {sorted(TILE_TYPES)}"
            )

        prompt = _assemble("background_tile", f"{tile_type} ground texture")
        seed = seed or random.randint(10**14, 10**15 - 1)

        start = time.time()

        img = await self._client.generate(
            os.path.join(settings.workflow_dir, "txt2img.json"),
            positive_prompt=prompt,
            seed=seed,
        )

        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, img)

        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="background_tile",
                generation_mode="comfyui",
                tile_type=tile_type,
            ))
            db.commit()

        elapsed = int((time.time() - start) * 1000)
        logger.info(
            "Background tile '%s' generated in %dms (%s)",
            tile_type, elapsed, filename,
        )
        return filename


# ===========================================================================
#  Static Background Tile Engine  (serves from static_tiles/)
# ===========================================================================

class StaticBackgroundTileEngine:
    """Serves pre-made background tile PNGs from static_tiles/background_tile/."""

    async def generate(self, tile_type: str, seed: int | None = None) -> str:
        if tile_type not in TILE_TYPES:
            raise ValueError(
                f"Unknown tile_type '{tile_type}'. Valid: {sorted(TILE_TYPES)}"
            )

        # Try static catalog first
        path = static_catalog.resolve_tile(tile_type)
        if path:
            filename = _load_and_save(path)
            logger.info("Served static background tile '%s' → %s", tile_type, filename)
            return filename

        # Fall through to placeholder
        return await _PlaceholderBackgroundTileEngine().generate(tile_type, seed)


# ===========================================================================
#  Placeholder Background Tile Engine
# ===========================================================================

class _PlaceholderBackgroundTileEngine:
    """Produces a coloured rectangle labelled with the tile type."""

    async def generate(self, tile_type: str, seed: int | None = None) -> str:
        color = _PLACEHOLDER_COLORS.get(tile_type, (128, 128, 128, 255))
        font = _get_font()

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
        logger.info("Placeholder background tile '%s' → %s", tile_type, filename)
        return filename


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

"""Image generators -- routes requests to ComfyUI, static PNGs, or procedural placeholders.

The factory function ``get_generator()`` inspects the per-family generation mode
set in the environment and returns the appropriate generator.  The caller never
needs to know which one was chosen.

All generators expose an **async** ``generate()`` method that can be awaited
directly from async FastAPI endpoints -- no thread-pool required.
"""

from __future__ import annotations

import logging
import os
import random
import uuid
from abc import ABC, abstractmethod

from PIL import Image, ImageDraw, ImageFont

from .comfyui_client import ComfyUIClient
from .config import settings
from .inpainting import create_inpaint_mask, get_inpaint_prompt
from .models import GenerationRequest, SplashRequest
from .static_catalog import catalog as static_catalog
from .storage import store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Singleton ComfyUI client (lazily created)
# ---------------------------------------------------------------------------

_comfyui_client: ComfyUIClient | None = None
_comfyui_available: bool | None = None  # None = unchecked, True/False = known


def _get_comfyui_client() -> ComfyUIClient | None:
    """Return a ComfyUIClient instance. The caller is responsible for
    performing an async health check separately if needed."""
    global _comfyui_client, _comfyui_available
    if _comfyui_available is None:
        _comfyui_client = ComfyUIClient()
        _comfyui_available = True
    return _comfyui_client if _comfyui_available else None


async def close_comfyui_client() -> None:
    """Shut down the singleton ComfyUI client (called during app shutdown)."""
    global _comfyui_client, _comfyui_available
    if _comfyui_client is not None:
        await _comfyui_client.close()
        _comfyui_client = None
    _comfyui_available = None


# ---------------------------------------------------------------------------
#  Abstract base
# ---------------------------------------------------------------------------


class ImageGenerator(ABC):
    @abstractmethod
    async def generate(self, request: GenerationRequest | SplashRequest) -> str:
        """Produce an image, save it, return the filename."""
        ...


# ---------------------------------------------------------------------------
#  ComfyUI generator
# ---------------------------------------------------------------------------


class ComfyUIGenerator(ImageGenerator):
    """Delegates everything to an external ComfyUI server.

    Parameters
    ----------
    workflow_file : str
        Basename of the workflow JSON (e.g. ``'txt2img.json'``).
    """

    _WORKFLOW_MAP = {
        "structure": "txt2img.json",
        "nature_object": "txt2img.json",
        "background_tile": "inpaint.json",
        "character_sprite": "txt2img.json",
        "story": "story.json",
        "splash": "splash.json",
    }

    def __init__(self, client: ComfyUIClient, workflow_file: str) -> None:
        self._client = client
        self._workflow_path = os.path.join(settings.workflow_dir, workflow_file)

    async def generate(self, request: GenerationRequest | SplashRequest) -> str:
        if isinstance(request, SplashRequest):
            return await self._generate_splash(request)
        return await self._generate_generic(request)

    # ------------------------------------------------------------------
    #  Generic (txt2img / story / inpainting)
    # ------------------------------------------------------------------

    async def _generate_generic(self, request: GenerationRequest) -> str:
        positive = self._build_positive_prompt(request)
        width, height = self._dimensions_for(request.asset_family)

        # --- Handle inpainting (CoW) ---
        if request.asset_family == "background_tile" and request.inpaints:
            return await self._generate_inpaint(request, positive, width, height)

        img = await self._client.generate(
            self._workflow_path,
            positive_prompt=positive,
            width=width,
            height=height,
        )
        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, img)
        return filename

    async def _generate_inpaint(
        self,
        request: GenerationRequest,
        positive: str,
        width: int,
        height: int,
    ) -> str:
        """Sequential CoW inpainting: upload base → mask → inpaint → loop."""
        if request.base_image_id:
            current_img = store.get_image_pil(request.base_image_id)
        else:
            # Start with a blank tile, then inpaint over it
            current_img = Image.new("RGBA", (width, height), (100, 100, 100, 255))

        for patch in request.inpaints:
            mask = create_inpaint_mask(
                current_img.width, current_img.height,
                patch.point_a.model_dump(), patch.point_b.model_dump(),
                blur_radius=2,
            )
            fill_prompt = get_inpaint_prompt(patch.fill_type)
            logger.info(
                "Inpainting feature '%s' with prompt: %s", patch.fill_type, fill_prompt
            )

            current_img = await self._client.generate(
                self._workflow_path,
                positive_prompt=fill_prompt,
                width=current_img.width,
                height=current_img.height,
                input_images={
                    "2": current_img,  # LoadImage node for base
                    "3": mask,          # LoadImage node for mask
                },
            )

        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, current_img)
        return filename

    # ------------------------------------------------------------------
    #  Splash
    # ------------------------------------------------------------------

    async def _generate_splash(self, request: SplashRequest) -> str:
        prompt = self._build_splash_prompt(request)
        w, h = settings.splash.width, settings.splash.height

        img = await self._client.generate(
            self._workflow_path,
            positive_prompt=prompt,
            width=512,
            height=512,
        )
        if img.size != (w, h):
            img = img.resize((w, h), Image.LANCZOS)

        filename = f"{uuid.uuid4()}_splash.png"
        store.save_image(filename, img)
        logger.info("Splash art generated via ComfyUI for '%s'", request.character_name)
        return filename

    # ------------------------------------------------------------------
    #  Prompt builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_positive_prompt(request: GenerationRequest) -> str:
        """Build a rich prompt from family + subtype + user prompt."""
        parts: list[str] = []

        # Family-specific prefix
        if request.asset_family == "structure":
            subtype = (request.structure_subtype or "medieval").replace("_", " ")
            parts.append(f"pixel art top-down 2d game {subtype} building")
            parts.append("top-down view, isometric pixel art, medieval fantasy")

        elif request.asset_family == "nature_object":
            parts.append("pixel art top-down 2d game nature object")
            parts.append("tree or rock, isometric pixel art, medieval fantasy")

        elif request.asset_family == "background_tile":
            tile = request.tile_type or "grass"
            parts.append(get_inpaint_prompt(tile))

        elif request.asset_family == "character_sprite":
            parts.append("pixel art top-down 2d game character sprite")
            parts.append("medieval fantasy character, sprite sheet, isometric view")

        elif request.asset_family == "story":
            parts.append("Epic cliffhanger concept art, dramatic dynamic lighting")
            parts.append("ultra detailed, fantasy style")
            if request.prompt:
                parts.append(request.prompt)
            parts.append("--ar 16:9")

        # User prompt override
        if request.prompt and request.asset_family != "story":
            parts.append(request.prompt)

        return ", ".join(parts)

    @staticmethod
    def _build_splash_prompt(request: SplashRequest) -> str:
        parts = [
            "pixel art",
            request.style,
            "character portrait",
            "splash art",
            "medieval fantasy",
        ]
        if request.description:
            parts.append(request.description)
        if request.outfit:
            parts.append(f"wearing {request.outfit}")
        if request.weapon:
            parts.append(f"holding {request.weapon}")
        return ", ".join(parts)

    @staticmethod
    def _dimensions_for(asset_family: str) -> tuple[int, int]:
        if asset_family == "story":
            return (1024, 576)
        return (512, 512)


# ---------------------------------------------------------------------------
#  Static-tile generator
# ---------------------------------------------------------------------------


class StaticTileGenerator(ImageGenerator):
    """Serves pre-made PNGs from ``static_tiles/``."""

    def __init__(self, family: str) -> None:
        self._family = family

    async def generate(self, request: GenerationRequest | SplashRequest) -> str:
        if isinstance(request, SplashRequest):
            return _PlaceholderSplash.generate(request)

        # background_tile → exact tile_type match
        if request.asset_family == "background_tile":
            tile = request.tile_type
            if tile is None:
                raise ValueError("tile_type is required for background_tile")
            path = static_catalog.resolve_tile(tile)
            if path:
                return _load_and_save(path, f"{uuid.uuid4()}.png")
            # Fall through to placeholder -- no static PNG for this tile type

        # structure → random from subtype (or all subtypes)
        if request.asset_family == "structure":
            path = static_catalog.resolve_random("structure", request.structure_subtype)
            if path:
                return _load_and_save(path, f"{uuid.uuid4()}.png")

        # nature_object / character_sprite → random from folder
        path = static_catalog.resolve_random(request.asset_family)
        if path:
            return _load_and_save(path, f"{uuid.uuid4()}.png")

        # Fallback: procedural placeholder
        return await _PlaceholderGenerator(self._family).generate(request)


# ---------------------------------------------------------------------------
#  Procedural placeholder (when nothing else is available)
# ---------------------------------------------------------------------------


class _PlaceholderGenerator(ImageGenerator):
    """Produces a coloured rectangle with a text label."""

    _COLORS = {
        "structure": (139, 90, 43, 255),
        "nature_object": (34, 139, 34, 255),
        "background_tile": (144, 238, 144, 255),
        "character_sprite": (200, 60, 60, 255),
        "story": (25, 25, 112, 255),
        "splash": (30, 25, 40, 255),
    }

    def __init__(self, family: str) -> None:
        self._family = family

    async def generate(self, request: GenerationRequest | SplashRequest) -> str:
        color = self._COLORS.get(self._family, (128, 128, 128, 255))
        w, h = (512, 512)
        if self._family == "story":
            w, h = (1024, 576)
        elif isinstance(request, SplashRequest):
            w, h = settings.splash.width, settings.splash.height

        img = Image.new("RGBA", (w, h), color)
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18
            )
        except (OSError, IOError):
            font = ImageFont.load_default()

        label = request.asset_family if isinstance(request, GenerationRequest) else "splash"
        draw.text((10, 10), f"[placeholder] {label}", fill=(255, 255, 255, 255), font=font)
        if isinstance(request, GenerationRequest) and request.tile_type:
            draw.text(
                (10, 36), f"tile: {request.tile_type}",
                fill=(220, 220, 220, 255), font=font,
            )

        filename = f"{uuid.uuid4()}.png"
        store.save_image(filename, img)
        logger.info("Returned placeholder for family '%s'", self._family)
        return filename


# ---------------------------------------------------------------------------
#  Splash placeholder (preserves original mock art logic)
# ---------------------------------------------------------------------------


class _PlaceholderSplash:
    """Render a procedural splash portrait.  Kept as static method for reuse."""

    @staticmethod
    def generate(request: SplashRequest) -> str:
        w, h = settings.splash.width, settings.splash.height
        background_colors = {
            "solid_dark": (30, 25, 40, 255),
            "banner": (60, 30, 20, 255),
            "landscape": (50, 70, 120, 255),
        }
        bg_color = background_colors.get(request.background, (30, 25, 40, 255))
        img = Image.new("RGBA", (w, h), bg_color)
        draw = ImageDraw.Draw(img)

        # Decorative border
        border_color = (180, 160, 120, 255)
        draw.rectangle([4, 4, w - 5, h - 5], outline=border_color, width=2)

        # Portrait silhouette
        portrait_size = min(w, h) // 2
        cx, cy = w // 2, h // 2 + 8
        palette = [
            (180, 100, 80, 255),
            (80, 140, 180, 255),
            (160, 80, 160, 255),
            (80, 180, 100, 255),
            (200, 160, 60, 255),
            (60, 100, 200, 255),
        ]
        portrait_color = palette[hash(request.character_name) % len(palette)]
        draw.ellipse(
            [cx - portrait_size, cy - portrait_size, cx + portrait_size, cy + portrait_size],
            fill=portrait_color,
            outline=(220, 200, 160, 255),
            width=2,
        )

        # Title badge
        if request.title:
            badge_y = cy + portrait_size + 10
            badge_text = request.title.upper()
            draw.rectangle(
                [cx - 40, badge_y - 6, cx + 40, badge_y + 10],
                fill=(80, 60, 40, 255),
            )
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12
                )
            except (OSError, IOError):
                font = ImageFont.load_default()
            text_w = draw.textlength(badge_text, font=font)
            draw.text(
                (cx - text_w // 2, badge_y - 4),
                badge_text,
                fill=(220, 200, 160, 255),
                font=font,
            )

        # Name at bottom
        name_y = h - 24
        try:
            name_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14
            )
        except (OSError, IOError):
            name_font = ImageFont.load_default()
        name_w = draw.textlength(request.character_name, font=name_font)
        draw.text(
            (cx - name_w // 2, name_y),
            request.character_name,
            fill=(240, 230, 210, 255),
            font=name_font,
        )

        filename = f"{uuid.uuid4()}_splash.png"
        store.save_image(filename, img)
        logger.info("Splash placeholder generated for '%s'", request.character_name)
        return filename


# ---------------------------------------------------------------------------
#  Helper
# ---------------------------------------------------------------------------


def _load_and_save(src_path: str, filename: str) -> str:
    """Open a PNG from disk, save to AssetStore, return the UUID filename."""
    img = Image.open(src_path).convert("RGBA")
    store.save_image(filename, img)
    logger.info("Served static asset %s → %s", src_path, filename)
    return filename


# ---------------------------------------------------------------------------
#  Factory
# ---------------------------------------------------------------------------


def get_generator(
    asset_family: str,
    request: GenerationRequest | SplashRequest | None = None,
) -> ImageGenerator:
    """Return the appropriate generator based on server-side generation mode.

    The client never influences this decision -- it's entirely driven by
    per-family environment variables.
    """
    mode = settings.get_mode(asset_family)

    if mode == "static":
        return StaticTileGenerator(asset_family)

    if mode == "random":
        # Coin-flip per request
        if random.random() >= settings.generation.random_probability:
            return StaticTileGenerator(asset_family)

    # mode == "comfyui" (or random coin landed on comfyui)
    client = _get_comfyui_client()
    if client is None:
        raise RuntimeError(
            f"Asset family '{asset_family}' is in 'comfyui' mode but ComfyUI server is "
            f"unreachable at {settings.comfyui.base_url}"
        )

    workflow_file = ComfyUIGenerator._WORKFLOW_MAP.get(asset_family, "txt2img.json")
    return ComfyUIGenerator(client, workflow_file)

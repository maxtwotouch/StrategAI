"""Shared font loading with configurable path and cross-platform fallbacks.

Used by placeholder engines (tile, unit, background_tile) to draw labels
on procedural placeholder images.  Tries, in order:

1. A path configured in ``config.yaml`` → ``paths.font_path`` (optional)
2. Common system TrueType font directories (Debian/Ubuntu, Fedora, macOS)
3. ``PIL.ImageFont.load_default()`` — always available, works everywhere

All callers share a single cached font per size via a thread-safe singleton.
"""

from __future__ import annotations

import os
import threading
from PIL import ImageFont


# ---------------------------------------------------------------------------
#  Common system font paths (tried in order)
# ---------------------------------------------------------------------------

_FALLBACK_PATHS: list[str] = [
    # Debian / Ubuntu
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    # Fedora / RHEL
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/SFNSDisplay.ttf",
    "/Library/Fonts/Arial.ttf",
    # Windows (via WSL or native)
    "/mnt/c/Windows/Fonts/arial.ttf",
]

# Per-size font cache: {size: font}
_font_cache: dict[int, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
_font_lock = threading.Lock()


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------


def get_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return a PIL font at the requested size, with cross-platform fallback.

    The font is cached per *size* on first call — subsequent calls for the
    same size return the cached instance without any filesystem access.

    Parameters
    ----------
    size : int
        Font size in points (default 14).

    Returns
    -------
    ImageFont.FreeTypeFont | ImageFont.ImageFont
        A usable font — never raises.
    """
    global _font_cache
    if size in _font_cache:
        return _font_cache[size]

    with _font_lock:
        if size in _font_cache:
            return _font_cache[size]

        font = _resolve_font(size)
        _font_cache[size] = font
        return font


# ---------------------------------------------------------------------------
#  Internal
# ---------------------------------------------------------------------------


def _resolve_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try config path → system paths → PIL default."""
    # 1. Config-specified path (optional)
    try:
        from src.config import settings
        cfg_path = getattr(settings.paths, "font_path", None)
        if cfg_path and os.path.isfile(cfg_path):
            return ImageFont.truetype(cfg_path, size)
    except Exception:
        pass  # config not yet loaded or path invalid — try fallbacks

    # 2. Common system paths
    for path in _FALLBACK_PATHS:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue

    # 3. PIL built-in fallback (always works, tiny bitmap font)
    return ImageFont.load_default()

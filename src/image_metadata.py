#!/usr/bin/env python3
"""Embed and read JSON metadata in PNG tEXt chunks via Pillow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL.PngImagePlugin import PngInfo

META_KEY = "generation_metadata"


def embed_metadata_into_file(img_path: str | Path, metadata: dict[str, Any]) -> None:
    """Inject a JSON metadata dict into a PNG as a 'generation_metadata' tEXt chunk."""
    img_path = Path(img_path)
    from PIL import Image

    with Image.open(img_path) as im:
        png_info = PngInfo()
        # Preserve any existing tEXt chunks
        if im.info:
            for k, v in im.info.items():
                if isinstance(v, str):
                    png_info.add_text(k, v)

        png_info.add_text(META_KEY, json.dumps(metadata, ensure_ascii=False))
        im.save(img_path, "PNG", pnginfo=png_info)


def read_metadata_from_file(img_path: str | Path) -> dict[str, Any] | None:
    """Read and parse the 'generation_metadata' tEXt chunk from a PNG. Returns None if absent."""
    img_path = Path(img_path)
    from PIL import Image

    with Image.open(img_path) as im:
        raw = im.info.get(META_KEY)
        if raw is None:
            return None
        return json.loads(raw)

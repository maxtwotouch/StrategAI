"""Tests for image_metadata.py — embed/read PNG metadata roundtrip."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from src.generation.image_metadata import (
    META_KEY,
    embed_metadata_into_file,
    read_metadata_from_file,
)


def test_embed_and_read_roundtrip(tmp_path: Path) -> None:
    """Metadata survives a save/load cycle."""
    img_path = tmp_path / "test.png"
    # Create a minimal 1×1 PNG
    Image.new("RGB", (1, 1), color=(255, 0, 0)).save(img_path, "PNG")

    meta = {"caption": "a test caption", "asset_type": "structure", "palette": "earthy palette"}
    embed_metadata_into_file(img_path, meta)

    result = read_metadata_from_file(img_path)
    assert result is not None
    assert result["caption"] == "a test caption"
    assert result["asset_type"] == "structure"
    assert result["palette"] == "earthy palette"


def test_read_metadata_returns_none_when_absent(tmp_path: Path) -> None:
    """An image with no embedded metadata returns None."""
    img_path = tmp_path / "clean.png"
    Image.new("RGB", (1, 1), color=(0, 255, 0)).save(img_path, "PNG")

    result = read_metadata_from_file(img_path)
    assert result is None


def test_embed_preserves_existing_text_chunks(tmp_path: Path) -> None:
    """Existing tEXt chunks are preserved when embedding new metadata."""
    img_path = tmp_path / "with_existing.png"
    im = Image.new("RGB", (1, 1), color=(0, 0, 255))
    from PIL.PngImagePlugin import PngInfo
    existing = PngInfo()
    existing.add_text("existing_key", "existing_value")
    im.save(img_path, "PNG", pnginfo=existing)

    embed_metadata_into_file(img_path, {"new": "data"})

    # Re-open and check both keys
    with Image.open(img_path) as reopened:
        assert reopened.info.get("existing_key") == "existing_value"
        raw_meta = reopened.info.get(META_KEY)
        assert raw_meta is not None
        assert json.loads(raw_meta) == {"new": "data"}


def test_embed_handles_unicode_metadata(tmp_path: Path) -> None:
    """Unicode characters in metadata survive roundtrip."""
    img_path = tmp_path / "unicode.png"
    Image.new("RGB", (1, 1), color=(128, 128, 128)).save(img_path, "PNG")

    meta = {"caption": "médiéval château élégant", "palette": "sépia fumé"}
    embed_metadata_into_file(img_path, meta)

    result = read_metadata_from_file(img_path)
    assert result is not None
    assert result["caption"] == "médiéval château élégant"
    assert result["palette"] == "sépia fumé"


def test_read_metadata_from_str_path(tmp_path: Path) -> None:
    """read_metadata_from_file accepts str paths as well as Path objects."""
    img_path = tmp_path / "str_test.png"
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(img_path, "PNG")
    embed_metadata_into_file(img_path, {"key": "value"})

    result = read_metadata_from_file(str(img_path))
    assert result == {"key": "value"}

"""Tests for prepare_dataset.py — metadata stripping and filename generation."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.generation.prepare_dataset import strip_png_metadata
from src.generation.image_metadata import embed_metadata_into_file, read_metadata_from_file


def test_strip_png_metadata_removes_chunks(tmp_path: Path) -> None:
    """strip_png_metadata produces a clean PNG with no generation_metadata."""
    src = tmp_path / "src.png"
    dest = tmp_path / "dest.png"

    # Create an image with embedded metadata
    Image.new("RGB", (1, 1), color=(255, 0, 0)).save(src, "PNG")
    embed_metadata_into_file(src, {"caption": "should be removed"})

    # Confirm metadata is present before stripping
    assert read_metadata_from_file(src) is not None

    strip_png_metadata(src, dest)

    # Destination should have no metadata
    assert read_metadata_from_file(dest) is None
    # Source should be untouched
    assert read_metadata_from_file(src) is not None


def test_strip_png_metadata_preserves_pixel_data(tmp_path: Path) -> None:
    """Pixels are byte-identical after metadata stripping."""
    src = tmp_path / "src.png"
    dest = tmp_path / "dest.png"

    # Create a recognizable test image (4×4 with a pattern)
    im = Image.new("RGB", (4, 4))
    pixels = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
        (255, 0, 255), (0, 255, 255), (128, 128, 128), (64, 64, 64),
        (200, 100, 50), (50, 200, 100), (100, 50, 200), (0, 0, 0),
        (255, 255, 255), (1, 2, 3), (250, 250, 0), (128, 0, 128),
    ]
    im.putdata(pixels)
    im.save(src, "PNG")

    # Embed metadata
    embed_metadata_into_file(src, {"caption": "pattern test", "asset_type": "structure"})

    # Strip and compare
    strip_png_metadata(src, dest)

    with Image.open(src) as src_im, Image.open(dest) as dest_im:
        assert list(src_im.getdata()) == list(dest_im.getdata())
        assert src_im.size == dest_im.size
        assert src_im.mode == dest_im.mode


def test_strip_png_metadata_handles_clean_image(tmp_path: Path) -> None:
    """Strip on an already-clean image is a no-op for pixels."""
    src = tmp_path / "src.png"
    dest = tmp_path / "dest.png"

    Image.new("RGB", (2, 2), color=(100, 150, 200)).save(src, "PNG")
    strip_png_metadata(src, dest)

    assert dest.exists()
    with Image.open(src) as src_im, Image.open(dest) as dest_im:
        assert list(src_im.getdata()) == list(dest_im.getdata())

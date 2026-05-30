"""Unit tests for background tile engine (src/tile/background_engine.py)."""

import pytest
from unittest.mock import AsyncMock, patch
from PIL import Image

from src.tile.background_models import BackgroundTileRequest
from src.tile.background_engine import (
    BackgroundTileEngine,
    StaticBackgroundTileEngine,
    _PlaceholderBackgroundTileEngine,
)


def _make_bg_tile_req(**overrides):
    defaults = {"tile_type": "grass", "seed": 42}
    defaults.update(overrides)
    return BackgroundTileRequest(**defaults)


class TestBackgroundTileEngine:
    """Tests for BackgroundTileEngine (comfyui mode)."""

    @pytest.mark.asyncio
    async def test_generate_grass(self, mock_comfyui_client, test_store, monkeypatch):
        """Returns a filename string for a grass tile."""
        monkeypatch.setattr("src.tile.background_engine.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (128, 128), (0, 255, 0, 255))

        engine = BackgroundTileEngine(mock_comfyui_client)
        req = _make_bg_tile_req(tile_type="grass")
        result = await engine.generate(req.tile_type, seed=req.seed)

        assert isinstance(result.filename, str)
        assert result.filename.endswith(".png")
        # Verify the image was saved to the store
        assert test_store.get_image_bytes(result.filename) is not None

    @pytest.mark.asyncio
    async def test_generate_water(self, mock_comfyui_client, test_store, monkeypatch):
        """Generates a water tile."""
        monkeypatch.setattr("src.tile.background_engine.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (128, 128), (0, 0, 255, 255))

        engine = BackgroundTileEngine(mock_comfyui_client)
        req = _make_bg_tile_req(tile_type="water")
        result = await engine.generate(req.tile_type, seed=req.seed)

        assert isinstance(result.filename, str)
        assert test_store.get_image_bytes(result.filename) is not None

    @pytest.mark.asyncio
    async def test_invalid_tile_type_rejected(self, mock_comfyui_client, test_store, monkeypatch):
        """Invalid tile_type raises ValueError."""
        monkeypatch.setattr("src.tile.background_engine.store", test_store)

        engine = BackgroundTileEngine(mock_comfyui_client)
        with pytest.raises(ValueError, match="Unknown tile_type"):
            await engine.generate("lava", seed=1)


class TestStaticBackgroundTileEngine:
    """Tests for StaticBackgroundTileEngine."""

    @pytest.mark.asyncio
    async def test_generate_static_falls_to_placeholder(self, test_store, monkeypatch):
        """When no static tile is available, falls back to placeholder."""
        monkeypatch.setattr("src.tile.background_engine.store", test_store)

        engine = StaticBackgroundTileEngine()
        result = await engine.generate("water", seed=1)

        assert isinstance(result.filename, str)
        assert result.filename.endswith(".png")
        assert test_store.get_image_bytes(result.filename) is not None


class TestPlaceholderBackgroundTileEngine:
    """Tests for _PlaceholderBackgroundTileEngine."""

    @pytest.mark.asyncio
    async def test_generate_placeholder(self, test_store, monkeypatch):
        """Placeholder engine generates a coloured rectangle."""
        monkeypatch.setattr("src.tile.background_engine.store", test_store)

        engine = _PlaceholderBackgroundTileEngine()
        result = await engine.generate("grass", seed=1)

        assert isinstance(result.filename, str)
        assert result.filename.endswith(".png")
        pil_img = test_store.get_image_pil(result.filename)
        assert pil_img is not None
        assert pil_img.size == (128, 128)
        assert pil_img.mode == "RGBA"

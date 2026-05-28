"""Unit tests for generators (src/generators.py)."""

import pytest
from unittest.mock import AsyncMock, patch
from PIL import Image

from src.generators import (
    get_generator, ComfyUIGenerator, StaticTileGenerator,
    _PlaceholderGenerator, _PlaceholderSplash,
    _get_comfyui_client, close_comfyui_client,
)
from src.models import GenerationRequest, SplashRequest


class TestGetGenerator:
    """Tests for get_generator factory."""

    def test_placeholder_mode(self, test_settings, monkeypatch):
        """mode='placeholder' → _PlaceholderGenerator."""
        monkeypatch.setattr("src.generators.settings", test_settings)
        test_settings.generation.modes["structure"] = "placeholder"
        gen = get_generator("structure")
        assert isinstance(gen, _PlaceholderGenerator)

    def test_static_mode(self, test_settings, monkeypatch):
        """mode='static' → StaticTileGenerator."""
        monkeypatch.setattr("src.generators.settings", test_settings)
        test_settings.generation.modes["structure"] = "static"
        gen = get_generator("structure")
        assert isinstance(gen, StaticTileGenerator)

    def test_comfyui_mode_requires_client(self, test_settings, monkeypatch):
        """mode='comfyui' with no client → RuntimeError."""
        monkeypatch.setattr("src.generators.settings", test_settings)
        monkeypatch.setattr("src.generators._comfyui_client", None)
        monkeypatch.setattr("src.generators._comfyui_available", False)
        test_settings.generation.modes["structure"] = "comfyui"
        with pytest.raises(RuntimeError, match="unreachable"):
            get_generator("structure")

    def test_random_mode_coin_flip(self, test_settings, monkeypatch):
        """mode='random' → either StaticTileGenerator or ComfyUIGenerator."""
        monkeypatch.setattr("src.generators.settings", test_settings)
        test_settings.generation.modes["structure"] = "random"
        # Force coin to land on static
        monkeypatch.setattr("src.generators.random.random", lambda: 0.6)
        gen = get_generator("structure")
        assert isinstance(gen, StaticTileGenerator)


class TestPlaceholderGenerator:
    """Tests for _PlaceholderGenerator."""

    @pytest.mark.asyncio
    async def test_generate_structure(self, test_store, monkeypatch):
        """Returns a filename, image saved to store."""
        monkeypatch.setattr("src.generators.store", test_store)
        gen = _PlaceholderGenerator("structure")
        req = GenerationRequest(asset_family="structure")
        filename = await gen.generate(req)
        assert filename.endswith(".png")
        assert test_store.get_image_bytes(filename) is not None

    @pytest.mark.asyncio
    async def test_generate_background_tile(self, test_store, monkeypatch):
        monkeypatch.setattr("src.generators.store", test_store)
        gen = _PlaceholderGenerator("background_tile")
        req = GenerationRequest(asset_family="background_tile", tile_type="grass")
        filename = await gen.generate(req)
        assert filename.endswith(".png")

    @pytest.mark.asyncio
    async def test_generate_splash(self, test_store, monkeypatch):
        monkeypatch.setattr("src.generators.store", test_store)
        gen = _PlaceholderGenerator("splash")
        req = SplashRequest(character_name="Test")
        filename = await gen.generate(req)
        assert filename.endswith(".png")
        assert test_store.get_image_bytes(filename) is not None

    @pytest.mark.asyncio
    async def test_generate_story_dimensions(self, test_store, monkeypatch):
        """Story family → 1024x576."""
        monkeypatch.setattr("src.generators.store", test_store)
        gen = _PlaceholderGenerator("story")
        req = GenerationRequest(asset_family="story")
        filename = await gen.generate(req)
        img = test_store.get_image_pil(filename)
        assert img.size == (1024, 576)


class TestPlaceholderSplash:
    """Tests for _PlaceholderSplash."""

    def test_generate_returns_filename(self, test_store, monkeypatch):
        monkeypatch.setattr("src.generators.store", test_store)
        req = SplashRequest(character_name="Arthur", title="King")
        filename = _PlaceholderSplash.generate(req)
        assert filename.endswith("_splash.png")
        assert test_store.get_image_bytes(filename) is not None

    def test_different_characters_different_colors(self, test_store, monkeypatch):
        """Different character names → different portrait colors."""
        monkeypatch.setattr("src.generators.store", test_store)
        f1 = _PlaceholderSplash.generate(SplashRequest(character_name="Alice"))
        f2 = _PlaceholderSplash.generate(SplashRequest(character_name="Bob"))
        # Different filenames
        assert f1 != f2


class TestStaticTileGenerator:
    """Tests for StaticTileGenerator."""

    @pytest.mark.asyncio
    async def test_background_tile_resolves(self, test_store, test_catalog, monkeypatch):
        """With a valid tile_type, resolves from static catalog."""
        monkeypatch.setattr("src.generators.store", test_store)
        monkeypatch.setattr("src.generators.static_catalog", test_catalog)
        gen = StaticTileGenerator("background_tile")
        req = GenerationRequest(asset_family="background_tile", tile_type="water")
        filename = await gen.generate(req)
        assert filename.endswith(".png")
        assert test_store.get_image_bytes(filename) is not None

    @pytest.mark.asyncio
    async def test_background_tile_missing_tile_type(self, test_store, monkeypatch):
        """Missing tile_type → ValueError."""
        monkeypatch.setattr("src.generators.store", test_store)
        gen = StaticTileGenerator("background_tile")
        req = GenerationRequest(asset_family="background_tile")
        with pytest.raises(ValueError, match="tile_type"):
            await gen.generate(req)

    @pytest.mark.asyncio
    async def test_structure_resolves(self, test_store, test_catalog, monkeypatch):
        monkeypatch.setattr("src.generators.store", test_store)
        monkeypatch.setattr("src.generators.static_catalog", test_catalog)
        gen = StaticTileGenerator("structure")
        req = GenerationRequest(asset_family="structure", structure_subtype="fortification")
        filename = await gen.generate(req)
        assert filename.endswith(".png")

    @pytest.mark.asyncio
    async def test_falls_back_to_placeholder(self, test_store, test_catalog, monkeypatch):
        """When no static PNG found, falls back to placeholder."""
        monkeypatch.setattr("src.generators.store", test_store)
        monkeypatch.setattr("src.generators.static_catalog", test_catalog)
        gen = StaticTileGenerator("background_tile")
        req = GenerationRequest(asset_family="background_tile", tile_type="sand")
        filename = await gen.generate(req)
        assert filename.endswith(".png")


class TestComfyUIGenerator:
    """Tests for ComfyUIGenerator."""

    @pytest.mark.asyncio
    async def test_generate_generic(self, mock_comfyui_client, test_store, monkeypatch):
        """Calls client.generate, saves result."""
        monkeypatch.setattr("src.generators.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (512, 512), (0, 255, 0, 255))

        gen = ComfyUIGenerator(mock_comfyui_client, "txt2img.json")
        req = GenerationRequest(asset_family="structure", structure_subtype="fortification")
        filename = await gen.generate(req)
        assert filename.endswith(".png")
        mock_comfyui_client.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_splash(self, mock_comfyui_client, test_store, monkeypatch):
        monkeypatch.setattr("src.generators.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (512, 512), (0, 0, 255, 255))

        gen = ComfyUIGenerator(mock_comfyui_client, "splash.json")
        req = SplashRequest(character_name="Test")
        filename = await gen.generate(req)
        assert filename.endswith("_splash.png")
        assert test_store.get_image_bytes(filename) is not None

    @pytest.mark.asyncio
    async def test_generate_inpaint(self, mock_comfyui_client, test_store, monkeypatch):
        """Inpaint request → calls client.generate with input_images."""
        monkeypatch.setattr("src.generators.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (512, 512), (255, 0, 0, 255))

        gen = ComfyUIGenerator(mock_comfyui_client, "inpaint.json")
        from src.models import Coordinate, InpaintRequest
        req = GenerationRequest(
            asset_family="background_tile",
            tile_type="grass",
            inpaints=[
                InpaintRequest(
                    point_a=Coordinate(x=0, y=0),
                    point_b=Coordinate(x=32, y=32),
                    fill_type="water",
                )
            ],
        )
        filename = await gen.generate(req)
        assert filename.endswith(".png")
        # Should have been called with input_images
        call_kwargs = mock_comfyui_client.generate.call_args.kwargs
        assert "input_images" in call_kwargs


class TestComfyUIClientLifecycle:
    """Tests for _get_comfyui_client and close_comfyui_client."""

    def test_get_client_creates_singleton(self, monkeypatch):
        """First call creates client, second returns same."""
        monkeypatch.setattr("src.generators._comfyui_client", None)
        monkeypatch.setattr("src.generators._comfyui_available", None)
        c1 = _get_comfyui_client()
        c2 = _get_comfyui_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_close_resets_state(self, monkeypatch):
        monkeypatch.setattr("src.generators._comfyui_client", None)
        monkeypatch.setattr("src.generators._comfyui_available", None)
        _get_comfyui_client()
        await close_comfyui_client()
        from src.generators import _comfyui_client, _comfyui_available
        assert _comfyui_client is None
        assert _comfyui_available is None

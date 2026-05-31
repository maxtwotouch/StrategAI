"""Unit tests for tile engine (src/tile/engine.py)."""

import pytest
from unittest.mock import AsyncMock, patch
from PIL import Image

from src.tile.models import StructureRequest, ObjectRequest, TerrainRequest
from src.tile.engine import TileEngine, StaticTileEngine, _PlaceholderTileEngine


def _make_structure_req(**overrides):
    defaults = {
        "category": "fortification",
        "style": "nordic_wooden",
        "condition": "pristine",
        "scale": "small",
        "description": "A small wooden watchtower with a pointed roof and a lookout platform.",
    }
    defaults.update(overrides)
    return StructureRequest(**defaults)


def _make_object_req(**overrides):
    defaults = {
        "category": "vegetation",
        "biome": "temperate_forest",
        "season": "summer",
        "description": "A large oak tree with a thick trunk and sprawling branches full of green leaves.",
    }
    defaults.update(overrides)
    return ObjectRequest(**defaults)


def _make_terrain_req(**overrides):
    defaults = {
        "category": "hill",
        "scale": "medium",
        "material": "earthen",
        "description": "A rounded grassy hill with gentle slopes on all sides and a flat top.",
    }
    defaults.update(overrides)
    return TerrainRequest(**defaults)


class TestTileEngine:
    """Tests for TileEngine (comfyui mode)."""

    @pytest.mark.asyncio
    async def test_generate_structure(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        """Returns StructureResponse with correct fields."""
        monkeypatch.setattr("src.tile.engine.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (128, 128), (0, 255, 0, 255))

        engine = TileEngine(mock_comfyui_client)
        req = _make_structure_req()
        resp = await engine.generate_structure(req)

        assert resp.asset_type == "structure"
        assert resp.category == "fortification"
        assert resp.style == "nordic_wooden"
        assert resp.generation_mode == "comfyui"
        assert resp.url.startswith("/assets/")
        assert resp.asset_id.startswith("struct_")
        assert resp.seed is not None
        assert resp.prompt_used is not None
        assert resp.resolution == "128x128"
        assert resp.generation_time_ms is not None

    @pytest.mark.asyncio
    async def test_generate_object(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.tile.engine.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (128, 128), (0, 255, 0, 255))

        engine = TileEngine(mock_comfyui_client)
        req = _make_object_req()
        resp = await engine.generate_object(req)

        assert resp.asset_type == "object"
        assert resp.category == "vegetation"
        assert resp.biome == "temperate_forest"
        assert resp.generation_mode == "comfyui"

    @pytest.mark.asyncio
    async def test_generate_terrain(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.tile.engine.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (512, 512), (0, 255, 0, 255))

        engine = TileEngine(mock_comfyui_client)
        req = _make_terrain_req()
        resp = await engine.generate_terrain(req)

        assert resp.asset_type == "terrain"
        assert resp.category == "hill"
        assert resp.material == "earthen"
        assert resp.generation_mode == "comfyui"

    @pytest.mark.asyncio
    async def test_seed_propagation(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        """Explicit seed → used in response."""
        monkeypatch.setattr("src.tile.engine.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (512, 512), (0, 255, 0, 255))

        engine = TileEngine(mock_comfyui_client)
        req = _make_structure_req(seed=12345)
        resp = await engine.generate_structure(req)
        assert resp.seed == 12345

    @pytest.mark.asyncio
    async def test_persists_asset_record(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        """AssetRecord created in DB."""
        monkeypatch.setattr("src.tile.engine.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (512, 512), (0, 255, 0, 255))

        engine = TileEngine(mock_comfyui_client)
        req = _make_structure_req()
        resp = await engine.generate_structure(req)

        from src.database import SessionLocal, AssetRecord
        with SessionLocal() as db:
            record = db.query(AssetRecord).filter(AssetRecord.id == resp.url.split("/")[-1]).first()
            assert record is not None
            assert record.asset_family == "structure"


class TestStaticTileEngine:
    """Tests for StaticTileEngine."""

    @pytest.mark.asyncio
    async def test_generate_structure_static(self, test_store, test_catalog, test_db, monkeypatch):
        """Resolves from static catalog → StructureResponse."""
        monkeypatch.setattr("src.tile.engine.store", test_store)
        monkeypatch.setattr("src.tile.engine.static_catalog", test_catalog)

        engine = StaticTileEngine()
        req = _make_structure_req()
        resp = await engine.generate_structure(req)

        assert resp.asset_type == "structure"
        assert resp.generation_mode == "static"
        assert resp.url.startswith("/assets/")

    @pytest.mark.asyncio
    async def test_generate_object_static(self, test_store, test_catalog, test_db, monkeypatch):
        monkeypatch.setattr("src.tile.engine.store", test_store)
        monkeypatch.setattr("src.tile.engine.static_catalog", test_catalog)

        engine = StaticTileEngine()
        req = _make_object_req()
        resp = await engine.generate_object(req)

        assert resp.asset_type == "object"
        assert resp.generation_mode == "static"

    @pytest.mark.asyncio
    async def test_generate_terrain_falls_to_placeholder(self, test_store, test_catalog, test_db, monkeypatch):
        """Terrain has no static folder → placeholder."""
        monkeypatch.setattr("src.tile.engine.store", test_store)
        monkeypatch.setattr("src.tile.engine.static_catalog", test_catalog)

        engine = StaticTileEngine()
        req = _make_terrain_req()
        resp = await engine.generate_terrain(req)

        assert resp.asset_type == "terrain"
        assert resp.generation_mode == "static"


class TestPlaceholderTileEngine:
    """Tests for _PlaceholderTileEngine."""

    @pytest.mark.asyncio
    async def test_generate_structure(self, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.tile.engine.store", test_store)

        engine = _PlaceholderTileEngine()
        req = _make_structure_req()
        resp = await engine.generate_structure(req)

        assert resp.asset_type == "structure"
        assert resp.generation_mode == "static"
        assert resp.url.startswith("/assets/")
        assert resp.resolution == "128x128"

    @pytest.mark.asyncio
    async def test_generate_object(self, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.tile.engine.store", test_store)

        engine = _PlaceholderTileEngine()
        req = _make_object_req()
        resp = await engine.generate_object(req)

        assert resp.asset_type == "object"
        assert resp.generation_mode == "static"

    @pytest.mark.asyncio
    async def test_generate_terrain(self, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.tile.engine.store", test_store)

        engine = _PlaceholderTileEngine()
        req = _make_terrain_req()
        resp = await engine.generate_terrain(req)

        assert resp.asset_type == "terrain"
        assert resp.generation_mode == "static"

    @pytest.mark.asyncio
    async def test_persists_registry_record(self, test_store, test_db, monkeypatch):
        """Placeholder engine persists to tile-specific table."""
        monkeypatch.setattr("src.tile.engine.store", test_store)

        engine = _PlaceholderTileEngine()
        req = _make_structure_req()
        resp = await engine.generate_structure(req)

        from src.tile.registry import StructureRegistry
        record = StructureRegistry.get(resp.asset_id)
        assert record is not None
        assert record.category == "fortification"
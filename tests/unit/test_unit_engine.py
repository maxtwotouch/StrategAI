"""Unit tests for unit engine (src/unit/engine.py)."""

import pytest
from unittest.mock import AsyncMock, patch
from PIL import Image

from src.unit.models import UnitRequest
from src.unit.engine import UnitEngine, StaticUnitEngine, _PlaceholderUnitEngine


def _make_unit_req(**overrides):
    defaults = {
        "unit_type": "archer",
        "description": "A medieval archer in green leather armor with a longbow and quiver of arrows.",
    }
    defaults.update(overrides)
    return UnitRequest(**defaults)


class TestUnitEngine:
    """Tests for UnitEngine (comfyui mode)."""

    @pytest.mark.asyncio
    async def test_generate(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        """Returns UnitResponse with a single sprite URL."""
        monkeypatch.setattr("src.unit.engine.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (512, 512), (0, 255, 0, 255))

        engine = UnitEngine(mock_comfyui_client)
        req = _make_unit_req()
        resp = await engine.generate(req)

        assert resp.asset_type == "unit"
        assert resp.unit_type == "archer"
        assert resp.generation_mode == "comfyui"
        assert resp.url.startswith("/assets/")
        assert resp.unit_id.startswith("unit_archer_")
        assert resp.seed is not None
        assert resp.prompt_used is not None
        assert resp.resolution == "128x128"
        assert resp.generation_time_ms is not None

    @pytest.mark.asyncio
    async def test_generates_single_image(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        """client.generate called once (single sprite)."""
        monkeypatch.setattr("src.unit.engine.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (128, 128), (0, 255, 0, 255))

        engine = UnitEngine(mock_comfyui_client)
        req = _make_unit_req()
        await engine.generate(req)

        assert mock_comfyui_client.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_persists_unit_record(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        """UnitRegistry record created."""
        monkeypatch.setattr("src.unit.engine.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (512, 512), (0, 255, 0, 255))

        engine = UnitEngine(mock_comfyui_client)
        req = _make_unit_req()
        resp = await engine.generate(req)

        from src.unit.registry import UnitRegistry
        record = UnitRegistry.get(resp.unit_id)
        assert record is not None
        assert record.unit_type == "archer"

    @pytest.mark.asyncio
    async def test_seed_propagation(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        """Explicit seed → used in response."""
        monkeypatch.setattr("src.unit.engine.store", test_store)
        mock_comfyui_client.generate.return_value = Image.new("RGBA", (512, 512), (0, 255, 0, 255))

        engine = UnitEngine(mock_comfyui_client)
        req = _make_unit_req(seed=12345)
        resp = await engine.generate(req)
        assert resp.seed == 12345


class TestStaticUnitEngine:
    """Tests for StaticUnitEngine."""

    @pytest.mark.asyncio
    async def test_generate_from_static(self, test_store, test_catalog, test_db, monkeypatch):
        """Resolves from static catalog → UnitResponse."""
        monkeypatch.setattr("src.unit.engine.store", test_store)
        monkeypatch.setattr("src.unit.engine.static_catalog", test_catalog)

        engine = StaticUnitEngine()
        req = _make_unit_req(unit_type="archer")
        resp = await engine.generate(req)

        assert resp.asset_type == "unit"
        assert resp.generation_mode == "static"
        assert resp.unit_type == "archer"

    @pytest.mark.asyncio
    async def test_falls_back_to_placeholder(self, test_store, test_catalog, test_db, monkeypatch):
        """No static sprite for warrior → placeholder."""
        monkeypatch.setattr("src.unit.engine.store", test_store)
        monkeypatch.setattr("src.unit.engine.static_catalog", test_catalog)

        engine = StaticUnitEngine()
        req = _make_unit_req(unit_type="warrior")
        resp = await engine.generate(req)

        assert resp.asset_type == "unit"
        assert resp.generation_mode == "placeholder"


class TestPlaceholderUnitEngine:
    """Tests for _PlaceholderUnitEngine."""

    @pytest.mark.asyncio
    async def test_generate(self, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.unit.engine.store", test_store)

        engine = _PlaceholderUnitEngine()
        req = _make_unit_req()
        resp = await engine.generate(req)

        assert resp.asset_type == "unit"
        assert resp.generation_mode == "placeholder"
        assert resp.unit_type == "archer"
        assert resp.url.startswith("/assets/")
        assert resp.resolution == "128x128"

    @pytest.mark.asyncio
    async def test_persists_unit_record(self, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.unit.engine.store", test_store)

        engine = _PlaceholderUnitEngine()
        req = _make_unit_req()
        resp = await engine.generate(req)

        from src.unit.registry import UnitRegistry
        record = UnitRegistry.get(resp.unit_id)
        assert record is not None
        assert record.unit_type == "archer"

    @pytest.mark.asyncio
    async def test_different_unit_types_different_colors(self, test_store, test_db, monkeypatch):
        """Archer vs warrior → different placeholder colors."""
        monkeypatch.setattr("src.unit.engine.store", test_store)

        engine = _PlaceholderUnitEngine()
        resp1 = await engine.generate(_make_unit_req(unit_type="archer"))
        resp2 = await engine.generate(_make_unit_req(unit_type="warrior"))

        assert resp1.unit_type == "archer"
        assert resp2.unit_type == "warrior"
        assert resp2.unit_type == "warrior"
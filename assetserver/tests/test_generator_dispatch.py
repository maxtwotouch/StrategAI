"""
Generator factory dispatch tests — Phase D.1

Verifies correct engine selection based on generation mode (comfyui vs. static
vs. placeholder) for each asset family.  Tests that the dispatch logic (e.g.,
LeaderEngine vs. StaticLeaderEngine) routes to the correct handler.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.leader.engine import LeaderEngine, StaticLeaderEngine
from src.leader.models import LeaderRequest
from src.tile.engine import TileEngine, StaticTileEngine
from src.tile.background_engine import BackgroundTileEngine, StaticBackgroundTileEngine, BackgroundTileResult
from src.unit.engine import UnitEngine, StaticUnitEngine
from src.tile.models import StructureRequest, ObjectRequest, TerrainRequest
from src.unit.models import UnitRequest


# ===========================================================================
#  Leader Engine Dispatch
# ===========================================================================


class TestLeaderEngineDispatch:
    """Tests for LeaderEngine.generate() routing to correct handler."""

    def test_splash_routes_to_generate_splash(self):
        """asset_type='splash' calls _generate_splash."""
        mock_client = AsyncMock()
        engine = LeaderEngine(mock_client)

        # Patch _generate_splash directly
        mock_splash = AsyncMock()
        mock_splash.return_value = MagicMock()
        engine._generate_splash = mock_splash
        engine._generate_profile = AsyncMock()
        engine._generate_action = AsyncMock()

        req = LeaderRequest(
            asset_type="splash",
            leader_name="Test",
            leader_description="A test leader with a commanding presence and golden armor for a RPG game.",
            archetype="warrior_king",
            culture="medieval_european",
            time_of_day="midday",
            mood="triumphant",
        )

        import asyncio
        asyncio.run(engine.generate(req))

        mock_splash.assert_called_once_with(req)

    def test_profile_routes_to_generate_profile(self):
        """asset_type='profile' calls _generate_profile."""
        mock_client = AsyncMock()
        engine = LeaderEngine(mock_client)

        mock_profile = AsyncMock()
        mock_profile.return_value = MagicMock()
        engine._generate_profile = mock_profile
        engine._generate_splash = AsyncMock()
        engine._generate_action = AsyncMock()

        req = LeaderRequest(
            asset_type="profile",
            leader_name="Test",
            leader_description="A test leader with a commanding presence and golden armor.",
            archetype="warrior_king",
            culture="medieval_european",
            time_of_day="midday",
            mood="triumphant",
            leader_id="leader_test_abc123",
        )

        import asyncio
        asyncio.run(engine.generate(req))

        mock_profile.assert_called_once_with(req)

    def test_action_routes_to_generate_action(self):
        """asset_type='action' calls _generate_action."""
        mock_client = AsyncMock()
        engine = LeaderEngine(mock_client)

        mock_action = AsyncMock()
        mock_action.return_value = MagicMock()
        engine._generate_action = mock_action
        engine._generate_splash = AsyncMock()
        engine._generate_profile = AsyncMock()

        req = LeaderRequest(
            asset_type="action",
            leader_name="Test",
            leader_description="A test leader with a commanding presence and golden armor.",
            archetype="warrior_king",
            culture="medieval_european",
            time_of_day="midday",
            mood="triumphant",
            leader_id="leader_test_abc123",
            action_category="military",
            action_description="Leading troops into battle.",
        )

        import asyncio
        asyncio.run(engine.generate(req))

        mock_action.assert_called_once_with(req)

    def test_invalid_asset_type_validated_by_pydantic(self):
        """Pydantic validates asset_type — unknown values fail at model level."""
        # The LeaderRequest model has a Literal type for asset_type
        # So invalid values fail before reaching the engine
        with pytest.raises(Exception):  # Pydantic ValidationError
            LeaderRequest(
                asset_type="unknown_type",  # type: ignore[arg-type]
                leader_name="Test",
                leader_description="A test leader with a commanding presence and golden armor for a RPG.",
                archetype="warrior_king",
                culture="medieval_european",
                time_of_day="midday",
                mood="triumphant",
            )


class TestStaticLeaderEngineDispatch:
    """Tests for StaticLeaderEngine.generate() routing."""

    def test_static_engine_splash_calls_generate_splash(self):
        """StaticLeaderEngine routes splash requests correctly."""
        engine = StaticLeaderEngine()

        mock_splash = AsyncMock()
        mock_splash.return_value = MagicMock()
        engine._generate_splash = mock_splash

        req = LeaderRequest(
            asset_type="splash",
            leader_name="Test Static",
            leader_description="A test static leader with a commanding presence and golden armor for RPG game.",
            archetype="warrior_king",
            culture="medieval_european",
            time_of_day="midday",
            mood="triumphant",
        )

        import asyncio
        asyncio.run(engine.generate(req))

        mock_splash.assert_called_once_with(req)

    def test_static_engine_profile_calls_generate_profile(self):
        """StaticLeaderEngine routes profile requests correctly."""
        engine = StaticLeaderEngine()

        mock_profile = AsyncMock()
        mock_profile.return_value = MagicMock()
        engine._generate_profile = mock_profile

        req = LeaderRequest(
            asset_type="profile",
            leader_name="Test Static",
            leader_description="A test static leader with a commanding presence and golden armor.",
            archetype="warrior_king",
            culture="medieval_european",
            time_of_day="midday",
            mood="triumphant",
            leader_id="leader_test_static_abc123",
        )

        import asyncio
        asyncio.run(engine.generate(req))

        mock_profile.assert_called_once_with(req)

    def test_static_engine_action_calls_generate_action(self):
        """StaticLeaderEngine routes action requests."""
        engine = StaticLeaderEngine()

        mock_action = AsyncMock()
        mock_action.return_value = MagicMock()
        engine._generate_action = mock_action

        req = LeaderRequest(
            asset_type="action",
            leader_name="Test Static",
            leader_description="A test static leader with a commanding presence and golden armor.",
            archetype="warrior_king",
            culture="medieval_european",
            time_of_day="midday",
            mood="triumphant",
            leader_id="leader_test_static_abc123",
            action_category="military",
            action_description="Leading troops into battle.",
        )

        import asyncio
        asyncio.run(engine.generate(req))

        mock_action.assert_called_once_with(req)


# ===========================================================================
#  Tile Engine Dispatch
# ===========================================================================


class TestTileEngineDispatch:
    """Tests for TileEngine per-family generate methods."""

    def test_tile_engine_instantiates_with_client(self):
        """TileEngine requires a ComfyUIClient."""
        mock_client = AsyncMock()
        engine = TileEngine(mock_client)
        assert engine is not None

    def test_tile_engine_has_generate_structure(self):
        """TileEngine has generate_structure method."""
        mock_client = AsyncMock()
        engine = TileEngine(mock_client)
        assert hasattr(engine, "generate_structure")
        assert callable(engine.generate_structure)

    def test_tile_engine_has_generate_object(self):
        """TileEngine has generate_object method."""
        mock_client = AsyncMock()
        engine = TileEngine(mock_client)
        assert hasattr(engine, "generate_object")

    def test_tile_engine_has_generate_terrain(self):
        """TileEngine has generate_terrain method."""
        mock_client = AsyncMock()
        engine = TileEngine(mock_client)
        assert hasattr(engine, "generate_terrain")


class TestStaticTileEngine:
    """Tests for StaticTileEngine (placeholder mode)."""

    @pytest.mark.asyncio
    async def test_static_tile_engine_returns_structure(self, test_db, test_store, monkeypatch):
        """StaticTileEngine.generate_structure() returns a valid StructureResponse."""
        monkeypatch.setattr("src.tile.engine.store", test_store)
        engine = StaticTileEngine()

        req = StructureRequest(
            category="fortification",
            style="nordic_wooden",
            condition="pristine",
            scale="small",
            description="A small wooden watchtower with a pointed roof and a lookout platform.",
        )

        result = await engine.generate_structure(req)

        assert result.asset_type == "structure"
        assert result.category == "fortification"
        assert result.url.startswith("/assets/")
        assert result.asset_id.startswith("struct_")
        assert result.generation_mode == "static"
        assert result.seed > 0

    @pytest.mark.asyncio
    async def test_static_tile_engine_returns_object(self, test_db, test_store, monkeypatch):
        """StaticTileEngine.generate_object() returns a valid ObjectResponse."""
        monkeypatch.setattr("src.tile.engine.store", test_store)
        engine = StaticTileEngine()

        req = ObjectRequest(
            category="vegetation",
            biome="temperate_forest",
            season="summer",
            description="A large oak tree with a thick trunk and sprawling branches full of green leaves.",
        )

        result = await engine.generate_object(req)

        assert result.asset_type == "object"
        assert result.category == "vegetation"
        assert result.generation_mode == "static"
        assert result.seed > 0


# ===========================================================================
#  Background Tile Engine
# ===========================================================================


class TestBackgroundTileEngineDispatch:
    """Tests for BackgroundTileEngine dispatch."""

    def test_background_tile_engine_requires_client(self):
        """BackgroundTileEngine requires a ComfyUIClient."""
        with pytest.raises(TypeError):
            BackgroundTileEngine()  # missing client arg


class TestStaticBackgroundTileEngine:
    """Tests for StaticBackgroundTileEngine."""

    def test_static_background_tile_generates(self, test_db, test_store, monkeypatch):
        """StaticBackgroundTileEngine.generate() returns a valid result."""
        monkeypatch.setattr("src.tile.background_engine.store", test_store)
        engine = StaticBackgroundTileEngine()

        import asyncio
        result = asyncio.run(engine.generate("grass"))

        assert result.filename.endswith(".png")
        assert result.bg_tile_id.startswith("bg_grass_")
        assert result.seed > 0
        assert result.generation_mode == "static"
        assert result.prompt_used is not None
        assert result.elapsed_ms is not None

    def test_static_background_tile_different_types(self, test_db, test_store, monkeypatch):
        """StaticBackgroundTileEngine accepts all valid tile types."""
        monkeypatch.setattr("src.tile.background_engine.store", test_store)
        engine = StaticBackgroundTileEngine()

        for tile_type in ["water", "grass", "sand", "stone", "dirt"]:
            import asyncio
            result = asyncio.run(engine.generate(tile_type))
            assert result.bg_tile_id.startswith(f"bg_{tile_type}_")
            assert result.filename.endswith(".png")
            assert result.seed > 0


class TestUnitEngineDispatch:
    """Tests for UnitEngine."""

    def test_unit_engine_has_generate(self):
        """UnitEngine has a generate method."""
        mock_client = AsyncMock()
        engine = UnitEngine(mock_client)
        assert hasattr(engine, "generate")
        assert callable(engine.generate)


class TestStaticUnitEngine:
    """Tests for StaticUnitEngine."""

    def test_static_unit_engine_generates(self, test_db, test_store, monkeypatch):
        """StaticUnitEngine returns a valid UnitResponse."""
        monkeypatch.setattr("src.unit.engine.store", test_store)
        engine = StaticUnitEngine()

        req = UnitRequest(
            unit_type="archer",
            description="A medieval archer in green leather armor with a longbow and quiver of arrows.",
        )

        import asyncio
        result = asyncio.run(engine.generate(req))

        assert result.asset_type == "unit"
        assert result.unit_type == "archer"
        assert result.url.startswith("/assets/")
        assert result.unit_id.startswith("unit_archer_")
        assert result.generation_mode == "static"
        assert result.seed > 0

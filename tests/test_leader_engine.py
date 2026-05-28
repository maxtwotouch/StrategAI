"""Unit tests for leader engine (src/leader_engine.py)."""

import os
import pytest
from unittest.mock import AsyncMock, patch
from PIL import Image

from src.leader_models import LeaderRequest
from src.leader_engine import LeaderEngine, StaticLeaderEngine


def _make_leader_req(asset_type="splash", **overrides):
    defaults = {
        "asset_type": asset_type,
        "leader_name": "Cleopatra VII",
        "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
        "archetype": "warrior_queen",
        "culture": "ancient_egyptian",
        "time_of_day": "golden_hour",
        "mood": "triumphant",
    }
    if asset_type == "action":
        defaults["leader_id"] = "leader_test_a1b2c3"
        defaults["action_category"] = "military"
        defaults["action_description"] = "Leading troops into battle with sword raised high."
    defaults.update(overrides)
    return LeaderRequest(**defaults)


class TestLeaderEngineSplash:
    """Tests for LeaderEngine._generate_splash."""

    @pytest.mark.asyncio
    async def test_generate_splash(self, mock_comfyui_client, test_store, test_db, tmp_project_root, monkeypatch):
        """Returns LeaderResponse with correct fields."""
        monkeypatch.setattr("src.leader_engine.store", test_store)
        monkeypatch.setattr("src.leader_engine.BASE_DIR", tmp_project_root)
        # Ensure directories exist
        os.makedirs(os.path.join(tmp_project_root, "leader_references"), exist_ok=True)
        os.makedirs(os.path.join(tmp_project_root, "generated_assets"), exist_ok=True)
        monkeypatch.setattr("src.leader_engine.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader_engine.settings.paths.leader_reference_dir", "leader_references")
        monkeypatch.setattr("src.leader_registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader_registry.settings.paths.leader_reference_dir", "leader_references")
        monkeypatch.setattr("src.leader_registry.BASE_DIR", tmp_project_root)

        mock_comfyui_client.generate.return_value = Image.new("RGBA", (1920, 1088), (0, 255, 0, 255))

        engine = LeaderEngine(mock_comfyui_client)
        req = _make_leader_req("splash")
        resp = await engine.generate(req)

        assert resp.asset_type == "splash"
        assert resp.leader_name == "Cleopatra VII"
        assert resp.leader_id.startswith("leader_cleopatra_vii_")
        assert resp.generation_mode == "comfyui"
        assert resp.url.startswith("/assets/")
        assert resp.seed is not None
        assert resp.prompt_used is not None
        assert resp.resolution == "1920x1088"
        assert resp.generation_time_ms is not None

    @pytest.mark.asyncio
    async def test_registers_leader(self, mock_comfyui_client, test_store, test_db, tmp_project_root, monkeypatch):
        """LeaderRegistry.register called, leader exists after."""
        monkeypatch.setattr("src.leader_engine.store", test_store)
        monkeypatch.setattr("src.leader_engine.BASE_DIR", tmp_project_root)
        os.makedirs(os.path.join(tmp_project_root, "leader_references"), exist_ok=True)
        os.makedirs(os.path.join(tmp_project_root, "generated_assets"), exist_ok=True)
        monkeypatch.setattr("src.leader_engine.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader_engine.settings.paths.leader_reference_dir", "leader_references")
        monkeypatch.setattr("src.leader_registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader_registry.settings.paths.leader_reference_dir", "leader_references")
        monkeypatch.setattr("src.leader_registry.BASE_DIR", tmp_project_root)

        mock_comfyui_client.generate.return_value = Image.new("RGBA", (1920, 1088), (0, 255, 0, 255))

        engine = LeaderEngine(mock_comfyui_client)
        req = _make_leader_req("splash")
        resp = await engine.generate(req)

        from src.leader_registry import LeaderRegistry
        record = LeaderRegistry.get(resp.leader_id)
        assert record is not None
        assert record.leader_name == "Cleopatra VII"


class TestLeaderEngineProfile:
    """Tests for LeaderEngine._generate_profile."""

    @pytest.mark.asyncio
    async def test_profile_requires_leader_id(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        """Missing leader_id → ValueError."""
        monkeypatch.setattr("src.leader_engine.store", test_store)
        engine = LeaderEngine(mock_comfyui_client)
        req = _make_leader_req("profile", leader_id=None)
        with pytest.raises(ValueError, match="leader_id"):
            await engine.generate(req)

    @pytest.mark.asyncio
    async def test_profile_leader_not_found(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        """Nonexistent leader_id → ValueError."""
        monkeypatch.setattr("src.leader_engine.store", test_store)
        engine = LeaderEngine(mock_comfyui_client)
        req = _make_leader_req("profile", leader_id="nonexistent")
        with pytest.raises(ValueError, match="not found"):
            await engine.generate(req)


class TestLeaderEngineAction:
    """Tests for LeaderEngine._generate_action."""

    @pytest.mark.asyncio
    async def test_action_requires_leader_id(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.leader_engine.store", test_store)
        engine = LeaderEngine(mock_comfyui_client)
        req = _make_leader_req("action", leader_id=None)
        with pytest.raises(ValueError, match="leader_id"):
            await engine.generate(req)

    @pytest.mark.asyncio
    async def test_action_requires_category(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.leader_engine.store", test_store)
        engine = LeaderEngine(mock_comfyui_client)
        req = _make_leader_req("action", action_category=None)
        with pytest.raises(ValueError, match="action_category"):
            await engine.generate(req)

    @pytest.mark.asyncio
    async def test_action_requires_description(self, mock_comfyui_client, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.leader_engine.store", test_store)
        engine = LeaderEngine(mock_comfyui_client)
        req = _make_leader_req("action", action_description=None)
        with pytest.raises(ValueError, match="action_description"):
            await engine.generate(req)


class TestStaticLeaderEngine:
    """Tests for StaticLeaderEngine."""

    @pytest.mark.asyncio
    async def test_generate_splash(self, test_store, test_db, tmp_project_root, monkeypatch):
        """Returns LeaderResponse with generation_mode='static'."""
        monkeypatch.setattr("src.leader_engine.store", test_store)
        monkeypatch.setattr("src.leader_engine.BASE_DIR", tmp_project_root)
        os.makedirs(os.path.join(tmp_project_root, "leader_references"), exist_ok=True)
        os.makedirs(os.path.join(tmp_project_root, "generated_assets"), exist_ok=True)
        monkeypatch.setattr("src.leader_engine.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader_engine.settings.paths.leader_reference_dir", "leader_references")
        monkeypatch.setattr("src.leader_registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader_registry.settings.paths.leader_reference_dir", "leader_references")
        monkeypatch.setattr("src.leader_registry.BASE_DIR", tmp_project_root)

        engine = StaticLeaderEngine()
        req = _make_leader_req("splash")
        resp = await engine.generate(req)

        assert resp.asset_type == "splash"
        assert resp.generation_mode == "static"
        assert resp.leader_id.startswith("leader_cleopatra_vii_")
        assert resp.resolution == "1920x1088"

    @pytest.mark.asyncio
    async def test_generate_profile(self, test_store, test_db, tmp_project_root, monkeypatch):
        """Profile after splash → works."""
        monkeypatch.setattr("src.leader_engine.store", test_store)
        monkeypatch.setattr("src.leader_engine.BASE_DIR", tmp_project_root)
        os.makedirs(os.path.join(tmp_project_root, "leader_references"), exist_ok=True)
        os.makedirs(os.path.join(tmp_project_root, "generated_assets"), exist_ok=True)
        monkeypatch.setattr("src.leader_engine.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader_engine.settings.paths.leader_reference_dir", "leader_references")
        monkeypatch.setattr("src.leader_registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader_registry.settings.paths.leader_reference_dir", "leader_references")
        monkeypatch.setattr("src.leader_registry.BASE_DIR", tmp_project_root)

        engine = StaticLeaderEngine()
        # First generate splash
        splash_req = _make_leader_req("splash")
        splash_resp = await engine.generate(splash_req)

        # Then generate profile
        profile_req = _make_leader_req("profile", leader_id=splash_resp.leader_id)
        profile_resp = await engine.generate(profile_req)

        assert profile_resp.asset_type == "profile"
        assert profile_resp.generation_mode == "static"
        assert profile_resp.leader_id == splash_resp.leader_id

    @pytest.mark.asyncio
    async def test_generate_action(self, test_store, test_db, tmp_project_root, monkeypatch):
        """Action after splash → works."""
        monkeypatch.setattr("src.leader_engine.store", test_store)
        monkeypatch.setattr("src.leader_engine.BASE_DIR", tmp_project_root)
        os.makedirs(os.path.join(tmp_project_root, "leader_references"), exist_ok=True)
        os.makedirs(os.path.join(tmp_project_root, "generated_assets"), exist_ok=True)
        monkeypatch.setattr("src.leader_engine.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader_engine.settings.paths.leader_reference_dir", "leader_references")
        monkeypatch.setattr("src.leader_registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader_registry.settings.paths.leader_reference_dir", "leader_references")
        monkeypatch.setattr("src.leader_registry.BASE_DIR", tmp_project_root)

        engine = StaticLeaderEngine()
        splash_req = _make_leader_req("splash")
        splash_resp = await engine.generate(splash_req)

        action_req = _make_leader_req(
            "action",
            leader_id=splash_resp.leader_id,
            action_category="military",
            action_description="Leading troops into battle.",
        )
        action_resp = await engine.generate(action_req)

        assert action_resp.asset_type == "action"
        assert action_resp.generation_mode == "static"

    @pytest.mark.asyncio
    async def test_profile_requires_leader_id(self, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.leader_engine.store", test_store)
        engine = StaticLeaderEngine()
        req = _make_leader_req("profile", leader_id=None)
        with pytest.raises(ValueError, match="leader_id"):
            await engine.generate(req)

    @pytest.mark.asyncio
    async def test_action_requires_leader_id(self, test_store, test_db, monkeypatch):
        monkeypatch.setattr("src.leader_engine.store", test_store)
        engine = StaticLeaderEngine()
        req = _make_leader_req("action", leader_id=None)
        with pytest.raises(ValueError, match="leader_id"):
            await engine.generate(req)


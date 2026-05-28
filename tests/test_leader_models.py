"""Unit tests for leader models (src/leader_models.py)."""

import pytest
from pydantic import ValidationError
from src.leader_models import (
    LeaderRequest, LeaderResponse, LeaderInfo,
    LeaderAssetType, Archetype, Culture, TimeOfDay, Mood, ActionCategory,
)


class TestLeaderRequest:
    """Tests for LeaderRequest validation."""

    def test_splash_valid(self):
        """asset_type='splash' without leader_id → valid."""
        req = LeaderRequest(
            asset_type="splash",
            leader_name="Cleopatra VII",
            leader_description="A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress.",
            archetype="warrior_queen",
            culture="ancient_egyptian",
            time_of_day="golden_hour",
            mood="triumphant",
        )
        assert req.asset_type == "splash"
        assert req.leader_id is None

    def test_profile_without_leader_id(self):
        """asset_type='profile' without leader_id → valid at schema level (enforced at engine)."""
        req = LeaderRequest(
            asset_type="profile",
            leader_name="Cleopatra VII",
            leader_description="A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress.",
            archetype="warrior_queen",
            culture="ancient_egyptian",
            time_of_day="golden_hour",
            mood="triumphant",
        )
        assert req.asset_type == "profile"

    def test_action_requires_category(self):
        """asset_type='action' with action_category → valid."""
        req = LeaderRequest(
            asset_type="action",
            leader_name="Cleopatra VII",
            leader_description="A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress.",
            archetype="warrior_queen",
            culture="ancient_egyptian",
            time_of_day="golden_hour",
            mood="triumphant",
            leader_id="leader_cleopatra_vii_a1b2c3",
            action_category="military",
            action_description="Leading troops into battle.",
        )
        assert req.action_category == "military"

    def test_invalid_asset_type(self):
        """Unknown asset_type → ValidationError."""
        with pytest.raises(ValidationError):
            LeaderRequest(
                asset_type="invalid",
                leader_name="Test",
                leader_description="A test leader with enough characters to pass the minimum length requirement of fifty.",
                archetype="warrior_queen",
                culture="ancient_egyptian",
                time_of_day="dawn",
                mood="triumphant",
            )

    def test_leader_description_too_short(self):
        """Description < 50 chars → ValidationError."""
        with pytest.raises(ValidationError):
            LeaderRequest(
                asset_type="splash",
                leader_name="Test",
                leader_description="Too short",
                archetype="warrior_queen",
                culture="ancient_egyptian",
                time_of_day="dawn",
                mood="triumphant",
            )

    def test_leader_description_too_long(self):
        """Description > 800 chars → ValidationError."""
        with pytest.raises(ValidationError):
            LeaderRequest(
                asset_type="splash",
                leader_name="Test",
                leader_description="x" * 801,
                archetype="warrior_queen",
                culture="ancient_egyptian",
                time_of_day="dawn",
                mood="triumphant",
            )

    def test_leader_name_too_long(self):
        """Name > 100 chars → ValidationError."""
        with pytest.raises(ValidationError):
            LeaderRequest(
                asset_type="splash",
                leader_name="x" * 101,
                leader_description="A test leader with enough characters to pass the minimum length requirement of fifty characters total.",
                archetype="warrior_queen",
                culture="ancient_egyptian",
                time_of_day="dawn",
                mood="triumphant",
            )

    def test_action_description_too_long(self):
        """action_description > 800 chars → ValidationError."""
        with pytest.raises(ValidationError):
            LeaderRequest(
                asset_type="action",
                leader_name="Test",
                leader_description="A test leader with enough characters to pass the minimum length requirement of fifty characters total.",
                archetype="warrior_queen",
                culture="ancient_egyptian",
                time_of_day="dawn",
                mood="triumphant",
                leader_id="leader_test_a1b2c3",
                action_category="military",
                action_description="x" * 801,
            )

    def test_seed_optional(self):
        """Missing seed → valid."""
        req = LeaderRequest(
            asset_type="splash",
            leader_name="Test",
            leader_description="A test leader with enough characters to pass the minimum length requirement of fifty.",
            archetype="warrior_queen",
            culture="ancient_egyptian",
            time_of_day="dawn",
            mood="triumphant",
        )
        assert req.seed is None


class TestLeaderResponse:
    """Tests for LeaderResponse construction."""

    def test_construction(self):
        resp = LeaderResponse(
            url="/assets/test.png",
            asset_type="splash",
            leader_name="Cleopatra VII",
            leader_id="leader_cleopatra_vii_a1b2c3",
            seed=42,
            generation_mode="placeholder",
        )
        assert resp.status == "completed"
        assert resp.leader_name == "Cleopatra VII"


class TestLeaderInfo:
    """Tests for LeaderInfo construction."""

    def test_construction(self):
        info = LeaderInfo(
            leader_id="leader_test_a1b2c3",
            leader_name="Test",
            archetype="warrior_queen",
            culture="ancient_egyptian",
            splash_url="/assets/splash.png",
            action_urls=["/assets/action1.png"],
        )
        assert info.leader_id == "leader_test_a1b2c3"
        assert len(info.action_urls) == 1


class TestEnums:
    """Verify enum sets are complete."""

    def test_archetype_all(self):
        assert len(Archetype.ALL) == 8

    def test_culture_all(self):
        assert len(Culture.ALL) == 12

    def test_time_of_day_all(self):
        assert len(TimeOfDay.ALL) == 6

    def test_mood_all(self):
        assert len(Mood.ALL) == 8

    def test_action_category_all(self):
        assert len(ActionCategory.ALL) == 7


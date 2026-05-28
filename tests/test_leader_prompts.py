"""Unit tests for leader prompts (src/leader_prompts.py)."""

import pytest
from src.leader_models import LeaderRequest
from src.leader_prompts import (
    build_splash_prompt, build_profile_prompt, build_action_prompt, build_prompt,
    SPLASH_TAIL, PROFILE_TAIL, ACTION_TAIL,
    ARCHETYPE, CULTURE, TIME_OF_DAY, MOOD, ACTION_CATEGORY,
)


def _make_leader_req(asset_type="splash", **overrides):
    """Helper to create a valid LeaderRequest with minimal defaults."""
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


class TestBuildSplashPrompt:
    """Tests for build_splash_prompt."""

    def test_contains_all_enums(self):
        """Output contains archetype prose, culture prose, time_of_day prose, mood prose, SPLASH_TAIL."""
        req = _make_leader_req("splash")
        prompt = build_splash_prompt(req)
        assert "standing proudly" in prompt  # archetype prose
        assert "sandstone temple" in prompt  # culture prose
        assert "golden sunlight" in prompt  # time_of_day prose
        assert "hard-won victory" in prompt  # mood prose
        assert SPLASH_TAIL in prompt

    def test_ends_with_tail(self):
        """Final comma-separated segment matches SPLASH_TAIL."""
        req = _make_leader_req("splash")
        prompt = build_splash_prompt(req)
        assert prompt.endswith(SPLASH_TAIL)

    def test_leader_description_included(self):
        """The leader_description field appears verbatim."""
        req = _make_leader_req("splash")
        prompt = build_splash_prompt(req)
        assert req.leader_description.strip() in prompt


class TestBuildProfilePrompt:
    """Tests for build_profile_prompt."""

    def test_contains_close_up(self):
        """Contains 'close-up portrait', 'face filling the frame', mood, PROFILE_TAIL."""
        req = _make_leader_req("profile")
        prompt = build_profile_prompt(req)
        assert "close-up portrait" in prompt
        assert "face filling the frame" in prompt
        assert "hard-won victory" in prompt  # mood
        assert PROFILE_TAIL in prompt

    def test_leader_description_included(self):
        req = _make_leader_req("profile")
        prompt = build_profile_prompt(req)
        assert req.leader_description.strip() in prompt


class TestBuildActionPrompt:
    """Tests for build_action_prompt."""

    def test_contains_all_parts(self):
        """Contains action_description, action_category prose, culture, time_of_day, mood, ACTION_TAIL."""
        req = _make_leader_req("action")
        prompt = build_action_prompt(req)
        assert "Leading troops into battle" in prompt
        assert "dynamic action composition" in prompt  # action_category prose
        assert "sandstone temple" in prompt  # culture
        assert "golden sunlight" in prompt  # time_of_day
        assert "hard-won victory" in prompt  # mood
        assert ACTION_TAIL in prompt


class TestBuildPromptDispatcher:
    """Tests for build_prompt routing."""

    def test_routes_to_splash(self):
        req = _make_leader_req("splash")
        prompt = build_prompt(req)
        assert SPLASH_TAIL in prompt

    def test_routes_to_profile(self):
        req = _make_leader_req("profile")
        prompt = build_prompt(req)
        assert PROFILE_TAIL in prompt

    def test_routes_to_action(self):
        req = _make_leader_req("action")
        prompt = build_prompt(req)
        assert ACTION_TAIL in prompt


class TestEnumMaps:
    """Verify all enum values have entries in injection maps."""

    def test_archetype_map_complete(self):
        from src.leader_models import Archetype
        for key in Archetype.ALL:
            assert key in ARCHETYPE, f"Missing archetype: {key}"

    def test_culture_map_complete(self):
        from src.leader_models import Culture
        for key in Culture.ALL:
            assert key in CULTURE, f"Missing culture: {key}"

    def test_time_of_day_map_complete(self):
        from src.leader_models import TimeOfDay
        for key in TimeOfDay.ALL:
            assert key in TIME_OF_DAY, f"Missing time_of_day: {key}"

    def test_mood_map_complete(self):
        from src.leader_models import Mood
        for key in Mood.ALL:
            assert key in MOOD, f"Missing mood: {key}"

    def test_action_category_map_complete(self):
        from src.leader_models import ActionCategory
        for key in ActionCategory.ALL:
            assert key in ACTION_CATEGORY, f"Missing action_category: {key}"


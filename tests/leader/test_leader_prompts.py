"""Unit tests for leader prompts (src/leader/prompts.py)."""

import pytest
from src.leader.models import LeaderRequest
from src.leader.prompts import (
    build_splash_prompt, build_profile_prompt, build_action_prompt, build_prompt,
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
        """Output contains archetype prose, culture prose, time_of_day prose, mood prose, style tail (from template suffix)."""
        req = _make_leader_req("splash")
        prompt = build_splash_prompt(req)
        assert "standing proudly" in prompt  # archetype prose
        assert "sandstone temple" in prompt  # culture prose
        assert "golden sunlight" in prompt  # time_of_day prose
        assert "hard-won victory" in prompt  # mood prose
        assert "professional cinematic quality" in prompt  # tail prose (template suffix)

    def test_ends_with_tail(self):
        """Prompt ends with the style tail from the template suffix."""
        req = _make_leader_req("splash")
        prompt = build_splash_prompt(req)
        assert prompt.endswith("ultra-detailed")

    def test_leader_description_included(self):
        """The leader_description field appears verbatim."""
        req = _make_leader_req("splash")
        prompt = build_splash_prompt(req)
        assert req.leader_description.strip() in prompt


class TestBuildProfilePrompt:
    """Tests for build_profile_prompt."""

    def test_contains_close_up(self):
        """Contains 'close-up portrait', 'face filling the frame', mood, style tail (template suffix)."""
        req = _make_leader_req("profile")
        prompt = build_profile_prompt(req)
        assert "close-up portrait" in prompt
        assert "face filling the frame" in prompt
        assert "hard-won victory" in prompt  # mood
        assert "professional cinematic quality" in prompt  # tail prose (template suffix)

    def test_leader_description_included(self):
        req = _make_leader_req("profile")
        prompt = build_profile_prompt(req)
        assert req.leader_description.strip() in prompt


class TestBuildActionPrompt:
    """Tests for build_action_prompt."""

    def test_contains_all_parts(self):
        """Contains action_description, action_category prose, culture, time_of_day, mood, style tail (template suffix)."""
        req = _make_leader_req("action")
        prompt = build_action_prompt(req)
        assert "Leading troops into battle" in prompt
        assert "dynamic action composition" in prompt  # action_category prose
        assert "sandstone temple" in prompt  # culture
        assert "golden sunlight" in prompt  # time_of_day
        assert "hard-won victory" in prompt  # mood
        assert "professional cinematic quality" in prompt  # tail prose (template suffix)


class TestBuildPromptDispatcher:
    """Tests for build_prompt routing."""

    def test_routes_to_splash(self):
        req = _make_leader_req("splash")
        prompt = build_prompt(req)
        assert "ultra-detailed" in prompt  # splash tail in template suffix

    def test_routes_to_profile(self):
        req = _make_leader_req("profile")
        prompt = build_prompt(req)
        assert "close-up portrait" in prompt  # profile tail in template suffix

    def test_routes_to_action(self):
        req = _make_leader_req("action")
        prompt = build_prompt(req)
        assert "dynamic action" in prompt  # action tail in template suffix


class TestEnumMaps:
    """Verify all enum values have entries in injection maps."""

    def test_archetype_map_complete(self):
        from src.leader.models import Archetype
        for key in Archetype.ALL:
            assert key in ARCHETYPE, f"Missing archetype: {key}"

    def test_culture_map_complete(self):
        from src.leader.models import Culture
        for key in Culture.ALL:
            assert key in CULTURE, f"Missing culture: {key}"

    def test_time_of_day_map_complete(self):
        from src.leader.models import TimeOfDay
        for key in TimeOfDay.ALL:
            assert key in TIME_OF_DAY, f"Missing time_of_day: {key}"

    def test_mood_map_complete(self):
        from src.leader.models import Mood
        for key in Mood.ALL:
            assert key in MOOD, f"Missing mood: {key}"

    def test_action_category_map_complete(self):
        from src.leader.models import ActionCategory
        for key in ActionCategory.ALL:
            assert key in ACTION_CATEGORY, f"Missing action_category: {key}"
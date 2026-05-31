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
        for member in Archetype:
            assert member.value in ARCHETYPE, f"Missing archetype: {member.value}"

    def test_culture_map_complete(self):
        from src.leader.models import Culture
        for member in Culture:
            assert member.value in CULTURE, f"Missing culture: {member.value}"

    def test_time_of_day_map_complete(self):
        from src.leader.models import TimeOfDay
        for member in TimeOfDay:
            assert member.value in TIME_OF_DAY, f"Missing time_of_day: {member.value}"

    def test_mood_map_complete(self):
        from src.leader.models import Mood
        for member in Mood:
            assert member.value in MOOD, f"Missing mood: {member.value}"

    def test_action_category_map_complete(self):
        from src.leader.models import ActionCategory
        for member in ActionCategory:
            assert member.value in ACTION_CATEGORY, f"Missing action_category: {member.value}"


class TestAnatomicalDirectives:
    """Ensure leader prompt templates include anatomical correctness language."""

    def test_splash_contains_anatomical_directives(self):
        """Splash prompt includes full-body anatomical correctness terms."""
        req = _make_leader_req("splash")
        prompt = build_splash_prompt(req)
        assert "anatomically correct human figure" in prompt
        assert "proper limb proportions" in prompt
        assert "well-formed hands with five distinct fingers" in prompt
        assert "natural joint articulation" in prompt
        assert "symmetrical facial features" in prompt

    def test_action_contains_anatomical_directives(self):
        """Action prompt includes full-body anatomical correctness terms."""
        req = _make_leader_req("action")
        prompt = build_action_prompt(req)
        assert "anatomically correct human figure" in prompt
        assert "proper limb proportions" in prompt
        assert "well-formed hands with five distinct fingers" in prompt
        assert "natural joint articulation" in prompt
        assert "symmetrical facial features" in prompt

    def test_profile_contains_facial_anatomy(self):
        """Profile prompt includes facial-specific anatomical correctness term."""
        req = _make_leader_req("profile")
        prompt = build_profile_prompt(req)
        assert "symmetrical well-proportioned facial anatomy" in prompt
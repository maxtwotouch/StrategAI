"""Unit tests for unit prompts (src/unit_prompts.py)."""

import pytest
from src.unit_prompts import build_unit_prompt
from src.unit_models import UnitType, Direction


class TestBuildUnitPrompt:
    """Tests for build_unit_prompt."""

    def test_archer_south(self):
        """Contains 'medieval archer', 'facing camera', 'front view'."""
        prompt = build_unit_prompt("archer", "s", "A test archer description.")
        assert "medieval archer" in prompt
        assert "facing camera" in prompt
        assert "front view" in prompt

    def test_warrior_east(self):
        """Contains 'medieval warrior', 'facing right', 'side profile'."""
        prompt = build_unit_prompt("warrior", "e", "A test warrior description.")
        assert "medieval warrior" in prompt
        assert "facing right" in prompt
        assert "side profile" in prompt

    def test_settler_north(self):
        """Contains 'medieval settler', 'facing away', 'back view'."""
        prompt = build_unit_prompt("settler", "n", "A test settler description.")
        assert "medieval settler" in prompt
        assert "facing away" in prompt
        assert "back view" in prompt

    def test_scout_west(self):
        """Contains 'medieval scout', 'facing left'."""
        prompt = build_unit_prompt("scout", "w", "A test scout description.")
        assert "medieval scout" in prompt
        assert "facing left" in prompt

    def test_unknown_unit_type_graceful(self):
        """build_unit_prompt('dragon', 's', 'desc') → uses 'medieval character sprite' fallback."""
        prompt = build_unit_prompt("dragon", "s", "A dragon description.")
        assert "medieval character sprite" in prompt

    def test_unknown_direction_graceful(self):
        """build_unit_prompt('archer', 'x', 'desc') → uses 'front view' fallback."""
        prompt = build_unit_prompt("archer", "x", "A test description.")
        assert "front view" in prompt

    def test_description_included(self):
        """User description appears in output."""
        desc = "Green leather armor with golden trim."
        prompt = build_unit_prompt("archer", "s", desc)
        assert desc in prompt

    def test_transparent_background_always_present(self):
        """Output contains 'isolated on transparent background'."""
        prompt = build_unit_prompt("archer", "s", "desc")
        assert "isolated on transparent background" in prompt

    def test_crisp_edges_always_present(self):
        """Output contains 'crisp pixel edges'."""
        prompt = build_unit_prompt("archer", "s", "desc")
        assert "crisp pixel edges" in prompt

    def test_all_directions_for_archer(self):
        """All 4 directions produce distinct prompts."""
        prompts = {
            d: build_unit_prompt("archer", d, "Test description.")
            for d in Direction.ALL
        }
        # Each direction should have a unique prompt
        assert len(set(prompts.values())) == 4

    def test_empty_description_handling(self):
        """Empty description handled gracefully (still builds valid prompt)."""
        prompt = build_unit_prompt("archer", "s", "")
        assert "pixel art top-down 2d game character sprite" in prompt

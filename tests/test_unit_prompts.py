"""Unit tests for unit prompts (src/unit_prompts.py)."""

import pytest
from src.unit_prompts import build_unit_prompt
from src.unit_models import UnitType


class TestBuildUnitPrompt:
    """Tests for build_unit_prompt."""

    def test_archer(self):
        """Contains 'medieval archer', 'facing camera', 'front view'."""
        prompt = build_unit_prompt("archer", "A test archer description.")
        assert "medieval archer" in prompt
        assert "facing camera" in prompt
        assert "front view" in prompt

    def test_warrior(self):
        """Contains 'medieval warrior'."""
        prompt = build_unit_prompt("warrior", "A test warrior description.")
        assert "medieval warrior" in prompt

    def test_settler(self):
        """Contains 'medieval settler'."""
        prompt = build_unit_prompt("settler", "A test settler description.")
        assert "medieval settler" in prompt

    def test_scout(self):
        """Contains 'medieval scout'."""
        prompt = build_unit_prompt("scout", "A test scout description.")
        assert "medieval scout" in prompt

    def test_unknown_unit_type_graceful(self):
        """build_unit_prompt('dragon', 'desc') → uses 'medieval character sprite' fallback."""
        prompt = build_unit_prompt("dragon", "A dragon description.")
        assert "medieval character sprite" in prompt

    def test_description_included(self):
        """User description appears in output."""
        desc = "Green leather armor with golden trim."
        prompt = build_unit_prompt("archer", desc)
        assert desc in prompt

    def test_transparent_background_always_present(self):
        """Output contains 'isolated on transparent background'."""
        prompt = build_unit_prompt("archer", "desc")
        assert "isolated on transparent background" in prompt

    def test_crisp_edges_always_present(self):
        """Output contains 'crisp pixel edges'."""
        prompt = build_unit_prompt("archer", "desc")
        assert "crisp pixel edges" in prompt

    def test_empty_description_handling(self):
        """Empty description handled gracefully (still builds valid prompt)."""
        prompt = build_unit_prompt("archer", "")
        assert "pixel art top-down 2d game character sprite" in prompt

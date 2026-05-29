"""Unit tests for unit prompts (src/unit/prompts.py)."""

import pytest
from src.unit.prompts import build_unit_prompt
from src.unit.models import UnitType


class TestBuildUnitPrompt:
    """Tests for build_unit_prompt."""

    def test_archer_prompt(self):
        prompt = build_unit_prompt("archer", "green leather armor, longbow")
        assert "pixel art" in prompt.lower()
        assert "archer" in prompt.lower()
        assert "green leather armor" in prompt

    def test_warrior_prompt(self):
        prompt = build_unit_prompt("warrior", "heavy plate armor, longsword")
        assert "warrior" in prompt.lower()
        assert "heavy plate armor" in prompt

    def test_scout_prompt(self):
        prompt = build_unit_prompt("scout", "light armor, running pose")
        assert "scout" in prompt.lower()

    def test_settler_prompt(self):
        prompt = build_unit_prompt("settler", "wool tunic, carrying supplies")
        assert "settler" in prompt.lower()

    def test_invalid_type_uses_default(self):
        prompt = build_unit_prompt("unknown_type", "some description")
        assert "medieval character sprite" in prompt.lower()

    def test_prompt_contains_front_view(self):
        prompt = build_unit_prompt("archer", "test description")
        assert "front view" in prompt.lower() or "facing camera" in prompt.lower()

    def test_prompt_contains_pixel_art(self):
        prompt = build_unit_prompt("archer", "test description")
        assert "pixel art" in prompt.lower()
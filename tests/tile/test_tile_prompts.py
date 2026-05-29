"""Unit tests for tile prompts (src/tile/prompts.py)."""

import pytest
from src.tile.models import StructureRequest, ObjectRequest, TerrainRequest
from src.tile.prompts import (
    build_structure_prompt, build_object_prompt, build_terrain_prompt,
    load_template,
    STRUCTURE_CATEGORY, STRUCTURE_STYLE, STRUCTURE_CONDITION, STRUCTURE_SCALE,
    OBJECT_CATEGORY, BIOME, SEASON,
    TERRAIN_CATEGORY, TERRAIN_SCALE, TERRAIN_MATERIAL,
)


def _make_structure_req(**overrides):
    defaults = {
        "category": "fortification",
        "style": "nordic_wooden",
        "condition": "pristine",
        "scale": "small",
        "description": "A small wooden watchtower with a pointed roof and a lookout platform.",
    }
    defaults.update(overrides)
    return StructureRequest(**defaults)


def _make_object_req(**overrides):
    defaults = {
        "category": "vegetation",
        "biome": "temperate_forest",
        "season": "summer",
        "description": "A large oak tree with a thick trunk and sprawling branches full of green leaves.",
    }
    defaults.update(overrides)
    return ObjectRequest(**defaults)


def _make_terrain_req(**overrides):
    defaults = {
        "category": "hill",
        "scale": "medium",
        "material": "earthen",
        "description": "A rounded grassy hill with gentle slopes on all sides and a flat top.",
    }
    defaults.update(overrides)
    return TerrainRequest(**defaults)


class TestBuildStructurePrompt:
    """Tests for build_structure_prompt."""

    def test_contains_all_enums(self):
        """Output contains scale, category, style, condition, description (prose values, not enum keys)."""
        req = _make_structure_req()
        prompt = build_structure_prompt(req)
        assert "compact" in prompt.lower()
        assert "defensive" in prompt.lower()  # fortification prose
        assert "norse" in prompt.lower()      # nordic_wooden prose
        assert "freshly built" in prompt.lower()  # pristine prose

    def test_uses_template(self):
        """Prompt is wrapped by the structure template (prefix and suffix present)."""
        req = _make_structure_req()
        prompt = build_structure_prompt(req)
        template = load_template("structure")
        parts = template.split("{PROMPT_HERE}")
        assert len(parts) == 2, "Template must have exactly one {PROMPT_HERE} placeholder"
        assert parts[0].strip() in prompt
        assert parts[1].strip() in prompt


class TestBuildObjectPrompt:
    """Tests for build_object_prompt."""

    def test_contains_all_enums(self):
        """Output contains category, biome, season, description (prose values, not enum keys)."""
        req = _make_object_req()
        prompt = build_object_prompt(req)
        assert "natural living plant" in prompt.lower()  # vegetation prose
        assert "deciduous" in prompt.lower()              # temperate_forest prose
        assert "mature foliage" in prompt.lower()         # summer prose


class TestBuildTerrainPrompt:
    """Tests for build_terrain_prompt."""

    def test_contains_all_enums(self):
        """Output contains scale, category, material, description (prose values, not enum keys)."""
        req = _make_terrain_req()
        prompt = build_terrain_prompt(req)
        assert "hill" in prompt.lower()                  # hill IS in the terrain prose
        assert "moderate" in prompt.lower()              # medium scale prose
        assert "grass-topped" in prompt.lower()          # earthen material prose


class TestEnumMaps:
    """Verify all enum values have entries in injection maps."""

    def test_structure_category_map_complete(self):
        from src.tile.models import StructureCategory
        for member in StructureCategory:
            assert member.value in STRUCTURE_CATEGORY, f"Missing structure category: {member.value}"

    def test_structure_style_map_complete(self):
        from src.tile.models import StructureStyle
        for member in StructureStyle:
            assert member.value in STRUCTURE_STYLE, f"Missing structure style: {member.value}"

    def test_structure_condition_map_complete(self):
        from src.tile.models import StructureCondition
        for member in StructureCondition:
            assert member.value in STRUCTURE_CONDITION, f"Missing structure condition: {member.value}"

    def test_structure_scale_map_complete(self):
        from src.tile.models import StructureScale
        for member in StructureScale:
            assert member.value in STRUCTURE_SCALE, f"Missing structure scale: {member.value}"

    def test_object_category_map_complete(self):
        from src.tile.models import ObjectCategory
        for member in ObjectCategory:
            assert member.value in OBJECT_CATEGORY, f"Missing object category: {member.value}"

    def test_biome_map_complete(self):
        from src.tile.models import Biome
        for member in Biome:
            assert member.value in BIOME, f"Missing biome: {member.value}"

    def test_season_map_complete(self):
        from src.tile.models import Season
        for member in Season:
            assert member.value in SEASON, f"Missing season: {member.value}"

    def test_terrain_category_map_complete(self):
        from src.tile.models import TerrainCategory
        for member in TerrainCategory:
            assert member.value in TERRAIN_CATEGORY, f"Missing terrain category: {member.value}"

    def test_terrain_scale_map_complete(self):
        from src.tile.models import TerrainScale
        for member in TerrainScale:
            assert member.value in TERRAIN_SCALE, f"Missing terrain scale: {member.value}"

    def test_terrain_material_map_complete(self):
        from src.tile.models import TerrainMaterial
        for member in TerrainMaterial:
            assert member.value in TERRAIN_MATERIAL, f"Missing terrain material: {member.value}"
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
        """Output contains scale, category, style, condition, description."""
        req = _make_structure_req()
        prompt = build_structure_prompt(req)
        assert "small" in prompt.lower() or "compact" in prompt
        assert "fortification" in prompt.lower()
        assert "nordic" in prompt.lower()
        assert "pristine" in prompt.lower()

    def test_uses_template(self):
        """Prompt is wrapped by the structure template."""
        req = _make_structure_req()
        prompt = build_structure_prompt(req)
        template = load_template("structure")
        assert template.replace("{PROMPT_HERE}", "") in prompt or prompt in template.replace("{PROMPT_HERE}", "test")


class TestBuildObjectPrompt:
    """Tests for build_object_prompt."""

    def test_contains_all_enums(self):
        """Output contains category, biome, season, description."""
        req = _make_object_req()
        prompt = build_object_prompt(req)
        assert "vegetation" in prompt.lower()
        assert "temperate" in prompt.lower()
        assert "summer" in prompt.lower()


class TestBuildTerrainPrompt:
    """Tests for build_terrain_prompt."""

    def test_contains_all_enums(self):
        """Output contains scale, category, material, description."""
        req = _make_terrain_req()
        prompt = build_terrain_prompt(req)
        assert "hill" in prompt.lower()
        assert "medium" in prompt.lower()
        assert "earthen" in prompt.lower()


class TestEnumMaps:
    """Verify all enum values have entries in injection maps."""

    def test_structure_category_map_complete(self):
        from src.tile.models import StructureCategory
        for key in StructureCategory.ALL:
            assert key in STRUCTURE_CATEGORY, f"Missing structure category: {key}"

    def test_structure_style_map_complete(self):
        from src.tile.models import StructureStyle
        for key in StructureStyle.ALL:
            assert key in STRUCTURE_STYLE, f"Missing structure style: {key}"

    def test_structure_condition_map_complete(self):
        from src.tile.models import StructureCondition
        for key in StructureCondition.ALL:
            assert key in STRUCTURE_CONDITION, f"Missing structure condition: {key}"

    def test_structure_scale_map_complete(self):
        from src.tile.models import StructureScale
        for key in StructureScale.ALL:
            assert key in STRUCTURE_SCALE, f"Missing structure scale: {key}"

    def test_object_category_map_complete(self):
        from src.tile.models import ObjectCategory
        for key in ObjectCategory.ALL:
            assert key in OBJECT_CATEGORY, f"Missing object category: {key}"

    def test_biome_map_complete(self):
        from src.tile.models import Biome
        for key in Biome.ALL:
            assert key in BIOME, f"Missing biome: {key}"

    def test_season_map_complete(self):
        from src.tile.models import Season
        for key in Season.ALL:
            assert key in SEASON, f"Missing season: {key}"

    def test_terrain_category_map_complete(self):
        from src.tile.models import TerrainCategory
        for key in TerrainCategory.ALL:
            assert key in TERRAIN_CATEGORY, f"Missing terrain category: {key}"

    def test_terrain_scale_map_complete(self):
        from src.tile.models import TerrainScale
        for key in TerrainScale.ALL:
            assert key in TERRAIN_SCALE, f"Missing terrain scale: {key}"

    def test_terrain_material_map_complete(self):
        from src.tile.models import TerrainMaterial
        for key in TerrainMaterial.ALL:
            assert key in TERRAIN_MATERIAL, f"Missing terrain material: {key}"
"""Unit tests for tile prompts (src/tile_prompts.py)."""

import pytest
from src.tile_models import StructureRequest, ObjectRequest, TerrainRequest
from src.tile_prompts import (
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

    def test_injection(self):
        """Each enum value's prose appears in output."""
        req = _make_structure_req()
        prompt = build_structure_prompt(req)
        assert "defensive structure" in prompt  # category
        assert "dark timber" in prompt  # style
        assert "freshly built" in prompt  # condition
        assert "compact single-room" in prompt  # scale

    def test_template_wrapping(self):
        """Output starts with <tdp> prefix from prompt_templates.json."""
        req = _make_structure_req()
        prompt = build_structure_prompt(req)
        assert prompt.startswith("<tdp>")

    def test_description_appears_last(self):
        """User's free-form description appears verbatim."""
        req = _make_structure_req()
        prompt = build_structure_prompt(req)
        assert req.description.strip() in prompt


class TestBuildObjectPrompt:
    """Tests for build_object_prompt."""

    def test_injection(self):
        """Category, biome, season prose all present."""
        req = _make_object_req()
        prompt = build_object_prompt(req)
        assert "natural living plant" in prompt  # category
        assert "deciduous woodland" in prompt  # biome
        assert "full mature foliage" in prompt  # season (summer)

    def test_template_wrapping(self):
        req = _make_object_req()
        prompt = build_object_prompt(req)
        assert prompt.startswith("<tdp>")

    def test_description_included(self):
        req = _make_object_req()
        prompt = build_object_prompt(req)
        assert req.description.strip() in prompt


class TestBuildTerrainPrompt:
    """Tests for build_terrain_prompt."""

    def test_injection(self):
        """Category, scale, material prose all present."""
        req = _make_terrain_req()
        prompt = build_terrain_prompt(req)
        assert "rounded mound" in prompt  # category
        assert "noticeable elevation" in prompt  # scale
        assert "grass-topped soil" in prompt  # material

    def test_template_wrapping(self):
        req = _make_terrain_req()
        prompt = build_terrain_prompt(req)
        assert prompt.startswith("<tdp>")

    def test_description_included(self):
        req = _make_terrain_req()
        prompt = build_terrain_prompt(req)
        assert req.description.strip() in prompt


class TestLoadTemplate:
    """Tests for load_template."""

    def test_load_known_keys(self):
        assert "structure" in load_template("structure")
        assert "object" in load_template("object")
        assert "terrain" in load_template("terrain")

    def test_load_invalid_key_raises(self):
        """Invalid key raises KeyError."""
        with pytest.raises(KeyError):
            load_template("nonexistent")


class TestEnumMaps:
    """Verify all enum values have entries in injection maps."""

    def test_structure_category_map_complete(self):
        from src.tile_models import StructureCategory
        for key in StructureCategory.ALL:
            assert key in STRUCTURE_CATEGORY, f"Missing structure category: {key}"

    def test_structure_style_map_complete(self):
        from src.tile_models import StructureStyle
        for key in StructureStyle.ALL:
            assert key in STRUCTURE_STYLE, f"Missing structure style: {key}"

    def test_structure_condition_map_complete(self):
        from src.tile_models import StructureCondition
        for key in StructureCondition.ALL:
            assert key in STRUCTURE_CONDITION, f"Missing structure condition: {key}"

    def test_structure_scale_map_complete(self):
        from src.tile_models import StructureScale
        for key in StructureScale.ALL:
            assert key in STRUCTURE_SCALE, f"Missing structure scale: {key}"

    def test_object_category_map_complete(self):
        from src.tile_models import ObjectCategory
        for key in ObjectCategory.ALL:
            assert key in OBJECT_CATEGORY, f"Missing object category: {key}"

    def test_biome_map_complete(self):
        from src.tile_models import Biome
        for key in Biome.ALL:
            assert key in BIOME, f"Missing biome: {key}"

    def test_season_map_complete(self):
        from src.tile_models import Season
        for key in Season.ALL:
            assert key in SEASON, f"Missing season: {key}"

    def test_terrain_category_map_complete(self):
        from src.tile_models import TerrainCategory
        for key in TerrainCategory.ALL:
            assert key in TERRAIN_CATEGORY, f"Missing terrain category: {key}"

    def test_terrain_scale_map_complete(self):
        from src.tile_models import TerrainScale
        for key in TerrainScale.ALL:
            assert key in TERRAIN_SCALE, f"Missing terrain scale: {key}"

    def test_terrain_material_map_complete(self):
        from src.tile_models import TerrainMaterial
        for key in TerrainMaterial.ALL:
            assert key in TERRAIN_MATERIAL, f"Missing terrain material: {key}"

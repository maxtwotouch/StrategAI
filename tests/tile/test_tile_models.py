"""Unit tests for tile models (src/tile/models.py)."""

import pytest
from pydantic import ValidationError
from src.tile.models import (
    StructureRequest, StructureResponse, StructureCatalog,
    ObjectRequest, ObjectResponse, ObjectCatalog,
    TerrainRequest, TerrainResponse, TerrainCatalog,
    StructureCategory, StructureStyle, StructureCondition, StructureScale,
    ObjectCategory, Biome, Season,
    TerrainCategory, TerrainScale, TerrainMaterial,
)


class TestStructureRequest:
    """Tests for StructureRequest validation."""

    def test_valid(self):
        req = StructureRequest(
            category="fortification",
            style="nordic_wooden",
            condition="pristine",
            scale="small",
            description="A small wooden watchtower with a pointed roof and lookout platform.",
        )
        assert req.category == "fortification"
        assert req.style == "nordic_wooden"

    def test_description_too_short(self):
        """10-char description → ValidationError."""
        with pytest.raises(ValidationError):
            StructureRequest(
                category="fortification",
                style="nordic_wooden",
                condition="pristine",
                scale="small",
                description="x" * 10,
            )


class TestObjectRequest:
    """Tests for ObjectRequest validation."""

    def test_valid(self):
        req = ObjectRequest(
            category="vegetation",
            biome="temperate_forest",
            season="summer",
            description="A large oak tree with a thick trunk and sprawling branches full of green leaves.",
        )
        assert req.category == "vegetation"

    def test_description_too_short(self):
        with pytest.raises(ValidationError):
            ObjectRequest(
                category="vegetation",
                biome="temperate_forest",
                season="summer",
                description="x" * 10,
            )


class TestTerrainRequest:
    """Tests for TerrainRequest validation."""

    def test_valid(self):
        req = TerrainRequest(
            category="hill",
            scale="medium",
            material="earthen",
            description="A rounded grassy hill with gentle slopes on all sides and a flat top.",
        )
        assert req.category == "hill"

    def test_description_too_short(self):
        with pytest.raises(ValidationError):
            TerrainRequest(
                category="hill",
                scale="medium",
                material="earthen",
                description="x" * 10,
            )


class TestEnums:
    """Verify enum sets."""

    def test_structure_category_all(self):
        assert len(StructureCategory) == 4

    def test_structure_style_all(self):
        assert len(StructureStyle) == 7

    def test_structure_condition_all(self):
        assert len(StructureCondition) == 5

    def test_structure_scale_all(self):
        assert len(StructureScale) == 3

    def test_object_category_all(self):
        assert len(ObjectCategory) == 5

    def test_biome_all(self):
        assert len(Biome) == 7

    def test_season_all(self):
        assert len(Season) == 4

    def test_terrain_category_all(self):
        assert len(TerrainCategory) == 5

    def test_terrain_scale_all(self):
        assert len(TerrainScale) == 3

    def test_terrain_material_all(self):
        assert len(TerrainMaterial) == 5
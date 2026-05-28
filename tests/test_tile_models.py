"""Unit tests for tile models (src/tile_models.py)."""

import pytest
from pydantic import ValidationError
from src.tile_models import (
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
                description="Too short",
            )

    def test_description_too_long(self):
        """500-char description → ValidationError."""
        with pytest.raises(ValidationError):
            StructureRequest(
                category="fortification",
                style="nordic_wooden",
                condition="pristine",
                scale="small",
                description="x" * 500,
            )

    def test_seed_optional(self):
        """Missing seed → valid, seed is None."""
        req = StructureRequest(
            category="fortification",
            style="nordic_wooden",
            condition="pristine",
            scale="small",
            description="A small wooden watchtower with a pointed roof and lookout platform.",
        )
        assert req.seed is None

    def test_with_seed(self):
        req = StructureRequest(
            category="fortification",
            style="nordic_wooden",
            condition="pristine",
            scale="small",
            description="A small wooden watchtower with a pointed roof and lookout platform.",
            seed=42,
        )
        assert req.seed == 42


class TestObjectRequest:
    """Tests for ObjectRequest validation."""

    def test_valid(self):
        req = ObjectRequest(
            category="vegetation",
            biome="temperate_forest",
            season="summer",
            description="A large oak tree with a thick trunk and sprawling branches full of leaves.",
        )
        assert req.category == "vegetation"
        assert req.biome == "temperate_forest"

    def test_description_too_short(self):
        with pytest.raises(ValidationError):
            ObjectRequest(
                category="vegetation",
                biome="temperate_forest",
                season="summer",
                description="short",
            )

    def test_seed_optional(self):
        req = ObjectRequest(
            category="vegetation",
            biome="temperate_forest",
            season="summer",
            description="A large oak tree with a thick trunk and sprawling branches full of leaves.",
        )
        assert req.seed is None


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
        assert req.material == "earthen"

    def test_description_too_short(self):
        with pytest.raises(ValidationError):
            TerrainRequest(
                category="hill",
                scale="medium",
                material="earthen",
                description="short",
            )

    def test_seed_optional(self):
        req = TerrainRequest(
            category="hill",
            scale="medium",
            material="earthen",
            description="A rounded grassy hill with gentle slopes on all sides and a flat top.",
        )
        assert req.seed is None


class TestStructureResponse:
    """Tests for StructureResponse construction."""

    def test_construction(self):
        resp = StructureResponse(
            url="/assets/test.png",
            asset_id="struct_fort_a1b2c3",
            category="fortification",
            style="nordic_wooden",
            condition="pristine",
            scale="small",
            seed=42,
            generation_mode="placeholder",
        )
        assert resp.asset_type == "structure"
        assert resp.status == "completed"
        assert resp.url == "/assets/test.png"


class TestObjectResponse:
    """Tests for ObjectResponse construction."""

    def test_construction(self):
        resp = ObjectResponse(
            url="/assets/test.png",
            asset_id="object_veg_a1b2c3",
            category="vegetation",
            biome="temperate_forest",
            season="summer",
            seed=42,
            generation_mode="placeholder",
        )
        assert resp.asset_type == "object"
        assert resp.status == "completed"


class TestTerrainResponse:
    """Tests for TerrainResponse construction."""

    def test_construction(self):
        resp = TerrainResponse(
            url="/assets/test.png",
            asset_id="terrain_hill_a1b2c3",
            category="hill",
            scale="medium",
            material="earthen",
            seed=42,
            generation_mode="placeholder",
        )
        assert resp.asset_type == "terrain"
        assert resp.status == "completed"


class TestCatalogModels:
    """Tests for catalog response models."""

    def test_structure_catalog(self):
        cat = StructureCatalog(
            categories=sorted(StructureCategory.ALL),
            styles=sorted(StructureStyle.ALL),
            conditions=sorted(StructureCondition.ALL),
            scales=sorted(StructureScale.ALL),
        )
        assert "fortification" in cat.categories
        assert "nordic_wooden" in cat.styles

    def test_object_catalog(self):
        cat = ObjectCatalog(
            categories=sorted(ObjectCategory.ALL),
            biomes=sorted(Biome.ALL),
            seasons=sorted(Season.ALL),
        )
        assert "vegetation" in cat.categories
        assert "summer" in cat.seasons

    def test_terrain_catalog(self):
        cat = TerrainCatalog(
            categories=sorted(TerrainCategory.ALL),
            scales=sorted(TerrainScale.ALL),
            materials=sorted(TerrainMaterial.ALL),
        )
        assert "hill" in cat.categories
        assert "earthen" in cat.materials


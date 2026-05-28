"""Unit tests for core models (src/models.py)."""

import pytest
from pydantic import ValidationError
from src.models import (
    GenerationRequest, SplashRequest, GenerationResponse, SplashResponse,
    Coordinate, InpaintRequest, AssetFamily, TileType, StructureSubtype,
)


class TestGenerationRequest:
    """Tests for GenerationRequest validation."""

    def test_valid_background_tile(self):
        """Valid background_tile request passes."""
        req = GenerationRequest(
            asset_family="background_tile",
            tile_type="grass",
            prompt="A lush green grass tile.",
        )
        assert req.asset_family == "background_tile"
        assert req.tile_type == "grass"

    def test_valid_structure(self):
        """Valid structure request passes."""
        req = GenerationRequest(
            asset_family="structure",
            structure_subtype="fortification",
            prompt="A stone castle.",
        )
        assert req.structure_subtype == "fortification"

    def test_invalid_asset_family(self):
        """Unknown asset_family → ValidationError."""
        with pytest.raises(ValidationError):
            GenerationRequest(asset_family="invalid_family")

    def test_invalid_tile_type(self):
        """Unknown tile_type → ValidationError."""
        with pytest.raises(ValidationError):
            GenerationRequest(asset_family="background_tile", tile_type="lava")

    def test_invalid_structure_subtype(self):
        """Unknown structure_subtype → ValidationError."""
        with pytest.raises(ValidationError):
            GenerationRequest(asset_family="structure", structure_subtype="invalid")

    def test_tile_type_optional(self):
        """Missing tile_type → valid, tile_type is None."""
        req = GenerationRequest(asset_family="structure")
        assert req.tile_type is None

    def test_prompt_optional(self):
        """Missing prompt → valid."""
        req = GenerationRequest(asset_family="nature_object")
        assert req.prompt is None

    def test_base_image_id_optional(self):
        """base_image_id is optional."""
        req = GenerationRequest(asset_family="background_tile", tile_type="water")
        assert req.base_image_id is None

    def test_inpaints_optional(self):
        """inpaints is optional."""
        req = GenerationRequest(asset_family="background_tile", tile_type="grass")
        assert req.inpaints is None

    def test_with_inpaints(self):
        """Request with inpaint list passes."""
        req = GenerationRequest(
            asset_family="background_tile",
            tile_type="grass",
            inpaints=[
                InpaintRequest(
                    point_a=Coordinate(x=0, y=0),
                    point_b=Coordinate(x=10, y=10),
                    fill_type="water",
                )
            ],
        )
        assert len(req.inpaints) == 1
        assert req.inpaints[0].fill_type == "water"


class TestCoordinate:
    """Tests for Coordinate model."""

    def test_valid_coordinate(self):
        c = Coordinate(x=5, y=10)
        assert c.x == 5
        assert c.y == 10

    def test_negative_coordinate(self):
        """Coordinate allows negative values."""
        c = Coordinate(x=-1, y=0)
        assert c.x == -1


class TestInpaintRequest:
    """Tests for InpaintRequest model."""

    def test_valid_inpaint(self):
        req = InpaintRequest(
            point_a=Coordinate(x=0, y=0),
            point_b=Coordinate(x=32, y=32),
            fill_type="water",
        )
        assert req.fill_type == "water"

    def test_missing_fill_type(self):
        """fill_type is required."""
        with pytest.raises(ValidationError):
            InpaintRequest(
                point_a=Coordinate(x=0, y=0),
                point_b=Coordinate(x=10, y=10),
            )


class TestSplashRequest:
    """Tests for SplashRequest validation."""

    def test_valid_splash(self):
        req = SplashRequest(character_name="Arthur")
        assert req.character_name == "Arthur"
        assert req.style == "pixel_art"
        assert req.background == "solid_dark"

    def test_missing_character_name(self):
        """character_name is required."""
        with pytest.raises(ValidationError):
            SplashRequest()

    def test_all_fields(self):
        req = SplashRequest(
            character_name="Arthur",
            title="King",
            description="A noble king.",
            style="pixel_art",
            outfit="Plate armor",
            weapon="Excalibur",
            background="banner",
        )
        assert req.title == "King"
        assert req.weapon == "Excalibur"


class TestGenerationResponse:
    """Tests for GenerationResponse construction."""

    def test_minimal_response(self):
        resp = GenerationResponse(url="/assets/test.png", asset_family="structure")
        assert resp.url == "/assets/test.png"
        assert resp.status == "completed"
        assert resp.tile_type is None
        assert resp.generation_mode is None

    def test_full_response(self):
        resp = GenerationResponse(
            url="/assets/test.png",
            asset_family="background_tile",
            tile_type="grass",
            generation_mode="placeholder",
        )
        assert resp.tile_type == "grass"
        assert resp.generation_mode == "placeholder"


class TestSplashResponse:
    """Tests for SplashResponse construction."""

    def test_minimal_response(self):
        resp = SplashResponse(url="/assets/splash.png", character_name="Arthur")
        assert resp.character_name == "Arthur"
        assert resp.status == "completed"


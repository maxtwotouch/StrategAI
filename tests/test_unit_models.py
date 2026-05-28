"""Unit tests for unit models (src/unit_models.py)."""

import pytest
from pydantic import ValidationError
from src.unit_models import (
    UnitRequest, UnitResponse, UnitCatalog,
    UnitType,
)


class TestUnitRequest:
    """Tests for UnitRequest validation."""

    def test_valid(self):
        req = UnitRequest(
            unit_type="archer",
            description="A medieval archer in green leather armor with a longbow and quiver of arrows.",
        )
        assert req.unit_type == "archer"

    def test_description_too_short(self):
        """Description < 20 chars → ValidationError."""
        with pytest.raises(ValidationError):
            UnitRequest(unit_type="archer", description="short")

    def test_description_too_long(self):
        """Description > 400 chars → ValidationError."""
        with pytest.raises(ValidationError):
            UnitRequest(unit_type="archer", description="x" * 401)

    def test_seed_optional(self):
        req = UnitRequest(
            unit_type="archer",
            description="A medieval archer in green leather armor with a longbow and quiver of arrows.",
        )
        assert req.seed is None

    def test_with_seed(self):
        req = UnitRequest(
            unit_type="archer",
            description="A medieval archer in green leather armor with a longbow and quiver of arrows.",
            seed=42,
        )
        assert req.seed == 42

    def test_all_valid_unit_types(self):
        """All UnitType.ALL values pass validation."""
        for ut in UnitType.ALL:
            req = UnitRequest(
                unit_type=ut,
                description="A medieval unit with enough characters to pass the minimum length requirement.",
            )
            assert req.unit_type == ut

    def test_unknown_unit_type_passes_validation(self):
        """unit_type='dragon' passes Pydantic validation (no Literal constraint)."""
        req = UnitRequest(
            unit_type="dragon",
            description="A fire-breathing dragon with scales and wings, soaring through the sky.",
        )
        assert req.unit_type == "dragon"


class TestUnitResponse:
    """Tests for UnitResponse construction."""

    def test_construction(self):
        resp = UnitResponse(
            url="/assets/s.png",
            unit_id="unit_archer_a1b2c3",
            unit_type="archer",
            seed=42,
            generation_mode="placeholder",
        )
        assert resp.asset_type == "unit"
        assert resp.status == "completed"
        assert resp.url == "/assets/s.png"


class TestUnitCatalog:
    """Tests for UnitCatalog model."""

    def test_construction(self):
        cat = UnitCatalog(
            unit_types=sorted(UnitType.ALL),
        )
        assert "archer" in cat.unit_types


class TestEnums:
    """Verify enum sets."""

    def test_unit_type_all(self):
        assert UnitType.ALL == {"archer", "scout", "settler", "warrior"}

"""Unit tests for unit models (src/unit/models.py)."""

import pytest
from pydantic import ValidationError
from src.unit.models import (
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
        """10-char description → ValidationError."""
        with pytest.raises(ValidationError):
            UnitRequest(
                unit_type="archer",
                description="x" * 10,
            )

    def test_invalid_unit_type(self):
        """Unknown unit_type → ValidationError."""
        with pytest.raises(ValidationError):
            UnitRequest(
                unit_type="dragon",
                description="A fearsome dragon with scales and wings.",
            )


class TestUnitResponse:
    """Tests for UnitResponse construction."""

    def test_construction(self):
        resp = UnitResponse(
            url="/assets/test.png",
            unit_id="unit_archer_abc123",
            unit_type="archer",
            seed=42,
            generation_mode="placeholder",
        )
        assert resp.status == "completed"
        assert resp.unit_type == "archer"


class TestUnitType:
    """Verify UnitType enum."""

    def test_all_types(self):
        assert len(UnitType.ALL) == 4
        assert "archer" in UnitType.ALL
        assert "scout" in UnitType.ALL
        assert "settler" in UnitType.ALL
        assert "warrior" in UnitType.ALL
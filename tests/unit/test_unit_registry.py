"""Unit tests for unit registry (src/unit/registry.py)."""

import pytest
from src.unit.registry import UnitRegistry, generate_unit_id


class TestGenerateUnitId:
    """Tests for generate_unit_id."""

    def test_generates_unit_id(self):
        uid = generate_unit_id("archer")
        assert uid.startswith("unit_archer_")
        assert len(uid) > len("unit_archer_")

    def test_unique_ids(self):
        id1 = generate_unit_id("archer")
        id2 = generate_unit_id("archer")
        assert id1 != id2


class TestUnitRegistry:
    """Tests for UnitRegistry CRUD."""

    def test_register_and_get(self, test_db):
        UnitRegistry.register(
            unit_id="unit_test_abc123",
            unit_type="archer",
            description="A test archer.",
            image_id="archer.png",
            seed=42,
            prompt_used="archer prompt",
            generation_mode="placeholder",
        )
        record = UnitRegistry.get("unit_test_abc123")
        assert record is not None
        assert record.unit_type == "archer"

    def test_list_all(self, test_db):
        UnitRegistry.register(
            unit_id="unit_list_abc123",
            unit_type="warrior",
            description="A test warrior.",
            image_id="warrior.png",
            seed=123,
            prompt_used="warrior prompt",
            generation_mode="placeholder",
        )
        records = UnitRegistry.list_all()
        assert len(records) >= 1

    def test_delete(self, test_db):
        UnitRegistry.register(
            unit_id="unit_del_abc123",
            unit_type="scout",
            description="A test scout.",
            image_id="scout.png",
            seed=999,
            prompt_used="scout prompt",
            generation_mode="placeholder",
        )
        result = UnitRegistry.delete("unit_del_abc123")
        assert result is True
        assert UnitRegistry.get("unit_del_abc123") is None
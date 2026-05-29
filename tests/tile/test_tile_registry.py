"""Unit tests for tile registry (src/tile/registry.py)."""

import pytest
from src.tile.registry import (
    StructureRegistry, ObjectRegistry, TerrainRegistry,
    generate_structure_id, generate_object_id, generate_terrain_id,
)


class TestGenerateIds:
    """Tests for ID generators."""

    def test_generate_structure_id(self):
        sid = generate_structure_id("fortification")
        assert sid.startswith("struct_fortification_")
        assert len(sid) > len("struct_fortification_")

    def test_generate_object_id(self):
        oid = generate_object_id("vegetation")
        assert oid.startswith("object_vegetation_")

    def test_generate_terrain_id(self):
        tid = generate_terrain_id("hill")
        assert tid.startswith("terrain_hill_")


class TestStructureRegistry:
    """Tests for StructureRegistry CRUD."""

    def test_register_and_get(self, test_db):
        StructureRegistry.register(
            structure_id="struct_test_abc123",
            category="fortification",
            style="nordic_wooden",
            condition="pristine",
            scale="small",
            description="A test structure.",
            image_id="test.png",
            seed=42,
            prompt_used="test prompt",
        )
        record = StructureRegistry.get("struct_test_abc123")
        assert record is not None
        assert record.category == "fortification"

    def test_list_all(self, test_db):
        StructureRegistry.register(
            structure_id="struct_list_abc123",
            category="production",
            style="gothic",
            condition="pristine",
            scale="large",
            description="A production structure.",
            image_id="test2.png",
            seed=123,
            prompt_used="test prompt 2",
        )
        records = StructureRegistry.list_all()
        assert len(records) >= 1

    def test_delete(self, test_db):
        StructureRegistry.register(
            structure_id="struct_del_abc123",
            category="housing",
            style="mediterranean",
            condition="pristine",
            scale="medium",
            description="A housing structure.",
            image_id="test3.png",
            seed=999,
            prompt_used="test prompt 3",
        )
        result = StructureRegistry.delete("struct_del_abc123")
        assert result is True
        assert StructureRegistry.get("struct_del_abc123") is None


class TestObjectRegistry:
    """Tests for ObjectRegistry CRUD."""

    def test_register_and_get(self, test_db):
        ObjectRegistry.register(
            object_id="object_test_abc123",
            category="vegetation",
            biome="temperate_forest",
            season="summer",
            description="A test tree.",
            image_id="tree.png",
            seed=42,
            prompt_used="tree prompt",
        )
        record = ObjectRegistry.get("object_test_abc123")
        assert record is not None
        assert record.category == "vegetation"


class TestTerrainRegistry:
    """Tests for TerrainRegistry CRUD."""

    def test_register_and_get(self, test_db):
        TerrainRegistry.register(
            terrain_id="terrain_test_abc123",
            category="hill",
            scale="medium",
            material="earthen",
            description="A grassy hill.",
            image_id="hill.png",
            seed=42,
            prompt_used="hill prompt",
        )
        record = TerrainRegistry.get("terrain_test_abc123")
        assert record is not None
        assert record.category == "hill"
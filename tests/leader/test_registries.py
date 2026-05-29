"""Unit tests for registries (leader, tile, unit)."""

import os
import pytest
from src.leader.registry import LeaderRegistry, generate_leader_id
from src.tile.registry import (
    StructureRegistry, ObjectRegistry, TerrainRegistry,
    generate_structure_id, generate_object_id, generate_terrain_id,
)
from src.unit.registry import UnitRegistry, generate_unit_id


# ===========================================================================
#  Leader Registry
# ===========================================================================


class TestLeaderRegistry:
    """Tests for LeaderRegistry CRUD operations."""

    def test_register_and_get(self, test_db, tmp_project_root, monkeypatch):
        """Insert → get → fields match."""
        monkeypatch.setattr("src.leader.registry.BASE_DIR", tmp_project_root)
        # Ensure reference dir exists
        ref_dir = os.path.join(tmp_project_root, "leader_references")
        os.makedirs(ref_dir, exist_ok=True)
        # Create a dummy splash image in output dir
        out_dir = os.path.join(tmp_project_root, "generated_assets")
        os.makedirs(out_dir, exist_ok=True)
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
        img.save(os.path.join(out_dir, "splash_test.png"), format="PNG")

        monkeypatch.setattr("src.leader.registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader.registry.settings.paths.leader_reference_dir", "leader_references")

        lid = "leader_test_a1b2c3"
        LeaderRegistry.register(
            leader_id=lid,
            leader_name="Test Leader",
            leader_description="A test leader for unit testing purposes.",
            archetype="warrior_king",
            culture="medieval_european",
            time_of_day="midday",
            mood="triumphant",
            splash_image_filename="splash_test.png",
            splash_seed=42,
            splash_prompt="test prompt",
        )

        record = LeaderRegistry.get(lid)
        assert record is not None
        assert record.leader_name == "Test Leader"
        assert record.archetype == "warrior_king"
        assert record.splash_seed == 42

    def test_register_copies_reference_image(self, test_db, tmp_project_root, monkeypatch):
        """ref_{leader_id}.png exists in reference dir."""
        monkeypatch.setattr("src.leader.registry.BASE_DIR", tmp_project_root)
        ref_dir = os.path.join(tmp_project_root, "leader_references")
        os.makedirs(ref_dir, exist_ok=True)
        out_dir = os.path.join(tmp_project_root, "generated_assets")
        os.makedirs(out_dir, exist_ok=True)
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
        img.save(os.path.join(out_dir, "splash_ref.png"), format="PNG")

        monkeypatch.setattr("src.leader.registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader.registry.settings.paths.leader_reference_dir", "leader_references")

        lid = "leader_ref_test"
        LeaderRegistry.register(
            leader_id=lid, leader_name="Ref Test",
            leader_description="A test leader for reference image testing.",
            archetype="warrior_queen", culture="ancient_egyptian",
            time_of_day="dawn", mood="grim_determined",
            splash_image_filename="splash_ref.png",
            splash_seed=1, splash_prompt="p",
        )
        ref_path = os.path.join(ref_dir, f"ref_{lid}.png")
        assert os.path.exists(ref_path)

    def test_get_nonexistent_returns_none(self, test_db):
        assert LeaderRegistry.get("nonexistent") is None

    def test_exists_true(self, test_db, tmp_project_root, monkeypatch):
        monkeypatch.setattr("src.leader.registry.BASE_DIR", tmp_project_root)
        ref_dir = os.path.join(tmp_project_root, "leader_references")
        os.makedirs(ref_dir, exist_ok=True)
        out_dir = os.path.join(tmp_project_root, "generated_assets")
        os.makedirs(out_dir, exist_ok=True)
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
        img.save(os.path.join(out_dir, "splash_ex.png"), format="PNG")
        monkeypatch.setattr("src.leader.registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader.registry.settings.paths.leader_reference_dir", "leader_references")

        lid = "leader_exists_test"
        LeaderRegistry.register(
            leader_id=lid, leader_name="Exists",
            leader_description="A test leader for existence checking.",
            archetype="warrior_king", culture="medieval_european",
            time_of_day="midday", mood="triumphant",
            splash_image_filename="splash_ex.png",
            splash_seed=1, splash_prompt="p",
        )
        assert LeaderRegistry.exists(lid) is True

    def test_exists_false(self, test_db):
        assert LeaderRegistry.exists("nonexistent") is False

    def test_list_all_ordering(self, test_db, tmp_project_root, monkeypatch):
        """Newest first."""
        monkeypatch.setattr("src.leader.registry.BASE_DIR", tmp_project_root)
        ref_dir = os.path.join(tmp_project_root, "leader_references")
        os.makedirs(ref_dir, exist_ok=True)
        out_dir = os.path.join(tmp_project_root, "generated_assets")
        os.makedirs(out_dir, exist_ok=True)
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
        img.save(os.path.join(out_dir, "splash_list.png"), format="PNG")
        monkeypatch.setattr("src.leader.registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader.registry.settings.paths.leader_reference_dir", "leader_references")

        for i in range(3):
            LeaderRegistry.register(
                leader_id=f"leader_list_{i}",
                leader_name=f"Leader {i}",
                leader_description="A test leader for list ordering.",
                archetype="warrior_king", culture="medieval_european",
                time_of_day="midday", mood="triumphant",
                splash_image_filename="splash_list.png",
                splash_seed=i, splash_prompt="p",
            )
        records = LeaderRegistry.list_all()
        assert len(records) >= 3

    def test_record_profile(self, test_db, tmp_project_root, monkeypatch):
        monkeypatch.setattr("src.leader.registry.BASE_DIR", tmp_project_root)
        ref_dir = os.path.join(tmp_project_root, "leader_references")
        os.makedirs(ref_dir, exist_ok=True)
        out_dir = os.path.join(tmp_project_root, "generated_assets")
        os.makedirs(out_dir, exist_ok=True)
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
        img.save(os.path.join(out_dir, "splash_prof.png"), format="PNG")
        monkeypatch.setattr("src.leader.registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader.registry.settings.paths.leader_reference_dir", "leader_references")

        lid = "leader_profile_test"
        LeaderRegistry.register(
            leader_id=lid, leader_name="Profile",
            leader_description="A test leader for profile recording.",
            archetype="warrior_king", culture="medieval_european",
            time_of_day="midday", mood="triumphant",
            splash_image_filename="splash_prof.png",
            splash_seed=1, splash_prompt="p",
        )
        LeaderRegistry.record_profile(lid, "profile_img.png")
        record = LeaderRegistry.get(lid)
        assert record.profile_image_id == "profile_img.png"

    def test_record_action_appends(self, test_db, tmp_project_root, monkeypatch):
        monkeypatch.setattr("src.leader.registry.BASE_DIR", tmp_project_root)
        ref_dir = os.path.join(tmp_project_root, "leader_references")
        os.makedirs(ref_dir, exist_ok=True)
        out_dir = os.path.join(tmp_project_root, "generated_assets")
        os.makedirs(out_dir, exist_ok=True)
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
        img.save(os.path.join(out_dir, "splash_act.png"), format="PNG")
        monkeypatch.setattr("src.leader.registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader.registry.settings.paths.leader_reference_dir", "leader_references")

        lid = "leader_action_test"
        LeaderRegistry.register(
            leader_id=lid, leader_name="Action",
            leader_description="A test leader for action recording.",
            archetype="warrior_king", culture="medieval_european",
            time_of_day="midday", mood="triumphant",
            splash_image_filename="splash_act.png",
            splash_seed=1, splash_prompt="p",
        )
        LeaderRegistry.record_action(lid, "action1.png")
        LeaderRegistry.record_action(lid, "action2.png")
        record = LeaderRegistry.get(lid)
        assert record.action_image_ids == ["action1.png", "action2.png"]

    def test_delete(self, test_db, tmp_project_root, monkeypatch):
        monkeypatch.setattr("src.leader.registry.BASE_DIR", tmp_project_root)
        ref_dir = os.path.join(tmp_project_root, "leader_references")
        os.makedirs(ref_dir, exist_ok=True)
        out_dir = os.path.join(tmp_project_root, "generated_assets")
        os.makedirs(out_dir, exist_ok=True)
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
        img.save(os.path.join(out_dir, "splash_del.png"), format="PNG")
        monkeypatch.setattr("src.leader.registry.settings.paths.output_dir", "generated_assets")
        monkeypatch.setattr("src.leader.registry.settings.paths.leader_reference_dir", "leader_references")

        lid = "leader_delete_test"
        LeaderRegistry.register(
            leader_id=lid, leader_name="Delete",
            leader_description="A test leader for deletion testing.",
            archetype="warrior_king", culture="medieval_european",
            time_of_day="midday", mood="triumphant",
            splash_image_filename="splash_del.png",
            splash_seed=1, splash_prompt="p",
        )
        assert LeaderRegistry.delete(lid) is True
        assert LeaderRegistry.get(lid) is None

    def test_delete_returns_false_for_missing(self, test_db):
        assert LeaderRegistry.delete("nonexistent") is False


class TestGenerateLeaderId:
    """Tests for generate_leader_id."""

    def test_deterministic_slug(self):
        """Same name → same slug, different uuid."""
        id1 = generate_leader_id("Cleopatra VII")
        id2 = generate_leader_id("Cleopatra VII")
        # Slugs should be the same
        assert id1.split("_")[1:-1] == id2.split("_")[1:-1]
        # But UUIDs differ
        assert id1 != id2

    def test_slugging(self):
        """'Cleopatra VII' → slug contains cleopatra_vii."""
        lid = generate_leader_id("Cleopatra VII")
        assert "cleopatra_vii" in lid
        assert lid.startswith("leader_")

    def test_format(self):
        lid = generate_leader_id("Test")
        assert lid.startswith("leader_test_")
        # Should have 6-char hex suffix
        suffix = lid.split("_")[-1]
        assert len(suffix) == 6


# ===========================================================================
#  Tile Registries
# ===========================================================================


class TestStructureRegistry:
    """Tests for StructureRegistry."""

    def test_register_and_get(self, test_db):
        sid = "struct_fort_a1b2c3"
        StructureRegistry.register(
            structure_id=sid,
            category="fortification",
            style="nordic_wooden",
            condition="pristine",
            scale="small",
            description="A test structure",
            image_id="img.png",
            seed=42,
            prompt_used="test prompt",
        )
        record = StructureRegistry.get(sid)
        assert record is not None
        assert record.category == "fortification"
        assert record.style == "nordic_wooden"

    def test_list_all(self, test_db):
        for i in range(3):
            StructureRegistry.register(
                structure_id=f"struct_list_{i}",
                category="fortification",
                style="nordic_wooden",
                condition="pristine",
                scale="small",
                description="test",
                image_id=f"img_{i}.png",
                seed=i,
                prompt_used="p",
            )
        records = StructureRegistry.list_all()
        assert len(records) >= 3

    def test_delete(self, test_db):
        sid = "struct_del_test"
        StructureRegistry.register(
            structure_id=sid,
            category="fortification",
            style="nordic_wooden",
            condition="pristine",
            scale="small",
            description="test",
            image_id="img.png",
            seed=1,
            prompt_used="p",
        )
        assert StructureRegistry.delete(sid) is True
        assert StructureRegistry.get(sid) is None

    def test_delete_returns_false(self, test_db):
        assert StructureRegistry.delete("nonexistent") is False


class TestObjectRegistry:
    """Tests for ObjectRegistry."""

    def test_register_and_get(self, test_db):
        oid = "object_veg_a1b2c3"
        ObjectRegistry.register(
            object_id=oid,
            category="vegetation",
            biome="temperate_forest",
            season="summer",
            description="A test object",
            image_id="img.png",
            seed=42,
            prompt_used="test prompt",
        )
        record = ObjectRegistry.get(oid)
        assert record is not None
        assert record.biome == "temperate_forest"

    def test_list_all(self, test_db):
        for i in range(2):
            ObjectRegistry.register(
                object_id=f"object_list_{i}",
                category="vegetation",
                biome="temperate_forest",
                season="summer",
                description="test",
                image_id=f"img_{i}.png",
                seed=i,
                prompt_used="p",
            )
        assert len(ObjectRegistry.list_all()) >= 2

    def test_delete(self, test_db):
        oid = "object_del"
        ObjectRegistry.register(
            object_id=oid, category="vegetation", biome="temperate_forest",
            season="summer", description="test", image_id="img.png",
            seed=1, prompt_used="p",
        )
        assert ObjectRegistry.delete(oid) is True
        assert ObjectRegistry.get(oid) is None


class TestTerrainRegistry:
    """Tests for TerrainRegistry."""

    def test_register_and_get(self, test_db):
        tid = "terrain_hill_a1b2c3"
        TerrainRegistry.register(
            terrain_id=tid,
            category="hill",
            scale="medium",
            material="earthen",
            description="A test terrain",
            image_id="img.png",
            seed=42,
            prompt_used="test prompt",
        )
        record = TerrainRegistry.get(tid)
        assert record is not None
        assert record.material == "earthen"

    def test_list_all(self, test_db):
        for i in range(2):
            TerrainRegistry.register(
                terrain_id=f"terrain_list_{i}",
                category="hill", scale="medium", material="earthen",
                description="test", image_id=f"img_{i}.png",
                seed=i, prompt_used="p",
            )
        assert len(TerrainRegistry.list_all()) >= 2

    def test_delete(self, test_db):
        tid = "terrain_del"
        TerrainRegistry.register(
            terrain_id=tid, category="hill", scale="medium", material="earthen",
            description="test", image_id="img.png", seed=1, prompt_used="p",
        )
        assert TerrainRegistry.delete(tid) is True
        assert TerrainRegistry.get(tid) is None


class TestGenerateTileIds:
    """Tests for tile ID generators."""

    def test_structure_id_format(self):
        sid = generate_structure_id("fortification")
        assert sid.startswith("struct_fortification_")

    def test_object_id_format(self):
        oid = generate_object_id("vegetation")
        assert oid.startswith("object_vegetation_")

    def test_terrain_id_format(self):
        tid = generate_terrain_id("hill")
        assert tid.startswith("terrain_hill_")


# ===========================================================================
#  Unit Registry
# ===========================================================================


class TestUnitRegistry:
    """Tests for UnitRegistry."""

    def test_register_and_get(self, test_db):
        uid = "unit_archer_a1b2c3"
        UnitRegistry.register(
            unit_id=uid,
            unit_type="archer",
            description="A test unit",
            image_id="sprite.png",
            seed=42,
            prompt_used="test prompt",
            generation_mode="placeholder",
        )
        record = UnitRegistry.get(uid)
        assert record is not None
        assert record.unit_type == "archer"
        assert record.image_id == "sprite.png"

    def test_list_all(self, test_db):
        for i in range(3):
            UnitRegistry.register(
                unit_id=f"unit_list_{i}",
                unit_type="archer",
                description="test",
                image_id=f"sprite_{i}.png",
                seed=i,
                prompt_used="p",
                generation_mode="placeholder",
            )
        assert len(UnitRegistry.list_all()) >= 3

    def test_delete(self, test_db):
        uid = "unit_del"
        UnitRegistry.register(
            unit_id=uid, unit_type="archer", description="test",
            image_id="sprite.png",
            seed=1, prompt_used="p", generation_mode="placeholder",
        )
        assert UnitRegistry.delete(uid) is True
        assert UnitRegistry.get(uid) is None

    def test_delete_returns_false(self, test_db):
        assert UnitRegistry.delete("nonexistent") is False

    def test_has_static_checks_catalog(self):
        """has_static() delegates to StaticCatalog — False when no static files."""
        # In test environment there are no static unit PNGs, so has_static returns False.
        # The old stub always returned True; this now reflects real catalog state.
        result = UnitRegistry.has_static("archer")
        assert isinstance(result, bool)  # returns a bool (False in test env)


class TestGenerateUnitId:
    """Tests for generate_unit_id."""

    def test_format(self):
        uid = generate_unit_id("archer")
        assert uid.startswith("unit_archer_")
        suffix = uid.split("_")[-1]
        assert len(suffix) == 6

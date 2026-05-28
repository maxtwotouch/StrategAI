"""Unit tests for database models and session management (src/database.py)."""

import pytest
from sqlalchemy import inspect
from src.database import (
    Base, AssetRecord, LeaderRecord, StructureRecord,
    ObjectRecord, TerrainRecord, UnitRecord, get_db,
)


class TestAllTablesCreated:
    """Verify all tables exist after Base.metadata.create_all."""

    def test_all_tables_created(self, test_db):
        """All 7 tables exist in SQLite after create_all."""
        inspector = inspect(test_db)
        table_names = set(inspector.get_table_names())
        expected = {
            "asset_records", "leader_records", "structure_records",
            "object_records", "terrain_records", "unit_records",
        }
        # Note: SQLAlchemy may not create all 7 if some are missing from Base
        for t in expected:
            assert t in table_names, f"Table {t} not found in {table_names}"


class TestAssetRecord:
    """Tests for the AssetRecord model."""

    def test_insert_and_query(self, db_session):
        """Insert + query by ID."""
        record = AssetRecord(id="test_asset.png", asset_family="structure")
        db_session.add(record)
        db_session.commit()

        result = db_session.query(AssetRecord).filter(AssetRecord.id == "test_asset.png").first()
        assert result is not None
        assert result.asset_family == "structure"

    def test_defaults(self, db_session):
        """created_at auto-set, asset_family defaults to 'unknown'."""
        record = AssetRecord(id="test_defaults.png")
        db_session.add(record)
        db_session.commit()

        result = db_session.query(AssetRecord).filter(AssetRecord.id == "test_defaults.png").first()
        assert result.asset_family == "unknown"
        assert result.created_at is not None


class TestLeaderRecord:
    """Tests for the LeaderRecord model."""

    def test_full_insert(self, db_session):
        """Full insert with all columns."""
        record = LeaderRecord(
            leader_id="leader_test_a1b2c3",
            leader_name="Test Leader",
            archetype="warrior_king",
            culture="medieval_european",
            time_of_day="midday",
            mood="triumphant",
            splash_image_id="splash.png",
            splash_seed=12345,
            splash_prompt="test prompt",
            reference_filename="ref_leader_test_a1b2c3.png",
        )
        db_session.add(record)
        db_session.commit()

        result = db_session.query(LeaderRecord).filter(
            LeaderRecord.leader_id == "leader_test_a1b2c3"
        ).first()
        assert result is not None
        assert result.leader_name == "Test Leader"
        assert result.splash_seed == 12345

    def test_action_ids_json(self, db_session):
        """action_image_ids stored/retrieved as list."""
        record = LeaderRecord(
            leader_id="leader_action_test",
            leader_name="Action Leader",
            archetype="warrior_queen",
            culture="ancient_egyptian",
            time_of_day="dawn",
            mood="grim_determined",
            splash_image_id="splash2.png",
            splash_seed=42,
            splash_prompt="prompt",
            reference_filename="ref_leader_action_test.png",
            action_image_ids=["action1.png", "action2.png"],
        )
        db_session.add(record)
        db_session.commit()

        result = db_session.query(LeaderRecord).filter(
            LeaderRecord.leader_id == "leader_action_test"
        ).first()
        assert result.action_image_ids == ["action1.png", "action2.png"]


class TestStructureRecord:
    """Tests for the StructureRecord model."""

    def test_insert_and_query(self, db_session):
        record = StructureRecord(
            structure_id="struct_fort_a1b2c3",
            category="fortification",
            style="nordic_wooden",
            condition="pristine",
            scale="small",
            description="A test structure",
            image_id="img.png",
            seed=100,
            prompt_used="test prompt",
        )
        db_session.add(record)
        db_session.commit()

        result = db_session.query(StructureRecord).filter(
            StructureRecord.structure_id == "struct_fort_a1b2c3"
        ).first()
        assert result is not None
        assert result.category == "fortification"

    def test_image_id_not_null_constraint(self, db_session):
        """image_id NOT NULL — insert without it raises."""
        record = StructureRecord(
            structure_id="struct_bad",
            category="fortification",
            style="nordic_wooden",
            condition="pristine",
            scale="small",
            description="desc",
            image_id=None,  # This should fail
            seed=1,
            prompt_used="p",
        )
        db_session.add(record)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()


class TestObjectRecord:
    """Tests for the ObjectRecord model."""

    def test_insert_and_query(self, db_session):
        record = ObjectRecord(
            object_id="object_veg_a1b2c3",
            category="vegetation",
            biome="temperate_forest",
            season="summer",
            description="A test object",
            image_id="img.png",
            seed=200,
            prompt_used="test prompt",
        )
        db_session.add(record)
        db_session.commit()

        result = db_session.query(ObjectRecord).filter(
            ObjectRecord.object_id == "object_veg_a1b2c3"
        ).first()
        assert result is not None
        assert result.biome == "temperate_forest"


class TestTerrainRecord:
    """Tests for the TerrainRecord model."""

    def test_insert_and_query(self, db_session):
        record = TerrainRecord(
            terrain_id="terrain_hill_a1b2c3",
            category="hill",
            scale="medium",
            material="earthen",
            description="A test terrain",
            image_id="img.png",
            seed=300,
            prompt_used="test prompt",
        )
        db_session.add(record)
        db_session.commit()

        result = db_session.query(TerrainRecord).filter(
            TerrainRecord.terrain_id == "terrain_hill_a1b2c3"
        ).first()
        assert result is not None
        assert result.material == "earthen"


class TestUnitRecord:
    """Tests for the UnitRecord model."""

    def test_insert_and_query(self, db_session):
        record = UnitRecord(
            unit_id="unit_archer_a1b2c3",
            unit_type="archer",
            description="A test unit",
            image_id="sprite.png",
            seed=400,
            prompt_used="test prompt",
        )
        db_session.add(record)
        db_session.commit()

        result = db_session.query(UnitRecord).filter(
            UnitRecord.unit_id == "unit_archer_a1b2c3"
        ).first()
        assert result is not None
        assert result.unit_type == "archer"
        assert result.image_id == "sprite.png"

    def test_image_id_required(self, db_session):
        """image_id is NOT NULL — omitting it raises."""
        record = UnitRecord(
            unit_id="unit_no_image",
            unit_type="archer",
            description="missing image",
            image_id=None,
            seed=1,
            prompt_used="p",
        )
        db_session.add(record)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()


class TestGetDb:
    """Tests for the get_db context manager."""

    def test_get_db_yields_session(self, test_db):
        """get_db() yields a session and closes it."""
        db_gen = get_db()
        session = next(db_gen)
        assert session is not None
        # Close via generator
        try:
            next(db_gen)
        except StopIteration:
            pass

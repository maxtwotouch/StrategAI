"""Unit tests for database models and session management (src/database.py)."""

import pytest
from sqlalchemy import inspect
from src.database import (
    Base, AssetRecord, LeaderRecord, StructureRecord,
    ObjectRecord, TerrainRecord, UnitRecord, get_db,
)


def _create_asset(db_session, filename: str, family: str = "structure") -> None:
    """Create a minimal AssetRecord so FK constraints are satisfied."""
    existing = db_session.query(AssetRecord).filter(AssetRecord.id == filename).first()
    if existing is None:
        db_session.add(AssetRecord(id=filename, asset_family=family))
        db_session.flush()


class TestAllTablesCreated:
    """Verify all tables exist after Base.metadata.create_all."""

    def test_all_tables_created(self, test_db):
        """All 7 tables exist in SQLite."""
        inspector = inspect(test_db)
        table_names = set(inspector.get_table_names())
        expected = {
            "asset_records", "leader_records", "structure_records",
            "object_records", "terrain_records", "unit_records",
            "background_tile_records",
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
        _create_asset(db_session, "splash.png", "leader_splash")
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
        _create_asset(db_session, "splash2.png", "leader_splash")
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
        _create_asset(db_session, "img.png", "structure")
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


    def test_insert_and_query(self, db_session):
        _create_asset(db_session, "img.png", "nature_object")
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


    def test_insert_and_query(self, db_session):
        _create_asset(db_session, "img.png", "terrain")
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


    def test_insert_and_query(self, db_session):
        _create_asset(db_session, "sprite.png", "unit")
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


# ===========================================================================
#  Database connectivity verification
# ===========================================================================


class TestVerifyDbConnectivity:
    """Tests for verify_db_connectivity()."""

    def test_healthy_db_returns_true(self, test_db, monkeypatch):
        """All expected tables exist → True."""
        from src.database import verify_db_connectivity
        monkeypatch.setattr("src.database.engine", test_db)
        assert verify_db_connectivity() is True

    def test_missing_tables_returns_false(self, test_db, monkeypatch):
        """Drop a table → False."""
        from src.database import verify_db_connectivity, Base
        monkeypatch.setattr("src.database.engine", test_db)
        # Drop the unit_records table to simulate a missing table
        Base.metadata.tables["unit_records"].drop(bind=test_db)
        assert verify_db_connectivity() is False
        # Recreate for subsequent tests
        Base.metadata.tables["unit_records"].create(bind=test_db)


# ===========================================================================
#  Schema health verification
# ===========================================================================


class TestVerifySchemaHealth:
    """Tests for verify_schema_health()."""

    def test_matching_schema_returns_true(self, test_db, monkeypatch):
        """Freshly created tables match models → (True, [])."""
        from src.database import verify_schema_health
        monkeypatch.setattr("src.database.engine", test_db)
        ok, mismatches = verify_schema_health()
        assert ok is True
        assert mismatches == []

    def test_extra_column_in_db_detected(self, test_db, monkeypatch):
        """A column in the DB but not in the model → mismatch reported."""
        from src.database import verify_schema_health
        monkeypatch.setattr("src.database.engine", test_db)

        # Manually add an extra column to asset_records via raw SQL
        with test_db.connect() as conn:
            conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE asset_records ADD COLUMN stray_column VARCHAR"
                )
            )
            conn.commit()

        ok, mismatches = verify_schema_health()
        assert ok is False
        assert any("stray_column" in m for m in mismatches)

    def test_missing_column_in_db_detected(self, test_db, monkeypatch):
        """Simulate a column missing from DB but present in model.

        We create a temporary in-memory engine whose asset_records table
        lacks one column that the real model has, then verify that
        verify_schema_health() detects the discrepancy.
        """
        from sqlalchemy import create_engine as sa_create_engine, Column, String, Integer, inspect as sa_inspect
        from sqlalchemy.orm import declarative_base as sa_declarative_base

        # Create a separate engine with a deliberately incomplete schema
        stale_engine = sa_create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

        # Copy the real Base metadata but tweak one table
        from src.database import Base
        # Clone metadata to a fresh Base so we don't mutate the real models
        stale_base = sa_declarative_base()
        # Create only asset_records with one fewer column (omit 'coords_y')
        stale_asset = type("StaleAssetRecord", (stale_base,), {
            "__tablename__": "asset_records",
            "__table_args__": {"extend_existing": True},
            "id": Column(String, primary_key=True),
            "asset_family": Column(String, nullable=False, default="unknown"),
            "base_image_id": Column(String, nullable=True),
            "coords_x": Column(Integer, nullable=True),
            # coords_y intentionally omitted
            "inpaints": Column(__import__("sqlalchemy").JSON, nullable=True),
            "created_at": Column(__import__("sqlalchemy").DateTime),
            "updated_at": Column(__import__("sqlalchemy").DateTime),
        })
        stale_base.metadata.create_all(bind=stale_engine)

        # Run schema health against the stale engine
        monkeypatch.setattr("src.database.engine", stale_engine)
        from src.database import verify_schema_health
        ok, mismatches = verify_schema_health()
        # The real AssetRecord model has coords_y, but the stale DB doesn't
        assert ok is False
        assert any("coords_y" in m for m in mismatches)

        # Restore the real test_db engine
        monkeypatch.setattr("src.database.engine", test_db)


# ===========================================================================
#  Database reset
# ===========================================================================


class TestResetDatabase:
    """Tests for reset_database()."""

    def test_reset_preserves_all_tables(self, test_db, monkeypatch):
        """After reset, all expected tables exist and are empty."""
        from src.database import reset_database, Base, SessionLocal
        from sqlalchemy import inspect as sa_inspect

        monkeypatch.setattr("src.database.engine", test_db)
        monkeypatch.setattr("src.database.SessionLocal", SessionLocal)

        # Insert data first
        session = SessionLocal()
        session.add(AssetRecord(id="pre_reset.png", asset_family="test"))
        session.commit()
        session.close()

        # Reset
        reset_database()

        # Verify all tables exist
        inspector = sa_inspect(test_db)
        table_names = set(inspector.get_table_names())
        expected = {
            "asset_records", "leader_records", "structure_records",
            "object_records", "terrain_records", "unit_records",
            "background_tile_records",
        }
        assert expected.issubset(table_names)

        # Verify data is gone
        session = SessionLocal()
        count = session.query(AssetRecord).count()
        session.close()
        assert count == 0

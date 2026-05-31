from __future__ import annotations

import logging
import os
import time as _time_module
from typing import Generator

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    create_engine,
    event,
    exc as sa_exc,
    func,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Place the database at the project root, not inside src/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Import settings lazily to avoid circular imports — config.py imports nothing
# from this module, so it is safe to import at the top.
try:
    from src.config import settings as _cfg
    DATABASE_URL = getattr(_cfg, "database_url", None) or f"sqlite:///{os.path.join(BASE_DIR, 'tilemap.db')}"
except Exception:
    DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'tilemap.db')}"

# Connection pool settings tuned for SQLite under concurrent load.
# SQLite serializes all writes, so more pooled connections just increase
# lock contention.  pool_size=2 keeps one connection for reads and one
# for writes.  max_overflow=5 provides headroom for load spikes without
# overwhelming the single-writer lock.
#
# The pool is sized conservatively for SQLite's single-writer architecture.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=2,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=3600,
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable SQLite PRAGMAs for production safety and concurrency.

    Applied on every new SQLite connection.

    PRAGMAs set:
    - ``foreign_keys=ON`` — enforce FK constraints (off by default).
    - ``journal_mode=WAL`` — Write-Ahead Logging.  Readers and writers
      run concurrently instead of blocking each other.  Critical for any
      multi-user workload.
    - ``busy_timeout=5000`` — wait up to 5 s instead of failing immediately
      with SQLITE_BUSY when another connection holds the write lock.
    - ``synchronous=NORMAL`` — still crash-safe with WAL, but avoids the
      per-transaction fsync penalty of FULL mode for greatly improved
      write throughput.
    """
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
    except Exception:
        pass  # Not SQLite — pragmas not supported
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------------------------------------------------------------------------
#  SQLite busy-retry helper
# ---------------------------------------------------------------------------

_SQLITE_BUSY_RETRIES = 3
_SQLITE_BUSY_BACKOFF_MS = [50, 100, 200]


def _execute_with_busy_retry(session: Session, operation, *args, **kwargs):
    """Execute a database operation with retry on SQLITE_BUSY.

    Even with ``busy_timeout=5000``, extreme write contention can exceed
    the timeout.  This wrapper catches ``OperationalError: database is
    locked`` and retries with exponential backoff (50ms → 100ms → 200ms).

    Usage::

        with SessionLocal() as db:
            _execute_with_busy_retry(db, db.commit)
    """
    last_exc = None
    for attempt in range(_SQLITE_BUSY_RETRIES):
        try:
            return operation(*args, **kwargs)
        except sa_exc.OperationalError as exc:
            msg = str(exc).lower()
            if "database is locked" not in msg and "database is busy" not in msg:
                raise
            last_exc = exc
            if attempt < _SQLITE_BUSY_RETRIES - 1:
                backoff = _SQLITE_BUSY_BACKOFF_MS[attempt] / 1000.0
                logger.warning(
                    "SQLite busy (attempt %d/%d), retrying in %.0fms…",
                    attempt + 1, _SQLITE_BUSY_RETRIES, backoff * 1000,
                )
                _time_module.sleep(backoff)
    raise last_exc  # type: ignore[misc]


class AssetRecord(Base):
    """Central asset registry — one row per generated image file.

    All other record types reference this table via their ``image_id``
    foreign keys.
    """
    __tablename__ = "asset_records"

    id: str = Column(String, primary_key=True, index=True)  # type: ignore[assignment]
    asset_family: str = Column(String, index=True, nullable=False, default="unknown")  # type: ignore[assignment]
    base_image_id: str | None = Column(String, index=True, nullable=True)  # type: ignore[assignment]
    coords_x: int | None = Column(Integer, nullable=True)  # type: ignore[assignment]
    coords_y: int | None = Column(Integer, nullable=True)  # type: ignore[assignment]
    inpaints: list | None = Column(JSON, nullable=True)  # type: ignore[assignment]
    character_name: str | None = Column(String, nullable=True)  # type: ignore[assignment]
    tile_type: str | None = Column(String, nullable=True)  # type: ignore[assignment]
    structure_subtype: str | None = Column(String, nullable=True)  # type: ignore[assignment]
    generation_mode: str | None = Column(String, nullable=True)  # type: ignore[assignment]
    created_at: DateTime = Column(DateTime, server_default=func.now(), index=True)  # type: ignore[assignment]
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())  # type: ignore[assignment]


class LeaderRecord(Base):
    """Leader identity — splash portrait anchors the canonical identity.

    Profile and action images reference this record.  The splash image
    doubles as the reference image for img2img consistency in subsequent
    generations.
    """
    __tablename__ = "leader_records"

    leader_id: str = Column(String, primary_key=True, index=True)  # type: ignore[assignment]
    leader_name: str = Column(String, nullable=False)  # type: ignore[assignment]
    leader_description: str = Column(String, nullable=False, default="")  # type: ignore[assignment]
    archetype: str = Column(String, nullable=False)  # type: ignore[assignment]
    culture: str = Column(String, nullable=False)  # type: ignore[assignment]
    time_of_day: str = Column(String, nullable=False)  # type: ignore[assignment]
    mood: str = Column(String, nullable=False)  # type: ignore[assignment]

    # Canonical identity
    splash_image_id: str = Column(  # type: ignore[assignment]
        String, ForeignKey("asset_records.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    splash_seed: int = Column(Integer, nullable=False)  # type: ignore[assignment]
    splash_prompt: str = Column(String, nullable=False)  # type: ignore[assignment]

    # Subsequent generations
    profile_image_id: str | None = Column(  # type: ignore[assignment]
        String, ForeignKey("asset_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    action_image_ids: list | None = Column(JSON, nullable=True)  # type: ignore[assignment]

    # Reference image
    reference_filename: str = Column(String, nullable=False)  # type: ignore[assignment]

    created_at: DateTime = Column(DateTime, server_default=func.now(), index=True)  # type: ignore[assignment]
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())  # type: ignore[assignment]


class StructureRecord(Base):
    """Generated structure tiles — fortification, production, housing, sacred."""
    __tablename__ = "structure_records"

    structure_id: str = Column(String, primary_key=True, index=True)  # type: ignore[assignment]
    category: str = Column(String, index=True, nullable=False)  # type: ignore[assignment]
    style: str = Column(String, nullable=False)  # type: ignore[assignment]
    condition: str = Column(String, nullable=False)  # type: ignore[assignment]
    scale: str = Column(String, nullable=False)  # type: ignore[assignment]
    description: str = Column(String, nullable=False)  # type: ignore[assignment]
    image_id: str = Column(  # type: ignore[assignment]
        String, ForeignKey("asset_records.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    seed: int = Column(Integer, nullable=False)  # type: ignore[assignment]
    prompt_used: str = Column(String, nullable=False)  # type: ignore[assignment]
    generation_mode: str | None = Column(String, nullable=True)  # type: ignore[assignment]
    created_at: DateTime = Column(DateTime, server_default=func.now(), index=True)  # type: ignore[assignment]
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())  # type: ignore[assignment]


class ObjectRecord(Base):
    """Generated object tiles — vegetation, geological, rural/urban props, debris."""
    __tablename__ = "object_records"

    object_id: str = Column(String, primary_key=True, index=True)  # type: ignore[assignment]
    category: str = Column(String, index=True, nullable=False)  # type: ignore[assignment]
    biome: str = Column(String, nullable=False)  # type: ignore[assignment]
    season: str = Column(String, nullable=False)  # type: ignore[assignment]
    description: str = Column(String, nullable=False)  # type: ignore[assignment]
    image_id: str = Column(  # type: ignore[assignment]
        String, ForeignKey("asset_records.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    seed: int = Column(Integer, nullable=False)  # type: ignore[assignment]
    prompt_used: str = Column(String, nullable=False)  # type: ignore[assignment]
    generation_mode: str | None = Column(String, nullable=True)  # type: ignore[assignment]
    created_at: DateTime = Column(DateTime, server_default=func.now(), index=True)  # type: ignore[assignment]
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())  # type: ignore[assignment]


class TerrainRecord(Base):
    """Generated terrain tiles — hill, cliff, slope, ridge, depression."""
    __tablename__ = "terrain_records"

    terrain_id: str = Column(String, primary_key=True, index=True)  # type: ignore[assignment]
    category: str = Column(String, index=True, nullable=False)  # type: ignore[assignment]
    scale: str = Column(String, nullable=False)  # type: ignore[assignment]
    material: str = Column(String, nullable=False)  # type: ignore[assignment]
    description: str = Column(String, nullable=False)  # type: ignore[assignment]
    image_id: str = Column(  # type: ignore[assignment]
        String, ForeignKey("asset_records.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    seed: int = Column(Integer, nullable=False)  # type: ignore[assignment]
    prompt_used: str = Column(String, nullable=False)  # type: ignore[assignment]
    generation_mode: str | None = Column(String, nullable=True)  # type: ignore[assignment]
    created_at: DateTime = Column(DateTime, server_default=func.now(), index=True)  # type: ignore[assignment]
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())  # type: ignore[assignment]


class UnitRecord(Base):
    """Generated unit sprites — archer, scout, settler, warrior."""
    __tablename__ = "unit_records"

    unit_id: str = Column(String, primary_key=True, index=True)  # type: ignore[assignment]
    unit_type: str = Column(String, index=True, nullable=False)  # type: ignore[assignment]
    description: str | None = Column(String, nullable=True)  # type: ignore[assignment]
    image_id: str = Column(  # type: ignore[assignment]
        String, ForeignKey("asset_records.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    seed: int = Column(Integer, nullable=False)  # type: ignore[assignment]
    prompt_used: str = Column(String, nullable=False)  # type: ignore[assignment]
    generation_mode: str | None = Column(String, nullable=True)  # type: ignore[assignment]
    created_at: DateTime = Column(DateTime, server_default=func.now(), index=True)  # type: ignore[assignment]
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())  # type: ignore[assignment]


class BackgroundTileRecord(Base):
    """Tracks generated background tile assets with tile_type + seed metadata."""
    __tablename__ = "background_tile_records"

    background_tile_id: str = Column(String, primary_key=True)  # type: ignore[assignment]
    tile_type: str = Column(String, nullable=False, index=True)  # type: ignore[assignment]
    seed: int = Column(Integer, nullable=False)  # type: ignore[assignment]
    image_id: str = Column(  # type: ignore[assignment]
        String, ForeignKey("asset_records.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created_at: DateTime = Column(DateTime, server_default=func.now(), index=True)  # type: ignore[assignment]
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Schema management is now handled by Alembic migrations.
# ``alembic upgrade head`` runs automatically in the app lifespan (src/main.py).
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """Yield a database session (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_db_connectivity() -> bool:
    """Check that the database is reachable and all expected tables exist.

    Uses SQLAlchemy's inspector API so the check is database-agnostic.

    Returns True if the database is healthy, False otherwise.
    Called at startup by the application lifespan handler.
    """
    from sqlalchemy import inspect as _sa_inspect
    try:
        inspector = _sa_inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {
            "asset_records", "leader_records", "structure_records",
            "object_records", "terrain_records", "unit_records",
            "background_tile_records",
        }
        missing = expected - tables
        if missing:
            logger.error("Database missing tables: %s", missing)
            return False
        logger.info("Database connectivity verified — %d tables present", len(tables))
        return True
    except Exception as exc:
        logger.error("Database connectivity check failed: %s", exc)
        return False


def verify_schema_health() -> tuple[bool, list[str]]:
    """Compare live DB columns against SQLAlchemy model definitions.

    Returns (ok, mismatches) where *ok* is True when every table's columns
    match the corresponding model, and *mismatches* is a list of
    human-readable descriptions of any discrepancies found.

    This catches the common case where ``tilemap.db`` was created by an
    older version of the code and ``create_all()`` silently skipped it.
    """
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(engine)
    mismatches: list[str] = []

    model_map = {
        "asset_records": AssetRecord,
        "leader_records": LeaderRecord,
        "structure_records": StructureRecord,
        "object_records": ObjectRecord,
        "terrain_records": TerrainRecord,
        "unit_records": UnitRecord,
        "background_tile_records": BackgroundTileRecord,
    }

    for table_name, model in model_map.items():
        try:
            db_columns = {col["name"] for col in inspector.get_columns(table_name)}
        except Exception as exc:
            mismatches.append(f"{table_name}: cannot inspect columns — {exc}")
            continue

        model_columns = {c.name for c in model.__table__.columns}

        missing_in_db = model_columns - db_columns
        extra_in_db = db_columns - model_columns

        if missing_in_db:
            mismatches.append(
                f"{table_name}: columns in model but missing from DB: "
                + ", ".join(sorted(missing_in_db))
            )
        if extra_in_db:
            mismatches.append(
                f"{table_name}: columns in DB but not in model: "
                + ", ".join(sorted(extra_in_db))
            )

    if mismatches:
        for msg in mismatches:
            logger.critical("Schema mismatch: %s", msg)
        logger.critical(
            "Database schema is out of sync with models. "
            "Restart with DATABASE_RESET=true or delete tilemap.db to recreate."
        )
        return False, mismatches

    logger.info("Schema health check passed — %d tables match models", len(model_map))
    return True, []


def reset_database() -> None:
    """Drop all tables and recreate them from Alembic migrations.

    **Destructive** — all data is lost.  Intended for development and as
    an escape hatch when the schema has diverged.

    Refuses to run in PRODUCTION mode to prevent accidental data loss.
    """
    from src.config import settings as _settings, DeploymentMode as _DeploymentMode
    if _settings.mode == _DeploymentMode.PRODUCTION:
        raise RuntimeError(
            "reset_database() is blocked in PRODUCTION mode. "
            "Set DEPLOYMENT_MODE=development to use this escape hatch."
        )

    import os
    logger.warning("Resetting database — dropping all tables and recreating.")
    Base.metadata.drop_all(bind=engine)
    # Use create_all for in-memory SQLite (tests); Alembic for persistent DBs
    engine_url = str(engine.url)
    if ":memory:" in engine_url or engine_url == "sqlite://":
        Base.metadata.create_all(bind=engine)
        logger.info("Database reset complete — tables recreated via create_all (in-memory).")
    else:
        try:
            from alembic.config import Config as AlembicConfig
            from alembic import command as alembic_command
            alembic_cfg = AlembicConfig(os.path.join(BASE_DIR, "alembic.ini"))
            alembic_cfg.set_main_option("sqlalchemy.url", engine_url)
            alembic_command.upgrade(alembic_cfg, "head")
            logger.info("Database reset complete — all tables recreated via Alembic migrations.")
        except Exception as exc:
            logger.warning("Alembic migration failed (%s), falling back to create_all.", exc)
            Base.metadata.create_all(bind=engine)
            # Stamp the Alembic version head so subsequent migrations
            # know the schema is current and won't attempt duplicate DDL.
            try:
                alembic_command.stamp(alembic_cfg, "head")
                logger.info("Alembic version stamped after create_all fallback.")
            except Exception as stamp_exc:
                logger.warning("Failed to stamp Alembic version: %s", stamp_exc)
            logger.info("Database reset complete — all tables recreated via create_all.")

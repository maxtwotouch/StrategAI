from __future__ import annotations

import logging
import os
from typing import Generator

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    create_engine,
    func,
    text,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Place the database at the project root, not inside src/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'tilemap.db')}"

# Connection pool settings — conservative defaults for SQLite.
# For PostgreSQL in production, increase pool_size (e.g. 20) and add
# pool_pre_ping=True, pool_recycle=3600.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


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
    created_at: DateTime = Column(DateTime, server_default=func.now())  # type: ignore[assignment]
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
        nullable=False, index=True,
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

    created_at: DateTime = Column(DateTime, server_default=func.now())  # type: ignore[assignment]
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

# ---------------------------------------------------------------------------
# PRODUCTION WARNING: Base.metadata.create_all() is a development convenience
# that creates tables only if they don't exist.  It does NOT handle schema
# changes (ALTER TABLE, column drops, renames).
#
# For production deployments you MUST use Alembic migrations:
#   1. alembic init migrations
#   2. alembic revision --autogenerate -m "initial"
#   3. alembic upgrade head
#
# create_all() is retained here for zero-dependency development and testing.
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_db_connectivity() -> bool:
    """Check that the database is reachable and all expected tables exist.

    Returns True if the database is healthy, False otherwise.
    Called at startup by the application lifespan handler.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            tables = {row[0] for row in result}
        expected = {
            "asset_records", "leader_records", "structure_records",
            "object_records", "terrain_records", "unit_records",
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

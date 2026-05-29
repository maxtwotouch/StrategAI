"""Unit registry — SQLite-backed persistence for unit sprite records.

Stores a single image ID per unit (south-facing front view) and provides
CRUD operations through the same pattern as StructureRegistry / ObjectRegistry /
TerrainRegistry.
"""

from __future__ import annotations

import uuid
import logging

from sqlalchemy.orm import Session

from src.database import SessionLocal, UnitRecord
from src.storage import store

logger = logging.getLogger(__name__)


def generate_unit_id(unit_type: str) -> str:
    """Create a deterministic, human-readable unit ID.

    Example: ``"unit_archer_a1b2c3"``
    """
    short = uuid.uuid4().hex[:6]
    return f"unit_{unit_type}_{short}"


class UnitRegistry:
    """CRUD operations for UnitRecord rows."""

    # ------------------------------------------------------------------
    #  Create
    # ------------------------------------------------------------------

    @staticmethod
    def register(
        unit_id: str,
        unit_type: str,
        description: str,
        image_id: str,
        seed: int,
        prompt_used: str,
        generation_mode: str,
        session: Session | None = None,
    ) -> None:
        """Persist a new unit record.

        If *session* is provided the caller owns the transaction.
        """
        _close = session is None
        db = session or SessionLocal()
        try:
            record = UnitRecord(
                unit_id=unit_id,
                unit_type=unit_type,
                description=description,
                image_id=image_id,
                seed=seed,
                prompt_used=prompt_used,
                generation_mode=generation_mode,
            )
            db.add(record)
            if _close:
                db.commit()
            logger.info("Unit registered: %s (%s)", unit_id, unit_type)
        finally:
            if _close:
                db.close()

    # ------------------------------------------------------------------
    #  Read
    # ------------------------------------------------------------------

    @staticmethod
    def get(unit_id: str) -> UnitRecord | None:
        """Return a single unit record by ID, or None."""
        with SessionLocal() as db:
            return db.query(UnitRecord).filter(UnitRecord.unit_id == unit_id).first()

    @staticmethod
    def list_all() -> list[UnitRecord]:
        """Return all unit records, newest first."""
        with SessionLocal() as db:
            return (
                db.query(UnitRecord)
                .order_by(UnitRecord.created_at.desc())
                .all()
            )

    @staticmethod
    def has_static(unit_type: str) -> bool:
        """Return True if a static sprite exists for this unit type.

        Delegates to ``StaticCatalog.has_unit_type()`` which scans
        ``static_tiles/unit/`` for matching PNG files.
        """
        from src.static_catalog import catalog as _catalog
        return _catalog.has_unit_type(unit_type)

    # ------------------------------------------------------------------
    #  Delete
    # ------------------------------------------------------------------

    @staticmethod
    def delete(unit_id: str) -> bool:
        """Remove a unit record.  Returns True if a row was deleted."""
        with SessionLocal() as db:
            record = db.query(UnitRecord).filter(UnitRecord.unit_id == unit_id).first()
            if record is None:
                return False
            image_id = record.image_id
            db.delete(record)
            db.commit()
            # Best-effort cleanup of the image file on disk
            try:
                store.delete(image_id)
            except Exception as exc:
                logger.warning(
                    "Failed to delete image file %s for unit %s: %s",
                    image_id, unit_id, exc,
                )
            logger.info("Unit deleted: %s", unit_id)
            return True
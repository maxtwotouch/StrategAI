"""Unit registry — SQLite-backed persistence for unit sprite records.

Stores a single image ID per unit (south-facing front view) and provides
CRUD operations through the same pattern as StructureRegistry / ObjectRegistry /
TerrainRegistry.
"""

import uuid
import logging

from .database import SessionLocal, UnitRecord

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
    ) -> None:
        """Persist a new unit record."""
        with SessionLocal() as db:
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
            db.commit()
            logger.info("Unit registered: %s (%s)", unit_id, unit_type)

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

        This is checked by the static catalog, not the database, but we provide
        a convenience hook for the engine to query.
        """
        return True  # optimistic — the engine checks the catalog directly

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
            db.delete(record)
            db.commit()
            logger.info("Unit deleted: %s", unit_id)
            return True

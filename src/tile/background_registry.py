"""Registry for background tile asset records."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.database import SessionLocal, BackgroundTileRecord
from src.storage import store

logger = logging.getLogger(__name__)


class BackgroundTileRegistry:
    """CRUD operations for BackgroundTileRecord."""

    @staticmethod
    def register(
        background_tile_id: str,
        tile_type: str,
        seed: int,
        image_filename: str,
        *,
        session: Session | None = None,
    ) -> None:
        """Create a new background tile record."""
        _close = session is None
        db = session or SessionLocal()
        try:
            record = BackgroundTileRecord(
                background_tile_id=background_tile_id,
                tile_type=tile_type,
                seed=seed,
                image_id=image_filename,
            )
            db.add(record)
            if _close:
                db.commit()
            logger.info("Background tile registered: %s (%s)", background_tile_id, tile_type)
        finally:
            if _close:
                db.close()

    @staticmethod
    def get(background_tile_id: str) -> BackgroundTileRecord | None:
        """Get a background tile record by ID."""
        with SessionLocal() as db:
            return (
                db.query(BackgroundTileRecord)
                .filter(BackgroundTileRecord.background_tile_id == background_tile_id)
                .first()
            )

    @staticmethod
    def list_all(limit: int = 50, offset: int = 0) -> list[BackgroundTileRecord]:
        """List background tile records with pagination."""
        with SessionLocal() as db:
            return (
                db.query(BackgroundTileRecord)
                .order_by(BackgroundTileRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

    @staticmethod
    def delete(background_tile_id: str) -> bool:
        """Delete a background tile record and its generated image file. Returns True if deleted."""
        with SessionLocal() as db:
            record = (
                db.query(BackgroundTileRecord)
                .filter(BackgroundTileRecord.background_tile_id == background_tile_id)
                .first()
            )
            if record:
                image_id = record.image_id
                db.delete(record)
                db.commit()
                # Best-effort cleanup of the image file on disk
                try:
                    store.delete(image_id)
                except (FileNotFoundError, OSError) as exc:
                    logger.warning(
                        "Failed to delete image file %s for background tile %s: %s",
                        image_id, background_tile_id, exc,
                    )
                logger.info("Background tile deleted: %s", background_tile_id)
                return True
            return False

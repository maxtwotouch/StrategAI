"""Leader registry backed by SQLite via SQLAlchemy.

Replaces the guide's JSON-file approach. Thread-safe, queryable,
and integrated with the existing database infrastructure.
"""

import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.config import settings, BASE_DIR
from src.database import SessionLocal, AssetRecord, LeaderRecord
from src.storage import store

logger = logging.getLogger(__name__)


def generate_leader_id(leader_name: str) -> str:
    """Generate a deterministic, URL-safe leader ID.

    Format: leader_{slugified_name}_{short_uuid}
    Example: leader_cleopatra_vii_a1b2c3
    """
    slug = re.sub(r'[^a-z0-9]+', '_', leader_name.lower()).strip('_')[:40]
    return f"leader_{slug}_{uuid.uuid4().hex[:6]}"


class LeaderRegistry:
    """CRUD operations for leader records. Uses SQLAlchemy sessions."""

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    @staticmethod
    def register(
        leader_id: str,
        leader_name: str,
        leader_description: str,
        archetype: str,
        culture: str,
        time_of_day: str,
        mood: str,
        splash_image_filename: str,
        splash_seed: int,
        splash_prompt: str,
        session: Session | None = None,
    ) -> str:
        """Register a new leader after splash generation.

        Copies the splash image to the reference directory as ref_{leader_id}.png
        and inserts a LeaderRecord.

        If *session* is provided the caller owns the transaction.
        Returns the reference filename.
        """
        ref_name = f"ref_{leader_id}.png"

        # Copy splash → reference directory.
        # If the DB insert fails, clean up the copied file so we don't
        # leave an orphaned reference image.
        src = Path(os.path.join(BASE_DIR, settings.paths.output_dir)) / splash_image_filename
        dst = Path(os.path.join(BASE_DIR, settings.paths.leader_reference_dir)) / ref_name
        shutil.copy2(src, dst)
        logger.info("Copied splash → reference image: %s", ref_name)

        _close = session is None
        db = session or SessionLocal()
        try:
            record = LeaderRecord(
                leader_id=leader_id,
                leader_name=leader_name,
                leader_description=leader_description,
                archetype=archetype,
                culture=culture,
                time_of_day=time_of_day,
                mood=mood,
                splash_image_id=splash_image_filename,
                splash_seed=splash_seed,
                splash_prompt=splash_prompt,
                reference_filename=ref_name,
                profile_image_id=None,
                action_image_ids=None,
            )
            db.add(record)
            if _close:
                db.commit()
            logger.info("Leader registered: %s (%s)", leader_name, leader_id)
        except Exception:
            if _close:
                db.rollback()
            # Clean up the reference file we already copied
            if dst.exists():
                dst.unlink()
                logger.warning("Cleaned up orphaned reference file after DB failure: %s", ref_name)
            raise
        finally:
            if _close:
                db.close()

        return ref_name

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def get(leader_id: str) -> Optional[LeaderRecord]:
        """Return a LeaderRecord or None."""
        with SessionLocal() as db:
            return db.query(LeaderRecord).filter(
                LeaderRecord.leader_id == leader_id
            ).first()

    @staticmethod
    def exists(leader_id: str) -> bool:
        """Check if a leader_id is registered."""
        with SessionLocal() as db:
            return db.query(LeaderRecord).filter(
                LeaderRecord.leader_id == leader_id
            ).first() is not None

    @staticmethod
    def list_all(limit: int = 50, offset: int = 0) -> list[LeaderRecord]:
        """Return all registered leaders, most recent first."""
        with SessionLocal() as db:
            return db.query(LeaderRecord).order_by(
                LeaderRecord.created_at.desc()
            ).offset(offset).limit(limit).all()

    @staticmethod
    def count_all() -> int:
        """Return the total number of registered leaders."""
        with SessionLocal() as db:
            return db.query(LeaderRecord).count()

    @staticmethod
    def get_reference_filename(leader_id: str) -> Optional[str]:
        """Return the reference image filename or None."""
        leader = LeaderRegistry.get(leader_id)
        return leader.reference_filename if leader else None

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    @staticmethod
    def record_profile(
        leader_id: str,
        image_filename: str,
        session: Session | None = None,
    ) -> None:
        """Record a profile image for an existing leader."""
        _close = session is None
        db = session or SessionLocal()
        try:
            leader = db.query(LeaderRecord).filter(
                LeaderRecord.leader_id == leader_id
            ).first()
            if leader:
                leader.profile_image_id = image_filename
                if _close:
                    db.commit()
                logger.info("Profile recorded for leader: %s", leader_id)
        finally:
            if _close:
                db.close()

    @staticmethod
    def record_action(
        leader_id: str,
        image_filename: str,
        session: Session | None = None,
    ) -> None:
        """Append an action image to the leader's action_image_ids list.

        Uses ``SELECT ... FOR UPDATE`` to acquire a row-level lock,
        preventing lost updates when two concurrent requests append to
        the same leader's action list.
        """
        _close = session is None
        db = session or SessionLocal()
        try:
            leader = (
                db.query(LeaderRecord)
                .with_for_update()
                .filter(LeaderRecord.leader_id == leader_id)
                .first()
            )
            if leader:
                ids = list(leader.action_image_ids or [])
                ids.append(image_filename)
                leader.action_image_ids = ids
                flag_modified(leader, "action_image_ids")
                if _close:
                    db.commit()
                logger.info("Action recorded for leader: %s", leader_id)
        finally:
            if _close:
                db.close()

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    @staticmethod
    def delete(leader_id: str) -> bool:
        """Remove a leader and clean up their reference image and all generated assets.

        Returns True if a leader was deleted, False if not found.
        """
        # Clean up reference image
        ref_name = f"ref_{leader_id}.png"
        ref_path = Path(os.path.join(BASE_DIR, settings.paths.leader_reference_dir)) / ref_name
        if ref_path.exists():
            ref_path.unlink()

        with SessionLocal() as db:
            leader = db.query(LeaderRecord).filter(
                LeaderRecord.leader_id == leader_id
            ).first()
            if leader:
                # Collect all image filenames to clean up from disk
                image_ids_to_clean = []
                if leader.splash_image_id:
                    image_ids_to_clean.append(leader.splash_image_id)
                if leader.profile_image_id:
                    image_ids_to_clean.append(leader.profile_image_id)
                if leader.action_image_ids:
                    image_ids_to_clean.extend(leader.action_image_ids)

                db.delete(leader)
                db.commit()

                # Best-effort cleanup of generated image files on disk
                for image_id in image_ids_to_clean:
                    try:
                        store.delete(image_id)
                    except (FileNotFoundError, OSError) as exc:
                        logger.warning(
                            "Failed to delete image file %s for leader %s: %s",
                            image_id, leader_id, exc,
                        )
                # Note: AssetRecords are NOT deleted here because
                # splash_image_id is NOT NULL with ondelete=SET NULL —
                # deleting the parent AssetRecord would violate the
                # constraint.  Profile/action AssetRecords are cleaned up
                # via ON DELETE CASCADE when the leader row is removed.
                logger.info("Leader deleted: %s", leader_id)
                return True
        return False
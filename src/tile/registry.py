"""Tile registry — CRUD for StructureRecord, ObjectRecord, and TerrainRecord.

Mirrors the LeaderRegistry pattern: SQLite-backed, thread-safe, queryable.
Each asset type has its own table and ID prefix.
"""

import logging
import re
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.database import SessionLocal, AssetRecord, StructureRecord, ObjectRecord, TerrainRecord
from src.storage import store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  ID generators (deterministic, URL-safe)
# ---------------------------------------------------------------------------

def generate_structure_id(category: str) -> str:
    """struct_{category}_{short_uuid}"""
    slug = re.sub(r'[^a-z0-9]+', '_', category.lower()).strip('_')[:20]
    return f"struct_{slug}_{uuid.uuid4().hex[:6]}"


def generate_object_id(category: str) -> str:
    """object_{category}_{short_uuid}"""
    slug = re.sub(r'[^a-z0-9]+', '_', category.lower()).strip('_')[:20]
    return f"object_{slug}_{uuid.uuid4().hex[:6]}"


def generate_terrain_id(category: str) -> str:
    """terrain_{category}_{short_uuid}"""
    slug = re.sub(r'[^a-z0-9]+', '_', category.lower()).strip('_')[:20]
    return f"terrain_{slug}_{uuid.uuid4().hex[:6]}"


# ===========================================================================
#  Structure Registry
# ===========================================================================

class StructureRegistry:
    """CRUD for structure_records."""

    @staticmethod
    def register(
        structure_id: str,
        category: str,
        style: str,
        condition: str,
        scale: str,
        description: str,
        image_id: str,
        seed: int,
        prompt_used: str,
        generation_mode: str = "comfyui",
        session: Session | None = None,
    ) -> None:
        """Persist a new structure record.

        If *session* is provided the caller owns the transaction (commit/rollback).
        Otherwise a temporary session is created and committed immediately.
        """
        _close = session is None
        db = session or SessionLocal()
        try:
            db.add(StructureRecord(
                structure_id=structure_id,
                category=category,
                style=style,
                condition=condition,
                scale=scale,
                description=description,
                image_id=image_id,
                seed=seed,
                prompt_used=prompt_used,
                generation_mode=generation_mode,
            ))
            if _close:
                db.commit()
            logger.info("Structure registered: %s (%s)", structure_id, category)
        finally:
            if _close:
                db.close()

    @staticmethod
    def get(structure_id: str) -> Optional[StructureRecord]:
        with SessionLocal() as db:
            return db.query(StructureRecord).filter(
                StructureRecord.structure_id == structure_id
            ).first()

    @staticmethod
    def list_all(limit: int = 50, offset: int = 0) -> list[StructureRecord]:
        with SessionLocal() as db:
            return db.query(StructureRecord).order_by(
                StructureRecord.created_at.desc()
            ).offset(offset).limit(limit).all()

    @staticmethod
    def count_all() -> int:
        with SessionLocal() as db:
            return db.query(StructureRecord).count()

    @staticmethod
    def delete(structure_id: str) -> bool:
        with SessionLocal() as db:
            record = db.query(StructureRecord).filter(
                StructureRecord.structure_id == structure_id
            ).first()
            if record:
                image_id = record.image_id
                db.delete(record)
                # Also delete the parent AssetRecord to prevent orphan leaks
                db.query(AssetRecord).filter(AssetRecord.id == image_id).delete()
                db.commit()
                # Best-effort cleanup of the image file on disk
                try:
                    store.delete(image_id)
                except (FileNotFoundError, OSError) as exc:
                    logger.warning(
                        "Failed to delete image file %s for structure %s: %s",
                        image_id, structure_id, exc,
                    )
                logger.info("Structure deleted: %s", structure_id)
                return True
        return False


# ===========================================================================
#  Object Registry
# ===========================================================================

class ObjectRegistry:
    """CRUD for object_records."""

    @staticmethod
    def register(
        object_id: str,
        category: str,
        biome: str,
        season: str,
        description: str,
        image_id: str,
        seed: int,
        prompt_used: str,
        generation_mode: str = "comfyui",
        session: Session | None = None,
    ) -> None:
        _close = session is None
        db = session or SessionLocal()
        try:
            db.add(ObjectRecord(
                object_id=object_id,
                category=category,
                biome=biome,
                season=season,
                description=description,
                image_id=image_id,
                seed=seed,
                prompt_used=prompt_used,
                generation_mode=generation_mode,
            ))
            if _close:
                db.commit()
            logger.info("Object registered: %s (%s)", object_id, category)
        finally:
            if _close:
                db.close()

    @staticmethod
    def get(object_id: str) -> Optional[ObjectRecord]:
        with SessionLocal() as db:
            return db.query(ObjectRecord).filter(
                ObjectRecord.object_id == object_id
            ).first()

    @staticmethod
    def list_all(limit: int = 50, offset: int = 0) -> list[ObjectRecord]:
        with SessionLocal() as db:
            return db.query(ObjectRecord).order_by(
                ObjectRecord.created_at.desc()
            ).offset(offset).limit(limit).all()

    @staticmethod
    def count_all() -> int:
        with SessionLocal() as db:
            return db.query(ObjectRecord).count()

    @staticmethod
    def delete(object_id: str) -> bool:
        with SessionLocal() as db:
            record = db.query(ObjectRecord).filter(
                ObjectRecord.object_id == object_id
            ).first()
            if record:
                image_id = record.image_id
                db.delete(record)
                # Also delete the parent AssetRecord to prevent orphan leaks
                db.query(AssetRecord).filter(AssetRecord.id == image_id).delete()
                db.commit()
                try:
                    store.delete(image_id)
                except (FileNotFoundError, OSError) as exc:
                    logger.warning(
                        "Failed to delete image file %s for object %s: %s",
                        image_id, object_id, exc,
                    )
                logger.info("Object deleted: %s", object_id)
                return True
        return False


# ===========================================================================
#  Terrain Registry
# ===========================================================================

class TerrainRegistry:
    """CRUD for terrain_records."""

    @staticmethod
    def register(
        terrain_id: str,
        category: str,
        scale: str,
        material: str,
        description: str,
        image_id: str,
        seed: int,
        prompt_used: str,
        generation_mode: str = "comfyui",
        session: Session | None = None,
    ) -> None:
        _close = session is None
        db = session or SessionLocal()
        try:
            db.add(TerrainRecord(
                terrain_id=terrain_id,
                category=category,
                scale=scale,
                material=material,
                description=description,
                image_id=image_id,
                seed=seed,
                prompt_used=prompt_used,
                generation_mode=generation_mode,
            ))
            if _close:
                db.commit()
            logger.info("Terrain registered: %s (%s)", terrain_id, category)
        finally:
            if _close:
                db.close()

    @staticmethod
    def get(terrain_id: str) -> Optional[TerrainRecord]:
        with SessionLocal() as db:
            return db.query(TerrainRecord).filter(
                TerrainRecord.terrain_id == terrain_id
            ).first()

    @staticmethod
    def list_all(limit: int = 50, offset: int = 0) -> list[TerrainRecord]:
        with SessionLocal() as db:
            return db.query(TerrainRecord).order_by(
                TerrainRecord.created_at.desc()
            ).offset(offset).limit(limit).all()

    @staticmethod
    def count_all() -> int:
        with SessionLocal() as db:
            return db.query(TerrainRecord).count()

    @staticmethod
    def delete(terrain_id: str) -> bool:
        with SessionLocal() as db:
            record = db.query(TerrainRecord).filter(
                TerrainRecord.terrain_id == terrain_id
            ).first()
            if record:
                image_id = record.image_id
                db.delete(record)
                # Also delete the parent AssetRecord to prevent orphan leaks
                db.query(AssetRecord).filter(AssetRecord.id == image_id).delete()
                db.commit()
                try:
                    store.delete(image_id)
                except (FileNotFoundError, OSError) as exc:
                    logger.warning(
                        "Failed to delete image file %s for terrain %s: %s",
                        image_id, terrain_id, exc,
                    )
                logger.info("Terrain deleted: %s", terrain_id)
                return True
        return False
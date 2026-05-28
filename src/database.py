import os
from sqlalchemy import create_engine, Column, String, Integer, JSON, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker

# Place the database at the project root, not inside src/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'tilemap.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class AssetRecord(Base):
    __tablename__ = "asset_records"

    id = Column(String, primary_key=True, index=True)
    asset_family = Column(String, index=True, nullable=False, default="unknown")
    base_image_id = Column(String, index=True, nullable=True)
    coords_x = Column(Integer, nullable=True)
    coords_y = Column(Integer, nullable=True)
    inpaints = Column(JSON, nullable=True)
    character_name = Column(String, nullable=True)
    tile_type = Column(String, nullable=True)
    structure_subtype = Column(String, nullable=True)
    generation_mode = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class LeaderRecord(Base):
    __tablename__ = "leader_records"

    leader_id = Column(String, primary_key=True, index=True)
    leader_name = Column(String, nullable=False)
    leader_description = Column(String, nullable=False, default="")
    archetype = Column(String, nullable=False)
    culture = Column(String, nullable=False)
    time_of_day = Column(String, nullable=False)
    mood = Column(String, nullable=False)

    # Canonical identity
    splash_image_id = Column(String, nullable=False)         # FK → asset_records.id
    splash_seed = Column(Integer, nullable=False)            # canonical seed for profile/action consistency
    splash_prompt = Column(String, nullable=False)           # debug / reproducibility

    # Subsequent generations
    profile_image_id = Column(String, nullable=True)
    action_image_ids = Column(JSON, nullable=True)           # list of asset IDs

    # Reference image
    reference_filename = Column(String, nullable=False)      # "ref_{leader_id}.png"

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class StructureRecord(Base):
    __tablename__ = "structure_records"

    structure_id = Column(String, primary_key=True, index=True)
    category = Column(String, nullable=False)
    style = Column(String, nullable=False)
    condition = Column(String, nullable=False)
    scale = Column(String, nullable=False)
    description = Column(String, nullable=False)
    image_id = Column(String, nullable=False)
    seed = Column(Integer, nullable=False)
    prompt_used = Column(String, nullable=False)
    generation_mode = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ObjectRecord(Base):
    __tablename__ = "object_records"

    object_id = Column(String, primary_key=True, index=True)
    category = Column(String, nullable=False)
    biome = Column(String, nullable=False)
    season = Column(String, nullable=False)
    description = Column(String, nullable=False)
    image_id = Column(String, nullable=False)
    seed = Column(Integer, nullable=False)
    prompt_used = Column(String, nullable=False)
    generation_mode = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class TerrainRecord(Base):
    __tablename__ = "terrain_records"

    terrain_id = Column(String, primary_key=True, index=True)
    category = Column(String, nullable=False)
    scale = Column(String, nullable=False)
    material = Column(String, nullable=False)
    description = Column(String, nullable=False)
    image_id = Column(String, nullable=False)
    seed = Column(Integer, nullable=False)
    prompt_used = Column(String, nullable=False)
    generation_mode = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class UnitRecord(Base):
    __tablename__ = "unit_records"

    unit_id = Column(String, primary_key=True, index=True)
    unit_type = Column(String, nullable=False)
    description = Column(String, nullable=True)

    # Four directional sprite image IDs (FK → asset_records.id)
    image_id_s = Column(String, nullable=False)       # south/front (canonical, always present)
    image_id_n = Column(String, nullable=True)        # north/back  (null when not generated)
    image_id_e = Column(String, nullable=True)        # east/right  (null when not generated)
    image_id_w = Column(String, nullable=True)        # west/left   (null when not generated)

    seed = Column(Integer, nullable=False)
    prompt_used = Column(String, nullable=False)
    generation_mode = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

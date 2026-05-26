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


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

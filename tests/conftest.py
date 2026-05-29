"""Shared fixtures for the test suite.

Provides temp directories, in-memory SQLite, AssetStore, StaticCatalog,
httpx async client, mock ComfyUI client, sample requests, and a sample PNG.
"""

import os
import io
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ===========================================================================
#  Temp project root
# ===========================================================================


@pytest.fixture
def tmp_project_root():
    """Create a temporary directory with the minimal project skeleton.

    Contains: static_tiles/, generated_assets/, splash_assets/,
    leader_references/, config.yaml, config/prompt_templates.json.
    """
    root = tempfile.mkdtemp(prefix="test_project_")

    # Subdirectories
    for d in ["static_tiles", "generated_assets", "splash_assets", "leader_references", "config"]:
        os.makedirs(os.path.join(root, d), exist_ok=True)

    # config.yaml
    with open(os.path.join(root, "config.yaml"), "w") as f:
        f.write("host: 0.0.0.0\nport: 8000\n")

    # prompt_templates.json
    templates = {
        "schema_version": 1,
        "templates": {
            "structure": "<tdp> {PROMPT_HERE}. Pixel art.",
            "object": "<tdp> {PROMPT_HERE}. Pixel art.",
            "terrain": "<tdp> {PROMPT_HERE}. Pixel art.",
        },
    }
    import json
    with open(os.path.join(root, "config", "prompt_templates.json"), "w") as f:
        json.dump(templates, f)

    yield root

    shutil.rmtree(root, ignore_errors=True)


# ===========================================================================
#  Settings
# ===========================================================================


@pytest.fixture
def test_settings(tmp_project_root, monkeypatch):
    """Return a Settings instance pointed at the temp project root.

    Overrides BASE_DIR so all path-derived properties resolve inside tmp_project_root.
    """
    monkeypatch.setattr("src.config.BASE_DIR", tmp_project_root)
    monkeypatch.setattr("src.storage.BASE_DIR", tmp_project_root)
    monkeypatch.setattr("src.leader.registry.BASE_DIR", tmp_project_root)
    monkeypatch.setattr("src.leader.engine.BASE_DIR", tmp_project_root)

    # Force reimport of settings to pick up the new BASE_DIR
    from src.config import Settings
    s = Settings()
    # Override modes to placeholder for safe testing
    s.generation.modes = {k: "placeholder" for k in s.generation.modes}
    s.generation.default_mode = "placeholder"
    return s


# ===========================================================================
#  Database
# ===========================================================================


@pytest.fixture
def test_db(monkeypatch):
    """In-memory SQLite engine with all tables created.

    Monkeypatches src.database.engine and SessionLocal so all code
    that imports them uses the test database.
    """
    from sqlalchemy.orm import declarative_base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Import Base and all models to ensure they're registered
    from src.database import Base, AssetRecord, LeaderRecord, StructureRecord, ObjectRecord, TerrainRecord, UnitRecord

    Base.metadata.create_all(bind=engine)

    # Monkeypatch the module-level engine + SessionLocal
    monkeypatch.setattr("src.database.engine", engine)
    monkeypatch.setattr("src.database.SessionLocal", SessionLocal)
    monkeypatch.setattr("src.leader.registry.SessionLocal", SessionLocal)
    monkeypatch.setattr("src.tile.registry.SessionLocal", SessionLocal)
    monkeypatch.setattr("src.unit.registry.SessionLocal", SessionLocal)
    monkeypatch.setattr("src.tile.engine.SessionLocal", SessionLocal)
    monkeypatch.setattr("src.leader.engine.SessionLocal", SessionLocal)
    monkeypatch.setattr("src.unit.engine.SessionLocal", SessionLocal)
    monkeypatch.setattr("src.main.SessionLocal", SessionLocal)

    yield engine

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db):
    """SQLAlchemy session from the test database."""
    from src.database import SessionLocal
    session = SessionLocal()
    yield session
    session.close()


# ===========================================================================
#  AssetStore
# ===========================================================================


@pytest.fixture
def test_store(tmp_project_root, monkeypatch):
    """AssetStore pointed at the temp output dir."""
    monkeypatch.setattr("src.storage.BASE_DIR", tmp_project_root)
    from src.storage import AssetStore
    store = AssetStore(max_cache_size=10)
    store._output_dir = os.path.join(tmp_project_root, "generated_assets")
    return store


# ===========================================================================
#  StaticCatalog
# ===========================================================================


@pytest.fixture
def test_catalog_dir(tmp_project_root):
    """Create a controlled static_tiles/ tree for catalog tests."""
    root = os.path.join(tmp_project_root, "static_tiles")

    # background_tile/
    bg = os.path.join(root, "background_tile")
    os.makedirs(bg, exist_ok=True)
    for name in ["water.png", "grass_1.png", "grass_2.png"]:
        _make_empty_png(os.path.join(bg, name))

    # structure/
    struct = os.path.join(root, "structure")
    for sub in ["fortification", "production"]:
        sp = os.path.join(struct, sub)
        os.makedirs(sp, exist_ok=True)
        _make_empty_png(os.path.join(sp, f"{sub}.png"))

    # nature_object/
    nat = os.path.join(root, "nature_object")
    os.makedirs(nat, exist_ok=True)
    _make_empty_png(os.path.join(nat, "tree.png"))

    # character_sprite/
    cs = os.path.join(root, "character_sprite")
    os.makedirs(cs, exist_ok=True)
    _make_empty_png(os.path.join(cs, "knight.png"))

    # unit/
    unit = os.path.join(root, "unit")
    os.makedirs(unit, exist_ok=True)
    for name in ["archer.png", "scout.png"]:
        _make_empty_png(os.path.join(unit, name))

    return root


@pytest.fixture
def test_catalog(test_catalog_dir):
    """StaticCatalog scanning the controlled static_tiles/ tree."""
    from src.static_catalog import StaticCatalog
    return StaticCatalog(root_dir=test_catalog_dir)


# ===========================================================================
#  Async HTTP client
# ===========================================================================


@pytest_asyncio.fixture
async def async_client(test_db, monkeypatch, tmp_project_root):
    """httpx.AsyncClient against the FastAPI app with placeholder mode.

    The app is created with its lifespan, which initializes engines in
    placeholder/static mode.
    """
    # 1. Set BASE_DIR before any module that uses it is imported
    import src.config
    monkeypatch.setattr("src.config.BASE_DIR", tmp_project_root)
    monkeypatch.setattr("src.leader.registry.BASE_DIR", tmp_project_root)
    monkeypatch.setattr("src.leader.engine.BASE_DIR", tmp_project_root)
    monkeypatch.setattr("src.storage.BASE_DIR", tmp_project_root)

    # 2. Mutate the actual src.config.settings in-place
    import src.config as config_mod
    config_mod.settings.generation.modes = {
        k: "placeholder" for k in config_mod.settings.generation.modes
    }
    config_mod.settings.generation.default_mode = "placeholder"

    # 3. Ensure directories exist
    os.makedirs(os.path.join(tmp_project_root, "leader_references"), exist_ok=True)
    os.makedirs(os.path.join(tmp_project_root, "generated_assets"), exist_ok=True)
    os.makedirs(os.path.join(tmp_project_root, "splash_assets"), exist_ok=True)

    # 4. Patch the global store's output dir to use the temp dir
    import src.storage
    src.storage.store._output_dir = os.path.join(tmp_project_root, "generated_assets")

    from src.main import app, lifespan

    transport = ASGITransport(app=app)

    # Manually enter the lifespan before creating the client,
    # since ASGITransport in httpx 0.28 does not trigger it automatically.
    lifespan_ctx = lifespan(app)
    await lifespan_ctx.__aenter__()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await lifespan_ctx.__aexit__(None, None, None)


# ===========================================================================
#  Mock ComfyUI client
# ===========================================================================


@pytest.fixture
def mock_comfyui_client():
    """AsyncMock wrapping ComfyUIClient."""
    mock = AsyncMock()
    mock.base_url = "http://mock:8188"
    mock.timeout = 300
    return mock


# ===========================================================================
#  Sample requests
# ===========================================================================


@pytest.fixture
def sample_requests():
    """Dict of valid request objects for each pipeline."""
    from src.models import GenerationRequest, SplashRequest
    from src.tile.models import StructureRequest, ObjectRequest, TerrainRequest
    from src.leader.models import LeaderRequest
    from src.unit.models import UnitRequest

    return {
        "structure": StructureRequest(
            category="fortification",
            style="nordic_wooden",
            condition="pristine",
            scale="small",
            description="A small wooden watchtower with a pointed roof and a lookout platform.",
        ),
        "object": ObjectRequest(
            category="vegetation",
            biome="temperate_forest",
            season="summer",
            description="A large oak tree with a thick trunk and sprawling branches full of green leaves.",
        ),
        "terrain": TerrainRequest(
            category="hill",
            scale="medium",
            material="earthen",
            description="A rounded grassy hill with gentle slopes on all sides and a flat top.",
        ),
        "generation": GenerationRequest(
            asset_family="background_tile",
            tile_type="grass",
            prompt="A lush green grass tile for a medieval game.",
        ),
        "splash": SplashRequest(
            character_name="Test King",
            title="King",
            description="A wise old king with a long white beard and golden crown.",
        ),
        "leader": LeaderRequest(
            asset_type="splash",
            leader_name="Cleopatra VII",
            leader_description="A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
            archetype="warrior_queen",
            culture="ancient_egyptian",
            time_of_day="golden_hour",
            mood="triumphant",
        ),
        "unit": UnitRequest(
            unit_type="archer",
            description="A medieval archer in green leather armor with a longbow and a quiver of arrows.",
        ),
    }


# ===========================================================================
#  Sample PNG
# ===========================================================================


@pytest.fixture
def sample_png():
    """A minimal 16x16 RGBA PIL Image."""
    return Image.new("RGBA", (16, 16), (255, 0, 0, 255))


# ===========================================================================
#  Persistent on-disk SQLite (for schema-mismatch tests)
# ===========================================================================


@pytest.fixture
def test_db_file(monkeypatch):
    """Create a real SQLite file on disk (not in-memory) with all tables.

    Unlike ``test_db`` (which uses ``:memory:``), this creates a temporary
    file so tests can verify behaviour against a persistent database —
    including stale-schema detection and the DATABASE_RESET escape hatch.

    Yields the engine; the temp file is cleaned up after the test.
    """
    import tempfile
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="test_tilemap_")
    os.close(fd)

    try:
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        from src.database import Base
        Base.metadata.create_all(bind=engine)

        monkeypatch.setattr("src.database.engine", engine)
        monkeypatch.setattr("src.database.SessionLocal", SessionLocal)
        monkeypatch.setattr("src.leader.registry.SessionLocal", SessionLocal)
        monkeypatch.setattr("src.tile.registry.SessionLocal", SessionLocal)
        monkeypatch.setattr("src.unit.registry.SessionLocal", SessionLocal)
        monkeypatch.setattr("src.tile.engine.SessionLocal", SessionLocal)
        monkeypatch.setattr("src.leader.engine.SessionLocal", SessionLocal)
        monkeypatch.setattr("src.unit.engine.SessionLocal", SessionLocal)
        monkeypatch.setattr("src.main.SessionLocal", SessionLocal)

        yield engine
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


# ===========================================================================
#  Helpers
# ===========================================================================


def _make_empty_png(path: str) -> None:
    """Create a minimal 1x1 RGBA PNG at the given path."""
    img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
    img.save(path, format="PNG")


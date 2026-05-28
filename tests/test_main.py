"""Integration tests for FastAPI endpoints (src/main.py).

Tests the full HTTP layer: request → validation → engine → response.
All tests use placeholder mode so no external ComfyUI is needed.
"""

import pytest
from httpx import ASGITransport, AsyncClient


# ===========================================================================
#  Health & Modes
# ===========================================================================


class TestHealth:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_health_ok(self, async_client):
        resp = await async_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "modes" in data
        assert "leaders_registered" in data
        assert "units_registered" in data

    @pytest.mark.asyncio
    async def test_health_comfyui_disconnected(self, async_client):
        """In placeholder mode, comfyui_connected is False."""
        resp = await async_client.get("/health")
        data = resp.json()
        assert data["comfyui_connected"] is False


class TestModes:
    """Tests for GET /modes."""

    @pytest.mark.asyncio
    async def test_modes_returns_all_families(self, async_client):
        resp = await async_client.get("/modes")
        assert resp.status_code == 200
        data = resp.json()
        assert "modes" in data
        assert "valid_modes" in data
        # All 10 families present
        families = data["modes"]
        assert "structure" in families
        assert "leader" in families
        assert "unit" in families


# ===========================================================================
#  Catalog
# ===========================================================================


class TestCatalog:
    """Tests for GET /catalog."""

    @pytest.mark.asyncio
    async def test_catalog_returns_structure(self, async_client):
        resp = await async_client.get("/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "background_tile" in data
        assert "structure" in data
        assert "nature_object" in data
        assert "character_sprite" in data


# ===========================================================================
#  Assets
# ===========================================================================


class TestAssets:
    """Tests for GET /assets/{filename}."""

    @pytest.mark.asyncio
    async def test_asset_not_found(self, async_client):
        resp = await async_client.get("/assets/nonexistent.png")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_asset_found(self, async_client, test_store, monkeypatch):
        """After generating a structure, the asset URL returns 200."""
        monkeypatch.setattr("src.main.store", test_store)
        from PIL import Image
        img = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
        test_store.save_image("test_asset.png", img)

        resp = await async_client.get("/assets/test_asset.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"


# ===========================================================================
#  Structure endpoints
# ===========================================================================


class TestStructureEndpoints:
    """Tests for POST/GET/DELETE /structure and /structure/catalog."""

    @pytest.mark.asyncio
    async def test_generate_structure(self, async_client):
        resp = await async_client.post("/structure", json={
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a lookout platform.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "structure"
        assert data["category"] == "fortification"
        assert data["url"].startswith("/assets/")
        assert data["asset_id"].startswith("struct_")
        assert data["generation_mode"] == "static"

    @pytest.mark.asyncio
    async def test_generate_structure_validation_error(self, async_client):
        """Missing required field → 422."""
        resp = await async_client.post("/structure", json={
            "category": "fortification",
            # missing style, condition, scale, description
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_structures(self, async_client):
        """GET /structure returns list."""
        # Generate one first
        await async_client.post("/structure", json={
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a lookout platform.",
        })
        resp = await async_client.get("/structure")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_structure_by_id(self, async_client):
        """GET /structure/{id} returns the structure."""
        gen_resp = await async_client.post("/structure", json={
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a lookout platform.",
        })
        asset_id = gen_resp.json()["asset_id"]

        resp = await async_client.get(f"/structure/{asset_id}")
        assert resp.status_code == 200
        assert resp.json()["asset_id"] == asset_id

    @pytest.mark.asyncio
    async def test_get_structure_not_found(self, async_client):
        resp = await async_client.get("/structure/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_structure(self, async_client):
        gen_resp = await async_client.post("/structure", json={
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a lookout platform.",
        })
        asset_id = gen_resp.json()["asset_id"]

        resp = await async_client.delete(f"/structure/{asset_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Verify gone
        get_resp = await async_client.get(f"/structure/{asset_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_structure_catalog(self, async_client):
        resp = await async_client.get("/structure/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert "styles" in data
        assert "conditions" in data
        assert "scales" in data
        assert "fortification" in data["categories"]


# ===========================================================================
#  Object endpoints
# ===========================================================================


class TestObjectEndpoints:
    """Tests for POST/GET/DELETE /object and /object/catalog."""

    @pytest.mark.asyncio
    async def test_generate_object(self, async_client):
        resp = await async_client.post("/object", json={
            "category": "vegetation",
            "biome": "temperate_forest",
            "season": "summer",
            "description": "A large oak tree with a thick trunk and sprawling branches full of green leaves.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "object"
        assert data["category"] == "vegetation"
        assert data["generation_mode"] == "static"

    @pytest.mark.asyncio
    async def test_list_objects(self, async_client):
        await async_client.post("/object", json={
            "category": "vegetation",
            "biome": "temperate_forest",
            "season": "summer",
            "description": "A large oak tree with a thick trunk and sprawling branches full of green leaves.",
        })
        resp = await async_client.get("/object")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_object_by_id(self, async_client):
        gen_resp = await async_client.post("/object", json={
            "category": "vegetation",
            "biome": "temperate_forest",
            "season": "summer",
            "description": "A large oak tree with a thick trunk and sprawling branches full of green leaves.",
        })
        asset_id = gen_resp.json()["asset_id"]
        resp = await async_client.get(f"/object/{asset_id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_object(self, async_client):
        gen_resp = await async_client.post("/object", json={
            "category": "vegetation",
            "biome": "temperate_forest",
            "season": "summer",
            "description": "A large oak tree with a thick trunk and sprawling branches full of green leaves.",
        })
        asset_id = gen_resp.json()["asset_id"]
        resp = await async_client.delete(f"/object/{asset_id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_object_catalog(self, async_client):
        resp = await async_client.get("/object/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert "biomes" in data
        assert "seasons" in data


# ===========================================================================
#  Terrain endpoints
# ===========================================================================


class TestTerrainEndpoints:
    """Tests for POST/GET/DELETE /terrain and /terrain/catalog."""

    @pytest.mark.asyncio
    async def test_generate_terrain(self, async_client):
        resp = await async_client.post("/terrain", json={
            "category": "hill",
            "scale": "medium",
            "material": "earthen",
            "description": "A rounded grassy hill with gentle slopes on all sides and a flat top.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "terrain"
        assert data["category"] == "hill"
        assert data["generation_mode"] == "placeholder"

    @pytest.mark.asyncio
    async def test_list_terrains(self, async_client):
        await async_client.post("/terrain", json={
            "category": "hill",
            "scale": "medium",
            "material": "earthen",
            "description": "A rounded grassy hill with gentle slopes on all sides and a flat top.",
        })
        resp = await async_client.get("/terrain")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_terrain_by_id(self, async_client):
        gen_resp = await async_client.post("/terrain", json={
            "category": "hill",
            "scale": "medium",
            "material": "earthen",
            "description": "A rounded grassy hill with gentle slopes on all sides and a flat top.",
        })
        asset_id = gen_resp.json()["asset_id"]
        resp = await async_client.get(f"/terrain/{asset_id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_terrain(self, async_client):
        gen_resp = await async_client.post("/terrain", json={
            "category": "hill",
            "scale": "medium",
            "material": "earthen",
            "description": "A rounded grassy hill with gentle slopes on all sides and a flat top.",
        })
        asset_id = gen_resp.json()["asset_id"]
        resp = await async_client.delete(f"/terrain/{asset_id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_terrain_catalog(self, async_client):
        resp = await async_client.get("/terrain/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert "scales" in data
        assert "materials" in data


# ===========================================================================
#  Leader endpoints
# ===========================================================================


class TestLeaderEndpoints:
    """Tests for POST/GET/DELETE /leader."""

    @pytest.mark.asyncio
    async def test_generate_splash(self, async_client):
        resp = await async_client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "splash"
        assert data["leader_name"] == "Cleopatra VII"
        assert data["leader_id"].startswith("leader_cleopatra_vii_")
        assert data["generation_mode"] == "static"

    @pytest.mark.asyncio
    async def test_generate_profile(self, async_client):
        """Profile after splash → 200."""
        # Generate splash first
        splash_resp = await async_client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        })
        leader_id = splash_resp.json()["leader_id"]

        # Generate profile
        resp = await async_client.post("/leader", json={
            "asset_type": "profile",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
            "leader_id": leader_id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "profile"
        assert data["leader_id"] == leader_id

    @pytest.mark.asyncio
    async def test_generate_action(self, async_client):
        """Action after splash → 200."""
        splash_resp = await async_client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        })
        leader_id = splash_resp.json()["leader_id"]

        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
            "leader_id": leader_id,
            "action_category": "military",
            "action_description": "Leading troops into battle with sword raised high.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "action"

    @pytest.mark.asyncio
    async def test_profile_without_splash_fails(self, async_client):
        """Profile without prior splash → 400."""
        resp = await async_client.post("/leader", json={
            "asset_type": "profile",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
            "leader_id": "nonexistent",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_leaders(self, async_client):
        """GET /leader returns list."""
        # Generate a splash first
        await async_client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        })

        resp = await async_client.get("/leader")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["leader_name"] == "Cleopatra VII"

    @pytest.mark.asyncio
    async def test_get_leader_by_id(self, async_client):
        splash_resp = await async_client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        })
        leader_id = splash_resp.json()["leader_id"]

        resp = await async_client.get(f"/leader/{leader_id}")
        assert resp.status_code == 200
        assert resp.json()["leader_id"] == leader_id

    @pytest.mark.asyncio
    async def test_get_leader_not_found(self, async_client):
        resp = await async_client.get("/leader/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_leader(self, async_client):
        splash_resp = await async_client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        })
        leader_id = splash_resp.json()["leader_id"]

        resp = await async_client.delete(f"/leader/{leader_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Verify gone
        get_resp = await async_client.get(f"/leader/{leader_id}")
        assert get_resp.status_code == 404


# ===========================================================================
#  Unit endpoints
# ===========================================================================


class TestUnitEndpoints:
    """Tests for POST/GET/DELETE /unit and /unit/catalog."""

    @pytest.mark.asyncio
    async def test_generate_unit(self, async_client):
        resp = await async_client.post("/unit", json={
            "unit_type": "archer",
            "description": "A medieval archer in green leather armor with a longbow and quiver of arrows.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "unit"
        assert data["unit_type"] == "archer"
        assert data["generation_mode"] == "placeholder"
        assert "directions" in data
        assert data["directions"]["s"].startswith("/assets/")
        assert data["directions"]["n"].startswith("/assets/")
        assert data["directions"]["e"].startswith("/assets/")
        assert data["directions"]["w"].startswith("/assets/")

    @pytest.mark.asyncio
    async def test_list_units(self, async_client):
        await async_client.post("/unit", json={
            "unit_type": "archer",
            "description": "A medieval archer in green leather armor with a longbow and quiver of arrows.",
        })
        resp = await async_client.get("/unit")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_unit_by_id(self, async_client):
        gen_resp = await async_client.post("/unit", json={
            "unit_type": "archer",
            "description": "A medieval archer in green leather armor with a longbow and quiver of arrows.",
        })
        unit_id = gen_resp.json()["unit_id"]

        resp = await async_client.get(f"/unit/{unit_id}")
        assert resp.status_code == 200
        assert resp.json()["unit_id"] == unit_id

    @pytest.mark.asyncio
    async def test_get_unit_not_found(self, async_client):
        resp = await async_client.get("/unit/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_unit(self, async_client):
        gen_resp = await async_client.post("/unit", json={
            "unit_type": "archer",
            "description": "A medieval archer in green leather armor with a longbow and quiver of arrows.",
        })
        unit_id = gen_resp.json()["unit_id"]

        resp = await async_client.delete(f"/unit/{unit_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_unit_catalog(self, async_client):
        resp = await async_client.get("/unit/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "unit_types" in data
        assert "directions" in data
        assert "archer" in data["unit_types"]
        assert "s" in data["directions"]


# ===========================================================================
#  Legacy endpoints
# ===========================================================================


class TestLegacyEndpoints:
    """Tests for /generate and /splash (legacy)."""

    @pytest.mark.asyncio
    async def test_generate_background_tile(self, async_client):
        resp = await async_client.post("/generate", json={
            "asset_family": "background_tile",
            "tile_type": "grass",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_family"] == "background_tile"
        assert data["url"].startswith("/assets/")

    @pytest.mark.asyncio
    async def test_generate_structure_legacy(self, async_client):
        resp = await async_client.post("/generate", json={
            "asset_family": "structure",
            "structure_subtype": "fortification",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_family"] == "structure"

    @pytest.mark.asyncio
    async def test_generate_invalid_family(self, async_client):
        resp = await async_client.post("/generate", json={
            "asset_family": "invalid_family",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_splash(self, async_client):
        resp = await async_client.post("/splash", json={
            "character_name": "Arthur",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["character_name"] == "Arthur"
        assert data["url"].startswith("/assets/")



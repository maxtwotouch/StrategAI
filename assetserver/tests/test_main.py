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
        # In tests, ComfyUI is unreachable so status is "degraded"
        assert data["status"] in ("ok", "degraded")
        assert "components" in data
        assert "database" in data["components"]
        assert "comfyui" in data["components"]
        assert "modes" in data
        assert "registered" in data
        assert "leaders" in data["registered"]
        assert "units" in data["registered"]
        assert "structures" in data["registered"]

    @pytest.mark.asyncio
    async def test_health_comfyui_disconnected(self, async_client):
        """Health endpoint always returns a valid comfyui component status."""
        resp = await async_client.get("/health")
        data = resp.json()
        assert data["components"]["comfyui"] in ("ok", "unhealthy", "unreachable")


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
        # Response completeness (optional fields — may be None in static/placeholder modes)
        if data.get("prompt_used") is not None:
            assert isinstance(data["prompt_used"], str) and len(data["prompt_used"]) > 0
        if data.get("resolution") is not None:
            assert isinstance(data["resolution"], str) and len(data["resolution"]) > 0
        if data.get("generation_time_ms") is not None:
            assert isinstance(data["generation_time_ms"], int) and data["generation_time_ms"] >= 0
        assert isinstance(data["seed"], int)

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
    async def test_generate_with_seed(self, async_client):
        """Providing a seed produces deterministic results."""
        payload = {
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a lookout platform.",
            "seed": 424242,
        }
        resp1 = await async_client.post("/structure", json=payload)
        resp2 = await async_client.post("/structure", json=payload)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["seed"] == 424242
        assert resp2.json()["seed"] == 424242

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
    async def test_generate_object_validation_error(self, async_client):
        """Missing required field → 422."""
        resp = await async_client.post("/object", json={
            "category": "vegetation",
            # missing biome, season, description
        })
        assert resp.status_code == 422

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
        assert data["generation_mode"] == "static"

    @pytest.mark.asyncio
    async def test_generate_terrain_validation_error(self, async_client):
        """Missing required field → 422."""
        resp = await async_client.post("/terrain", json={
            "category": "hill",
            # missing scale, material, description
        })
        assert resp.status_code == 422

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
        # Response completeness (optional fields — may be None in static/placeholder modes)
        if data.get("prompt_used") is not None:
            assert isinstance(data["prompt_used"], str) and len(data["prompt_used"]) > 0
        if data.get("resolution") is not None:
            assert isinstance(data["resolution"], str) and len(data["resolution"]) > 0
        if data.get("generation_time_ms") is not None:
            assert isinstance(data["generation_time_ms"], int) and data["generation_time_ms"] >= 0
        assert isinstance(data["seed"], int)

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

    # ------------------------------------------------------------------
    #  Multi-leader action
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_generate_multi_leader_action(self, async_client):
        """Multi-leader action scene via leader_ids → 200 with leader_ids/leader_names in response."""
        # Generate two leaders first
        lid1 = await self._create_splash(async_client, "Cleopatra VII",
            "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence.")
        lid2 = await self._create_splash(async_client, "Ramesses II",
            "A tall pharaoh with broad shoulders, shaved head, a gold and lapis nemes crown, "
            "and a stern expression of absolute power.")

        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Multi-Scene",
            "leader_description": "Placeholder description ignored when leader_ids is provided for multi-leader action scenes.",
            "leader_ids": [lid1, lid2],
            "archetype": "diplomat",
            "culture": "ancient_egyptian",
            "time_of_day": "midday",
            "mood": "contemplative",
            "action_category": "diplomatic",
            "action_description": "Two pharaohs seated at a long stone table signing a peace treaty.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "action"
        assert data["leader_ids"] == [lid1, lid2]
        assert data["leader_names"] == ["Cleopatra VII", "Ramesses II"]
        assert "prompt_used" in data
        assert len(data["prompt_used"]) > 0
        assert data["url"].startswith("/assets/")
        assert data["generation_mode"] == "static"

    @pytest.mark.asyncio
    async def test_multi_action_empty_leader_ids_422(self, async_client):
        """Empty leader_ids list → 422 (Pydantic validation error)."""
        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Test",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears white linen.",
            "leader_ids": [],
            "archetype": "diplomat",
            "culture": "ancient_egyptian",
            "time_of_day": "midday",
            "mood": "contemplative",
            "action_category": "diplomatic",
            "action_description": "Signing a treaty.",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_multi_action_nonexistent_leader_400(self, async_client):
        """leader_ids with unknown leader → 400."""
        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Test",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears white linen.",
            "leader_ids": ["nonexistent_leader_id"],
            "archetype": "diplomat",
            "culture": "ancient_egyptian",
            "time_of_day": "midday",
            "mood": "contemplative",
            "action_category": "diplomatic",
            "action_description": "Signing a treaty.",
        })
        assert resp.status_code == 400

    # ------------------------------------------------------------------
    #  Action validation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_action_without_category_400(self, async_client):
        """Action without action_category → 422 (Pydantic validation)."""
        lid = await self._create_splash(async_client, "Cleopatra VII",
            "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence.")
        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry. She wears white linen.",
            "leader_id": lid,
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
            "action_description": "Leading troops into battle.",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_action_without_description_400(self, async_client):
        """Action without action_description → 422 (Pydantic validation)."""
        lid = await self._create_splash(async_client, "Cleopatra VII",
            "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence.")
        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry. She wears white linen.",
            "leader_id": lid,
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
            "action_category": "military",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_full_leader_pipeline(self, async_client):
        """Complete pipeline: splash → profile → action → verify registry state."""
        # 1. Splash
        splash = await async_client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. She wears a white linen dress and a nemes headdress.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        })
        assert splash.status_code == 200
        lid = splash.json()["leader_id"]

        # 2. After splash: splash_url present, no profile_url, no action_urls
        leader_info = await async_client.get(f"/leader/{lid}")
        assert leader_info.status_code == 200
        info = leader_info.json()
        assert info["splash_url"] is not None
        assert info["profile_url"] is None
        assert info["action_urls"] == []

        # 3. Profile
        profile = await async_client.post("/leader", json={
            "asset_type": "profile",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry. She wears white linen.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
            "leader_id": lid,
        })
        assert profile.status_code == 200

        # 4. After profile: profile_url now present
        leader_info = await async_client.get(f"/leader/{lid}")
        info = leader_info.json()
        assert info["profile_url"] is not None

        # 5. Action (single)
        action = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry. She wears white linen.",
            "leader_id": lid,
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
            "action_category": "military",
            "action_description": "Leading troops into battle with sword raised high.",
        })
        assert action.status_code == 200

        # 6. After action: action_urls now has 1 entry
        leader_info = await async_client.get(f"/leader/{lid}")
        info = leader_info.json()
        assert len(info["action_urls"]) >= 1

        # 7. Delete
        delete_resp = await async_client.delete(f"/leader/{lid}")
        assert delete_resp.status_code == 200

        # 8. Verify gone
        get_resp = await async_client.get(f"/leader/{lid}")
        assert get_resp.status_code == 404

    # --- helper --------------------------------------------------------

    @staticmethod
    async def _create_splash(client, name: str, description: str) -> str:
        """Create a splash leader and return the leader_id."""
        resp = await client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": name,
            "leader_description": description,
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        })
        assert resp.status_code == 200, f"Splash failed: {resp.text}"
        return resp.json()["leader_id"]

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
        assert data["generation_mode"] == "static"
        assert data["url"].startswith("/assets/")
        assert data["unit_id"].startswith("unit_archer_")
        # Response completeness (optional fields — may be None in static/placeholder modes)
        if data.get("prompt_used") is not None:
            assert isinstance(data["prompt_used"], str) and len(data["prompt_used"]) > 0
        if data.get("resolution") is not None:
            assert isinstance(data["resolution"], str) and len(data["resolution"]) > 0
        if data.get("generation_time_ms") is not None:
            assert isinstance(data["generation_time_ms"], int) and data["generation_time_ms"] >= 0
        assert isinstance(data["seed"], int)

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
        assert "archer" in data["unit_types"]

    @pytest.mark.asyncio
    async def test_generate_unit_rejects_invalid_unit_type(self, async_client):
        """POST /unit with invalid unit_type returns 422."""
        resp = await async_client.post("/unit", json={
            "unit_type": "catapult",
            "description": "A heavy siege weapon with wheels and a tension mechanism.",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_units_returns_paginated(self, async_client):
        """GET /unit returns paginated list with X-Total-Count and X-Has-More headers."""
        # Generate a unit first
        await async_client.post("/unit", json={
            "unit_type": "archer",
            "description": "A medieval archer in green leather armor with a longbow and quiver of arrows.",
        })
        resp = await async_client.get("/unit")
        assert resp.status_code == 200
        assert "x-total-count" in resp.headers
        assert "x-has-more" in resp.headers
        assert int(resp.headers["x-total-count"]) >= 1
        assert resp.headers["x-has-more"] in ("true", "false")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_unit_list_respects_limit(self, async_client):
        """GET /unit?limit=1 returns at most 1 item."""
        # Generate two units
        for _ in range(2):
            await async_client.post("/unit", json={
                "unit_type": "archer",
                "description": "A medieval archer in green leather armor with a longbow and quiver of arrows.",
            })
        resp = await async_client.get("/unit?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) <= 1


# ===========================================================================
#  Schema health — endpoint-level 503 guard
# ===========================================================================


class TestSchemaHealthEndpoint:
    """Verify that DB-dependent endpoints return 503 when _db_schema_ok is False."""

    @pytest.mark.asyncio
    async def test_db_endpoint_503_when_schema_bad(self, async_client, monkeypatch):
        """Any DB-dependent endpoint returns 503 when schema check fails."""
        monkeypatch.setattr("src.main._db_schema_ok", False)

        # Try a few DB-dependent endpoints — all should return 503
        for method, url, payload in [
            ("GET", "/leader", None),
            ("GET", "/structure", None),
            ("GET", "/object", None),
            ("GET", "/terrain", None),
            ("GET", "/unit", None),
            ("DELETE", "/structure/nonexistent", None),
        ]:
            if payload is not None:
                resp = await async_client.request(method, url, json=payload)
            else:
                resp = await async_client.request(method, url)
            assert resp.status_code == 503, f"{method} {url} should return 503"
            detail = resp.json()["detail"]
            assert "DATABASE_RESET" in detail

        # Reset for other tests
        monkeypatch.setattr("src.main._db_schema_ok", True)

    @pytest.mark.asyncio
    async def test_non_db_endpoints_unaffected(self, async_client, monkeypatch):
        """Endpoints that don't touch DB still work when schema is bad."""
        monkeypatch.setattr("src.main._db_schema_ok", False)

        # These endpoints don't read/write the database
        resp = await async_client.get("/modes")
        assert resp.status_code == 200

        resp = await async_client.get("/structure/catalog")
        assert resp.status_code == 200

        # Reset
        monkeypatch.setattr("src.main._db_schema_ok", True)


# ===========================================================================
#  Background tile endpoints
# ===========================================================================


class TestBackgroundTileEndpoints:
    """Tests for POST/GET/DELETE /background_tile and /background_tile/catalog."""

    @pytest.mark.asyncio
    async def test_generate_background_tile(self, async_client):
        """POST /background_tile returns 200 with valid response fields."""
        resp = await async_client.post("/background_tile", json={
            "tile_type": "grass",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "background_tile"
        assert data["tile_type"] == "grass"
        assert data["url"].startswith("/assets/")
        assert data["status"] == "completed"
        assert isinstance(data["seed"], int)
        assert data["seed"] > 0  # Regression: was 0 before fix
        assert data["generation_mode"] in ("comfyui", "static")
        # Response completeness — these should be populated (regression: were null before fix)
        assert data.get("resolution") is not None, "resolution should be populated"
        assert data.get("generation_time_ms") is not None, "generation_time_ms should be populated"
        assert data.get("prompt_used") is not None, "prompt_used should be populated"

    @pytest.mark.asyncio
    async def test_generate_background_tile_with_seed(self, async_client):
        """Providing a seed produces deterministic results."""
        payload = {"tile_type": "water", "seed": 999888}
        resp = await async_client.post("/background_tile", json=payload)
        assert resp.status_code == 200
        assert resp.json()["seed"] == 999888

    @pytest.mark.asyncio
    async def test_background_tile_invalid_type_400(self, async_client):
        """Invalid tile_type → 422 (Pydantic validation)."""
        resp = await async_client.post("/background_tile", json={
            "tile_type": "lava",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_background_tiles(self, async_client):
        """GET /background_tile returns list."""
        await async_client.post("/background_tile", json={"tile_type": "grass"})
        resp = await async_client.get("/background_tile")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_background_tile_catalog(self, async_client):
        """GET /background_tile/catalog returns tile types."""
        resp = await async_client.get("/background_tile/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "tile_types" in data
        assert isinstance(data["tile_types"], list)
        assert "grass" in data["tile_types"]

    @pytest.mark.asyncio
    async def test_delete_background_tile(self, async_client):
        """DELETE /background_tile/{background_tile_id} removes record."""
        gen_resp = await async_client.post("/background_tile", json={
            "tile_type": "grass",
        })
        assert gen_resp.status_code == 200, f"POST failed: {gen_resp.text}"
        data = gen_resp.json()
        bg_tile_id = data["background_tile_id"]

        resp = await async_client.delete(f"/background_tile/{bg_tile_id}")
        assert resp.status_code == 200, f"DELETE failed for {bg_tile_id}: {resp.text}"
        assert resp.json()["status"] == "deleted"

        # Verify gone — second delete should 404
        resp2 = await async_client.delete(f"/background_tile/{bg_tile_id}")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_background_tile_not_found(self, async_client):
        """DELETE nonexistent background tile → 404."""
        resp = await async_client.delete("/background_tile/nonexistent_bg_id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_background_tile_by_id(self, async_client):
        """GET /background_tile/{id} returns the tile."""
        gen_resp = await async_client.post("/background_tile", json={
            "tile_type": "grass",
        })
        bg_tile_id = gen_resp.json()["background_tile_id"]

        resp = await async_client.get(f"/background_tile/{bg_tile_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["background_tile_id"] == bg_tile_id
        assert data["tile_type"] == "grass"

    @pytest.mark.asyncio
    async def test_get_background_tile_not_found(self, async_client):
        """GET /background_tile/{id} with nonexistent id returns 404."""
        resp = await async_client.get("/background_tile/nonexistent_bg_id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_background_tiles_returns_paginated(self, async_client):
        """GET /background_tile returns paginated list with X-Total-Count and X-Has-More headers."""
        await async_client.post("/background_tile", json={"tile_type": "grass"})
        resp = await async_client.get("/background_tile")
        assert resp.status_code == 200
        assert "x-total-count" in resp.headers
        assert "x-has-more" in resp.headers
        assert int(resp.headers["x-total-count"]) >= 1
        assert resp.headers["x-has-more"] in ("true", "false")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_background_tile_list_respects_limit(self, async_client):
        """GET /background_tile?limit=1 returns at most 1 item."""
        for _ in range(2):
            await async_client.post("/background_tile", json={"tile_type": "grass"})
        resp = await async_client.get("/background_tile?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) <= 1


# ===========================================================================
#  Response field consistency (regression tests)
# ===========================================================================


class TestResponseFields:
    """Ensure all asset families return consistent response shapes."""

    @pytest.mark.asyncio
    async def test_structure_response_has_resolution_and_timing(self, async_client):
        """Regression: static mode responses must include resolution and generation_time_ms."""
        resp = await async_client.post("/structure", json={
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a lookout platform.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("resolution") is not None, \
            "structure response must have resolution (regression: was null for static mode)"
        assert data.get("generation_time_ms") is not None, \
            "structure response must have generation_time_ms (regression: was null for static mode)"

    @pytest.mark.asyncio
    async def test_object_response_has_resolution_and_timing(self, async_client):
        """Regression: static object responses must include resolution and generation_time_ms."""
        resp = await async_client.post("/object", json={
            "category": "vegetation",
            "biome": "temperate_forest",
            "season": "summer",
            "description": "A large oak tree with a thick trunk and sprawling branches full of green leaves.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("resolution") is not None, \
            "object response must have resolution"
        assert data.get("generation_time_ms") is not None, \
            "object response must have generation_time_ms"

    @pytest.mark.asyncio
    async def test_multi_action_seed_not_zero(self, async_client):
        """Regression: multi-leader action seed must not be 0 (was hardcoded)."""
        # Create a splash first
        splash = await async_client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": "Multi Action Test Leader",
            "leader_description": "A regal monarch with a commanding presence, wearing an ornate golden crown and deep crimson robes, standing before a great audience hall.",
            "archetype": "warrior_king",
            "culture": "medieval_european",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        })
        assert splash.status_code == 200
        lid = splash.json()["leader_id"]

        # Multi-leader action
        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Multi Action Test Leader",
            "leader_description": "A regal monarch with a commanding presence, wearing an ornate golden crown and deep crimson robes.",
            "archetype": "warrior_king",
            "culture": "medieval_european",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
            "leader_ids": [lid],
            "action_category": "military",
            "action_description": "Leading a grand cavalry charge across the battlefield with banners flying high.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["seed"] > 0, \
            f"multi-action seed should be > 0, got {data['seed']} (regression: was hardcoded to 0)"
        assert data["leader_ids"] == [lid]
        assert lid in data["leader_ids"]


# ===========================================================================
#  Pagination (cross-endpoint)
# ===========================================================================


class TestPagination:
    """Tests for pagination across list endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", [
        "/leader", "/structure", "/object", "/terrain", "/unit", "/background_tile"
    ])
    async def test_list_endpoint_supports_limit(self, async_client, endpoint):
        """All list endpoints support ?limit= query param and return ≤limit items."""
        resp = await async_client.get(f"{endpoint}?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) <= 2
        assert "x-total-count" in resp.headers
        assert "x-has-more" in resp.headers

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", [
        "/leader", "/structure", "/object", "/terrain", "/unit", "/background_tile"
    ])
    async def test_list_endpoint_supports_offset(self, async_client, endpoint):
        """All list endpoints support ?offset= query param without error."""
        resp = await async_client.get(f"{endpoint}?offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert "x-total-count" in resp.headers

    @pytest.mark.asyncio
    async def test_limit_clamped_to_maximum(self, async_client):
        """?limit=99999 is clamped to the configured maximum (200) and does not 500."""
        resp = await async_client.get("/leader?limit=99999")
        # Should either succeed with clamped limit or return 422 for exceeding max
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) <= 200  # max limit


# ===========================================================================
#  Multi-leader action (additional edge cases)
# ===========================================================================


class TestMultiLeaderAction:
    """Tests for multi-leader action generation."""

    @pytest.mark.asyncio
    async def test_multi_leader_action_requires_leader_ids(self, async_client):
        """POST /leader with asset_type=action and leader_ids list succeeds."""
        # Create two leaders first
        lid1 = await self._create_splash(async_client, "Julius Caesar",
            "A tall Roman general with short cropped dark hair, a prominent aquiline nose, "
            "deep-set brown eyes, and a clean-shaven angular face. He wears a white toga "
            "with a purple stripe over a crimson tunic, with a laurel wreath on his head.")
        lid2 = await self._create_splash(async_client, "Vercingetorix",
            "A Gallic chieftain with long braided blond hair, a thick drooping mustache, "
            "fierce blue eyes, and a muscular build. He wears chainmail armor with a torc "
            "around his neck and carries a long iron sword.")

        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Gaul Surrender",
            "leader_description": "Two leaders meeting after battle — one victorious Roman, "
                "one defiant Gallic chieftain standing across a wooden table.",
            "leader_ids": [lid1, lid2],
            "archetype": "diplomat",
            "culture": "roman_imperial",
            "time_of_day": "midday",
            "mood": "grim_determined",
            "action_category": "diplomatic",
            "action_description": "Vercingetorix throws down his sword at Caesar's feet "
                "in surrender as Roman soldiers look on.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "action"
        assert data["leader_ids"] == [lid1, lid2]
        assert data["leader_names"] == ["Julius Caesar", "Vercingetorix"]
        assert data["url"].startswith("/assets/")
        assert isinstance(data["seed"], int)
        assert data["seed"] > 0

    @pytest.mark.asyncio
    async def test_multi_action_single_leader_ok(self, async_client):
        """Multi-leader action with a single leader_id is accepted (≥1 required)."""
        lid = await self._create_splash(async_client, "Single Leader",
            "A lone warrior king with broad shoulders and a shaved head, wearing silver "
            "plate armor with an azure cape, standing tall with a greatsword planted before him.")
        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Single Leader",
            "leader_description": "A lone warrior king with broad shoulders and a shaved head, "
                "wearing silver plate armor with an azure cape.",
            "leader_ids": [lid],
            "archetype": "warrior_king",
            "culture": "medieval_european",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
            "action_category": "military",
            "action_description": "The warrior king stands atop a hill surveying the battlefield "
                "after a decisive victory.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_type"] == "action"
        assert data["leader_ids"] == [lid]

    @pytest.mark.asyncio
    async def test_multi_action_missing_action_category_422(self, async_client):
        """Multi-leader action without action_category → 422."""
        lid = await self._create_splash(async_client, "Test Leader MC",
            "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. "
            "She wears a white linen dress and a nemes headdress with a golden cobra emblem.")
        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Test Leader MC",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry. "
                "She wears white linen and a nemes headdress.",
            "leader_ids": [lid],
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
            "action_description": "Leading troops into battle.",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_multi_action_missing_description_422(self, async_client):
        """Multi-leader action without action_description → 422."""
        lid = await self._create_splash(async_client, "Test Leader MD",
            "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. "
            "She wears a white linen dress and a nemes headdress with a golden cobra emblem.")
        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Test Leader MD",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry. "
                "She wears white linen and a nemes headdress.",
            "leader_ids": [lid],
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
            "action_category": "military",
        })
        assert resp.status_code == 422

    # --- helpers --------------------------------------------------------

    @staticmethod
    async def _create_splash(client, name: str, description: str) -> str:
        """Create a splash leader and return the leader_id."""
        resp = await client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": name,
            "leader_description": description,
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        })
        assert resp.status_code == 200, f"Splash failed for {name}: {resp.text}"
        return resp.json()["leader_id"]


# ===========================================================================
#  Rate limiting middleware
# ===========================================================================


class TestRateLimiting:
    """Tests for rate limiting middleware.

    The RateLimitMiddleware creates its token buckets once at app startup with
    the configured rates.  Changing settings.rate_limit.post_rps after startup
    has no effect on the already-instantiated buckets.  These tests therefore
    work with the *default* bucket parameters (burst_size=5, post_rps=2.0) and
    exhaust the burst to trigger 429s.
    """

    async def _drain_post_bucket(self, async_client) -> None:
        """Send enough rapid POST requests to exhaust the burst bucket.

        The default burst_size is 5, so 6 requests in rapid succession
        should produce at least one 429 once the burst is consumed.
        """
        # First enable rate limiting (disabled by default in test fixture)
        import src.config as config_mod
        config_mod.settings.rate_limit.enabled = True

        # Drain the bucket by sending 7 rapid requests
        statuses = []
        for _ in range(7):
            resp = await async_client.post("/structure", json={
                "category": "fortification",
                "style": "nordic_wooden",
                "condition": "pristine",
                "scale": "small",
                "description": "A small wooden watchtower with a pointed roof and a lookout platform.",
            })
            statuses.append(resp.status_code)

        return statuses

    @pytest.mark.asyncio
    async def test_rate_limit_429_when_exceeded(self, async_client, monkeypatch):
        """Rapid POST requests beyond the burst limit return 429."""
        import src.config as config_mod

        orig_enabled = config_mod.settings.rate_limit.enabled
        try:
            statuses = await self._drain_post_bucket(async_client)

            assert 429 in statuses, (
                f"Expected at least one 429 after exhausting burst (burst_size=5), "
                f"got statuses: {statuses}"
            )

        finally:
            config_mod.settings.rate_limit.enabled = orig_enabled

    @pytest.mark.asyncio
    async def test_rate_limit_disabled_bypasses_check(self, async_client, monkeypatch):
        """When rate_limit.enabled=False, no 429 is returned even with rapid requests."""
        import src.config as config_mod

        orig_enabled = config_mod.settings.rate_limit.enabled
        try:
            config_mod.settings.rate_limit.enabled = False

            # Send several rapid requests — all should succeed
            statuses = []
            for _ in range(7):
                resp = await async_client.post("/structure", json={
                    "category": "fortification",
                    "style": "nordic_wooden",
                    "condition": "pristine",
                    "scale": "small",
                    "description": "A small wooden watchtower with a pointed roof and a lookout platform.",
                })
                statuses.append(resp.status_code)

            # All should succeed (200) since rate limiting is disabled
            assert all(s == 200 for s in statuses), (
                f"Expected all 200 with rate limiting disabled, got: {statuses}"
            )

        finally:
            config_mod.settings.rate_limit.enabled = orig_enabled

    @pytest.mark.asyncio
    async def test_get_requests_use_separate_bucket(self, async_client, monkeypatch):
        """GET requests use a different (higher) rate limit bucket than POST.

        Even after exhausting the POST bucket, GET requests should still
        succeed because they use a separate bucket with higher limits
        (default get_rps=50.0, burst=50).
        """
        import src.config as config_mod

        orig_enabled = config_mod.settings.rate_limit.enabled
        try:
            # First exhaust the POST bucket to prove POSTs are rate-limited
            config_mod.settings.rate_limit.enabled = True
            post_statuses = await self._drain_post_bucket(async_client)
            assert 429 in post_statuses, "POST bucket should be exhausted"

            # Now send many GET requests — they should all succeed
            # because GET uses a separate, higher-capacity bucket
            get_statuses = []
            for _ in range(10):
                resp = await async_client.get("/health")
                get_statuses.append(resp.status_code)

            assert all(s == 200 for s in get_statuses), (
                f"GET requests should not be rate-limited even when POST bucket is "
                f"exhausted, got: {get_statuses}"
            )

        finally:
            config_mod.settings.rate_limit.enabled = orig_enabled


# ===========================================================================
#  API key authentication middleware
# ===========================================================================


class TestAPIKeyAuth:
    """Tests for API key authentication middleware."""

    @pytest.mark.asyncio
    async def test_health_endpoint_exempt_from_auth(self, async_client, monkeypatch):
        """GET /health works without API key even when auth is enabled."""
        import src.config as config_mod

        orig_key = config_mod.settings.server.api_key
        try:
            config_mod.settings.server.api_key = "test-secret-key"
            resp = await async_client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] in ("ok", "degraded")
        finally:
            config_mod.settings.server.api_key = orig_key

    @pytest.mark.asyncio
    async def test_assets_endpoint_exempt_from_auth(self, async_client, monkeypatch):
        """GET /assets/{filename} works without API key even when auth is enabled."""
        import src.config as config_mod

        orig_key = config_mod.settings.server.api_key
        try:
            config_mod.settings.server.api_key = "test-secret-key"
            # /assets/ even for nonexistent files should return 404, not 401
            resp = await async_client.get("/assets/nonexistent.png")
            assert resp.status_code == 404  # not 401
        finally:
            config_mod.settings.server.api_key = orig_key

    @pytest.mark.asyncio
    async def test_401_when_api_key_required_but_missing(self, async_client, monkeypatch):
        """When api_key is set, requests without X-API-Key return 401."""
        import src.config as config_mod

        orig_key = config_mod.settings.server.api_key
        try:
            config_mod.settings.server.api_key = "test-secret-key"
            resp = await async_client.get("/modes")
            assert resp.status_code == 401
            assert "Invalid or missing API key" in resp.json()["detail"]
        finally:
            config_mod.settings.server.api_key = orig_key

    @pytest.mark.asyncio
    async def test_401_when_api_key_wrong(self, async_client, monkeypatch):
        """Wrong API key returns 401."""
        import src.config as config_mod

        orig_key = config_mod.settings.server.api_key
        try:
            config_mod.settings.server.api_key = "test-secret-key"
            resp = await async_client.get(
                "/modes",
                headers={"X-API-Key": "wrong-key"},
            )
            assert resp.status_code == 401
            assert "Invalid or missing API key" in resp.json()["detail"]
        finally:
            config_mod.settings.server.api_key = orig_key

    @pytest.mark.asyncio
    async def test_200_when_api_key_correct(self, async_client, monkeypatch):
        """Correct API key allows request through."""
        import src.config as config_mod

        orig_key = config_mod.settings.server.api_key
        try:
            config_mod.settings.server.api_key = "test-secret-key"
            resp = await async_client.get(
                "/modes",
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200
            assert "modes" in resp.json()
        finally:
            config_mod.settings.server.api_key = orig_key

    @pytest.mark.asyncio
    async def test_auth_disabled_when_api_key_empty(self, async_client, monkeypatch):
        """When api_key is empty string, all requests pass without auth."""
        import src.config as config_mod

        orig_key = config_mod.settings.server.api_key
        try:
            config_mod.settings.server.api_key = ""
            resp = await async_client.get("/modes")
            assert resp.status_code == 200
            assert "modes" in resp.json()
        finally:
            config_mod.settings.server.api_key = orig_key


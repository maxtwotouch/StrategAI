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
        assert "registered" in data
        assert "leaders" in data["registered"]
        assert "units" in data["registered"]
        assert "structures" in data["registered"]

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
        assert data["generation_mode"] == "placeholder"

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
        assert data["generation_mode"] == "placeholder"
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
        assert data["generation_mode"] in ("comfyui", "static", "placeholder")
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
        """DELETE /background_tile/{filename} removes record."""
        gen_resp = await async_client.post("/background_tile", json={
            "tile_type": "grass",
        })
        assert gen_resp.status_code == 200, f"POST failed: {gen_resp.text}"
        data = gen_resp.json()
        url = data["url"]
        assert url.startswith("/assets/"), f"Unexpected URL: {url}"
        filename = url.split("/")[-1]

        resp = await async_client.delete(f"/background_tile/{filename}")
        assert resp.status_code == 200, f"DELETE failed for {filename}: {resp.text}"
        assert resp.json()["status"] == "deleted"

        # Verify gone — second delete should 404
        resp2 = await async_client.delete(f"/background_tile/{filename}")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_background_tile_not_found(self, async_client):
        """DELETE nonexistent background tile → 404."""
        resp = await async_client.delete("/background_tile/nonexistent_file.png")
        assert resp.status_code == 404


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


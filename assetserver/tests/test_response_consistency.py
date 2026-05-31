"""Response consistency tests across generation modes.

Verifies that responses from different generation modes (comfyui, static,
placeholder) have consistent field shapes — no missing fields, consistent
types, and predictable optional-field behavior.
"""

import pytest
from httpx import ASGITransport, AsyncClient


# ===========================================================================
#  Common response fields
# ===========================================================================

# Fields that every asset response MUST include
_COMMON_FIELDS = {"url", "asset_type", "seed", "generation_mode", "status"}

# Fields that every non-background tile response SHOULD include (may be None)
_OPTIONAL_FIELDS = {"prompt_used", "resolution", "generation_time_ms"}


class TestCommonResponseShape:
    """All asset families share a common response skeleton."""

    @pytest.mark.asyncio
    async def test_structure_response_fields(self, async_client):
        resp = await async_client.post("/structure", json={
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a flag on top.",
        })
        assert resp.status_code == 200
        data = resp.json()

        # Required common fields
        for field in _COMMON_FIELDS:
            assert field in data, f"'{field}' missing from structure response"

        # Idiosyncratic fields
        assert "asset_id" in data
        assert "category" in data
        assert "style" in data

    @pytest.mark.asyncio
    async def test_object_response_fields(self, async_client):
        resp = await async_client.post("/object", json={
            "category": "vegetation",
            "biome": "temperate_forest",
            "season": "summer",
            "description": "A large oak tree with a thick trunk and sprawling branches full of green leaves.",
        })
        assert resp.status_code == 200
        data = resp.json()

        for field in _COMMON_FIELDS:
            assert field in data, f"'{field}' missing from object response"

    @pytest.mark.asyncio
    async def test_unit_response_fields(self, async_client):
        resp = await async_client.post("/unit", json={
            "unit_type": "archer",
            "description": "A skilled medieval archer with a longbow and green hooded cloak, wearing leather armor.",
        })
        assert resp.status_code == 200
        data = resp.json()

        for field in _COMMON_FIELDS:
            assert field in data, f"'{field}' missing from unit response"

        assert "unit_id" in data
        assert "unit_type" in data

    @pytest.mark.asyncio
    async def test_leader_response_fields(self, async_client):
        resp = await async_client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": "Response Test Leader",
            "leader_description": "A regal monarch with a commanding presence, wearing an ornate golden crown and deep crimson robes, standing before a great audience hall.",
            "archetype": "warrior_king",
            "culture": "medieval_european",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        })
        assert resp.status_code == 200
        data = resp.json()

        for field in _COMMON_FIELDS:
            assert field in data, f"'{field}' missing from leader response"

        assert "leader_id" in data
        assert "leader_name" in data
        assert "leader_ids" in data
        assert "leader_names" in data

    @pytest.mark.asyncio
    async def test_background_tile_response_fields(self, async_client):
        resp = await async_client.post("/background_tile", json={"tile_type": "grass"})
        assert resp.status_code == 200
        data = resp.json()

        for field in _COMMON_FIELDS:
            assert field in data, f"'{field}' missing from background_tile response"

        assert "tile_type" in data


class TestResponseFieldTypes:
    """Field types are consistent across families."""

    @pytest.mark.asyncio
    async def test_seed_is_positive_int(self, async_client):
        """All responses must have seed as a positive integer."""
        endpoints = [
            ("/structure", {"category": "fortification", "style": "nordic_wooden",
             "condition": "pristine", "scale": "small",
             "description": "A small wooden watchtower with a pointed roof and a flag on top."}),
            ("/unit", {"unit_type": "archer",
             "description": "A skilled medieval archer with a longbow and green hooded cloak, wearing leather armor."}),
            ("/background_tile", {"tile_type": "grass"}),
        ]

        for endpoint, payload in endpoints:
            resp = await async_client.post(endpoint, json=payload)
            assert resp.status_code == 200, f"{endpoint} failed: {resp.text}"
            data = resp.json()
            assert isinstance(data["seed"], int), \
                f"{endpoint}: seed is {type(data['seed']).__name__}, expected int"
            assert data["seed"] > 0, \
                f"{endpoint}: seed is {data['seed']}, expected > 0"

    @pytest.mark.asyncio
    async def test_url_starts_with_assets(self, async_client):
        """All asset URLs must start with /assets/."""
        endpoints = [
            ("/structure", {"category": "fortification", "style": "nordic_wooden",
             "condition": "pristine", "scale": "small",
             "description": "A small wooden watchtower with a pointed roof and a flag on top."}),
            ("/unit", {"unit_type": "archer",
             "description": "A skilled medieval archer with a longbow and green hooded cloak, wearing leather armor."}),
            ("/background_tile", {"tile_type": "grass"}),
        ]

        for endpoint, payload in endpoints:
            resp = await async_client.post(endpoint, json=payload)
            assert resp.status_code == 200, f"{endpoint} failed: {resp.text}"
            url = resp.json()["url"]
            assert url.startswith("/assets/"), \
                f"{endpoint}: url={url}, expected /assets/ prefix"

    @pytest.mark.asyncio
    async def test_generation_mode_is_valid(self, async_client):
        """generation_mode must be one of: comfyui, static."""
        valid = {"comfyui", "static"}
        resp = await async_client.post("/structure", json={
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a flag on top.",
        })
        assert resp.status_code == 200
        mode = resp.json()["generation_mode"]
        assert mode in valid, f"Invalid generation_mode: {mode}"


class TestListEndpointConsistency:
    """GET list endpoints return arrays with consistent item shapes."""

    @pytest.mark.asyncio
    async def test_list_endpoints_return_arrays(self, async_client):
        """All list endpoints return JSON arrays."""
        list_endpoints = [
            "/structure",
            "/object",
            "/terrain",
            "/unit",
            "/leader",
            "/background_tile",
        ]
        for endpoint in list_endpoints:
            resp = await async_client.get(endpoint)
            assert resp.status_code == 200, f"{endpoint} failed: {resp.text}"
            data = resp.json()
            assert isinstance(data, list), \
                f"{endpoint}: expected list, got {type(data).__name__}"


class TestDeleteResponseConsistency:
    """DELETE responses have a consistent shape."""

    @pytest.mark.asyncio
    async def test_delete_returns_status_deleted(self, async_client):
        """Successful DELETE returns {'status': 'deleted'}."""
        gen = await async_client.post("/structure", json={
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a flag on top.",
        })
        asset_id = gen.json()["asset_id"]

        resp = await async_client.delete(f"/structure/{asset_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, async_client):
        """DELETE on nonexistent resource returns 404 with detail."""
        for endpoint in ["/structure/nonexistent_xyz", "/leader/nonexistent_leader_xyz",
                         "/unit/nonexistent_unit_xyz"]:
            resp = await async_client.delete(endpoint)
            assert resp.status_code == 404, f"{endpoint}: expected 404, got {resp.status_code}"
            data = resp.json()
            assert "detail" in data, f"{endpoint}: missing 'detail' in error response"

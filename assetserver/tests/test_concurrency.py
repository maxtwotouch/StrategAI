"""Concurrency tests — multiple simultaneous requests.

Verifies that the API handles concurrent generation requests without
race conditions, data corruption, or duplicate asset IDs.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient


# ===========================================================================
#  Concurrent POST requests
# ===========================================================================


class TestConcurrentGeneration:
    """Test multiple simultaneous generation requests."""

    @pytest.mark.asyncio
    async def test_concurrent_structures(self, async_client):
        """Generate 5 structures simultaneously — all should succeed."""
        payloads = [
            {
                "category": cat,
                "style": style,
                "condition": "pristine",
                "scale": "small",
                "description": f"A {cat} structure in {style} style with distinct architectural features and a prominent silhouette.",
            }
            for cat, style in [
                ("fortification", "nordic_wooden"),
                ("production", "gothic"),
                ("housing", "mediterranean"),
                ("sacred", "norman_romanesque"),
                ("fortification", "anglo_saxon_stone"),
            ]
        ]

        async def post_one(payload):
            return await async_client.post("/structure", json=payload)

        results = await asyncio.gather(*[post_one(p) for p in payloads])

        asset_ids = []
        for i, resp in enumerate(results):
            assert resp.status_code == 200, f"Request {i} failed: {resp.text}"
            data = resp.json()
            assert data["asset_type"] == "structure"
            assert data["asset_id"].startswith("struct_")
            assert isinstance(data["seed"], int) and data["seed"] > 0
            asset_ids.append(data["asset_id"])

        # All asset IDs must be unique
        assert len(set(asset_ids)) == len(asset_ids), \
            f"Duplicate asset IDs detected: {asset_ids}"

    @pytest.mark.asyncio
    async def test_concurrent_mixed_families(self, async_client):
        """Generate different asset families concurrently."""
        posts = [
            async_client.post("/structure", json={
                "category": "fortification",
                "style": "nordic_wooden",
                "condition": "pristine",
                "scale": "small",
                "description": "A small wooden watchtower with a pointed roof and a flag on top.",
            }),
            async_client.post("/object", json={
                "category": "vegetation",
                "biome": "temperate_forest",
                "season": "autumn",
                "description": "A tall oak tree with orange and red autumn leaves and a thick brown trunk.",
            }),
            async_client.post("/terrain", json={
                "category": "hill",
                "scale": "low",
                "material": "earthen",
                "description": "A gentle grassy hill with soft slopes and a rounded top.",
            }),
            async_client.post("/unit", json={
                "unit_type": "archer",
                "description": "A skilled medieval archer with a longbow and green hooded cloak, wearing leather armor.",
            }),
            async_client.post("/background_tile", json={"tile_type": "grass"}),
        ]

        results = await asyncio.gather(*posts)

        for i, resp in enumerate(results):
            assert resp.status_code == 200, f"Request {i} failed: {resp.text}"

    @pytest.mark.asyncio
    async def test_concurrent_same_leader_splash(self, async_client):
        """Simultaneous splash requests for the same leader name — unique IDs."""
        payload = {
            "asset_type": "splash",
            "leader_name": "Concurrent King",
            "leader_description": "A noble king wearing a golden crown and royal robes, standing in a grand throne room with marble pillars.",
            "archetype": "warrior_king",
            "culture": "medieval_european",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        }

        async def post_one():
            return await async_client.post("/leader", json=payload)

        results = await asyncio.gather(*[post_one() for _ in range(3)])

        leader_ids = []
        for i, resp in enumerate(results):
            assert resp.status_code == 200, f"Request {i} failed: {resp.text}"
            data = resp.json()
            leader_ids.append(data["leader_id"])

        # IDs should be unique (different UUID portion)
        assert len(set(leader_ids)) == len(leader_ids), \
            f"Duplicate leader IDs from concurrent requests: {leader_ids}"

    @pytest.mark.asyncio
    async def test_concurrent_reads_during_write(self, async_client):
        """GET requests during a POST should not interfere."""
        # Start a POST
        post_task = asyncio.create_task(
            async_client.post("/structure", json={
                "category": "fortification",
                "style": "nordic_wooden",
                "condition": "pristine",
                "scale": "small",
                "description": "A small wooden watchtower with a pointed roof and a flag on top.",
            })
        )

        # Run reads concurrently
        reads = await asyncio.gather(
            async_client.get("/health"),
            async_client.get("/modes"),
            async_client.get("/structure"),
            async_client.get("/catalog"),
        )

        for resp in reads:
            assert resp.status_code == 200, f"Read failed: {resp.text}"

        # POST should also succeed
        post_resp = await post_task
        assert post_resp.status_code == 200


# ===========================================================================
#  DELETE + regenerate race
# ===========================================================================


class TestDeleteAndRegenerate:
    """Race conditions between DELETE and POST."""

    @pytest.mark.asyncio
    async def test_delete_then_immediate_regenerate(self, async_client):
        """Delete a structure and immediately regenerate the same category."""
        # Generate
        gen = await async_client.post("/structure", json={
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a flag on top.",
        })
        asset_id = gen.json()["asset_id"]

        # Delete
        await async_client.delete(f"/structure/{asset_id}")

        # Regenerate (same category)
        regen = await async_client.post("/structure", json={
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a flag on top.",
        })
        assert regen.status_code == 200
        # New asset should have different ID
        new_id = regen.json()["asset_id"]
        assert new_id != asset_id

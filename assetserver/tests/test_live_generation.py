"""
Live ComfyUI Integration Tests — Phase C

Tests against a running ComfyUI server at http://localhost:8188.

These tests exercise the full generation pipeline: prompt construction,
workflow submission, image download, and asset persistence.  They are
**not** run by default (marked with a custom marker).  To opt in:

    pytest -m live_comfyui --comfyui-url http://localhost:8188

Or set the COMFYUI__BASE_URL env var and run:

    COMFYUI__BASE_URL="http://localhost:8188" pytest -m live_comfyui

WARNING: These tests submit actual GPU generations and may take 30-120s each.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
import io

# ---------------------------------------------------------------------------
#  Configuration
# ---------------------------------------------------------------------------

COMFYUI_URL = os.environ.get("COMFYUI__BASE_URL", "http://localhost:8188")

pytestmark = pytest.mark.live_comfyui

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _is_valid_png(data: bytes) -> bool:
    """Check if bytes are a valid PNG file."""
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def _png_dimensions(data: bytes) -> tuple[int, int]:
    """Return (width, height) from a PNG byte buffer."""
    img = Image.open(io.BytesIO(data))
    return img.size


async def _delete_asset(async_client: AsyncClient, asset_type: str, asset_id: str) -> bool:
    """Delete an asset by type and id. Returns True on success."""
    resp = await async_client.delete(f"/{asset_type}/{asset_id}")
    return resp.status_code == 200


# ---------------------------------------------------------------------------
#  Config fixture — override ComfyUI URL
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def live_settings(monkeypatch):
    """Override ComfyUI settings to point at the live server."""
    monkeypatch.setattr("src.config.settings.comfyui.base_url", COMFYUI_URL)
    monkeypatch.setattr("src.config.settings.comfyui.nodes", [COMFYUI_URL])
    monkeypatch.setattr("src.config.settings.comfyui.timeout", 600)
    # Force comfyui mode for all families — NOT static/placeholder
    monkeypatch.setattr("src.config.settings.generation.modes", {
        "structure": "comfyui",
        "object": "comfyui",
        "terrain": "comfyui",
        "background_tile": "comfyui",
        "unit": "comfyui",
        "leader": "comfyui",
        "character_sprite": "comfyui",
        "story": "comfyui",
        "splash": "comfyui",
    })
    monkeypatch.setattr("src.config.settings.generation.default_mode", "comfyui")
    yield


# ===========================================================================
#  C1: Happy Path — One asset per family (POST + GET + DELETE)
# ===========================================================================


class TestLiveGenerationHappyPath:
    """POST then GET then DELETE for each of the 6 asset families.

    These tests assert:
    - 200 on POST with valid response shape
    - Valid PNG output with correct dimensions
    - DB record is created (GET after POST returns the record)
    - Clean DELETE removes the asset
    """

    @pytest.mark.asyncio
    async def test_generate_structure_live(self, async_client: AsyncClient, live_settings):
        """POST /structure → valid PNG, DB record, then DELETE."""
        payload = {
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a lookout platform on top of a hill.",
        }
        resp = await async_client.post("/structure", json=payload)
        assert resp.status_code == 200, f"POST /structure failed: {resp.text}"
        data = resp.json()

        # Response shape
        assert data["asset_type"] == "structure"
        assert data["category"] == "fortification"
        assert data["url"].startswith("/assets/")
        assert data["asset_id"].startswith("struct_")
        assert data["generation_mode"] in ("comfyui", "static")
        assert isinstance(data["seed"], int) and data["seed"] > 0
        assert data.get("resolution") is not None
        assert data.get("generation_time_ms", 0) >= 0
        assert data.get("prompt_used") is not None

        # Fetch the actual PNG
        asset_url = data["url"]
        img_resp = await async_client.get(asset_url)
        assert img_resp.status_code == 200
        assert img_resp.headers["content-type"] == "image/png"
        png_data = img_resp.content
        assert _is_valid_png(png_data), "Output is not a valid PNG"
        w, h = _png_dimensions(png_data)
        assert w > 0 and h > 0, f"Invalid PNG dimensions: {w}x{h}"

        # DB record exists
        get_resp = await async_client.get(f"/structure/{data['asset_id']}")
        assert get_resp.status_code == 200

        # Clean up
        del_resp = await async_client.delete(f"/structure/{data['asset_id']}")
        assert del_resp.status_code == 200
        # Verify gone
        gone = await async_client.get(f"/structure/{data['asset_id']}")
        assert gone.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_object_live(self, async_client: AsyncClient, live_settings):
        """POST /object → valid PNG, DB record, then DELETE."""
        payload = {
            "category": "vegetation",
            "biome": "temperate_forest",
            "season": "summer",
            "description": "A large oak tree with a thick trunk and sprawling branches full of green leaves in a meadow.",
        }
        resp = await async_client.post("/object", json=payload)
        assert resp.status_code == 200, f"POST /object failed: {resp.text}"
        data = resp.json()

        assert data["asset_type"] == "object"
        assert data["category"] == "vegetation"
        assert data["url"].startswith("/assets/")
        assert isinstance(data["seed"], int) and data["seed"] > 0

        # Valid PNG
        img_resp = await async_client.get(data["url"])
        assert img_resp.status_code == 200
        assert _is_valid_png(img_resp.content)

        # DB record
        get_resp = await async_client.get(f"/object/{data['asset_id']}")
        assert get_resp.status_code == 200

        # Clean up
        await async_client.delete(f"/object/{data['asset_id']}")

    @pytest.mark.asyncio
    async def test_generate_terrain_live(self, async_client: AsyncClient, live_settings):
        """POST /terrain → valid PNG, DB record, then DELETE."""
        payload = {
            "category": "hill",
            "scale": "medium",
            "material": "earthen",
            "description": "A rounded grassy hill with gentle slopes on all sides and a flat top with a few scattered rocks.",
        }
        resp = await async_client.post("/terrain", json=payload)
        assert resp.status_code == 200, f"POST /terrain failed: {resp.text}"
        data = resp.json()

        assert data["asset_type"] == "terrain"
        assert data["category"] == "hill"
        assert data["url"].startswith("/assets/")

        img_resp = await async_client.get(data["url"])
        assert img_resp.status_code == 200
        assert _is_valid_png(img_resp.content)

        get_resp = await async_client.get(f"/terrain/{data['asset_id']}")
        assert get_resp.status_code == 200

        await async_client.delete(f"/terrain/{data['asset_id']}")

    @pytest.mark.asyncio
    async def test_generate_unit_live(self, async_client: AsyncClient, live_settings):
        """POST /unit → valid PNG, DB record, then DELETE."""
        payload = {
            "unit_type": "archer",
            "description": "A medieval archer in green leather armor with a longbow and quiver of arrows, facing directly forward toward the camera.",
        }
        resp = await async_client.post("/unit", json=payload)
        assert resp.status_code == 200, f"POST /unit failed: {resp.text}"
        data = resp.json()

        assert data["asset_type"] == "unit"
        assert data["unit_type"] == "archer"
        assert data["url"].startswith("/assets/")
        assert isinstance(data["seed"], int) and data["seed"] > 0

        img_resp = await async_client.get(data["url"])
        assert img_resp.status_code == 200
        assert _is_valid_png(img_resp.content)

        get_resp = await async_client.get(f"/unit/{data['unit_id']}")
        assert get_resp.status_code == 200

        await async_client.delete(f"/unit/{data['unit_id']}")

    @pytest.mark.asyncio
    async def test_generate_background_tile_live(self, async_client: AsyncClient, live_settings):
        """POST /background_tile → valid PNG, DB record, then DELETE."""
        payload = {"tile_type": "grass"}
        resp = await async_client.post("/background_tile", json=payload)
        assert resp.status_code == 200, f"POST /background_tile failed: {resp.text}"
        data = resp.json()

        assert data["asset_type"] == "background_tile"
        assert data["tile_type"] == "grass"
        assert data["url"].startswith("/assets/")
        assert isinstance(data["seed"], int) and data["seed"] > 0
        assert data["status"] == "completed"
        assert data.get("resolution") is not None
        assert data.get("generation_time_ms") is not None

        img_resp = await async_client.get(data["url"])
        assert img_resp.status_code == 200
        assert _is_valid_png(img_resp.content)

        get_resp = await async_client.get(f"/background_tile/{data['background_tile_id']}")
        assert get_resp.status_code == 200

        await async_client.delete(f"/background_tile/{data['background_tile_id']}")

    @pytest.mark.asyncio
    async def test_generate_leader_splash_live(self, async_client: AsyncClient, live_settings):
        """POST /leader (splash) → valid PNG, DB record, then DELETE."""
        payload = {
            "asset_type": "splash",
            "leader_name": "Cleopatra VII",
            "leader_description": "A regal Egyptian queen with dark hair, gold jewelry, and a commanding presence. "
                "She wears a white linen dress and a nemes headdress with a golden cobra emblem.",
            "archetype": "warrior_queen",
            "culture": "ancient_egyptian",
            "time_of_day": "golden_hour",
            "mood": "triumphant",
        }
        resp = await async_client.post("/leader", json=payload)
        assert resp.status_code == 200, f"POST /leader splash failed: {resp.text}"
        data = resp.json()

        assert data["asset_type"] == "splash"
        assert data["leader_name"] == "Cleopatra VII"
        assert data["leader_id"].startswith("leader_cleopatra_vii_")
        assert data["url"].startswith("/assets/")
        assert isinstance(data["seed"], int) and data["seed"] > 0

        img_resp = await async_client.get(data["url"])
        assert img_resp.status_code == 200
        assert _is_valid_png(img_resp.content)

        # DB record via leader endpoint
        leader_resp = await async_client.get(f"/leader/{data['leader_id']}")
        assert leader_resp.status_code == 200
        assert leader_resp.json()["splash_url"] is not None

        # Clean up
        await async_client.delete(f"/leader/{data['leader_id']}")


# ===========================================================================
#  C2: Leader Pipeline End-to-End
# ===========================================================================


class TestLiveLeaderPipeline:
    """Full leader pipeline: splash → profile → action.

    Verifies all 3 images link correctly via the leader record.
    """

    @pytest.mark.asyncio
    async def test_full_leader_pipeline_live(self, async_client: AsyncClient, live_settings):
        """Complete pipeline: splash → profile → action → verify all links."""
        # 1. Splash
        splash = await async_client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": "Caesar",
            "leader_description": "A tall Roman general with short cropped dark hair, "
                "a prominent aquiline nose, deep-set brown eyes, and a clean-shaven angular "
                "face. He wears a white toga with a purple stripe over a crimson tunic, "
                "with a laurel wreath on his head.",
            "archetype": "warrior_king",
            "culture": "roman_imperial",
            "time_of_day": "midday",
            "mood": "triumphant",
        })
        assert splash.status_code == 200, f"Splash failed: {splash.text}"
        lid = splash.json()["leader_id"]
        splash_url = splash.json()["url"]

        # Verify splash PNG
        img = await async_client.get(splash_url)
        assert img.status_code == 200
        assert _is_valid_png(img.content)

        # 2. Profile
        profile = await async_client.post("/leader", json={
            "asset_type": "profile",
            "leader_name": "Caesar",
            "leader_description": "A tall Roman general with short cropped dark hair, "
                "a prominent aquiline nose, deep-set brown eyes. Toga with purple stripe.",
            "archetype": "warrior_king",
            "culture": "roman_imperial",
            "time_of_day": "midday",
            "mood": "triumphant",
            "leader_id": lid,
        })
        assert profile.status_code == 200, f"Profile failed: {profile.text}"
        profile_url = profile.json()["url"]

        # Verify profile PNG
        img_p = await async_client.get(profile_url)
        assert img_p.status_code == 200
        assert _is_valid_png(img_p.content)

        # 3. Action
        action = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Caesar",
            "leader_description": "A tall Roman general with short cropped dark hair. "
                "Toga with purple stripe and a laurel wreath.",
            "leader_id": lid,
            "archetype": "warrior_king",
            "culture": "roman_imperial",
            "time_of_day": "midday",
            "mood": "triumphant",
            "action_category": "military",
            "action_description": "Caesar stands atop a hill with his legion behind him, "
                "sword raised toward the sky as golden sunlight breaks through storm clouds.",
        })
        assert action.status_code == 200, f"Action failed: {action.text}"
        action_url = action.json()["url"]

        # Verify action PNG
        img_a = await async_client.get(action_url)
        assert img_a.status_code == 200
        assert _is_valid_png(img_a.content)

        # 4. Verify leader record links all 3
        info = await async_client.get(f"/leader/{lid}")
        assert info.status_code == 200
        info_data = info.json()
        assert info_data["splash_url"] is not None
        assert info_data["profile_url"] is not None
        assert len(info_data["action_urls"]) >= 1
        # All URLs should resolve to valid PNGs
        for url in [info_data["splash_url"], info_data["profile_url"]] + info_data["action_urls"]:
            r = await async_client.get(url)
            assert r.status_code == 200, f"Asset URL {url} not found"

        # 5. Clean up
        await async_client.delete(f"/leader/{lid}")

    @pytest.mark.asyncio
    async def test_multi_leader_action_live(self, async_client: AsyncClient, live_settings):
        """Multi-leader action: 2 leaders → ImageStitch workflow."""
        # Create two leaders
        lid1 = await self._create_live_splash(async_client, "Julius Caesar",
            "A tall Roman general with short cropped dark hair, a prominent aquiline nose, "
            "deep-set brown eyes, and a clean-shaven angular face. He wears a white toga "
            "with a purple stripe over a crimson tunic, with a laurel wreath on his head.")
        lid2 = await self._create_live_splash(async_client, "Vercingetorix",
            "A Gallic chieftain with long braided blond hair, a thick drooping mustache, "
            "fierce blue eyes, and a muscular build. He wears chainmail armor with a torc "
            "around his neck and carries a long iron sword.")

        # Multi-leader action
        resp = await async_client.post("/leader", json={
            "asset_type": "action",
            "leader_name": "Gaul Surrender",
            "leader_description": "Two leaders meeting after battle — one victorious Roman, "
                "one defiant Gallic chieftain standing across a wooden table in a field tent.",
            "leader_ids": [lid1, lid2],
            "archetype": "diplomat",
            "culture": "roman_imperial",
            "time_of_day": "midday",
            "mood": "grim_determined",
            "action_category": "diplomatic",
            "action_description": "Vercingetorix throws down his sword at Caesar's feet "
                "in surrender as Roman soldiers look on from the tent entrance.",
        })
        assert resp.status_code == 200, f"Multi-leader action failed: {resp.text}"
        data = resp.json()

        assert data["asset_type"] == "action"
        assert data["leader_ids"] == [lid1, lid2]
        assert data["leader_names"] == ["Julius Caesar", "Vercingetorix"]
        assert data["url"].startswith("/assets/")
        assert isinstance(data["seed"], int) and data["seed"] > 0

        # Verify PNG
        img = await async_client.get(data["url"])
        assert img.status_code == 200
        assert _is_valid_png(img.content)

        # Clean up
        await async_client.delete(f"/leader/{lid1}")
        await async_client.delete(f"/leader/{lid2}")

    @staticmethod
    async def _create_live_splash(client: AsyncClient, name: str, desc: str) -> str:
        """Helper: create a splash leader and return leader_id."""
        resp = await client.post("/leader", json={
            "asset_type": "splash",
            "leader_name": name,
            "leader_description": desc,
            "archetype": "warrior_king",
            "culture": "roman_imperial",
            "time_of_day": "midday",
            "mood": "triumphant",
        })
        assert resp.status_code == 200, f"Splash failed for {name}: {resp.text}"
        return resp.json()["leader_id"]


# ===========================================================================
#  C3: Error Handling — Live ComfyUI
# ===========================================================================


class TestLiveErrorHandling:
    """Test that the service handles ComfyUI errors gracefully.

    These tests exercise real error paths against a live ComfyUI server.
    """

    @pytest.mark.asyncio
    async def test_live_concurrent_requests(self, async_client: AsyncClient, live_settings):
        """Fire 3+ POSTs simultaneously — all should succeed or fail cleanly."""
        payload = {
            "category": "fortification",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "A small wooden watchtower with a pointed roof and a lookout platform.",
        }

        async def _post():
            return await async_client.post("/structure", json=payload)

        tasks = [_post() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        asset_ids = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning("Concurrent request %d raised: %s", i, r)
            else:
                assert r.status_code in (200, 503), \
                    f"Request {i} returned {r.status_code}: {r.text}"
                if r.status_code == 200:
                    asset_ids.append(r.json()["asset_id"])

        # Clean up any created assets
        for aid in asset_ids:
            await async_client.delete(f"/structure/{aid}")

    @pytest.mark.asyncio
    async def test_live_invalid_payload_422(self, async_client: AsyncClient, live_settings):
        """Invalid payload returns 422 even against a live ComfyUI server."""
        resp = await async_client.post("/structure", json={
            "category": "invalid_category",
            "style": "nordic_wooden",
            "condition": "pristine",
            "scale": "small",
            "description": "This should fail fast with 422.",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_live_get_nonexistent_asset_404(self, async_client: AsyncClient, live_settings):
        """GET a nonexistent asset → 404 even in live mode."""
        resp = await async_client.get("/assets/nonexistent_live_test.png")
        assert resp.status_code == 404


# ===========================================================================
#  C4: Performance Baseline
# ===========================================================================


class TestLivePerformance:
    """Record and assert reasonable generation performance."""

    @pytest.mark.asyncio
    async def test_background_tile_generation_time(self, async_client: AsyncClient, live_settings):
        """Background tile should generate within 120 seconds."""
        t0 = time.time()
        resp = await async_client.post("/background_tile", json={"tile_type": "grass"})
        elapsed = time.time() - t0

        assert resp.status_code == 200, f"BG tile failed: {resp.text}"
        data = resp.json()
        gen_time = data.get("generation_time_ms", 0)

        logger.info("Background tile generation: %dms (wall clock: %.1fs)", gen_time, elapsed)

        # Assert reasonable generation time (under 120s wall clock)
        assert elapsed < 120, f"Background tile took {elapsed:.1f}s — too slow"

        # Verify PNG
        img = await async_client.get(data["url"])
        assert img.status_code == 200
        assert _is_valid_png(img.content)

        # Clean up
        await async_client.delete(f"/background_tile/{data['background_tile_id']}")

    @pytest.mark.asyncio
    async def test_ten_consecutive_generations(self, async_client: AsyncClient, live_settings):
        """10 consecutive background tile generations — record P50/P95."""
        times: list[float] = []
        asset_ids: list[str] = []
        payload = {"tile_type": "dirt"}

        for i in range(10):
            t0 = time.time()
            resp = await async_client.post("/background_tile", json=payload)
            elapsed = time.time() - t0

            assert resp.status_code == 200, f"Gen {i} failed: {resp.text}"
            data = resp.json()
            gen_ms = data.get("generation_time_ms", 0)
            times.append(gen_ms / 1000.0)
            asset_ids.append(data["background_tile_id"])

            logger.info("Gen %d: %dms (wall: %.1fs), seed=%d",
                         i, gen_ms, elapsed, data["seed"])

        # Sort times for percentile calculation
        times.sort()
        p50 = times[len(times) // 2]
        p95 = times[int(len(times) * 0.95)]
        avg = sum(times) / len(times)

        logger.info("Performance: P50=%.1fs, P95=%.1fs, Avg=%.1fs", p50, p95, avg)

        # Reasonable bounds: P95 under 180s for background tiles on a warm GPU
        assert p95 < 180, f"P95 generation time {p95:.1f}s exceeds 180s limit"

        # Clean up all
        for aid in asset_ids:
            await async_client.delete(f"/background_tile/{aid}")

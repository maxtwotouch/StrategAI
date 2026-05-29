#!/usr/bin/env python3
"""
API Validation & Bulk Generation Script
========================================

Hits the running FastAPI server (:8000) via HTTP to:

1. **Smoke-test** every endpoint with a valid payload — validates 200 + response shape.
2. **Bulk-generate** N assets per family — stress-tests workflows, tracks timing & failures.
3. **Validate response contracts** — checks field types, URL format, ID naming patterns,
   `generation_mode` validity, etc.
4. **Test multi-step workflows** — leader splash → profile → action → multi-leader action chain.
5. **Probe edge cases** — missing fields, invalid enums, boundary lengths, 404 paths.

Output
------
- Console: live progress with pass/fail counts.
- JSON report: ``reports/validate_{timestamp}.json`` with per-request details.

Usage::

    python scripts/validate_api.py --family all --count 10 --verbose
    python scripts/validate_api.py --smoke-only
    python scripts/validate_api.py --family leader --count 5 --output-dir my_reports/
    python scripts/validate_api.py --base-url http://192.168.1.50:8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_MODES = {"comfyui", "static", "placeholder"}
ASSET_URL_PREFIX = "/assets/"
LEADER_ID_PREFIX = "leader_"
STRUCT_ID_PREFIX = "struct_"
OBJECT_ID_PREFIX = "object_"
TERRAIN_ID_PREFIX = "terrain_"
UNIT_ID_PREFIX = "unit_"

ALL_FAMILIES = ["structure", "object", "terrain", "unit", "leader", "background_tile"]

# How many consecutive failures before we consider the server unhealthy
CONSECUTIVE_FAILURE_THRESHOLD = 5

# Per-request timeout (seconds)
DEFAULT_REQUEST_TIMEOUT = 120.0


# ===========================================================================
# Data classes
# ===========================================================================


@dataclass
class RequestResult:
    """Outcome of a single API request."""

    endpoint: str
    method: str
    status_code: int | None = None
    elapsed_ms: float = 0.0
    response_body: Any = None
    error: str | None = None
    checks_passed: int = 0
    checks_failed: int = 0
    check_details: list[str] = field(default_factory=list)


@dataclass
class RunReport:
    """Aggregate report for the full script run."""

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    base_url: str = ""
    smoke_results: list[dict] = field(default_factory=list)
    bulk_results: list[dict] = field(default_factory=list)
    edge_results: list[dict] = field(default_factory=list)
    workflow_results: list[dict] = field(default_factory=list)
    totals: dict = field(default_factory=lambda: {
        "smoke": {"passed": 0, "failed": 0},
        "bulk": {"passed": 0, "failed": 0},
        "edge": {"passed": 0, "failed": 0},
        "workflow": {"passed": 0, "failed": 0},
    })


# ===========================================================================
# Payload builders
# ===========================================================================


# Each family has a list of valid payloads that rotate for bulk generation.
# When N > len(payloads), we cycle.  Payloads exercise different enum combos.

STRUCTURE_PAYLOADS = [
    {"category": "fortification", "style": "nordic_wooden", "condition": "pristine",
     "scale": "small", "description": "A compact wooden watchtower with a pointed shingled roof, a lookout platform, and a small flagpole on top"},
    {"category": "production", "style": "gothic", "condition": "weathered",
     "scale": "medium", "description": "A weathered stone windmill with a conical roof, four wooden blades, and a small grain storage annex attached to the side"},
    {"category": "housing", "style": "mediterranean", "condition": "pristine",
     "scale": "medium", "description": "A whitewashed cottage with a red terracotta tiled roof, a chimney with smoke, and a small walled garden"},
    {"category": "sacred", "style": "norman_romanesque", "condition": "ruined",
     "scale": "large", "description": "A ruined stone chapel with a collapsed bell tower, broken stained glass windows, and ivy covering the remaining walls"},
    {"category": "fortification", "style": "anglo_saxon_stone", "condition": "fortified",
     "scale": "large", "description": "A massive stone gatehouse with twin towers, a portcullis, battlements with arrow slits, and a heavy oak reinforced door"},
]

OBJECT_PAYLOADS = [
    {"category": "vegetation", "biome": "temperate_forest", "season": "autumn",
     "description": "A tall deciduous oak tree with orange and red autumn leaves, a thick brown trunk, and exposed roots at the base"},
    {"category": "geological", "biome": "mountain", "season": "summer",
     "description": "A large grey boulder with jagged edges and patches of green moss growing on the shaded north face"},
    {"category": "rural_props", "biome": "grassland", "season": "spring",
     "description": "A wooden hay cart with two large spoked wheels, loaded with fresh green hay and a pitchfork leaning against the side"},
    {"category": "urban_props", "biome": "coastal", "season": "summer",
     "description": "A wooden market stall with a striped canvas awning, displaying colourful fruits and vegetables in woven baskets"},
    {"category": "debris", "biome": "desert", "season": "summer",
     "description": "Scattered broken pottery shards and splintered wooden planks around the remains of a collapsed wooden crate"},
]

TERRAIN_PAYLOADS = [
    {"category": "hill", "scale": "low", "material": "earthen",
     "description": "A gentle rounded grassy hill with soft slopes, a few small rocks visible in the soil, suitable for grazing sheep"},
    {"category": "cliff", "scale": "high", "material": "rocky",
     "description": "A sheer vertical rock face with visible strata layers, a few hardy shrubs clinging to crevices, and a sharp drop-off"},
    {"category": "slope", "scale": "medium", "material": "sandy",
     "description": "A gradual sandy slope with rippled wind patterns in the sand and a few scattered pebbles near the top edge"},
    {"category": "ridge", "scale": "medium", "material": "snowy",
     "description": "A narrow snowy ridge line with cornices of wind-blown snow on the leeward side and exposed dark rock beneath"},
    {"category": "depression", "scale": "low", "material": "muddy",
     "description": "A shallow muddy hollow with standing water in the centre, surrounded by churned-up mud and hoof prints"},
]

UNIT_PAYLOADS = [
    {"unit_type": "archer", "description": "A skilled medieval archer with a yew longbow, wearing a green hooded cloak over a quilted leather gambeson, quiver of arrows on the back"},
    {"unit_type": "warrior", "description": "A heavily armoured foot soldier in polished steel plate armour, carrying a large kite shield with a golden lion crest and a one-handed arming sword"},
    {"unit_type": "scout", "description": "A swift-moving medieval scout in light leather armour and a hooded dark green cloak, carrying a short bow and a hunting dagger on the belt"},
    {"unit_type": "settler", "description": "A humble medieval settler woman in a simple wool tunic and linen apron, carrying a wicker basket of harvested wheat under one arm"},
]

LEADER_SPLASH_PAYLOADS = [
    {"asset_type": "splash", "leader_name": "Queen Isabella", "archetype": "warrior_queen", "culture": "medieval_european",
     "time_of_day": "golden_hour", "mood": "triumphant",
     "leader_description": "Queen Isabella stands proudly on the castle ramparts overlooking her kingdom, wearing ceremonial silver plate armour with a royal purple cloak billowing in the wind, her crowned helm held in the crook of her arm"},
    {"asset_type": "splash", "leader_name": "Pharaoh Akhenaten", "archetype": "spiritual_leader", "culture": "ancient_egyptian",
     "time_of_day": "midday", "mood": "wise_serene",
     "leader_description": "Pharaoh Akhenaten sits upon a golden throne in a sun-drenched temple courtyard, wearing the double crown of Upper and Lower Egypt, holding a golden ankh sceptre, with rays of sunlight streaming through towering columns"},
    {"asset_type": "splash", "leader_name": "Lord Harald", "archetype": "warrior_king", "culture": "nordic_viking",
     "time_of_day": "storm", "mood": "grim_determined",
     "leader_description": "Lord Harald stands at the prow of a longship in stormy seas, wearing studded leather armour with a bearskin cloak, a one-handed axe raised high, with lightning illuminating the dark clouds behind him"},
]

LEADER_PROFILE_PAYLOAD = {
    "asset_type": "profile", "leader_name": "placeholder", "archetype": "warrior_king", "culture": "medieval_european",
    "time_of_day": "golden_hour", "mood": "triumphant",
    "leader_description": "A regal ruler with a commanding presence, sharp facial features, and an elaborate jewelled crown resting upon greying hair",
}

LEADER_ACTION_PAYLOADS = [
    {"action_category": "military", "action_description": "Leading a cavalry charge across an open battlefield, sword raised high, warhorse rearing up, banners of the kingdom fluttering in the wind"},
    {"action_category": "diplomatic", "action_description": "Greeting a foreign ambassador in the grand hall, extending a hand of friendship, with scribes recording the historic moment on parchment scrolls"},
    {"action_category": "construction", "action_description": "Surveying the construction of a grand cathedral, holding architectural blueprints, with stonemasons and carpenters working on scaffolding behind"},
]

BACKGROUND_TILE_PAYLOADS = [
    {"tile_type": "grass"},
    {"tile_type": "water"},
    {"tile_type": "sand"},
    {"tile_type": "stone"},
    {"tile_type": "dirt"},
]


# ===========================================================================
# Response schema validators
# ===========================================================================


def _check(ok: bool, msg: str, details: list[str]) -> bool:
    """Record a pass/fail check."""
    if ok:
        details.append(f"  ✓ {msg}")
    else:
        details.append(f"  ✗ {msg}")
    return ok


def validate_tile_response(data: dict, family: str, details: list[str]) -> int:
    """Validate a structure/object/terrain response. Returns pass count."""
    passed = 0

    passed += _check(isinstance(data.get("url"), str) and data["url"].startswith(ASSET_URL_PREFIX),
                     f"url starts with '{ASSET_URL_PREFIX}'", details)
    passed += _check(data.get("asset_type") == family,
                     f"asset_type is '{family}'", details)
    passed += _check(isinstance(data.get("asset_id"), str) and len(data["asset_id"]) > 10,
                     "asset_id present and non-empty", details)
    passed += _check(data.get("asset_id", "").startswith((
                         STRUCT_ID_PREFIX if family == "structure" else
                         OBJECT_ID_PREFIX if family == "object" else TERRAIN_ID_PREFIX)),
                     f"asset_id starts with correct prefix", details)
    passed += _check(isinstance(data.get("seed"), int) and data["seed"] > 0,
                     "seed is positive int", details)
    passed += _check(data.get("generation_mode") in VALID_MODES,
                     f"generation_mode is valid ({VALID_MODES})", details)
    passed += _check(data.get("status") == "completed",
                     "status is 'completed'", details)

    # Optional fields — validate type if present
    if data.get("prompt_used") is not None:
        passed += _check(isinstance(data["prompt_used"], str) and len(data["prompt_used"]) > 0,
                         "prompt_used is non-empty string", details)
    if data.get("resolution") is not None:
        passed += _check(isinstance(data["resolution"], str) and "x" in data["resolution"],
                         "resolution format like WxH", details)
    if data.get("generation_time_ms") is not None:
        passed += _check(isinstance(data["generation_time_ms"], int) and data["generation_time_ms"] >= 0,
                         "generation_time_ms is positive int", details)

    return passed


def validate_unit_response(data: dict, details: list[str]) -> int:
    """Validate a unit response."""
    passed = 0
    passed += _check(isinstance(data.get("url"), str) and data["url"].startswith(ASSET_URL_PREFIX),
                     f"url starts with '{ASSET_URL_PREFIX}'", details)
    passed += _check(data.get("asset_type") == "unit",
                     "asset_type is 'unit'", details)
    passed += _check(isinstance(data.get("unit_id"), str) and data["unit_id"].startswith(UNIT_ID_PREFIX),
                     "unit_id starts with 'unit_'", details)
    passed += _check(isinstance(data.get("seed"), int) and data["seed"] > 0,
                     "seed is positive int", details)
    passed += _check(data.get("generation_mode") in VALID_MODES,
                     f"generation_mode is valid ({VALID_MODES})", details)
    passed += _check(data.get("status") == "completed",
                     "status is 'completed'", details)
    if data.get("prompt_used") is not None:
        passed += _check(isinstance(data["prompt_used"], str) and len(data["prompt_used"]) > 0,
                         "prompt_used is non-empty string", details)
    if data.get("resolution") is not None:
        passed += _check(isinstance(data["resolution"], str) and "x" in data["resolution"],
                         "resolution format like WxH", details)
    if data.get("generation_time_ms") is not None:
        passed += _check(isinstance(data["generation_time_ms"], int) and data["generation_time_ms"] >= 0,
                         "generation_time_ms is positive int", details)
    return passed


def validate_leader_response(data: dict, asset_type: str, details: list[str]) -> int:
    """Validate a leader response (splash, profile, or action)."""
    passed = 0
    passed += _check(isinstance(data.get("url"), str) and data["url"].startswith(ASSET_URL_PREFIX),
                     f"url starts with '{ASSET_URL_PREFIX}'", details)
    passed += _check(data.get("asset_type") == asset_type,
                     f"asset_type is '{asset_type}'", details)
    # leader_id format: for multi-leader actions, leader_id is a scene UUID;
    # for single-leader assets, it starts with "leader_"
    lid = data.get("leader_id", "")
    is_multi = len(data.get("leader_ids") or []) > 0
    if is_multi:
        passed += _check(isinstance(lid, str) and len(lid) > 0,
                         "leader_id present (multi-leader scene ID)", details)
    else:
        passed += _check(isinstance(lid, str) and lid.startswith(LEADER_ID_PREFIX),
                         "leader_id starts with 'leader_'", details)
    passed += _check(isinstance(data.get("leader_name"), str) and len(data["leader_name"]) > 0,
                     "leader_name present and non-empty", details)
    passed += _check(isinstance(data.get("seed"), int) and data["seed"] > 0,
                     "seed is positive int", details)
    passed += _check(data.get("generation_mode") in VALID_MODES,
                     f"generation_mode is valid ({VALID_MODES})", details)
    passed += _check(data.get("status") == "completed",
                     "status is 'completed'", details)
    if data.get("prompt_used") is not None:
        passed += _check(isinstance(data["prompt_used"], str) and len(data["prompt_used"]) > 0,
                         "prompt_used is non-empty string", details)
    if data.get("resolution") is not None:
        passed += _check(isinstance(data["resolution"], str) and "x" in data["resolution"],
                         "resolution format like WxH", details)
    if data.get("generation_time_ms") is not None:
        passed += _check(isinstance(data["generation_time_ms"], int) and data["generation_time_ms"] >= 0,
                         "generation_time_ms is positive int", details)
    if asset_type == "action":
        passed += _check(isinstance(data.get("leader_ids"), list),
                         "leader_ids is a list", details)
        passed += _check(isinstance(data.get("leader_names"), list),
                         "leader_names is a list", details)
    return passed


def validate_background_tile_response(data: dict, details: list[str]) -> int:
    """Validate a background tile response."""
    passed = 0
    passed += _check(isinstance(data.get("url"), str) and data["url"].startswith(ASSET_URL_PREFIX),
                     f"url starts with '{ASSET_URL_PREFIX}'", details)
    passed += _check(data.get("asset_type") == "background_tile",
                     "asset_type is 'background_tile'", details)
    passed += _check(isinstance(data.get("tile_type"), str) and len(data["tile_type"]) > 0,
                     "tile_type present and non-empty", details)
    passed += _check(data.get("generation_mode") in VALID_MODES,
                     f"generation_mode is valid ({VALID_MODES})", details)
    passed += _check(data.get("status") == "completed",
                     "status is 'completed'", details)
    if data.get("seed") is not None:
        passed += _check(isinstance(data["seed"], int) and data["seed"] >= 0,
                         "seed is int (>= 0)", details)
    if data.get("prompt_used") is not None:
        passed += _check(isinstance(data["prompt_used"], str) and len(data["prompt_used"]) > 0,
                         "prompt_used is non-empty string", details)
    if data.get("resolution") is not None:
        passed += _check(isinstance(data["resolution"], str) and "x" in data["resolution"],
                         "resolution format like WxH", details)
    if data.get("generation_time_ms") is not None:
        passed += _check(isinstance(data["generation_time_ms"], int) and data["generation_time_ms"] >= 0,
                         "generation_time_ms is positive int", details)
    return passed


def validate_health_response(data: dict, details: list[str]) -> int:
    """Validate GET /health response."""
    passed = 0
    passed += _check(data.get("status") == "ok", "status is 'ok'", details)
    passed += _check(isinstance(data.get("comfyui_connected"), bool),
                     "comfyui_connected is bool", details)
    passed += _check(isinstance(data.get("comfyui_nodes"), int) and data["comfyui_nodes"] >= 0,
                     "comfyui_nodes is non-negative int", details)
    passed += _check(isinstance(data.get("modes"), dict), "modes is dict", details)
    passed += _check(isinstance(data.get("registered"), dict), "registered is dict", details)
    for family in ALL_FAMILIES:
        passed += _check(family in data.get("modes", {}),
                         f"'{family}' present in modes", details)
    return passed


def validate_modes_response(data: dict, details: list[str]) -> int:
    """Validate GET /modes response."""
    passed = 0
    passed += _check(isinstance(data.get("modes"), dict), "modes is dict", details)
    passed += _check(isinstance(data.get("valid_modes"), list), "valid_modes is list", details)
    for family in ALL_FAMILIES:
        passed += _check(family in data.get("modes", {}),
                         f"'{family}' present", details)
    for mode in VALID_MODES:
        passed += _check(mode in data.get("valid_modes", []),
                         f"'{mode}' in valid_modes", details)
    return passed


def validate_catalog_response(data: dict, details: list[str]) -> int:
    """Validate GET /catalog response."""
    passed = 0
    required = {"background_tile", "structure", "nature_object", "character_sprite", "unit"}
    for key in required:
        passed += _check(key in data, f"'{key}' present in catalog", details)
    return passed


def validate_leader_list_item(item: dict, details: list[str]) -> int:
    """Validate a single item from GET /leader listing."""
    passed = 0
    passed += _check(isinstance(item.get("leader_id"), str) and item["leader_id"].startswith(LEADER_ID_PREFIX),
                     "leader_id present and starts with 'leader_'", details)
    passed += _check(isinstance(item.get("leader_name"), str) and len(item["leader_name"]) > 0,
                     "leader_name present", details)
    passed += _check(isinstance(item.get("archetype"), str), "archetype is str", details)
    passed += _check(isinstance(item.get("culture"), str), "culture is str", details)
    passed += _check(isinstance(item.get("splash_url"), str) and item["splash_url"].startswith(ASSET_URL_PREFIX),
                     "splash_url present", details)
    passed += _check(isinstance(item.get("action_urls"), list), "action_urls is list", details)
    passed += _check(isinstance(item.get("splash_seed"), int), "splash_seed is int", details)
    return passed


def validate_delete_response(data: dict, details: list[str]) -> int:
    """Validate a DELETE response."""
    passed = 0
    passed += _check(data.get("status") == "deleted",
                     "status is 'deleted'", details)
    return passed


def validate_error_response(data: dict, expected_status: int, details: list[str]) -> int:
    """Validate an error response has 'detail' field."""
    passed = 0
    passed += _check("detail" in data,
                     "error response has 'detail' field", details)
    return passed


# ===========================================================================
# HTTP client helpers
# ===========================================================================


async def _post(client: httpx.AsyncClient, url: str, payload: dict,
                timeout: float = DEFAULT_REQUEST_TIMEOUT) -> RequestResult:
    """Send a POST request and return a RequestResult."""
    result = RequestResult(endpoint=url, method="POST")
    t0 = time.time()
    try:
        resp = await client.post(url, json=payload, timeout=timeout)
        result.elapsed_ms = (time.time() - t0) * 1000
        result.status_code = resp.status_code
        try:
            result.response_body = resp.json()
        except json.JSONDecodeError:
            result.response_body = resp.text[:500]
    except httpx.TimeoutException as e:
        result.elapsed_ms = (time.time() - t0) * 1000
        result.error = f"Timeout: {e}"
    except httpx.ConnectError as e:
        result.elapsed_ms = (time.time() - t0) * 1000
        result.error = f"Connection refused: {e}"
    except Exception as e:
        result.elapsed_ms = (time.time() - t0) * 1000
        result.error = f"Exception: {type(e).__name__}: {e}"
    return result


async def _get(client: httpx.AsyncClient, url: str,
               timeout: float = DEFAULT_REQUEST_TIMEOUT) -> RequestResult:
    """Send a GET request."""
    result = RequestResult(endpoint=url, method="GET")
    t0 = time.time()
    try:
        resp = await client.get(url, timeout=timeout)
        result.elapsed_ms = (time.time() - t0) * 1000
        result.status_code = resp.status_code
        try:
            result.response_body = resp.json()
        except json.JSONDecodeError:
            result.response_body = resp.text[:500]
    except Exception as e:
        result.elapsed_ms = (time.time() - t0) * 1000
        result.error = f"Exception: {type(e).__name__}: {e}"
    return result


async def _delete(client: httpx.AsyncClient, url: str,
                  timeout: float = DEFAULT_REQUEST_TIMEOUT) -> RequestResult:
    """Send a DELETE request."""
    result = RequestResult(endpoint=url, method="DELETE")
    t0 = time.time()
    try:
        resp = await client.delete(url, timeout=timeout)
        result.elapsed_ms = (time.time() - t0) * 1000
        result.status_code = resp.status_code
        try:
            result.response_body = resp.json()
        except json.JSONDecodeError:
            result.response_body = resp.text[:500]
    except Exception as e:
        result.elapsed_ms = (time.time() - t0) * 1000
        result.error = f"Exception: {type(e).__name__}: {e}"
    return result


# ===========================================================================
# Smoke tests — one request per endpoint
# ===========================================================================


async def run_smoke_tests(base_url: str, client: httpx.AsyncClient,
                          timeout: float, verbose: bool) -> list[dict]:
    """Run one valid request per endpoint. Returns list of result dicts."""
    results: list[dict] = []
    print("\n" + "=" * 64)
    print("  SMOKE TESTS — one request per endpoint")
    print("=" * 64)

    # ------------------------------------------------------------------
    # 1. Health
    # ------------------------------------------------------------------
    print("\n  ── Meta endpoints ──")
    r = await _get(client, f"{base_url}/health", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /health  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_health_response(r.response_body, details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        if verbose:
            for d in details:
                print(f"      {d}")
    results.append(_result_dict(r, "smoke"))

    # 2. Modes
    r = await _get(client, f"{base_url}/modes", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /modes   [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_modes_response(r.response_body, details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
    results.append(_result_dict(r, "smoke"))

    # 3. Catalog
    r = await _get(client, f"{base_url}/catalog", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /catalog [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_catalog_response(r.response_body, details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
    results.append(_result_dict(r, "smoke"))

    # ------------------------------------------------------------------
    # 2. Structure endpoints
    # ------------------------------------------------------------------
    print("\n  ── Structure endpoints ──")
    payload = STRUCTURE_PAYLOADS[0]
    r = await _post(client, f"{base_url}/structure", payload, timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} POST /structure  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    structure_id = None
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_tile_response(r.response_body, "structure", details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        structure_id = r.response_body.get("asset_id")
        if verbose:
            for d in details:
                print(f"      {d}")
    results.append(_result_dict(r, "smoke"))

    # List
    r = await _get(client, f"{base_url}/structure", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /structure  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200:
        passed = _check(isinstance(r.response_body, list), "response is list", r.check_details)
        r.checks_passed += passed
        r.checks_failed += 1 - passed
    results.append(_result_dict(r, "smoke"))

    # Catalog
    r = await _get(client, f"{base_url}/structure/catalog", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /structure/catalog  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        for key in ("categories", "styles", "conditions", "scales"):
            ok = isinstance(r.response_body.get(key), list) and len(r.response_body[key]) > 0
            r.checks_passed += _check(ok, f"'{key}' is non-empty list", r.check_details)
            r.checks_failed += 1 - ok
    results.append(_result_dict(r, "smoke"))

    # GET by ID (if we have one)
    if structure_id:
        r = await _get(client, f"{base_url}/structure/{structure_id}", timeout)
        status_icon = _icon(r)
        print(f"    {status_icon} GET /structure/{structure_id}  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
        if r.status_code == 200 and isinstance(r.response_body, dict):
            details: list[str] = []
            r.checks_passed = validate_tile_response(r.response_body, "structure", details)
            r.checks_failed = len(details) - r.checks_passed
            r.check_details = details
        results.append(_result_dict(r, "smoke"))

    # DELETE (if we have one — but we'll test on a fresh asset later)
    r = await _delete(client, f"{base_url}/structure/nonexistent_id_12345", timeout)
    status_icon = _check_icon(r.status_code == 404)
    print(f"    {status_icon} DELETE /structure/nonexistent  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 404:
        r.checks_passed += _check("detail" in (r.response_body or {}),
                                  "404 has 'detail' field", r.check_details)
        r.checks_failed += 1 - r.checks_passed
    else:
        r.checks_failed += 1
    results.append(_result_dict(r, "smoke"))

    # ------------------------------------------------------------------
    # 3. Object endpoints
    # ------------------------------------------------------------------
    print("\n  ── Object endpoints ──")
    payload = OBJECT_PAYLOADS[0]
    r = await _post(client, f"{base_url}/object", payload, timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} POST /object  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    object_id = None
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_tile_response(r.response_body, "object", details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        object_id = r.response_body.get("asset_id")
    results.append(_result_dict(r, "smoke"))

    r = await _get(client, f"{base_url}/object", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /object  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200:
        r.checks_passed += _check(isinstance(r.response_body, list), "response is list", r.check_details)
    results.append(_result_dict(r, "smoke"))

    r = await _get(client, f"{base_url}/object/catalog", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /object/catalog  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        for key in ("categories", "biomes", "seasons"):
            ok = isinstance(r.response_body.get(key), list) and len(r.response_body[key]) > 0
            r.checks_passed += _check(ok, f"'{key}' is non-empty list", r.check_details)
            r.checks_failed += 1 - ok
    results.append(_result_dict(r, "smoke"))

    if object_id:
        r = await _get(client, f"{base_url}/object/{object_id}", timeout)
        status_icon = _icon(r)
        print(f"    {status_icon} GET /object/{object_id}  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
        if r.status_code == 200 and isinstance(r.response_body, dict):
            details: list[str] = []
            r.checks_passed = validate_tile_response(r.response_body, "object", details)
            r.checks_failed = len(details) - r.checks_passed
            r.check_details = details
        results.append(_result_dict(r, "smoke"))

    # ------------------------------------------------------------------
    # 4. Terrain endpoints
    # ------------------------------------------------------------------
    print("\n  ── Terrain endpoints ──")
    payload = TERRAIN_PAYLOADS[0]
    r = await _post(client, f"{base_url}/terrain", payload, timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} POST /terrain  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    terrain_id = None
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_tile_response(r.response_body, "terrain", details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        terrain_id = r.response_body.get("asset_id")
    results.append(_result_dict(r, "smoke"))

    r = await _get(client, f"{base_url}/terrain", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /terrain  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200:
        r.checks_passed += _check(isinstance(r.response_body, list), "response is list", r.check_details)
    results.append(_result_dict(r, "smoke"))

    r = await _get(client, f"{base_url}/terrain/catalog", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /terrain/catalog  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        for key in ("categories", "scales", "materials"):
            ok = isinstance(r.response_body.get(key), list) and len(r.response_body[key]) > 0
            r.checks_passed += _check(ok, f"'{key}' is non-empty list", r.check_details)
            r.checks_failed += 1 - ok
    results.append(_result_dict(r, "smoke"))

    if terrain_id:
        r = await _get(client, f"{base_url}/terrain/{terrain_id}", timeout)
        status_icon = _icon(r)
        print(f"    {status_icon} GET /terrain/{terrain_id}  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
        if r.status_code == 200 and isinstance(r.response_body, dict):
            details: list[str] = []
            r.checks_passed = validate_tile_response(r.response_body, "terrain", details)
            r.checks_failed = len(details) - r.checks_passed
            r.check_details = details
        results.append(_result_dict(r, "smoke"))

    # ------------------------------------------------------------------
    # 5. Unit endpoints
    # ------------------------------------------------------------------
    print("\n  ── Unit endpoints ──")
    payload = UNIT_PAYLOADS[0]
    r = await _post(client, f"{base_url}/unit", payload, timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} POST /unit  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    unit_id = None
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_unit_response(r.response_body, details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        unit_id = r.response_body.get("unit_id")
    results.append(_result_dict(r, "smoke"))

    r = await _get(client, f"{base_url}/unit", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /unit  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200:
        r.checks_passed += _check(isinstance(r.response_body, list), "response is list", r.check_details)
    results.append(_result_dict(r, "smoke"))

    r = await _get(client, f"{base_url}/unit/catalog", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /unit/catalog  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        ok = isinstance(r.response_body.get("unit_types"), list)
        r.checks_passed += _check(ok, "'unit_types' is list", r.check_details)
        r.checks_failed += 1 - ok
    results.append(_result_dict(r, "smoke"))

    if unit_id:
        r = await _get(client, f"{base_url}/unit/{unit_id}", timeout)
        status_icon = _icon(r)
        print(f"    {status_icon} GET /unit/{unit_id}  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
        if r.status_code == 200 and isinstance(r.response_body, dict):
            details: list[str] = []
            r.checks_passed = validate_unit_response(r.response_body, details)
            r.checks_failed = len(details) - r.checks_passed
            r.check_details = details
        results.append(_result_dict(r, "smoke"))

    # ------------------------------------------------------------------
    # 6. Leader endpoints
    # ------------------------------------------------------------------
    print("\n  ── Leader endpoints ──")
    payload = LEADER_SPLASH_PAYLOADS[0]
    r = await _post(client, f"{base_url}/leader", payload, timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} POST /leader (splash)  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    leader_id = None
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_leader_response(r.response_body, "splash", details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        leader_id = r.response_body.get("leader_id")
        if verbose:
            for d in details:
                print(f"      {d}")
    results.append(_result_dict(r, "smoke"))

    r = await _get(client, f"{base_url}/leader", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /leader  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, list) and len(r.response_body) > 0:
        details: list[str] = []
        r.checks_passed = validate_leader_list_item(r.response_body[0], details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        if verbose:
            for d in details:
                print(f"      {d}")
    results.append(_result_dict(r, "smoke"))

    if leader_id:
        r = await _get(client, f"{base_url}/leader/{leader_id}", timeout)
        status_icon = _icon(r)
        print(f"    {status_icon} GET /leader/{leader_id}  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
        if r.status_code == 200:
            details: list[str] = []
            r.checks_passed = validate_leader_list_item(r.response_body, details)
            r.checks_failed = len(details) - r.checks_passed
            r.check_details = details
        results.append(_result_dict(r, "smoke"))

        # Profile
        profile_payload = {**LEADER_PROFILE_PAYLOAD, "leader_id": leader_id}
        r = await _post(client, f"{base_url}/leader", profile_payload, timeout)
        status_icon = _icon(r)
        print(f"    {status_icon} POST /leader (profile)  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
        if r.status_code == 200 and isinstance(r.response_body, dict):
            details: list[str] = []
            r.checks_passed = validate_leader_response(r.response_body, "profile", details)
            r.checks_failed = len(details) - r.checks_passed
            r.check_details = details
        results.append(_result_dict(r, "smoke"))

        # Action
        action_payload = {**LEADER_ACTION_PAYLOADS[0], "asset_type": "action",
                          "leader_name": "placeholder", "leader_description": "A regal ruler with a commanding presence, sharp facial features, and an elaborate jewelled crown resting upon greying hair",
                          "archetype": "warrior_king", "culture": "medieval_european",
                          "time_of_day": "golden_hour", "mood": "triumphant",
                          "leader_id": leader_id}
        r = await _post(client, f"{base_url}/leader", action_payload, timeout)
        status_icon = _icon(r)
        print(f"    {status_icon} POST /leader (action)  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
        if r.status_code == 200 and isinstance(r.response_body, dict):
            details: list[str] = []
            r.checks_passed = validate_leader_response(r.response_body, "action", details)
            r.checks_failed = len(details) - r.checks_passed
            r.check_details = details
        results.append(_result_dict(r, "smoke"))

    r = await _delete(client, f"{base_url}/leader/nonexistent_leader_12345", timeout)
    status_icon = _check_icon(r.status_code == 404)
    print(f"    {status_icon} DELETE /leader/nonexistent  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    r.checks_passed += _check(r.status_code == 404, "nonexistent leader returns 404", r.check_details)
    r.checks_failed += 1 - r.checks_passed
    results.append(_result_dict(r, "smoke"))

    # ------------------------------------------------------------------
    # 7. Background tile endpoints
    # ------------------------------------------------------------------
    print("\n  ── Background tile endpoints ──")
    payload = BACKGROUND_TILE_PAYLOADS[0]
    r = await _post(client, f"{base_url}/background_tile", payload, timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} POST /background_tile  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_background_tile_response(r.response_body, details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        if verbose:
            for d in details:
                print(f"      {d}")
    elif r.error:
        r.check_details.append(f"  ✗ {r.error}")
        r.checks_failed += 1
    else:
        detail = (r.response_body or {}).get("detail", str(r.response_body)[:100])
        r.check_details.append(f"  ✗ status {r.status_code}: {detail}")
        r.checks_failed += 1
    results.append(_result_dict(r, "smoke"))

    r = await _get(client, f"{base_url}/background_tile", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /background_tile  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200:
        r.checks_passed += _check(isinstance(r.response_body, list), "response is list", r.check_details)
    results.append(_result_dict(r, "smoke"))

    r = await _get(client, f"{base_url}/background_tile/catalog", timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} GET /background_tile/catalog  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        ok = isinstance(r.response_body.get("tile_types"), list)
        r.checks_passed += _check(ok, "'tile_types' is list", r.check_details)
        r.checks_failed += 1 - ok
    results.append(_result_dict(r, "smoke"))

    return results


# ===========================================================================
# Bulk generation
# ===========================================================================


async def run_bulk_generation(base_url: str, client: httpx.AsyncClient,
                              families: list[str], count: int,
                              timeout: float, verbose: bool) -> list[dict]:
    """Generate N assets per family, tracking stats."""
    results: list[dict] = []
    print("\n" + "=" * 64)
    print(f"  BULK GENERATION — {count} requests per family")
    print("=" * 64)

    family_configs = {
        "structure": ("/structure", STRUCTURE_PAYLOADS, "asset_id"),
        "object": ("/object", OBJECT_PAYLOADS, "asset_id"),
        "terrain": ("/terrain", TERRAIN_PAYLOADS, "asset_id"),
        "unit": ("/unit", UNIT_PAYLOADS, "unit_id"),
        "background_tile": ("/background_tile", BACKGROUND_TILE_PAYLOADS, None),
    }

    for family in families:
        if family == "leader":
            # Leader treated separately (splash generation only for bulk)
            continue

        cfg = family_configs.get(family)
        if cfg is None:
            print(f"\n    ⚠ Unknown family '{family}', skipping")
            continue

        endpoint, payloads, _id_key = cfg
        print(f"\n  ── {family} ({endpoint}) ──")

        successes = 0
        failures = 0
        timings: list[float] = []
        consecutive_fails = 0

        for i in range(count):
            payload = payloads[i % len(payloads)]
            r = await _post(client, f"{base_url}{endpoint}", payload, timeout)
            status_icon = _icon(r)

            if r.status_code == 200:
                successes += 1
                timings.append(r.elapsed_ms)
                consecutive_fails = 0
                asset_id = (r.response_body or {}).get(_id_key) if _id_key else "—"
                if verbose:
                    print(f"    {status_icon} #{i+1:3d} [{r.status_code}] {r.elapsed_ms:6.0f}ms  {asset_id}")
            else:
                failures += 1
                consecutive_fails += 1
                detail = r.error or (r.response_body or {}).get("detail", str(r.response_body)[:80])
                print(f"    {status_icon} #{i+1:3d} [{r.status_code}] {r.elapsed_ms:6.0f}ms  {detail}")

            results.append(_result_dict(r, "bulk"))

            # Stop early if server seems unhealthy
            if consecutive_fails >= CONSECUTIVE_FAILURE_THRESHOLD:
                print(f"    ⚠ {consecutive_fails} consecutive failures — stopping {family}")
                break

            # Brief pause between requests
            await asyncio.sleep(0.05)

        # Summary for this family
        if timings:
            avg_ms = sum(timings) / len(timings)
            min_ms = min(timings)
            max_ms = max(timings)
            print(f"    ✓ {successes} ok, ✗ {failures} failed | "
                  f"min/avg/max: {min_ms:.0f}/{avg_ms:.0f}/{max_ms:.0f}ms")
        else:
            print(f"    ✗ ALL {failures} requests failed")

    return results


# ===========================================================================
# Leader workflow chain test
# ===========================================================================


async def run_leader_workflow(base_url: str, client: httpx.AsyncClient,
                              timeout: float, verbose: bool) -> list[dict]:
    """Test the full leader workflow: splash → profile → action → multi-action."""
    results: list[dict] = []
    print("\n" + "=" * 64)
    print("  LEADER WORKFLOW — splash → profile → action → multi-action")
    print("=" * 64)

    # Step 1: Generate a splash to get a leader_id
    print("\n  Step 1: Generate splash")
    payload = LEADER_SPLASH_PAYLOADS[0]
    r = await _post(client, f"{base_url}/leader", payload, timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} POST /leader (splash)  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_leader_response(r.response_body, "splash", details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        if verbose:
            for d in details:
                print(f"      {d}")
    else:
        print(f"    ✗ Splash generation failed — cannot continue workflow test")
        results.append(_result_dict(r, "workflow"))
        return results
    results.append(_result_dict(r, "workflow"))

    leader_id = (r.response_body or {}).get("leader_id")
    if not leader_id:
        print(f"    ✗ No leader_id returned — cannot continue")
        return results

    # Step 2: Generate profile for the same leader
    print(f"\n  Step 2: Generate profile for {leader_id}")
    profile_payload = {**LEADER_PROFILE_PAYLOAD, "leader_id": leader_id}
    r = await _post(client, f"{base_url}/leader", profile_payload, timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} POST /leader (profile)  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_leader_response(r.response_body, "profile", details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        # Verify leader_id matches
        returned_id = r.response_body.get("leader_id")
        r.checks_passed += _check(returned_id == leader_id,
                                  f"leader_id matches ({returned_id} == {leader_id})", r.check_details)
        r.checks_failed += 1 - (returned_id == leader_id)
        if verbose:
            for d in details:
                print(f"      {d}")
    results.append(_result_dict(r, "workflow"))

    # Step 3: Generate action for the same leader
    print(f"\n  Step 3: Generate action for {leader_id}")
    action_payload = {**LEADER_ACTION_PAYLOADS[0], "asset_type": "action",
                      "leader_name": "placeholder", "leader_description": "A regal ruler with a commanding presence, sharp facial features, and an elaborate jewelled crown resting upon greying hair",
                      "archetype": "warrior_king", "culture": "medieval_european",
                      "time_of_day": "golden_hour", "mood": "triumphant",
                      "leader_id": leader_id}
    r = await _post(client, f"{base_url}/leader", action_payload, timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} POST /leader (action)  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_leader_response(r.response_body, "action", details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        returned_id = r.response_body.get("leader_id")
        r.checks_passed += _check(returned_id == leader_id,
                                  f"leader_id matches ({returned_id} == {leader_id})", r.check_details)
        r.checks_failed += 1 - (returned_id == leader_id)
        if verbose:
            for d in details:
                print(f"      {d}")
    results.append(_result_dict(r, "workflow"))

    # Step 4: Multi-leader action
    print(f"\n  Step 4: Multi-leader action with [{leader_id}]")
    multi_payload = {"asset_type": "action", "leader_name": "placeholder",
                     "leader_description": "A regal ruler with a commanding presence, sharp facial features, and an elaborate jewelled crown resting upon greying hair",
                     "archetype": "warrior_king", "culture": "medieval_european",
                     "time_of_day": "golden_hour", "mood": "triumphant",
                     "leader_ids": [leader_id],
                     "action_category": "military",
                     "action_description": "Leading a joint cavalry charge across the battlefield, swords raised high, warhorses thundering across the plains"}
    r = await _post(client, f"{base_url}/leader", multi_payload, timeout)
    status_icon = _icon(r)
    print(f"    {status_icon} POST /leader (multi-action)  [{r.status_code}]  {r.elapsed_ms:.0f}ms")
    if r.status_code == 200 and isinstance(r.response_body, dict):
        details: list[str] = []
        r.checks_passed = validate_leader_response(r.response_body, "action", details)
        r.checks_failed = len(details) - r.checks_passed
        r.check_details = details
        # Verify leader_ids are returned
        ids = r.response_body.get("leader_ids", [])
        r.checks_passed += _check(leader_id in ids,
                                  f"leader_id {leader_id} in returned leader_ids", r.check_details)
        r.checks_failed += 1 - (leader_id in ids)
        if verbose:
            for d in details:
                print(f"      {d}")
    results.append(_result_dict(r, "workflow"))

    return results


# ===========================================================================
# Edge case probing
# ===========================================================================


async def run_edge_cases(base_url: str, client: httpx.AsyncClient,
                         timeout: float, verbose: bool) -> list[dict]:
    """Probe edge cases: missing fields, invalid values, 404 paths."""
    results: list[dict] = []
    print("\n" + "=" * 64)
    print("  EDGE CASES — missing fields, invalid values, 404s")
    print("=" * 64)

    tests = [
        # (description, method, endpoint, payload, expected_status)
        ("missing required fields (structure)", "POST", "/structure",
         {"category": "fortification"}, 422),
        ("invalid enum value (structure)", "POST", "/structure",
         {"category": "spaceship", "style": "nordic_wooden", "condition": "pristine",
          "scale": "small", "description": "A test structure with enough characters to pass validation check"}, 422),
        ("description too short (structure)", "POST", "/structure",
         {"category": "fortification", "style": "nordic_wooden", "condition": "pristine",
          "scale": "small", "description": "A"}, 422),
        ("description too long (structure)", "POST", "/structure",
         {"category": "fortification", "style": "nordic_wooden", "condition": "pristine",
          "scale": "small", "description": "A" * 500}, 422),
        ("invalid unit_type", "POST", "/unit",
         {"unit_type": "dragon_rider", "description": "A brave dragon rider soaring through the skies on a majestic golden scaled dragon"}, 422),
        ("missing leader_description", "POST", "/leader",
         {"asset_type": "splash", "leader_name": "Test"}, 422),
        ("leader_description too short", "POST", "/leader",
         {"asset_type": "splash", "leader_name": "Test",
          "leader_description": "Short desc", "archetype": "warrior_king",
          "culture": "medieval_european", "time_of_day": "dawn", "mood": "triumphant"}, 422),
        ("action without category", "POST", "/leader",
         {"asset_type": "action", "leader_name": "Test", "leader_description": "A" * 60,
          "archetype": "warrior_king", "culture": "medieval_european",
          "time_of_day": "dawn", "mood": "triumphant", "leader_id": "leader_test_12345"}, 422),
        ("nonexistent structure GET", "GET", "/structure/nonexistent_id_xyz_12345", None, 404),
        ("nonexistent leader GET", "GET", "/leader/nonexistent_leader_xyz_12345", None, 404),
        ("nonexistent unit GET", "GET", "/unit/nonexistent_unit_xyz_12345", None, 404),
        ("nonexistent structure DELETE", "DELETE", "/structure/nonexistent_id_xyz_12345", None, 404),
        ("nonexistent leader DELETE", "DELETE", "/leader/nonexistent_leader_xyz_12345", None, 404),
        ("invalid asset_type (leader)", "POST", "/leader",
         {"asset_type": "animation", "leader_name": "Test",
          "leader_description": "A" * 60, "archetype": "warrior_king",
          "culture": "medieval_european", "time_of_day": "dawn", "mood": "triumphant"}, 422),
    ]

    for desc, method, endpoint, payload, expected_status in tests:
        url = f"{base_url}{endpoint}"
        if method == "POST":
            r = await _post(client, url, payload, timeout)
        elif method == "GET":
            r = await _get(client, url, timeout)
        elif method == "DELETE":
            r = await _delete(client, url, timeout)
        else:
            continue

        status_match = r.status_code == expected_status
        icon = "✓" if status_match else "✗"
        status_str = f"{r.status_code} (expected {expected_status})"
        r.checks_passed += _check(status_match, f"status {status_str}", r.check_details)
        r.checks_failed += 1 - status_match

        if r.status_code == 422:
            r.checks_passed += _check("detail" in (r.response_body or {}),
                                      "422 response has 'detail'", r.check_details)

        if not status_match or verbose:
            print(f"    {icon} {method} {endpoint} → [{r.status_code}]  {desc}")

        results.append(_result_dict(r, "edge"))

    return results


# ===========================================================================
# Helpers
# ===========================================================================


def _icon(r: RequestResult) -> str:
    """Return a status icon for a request result."""
    if r.error:
        return "✗"
    if r.status_code is None:
        return "?"
    if 200 <= r.status_code < 300:
        return "✓"
    if r.status_code == 404:
        return "○"  # Expected for edge cases
    return "✗"


def _check_icon(ok: bool) -> str:
    """Simple check icon."""
    return "✓" if ok else "✗"


def _result_dict(r: RequestResult, category: str) -> dict:
    """Serialize a RequestResult to a dict for the JSON report."""
    return {
        "category": category,
        "endpoint": r.endpoint,
        "method": r.method,
        "status_code": r.status_code,
        "elapsed_ms": r.elapsed_ms,
        "error": r.error,
        "checks_passed": r.checks_passed,
        "checks_failed": r.checks_failed,
        "check_details": r.check_details,
        # Truncate response body for JSON size
        "response_body": _truncate_body(r.response_body),
    }


def _truncate_body(body: Any, max_len: int = 500) -> Any:
    """Truncate strings in response body for compact JSON reports."""
    if isinstance(body, str) and len(body) > max_len:
        return body[:max_len] + "..."
    if isinstance(body, dict):
        return {k: _truncate_body(v, max_len) for k, v in body.items()}
    if isinstance(body, list):
        if len(body) > 10:
            return [_truncate_body(v, max_len) for v in body[:10]] + ["..."]
        return [_truncate_body(v, max_len) for v in body]
    return body


# ===========================================================================
# Main
# ===========================================================================


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    p = argparse.ArgumentParser(
        description="API Validation & Bulk Generation Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_api.py --smoke-only
  python scripts/validate_api.py --family all --count 10 --verbose
  python scripts/validate_api.py --family leader --count 5
  python scripts/validate_api.py --base-url http://192.168.1.50:8000 --family tile
        """,
    )
    p.add_argument("--base-url", default="http://localhost:8000",
                   help="Base URL of the running FastAPI server (default: http://localhost:8000)")
    p.add_argument("--family", default="all",
                   choices=["all", "tile", "leader", "unit", "background_tile",
                            "structure", "object", "terrain"],
                   help="Asset family to test (default: all)")
    p.add_argument("--count", type=int, default=0,
                   help="Number of bulk generation requests per family (0 = skip bulk)")
    p.add_argument("--timeout", type=float, default=DEFAULT_REQUEST_TIMEOUT,
                   help=f"Per-request timeout in seconds (default: {DEFAULT_REQUEST_TIMEOUT})")
    p.add_argument("--output-dir", default="reports",
                   help="Directory for JSON report output (default: reports/)")
    p.add_argument("--smoke-only", action="store_true",
                   help="Run only smoke tests and edge cases (no bulk generation)")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Show detailed check output for each request")
    return p.parse_args()


def resolve_families(family_arg: str) -> list[str]:
    """Convert family argument to list of endpoint families."""
    if family_arg == "all":
        return list(ALL_FAMILIES)
    if family_arg == "tile":
        return ["structure", "object", "terrain"]
    return [family_arg]


async def main() -> None:
    args = parse_args()

    families = resolve_families(args.family)
    print(f"🔍 API Validation Script")
    print(f"   Base URL: {args.base_url}")
    print(f"   Families: {', '.join(families)}")
    print(f"   Bulk count: {args.count}")
    print(f"   Timeout: {args.timeout}s")
    print(f"   Output dir: {args.output_dir}")

    report = RunReport(base_url=args.base_url)

    async with httpx.AsyncClient(timeout=httpx.Timeout(args.timeout)) as client:
        # 1. Smoke tests
        report.smoke_results = await run_smoke_tests(
            args.base_url, client, args.timeout, args.verbose)

        # 2. Edge cases
        report.edge_results = await run_edge_cases(
            args.base_url, client, args.timeout, args.verbose)

        # 3. Leader workflow (if leader in scope)
        if "leader" in families or args.family == "all":
            report.workflow_results = await run_leader_workflow(
                args.base_url, client, args.timeout, args.verbose)

        # 4. Bulk generation
        if args.count > 0 and not args.smoke_only:
            report.bulk_results = await run_bulk_generation(
                args.base_url, client, families, args.count,
                args.timeout, args.verbose)

    # Compute totals — "passed" means all checks passed (regardless of status code)
    for cat_key in ("smoke", "bulk", "edge", "workflow"):
        results = getattr(report, f"{cat_key}_results", [])
        passed = sum(1 for r in results
                     if r.get("checks_failed", 1) == 0)
        failed = len(results) - passed
        report.totals[cat_key] = {"passed": passed, "failed": failed}

    # Print final summary
    print("\n" + "=" * 64)
    print("  FINAL SUMMARY")
    print("=" * 64)
    for cat, counts in report.totals.items():
        if counts["passed"] + counts["failed"] > 0:
            pct = counts["passed"] / max(counts["passed"] + counts["failed"], 1) * 100
            print(f"  {cat:10s}:  ✓ {counts['passed']:4d} passed  ✗ {counts['failed']:4d} failed  ({pct:.0f}%)")

    total_passed = sum(c["passed"] for c in report.totals.values())
    total_failed = sum(c["failed"] for c in report.totals.values())
    print(f"  {'TOTAL':10s}:  ✓ {total_passed:4d} passed  ✗ {total_failed:4d} failed")
    print()

    # Write JSON report
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"validate_{timestamp}.json"

    # Build report dict manually since dataclasses aren't directly serializable
    report_dict = {
        "timestamp": report.timestamp,
        "base_url": report.base_url,
        "args": {
            "family": args.family,
            "count": args.count,
            "timeout": args.timeout,
        },
        "totals": report.totals,
        "smoke_results": report.smoke_results,
        "edge_results": report.edge_results,
        "workflow_results": report.workflow_results,
        "bulk_results": report.bulk_results[:50] if len(report.bulk_results) > 50 else report.bulk_results,
    }
    if len(report.bulk_results) > 50:
        report_dict["bulk_truncated"] = f"Only showing first 50 of {len(report.bulk_results)} results"

    with open(report_path, "w") as f:
        json.dump(report_dict, f, indent=2, default=str)
    print(f"📄 Report saved to: {report_path}")

    # Exit with non-zero if any checks failed
    if total_failed > 0:
        print(f"⚠ {total_failed} failures detected — check the report for details.")
        sys.exit(1)
    else:
        print("✅ All checks passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

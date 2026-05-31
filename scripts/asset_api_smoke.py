#!/usr/bin/env python3
"""Smoke test for the remote asset generation API.

Hits every POST endpoint the frontend uses on game start with a realistic
payload, plus the GET endpoints we rely on. Prints a coloured pass/fail
table with HTTP status + wall time and a one-line excerpt of the response.

Usage:
    python3 scripts/asset_api_smoke.py
    python3 scripts/asset_api_smoke.py --base https://other.host.example
    python3 scripts/asset_api_smoke.py --timeout 120  # per-request seconds
    python3 scripts/asset_api_smoke.py --fast        # skip slow POSTs

Exits 0 if every critical check (health + at least one generation endpoint)
passes, else 1. Uses only the Python standard library so it runs anywhere.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

DEFAULT_BASE = "https://c6-5.stixxert.dev"
# Cloudflare blocks the default Python-urllib UA. Mimic a normal browser.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
)

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"


@dataclass
class Result:
    name: str
    status: Optional[int]
    seconds: float
    body_excerpt: str
    ok: bool


def _request(
    base: str,
    path: str,
    method: str,
    body: Optional[dict],
    timeout: float,
) -> tuple[Optional[int], float, str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        base + path,
        method=method,
        headers={
            "User-Agent": UA,
            "Accept": "application/json, */*",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
        data=data,
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
            return resp.status, time.perf_counter() - started, payload[:240].decode(
                "utf-8", errors="replace"
            )
    except urllib.error.HTTPError as e:
        return e.code, time.perf_counter() - started, e.read()[:240].decode(
            "utf-8", errors="replace"
        )
    except urllib.error.URLError as e:
        return None, time.perf_counter() - started, f"URLError: {e.reason}"
    except Exception as e:  # noqa: BLE001
        return None, time.perf_counter() - started, f"{type(e).__name__}: {e}"


def run_check(
    name: str,
    base: str,
    path: str,
    method: str = "GET",
    body: Optional[dict] = None,
    timeout: float = 60.0,
    expect: int = 200,
) -> Result:
    status, seconds, excerpt = _request(base, path, method, body, timeout)
    ok = status == expect
    return Result(
        name=name,
        status=status,
        seconds=seconds,
        body_excerpt=excerpt.replace("\n", " ").strip(),
        ok=ok,
    )


def print_result(r: Result) -> None:
    status_text = str(r.status) if r.status is not None else "ERR"
    color = GREEN if r.ok else RED
    print(
        f"  {color}{'OK ' if r.ok else 'FAIL'}{RESET}  "
        f"{r.name:<32} "
        f"{color}{status_text:>4}{RESET} "
        f"{DIM}{r.seconds:>6.2f}s{RESET}  "
        f"{r.body_excerpt[:90]}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the asset API")
    parser.add_argument("--base", default=DEFAULT_BASE, help="API base URL")
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Per-request timeout in seconds (comfyui generation can take a minute)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip the slow POST endpoints (just GET checks + 1 POST for sanity)",
    )
    args = parser.parse_args()

    base = args.base.rstrip("/")
    print(f"{DIM}Asset API smoke test{RESET}  →  {base}\n")

    checks: list[Result] = []

    # 1. Quick GET sanity
    print("GETs:")
    checks.append(run_check("GET /health", base, "/health", timeout=10))
    checks.append(run_check("GET /modes", base, "/modes", timeout=10))
    checks.append(run_check("GET /leader (pool)", base, "/leader", timeout=15))
    checks.append(run_check("GET /catalog", base, "/catalog", timeout=10))
    for r in checks:
        print_result(r)

    # Print high-level mode summary if health worked
    health = checks[0]
    if health.ok:
        try:
            data = json.loads(_request(base, "/health", "GET", None, 10)[2])
            modes = data.get("modes", {})
            registered = data.get("registered", {})
            print(
                f"\n  {DIM}modes: {modes}{RESET}\n  {DIM}registered: {registered}{RESET}"
            )
        except Exception:  # noqa: BLE001
            pass

    # 2. POST generation endpoints
    post_payloads = [
        (
            "POST /leader (splash)",
            "/leader",
            {
                "asset_type": "splash",
                "leader_name": "Smoke Test Leader",
                "leader_description": (
                    "A dignified medieval ruler of middle age, fair complexion, "
                    "neatly trimmed beard, keen thoughtful eyes, wearing a "
                    "fur-trimmed velvet robe over a tunic."
                ),
                "archetype": "philosopher_king",
                "culture": "medieval_european",
                "time_of_day": "golden_hour",
                "mood": "contemplative",
            },
        ),
        (
            "POST /background_tile",
            "/background_tile",
            {"tile_type": "grass"},
        ),
        (
            "POST /unit",
            "/unit",
            {
                "unit_type": "warrior",
                "description": (
                    "a medieval foot soldier in leather and mail armor, "
                    "holding a sword and a round wooden shield, helmeted, "
                    "alert standing stance"
                ),
            },
        ),
        (
            "POST /structure",
            "/structure",
            {
                "category": "production",
                "style": "mediterranean",
                "condition": "pristine",
                "scale": "medium",
                "description": (
                    "a stone workshop with a tiled roof, a chimney trailing "
                    "smoke, an open doorway revealing a forge inside"
                ),
            },
        ),
        (
            "POST /terrain",
            "/terrain",
            {
                "category": "hill",
                "scale": "medium",
                "material": "earthen",
                "description": (
                    "a rounded grassy hill rising gently from a grass tile, "
                    "low scattered rocks on top, soft slopes"
                ),
            },
        ),
        (
            "POST /object",
            "/object",
            {
                "category": "vegetation",
                "biome": "temperate_forest",
                "season": "summer",
                "description": (
                    "a tall oak with thick gnarled branches and lush green "
                    "leaves, deep textured bark, acorns on the ground"
                ),
            },
        ),
    ]

    if args.fast:
        post_payloads = post_payloads[:1]

    print("\nPOSTs:")
    post_results: list[Result] = []
    for name, path, body in post_payloads:
        r = run_check(
            name, base, path, method="POST", body=body, timeout=args.timeout
        )
        post_results.append(r)
        print_result(r)
        checks.append(r)

    # 3. If any leader URLs came back, verify the asset actually serves PNG bytes
    print("\nAsset delivery:")
    leader_results = [r for r in post_results if "leader" in r.name]
    asset_path = None
    if leader_results and leader_results[0].ok:
        try:
            url = json.loads(leader_results[0].body_excerpt + "}").get("url")
        except Exception:  # noqa: BLE001
            # JSON might be truncated; re-fetch fresh leader list and grab one
            url = None
        if not url:
            try:
                pool_status, _, pool_body = _request(
                    base, "/leader", "GET", None, 10
                )
                if pool_status == 200:
                    pool = json.loads(pool_body if pool_body.startswith("[") else "[]")
                    for entry in pool:
                        if entry.get("splash_url"):
                            url = entry["splash_url"]
                            break
            except Exception:  # noqa: BLE001
                pass
        asset_path = url

    if asset_path:
        delivery = run_check(
            f"GET {asset_path[:48]}…",
            base,
            asset_path,
            timeout=20,
        )
        # Inspect content-type via a HEAD-equivalent: just check first bytes
        status, secs, _ = _request(base, asset_path, "GET", None, 20)
        is_png = False
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    base + asset_path,
                    headers={"User-Agent": UA},
                ),
                timeout=20,
            ) as resp:
                first = resp.read(8)
                is_png = first.startswith(b"\x89PNG\r\n\x1a\n")
                delivery.body_excerpt = (
                    f"first bytes {'OK PNG' if is_png else first.hex()}; "
                    f"{resp.headers.get('content-type', '?')}"
                )
                delivery.ok = is_png
        except Exception as e:  # noqa: BLE001
            delivery.body_excerpt = f"could not fetch bytes: {e}"
            delivery.ok = False
        print_result(delivery)
        checks.append(delivery)
    else:
        print(f"  {YELLOW}SKIP{RESET}  no leader splash URL available to verify")

    # 4. Summary
    passed = sum(1 for c in checks if c.ok)
    total = len(checks)
    critical_ok = checks[0].ok and any(
        c.ok for c in checks if c.name.startswith("POST")
    )
    summary_color = GREEN if critical_ok else RED
    print(
        f"\n{summary_color}━━━{RESET} {passed}/{total} passed "
        f"{summary_color}━━━{RESET}\n"
    )

    failing = [c for c in checks if not c.ok]
    if failing:
        print(f"{YELLOW}Failing:{RESET}")
        for c in failing:
            print(f"  - {c.name}: HTTP {c.status} | {c.body_excerpt[:120]}")
        print()

    return 0 if critical_ok else 1


if __name__ == "__main__":
    sys.exit(main())

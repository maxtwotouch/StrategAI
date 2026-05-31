#!/usr/bin/env bash
# Smoke-test all POST endpoints with minimal valid payloads.
# Usage: ./scripts/smoke_test_endpoints.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://localhost:8000}"
PASS=0
FAIL=0

test_endpoint() {
  local name="$1" method="$2" path="$3" payload="$4"
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' -X "$method" "$BASE$path" \
    -H 'Content-Type: application/json' -d "$payload")
  if [ "$code" = "200" ]; then
    echo "  ✓ PASS  $name ($code)"
    ((++PASS))
  else
    echo "  ✗ FAIL  $name (got $code, expected 200)"
    ((++FAIL))
  fi
  # Rate-limit: sleep briefly between requests
  sleep 0.5
}

echo "=== Smoke-testing POST endpoints at $BASE ==="
echo ""

test_endpoint "Leader splash"   POST /leader \
  '{"asset_type":"splash","leader_name":"Test","leader_description":"A test leader standing on castle ramparts at sunrise with a sword raised overlooking the kingdom.","archetype":"warrior_king","culture":"medieval_european","time_of_day":"dawn","mood":"triumphant"}'

test_endpoint "Structure"       POST /structure \
  '{"category":"fortification","style":"nordic_wooden","condition":"pristine","scale":"small","description":"A small wooden watchtower with a pointed roof and signal fire."}'

test_endpoint "Object"          POST /object \
  '{"category":"vegetation","biome":"temperate_forest","season":"autumn","description":"An ancient oak tree with gnarled branches and autumn leaves on the ground."}'

test_endpoint "Terrain"         POST /terrain \
  '{"category":"hill","scale":"medium","material":"earthen","description":"A gently rolling earthen hill with wildflowers and exposed rocks on the slope."}'

test_endpoint "Unit"            POST /unit \
  '{"unit_type":"archer","description":"A medieval archer in green leather armor with a yew longbow and quiver."}'

test_endpoint "Background tile" POST /background_tile \
  '{"tile_type":"grass"}'

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1

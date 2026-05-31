# Asset Service Integration

The game pulls generative pixel-art assets — terrain tiles, unit sprites,
city buildings, terrain elevation overlays, leader splash + profile — from a
separate **Medieval Pixel Art Image Service** (`TopDownMedievalPixelArt-Prod`).
This document covers the contract, the resolver, the no-cache policy, and the
graceful-fallback behavior so the game stays playable when the service is
degraded.

For the game-side mechanics see [GAMEPLAY.md](GAMEPLAY.md); for UI surfaces
see [UI_GUIDE.md](UI_GUIDE.md).

---

## 1. Configuration

Single env var, read at Next.js dev-server startup:

```bash
# frontend/.env.local
NEXT_PUBLIC_ASSET_API_URL=https://c6-5.stixxert.dev
```

The `NEXT_PUBLIC_` prefix is required for the value to be inlined into the
client bundle. Restart `next dev` after editing the file.

**When unset**, `assetApiConfigured()` returns false and `resolveManifest()`
returns `null` immediately — the game renders with built-in colors, glyphs,
and letter-initial portraits. No asset requests are made.

A `frontend/.env.example` shows the expected shape.

### Same-origin proxy (CORS shield)

POST and JSON GET calls from the browser route through a Next.js API route at
**`/api/asset/[...path]`** (`frontend/app/api/asset/[...path]/route.ts`) which
forwards server-to-server to `NEXT_PUBLIC_ASSET_API_URL`. The browser only
ever talks to its own origin, so CORS is never a factor — including when the
upstream returns 5xx (typical CORS gotcha: error responses don't include
`Access-Control-Allow-Origin` headers, and browsers report that as a CORS
failure even though the real problem is the 5xx).

**PNG fetches do not go through the proxy.** `<img src>` and SVG
`<image href>` aren't CORS-restricted for display, so `absoluteAssetUrl()`
still returns direct `https://…/assets/{uuid}.png` URLs — no extra Next.js
hop on every map tile.

---

## 2. Endpoints We Use

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/leader` | Splash, profile, or action art for a leader (one request per stage; profile chains via `leader_id`). |
| `GET` | `/leader` | List existing generated leaders — used as a fallback pool when splash POSTs fail. |
| `POST` | `/background_tile` | One of 5 ground textures (`water`, `grass`, `sand`, `stone`, `dirt`). |
| `POST` | `/unit` | Single south-facing 128×128 sprite per `unit_type`. |
| `POST` | `/structure` | Building art keyed by category × style × condition × scale. |
| `POST` | `/terrain` | Elevation overlay (hill, cliff, etc.) layered on top of base tiles. |
| `GET` | `/assets/{filename}` | Returns the generated PNG. |
| `GET` | `/health` | Mode + comfyui connectivity + registry counts. |

`GET /leader` supports pagination (`?limit=`, `?offset=`); default limit is
50 which is plenty for our fallback pool.

`POST` request schemas use `model_config = ConfigDict(extra="forbid")` —
extra fields are rejected. Our client (`lib/assetApi.ts`) only sends fields
that exist on the corresponding `*Request` Pydantic model.

---

## 3. Mapping Game Taxonomy → Service Vocabularies

The game has more terrain types than the service's background-tile vocabulary,
more unit types than the service's unit catalog, etc. Deterministic mapping
tables live in `frontend/lib/`:

### Background tiles (`assetManifest.ts:TERRAIN_TO_TILE_TYPE`)

13 terrains collapse onto 5 tile_types. Different game terrains sharing a type
each resolve their own image, so e.g. ocean / coast / lake all map to
`water` but receive distinct generations.

```
ocean | coast | lake          → water
grassland | plains | savanna
| forest | taiga              → grass
hills | mountain | tundra | snow → stone
desert                          → sand
```

### Units (`assetMapping.ts:UNIT_TYPE_MAP` + `unitDescriptionFor`)

7 game units collapse onto 4 service types:

```
warrior, swordsman, horseman → warrior
archer                       → archer
scout                        → scout
settler, worker              → settler
```

**Per-civ unique sprites.** The resolver fans out across **every civ × every
service unit type** (so 4 civs × 4 types = 16 POSTs per game start), passing a
civ-specific description so each civilization's units look distinct.
`unitDescriptionFor(apiType, culture, leaderName)` combines the gameplay unit
role with that civ's materials, kit, and visual motifs. The human player's
custom culture is passed through this same path.
The manifest stores units as `Record<civId, Record<gameUnitType, url>>`, and
`SquareMap` looks up `assets.units[unit.owner]?.[unit.type]` so each civ's
units render with their own sprite even when they happen to be the same
gameplay type.

### Elevation overlays (`assetMapping.ts:ELEVATION_TERRAINS`)

Only `hills` and `mountain` opt in — they receive a transparent relief sprite
rendered on top of the base terrain tile. Each entry holds a `category`,
`scale`, `material`, and a description matching the `/terrain` schema.

### City structures (`assetMapping.ts:cityStructureFor`)

Structure prompts are also civ-specific. `cityStructureFor(leaderName, category,
culture)` keeps the gameplay category clear (`production`, `fortification`,
`housing`, `sacred`) while adding per-civ style, materials, silhouette, and
motifs. Descriptions are capped before POSTing so they stay inside the
structure API's request limits.

### Leader portraits (`leaderMapping.ts`)

Two paths into the leader pipeline:

- **`leaderParamsFor(leaderName)`** — used for the fixed AI roster
  (Genghis, Cleopatra, Gandhi). Returns full `LeaderParams` with hand-authored
  description, archetype, culture, time-of-day, mood.
- **`buildCustomLeaderParams({leaderName, archetype, culture, description})`**
  — used for the human civ. Pulls user-supplied values from the start screen
  setup state with safe defaults; pads too-short descriptions up to the 50-char
  floor the API requires.

---

## 4. Resolver Flow (`assetManifest.ts:resolveManifest`)

Called from `loadGame()` after `api.createGame()` returns, inside the loading
phase.

```
resolveManifest({ gameId, terrains, civs, leaders }, { onProgress }) ──┐
                                                                       │
1.  assetApiConfigured() ──── false ──► return null  ◄─── NEXT_PUBLIC_… unset
                                                                       │
2.  Compute work items:                                              ◄─┘
       distinctTerrains   = unique(terrains) ∩ TERRAIN_TO_TILE_TYPE
       elevationTerrains  = unique(terrains) ∩ ELEVATION_TERRAINS
       apiUnitTypes       = unique(values(UNIT_TYPE_MAP))     // = 4
       civs               // for per-civ /unit and per-category /structure batches
       leaders            // for /leader (splash+profile)

3.  Fetch leader pool once:    listLeaders()  GET /leader

4.  Run all batches concurrently via mapLimit():
       terrainWork    limit 4   → POST /background_tile     × distinctTerrains
       elevationWork  limit 2   → POST /terrain             × elevationTerrains
       unitWork                 → per civ in parallel, each civ runs
                                  mapLimit(apiUnitTypes, 2) so up to
                                  civs × 2 unit POSTs are in flight at once
                                  (descriptions are culture-flavored per civ)
       structureWork           → per civ in parallel, each civ runs
                                  mapLimit(structure categories, 2)
                                  so each category gets distinct art
       leaderWork     limit 2   → POST /leader splash → POST /leader profile
                                  (per civ; falls back to pool on POST failure)

5.  Build the manifest object and return it to loadGame() → setAssets(manifest).
```

There is **no caching layer** — every game start (and every page refresh that
triggers a new game) re-resolves from the asset service. This keeps the game
honest about backend restarts that reuse a `gameId`: stale URLs from a
previous deploy can never linger in `localStorage`.

`mapLimit(items, limit, worker)` is a small concurrency-limited iterator —
keeps in-flight requests under control even when the asset server is GPU-bound
on the ComfyUI side.

Each per-asset call is wrapped in `try/catch`. **Failures don't break the
manifest**; they just leave the corresponding key unset, and the renderer
falls back to its built-in surface. After the full fan-out, the manifest is
returned even if half the batches failed.

### Progress reporting

`onProgress(done, total)` fires after every individual completion. The Loading
Screen surfaces this as `Conjuring world art… {done}/{total}`. `total` =
sum of items across all batches.

---

## 5. The `AssetManifest`

```ts
interface AssetManifest {
  gameId: number;
  terrain:    Record<string, string>;          // gameTerrain    → tile URL
  elevation:  Record<string, string>;          // gameTerrain    → overlay URL
  units:      Record<number, Record<string, string>>;
                                               // civId → gameUnitType → sprite URL
  structures: Record<number, Record<string, string>>;
                                               // civId → category → building URL
  leaders:    Record<number, LeaderAssets>;    // civId          → { splash, profile }
}
```

URLs in the manifest are **absolute** (the resolver runs every `/assets/...`
response through `absoluteAssetUrl()` to prefix the base URL). That means the
manifest is self-contained: the renderer doesn't need to know about the asset
service base URL.

---

## 6. No Caching

The asset manifest is **not persisted**. Every game start hits the asset
service fresh. Earlier iterations cached the manifest in `localStorage` keyed
by `{hostTag}:{gameId}`, but that masked a real problem: when the backend
restarted and reused a `gameId`, the cache served URLs the asset server had
since rotated out — and that looked identical to "the resolver never fired."
The performance win of skipping fetches at game start (a few seconds behind
the load screen) wasn't worth that hazard.

### What happens on:

- **New game.** Full resolution every time.
- **Page refresh during a game.** Lost React state forces the user back to
  the start screen; the next Begin Campaign creates a new game and a new
  resolution.
- **Backend restart that reuses a `gameId`.** Doesn't matter — there's nothing
  cached to reuse.

`lib/assetManifest.ts` includes a one-off `localStorage` housekeeping block
that wipes `inf3600:assetManifest:*` entries left over from the cached era.
Safe to delete after a release or two.

### Browser-console helpers

```js
// verify the env var made it into the bundle
console.log(process.env.NEXT_PUBLIC_ASSET_API_URL);

// confirm no stale manifests linger (should always be empty now)
Object.keys(localStorage).filter(k => k.startsWith("inf3600:assetManifest:"));
```

---

## 7. Graceful Fallback

The frontend is built to look reasonable in every degraded state.

### Failed POST per family

- `terrain[…]` missing → `<image>` not rendered for that terrain; the
  underlying color fill shows through.
- `elevation[…]` missing → no relief overlay; base terrain renders alone.
- `units[…]` missing → `SquareMap` falls back to the colored rect + glyph for
  that unit type.
- `structures[civId][category]` missing → placed structures render with the
  built-in compact building marker.
- `leaders[civId]` empty → portraits in the badge and drawers fall back to
  the first letter of the civ name in a faction-color shape.

### Browser load failure on a resolved URL

If a URL resolves but the browser fails to fetch it (404, CORS, network
error), the `onError` handler on the SVG `<image>` adds the URL to a
`failedHrefs` Set. Subsequent renders skip that URL across **all** tiles that
share it, so a single broken file doesn't leave 50 broken-image icons on the
map.

### Splash POST fails → leader pool fallback (`pickFromPool`)

When `POST /leader` rejects for a civ, the resolver picks a leader from the
already-existing pool returned by `GET /leader`:

1. Rank pool entries by match against the civ's archetype + culture
   (`archetype` match = 2 pts; `culture` match = 1 pt; sum descending).
2. Modulo by `civId` so distinct civs in the same game pick distinct entries
   when the pool has more than one suitable leader.
3. Assign `splash_url` and (if present) `profile_url` after running through
   `absoluteAssetUrl`.

The result: even during a generation outage, the Sovereign Overlay / audience
backgrounds keep showing real art instead of blank dark gradients.

### Asset service entirely unreachable

`GET /leader` and every `POST` rejects → manifest has empty maps for everything.
`SquareMap` renders identically to the no-env-var case (color fills, glyphs,
initials). The game is fully playable.

---

## 8. Smoke Testing

`scripts/asset_api_smoke.py` is a stdlib-only Python script that hits every
endpoint with realistic payloads and prints a coloured pass/fail table.

```bash
python3 scripts/asset_api_smoke.py             # full run (~2 min when healthy)
python3 scripts/asset_api_smoke.py --fast      # GETs + 1 POST (~10 s)
python3 scripts/asset_api_smoke.py --base URL  # override base
python3 scripts/asset_api_smoke.py --timeout 180
```

Sets a Safari User-Agent to avoid Cloudflare's bot block (a `Python-urllib/x.y`
UA gets 403'd by the WAF on this host). Exits 0 iff `/health` passes and at
least one POST returns 200.

---

## 9. Debugging Game-Start Asset Resolution

Open DevTools console + Network tab, click Begin Campaign:

1. **Console** prints one of:
   - `[assetManifest] Resolving game N: X tiles, Y civs, Z leaders → POSTing to asset service…` (fetches firing)
   - `[assetManifest] NEXT_PUBLIC_ASSET_API_URL is empty — skipping all asset fetches.` (restart `next dev`)
2. **Network → filter `stixxert`** (or whatever your host is) shows every
   actual HTTP request with status + duration. You'll see the resolver fan-out
   live.

---

## 10. Known Issues with the Live Asset Service

(As of this writing — see the commit history of the asset repo for current
status.)

- **`POST /background_tile`, `/unit`, `/structure`, `/terrain`, `/object`
  return HTTP 400** with `{"detail": "'utf-32-be' codec can't decode bytes
  in position 8-11: code point not in range(0x110000)"}`. Reproducible across
  request shapes; not a client encoding issue. The math: bytes 8-11 of
  `{"tile_type":"grass"}` are ASCII `tile` = `0x7469_6C65` which exceeds
  Unicode's `0x110000` cap. Something on the server is calling
  `.decode("utf-32-be")` on raw UTF-8 JSON bytes in those routes. The
  `/leader` pipeline doesn't go through that code path and is unaffected.
- **Profile generation is rare in the existing leader pool.** All current
  pool leaders have `profile_url: null`. Until the splash→profile chain
  succeeds for at least one civ, portrait-shaped surfaces (empire badge,
  drawer/audience avatars) keep falling back to initials.

Tracked in the bug report; once the server is redeployed, no client changes
are needed.

---

## 11. Reference

| Topic | File |
|---|---|
| Asset service client | `frontend/lib/assetApi.ts` |
| Resolver | `frontend/lib/assetManifest.ts` |
| Game-side mappings | `frontend/lib/assetMapping.ts` |
| Leader mapping (deterministic + custom) | `frontend/lib/leaderMapping.ts` |
| Manifest consumption | `frontend/components/SquareMap.tsx` + `frontend/app/page.tsx` (empire badge, sovereign overlay, diplomatic audience) |
| Smoke test | `scripts/asset_api_smoke.py` |
| Env example | `frontend/.env.example` |

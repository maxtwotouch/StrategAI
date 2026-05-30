// Resolves the game's asset URLs once per game start and caches them.
//
// The service generates a fresh image per POST, so we resolve each asset
// *type* once and reuse the URL. Resolution is keyed by gameId: a new game
// gets a fresh look, while reloading the same game reuses the cached set.
// When NEXT_PUBLIC_ASSET_API_URL is unset, resolution is a no-op (null) and
// the game renders with its built-in colors and initials.

import {
  ApiUnitType,
  BackgroundTileType,
  assetApiConfigured,
  generateBackgroundTile,
  generateLeaderProfile,
  generateLeaderSplash,
  generateStructure,
  generateTerrainFeature,
  generateUnit,
} from "@/lib/assetApi";
import { leaderParamsFor } from "@/lib/leaderMapping";
import {
  ELEVATION_TERRAINS,
  UNIT_TYPE_MAP,
  cityStructureFor,
  unitDescriptionFor,
} from "@/lib/assetMapping";

// 13 game terrains collapse onto the 4 background-tile types the service
// offers. Each distinct terrain still resolves its own image, so terrains
// sharing a type (e.g. ocean/coast/lake) look different within a game.
export const TERRAIN_TO_TILE_TYPE: Record<string, BackgroundTileType> = {
  ocean: "water",
  coast: "water",
  lake: "water",
  grassland: "grass",
  plains: "grass",
  savanna: "grass",
  forest: "grass",
  taiga: "grass",
  hills: "stone",
  mountain: "stone",
  tundra: "stone",
  snow: "stone",
  desert: "sand",
};

export interface LeaderAssets {
  splashUrl?: string;
  profileUrl?: string;
}

export interface AssetManifest {
  gameId: number;
  terrain: Record<string, string>; // terrain key → base tile image URL
  elevation: Record<string, string>; // terrain key → relief overlay URL
  units: Record<string, string>; // game unit type → south-facing sprite URL
  structures: Record<number, string>; // civ id → city building URL
  leaders: Record<number, LeaderAssets>; // civ id → portrait/splash URLs
}

export interface CivInput {
  civId: number;
  leaderName: string;
}

export interface ResolveInput {
  gameId: number;
  terrains: string[];
  civs: CivInput[]; // all civs — drives city/structure art
  leaders: CivInput[]; // civs that get leader portraits (typically non-human)
}

export interface ResolveOptions {
  signal?: AbortSignal;
  onProgress?: (done: number, total: number) => void;
}

const CACHE_PREFIX = "inf3600:assetManifest:";

function cacheKey(gameId: number): string {
  return `${CACHE_PREFIX}${gameId}`;
}

export function loadCachedManifest(gameId: number): AssetManifest | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(cacheKey(gameId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AssetManifest;
    return parsed.gameId === gameId ? parsed : null;
  } catch {
    return null;
  }
}

function saveManifest(manifest: AssetManifest): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(cacheKey(manifest.gameId), JSON.stringify(manifest));
  } catch {
    // localStorage full or unavailable — non-fatal; manifest stays in memory.
  }
}

// Run an async worker over items with a bounded number in flight, so we don't
// open dozens of parallel generations against a (possibly GPU-bound) server.
async function mapLimit<T>(
  items: T[],
  limit: number,
  worker: (item: T) => Promise<void>,
): Promise<void> {
  let cursor = 0;
  const runners = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      const index = cursor;
      cursor += 1;
      await worker(items[index]);
    }
  });
  await Promise.all(runners);
}

export async function resolveManifest(
  input: ResolveInput,
  options: ResolveOptions = {},
): Promise<AssetManifest | null> {
  if (!assetApiConfigured()) return null;

  const { gameId, terrains, civs, leaders } = input;

  const cached = loadCachedManifest(gameId);
  if (cached) return cached;

  const distinctTerrains = [...new Set(terrains)].filter(
    (t) => t in TERRAIN_TO_TILE_TYPE,
  );
  const elevationTerrains = [...new Set(terrains)].filter(
    (t) => t in ELEVATION_TERRAINS,
  );
  const apiUnitTypes = [...new Set(Object.values(UNIT_TYPE_MAP))];

  const total =
    distinctTerrains.length +
    elevationTerrains.length +
    apiUnitTypes.length +
    civs.length +
    leaders.length;
  let done = 0;
  const tick = () => options.onProgress?.((done += 1), total);
  options.onProgress?.(0, total);

  const terrain: Record<string, string> = {};
  const elevation: Record<string, string> = {};
  const apiUnitUrls: Partial<Record<ApiUnitType, string>> = {};
  const structures: Record<number, string> = {};
  const leaderAssets: Record<number, LeaderAssets> = {};

  const terrainWork = mapLimit(distinctTerrains, 4, async (terrainKey) => {
    try {
      terrain[terrainKey] = await generateBackgroundTile(
        TERRAIN_TO_TILE_TYPE[terrainKey],
        options.signal,
      );
    } catch {
      // Leave unmapped → renderer falls back to the terrain color.
    } finally {
      tick();
    }
  });

  const elevationWork = mapLimit(elevationTerrains, 2, async (terrainKey) => {
    try {
      elevation[terrainKey] = await generateTerrainFeature(
        ELEVATION_TERRAINS[terrainKey],
        options.signal,
      );
    } catch {
      // No overlay → the base terrain tile renders alone.
    } finally {
      tick();
    }
  });

  const unitWork = mapLimit(apiUnitTypes, 2, async (apiType) => {
    try {
      apiUnitUrls[apiType] = await generateUnit(
        apiType,
        unitDescriptionFor(apiType),
        options.signal,
      );
    } catch {
      // No sprite → renderer falls back to the colored glyph.
    } finally {
      tick();
    }
  });

  const structureWork = mapLimit(civs, 2, async ({ civId, leaderName }) => {
    try {
      structures[civId] = await generateStructure(
        cityStructureFor(leaderName),
        options.signal,
      );
    } catch {
      // No building art → cities render as the colored marker.
    } finally {
      tick();
    }
  });

  const leaderWork = mapLimit(leaders, 2, async ({ civId, leaderName }) => {
    try {
      const params = leaderParamsFor(leaderName);
      const splash = await generateLeaderSplash(params, options.signal);
      const assets: LeaderAssets = { splashUrl: splash.url };
      try {
        assets.profileUrl = await generateLeaderProfile(
          params,
          splash.leaderId,
          options.signal,
        );
      } catch {
        // Profile failed — keep the splash, drawer falls back to the initial.
      }
      leaderAssets[civId] = assets;
    } catch {
      // Leader failed entirely → UI falls back to the colored initial.
    } finally {
      tick();
    }
  });

  await Promise.all([
    terrainWork,
    elevationWork,
    unitWork,
    structureWork,
    leaderWork,
  ]);

  // Expand the per-API-type unit sprites back onto every game unit type.
  const units: Record<string, string> = {};
  for (const [gameType, apiType] of Object.entries(UNIT_TYPE_MAP)) {
    const url = apiUnitUrls[apiType];
    if (url) units[gameType] = url;
  }

  const manifest: AssetManifest = {
    gameId,
    terrain,
    elevation,
    units,
    structures,
    leaders: leaderAssets,
  };
  // Only cache when something actually resolved — otherwise a transient outage
  // would freeze an empty manifest and block retries on the next load.
  const resolvedAny =
    Object.keys(terrain).length > 0 ||
    Object.keys(elevation).length > 0 ||
    Object.keys(units).length > 0 ||
    Object.keys(structures).length > 0 ||
    Object.keys(leaderAssets).length > 0;
  if (resolvedAny) saveManifest(manifest);
  return manifest;
}

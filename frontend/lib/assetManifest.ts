// Resolves the game's asset URLs on every game start.
//
// No persistent cache. Every `Begin Campaign` (and every page refresh that
// triggers a new game) hits the asset service fresh, so backend restarts that
// reuse a gameId can never serve stale URLs that the asset server has rotated
// out. When NEXT_PUBLIC_ASSET_API_URL is unset, resolution is a no-op (null)
// and the game renders with its built-in colors and initials.

// One-time housekeeping: wipe any old localStorage entries from earlier
// sessions when caching was still on, so they don't sit forever in users'
// browsers. Safe to remove this block after one or two releases.
if (typeof window !== "undefined") {
  try {
    for (const key of Object.keys(window.localStorage)) {
      if (key.startsWith("inf3600:assetManifest:")) {
        window.localStorage.removeItem(key);
      }
    }
  } catch {
    // localStorage unavailable — nothing to clean.
  }
}

import {
  ApiUnitType,
  BackgroundTileType,
  ExistingLeader,
  absoluteAssetUrl,
  assetApiConfigured,
  generateBackgroundTile,
  generateLeaderProfile,
  generateLeaderSplash,
  generateStructure,
  generateTerrainFeature,
  generateUnit,
  listLeaders,
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
  // civ id → game unit type → south-facing sprite URL.
  // Each civ gets its own per-culture variant of the four API unit types.
  units: Record<number, Record<string, string>>;
  structures: Record<number, string>; // civ id → city building URL
  leaders: Record<number, LeaderAssets>; // civ id → portrait/splash URLs
}

export interface CivInput {
  civId: number;
  leaderName: string;
  // When provided, used verbatim instead of the deterministic lookup table —
  // lets the player author their own leader (see start screen inputs).
  customLeaderParams?: import("@/lib/assetApi").LeaderParams;
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
  if (!assetApiConfigured()) {
    // eslint-disable-next-line no-console
    console.info(
      "[assetManifest] NEXT_PUBLIC_ASSET_API_URL is empty — skipping all asset fetches. Restart `next dev` after editing .env.local.",
    );
    return null;
  }

  const { gameId, terrains, civs, leaders } = input;

  // No persistent cache — every Begin Campaign + every page refresh hits the
  // asset service fresh. The original localStorage cache was masking stale
  // URLs whenever the backend restarted and reused a gameId, and the speed
  // win of skipping fetches doesn't outweigh that hazard.
  // eslint-disable-next-line no-console
  console.info(
    `[assetManifest] Resolving game ${gameId}: ${terrains.length} tiles, ${civs.length} civs, ${leaders.length} leaders → POSTing to asset service…`,
  );

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
    civs.length * apiUnitTypes.length + // per-civ unit sprites
    civs.length + // city structures
    leaders.length;
  let done = 0;
  const tick = () => options.onProgress?.((done += 1), total);
  options.onProgress?.(0, total);

  const terrain: Record<string, string> = {};
  const elevation: Record<string, string> = {};
  const unitsByCiv: Record<number, Record<string, string>> = {};
  const structures: Record<number, string> = {};
  const leaderAssets: Record<number, LeaderAssets> = {};

  // Each civ's culture comes from either the player-authored custom params
  // (human) or the deterministic leader lookup (AI). Drives the per-civ
  // unit-sprite description so each civilization has its own visual flavor.
  const cultureFor = (civ: CivInput): string =>
    civ.customLeaderParams?.culture ?? leaderParamsFor(civ.leaderName).culture;

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

  // Per-civ unit sprites: each civilization generates its own four API types
  // (warrior / archer / scout / settler) with a culture-flavored description.
  // Runs all civs' batches in parallel, each batch with up to 2 sprites in
  // flight to avoid hammering the asset server.
  const unitWork = Promise.all(
    civs.map(async (civ) => {
      const culture = cultureFor(civ);
      const civUrls: Record<string, string> = {};
      const apiUrls: Partial<Record<ApiUnitType, string>> = {};
      await mapLimit(apiUnitTypes, 2, async (apiType) => {
        try {
          apiUrls[apiType] = await generateUnit(
            apiType,
            unitDescriptionFor(apiType, culture),
            options.signal,
          );
        } catch {
          // No sprite → renderer falls back to the colored glyph.
        } finally {
          tick();
        }
      });
      for (const [gameType, apiType] of Object.entries(UNIT_TYPE_MAP)) {
        const url = apiUrls[apiType];
        if (url) civUrls[gameType] = url;
      }
      if (Object.keys(civUrls).length > 0) unitsByCiv[civ.civId] = civUrls;
    }),
  );

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

  // Pull the existing leader catalog once so we can fall back to it when a
  // POST fails (e.g., upstream generation errors). Best-match by
  // archetype+culture, then rotate by civ id so distinct civs get distinct
  // leaders when the pool has more than one entry.
  const leaderPool: ExistingLeader[] = await listLeaders(options.signal);

  function pickFromPool(
    archetype: string,
    culture: string,
    civId: number,
  ): ExistingLeader | null {
    if (leaderPool.length === 0) return null;
    const ranked = [...leaderPool].sort((a, b) => {
      const scoreA =
        (a.archetype === archetype ? 2 : 0) + (a.culture === culture ? 1 : 0);
      const scoreB =
        (b.archetype === archetype ? 2 : 0) + (b.culture === culture ? 1 : 0);
      return scoreB - scoreA;
    });
    return ranked[civId % ranked.length] ?? null;
  }

  const leaderWork = mapLimit(leaders, 2, async ({ civId, leaderName, customLeaderParams }) => {
    try {
      const params = customLeaderParams ?? leaderParamsFor(leaderName);
      const assets: LeaderAssets = {};
      try {
        const splash = await generateLeaderSplash(params, options.signal);
        assets.splashUrl = splash.url;
        try {
          assets.profileUrl = await generateLeaderProfile(
            params,
            splash.leaderId,
            options.signal,
          );
        } catch {
          // Profile failed — keep the splash.
        }
      } catch {
        // Splash POST failed (server-side generation outage). Fall back to a
        // matching entry from the existing leader catalog so the slot still
        // shows real art rather than an initial.
        const fallback = pickFromPool(params.archetype, params.culture, civId);
        if (fallback?.splash_url) {
          assets.splashUrl = absoluteAssetUrl(fallback.splash_url);
        }
        if (fallback?.profile_url) {
          assets.profileUrl = absoluteAssetUrl(fallback.profile_url);
        }
      }
      if (assets.splashUrl || assets.profileUrl) {
        leaderAssets[civId] = assets;
      }
    } catch {
      // Total failure → UI falls back to the colored initial.
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

  const manifest: AssetManifest = {
    gameId,
    terrain,
    elevation,
    units: unitsByCiv,
    structures,
    leaders: leaderAssets,
  };
  return manifest;
}

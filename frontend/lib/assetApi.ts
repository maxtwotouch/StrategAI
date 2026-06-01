// Client for the remote Medieval Pixel Art asset service.
//
// The service is a generate-and-cache API: every POST returns a freshly
// generated PNG under a unique /assets/{uuid}.png URL. There is no stable
// "look up the grass tile" endpoint, so callers resolve each asset type once
// and reuse the returned URL (see assetManifest.ts).
//
// Base URL comes from NEXT_PUBLIC_ASSET_API_URL. When unset, the client
// reports itself unconfigured and the game renders with its built-in colors.

const ASSET_BASE_URL = (process.env.NEXT_PUBLIC_ASSET_API_URL ?? "").replace(/\/+$/, "");

// All POST / generation calls route through this Next.js API route. The proxy
// (app/api/asset/[...path]/route.ts) forwards to the asset server server-to-
// server, which sidesteps browser CORS checks for JSON API calls.
const PROXY_PREFIX = "/api/asset";

export type BackgroundTileType = "water" | "grass" | "sand" | "stone" | "dirt";

interface BackgroundTileResponse {
  url: string;
  background_tile_id: string;
  tile_type: string;
  seed: number;
  generation_mode: string;
}

export function assetApiConfigured(): boolean {
  return ASSET_BASE_URL.length > 0;
}

// Turn a service-relative URL ("/assets/x.png") into a direct image URL the
// browser can render in <img> and SVG <image>. Image display is not blocked by
// CORS, and keeping PNGs direct avoids routing high-volume map tile loads
// through the Next.js API proxy.
export function absoluteAssetUrl(url: string): string {
  if (!url) return url;
  if (/^https?:\/\//i.test(url)) return url;
  return `${ASSET_BASE_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

async function postJson<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(`${PROXY_PREFIX}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

// POST /background_tile. Returns an absolute image URL.
export async function generateBackgroundTile(
  tileType: BackgroundTileType,
  signal?: AbortSignal,
): Promise<string> {
  const res = await postJson<BackgroundTileResponse>(
    "/background_tile",
    { tile_type: tileType },
    signal,
  );
  return absoluteAssetUrl(res.url);
}

// Leader pipeline. The service is enum-driven: the client picks vocabulary
// values and supplies a free-text physical description. No LLM is required —
// see lib/leaderMapping.ts for the deterministic game-leader → params table.
export interface LeaderParams {
  leaderName: string;
  leaderDescription: string; // physical description, 50-800 chars
  archetype: string;
  culture: string;
  timeOfDay: string;
  mood: string;
}

export interface LeaderResponse {
  url: string;
  asset_type: string;
  leader_name: string;
  leader_id: string;
  leader_ids?: string[];
  leader_names?: string[];
  seed: number;
  generation_mode: string;
  status?: string;
}

export interface LeaderSplashResult {
  url: string;
  leaderId: string;
  seed: number;
}

function leaderBody(params: LeaderParams): Record<string, unknown> {
  return {
    leader_name: params.leaderName,
    leader_description: params.leaderDescription,
    archetype: params.archetype,
    culture: params.culture,
    time_of_day: params.timeOfDay,
    mood: params.mood,
  };
}

function randomAssetSeed(): number {
  if (typeof crypto !== "undefined" && "getRandomValues" in crypto) {
    const values = new Uint32Array(1);
    crypto.getRandomValues(values);
    return values[0];
  }
  return Math.floor(Math.random() * 2 ** 32);
}

// Stage 1: cinematic 16:9 splash. Returns leader_id for chaining the profile.
export async function generateLeaderSplash(
  params: LeaderParams,
  signal?: AbortSignal,
): Promise<LeaderSplashResult> {
  const res = await postJson<LeaderResponse>(
    "/leader",
    { asset_type: "splash", ...leaderBody(params) },
    signal,
  );
  return { url: absoluteAssetUrl(res.url), leaderId: res.leader_id, seed: res.seed };
}

// GET /leader returns the catalog of leaders that have already been generated
// on the server. Useful as a fallback when fresh POST generation isn't
// available (e.g., upstream model errors) — we can still show real art.
export interface ExistingLeader {
  leader_id: string;
  leader_name: string;
  archetype: string;
  culture: string;
  splash_url: string | null;
  profile_url: string | null;
  action_urls?: string[];
}

export async function listLeaders(
  signal?: AbortSignal,
): Promise<ExistingLeader[]> {
  if (!assetApiConfigured()) return [];
  try {
    const res = await fetch(`${PROXY_PREFIX}/leader`, { signal });
    if (!res.ok) return [];
    return (await res.json()) as ExistingLeader[];
  } catch {
    return [];
  }
}

// Stage 2: square portrait, img2img off the splash for face consistency.
// Requires the leader_id returned by generateLeaderSplash.
export async function generateLeaderProfile(
  params: LeaderParams,
  leaderId: string,
  signal?: AbortSignal,
): Promise<string> {
  const res = await postJson<LeaderResponse>(
    "/leader",
    { asset_type: "profile", leader_id: leaderId, ...leaderBody(params) },
    signal,
  );
  return absoluteAssetUrl(res.url);
}

export type LeaderActionCategory =
  | "military"
  | "diplomatic"
  | "construction"
  | "scientific"
  | "cultural"
  | "exploration"
  | "crisis";

export interface LeaderActionResult {
  url: string;
  leaderId: string;
  leaderIds: string[];
  seed: number;
}

export async function generateLeaderAction(
  params: LeaderParams,
  leaderId: string,
  actionCategory: LeaderActionCategory,
  actionDescription: string,
  signal?: AbortSignal,
): Promise<LeaderActionResult> {
  const res = await postJson<LeaderResponse>(
    "/leader",
    {
      asset_type: "action",
      leader_id: leaderId,
      action_category: actionCategory,
      action_description: actionDescription,
      seed: randomAssetSeed(),
      ...leaderBody(params),
    },
    signal,
  );
  return {
    url: absoluteAssetUrl(res.url),
    leaderId: res.leader_id,
    leaderIds: res.leader_ids ?? [res.leader_id],
    seed: res.seed,
  };
}

export async function generateLeaderMultiAction(
  params: LeaderParams,
  leaderIds: string[],
  actionCategory: LeaderActionCategory,
  actionDescription: string,
  signal?: AbortSignal,
): Promise<LeaderActionResult> {
  const res = await postJson<LeaderResponse>(
    "/leader",
    {
      asset_type: "action",
      leader_ids: leaderIds,
      action_category: actionCategory,
      action_description: actionDescription,
      seed: randomAssetSeed(),
      ...leaderBody(params),
    },
    signal,
  );
  return {
    url: absoluteAssetUrl(res.url),
    leaderId: res.leader_id,
    leaderIds: res.leader_ids ?? leaderIds,
    seed: res.seed,
  };
}

// --- Structure (buildings) ---
export interface StructureParams {
  category: string; // fortification | production | housing | sacred
  style: string; // nordic_wooden | gothic | moorish | ...
  condition: string; // pristine | weathered | ruined | ...
  scale: string; // small | medium | large
  description: string; // 20-400 chars
}

interface StructureResponse {
  url: string;
  asset_id: string;
}

export async function generateStructure(
  params: StructureParams,
  signal?: AbortSignal,
): Promise<string> {
  const res = await postJson<StructureResponse>("/structure", params, signal);
  return absoluteAssetUrl(res.url);
}

// --- Unit sprites ---
export type ApiUnitType = "archer" | "scout" | "settler" | "warrior";

interface UnitResponse {
  url: string; // canonical south-facing sprite
  unit_id: string;
  unit_type: string;
}

// All unit sprites are south-facing (front view) — the canonical direction
// for top-down characters. The API dropped the `direction` field after every
// sprite became single-facing by design.
export async function generateUnit(
  unitType: ApiUnitType,
  description: string,
  signal?: AbortSignal,
): Promise<string> {
  const res = await postJson<UnitResponse>(
    "/unit",
    { unit_type: unitType, description },
    signal,
  );
  return absoluteAssetUrl(res.url);
}

// --- Terrain elevation features (hills, cliffs) layered on top of tiles ---
export interface TerrainParams {
  category: string; // hill | slope | cliff | ridge | depression
  scale: string; // low | medium | high
  material: string; // earthen | sandy | rocky | snowy | muddy
  description: string; // 20-400 chars
}

interface TerrainResponse {
  url: string;
  asset_id: string;
}

export async function generateTerrainFeature(
  params: TerrainParams,
  signal?: AbortSignal,
): Promise<string> {
  const res = await postJson<TerrainResponse>("/terrain", params, signal);
  return absoluteAssetUrl(res.url);
}

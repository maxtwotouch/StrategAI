// Grid coordinate math for an 8-directional square grid.
// The module name is retained for historical reasons; `q` is x and `r` is y.

export type Hex = { q: number; r: number };

export const TILE_SIZE = 28;
// Alias retained so other files can import either name.
export const HEX_SIZE = TILE_SIZE;

export function hexToPixel(
  h: Hex,
  size = TILE_SIZE,
): { x: number; y: number } {
  return { x: h.q * size, y: h.r * size };
}

export function tileCorners(
  cx: number,
  cy: number,
  size = TILE_SIZE,
): { x: number; y: number }[] {
  const half = size / 2;
  return [
    { x: cx - half, y: cy - half },
    { x: cx + half, y: cy - half },
    { x: cx + half, y: cy + half },
    { x: cx - half, y: cy + half },
  ];
}

// Kept for any stale callers; forwards to tileCorners.
export const hexCorners = tileCorners;

export function hexDistance(a: Hex, b: Hex): number {
  return Math.max(Math.abs(a.q - b.q), Math.abs(a.r - b.r));
}

export function tileKey(q: number, r: number): string {
  return `${q},${r}`;
}

export const TERRAIN_COLORS: Record<string, string> = {
  ocean: "#13243a",
  coast: "#2f5678",
  grassland: "#4f7a2a",
  plains: "#b59750",
  forest: "#274820",
  hills: "#7a6338",
  mountain: "#3f372c",
  desert: "#d0b061",
  tundra: "#9ba196",
  snow: "#d7dee1",
  lake: "#3b6f97",
  savanna: "#a88a2f",
  taiga: "#334d3d",
};

export const TERRAIN_STROKE: Record<string, string> = {
  ocean: "#0c1a2d",
  coast: "#224363",
  grassland: "#355c16",
  plains: "#846632",
  forest: "#152d13",
  hills: "#5a4324",
  mountain: "#2b2620",
  desert: "#9f8136",
  tundra: "#7b8276",
  snow: "#a9b3b9",
  lake: "#274e6e",
  savanna: "#7a621a",
  taiga: "#223328",
};

// Warm gold + muted faction tones to match the dark, painterly mockup.
export const CIV_COLORS = ["#d4a443", "#5a8cc4", "#b05a4a", "#7e6ac4"];

export const UNIT_GLYPH: Record<string, string> = {
  warrior: "⚔",
  settler: "⌂",
  scout: "◉",
};

export const RESOURCE_GLYPH: Record<string, string> = {
  wheat: "🌾",
  cattle: "🐂",
  fish: "🐟",
  iron: "⚒",
  horses: "🐎",
  coal: "▮",
  gems: "◆",
  silk: "❀",
  spices: "✦",
};

export const RESOURCE_LABEL: Record<string, string> = {
  wheat: "Wheat",
  cattle: "Cattle",
  fish: "Fish",
  iron: "Iron",
  horses: "Horses",
  coal: "Coal",
  gems: "Gems",
  silk: "Silk",
  spices: "Spices",
};

export const FEATURE_GLYPH: Record<string, string> = {
  forest: "♣",
  jungle: "❦",
  marsh: "≈",
  oasis: "❂",
};

export const FEATURE_LABEL: Record<string, string> = {
  forest: "Forest",
  jungle: "Jungle",
  marsh: "Marsh",
  oasis: "Oasis",
};

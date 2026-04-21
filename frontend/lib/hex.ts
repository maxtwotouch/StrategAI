export type Hex = { q: number; r: number };

export const HEX_SIZE = 34;

export function hexToPixel(h: Hex, size = HEX_SIZE): { x: number; y: number } {
  const x = size * Math.sqrt(3) * (h.q + h.r / 2);
  const y = size * (3 / 2) * h.r;
  return { x, y };
}

export function hexCorners(
  cx: number,
  cy: number,
  size = HEX_SIZE,
): { x: number; y: number }[] {
  const corners: { x: number; y: number }[] = [];
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 180) * (60 * i - 30); // pointy-top
    corners.push({
      x: cx + size * Math.cos(angle),
      y: cy + size * Math.sin(angle),
    });
  }
  return corners;
}

export function hexPolygonPoints(cx: number, cy: number, size = HEX_SIZE): string {
  return hexCorners(cx, cy, size)
    .map((c) => `${c.x.toFixed(2)},${c.y.toFixed(2)}`)
    .join(" ");
}

export function hexDistance(a: Hex, b: Hex): number {
  const dq = a.q - b.q;
  const dr = a.r - b.r;
  const ds = -dq - dr;
  return (Math.abs(dq) + Math.abs(dr) + Math.abs(ds)) / 2;
}

export function tileKey(q: number, r: number): string {
  return `${q},${r}`;
}

// Painterly atlas palette — more saturated, more contrast between terrains.
export const TERRAIN_COLORS: Record<string, string> = {
  ocean: "#1b3a5b",
  coast: "#3f7aa8",
  grassland: "#6fa539",
  plains: "#d2b463",
  forest: "#2f5a2b",
  hills: "#8a7147",
  mountain: "#564a3a",
  desert: "#e8c879",
  tundra: "#bfc4b8",
  snow: "#ecf2f5",
  lake: "#4a87b9",
  savanna: "#c9a946",
  taiga: "#3d5a4a",
};

export const TERRAIN_STROKE: Record<string, string> = {
  ocean: "#0f243d",
  coast: "#1f4a72",
  grassland: "#456a23",
  plains: "#9a7f3a",
  forest: "#1d3c1b",
  hills: "#5e4d30",
  mountain: "#39312a",
  desert: "#b29548",
  tundra: "#8d9385",
  snow: "#bcc7cc",
  lake: "#2a5d83",
  savanna: "#967d2c",
  taiga: "#28403a",
};

export const CIV_COLORS = ["#e05a4a", "#4a90e2", "#a855f7", "#f59e0b"];

// Text-glyph fallbacks until proper sprite assets land.
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

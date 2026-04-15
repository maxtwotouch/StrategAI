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

// Natural Civilization-inspired palette.
export const TERRAIN_COLORS: Record<string, string> = {
  ocean: "#1e3a5f",
  coast: "#3a6d9e",
  grassland: "#6a9c3a",
  plains: "#c4a95b",
  forest: "#2f5a2b",
  hills: "#8a7147",
  mountain: "#4e4638",
  desert: "#e5c77a",
};

export const TERRAIN_STROKE: Record<string, string> = {
  ocean: "#14253d",
  coast: "#244a6d",
  grassland: "#486b27",
  plains: "#8a7538",
  forest: "#1d3c1b",
  hills: "#5e4d30",
  mountain: "#33302a",
  desert: "#b29550",
};

export const CIV_COLORS = ["#e05a4a", "#4a90e2", "#a855f7", "#f59e0b"];

export const UNIT_GLYPH: Record<string, string> = {
  warrior: "⚔",
  settler: "⌂",
  scout: "◉",
};

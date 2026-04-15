"use client";

import { useState } from "react";

import { CityDTO, GameStateDTO, UnitDTO } from "@/lib/api";
import {
  CIV_COLORS,
  HEX_SIZE,
  TERRAIN_COLORS,
  TERRAIN_STROKE,
  UNIT_GLYPH,
  hexPolygonPoints,
  hexToPixel,
} from "@/lib/hex";

interface HexMapProps {
  state: GameStateDTO;
  selectedUnitId: number | null;
  reachable: Set<string>;
  onTileClick?: (q: number, r: number) => void;
  onUnitClick?: (unit: UnitDTO) => void;
}

function tileKey(q: number, r: number): string {
  return `${q},${r}`;
}

export function HexMap({
  state,
  selectedUnitId,
  reachable,
  onTileClick,
  onUnitClick,
}: HexMapProps) {
  const [hover, setHover] = useState<string | null>(null);

  const pixels = state.tiles.map((t) => ({
    tile: t,
    ...hexToPixel({ q: t.q, r: t.r }),
  }));

  if (pixels.length === 0) return null;

  const xs = pixels.map((p) => p.x);
  const ys = pixels.map((p) => p.y);
  const pad = HEX_SIZE * 1.8;
  const minX = Math.min(...xs) - pad;
  const minY = Math.min(...ys) - pad;
  const width = Math.max(...xs) - minX + pad;
  const height = Math.max(...ys) - minY + pad;

  const unitAt = new Map<string, UnitDTO>();
  for (const u of state.units) unitAt.set(tileKey(u.q, u.r), u);
  const cityAt = new Map<string, CityDTO>();
  for (const c of state.cities) cityAt.set(tileKey(c.q, c.r), c);

  return (
    <svg
      viewBox={`${minX} ${minY} ${width} ${height}`}
      width="100%"
      height="100%"
      style={{
        maxHeight: "82vh",
        display: "block",
        background:
          "radial-gradient(ellipse at center, #152135 0%, #0a0e1a 85%)",
      }}
    >
      <defs>
        <filter id="tile-shadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="1.5" stdDeviation="0.8" floodOpacity="0.35" />
        </filter>
        <filter id="unit-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="drop" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="2" stdDeviation="1.6" floodOpacity="0.6" />
        </filter>
        <radialGradient id="tile-sheen" cx="50%" cy="30%" r="70%">
          <stop offset="0%" stopColor="rgba(255,255,255,0.12)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </radialGradient>
      </defs>

      {pixels.map(({ tile, x, y }) => {
        const key = tileKey(tile.q, tile.r);
        const fill = TERRAIN_COLORS[tile.terrain] ?? "#888";
        const stroke = TERRAIN_STROKE[tile.terrain] ?? "#444";
        const isHover = hover === key;
        const isReachable = reachable.has(key);
        return (
          <g
            key={key}
            onMouseEnter={() => setHover(key)}
            onMouseLeave={() => setHover((h) => (h === key ? null : h))}
          >
            <polygon
              points={hexPolygonPoints(x, y)}
              fill={fill}
              stroke={stroke}
              strokeWidth={1.2}
              filter="url(#tile-shadow)"
              style={{ cursor: onTileClick ? "pointer" : "default" }}
              onClick={() => onTileClick?.(tile.q, tile.r)}
            />
            <polygon
              points={hexPolygonPoints(x, y)}
              fill="url(#tile-sheen)"
              pointerEvents="none"
            />
            {isReachable && (
              <polygon
                points={hexPolygonPoints(x, y)}
                fill="rgba(242, 178, 74, 0.18)"
                stroke="rgba(242, 178, 74, 0.8)"
                strokeWidth={2}
                strokeDasharray="3 3"
                pointerEvents="none"
              />
            )}
            {isHover && (
              <polygon
                points={hexPolygonPoints(x, y)}
                fill="none"
                stroke="rgba(255,255,255,0.5)"
                strokeWidth={2}
                pointerEvents="none"
              />
            )}
          </g>
        );
      })}

      {pixels.map(({ tile, x, y }) => {
        const key = tileKey(tile.q, tile.r);
        const city = cityAt.get(key);
        const unit = unitAt.get(key);
        const isSelected = unit && unit.id === selectedUnitId;
        return (
          <g key={`ent-${key}`}>
            {city && (
              <g
                filter="url(#drop)"
                style={{ cursor: onTileClick ? "pointer" : "default" }}
                onClick={() => onTileClick?.(tile.q, tile.r)}
              >
                <rect
                  x={x - 13}
                  y={y - 12}
                  width={26}
                  height={18}
                  rx={2}
                  fill={CIV_COLORS[city.owner % CIV_COLORS.length]}
                  stroke="#0b1220"
                  strokeWidth={1.2}
                />
                <rect
                  x={x - 13}
                  y={y - 12}
                  width={26}
                  height={5}
                  fill="rgba(255,255,255,0.25)"
                />
                <polygon
                  points={`${x - 13},${y - 12} ${x - 9},${y - 16} ${x - 5},${y - 12}`}
                  fill={CIV_COLORS[city.owner % CIV_COLORS.length]}
                  stroke="#0b1220"
                  strokeWidth={1}
                />
                <polygon
                  points={`${x - 2},${y - 12} ${x + 2},${y - 16} ${x + 6},${y - 12}`}
                  fill={CIV_COLORS[city.owner % CIV_COLORS.length]}
                  stroke="#0b1220"
                  strokeWidth={1}
                />
                <polygon
                  points={`${x + 9},${y - 12} ${x + 13},${y - 16} ${x + 13},${y - 12}`}
                  fill={CIV_COLORS[city.owner % CIV_COLORS.length]}
                  stroke="#0b1220"
                  strokeWidth={1}
                />
                <text
                  x={x}
                  y={y + 24}
                  textAnchor="middle"
                  fontSize={10}
                  fontWeight={700}
                  fill="#e8ecf4"
                  stroke="#0b1220"
                  strokeWidth={3}
                  paintOrder="stroke"
                  style={{ letterSpacing: 0.3 }}
                  pointerEvents="none"
                >
                  {city.name}
                </text>
              </g>
            )}
            {unit && (
              <g
                filter={isSelected ? "url(#unit-glow)" : "url(#drop)"}
                style={{ cursor: "pointer" }}
                onClick={(e) => {
                  e.stopPropagation();
                  onUnitClick?.(unit);
                }}
              >
                {isSelected && (
                  <circle
                    cx={x}
                    cy={y}
                    r={15}
                    fill="none"
                    stroke="#f2b24a"
                    strokeWidth={2}
                    strokeDasharray="3 2"
                    style={{ animation: "pulse 1.8s ease-in-out infinite" }}
                  />
                )}
                <circle
                  cx={x}
                  cy={y}
                  r={11}
                  fill={CIV_COLORS[unit.owner % CIV_COLORS.length]}
                  stroke="#0b1220"
                  strokeWidth={1.5}
                />
                <circle
                  cx={x - 3}
                  cy={y - 3}
                  r={3.5}
                  fill="rgba(255,255,255,0.3)"
                />
                <text
                  x={x}
                  y={y + 4}
                  textAnchor="middle"
                  fontSize={12}
                  fontWeight={700}
                  fill="#fff"
                  pointerEvents="none"
                  style={{ userSelect: "none" }}
                >
                  {UNIT_GLYPH[unit.type] ?? unit.type[0].toUpperCase()}
                </text>
              </g>
            )}
          </g>
        );
      })}
    </svg>
  );
}

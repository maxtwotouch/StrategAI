"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { CityDTO, GameStateDTO, UnitDTO } from "@/lib/api";
import {
  CIV_COLORS,
  FEATURE_GLYPH,
  HEX_SIZE,
  Hex,
  RESOURCE_GLYPH,
  TERRAIN_COLORS,
  TERRAIN_STROKE,
  UNIT_GLYPH,
  hexPolygonPoints,
  hexToPixel,
  tileKey,
} from "@/lib/hex";

interface HexMapProps {
  state: GameStateDTO;
  selectedUnitId: number | null;
  reachable: Set<string>;
  highlightedTileKey?: string | null;
  focusHex?: Hex | null;
  humanCivId?: number | null;
  visibleTiles: Set<string>;
  onTileClick?: (q: number, r: number) => void;
  onTileHover?: (q: number, r: number) => void;
  onUnitClick?: (unit: UnitDTO) => void;
}

type Camera = {
  x: number;
  y: number;
  width: number;
  height: number;
};

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function HexMap({
  state,
  selectedUnitId,
  reachable,
  highlightedTileKey,
  focusHex,
  humanCivId,
  visibleTiles,
  onTileClick,
  onTileHover,
  onUnitClick,
}: HexMapProps) {
  const [hover, setHover] = useState<string | null>(null);
  const [camera, setCamera] = useState<Camera | null>(null);
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    camera: Camera;
  } | null>(null);

  const pixels = useMemo(
    () =>
      state.tiles.map((t) => ({
        tile: t,
        ...hexToPixel({ q: t.q, r: t.r }),
      })),
    [state.tiles],
  );

  const unitAt = useMemo(() => {
    const map = new Map<string, UnitDTO>();
    for (const u of state.units) map.set(tileKey(u.q, u.r), u);
    return map;
  }, [state.units]);

  const cityAt = useMemo(() => {
    const map = new Map<string, CityDTO>();
    for (const c of state.cities) map.set(tileKey(c.q, c.r), c);
    return map;
  }, [state.cities]);

  const bounds = useMemo(() => {
    if (pixels.length === 0) return null;
    const xs = pixels.map((p) => p.x);
    const ys = pixels.map((p) => p.y);
    const pad = HEX_SIZE * 2.5;
    const minX = Math.min(...xs) - pad;
    const minY = Math.min(...ys) - pad;
    const width = Math.max(...xs) - minX + pad;
    const height = Math.max(...ys) - minY + pad;
    return { minX, minY, width, height };
  }, [pixels]);

  const focusPoint = useMemo(() => {
    if (focusHex) return hexToPixel(focusHex);
    const firstHumanCity =
      humanCivId !== null && humanCivId !== undefined
        ? state.cities.find((city) => city.owner === humanCivId)
        : null;
    if (firstHumanCity) return hexToPixel({ q: firstHumanCity.q, r: firstHumanCity.r });
    const firstHumanUnit =
      humanCivId !== null && humanCivId !== undefined
        ? state.units.find((unit) => unit.owner === humanCivId)
        : null;
    if (firstHumanUnit) return hexToPixel({ q: firstHumanUnit.q, r: firstHumanUnit.r });
    return { x: 0, y: 0 };
  }, [focusHex, humanCivId, state.cities, state.units]);

  const baseCamera = useMemo(() => {
    if (!bounds) return null;
    const fullWidth = bounds.width;
    const fullHeight = bounds.height;
    const zoom = 0.55;
    const width = fullWidth * zoom;
    const height = fullHeight * zoom;
    const x = clamp(
      focusPoint.x - width / 2,
      bounds.minX,
      bounds.minX + bounds.width - width,
    );
    const y = clamp(
      focusPoint.y - height / 2,
      bounds.minY,
      bounds.minY + bounds.height - height,
    );
    return { x, y, width, height };
  }, [bounds, focusPoint]);

  useEffect(() => {
    if (baseCamera) {
      setCamera(baseCamera);
    }
  }, [baseCamera, state.id, focusPoint.x, focusPoint.y]);

  if (pixels.length === 0 || !bounds || !camera) return null;

  const minViewWidth = bounds.width * 0.18;
  const maxViewWidth = bounds.width * 1.05;
  const minViewHeight = bounds.height * 0.18;
  const maxViewHeight = bounds.height * 1.05;

  const zoomBy = (factor: number) => {
    setCamera((current) => {
      if (!current) return current;
      const nextWidth = clamp(current.width * factor, minViewWidth, maxViewWidth);
      const nextHeight = clamp(current.height * factor, minViewHeight, maxViewHeight);
      const centerX = current.x + current.width / 2;
      const centerY = current.y + current.height / 2;
      return {
        x: clamp(centerX - nextWidth / 2, bounds.minX, bounds.minX + bounds.width - nextWidth),
        y: clamp(centerY - nextHeight / 2, bounds.minY, bounds.minY + bounds.height - nextHeight),
        width: nextWidth,
        height: nextHeight,
      };
    });
  };

  const recenter = () => {
    if (baseCamera) setCamera(baseCamera);
  };

  return (
    <div className="map-shell">
      <div className="map-hud">
        <div className="map-chip">{dragging ? "Dragging map" : "Drag to pan"}</div>
        <div className="map-chip">Wheel to zoom</div>
        <div className="map-controls">
          <button type="button" onClick={() => zoomBy(0.82)}>
            +
          </button>
          <button type="button" onClick={() => zoomBy(1.22)}>
            -
          </button>
          <button type="button" onClick={recenter}>
            Recenter
          </button>
        </div>
      </div>

      <svg
        viewBox={`${camera.x} ${camera.y} ${camera.width} ${camera.height}`}
        width="100%"
        height="100%"
        style={{
          width: "100%",
          height: "100%",
          display: "block",
          background:
            "radial-gradient(circle at 30% 25%, #2c4a63 0%, #122638 38%, #050d16 100%)",
          cursor: dragging ? "grabbing" : "grab",
        }}
        onWheel={(event) => {
          event.preventDefault();
          zoomBy(event.deltaY > 0 ? 1.1 : 0.9);
        }}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          dragRef.current = {
            pointerId: event.pointerId,
            startX: event.clientX,
            startY: event.clientY,
            camera,
          };
          setDragging(true);
        }}
        onPointerMove={(event) => {
          if (!dragRef.current || dragRef.current.pointerId !== event.pointerId) return;
          const dx = event.clientX - dragRef.current.startX;
          const dy = event.clientY - dragRef.current.startY;
          const scaleX = dragRef.current.camera.width / 1100;
          const scaleY = dragRef.current.camera.height / 760;
          const nextX = clamp(
            dragRef.current.camera.x - dx * scaleX,
            bounds.minX,
            bounds.minX + bounds.width - dragRef.current.camera.width,
          );
          const nextY = clamp(
            dragRef.current.camera.y - dy * scaleY,
            bounds.minY,
            bounds.minY + bounds.height - dragRef.current.camera.height,
          );
          setCamera({ ...dragRef.current.camera, x: nextX, y: nextY });
        }}
        onPointerUp={(event) => {
          if (dragRef.current?.pointerId === event.pointerId) {
            dragRef.current = null;
            setDragging(false);
          }
        }}
        onPointerLeave={() => {
          dragRef.current = null;
          setDragging(false);
        }}
      >
        <defs>
          <filter id="tile-shadow" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="1.8" stdDeviation="1.2" floodOpacity="0.33" />
          </filter>
          <filter id="unit-glow" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="drop" x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="2" stdDeviation="1.8" floodOpacity="0.5" />
          </filter>
          <radialGradient id="tile-sheen" cx="50%" cy="30%" r="70%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.14)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </radialGradient>
          <radialGradient id="ocean-glow" cx="50%" cy="50%" r="65%">
            <stop offset="0%" stopColor="rgba(139, 195, 235, 0.18)" />
            <stop offset="100%" stopColor="rgba(139, 195, 235, 0)" />
          </radialGradient>
        </defs>

        <rect
          x={bounds.minX - 600}
          y={bounds.minY - 600}
          width={bounds.width + 1200}
          height={bounds.height + 1200}
          fill="url(#ocean-glow)"
          pointerEvents="none"
        />

        {pixels.map(({ tile, x, y }) => {
          const key = tileKey(tile.q, tile.r);
          const fill = TERRAIN_COLORS[tile.terrain] ?? "#888";
          const stroke = TERRAIN_STROKE[tile.terrain] ?? "#444";
          const isHover = hover === key;
          const isReachable = reachable.has(key);
          const isHighlighted = highlightedTileKey === key;
          const occupant = unitAt.get(key);
          const city = cityAt.get(key);
          const isHumanOwned =
            humanCivId !== null &&
            humanCivId !== undefined &&
            ((occupant && occupant.owner === humanCivId) || (city && city.owner === humanCivId));
          const isVisible = visibleTiles.size === 0 || visibleTiles.has(key);

          return (
            <g
              key={key}
              onMouseEnter={() => {
                setHover(key);
                onTileHover?.(tile.q, tile.r);
              }}
              onMouseLeave={() => setHover((current) => (current === key ? null : current))}
            >
              <polygon
                points={hexPolygonPoints(x, y)}
                fill={fill}
                stroke={stroke}
                strokeWidth={1.15}
                filter="url(#tile-shadow)"
                style={{ cursor: onTileClick ? "pointer" : "default" }}
                onClick={() => onTileClick?.(tile.q, tile.r)}
              />
              <polygon
                points={hexPolygonPoints(x, y)}
                fill="url(#tile-sheen)"
                pointerEvents="none"
              />
              {tile.terrain === "coast" && (
                <polygon
                  points={hexPolygonPoints(x, y)}
                  fill="none"
                  stroke="rgba(221, 241, 255, 0.55)"
                  strokeWidth={1.3}
                  pointerEvents="none"
                />
              )}
              {tile.river && (
                <text
                  x={x - 12}
                  y={y + 14}
                  fontSize={13}
                  fill="rgba(160, 220, 255, 0.85)"
                  stroke="rgba(20, 40, 65, 0.6)"
                  strokeWidth={0.6}
                  paintOrder="stroke"
                  pointerEvents="none"
                >
                  ≈
                </text>
              )}
              {tile.feature && (
                <text
                  x={x + 9}
                  y={y - 6}
                  fontSize={12}
                  fill="rgba(20, 28, 16, 0.78)"
                  pointerEvents="none"
                >
                  {FEATURE_GLYPH[tile.feature] ?? "•"}
                </text>
              )}
              {tile.resource && (
                <g pointerEvents="none">
                  <circle
                    cx={x + 10}
                    cy={y + 9}
                    r={7}
                    fill="rgba(255, 246, 218, 0.92)"
                    stroke="rgba(80, 55, 20, 0.65)"
                    strokeWidth={0.8}
                  />
                  <text
                    x={x + 10}
                    y={y + 13}
                    textAnchor="middle"
                    fontSize={9}
                    fill="#3a2a10"
                  >
                    {RESOURCE_GLYPH[tile.resource] ?? "?"}
                  </text>
                </g>
              )}
              {isHumanOwned && (
                <polygon
                  points={hexPolygonPoints(x, y)}
                  fill="rgba(255,255,255,0.02)"
                  stroke="rgba(255, 244, 196, 0.6)"
                  strokeWidth={1.8}
                  pointerEvents="none"
                />
              )}
              {isReachable && (
                <polygon
                  points={hexPolygonPoints(x, y)}
                  fill="rgba(242, 178, 74, 0.18)"
                  stroke="rgba(242, 178, 74, 0.82)"
                  strokeWidth={2}
                  strokeDasharray="3 3"
                  pointerEvents="none"
                />
              )}
              {!isVisible && (
                <polygon
                  points={hexPolygonPoints(x, y)}
                  fill="rgba(8, 14, 22, 0.62)"
                  stroke="rgba(8, 14, 22, 0.45)"
                  strokeWidth={0.6}
                  pointerEvents="none"
                />
              )}
              {isHover && (
                <polygon
                  points={hexPolygonPoints(x, y)}
                  fill="none"
                  stroke="rgba(255,255,255,0.62)"
                  strokeWidth={2}
                  pointerEvents="none"
                />
              )}
              {isHighlighted && (
                <polygon
                  points={hexPolygonPoints(x, y)}
                  fill="none"
                  stroke="rgba(125, 211, 252, 0.95)"
                  strokeWidth={2.4}
                  pointerEvents="none"
                />
              )}
            </g>
          );
        })}

        {pixels.map(({ tile, x, y }) => {
          const key = tileKey(tile.q, tile.r);
          const isVisible = visibleTiles.size === 0 || visibleTiles.has(key);
          if (!isVisible) return null;
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
                    x={x - 14}
                    y={y - 12}
                    width={28}
                    height={18}
                    rx={2}
                    fill={CIV_COLORS[city.owner % CIV_COLORS.length]}
                    stroke="#10151d"
                    strokeWidth={1.2}
                  />
                  <rect
                    x={x - 14}
                    y={y - 12}
                    width={28}
                    height={5}
                    fill="rgba(255,255,255,0.25)"
                  />
                  <polygon
                    points={`${x - 14},${y - 12} ${x - 9},${y - 17} ${x - 4},${y - 12}`}
                    fill={CIV_COLORS[city.owner % CIV_COLORS.length]}
                    stroke="#10151d"
                    strokeWidth={1}
                  />
                  <polygon
                    points={`${x - 1},${y - 12} ${x + 3},${y - 17} ${x + 8},${y - 12}`}
                    fill={CIV_COLORS[city.owner % CIV_COLORS.length]}
                    stroke="#10151d"
                    strokeWidth={1}
                  />
                  <text
                    x={x}
                    y={y + 25}
                    textAnchor="middle"
                    fontSize={10}
                    fontWeight={700}
                    fill="#eef4f8"
                    stroke="#121920"
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
                  onClick={(event) => {
                    event.stopPropagation();
                    onUnitClick?.(unit);
                  }}
                >
                  {isSelected && (
                    <circle
                      cx={x}
                      cy={y}
                      r={16}
                      fill="none"
                      stroke="#f2b24a"
                      strokeWidth={2.2}
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
                    strokeWidth={1.6}
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
    </div>
  );
}

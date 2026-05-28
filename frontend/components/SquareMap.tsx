"use client";

import React, {
  PointerEvent as ReactPointerEvent,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { StrategyMapProps } from "@/components/mapTypes";
import { CityDTO, UnitDTO } from "@/lib/api";
import {
  CIV_COLORS,
  FEATURE_GLYPH,
  IMPROVEMENT_GLYPH,
  RESOURCE_GLYPH,
  TERRAIN_COLORS,
  TILE_SIZE,
  UNIT_GLYPH,
  hexToPixel,
  tileKey,
} from "@/lib/hex";

type Camera = { x: number; y: number; width: number; height: number };
type StageSize = { width: number; height: number };

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function clampCameraStart(start: number, min: number, span: number, view: number): number {
  if (view >= span) return min - (view - span) / 2;
  return clamp(start, min, min + span - view);
}

function initialScale(radius: number): number {
  return clamp(1.5 - radius * 0.018, 0.6, 1.8);
}

function shade(hex: string, amount: number): string {
  const raw = hex.replace("#", "");
  const num = Number.parseInt(raw, 16);
  const r = clamp(((num >> 16) & 0xff) + amount, 0, 255);
  const g = clamp(((num >> 8) & 0xff) + amount, 0, 255);
  const b = clamp((num & 0xff) + amount, 0, 255);
  return `rgb(${r}, ${g}, ${b})`;
}

function deterministicJitter(q: number, r: number): number {
  const h = Math.sin(q * 928.12 + r * 71.91) * 43758.5453;
  return h - Math.floor(h);
}

function buildCamera(
  bounds: { minX: number; minY: number; width: number; height: number },
  size: StageSize,
  scale: number,
  focusPoint: { x: number; y: number },
): Camera {
  const fitScale = Math.max(size.width / bounds.width, size.height / bounds.height);
  const effectiveScale = Math.max(scale, fitScale * 1.08);
  const width = size.width / effectiveScale;
  const height = size.height / effectiveScale;
  const x = clampCameraStart(
    focusPoint.x - width / 2,
    bounds.minX,
    bounds.width,
    width,
  );
  const y = clampCameraStart(
    focusPoint.y - height / 2,
    bounds.minY,
    bounds.height,
    height,
  );
  return { x, y, width, height };
}

export function SquareMap(props: StrategyMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [stageSize, setStageSize] = useState<StageSize>({
    width: 1100,
    height: 760,
  });
  const [camera, setCamera] = useState<Camera | null>(null);
  const [dragging, setDragging] = useState(false);
  const [hover, setHover] = useState<string | null>(null);

  // Drag state lives in refs so document-level listeners see the latest values.
  const dragRef = useRef<{
    startX: number;
    startY: number;
    lastX: number;
    lastY: number;
    moved: boolean;
  } | null>(null);
  const stageSizeRef = useRef(stageSize);
  const cameraRef = useRef<Camera | null>(null);
  const boundsRef = useRef<{
    minX: number;
    minY: number;
    width: number;
    height: number;
  } | null>(null);
  const panDeltaRef = useRef({ dx: 0, dy: 0 });
  const panFrameRef = useRef<number | null>(null);
  const justDraggedRef = useRef(false);
  const userCameraDirtyRef = useRef(false);
  const homeFocusRef = useRef<{ x: number; y: number } | null>(null);

  const applyViewBox = (next: Camera | null) => {
    const node = svgRef.current;
    if (!node || !next) return;
    node.setAttribute("viewBox", `${next.x} ${next.y} ${next.width} ${next.height}`);
  };

  const pixels = useMemo(
    () =>
      props.state.tiles.map((tile) => ({
        tile,
        ...hexToPixel({ q: tile.q, r: tile.r }),
      })),
    [props.state.tiles],
  );

  const unitAt = useMemo(() => {
    const map = new Map<string, UnitDTO>();
    for (const unit of props.state.units) map.set(tileKey(unit.q, unit.r), unit);
    return map;
  }, [props.state.units]);

  const cityAt = useMemo(() => {
    const map = new Map<string, CityDTO>();
    for (const city of props.state.cities) map.set(tileKey(city.q, city.r), city);
    return map;
  }, [props.state.cities]);

  // Owner color per tile derived from authoritative tile_owner map.
  // tile_owner maps tile → city_id; we look the city up to find its civ owner.
  const tileOwnerByCiv = useMemo(() => {
    const byCiv = new Map<number, Set<string>>();
    const cityToCiv = new Map<number, number>();
    for (const city of props.state.cities) cityToCiv.set(city.id, city.owner);
    for (const entry of props.state.tile_owner ?? []) {
      const civId = cityToCiv.get(entry.city_id);
      if (civId === undefined) continue;
      const key = tileKey(entry.q, entry.r);
      let set = byCiv.get(civId);
      if (!set) {
        set = new Set<string>();
        byCiv.set(civId, set);
      }
      set.add(key);
    }
    return byCiv;
  }, [props.state.cities, props.state.tile_owner]);

  const humanOwnedKeys = useMemo(() => {
    if (props.humanCivId === null || props.humanCivId === undefined) {
      return new Set<string>();
    }
    return tileOwnerByCiv.get(props.humanCivId) ?? new Set<string>();
  }, [tileOwnerByCiv, props.humanCivId]);

  // Worked-tile highlight when the selected unit is on a city center.
  const workedHighlight = useMemo(() => {
    const keys = new Set<string>();
    if (props.selectedUnitId === null || props.selectedUnitId === undefined) {
      return keys;
    }
    const selected = props.state.units.find((u) => u.id === props.selectedUnitId);
    if (!selected) return keys;
    const city = props.state.cities.find(
      (c) => c.q === selected.q && c.r === selected.r && c.owner === selected.owner,
    );
    if (!city) return keys;
    for (const t of city.worked_tiles ?? []) keys.add(tileKey(t.q, t.r));
    return keys;
  }, [props.selectedUnitId, props.state.units, props.state.cities]);

  const bounds = useMemo(() => {
    if (pixels.length === 0) return null;
    const pad = TILE_SIZE * 2;
    const xs = pixels.map((p) => p.x);
    const ys = pixels.map((p) => p.y);
    const minX = Math.min(...xs) - pad;
    const minY = Math.min(...ys) - pad;
    const width = Math.max(...xs) - minX + pad;
    const height = Math.max(...ys) - minY + pad;
    return { minX, minY, width, height };
  }, [pixels]);

  useEffect(() => {
    stageSizeRef.current = stageSize;
  }, [stageSize]);

  useEffect(() => {
    boundsRef.current = bounds;
  }, [bounds]);

  useEffect(() => {
    cameraRef.current = camera;
    applyViewBox(camera);
  }, [camera]);

  // After every render, reassert the viewBox from the live ref. Without this,
  // a parent re-render (e.g., hover state updates) during a drag would snap
  // the SVG back to the pre-drag camera state in React, causing visible jitter.
  useLayoutEffect(() => {
    if (cameraRef.current) applyViewBox(cameraRef.current);
  });

  const focusPoint = useMemo(() => {
    if (props.focusHex) return hexToPixel(props.focusHex);
    const firstCity =
      props.humanCivId !== null && props.humanCivId !== undefined
        ? props.state.cities.find((c) => c.owner === props.humanCivId)
        : null;
    if (firstCity) return hexToPixel({ q: firstCity.q, r: firstCity.r });
    const firstUnit =
      props.humanCivId !== null && props.humanCivId !== undefined
        ? props.state.units.find((u) => u.owner === props.humanCivId)
        : null;
    if (firstUnit) return hexToPixel({ q: firstUnit.q, r: firstUnit.r });
    return { x: 0, y: 0 };
  }, [props.focusHex, props.humanCivId, props.state.cities, props.state.units]);

  useEffect(() => {
    userCameraDirtyRef.current = false;
    homeFocusRef.current = focusPoint;
  }, [props.state.id]);

  useEffect(() => {
    if (!bounds || !homeFocusRef.current || userCameraDirtyRef.current) return;
    const scale = initialScale(props.state.map_radius);
    setCamera(buildCamera(bounds, stageSize, scale, homeFocusRef.current));
  }, [bounds, props.state.map_radius, stageSize.height, stageSize.width]);

  // When the parent updates focusHex (e.g., a unit was selected), pan the
  // camera so the focused point is visible. Doesn't change zoom; if the
  // point is already in view, do nothing. Skipped while the user is
  // actively dragging.
  useEffect(() => {
    if (!props.focusHex || !bounds) return;
    const cam = cameraRef.current;
    if (!cam) return;
    if (dragRef.current?.moved) return;
    const target = hexToPixel(props.focusHex);
    const margin = TILE_SIZE * 1.5;
    const insideX =
      target.x >= cam.x + margin && target.x <= cam.x + cam.width - margin;
    const insideY =
      target.y >= cam.y + margin && target.y <= cam.y + cam.height - margin;
    if (insideX && insideY) return;
    const nextX = clampCameraStart(
      target.x - cam.width / 2,
      bounds.minX,
      bounds.width,
      cam.width,
    );
    const nextY = clampCameraStart(
      target.y - cam.height / 2,
      bounds.minY,
      bounds.height,
      cam.height,
    );
    setCamera({ ...cam, x: nextX, y: nextY });
  }, [props.focusHex?.q, props.focusHex?.r, bounds]);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      setStageSize({
        width: Math.max(320, Math.round(width)),
        height: Math.max(320, Math.round(height)),
      });
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  // Zoom around a fixed world anchor — keeps the pixel under the cursor put.
  const zoomAround = (factor: number, anchor?: { wx: number; wy: number }) => {
    userCameraDirtyRef.current = true;
    setCamera((current) => {
      const b = boundsRef.current;
      if (!current || !b) return current;
      const minW = b.width * 0.1;
      const maxW = b.width * 1.1;
      const minH = b.height * 0.1;
      const maxH = b.height * 1.1;
      const width = clamp(current.width * factor, minW, maxW);
      const height = clamp(current.height * factor, minH, maxH);
      const ax = anchor ? anchor.wx : current.x + current.width / 2;
      const ay = anchor ? anchor.wy : current.y + current.height / 2;
      const rx = (ax - current.x) / Math.max(current.width, 1e-6);
      const ry = (ay - current.y) / Math.max(current.height, 1e-6);
      const nx = ax - rx * width;
      const ny = ay - ry * height;
      return {
        x: clampCameraStart(nx, b.minX, b.width, width),
        y: clampCameraStart(ny, b.minY, b.height, height),
        width,
        height,
      };
    });
  };

  const zoomBy = (factor: number) => zoomAround(factor);

  const recenter = () => {
    if (!bounds) return;
    userCameraDirtyRef.current = false;
    homeFocusRef.current = focusPoint;
    setCamera(buildCamera(bounds, stageSize, initialScale(props.state.map_radius), focusPoint));
  };

  // Document-level drag — survives pointer leaving the SVG.
  // Pan is frame-synced so motion stays smooth even when pointer events burst.
  useEffect(() => {
    const flushPan = () => {
      panFrameRef.current = null;
      const drag = dragRef.current;
      const b = boundsRef.current;
      const cam = cameraRef.current;
      const { dx, dy } = panDeltaRef.current;
      if (!drag || !b || !cam || (dx === 0 && dy === 0)) return;

      panDeltaRef.current = { dx: 0, dy: 0 };

      const size = stageSizeRef.current;
      const sx = cam.width / Math.max(size.width, 1);
      const sy = cam.height / Math.max(size.height, 1);

      const nx = clamp(
        cam.x - dx * sx,
        b.minX,
        b.minX + Math.max(0, b.width - cam.width),
      );
      const ny = clamp(
        cam.y - dy * sy,
        b.minY,
        b.minY + Math.max(0, b.height - cam.height),
      );
      const next = { ...cam, x: nx, y: ny };
      cameraRef.current = next;
      applyViewBox(next);
    };

    const schedulePan = () => {
      if (panFrameRef.current !== null) return;
      panFrameRef.current = window.requestAnimationFrame(flushPan);
    };

    const handleMove = (event: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag) return;

      const totalDx = event.clientX - drag.startX;
      const totalDy = event.clientY - drag.startY;
      if (Math.abs(totalDx) > 5 || Math.abs(totalDy) > 5) {
        // Only mark as a real drag (and dirty the camera) after the pointer
        // has moved past a noise threshold.
        if (!drag.moved) {
          drag.moved = true;
          userCameraDirtyRef.current = true;
          setDragging(true);
        }
      }

      if (!drag.moved) return;

      const dx = event.clientX - drag.lastX;
      const dy = event.clientY - drag.lastY;
      drag.lastX = event.clientX;
      drag.lastY = event.clientY;
      panDeltaRef.current.dx += dx;
      panDeltaRef.current.dy += dy;
      schedulePan();
    };
    const handleUp = () => {
      const drag = dragRef.current;
      if (!drag) return;
      if (panFrameRef.current !== null) {
        window.cancelAnimationFrame(panFrameRef.current);
        panFrameRef.current = null;
        flushPan();
      }
      panDeltaRef.current = { dx: 0, dy: 0 };
      if (cameraRef.current) {
        setCamera(cameraRef.current);
      }
      if (drag.moved) {
        justDraggedRef.current = true;
        // Clear on the next microtask so the click handler that fires
        // immediately after pointerup can see it.
        setTimeout(() => {
          justDraggedRef.current = false;
        }, 0);
      }
      dragRef.current = null;
      setDragging(false);
    };
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    window.addEventListener("pointercancel", handleUp);
    return () => {
      if (panFrameRef.current !== null) {
        window.cancelAnimationFrame(panFrameRef.current);
        panFrameRef.current = null;
      }
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
      window.removeEventListener("pointercancel", handleUp);
    };
  }, []);

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || !camera || !bounds) return;
    // Don't mark camera dirty here — wait until actual drag movement is
    // detected so that simple clicks still allow auto-recentering on focus
    // changes (e.g., selecting a unit).
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      moved: false,
    };
  };

  // Native non-passive wheel listener → we can preventDefault to stop page
  // scroll, and compute a cursor-anchored zoom.
  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const onWheelNative = (event: WheelEvent) => {
      event.preventDefault();
      const cam = cameraRef.current;
      if (!cam) return;
      const rect = node.getBoundingClientRect();
      const px = (event.clientX - rect.left) / Math.max(rect.width, 1);
      const py = (event.clientY - rect.top) / Math.max(rect.height, 1);
      const wx = cam.x + px * cam.width;
      const wy = cam.y + py * cam.height;
      // Smooth exponential factor — tuned for trackpad + mouse wheel.
      const factor = Math.exp(event.deltaY * 0.0022);
      const clamped = clamp(factor, 0.5, 2);
      zoomAround(clamped, { wx, wy });
    };
    node.addEventListener("wheel", onWheelNative, { passive: false });
    return () => {
      node.removeEventListener("wheel", onWheelNative);
    };
  }, []);

  const handleTileClick = (q: number, r: number) => {
    if (justDraggedRef.current) return;
    const key = tileKey(q, r);
    const unit = unitAt.get(key);
    if (unit) {
      props.onUnitClick?.(unit);
      return;
    }
    props.onTileClick?.(q, r);
  };

  const viewBox = camera
    ? `${camera.x} ${camera.y} ${camera.width} ${camera.height}`
    : "0 0 1 1";

  const half = TILE_SIZE / 2;
  const strokeWidth = Math.max(0.8, TILE_SIZE * 0.07);
  const borderWidth = Math.max(1.2, TILE_SIZE * 0.11);

  const visibleAll = props.visibleTiles.size === 0;
  const ownedKeys = humanOwnedKeys;

  return (
    <div className="map-shell">
      <div className="map-hud">
        <div className="map-chip">{dragging ? "Panning" : "Drag to pan"}</div>
        <div className="map-chip">Wheel to zoom</div>
        <div className="map-controls">
          <button type="button" onClick={() => zoomBy(0.82)}>
            +
          </button>
          <button type="button" onClick={() => zoomBy(1.22)}>
            −
          </button>
          <button type="button" onClick={recenter}>
            Recenter
          </button>
        </div>
      </div>

      <div
        ref={containerRef}
        className="pixi-stage"
        style={{ cursor: dragging ? "grabbing" : "grab" }}
        onPointerDownCapture={onPointerDown}
      >
        <svg
          ref={svgRef}
          width={stageSize.width}
          height={stageSize.height}
          viewBox={viewBox}
          preserveAspectRatio="xMidYMid slice"
          onPointerLeave={() => setHover(null)}
          style={{
            display: "block",
            background: "#0a0f14",
            shapeRendering: "crispEdges",
            userSelect: "none",
          }}
        >
          {/* Tile fills */}
          <g pointerEvents="none">
            {pixels.map(({ tile, x, y }) => {
              const base = TERRAIN_COLORS[tile.terrain] ?? "#444444";
              const jitter = Math.round(
                (deterministicJitter(tile.q, tile.r) - 0.5) * 14,
              );
              return (
                <rect
                  key={tileKey(tile.q, tile.r) + ":fill"}
                  x={x - half}
                  y={y - half}
                  width={TILE_SIZE}
                  height={TILE_SIZE}
                  fill={shade(base, jitter)}
                />
              );
            })}
          </g>

          {/* Rivers */}
          <g
            pointerEvents="none"
            stroke="#7fbde7"
            strokeOpacity={0.85}
            strokeWidth={strokeWidth * 1.4}
            fill="none"
          >
            {pixels.map(({ tile, x, y }) =>
              tile.river ? (
                <line
                  key={tileKey(tile.q, tile.r) + ":river"}
                  x1={x - half}
                  y1={y + 2}
                  x2={x + half}
                  y2={y - 2}
                />
              ) : null,
            )}
          </g>

          {/* Feature glyphs */}
          <g
            pointerEvents="none"
            fill="#0a0f14"
            fillOpacity={0.65}
            style={{
              fontFamily: "ui-monospace, SF Mono, Menlo, monospace",
              fontWeight: 700,
            }}
            textAnchor="middle"
            dominantBaseline="central"
          >
            {pixels.map(({ tile, x, y }) =>
              tile.feature ? (
                <text
                  key={tileKey(tile.q, tile.r) + ":feature"}
                  x={x}
                  y={y}
                  fontSize={TILE_SIZE * 0.45}
                >
                  {FEATURE_GLYPH[tile.feature] ?? "•"}
                </text>
              ) : null,
            )}
          </g>

          {/* Resource badges */}
          <g pointerEvents="none">
            {pixels.map(({ tile, x, y }) =>
              tile.resource ? (
                <g key={tileKey(tile.q, tile.r) + ":resource"}>
                  <circle
                    cx={x + half - TILE_SIZE * 0.22}
                    cy={y - half + TILE_SIZE * 0.22}
                    r={TILE_SIZE * 0.18}
                    fill="#e8d79a"
                    stroke="#0a0f14"
                    strokeWidth={strokeWidth * 0.8}
                  />
                  <text
                    x={x + half - TILE_SIZE * 0.22}
                    y={y - half + TILE_SIZE * 0.22}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={TILE_SIZE * 0.3}
                    fontWeight={700}
                    fill="#2b1d08"
                  >
                    {RESOURCE_GLYPH[tile.resource] ?? "?"}
                  </text>
                </g>
              ) : null,
            )}
          </g>

          {/* Improvements (farm, mine, road) */}
          <g
            pointerEvents="none"
            style={{
              fontFamily: "ui-monospace, SF Mono, Menlo, monospace",
              fontWeight: 700,
            }}
            textAnchor="middle"
            dominantBaseline="central"
          >
            {pixels.map(({ tile, x, y }) =>
              tile.improvement ? (
                <g key={tileKey(tile.q, tile.r) + ":imp"}>
                  <circle
                    cx={x - half + TILE_SIZE * 0.22}
                    cy={y + half - TILE_SIZE * 0.22}
                    r={TILE_SIZE * 0.18}
                    fill="#f5eedb"
                    fillOpacity={0.9}
                    stroke="#0a0f14"
                    strokeWidth={strokeWidth * 0.8}
                  />
                  <text
                    x={x - half + TILE_SIZE * 0.22}
                    y={y + half - TILE_SIZE * 0.22}
                    fontSize={TILE_SIZE * 0.3}
                    fill="#2b1d08"
                  >
                    {IMPROVEMENT_GLYPH[tile.improvement] ?? "?"}
                  </text>
                </g>
              ) : null,
            )}
          </g>

          {/* Worked-tile markers for the selected city */}
          {workedHighlight.size > 0 && (
            <g pointerEvents="none">
              {[...workedHighlight].map((key) => {
                const [qStr, rStr] = key.split(",");
                const q = Number(qStr);
                const r = Number(rStr);
                const { x, y } = hexToPixel({ q, r });
                return (
                  <circle
                    key={key + ":worked"}
                    cx={x + half - TILE_SIZE * 0.18}
                    cy={y + half - TILE_SIZE * 0.18}
                    r={TILE_SIZE * 0.08}
                    fill="#f0c76a"
                    stroke="#0a0f14"
                    strokeWidth={strokeWidth * 0.6}
                  />
                );
              })}
            </g>
          )}

          {/* Grid lines */}
          <g
            pointerEvents="none"
            stroke="#000"
            strokeOpacity={0.22}
            strokeWidth={strokeWidth * 0.5}
            fill="none"
          >
            {pixels.map(({ tile, x, y }) => (
              <rect
                key={tileKey(tile.q, tile.r) + ":grid"}
                x={x - half}
                y={y - half}
                width={TILE_SIZE}
                height={TILE_SIZE}
              />
            ))}
          </g>

          {/* Fog overlay */}
          <g pointerEvents="none">
            {pixels.map(({ tile, x, y }) => {
              const key = tileKey(tile.q, tile.r);
              if (visibleAll || props.visibleTiles.has(key)) return null;
              return (
                <rect
                  key={key + ":fog"}
                  x={x - half}
                  y={y - half}
                  width={TILE_SIZE}
                  height={TILE_SIZE}
                  fill="#050810"
                  fillOpacity={0.66}
                />
              );
            })}
          </g>

          {/* Human territory borders */}
          <g
            pointerEvents="none"
            stroke="#d4a443"
            strokeWidth={borderWidth}
            fill="none"
            strokeLinecap="square"
          >
            {[...ownedKeys].flatMap((key) => {
              const [qStr, rStr] = key.split(",");
              const q = Number(qStr);
              const r = Number(rStr);
              const { x, y } = hexToPixel({ q, r });
              const lines: React.ReactElement[] = [];
              if (!ownedKeys.has(tileKey(q, r - 1))) {
                lines.push(
                  <line
                    key={`${key}:top`}
                    x1={x - half}
                    y1={y - half}
                    x2={x + half}
                    y2={y - half}
                  />,
                );
              }
              if (!ownedKeys.has(tileKey(q, r + 1))) {
                lines.push(
                  <line
                    key={`${key}:bottom`}
                    x1={x - half}
                    y1={y + half}
                    x2={x + half}
                    y2={y + half}
                  />,
                );
              }
              if (!ownedKeys.has(tileKey(q - 1, r))) {
                lines.push(
                  <line
                    key={`${key}:left`}
                    x1={x - half}
                    y1={y - half}
                    x2={x - half}
                    y2={y + half}
                  />,
                );
              }
              if (!ownedKeys.has(tileKey(q + 1, r))) {
                lines.push(
                  <line
                    key={`${key}:right`}
                    x1={x + half}
                    y1={y - half}
                    x2={x + half}
                    y2={y + half}
                  />,
                );
              }
              return lines;
            })}
          </g>

          {/* Rival territory borders — thinner, civ-colored */}
          {[...tileOwnerByCiv.entries()].map(([civId, keys]) => {
            if (civId === props.humanCivId) return null;
            const color = CIV_COLORS[civId % CIV_COLORS.length];
            return (
              <g
                key={`rival-borders-${civId}`}
                pointerEvents="none"
                stroke={color}
                strokeOpacity={0.7}
                strokeWidth={borderWidth * 0.55}
                fill="none"
                strokeLinecap="square"
              >
                {[...keys].flatMap((key) => {
                  const [qStr, rStr] = key.split(",");
                  const q = Number(qStr);
                  const r = Number(rStr);
                  const { x, y } = hexToPixel({ q, r });
                  const lines: React.ReactElement[] = [];
                  if (!keys.has(tileKey(q, r - 1))) {
                    lines.push(
                      <line key={`${key}:rt`} x1={x - half} y1={y - half} x2={x + half} y2={y - half} />,
                    );
                  }
                  if (!keys.has(tileKey(q, r + 1))) {
                    lines.push(
                      <line key={`${key}:rb`} x1={x - half} y1={y + half} x2={x + half} y2={y + half} />,
                    );
                  }
                  if (!keys.has(tileKey(q - 1, r))) {
                    lines.push(
                      <line key={`${key}:rl`} x1={x - half} y1={y - half} x2={x - half} y2={y + half} />,
                    );
                  }
                  if (!keys.has(tileKey(q + 1, r))) {
                    lines.push(
                      <line key={`${key}:rr`} x1={x + half} y1={y - half} x2={x + half} y2={y + half} />,
                    );
                  }
                  return lines;
                })}
              </g>
            );
          })}

          {/* Reachable range */}
          {props.reachable.size > 0 && (
            <g pointerEvents="none">
              <g fill="#d4a443" fillOpacity={0.16}>
                {[...props.reachable].map((key) => {
                  const [qStr, rStr] = key.split(",");
                  const q = Number(qStr);
                  const r = Number(rStr);
                  const { x, y } = hexToPixel({ q, r });
                  return (
                    <rect
                      key={key + ":reach-fill"}
                      x={x - half}
                      y={y - half}
                      width={TILE_SIZE}
                      height={TILE_SIZE}
                    />
                  );
                })}
              </g>
              <g stroke="#f0c76a" strokeWidth={borderWidth} fill="none">
                {[...props.reachable].flatMap((key) => {
                  const [qStr, rStr] = key.split(",");
                  const q = Number(qStr);
                  const r = Number(rStr);
                  const { x, y } = hexToPixel({ q, r });
                  const lines: React.ReactElement[] = [];
                  if (!props.reachable.has(tileKey(q, r - 1))) {
                    lines.push(
                      <line
                        key={`${key}:rt`}
                        x1={x - half}
                        y1={y - half}
                        x2={x + half}
                        y2={y - half}
                      />,
                    );
                  }
                  if (!props.reachable.has(tileKey(q, r + 1))) {
                    lines.push(
                      <line
                        key={`${key}:rb`}
                        x1={x - half}
                        y1={y + half}
                        x2={x + half}
                        y2={y + half}
                      />,
                    );
                  }
                  if (!props.reachable.has(tileKey(q - 1, r))) {
                    lines.push(
                      <line
                        key={`${key}:rl`}
                        x1={x - half}
                        y1={y - half}
                        x2={x - half}
                        y2={y + half}
                      />,
                    );
                  }
                  if (!props.reachable.has(tileKey(q + 1, r))) {
                    lines.push(
                      <line
                        key={`${key}:rr`}
                        x1={x + half}
                        y1={y - half}
                        x2={x + half}
                        y2={y + half}
                      />,
                    );
                  }
                  return lines;
                })}
              </g>
            </g>
          )}

          {/* Cities */}
          <g pointerEvents="none">
            {props.state.cities.map((city) => {
              const key = tileKey(city.q, city.r);
              const { x, y } = hexToPixel({ q: city.q, r: city.r });
              const color = CIV_COLORS[city.owner % CIV_COLORS.length];
              return (
                <g key={key + ":city"}>
                  <rect
                    x={x - half + 2}
                    y={y - half + 4}
                    width={TILE_SIZE - 4}
                    height={TILE_SIZE - 6}
                    fill={color}
                    stroke="#0a0f14"
                    strokeWidth={strokeWidth}
                  />
                  <rect
                    x={x - half + 2}
                    y={y - half + 4}
                    width={TILE_SIZE - 4}
                    height={2.5}
                    fill="#fff"
                    fillOpacity={0.22}
                  />
                  <text
                    x={x}
                    y={y + half + TILE_SIZE * 0.2}
                    textAnchor="middle"
                    dominantBaseline="hanging"
                    fontSize={Math.max(8, TILE_SIZE * 0.32)}
                    fontWeight={700}
                    fill="#f5eedb"
                    stroke="#0a0f14"
                    strokeWidth={1.5}
                    paintOrder="stroke"
                  >
                    {city.name}
                  </text>
                </g>
              );
            })}
          </g>

          {/* Units */}
          <g pointerEvents="none">
            {props.state.units.map((unit) => {
              const key = tileKey(unit.q, unit.r);
              const { x, y } = hexToPixel({ q: unit.q, r: unit.r });
              const color = CIV_COLORS[unit.owner % CIV_COLORS.length];
              const isSelected = unit.id === props.selectedUnitId;
              const size = TILE_SIZE * 0.62;
              return (
                <g key={key + ":unit:" + unit.id}>
                  {isSelected && (
                    <rect
                      x={x - half + 1}
                      y={y - half + 1}
                      width={TILE_SIZE - 2}
                      height={TILE_SIZE - 2}
                      fill="none"
                      stroke="#d4a443"
                      strokeWidth={borderWidth}
                    />
                  )}
                  <rect
                    x={x - size / 2}
                    y={y - size / 2}
                    width={size}
                    height={size}
                    fill={color}
                    stroke="#0a0f14"
                    strokeWidth={strokeWidth}
                  />
                  <text
                    x={x}
                    y={y}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={Math.max(10, TILE_SIZE * 0.44)}
                    fontWeight={700}
                    fill="#f5eedb"
                  >
                    {UNIT_GLYPH[unit.type] ?? unit.type[0]?.toUpperCase() ?? "?"}
                  </text>
                  {unit.work_order && (
                    <text
                      x={x}
                      y={y + half - 2}
                      textAnchor="middle"
                      dominantBaseline="alphabetic"
                      fontSize={Math.max(7, TILE_SIZE * 0.22)}
                      fontWeight={700}
                      fill="#f5eedb"
                      stroke="#0a0f14"
                      strokeWidth={1.2}
                      paintOrder="stroke"
                    >
                      {(IMPROVEMENT_GLYPH[unit.work_order.improvement] ?? "·") +
                        " " +
                        unit.work_order.turns_remaining}
                    </text>
                  )}
                </g>
              );
            })}
          </g>

          {/* Hover outline */}
          {hover &&
            (() => {
              const [qStr, rStr] = hover.split(",");
              const q = Number(qStr);
              const r = Number(rStr);
              const { x, y } = hexToPixel({ q, r });
              return (
                <rect
                  x={x - half}
                  y={y - half}
                  width={TILE_SIZE}
                  height={TILE_SIZE}
                  fill="none"
                  stroke="#f8eac2"
                  strokeWidth={strokeWidth * 1.4}
                  strokeOpacity={0.9}
                  pointerEvents="none"
                />
              );
            })()}

          {/* Highlight outline */}
          {props.highlightedTileKey &&
            (() => {
              const [qStr, rStr] = props.highlightedTileKey.split(",");
              const q = Number(qStr);
              const r = Number(rStr);
              const { x, y } = hexToPixel({ q, r });
              return (
                <rect
                  x={x - half}
                  y={y - half}
                  width={TILE_SIZE}
                  height={TILE_SIZE}
                  fill="none"
                  stroke="#d4a443"
                  strokeWidth={borderWidth}
                  pointerEvents="none"
                />
              );
            })()}

          {/* Hit zones — transparent, topmost, sole owner of pointer events.
              Disabled during drag so cursor sweeps don't spam hover updates
              (which would re-render the parent and cause viewBox jitter). */}
          <g style={{ pointerEvents: dragging ? "none" : "auto" }}>
            {pixels.map(({ tile, x, y }) => {
              const key = tileKey(tile.q, tile.r);
              return (
                <rect
                  key={key + ":hit"}
                  x={x - half}
                  y={y - half}
                  width={TILE_SIZE}
                  height={TILE_SIZE}
                  fill="transparent"
                  onMouseEnter={() => {
                    setHover(key);
                    props.onTileHover?.(tile.q, tile.r);
                  }}
                  onMouseLeave={() =>
                    setHover((current) => (current === key ? null : current))
                  }
                  onClick={() => handleTileClick(tile.q, tile.r)}
                />
              );
            })}
          </g>
        </svg>
      </div>
    </div>
  );
}

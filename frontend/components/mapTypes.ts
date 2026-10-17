"use client";

import { GameStateDTO, UnitDTO } from "@/lib/api";
import { AssetManifest } from "@/lib/assetManifest";
import { Hex } from "@/lib/hex";
import { TFunction } from "@/lib/i18n";

export interface StrategyMapProps {
  state: GameStateDTO;
  selectedUnitId: number | null;
  reachable: Set<string>;
  highlightedTileKey?: string | null;
  focusHex?: Hex | null;
  humanCivId?: number | null;
  visibleTiles: Set<string>;
  assets?: AssetManifest | null;
  placedStructureAssets?: Record<string, string>;
  /** Translator for the map HUD chrome (pan/zoom hints, recenter). */
  t: TFunction;
  onTileClick?: (q: number, r: number) => void;
  onTileHover?: (q: number, r: number) => void;
  onStructureDrop?: (cityId: number, category: string, q: number, r: number) => void;
  onUnitClick?: (unit: UnitDTO) => void;
}

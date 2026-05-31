"use client";

import { GameStateDTO, UnitDTO } from "@/lib/api";
import { AssetManifest } from "@/lib/assetManifest";
import { Hex } from "@/lib/hex";

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
  onTileClick?: (q: number, r: number) => void;
  onTileHover?: (q: number, r: number) => void;
  onStructureDrop?: (cityId: number, category: string, q: number, r: number) => void;
  onUnitClick?: (unit: UnitDTO) => void;
}

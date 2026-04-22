"use client";

import { GameStateDTO, UnitDTO } from "@/lib/api";
import { Hex } from "@/lib/hex";

export interface StrategyMapProps {
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

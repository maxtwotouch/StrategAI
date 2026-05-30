// Deterministic maps from game vocabulary to the asset service's enum-driven
// parameters, for units, terrain elevation, and city/structure art. No LLM:
// the service assembles prompts from these enums plus the static descriptions.

import { ApiUnitType, StructureParams, TerrainParams } from "@/lib/assetApi";

// --- Units: 7 game unit types collapse onto the 4 the service offers ---
export const UNIT_TYPE_MAP: Record<string, ApiUnitType> = {
  warrior: "warrior",
  swordsman: "warrior",
  horseman: "warrior",
  archer: "archer",
  scout: "scout",
  settler: "settler",
  worker: "settler",
};

const UNIT_DESCRIPTION: Record<ApiUnitType, string> = {
  warrior:
    "a medieval foot soldier in leather and mail armor, holding a sword and a round wooden shield, helmeted, alert standing stance",
  archer:
    "a medieval archer in light leather armor drawing a longbow, a quiver of arrows on the back, hooded, focused stance",
  scout:
    "a lightly equipped medieval scout in a hooded traveling cloak, holding a short spear, a satchel at the hip, watchful posture",
  settler:
    "a medieval settler in plain peasant clothes carrying tools and a bundle of supplies, a walking staff in hand, weary but resolute",
};

export function unitDescriptionFor(apiType: ApiUnitType): string {
  return UNIT_DESCRIPTION[apiType];
}

// --- Terrain elevation: which terrains get a relief sprite layered on top ---
export const ELEVATION_TERRAINS: Record<string, TerrainParams> = {
  hills: {
    category: "hill",
    scale: "medium",
    material: "earthen",
    description:
      "a broad grassy hill rising from the tile with gentle rounded slopes, a few small rocks and grass tufts on the crest, meant to sit on a grass tile",
  },
  mountain: {
    category: "cliff",
    scale: "high",
    material: "rocky",
    description:
      "a tall jagged grey rock cliff with horizontal strata bands, a sharp uneven peak, loose stones and rubble at the base, meant to sit on a stone tile",
  },
};

// --- City structure style per civ (by leader_name; neutral fallback) ---
const STRUCTURE_STYLE: Record<string, string> = {
  "Genghis Khan": "slavic_timber",
  Cleopatra: "moorish",
  "Mahatma Gandhi": "mediterranean",
};
const FALLBACK_STYLE = "anglo_saxon_stone";

export function cityStructureFor(leaderName: string): StructureParams {
  return {
    category: "housing",
    style: STRUCTURE_STYLE[leaderName] ?? FALLBACK_STYLE,
    condition: "pristine",
    scale: "medium",
    description:
      "a medieval town center with a great hall under a tiled gabled roof, a stone-and-timber facade, a banner above the entrance, smaller dwellings clustered around it",
  };
}

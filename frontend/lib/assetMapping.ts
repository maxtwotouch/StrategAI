// Deterministic maps from game vocabulary to the asset service's enum-driven
// parameters, for units, terrain elevation, and city/structure art. No LLM:
// the service assembles prompts from these enums plus the static descriptions.

import { ApiUnitType, StructureParams, TerrainParams } from "@/lib/assetApi";

// Display-label / enum-value pairs surfaced in the start-screen dropdowns
// so the player can compose their own leader. Values match the asset
// service's enum vocabularies in leader/models.py.
export const ARCHETYPE_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "warrior_king", label: "Warrior King" },
  { value: "warrior_queen", label: "Warrior Queen" },
  { value: "philosopher_king", label: "Philosopher King" },
  { value: "merchant_prince", label: "Merchant Prince" },
  { value: "spiritual_leader", label: "Spiritual Leader" },
  { value: "diplomat", label: "Diplomat" },
  { value: "tyrant", label: "Tyrant" },
  { value: "visionary", label: "Visionary" },
];

export const CULTURE_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "medieval_european", label: "Medieval European" },
  { value: "classical_greek", label: "Classical Greek" },
  { value: "roman_imperial", label: "Roman Imperial" },
  { value: "ancient_egyptian", label: "Ancient Egyptian" },
  { value: "east_asian_imperial", label: "East Asian Imperial" },
  { value: "south_asian", label: "South Asian" },
  { value: "nordic_viking", label: "Nordic Viking" },
  { value: "persian", label: "Persian" },
  { value: "mesopotamian", label: "Mesopotamian" },
  { value: "mesoamerican", label: "Mesoamerican" },
  { value: "sub_saharan_african", label: "Sub-Saharan African" },
  { value: "islamic_golden_age", label: "Islamic Golden Age" },
];

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

// Base shape + gear per unit, expressed without a culture so the per-civ
// generator can vary the styling.
const UNIT_BASE: Record<ApiUnitType, string> = {
  warrior:
    "foot soldier in armor, holding a sword and a round wooden shield, helmeted, alert standing stance",
  archer:
    "archer drawing a longbow, a quiver of arrows on the back, hooded, focused stance",
  scout:
    "lightly equipped scout in a hooded traveling cloak, holding a short spear, a satchel at the hip, watchful posture",
  settler:
    "settler in plain peasant clothes carrying tools and a bundle of supplies, a walking staff in hand, weary but resolute",
};

// Cultural flavor prepended to the base description so each civ gets a
// distinct sprite for the same gameplay unit type. Matches the asset
// service's Culture enum.
const CULTURE_FLAVOR: Record<string, string> = {
  ancient_egyptian: "an Ancient Egyptian",
  classical_greek: "a Classical Greek",
  roman_imperial: "a Roman imperial",
  medieval_european: "a medieval European",
  east_asian_imperial: "an East Asian imperial",
  mesopotamian: "a Mesopotamian",
  mesoamerican: "a Mesoamerican",
  nordic_viking: "a Nordic Viking",
  persian: "a Persian",
  sub_saharan_african: "a Sub-Saharan African",
  south_asian: "a South Asian",
  islamic_golden_age: "an Islamic Golden Age",
};

export function unitDescriptionFor(apiType: ApiUnitType, culture: string): string {
  const flavor = CULTURE_FLAVOR[culture] ?? "a medieval";
  return `${flavor} ${UNIT_BASE[apiType]}`;
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

// Deterministic map from a game leader to the asset service's enum-driven
// leader parameters. No LLM: the service assembles the diffusion prompt from
// these enums plus the physical description below.
//
// Keyed by leader_name to match the fixed roster in
// backend/app/api/game_factory.py. Unknown names fall back to a neutral
// medieval ruler so newly-added leaders still render something sensible.

import { LeaderParams } from "@/lib/assetApi";

interface LeaderDef {
  archetype: string; // Archetype enum
  culture: string; // Culture enum
  timeOfDay: string; // TimeOfDay enum
  mood: string; // Mood enum — kept stable (from identity, not live diplomacy)
  description: string; // physical description, >= 50 chars
}

const LEADER_DEFS: Record<string, LeaderDef> = {
  "Genghis Khan": {
    archetype: "warrior_king",
    culture: "east_asian_imperial",
    timeOfDay: "storm",
    mood: "menacing",
    description:
      "A weathered Mongol warlord in his fifties, broad and heavyset, sun-darkened skin, a long thin braided beard streaked with grey, narrow piercing eyes, wearing layered lamellar armor of lacquered leather and iron, a fur-trimmed cloak, and a gold-banded helm.",
  },
  Cleopatra: {
    archetype: "diplomat",
    culture: "ancient_egyptian",
    timeOfDay: "golden_hour",
    mood: "wise_serene",
    description:
      "A poised Egyptian queen in her late twenties, olive skin, sharp dark kohl-lined eyes, a sleek black bob beneath a golden vulture headdress, wearing a pleated white linen gown with a broad beaded collar of gold and lapis lazuli, and gold serpent armlets.",
  },
  "Mahatma Gandhi": {
    archetype: "philosopher_king",
    culture: "south_asian",
    timeOfDay: "dawn",
    mood: "wise_serene",
    description:
      "A slender elderly Indian leader, bald with round wire-rimmed spectacles, a small grey moustache, gentle calm eyes, draped in a simple handspun white cotton shawl over bare shoulders, holding a wooden walking staff, with a serene and dignified bearing.",
  },
};

const FALLBACK: LeaderDef = {
  archetype: "philosopher_king",
  culture: "medieval_european",
  timeOfDay: "golden_hour",
  mood: "contemplative",
  description:
    "A dignified medieval ruler of middle age, fair complexion, a neatly trimmed beard, keen thoughtful eyes, wearing a fur-trimmed velvet robe over a tunic, a simple gold circlet upon the brow, with a composed and authoritative bearing.",
};

export function leaderParamsFor(leaderName: string): LeaderParams {
  const def = LEADER_DEFS[leaderName] ?? FALLBACK;
  return {
    leaderName,
    leaderDescription: def.description,
    archetype: def.archetype,
    culture: def.culture,
    timeOfDay: def.timeOfDay,
    mood: def.mood,
  };
}

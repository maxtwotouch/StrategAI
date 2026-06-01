// Deterministic map from a game leader to the asset service's enum-driven
// leader parameters. No LLM: the service assembles the diffusion prompt from
// these enums plus the physical description below.
//
// Keyed by leader_name to match the fixed roster in
// backend/app/api/game_factory.py. Unknown names fall back to a neutral
// medieval ruler so newly-added leaders still render something sensible.

import { LeaderParams, LeaderActionCategory } from "@/lib/assetApi";

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

// Per-scene cinematic variation. The leader's identity (archetype, culture,
// physical description) stays fixed, but an action scene's lighting and mood
// should track *what is happening* and shift turn to turn — otherwise every
// scene for a given leader is lit the same way and looks repetitive. Each
// category lists candidate TimeOfDay / Mood enum values; we rotate through them
// by turn (with an offset so time and mood don't move in lockstep) to maximise
// variety while staying tonally appropriate to the event.
const SCENE_CINEMATICS: Record<
  LeaderActionCategory,
  { timeOfDay: string[]; mood: string[] }
> = {
  military: {
    timeOfDay: ["twilight", "storm", "night", "golden_hour"],
    mood: ["grim_determined", "menacing", "triumphant"],
  },
  diplomatic: {
    timeOfDay: ["golden_hour", "midday", "dawn"],
    mood: ["contemplative", "wise_serene", "hopeful", "menacing"],
  },
  construction: {
    timeOfDay: ["dawn", "golden_hour", "midday"],
    mood: ["hopeful", "triumphant", "contemplative"],
  },
  scientific: {
    timeOfDay: ["night", "twilight", "dawn"],
    mood: ["contemplative", "wise_serene", "mystical"],
  },
  cultural: {
    timeOfDay: ["golden_hour", "twilight", "midday"],
    mood: ["triumphant", "hopeful", "mystical"],
  },
  exploration: {
    timeOfDay: ["dawn", "golden_hour", "midday", "storm"],
    mood: ["hopeful", "contemplative", "wise_serene"],
  },
  crisis: {
    timeOfDay: ["storm", "night", "twilight"],
    mood: ["grim_determined", "menacing", "melancholic"],
  },
};

// Returns the TimeOfDay / Mood overrides for a given scene, rotated by turn so
// successive scenes of the same category still differ. Merge onto a leader's
// base LeaderParams before generating an action image.
export function sceneCinematicsFor(
  category: LeaderActionCategory,
  turn: number,
): Pick<LeaderParams, "timeOfDay" | "mood"> {
  const profile = SCENE_CINEMATICS[category] ?? SCENE_CINEMATICS.cultural;
  const safeTurn = Number.isFinite(turn) ? Math.abs(Math.trunc(turn)) : 0;
  return {
    timeOfDay: profile.timeOfDay[safeTurn % profile.timeOfDay.length],
    // Offset the mood index so lighting and mood cycle out of phase.
    mood: profile.mood[(safeTurn + 1) % profile.mood.length],
  };
}

// Build LeaderParams from user-supplied fields, filling in safe defaults and
// padding too-short descriptions so the API's 50-char floor is always met.
export function buildCustomLeaderParams(input: {
  leaderName: string;
  archetype?: string;
  culture?: string;
  description?: string;
}): LeaderParams {
  const fallback = FALLBACK;
  const trimmedDesc = (input.description ?? "").trim();
  const description = trimmedDesc.length >= 50 ? trimmedDesc : fallback.description;
  return {
    leaderName: input.leaderName.trim() || "Unknown Sovereign",
    leaderDescription: description,
    archetype: input.archetype || fallback.archetype,
    culture: input.culture || fallback.culture,
    timeOfDay: fallback.timeOfDay,
    mood: fallback.mood,
  };
}

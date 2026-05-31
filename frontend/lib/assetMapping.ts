// Deterministic maps from game vocabulary to the asset service's enum-driven
// parameters, for units, terrain elevation, and city/structure art. No LLM:
// the service assembles prompts from these enums plus the static descriptions.

import { ApiUnitType, StructureParams, TerrainParams } from "@/lib/assetApi";

export const STRUCTURE_CATEGORIES: ReadonlyArray<{
  id: string;
  label: string;
  hint: string;
}> = [
  { id: "production", label: "Production Hall", hint: "Workshop, forge, mill" },
  { id: "fortification", label: "Fortification", hint: "Walls, keep, gatehouse" },
  { id: "housing", label: "Housing District", hint: "Townhouse, longhouse, manor" },
  { id: "sacred", label: "Sacred Site", hint: "Temple, shrine, cathedral" },
];

export const STRUCTURE_CATEGORY_IDS = STRUCTURE_CATEGORIES.map((cat) => cat.id);

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

interface CivVisualProfile {
  culturePrefix: string;
  style: string;
  materials: string;
  silhouette: string;
  motifs: string;
  unitKit: string;
}

const CULTURE_PROFILES: Record<string, CivVisualProfile> = {
  ancient_egyptian: {
    culturePrefix: "an Ancient Egyptian",
    style: "moorish",
    materials: "sun-baked limestone, painted plaster, gold, lapis lazuli, and reed mats",
    silhouette: "flat roofs, battered walls, pylons, lotus columns, and small obelisks",
    motifs: "lotus flowers, solar disks, blue-and-gold trim, and kohl-dark ceremonial detail",
    unitKit: "white linen wraps, bronze fittings, striped cloth, bead collars, and sun-faded shields",
  },
  classical_greek: {
    culturePrefix: "a Classical Greek",
    style: "mediterranean",
    materials: "white marble, pale limestone, terracotta roof tiles, and painted wood",
    silhouette: "columned porches, triangular pediments, tiled roofs, and open courtyards",
    motifs: "meander borders, olive branches, bronze trim, and red-black pottery patterns",
    unitKit: "bronze greaves, linen cuirasses, crested helmets, round hoplon shields, and red cloaks",
  },
  roman_imperial: {
    culturePrefix: "a Roman imperial",
    style: "mediterranean",
    materials: "cut stone, brick, red tile, concrete arches, and bronze hardware",
    silhouette: "arched gates, tiled basilica roofs, square towers, and orderly courtyards",
    motifs: "eagle standards, laurel wreaths, red banners, and disciplined geometric masonry",
    unitKit: "segmented armor, red tunics, rectangular shields, iron helmets, and military belts",
  },
  medieval_european: {
    culturePrefix: "a medieval European",
    style: "anglo_saxon_stone",
    materials: "grey fieldstone, oak beams, lime plaster, thatch, and iron hinges",
    silhouette: "steep roofs, squat keeps, timber frames, chimneys, and fenced yards",
    motifs: "simple heraldic cloth, carved oak braces, iron lanterns, and practical village clutter",
    unitKit: "mail shirts, wool tabards, kettle helmets, leather belts, and painted wooden shields",
  },
  east_asian_imperial: {
    culturePrefix: "an East Asian imperial",
    style: "mediterranean",
    materials: "dark lacquered timber, pale stone plinths, ceramic roof tiles, and red pillars",
    silhouette: "tiered roofs, bracketed eaves, raised platforms, and compact walled courts",
    motifs: "hanging banners, carved cloud forms, bronze bells, and black-red-gold lacquer detail",
    unitKit: "lamellar plates, cloth sashes, conical helmets, lacquered shields, and banner poles",
  },
  mesopotamian: {
    culturePrefix: "a Mesopotamian",
    style: "moorish",
    materials: "mud brick, glazed blue tile, cedar beams, woven reed, and baked clay",
    silhouette: "stepped platforms, thick battered walls, shaded arcades, and flat roofs",
    motifs: "cuneiform tablets, rosette tiles, date-palm details, and deep blue glazed accents",
    unitKit: "wool tunics, bronze helmets, scale armor, fringed hems, and wicker shields",
  },
  mesoamerican: {
    culturePrefix: "a Mesoamerican",
    style: "moorish",
    materials: "carved volcanic stone, stucco, bright mineral paint, woven fiber, and jade",
    silhouette: "stepped temple forms, sloped walls, terraces, and carved stone thresholds",
    motifs: "feathered banners, jade beads, geometric glyphs, and red turquoise painted trim",
    unitKit: "quilted cotton armor, feather crests, obsidian-edged weapons, and woven sandals",
  },
  nordic_viking: {
    culturePrefix: "a Nordic Viking",
    style: "nordic_wooden",
    materials: "pine logs, dark oak planks, turf roofs, carved posts, hide, and iron rivets",
    silhouette: "longhouse roofs, dragon-head gables, palisades, smoke holes, and windbreak fences",
    motifs: "rune carving, knotwork trim, raven banners, weathered shields, and cold iron hardware",
    unitKit: "fur trim, mail patches, round shields, nasal helmets, wool cloaks, and leather boots",
  },
  persian: {
    culturePrefix: "a Persian",
    style: "moorish",
    materials: "polished stone, turquoise tile, cedar screens, woven carpets, and brass fittings",
    silhouette: "arched iwans, domed roofs, screened courtyards, and slender corner towers",
    motifs: "cypress patterns, star geometry, jewel-toned textiles, and gold-edged banners",
    unitKit: "scale armor, patterned robes, soft caps, recurved bows, and ornate belts",
  },
  sub_saharan_african: {
    culturePrefix: "a Sub-Saharan African",
    style: "slavic_timber",
    materials: "red earth plaster, dark hardwood, thatch, woven reed, brass, and dyed cloth",
    silhouette: "rounded walls, conical roofs, carved posts, open shade structures, and palisades",
    motifs: "bold textile patterns, brass ornaments, carved masks, and ochre-white painted geometry",
    unitKit: "dyed cloth wraps, leather armor, brass cuffs, tall shields, and carved wooden gear",
  },
  south_asian: {
    culturePrefix: "a South Asian",
    style: "mediterranean",
    materials: "warm sandstone, carved teak, white limewash, brass lamps, and patterned cloth",
    silhouette: "domed pavilions, carved screens, stepped plinths, and shaded verandas",
    motifs: "lotus medallions, peacock colors, brass bells, and intricate floral carving",
    unitKit: "cotton wraps, quilted vests, turbans, curved blades, brass details, and patterned sashes",
  },
  islamic_golden_age: {
    culturePrefix: "an Islamic Golden Age",
    style: "moorish",
    materials: "cream stone, turquoise tile, cedar lattice, carved plaster, and brass lamps",
    silhouette: "horseshoe arches, domes, courtyards, minaret-like towers, and shaded arcades",
    motifs: "star geometry, calligraphic bands, blue-green tilework, and brass lantern light",
    unitKit: "mail under robes, wrapped turbans, patterned shields, curved blades, and leather boots",
  },
};

const LEADER_PROFILE_OVERRIDES: Record<string, Partial<CivVisualProfile>> = {
  "Genghis Khan": {
    culturePrefix: "a Mongol steppe",
    style: "slavic_timber",
    materials: "hide, felt, dark timber, braided rope, bone charms, and blackened iron",
    silhouette: "low wind-bent halls, round yurt forms, horse pens, palisades, and banner poles",
    motifs: "horsehair standards, wolf-tail tassels, weathered shields, and soot-dark campaign gear",
    unitKit: "lamellar armor, fur collars, leather boots, horsehair plumes, and compact steppe weapons",
  },
  Cleopatra: {
    culturePrefix: "an Alexandrian Egyptian",
  },
  "Mahatma Gandhi": {
    culturePrefix: "a South Asian",
    materials: "white limewash, warm sandstone, woven cotton awnings, carved teak, and brass lamps",
    motifs: "simple handspun cloth, lotus carving, brass oil lamps, and restrained civic ornament",
    unitKit: "plain cotton wraps, leather sandals, quilted vests, wooden staffs, and modest brass details",
  },
};

function civVisualProfileFor(
  leaderName: string,
  culture: string,
): CivVisualProfile {
  const base = CULTURE_PROFILES[culture] ?? CULTURE_PROFILES.medieval_european;
  return { ...base, ...(LEADER_PROFILE_OVERRIDES[leaderName] ?? {}) };
}

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

export function unitDescriptionFor(
  apiType: ApiUnitType,
  culture: string,
  leaderName = "",
): string {
  const profile = civVisualProfileFor(leaderName, culture);
  return [
    `${profile.culturePrefix} ${UNIT_BASE[apiType]}`,
    `wearing ${profile.unitKit}`,
    `with visual motifs of ${profile.motifs}`,
  ].join(", ");
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

const STRUCTURE_COPY: Record<string, { label: string; purpose: string }> = {
  production: {
    label: "production",
    purpose:
      "a compact workshop with a forge chimney, stacked supplies, an anvil yard, and practical work sheds",
  },
  fortification: {
    label: "fortification",
    purpose:
      "a compact defensive gatehouse with walls, a watch platform, narrow firing slits, and reinforced doors",
  },
  housing: {
    label: "housing",
    purpose:
      "a small residential district with clustered homes, fenced yards, domestic clutter, and warm lived-in detail",
  },
  sacred: {
    label: "sacred",
    purpose:
      "a small sacred site with a shrine, altar, banners, ritual objects, and ceremonial detail",
  },
};

function limitStructureDescription(description: string): string {
  if (description.length <= 390) return description;
  const clipped = description.slice(0, 390);
  const lastSpace = clipped.lastIndexOf(" ");
  return `${clipped.slice(0, Math.max(20, lastSpace)).replace(/[,. ]+$/, "")}.`;
}

export function cityStructureFor(
  leaderName: string,
  category: string,
  culture = "medieval_european",
): StructureParams {
  const copy = STRUCTURE_COPY[category] ?? STRUCTURE_COPY.housing;
  const profile = civVisualProfileFor(leaderName, culture);
  return {
    category: copy.label,
    style: profile.style,
    condition: "pristine",
    scale: "small",
    description: limitStructureDescription([
      copy.purpose,
      `built from ${profile.materials}`,
      `with ${profile.silhouette}`,
      `and ${profile.motifs}`,
    ].join(", ")),
  };
}

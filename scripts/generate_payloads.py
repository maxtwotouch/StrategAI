#!/usr/bin/env python3
"""
Bulk API Payload Generator
===========================

Generates diverse, realistic API request payloads for all asset families
(structure, object, terrain, unit, leader, background_tile).  Uses
**component banks** — pools of descriptive words and phrases per family —
to synthesize varied descriptions programmatically, without an LLM.

Coverage Strategies
-------------------
**combinatorial**  Full cross-product of all enum values × 1 description each.
                   Produces ~200-500 payloads per family.  Best for validating
                   every enum value works end-to-end.

**representative** Interesting enum combos that span the diversity space
                   (e.g. each category × 2 styles × 2 conditions).
                   ~20-50 payloads per family.  Best for daily sanity.

**random**         Random enums + random descriptions for N payloads.
                   Best for stress testing at scale.

Output Formats
--------------
**json**   Single JSON array of payload objects.
**jsonl**  One JSON object per line (streaming replay).
**curl**   Shell script with ``curl`` commands.

Replay
------
Feed the generated payloads to ``scripts/validate_api.py --payloads-file``
to replay them against a live server and validate response contracts.

Usage::

    # Generate 50 representative payloads per family
    python scripts/generate_payloads.py --strategy representative --output payloads.json

    # Generate 200 random leader payloads for stress testing
    python scripts/generate_payloads.py --family leader --count 200 --strategy random \\
        --output leader_payloads.jsonl --format jsonl

    # Combinatorial coverage for structure only
    python scripts/generate_payloads.py --family structure --strategy combinatorial \\
        --output structure_combo.json

    # Output curl commands for quick manual testing
    python scripts/generate_payloads.py --family unit --count 10 --format curl \\
        --output test_units.sh

    # All families, representative, output to stdout
    python scripts/generate_payloads.py --stdout
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
#  Enum value sets — mirrors src/leader/models.py, src/tile/models.py,
#  src/unit/models.py, src/tile/background_models.py
# ---------------------------------------------------------------------------

ARCHETYPES = [
    "warrior_queen", "warrior_king", "philosopher_king", "merchant_prince",
    "spiritual_leader", "diplomat", "tyrant", "visionary",
]

CULTURES = [
    "ancient_egyptian", "classical_greek", "roman_imperial", "medieval_european",
    "east_asian_imperial", "mesopotamian", "mesoamerican", "nordic_viking",
    "persian", "sub_saharan_african", "south_asian", "islamic_golden_age",
]

TIMES_OF_DAY = ["dawn", "golden_hour", "midday", "twilight", "night", "storm"]

MOODS = [
    "triumphant", "wise_serene", "grim_determined", "mystical",
    "melancholic", "menacing", "hopeful", "contemplative",
]

ACTION_CATEGORIES = [
    "military", "diplomatic", "construction", "scientific", "cultural",
    "exploration", "crisis",
]

STRUCTURE_CATEGORIES = ["fortification", "production", "housing", "sacred"]
STRUCTURE_STYLES = [
    "nordic_wooden", "anglo_saxon_stone", "norman_romanesque", "gothic",
    "mediterranean", "slavic_timber", "moorish",
]
STRUCTURE_CONDITIONS = [
    "pristine", "weathered", "ruined", "under_construction", "fortified",
]
STRUCTURE_SCALES = ["small", "medium", "large"]

OBJECT_CATEGORIES = ["vegetation", "geological", "rural_props", "urban_props", "debris"]
BIOMES = [
    "temperate_forest", "taiga", "desert", "swamp", "mountain", "coastal", "grassland",
]
SEASONS = ["spring", "summer", "autumn", "winter"]

TERRAIN_CATEGORIES = ["hill", "slope", "cliff", "ridge", "depression"]
TERRAIN_SCALES = ["low", "medium", "high"]
TERRAIN_MATERIALS = ["earthen", "sandy", "rocky", "snowy", "muddy"]

UNIT_TYPES = ["archer", "scout", "settler", "warrior"]

BACKGROUND_TILE_TYPES = ["water", "grass", "sand", "stone", "dirt"]

LEADER_NAMES = [
    "Queen Isabella", "Pharaoh Akhenaten", "Lord Harald", "Empress Theodora",
    "King Leonidas", "Shogun Takeda", "Sultan Saladin", "Chief Cihuacoatl",
    "Khan Batu", "Emperor Qin", "Rajah Ashoka", "Caliph Al-Rashid",
    "High King Brian", "Priestess Nefertari", "Merchant Doge Enrico",
    "Philosopher Seneca", "Warlord Attila", "Visionary Da Vinci",
    "Queen Boudica", "Strategist Sun Tzu",
]


# ===========================================================================
#  Description Component Banks
# ===========================================================================
# Each family has pools of descriptive fragments.  The generator picks
# components pseudo-randomly (seeded by a hash of the enum combo for
# reproducibility) and assembles them into a realistic prose description.

_STRUCTURE_COMPONENTS = {
    "roof_material": [
        "thatched straw", "weathered slate", "red terracotta tiles",
        "dark wooden shingles", "copper sheeting", "rough-hewn stone slabs",
        "ceramic blue tiles", "moss-covered thatch",
    ],
    "roof_shape": [
        "a steep gabled roof", "a conical roof", "a flat roof with parapets",
        "a domed roof", "a pitched roof with dormers", "a pyramidal roof",
        "a sawtooth roof line",
    ],
    "stories": [
        "a single-story building", "a two-story structure",
        "a compact ground-level footprint", "a towering three-story edifice",
    ],
    "feature": [
        "a smoking chimney", "a bell tower", "a portcullis gate",
        "stained glass windows", "a water wheel", "a wooden signboard",
        "battlements with arrow slits", "a dovecote in the eaves",
        "a walled garden", "iron window bars", "a drawbridge",
        "climbing ivy on the walls", "a weather vane atop the roof",
        "a covered porch", "a stone well beside the entrance",
    ],
    "entrance": [
        "heavy oak double doors", "an iron-reinforced gate",
        "an ivy-covered stone archway", "a wooden drawbridge entrance",
        "iron-studded doors", "a portcullis with a raised gate",
        "a carved wooden door with iron hinges", "an arched stone doorway",
    ],
    "activity": [
        "smoke curling from the chimney", "banners fluttering in the breeze",
        "pigeons roosting on the ledges", "guards patrolling the parapet",
        "a merchant cart parked outside", "lanterns glowing in the windows",
        "tools leaning against the wall", "freshly cut timber stacked nearby",
    ],
}

_OBJECT_COMPONENTS = {
    "object_type": [
        "a towering oak tree", "a weathered grey boulder",
        "a wooden hay cart with two wheels", "a market stall with a canvas awning",
        "scattered broken pottery shards", "a moss-covered fallen log",
        "a hand-painted wooden signpost", "an old stone well with a bucket",
        "a stack of firewood logs", "a blacksmith's anvil on a stump",
        "a wicker basket of apples", "a fishing net draped over a post",
        "a water trough for horses", "a stack of hay bales",
        "a rusted iron lantern on a pole",
    ],
    "material": [
        "rough bark", "smooth grey stone", "weathered oak wood",
        "woven wicker", "rusted iron bands", "terracotta clay",
        "coarse woven fabric", "splintered pinewood", "chiselled granite",
        "cast iron", "braided rope", "green copper patina",
    ],
    "feature": [
        "a hollow trunk", "moss covering the shaded north face",
        "carved initials on the surface", "a broken spoke on one wheel",
        "rusted metal hinges", "dried mud caked on the base",
        "lichen growing in patches", "scorch marks from a fire",
        "a faded painted emblem", "rope marks worn into the wood",
    ],
}

_TERRAIN_COMPONENTS = {
    "shape": [
        "a rounded mound", "a jagged ridgeline", "a gentle sweeping slope",
        "a stepped terraced incline", "a bowl-shaped hollow",
        "a sharp vertical face", "an undulating low rise",
        "a narrow spine-like ridge", "a domed hilltop",
    ],
    "surface": [
        "grass tufts on the top surface", "small rocks scattered around",
        "exposed soil on steeper faces", "a snow cap on the peak",
        "muddy patches near the base", "sparse thorny scrub",
        "wildflowers dotting the slope", "wind-blown sand ripples",
        "patches of ice in the crevices",
    ],
    "bg_hint": [
        "sits comfortably on grass terrain", "blends with sandy ground below",
        "rises from a dirt base", "edges merge with stone ground",
        "nestled in snowy surroundings", "borders muddy wetland",
    ],
}

_UNIT_COMPONENTS = {
    "clothing_color": [
        "forest green", "crimson red", "navy blue", "dark brown",
        "charcoal grey", "royal purple", "ochre yellow", "russet orange",
        "undyed wool white", "midnight black",
    ],
    "clothing_material": [
        "a quilted leather gambeson", "a heavy wool tunic",
        "polished steel plate armour", "a hooded linen cloak",
        "chainmail over a padded undershirt", "studded leather jerkin",
        "a simple woven tunic", "lamellar scale armour",
        "a fur-lined travelling cloak",
    ],
    "weapon_detail": [
        "a yew longbow", "a steel arming sword", "a short hunting bow",
        "a kite shield with a golden lion crest", "a walking staff",
        "a battle axe with a leather-wrapped haft", "a crossbow with iron bolts",
        "a round wooden shield with iron rim", "a dagger on the belt",
        "a spear with a leaf-shaped blade",
    ],
    "posture": [
        "standing in a ready combat stance", "mid-stride in a running pose",
        "standing at attention", "kneeling with bow drawn",
        "advancing with shield raised", "walking with staff in hand",
        "holding a defensive guard position", "scanning the horizon watchfully",
    ],
    "feature": [
        "a feathered cap", "a scar across the left cheek",
        "a crested helm with a visor", "a deep hood casting shadows on the face",
        "a bushy beard", "a clean-shaven youthful face",
        "a braided leather headband", "a silver pendant necklace",
        "worn leather gloves", "a belt pouch with provisions",
    ],
    "build": [
        "lean and wiry build", "stocky powerful frame",
        "average athletic proportions", "tall and slender silhouette",
        "broad-shouldered muscular build", "compact and agile physique",
    ],
}

_LEADER_COMPONENTS = {
    "age": [
        "middle-aged", "weathered by years of rule", "youthful but commanding",
        "in their prime", "elder statesperson with silver hair",
        "ageless with an intense gaze",
    ],
    "build": [
        "tall and imposing", "lean and sharp-featured",
        "broad-shouldered and muscular", "slender and graceful",
        "stocky with a powerful presence", "elegant and refined",
    ],
    "skin": [
        "olive skin", "dark brown skin", "fair complexion",
        "weathered bronze skin", "golden-toned skin", "pale ivory skin",
    ],
    "hair": [
        "flowing silver-streaked hair", "closely cropped dark hair",
        "elaborate braided hair with gold threads", "long straight black hair",
        "curly auburn hair", "a shaved head with ceremonial tattoos",
        "greying hair beneath the crown", "flame-red hair in warrior braids",
    ],
    "eyes": [
        "piercing amber eyes", "deep brown intelligent eyes",
        "icy blue calculating eyes", "warm hazel eyes with crows feet",
        "dark intense eyes", "grey-green watchful eyes",
    ],
    "feature": [
        "a prominent scar across the brow", "an elaborate jewelled crown",
        "a commander's circlet of twisted gold", "a pharaoh's striped nemes headdress",
        "a laurel wreath of gold leaves", "ceremonial war paint on the cheeks",
        "a ruby-studded necklace", "intricate facial tattoos",
        "a gold signet ring on every finger",
    ],
    "clothing": [
        "wearing royal purple silk robes embroidered with gold thread",
        "clad in polished ceremonial silver plate armour",
        "draped in white linen with lapis lazuli ornaments",
        "in a crimson commander's coat with gold epaulettes",
        "wearing a bearskin cloak over studded leather",
        "in flowing sage-green scholar's robes",
        "adorned in imperial jade and gold silk",
    ],
    "expression": [
        "a commanding expression of authority",
        "a serene and knowing half-smile",
        "a grim determined set of the jaw",
        "mystical far-seeing eyes",
        "a melancholic gaze into the distance",
        "a menacing cold stare",
        "a hopeful forward-looking expression",
        "a contemplative furrowed brow",
    ],
    "bearing": [
        "stands with regal poise", "sits upon an ornate throne",
        "grips the hilt of the sword planted before them",
        "holds an ancient scroll unrolled in both hands",
        "rests one hand on a celestial globe",
        "crosses arms with quiet confidence",
    ],
}

_ACTION_DESCRIPTIONS = {
    "military": [
        "Leading a cavalry charge across an open battlefield, sword raised high, warhorse rearing up, banners of the kingdom snapping in the wind",
        "Standing atop the battlements directing the defence, siege engines approaching in the distance, archers taking positions along the walls",
        "Rallying the troops before dawn, torches flickering in the pre-battle darkness, armour glinting in the firelight",
        "Surveying the aftermath of battle on a smoky field, standards still flying, medics tending to the wounded behind",
    ],
    "diplomatic": [
        "Greeting a foreign ambassador in the grand hall, extending a hand of friendship, scribes recording the historic moment on parchment scrolls",
        "Negotiating a peace treaty at a round table, maps and documents spread before them, advisors leaning in to confer",
        "Receiving tribute from a delegation, exotic gifts laid out on silk cushions, courtiers murmuring in the background",
        "Signing a historic accord with a quill pen, witnesses from both nations standing solemnly behind",
    ],
    "construction": [
        "Surveying the construction of a grand cathedral, holding architectural blueprints, stonemasons and carpenters working on scaffolding behind",
        "Laying the foundation stone of a new city, ceremonial trowel in hand, crowds gathered to witness the occasion",
        "Inspecting the progress of a great aqueduct, engineers explaining the water flow, arches stretching into the distance",
        "Overseeing the raising of a monumental obelisk, ropes and pulleys straining, workers chanting in unison",
    ],
    "scientific": [
        "Studying star charts in an observatory tower, an astrolabe on the desk, moonlight streaming through the open dome above",
        "Conducting an alchemical experiment, coloured vapours rising from glass vessels, notes scribbled in a leather-bound journal",
        "Examining a rare manuscript under a magnifying lens, candlelight flickering, shelves of scrolls lining the walls",
        "Demonstrating a new mechanical invention to the court, gears and springs visible, courtiers leaning forward in fascination",
    ],
    "cultural": [
        "Presiding over a grand festival, musicians playing lutes and drums, dancers swirling in colourful silks before the throne",
        "Unveiling a monumental statue before a gathered crowd, the cloth falling away, gasps of admiration from the audience",
        "Leading a ceremonial procession through the city streets, flower petals strewn along the path, temple bells ringing",
        "Watching a theatrical performance from the royal box, actors on stage in elaborate masks, the audience enraptured",
    ],
    "exploration": [
        "Standing at the prow of a ship approaching an uncharted coastline, map unfurled on the deck, crew pointing toward the distant shore",
        "Examining a newly discovered land from a hilltop vantage, scouts sketching the terrain below, the expedition flag planted in the ground",
        "Consulting an ancient map in a torchlit tent, expedition gear scattered around, the sounds of a jungle night outside",
        "Gazing across a vast unexplored desert from a dune summit, camel train resting below, the path ahead marked on parchment",
    ],
    "crisis": [
        "Addressing the council in an emergency session, maps showing an approaching threat, advisors arguing urgently around the table",
        "Standing firm as floodwaters rise around the city walls, directing rescue efforts, citizens being evacuated in boats behind",
        "Confronting an assassin in the throne room, guards rushing forward, the leader standing unflinching before the blade",
        "Receiving urgent news from a breathless messenger, the court frozen in tense silence, a single candle flickering on the table",
    ],
}


# ===========================================================================
#  Description synthesizers
# ===========================================================================


def _pseudo_random_pick(choices: list[str], seed: str, index: int) -> str:
    """Deterministic pseudo-random pick reproducible by seed + index."""
    rng = random.Random(hash(seed) + index)
    return rng.choice(choices)


def _build_structure_description(category: str, style: str, condition: str,
                                 scale: str, seed: str) -> str:
    """Synthesize a structure description from component banks."""
    parts = [
        _pseudo_random_pick(_STRUCTURE_COMPONENTS["roof_material"], seed, 0),
        _pseudo_random_pick(_STRUCTURE_COMPONENTS["roof_shape"], seed, 1),
        _pseudo_random_pick(_STRUCTURE_COMPONENTS["stories"], seed, 2),
        _pseudo_random_pick(_STRUCTURE_COMPONENTS["feature"], seed, 3),
        _pseudo_random_pick(_STRUCTURE_COMPONENTS["entrance"], seed, 4),
        _pseudo_random_pick(_STRUCTURE_COMPONENTS["activity"], seed, 5),
    ]
    # Build a natural-sounding sentence
    desc = (
        f"A {scale} {condition.replace('_', ' ')} {style.replace('_', ' ')} "
        f"{category} building with {parts[0]}, {parts[1]}, {parts[2]}. "
        f"It has {parts[3]} and {parts[4]}, with {parts[5]}."
    )
    # Ensure meets min length
    while len(desc) < 60:
        extra = _pseudo_random_pick(_STRUCTURE_COMPONENTS["activity"], seed, 6 + len(desc))
        desc += f" {extra.capitalize()}."
    return desc[:400]


def _build_object_description(category: str, biome: str, season: str,
                              seed: str) -> str:
    """Synthesize an object description from component banks."""
    obj = _pseudo_random_pick(_OBJECT_COMPONENTS["object_type"], seed, 0)
    mat = _pseudo_random_pick(_OBJECT_COMPONENTS["material"], seed, 1)
    feat = _pseudo_random_pick(_OBJECT_COMPONENTS["feature"], seed, 2)

    desc = (
        f"{obj.capitalize()} with {mat}, showing {feat}, "
        f"set in a {biome.replace('_', ' ')} during {season}."
    )
    while len(desc) < 60:
        extra = _pseudo_random_pick(_OBJECT_COMPONENTS["object_type"], seed, 3 + len(desc))
        desc += f" Nearby {extra}."
    return desc[:400]


def _build_terrain_description(category: str, scale: str, material: str,
                               seed: str) -> str:
    """Synthesize a terrain description from component banks."""
    shape = _pseudo_random_pick(_TERRAIN_COMPONENTS["shape"], seed, 0)
    surf = _pseudo_random_pick(_TERRAIN_COMPONENTS["surface"], seed, 1)
    bg = _pseudo_random_pick(_TERRAIN_COMPONENTS["bg_hint"], seed, 2)

    desc = (
        f"A {scale} {material} {category}, shaped as {shape} with {surf}. "
        f"The feature {bg}."
    )
    while len(desc) < 60:
        extra = _pseudo_random_pick(_TERRAIN_COMPONENTS["surface"], seed, 3 + len(desc))
        desc += f" {extra.capitalize()}."
    return desc[:400]


def _build_unit_description(unit_type: str, seed: str) -> str:
    """Synthesize a unit description from component banks."""
    color = _pseudo_random_pick(_UNIT_COMPONENTS["clothing_color"], seed, 0)
    material = _pseudo_random_pick(_UNIT_COMPONENTS["clothing_material"], seed, 1)
    weapon = _pseudo_random_pick(_UNIT_COMPONENTS["weapon_detail"], seed, 2)
    posture = _pseudo_random_pick(_UNIT_COMPONENTS["posture"], seed, 3)
    feature = _pseudo_random_pick(_UNIT_COMPONENTS["feature"], seed, 4)
    build = _pseudo_random_pick(_UNIT_COMPONENTS["build"], seed, 5)

    desc = (
        f"A medieval {unit_type} in {color} {material}, carrying {weapon}, "
        f"{posture}. {build}, with {feature}."
    )
    while len(desc) < 60:
        extra = _pseudo_random_pick(_UNIT_COMPONENTS["clothing_color"], seed, 6 + len(desc))
        desc += f" Accented with {extra} details."
    return desc[:400]


def _build_leader_description(archetype: str, seed: str) -> str:
    """Synthesize a leader_description from component banks."""
    age = _pseudo_random_pick(_LEADER_COMPONENTS["age"], seed, 0)
    build = _pseudo_random_pick(_LEADER_COMPONENTS["build"], seed, 1)
    skin = _pseudo_random_pick(_LEADER_COMPONENTS["skin"], seed, 2)
    hair = _pseudo_random_pick(_LEADER_COMPONENTS["hair"], seed, 3)
    eyes = _pseudo_random_pick(_LEADER_COMPONENTS["eyes"], seed, 4)
    feature = _pseudo_random_pick(_LEADER_COMPONENTS["feature"], seed, 5)
    clothing = _pseudo_random_pick(_LEADER_COMPONENTS["clothing"], seed, 6)
    expression = _pseudo_random_pick(_LEADER_COMPONENTS["expression"], seed, 7)
    bearing = _pseudo_random_pick(_LEADER_COMPONENTS["bearing"], seed, 8)

    desc = (
        f"A {age} {archetype.replace('_', ' ')} — {build}, with {skin}, {hair}, "
        f"and {eyes}. {feature}, {clothing}, with {expression} as they {bearing}."
    )
    # Ensure meets 50-char minimum for leader_description
    while len(desc) < 80:
        extra = _pseudo_random_pick(_LEADER_COMPONENTS["clothing"], seed, 9 + len(desc))
        desc += f" {extra.capitalize()}."
    return desc[:800]


def _build_action_description(action_category: str, seed: str) -> str:
    """Pick an action description for the category."""
    choices = _ACTION_DESCRIPTIONS.get(action_category, ["A dramatic scene unfolding."])
    return _pseudo_random_pick(choices, seed, 0)


# ===========================================================================
#  Payload generators per family
# ===========================================================================


def _generate_structure_payloads(strategy: str, count: int) -> list[dict[str, Any]]:
    """Generate structure request payloads."""
    payloads: list[dict[str, Any]] = []

    if strategy == "combinatorial":
        combos = list(product(
            STRUCTURE_CATEGORIES, STRUCTURE_STYLES,
            STRUCTURE_CONDITIONS, STRUCTURE_SCALES,
        ))
        for cat, sty, con, scl in combos:
            seed = f"structure:{cat}:{sty}:{con}:{scl}"
            desc = _build_structure_description(cat, sty, con, scl, seed)
            payloads.append({
                "category": cat, "style": sty,
                "condition": con, "scale": scl,
                "description": desc,
            })
    elif strategy == "representative":
        # Pick interesting representative combos
        for cat in STRUCTURE_CATEGORIES:
            for sty in random.sample(STRUCTURE_STYLES, min(2, len(STRUCTURE_STYLES))):
                for con in random.sample(STRUCTURE_CONDITIONS, min(2, len(STRUCTURE_CONDITIONS))):
                    scl = random.choice(STRUCTURE_SCALES)
                    seed = f"structure:{cat}:{sty}:{con}:{scl}"
                    desc = _build_structure_description(cat, sty, con, scl, seed)
                    payloads.append({
                        "category": cat, "style": sty,
                        "condition": con, "scale": scl,
                        "description": desc,
                    })
    else:  # random
        for i in range(count):
            cat = random.choice(STRUCTURE_CATEGORIES)
            sty = random.choice(STRUCTURE_STYLES)
            con = random.choice(STRUCTURE_CONDITIONS)
            scl = random.choice(STRUCTURE_SCALES)
            seed = f"structure:random:{i}:{random.random()}"
            desc = _build_structure_description(cat, sty, con, scl, seed)
            payloads.append({
                "category": cat, "style": sty,
                "condition": con, "scale": scl,
                "description": desc,
            })

    return payloads


def _generate_object_payloads(strategy: str, count: int) -> list[dict[str, Any]]:
    """Generate object request payloads."""
    payloads: list[dict[str, Any]] = []

    if strategy == "combinatorial":
        combos = list(product(OBJECT_CATEGORIES, BIOMES, SEASONS))
        for cat, bio, sea in combos:
            seed = f"object:{cat}:{bio}:{sea}"
            desc = _build_object_description(cat, bio, sea, seed)
            payloads.append({
                "category": cat, "biome": bio,
                "season": sea, "description": desc,
            })
    elif strategy == "representative":
        for cat in OBJECT_CATEGORIES:
            for bio in random.sample(BIOMES, min(2, len(BIOMES))):
                for sea in random.sample(SEASONS, min(2, len(SEASONS))):
                    seed = f"object:{cat}:{bio}:{sea}"
                    desc = _build_object_description(cat, bio, sea, seed)
                    payloads.append({
                        "category": cat, "biome": bio,
                        "season": sea, "description": desc,
                    })
    else:  # random
        for i in range(count):
            cat = random.choice(OBJECT_CATEGORIES)
            bio = random.choice(BIOMES)
            sea = random.choice(SEASONS)
            seed = f"object:random:{i}:{random.random()}"
            desc = _build_object_description(cat, bio, sea, seed)
            payloads.append({
                "category": cat, "biome": bio,
                "season": sea, "description": desc,
            })

    return payloads


def _generate_terrain_payloads(strategy: str, count: int) -> list[dict[str, Any]]:
    """Generate terrain request payloads."""
    payloads: list[dict[str, Any]] = []

    if strategy == "combinatorial":
        combos = list(product(TERRAIN_CATEGORIES, TERRAIN_SCALES, TERRAIN_MATERIALS))
        for cat, scl, mat in combos:
            seed = f"terrain:{cat}:{scl}:{mat}"
            desc = _build_terrain_description(cat, scl, mat, seed)
            payloads.append({
                "category": cat, "scale": scl,
                "material": mat, "description": desc,
            })
    elif strategy == "representative":
        for cat in TERRAIN_CATEGORIES:
            for scl in TERRAIN_SCALES:
                for mat in random.sample(TERRAIN_MATERIALS, min(2, len(TERRAIN_MATERIALS))):
                    seed = f"terrain:{cat}:{scl}:{mat}"
                    desc = _build_terrain_description(cat, scl, mat, seed)
                    payloads.append({
                        "category": cat, "scale": scl,
                        "material": mat, "description": desc,
                    })
    else:  # random
        for i in range(count):
            cat = random.choice(TERRAIN_CATEGORIES)
            scl = random.choice(TERRAIN_SCALES)
            mat = random.choice(TERRAIN_MATERIALS)
            seed = f"terrain:random:{i}:{random.random()}"
            desc = _build_terrain_description(cat, scl, mat, seed)
            payloads.append({
                "category": cat, "scale": scl,
                "material": mat, "description": desc,
            })

    return payloads


def _generate_unit_payloads(strategy: str, count: int) -> list[dict[str, Any]]:
    """Generate unit request payloads."""
    payloads: list[dict[str, Any]] = []

    if strategy == "combinatorial":
        for utype in UNIT_TYPES:
            seed = f"unit:{utype}:1"
            desc = _build_unit_description(utype, seed)
            payloads.append({"unit_type": utype, "description": desc})
    elif strategy == "representative":
        for utype in UNIT_TYPES:
            for i in range(3):
                seed = f"unit:{utype}:{i}"
                desc = _build_unit_description(utype, seed)
                payloads.append({"unit_type": utype, "description": desc})
    else:  # random
        for i in range(count):
            utype = random.choice(UNIT_TYPES)
            seed = f"unit:random:{i}:{random.random()}"
            desc = _build_unit_description(utype, seed)
            payloads.append({"unit_type": utype, "description": desc})

    return payloads


def _generate_leader_splash_payloads(strategy: str, count: int) -> list[dict[str, Any]]:
    """Generate leader splash request payloads."""
    payloads: list[dict[str, Any]] = []

    if strategy == "combinatorial":
        combos = list(product(ARCHETYPES, CULTURES, TIMES_OF_DAY, MOODS))
        for arch, cul, tod, mood in combos:
            name = random.choice(LEADER_NAMES)
            seed = f"leader:splash:{arch}:{cul}:{tod}:{mood}"
            desc = _build_leader_description(arch, seed)
            payloads.append({
                "asset_type": "splash",
                "leader_name": name,
                "leader_description": desc,
                "archetype": arch,
                "culture": cul,
                "time_of_day": tod,
                "mood": mood,
            })
    elif strategy == "representative":
        for arch in ARCHETYPES:
            for cul in random.sample(CULTURES, min(2, len(CULTURES))):
                tod = random.choice(TIMES_OF_DAY)
                mood = random.choice(MOODS)
                name = random.choice(LEADER_NAMES)
                seed = f"leader:splash:{arch}:{cul}:{tod}:{mood}"
                desc = _build_leader_description(arch, seed)
                payloads.append({
                    "asset_type": "splash",
                    "leader_name": name,
                    "leader_description": desc,
                    "archetype": arch,
                    "culture": cul,
                    "time_of_day": tod,
                    "mood": mood,
                })
    else:  # random
        for i in range(count):
            arch = random.choice(ARCHETYPES)
            cul = random.choice(CULTURES)
            tod = random.choice(TIMES_OF_DAY)
            mood = random.choice(MOODS)
            name = random.choice(LEADER_NAMES)
            seed = f"leader:splash:random:{i}:{random.random()}"
            desc = _build_leader_description(arch, seed)
            payloads.append({
                "asset_type": "splash",
                "leader_name": name,
                "leader_description": desc,
                "archetype": arch,
                "culture": cul,
                "time_of_day": tod,
                "mood": mood,
            })

    return payloads


def _generate_leader_action_payloads(strategy: str, count: int) -> list[dict[str, Any]]:
    """Generate leader action request payloads.

    These require a leader_id, so they are designed for the leader workflow
    chain (splash first, then action referencing the leader_id).
    """
    payloads: list[dict[str, Any]] = []

    if strategy in ("combinatorial", "representative"):
        combos = []
        for ac in ACTION_CATEGORIES:
            for cul in random.sample(CULTURES, min(2, len(CULTURES))):
                tod = random.choice(TIMES_OF_DAY)
                mood = random.choice(MOODS)
                combos.append((ac, cul, tod, mood))

        for ac, cul, tod, mood in combos:
            arch = random.choice(ARCHETYPES)
            name = random.choice(LEADER_NAMES)
            seed = f"leader:action:{ac}:{cul}:{tod}:{mood}"
            desc = _build_leader_description(arch, seed)
            act_desc = _build_action_description(ac, seed)
            payloads.append({
                "asset_type": "action",
                "leader_name": name,
                "leader_description": desc,
                "archetype": arch,
                "culture": cul,
                "time_of_day": tod,
                "mood": mood,
                "action_category": ac,
                "action_description": act_desc,
                "leader_id": "REPLACE_WITH_LEADER_ID",
            })
    else:  # random
        for i in range(count):
            ac = random.choice(ACTION_CATEGORIES)
            arch = random.choice(ARCHETYPES)
            cul = random.choice(CULTURES)
            tod = random.choice(TIMES_OF_DAY)
            mood = random.choice(MOODS)
            name = random.choice(LEADER_NAMES)
            seed = f"leader:action:random:{i}:{random.random()}"
            desc = _build_leader_description(arch, seed)
            act_desc = _build_action_description(ac, seed)
            payloads.append({
                "asset_type": "action",
                "leader_name": name,
                "leader_description": desc,
                "archetype": arch,
                "culture": cul,
                "time_of_day": tod,
                "mood": mood,
                "action_category": ac,
                "action_description": act_desc,
                "leader_id": "REPLACE_WITH_LEADER_ID",
            })

    return payloads


def _generate_background_tile_payloads(strategy: str, count: int) -> list[dict[str, Any]]:
    """Generate background tile request payloads."""
    payloads: list[dict[str, Any]] = []

    if strategy == "combinatorial":
        for tt in BACKGROUND_TILE_TYPES:
            payloads.append({"tile_type": tt})
    elif strategy == "representative":
        for tt in BACKGROUND_TILE_TYPES:
            payloads.append({"tile_type": tt})
    else:  # random
        for i in range(count):
            tt = random.choice(BACKGROUND_TILE_TYPES)
            payloads.append({"tile_type": tt})

    return payloads


# ===========================================================================
#  Payload generator registry
# ===========================================================================

GENERATORS: dict[str, Any] = {
    "structure": _generate_structure_payloads,
    "object": _generate_object_payloads,
    "terrain": _generate_terrain_payloads,
    "unit": _generate_unit_payloads,
    "leader_splash": _generate_leader_splash_payloads,
    "leader_action": _generate_leader_action_payloads,
    "background_tile": _generate_background_tile_payloads,
}

ALL_FAMILIES = list(GENERATORS.keys())


# ===========================================================================
#  Output formatters
# ===========================================================================


def _format_json(payloads: list[dict[str, Any]]) -> str:
    """Format as pretty-printed JSON array."""
    return json.dumps(payloads, indent=2, ensure_ascii=False)


def _format_jsonl(payloads: list[dict[str, Any]]) -> str:
    """Format as JSON lines (one object per line)."""
    return "\n".join(json.dumps(p, ensure_ascii=False) for p in payloads)


def _format_curl(payloads: list[dict[str, Any]], base_url: str = "http://localhost:8000") -> str:
    """Format as a shell script with curl commands."""
    lines: list[str] = ["#!/bin/bash", "# Generated API test payloads", ""]
    endpoint_map = {
        "structure": "/structure",
        "object": "/object",
        "terrain": "/terrain",
        "unit": "/unit",
        "background_tile": "/background_tile",
        "leader_splash": "/leader",
        "leader_action": "/leader",
    }

    for i, p in enumerate(payloads):
        # Determine endpoint from payload shape
        if "tile_type" in p and "category" not in p and "unit_type" not in p:
            endpoint = "/background_tile"
        elif "unit_type" in p:
            endpoint = "/unit"
        elif "asset_type" in p:
            endpoint = "/leader"
        elif "category" in p and "scale" in p and "material" in p:
            endpoint = "/terrain"
        elif "category" in p and "biome" in p:
            endpoint = "/object"
        elif "category" in p and "style" in p:
            endpoint = "/structure"
        else:
            endpoint = "/structure"  # fallback

        # Strip internal fields
        clean = {k: v for k, v in p.items() if not k.startswith("_")}
        json_str = json.dumps(clean, ensure_ascii=False)
        escaped = json_str.replace("'", "'\\''")
        lines.append(f"# Payload #{i + 1}: {endpoint}")
        lines.append(f"curl -s -X POST '{base_url}{endpoint}' \\")
        lines.append(f"  -H 'Content-Type: application/json' \\")
        lines.append(f"  -d '{escaped}'")
        lines.append("")

    return "\n".join(lines)


# ===========================================================================
#  CLI
# ===========================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate diverse API request payloads for all asset families.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/generate_payloads.py --strategy representative --output payloads.json
  python scripts/generate_payloads.py --family leader --count 200 --strategy random
  python scripts/generate_payloads.py --family structure --strategy combinatorial --stdout
  python scripts/generate_payloads.py --format curl --output test.sh
        """,
    )

    parser.add_argument(
        "--family",
        choices=ALL_FAMILIES + ["all"],
        default="all",
        help="Asset family to generate payloads for (default: all)",
    )
    parser.add_argument(
        "--strategy",
        choices=["combinatorial", "representative", "random"],
        default="representative",
        help="Coverage strategy (default: representative)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of payloads for 'random' strategy (default: 50)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "jsonl", "curl"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Force output to stdout even when --output is set",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for curl format (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible generation",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Seed for reproducibility
    if args.seed is not None:
        random.seed(args.seed)

    # Determine families to generate
    if args.family == "all":
        families = ALL_FAMILIES
    else:
        families = [args.family]

    # Generate payloads
    all_payloads: list[dict[str, Any]] = []
    for family in families:
        generator = GENERATORS.get(family)
        if generator is None:
            print(f"⚠ Unknown family '{family}', skipping", file=sys.stderr)
            continue
        payloads = generator(args.strategy, args.count)
        all_payloads.extend(payloads)

    if not all_payloads:
        print("✗ No payloads generated.", file=sys.stderr)
        sys.exit(1)

    # Format output
    if args.format == "json":
        output = _format_json(all_payloads)
    elif args.format == "jsonl":
        output = _format_jsonl(all_payloads)
    elif args.format == "curl":
        output = _format_curl(all_payloads, args.base_url)
    else:
        output = _format_json(all_payloads)

    # Write output
    if args.stdout or args.output is None:
        print(output)
    else:
        args.output.write_text(output, encoding="utf-8")
        print(f"✓ {len(all_payloads)} payloads written to {args.output}", file=sys.stderr)

    # Stats
    print(
        f"✓ Generated {len(all_payloads)} payloads across {len(families)} families "
        f"(strategy={args.strategy}, format={args.format})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()

"""Assembles final prompts from request fields and enum injection maps.

The client never writes raw prompts. The server builds them from structured
enums (archetype, culture, time_of_day, mood, action_category) plus the
leader_description and action_description prose fields.

Prompt templates live in ``config/prompt_templates.json`` and use
``{placeholder}`` variables.  This module prepares the keyword arguments
(enum-injected prose + user descriptions) and calls ``render()``.
"""

from src.prompt_templates import render as _render
from .models import LeaderRequest

# ---------------------------------------------------------------------------
# Enum injection maps  (hand-crafted, rich prose per value)
# ---------------------------------------------------------------------------

ARCHETYPE = {
    "warrior_queen": (
        "standing proudly, martial bearing, armor and weapons prominent, "
        "battle-hardened confidence"
    ),
    "warrior_king": (
        "commanding presence, battle-scarred dignity, weapon in hand, "
        "military authority"
    ),
    "philosopher_king": (
        "seated or standing in contemplation, scrolls or scientific instruments "
        "nearby, learned wisdom"
    ),
    "merchant_prince": (
        "calculating gaze, surrounded by symbols of wealth and trade, "
        "shrewd intelligence"
    ),
    "spiritual_leader": (
        "mystical aura, religious or natural symbols, ceremonial pose, "
        "transcendent connection"
    ),
    "diplomat": (
        "open posture, formal court or negotiating setting, measured diplomacy"
    ),
    "tyrant": (
        "imposing dominance, deep shadows, iron grip on throne or weapon, "
        "intimidating power"
    ),
    "visionary": (
        "gazing toward horizon, plans or blueprints in hand, forward-looking ambition"
    ),
}

CULTURE = {
    "ancient_egyptian": (
        "a vast sandstone temple with towering hieroglyph-carved pillars, "
        "gold and lapis lazuli accents, bronze braziers burning incense, "
        "desert beyond colonnades"
    ),
    "classical_greek": (
        "a marble temple with corinthian columns, olive groves on the hillside, "
        "Aegean blue sea in the distance, white stone catching golden light"
    ),
    "roman_imperial": (
        "a grand travertine forum with domes and aqueducts, crimson banners "
        "with gold eagles, paved stone plaza, imperial majesty"
    ),
    "medieval_european": (
        "a stone castle great hall with oak beams, heraldic tapestries, iron "
        "chandeliers, stained glass catching colored light through tall windows"
    ),
    "east_asian_imperial": (
        "a magnificent jade and red lacquer palace interior, silk screens with "
        "landscape paintings, cherry blossoms visible through moon gates, misty "
        "mountains beyond"
    ),
    "mesopotamian": (
        "a mud-brick ziggurat temple complex, bronze and lapis lazuli ornamentation, "
        "reed marshes and twin rivers visible in the distance"
    ),
    "mesoamerican": (
        "a stone step pyramid amid dense jungle, obsidian mirrors, jade ornaments "
        "and quetzal feather adornments, carved stone stelae in the foreground"
    ),
    "nordic_viking": (
        "a timber longhouse with carved dragon posts, fur-draped walls, iron "
        "braziers casting warm light, fjord waters and northern lights through "
        "the smoke hole above"
    ),
    "persian": (
        "a blue-tiled palace overlooking cypress gardens and reflecting pools, "
        "silk curtains billowing in mountain breeze, snow-capped peaks in the distance"
    ),
    "sub_saharan_african": (
        "a grand mud-brick structure with carved wooden beams, gold and ivory "
        "ornaments, baobab trees on the savanna horizon, richly woven textile hangings"
    ),
    "south_asian": (
        "a sandstone temple complex with intricate carvings, lotus ponds reflecting "
        "the architecture, gold jewelry catching warm sunlight, monsoon clouds "
        "gathering dramatically"
    ),
    "islamic_golden_age": (
        "a domed observatory with intricate geometric tile patterns, brass "
        "astrolabes on pedestals, parchment manuscripts on shelves, arabesque "
        "arches framing a star-filled desert sky"
    ),
}

TIME_OF_DAY = {
    "dawn": (
        "first light of dawn breaking over the horizon, cool blue shadows "
        "giving way to warm gold, mist rising from the ground"
    ),
    "golden_hour": (
        "low golden sunlight casting long dramatic shadows, warm amber glow "
        "suffusing everything, dust motes dancing in light beams"
    ),
    "midday": (
        "harsh clear sunlight from overhead, strong contrast with deep black "
        "shadows, bright cloudless sky"
    ),
    "twilight": (
        "purple and orange sky at the boundary of day and night, torches and "
        "braziers being lit, the first stars appearing"
    ),
    "night": (
        "deep night with moonlight streaming through openings, warm firelight "
        "from torches and braziers, stars visible overhead"
    ),
    "storm": (
        "dark brooding storm clouds massing overhead, dramatic lightning "
        "illuminating the scene in flashes, wind whipping through"
    ),
}

MOOD = {
    "triumphant": (
        "expression of hard-won victory, proud celebratory atmosphere, head held high"
    ),
    "wise_serene": (
        "expression of profound calm wisdom, peaceful dignified atmosphere, "
        "gentle knowing gaze"
    ),
    "grim_determined": (
        "expression of steely unbreakable resolve, tense charged atmosphere, "
        "jaw set firm"
    ),
    "mystical": (
        "expression of spiritual transcendence, ethereal otherworldly atmosphere, "
        "eyes seeing beyond the visible"
    ),
    "melancholic": (
        "expression of bittersweet reflection, quiet somber atmosphere, heavy "
        "with history and memory"
    ),
    "menacing": (
        "expression of cold calculated power, oppressive intimidating atmosphere, "
        "danger crackling in the air"
    ),
    "hopeful": (
        "expression of optimistic vision, bright aspirational atmosphere, looking "
        "toward possibility"
    ),
    "contemplative": (
        "expression of deep thought, quiet introspective atmosphere, weighing "
        "profound decisions"
    ),
}

ACTION_CATEGORY = {
    "military": (
        "dynamic action composition, weapons drawn, battlefield context with "
        "smoke and banners, cavalry and infantry in motion"
    ),
    "diplomatic": (
        "formal court or neutral meeting ground, treaty documents on the table, "
        "multiple parties present, ceremonial exchange unfolding"
    ),
    "construction": (
        "monument or great building in progress, workers on scaffolding, stone "
        "blocks being lifted by cranes, immense civic scale"
    ),
    "scientific": (
        "instruments and scrolls in an observatory or study, moment of breakthrough "
        "discovery, intellectual excitement in the air"
    ),
    "cultural": (
        "ceremony or festival with rich ritual elements, artistic performance "
        "in progress, gathered audience, cultural pageantry"
    ),
    "exploration": (
        "newly discovered territory unfolding before them, map unfurled on a "
        "stone table, scouts pointing ahead, vista of unknown lands"
    ),
    "crisis": (
        "imminent threat approaching, the leader responding to emergency, tense "
        "urgent body language, decisive action required"
    ),
}

# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------
# Style directives live exclusively in config/prompt_templates.json —
# the Python layer only passes enum-injected prose as keyword arguments
# to ``_render()``.  No hardcoded style directives.
# ---------------------------------------------------------------------------

def build_splash_prompt(req: LeaderRequest) -> str:
    return _render(
        "leader_splash",
        leader_description=req.leader_description.strip(),
        archetype=ARCHETYPE[req.archetype],
        culture=CULTURE[req.culture],
        time_of_day=TIME_OF_DAY[req.time_of_day],
        mood=MOOD[req.mood],
    )


def build_profile_prompt(req: LeaderRequest) -> str:
    # Composition directives (face filling the frame, headpiece visible) live
    # in the leader_profile template — see config/prompt_templates.json.
    return _render(
        "leader_profile",
        leader_description=req.leader_description.strip(),
        mood=MOOD[req.mood],
    )


def build_action_prompt(req: LeaderRequest) -> str:
    return _render(
        "leader_action",
        leader_description=req.leader_description.strip(),
        action_description=req.action_description.strip() if req.action_description else "",
        culture=CULTURE[req.culture],
        time_of_day=TIME_OF_DAY[req.time_of_day],
        mood=MOOD[req.mood],
        action_category=ACTION_CATEGORY[req.action_category] if req.action_category else "",
    )


def build_multi_action_prompt(
    req: LeaderRequest,
    leader_descriptions: list[str],
    leader_names: list[str],
) -> str:
    """Build a prompt for a multi-leader action scene.

    Composes all leader descriptions into a single prompt describing
    their interaction within the action scene.
    """
    if len(leader_descriptions) == 1:
        char_part = leader_descriptions[0].strip()
    elif len(leader_descriptions) == 2:
        char_part = (
            f"two leaders interacting: "
            f"{leader_names[0]}, {leader_descriptions[0].strip()}, "
            f"and {leader_names[1]}, {leader_descriptions[1].strip()}"
        )
    else:
        named = ", ".join(
            f"{name}, {desc.strip()}"
            for name, desc in zip(leader_names, leader_descriptions)
        )
        char_part = f"multiple leaders: {named}"

    return _render(
        "leader_action",
        leader_description=char_part,
        action_description=req.action_description.strip() if req.action_description else "",
        culture=CULTURE[req.culture],
        time_of_day=TIME_OF_DAY[req.time_of_day],
        mood=MOOD[req.mood],
        action_category=ACTION_CATEGORY[req.action_category] if req.action_category else "",
    )


def build_prompt(req: LeaderRequest) -> str:
    """Route to the correct builder based on asset_type."""
    builders = {
        "splash":  build_splash_prompt,
        "profile": build_profile_prompt,
        "action":  build_action_prompt,
    }
    return builders[req.asset_type](req)
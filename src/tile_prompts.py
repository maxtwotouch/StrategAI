"""Assembles final prompts from request fields and enum injection maps
for the structure, object, and terrain pipelines.

Mirrors the leader_prompts.py pattern: the client never writes raw
prompts. The server builds them from structured enums plus the
free-form description field, then wraps them in a template from
prompt_templates.json.
"""

import json
import os
from pathlib import Path

from .tile_models import (
    StructureRequest, ObjectRequest, TerrainRequest,
)

# ---------------------------------------------------------------------------
#  Prompt template loader
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATES_PATH = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "config" / "prompt_templates.json"

_templates: dict[str, str] | None = None


def _load_templates() -> dict[str, str]:
    global _templates
    if _templates is None:
        with open(_PROMPT_TEMPLATES_PATH) as fh:
            data = json.load(fh)
        _templates = data["templates"]
    return _templates


def load_template(key: str) -> str:
    """Return the raw template string for a tile family.

    Keys: ``"structure"``, ``"object"``, ``"terrain"``.
    """
    return _load_templates()[key]


# ===========================================================================
#  Structure injection maps
# ===========================================================================

STRUCTURE_CATEGORY = {
    "fortification": (
        "a sturdy defensive structure with crenellated battlements, arrow slits, "
        "thick stone walls, watchtower, military functionality"
    ),
    "production": (
        "a working industrial building with chimney smoke, visible tools and "
        "raw materials outside, functional workshop architecture"
    ),
    "housing": (
        "a lived-in residential building with shuttered windows, chimney, "
        "small garden or yard, domestic warmth and character"
    ),
    "sacred": (
        "a reverent religious building with stained glass, spire or steeple, "
        "ceremonial entrance, spiritual architectural grandeur"
    ),
}

STRUCTURE_STYLE = {
    "nordic_wooden": (
        "dark timber construction with carved dragon-head gables, steep "
        "shingled roof, iron hinges and fittings, Norse craftsmanship"
    ),
    "anglo_saxon_stone": (
        "rough-hewn stone walls with timber framing, thick thatched roof, "
        "low profile, wattle-and-daub accents, early medieval English vernacular"
    ),
    "norman_romanesque": (
        "heavy stone construction with round arches, thick pillars, small "
        "deep-set windows, fortress-like solidity, chevron ornament"
    ),
    "gothic": (
        "pointed arches soaring upward, flying buttresses, tall spires, "
        "ornate stone tracery, large rose window, vertical emphasis"
    ),
    "mediterranean": (
        "warm terracotta roof tiles, whitewashed stone or stucco walls, "
        "arched colonnades and loggias, cypress trees nearby, sun-baked palette"
    ),
    "slavic_timber": (
        "horizontal log construction with notched corners, carved wooden "
        "trim and window frames, steep shingled roofs, onion-dome influences"
    ),
    "moorish": (
        "horseshoe arches, intricate geometric tile patterns, carved stucco "
        "arabesques, interior courtyard implied, domed roofs with tile work"
    ),
}

STRUCTURE_CONDITION = {
    "pristine": (
        "freshly built, clean stonework with bright mortar, new timber showing "
        "no weathering, sharp edges and crisp details"
    ),
    "weathered": (
        "aged stone with patches of moss and lichen, faded and greyed timber, "
        "subtle settlement cracks, lived-in character, slightly worn edges"
    ),
    "ruined": (
        "collapsed roof sections exposing beams, ivy and climbing plants covering "
        "walls, broken or missing windows, scattered rubble and fallen stones at the base"
    ),
    "under_construction": (
        "wooden scaffolding lashed to partially built walls, piles of cut stone "
        "and timber on the ground, workers' tools and rope, exposed structural framing"
    ),
    "fortified": (
        "extra defensive additions — reinforced iron-bound doors, added crenellations, "
        "wooden barricades and sharpened stakes, hurried military practicality"
    ),
}

STRUCTURE_SCALE = {
    "small": (
        "compact single-room footprint, modest proportions, humble village scale, "
        "simple unpretentious architecture"
    ),
    "medium": (
        "substantial multi-room building, prominent in a village or town setting, "
        "balanced proportions with architectural detail"
    ),
    "large": (
        "imposing grand structure that dominates the landscape, monumental scale, "
        "complex architecture with multiple sections and towers"
    ),
}


# ===========================================================================
#  Object injection maps
# ===========================================================================

OBJECT_CATEGORY = {
    "vegetation": (
        "a natural living plant with organic form, textured bark or stems, "
        "leaves or needles, rooted in the ground"
    ),
    "geological": (
        "a natural rock formation with textured stone surface, mineral colouring, "
        "angular or weathered shape, heavy grounded presence"
    ),
    "rural_props": (
        "a hand-crafted countryside object made of wood, stone, or metal, "
        "functional rustic design, weathered by outdoor exposure"
    ),
    "urban_props": (
        "a crafted town object with refined workmanship, iron or wood construction, "
        "decorative or functional civic purpose"
    ),
    "debris": (
        "scattered broken remnants, damaged and abandoned, fragments and wreckage, "
        "signs of past destruction or decay"
    ),
}

BIOME = {
    "temperate_forest": (
        "deciduous woodland context with rich soil, leaf litter, ferns, varied greens"
    ),
    "taiga": (
        "boreal conifer forest context with pale soil, pine needles, lichen, muted greens"
    ),
    "desert": (
        "arid desert context with sand, dry cracked earth, sparse scrub, warm earth tones"
    ),
    "swamp": (
        "wetland marsh context with dark mud, still water, reeds, twisted roots, murky tones"
    ),
    "mountain": (
        "alpine rocky context with exposed stone, scree, thin soil, sparse vegetation"
    ),
    "coastal": (
        "seaside context with sand, driftwood, salt-worn textures, bleached tones"
    ),
    "grassland": (
        "open grassy plain with wildflowers, gently rolling terrain, scattered herbs, "
        "golden-green palette, big sky atmosphere"
    ),
}

SEASON = {
    "spring": (
        "fresh green growth, new leaves unfurling, blossoms, bright and verdant"
    ),
    "summer": (
        "full mature foliage, dry ground, warm tones, peak growth and ripeness"
    ),
    "autumn": (
        "orange and red turning leaves, bare branches appearing, fallen leaves "
        "on ground, harvest tones"
    ),
    "winter": (
        "bare dormant branches, snow cover, ice, muted browns and greys, stark silhouette"
    ),
}


# ===========================================================================
#  Terrain injection maps
# ===========================================================================

TERRAIN_CATEGORY = {
    "hill": (
        "a rounded mound or hill rising from the base plane, soft organic "
        "contour, natural elevation feature"
    ),
    "slope": (
        "a gradual inclined ramp sloping upward from one edge to the other, "
        "directional grade change, stepped or smooth transition"
    ),
    "cliff": (
        "a sheer vertical rock face with a sharp drop-off, exposed stone strata "
        "on the vertical face, flat or sloped top surface"
    ),
    "ridge": (
        "a narrow elevated spine connecting higher points, ridgeline with slopes "
        "falling away on both sides, jagged or rounded crest"
    ),
    "depression": (
        "a sunken pit or bowl-shaped hollow below the base plane, concave form, "
        "descending below grade level"
    ),
}

TERRAIN_SCALE = {
    "low": (
        "subtle barely-perceptible elevation change, just 1-2 pixels of height, "
        "small footprint, gentle barely-there feature"
    ),
    "medium": (
        "noticeable elevation change of 3-4 pixels, moderate footprint occupying "
        "most of the tile, distinct landform"
    ),
    "high": (
        "prominent dramatic elevation of 5+ pixels, fills the tile with towering "
        "presence, dominant landscape feature"
    ),
}

TERRAIN_MATERIAL = {
    "earthen": (
        "grass-topped soil with exposed dirt on steeper faces, green surface "
        "with brown earth edges, pastoral character"
    ),
    "sandy": (
        "loose sand with granular texture, wind-rippled surface, warm beige and "
        "tan tones, soft edges and curves"
    ),
    "rocky": (
        "grey stone with visible strata lines, scattered small boulders on the "
        "surface, hard angular edges, mineral tones"
    ),
    "snowy": (
        "white snow cover on the top surface with darker ground exposed on "
        "steep faces, crisp cold palette, ice patches"
    ),
    "muddy": (
        "dark wet earth with a slick sheen, soft squelchy contours, deep brown "
        "tones, small puddles in depressions"
    ),
}


# ===========================================================================
#  Prompt builders
# ===========================================================================

def build_structure_prompt(req: StructureRequest) -> str:
    inner = ", ".join([
        f"a {STRUCTURE_SCALE[req.scale]} {STRUCTURE_CATEGORY[req.category]}",
        f"in {STRUCTURE_STYLE[req.style]} style",
        STRUCTURE_CONDITION[req.condition],
        req.description.strip(),
    ])
    template = load_template("structure")
    return template.replace("{PROMPT_HERE}", inner)


def build_object_prompt(req: ObjectRequest) -> str:
    inner = ", ".join([
        OBJECT_CATEGORY[req.category],
        f"in a {BIOME[req.biome]}",
        f"during {SEASON[req.season]}",
        req.description.strip(),
    ])
    template = load_template("object")
    return template.replace("{PROMPT_HERE}", inner)


def build_terrain_prompt(req: TerrainRequest) -> str:
    inner = ", ".join([
        f"a {TERRAIN_SCALE[req.scale]} {TERRAIN_CATEGORY[req.category]}",
        f"with {TERRAIN_MATERIAL[req.material]} material",
        req.description.strip(),
    ])
    template = load_template("terrain")
    return template.replace("{PROMPT_HERE}", inner)

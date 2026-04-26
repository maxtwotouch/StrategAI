#!/usr/bin/env python3
# generate_medieval_prompt_pack_flux2.py

import argparse
import json
import random
import itertools
from pathlib import Path
from collections import defaultdict

OBJECT_PROMPT_TEMPLATE = (
    "<sks> front view overhead shot elevated shot medium shot. "
    "The structure faces the camera straight from the front. "
    "The structure should flow into any inserted background. "
    "Isolate the object on a plain white background, only focusing on the specified object. "
    "{PROMPT_HERE}. "
    "Pixel art 16x16 for game tile assets, crisp pixel edges, no anti-aliasing, centered single asset on white. "
    "Grounded, stable perspective, no floating objects."
)

TILE_PROMPT_TEMPLATE = (
    "<sks> front view overhead shot elevated shot medium shot. "
    "The entire image must be one single 16x16 pixel art tile that fully fills the frame with continuous texture. "
    "No borders, no centered composition, no empty space. "
    "Generate one cohesive tile that can be seamlessly repeated in all directions. "
    "No disruptive features or objects touching the outermost pixel edges. "
    "16x16 pixel art {material} texture with {texture_details}, no rocks or objects near the edges. "
    "Crisp pixel edges, consistent top-down game tile style, perfect seamless tiling, simple and readable at small scale."
)

# ------------------------------------------------------------
# STRUCTURES (updated with mystical/wizarding content)
# ------------------------------------------------------------
STRUCTURE_TYPES = [
    "timber-framed cottage",
    "stone cottage",
    "farm house",
    "large farm house",
    "inn building",
    "market hall",
    "town hall",
    "blacksmith workshop",
    "master blacksmith forge hall",
    "sawmill",
    "riverside sawmill",
    "watermill",
    "windmill",
    "granary",
    "straight-down mine entrance shaft",
    "reinforced straight-down mine headframe",
    "ore smelter building",
    "quarry outpost",
    "watchtower",
    "gatehouse",
    "barracks",
    "castle keep",
    "castle wall tower",
    "chapel",
    "monastery building",
    "volcanic extraction outpost",
    "volcano caldera mining station",
    "steampunk workshop with brass piping",
    "gear-accented foundry hall",

    # NEW mystical structures
    "wizarding tower",
    "arcane observatory tower",
    "rune-etched mage spire",
    "enchanted library tower",
    "alchemist laboratory tower",
]

STRUCTURE_THEMES = [
    "homely village restoration",
    "cozy harvest season",
    "frontier outpost survival",
    "feudal military readiness",
    "merchant prosperity district",
    "scholarly monastic order",
    "sacred pilgrimage route",
    "malevolent blight influence",
    "ominous cursed quarter",
    "post-siege reconstruction",
    "ashen volcanic frontier",
    "steampunk industrial expansion",
    "mystical arcane enclave",  # NEW
    "wizarding scholarly district",  # NEW
]

THEME_MOTIFS = [
    "careful repairs and patched materials",
    "reinforced foundations and defensive practicality",
    "trade-focused storage additions",
    "ritual markings and weathered iconography",
    "smoke-stained chimneys and heavy use marks",
    "ash dust buildup and heat-worn surfaces",
    "brass fittings and riveted mechanical accents",
    "aged masonry seams and timber bracing",
    "glowing rune inlays and arcane sigils",   # NEW
    "astronomical instruments and spellcraft details",  # NEW
]

ARCHITECTURAL_PERSONALITY = [
    "humble and practical",
    "sturdy and fortified",
    "ornate but functional",
    "improvised frontier engineering",
    "ritually maintained",
    "industrially retrofitted",
    "mystical but grounded",   # NEW
]

DETAIL_LEVELS = ["low detail", "medium detail", "high detail", "ornate detail"]

STRUCTURAL_COMPLEXITY = [
    "simple footprint",
    "multi-wing footprint",
    "courtyard layout",
    "reinforced buttresses",
    "layered rooflines",
    "asymmetrical annexes",
    "industrial annex modules",
    "vertical spire layering",  # NEW (for wizard towers)
]

MATERIALS_STRUCTURE = [
    "oak timber and plaster",
    "rough stone masonry",
    "brick and timber hybrid",
    "aged limestone blocks",
    "dark wood beams with stone base",
    "iron braces and chain supports",
    "brass and iron mechanical accents",
    "volcanic basalt stone and reinforced timber",
    "rune-carved stone and reinforced masonry",  # NEW
]

CONDITIONS_STRUCTURE = [
    "well-maintained",
    "weathered",
    "war-damaged",
    "partially ruined",
    "heavily used industrial wear",
    "heat-scorched but operational",
    "well-kept arcane condition",  # NEW
]

PALETTES_STRUCTURE = [
    "warm muted palette",
    "earthy palette",
    "cool medieval palette",
    "desaturated retro palette",
    "high contrast retro palette",
    "smoky sepia palette",
    "ash-and-ember palette",
    "mystic violet-cyan palette",  # NEW
]

# ------------------------------------------------------------
# NATURE OBJECTS (updated with wheat fields)
# ------------------------------------------------------------
NATURE_OBJECTS = [
    "ancient oak tree",
    "windswept pine tree",
    "lightning-scarred dead tree",
    "gnarled forest tree cluster",
    "thorny bramble mass",
    "jagged boulder",
    "boulder group",
    "broken rock cluster",
    "reeds cluster",
    "grass tuft cluster",
    "large hill",
    "broad plateau hill",
    "rounded ridge hill",
    "volcanic rock spire",
    "charred stump cluster",

    # NEW wheat/farming nature objects
    "wheat field patch",
    "harvest-ready wheat field",
    "wind-swept wheat cluster",
]

NATURE_DRAMA = [
    "storm-battered silhouette",
    "wind-carved shape language",
    "ancient growth with twisted massing",
    "battle-scarred surface forms",
    "volcanic weathering and fracture lines",
    "ominous high-contrast shape breakup",
    "wind-rippled crop flow",  # NEW (for wheat)
]

NATURE_COMPLEXITY = [
    "simple silhouette",
    "layered silhouette",
    "dense readable forms",
    "weathered rough form",
]

MATERIALS_NATURE = [
    "lush foliage and bark",
    "dark evergreen foliage",
    "dry bark and sparse foliage",
    "mossy stone texture",
    "packed earth and dry grass",
    "volcanic basalt texture",
    "golden wheat stalk texture",  # NEW
]

CONDITIONS_NATURE = [
    "healthy growth",
    "weathered growth",
    "overgrown",
    "storm-worn",
    "heat-scorched",
    "harvest-ready condition",  # NEW
]

PALETTES_NATURE = [
    "earthy palette",
    "cool medieval palette",
    "desaturated retro palette",
    "high contrast retro palette",
    "storm-muted palette",
    "ash-and-ember palette",
    "golden harvest palette",  # NEW
]

HILL_TOP_SHAPES = ["wide flat top", "broad rounded top", "wide plateau top"]
HILL_SIDE_SMOOTHNESS = ["soft smooth side slopes", "medium smooth side slopes", "controlled semi-sharp side slopes"]
HILL_SEAM_INTEGRITY = [
    "slope mass tapers cleanly before tile boundaries",
    "side slopes preserve edge readability near tile seams",
    "outer silhouette avoids seam collisions and edge tangents",
    "base footprint remains map-placeable without seam artifacts",
]

NATURE_TILE_COMPAT_CLAUSE = (
    "Composed as a clean game asset silhouette with tile-grid aware proportions, "
    "readable placement footprint, and seam-safe outer contour for top-down RPG maps."
)

# ------------------------------------------------------------
# BACKGROUND TILE VARIANTS
# ------------------------------------------------------------
TILE_VARIANTS = [
    ("sand", "soft grain, subtle micro-dunes, gentle color noise, faint dithering"),
    ("sand", "dry fine grain clusters, smooth dune ripples, low-contrast color noise, subtle dithering"),
    ("grass", "short blade clusters, earthy undertone, mild color noise, subtle dithering"),
    ("lush grass", "dense micro-blade clusters, soft green variation, gentle color noise, faint dithering"),
    ("autumn grass", "dry yellow-green blade texture, muted tonal shifts, subtle dithering"),
    ("swamp grass", "damp mossy grain, muddy-green variation, restrained noise, faint dithering"),
    ("stone", "fine pebbled grain, low-contrast mineral variation, subtle dithering"),
    ("stone", "weathered flat-rock grain, gentle fracture rhythm, controlled color noise, faint dithering"),
    ("cobblestone", "tight stone pattern, even mortar rhythm, mild tonal variation, subtle dithering"),
    ("shallow water", "soft ripple bands, gentle wave noise, restrained highlights, faint dithering"),
    ("water", "calm surface texture, micro-ripple variation, smooth tonal transitions, subtle dithering"),
    ("deep water", "darker pooled texture, low-frequency ripple noise, controlled highlight specks, faint dithering"),
    ("wheat-ground", "dry straw flecks, golden grain noise, subtle directional variation, faint dithering"),  # NEW thematic tile
]

# ------------------------------------------------------------
# Prompt composition
# ------------------------------------------------------------
def make_object_prompt(story_text: str) -> str:
    return OBJECT_PROMPT_TEMPLATE.replace("{PROMPT_HERE}", story_text)

def make_tile_prompt(material: str, texture_details: str) -> str:
    return TILE_PROMPT_TEMPLATE.format(material=material, texture_details=texture_details)

def structure_story(structure, theme, motif, personality, detail, complexity, material, condition, palette):
    return (
        f"A medieval {structure} in a {theme} setting, featuring {motif}, {personality} character, "
        f"{detail}, {complexity}, {material}, {condition}, and {palette}"
    )

def nature_story(obj, drama, detail, complexity, material, condition, palette):
    if "hill" in obj:
        top_shape = random.choice(HILL_TOP_SHAPES)
        side_shape = random.choice(HILL_SIDE_SMOOTHNESS)
        seam_rule = random.choice(HILL_SEAM_INTEGRITY)
        base = (
            f"A dramatic terrain object of a {obj} with {top_shape}, {side_shape}, {seam_rule}, "
            f"{detail}, {complexity}, {material}, {condition}, and {palette}"
        )
    else:
        base = (
            f"A dramatic medieval world asset object of a {obj} with {drama}, "
            f"{detail}, {complexity}, {material}, {condition}, and {palette}"
        )
    return f"{base}. {NATURE_TILE_COMPAT_CLAUSE}"

# ------------------------------------------------------------
# Ratio helpers
# ------------------------------------------------------------
def ratio_to_counts(total_target: int, ratios: dict) -> dict:
    keys = list(ratios.keys())
    vals = [max(0.0, float(ratios[k])) for k in keys]
    s = sum(vals)

    if s <= 0:
        vals = [1.0 for _ in vals]
        s = float(len(vals))

    norm = [v / s for v in vals]
    raw = [total_target * n for n in norm]
    base = [int(x) for x in raw]
    remainder = total_target - sum(base)

    frac = sorted([(raw[i] - base[i], i) for i in range(len(keys))], key=lambda x: x[0], reverse=True)
    for j in range(remainder):
        base[frac[j % len(keys)][1]] += 1

    return {keys[i]: base[i] for i in range(len(keys))}

# ------------------------------------------------------------
# Row builders
# ------------------------------------------------------------
def build_rows_structures(target_count: int, start_idx: int):
    rows, idx = [], start_idx
    combos = list(itertools.product(
        STRUCTURE_TYPES, STRUCTURE_THEMES, THEME_MOTIFS, ARCHITECTURAL_PERSONALITY,
        DETAIL_LEVELS, STRUCTURAL_COMPLEXITY, MATERIALS_STRUCTURE, CONDITIONS_STRUCTURE, PALETTES_STRUCTURE
    ))
    random.shuffle(combos)

    ptr = 0
    for _ in range(target_count):
        c = combos[ptr % len(combos)]
        ptr += 1
        structure, theme, motif, personality, detail, complexity, material, condition, palette = c
        prompt = make_object_prompt(
            structure_story(structure, theme, motif, personality, detail, complexity, material, condition, palette)
        )
        rows.append({
            "id": f"mdv_{idx:07d}",
            "domain": "medieval_pixel_assets",
            "asset_family": "structure",
            "object_class": structure,
            "theme_mood": theme,
            "theme_motif": motif,
            "architectural_personality": personality,
            "detail_level": detail,
            "complexity": complexity,
            "material_profile": material,
            "condition": condition,
            "palette": palette,
            "positive_prompt": prompt,
            "negative_prompt": "",
            "pose_token": "<pose_overhead>",
            "style_token": "<pixel_art_medieval_arch>"
        })
        idx += 1
    return rows, idx

def build_rows_nature(target_count: int, start_idx: int):
    rows, idx = [], start_idx
    combos = list(itertools.product(
        NATURE_OBJECTS, NATURE_DRAMA, DETAIL_LEVELS, NATURE_COMPLEXITY,
        MATERIALS_NATURE, CONDITIONS_NATURE, PALETTES_NATURE
    ))
    random.shuffle(combos)

    ptr = 0
    for _ in range(target_count):
        c = combos[ptr % len(combos)]
        ptr += 1
        obj, drama, detail, complexity, material, condition, palette = c
        prompt = make_object_prompt(nature_story(obj, drama, detail, complexity, material, condition, palette))
        rows.append({
            "id": f"mdv_{idx:07d}",
            "domain": "medieval_pixel_assets",
            "asset_family": "nature_object",
            "object_class": obj,
            "nature_drama": drama,
            "detail_level": detail,
            "complexity": complexity,
            "material_profile": material,
            "condition": condition,
            "palette": palette,
            "positive_prompt": prompt,
            "negative_prompt": "",
            "pose_token": "<pose_overhead>",
            "style_token": "<pixel_art_medieval_arch>"
        })
        idx += 1
    return rows, idx

def build_rows_tiles(target_count: int, start_idx: int):
    rows, idx = [], start_idx
    combos = list(itertools.product(TILE_VARIANTS, PALETTES_NATURE))
    random.shuffle(combos)

    ptr = 0
    for _ in range(target_count):
        (material, texture_details), palette = combos[ptr % len(combos)]
        ptr += 1
        prompt = make_tile_prompt(material, texture_details)
        rows.append({
            "id": f"mdv_{idx:07d}",
            "domain": "medieval_pixel_assets",
            "asset_family": "background_tile",
            "object_class": f"{material}_tile",
            "detail_level": "tile_optimized",
            "complexity": "seamless_repeatable",
            "material_profile": material,
            "condition": "stable_tile_state",
            "palette": palette,
            "positive_prompt": prompt,
            "negative_prompt": "",
            "pose_token": "<pose_overhead>",
            "style_token": "<pixel_art_tile_seamless>"
        })
        idx += 1
    return rows, idx

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def parse_args():
    ap = argparse.ArgumentParser(description="Generate medieval FLUX prompt pack with mystical structures + wheat assets")
    ap.add_argument("--out-dir", default="./dataset/prompts")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--total-target", type=int, default=28000)
    ap.add_argument("--ratio-structures", type=float, default=0.54)
    ap.add_argument("--ratio-nature", type=float, default=0.28)
    ap.add_argument("--ratio-tiles", type=float, default=0.18)
    return ap.parse_args()

def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)

    ratios = {
        "structure": args.ratio_structures,
        "nature_object": args.ratio_nature,
        "background_tile": args.ratio_tiles,
    }
    counts = ratio_to_counts(args.total_target, ratios)

    all_rows = []
    cursor = 0

    rs, cursor = build_rows_structures(counts["structure"], cursor)
    rn, cursor = build_rows_nature(counts["nature_object"], cursor)
    rt, cursor = build_rows_tiles(counts["background_tile"], cursor)

    all_rows.extend(rs)
    all_rows.extend(rn)
    all_rows.extend(rt)

    random.shuffle(all_rows)
    all_rows = all_rows[:args.total_target]

    out_jsonl = out_dir / "medieval_prompt_pack.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = defaultdict(lambda: defaultdict(int))
    for r in all_rows:
        summary["asset_family"][r["asset_family"]] += 1
        summary["object_class"][r["object_class"]] += 1
        summary["palette"][r["palette"]] += 1
        if r["asset_family"] == "structure":
            summary["structure_theme"][r.get("theme_mood", "unknown")] += 1

    summary_payload = {
        "total_prompts": len(all_rows),
        "input_ratios": ratios,
        "normalized_targets": counts,
        "added_features": {
            "mystical_structures": [
                "wizarding tower",
                "arcane observatory tower",
                "rune-etched mage spire",
                "enchanted library tower",
                "alchemist laboratory tower"
            ],
            "wheat_assets": [
                "wheat field patch",
                "harvest-ready wheat field",
                "wind-swept wheat cluster",
                "wheat-ground tile variant"
            ]
        },
        "distribution": summary
    }

    summary_path = out_dir / "medieval_prompt_pack_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(all_rows)} prompts to {out_jsonl}")
    print(f"Wrote summary to {summary_path}")

if __name__ == "__main__":
    main()
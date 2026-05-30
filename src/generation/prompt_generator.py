#!/usr/bin/env python3
# prompt_generator.py

import argparse
import json
import random
import sys
import warnings
from pathlib import Path
from collections import defaultdict



# ------------------------------------------------------------
# STRUCTURES
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
    "mystical arcane enclave",
    "wizarding scholarly district",
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
    "glowing rune inlays and arcane sigils",
    "astronomical instruments and spellcraft details",
]

ARCHITECTURAL_PERSONALITY = [
    "humble and practical",
    "sturdy and fortified",
    "ornate but functional",
    "improvised frontier engineering",
    "ritually maintained",
    "industrially retrofitted",
    "mystical but grounded",
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
    "vertical spire layering",
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
    "rune-carved stone and reinforced masonry",
]

CONDITIONS_STRUCTURE = [
    "well-maintained",
    "weathered",
    "war-damaged",
    "partially ruined",
    "heavily used industrial wear",
    "heat-scorched but operational",
    "well-kept arcane condition",
]

PALETTES_STRUCTURE = [
    "warm muted palette",
    "earthy palette",
    "cool medieval palette",
    "desaturated retro palette",
    "high contrast retro palette",
    "smoky sepia palette",
    "ash-and-ember palette",
    "mystic violet-cyan palette",
]

# ------------------------------------------------------------
# OBJECTS (trees, boulders, wheat, stumps, reeds, brambles, volcanic spires)
# ------------------------------------------------------------
OBJECT_TYPES = [
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
    "volcanic rock spire",
    "charred stump cluster",
    "wheat field patch",
    "harvest-ready wheat field",
    "wind-swept wheat cluster",
]

OBJECT_DRAMA = [
    "storm-battered silhouette",
    "wind-carved shape language",
    "ancient growth with twisted massing",
    "battle-scarred surface forms",
    "volcanic weathering and fracture lines",
    "ominous high-contrast shape breakup",
    "wind-rippled crop flow",
]

OBJECT_COMPLEXITY = [
    "simple silhouette",
    "layered silhouette",
    "dense readable forms",
    "weathered rough form",
]

MATERIALS_OBJECT = [
    "lush foliage and bark",
    "dark evergreen foliage",
    "dry bark and sparse foliage",
    "mossy stone texture",
    "packed earth and dry grass",
    "volcanic basalt texture",
    "golden wheat stalk texture",
]

CONDITIONS_OBJECT = [
    "healthy growth",
    "weathered growth",
    "overgrown",
    "storm-worn",
    "heat-scorched",
    "harvest-ready condition",
]

PALETTES_OBJECT = [
    "earthy palette",
    "cool medieval palette",
    "desaturated retro palette",
    "high contrast retro palette",
    "storm-muted palette",
    "ash-and-ember palette",
    "golden harvest palette",
]

# ------------------------------------------------------------
# TERRAIN (hills/plateaus — always wide flat top)
# ------------------------------------------------------------
TERRAIN_TYPES = [
    "large hill",
    "broad plateau hill",
    "rounded ridge hill",
]

TERRAIN_SIDE_SMOOTHNESS = [
    "soft smooth side slopes",
    "medium smooth side slopes",
    "controlled semi-sharp side slopes",
]

TERRAIN_SEAM_INTEGRITY = [
    "slope mass tapers cleanly before tile boundaries",
    "side slopes preserve edge readability near tile seams",
    "outer silhouette avoids seam collisions and edge tangents",
    "base footprint remains map-placeable without seam artifacts",
]

MATERIALS_TERRAIN = [
    "packed earth and dry grass",
    "mossy stone texture",
    "volcanic basalt texture",
    "lush foliage and bark",
]

CONDITIONS_TERRAIN = [
    "weathered growth",
    "healthy growth",
    "overgrown",
    "storm-worn",
]

PALETTES_TERRAIN = [
    "earthy palette",
    "cool medieval palette",
    "desaturated retro palette",
    "high contrast retro palette",
    "storm-muted palette",
]

# ------------------------------------------------------------
# CAPTION BUILDERS (clean, template-free, descriptive)
# ------------------------------------------------------------
def structure_caption(structure, theme, motif, personality, detail, complexity, material, condition, palette):
    return (
        f"top-down view. "
        f"a medieval {structure} in a {theme} setting, "
        f"featuring {motif}, {personality} character, "
        f"{detail}, {complexity}, {material}, {condition}, {palette}"
    )

def object_caption(obj, drama, complexity, material, condition, palette):
    return (
        f"top-down view. "
        f"a dramatic medieval world asset of a {obj} with {drama}, "
        f"{complexity}, {material}, {condition}, {palette}"
    )

def terrain_caption(terrain_type, side_smoothness, seam_integrity, complexity, material, condition, palette):
    return (
        f"top-down view. "
        f"a {terrain_type} with wide flat top, {side_smoothness}, "
        f"{complexity}, {seam_integrity}, "
        f"{material}, {condition}, {palette}"
    )

# ------------------------------------------------------------
# POSITIVE PROMPT BUILDERS (ComfyUI template injection)
# ------------------------------------------------------------
def structure_positive_prompt(story_text, template):
    return template.replace("{PROMPT_HERE}", story_text)

def object_positive_prompt(story_text, template):
    return template.replace("{PROMPT_HERE}", story_text)

def terrain_positive_prompt(story_text, template):
    return template.replace("{PROMPT_HERE}", story_text)

def background_positive_prompt(material, texture_details, template):
    return template.format(material=material, texture_details=texture_details)

# ------------------------------------------------------------
# Template loader
# ------------------------------------------------------------
def load_prompt_templates(path: Path) -> dict:
    """Load and validate prompt templates JSON.

    Provides a friendly error message if the JSON is malformed (e.g. trailing
    commas, missing quotes) so users can fix it without decoding a traceback.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"[ERROR] Failed to parse {path}: {exc}\n"
            f"        JSON does not allow trailing commas — check the last entry "
            f"in each object block and remove any trailing ',' before the closing '}}' or ']'."
        ) from exc

    templates = data.get("templates", {})
    if not isinstance(templates, dict):
        raise ValueError("Invalid templates JSON: `templates` must be an object")

    required = ["structure", "object", "terrain"]
    for key in required:
        val = templates.get(key)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"Invalid templates JSON: `templates.{key}` must be a non-empty string")

    if "{PROMPT_HERE}" not in templates["structure"]:
        raise ValueError("`templates.structure` must contain {PROMPT_HERE}")
    if "{PROMPT_HERE}" not in templates["object"]:
        raise ValueError("`templates.object` must contain {PROMPT_HERE}")
    if "{PROMPT_HERE}" not in templates["terrain"]:
        raise ValueError("`templates.terrain` must contain {PROMPT_HERE}")

    # Warn if templates still use deprecated trigger / angle phrase
    for key, tmpl in templates.items():
        if "<sks>" in tmpl:
            warnings.warn(
                f"Template '{key}' contains deprecated trigger '<sks>'. "
                f"The current trigger is '<tdp>'. Update config/prompt_templates.json.",
                UserWarning,
            )
        if "front view overhead" in tmpl.lower():
            warnings.warn(
                f"Template '{key}' contains deprecated angle phrase 'front view overhead...'. "
                f"The current angle phrase is 'top-down view.'. Update config/prompt_templates.json.",
                UserWarning,
            )

    return templates

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
def _pick_one(choices):
    """Return random.choice without materializing product space."""
    return random.choice(choices)

def build_structure_rows(target_count, start_idx, templates):
    rows, idx = [], start_idx
    if target_count <= 0:
        return rows, idx

    for _ in range(target_count):
        structure = _pick_one(STRUCTURE_TYPES)
        theme = _pick_one(STRUCTURE_THEMES)
        motif = _pick_one(THEME_MOTIFS)
        personality = _pick_one(ARCHITECTURAL_PERSONALITY)
        detail = _pick_one(DETAIL_LEVELS)
        complexity = _pick_one(STRUCTURAL_COMPLEXITY)
        material = _pick_one(MATERIALS_STRUCTURE)
        condition = _pick_one(CONDITIONS_STRUCTURE)
        palette = _pick_one(PALETTES_STRUCTURE)

        story = (
            f"A medieval {structure} in a {theme} setting, featuring {motif}, "
            f"{personality} character, {detail}, {complexity}, {material}, {condition}, "
            f"and {palette}"
        )

        caption = structure_caption(structure, theme, motif, personality, detail, complexity, material, condition, palette)
        positive_prompt = structure_positive_prompt(story, templates["structure"])

        rows.append({
            "id": f"mdv_{idx:07d}",
            "asset_type": "structure",
            "caption": caption,
            "positive_prompt": positive_prompt,
            "palette": palette,
        })
        idx += 1
    return rows, idx

def build_object_rows(target_count, start_idx, templates):
    rows, idx = [], start_idx
    if target_count <= 0:
        return rows, idx

    for _ in range(target_count):
        obj = _pick_one(OBJECT_TYPES)
        drama = _pick_one(OBJECT_DRAMA)
        complexity = _pick_one(OBJECT_COMPLEXITY)
        material = _pick_one(MATERIALS_OBJECT)
        condition = _pick_one(CONDITIONS_OBJECT)
        palette = _pick_one(PALETTES_OBJECT)

        story = (
            f"A dramatic medieval world asset object of a {obj} with {drama}, "
            f"{complexity}, {material}, {condition}, and {palette}"
        )

        caption = object_caption(obj, drama, complexity, material, condition, palette)
        positive_prompt = object_positive_prompt(story, templates["object"])

        rows.append({
            "id": f"mdv_{idx:07d}",
            "asset_type": "object",
            "caption": caption,
            "positive_prompt": positive_prompt,
            "palette": palette,
        })
        idx += 1
    return rows, idx

def build_terrain_rows(target_count, start_idx, templates):
    rows, idx = [], start_idx
    if target_count <= 0:
        return rows, idx

    for _ in range(target_count):
        terrain_type = _pick_one(TERRAIN_TYPES)
        side_smoothness = _pick_one(TERRAIN_SIDE_SMOOTHNESS)
        seam_integrity = _pick_one(TERRAIN_SEAM_INTEGRITY)
        complexity = _pick_one(OBJECT_COMPLEXITY)
        material = _pick_one(MATERIALS_TERRAIN)
        condition = _pick_one(CONDITIONS_TERRAIN)
        palette = _pick_one(PALETTES_TERRAIN)

        story = (
            f"A dramatic terrain object of a {terrain_type} with wide flat top, "
            f"{side_smoothness}, {seam_integrity}, {complexity}, {material}, {condition}, "
            f"and {palette}"
        )

        caption = terrain_caption(terrain_type, side_smoothness, seam_integrity, complexity, material, condition, palette)
        positive_prompt = terrain_positive_prompt(story, templates["terrain"])

        rows.append({
            "id": f"mdv_{idx:07d}",
            "asset_type": "terrain",
            "caption": caption,
            "positive_prompt": positive_prompt,
            "palette": palette,
        })
        idx += 1
    return rows, idx

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def parse_args():
    ap = argparse.ArgumentParser(description="Generate medieval FLUX prompt data: 4 asset types with clean captions")
    ap.add_argument("--out-dir", default="./dataset/prompts")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--total-target", type=int, default=28000)
    ap.add_argument("--ratio-structure", type=float, default=0.50)
    ap.add_argument("--ratio-object", type=float, default=0.20)
    ap.add_argument("--ratio-terrain", type=float, default=0.10)
    ap.add_argument(
        "--templates-json",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "config" / "prompt_templates.json",
        help="Path to JSON file containing prompt templates.",
    )
    return ap.parse_args()

def main():
    args = parse_args()
    from src.generation import _check_runtime
    _check_runtime()

    templates_json_path = args.templates_json.resolve()
    if not templates_json_path.is_file():
        print(f"[ERROR] Required file not found: {templates_json_path} (prompt templates JSON)", file=sys.stderr)
        print("        Make sure you are running from the project root.", file=sys.stderr)
        raise SystemExit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)
    templates = load_prompt_templates(templates_json_path)

    ratios = {
        "structure": args.ratio_structure,
        "object": args.ratio_object,
        "terrain": args.ratio_terrain,
    }
    counts = ratio_to_counts(args.total_target, ratios)

    all_rows = []
    cursor = 0

    rs, cursor = build_structure_rows(counts["structure"], cursor, templates)
    ro, cursor = build_object_rows(counts["object"], cursor, templates)
    rb, cursor = build_background_rows(counts["background"], cursor, templates)
    rt, cursor = build_terrain_rows(counts["terrain"], cursor, templates)

    all_rows.extend(rs)
    all_rows.extend(ro)
    all_rows.extend(rb)
    all_rows.extend(rt)

    random.shuffle(all_rows)
    all_rows = all_rows[:args.total_target]

    out_jsonl = out_dir / "generated_prompts.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = defaultdict(lambda: defaultdict(int))
    for r in all_rows:
        summary["asset_type"][r["asset_type"]] += 1
        summary["palette"][r["palette"]] += 1

    summary_payload = {
        "total_prompts": len(all_rows),
        "input_ratios": ratios,
        "normalized_targets": counts,
        "templates_json": str(templates_json_path),
        "distribution": summary,
    }

    summary_path = out_dir / "generated_prompts_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(all_rows)} prompts to {out_jsonl}")
    print(f"Wrote summary to {summary_path}")

if __name__ == "__main__":
    main()
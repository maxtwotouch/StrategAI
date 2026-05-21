#!/usr/bin/env python3
"""Extract reusable prompt templates from an existing prompt-data JSONL file.

Scans prompt rows and extracts common structural patterns into a
prompt_templates.json-compatible format. Useful for bootstrapping new
template variants from previously generated data.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def extract_structure_template(rows: list[dict]) -> str | None:
    """Attempt to extract a common structure template from positive_prompt fields."""
    prompts = [r.get("positive_prompt", "") for r in rows if r.get("asset_family") == "structure"]
    if not prompts:
        return None

    # Find common prefix/suffix patterns
    prefix_counts: Counter[str] = Counter()
    suffix_counts: Counter[str] = Counter()

    for p in prompts:
        words = p.split()
        if len(words) >= 3:
            prefix_counts[" ".join(words[:3])] += 1
            suffix_counts[" ".join(words[-3:])] += 1

    # Most common prefix and suffix
    top_prefix = prefix_counts.most_common(1)
    top_suffix = suffix_counts.most_common(1)

    # Build a template by replacing the variable middle with {PROMPT_HERE}
    if top_prefix and top_suffix:
        prefix = top_prefix[0][0]
        suffix = top_suffix[0][0]
        # Use a sample prompt to find where prefix ends and suffix begins
        sample = prompts[0]
        if sample.startswith(prefix) and sample.endswith(suffix):
            middle = sample[len(prefix):len(sample) - len(suffix)].strip()
            if middle:
                template = sample.replace(middle, "{PROMPT_HERE}", 1)
                return template

    return None


def extract_tile_template(rows: list[dict]) -> str | None:
    """Extract a tile template from background_tile rows."""
    prompts = [r.get("positive_prompt", "") for r in rows if r.get("asset_family") == "background_tile"]
    if not prompts:
        return None

    # Look for material and texture pattern
    for p in prompts[:5]:
        # Try to find material and texture placeholders
        if "material" in p.lower() or "texture" in p.lower():
            # Replace material-specific words with placeholders
            template = re.sub(
                r'\b(sand|grass|stone|cobblestone|water|wheat)\b',
                '{material}',
                p,
                flags=re.IGNORECASE
            )
            template = re.sub(
                r'(fine grain|dry fine|short blade|dense micro|weathered flat|tight stone|soft ripple|calm surface|darker pool|dry straw|smooth dune|muddy green|faint dithering|subtle dithering|gentle color noise|controlled color noise|low-contrast|muted tonal|gentle|restrained|faint)\b',
                '{texture_details}',
                template,
                flags=re.IGNORECASE
            )
            if "{material}" in template and "{texture_details}" in template:
                return template

    return None


def main():
    ap = argparse.ArgumentParser(description="Extract prompt templates from existing prompt data")
    ap.add_argument("prompt_data", type=Path, help="Path to generated_prompts.jsonl")
    ap.add_argument("--out", type=Path, default=None,
                    help="Output path (default: <prompt_data parent>/../config/prompt_templates.json)")
    args = ap.parse_args()

    rows = load_jsonl(args.prompt_data)
    print(f"Loaded {len(rows)} prompt rows")

    structure_template = extract_structure_template(rows)
    tile_template = extract_tile_template(rows)

    output = {
        "schema_version": 1,
        "templates": {},
        "required_placeholders": {}
    }

    if structure_template:
        output["templates"]["structure"] = structure_template
        output["required_placeholders"]["structure"] = ["{PROMPT_HERE}"]
        print(f"Extracted structure template: {structure_template[:100]}...")
    else:
        print("WARNING: Could not extract structure template")

    if tile_template:
        output["templates"]["background_tile"] = tile_template
        output["required_placeholders"]["background_tile"] = ["{material}", "{texture_details}"]
        print(f"Extracted tile template: {tile_template[:100]}...")
    else:
        print("WARNING: Could not extract tile template")

    out_path = args.out or (args.prompt_data.parent.parent / "config" / "prompt_templates.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote templates to {out_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Derive three caption-detail variants from the source dataset sidecar .txt files.

Produces:
  minimal/      — "[trigger] top-down view. A medieval <category>."
  detailed/     — "[trigger] top-down view. <original description sans old angle phrase>"
  ultra_minimal/ — "[trigger] top-down view."

Categories are heuristically assigned by scanning the caption for subject keywords.
Each derived dataset directory gets symlinks to the original PNGs + new .txt files.

Usage:
    python -m src.derive_captions                 # write all three
    python -m src.derive_captions --dry-run       # preview only
    python -m src.derive_captions --variants minimal,detailed  # subset
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# ── Path defaults (relative to project root) ──────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "dataset"
DEFAULT_DERIVED_DIR = PROJECT_ROOT / "dataset" / "derived"

# ── Old angle phrase to strip ─────────────────────────────────────────
OLD_ANGLE = "Front view overhead elevated medium shot."
NEW_ANGLE = "top-down view."
TRIGGER = "[trigger]"

# ── Category mapping ──────────────────────────────────────────────────
# Maps subject-matching regexes to category labels (checked in order).
CATEGORY_RULES: List[Tuple[str, str]] = [
    # Terrain / natural ground (compound patterns first)
    (r"\b(grass|dirt|sand|stone|water|swamp|snow|ice|lava|cobblestone|gravel)\s+(tile|texture|patch|terrain)",
     "terrain"),
    # Vegetation
    (r"\b(bramble|reeds|bush|shrub|tree|forest|vine|thicket|undergrowth|fungus|mushroom|crop|foliage|canopy)\b",
     "vegetation"),
    # Buildings — check BEFORE objects since "forge", "mill", etc. can appear as substrings
    (r"\b(building|tower|house|hall|forge\b|workshop|mill|farm|cottage|monastery|barracks|granary|sawmill|watchtower|outpost|station|laboratory|observatory|wall|keep|castle|temple|church|tavern|inn|shop|market|bridge|gate|mine|quarry|foundry|windmill|watermill|stronghold|fortress|citadel)\b",
     "building"),
    # Objects / props — specific standalone nouns (exclude "well"/"forge"/"table" to avoid false matches)
    (r"\b(chest|barrel|crate|anvil|tool|weapon|shield|torch|lantern|bench|throne|statue|fountain|cart|wagon|cauldron|bookcase|bed|chair)\b",
     "object"),
    # Terrain textures (catch-all)
    (r"\b(tile|texture|terrain|ground|floor|path|road)\b",
     "terrain"),
]

# ── Caption helpers ────────────────────────────────────────────────────

def strip_old_angle(text: str) -> str:
    """Remove the old angle phrase prefix, returning the clean description."""
    t = text.strip()
    # Remove [trigger] if present at start (from source files)
    if t.startswith("[trigger]"):
        t = t[len("[trigger]"):].strip()
    if t.lower().startswith(OLD_ANGLE.lower()):
        t = t[len(OLD_ANGLE):].strip()
    # Also try without the period
    if t.lower().startswith(OLD_ANGLE.lower().rstrip(".")):
        t = t[len(OLD_ANGLE) - 1:].strip()
    return t


def classify_category(text: str) -> str:
    """Heuristically assign a category label based on caption keywords."""
    lower = text.lower()
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, lower):
            return category
    return "building"


def build_minimal(text: str) -> str:
    """Build a minimal caption: trigger + angle + category."""
    clean = strip_old_angle(text)
    category = classify_category(clean)
    return f"{TRIGGER} {NEW_ANGLE} A medieval {category}."


def build_detailed(text: str) -> str:
    """Build a detailed caption: trigger + angle + full original description."""
    clean = strip_old_angle(text)
    return f"{TRIGGER} {NEW_ANGLE} {clean}"


def build_ultra_minimal() -> str:
    """Build an ultra-minimal caption: trigger + angle only."""
    return f"{TRIGGER} {NEW_ANGLE}"


# ── Main ───────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Derive caption-detail variants from source .txt files.")
    p.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR,
                   help="Directory containing .png and .txt source files.")
    p.add_argument("--derived-dir", type=Path, default=DEFAULT_DERIVED_DIR,
                   help="Root directory for derived datasets.")
    p.add_argument("--variants", type=str, default="minimal,detailed,ultra_minimal",
                   help="Comma-separated variant names to generate.")
    p.add_argument("--dry-run", action="store_true", help="Preview only, do not write files.")
    return p.parse_args()


def iter_pairs(source_dir: Path) -> List[Tuple[Path, str]]:
    """Yield (png_path, caption_text) pairs from source_dir."""
    pairs: List[Tuple[Path, str]] = []
    for png in sorted(source_dir.glob("*.png")):
        txt = png.with_suffix(".txt")
        if not txt.exists():
            print(f"  ⚠  skipping: no .txt for {png.name}")
            continue
        caption = txt.read_text(encoding="utf-8").strip()
        if not caption:
            print(f"  ⚠  skipping: empty caption for {png.name}")
            continue
        pairs.append((png, caption))
    return pairs


def main() -> int:
    args = parse_args()
    source_dir = args.source_dir.resolve()
    if not source_dir.is_dir():
        print(f"[ERROR] Source directory not found: {source_dir}")
        return 1

    requested = {v.strip() for v in args.variants.split(",") if v.strip()}
    valid = {"minimal", "detailed", "ultra_minimal"}
    unknown = requested - valid
    if unknown:
        print(f"[ERROR] Unknown variant(s): {', '.join(sorted(unknown))}")
        print(f"        Valid: {', '.join(sorted(valid))}")
        return 1

    pairs = iter_pairs(source_dir)
    if not pairs:
        print("[ERROR] No image-caption pairs found.")
        return 1

    print(f"Found {len(pairs)} image-caption pairs in {source_dir}")
    print(f"Variants: {', '.join(sorted(requested))}")
    print()

    builders = {
        "minimal": build_minimal,
        "detailed": build_detailed,
        "ultra_minimal": lambda _: build_ultra_minimal(),
    }

    for variant in sorted(requested):
        out_dir = (args.derived_dir / variant).resolve()
        if not args.dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)

        print(f"── {variant} ──")
        count = 0
        for png_path, orig_caption in pairs:
            new_caption = builders[variant](orig_caption)

            if not args.dry_run:
                # Symlink the PNG (remove existing if broken or wrong)
                link_path = out_dir / png_path.name
                if link_path.exists() or link_path.is_symlink():
                    link_path.unlink()
                link_path.symlink_to(os.path.relpath(png_path, out_dir))

                # Write .txt
                txt_path = out_dir / f"{png_path.stem}.txt"
                txt_path.write_text(new_caption + "\n", encoding="utf-8")

            # Show preview (first 3)
            if count < 3:
                print(f"  {png_path.stem}: {new_caption}")
            count += 1

        if count > 3:
            print(f"  ... and {count - 3} more")
        print(f"  Total: {count} pairs")
        print()

    if args.dry_run:
        print("[DRY RUN] No files written. Remove --dry-run to write.")
    else:
        print("[DONE] Derived datasets written.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

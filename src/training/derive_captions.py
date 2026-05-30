#!/usr/bin/env python3
"""
Derive three caption-detail training variants from the dataset manifest.

Reads dataset/metadata.jsonl (canonical manifest) and produces:
  dataset/derived/minimal/       — "[trigger] top-down view. A medieval <category>."
  dataset/derived/detailed/      — "[trigger] top-down view. <full description>"
  dataset/derived/ultra_minimal/ — "[trigger] top-down view."

If no manifest exists, one is auto-generated from the .txt sidecar files
(stripping the old angle phrase) — this is a one-time migration step.

Categories are heuristically assigned by scanning the caption for subject keywords.
Each derived dataset gets symlinks to the original PNGs + new .txt sidecar files.

Usage:
    python -m src.derive_captions                   # write all three
    python -m src.derive_captions --dry-run         # preview only
    python -m src.derive_captions --variants minimal,detailed
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

# ── Path defaults (relative to project root) ──────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "dataset" / "hf" / "images"
DEFAULT_MANIFEST = DEFAULT_SOURCE_DIR / "metadata.jsonl"
DEFAULT_DERIVED_DIR = PROJECT_ROOT / "dataset" / "derived"

# ── Angle phrase (manifest captions already use this) ──────────────────
NEW_ANGLE = "top-down view."
TRIGGER = "[trigger]"
# Old phrase — only relevant during one-time manifest generation from sidecar files
OLD_ANGLE = "Front view overhead elevated medium shot."

# ── Category mapping ──────────────────────────────────────────────────
CATEGORY_RULES: List[Tuple[str, str]] = [
    (r"\b(grass|dirt|sand|stone|water|swamp|snow|ice|lava|cobblestone|gravel)\s+(tile|texture|patch|terrain)",
     "terrain"),
    (r"\b(bramble|reeds|bush|shrub|tree|forest|vine|thicket|undergrowth|fungus|mushroom|crop|foliage|canopy)\b",
     "vegetation"),
    (r"\b(building|tower|house|hall|forge\b|workshop|mill|farm|cottage|monastery|barracks|granary|sawmill|watchtower|outpost|station|laboratory|observatory|wall|keep|castle|temple|church|tavern|inn|shop|market|bridge|gate|mine|quarry|foundry|windmill|watermill|stronghold|fortress|citadel|spire)\b",
     "structure"),
    (r"\b(chest|barrel|crate|anvil|tool|weapon|shield|torch|lantern|bench|throne|statue|fountain|cart|wagon|cauldron|bookcase|bed|chair)\b",
     "object"),
    (r"\b(tile|texture|terrain|ground|floor|path|road)\b",
     "terrain"),
]

# ── Caption helpers ────────────────────────────────────────────────────

def classify_category(text: str) -> str:
    """Heuristically assign a category label from a clean description."""
    lower = text.lower()
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, lower):
            return category
    return "structure"


def extract_description(caption: str) -> str:
    """Return the description portion of a caption (after trigger + angle phrase)."""
    t = caption.strip()
    if t.startswith("[trigger]"):
        t = t[len("[trigger]"):].strip()
    # Strip angle phrase — try old then new, with and without trailing period
    for prefix in (OLD_ANGLE, OLD_ANGLE.rstrip("."), NEW_ANGLE, NEW_ANGLE.rstrip(".")):
        if t.lower().startswith(prefix.lower()):
            t = t[len(prefix):].strip()
    return t


def build_minimal(caption: str) -> str:
    """Build a minimal caption: trigger + angle + category."""
    desc = extract_description(caption)
    category = classify_category(desc)
    return f"{TRIGGER} {NEW_ANGLE} A medieval {category}."


def build_detailed(caption: str) -> str:
    """Build a detailed caption: trigger + angle + full description."""
    desc = extract_description(caption)
    return f"{TRIGGER} {NEW_ANGLE} {desc}"


def build_ultra_minimal() -> str:
    """Build an ultra-minimal caption: trigger + angle only."""
    return f"{TRIGGER} {NEW_ANGLE}"


# ── Manifest generation (one-time migration) ──────────────────────────

def _strip_old_phrase(text: str) -> str:
    """Strip [trigger] and any angle phrase (old or new), return bare description."""
    t = text.strip()
    if t.startswith("[trigger]"):
        t = t[len("[trigger]"):].strip()
    # Try old phrase first, then new phrase
    for prefix in (OLD_ANGLE, OLD_ANGLE.rstrip("."), NEW_ANGLE, NEW_ANGLE.rstrip(".")):
        if t.lower().startswith(prefix.lower()):
            t = t[len(prefix):].strip()
    return t


def generate_manifest(source_dir: Path, manifest_path: Path) -> int:
    """One-time: scan .txt sidecar files → write clean metadata.jsonl."""
    rows: List[dict] = []
    for png in sorted(source_dir.glob("*.png")):
        txt = png.with_suffix(".txt")
        if not txt.exists():
            print(f"  !  no .txt for {png.name} — skipping")
            continue
        raw = txt.read_text(encoding="utf-8").strip()
        if not raw:
            print(f"  !  empty caption for {png.name} — skipping")
            continue

        # Build clean caption in canonical format
        desc = _strip_old_phrase(raw)
        clean = f"{TRIGGER} {NEW_ANGLE} {desc}"
        rows.append({
            "id": png.stem,
            "file_name": png.name,
            "text": clean,
        })

    if not rows:
        print("[ERROR] No image-caption pairs found for manifest generation.")
        return 0

    with manifest_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")
    print(f"Generated manifest: {len(rows)} rows → {manifest_path}")
    return len(rows)


# ── Main ───────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Derive caption-detail training variants from the dataset manifest."
    )
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST,
                   help="Path to metadata.jsonl (auto-generated if missing).")
    p.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR,
                   help="Directory containing .png files (for symlink resolution).")
    p.add_argument("--derived-dir", type=Path, default=DEFAULT_DERIVED_DIR,
                   help="Root directory for derived datasets.")
    p.add_argument("--variants", type=str, default="minimal,detailed,ultra_minimal",
                   help="Comma-separated variant names to generate.")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview only, do not write files.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    source_dir = args.source_dir.resolve()

    if not source_dir.is_dir():
        print(f"[ERROR] Source directory not found: {source_dir}")
        return 1

    # ── Ensure manifest exists ─────────────────────────────────────
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        print("Generating from .txt sidecar files (one-time migration)...")
        count = generate_manifest(source_dir, manifest_path)
        if count == 0:
            return 1

    # ── Load manifest ──────────────────────────────────────────────
    rows: List[dict] = []
    with manifest_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  !  skipping invalid JSON line: {e}")
                continue
            if "text" not in row or "file_name" not in row:
                print(f"  !  skipping row missing 'text' or 'file_name': {row.get('id', '?')}")
                continue
            rows.append(row)

    if not rows:
        print("[ERROR] No valid rows in manifest.")
        return 1

    print(f"Loaded {len(rows)} rows from {manifest_path}")

    # ── Resolve variants ───────────────────────────────────────────
    requested = {v.strip() for v in args.variants.split(",") if v.strip()}
    valid = {"minimal", "detailed", "ultra_minimal"}
    unknown = requested - valid
    if unknown:
        print(f"[ERROR] Unknown variant(s): {', '.join(sorted(unknown))}")
        return 1

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
        for row in rows:
            orig_caption = row["text"]
            new_caption = builders[variant](orig_caption)
            png_name = row["file_name"]
            png_path = source_dir / png_name

            if not args.dry_run:
                # Symlink the PNG
                link_path = out_dir / png_name
                if link_path.exists() or link_path.is_symlink():
                    link_path.unlink()
                link_path.symlink_to(os.path.relpath(png_path, out_dir))

                # Write .txt sidecar
                txt_path = out_dir / f"{Path(png_name).stem}.txt"
                txt_path.write_text(new_caption + "\n", encoding="utf-8")

            if count < 3:
                print(f"  {Path(png_name).stem}: {new_caption}")
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

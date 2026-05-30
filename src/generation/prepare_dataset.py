#!/usr/bin/env python3
"""Post-curation step: scan curated PNGs, strip metadata, copy with incremental filenames,
and produce a metadata.jsonl manifest for Hugging Face imagefolder.

Usage:
    python3 src/prepare_dataset.py ./dataset/raw --out-dir ./dataset/hf
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.generation.image_metadata import read_metadata_from_file


def strip_png_metadata(src: Path, dest: Path) -> None:
    """Copy src PNG to dest, stripping all metadata chunks."""
    from PIL import Image
    with Image.open(src) as im:
        # Save without any metadata (no pnginfo)
        im.save(dest, "PNG")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Prepare final dataset from curated PNGs with embedded metadata"
    )
    ap.add_argument(
        "images_dir",
        type=Path,
        help="Directory containing curated PNG images with embedded generation_metadata",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path("./dataset/hf"),
        help="Output directory for HF dataset (default: ./dataset/hf)",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    from src.generation import _check_runtime
    _check_runtime()

    images_dir = args.images_dir.resolve()
    out_dir = args.out_dir.resolve()

    if not images_dir.is_dir():
        print(f"ERROR: images directory not found: {images_dir}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    metadata_rows: list[dict[str, Any]] = []
    processed = 0
    skipped = 0
    counter = 0  # sequential counter for incremental filenames

    for png_path in sorted(images_dir.glob("*.png")):
        try:
            meta = read_metadata_from_file(png_path)
        except Exception as exc:
            print(f"[SKIP] {png_path.name}: failed to read metadata ({exc})")
            skipped += 1
            continue

        if meta is None:
            print(f"[SKIP] {png_path.name}: no generation_metadata chunk found")
            skipped += 1
            continue

        caption = meta.get("caption", "")
        asset_type = meta.get("asset_type", "")
        palette = meta.get("palette", "")

        if not caption:
            print(f"[SKIP] {png_path.name}: empty caption")
            skipped += 1
            continue

        counter += 1
        new_name = f"{counter:07d}.png"
        dest_png = out_dir / new_name

        # Copy as a clean PNG with no embedded metadata
        strip_png_metadata(png_path, dest_png)

        # Build HF imagefolder-compatible metadata row
        metadata_rows.append({
            "file_name": new_name,
            "text": caption,
            "asset_type": asset_type,
            "palette": palette,
        })

        processed += 1

    # Write metadata.jsonl
    meta_path = out_dir / "metadata.jsonl"
    with open(meta_path, "w", encoding="utf-8") as f:
        for row in metadata_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Write summary
    summary = {
        "source": str(images_dir),
        "output": str(out_dir),
        "total_pngs_found": processed + skipped,
        "processed": processed,
        "skipped": skipped,
    }
    summary_path = out_dir / "prepare_report.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Processed {processed} images, skipped {skipped}")
    print(f"Output: {out_dir}/  ({processed} PNGs)")
    print(f"Metadata: {meta_path}")
    print(f"Report: {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

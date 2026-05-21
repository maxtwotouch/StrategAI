#!/usr/bin/env python3
"""Remove bad assets by ID and clean up all related manifests and sidecars.

Usage:
    python3 src/remove_bad_assets.py --ids-file bad_ids.txt --dataset-root ./dataset

The IDs file should contain one asset ID per line (e.g., "mdv_0000001").
"""

import argparse
import json
from pathlib import Path


def load_ids(path: Path) -> set[str]:
    ids = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(line)
    return ids


def remove_from_manifest(manifest_path: Path, bad_ids: set[str]) -> int:
    """Remove entries from a JSONL manifest and return count of removed rows."""
    rows = []
    removed = 0
    if not manifest_path.exists():
        return 0

    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("id") in bad_ids:
                removed += 1
            else:
                rows.append(line)

    with open(manifest_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(row + "\n")

    return removed


def remove_from_metadata_dir(metadata_dir: Path, bad_ids: set[str]) -> int:
    """Remove individual sidecar JSON files for bad IDs."""
    removed = 0
    if not metadata_dir.exists():
        return 0

    for meta_file in metadata_dir.glob("*.json"):
        if meta_file.stem in bad_ids:
            meta_file.unlink()
            removed += 1
    return removed


def remove_from_images_dir(images_dir: Path, bad_ids: set[str]) -> int:
    """Remove image PNG files for bad IDs."""
    removed = 0
    if not images_dir.exists():
        return 0

    for img_file in images_dir.glob("*.png"):
        if img_file.stem in bad_ids:
            img_file.unlink()
            removed += 1
    return removed


def remove_from_hf_metadata(hf_meta_path: Path, bad_ids: set[str]) -> int:
    """Remove entries from HF metadata.jsonl and return count of removed rows."""
    rows = []
    removed = 0
    if not hf_meta_path.exists():
        return 0

    with open(hf_meta_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("id") in bad_ids:
                removed += 1
            else:
                rows.append(line)

    with open(hf_meta_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(row + "\n")

    return removed


def main():
    ap = argparse.ArgumentParser(description="Remove bad assets and clean manifests")
    ap.add_argument("--ids-file", type=Path, required=True,
                    help="Text file with one bad asset ID per line")
    ap.add_argument("--dataset-root", type=Path, required=True,
                    help="Root of the dataset (dataset/)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be removed without deleting anything")
    args = ap.parse_args()

    bad_ids = load_ids(args.ids_file)
    print(f"Loaded {len(bad_ids)} bad IDs from {args.ids_file}")

    root = args.dataset_root.resolve()

    # Paths to clean
    v1_images = root / "v1" / "images"
    v1_meta = root / "v1" / "metadata"
    v1_manifest = root / "v1" / "dataset_manifest.jsonl"
    v1_errors = root / "v1" / "errors.jsonl"

    hf_images = root / "v2" / "images"
    hf_meta = root / "v2" / "metadata.jsonl"
    hf_sidecars = root / "v2" / "metadata"

    total_removed = 0

    for label, path, func in [
        ("v1/dataset_manifest.jsonl", v1_manifest, remove_from_manifest),
        ("v1/metadata/*.json", v1_meta, remove_from_metadata_dir),
        ("v1/images/*.png", v1_images, remove_from_images_dir),
        ("v2/metadata.jsonl", hf_meta, remove_from_hf_metadata),
        ("v2/metadata/*.json", hf_sidecars, remove_from_metadata_dir),
        ("v2/images/*.png", hf_images, remove_from_images_dir),
    ]:
        count = func(path, bad_ids)
        if count:
            print(f"  Removed {count} entries from {label}")
            total_removed += count

    print(f"\nTotal removed: {total_removed}")

    if args.dry_run:
        print("(dry run — nothing was actually deleted)")


if __name__ == "__main__":
    main()

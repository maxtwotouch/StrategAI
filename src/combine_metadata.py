#!/usr/bin/env python3
"""
Combine individual metadata JSON files from dataset/metadata/ into a single
dataset/metadata.jsonl file expected by the training pipeline.

Usage:
    python -m src.combine_metadata
    python -m src.combine_metadata --metadata-dir dataset/metadata --output dataset/metadata.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine per-item metadata JSON files into a single JSONL metadata file."
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=Path("dataset/metadata"),
        help="Directory containing individual .json metadata files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dataset/metadata.jsonl"),
        help="Output JSONL file path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    metadata_dir = args.metadata_dir.resolve()
    if not metadata_dir.exists():
        print(f"[ERROR] Metadata directory not found: {metadata_dir}")
        return 1

    json_files = sorted(metadata_dir.glob("*.json"))
    if not json_files:
        print(f"[ERROR] No .json files found in {metadata_dir}")
        return 1

    rows = []
    for json_file in json_files:
        try:
            with json_file.open("r", encoding="utf-8") as handle:
                row = json.load(handle)
            if not isinstance(row, dict):
                print(f"[WARN] Skipping non-object file: {json_file}")
                continue
            rows.append(row)
        except json.JSONDecodeError as exc:
            print(f"[WARN] Skipping invalid JSON in {json_file}: {exc}")
            continue

    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    print(f"[INFO] Combined {len(rows)} metadata rows → {output_path}")

    # Print summary
    families = {}
    for row in rows:
        fam = row.get("asset_family", "__missing__")
        families[fam] = families.get(fam, 0) + 1

    if families:
        print("[INFO] Asset family distribution:")
        for fam, count in sorted(families.items()):
            print(f"       {fam}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

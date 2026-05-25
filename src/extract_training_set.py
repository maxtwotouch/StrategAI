#!/usr/bin/env python3
"""
Generate sidecar .txt caption files from metadata.jsonl, with trigger token injection.

Reads a HF-style metadata.jsonl, groups records by asset type, applies ratio-controlled
sampling, and writes .txt caption files alongside the source images (sidecar mode, default).
Optionally copies images+txt to a flat output directory (extract mode, --no-sidecar).

Trigger token injection:
  --trigger-word <tdmp>      The trigger word to inject (default: "<tdmp>")
  --trigger-mode manual      Prepend "<tdmp> " to every .txt caption
  --trigger-mode placeholder Prepend "[trigger] " — toolkit replaces at train time
  --trigger-mode none        Leave captions bare (toolkit auto-prepends trigger_word)

Usage:
    # Sidecar mode (default): write .txt files alongside images
    python -m src.extract_training_set
    python -m src.extract_training_set --total 120 --ratios structure=0.40,terrain=0.30,object=0.20,background=0.10

    # Extract mode: copy images + .txt to a flat directory
    python -m src.extract_training_set --no-sidecar --out training_set
    python -m src.extract_training_set --trigger-mode placeholder
    python -m src.extract_training_set --dry-run
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

# ── Hard-coded defaults ────────────────────────────────────────────────

DEFAULT_RATIOS = {
    "structure": 0.50,
    "terrain": 0.30,
    "object": 0.20,
    "background": 0.10,
}

TRIGGER_MODES = ("manual", "placeholder", "none")
DEFAULT_TRIGGER_WORD = "<tdmp>"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract a ratio-controlled training set.")
    p.add_argument("--metadata", type=Path, default=Path("dataset/metadata.jsonl"))
    p.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("dataset"),
        help="Dataset root directory. file_name paths in metadata are resolved relative to this.",
    )
    p.add_argument("--out", type=Path, default=Path("training_set"),
                   help="Output directory for extract mode (--no-sidecar).")
    p.add_argument("--total", type=int, default=0, help="Target size. 0 = use all available.")
    p.add_argument(
        "--ratios",
        type=str,
        default=",".join(f"{k}={v}" for k, v in DEFAULT_RATIOS.items()),
        help="Comma-separated key=value pairs, e.g. structure=0.50,terrain=0.30,...",
    )
    p.add_argument("--type-column", type=str, default="asset_type", help="JSONL column name for the category.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--dry-run", action="store_true", help="Print plan only, don't write files.")
    p.add_argument(
        "--sidecar",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write .txt caption files alongside source images (default). "
             "Use --no-sidecar to copy images+txt to --out directory instead.",
    )
    p.add_argument(
        "--trigger-word",
        type=str,
        default=DEFAULT_TRIGGER_WORD,
        help="Trigger word to inject into captions (default: '<tdmp>').",
    )
    p.add_argument(
        "--trigger-mode",
        type=str,
        choices=TRIGGER_MODES,
        default="placeholder",
        help="How to inject trigger token: manual='<tdmp> caption', "
             "placeholder='[trigger] caption', none=bare caption.",
    )
    return p.parse_args()


def load_metadata(path: Path) -> List[dict]:
    records: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def group_by_type(records: List[dict], column: str) -> Dict[str, List[dict]]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for rec in records:
        groups[rec.get(column, "__unknown__")].append(rec)
    return dict(groups)


def parse_ratios(raw: str) -> Dict[str, float]:
    ratios: Dict[str, float] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        k, _, v = chunk.partition("=")
        ratios[k.strip()] = float(v.strip())
    return ratios


def sample(
    groups: Dict[str, List[dict]],
    ratios: Dict[str, float],
    total: int,
    seed: int,
) -> Dict[str, List[dict]]:
    """Sample per ratios.  If total==0, use ALL available images (ratios are informational only)."""
    rng = random.Random(seed)
    result: Dict[str, List[dict]] = {}

    if total == 0:
        for atype, pool in groups.items():
            result[atype] = pool[:]
        return result

    for atype, ratio in ratios.items():
        pool = groups.get(atype, [])
        n = round(total * ratio)
        if n > len(pool):
            print(f"  ⚠  {atype}: wanted {n}, only {len(pool)} available — using all")
            n = len(pool)
        result[atype] = rng.sample(pool, n) if n else []
    return result


def _resolve_image(dataset_root: Path, file_name: str) -> Path:
    """Resolve file_name relative to dataset_root.

    The metadata 'file_name' may include a subdirectory (e.g. 'images/0001.png').
    If dataset_root/file_name doesn't exist, fall back to dataset_root/basename.
    """
    candidate = (dataset_root / file_name).resolve()
    if candidate.exists():
        return candidate
    # Fallback: strip any directory prefix from file_name
    fallback = (dataset_root / Path(file_name).name).resolve()
    if fallback.exists():
        return fallback
    return candidate  # doesn't exist anyway, caller handles


def _format_caption(text: str, trigger_word: str, trigger_mode: str) -> str:
    """Format a caption with trigger token injection."""
    text = text.strip()
    if trigger_mode == "none":
        return text
    if trigger_mode == "placeholder":
        return f"[trigger] {text}"
    # manual mode
    return f"{trigger_word} {text}"


def write_output(
    sampled: Dict[str, List[dict]],
    dataset_root: Path,
    output_dir: Path,
    trigger_word: str = "",
    trigger_mode: str = "none",
    sidecar: bool = True,
) -> int:
    """Write caption files. In sidecar mode, .txt goes next to the source image.
    In extract mode, images are copied to output_dir with .txt sidecars."""
    if not sidecar:
        output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for _atype, records in sampled.items():
        for rec in records:
            file_name = rec["file_name"]
            src = _resolve_image(dataset_root, file_name)
            if not src.exists():
                print(f"  ⚠  missing image, skipping: {src}")
                continue
            caption = _format_caption(
                str(rec.get("text", "")).strip(),
                trigger_word,
                trigger_mode,
            )
            if sidecar:
                # Write .txt alongside the source image (no image copy)
                txt_path = src.with_suffix(".txt")
                txt_path.write_text(caption, encoding="utf-8")
            else:
                dst_img = output_dir / Path(file_name).name
                shutil.copy2(src, dst_img)
                (output_dir / f"{Path(file_name).stem}.txt").write_text(caption, encoding="utf-8")
            written += 1
    return written


def main() -> int:
    args = parse_args()

    metadata_path = args.metadata.resolve()
    dataset_root = args.dataset_root.resolve()
    output_dir = args.out.resolve()

    if not metadata_path.exists():
        print(f"[ERROR] metadata not found: {metadata_path}")
        return 1
    if not dataset_root.exists():
        print(f"[ERROR] dataset root not found: {dataset_root}")
        return 1

    ratios = parse_ratios(args.ratios)

    print("Loading metadata...")
    records = load_metadata(metadata_path)
    print(f"  {len(records)} total records")

    groups = group_by_type(records, args.type_column)
    print(f"  Types: {sorted(groups.keys())}")
    for t, recs in sorted(groups.items()):
        print(f"    {t}: {len(recs)}")

    if args.total > 0:
        print(f"\nSampling {args.total} examples with ratios:")
        for t, r in ratios.items():
            avail = len(groups.get(t, []))
            target = round(args.total * r)
            print(f"  {t}: {r*100:.0f}% → {target} of {avail} available")
    else:
        print(f"\nUsing all {len(records)} examples (--total not set).")

    sampled = sample(groups, ratios, args.total, args.seed)

    total_sampled = sum(len(v) for v in sampled.values())
    print("\nActual distribution:")
    for t, recs in sampled.items():
        pct = (len(recs) / total_sampled * 100) if total_sampled else 0
        print(f"  {t}: {len(recs)} ({pct:.1f}%)")
    print(f"  ── total: {total_sampled}")

    if args.dry_run:
        print("\n[dry-run] No files written.")
        return 0

    print(f"\nTrigger mode: {args.trigger_mode}")
    if args.trigger_mode != "none":
        print(f"Trigger word: {args.trigger_word}")
        if args.trigger_mode == "placeholder":
            print(f"Captions will use [trigger] placeholder — toolkit replaces at train time")
        else:
            print(f"Captions will be prefixed with: {args.trigger_word}")

    if args.sidecar:
        print(f"\nWriting sidecar .txt files alongside source images...")
    else:
        print(f"\nWriting to {output_dir}...")
    n = write_output(sampled, dataset_root, output_dir,
                     trigger_word=args.trigger_word,
                     trigger_mode=args.trigger_mode,
                     sidecar=args.sidecar)
    if args.sidecar:
        print(f"Done — {n} sidecar .txt files written alongside images")
    else:
        print(f"Done — {n} image+txt pairs written to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

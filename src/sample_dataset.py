from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.dataset_sampling import load_metadata_rows, stratified_sample_rows, write_metadata_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a stratified metadata subset for LoRA training experiments.")
    parser.add_argument("--dataset-root", type=Path, default=Path("dataset"))
    parser.add_argument("--metadata-file", default="metadata.jsonl")
    parser.add_argument("--output-metadata", type=Path, required=True)
    parser.add_argument("--target-size", type=int, required=True)
    parser.add_argument("--stratify-column", default="asset_family")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--report-path", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    dataset_root = args.dataset_root.resolve()
    metadata_path = (dataset_root / args.metadata_file).resolve()
    rows = load_metadata_rows(metadata_path)

    sampled_rows, report = stratified_sample_rows(
        rows=rows,
        target_size=args.target_size,
        stratify_column=args.stratify_column,
        seed=args.seed,
    )

    output_metadata = args.output_metadata.resolve()
    write_metadata_rows(output_metadata, sampled_rows)

    report_path = args.report_path.resolve() if args.report_path else output_metadata.with_suffix(".report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")

    print(f"[INFO] Source metadata: {metadata_path}")
    print(f"[INFO] Sampled metadata: {output_metadata}")
    print(f"[INFO] Sampling report: {report_path}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


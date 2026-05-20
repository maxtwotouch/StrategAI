from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image

from src.common import write_json


@dataclass
class ValidationIssue:
    level: str
    code: str
    row: int
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate HF-style text-to-image dataset for Ostris ai-toolkit fine-tuning.")
    parser.add_argument("--dataset-root", type=Path, default=Path("dataset"), help="Path to the HF-ready dataset root.")
    parser.add_argument(
        "--mode",
        choices=["hf_jsonl", "sidecar_txt"],
        default="hf_jsonl",
        help="Validation mode: metadata jsonl or sidecar .txt captions next to images.",
    )
    parser.add_argument("--metadata-file", default="metadata.jsonl", help="Metadata JSONL filename, relative to dataset root.")
    parser.add_argument("--image-dir", default="images", help="Image directory used in sidecar_txt mode.")
    parser.add_argument(
        "--caption-txt-extension",
        default=".txt",
        help="Caption sidecar extension used in sidecar_txt mode.",
    )
    parser.add_argument(
        "--image-extensions",
        default="png,jpg,jpeg,webp",
        help="Comma-separated image extensions for sidecar_txt mode.",
    )
    parser.add_argument("--expected-resolution", type=int, default=1024, help="Expected width/height in pixels (square).")
    parser.add_argument(
        "--allow-non-square",
        action="store_true",
        help="Allow non-square image files. If omitted, images must be square.",
    )
    parser.add_argument(
        "--caption-warn-chars",
        type=int,
        default=700,
        help="Warn when a caption exceeds this character count.",
    )
    parser.add_argument(
        "--min-per-stratum",
        type=int,
        default=30,
        help="Minimum recommended samples per asset_family/style bucket.",
    )
    parser.add_argument(
        "--require-trigger-token",
        type=str,
        default="",
        help="If set, captions must begin with this token (example: <sks>).",
    )
    return parser.parse_args()


def validate_row(
    row_idx: int,
    payload: Dict[str, object],
    dataset_root: Path,
    expected_resolution: int,
    allow_non_square: bool,
    caption_warn_chars: int,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    required_keys = ("id", "file_name", "text")

    for key in required_keys:
        if key not in payload:
            issues.append(ValidationIssue("error", "missing_key", row_idx, f"Missing required key '{key}'."))

    if issues:
        return issues

    file_name = str(payload["file_name"])
    text = str(payload["text"])

    if not text.strip():
        issues.append(ValidationIssue("error", "empty_caption", row_idx, "Caption text is empty."))
    elif len(text) > caption_warn_chars:
        issues.append(
            ValidationIssue(
                "warning",
                "caption_too_long",
                row_idx,
                f"Caption length is {len(text)} chars; consider shortening for more stable conditioning.",
            )
        )

    image_path = (dataset_root / file_name).resolve()
    if not image_path.exists():
        issues.append(ValidationIssue("error", "missing_image", row_idx, f"Image not found: {image_path}"))
        return issues

    try:
        with Image.open(image_path) as img:
            width, height = img.size
    except Exception as exc:  # noqa: BLE001
        issues.append(ValidationIssue("error", "image_open_failed", row_idx, f"Failed to read image: {exc}"))
        return issues

    if width != expected_resolution or height != expected_resolution:
        issues.append(
            ValidationIssue(
                "warning",
                "resolution_mismatch",
                row_idx,
                f"Image size is {width}x{height}; expected {expected_resolution}x{expected_resolution}.",
            )
        )

    if not allow_non_square and width != height:
        issues.append(
            ValidationIssue("error", "non_square", row_idx, f"Image size is {width}x{height}; square image required.")
        )

    return issues


def _validate_trigger_token(text: str, trigger_token: str, row_idx: int) -> Optional[ValidationIssue]:
    token = trigger_token.strip()
    if not token:
        return None
    if text.strip().startswith(token):
        return None
    return ValidationIssue("warning", "missing_trigger_prefix", row_idx, f"Caption does not start with trigger token '{token}'.")


def _format_recommendation(rows_parsed: int, asset_counts: Counter, min_per_stratum: int) -> str:
    if rows_parsed == 0:
        return "Dataset is empty. Add images and captions before training."

    num_styles = len(asset_counts)
    if num_styles == 0:
        return "No 'asset_family' column found. If this is intentional, set --min-per-stratum 0 to suppress."

    under_min = [name for name, count in asset_counts.items() if count < min_per_stratum]
    if under_min:
        buckets = ", ".join(f"{n}({asset_counts[n]})" for n in under_min)
        return (
            f"Low sample counts in style buckets: {buckets}. "
            f"Recommended minimum is {min_per_stratum} per style. "
            f"Training on <{min_per_stratum} samples per style often causes overfitting or poor generalization."
        )

    return "Dataset appears reasonably sized for training."


def main() -> int:
    args = parse_args()

    dataset_root = args.dataset_root.resolve()
    metadata_path = dataset_root / args.metadata_file
    issues: List[ValidationIssue] = []

    rows_total = 0
    rows_parsed = 0
    unique_ids = set()
    unique_files = set()
    caption_lengths: List[int] = []
    asset_families: List[str] = []

    if args.mode == "hf_jsonl":
        if not metadata_path.exists():
            print(f"[ERROR] metadata file not found: {metadata_path}")
            return 1

        with metadata_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                rows_total += 1
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    issues.append(ValidationIssue("error", "json_parse_error", line_number, str(exc)))
                    continue

                if not isinstance(payload, dict):
                    issues.append(
                        ValidationIssue("error", "invalid_row_type", line_number, f"Expected object, got {type(payload).__name__}")
                    )
                    continue

                rows_parsed += 1
                row_issues = validate_row(
                    row_idx=line_number,
                    payload=payload,
                    dataset_root=dataset_root,
                    expected_resolution=args.expected_resolution,
                    allow_non_square=args.allow_non_square,
                    caption_warn_chars=args.caption_warn_chars,
                )
                issues.extend(row_issues)

                if "id" in payload:
                    unique_ids.add(str(payload["id"]))
                if "file_name" in payload:
                    unique_files.add(str(payload["file_name"]))
                if "text" in payload:
                    text = str(payload["text"])
                    caption_lengths.append(len(text))
                    trigger_issue = _validate_trigger_token(text=text, trigger_token=args.require_trigger_token, row_idx=line_number)
                    if trigger_issue is not None:
                        issues.append(trigger_issue)
                family = payload.get("asset_family")
                if family is not None:
                    asset_families.append(str(family))
    else:
        image_dir = (dataset_root / args.image_dir).resolve()
        if not image_dir.exists():
            print(f"[ERROR] image directory not found: {image_dir}")
            return 1

        cap_ext = args.caption_txt_extension if args.caption_txt_extension.startswith(".") else f".{args.caption_txt_extension}"
        image_exts = {chunk.strip().lower().lstrip(".") for chunk in args.image_extensions.split(",") if chunk.strip()}

        line_number = 0
        for image_path in sorted(image_dir.rglob("*")):
            if not image_path.is_file() or image_path.suffix.lower().lstrip(".") not in image_exts:
                continue

            line_number += 1
            rows_total += 1
            relative_image = image_path.resolve().relative_to(dataset_root)
            caption_path = image_path.with_suffix(cap_ext)
            if not caption_path.exists():
                issues.append(
                    ValidationIssue("error", "missing_caption_txt", line_number, f"Caption file not found: {caption_path}")
                )
                continue

            text = caption_path.read_text(encoding="utf-8").strip()
            payload = {
                "id": image_path.stem,
                "file_name": str(relative_image),
                "text": text,
            }
            rows_parsed += 1
            row_issues = validate_row(
                row_idx=line_number,
                payload=payload,
                dataset_root=dataset_root,
                expected_resolution=args.expected_resolution,
                allow_non_square=args.allow_non_square,
                caption_warn_chars=args.caption_warn_chars,
            )
            issues.extend(row_issues)

            trigger_issue = _validate_trigger_token(text=text, trigger_token=args.require_trigger_token, row_idx=line_number)
            if trigger_issue is not None:
                issues.append(trigger_issue)

            unique_ids.add(payload["id"])
            unique_files.add(payload["file_name"])
            caption_lengths.append(len(text))
            family = image_path.parent.resolve().relative_to(image_dir)
            asset_families.append(str(family) if str(family) != "." else "__root__")

    errors = sum(1 for i in issues if i.level == "error")
    warnings = sum(1 for i in issues if i.level == "warning")
    asset_counts = Counter(asset_families)

    report = {
        "dataset_root": str(dataset_root),
        "mode": args.mode,
        "metadata_path": str(metadata_path),
        "rows_total": rows_total,
        "rows_parsed": rows_parsed,
        "unique_ids": len(unique_ids),
        "unique_file_names": len(unique_files),
        "errors": errors,
        "warnings": warnings,
        "status": "pass" if errors == 0 else "fail",
        "expected_resolution": args.expected_resolution,
        "asset_family_counts": dict(sorted(asset_counts.items())),
        "recommendation": _format_recommendation(rows_parsed, asset_counts, args.min_per_stratum),
        "caption_chars": {
            "min": min(caption_lengths) if caption_lengths else 0,
            "max": max(caption_lengths) if caption_lengths else 0,
            "avg": round((sum(caption_lengths) / len(caption_lengths)), 2) if caption_lengths else 0,
            "warn_threshold": args.caption_warn_chars,
        },
    }

    report_path = dataset_root / "validation_report.ostris.json"
    issues_path = dataset_root / "validation_issues.ostris.jsonl"
    write_json(report_path, report)

    with issues_path.open("w", encoding="utf-8") as handle:
        for issue in issues:
            handle.write(json.dumps(issue.__dict__) + "\n")

    print(json.dumps(report, indent=2))
    print(f"[INFO] Wrote report: {report_path}")
    print(f"[INFO] Wrote issues: {issues_path}")

    if rows_parsed > 0 and len(asset_counts) > 0:
        min_count = min(asset_counts.values())
        if min_count < args.min_per_stratum:
            print(f"[WARN] Some style buckets have < {args.min_per_stratum} samples. Consider collecting more data.")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())


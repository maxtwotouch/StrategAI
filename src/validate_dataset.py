from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from PIL import Image


def _read_yaml(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}, got {type(data).__name__}")
    return data


def _write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


@dataclass
class ValidationIssue:
    level: str
    code: str
    row: int
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate dataset for Ostris ai-toolkit fine-tuning.")
    parser.add_argument("--dataset-root", type=Path, default=Path("dataset"), help="Path to dataset root.")
    parser.add_argument(
        "--mode",
        choices=["hf_jsonl", "sidecar_txt"],
        default="hf_jsonl",
        help="Validation mode: metadata jsonl or sidecar .txt captions.",
    )
    parser.add_argument("--metadata-file", default="metadata.jsonl", help="Metadata JSONL filename.")
    parser.add_argument("--image-dir", default="hf", help="Image directory for sidecar_txt mode.")
    parser.add_argument("--caption-txt-extension", default=".txt", help="Caption sidecar extension.")
    parser.add_argument("--image-extensions", default="png,jpg,jpeg", help="Comma-separated image extensions.")
    parser.add_argument("--expected-resolution", type=int, default=1024, help="Expected width/height in pixels.")
    parser.add_argument("--allow-non-square", action="store_true", help="Allow non-square images.")
    parser.add_argument("--caption-warn-chars", type=int, default=700, help="Warn when caption exceeds this length.")
    parser.add_argument("--min-per-stratum", type=int, default=30, help="Minimum recommended samples per bucket.")
    parser.add_argument(
        "--training-config",
        type=Path,
        default=None,
        help="Path to training config (e.g. config/lora_4b.yaml) to read trigger_word for caption validation.",
    )
    parser.add_argument(
        "--trigger-mode",
        choices=["expected", "required", "forbidden", "ignore"],
        default="expected",
        help="How to validate trigger token presence in captions. "
             "expected: warn if trigger NOT in caption (guide recommendation). "
             "required: error if trigger NOT in caption. "
             "forbidden: warn if trigger IS in caption (legacy behavior). "
             "ignore: skip trigger checks entirely.",
    )
    parser.add_argument(
        "--trigger-word-override",
        type=str,
        default=None,
        help="Override trigger_word from training config (e.g. '<tdmp>' or '[trigger]'). "
             "Use '[trigger]' when validating placeholder-based captions.",
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


def _check_trigger_in_caption(
    text: str, trigger_word: str, row_idx: int, trigger_mode: str
) -> Optional[ValidationIssue]:
    """Validate trigger token presence in captions based on trigger_mode.

    Captions should contain the trigger word (or [trigger] placeholder) so the
    model learns to bind style+pose to it. The toolkit also auto-prepends
    trigger_word at train time if not already present.

    Modes:
      expected  — warn if trigger NOT in caption (default)
      required  — error if trigger NOT in caption
      forbidden — warn if trigger IS in caption (legacy: want toolkit-only injection)
      ignore    — no check
    """
    if not trigger_word.strip() or trigger_mode == "ignore":
        return None

    has_trigger = trigger_word.strip() in text

    if trigger_mode == "forbidden" and has_trigger:
        return ValidationIssue(
            "warning",
            "trigger_in_caption",
            row_idx,
            f"Caption contains trigger word '{trigger_word}'. "
            "The toolkit injects this automatically; consider removing it for cleaner, reusable captions.",
        )

    if trigger_mode in ("expected", "required") and not has_trigger:
        level = "error" if trigger_mode == "required" else "warning"
        code = "trigger_missing" if trigger_mode == "required" else "trigger_missing_warn"
        return ValidationIssue(
            level,
            code,
            row_idx,
            f"Caption does not contain trigger word '{trigger_word}'. "
            "Captions should include the trigger so the model binds unexplained "
            "pixel information (style + camera pose) to it. "
            "Use '[trigger]' placeholder for portable captions.",
        )

    return None


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

    # ── Trigger word ──────────────────────────────────────────────────────
    trigger_word: str = ""
    if args.trigger_word_override is not None:
        trigger_word = args.trigger_word_override.strip()
    elif args.training_config is not None:
        training_cfg = _read_yaml(args.training_config.resolve())
        config_block = training_cfg.get("config", {})
        process_list = config_block.get("process", [])
        process_block = process_list[0] if isinstance(process_list, list) and process_list else {}
        trigger_word = str(process_block.get("trigger_word", "")).strip()
    if trigger_word:
        print(f"[INFO] Trigger word: '{trigger_word}' — mode: {args.trigger_mode}")

    rows_total = 0
    rows_parsed = 0
    unique_ids = set()
    unique_files = set()
    caption_lengths: List[int] = []
    asset_families: List[str] = []
    trigger_warnings = 0

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

                    if trigger_word:
                        tw_issue = _check_trigger_in_caption(text, trigger_word, line_number, args.trigger_mode)
                        if tw_issue is not None:
                            issues.append(tw_issue)
                            trigger_warnings += 1

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
            # Use the symlink path (not resolved target) for relative_to,
            # otherwise symlinks pointing outside dataset_root break validation.
            relative_image = image_path.relative_to(dataset_root)
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

            if trigger_word:
                tw_issue = _check_trigger_in_caption(text, trigger_word, line_number, args.trigger_mode)
                if tw_issue is not None:
                    issues.append(tw_issue)
                    trigger_warnings += 1

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

    if trigger_word:
        report["trigger_word"] = trigger_word
        report["trigger_in_captions"] = trigger_warnings

    report_path = dataset_root / "validation_report.ostris.json"
    issues_path = dataset_root / "validation_issues.ostris.jsonl"
    _write_json(report_path, report)

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

#!/usr/bin/env python3
"""Validate a Hugging Face-ready dataset export.

This script validates `prepare_hf_dataset.py` outputs under an `hf_ready` directory.
It is designed for local QA and CI use with deterministic reports and exit codes.

Expected layout:
- <hf_dir>/metadata.jsonl
- <hf_dir>/images/*.png
- optional: <hf_dir>/images/*.txt captions
- optional: <hf_dir>/prepare_hf_report.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = ("id", "file_name", "text")
IMAGE_EXTENSIONS = {".png"}


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    row: int | None = None
    file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.row is not None:
            out["row"] = self.row
        if self.file is not None:
            out["file"] = self.file
        return out


@dataclass
class ValidationState:
    hf_dir: Path
    metadata_path: Path
    images_dir: Path
    expected_images: set[str]
    seen_ids: set[str]
    seen_file_names: set[str]
    issues: list[Issue]


@dataclass(frozen=True)
class ValidationConfig:
    require_caption_txt: bool
    check_orphans: bool
    check_prepare_report: bool
    fail_on_warnings: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a prepared Hugging Face dataset export for publishing and fine-tuning.",
    )
    parser.add_argument(
        "hf_dir",
        type=Path,
        help="Path to the prepared dataset root (typically ./dataset/hf_ready).",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Where to write JSON summary report (default: <hf_dir>/validation_report.json).",
    )
    parser.add_argument(
        "--issues-path",
        type=Path,
        default=None,
        help="Where to write JSONL issue log (default: <hf_dir>/validation_issues.jsonl).",
    )
    parser.add_argument(
        "--require-caption-txt",
        action="store_true",
        help="Require an image-matching .txt caption next to every referenced .png.",
    )
    parser.add_argument(
        "--skip-orphan-check",
        action="store_true",
        help="Skip checking for orphan image files not referenced by metadata.jsonl.",
    )
    parser.add_argument(
        "--skip-prepare-report-check",
        action="store_true",
        help="Skip checking count consistency against prepare_hf_report.json.",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Return non-zero if any warning is found.",
    )
    return parser.parse_args()


def add_issue(state: ValidationState, severity: str, code: str, message: str, row: int | None = None, file: str | None = None) -> None:
    state.issues.append(Issue(severity=severity, code=code, message=message, row=row, file=file))


def init_state(hf_dir: Path) -> ValidationState:
    return ValidationState(
        hf_dir=hf_dir,
        metadata_path=hf_dir / "metadata.jsonl",
        images_dir=hf_dir / "images",
        expected_images=set(),
        seen_ids=set(),
        seen_file_names=set(),
        issues=[],
    )


def validate_layout(state: ValidationState) -> bool:
    ok = True
    if not state.hf_dir.exists():
        add_issue(state, "error", "MISSING_HF_DIR", f"Directory does not exist: {state.hf_dir}")
        ok = False
    if not state.metadata_path.is_file():
        add_issue(state, "error", "MISSING_METADATA_JSONL", f"Missing metadata file: {state.metadata_path}")
        ok = False
    if not state.images_dir.is_dir():
        add_issue(state, "error", "MISSING_IMAGES_DIR", f"Missing images directory: {state.images_dir}")
        ok = False
    return ok


def _row_field_error(state: ValidationState, row_num: int, field: str, detail: str) -> None:
    add_issue(
        state,
        severity="error",
        code="INVALID_ROW_FIELD",
        message=f"Row {row_num}: field `{field}` {detail}",
        row=row_num,
    )


def _require_string_field(state: ValidationState, row_num: int, row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str):
        _row_field_error(state, row_num, field, "must be a string")
        return ""
    stripped = value.strip()
    if not stripped:
        _row_field_error(state, row_num, field, "must be non-empty")
        return ""
    return stripped


def validate_metadata_rows(state: ValidationState, config: ValidationConfig) -> dict[str, int]:
    rows_total = 0
    parsed_ok = 0

    with state.metadata_path.open("r", encoding="utf-8") as f:
        for row_num, line in enumerate(f, start=1):
            if not line.strip():
                continue

            rows_total += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                add_issue(
                    state,
                    severity="error",
                    code="INVALID_JSON",
                    message=f"Row {row_num} has invalid JSON: {exc}",
                    row=row_num,
                )
                continue

            if not isinstance(row, dict):
                add_issue(
                    state,
                    severity="error",
                    code="INVALID_ROW_TYPE",
                    message=f"Row {row_num} must decode to a JSON object",
                    row=row_num,
                )
                continue

            for field in REQUIRED_FIELDS:
                if field not in row:
                    add_issue(
                        state,
                        severity="error",
                        code="MISSING_REQUIRED_FIELD",
                        message=f"Row {row_num} missing required field `{field}`",
                        row=row_num,
                    )

            image_id = _require_string_field(state, row_num, row, "id")
            file_name = _require_string_field(state, row_num, row, "file_name")
            text = row.get("text")
            if not isinstance(text, str):
                _row_field_error(state, row_num, "text", "must be a string")
                text_value = ""
            else:
                text_value = text.strip()
                if not text_value:
                    add_issue(
                        state,
                        severity="warning",
                        code="EMPTY_CAPTION",
                        message=f"Row {row_num} has an empty caption in `text`",
                        row=row_num,
                    )

            if image_id:
                if image_id in state.seen_ids:
                    add_issue(
                        state,
                        severity="error",
                        code="DUPLICATE_ID",
                        message=f"Row {row_num} duplicates id `{image_id}`",
                        row=row_num,
                    )
                else:
                    state.seen_ids.add(image_id)

            if file_name:
                if file_name in state.seen_file_names:
                    add_issue(
                        state,
                        severity="error",
                        code="DUPLICATE_FILE_NAME",
                        message=f"Row {row_num} duplicates file_name `{file_name}`",
                        row=row_num,
                    )
                else:
                    state.seen_file_names.add(file_name)

                referenced_image = state.hf_dir / file_name
                state.expected_images.add(str(referenced_image.resolve()))
                if referenced_image.suffix.lower() not in IMAGE_EXTENSIONS:
                    add_issue(
                        state,
                        severity="warning",
                        code="UNEXPECTED_IMAGE_EXTENSION",
                        message=f"Row {row_num} references non-PNG image `{file_name}`",
                        row=row_num,
                    )
                if not referenced_image.exists():
                    add_issue(
                        state,
                        severity="error",
                        code="MISSING_REFERENCED_IMAGE",
                        message=f"Row {row_num} references missing file `{file_name}`",
                        row=row_num,
                        file=file_name,
                    )
                elif not referenced_image.is_file():
                    add_issue(
                        state,
                        severity="error",
                        code="REFERENCED_IMAGE_NOT_A_FILE",
                        message=f"Row {row_num} reference is not a file: `{file_name}`",
                        row=row_num,
                        file=file_name,
                    )

                if config.require_caption_txt:
                    caption_path = referenced_image.with_suffix(".txt")
                    if not caption_path.is_file():
                        add_issue(
                            state,
                            severity="error",
                            code="MISSING_CAPTION_TXT",
                            message=f"Row {row_num} missing caption txt `{caption_path.name}`",
                            row=row_num,
                            file=str(caption_path.relative_to(state.hf_dir)),
                        )

            parsed_ok += 1

    if rows_total == 0:
        add_issue(state, "error", "EMPTY_METADATA_JSONL", "metadata.jsonl has no non-empty rows")

    return {
        "rows_total": rows_total,
        "rows_parsed": parsed_ok,
    }


def validate_orphans(state: ValidationState) -> None:
    for png_path in sorted(state.images_dir.glob("*.png")):
        resolved = str(png_path.resolve())
        if resolved not in state.expected_images:
            add_issue(
                state,
                severity="warning",
                code="ORPHAN_IMAGE",
                message=f"Image is not referenced by metadata.jsonl: {png_path.name}",
                file=str(png_path.relative_to(state.hf_dir)),
            )


def validate_prepare_report(state: ValidationState, rows_total: int) -> None:
    report_path = state.hf_dir / "prepare_hf_report.json"
    if not report_path.is_file():
        add_issue(
            state,
            severity="warning",
            code="MISSING_PREPARE_REPORT",
            message="prepare_hf_report.json not found; count consistency check skipped",
        )
        return

    try:
        report_obj = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        add_issue(
            state,
            severity="warning",
            code="INVALID_PREPARE_REPORT_JSON",
            message=f"Could not parse prepare_hf_report.json: {exc}",
            file="prepare_hf_report.json",
        )
        return

    converted = report_obj.get("converted")
    if not isinstance(converted, int):
        add_issue(
            state,
            severity="warning",
            code="PREPARE_REPORT_MISSING_CONVERTED",
            message="prepare_hf_report.json missing integer `converted` field",
            file="prepare_hf_report.json",
        )
        return

    if converted != rows_total:
        add_issue(
            state,
            severity="warning",
            code="COUNT_MISMATCH",
            message=f"prepare_hf_report converted={converted} does not match metadata rows={rows_total}",
            file="prepare_hf_report.json",
        )


def write_outputs(state: ValidationState, report_path: Path, issues_path: Path, rows_total: int, rows_parsed: int) -> dict[str, Any]:
    errors = sum(1 for issue in state.issues if issue.severity == "error")
    warnings = sum(1 for issue in state.issues if issue.severity == "warning")

    report = {
        "hf_dir": str(state.hf_dir),
        "metadata_path": str(state.metadata_path),
        "images_dir": str(state.images_dir),
        "rows_total": rows_total,
        "rows_parsed": rows_parsed,
        "unique_ids": len(state.seen_ids),
        "unique_file_names": len(state.seen_file_names),
        "errors": errors,
        "warnings": warnings,
        "status": "pass" if errors == 0 else "fail",
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    issues_path.parent.mkdir(parents=True, exist_ok=True)

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with issues_path.open("w", encoding="utf-8") as f:
        for issue in state.issues:
            f.write(json.dumps(issue.to_dict(), ensure_ascii=False) + "\n")

    return report


def run_validation(args: argparse.Namespace) -> int:
    hf_dir = args.hf_dir.resolve()
    report_path = args.report_path.resolve() if args.report_path else hf_dir / "validation_report.json"
    issues_path = args.issues_path.resolve() if args.issues_path else hf_dir / "validation_issues.jsonl"

    config = ValidationConfig(
        require_caption_txt=args.require_caption_txt,
        check_orphans=not args.skip_orphan_check,
        check_prepare_report=not args.skip_prepare_report_check,
        fail_on_warnings=args.fail_on_warnings,
    )

    state = init_state(hf_dir)
    if not validate_layout(state):
        report = write_outputs(
            state=state,
            report_path=report_path,
            issues_path=issues_path,
            rows_total=0,
            rows_parsed=0,
        )
        print(json.dumps(report, indent=2))
        return 1

    row_stats = validate_metadata_rows(state, config)

    if config.check_orphans:
        validate_orphans(state)

    if config.check_prepare_report:
        validate_prepare_report(state, rows_total=row_stats["rows_total"])

    report = write_outputs(
        state=state,
        report_path=report_path,
        issues_path=issues_path,
        rows_total=row_stats["rows_total"],
        rows_parsed=row_stats["rows_parsed"],
    )
    print(json.dumps(report, indent=2))

    if report["errors"] > 0:
        return 1
    if config.fail_on_warnings and report["warnings"] > 0:
        return 1
    return 0


def main() -> int:
    return run_validation(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())


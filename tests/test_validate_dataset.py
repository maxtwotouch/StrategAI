from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.validate_dataset import (
    ValidationIssue,
    _check_trigger_in_caption,
    validate_row,
)


def test_validate_row_missing_keys() -> None:
    issues = validate_row(
        row_idx=1,
        payload={},
        dataset_root=Path("."),
        expected_resolution=1024,
        allow_non_square=False,
        caption_warn_chars=700,
    )
    codes = {i.code for i in issues}
    assert "missing_key" in codes


def test_validate_row_empty_caption() -> None:
    issues = validate_row(
        row_idx=1,
        payload={"id": "1", "file_name": "images/1.png", "text": ""},
        dataset_root=Path("."),
        expected_resolution=1024,
        allow_non_square=False,
        caption_warn_chars=700,
    )
    assert any(i.code == "empty_caption" for i in issues)


def test_validate_row_missing_image() -> None:
    issues = validate_row(
        row_idx=1,
        payload={"id": "1", "file_name": "images/nonexistent.png", "text": "a caption"},
        dataset_root=Path("."),
        expected_resolution=1024,
        allow_non_square=False,
        caption_warn_chars=700,
    )
    assert any(i.code == "missing_image" for i in issues)


def test_validate_row_caption_too_long() -> None:
    long_text = "x" * 800
    issues = validate_row(
        row_idx=1,
        payload={"id": "1", "file_name": "images/nonexistent.png", "text": long_text},
        dataset_root=Path("."),
        expected_resolution=1024,
        allow_non_square=False,
        caption_warn_chars=700,
    )
    assert any(i.code == "caption_too_long" for i in issues)


def test_check_trigger_in_caption_warns_when_present() -> None:
    issue = _check_trigger_in_caption("a <tdmp> caption", "<tdmp>", row_idx=5)
    assert issue is not None
    assert issue.level == "warning"
    assert issue.code == "trigger_in_caption"
    assert issue.row == 5


def test_check_trigger_in_caption_none_when_absent() -> None:
    issue = _check_trigger_in_caption("a normal caption", "<tdmp>", row_idx=5)
    assert issue is None


def test_check_trigger_in_caption_none_for_empty_trigger() -> None:
    issue = _check_trigger_in_caption("a caption", "", row_idx=5)
    assert issue is None


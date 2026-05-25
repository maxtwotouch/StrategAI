from __future__ import annotations

from pathlib import Path

from src.validate_dataset import (
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


# ── Trigger check: forbidden mode (legacy behavior) ──────────────────────

def test_check_trigger_forbidden_warns_when_present() -> None:
    issue = _check_trigger_in_caption("a <tdmp> caption", "<tdmp>", row_idx=5, trigger_mode="forbidden")
    assert issue is not None
    assert issue.level == "warning"
    assert issue.code == "trigger_in_caption"
    assert issue.row == 5


def test_check_trigger_forbidden_none_when_absent() -> None:
    issue = _check_trigger_in_caption("a normal caption", "<tdmp>", row_idx=5, trigger_mode="forbidden")
    assert issue is None


# ── Trigger check: expected mode (guide-aligned default) ─────────────────

def test_check_trigger_expected_warns_when_absent() -> None:
    issue = _check_trigger_in_caption("a normal caption without trigger", "<tdmp>", row_idx=5, trigger_mode="expected")
    assert issue is not None
    assert issue.level == "warning"
    assert issue.code == "trigger_missing_warn"
    assert issue.row == 5


def test_check_trigger_expected_none_when_present() -> None:
    issue = _check_trigger_in_caption("a <tdmp> caption", "<tdmp>", row_idx=5, trigger_mode="expected")
    assert issue is None


# ── Trigger check: required mode ─────────────────────────────────────────

def test_check_trigger_required_errors_when_absent() -> None:
    issue = _check_trigger_in_caption("no trigger here", "<tdmp>", row_idx=5, trigger_mode="required")
    assert issue is not None
    assert issue.level == "error"
    assert issue.code == "trigger_missing"


def test_check_trigger_required_none_when_present() -> None:
    issue = _check_trigger_in_caption("a <tdmp> caption", "<tdmp>", row_idx=5, trigger_mode="required")
    assert issue is None


# ── Trigger check: ignore mode ───────────────────────────────────────────

def test_check_trigger_ignore_always_none() -> None:
    assert _check_trigger_in_caption("no trigger", "<tdmp>", row_idx=5, trigger_mode="ignore") is None
    assert _check_trigger_in_caption("a <tdmp> caption", "<tdmp>", row_idx=5, trigger_mode="ignore") is None


# ── Edge cases ───────────────────────────────────────────────────────────

def test_check_trigger_none_for_empty_trigger() -> None:
    issue = _check_trigger_in_caption("a caption", "", row_idx=5, trigger_mode="expected")
    assert issue is None


def test_check_trigger_placeholder_match() -> None:
    """[trigger] placeholder should be detected just like the real trigger word."""
    issue = _check_trigger_in_caption("[trigger] a caption", "[trigger]", row_idx=5, trigger_mode="expected")
    assert issue is None

from __future__ import annotations

import pytest

from src.training.extract_training_set import _format_caption, _resolve_image, group_by_type, parse_ratios, sample, write_output


def test_parse_ratios_basic():
    assert parse_ratios("structure=0.50,terrain=0.30,object=0.20,background=0.10") == {
        "structure": 0.50,
        "terrain": 0.30,
        "object": 0.20,
        "background": 0.10,
    }


def test_parse_ratios_handles_spaces():
    assert parse_ratios(" a = 0.50 ,  b = 0.50 ") == {"a": 0.50, "b": 0.50}


def test_parse_ratios_empty_produces_empty():
    assert parse_ratios("") == {}


def test_group_by_type():
    records = [
        {"file_name": "a.png", "asset_type": "structure"},
        {"file_name": "b.png", "asset_type": "structure"},
        {"file_name": "c.png", "asset_type": "terrain"},
    ]
    g = group_by_type(records, "asset_type")
    assert len(g["structure"]) == 2
    assert len(g["terrain"]) == 1


def test_group_by_type_unknown_default():
    g = group_by_type([{"file_name": "x.png"}], "asset_type")
    assert "__unknown__" in g


def test_sample_with_total():
    groups = {
        "structure": [{"file_name": f"s{i}.png"} for i in range(100)],
        "terrain": [{"file_name": f"t{i}.png"} for i in range(100)],
    }
    r = {"structure": 0.70, "terrain": 0.30}
    s = sample(groups, r, total=50, seed=42)
    assert len(s["structure"]) == 35
    assert len(s["terrain"]) == 15


def test_sample_total_zero_uses_all():
    groups = {
        "structure": [{"file_name": "a.png"}, {"file_name": "b.png"}],
        "terrain": [{"file_name": "c.png"}],
    }
    s = sample(groups, {}, total=0, seed=42)
    assert sum(len(v) for v in s.values()) == 3


def test_sample_caps_at_available():
    groups = {"structure": [{"file_name": f"s{i}.png"} for i in range(3)]}
    s = sample(groups, {"structure": 0.50}, total=20, seed=42)
    assert len(s["structure"]) == 3  # only 3 available


def test_sample_deterministic():
    groups = {"structure": [{"file_name": f"s{i}.png"} for i in range(50)]}
    r = {"structure": 1.0}
    a = sample(groups, r, total=10, seed=42)
    b = sample(groups, r, total=10, seed=42)
    assert a == b


def test_resolve_image_with_subdir(tmp_path):
    root = tmp_path / "dataset"
    root.mkdir()
    img = root / "images" / "sub" / "a.png"
    img.parent.mkdir(parents=True)
    img.touch()
    # file_name includes path prefix
    found = _resolve_image(root, "images/sub/a.png")
    assert found == img.resolve()


def test_resolve_image_falls_back_to_basename(tmp_path):
    root = tmp_path / "dataset"
    root.mkdir()
    img = root / "a.png"
    img.touch()
    found = _resolve_image(root, "images/a.png")
    # images/a.png doesn't exist, falls back to root/basename
    assert found == img.resolve()


# ── _format_caption ─────────────────────────────────────────────────────

def test_format_caption_none_mode_injects_angle_phrase():
    """Bare captions get angle phrase prepended."""
    assert _format_caption("a caption", "<tdp>", "none") == "top-down view. a caption"


def test_format_caption_manual_mode_prepends_trigger_and_angle():
    assert _format_caption("a caption", "<tdp>", "manual") == "<tdp> top-down view. a caption"


def test_format_caption_placeholder_mode_uses_brackets_and_angle():
    assert _format_caption("a caption", "<tdp>", "placeholder") == "[trigger] top-down view. a caption"


def test_format_caption_strips_whitespace():
    assert _format_caption("  padded caption  ", "<tdp>", "manual") == "<tdp> top-down view. padded caption"


def test_format_caption_none_strips_whitespace():
    assert _format_caption("  padded caption  ", "<tdp>", "none") == "top-down view. padded caption"


def test_format_caption_angle_phrase_is_idempotent():
    """Angle phrase is NOT duplicated if already present."""
    assert _format_caption("top-down view. a caption", "<tdp>", "none") == "top-down view. a caption"
    assert _format_caption("top-down view. a caption", "<tdp>", "manual") == "<tdp> top-down view. a caption"
    assert _format_caption("TOP-DOWN VIEW. a caption", "<tdp>", "placeholder") == "[trigger] TOP-DOWN VIEW. a caption"


# ── write_output ─────────────────────────────────────────────────────────

def test_write_output_sidecar_mode(tmp_path):
    """Sidecar mode writes .txt alongside source images, does not copy images."""
    root = tmp_path / "dataset"
    root.mkdir()
    img_dir = root / "images"
    img_dir.mkdir(parents=True)
    img = img_dir / "a.png"
    img.touch()
    out = tmp_path / "training_set"

    sampled = {"structure": [{"file_name": "images/a.png", "text": "test caption"}]}
    n = write_output(sampled, root, out,
                     trigger_word="<tdp>",
                     trigger_mode="placeholder",
                     sidecar=True)
    assert n == 1
    # Sidecar .txt written next to source image
    assert (img_dir / "a.txt").read_text() == "[trigger] top-down view. test caption"
    # Output dir NOT created (sidecar mode)
    assert not out.exists()


def test_write_output_extract_mode(tmp_path):
    """Extract mode copies images + .txt to output dir."""
    root = tmp_path / "dataset"
    root.mkdir()
    img_dir = root / "images"
    img_dir.mkdir(parents=True)
    img = img_dir / "a.png"
    img.touch()
    out = tmp_path / "training_set"

    sampled = {"structure": [{"file_name": "images/a.png", "text": "test caption"}]}
    n = write_output(sampled, root, out,
                     trigger_word="<tdp>",
                     trigger_mode="manual",
                     sidecar=False)
    assert n == 1
    # Image copied to output dir
    assert (out / "a.png").exists()
    # .txt written in output dir with trigger
    assert (out / "a.txt").read_text() == "<tdp> top-down view. test caption"

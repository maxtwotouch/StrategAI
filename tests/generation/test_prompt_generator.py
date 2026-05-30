"""Tests for prompt_generator.py — caption builders and template validation."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from src.generation.prompt_generator import (
    structure_caption,
    object_caption,
    terrain_caption,
    load_prompt_templates,
    ratio_to_counts,
)


# ── Caption builder tests ──────────────────────────────────────────────

def test_structure_caption_contains_top_down_view() -> None:
    result = structure_caption(
        structure="watchtower",
        theme="feudal military readiness",
        motif="smoke-stained chimneys and heavy use marks",
        personality="sturdy and fortified",
        detail="medium detail",
        complexity="multi-wing footprint",
        material="oak timber and plaster",
        condition="weathered",
        palette="earthy palette",
    )
    assert result.startswith("top-down view.")
    assert "watchtower" in result
    assert "feudal military readiness" in result
    assert "earthy palette" in result


def test_object_caption_contains_top_down_view() -> None:
    result = object_caption(
        obj="ancient oak tree",
        drama="storm-battered silhouette",
        complexity="layered silhouette",
        material="lush foliage and bark",
        condition="healthy growth",
        palette="earthy palette",
    )
    assert result.startswith("top-down view.")
    assert "ancient oak tree" in result
    assert "storm-battered silhouette" in result
    assert "earthy palette" in result


def test_terrain_caption_contains_top_down_view() -> None:
    result = terrain_caption(
        terrain_type="large hill",
        side_smoothness="soft smooth side slopes",
        seam_integrity="dense seam integration",
        complexity="dense readable forms",
        material="packed earth and dry grass",
        condition="weathered growth",
        palette="earthy palette",
    )
    assert result.startswith("top-down view.")
    assert "large hill" in result
    assert "wide flat top" in result
    assert "earthy palette" in result


def test_caption_builders_produce_template_free_text() -> None:
    """Captions must NOT contain structured tags like 'pose:' or 'subject:'."""
    s = structure_caption("inn building", "cozy harvest season", "careful repairs",
                          "humble and practical", "low detail", "simple footprint",
                          "oak timber and plaster", "well-maintained", "warm muted palette")
    assert "pose:" not in s
    assert "subject:" not in s
    assert "{" not in s  # no unexpanded template placeholders

    o = object_caption("jagged boulder", "wind-carved shape language",
                       "dense readable forms", "volcanic basalt texture",
                       "storm-worn", "cool medieval palette")
    assert "pose:" not in o
    assert "{" not in o


# ── Template loader tests ──────────────────────────────────────────────

def test_load_valid_templates(tmp_path: Path) -> None:
    """Valid template JSON loads successfully."""
    tmpl_path = tmp_path / "templates.json"
    data = {
        "schema_version": 1,
        "templates": {
            "structure": "<tdp> top-down view. {PROMPT_HERE}. Pixel art 16x16.",
            "object": "<tdp> top-down view. {PROMPT_HERE}. Pixel art 16x16.",
            "terrain": "<tdp> top-down view. {PROMPT_HERE}. Pixel art 16x16.",
        },
    }
    tmpl_path.write_text(json.dumps(data))
    result = load_prompt_templates(tmpl_path)
    assert result["structure"] == data["templates"]["structure"]


def test_load_templates_missing_key_raises(tmp_path: Path) -> None:
    """Missing 'structure' template raises ValueError."""
    tmpl_path = tmp_path / "bad_templates.json"
    data = {"schema_version": 1, "templates": {"object": "test", "terrain": "test"}}
    tmpl_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="structure"):
        load_prompt_templates(tmpl_path)


def test_load_templates_missing_prompt_here_raises(tmp_path: Path) -> None:
    """Template without {PROMPT_HERE} raises ValueError."""
    tmpl_path = tmp_path / "bad_templates.json"
    data = {
        "schema_version": 1,
        "templates": {
            "structure": "no placeholder here",
            "object": "{PROMPT_HERE}",
            "terrain": "{PROMPT_HERE}",
        },
    }
    tmpl_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="PROMPT_HERE"):
        load_prompt_templates(tmpl_path)


def test_load_templates_malformed_json_exits(tmp_path: Path) -> None:
    """Malformed JSON raises SystemExit with a helpful message."""
    tmpl_path = tmp_path / "bad.json"
    tmpl_path.write_text("{this is not valid json")
    with pytest.raises(SystemExit):
        load_prompt_templates(tmpl_path)


def test_load_templates_warns_on_deprecated_trigger(tmp_path: Path) -> None:
    """Template containing deprecated <sks> trigger emits a warning."""
    tmpl_path = tmp_path / "warn_templates.json"
    data = {
        "schema_version": 1,
        "templates": {
            "structure": "<sks> top-down view. {PROMPT_HERE}.",
            "object": "<tdp> top-down view. {PROMPT_HERE}.",
            "terrain": "<tdp> top-down view. {PROMPT_HERE}.",
        },
    }
    tmpl_path.write_text(json.dumps(data))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        load_prompt_templates(tmpl_path)
        assert len(w) >= 1
        assert any("<sks>" in str(warning.message) for warning in w)


# ── Ratio helper tests ─────────────────────────────────────────────────

def test_ratio_to_counts_simple() -> None:
    ratios = {"a": 0.5, "b": 0.3, "c": 0.2}
    counts = ratio_to_counts(100, ratios)
    assert sum(counts.values()) <= 100
    assert counts["a"] == 50
    assert counts["b"] == 30
    assert counts["c"] == 20


def test_ratio_to_counts_rounds_down() -> None:
    ratios = {"x": 0.33, "y": 0.33, "z": 0.34}
    counts = ratio_to_counts(10, ratios)
    # Total should not exceed target (may be slightly less due to floor rounding)
    assert sum(counts.values()) <= 10
    assert all(v >= 0 for v in counts.values())


def test_ratio_to_counts_zero_ratio() -> None:
    ratios = {"a": 0.0, "b": 1.0}
    counts = ratio_to_counts(50, ratios)
    assert counts["a"] == 0
    assert counts["b"] == 50


def test_ratio_to_counts_empty() -> None:
    """Empty ratios dict returns empty dict."""
    counts = ratio_to_counts(10, {})
    assert counts == {}

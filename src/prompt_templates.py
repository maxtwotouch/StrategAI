"""Centralized prompt template loader.

Loads and caches templates from ``config/prompt_templates.json``.
Each template has a ``prefix`` and ``suffix`` field.  The caller
provides the prose that goes between them (enum-injected descriptions,
free-form user text), and ``assemble()`` returns the final prompt string.

All prompt text lives in the JSON file.  Python code only contributes
enum injection maps and assembly logic — never hardcoded style directives.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
#  Locate the JSON file
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATES_PATH = (
    Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    / "config"
    / "prompt_templates.json"
)

# ---------------------------------------------------------------------------
#  Cache
# ---------------------------------------------------------------------------

_templates: dict[str, dict[str, str]] | None = None


def _load() -> dict[str, dict[str, str]]:
    """Load and cache the template JSON (called once, lazily)."""
    global _templates
    if _templates is None:
        with open(_PROMPT_TEMPLATES_PATH, "r") as fh:
            data: dict[str, Any] = json.load(fh)
        _templates = data["templates"]
    return _templates


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------


def get_template(family: str) -> dict[str, str]:
    """Return ``{"prefix": ..., "suffix": ...}`` for a prompt family.

    Raises ``KeyError`` if the family is not defined.
    """
    tmpl = _load().get(family)
    if tmpl is None:
        available = ", ".join(sorted(_load().keys()))
        raise KeyError(
            f"Unknown prompt template family '{family}'. "
            f"Available: {available}"
        )
    return tmpl


def assemble(family: str, inner: str) -> str:
    """Build a complete prompt by wrapping *inner* prose in the template.

    Parameters
    ----------
    family : str
        Template key (e.g. ``"structure"``, ``"leader_splash"``).
    inner : str
        The enum-injected prose + user description that goes between
        ``prefix`` and ``suffix``.

    Returns
    -------
    str
        The final prompt string ready for ComfyUI injection.
    """
    tmpl = get_template(family)
    prefix = tmpl["prefix"]
    suffix = tmpl["suffix"]
    # Insert inner prose between prefix and suffix with natural spacing
    return f"{prefix}{inner}{suffix}"


def list_families() -> list[str]:
    """Return all available template family keys."""
    return sorted(_load().keys())

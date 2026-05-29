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
import threading
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
_templates_lock = threading.Lock()


def _load() -> dict[str, dict[str, str]]:
    """Load and cache the template JSON (called once, lazily, thread-safe)."""
    global _templates
    if _templates is None:
        with _templates_lock:
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


# ---------------------------------------------------------------------------
#  Startup validation
# ---------------------------------------------------------------------------

_REQUIRED_TEMPLATE_KEYS = {"prefix", "suffix"}


def validate_all_templates() -> list[str]:
    """Validate every loaded template at startup.

    Checks that:
    - Every template has ``prefix`` and ``suffix`` keys.
    - Both ``prefix`` and ``suffix`` are non-empty strings
      (degenerate templates would produce broken prompts).

    Returns a list of error messages (empty = all good).  The application
    should refuse to start if any errors are returned.
    """
    errors: list[str] = []
    try:
        templates = _load()
    except FileNotFoundError as exc:
        return [f"Prompt templates file not found: {_PROMPT_TEMPLATES_PATH} — {exc}"]
    except json.JSONDecodeError as exc:
        return [f"Prompt templates file is not valid JSON: {_PROMPT_TEMPLATES_PATH} — {exc}"]
    except KeyError as exc:
        return [
            f"Prompt templates file is missing required 'templates' key: "
            f"{_PROMPT_TEMPLATES_PATH} — {exc}"
        ]

    for family, tmpl in templates.items():
        # Check required keys
        missing_keys = _REQUIRED_TEMPLATE_KEYS - set(tmpl.keys())
        if missing_keys:
            errors.append(
                f"Template '{family}' is missing required keys: {missing_keys}"
            )
            continue

        # Check that prefix and suffix are non-empty
        for key in _REQUIRED_TEMPLATE_KEYS:
            val = tmpl.get(key, "")
            if not isinstance(val, str) or not val.strip():
                errors.append(
                    f"Template '{family}' has empty or non-string '{key}' — "
                    f"prompt assembly would produce incomplete output"
                )

    if errors:
        logger = __import__("logging").getLogger(__name__)
        for err in errors:
            logger.error("Template validation error: %s", err)

    return errors

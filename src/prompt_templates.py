"""Centralized prompt template loader.

Loads and caches templates from ``config/prompt_templates.json``.
Each template has a ``template`` field containing a string with
``{placeholder}`` variables.  The caller provides keyword arguments
matching the placeholders, and ``render()`` returns the final prompt string.

Enum-injected prose and user descriptions are prepared by the per-pipeline
prompt builders (``src/leader/prompts.py``, ``src/tile/prompts.py``, etc.)
and passed as keyword arguments.  All prompt text lives in the JSON file.
Python code only contributes enum injection maps and assembly logic —
never hardcoded style directives.
"""

from __future__ import annotations

import json
import logging
import os
import re
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

# Regex to extract {placeholder} names from template strings
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


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
    """Return ``{"template": "..."}`` for a prompt family.

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


def get_placeholders(family: str) -> list[str]:
    """Return the ordered list of ``{placeholder}`` names in a template.

    Useful for validation and introspection — callers can check which
    keyword arguments a template expects.
    """
    tmpl = get_template(family)
    return _PLACEHOLDER_RE.findall(tmpl["template"])


def render(family: str, **kwargs: str) -> str:
    """Build a complete prompt by substituting placeholders in the template.

    Parameters
    ----------
    family : str
        Template key (e.g. ``"structure"``, ``"leader_splash"``).
    **kwargs : str
        Keyword arguments whose names match the ``{placeholders}`` in the
        template string.

    Returns
    -------
    str
        The final prompt string ready for ComfyUI injection.

    Raises
    ------
    KeyError
        If a placeholder in the template has no corresponding keyword argument,
        or if the template family is unknown.
    """
    tmpl = get_template(family)
    template_str = tmpl["template"]

    # Detect mismatches between placeholders and supplied kwargs
    placeholders = set(_PLACEHOLDER_RE.findall(template_str))
    kwarg_keys = set(kwargs.keys())
    extra = kwarg_keys - placeholders
    missing = placeholders - kwarg_keys
    if extra:
        logging.getLogger(__name__).debug(
            "Unused kwargs in template render (family=%s): %s", family, sorted(extra)
        )
    if missing:
        logging.getLogger(__name__).warning(
            "Missing placeholder values in template (family=%s): %s — "
            "literal {placeholder} text will appear in prompt",
            family, sorted(missing),
        )

    return template_str.format_map(kwargs)


def assemble(family: str, inner: str) -> str:
    """Legacy wrapper — build a prompt using ``{inner}`` placeholder.

    Deprecated in favor of ``render()``.  Provided for backward compatibility
    with code that has not yet been migrated to the new placeholder API.

    Parameters
    ----------
    family : str
        Template key (e.g. ``"structure"``).
    inner : str
        The prose to substitute for ``{inner}`` in the template.

    Returns
    -------
    str
        The final prompt string.
    """
    return render(family, inner=inner)


def list_families() -> list[str]:
    """Return all available template family keys."""
    return sorted(_load().keys())


# ---------------------------------------------------------------------------
#  Startup validation
# ---------------------------------------------------------------------------

_REQUIRED_TEMPLATE_KEYS = {"template"}


def validate_all_templates() -> list[str]:
    """Validate every loaded template at startup.

    Checks that:
    - Every template has a ``template`` key.
    - The ``template`` value is a non-empty string.
    - Every ``{placeholder}`` in the template is a valid Python identifier.

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

        # Check that template is a non-empty string
        template_str = tmpl.get("template", "")
        if not isinstance(template_str, str) or not template_str.strip():
            errors.append(
                f"Template '{family}' has empty or non-string 'template' — "
                f"prompt assembly would produce incomplete output"
            )
            continue

        # Check that all placeholders are valid identifiers
        placeholders = _PLACEHOLDER_RE.findall(template_str)
        for ph in placeholders:
            if not ph.isidentifier():
                errors.append(
                    f"Template '{family}' has invalid placeholder '{{{ph}}}' — "
                    f"must be a valid Python identifier"
                )

    if errors:
        logger = logging.getLogger(__name__)
        for err in errors:
            logger.error("Template validation error: %s", err)

    return errors

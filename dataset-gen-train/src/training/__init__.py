"""LoRA training pipeline — caption extraction, validation, derivation, config syncing."""

import importlib
import os
import sys

# ── Lazy imports (all runnable modules — avoid runpy RuntimeWarning) ───
# Each entry maps an attribute name to (module, attr) for on-demand loading.
_LAZY = {
    "ANGLE_PHRASE":              ("src.training.extract_training_set", "ANGLE_PHRASE"),
    "extract_training_set":      ("src.training.extract_training_set", "main"),
    "validate_dataset":          ("src.training.validate_dataset", "main"),
    "derive_captions":           ("src.training.derive_captions", "main"),
    "sync_validation_prompts":   ("src.training.sync_validation_prompts", "main"),
}


def __getattr__(name: str):
    if name in _LAZY:
        mod_name, attr = _LAZY[name]
        mod = importlib.import_module(mod_name)
        obj = getattr(mod, attr)
        globals()[name] = obj  # cache for subsequent accesses
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _check_runtime() -> None:
    """Validate the runtime environment before any training pipeline step.

    Call this at the top of main() in every training module.  Warns on:
      * missing virtual environment
      * Python version below 3.10

    These are warnings, not hard errors — the pipeline may still work, but
    the user should be aware of potential issues.
    """
    if not os.environ.get("VIRTUAL_ENV"):
        print(
            "[WARN] No virtual environment detected (VIRTUAL_ENV not set).\n"
            "       It is recommended to activate the project venv first:\n"
            "         python3 -m venv .venv && source .venv/bin/activate\n"
            "         pip install -r requirements.txt",
            file=sys.stderr,
        )
    if sys.version_info[:2] < (3, 10):
        print(
            f"[WARN] Python {'.'.join(map(str, sys.version_info[:2]))} detected — "
            f"this project requires Python >= 3.10.\n"
            f"       Some features may not work correctly.",
            file=sys.stderr,
        )


__all__ = [
    "_check_runtime",
    "ANGLE_PHRASE",
    "extract_training_set",
    "validate_dataset",
    "derive_captions",
    "sync_validation_prompts",
]

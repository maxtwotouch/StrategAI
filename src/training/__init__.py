"""LoRA training pipeline — caption extraction, validation, derivation, config syncing."""

import os
import sys
from pathlib import Path

from src.training.extract_training_set import main as extract_training_set, ANGLE_PHRASE
from src.training.validate_dataset import main as validate_dataset
from src.training.derive_captions import main as derive_captions
from src.training.sync_validation_prompts import main as sync_validation_prompts


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

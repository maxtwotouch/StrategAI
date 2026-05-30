"""Dataset generation pipeline — ComfyUI orchestration, metadata embedding, HF dataset export."""

import os
import sys
from pathlib import Path

from src.generation.image_metadata import read_metadata_from_file, embed_metadata_into_file
from src.generation.dataset_generator import main as generate_images
from src.generation.prepare_dataset import main as prepare_dataset


def _check_runtime() -> None:
    """Validate the runtime environment before any generation pipeline step.

    Call this at the top of main() in every generation module.  Warns on:
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
    "read_metadata_from_file",
    "embed_metadata_into_file",
    "generate_images",
    "prepare_dataset",
]

"""
Pre-flight readiness check before launching LoRA training.

Run this to verify your dataset, configs, and environment are aligned.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.common import read_yaml
from src.tokens import parse_token_config


class CheckResult:
    def __init__(self, name: str, passed: bool, message: str, advice: str = "") -> None:
        self.name = name
        self.passed = passed
        self.message = message
        self.advice = advice


def _check_file_exists(path: Path, description: str) -> CheckResult:
    if path.exists():
        return CheckResult(description, True, f"Found: {path}")
    return CheckResult(description, False, f"Missing: {path}", f"Create or check the path for {path.name}.")


def check_configs(root: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    for name in ("config/data.yaml", "config/model_flux2_klein_4b.yaml", "config/run_lora.yaml"):
        results.append(_check_file_exists(root / name, f"Config file: {name}"))
    return results


def check_ostris_command() -> CheckResult:
    cmd = os.environ.get("OSTRIS_TRAIN_COMMAND", "").strip() or "python run.py {config_path}"
    binary = cmd.split()[0]
    try:
        subprocess.run([binary, "--version"], capture_output=True, check=False)
        return CheckResult("Ostris ai-toolkit CLI accessible", True, f"`{binary}` responds to --version")
    except FileNotFoundError:
        return CheckResult(
            "Ostris ai-toolkit CLI accessible",
            False,
            f"`{binary}` not found in PATH.",
            "Activate your ai-toolkit environment, or set OSTRIS_TRAIN_COMMAND in .env to the full path.",
        )


def check_dataset(root: Path) -> List[CheckResult]:
    results: List[CheckResult] = []
    data_cfg = read_yaml(root / "config" / "data.yaml")
    dataset_root = (root / str(data_cfg.get("dataset_root", "dataset"))).resolve()
    caption_source = str(data_cfg.get("caption_source", "metadata")).strip().lower()

    # ── Token configuration check ──────────────────────────────────────────
    token_config = parse_token_config(data_cfg)
    all_tokens = token_config.token_values()

    if token_config.prepend_to_captions and not all_tokens:
        results.append(
            CheckResult(
                "Custom tokens",
                False,
                "prepend_to_captions=true but no tokens defined.",
                "Define at least a trigger token in config/data.yaml under tokens:",
            )
        )
    elif all_tokens:
        categories = []
        if token_config.trigger:
            categories.append(f"trigger={token_config.trigger.value}")
        if token_config.pose:
            categories.append(f"pose={token_config.pose.value}")
        if token_config.style:
            categories.append(f"style={token_config.style.value}")
        if token_config.asset:
            categories.append(f"asset={token_config.asset.value}")
        if token_config.custom:
            categories.append(f"custom=[{', '.join(t.value for t in token_config.custom)}]")
        cat_str = ", ".join(categories) if categories else "none"
        results.append(
            CheckResult(
                "Custom tokens",
                True,
                f"{len(all_tokens)} token(s) defined ({cat_str}), prepend={token_config.prepend_to_captions}",
            )
        )
    else:
        results.append(
            CheckResult(
                "Custom tokens",
                True,
                "No custom tokens defined (using raw captions).",
            )
        )

    if caption_source == "sidecar_txt":
        image_dir = (dataset_root / str(data_cfg.get("image_dir", "images"))).resolve()
        results.append(_check_file_exists(image_dir, "Dataset image directory"))
        if not image_dir.exists():
            return results

        image_exts = data_cfg.get("image_extensions", ["png", "jpg", "jpeg"])
        normalized_exts = {str(ext).lower().lstrip(".") for ext in image_exts if str(ext).strip()}
        caption_ext = str(data_cfg.get("caption_txt_extension", ".txt"))
        caption_ext = caption_ext if caption_ext.startswith(".") else f".{caption_ext}"

        image_paths = [
            p
            for p in image_dir.rglob("*")
            if p.is_file() and p.suffix.lower().lstrip(".") in normalized_exts
        ]
        sidecar_missing = 0
        sidecar_empty = 0
        for image_path in image_paths:
            caption_path = image_path.with_suffix(caption_ext)
            if not caption_path.exists():
                sidecar_missing += 1
                continue
            if not caption_path.read_text(encoding="utf-8").strip():
                sidecar_empty += 1

        results.append(
            CheckResult(
                "Image files discovered",
                len(image_paths) >= 2,
                f"{len(image_paths)} images",
                "Minimum 30-50 per style recommended.",
            )
        )
        results.append(
            CheckResult(
                "Sidecar caption files",
                sidecar_missing == 0 and sidecar_empty == 0,
                f"missing={sidecar_missing}, empty={sidecar_empty}",
                "Each image needs a non-empty sidecar caption file for sidecar_txt mode.",
            )
        )
        return results

    metadata_path = dataset_root / str(data_cfg.get("metadata_file", "metadata.jsonl"))
    results.append(_check_file_exists(metadata_path, "Dataset metadata"))

    if not metadata_path.exists():
        return results

    rows: List[Dict[str, Any]] = []
    with metadata_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    total = len(rows)
    results.append(CheckResult("Dataset rows", total >= 2, f"{total} rows", "Minimum 30-50 per style recommended."))

    families: Dict[str, int] = {}
    missing_images = 0
    for row in rows:
        fam = str(row.get("asset_family", "__missing__"))
        families[fam] = families.get(fam, 0) + 1
        img_path = dataset_root / str(row.get("file_name", ""))
        if not img_path.exists():
            missing_images += 1

    results.append(
        CheckResult(
            "Dataset balance",
            len(families) >= 1 and min(families.values()) >= 5,
            f"{len(families)} buckets; smallest = {min(families.values()) if families else 0}",
            "Aim for 30+ samples per style. One dominant bucket weakens style separation.",
        )
    )

    results.append(
        CheckResult(
            "Image files present",
            missing_images == 0,
            f"{missing_images} missing images" if missing_images else "All images found",
            "Ensure every file_name in metadata points to an existing image.",
        )
    )

    return results


def check_env_file(root: Path) -> CheckResult:
    env_path = root / ".env"
    if env_path.exists():
        return CheckResult(".env file", True, f"Found: {env_path}")
    example = root / ".env.example"
    return CheckResult(
        ".env file",
        False,
        "No .env file found.",
        f"Copy from example: cp {example.name} .env && source .env",
    )


def estimate_epochs(root: Path) -> Tuple[int, int, int, int]:
    """Return (num_train_steps, batch_size, grad_accum, effective_batch_size)."""
    run_cfg = read_yaml(root / "config" / "run_lora.yaml")
    data_cfg = read_yaml(root / "config" / "data.yaml")

    steps = int(run_cfg.get("num_train_steps", 1500))
    batch = int(run_cfg.get("train_batch_size", 1))
    grad = int(run_cfg.get("gradient_accumulation_steps", 4))
    eff_batch = int(batch * grad)
    return steps, batch, grad, eff_batch


def print_summary(results: List[CheckResult], steps: int, batch: int, grad: int, eff_batch: int) -> None:
    print("\n" + "=" * 60)
    print("PRE-FLIGHT SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    print(f"Passed: {passed} / {len(results)}  |  Failed: {failed}\n")

    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        print(f"{status}  {r.name}")
        print(f"       {r.message}")
        if r.advice:
            print(f"       → {r.advice}")
        print()

    print("-" * 60)
    print(f"Training config: {steps} steps | batch={batch} | grad_accum={grad} → effective batch={eff_batch}")
    print("-" * 60)

    if failed == 0:
        print("🚀  All checks passed. You are ready to train!")
        print("    Next: ./scripts/smoke_test.sh")
    else:
        print("⚠️   Fix failed checks before launching training.")
        print("    Start with: ./scripts/validate_dataset.sh")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-flight readiness check for Flux2 Klein LoRA training.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()

    root = args.root.resolve()
    results: List[CheckResult] = []

    results.extend(check_configs(root))
    results.append(check_env_file(root))
    results.append(check_ostris_command())
    results.extend(check_dataset(root))

    steps, batch, grad, eff_batch = estimate_epochs(root)
    print_summary(results, steps, batch, grad, eff_batch)

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

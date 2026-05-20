from __future__ import annotations

import subprocess
from pathlib import Path

from src.common import build_ostris_training_payload, read_yaml


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    dataset_root = root / "dataset"

    print("[SMOKE] Running dataset validation...")
    validate_cmd = [
        "python3",
        "-m",
        "src.validate_dataset",
        "--dataset-root",
        str(dataset_root),
        "--expected-resolution",
        "1024",
    ]
    result = subprocess.run(validate_cmd, check=False)
    if result.returncode != 0:
        print("[SMOKE] Dataset validation failed.")
        return result.returncode

    print("[SMOKE] Building in-memory Ostris ai-toolkit config payload...")
    data_cfg = read_yaml(root / "configs" / "data.yaml")
    model_cfg = read_yaml(root / "configs" / "model_flux2_klein_4b.yaml")
    run_cfg = read_yaml(root / "configs" / "run_lora.yaml")
    payload = build_ostris_training_payload(data_cfg, model_cfg, run_cfg)

    required_sections = ["toolkit", "task", "model", "dataset", "training", "lora"]
    missing = [section for section in required_sections if section not in payload]
    if missing:
        print(f"[SMOKE] Missing config sections: {missing}")
        return 1
    if payload.get("toolkit") != "ostris-ai-toolkit":
        print(f"[SMOKE] Unexpected toolkit value: {payload.get('toolkit')}")
        return 1

    print("[SMOKE] Dry-running train launcher...")
    train_cmd = [
        "python3",
        "-m",
        "src.train_lora",
        "--data-config",
        str(root / "configs" / "data.yaml"),
        "--model-config",
        str(root / "configs" / "model_flux2_klein_4b.yaml"),
        "--run-config",
        str(root / "configs" / "run_lora.yaml"),
        "--run-name",
        "smoke_test_run",
        "--dataset-size",
        "2",
        "--skip-size-check",
        "--dry-run",
    ]
    result = subprocess.run(train_cmd, check=False)
    if result.returncode != 0:
        print("[SMOKE] Train launcher dry-run failed.")
        return result.returncode

    print("[SMOKE] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

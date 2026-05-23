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
        "--data-config",
        str(root / "config" / "data.yaml"),
    ]
    result = subprocess.run(validate_cmd, check=False)
    if result.returncode != 0:
        print("[SMOKE] Dataset validation failed.")
        return result.returncode

    print("[SMOKE] Building in-memory Ostris ai-toolkit config payload...")
    data_cfg = read_yaml(root / "config" / "data.yaml")
    model_cfg = read_yaml(root / "config" / "model_flux2_klein_4b.yaml")
    run_cfg = read_yaml(root / "config" / "run_lora.yaml")
    payload = build_ostris_training_payload(data_cfg, model_cfg, run_cfg)

    # Validate the ai-toolkit job + config structure
    if payload.get("job") != "extension":
        print(f"[SMOKE] Missing 'job: extension' top-level key.")
        return 1
    config = payload.get("config", {})
    required_sections = ["process", "model", "datasets", "train", "network", "save", "sample"]
    missing = [section for section in required_sections if section not in config]
    if missing:
        print(f"[SMOKE] Missing config sections: {missing}")
        return 1
    if config["model"].get("arch") != "flux2_klein_4b":
        print(f"[SMOKE] Unexpected model arch: {config['model'].get('arch')}")
        return 1
    if config["train"].get("noise_scheduler") != "flowmatch":
        print(f"[SMOKE] Wrong noise_scheduler: {config['train'].get('noise_scheduler')}")
        return 1

    print("[SMOKE] Dry-running train launcher...")
    train_cmd = [
        "python3",
        "-m",
        "src.train_lora",
        "--data-config",
        str(root / "config" / "data.yaml"),
        "--model-config",
        str(root / "config" / "model_flux2_klein_4b.yaml"),
        "--run-config",
        str(root / "config" / "run_lora.yaml"),
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

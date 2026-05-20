from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Dict, List

from src.common import build_ostris_training_payload, read_yaml, write_yaml
from src.dataset_sampling import (
    apply_caption_transform,
    load_metadata_rows,
    load_sidecar_caption_rows,
    stratified_sample_rows,
    write_metadata_rows,
)


def _load_dotenv(root: Path) -> None:
    """Auto-load .env file if present so users don't forget to source it."""
    env_path = root / ".env"
    if not env_path.exists():
        return
    with env_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                if key and key not in os.environ:
                    os.environ[key] = value.strip().strip('"').strip("'")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch Flux2 Klein LoRA training with Ostris ai-toolkit.")
    parser.add_argument("--data-config", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--run-config", type=Path, required=True)
    parser.add_argument("--run-name", type=str, default="flux2_klein_lora_run")
    parser.add_argument("--output-root", type=Path, default=Path("runs"))
    parser.add_argument("--dry-run", action="store_true", help="Only generate config and print command.")
    parser.add_argument(
        "--resume-from",
        type=Path,
        default=None,
        help="Optional checkpoint path to resume from.",
    )
    parser.add_argument(
        "--dataset-size",
        type=int,
        default=None,
        help="Optional stratified sample size for this run. If set, metadata is sampled by asset family before training.",
    )
    parser.add_argument(
        "--stratify-column",
        type=str,
        default=None,
        help="Column used for ratio-preserving sampling (default: data config sampling.stratify_column or asset_family).",
    )
    parser.add_argument(
        "--sampling-seed",
        type=int,
        default=None,
        help="Random seed for sampling (default: data config sampling.seed or run seed).",
    )
    parser.add_argument(
        "--skip-size-check",
        action="store_true",
        help="Skip the minimum dataset size warning.",
    )
    parser.add_argument(
        "--trigger-token",
        type=str,
        default=None,
        help="Optional trigger token override. If set, this token can be prepended to captions.",
    )
    parser.add_argument(
        "--prepend-trigger-token",
        action="store_true",
        help="Prepend trigger token to every caption before training metadata is written.",
    )
    return parser.parse_args()


def _stringify_mapping(mapping: Dict[str, object]) -> Dict[str, str]:
    return {key: str(value) for key, value in mapping.items()}


def _resolve_train_command_template() -> str:
    template = os.environ.get("OSTRIS_TRAIN_COMMAND", "").strip()
    if template:
        return template
    return "ai-toolkit train lora --config {config_path}"


def _load_rows_for_training(data_cfg: Dict[str, object], dataset_root: Path) -> List[Dict[str, object]]:
    source = str(data_cfg.get("caption_source", "metadata")).strip().lower()
    metadata_file = str(data_cfg.get("metadata_file", "metadata.jsonl"))
    caption_column = str(data_cfg.get("caption_column", "text"))

    if source == "sidecar_txt":
        image_dir = (dataset_root / str(data_cfg.get("image_dir", "images"))).resolve()
        caption_extension = str(data_cfg.get("caption_txt_extension", ".txt"))
        image_extensions = data_cfg.get("image_extensions", ["png", "jpg", "jpeg", "webp"])
        if not isinstance(image_extensions, list):
            raise ValueError("data.image_extensions must be a list when using caption_source=sidecar_txt")

        rows = load_sidecar_caption_rows(
            dataset_root=dataset_root,
            image_dir=image_dir,
            caption_extension=caption_extension,
            image_extensions=[str(ext) for ext in image_extensions],
            caption_column=caption_column,
        )
        if not rows:
            raise ValueError(
                f"No sidecar caption rows found under {image_dir}. "
                "Make sure each image has a matching caption .txt file."
            )
        return rows

    metadata_path = (dataset_root / metadata_file).resolve()
    return load_metadata_rows(metadata_path)


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    _load_dotenv(root)

    data_cfg = read_yaml(args.data_config.resolve())
    model_cfg = read_yaml(args.model_config.resolve())
    run_cfg = read_yaml(args.run_config.resolve())

    run_cfg["run_name"] = args.run_name
    run_dir = (args.output_root / args.run_name).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    run_cfg["output_dir"] = str(run_dir)
    if args.resume_from:
        run_cfg["resume_from"] = str(args.resume_from.resolve())

    sampling_cfg = data_cfg.get("sampling", {}) if isinstance(data_cfg.get("sampling", {}), dict) else {}
    dataset_root = Path(data_cfg["dataset_root"]).resolve()

    trigger_token = str(args.trigger_token if args.trigger_token is not None else data_cfg.get("trigger_token", "")).strip()
    prepend_trigger_token = bool(data_cfg.get("prepend_trigger_token", False) or args.prepend_trigger_token)
    caption_column = str(data_cfg.get("caption_column", "text"))

    rows = _load_rows_for_training(data_cfg=data_cfg, dataset_root=dataset_root)
    rows = apply_caption_transform(
        rows=rows,
        caption_column=caption_column,
        trigger_token=trigger_token,
        prepend_trigger_token=prepend_trigger_token,
    )

    target_size = args.dataset_size if args.dataset_size is not None else sampling_cfg.get("dataset_size")
    if target_size is not None:
        target_size = int(target_size)
        if target_size <= 0:
            raise ValueError("dataset_size must be a positive integer.")

        stratify_column = args.stratify_column or str(sampling_cfg.get("stratify_column", "asset_family"))
        sampling_seed = int(args.sampling_seed if args.sampling_seed is not None else sampling_cfg.get("seed", run_cfg.get("seed", 42)))

        sampled_metadata_path = run_dir / f"metadata.sampled.{target_size}.jsonl"
        sampling_report_path = run_dir / f"metadata.sampled.{target_size}.report.json"

        sampled_rows, sampling_report = stratified_sample_rows(
            rows=rows,
            target_size=target_size,
            stratify_column=stratify_column,
            seed=sampling_seed,
        )
        write_metadata_rows(sampled_metadata_path, sampled_rows)
        with sampling_report_path.open("w", encoding="utf-8") as handle:
            json.dump(sampling_report, handle, indent=2)
            handle.write("\n")

        data_cfg["metadata_file"] = str(sampled_metadata_path)
        data_cfg["format"] = "hf_jsonl"
        print(f"[INFO] Applied stratified sampling: {target_size} rows by `{stratify_column}`")
        print(f"[INFO] Wrote sampled metadata: {sampled_metadata_path}")
        print(f"[INFO] Wrote sampling report: {sampling_report_path}")
        rows = sampled_rows
    else:
        prepared_metadata_path = run_dir / "metadata.prepared.jsonl"
        write_metadata_rows(prepared_metadata_path, rows)
        data_cfg["metadata_file"] = str(prepared_metadata_path)
        data_cfg["format"] = "hf_jsonl"
        print(f"[INFO] Wrote prepared metadata: {prepared_metadata_path}")

    if prepend_trigger_token and trigger_token:
        print(f"[INFO] Trigger token will be prepended to captions: {trigger_token}")

    # Pre-training sanity checks
    num_rows = len(rows)
    steps = int(run_cfg.get("num_train_steps", 1500))
    batch = int(run_cfg.get("train_batch_size", 1))
    grad = int(run_cfg.get("gradient_accumulation_steps", 4))
    eff_batch = batch * grad
    repeats = int(data_cfg.get("repeats", 1))
    images_seen = steps * eff_batch
    epochs = images_seen / max(num_rows * repeats, 1)

    print(f"[INFO] Dataset size: {num_rows} images (repeats={repeats})")
    print(f"[INFO] Effective batch size: {eff_batch}  |  Steps: {steps}  |  Images seen: ~{images_seen}")
    print(f"[INFO] Estimated epochs: {epochs:.2f}")

    if num_rows < 10 and not args.skip_size_check:
        print(f"[WARN] Dataset only has {num_rows} images. Training on <10 images causes severe overfitting.")
        print("[WARN] Add more data, or pass --skip-size-check to proceed anyway.")
        return 1
    elif num_rows < 30 and not args.skip_size_check:
        print(f"[WARN] Dataset has {num_rows} images. This is below the recommended 30+ per style.")
        print("[WARN] Pass --skip-size-check to proceed anyway.")
        return 1

    payload = build_ostris_training_payload(data_cfg=data_cfg, model_cfg=model_cfg, run_cfg=run_cfg)
    config_path = run_dir / "ostris_train.yaml"
    write_yaml(config_path, payload)

    cmd_template = _resolve_train_command_template()

    placeholders = {
        "config_path": config_path,
        "run_dir": run_dir,
        "resume_from": args.resume_from.resolve() if args.resume_from else "",
    }

    # Safely shell-quote values while letting users define their own command template.
    fmt = _stringify_mapping({k: shlex.quote(str(v)) for k, v in placeholders.items()})
    command = cmd_template.format(**fmt)

    command_path = run_dir / "train_command.sh"
    command_path.write_text(command + "\n", encoding="utf-8")

    print(f"[INFO] Wrote generated config: {config_path}")
    print(f"[INFO] Wrote command script: {command_path}")
    print(f"[INFO] Command: {command}")

    if args.dry_run:
        print("[INFO] Dry-run mode enabled; not launching training.")
        return 0

    try:
        completed = subprocess.run(command, shell=True, check=False)
    except FileNotFoundError:
        print(
            "[ERROR] Could not find ai-toolkit command. "
            "Set OSTRIS_TRAIN_COMMAND in .env."
        )
        return 1

    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())


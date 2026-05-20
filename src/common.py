from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import yaml


def read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}, got {type(data).__name__}")
    return data


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    return value


def build_ostris_training_payload(data_cfg: Dict[str, Any], model_cfg: Dict[str, Any], run_cfg: Dict[str, Any]) -> Dict[str, Any]:
    data_cfg = expand_env(data_cfg)
    model_cfg = expand_env(model_cfg)
    run_cfg = expand_env(run_cfg)

    dataset_root = Path(data_cfg["dataset_root"]).resolve()
    metadata_file = (dataset_root / data_cfg.get("metadata_file", "metadata.jsonl")).resolve()
    image_dir = (dataset_root / data_cfg.get("image_dir", "images")).resolve()

    # Compute effective batch size and epoch estimate for user visibility.
    num_train_steps = int(run_cfg.get("num_train_steps", 1500))
    train_batch_size = int(run_cfg.get("train_batch_size", 1))
    grad_accum = int(run_cfg.get("gradient_accumulation_steps", 4))
    repeats = int(data_cfg.get("repeats", 1))

    payload: Dict[str, Any] = {
        "toolkit": "ostris-ai-toolkit",
        "schema_version": "1",
        "task": "text_to_image_lora",
        "model": {
            "name": model_cfg["name"],
            "base_model_id": model_cfg["base_model_id"],
            "family": model_cfg.get("family", "flux"),
            "variant": model_cfg.get("variant", "flux2-klein"),
            "parameter_count": model_cfg.get("parameter_count", "4B"),
            "dtype": model_cfg.get("dtype", "bf16"),
        },
        "dataset": {
            "root": str(dataset_root),
            "format": data_cfg.get("format", "hf_jsonl"),
            "caption_source": data_cfg.get("caption_source", "metadata"),
            "metadata_file": str(metadata_file),
            "image_dir": str(image_dir),
            "caption_column": data_cfg.get("caption_column", "text"),
            "caption_txt_extension": data_cfg.get("caption_txt_extension", ".txt"),
            "image_extensions": data_cfg.get("image_extensions", ["png", "jpg", "jpeg", "webp"]),
            "id_column": data_cfg.get("id_column", "id"),
            "image_column": data_cfg.get("image_column", "file_name"),
            "trigger_token": data_cfg.get("trigger_token", ""),
            "prepend_trigger_token": bool(data_cfg.get("prepend_trigger_token", False)),
            "repeats": repeats,
            "resolution": int(data_cfg.get("resolution", 1024)),
            "shuffle_seed": int(data_cfg.get("shuffle_seed", 42)),
            "caption_max_chars": int(data_cfg.get("caption_max_chars", 900)),
        },
        "training": {
            "output_dir": run_cfg["output_dir"],
            "run_name": run_cfg["run_name"],
            "num_train_steps": num_train_steps,
            "save_every_steps": int(run_cfg.get("save_every_steps", 250)),
            "eval_every_steps": int(run_cfg.get("eval_every_steps", 250)),
            "learning_rate": float(run_cfg.get("learning_rate", 1e-4)),
            "train_batch_size": train_batch_size,
            "gradient_accumulation_steps": grad_accum,
            "max_grad_norm": float(run_cfg.get("max_grad_norm", 1.0)),
            "lr_scheduler": run_cfg.get("lr_scheduler", "cosine"),
            "warmup_steps": int(run_cfg.get("warmup_steps", 100)),
            "mixed_precision": run_cfg.get("mixed_precision", "bf16"),
            "gradient_checkpointing": bool(run_cfg.get("gradient_checkpointing", True)),
            "num_workers": int(run_cfg.get("num_workers", 2)),
            "seed": int(run_cfg.get("seed", 42)),
        },
        "optimizer": {
            "type": run_cfg.get("optimizer", "adamw"),
            "weight_decay": float(run_cfg.get("weight_decay", 0.01)),
            "beta1": float(run_cfg.get("beta1", 0.9)),
            "beta2": float(run_cfg.get("beta2", 0.999)),
        },
        "lora": {
            "type": "lora",
            "rank": int(run_cfg.get("lora_rank", 32)),
            "alpha": int(run_cfg.get("lora_alpha", 32)),
            "dropout": float(run_cfg.get("lora_dropout", 0.05)),
            "target_modules": run_cfg.get("lora_target_modules", ["to_q", "to_k", "to_v", "to_out"]),
        },
        "validation": {
            "prompts": run_cfg.get("validation_prompts", []),
            "num_images_per_prompt": int(run_cfg.get("validation_images_per_prompt", 2)),
            "guidance_scale": float(run_cfg.get("validation_guidance_scale", 3.5)),
            "num_inference_steps": int(run_cfg.get("validation_num_inference_steps", 28)),
        },
        "notes": "Generated by src/train_lora.py. Adjust fields to match your Ostris ai-toolkit CLI/API if names differ.",
    }

    return payload




from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from src.tokens import TokenConfig, parse_token_config, prepend_tokens_to_caption


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


def build_ostris_training_payload(
    data_cfg: Dict[str, Any],
    model_cfg: Dict[str, Any],
    run_cfg: Dict[str, Any],
    token_config: Optional[TokenConfig] = None,
    prepared_dataset_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Build an ai-toolkit-compatible training config (the format accepted by
    ``python run.py <config.yml>`` in a standard Ostris ai-toolkit install).

    Field names and structure follow the reference described in
    training-guide.md §4.1 — compatible with the real toolkit CLI.
    """
    data_cfg = expand_env(data_cfg)
    model_cfg = expand_env(model_cfg)
    run_cfg = expand_env(run_cfg)

    token_config = token_config or parse_token_config(data_cfg)

    # ── dataset folder ────────────────────────────────────────────
    if prepared_dataset_dir is not None:
        folder_path = str(prepared_dataset_dir.resolve())
    else:
        # Fallback — the toolkit won't find sidecar .txt files unless
        # the user has already prepared them manually.
        dataset_root = Path(data_cfg["dataset_root"]).resolve()
        image_dir = (dataset_root / data_cfg.get("image_dir", "images")).resolve()
        folder_path = str(image_dir)

    # ── resolution buckets (prefer run_cfg list over data_cfg scalar)
    raw_resolution = run_cfg.get("resolution_buckets") or data_cfg.get("resolution")
    if raw_resolution is None:
        resolution_buckets = [1024]
    elif isinstance(raw_resolution, list):
        resolution_buckets = [int(r) for r in raw_resolution]
    else:
        resolution_buckets = [int(raw_resolution)]

    # ── trigger_word ──────────────────────────────────────────────
    # If tokens are already baked into captions via our prepend step,
    # we leave trigger_word unset so the toolkit doesn't double-prepend.
    trigger_word = None
    if token_config.trigger is not None and token_config.trigger.value.strip():
        if not token_config.prepend_to_captions:
            # User wants the toolkit itself to inject the trigger word.
            trigger_word = token_config.trigger.value.strip()

    # ── validation prompts (tokenised only when WE are doing the prepend) ──
    # When trigger_word is set, the toolkit prepends it to every caption and
    # sample prompt — we must NOT also prepend here or the token appears twice.
    raw_prompts: list = run_cfg.get("validation_prompts", [])
    sample_prompts = []
    if not trigger_word and token_config.prepend_to_captions and token_config.token_values():
        tokens = token_config.token_values()
        for p in raw_prompts:
            sample_prompts.append({"prompt": prepend_tokens_to_caption(str(p), tokens)})
    else:
        for p in raw_prompts:
            sample_prompts.append({"prompt": str(p)})

    # ── optimizer ─────────────────────────────────────────────────
    optimizer = str(run_cfg.get("optimizer", "adamw_8bit"))

    # ── assemble the config block ─────────────────────────────────
    config_block: Dict[str, Any] = {
        "name": run_cfg.get("run_name", "flux2_klein_lora"),
        "process": [{"type": "diffusion_trainer"}],
        "training_folder": run_cfg.get("training_folder", run_cfg.get("output_dir", "./output")),
        "device": "cuda",
    }

    if trigger_word:
        config_block["trigger_word"] = trigger_word

    config_block["network"] = {
        "type": "lora",
        "linear": int(run_cfg.get("lora_rank", 32)),
        "linear_alpha": int(run_cfg.get("lora_alpha", 32)),
    }

    config_block["save"] = {
        "dtype": str(run_cfg.get("mixed_precision", model_cfg.get("dtype", "bf16"))),
        "save_every": int(run_cfg.get("save_every_steps", 250)),
        "max_step_saves_to_keep": int(run_cfg.get("max_step_saves_to_keep", 10)),
    }

    config_block["datasets"] = [{
        "folder_path": folder_path,
        "default_caption": str(data_cfg.get("default_caption", "")),
        "caption_ext": str(data_cfg.get("caption_txt_extension", ".txt")).lstrip("."),
        "caption_dropout_rate": float(run_cfg.get("caption_dropout_rate", 0.0)),
        "resolution": resolution_buckets,
    }]

    config_block["train"] = {
        "batch_size": int(run_cfg.get("train_batch_size", 1)),
        "gradient_accumulation": int(run_cfg.get("gradient_accumulation_steps", 4)),
        "steps": int(run_cfg.get("num_train_steps", 1500)),
        "train_unet": True,
        "train_text_encoder": bool(run_cfg.get("train_text_encoder", False)),
        "gradient_checkpointing": bool(run_cfg.get("gradient_checkpointing", True)),
        "noise_scheduler": str(run_cfg.get("noise_scheduler", "flowmatch")),
        "optimizer": optimizer,
        "timestep_type": str(run_cfg.get("timestep_type", "sigmoid")),
        "content_or_style": str(run_cfg.get("content_or_style", "balanced")),
        "lr": float(run_cfg.get("learning_rate", 1e-4)),
        "weight_decay": float(run_cfg.get("weight_decay", 0.01)),
        "dtype": str(run_cfg.get("mixed_precision", model_cfg.get("dtype", "bf16"))),
        "cache_text_embeddings": bool(run_cfg.get("cache_text_embeddings", False)),
    }

    # Optional ema_config
    ema_enabled = bool(run_cfg.get("ema_enabled", False))
    if ema_enabled:
        config_block["train"]["ema_config"] = {
            "use_ema": True,
            "ema_decay": float(run_cfg.get("ema_decay", 0.99)),
        }

    config_block["model"] = {
        "name_or_path": str(model_cfg.get("base_model_id", "")),
        "quantize": bool(model_cfg.get("quantize", False)),
        "qtype": str(model_cfg.get("qtype", "qfloat8")),
        "arch": str(model_cfg.get("arch", "flux2_klein_4b")),
        "low_vram": bool(model_cfg.get("low_vram", True)),
    }

    config_block["sample"] = {
        "sampler": "flowmatch",
        "sample_every": int(run_cfg.get("eval_every_steps", run_cfg.get("save_every_steps", 250))),
        "width": int(run_cfg.get("validation_width", 1024)),
        "height": int(run_cfg.get("validation_height", 1024)),
        "guidance_scale": float(run_cfg.get("validation_guidance_scale", 4.0)),
        "sample_steps": int(run_cfg.get("validation_num_inference_steps", 25)),
        "seed": int(run_cfg.get("seed", 42)),
        "walk_seed": True,
        "samples": sample_prompts,
    }

    return {
        "job": "extension",
        "config": config_block,
    }

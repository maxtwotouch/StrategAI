from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

from src.common import build_ostris_training_payload, read_yaml, write_yaml


def _coerce_override(value: str) -> Any:
    """Convert common string overrides to proper Python types."""
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "none" or lowered == "null":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def parse_overrides(items: list[str]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Override must be key=value, got: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Override key must not be empty: {item}")
        overrides[key] = _coerce_override(value.strip())
    return overrides


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an Ostris ai-toolkit training config from model/data config.")
    parser.add_argument("--data-config", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--run-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        help="Override values in run config with key=value (example: num_train_steps=2500, gradient_checkpointing=false)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    data_cfg = read_yaml(args.data_config.resolve())
    model_cfg = read_yaml(args.model_config.resolve())
    run_cfg = read_yaml(args.run_config.resolve())

    overrides = parse_overrides(args.override)
    run_cfg.update(overrides)

    payload = build_ostris_training_payload(data_cfg=data_cfg, model_cfg=model_cfg, run_cfg=run_cfg)
    write_yaml(args.output.resolve(), payload)

    print(f"[INFO] Generated Ostris ai-toolkit config: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

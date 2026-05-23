from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Optional

from src.common import read_yaml
from src.tokens import TokenConfig, format_prompt_with_tokens, parse_token_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate evaluation samples with a trained Flux2 Klein LoRA adapter.")
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--data-config", type=Path, default=Path("config/data.yaml"),
                        help="Path to data.yaml to read custom tokens for prompt formatting.")
    parser.add_argument("--adapter-path", type=Path, required=True, help="Path to trained LoRA adapter/checkpoint.")
    parser.add_argument("--prompt", required=True, help="Prompt for evaluation image generation.")
    parser.add_argument("--token", action="append", default=None,
                        help="Extra custom token to prepend (repeatable). Example: --token '<my_token>' --token '<pose-topdown>'")
    parser.add_argument("--output-dir", type=Path, default=Path("eval_samples"))
    parser.add_argument("--num-images", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _stringify_mapping(mapping: Dict[str, object]) -> Dict[str, str]:
    return {key: str(value) for key, value in mapping.items()}


def main() -> int:
    args = parse_args()

    model_cfg = read_yaml(args.model_config.resolve())
    base_model_id = model_cfg["base_model_id"]

    # Format prompt with custom tokens
    prompt = args.prompt
    token_config: Optional[TokenConfig] = None
    data_config_path = args.data_config.resolve()
    if data_config_path.exists():
        data_cfg = read_yaml(data_config_path)
        token_config = parse_token_config(data_cfg)

    if token_config is not None and token_config.token_values():
        prompt = format_prompt_with_tokens(prompt, token_config)
        print(f"[INFO] Tokens applied: {', '.join(token_config.token_values())}")
        print(f"[INFO] Formatted prompt: {prompt}")

    # Apply any extra --token arguments on top
    if args.token:
        for tok in args.token:
            if tok.strip() and tok.strip() not in prompt:
                prompt = f"{tok.strip()} {prompt}"
        print(f"[INFO] Extra tokens applied. Final prompt: {prompt}")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd_template = os.environ.get("OSTRIS_INFER_COMMAND", "").strip()
    if not cmd_template:
        cmd_template = (
            "ai-toolkit infer text2img --base-model {base_model} --lora {adapter_path} "
            "--prompt {prompt} --num-images {num_images} --seed {seed} --output {output_dir}"
        )

    placeholders = {
        "base_model": base_model_id,
        "adapter_path": args.adapter_path.resolve(),
        "prompt": prompt,
        "num_images": args.num_images,
        "seed": args.seed,
        "output_dir": output_dir,
    }

    fmt = _stringify_mapping({k: shlex.quote(str(v)) for k, v in placeholders.items()})
    command = cmd_template.format(**fmt)

    print(f"[INFO] Command: {command}")
    if args.dry_run:
        print("[INFO] Dry-run mode enabled; not launching inference.")
        return 0

    try:
        completed = subprocess.run(command, shell=True, check=False)
    except FileNotFoundError:
        print(
            "[ERROR] Could not find ai-toolkit command. "
            "Set OSTRIS_INFER_COMMAND in .env."
        )
        return 1

    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

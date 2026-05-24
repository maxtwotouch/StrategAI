from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml


def _read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}, got {type(data).__name__}")
    return data


def _write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync validation prompts in training config from dataset captions."
    )
    parser.add_argument("--dataset-root", type=Path, default=Path("dataset"))
    parser.add_argument("--mode", choices=["hf_jsonl", "sidecar_txt"], default="hf_jsonl")
    parser.add_argument("--metadata-file", default="metadata.jsonl")
    parser.add_argument("--image-dir", default="images")
    parser.add_argument("--caption-txt-extension", default=".txt")
    parser.add_argument("--image-extensions", default="png,jpg,jpeg")
    parser.add_argument("--training-config", type=Path, default=Path("config/lora_4b.yaml"))
    parser.add_argument("--max-prompts", type=int, default=6)
    parser.add_argument("--max-chars", type=int, default=420)
    parser.add_argument("--caption-column", default="text")
    return parser.parse_args()


def clip_prompt(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    sentence_cut = max(window.rfind(". "), window.rfind("."))
    if sentence_cut >= int(max_chars * 0.55):
        return window[: sentence_cut + 1].strip()
    clipped = text[: max_chars - 1].rstrip(" ,.;")
    return clipped + "."


def collect_prompts(
    metadata_path: Path,
    caption_column: str,
    max_prompts: int,
    max_chars: int,
) -> List[str]:
    """Collect clean captions from metadata — toolkit injects trigger_word at training time."""
    prompts: List[str] = []
    seen = set()

    with metadata_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(prompts) >= max_prompts:
                break
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or caption_column not in row:
                continue
            raw = normalize_text(str(row[caption_column]))
            if not raw:
                continue
            clipped = clip_prompt(raw, max_chars)
            if clipped in seen:
                continue
            seen.add(clipped)
            prompts.append(clipped)

    return prompts


def collect_prompts_from_sidecar_txt(
    image_dir: Path,
    caption_extension: str,
    image_extensions: str,
    max_prompts: int,
    max_chars: int,
) -> List[str]:
    """Collect clean captions from sidecar .txt files — toolkit injects trigger_word at training time."""
    prompts: List[str] = []
    seen = set()
    cap_ext = caption_extension if caption_extension.startswith(".") else f".{caption_extension}"
    img_exts = {chunk.strip().lower().lstrip(".") for chunk in image_extensions.split(",") if chunk.strip()}

    for image_path in sorted(image_dir.rglob("*")):
        if len(prompts) >= max_prompts:
            break
        if not image_path.is_file() or image_path.suffix.lower().lstrip(".") not in img_exts:
            continue

        caption_path = image_path.with_suffix(cap_ext)
        if not caption_path.exists():
            continue

        raw = normalize_text(caption_path.read_text(encoding="utf-8"))
        if not raw:
            continue
        clipped = clip_prompt(raw, max_chars)
        if clipped in seen:
            continue
        seen.add(clipped)
        prompts.append(clipped)

    return prompts


def main() -> int:
    args = parse_args()

    if args.max_prompts <= 0:
        print("[ERROR] --max-prompts must be a positive integer.")
        return 1
    if args.max_chars <= 0:
        print("[ERROR] --max-chars must be a positive integer.")
        return 1

    dataset_root = args.dataset_root.resolve()
    metadata_path = dataset_root / args.metadata_file

    training_cfg_path = args.training_config.resolve()
    training_cfg = _read_yaml(training_cfg_path)

    if args.mode == "sidecar_txt":
        image_dir = (dataset_root / args.image_dir).resolve()
        if not image_dir.exists():
            print(f"[ERROR] Image directory not found: {image_dir}")
            return 1
        prompts = collect_prompts_from_sidecar_txt(
            image_dir=image_dir,
            caption_extension=args.caption_txt_extension,
            image_extensions=args.image_extensions,
            max_prompts=args.max_prompts,
            max_chars=args.max_chars,
        )
    else:
        if not metadata_path.exists():
            print(f"[ERROR] Metadata file not found: {metadata_path}")
            return 1
        prompts = collect_prompts(
            metadata_path=metadata_path,
            caption_column=args.caption_column,
            max_prompts=args.max_prompts,
            max_chars=args.max_chars,
        )
    if not prompts:
        print("[ERROR] No prompts collected from metadata.")
        return 1

    config_block = training_cfg.setdefault("config", training_cfg)
    sample_block = config_block.setdefault("sample", {})
    sample_block["samples"] = [{"prompt": p} for p in prompts]
    _write_yaml(training_cfg_path, training_cfg)

    print(f"[INFO] Updated sample.samples in: {training_cfg_path}")
    print(f"[INFO] Prompt count: {len(prompts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# generate_from_prompt_pack_comfyui.py
#
# Runtime generation script:
# - Uses FLUX single prompt field (positive only)
# - Overhead prompt pack compatible
# - Randomizes guidance per-sample within CLI range for a conditioning node
# - Keeps background/nature/structure metadata
# - Includes LoRA strength routing (background-like assets at 0.7 if desired)

import argparse
import json
import random
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests


# ----------------------------
# ComfyUI API helpers
# ----------------------------
def api_post_prompt(comfy_url: str, prompt_graph: Dict[str, Any], client_id: str) -> str:
    r = requests.post(
        f"{comfy_url}/prompt",
        json={"prompt": prompt_graph, "client_id": client_id},
        timeout=60
    )
    r.raise_for_status()
    payload = r.json()
    if "prompt_id" not in payload:
        raise RuntimeError(f"Missing prompt_id from ComfyUI response: {payload}")
    return payload["prompt_id"]

def api_get_history(comfy_url: str, prompt_id: str) -> Dict[str, Any]:
    r = requests.get(f"{comfy_url}/history/{prompt_id}", timeout=30)
    r.raise_for_status()
    return r.json()

def api_download_image(comfy_url: str, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
    r = requests.get(
        f"{comfy_url}/view",
        params={"filename": filename, "subfolder": subfolder, "type": folder_type},
        timeout=120
    )
    r.raise_for_status()
    return r.content

def wait_for_completion(comfy_url: str, prompt_id: str, timeout_sec: int = 900, poll_sec: float = 1.0) -> Dict[str, Any]:
    start = time.time()
    while time.time() - start < timeout_sec:
        hist = api_get_history(comfy_url, prompt_id)
        if prompt_id in hist:
            return hist[prompt_id]
        time.sleep(poll_sec)
    raise TimeoutError(f"Timed out waiting for prompt_id={prompt_id}")

def extract_output_images(history_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    images = []
    outputs = history_item.get("outputs", {})
    for _, node_out in outputs.items():
        for im in node_out.get("images", []):
            images.append(im)
    return images


# ----------------------------
# File helpers
# ----------------------------
def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def save_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def ensure_dirs(base_dir: Path):
    dirs = {
        "images": base_dir / "generated" / "images",
        "metadata": base_dir / "generated" / "metadata",
        "manifest": base_dir / "generated" / "dataset_manifest.jsonl",
        "errors": base_dir / "generated" / "errors.jsonl",
        "run_report": base_dir / "generated" / "run_report.json",
    }
    dirs["images"].mkdir(parents=True, exist_ok=True)
    dirs["metadata"].mkdir(parents=True, exist_ok=True)
    dirs["manifest"].parent.mkdir(parents=True, exist_ok=True)
    return dirs


# ----------------------------
# Workflow mutation helpers
# ----------------------------
def set_node_input(workflow: Dict[str, Any], node_id: str, key: str, value: Any, applied: Dict[str, Any]) -> None:
    if node_id not in workflow:
        raise KeyError(f"Node id '{node_id}' not found in workflow.")
    if "inputs" not in workflow[node_id]:
        workflow[node_id]["inputs"] = {}
    old_val = workflow[node_id]["inputs"].get(key, "__MISSING__")
    workflow[node_id]["inputs"][key] = value
    applied[f"{node_id}.{key}"] = {"old": old_val, "new": value}

def set_if_not_none(workflow: Dict[str, Any], node_id: Optional[str], key: str, value: Any, applied: Dict[str, Any]) -> None:
    if value is None:
        return
    if not node_id:
        raise ValueError(f"Cannot set {key}: missing node id")
    set_node_input(workflow, node_id, key, value, applied)

def resolve_lora_strength(row: Dict[str, Any], default_strength: float, nature_strength: float) -> float:
    """
    If nature object (trees/grass/boulders), optionally reduce multi-angle LoRA strength.
    """
    fam = (row.get("asset_family") or "").lower()
    if fam == "nature_object":
        return nature_strength
    return default_strength

def build_caption(row: Dict[str, Any]) -> str:
    return (
        f"{row.get('positive_prompt', '')} "
        f"{row.get('pose_token', '<pose_overhead>')} "
        f"{row.get('style_token', '<pixel_art_medieval_arch>')}"
    ).strip()


def parse_args():
    ap = argparse.ArgumentParser(description="Generate images from prompt pack via ComfyUI API")

    # Core
    ap.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    ap.add_argument("--base-dir", default="./dataset")
    ap.add_argument("--prompt-pack", default="./dataset/prompts/medieval_prompt_pack.jsonl")
    ap.add_argument("--workflow-api-json", required=True)

    # Prompt node (FLUX single prompt)
    ap.add_argument("--prompt-node", required=True, help="Node id that receives the single prompt text")
    ap.add_argument("--prompt-input-key", default="text", help="Input key for prompt field")

    # Optional second text node (some workflows still expose one)
    ap.add_argument("--secondary-text-node", default=None)
    ap.add_argument("--secondary-text-key", default="text")
    ap.add_argument("--secondary-text-value", default=None)

    # Iteration
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="0=all")
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--timeout-sec", type=int, default=900)

    # KSampler / latent optional overrides
    ap.add_argument("--ksampler-node", default=None)
    ap.add_argument("--latent-node", default=None)
    ap.add_argument("--override-steps", type=int, default=None)
    ap.add_argument("--override-cfg", type=float, default=None)
    ap.add_argument("--override-sampler-name", default=None)
    ap.add_argument("--override-scheduler", default=None)
    ap.add_argument("--override-width", type=int, default=None)
    ap.add_argument("--override-height", type=int, default=None)

    # Seed handling
    ap.add_argument("--override-seed-mode", choices=["none", "random", "fixed"], default="none")
    ap.add_argument("--override-fixed-seed", type=int, default=None)

    # Guidance randomization (NEW requirement)
    ap.add_argument("--guidance-node", default=None, help="Node id with guidance/conditioning field")
    ap.add_argument("--guidance-key", default="guidance", help="Input key name for guidance")
    ap.add_argument("--guidance-randomize", action="store_true", help="Enable per-sample random guidance")
    ap.add_argument("--guidance-min", type=float, default=2.5, help="Min guidance when randomizing")
    ap.add_argument("--guidance-max", type=float, default=4.0, help="Max guidance when randomizing")
    ap.add_argument("--guidance-decimals", type=int, default=3, help="Decimal precision for randomized guidance")

    # Multi-angle LoRA routing
    ap.add_argument("--multiangle-lora-node", default=None)
    ap.add_argument("--multiangle-strength-model-key", default="strength_model")
    ap.add_argument("--multiangle-strength-clip-key", default="strength_clip")
    ap.add_argument("--set-clip-strength", action="store_true")
    ap.add_argument("--lora-strength-default", type=float, default=1.0)
    ap.add_argument("--lora-strength-nature", type=float, default=0.7)

    return ap.parse_args()


def main():
    args = parse_args()
    random.seed(args.seed)

    if args.guidance_randomize and args.guidance_min > args.guidance_max:
        raise ValueError("--guidance-min cannot be greater than --guidance-max")

    base_dir = Path(args.base_dir)
    workflow_path = Path(args.workflow_api_json)
    prompt_pack_path = Path(args.prompt_pack)

    dirs = ensure_dirs(base_dir)
    workflow_template = load_json(workflow_path)
    rows = load_jsonl(prompt_pack_path)

    if args.shuffle:
        random.shuffle(rows)
    rows = rows[args.start:] if args.limit == 0 else rows[args.start:args.start + args.limit]

    client_id = str(uuid.uuid4())

    stats = {
        "total_requested": len(rows),
        "success": 0,
        "failed": 0,
        "pose_mode": "overhead",
        "guidance_randomize": args.guidance_randomize,
        "guidance_min": args.guidance_min,
        "guidance_max": args.guidance_max,
        "lora_strength_default": args.lora_strength_default,
        "lora_strength_nature": args.lora_strength_nature,
    }

    start = time.perf_counter()

    for i, row in enumerate(rows):
        idx = args.start + i
        image_id = f"{idx:07d}_{uuid.uuid4().hex[:8]}"
        image_name = f"{image_id}.png"
        applied = {}

        try:
            workflow = json.loads(json.dumps(workflow_template))  # deep copy

            # FLUX single prompt text
            set_node_input(workflow, args.prompt_node, args.prompt_input_key, row["positive_prompt"], applied)

            # Optional secondary text
            if args.secondary_text_node and args.secondary_text_value is not None:
                set_node_input(workflow, args.secondary_text_node, args.secondary_text_key, args.secondary_text_value, applied)

            # Seed override
            resolved_seed = None
            if args.override_seed_mode == "random":
                if not args.ksampler_node:
                    raise ValueError("--override-seed-mode random requires --ksampler-node")
                resolved_seed = random.randint(1, 2**31 - 1)
                set_node_input(workflow, args.ksampler_node, "seed", resolved_seed, applied)
            elif args.override_seed_mode == "fixed":
                if not args.ksampler_node:
                    raise ValueError("--override-seed-mode fixed requires --ksampler-node")
                if args.override_fixed_seed is None:
                    raise ValueError("--override-fixed-seed is required when seed mode is fixed")
                resolved_seed = args.override_fixed_seed
                set_node_input(workflow, args.ksampler_node, "seed", resolved_seed, applied)

            # Optional sampler overrides
            set_if_not_none(workflow, args.ksampler_node, "steps", args.override_steps, applied)
            set_if_not_none(workflow, args.ksampler_node, "cfg", args.override_cfg, applied)
            set_if_not_none(workflow, args.ksampler_node, "sampler_name", args.override_sampler_name, applied)
            set_if_not_none(workflow, args.ksampler_node, "scheduler", args.override_scheduler, applied)

            # Optional latent overrides
            set_if_not_none(workflow, args.latent_node, "width", args.override_width, applied)
            set_if_not_none(workflow, args.latent_node, "height", args.override_height, applied)

            # Guidance randomization
            resolved_guidance = None
            if args.guidance_randomize:
                if not args.guidance_node:
                    raise ValueError("--guidance-randomize requires --guidance-node")
                g = random.uniform(args.guidance_min, args.guidance_max)
                resolved_guidance = round(g, args.guidance_decimals)
                set_node_input(workflow, args.guidance_node, args.guidance_key, resolved_guidance, applied)

            # LoRA strength routing
            resolved_lora_strength = None
            if args.multiangle_lora_node:
                resolved_lora_strength = resolve_lora_strength(
                    row=row,
                    default_strength=args.lora_strength_default,
                    nature_strength=args.lora_strength_nature
                )
                set_node_input(
                    workflow,
                    args.multiangle_lora_node,
                    args.multiangle_strength_model_key,
                    resolved_lora_strength,
                    applied
                )
                if args.set_clip_strength:
                    set_node_input(
                        workflow,
                        args.multiangle_lora_node,
                        args.multiangle_strength_clip_key,
                        resolved_lora_strength,
                        applied
                    )

            # Submit + wait
            prompt_id = api_post_prompt(args.comfy_url, workflow, client_id)
            hist_item = wait_for_completion(args.comfy-url if False else args.comfy_url, prompt_id, timeout_sec=args.timeout_sec)
            images = extract_output_images(hist_item)
            if not images:
                raise RuntimeError("No output images returned by ComfyUI history")

            # Save first image
            im = images[0]
            blob = api_download_image(
                args.comfy_url,
                filename=im["filename"],
                subfolder=im.get("subfolder", ""),
                folder_type=im.get("type", "output")
            )
            out_img_path = dirs["images"] / image_name
            with open(out_img_path, "wb") as f:
                f.write(blob)

            # Record
            record = {
                "id": image_id,
                "domain": row.get("domain", "medieval_pixel_assets"),
                "asset_family": row.get("asset_family"),
                "image_path": str(out_img_path.relative_to(base_dir)),
                "caption": build_caption(row),
                "pose_token": row.get("pose_token", "<pose_overhead>"),
                "style_token": row.get("style_token", "<pixel_art_medieval_arch>"),
                "object_class": row.get("object_class"),
                "detail_level": row.get("detail_level"),
                "complexity": row.get("complexity"),
                "material_profile": row.get("material_profile"),
                "condition": row.get("condition"),
                "theme_mood": row.get("theme_mood"),
                "palette": row.get("palette"),
                "positive_prompt": row.get("positive_prompt"),
                "negative_prompt": "",
                "generation": {
                    "comfy_prompt_id": prompt_id,
                    "client_id": client_id,
                    "workflow_api_json": str(workflow_path),
                    "resolved_seed": resolved_seed,
                    "guidance": {
                        "randomized": args.guidance_randomize,
                        "node_id": args.guidance_node,
                        "key": args.guidance_key,
                        "min": args.guidance_min,
                        "max": args.guidance_max,
                        "resolved": resolved_guidance
                    },
                    "multiangle_lora": {
                        "node_id": args.multiangle_lora_node,
                        "model_key": args.multiangle_strength_model_key,
                        "clip_key": args.multiangle_strength_clip_key if args.set_clip_strength else None,
                        "default_strength": args.lora_strength_default,
                        "nature_strength": args.lora_strength_nature,
                        "resolved_strength": resolved_lora_strength
                    },
                    "overrides_applied": applied
                }
            }

            sidecar = dirs["metadata"] / f"{image_id}.json"
            save_json(sidecar, record)
            append_jsonl(dirs["manifest"], record)

            stats["success"] += 1
            done = stats["success"] + stats["failed"]
            if done % 50 == 0:
                print(f"[{done}/{stats['total_requested']}] success={stats['success']} failed={stats['failed']}")

        except Exception as e:
            stats["failed"] += 1
            append_jsonl(dirs["errors"], {
                "index": idx,
                "row_id": row.get("id"),
                "error": str(e),
                "prompt_row": row
            })
            print(f"[ERROR] idx={idx} row_id={row.get('id')} err={e}")

    save_json(dirs["run_report"], stats)

    stop = time.perf_counter()

    print(json.dumps(stats, indent=2))

    print("Done in {:.2f} minutes".format((stop - start) / 60))


if __name__ == "__main__":
    main()
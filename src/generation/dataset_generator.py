#!/usr/bin/env python3
# dataset_generator.py

import argparse
import json
import random
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Tuple
import requests

from src.generation.image_metadata import embed_metadata_into_file


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
    for node_out in outputs.values():
        for im in node_out.get("images", []):
            images.append(im)
    return images


# ----------------------------
# IO helpers
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


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def validate_prompt_row(row: Dict[str, Any], idx: int) -> None:
    required_fields = ("asset_type", "positive_prompt", "caption")
    missing = [field for field in required_fields if not normalize_text(row.get(field))]
    if missing:
        raise ValueError(f"Prompt row index={idx} is missing required fields: {', '.join(missing)}")


def resolve_asset_id(row: Dict[str, Any], idx: int, id_counts: Dict[str, int]) -> Tuple[str, bool]:
    base_id = normalize_text(row.get("id")) or f"asset_{idx:07d}"
    seen_count = id_counts.get(base_id, 0)
    id_counts[base_id] = seen_count + 1
    if seen_count == 0:
        return base_id, False
    return f"{base_id}_{seen_count + 1}", True


# ----------------------------
# Workflow mutation helpers
# ----------------------------
def set_node_input(workflow: Dict[str, Any], node_id: str, key: str, value: Any) -> None:
    if node_id not in workflow:
        raise KeyError(f"Node id '{node_id}' not found in workflow.")
    workflow[node_id].setdefault("inputs", {})[key] = value


def is_background(row: Dict[str, Any]) -> bool:
    """Route to tile workflow when asset_type == 'background'."""
    return (row.get("asset_type") or "").lower() == "background"


def is_object_or_terrain(row: Dict[str, Any]) -> bool:
    """Object and terrain assets share the nature guidance range."""
    at = (row.get("asset_type") or "").lower()
    return at in ("object", "terrain")


def resolve_guidance_for_row(
    row: Dict[str, Any],
    global_min: float,
    global_max: float,
    tile_min: float,
    tile_max: float,
    nature_min: float,
    nature_max: float,
    use_category_policy: bool,
    decimals: int,
) -> float:
    """
    Guidance routing priority:
      1) background -> tile range
      2) object / terrain -> nature range
      3) fallback (structure) -> global range
    """
    if use_category_policy and is_background(row):
        return round(random.uniform(tile_min, tile_max), decimals)
    if use_category_policy and is_object_or_terrain(row):
        return round(random.uniform(nature_min, nature_max), decimals)
    return round(random.uniform(global_min, global_max), decimals)


# ----------------------------
# Main
# ----------------------------
def ensure_dirs(base_dir: Path, output_layout: str):
    """Create output directories. All metadata goes into PNG tEXt chunks — no manifest or sidecars."""
    if output_layout == "huggingface":
        dirs = {
            "images": base_dir,
            "errors": base_dir / "errors.jsonl",
            "run_report": base_dir / "run_report.json",
        }
    else:
        dirs = {
            "images": base_dir / "raw",
            "errors": base_dir / "raw" / "errors.jsonl",
            "run_report": base_dir / "raw" / "run_report.json",
        }
    dirs["images"].mkdir(parents=True, exist_ok=True)
    dirs["errors"].parent.mkdir(parents=True, exist_ok=True)
    return dirs


def parse_args():
    ap = argparse.ArgumentParser(description="Generate FLUX dataset via ComfyUI with category-specific guidance ranges")

    ap.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    ap.add_argument("--base-dir", default="./dataset")
    ap.add_argument("--prompt-data", dest="prompt_data", default="./dataset/prompts/generated_prompts.jsonl")

    # Workflow
    ap.add_argument("--workflow-api-json", required=True, help="ComfyUI workflow API JSON")

    # Prompt nodes
    ap.add_argument("--prompt-node", required=True)
    ap.add_argument("--prompt-input-key", default="text")

    # Guidance nodes
    ap.add_argument("--guidance-randomize", action="store_true")
    ap.add_argument("--guidance-node", default=None, help="Guidance node id")
    ap.add_argument("--guidance-key", default="guidance")

    # Guidance ranges
    ap.add_argument("--guidance-min", type=float, default=3.0)
    ap.add_argument("--guidance-max", type=float, default=6.0)

    # Object+terrain range (higher guidance, formerly nature_object)

    ap.add_argument("--guidance-decimals", type=int, default=3)

    # Seed handling
    ap.add_argument("--ksampler-node", default=None)
    ap.add_argument("--override-seed-mode", choices=["none", "random", "fixed"], default="none")
    ap.add_argument("--override-fixed-seed", type=int, default=None)

    # Iteration
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--timeout-sec", type=int, default=900)
    ap.add_argument(
        "--output-layout",
        choices=["generated", "huggingface"],
        default="generated",
        help="generated → <base>/raw/...; huggingface → <base>/images + metadata",
    )

    return ap.parse_args()


def main():
    args = parse_args()
    random.seed(args.seed)

    if args.guidance_randomize:
        if args.guidance_min > args.guidance_max:
            raise ValueError("Invalid global guidance range")

    base_dir = Path(args.base_dir)
    primary_workflow = load_json(Path(args.workflow_api_json))
    rows = load_jsonl(Path(args.prompt_data))
    dirs = ensure_dirs(base_dir, args.output_layout)

    if args.shuffle:
        random.shuffle(rows)
    rows = rows[args.start:] if args.limit == 0 else rows[args.start:args.start + args.limit]

    client_id = str(uuid.uuid4())
    id_counts: Dict[str, int] = {}

    stats = {
        "total_requested": len(rows),
        "success": 0,
        "failed": 0,
        "used_primary_workflow": 0,
        "duplicate_id_collisions": 0,
        "metadata_embedded": 0,
        "guidance_policy": {
            "global": [args.guidance_min, args.guidance_max],
            "enabled": args.guidance_randomize
        }
    }

    start = time.perf_counter()

    for i, row in enumerate(rows):
        idx = args.start + i

        try:
            validate_prompt_row(row, idx)
            image_id, had_collision = resolve_asset_id(row, idx, id_counts)
            if had_collision:
                stats["duplicate_id_collisions"] += 1
            image_name = f"{image_id}.png"

            workflow = json.loads(json.dumps(primary_workflow))
            prompt_node = args.prompt_node
            prompt_key = args.prompt_input_key
            guidance_node = args.guidance_node
            guidance_key = args.guidance_key
            ksampler_node = args.ksampler_node
            stats["used_primary_workflow"] += 1

            # Inject prompt
            set_node_input(workflow, prompt_node, prompt_key, row["positive_prompt"])

            # Optional seed override
            if args.override_seed_mode == "random":
                if not ksampler_node:
                    raise ValueError("Seed override requested but ksampler node missing for selected workflow")
                set_node_input(workflow, ksampler_node, "seed", random.randint(1, 2**31 - 1))
            elif args.override_seed_mode == "fixed":
                if not ksampler_node:
                    raise ValueError("Fixed seed requested but ksampler node missing for selected workflow")
                if args.override_fixed_seed is None:
                    raise ValueError("--override-fixed-seed required for fixed seed mode")
                set_node_input(workflow, ksampler_node, "seed", args.override_fixed_seed)

            # Guidance randomization with category-specific nature range
            if args.guidance_randomize:
                if not guidance_node:
                    raise ValueError("Guidance randomization enabled but guidance node missing for selected workflow")
                resolved_guidance = round(random.uniform(args.guidance_min, args.guidance_max), args.guidance_decimals)
                set_node_input(workflow, guidance_node, guidance_key, resolved_guidance)

            # Run workflow
            prompt_id = api_post_prompt(args.comfy_url, workflow, client_id)
            hist_item = wait_for_completion(args.comfy_url, prompt_id, timeout_sec=args.timeout_sec)
            images = extract_output_images(hist_item)
            if not images:
                raise RuntimeError("No output images returned by selected workflow")

            im = images[0]
            blob = api_download_image(
                args.comfy_url,
                filename=im["filename"],
                subfolder=im.get("subfolder", ""),
                folder_type=im.get("type", "output")
            )

            out_path = dirs["images"] / image_name
            with open(out_path, "wb") as f:
                f.write(blob)

            # Embed only the minimal metadata into the PNG
            metadata_payload = {
                "asset_type": row["asset_type"],
                "caption": row["caption"],
                "palette": row["palette"],
            }
            embed_metadata_into_file(out_path, metadata_payload)
            stats["metadata_embedded"] += 1
            stats["success"] += 1

        except Exception as e:
            stats["failed"] += 1
            append_jsonl(dirs["errors"], {
                "index": idx,
                "row_id": row.get("id"),
                "asset_type": row.get("asset_type"),
                "error": str(e),
            })
            print(f"[ERROR] idx={idx} row_id={row.get('id')} err={e}")

    save_json(dirs["run_report"], stats)
    stop = time.perf_counter()

    print(json.dumps(stats, indent=2))
    print("Done in {:.2f} minutes".format((stop - start) / 60))


if __name__ == "__main__":
    main()

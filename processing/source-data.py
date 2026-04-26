#!/usr/bin/env python3
# generate_from_prompt_pack_comfyui.py

import argparse
import json
import random
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List
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

def build_caption(row: Dict[str, Any]) -> str:
    return (
        f"{row.get('positive_prompt', '')} "
        f"{row.get('pose_token', '<pose_overhead>')} "
        f"{row.get('style_token', '<pixel_art_medieval_arch>')}"
    ).strip()

def is_tile(row: Dict[str, Any]) -> bool:
    return (row.get("asset_family") or "").lower() == "background_tile"

def is_nature(row: Dict[str, Any]) -> bool:
    return (row.get("asset_family") or "").lower() == "nature_object"

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
) -> (float, str, List[float]):
    """
    Guidance routing priority:
      1) background_tile -> tile range
      2) nature_object   -> nature range
      3) fallback        -> global range
    """
    if use_category_policy and is_tile(row):
        return round(random.uniform(tile_min, tile_max), decimals), "background_tile", [tile_min, tile_max]
    if use_category_policy and is_nature(row):
        return round(random.uniform(nature_min, nature_max), decimals), "nature_object", [nature_min, nature_max]
    return round(random.uniform(global_min, global_max), decimals), "global", [global_min, global_max]

# ----------------------------
# Main
# ----------------------------
def parse_args():
    ap = argparse.ArgumentParser(description="Generate FLUX dataset via ComfyUI with category-specific guidance ranges")

    ap.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    ap.add_argument("--base-dir", default="./dataset")
    ap.add_argument("--prompt-pack", default="./dataset/prompts/medieval_prompt_pack.jsonl")

    # Separate workflows
    ap.add_argument("--workflow-api-json", required=True, help="Primary workflow for non-tile assets")
    ap.add_argument("--tile-workflow-api-json", required=True, help="Separate workflow for background_tile assets")

    # Prompt nodes
    ap.add_argument("--prompt-node", required=True)
    ap.add_argument("--tile-prompt-node", required=True)
    ap.add_argument("--prompt-input-key", default="text")
    ap.add_argument("--tile-prompt-input-key", default="text")

    # Guidance nodes
    ap.add_argument("--guidance-randomize", action="store_true")
    ap.add_argument("--guidance-node", default=None, help="Guidance node id for primary workflow")
    ap.add_argument("--tile-guidance-node", default=None, help="Guidance node id for tile workflow")
    ap.add_argument("--guidance-key", default="guidance")
    ap.add_argument("--tile-guidance-key", default="guidance")

    # Guidance ranges
    ap.add_argument("--guidance-min", type=float, default=3.0)
    ap.add_argument("--guidance-max", type=float, default=6.0)
    ap.add_argument("--tile-guidance-min", type=float, default=1.0)
    ap.add_argument("--tile-guidance-max", type=float, default=4.0)

    # NEW: nature-object range (higher guidance)
    ap.add_argument("--nature-guidance-min", type=float, default=5.0, help="Min guidance for nature_object rows")
    ap.add_argument("--nature-guidance-max", type=float, default=8.0, help="Max guidance for nature_object rows")

    ap.add_argument("--guidance-decimals", type=int, default=3)
    ap.add_argument("--use-category-guidance-policy", action="store_true")

    # Seed handling
    ap.add_argument("--ksampler-node", default=None)
    ap.add_argument("--tile-ksampler-node", default=None)
    ap.add_argument("--override-seed-mode", choices=["none", "random", "fixed"], default="none")
    ap.add_argument("--override-fixed-seed", type=int, default=None)

    # Iteration
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--timeout-sec", type=int, default=900)

    return ap.parse_args()

def main():
    args = parse_args()
    random.seed(args.seed)

    if args.guidance_randomize:
        if args.guidance_min > args.guidance_max:
            raise ValueError("Invalid global guidance range")
        if args.tile_guidance_min > args.tile_guidance_max:
            raise ValueError("Invalid tile guidance range")
        if args.nature_guidance_min > args.nature_guidance_max:
            raise ValueError("Invalid nature guidance range")

    base_dir = Path(args.base_dir)
    primary_workflow = load_json(Path(args.workflow_api_json))
    tile_workflow = load_json(Path(args.tile_workflow_api_json))
    rows = load_jsonl(Path(args.prompt_pack))
    dirs = ensure_dirs(base_dir)

    if args.shuffle:
        random.shuffle(rows)
    rows = rows[args.start:] if args.limit == 0 else rows[args.start:args.start + args.limit]

    client_id = str(uuid.uuid4())

    stats = {
        "total_requested": len(rows),
        "success": 0,
        "failed": 0,
        "used_primary_workflow": 0,
        "used_tile_workflow": 0,
        "guidance_policy": {
            "global": [args.guidance_min, args.guidance_max],
            "background_tile": [args.tile_guidance_min, args.tile_guidance_max],
            "nature_object": [args.nature_guidance_min, args.nature_guidance_max],
            "enabled": args.guidance_randomize,
            "category_policy_enabled": args.use_category_guidance_policy
        }
    }

    start = time.perf_counter()

    for i, row in enumerate(rows):
        idx = args.start + i
        image_id = f"{idx:07d}_{uuid.uuid4().hex[:8]}"
        image_name = f"{image_id}.png"
        applied = {}

        try:
            tile_row = is_tile(row)

            if tile_row:
                workflow = json.loads(json.dumps(tile_workflow))
                selected_workflow_path = args.tile_workflow_api_json
                prompt_node = args.tile_prompt_node
                prompt_key = args.tile_prompt_input_key
                guidance_node = args.tile_guidance_node
                guidance_key = args.tile_guidance_key
                ksampler_node = args.tile_ksampler_node
                stats["used_tile_workflow"] += 1
            else:
                workflow = json.loads(json.dumps(primary_workflow))
                selected_workflow_path = args.workflow_api_json
                prompt_node = args.prompt_node
                prompt_key = args.prompt_input_key
                guidance_node = args.guidance_node
                guidance_key = args.guidance_key
                ksampler_node = args.ksampler_node
                stats["used_primary_workflow"] += 1

            # Inject prompt
            set_node_input(workflow, prompt_node, prompt_key, row["positive_prompt"], applied)

            # Optional seed override
            resolved_seed = None
            if args.override_seed_mode == "random":
                if not ksampler_node:
                    raise ValueError("Seed override requested but ksampler node missing for selected workflow")
                resolved_seed = random.randint(1, 2**31 - 1)
                set_node_input(workflow, ksampler_node, "seed", resolved_seed, applied)
            elif args.override_seed_mode == "fixed":
                if not ksampler_node:
                    raise ValueError("Fixed seed requested but ksampler node missing for selected workflow")
                if args.override_fixed_seed is None:
                    raise ValueError("--override-fixed-seed required for fixed seed mode")
                resolved_seed = args.override_fixed_seed
                set_node_input(workflow, ksampler_node, "seed", resolved_seed, applied)

            # Guidance randomization with category-specific nature range
            resolved_guidance = None
            guidance_source = None
            guidance_range_used = None
            if args.guidance_randomize:
                if not guidance_node:
                    raise ValueError("Guidance randomization enabled but guidance node missing for selected workflow")

                resolved_guidance, guidance_source, guidance_range_used = resolve_guidance_for_row(
                    row=row,
                    global_min=args.guidance_min,
                    global_max=args.guidance_max,
                    tile_min=args.tile_guidance_min,
                    tile_max=args.tile_guidance_max,
                    nature_min=args.nature_guidance_min,
                    nature_max=args.nature_guidance_max,
                    use_category_policy=args.use_category_guidance_policy,
                    decimals=args.guidance_decimals
                )
                set_node_input(workflow, guidance_node, guidance_key, resolved_guidance, applied)

            # Run workflow
            prompt_id = api_post_prompt(args.comfy-url if False else args.comfy_url, workflow, client_id)
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

            record = {
                "id": image_id,
                "domain": row.get("domain", "medieval_pixel_assets"),
                "asset_family": row.get("asset_family"),
                "image_path": str(out_path.relative_to(base_dir)),
                "caption": build_caption(row),
                "positive_prompt": row.get("positive_prompt"),
                "negative_prompt": "",
                "generation": {
                    "comfy_prompt_id": prompt_id,
                    "client_id": client_id,
                    "selected_workflow_api_json": selected_workflow_path,
                    "workflow_type": "tile" if tile_row else "primary",
                    "resolved_seed": resolved_seed,
                    "resolved_guidance": resolved_guidance,
                    "guidance_source": guidance_source,          # global | background_tile | nature_object
                    "guidance_range_used": guidance_range_used,  # [min,max]
                    "overrides_applied": applied
                }
            }

            sidecar = dirs["metadata"] / f"{image_id}.json"
            save_json(sidecar, record)
            append_jsonl(dirs["manifest"], record)
            stats["success"] += 1

        except Exception as e:
            stats["failed"] += 1
            append_jsonl(dirs["errors"], {
                "index": idx,
                "row_id": row.get("id"),
                "asset_family": row.get("asset_family"),
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
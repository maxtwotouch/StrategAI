#!/usr/bin/env python3
"""
sample_checkpoints.py — Standalone async LoRA checkpoint evaluation script.

Generates images from 6 LoRA checkpoints × 5 prompts, targeting a pool of
ComfyUI server nodes with shortest-queue load balancing.

Usage:
    python scripts/sample_checkpoints.py
    python scripts/sample_checkpoints.py --checkpoints ./my_checkpoints/ --output ./results/
    python scripts/sample_checkpoints.py --nodes https://g1.stixxert.dev,https://g2.stixxert.dev

Dependencies: httpx, websockets, Pillow (see dataset-gen-train/requirements.txt)
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import websockets
import websockets.exceptions
from PIL import Image

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

FIXED_SEED: int = 42
MAX_RETRIES: int = 3
DEFAULT_CHECKPOINTS_DIR: str = "../checkpoints-samples/checkpoints/"
DEFAULT_PROMPTS_FILE: str = "sample_prompts.json"
DEFAULT_OUTPUT_DIR: str = "./comparison_output/"
DEFAULT_NODES: str = "http://localhost:8188"
DEFAULT_WORKFLOW: str = "../../assetserver/workflows/txt2img.json"

# ASCII spinner for progress indication
SPINNER: list[str] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


# ---------------------------------------------------------------------------
#  CLI argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LoRA checkpoint evaluation — generate comparison images across 6 checkpoints × 5 prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --checkpoints ./my_ckpts/ --output ./results/
  %(prog)s --nodes https://g1.example.com,https://g2.example.com
        """,
    )
    parser.add_argument(
        "--checkpoints",
        default=DEFAULT_CHECKPOINTS_DIR,
        help=f"Path to checkpoint directory (default: {DEFAULT_CHECKPOINTS_DIR})",
    )
    parser.add_argument(
        "--prompts",
        default=DEFAULT_PROMPTS_FILE,
        help=f"Path to prompts JSON file (default: {DEFAULT_PROMPTS_FILE})",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for comparison images (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--nodes",
        default=DEFAULT_NODES,
        help="Comma-separated list of ComfyUI node URLs (default: g1-g4.stixxert.dev)",
    )
    parser.add_argument(
        "--workflow",
        default=DEFAULT_WORKFLOW,
        help=f"Path to txt2img.json workflow template (default: {DEFAULT_WORKFLOW})",
    )
    parser.add_argument(
        "--lora-strength",
        type=float,
        default=1.0,
        help="LoRA strength (0.0-1.0, default: 1.0). Use 0.0 for base model comparison.",
    )
    parser.add_argument(
        "--output-resolution",
        type=int,
        default=256,
        help="Output image resolution in pixels (default: 256). Use 1024 for full-resolution HF samples.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
#  Utility helpers
# ---------------------------------------------------------------------------

def checkpoint_to_experiment_name(filename: str) -> str:
    """Extract experiment name from checkpoint filename.

    "detailed_high_1800.safetensors" → "detailed_high"
    "ultra_low_1600.safetensors"    → "ultra_low"
    """
    stem = Path(filename).stem  # e.g. "detailed_high_1800"
    # Remove trailing _<digits> suffix
    match = re.match(r"^(.+)_(\d+)$", stem)
    if match:
        return match.group(1)
    return stem


def validate_output_structure(base_dir: Path) -> None:
    """Print the expected output directory tree for user confirmation."""
    print("\n📁 Expected output structure:")
    print(f"   {base_dir}/")
    experiments = [
        "detailed_high", "detailed_low",
        "minimal_high", "minimal_low",
        "ultra_high", "ultra_low",
    ]
    prompt_ids = ["S1", "S2", "U1", "U2", "L1"]
    for exp in experiments:
        print(f"   ├── {exp}/")
        for pid in prompt_ids:
            print(f"   │   ├── {pid}.png")


# ---------------------------------------------------------------------------
#  Retryable exception classification (mirrors assetserver pattern)
# ---------------------------------------------------------------------------

_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    websockets.exceptions.ConnectionClosed,
    OSError,
)


def _is_retryable(exc: BaseException) -> bool:
    """Return True if the exception suggests a transient node connectivity issue."""
    if isinstance(exc, _RETRYABLE_EXCEPTIONS):
        return True
    if isinstance(exc, RuntimeError) and "did not complete successfully" in str(exc):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600
    return False


# ---------------------------------------------------------------------------
#  Single-node ComfyUI client (standalone — mirrors assetserver pattern)
# ---------------------------------------------------------------------------

class ComfyUINode:
    """Async HTTP + WebSocket client for a single ComfyUI server instance."""

    def __init__(self, base_url: str, timeout: int = 300) -> None:
        self.base_url: str = base_url.rstrip("/")
        self.timeout: int = timeout
        self._http: httpx.AsyncClient | None = None

    async def get_http(self) -> httpx.AsyncClient:
        """Lazily-initialized httpx client with connection pooling."""
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=15.0),
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                ),
            )
        return self._http

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def get_queue_depth(self) -> int | None:
        """GET /queue → return queue depth (running + pending) or None if down."""
        try:
            http = await self.get_http()
            resp = await http.get("/queue", timeout=15)
            resp.raise_for_status()
            body = resp.json()
            running = len(body.get("queue_running", []))
            pending = len(body.get("queue_pending", []))
            return running + pending
        except Exception:
            return None

    async def queue_workflow(self, workflow: dict, client_id: str) -> str:
        """POST /prompt → return prompt_id."""
        http = await self.get_http()
        resp = await http.post(
            "/prompt",
            json={"prompt": workflow, "client_id": client_id},
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        node_errors = body.get("node_errors", {})
        if node_errors:
            raise ValueError(f"Workflow validation errors: {json.dumps(node_errors)}")
        if "prompt_id" not in body:
            raise ValueError(f"ComfyUI rejected workflow: {body.get('error', 'unknown')}")
        return body["prompt_id"]

    async def wait_for_completion(self, prompt_id: str, client_id: str) -> None:
        """Block until prompt completes. WebSocket preferred; falls back to polling."""
        try:
            await self._wait_via_ws(prompt_id, client_id)
            return
        except RuntimeError:
            raise
        except (
            websockets.exceptions.WebSocketException,
            ConnectionError,
            ConnectionRefusedError,
            ConnectionResetError,
            BrokenPipeError,
        ):
            pass  # fall through to polling
        except Exception:
            pass  # fall through to polling

        ok = await self._wait_via_polling(prompt_id)
        if not ok:
            raise RuntimeError(
                f"ComfyUI prompt {prompt_id} did not complete within timeout"
            )

    async def _wait_via_ws(self, prompt_id: str, client_id: str) -> None:
        """WebSocket monitoring for execution completion."""
        ws_url = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
        try:
            async with websockets.connect(
                f"{ws_url}/ws?clientId={client_id}",
                open_timeout=10,
                close_timeout=5,
            ) as ws:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", errors="replace")
                    if not raw or not raw.strip():
                        continue
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    msg_type = data.get("type", "")
                    msg_data = data.get("data", {})
                    if (
                        msg_type == "executing"
                        and msg_data.get("prompt_id") == prompt_id
                        and msg_data.get("node") is None
                    ):
                        return  # success
                    if (
                        msg_type == "execution_error"
                        and msg_data.get("prompt_id") == prompt_id
                    ):
                        raise RuntimeError(
                            f"Execution error for {prompt_id}: "
                            f"{msg_data.get('exception_type', 'unknown')}: "
                            f"{msg_data.get('exception_message', '')}"
                        )
        except asyncio.TimeoutError:
            pass  # fall through to polling check

    async def _wait_via_polling(self, prompt_id: str) -> bool:
        """Poll GET /history every 2s until prompt completes."""
        http = await self.get_http()
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                resp = await http.get(f"/history/{prompt_id}", timeout=15)
                resp.raise_for_status()
                history = resp.json()
                if prompt_id in history:
                    return True
            except Exception:
                pass
            await asyncio.sleep(2)
        return False

    async def get_result(self, prompt_id: str) -> dict:
        """GET /history/{prompt_id} → output metadata."""
        http = await self.get_http()
        resp = await http.get(f"/history/{prompt_id}", timeout=15)
        resp.raise_for_status()
        return resp.json()

    async def download_image(
        self,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output",
    ) -> bytes:
        """GET /view → raw PNG bytes."""
        http = await self.get_http()
        resp = await http.get(
            "/view",
            params={"filename": filename, "subfolder": subfolder, "type": folder_type},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.content


# ---------------------------------------------------------------------------
#  Load balancer across multiple ComfyUI nodes (shortest-queue selection)
# ---------------------------------------------------------------------------

class ComfyUILoadBalancer:
    """Distributes work across a pool of ComfyUI nodes using shortest-queue selection."""

    def __init__(self, urls: list[str], timeout: int = 300) -> None:
        self._nodes: list[tuple[str, ComfyUINode, bool]] = []
        for url in urls:
            node = ComfyUINode(url, timeout=timeout)
            self._nodes.append((url, node, True))  # (url, client, healthy)
        self._select_lock = asyncio.Lock()
        print(f"🌐 Load balancer initialized with {len(self._nodes)} node(s):")
        for url, _, _ in self._nodes:
            print(f"   • {url}")

    async def close(self) -> None:
        for _, node, _ in self._nodes:
            await node.close()
        self._nodes.clear()

    async def select_node(self) -> tuple[str, ComfyUINode]:
        """Select the healthiest node with the shortest queue depth."""
        async with self._select_lock:
            # Gather queue depths from all healthy nodes
            depths: list[tuple[int, int, str, ComfyUINode]] = []
            for idx, (url, node, healthy) in enumerate(self._nodes):
                if not healthy:
                    # Attempt recovery — a single successful ping restores health
                    depth = await node.get_queue_depth()
                    if depth is not None:
                        self._nodes[idx] = (url, node, True)
                        depths.append((depth, idx, url, node))
                    continue
                depth = await node.get_queue_depth()
                if depth is None:
                    self._nodes[idx] = (url, node, False)
                    print(f"   ⚠️  Node marked unhealthy: {url}")
                    continue
                depths.append((depth, idx, url, node))

            if not depths:
                raise RuntimeError("All ComfyUI nodes are unhealthy — cannot proceed")

            # Sort by queue depth, then by index for stable tie-breaking
            depths.sort(key=lambda x: (x[0], x[1]))
            _, _, url, node = depths[0]
            return url, node

    async def generate(
        self,
        workflow: dict,
        positive_prompt: str,
        seed: int,
        lora_name: str,
        lora_strength: float = 1.0,
        output_resolution: int | None = None,
    ) -> Image.Image:
        """Generate one image with automatic node selection and retry on failure."""
        errors: list[str] = []

        for attempt in range(MAX_RETRIES):
            url, node = await self.select_node()

            try:
                return await self._generate_on_node(
                    node, workflow, positive_prompt, seed, lora_name, lora_strength,
                    output_resolution=output_resolution,
                )
            except Exception as exc:
                if not _is_retryable(exc):
                    raise
                # Mark node unhealthy
                for idx, (n_url, _, _) in enumerate(self._nodes):
                    if n_url == url:
                        self._nodes[idx] = (url, self._nodes[idx][1], False)
                        break
                msg = f"Node {url} failed (attempt {attempt + 1}/{MAX_RETRIES}): {exc}"
                print(f"   ⚠️  {msg}")
                errors.append(msg)

        raise RuntimeError(
            f"All {MAX_RETRIES} attempts exhausted:\n" + "\n".join(errors)
        )

    async def _generate_on_node(
        self,
        node: ComfyUINode,
        workflow: dict,
        positive_prompt: str,
        seed: int,
        lora_name: str,
        lora_strength: float,
        output_resolution: int | None = None,
    ) -> Image.Image:
        """Execute the full generation lifecycle on a specific node."""
        import copy

        # Deep-copy workflow so the template stays pristine for reuse
        wf = copy.deepcopy(workflow)

        # Patch: inject prompt into node 5 (PrimitiveStringMultiline)
        if "5" in wf:
            wf["5"]["inputs"]["value"] = positive_prompt

        # Patch: inject seed into node 15 (RandomNoise)
        if "15" in wf:
            wf["15"]["inputs"]["noise_seed"] = seed

        # Patch: override LoRA in node 12 (LoraLoaderModelOnly)
        if "12" in wf:
            wf["12"]["inputs"]["lora_name"] = lora_name
            wf["12"]["inputs"]["strength_model"] = lora_strength

        # Patch: override output resolution (nodes 28 = OutputWidth, 29 = OutputHeight)
        if output_resolution is not None:
            if "28" in wf:
                wf["28"]["inputs"]["value"] = output_resolution
            if "29" in wf:
                wf["29"]["inputs"]["value"] = output_resolution

        client_id = str(uuid.uuid4())

        # Queue the workflow
        prompt_id = await node.queue_workflow(wf, client_id)

        # Wait for completion (WebSocket + polling fallback)
        await node.wait_for_completion(prompt_id, client_id)

        # Retrieve output metadata
        result = await node.get_result(prompt_id)
        outputs = result.get(prompt_id, {}).get("outputs", {})

        # Download the first image we find
        for _node_id, node_output in outputs.items():
            images = node_output.get("images", [])
            for img_info in images:
                if not isinstance(img_info, dict) or "filename" not in img_info:
                    continue
                data = await node.download_image(
                    filename=img_info["filename"],
                    subfolder=img_info.get("subfolder", ""),
                    folder_type=img_info.get("type", "output"),
                )
                with Image.open(io.BytesIO(data)) as pil_img:
                    return pil_img.convert("RGBA")

        raise RuntimeError("Workflow completed but produced no output images")


# ---------------------------------------------------------------------------
#  Core orchestration
# ---------------------------------------------------------------------------

async def run_generations(
    lb: ComfyUILoadBalancer,
    workflow: dict,
    checkpoints: dict[str, str],   # experiment_name → checkpoint_filename
    prompts: list[dict],            # list of {id, prompt, ...}
    output_dir: Path,
    lora_strength: float = 1.0,
    output_resolution: int | None = None,
) -> dict[str, list[dict]]:
    """Run all checkpoint × prompt combinations and return a result summary.

    Returns:
        Dict mapping experiment_name → list of {prompt_id, status, path, error}
    """
    # ── Base model mode: use only ONE checkpoint, output flat into output_dir ──
    if lora_strength == 0.0:
        print("\n📌 Mode: BASE MODEL (LoRA disabled)")
        first_key = next(iter(checkpoints))
        checkpoints = {first_key: checkpoints[first_key]}
        base_model_mode = True
    else:
        base_model_mode = False

    total = len(checkpoints) * len(prompts)
    completed = 0
    failed = 0
    summary: dict[str, list[dict]] = {exp: [] for exp in checkpoints}

    print(f"\n🎯 Starting generation: {len(checkpoints)} checkpoints × {len(prompts)} prompts = {total} images")
    print(f"   Seed: {FIXED_SEED}  |  LoRA strength: {lora_strength}")
    print(f"{'─' * 60}\n")

    start_time = time.monotonic()

    for exp_name, lora_filename in checkpoints.items():
        if base_model_mode:
            exp_dir = output_dir  # images go directly into output_dir (flat)
        else:
            exp_dir = output_dir / exp_name
        exp_dir.mkdir(parents=True, exist_ok=True)

        for prompt_entry in prompts:
            prompt_id = prompt_entry["id"]
            prompt_text = prompt_entry["prompt"]
            output_path = exp_dir / f"{prompt_id}.png"

            spinner_idx = completed % len(SPINNER)
            label = f"{exp_name}/{prompt_id}"
            print(
                f"  {SPINNER[spinner_idx]} Generating {label} ...",
                end="",
                flush=True,
            )

            try:
                img = await lb.generate(
                    workflow=workflow,
                    positive_prompt=prompt_text,
                    seed=FIXED_SEED,
                    lora_name=lora_filename,
                    lora_strength=lora_strength,
                    output_resolution=output_resolution,
                )
                # Composite onto white background for RGBA images (HF samples need opaque PNGs)
                if img.mode == "RGBA":
                    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                    img = Image.alpha_composite(background, img).convert("RGB")
                img.save(output_path, format="PNG")
                elapsed = time.monotonic() - start_time
                print(
                    f"\r  ✅ {label}.png  ({img.width}×{img.height}, "
                    f"{_format_duration(elapsed)} elapsed)",
                    flush=True,
                )
                summary[exp_name].append({
                    "prompt_id": prompt_id,
                    "status": "ok",
                    "path": str(output_path),
                })
                completed += 1
            except Exception as exc:
                print(f"\r  ❌ {label}  FAILED: {exc}", flush=True)
                summary[exp_name].append({
                    "prompt_id": prompt_id,
                    "status": "error",
                    "path": str(output_path),
                    "error": str(exc),
                })
                failed += 1

            # Brief pause between submissions to avoid hammering nodes
            await asyncio.sleep(0.5)

    total_elapsed = time.monotonic() - start_time
    print(f"\n{'─' * 60}")
    print(f"🏁 Complete: {completed}/{total} succeeded, {failed} failed")
    print(f"⏱️  Total time: {_format_duration(total_elapsed)}")
    return summary


def _format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins, secs = divmod(seconds, 60)
    if mins < 60:
        return f"{int(mins)}m {secs:.0f}s"
    hrs, mins = divmod(mins, 60)
    return f"{int(hrs)}h {int(mins)}m {secs:.0f}s"


# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    args = parse_args()

    # Resolve paths relative to the script's location
    script_dir = Path(__file__).resolve().parent
    checkpoints_dir = (script_dir / args.checkpoints).resolve()
    prompts_path = (script_dir / args.prompts).resolve()
    output_dir = (script_dir / args.output).resolve()
    workflow_path = (script_dir / args.workflow).resolve()

    # ── Validate inputs ──────────────────────────────────────────────
    if not checkpoints_dir.is_dir():
        print(f"❌ Checkpoints directory not found: {checkpoints_dir}")
        sys.exit(1)

    if not prompts_path.is_file():
        print(f"❌ Prompts file not found: {prompts_path}")
        sys.exit(1)

    if not workflow_path.is_file():
        print(f"❌ Workflow file not found: {workflow_path}")
        sys.exit(1)

    # ── Load checkpoints ─────────────────────────────────────────────
    checkpoint_files = sorted(
        f for f in os.listdir(checkpoints_dir) if f.endswith(".safetensors")
    )
    if len(checkpoint_files) != 6:
        print(
            f"⚠️  Expected 6 checkpoint files, found {len(checkpoint_files)}: "
            f"{checkpoint_files}"
        )
    if not checkpoint_files:
        print("❌ No .safetensors checkpoint files found in", checkpoints_dir)
        sys.exit(1)

    checkpoints: dict[str, str] = {}
    for fname in checkpoint_files:
        exp_name = checkpoint_to_experiment_name(fname)
        checkpoints[exp_name] = fname

    print("📦 Loaded checkpoints:")
    for exp, fname in checkpoints.items():
        print(f"   • {exp}  ←  {fname}")

    # ── Load prompts ─────────────────────────────────────────────────
    with open(prompts_path, "r") as fh:
        prompts_data = json.load(fh)
    prompts: list[dict] = prompts_data.get("prompts", [])
    if len(prompts) != 5:
        print(f"⚠️  Expected 5 prompts, found {len(prompts)}")
    if not prompts:
        print("❌ No prompts found in", prompts_path)
        sys.exit(1)

    print(f"\n📝 Loaded {len(prompts)} prompts:")
    for p in prompts:
        print(f"   • {p['id']}: {p['name']} ({p['category']})")

    # ── Load workflow template ───────────────────────────────────────
    with open(workflow_path, "r") as fh:
        workflow: dict = json.load(fh)
    print(f"\n🔧 Loaded workflow: {workflow_path.name} ({len(workflow)} nodes)")

    # ── Validate output structure ────────────────────────────────────
    validate_output_structure(output_dir)

    # ── Parse node URLs ──────────────────────────────────────────────
    node_urls = [u.strip() for u in args.nodes.split(",") if u.strip()]
    if not node_urls:
        print("❌ No ComfyUI node URLs provided")
        sys.exit(1)

    # ── Initialize load balancer ─────────────────────────────────────
    lb = ComfyUILoadBalancer(node_urls)

    try:
        # ── Quick health check ───────────────────────────────────────
        print("\n🔍 Checking node health...")
        healthy_count = 0
        for url, node, _ in lb._nodes:
            depth = await node.get_queue_depth()
            if depth is not None:
                print(f"   ✅ {url}  (queue depth: {depth})")
                healthy_count += 1
            else:
                print(f"   ❌ {url}  UNREACHABLE")
                # Mark unhealthy
                for idx, (n_url, _, _) in enumerate(lb._nodes):
                    if n_url == url:
                        lb._nodes[idx] = (url, lb._nodes[idx][1], False)
                        break

        if healthy_count == 0:
            print("\n❌ No healthy ComfyUI nodes — aborting.")
            sys.exit(1)

        print(f"   {healthy_count}/{len(node_urls)} nodes healthy\n")

        # ── Run all generations ──────────────────────────────────────
        summary = await run_generations(
            lb=lb,
            workflow=workflow,
            checkpoints=checkpoints,
            prompts=prompts,
            output_dir=output_dir,
            lora_strength=args.lora_strength,
            output_resolution=args.output_resolution,
        )

        # ── Print final summary ──────────────────────────────────────
        print("\n📊 Results Summary")
        print("=" * 60)
        total_ok = 0
        total_err = 0
        for exp_name, entries in summary.items():
            ok = sum(1 for e in entries if e["status"] == "ok")
            err = sum(1 for e in entries if e["status"] == "error")
            total_ok += ok
            total_err += err
            status_icon = "✅" if err == 0 else "⚠️"
            print(f"  {status_icon} {exp_name}: {ok}/{len(entries)} ok")
            for e in entries:
                if e["status"] == "error":
                    print(f"       ❌ {e['prompt_id']}: {e.get('error', 'unknown')[:120]}")
        print(f"\n  Total: {total_ok} succeeded, {total_err} failed")
        print(f"  Output: {output_dir.resolve()}")

        if total_err > 0:
            sys.exit(1)

    finally:
        await lb.close()


if __name__ == "__main__":
    asyncio.run(main())

"""HTTP + WebSocket client for a ComfyUI server.

Connects to an external ComfyUI instance (default http://127.0.0.1:8188) and
handles the full lifecycle: upload images, submit workflow JSON, poll for
completion via WebSocket or HTTP polling, and download generated images.

Not async -- uses blocking I/O.  Callers should run this in a thread-pool
executor if called from an async FastAPI endpoint.
"""

from __future__ import annotations

import io
import json
import logging
import time
import uuid
from typing import Any

import requests

try:
    import websocket  # type: ignore[import-untyped]
except ImportError:
    websocket = None  # type: ignore[assignment]

from PIL import Image

from .config import settings

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """Thin HTTP + (optional) WebSocket client for a single ComfyUI server."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.comfyui_base_url).rstrip("/")
        self.timeout = timeout or settings.comfyui_timeout

    # ------------------------------------------------------------------
    #  Public high-level API
    # ------------------------------------------------------------------

    def generate(
        self,
        workflow_path: str,
        *,
        positive_prompt: str | None = None,
        negative_prompt: str | None = None,
        seed: int | None = None,
        width: int | None = None,
        height: int | None = None,
        input_images: dict[str, Image.Image] | None = None,
        extra_overrides: dict[str, Any] | None = None,
    ) -> Image.Image:
        """Load a workflow JSON, patch it, run it, return the first output image.

        Parameters
        ----------
        workflow_path:
            Absolute path to the workflow JSON template.
        positive_prompt / negative_prompt:
            Text prompts to inject into the workflow.
        seed:
            KSampler seed.  Random if None.
        width / height:
            Latent image dimensions.
        input_images:
            Mapping of node_id → PIL Image to upload before queueing.
        extra_overrides:
            Arbitrary node input overrides: {node_id: {input_name: value}}.
        """
        # 1. Load workflow
        with open(workflow_path, "r") as fh:
            workflow = json.load(fh)

        # 2. Upload input images (usually for inpainting)
        uploaded: dict[str, str] = {}
        if input_images:
            for node_id, img in input_images.items():
                fname = f"{uuid.uuid4()}.png"
                uploaded[node_id] = self.upload_image(img, fname)

        # 3. Patch common parameters into the workflow
        workflow = _patch_workflow(
            workflow,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            width=width,
            height=height,
            uploaded_filenames=uploaded,
            extra_overrides=extra_overrides,
        )

        # 4. Queue
        prompt_id = self.queue_workflow(workflow)
        logger.info("ComfyUI prompt queued: %s", prompt_id)

        # 5. Wait for completion
        ok = self.wait_for_completion(prompt_id)
        if not ok:
            raise RuntimeError(f"ComfyUI prompt {prompt_id} did not complete successfully")

        # 6. Retrieve output filenames
        result = self.get_result(prompt_id)
        outputs = result.get(prompt_id, {}).get("outputs", {})

        # 7. Download the first image we find
        for _node_id, node_output in outputs.items():
            images = node_output.get("images", [])
            for img_info in images:
                data = self.download_image(
                    filename=img_info["filename"],
                    subfolder=img_info.get("subfolder", ""),
                    folder_type=img_info.get("type", "output"),
                )
                return Image.open(io.BytesIO(data)).convert("RGBA")

        raise RuntimeError(f"Workflow completed but produced no output images")

    # ------------------------------------------------------------------
    #  Low-level ComfyUI endpoints
    # ------------------------------------------------------------------

    def upload_image(self, pil_image: Image.Image, filename: str) -> str:
        """Upload a PIL image to ComfyUI's input/ folder.  Returns the stored filename."""
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        buf.seek(0)

        resp = requests.post(
            f"{self.base_url}/upload/image",
            files={"image": (filename, buf, "image/png")},
            data={"overwrite": "true"},
            timeout=30,
        )
        resp.raise_for_status()
        logger.debug("Uploaded image: %s", filename)
        return filename

    def queue_workflow(self, workflow: dict) -> str:
        """Submit a workflow JSON.  Returns the prompt_id."""
        client_id = str(uuid.uuid4())
        resp = requests.post(
            f"{self.base_url}/prompt",
            json={"prompt": workflow, "client_id": client_id},
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        if "node_errors" in body:
            raise ValueError(f"Workflow validation errors: {body['node_errors']}")
        return body["prompt_id"]

    def wait_for_completion(self, prompt_id: str) -> bool:
        """Block until the prompt finishes (WebSocket preferred; falls back to polling)."""
        if websocket is not None:
            return self._wait_via_ws(prompt_id)
        return self._wait_via_polling(prompt_id)

    def get_result(self, prompt_id: str) -> dict:
        """GET /history/{prompt_id} → parsed output dict."""
        resp = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def download_image(
        self,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output",
    ) -> bytes:
        """GET /view → raw PNG bytes."""
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        resp = requests.get(f"{self.base_url}/view", params=params, timeout=30)
        resp.raise_for_status()
        return resp.content

    def health_check(self) -> bool:
        """Ping ComfyUI.  Returns True if reachable."""
        try:
            resp = requests.get(f"{self.base_url}/system_stats", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    #  Private: waiting strategies
    # ------------------------------------------------------------------

    def _wait_via_ws(self, prompt_id: str) -> bool:
        """Use WebSocket to track execution progress."""
        ws = websocket.create_connection(  # type: ignore[union-attr]
            f"{self.base_url.replace('http', 'ws', 1)}/ws?clientId={uuid.uuid4()}",
            timeout=self.timeout,
        )
        try:
            while True:
                msg = ws.recv()
                if not msg:
                    continue
                data = json.loads(msg)
                msg_type = data.get("type", "")
                msg_data = data.get("data", {})

                if msg_type == "executing" and msg_data.get("prompt_id") == prompt_id:
                    if msg_data.get("node") is None:
                        return True  # execution complete

                if msg_type == "execution_error" and msg_data.get("prompt_id") == prompt_id:
                    logger.error("ComfyUI execution error: %s", msg_data)
                    return False

                if (
                    msg_type == "status"
                    and msg_data.get("status", {}).get("exec_info", {}).get("queue_remaining") == 0
                ):
                    # Might already be done; let's verify below
                    pass
        except Exception as exc:
            logger.warning("WebSocket error, falling back to polling: %s", exc)
            return self._wait_via_polling(prompt_id)
        finally:
            ws.close()
        return True

    def _wait_via_polling(self, prompt_id: str) -> bool:
        """Poll GET /history every 2 seconds until the prompt appears."""
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                history = self.get_result(prompt_id)
                if prompt_id in history:
                    return True
            except Exception:
                pass
            time.sleep(2)
        return False


# ------------------------------------------------------------------
#  Workflow patching helpers
# ------------------------------------------------------------------

_COMMON_NEGATIVE = "blurry, low res, realistic, 3d render, photorealistic"


def _patch_workflow(
    workflow: dict,
    *,
    positive_prompt: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    width: int | None = None,
    height: int | None = None,
    uploaded_filenames: dict[str, str] | None = None,
    extra_overrides: dict[str, Any] | None = None,
) -> dict:
    """Walk every node and replace common input parameters.

    Node identification is by class_type (e.g. 'CLIPTextEncode', 'KSampler',
    'EmptyLatentImage', 'LoadImage').
    """
    import random as _random

    if seed is None:
        seed = _random.randint(0, 2**32 - 1)

    uploaded = uploaded_filenames or {}

    for node_id, node in workflow.items():
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})

        # --- Prompt nodes ---
        if ct == "CLIPTextEncode":
            meta = node.get("_meta", {})
            title = meta.get("title", "").lower()
            if "positive" in title or "pos" in title:
                if positive_prompt is not None:
                    inputs["text"] = positive_prompt
            elif "negative" in title or "neg" in title:
                inputs["text"] = negative_prompt or _COMMON_NEGATIVE

        # --- KSampler ---
        if ct == "KSampler":
            if "seed" in inputs:
                inputs["seed"] = seed

        # --- EmptyLatentImage ---
        if ct == "EmptyLatentImage":
            if width is not None:
                inputs["width"] = width
            if height is not None:
                inputs["height"] = height

        # --- LoadImage (uploaded) ---
        if ct == "LoadImage" and node_id in uploaded:
            inputs["image"] = uploaded[node_id]

        # --- Arbitrary overrides ---
        if extra_overrides and node_id in extra_overrides:
            inputs.update(extra_overrides[node_id])

    return workflow


"""Async HTTP + WebSocket client for a ComfyUI server.

Connects to an external ComfyUI instance (default http://127.0.0.1:8188) and
handles the full lifecycle: upload images, submit workflow JSON, poll for
completion via WebSocket or HTTP polling, and download generated images.

Fully async — uses httpx for HTTP and websockets for WS.  Callers should
await directly from async FastAPI endpoints; no thread-pool needed.
"""

from __future__ import annotations

import io
import json
import logging
import os
import time
import uuid
from typing import Any

import httpx
import websockets
import websockets.exceptions

from PIL import Image

from src.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Singleton client (lazily created, shared across all engines)
# ---------------------------------------------------------------------------

_comfyui_client: ComfyUIClient | None = None
_comfyui_lb: "ComfyUILoadBalancer | None" = None


def get_comfyui_client() -> ComfyUIClient | None:
    """Return the shared ComfyUIClient singleton, creating it if needed."""
    global _comfyui_client
    if _comfyui_client is None:
        _comfyui_client = ComfyUIClient()
    return _comfyui_client


def get_comfyui_loadbalancer() -> "ComfyUILoadBalancer | None":
    """Return the shared :class:`ComfyUILoadBalancer` singleton.

    If ``comfyui.nodes`` is configured with multiple URLs the load-balancer
    distributes work across all of them.  For single-node deployments this
    is equivalent to a plain ``ComfyUIClient`` (pool size = 1).
    """
    global _comfyui_lb
    if _comfyui_lb is None:
        from src.comfyui_loadbalancer import ComfyUILoadBalancer

        _comfyui_lb = ComfyUILoadBalancer()
    return _comfyui_lb


async def close_comfyui_client() -> None:
    """Shut down the shared ComfyUI client (called during app shutdown)."""
    global _comfyui_client, _comfyui_lb
    if _comfyui_lb is not None:
        await _comfyui_lb.close()
        _comfyui_lb = None
    if _comfyui_client is not None:
        await _comfyui_client.close()
        _comfyui_client = None
        _comfyui_client = None


class ComfyUIClient:
    """Thin async HTTP + WebSocket client for a single ComfyUI server.

    Lazily creates and reuses a single ``httpx.AsyncClient`` for connection
    pooling.  Call ``close()`` during shutdown to release resources.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.comfyui.base_url).rstrip("/")
        self.timeout = timeout or settings.comfyui.timeout
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Release the underlying HTTP client."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @property
    def http(self) -> httpx.AsyncClient:
        """Lazily-initialised ``httpx.AsyncClient`` (not thread-safe)."""
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=15.0),
            )
        return self._http

    # ------------------------------------------------------------------
    #  Public high-level API
    # ------------------------------------------------------------------

    async def generate(
        self,
        workflow_path: str,
        *,
        positive_prompt: str | None = None,
        seed: int | None = None,
        width: int | None = None,
        height: int | None = None,
        input_images: dict[str, Image.Image] | None = None,
        extra_overrides: dict[str, Any] | None = None,
        ref_image_filename: str | None = None,
    ) -> Image.Image:
        """Load a workflow JSON, patch it, run it, return the first output image.

        Flux2 Klein does not use negative prompts — only positive_prompt is
        injected into ``CLIPTextEncode`` nodes.

        Parameters
        ----------
        workflow_path:
            Absolute path to the workflow JSON template.
        positive_prompt:
            Text prompt to inject into CLIPTextEncode nodes.
        seed:
            Injected into ``SamplerCustomAdvanced.noise_seed``.  Random if None.
        width / height:
            Injected into ``EmptyFlux2LatentImage`` if present.
        input_images:
            Mapping of node_id → PIL Image to upload before queueing.
        extra_overrides:
            Arbitrary node input overrides: ``{node_id: {input_name: value}}``.
        ref_image_filename:
            Filename for LoadImage nodes whose ``_meta.title`` contains
            "reference".  The image must already be uploaded to ComfyUI's
            ``input/`` folder.
        """
        # 1. Load workflow
        with open(workflow_path, "r") as fh:
            workflow = json.load(fh)

        # 2. Upload input images (usually for inpainting)
        uploaded: dict[str, str] = {}
        if input_images:
            for node_id, img in input_images.items():
                fname = f"{uuid.uuid4()}.png"
                uploaded[node_id] = await self.upload_image(img, fname)

        # 3. Patch common parameters into the workflow
        workflow = _patch_workflow(
            workflow,
            positive_prompt=positive_prompt,
            seed=seed,
            width=width,
            height=height,
            uploaded_filenames=uploaded,
            extra_overrides=extra_overrides,
            ref_image_filename=ref_image_filename,
        )

        # 4. Queue
        prompt_id = await self.queue_workflow(workflow)
        logger.info("ComfyUI prompt queued: %s", prompt_id)

        # 5. Wait for completion
        ok = await self.wait_for_completion(prompt_id)
        if not ok:
            raise RuntimeError(
                f"ComfyUI prompt {prompt_id} did not complete successfully"
            )

        # 6. Retrieve output filenames
        result = await self.get_result(prompt_id)
        outputs = result.get(prompt_id, {}).get("outputs", {})

        # 7. Download the first image we find
        for _node_id, node_output in outputs.items():
            images = node_output.get("images", [])
            for img_info in images:
                data = await self.download_image(
                    filename=img_info["filename"],
                    subfolder=img_info.get("subfolder", ""),
                    folder_type=img_info.get("type", "output"),
                )
                return Image.open(io.BytesIO(data)).convert("RGBA")

        raise RuntimeError("Workflow completed but produced no output images")

    # ------------------------------------------------------------------
    #  Low-level ComfyUI endpoints
    # ------------------------------------------------------------------

    async def upload_image(self, pil_image: Image.Image, filename: str) -> str:
        """Upload a PIL image to ComfyUI's ``input/`` folder.  Returns the stored filename."""
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        buf.seek(0)

        resp = await self.http.post(
            "/upload/image",
            files={"image": (filename, buf, "image/png")},
            data={"overwrite": "true"},
            timeout=30,
        )
        resp.raise_for_status()
        logger.debug("Uploaded image: %s", filename)
        return filename

    async def upload_reference_image(
        self, pil_image: Image.Image, filename: str
    ) -> str:
        """Upload a reference image to ComfyUI's ``input/`` folder.

        Different from ``upload_image()``: this always overwrites and is
        intended for reference images that persist across multiple
        generations.  Returns the stored filename.
        """
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        buf.seek(0)

        resp = await self.http.post(
            "/upload/image",
            files={"image": (filename, buf, "image/png")},
            data={"overwrite": "true", "type": "input"},
            timeout=30,
        )
        resp.raise_for_status()
        logger.info("Uploaded reference image: %s", filename)
        return filename

    async def queue_workflow(self, workflow: dict) -> str:
        """Submit a workflow JSON.  Returns the ``prompt_id``."""
        client_id = str(uuid.uuid4())
        resp = await self.http.post(
            "/prompt",
            json={"prompt": workflow, "client_id": client_id},
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        if "node_errors" in body:
            raise ValueError(f"Workflow validation errors: {body['node_errors']}")
        return body["prompt_id"]

    async def wait_for_completion(self, prompt_id: str) -> bool:
        """Block until the prompt finishes (WebSocket preferred; falls back to polling)."""
        try:
            return await self._wait_via_ws(prompt_id)
        except Exception as exc:
            logger.warning("WebSocket error, falling back to polling: %s", exc)
            return await self._wait_via_polling(prompt_id)

    async def get_result(self, prompt_id: str) -> dict:
        """``GET /history/{prompt_id}`` → parsed output dict."""
        resp = await self.http.get(f"/history/{prompt_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()

    async def download_image(
        self,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output",
    ) -> bytes:
        """``GET /view`` → raw PNG bytes."""
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        resp = await self.http.get("/view", params=params, timeout=30)
        resp.raise_for_status()
        return resp.content

    async def health_check(self) -> bool:
        """Ping ComfyUI.  Returns ``True`` if reachable."""
        try:
            resp = await self.http.get("/system_stats", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    async def cancel_prompt(self, prompt_id: str) -> bool:
        """Cancel a queued or running prompt.  Returns ``True`` if successful."""
        try:
            resp = await self.http.post(
                "/queue",
                json={"delete": [prompt_id]},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def get_queue_info(self) -> dict | None:
        """``GET /queue`` → queue depth and status.

        Returns a dict with ``running``, ``pending``, and ``depth`` keys,
        or ``None`` if the node is unreachable.
        """
        try:
            resp = await self.http.get("/queue", timeout=5)
            resp.raise_for_status()
            body = resp.json()
            running = body.get("queue_running", [])
            pending = body.get("queue_pending", [])
            return {
                "running": len(running),
                "pending": len(pending),
                "depth": len(running) + len(pending),
            }
        except Exception:
            return None

    # ------------------------------------------------------------------
    #  Private: waiting strategies
    # ------------------------------------------------------------------

    async def _wait_via_ws(self, prompt_id: str) -> bool:
        """Use async WebSocket to track execution progress."""
        ws_url = self.base_url.replace("http", "ws", 1)
        async with websockets.connect(
            f"{ws_url}/ws?clientId={uuid.uuid4()}",
            open_timeout=10,
            close_timeout=5,
        ) as ws:
            try:
                async for raw in ws:
                    data = json.loads(raw)
                    msg_type = data.get("type", "")
                    msg_data = data.get("data", {})

                    if (
                        msg_type == "executing"
                        and msg_data.get("prompt_id") == prompt_id
                    ):
                        if msg_data.get("node") is None:
                            return True  # execution complete

                    if (
                        msg_type == "execution_error"
                        and msg_data.get("prompt_id") == prompt_id
                    ):
                        logger.error(
                            "ComfyUI execution error: %s", msg_data
                        )
                        return False
            except websockets.exceptions.ConnectionClosed as exc:
                logger.warning("WebSocket closed: %s", exc)
                return True  # assume completion on graceful close

        # If the loop exited naturally, fall back to polling
        return await self._wait_via_polling(prompt_id)

    async def _wait_via_polling(self, prompt_id: str) -> bool:
        """Poll ``GET /history`` every 2 seconds until the prompt appears."""
        import asyncio

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                history = await self.get_result(prompt_id)
                if prompt_id in history:
                    return True
            except Exception:
                pass
            await asyncio.sleep(2)
        return False


# ------------------------------------------------------------------
#  Workflow patching helpers
# ------------------------------------------------------------------

def _patch_workflow(
    workflow: dict,
    *,
    positive_prompt: str | None = None,
    seed: int | None = None,
    width: int | None = None,
    height: int | None = None,
    uploaded_filenames: dict[str, str] | None = None,
    extra_overrides: dict[str, Any] | None = None,
    ref_image_filename: str | None = None,
) -> dict:
    """Walk every node and replace common input parameters.

    Flux2 Klein node graph — no KSampler, no negative prompts.

    Node identification is by ``class_type``:
    - ``CLIPTextEncode`` → positive prompt
    - ``SamplerCustomAdvanced`` → noise_seed
    - ``EmptyFlux2LatentImage`` → width / height
    - ``Flux2Scheduler`` → steps / denoise
    - ``CFGGuider`` → cfg
    - ``LoadImage`` → uploaded image or reference filename
    """
    import random as _random

    if seed is None:
        seed = _random.randint(0, 2**32 - 1)

    uploaded = uploaded_filenames or {}

    for node_id, node in workflow.items():
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})

        # --- Positive prompt (Flux2 has no negative prompt node) ---
        if ct == "CLIPTextEncode":
            if positive_prompt is not None:
                inputs["text"] = positive_prompt

        # --- Seed (Flux2 uses SamplerCustomAdvanced + noise_seed) ---
        if ct == "SamplerCustomAdvanced":
            if "noise_seed" in inputs:
                inputs["noise_seed"] = seed

        # --- Latent dimensions ---
        if ct == "EmptyFlux2LatentImage":
            if width is not None:
                inputs["width"] = width
            if height is not None:
                inputs["height"] = height

        # --- LoadImage (uploaded) ---
        if ct == "LoadImage" and node_id in uploaded:
            inputs["image"] = uploaded[node_id]

        # --- LoadImage reference filename ---
        if ct == "LoadImage" and ref_image_filename is not None:
            meta = node.get("_meta", {})
            title = meta.get("title", "").lower()
            if "reference" in title:
                # Sanitize to prevent path traversal
                inputs["image"] = os.path.basename(ref_image_filename)

        # --- Arbitrary overrides ---
        if extra_overrides and node_id in extra_overrides:
            inputs.update(extra_overrides[node_id])

    return workflow

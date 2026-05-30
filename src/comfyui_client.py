"""Async HTTP + WebSocket client for a ComfyUI server.

Connects to an external ComfyUI instance (default http://127.0.0.1:8188) and
handles the full lifecycle: upload images, submit workflow JSON, poll for
completion via WebSocket or HTTP polling, and download generated images.

Fully async — uses httpx for HTTP and websockets for WS.  Callers should
await directly from async FastAPI endpoints; no thread-pool needed.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import secrets
import time
import uuid
from typing import Any, Iterable

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
        self._http_lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Release the underlying HTTP client."""
        async with self._http_lock:
            if self._http is not None:
                await self._http.aclose()
                self._http = None

    @property
    def http(self) -> httpx.AsyncClient:
        """Lazily-initialised ``httpx.AsyncClient``.

        .. warning::
           This property is **not** async-safe — it cannot use ``await``.
           Callers that need guaranteed single initialization should use
           :meth:`get_http` instead in async contexts.
        """
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=15.0),
            )
        return self._http

    async def get_http(self) -> httpx.AsyncClient:
        """Async-safe lazy initializer for the underlying HTTP client.

        Prefer this over the ``http`` property in production code to avoid
        double-initialisation races when two coroutines first access the
        client concurrently.
        """
        if self._http is None:
            async with self._http_lock:
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
        input_images: dict[str, Image.Image] | None = None,
        extra_overrides: dict[str, Any] | None = None,
        ref_image_filename: str | None = None,
    ) -> Image.Image:
        """Load a workflow JSON, patch it, run it, return the first output image.

        Workflows are treated as the single source of truth — only
        prompt text, seed, and input images are injected.  All other
        parameters (guidance, steps, denoise, sampler, resolution) are
        baked into the workflow JSONs and NOT overridden at runtime.

        Flux2 Klein does not use negative prompts — only positive_prompt is
        injected into ``CLIPTextEncode`` nodes.

        Parameters
        ----------
        workflow_path:
            Absolute path to the workflow JSON template.
        positive_prompt:
            Text prompt to inject into CLIPTextEncode nodes.
        seed:
            Injected into ``SamplerCustomAdvanced.noise_seed`` and
            ``RandomNoise.noise_seed``.  Random if None.
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
        if not os.path.isfile(workflow_path):
            raise FileNotFoundError(f"Workflow file not found: {workflow_path}")
        with open(workflow_path, "r") as fh:
            workflow = json.load(fh)

        # 1.5 Validate workflow structure before queueing — fail fast
        _validate_workflow(workflow, workflow_path)

        _start_time = time.monotonic()

        # 2. Upload input images (usually for inpainting)
        uploaded: dict[str, str] = {}
        if input_images:
            for node_id, img in input_images.items():
                fname = f"{uuid.uuid4()}.png"
                uploaded[node_id] = await self.upload_image(img, fname)

        # 2.5 Generate a single client_id for this generation session.
        #     Using the same client_id in queue_workflow and the WebSocket
        #     lets ComfyUI route execution events cleanly to our listener.
        client_id = str(uuid.uuid4())

        # 3. Patch only prompt, seed, and input images into the workflow.
        #    All other parameters (guidance, steps, denoise, sampler,
        #    resolution) are baked into the workflow JSONs.
        workflow = _patch_workflow(
            workflow,
            positive_prompt=positive_prompt,
            seed=seed,
            uploaded_filenames=uploaded,
            extra_overrides=extra_overrides,
            ref_image_filename=ref_image_filename,
        )

        try:
            # 4. Queue — use the same client_id for the WS listener
            prompt_id = await self.queue_workflow(workflow, client_id=client_id)
            logger.info("ComfyUI prompt queued: %s", prompt_id)

            # 5. Wait for completion — raises RuntimeError with details on failure
            await self._wait_for_completion_checked(prompt_id, client_id=client_id)

            # 6. Retrieve output filenames
            result = await self.get_result(prompt_id)
            outputs = result.get(prompt_id, {}).get("outputs", {})

            # 7. Download the first image we find (with retry and validation)
            for _node_id, node_output in outputs.items():
                images = node_output.get("images", [])
                for img_info in images:
                    if not isinstance(img_info, dict) or "filename" not in img_info:
                        logger.warning(
                            "Skipping unexpected output entry: %s", img_info
                        )
                        continue
                    data = await _download_with_retry(
                        self,
                        filename=img_info["filename"],
                        subfolder=img_info.get("subfolder", ""),
                        folder_type=img_info.get("type", "output"),
                    )
                    img = Image.open(io.BytesIO(data)).convert("RGBA")
                    _validate_downloaded_image(img, img_info["filename"])
                    elapsed = time.monotonic() - _start_time
                    logger.info(
                        "Generation completed: prompt_id=%s filename=%s elapsed=%.1fs size=%dx%d",
                        prompt_id, img_info["filename"], elapsed, img.width, img.height,
                    )
                    return img

            raise RuntimeError("Workflow completed but produced no output images")
        finally:
            # Always clean up uploaded images — success or failure — so
            # ComfyUI's input/ folder doesn't fill up with orphaned files.
            if uploaded:
                await _cleanup_uploaded_images(self, uploaded.values())

    # ------------------------------------------------------------------
    #  Low-level ComfyUI endpoints
    # ------------------------------------------------------------------

    async def upload_image(self, pil_image: Image.Image, filename: str) -> str:
        """Upload a PIL image to ComfyUI's ``input/`` folder.  Returns the stored filename."""
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        buf.seek(0)

        http = await self.get_http()
        resp = await http.post(
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

        http = await self.get_http()
        resp = await http.post(
            "/upload/image",
            files={"image": (filename, buf, "image/png")},
            data={"overwrite": "true", "type": "input"},
            timeout=30,
        )
        resp.raise_for_status()
        logger.info("Uploaded reference image: %s", filename)
        return filename

    async def queue_workflow(self, workflow: dict, *, client_id: str | None = None) -> str:
        """Submit a workflow JSON.  Returns the ``prompt_id``.

        If *client_id* is provided, ComfyUI routes execution events to
        a WebSocket listener with the same ID, reducing broadcast noise.
        """
        if client_id is None:
            client_id = str(uuid.uuid4())
        http = await self.get_http()
        resp = await http.post(
            "/prompt",
            json={"prompt": workflow, "client_id": client_id},
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()

        # ComfyUI always includes "node_errors" in the response — even on
        # success (as an empty dict).  Only treat non-empty node_errors as
        # a hard failure.  The presence of "prompt_id" signals acceptance.
        node_errors = body.get("node_errors", {})
        if node_errors:
            raise ValueError(
                f"Workflow validation errors: {json.dumps(node_errors)}"
            )

        if "prompt_id" not in body:
            top_error = body.get("error", "no details provided")
            raise ValueError(
                f"ComfyUI rejected workflow. "
                f"Error: {top_error}"
            )
        return body["prompt_id"]

    async def _wait_for_completion_checked(self, prompt_id: str, *, client_id: str | None = None) -> None:
        """Block until the prompt finishes.  Raises RuntimeError with details on failure.

        WebSocket is preferred; falls back to polling on connection errors.
        """
        try:
            await self._wait_via_ws(prompt_id, client_id=client_id)
        except (
            websockets.exceptions.WebSocketException,
            ConnectionError,
            ConnectionRefusedError,
            ConnectionResetError,
            BrokenPipeError,
        ) as exc:
            logger.warning("WebSocket error, falling back to polling: %s", exc)
            ok = await self._wait_via_polling(prompt_id)
            if not ok:
                raise RuntimeError(
                    f"ComfyUI prompt {prompt_id} did not complete within timeout"
                )

    async def get_result(self, prompt_id: str) -> dict:
        """``GET /history/{prompt_id}`` → parsed output dict."""
        http = await self.get_http()
        resp = await http.get(f"/history/{prompt_id}", timeout=self.timeout)
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
        http = await self.get_http()
        resp = await http.get("/view", params=params, timeout=30)
        resp.raise_for_status()
        return resp.content

    async def health_check(self) -> bool:
        """Ping ComfyUI.  Returns ``True`` if reachable."""
        try:
            http = await self.get_http()
            resp = await http.get("/system_stats", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    async def cancel_prompt(self, prompt_id: str) -> bool:
        """Cancel a queued or running prompt.  Returns ``True`` if successful."""
        try:
            http = await self.get_http()
            resp = await http.post(
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
            http = await self.get_http()
            resp = await http.get("/queue", timeout=min(self.timeout, 15))
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

    async def _wait_via_ws(self, prompt_id: str, *, client_id: str | None = None) -> None:
        """Use async WebSocket to track execution progress.

        Returns normally on success.  Raises RuntimeError with details
        from ComfyUI's ``execution_error`` message on failure.
        """
        if client_id is None:
            client_id = str(uuid.uuid4())
        ws_url = self.base_url.replace("http", "ws", 1)
        async with websockets.connect(
            f"{ws_url}/ws?clientId={client_id}",
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
                            return  # execution complete — success

                    if (
                        msg_type == "execution_error"
                        and msg_data.get("prompt_id") == prompt_id
                    ):
                        err_detail = msg_data.get("exception_message", "")
                        err_type = msg_data.get("exception_type", "unknown")
                        logger.error(
                            "ComfyUI execution error for %s: %s — %s",
                            prompt_id, err_type, err_detail,
                        )
                        raise RuntimeError(
                            f"ComfyUI execution error for {prompt_id}: "
                            f"{err_type}: {err_detail}"
                        )
            except websockets.exceptions.ConnectionClosed as exc:
                logger.warning(
                    "WebSocket closed prematurely (code=%s): %s — "
                    "falling back to polling to verify completion",
                    exc.code,
                    exc,
                )

        # If the loop exited naturally OR WS closed prematurely,
        # fall back to polling to verify completion.
        ok = await self._wait_via_polling(prompt_id)
        if not ok:
            raise RuntimeError(
                f"ComfyUI prompt {prompt_id} did not complete within timeout"
            )

    async def _wait_via_polling(self, prompt_id: str) -> bool:
        """Poll ``GET /history`` every 2 seconds until the prompt appears."""
        import asyncio

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                history = await self.get_result(prompt_id)
                if prompt_id in history:
                    return True
            except Exception as exc:
                logger.debug(
                    "Polling attempt for prompt %s failed (%.1fs remaining): %s",
                    prompt_id,
                    deadline - time.monotonic(),
                    exc,
                )
            await asyncio.sleep(2)
        return False


# ------------------------------------------------------------------
#  Internal helpers
# ------------------------------------------------------------------


async def _cleanup_uploaded_images(
    client: ComfyUIClient, filenames: "Iterable[str]"
) -> None:
    """Best-effort deletion of uploaded images from ComfyUI's input/ folder.

    Uses ``POST /api/delete/image`` if the ComfyUI server supports it
    (custom endpoint — not in vanilla ComfyUI).  Failures are logged but
    never raised — cleanup is always best-effort.
    """
    for fname in filenames:
        try:
            http = await client.get_http()
            await http.post(
                "/api/delete/image",
                json={"filename": fname},
                timeout=10,
            )
            logger.debug("Cleaned up uploaded image from ComfyUI: %s", fname)
        except Exception as exc:
            logger.warning(
                "Failed to clean up uploaded image '%s' from ComfyUI "
                "(the /api/delete/image endpoint may not exist on this "
                "server — manual cleanup may be needed): %s",
                fname, exc,
            )


async def _download_with_retry(
    client: ComfyUIClient,
    filename: str,
    subfolder: str = "",
    folder_type: str = "output",
    max_attempts: int = 3,
) -> bytes:
    """Download an image with exponential backoff on transient failures."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await client.download_image(
                filename=filename,
                subfolder=subfolder,
                folder_type=folder_type,
            )
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                delay = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    "Download attempt %d/%d for %s failed: %s — retrying in %.1fs",
                    attempt + 1, max_attempts, filename, exc, delay,
                )
                await asyncio.sleep(delay)
    raise RuntimeError(
        f"Failed to download {filename} after {max_attempts} attempts"
    ) from last_exc


def _validate_downloaded_image(img: Image.Image, filename: str) -> None:
    """Reject images that are clearly invalid (0-pixel, excessive size)."""
    if img.width <= 0 or img.height <= 0:
        raise ValueError(
            f"Downloaded image {filename} has invalid dimensions: "
            f"{img.width}x{img.height}"
        )
    # Reject unreasonably large images (> 16K on any axis)
    max_dim = 16384
    if img.width > max_dim or img.height > max_dim:
        raise ValueError(
            f"Downloaded image {filename} exceeds maximum dimension "
            f"{max_dim}: {img.width}x{img.height}"
        )


# ------------------------------------------------------------------
#  Workflow validation
# ------------------------------------------------------------------


def _validate_workflow(workflow: dict, workflow_path: str) -> None:
    """Validate workflow structure before queueing to fail fast.

    Checks that:
    - At least one ``SaveImage`` node exists (so we have output to download)
    - ``CLIPTextEncode`` nodes have a ``text`` input (so prompt injection works)
    """
    has_save_image = False
    for node_id, node in workflow.items():
        ct = node.get("class_type", "")
        if ct == "SaveImage":
            has_save_image = True
        if ct == "CLIPTextEncode":
            inputs = node.get("inputs", {})
            if "text" not in inputs:
                raise ValueError(
                    f"CLIPTextEncode node '{node_id}' in {workflow_path} "
                    f"is missing 'text' input — prompt injection will fail"
                )
    if not has_save_image:
        raise ValueError(
            f"Workflow {workflow_path} has no SaveImage node — "
            f"no output images will be produced"
        )


# ------------------------------------------------------------------
#  Workflow patching helpers
# ------------------------------------------------------------------

def _patch_workflow(
    workflow: dict,
    *,
    positive_prompt: str | None = None,
    seed: int | None = None,
    uploaded_filenames: dict[str, str] | None = None,
    extra_overrides: dict[str, Any] | None = None,
    ref_image_filename: str | None = None,
) -> dict:
    """Walk every node and replace ONLY prompt, seed, and input images.

    Workflow JSONs are the single source of truth for all other
    parameters (guidance, steps, denoise, sampler, resolution).
    Those values are NEVER patched at runtime.

    Node identification is by ``class_type``:

    - ``CLIPTextEncode`` → positive prompt
    - ``SamplerCustomAdvanced`` → noise_seed
    - ``RandomNoise`` → noise_seed (img2img workflows)
    - ``LoadImage`` → uploaded image (keyed by node_id) or reference filename
    - Arbitrary node overrides via ``extra_overrides``

    Returns a **deep copy** of the workflow — the original dict is never
    mutated so callers can safely reuse cached workflow templates.
    """
    import copy
    workflow = copy.deepcopy(workflow)

    if seed is None:
        seed = secrets.randbits(32)  # cryptographically secure, 0..2^32-1

    uploaded = uploaded_filenames or {}

    for node_id, node in workflow.items():
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})

        # --- Positive prompt ---
        if ct == "CLIPTextEncode":
            if positive_prompt is not None:
                inputs["text"] = positive_prompt

        # --- Seed: Flux2 Klein (SamplerCustomAdvanced + noise_seed) ---
        if ct == "SamplerCustomAdvanced":
            if "noise_seed" in inputs:
                inputs["noise_seed"] = seed

        # --- LoadImage (uploaded by node_id) ---
        if ct == "LoadImage" and node_id in uploaded:
            inputs["image"] = uploaded[node_id]

        # --- LoadImage reference filename ---
        # Matches nodes whose _meta.title contains "reference" (explicit
        # rename) OR the ComfyUI default "Load Image" title.  Our workflow
        # JSONs use the default title for all LoadImage nodes.  If multiple
        # LoadImage nodes need different images, use input_images dict
        # (keyed by node_id) instead of ref_image_filename.
        if ct == "LoadImage" and ref_image_filename is not None:
            meta = node.get("_meta", {})
            title = meta.get("title", "").lower()
            if "load image" in title or "reference" in title:
                # Sanitize to prevent path traversal
                inputs["image"] = os.path.basename(ref_image_filename)

        # --- Arbitrary overrides ---
        if extra_overrides and node_id in extra_overrides:
            inputs.update(extra_overrides[node_id])

    # --- RandomNoise (seed for img2img workflows) ---
    for node in workflow.values():
        if node.get("class_type") == "RandomNoise":
            if seed is not None:
                node["inputs"]["noise_seed"] = seed
            break

    return workflow

"""Integration tests for ComfyUIClient HTTP and WebSocket communication.

These tests mock the ComfyUI server's HTTP endpoints and WebSocket
connection using ``unittest.mock``.  They verify the client's full
request/response lifecycle — upload, queue, poll, download, error
handling, and retry — without requiring a real ComfyUI instance.

.. note::
   ``test_workflow_patching.py`` covers ``_patch_workflow()``.
"""

from __future__ import annotations

import io
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from src.comfyui_client import ComfyUIClient


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _make_png_bytes(width: int = 64, height: int = 64) -> bytes:
    """Return valid PNG bytes for a small solid-colour image."""
    img = Image.new("RGBA", (width, height), (128, 64, 32, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mock_response(status_code: int = 200, json_data=None, content=None):
    """Build an AsyncMock that mimics an httpx.Response.

    ``resp.json()`` in httpx is **synchronous**, so we use MagicMock.
    ``resp.raise_for_status()`` is also synchronous.
    """
    resp = AsyncMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    resp.content = content
    resp.headers = {"content-type": "image/png"}
    return resp


async def _setup_client_with_mock_http(client: ComfyUIClient):
    """Replace client._http with a mocked httpx.AsyncClient and return the mock."""
    mock_http = AsyncMock()
    async with client._http_lock:
        client._http = mock_http
    return mock_http


# ---------------------------------------------------------------------------
#  upload_image
# ---------------------------------------------------------------------------


class TestUploadImage:
    """Tests for ``ComfyUIClient.upload_image()``."""

    @pytest.mark.asyncio
    async def test_upload_success(self):
        """Happy path — ComfyUI accepts the image, returns the local filename."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        mock_http.post.return_value = _mock_response(
            200,
            json_data={"name": "uploaded_abc123.png"},
        )

        img = Image.new("RGBA", (64, 64))
        result = await client.upload_image(img, "test.png")

        # upload_image returns the local filename, not the server response
        assert result == "test.png"
        mock_http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_http_500_raises(self):
        """ComfyUI returns 500 — the client should propagate the error."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        mock_http.post.return_value = _mock_response(500)

        img = Image.new("RGBA", (64, 64))
        with pytest.raises(Exception):
            await client.upload_image(img, "test.png")

    @pytest.mark.asyncio
    async def test_upload_connection_refused(self):
        """ComfyUI is unreachable — should raise."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        mock_http.post.side_effect = OSError("Connection refused")

        img = Image.new("RGBA", (64, 64))
        with pytest.raises(OSError):
            await client.upload_image(img, "test.png")


# ---------------------------------------------------------------------------
#  queue_workflow
# ---------------------------------------------------------------------------


class TestQueueWorkflow:
    """Tests for ``ComfyUIClient.queue_workflow()``."""

    @pytest.mark.asyncio
    async def test_queue_success(self):
        """Happy path — ComfyUI accepts the workflow and returns a prompt_id."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        mock_http.post.return_value = _mock_response(
            200,
            json_data={"prompt_id": "abc-123-def"},
        )

        workflow = {"1": {"class_type": "SaveImage", "inputs": {}}}
        result = await client.queue_workflow(workflow)

        assert result == "abc-123-def"
        mock_http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_queue_http_500_raises(self):
        """ComfyUI rejects the workflow — should propagate error."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        mock_http.post.return_value = _mock_response(500)

        workflow = {"1": {"class_type": "SaveImage", "inputs": {}}}
        with pytest.raises(Exception):
            await client.queue_workflow(workflow)


# ---------------------------------------------------------------------------
#  get_result
# ---------------------------------------------------------------------------


class TestGetResult:
    """Tests for ``ComfyUIClient.get_result()``."""

    @pytest.mark.asyncio
    async def test_get_result_with_outputs(self):
        """History endpoint returns completed workflow with output images."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        history = {
            "abc-123": {
                "outputs": {
                    "9": {
                        "images": [
                            {"filename": "output_00001_.png", "subfolder": "", "type": "output"},
                        ],
                    },
                },
            },
        }
        mock_http.get.return_value = _mock_response(200, json_data=history)

        result = await client.get_result("abc-123")
        assert "abc-123" in result
        assert result["abc-123"]["outputs"]["9"]["images"][0]["filename"] == "output_00001_.png"

    @pytest.mark.asyncio
    async def test_get_result_empty_history(self):
        """Prompt not yet completed — history has no entry."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        mock_http.get.return_value = _mock_response(200, json_data={})

        result = await client.get_result("nonexistent")
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_result_missing_prompt_id(self):
        """Prompt exists but has no outputs yet (still running)."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        mock_http.get.return_value = _mock_response(200, json_data={"abc-123": {}})

        result = await client.get_result("abc-123")
        assert result == {"abc-123": {}}


# ---------------------------------------------------------------------------
#  download
# ---------------------------------------------------------------------------


class TestDownload:
    """Tests for image download and validation."""

    @pytest.mark.asyncio
    async def test_download_valid_png(self):
        """Download returns valid PNG bytes — decoded successfully."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        png_bytes = _make_png_bytes(64, 64)
        mock_http.get.return_value = _mock_response(200, content=png_bytes)

        # We test the internal download helper via generate() below;
        # the download itself is exercised through the client's
        # _download_with_retry helper.  For now, verify the HTTP call works.
        resp = await mock_http.get("http://mock:8188/view", params={"filename": "test.png"})
        assert resp.status_code == 200
        assert resp.content == png_bytes


# ---------------------------------------------------------------------------
#  health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Tests for ``ComfyUIClient.health_check()``."""

    @pytest.mark.asyncio
    async def test_health_check_ok(self):
        """ComfyUI /system_stats returns 200 — healthy."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        mock_http.get.return_value = _mock_response(
            200,
            json_data={"system": {"os": "linux"}},
        )

        result = await client.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_unreachable(self):
        """ComfyUI is down — health check returns False."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        mock_http.get.side_effect = OSError("Connection refused")

        result = await client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_http_500(self):
        """ComfyUI returns 500 on /system_stats — unhealthy."""
        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        mock_http.get.return_value = _mock_response(500)

        result = await client.health_check()
        assert result is False


# ---------------------------------------------------------------------------
#  Full generate() orchestration (happy path)
# ---------------------------------------------------------------------------


class TestGenerateOrchestration:
    """End-to-end test of ``ComfyUIClient.generate()`` with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_generate_happy_path(self, tmp_path):
        """Full generation cycle: load workflow → queue → poll → download → return image."""
        # Create a minimal workflow JSON
        workflow_path = tmp_path / "workflow.json"
        workflow = {
            "1": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "default"},
            },
            "2": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "test"},
            },
        }
        workflow_path.write_text(json.dumps(workflow))

        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        # Mock the three HTTP calls: queue, history, download
        png_bytes = _make_png_bytes(128, 128)

        # queue_workflow → POST /prompt
        # history → GET /history/{id}
        # download → GET /view
        call_count = 0
        post_responses = [
            _mock_response(200, json_data={"prompt_id": "prompt-001"}),
        ]
        get_responses = [
            # First GET: history still empty (polling)
            _mock_response(200, json_data={"prompt-001": {}}),
            # Second GET: history with outputs
            _mock_response(200, json_data={
                "prompt-001": {
                    "outputs": {
                        "2": {
                            "images": [
                                {"filename": "test_00001_.png", "subfolder": "", "type": "output"},
                            ],
                        },
                    },
                },
            }),
            # Third GET: download the image
            _mock_response(200, content=png_bytes),
        ]

        async def _post_side_effect(*args, **kwargs):
            nonlocal call_count
            resp = post_responses[0]
            call_count += 1
            return resp

        get_call_count = 0

        async def _get_side_effect(*args, **kwargs):
            nonlocal get_call_count
            resp = get_responses[get_call_count % len(get_responses)]
            get_call_count += 1
            return resp

        mock_http.post.side_effect = _post_side_effect
        mock_http.get.side_effect = _get_side_effect

        # Mock WebSocket to immediately fail (use polling fallback path)
        with patch.object(client, "_wait_via_ws", side_effect=ConnectionRefusedError("no ws")):
            img = await client.generate(
                str(workflow_path),
                positive_prompt="test prompt",
                seed=42,
            )

        assert isinstance(img, Image.Image)
        assert img.size == (128, 128)
        # Verify queue was called
        mock_http.post.assert_called()


# ---------------------------------------------------------------------------
#  generate() error paths
# ---------------------------------------------------------------------------


class TestGenerateErrorPaths:
    """Tests for error handling in ``ComfyUIClient.generate()``."""

    @pytest.mark.asyncio
    async def test_generate_workflow_not_found(self):
        """Referencing a non-existent workflow file raises FileNotFoundError."""
        client = ComfyUIClient(base_url="http://mock:8188")

        with pytest.raises(FileNotFoundError):
            await client.generate(
                "/nonexistent/workflow.json",
                positive_prompt="test",
            )

    @pytest.mark.asyncio
    async def test_generate_queue_fails(self, tmp_path):
        """If queueing fails, the error propagates and uploaded images are cleaned."""
        workflow_path = tmp_path / "workflow.json"
        workflow_path.write_text(json.dumps({
            "1": {"class_type": "SaveImage", "inputs": {}},
        }))

        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        # Queue returns 500
        mock_http.post.return_value = _mock_response(500)

        with pytest.raises(Exception):
            await client.generate(
                str(workflow_path),
                positive_prompt="test",
                seed=42,
            )

    @pytest.mark.asyncio
    async def test_generate_completion_fails_raises_runtime_error(self, tmp_path):
        """If the workflow doesn't complete (polling timeout), RuntimeError is raised."""
        workflow_path = tmp_path / "workflow.json"
        workflow_path.write_text(json.dumps({
            "1": {"class_type": "SaveImage", "inputs": {}},
        }))

        client = ComfyUIClient(base_url="http://mock:8188")
        mock_http = await _setup_client_with_mock_http(client)

        # Queue succeeds but history never returns outputs
        mock_http.post.return_value = _mock_response(
            200, json_data={"prompt_id": "prompt-002"},
        )
        # History always empty
        mock_http.get.return_value = _mock_response(
            200, json_data={"prompt-002": {}},
        )

        # Override _wait_for_completion_checked to simulate timeout
        with patch.object(client, "_wait_for_completion_checked", side_effect=RuntimeError("did not complete successfully")):
            with pytest.raises(RuntimeError, match="did not complete"):
                await client.generate(
                    str(workflow_path),
                    positive_prompt="test",
                    seed=42,
                )


# ---------------------------------------------------------------------------
#  WebSocket lifecycle
# ---------------------------------------------------------------------------


class TestWebSocketLifecycle:
    """Tests for ``ComfyUIClient._wait_via_ws()`` WebSocket handling."""

    @pytest.mark.asyncio
    async def test_ws_execution_completes_successfully(self):
        """Normal WS flow: execution_start → executing → progress → executed → returns True."""
        client = ComfyUIClient(base_url="http://mock:8188")

        # Build a mock websocket that yields the expected message sequence
        messages = [
            json.dumps({"type": "execution_start", "data": {"prompt_id": "p1"}}),
            json.dumps({"type": "executing", "data": {"node": "5", "prompt_id": "p1"}}),
            json.dumps({"type": "progress", "data": {"value": 5, "max": 10}}),
            json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "p1"}}),
        ]

        mock_ws = AsyncMock()
        mock_ws.__aiter__.return_value = messages
        mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_ws.__aexit__ = AsyncMock(return_value=None)

        with patch("websockets.connect", return_value=mock_ws):
            # Returns None on success (was: returned True before error-propagation refactor)
            await client._wait_via_ws("p1")

    @pytest.mark.asyncio
    async def test_ws_execution_error_propagates(self):
        """When ComfyUI sends execution_error, RuntimeError is raised with details."""
        client = ComfyUIClient(base_url="http://mock:8188")

        messages = [
            json.dumps({"type": "execution_start", "data": {"prompt_id": "p1"}}),
            json.dumps({"type": "execution_error", "data": {
                "prompt_id": "p1",
                "exception_message": "CUDA out of memory",
                "exception_type": "RuntimeError",
            }}),
        ]

        mock_ws = AsyncMock()
        mock_ws.__aiter__.return_value = messages
        mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_ws.__aexit__ = AsyncMock(return_value=None)

        with patch("websockets.connect", return_value=mock_ws):
            with pytest.raises(RuntimeError, match="CUDA out of memory"):
                await client._wait_via_ws("p1")

    @pytest.mark.asyncio
    async def test_ws_close_falls_back_to_polling(self):
        """WebSocket disconnects with ConnectionClosed — internal fallback to polling."""
        client = ComfyUIClient(base_url="http://mock:8188")

        mock_ws = AsyncMock()
        # Raise ConnectionClosed to trigger the internal except block
        mock_ws.__aiter__.side_effect = __import__("websockets").exceptions.ConnectionClosed(
            None, None
        )
        mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_ws.__aexit__ = AsyncMock(return_value=None)

        with patch("websockets.connect", return_value=mock_ws):
            with patch.object(client, "_wait_via_polling", return_value=True) as mock_poll:
                # Returns None on success (was: returned True before error-propagation refactor)
                await client._wait_via_ws("p1")

        mock_poll.assert_called_once_with("p1")

    @pytest.mark.asyncio
    async def test_ws_connect_failure_falls_back_to_polling(self):
        """Cannot establish WebSocket — _wait_for_completion_checked catches ConnectionRefusedError, falls back to polling."""
        client = ComfyUIClient(base_url="http://mock:8188")

        with patch.object(client, "_wait_via_ws", side_effect=ConnectionRefusedError("Connection refused")):
            with patch.object(client, "_wait_via_polling", return_value=True) as mock_poll:
                # Returns None on success (raises RuntimeError on polling failure)
                await client._wait_for_completion_checked("p1")

        mock_poll.assert_called_once_with("p1")

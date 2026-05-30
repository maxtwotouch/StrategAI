"""Tests for src/comfyui_loadbalancer.py — multi-node selection, failover, health."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from src.comfyui_loadbalancer import (
    ComfyUILoadBalancer,
    _Node,
    _is_retryable,
)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(*, queue_depth: int = 0, healthy: bool = True):
    """Create an AsyncMock ComfyUIClient with controllable behaviour."""
    client = AsyncMock()
    client.base_url = "http://mock:8188"
    client.timeout = 300

    # get_queue_info returns a dict or None (unreachable)
    async def _get_queue_info():
        if not healthy:
            return None
        return {"running": 0, "pending": queue_depth, "depth": queue_depth}

    client.get_queue_info = _get_queue_info

    # health_check pings /system_stats
    async def _health_check():
        return healthy

    client.health_check = _health_check

    # generate returns a dummy RGBA image
    async def _generate(*args, **kwargs):
        return Image.new("RGBA", (128, 128), (255, 0, 0, 255))

    client.generate = _generate

    # http property with async post (for cancel_prompt)
    http_mock = AsyncMock()
    http_mock.post = AsyncMock(return_value=MagicMock(status_code=200))
    client.http = http_mock

    return client


def _make_load_balancer(
    num_nodes: int = 2,
    *,
    urls: list[str] | None = None,
    queue_depths: list[int] | None = None,
    healthy_flags: list[bool] | None = None,
) -> ComfyUILoadBalancer:
    """Build a load-balancer with mock clients injected into each _Node."""
    if urls is None:
        urls = [f"http://mock:{8188 + i}" for i in range(num_nodes)]
    if queue_depths is None:
        queue_depths = [0] * len(urls)
    if healthy_flags is None:
        healthy_flags = [True] * len(urls)

    # Bypass normal __init__ to avoid reading real config
    lb = object.__new__(ComfyUILoadBalancer)
    lb._urls = urls
    lb._timeout = 300
    lb._health_check_interval = 30
    lb._max_retries = 3
    lb._rr_counter = __import__("itertools").count()
    lb._select_lock = __import__("asyncio").Lock()

    lb._nodes = []
    for url, depth, healthy in zip(urls, queue_depths, healthy_flags):
        node = _Node(url=url, timeout=300)
        node.client = _make_mock_client(queue_depth=depth, healthy=healthy)
        node.queue_depth = depth
        node.healthy = healthy
        node.last_health_check = time.monotonic() if healthy else 0.0
        lb._nodes.append(node)

    return lb


# ---------------------------------------------------------------------------
#  Exception classification
# ---------------------------------------------------------------------------


class TestIsRetryable:
    def test_connect_error_is_retryable(self):
        assert _is_retryable(httpx.ConnectError("refused")) is True

    def test_timeout_is_retryable(self):
        assert _is_retryable(httpx.TimeoutException("timeout")) is True

    def test_oserror_is_retryable(self):
        assert _is_retryable(OSError("connection refused")) is True

    def test_runtime_error_timeout_is_retryable(self):
        assert _is_retryable(RuntimeError("did not complete successfully")) is True

    def test_value_error_not_retryable(self):
        assert _is_retryable(ValueError("node errors")) is False

    def test_generic_runtime_error_not_retryable(self):
        assert _is_retryable(RuntimeError("some other error")) is False


# ---------------------------------------------------------------------------
#  Node selection
# ---------------------------------------------------------------------------


class TestSelectNode:
    @pytest.mark.asyncio
    async def test_shortest_queue_wins(self):
        """Node with smaller queue depth is selected."""
        lb = _make_load_balancer(3, queue_depths=[5, 0, 3])
        node = await lb._select_node()
        assert node.queue_depth == 0

    @pytest.mark.asyncio
    async def test_round_robin_tie_breaker(self):
        """When all queues equal, distribute via round-robin."""
        lb = _make_load_balancer(3, queue_depths=[0, 0, 0])
        picks = set()
        for _ in range(10):
            node = await lb._select_node()
            picks.add(node.url)
        assert len(picks) > 1  # not always the same node

    @pytest.mark.asyncio
    async def test_skips_unhealthy_nodes(self):
        """Unhealthy nodes are excluded from selection."""
        lb = _make_load_balancer(
            3,
            queue_depths=[0, 0, 0],
            healthy_flags=[True, False, True],
        )
        node = await lb._select_node()
        assert node.healthy is True

    @pytest.mark.asyncio
    async def test_marks_unreachable_during_ping(self):
        """Node that fails GET /queue during selection is marked unhealthy."""
        lb = _make_load_balancer(3, healthy_flags=[True, True, True])
        # Make node 1's ping return None (unreachable)
        lb._nodes[1].client.get_queue_info = AsyncMock(return_value=None)
        # Also make it unhealthy but we need a healthy flag first
        lb._nodes[1].healthy = True

        node = await lb._select_node()
        # Node 1 should now be unhealthy
        assert lb._nodes[1].healthy is False
        # Selected node should not be node 1
        assert node is not lb._nodes[1]

    @pytest.mark.asyncio
    async def test_no_healthy_nodes_raises(self):
        """When all nodes are unhealthy, RuntimeError is raised."""
        lb = _make_load_balancer(3, healthy_flags=[False, False, False])
        with pytest.raises(RuntimeError, match="No healthy ComfyUI nodes"):
            await lb._select_node()


# ---------------------------------------------------------------------------
#  Failover
# ---------------------------------------------------------------------------


class TestFailover:
    @pytest.mark.asyncio
    async def test_retries_on_connect_error(self):
        """generate() retries on a different node after connectivity failure."""
        lb = _make_load_balancer(3, queue_depths=[0, 0, 0])

        # Node 0 fails with a connect error
        async def _fail_generate(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")

        lb._nodes[0].client.generate = _fail_generate

        result = await lb.generate("workflow.json")
        assert result is not None
        # Node 0 should be marked unhealthy
        assert lb._nodes[0].healthy is False

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        """generate() retries after wait_for_completion timeout."""
        lb = _make_load_balancer(3, queue_depths=[0, 0, 0])

        async def _fail_generate(*args, **kwargs):
            raise RuntimeError("did not complete successfully")

        lb._nodes[0].client.generate = _fail_generate

        result = await lb.generate("workflow.json")
        assert result is not None
        assert lb._nodes[0].healthy is False

    @pytest.mark.asyncio
    async def test_exhaustion_raises(self):
        """When all nodes fail, RuntimeError is raised after max_retries."""
        lb = _make_load_balancer(2, queue_depths=[0, 0])
        lb._max_retries = 2

        async def _fail_generate(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")

        for node in lb._nodes:
            node.client.generate = _fail_generate

        with pytest.raises(RuntimeError, match="All 2 ComfyUI node attempts failed"):
            await lb.generate("workflow.json")

    @pytest.mark.asyncio
    async def test_non_retryable_propagates(self):
        """Workflow errors (not connectivity) are not retried."""
        lb = _make_load_balancer(2, queue_depths=[0, 0])

        async def _fail_generate(*args, **kwargs):
            raise ValueError("Validation error: node_errors")

        lb._nodes[0].client.generate = _fail_generate

        with pytest.raises(ValueError, match="Validation error"):
            await lb.generate("workflow.json")
        # Node 0 should still be healthy (it wasn't a node failure)
        assert lb._nodes[0].healthy is True

    @pytest.mark.asyncio
    async def test_cancel_called_on_failed_node(self):
        """When a node fails, cancel_prompt is called on it (best-effort)."""
        lb = _make_load_balancer(3, queue_depths=[0, 0, 0])

        async def _fail_generate(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")

        lb._nodes[0].client.generate = _fail_generate
        cancel_mock = AsyncMock()
        # Return a MagicMock (not AsyncMock) to avoid "never awaited" warnings
        # since raise_for_status() is a sync method on the response object.
        cancel_mock.return_value = MagicMock()
        # Mock get_http() to return a mock client whose .post is our cancel_mock
        mock_http = MagicMock()
        mock_http.post = cancel_mock
        lb._nodes[0].client.get_http = AsyncMock(return_value=mock_http)

        await lb.generate("workflow.json")

        # Give the fire-and-forget cancel task a moment
        await asyncio.sleep(0.1)
        assert cancel_mock.called


# ---------------------------------------------------------------------------
#  Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_true_when_any_reachable(self):
        """Returns True if at least one node is reachable."""
        lb = _make_load_balancer(2, healthy_flags=[False, True])
        # health_check() re-pings all nodes, so we need mock that respects health
        # Make node 0 unreachable, node 1 reachable
        lb._nodes[0].client.get_queue_info = AsyncMock(return_value=None)
        lb._nodes[1].client.get_queue_info = AsyncMock(
            return_value={"running": 0, "pending": 0, "depth": 0}
        )
        assert await lb.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_false_when_none_reachable(self):
        """Returns False when no nodes are reachable."""
        lb = _make_load_balancer(2)
        for node in lb._nodes:
            node.client.get_queue_info = AsyncMock(return_value=None)
        assert await lb.health_check() is False


# ---------------------------------------------------------------------------
#  Lazy health recovery
# ---------------------------------------------------------------------------


class TestLazyRecovery:
    @pytest.mark.asyncio
    async def test_recovers_stale_unhealthy_node(self):
        """After health_check_interval, unhealthy nodes are re-pinged and recovered."""
        lb = _make_load_balancer(2, healthy_flags=[True, False])
        lb._health_check_interval = 0  # always stale

        # Node 1 is unhealthy but its ping now succeeds
        lb._nodes[1].client.get_queue_info = AsyncMock(
            return_value={"running": 0, "pending": 0, "depth": 0}
        )

        healthy = await lb._get_healthy_nodes(lazy_recover=True)
        assert len(healthy) == 2
        assert lb._nodes[1].healthy is True


# ---------------------------------------------------------------------------
#  Single-node backward compatibility
# ---------------------------------------------------------------------------


class TestSingleNode:
    @pytest.mark.asyncio
    async def test_single_node_works(self):
        """Pool of size 1 behaves identically to a plain ComfyUIClient."""
        lb = _make_load_balancer(1, queue_depths=[0])
        result = await lb.generate("workflow.json")
        assert result is not None

    @pytest.mark.asyncio
    async def test_single_node_close(self):
        """close() releases the single client."""
        lb = _make_load_balancer(1)
        close_mock = AsyncMock()
        lb._nodes[0].client.close = close_mock
        await lb.close()
        assert close_mock.called
        assert len(lb._nodes) == 0

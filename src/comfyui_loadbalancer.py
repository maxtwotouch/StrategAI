"""Load-balancing proxy across multiple ComfyUI server nodes.

Wraps a pool of :class:`ComfyUIClient` instances (one per node) and exposes
the same ``generate()`` API.  Node selection uses shortest-queue (pending +
running) with round-robin tie-breaking.  If a node fails mid-generation the
work is transparently retried on a different node.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import time
from typing import Any

import httpx
import websockets.exceptions

from PIL import Image

from src.comfyui_client import ComfyUIClient
from src.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Exception classification
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
    OSError,  # covers ConnectionRefusedError, etc.
)


def _is_retryable(exc: BaseException) -> bool:
    """Return ``True`` if the exception suggests a node connectivity issue."""
    if isinstance(exc, _RETRYABLE_EXCEPTIONS):
        return True
    # RuntimeError("...did not complete successfully") → timeout / dead node
    if isinstance(exc, RuntimeError) and "did not complete successfully" in str(exc):
        return True
    return False


# ---------------------------------------------------------------------------
#  Internal node wrapper
# ---------------------------------------------------------------------------

class _Node:
    """Thin wrapper around a single :class:`ComfyUIClient` + health metadata."""

    __slots__ = ("url", "client", "healthy", "last_health_check", "queue_depth")

    def __init__(self, url: str, timeout: int) -> None:
        self.url = url
        self.client = ComfyUIClient(base_url=url, timeout=timeout)
        self.healthy: bool = True
        self.last_health_check: float = 0.0
        self.queue_depth: int = 0

    async def ping(self) -> int | None:
        """Ping ``GET /queue``; return queue depth or ``None`` if down."""
        info = await self.client.get_queue_info()
        if info is None:
            return None
        self.queue_depth = info["depth"]
        self.last_health_check = time.monotonic()
        return self.queue_depth

    async def close(self) -> None:
        await self.client.close()


# ---------------------------------------------------------------------------
#  Load-balancer
# ---------------------------------------------------------------------------

class ComfyUILoadBalancer:
    """Duck-types :class:`ComfyUIClient` across a pool of server nodes.

    Selection: shortest ComfyUI queue (pending + running).
    Tie-breaker: round-robin counter when all queues equal.
    Failover: transparent retry on next-best node for connectivity failures.
    """

    def __init__(
        self,
        urls: list[str] | None = None,
        timeout: int | None = None,
        health_check_interval: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        cfg = settings.comfyui
        self._urls = urls or cfg.get_urls()
        self._timeout = timeout or cfg.timeout
        self._health_check_interval = health_check_interval or cfg.health_check_interval
        self._max_retries = max_retries or cfg.max_retries

        self._nodes = [_Node(url, self._timeout) for url in self._urls]
        self._rr_counter = itertools.count()
        self._select_lock = asyncio.Lock()

        if len(self._nodes) == 1:
            logger.info("ComfyUI load-balancer: single-node mode (%s)", self._urls[0])
        else:
            logger.info(
                "ComfyUI load-balancer: %d nodes, max_retries=%d",
                len(self._nodes),
                self._max_retries,
            )

    # ------------------------------------------------------------------
    #  Public API (duck-typing ComfyUIClient)
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
        """Generate an image, transparently retrying on node failure.

        Raises ``RuntimeError`` if all nodes are unhealthy or all retries
        are exhausted.
        """
        errors: list[str] = []

        for attempt in range(self._max_retries):
            node = await self._select_node()

            try:
                return await node.client.generate(
                    workflow_path,
                    positive_prompt=positive_prompt,
                    seed=seed,
                    width=width,
                    height=height,
                    input_images=input_images,
                    extra_overrides=extra_overrides,
                    ref_image_filename=ref_image_filename,
                )
            except Exception as exc:
                if not _is_retryable(exc):
                    raise  # workflow error, not node failure — don't retry

                node.healthy = False
                msg = (
                    f"ComfyUI node {node.url} failed (attempt {attempt + 1}/"
                    f"{self._max_retries}): {exc}"
                )
                logger.warning(msg)
                errors.append(msg)

                # Best-effort cancel any submitted prompt on the dead node.
                # We don't have the prompt_id here, so we can't cancel a
                # specific job.  This is acceptable — if the node is truly
                # dead the cancel POST also fails, and if it recovers the
                # stale job will complete harmlessly (or timeout).
                # Fire-and-forget, don't block the retry.
                task = asyncio.create_task(self._cancel_all_on_node(node))
                task.add_done_callback(
                    lambda t: logger.warning(
                        "Cancel-on-failure task failed: %s", t.exception()
                    ) if t.exception() else None
                )

        raise RuntimeError(
            f"All {self._max_retries} ComfyUI node attempts failed:\n"
            + "\n".join(errors)
        )

    async def health_check(self) -> bool:
        """Return ``True`` if at least one node is reachable.

        Pings every node to get an authoritative answer — does not rely
        on cached health state.
        """
        results = await asyncio.gather(
            *(node.ping() for node in self._nodes),
            return_exceptions=True,
        )
        any_healthy = False
        for node, result in zip(self._nodes, results):
            if isinstance(result, int) and result >= 0:
                node.healthy = True
                any_healthy = True
            else:
                node.healthy = False
        return any_healthy

    async def close(self) -> None:
        """Release all underlying HTTP clients."""
        for node in self._nodes:
            await node.close()
        self._nodes.clear()

    # ------------------------------------------------------------------
    #  Node selection
    # ------------------------------------------------------------------

    async def _select_node(self) -> _Node:
        """Pick the healthiest, least-loaded node.

        Strategy:
        1. Filter to healthy nodes (lazy-recover unhealthy ones).
        2. Ping ``GET /queue`` on all candidates in parallel.
        3. Return the node with the smallest ``running + pending``.
        4. Tie-break with round-robin counter to avoid thundering-herd.

        Thread-safe via ``_select_lock`` to prevent concurrent selection
        from corrupting health state or round-robin counter.
        """
        async with self._select_lock:
            return await self._select_node_impl()

    async def _select_node_impl(self) -> _Node:
        """Internal node selection logic (called under lock)."""
        candidates = await self._get_healthy_nodes(lazy_recover=True)

        if not candidates:
            # Eager recheck of *all* nodes before giving up
            await self._ping_all_nodes()
            candidates = [n for n in self._nodes if n.healthy]
            if not candidates:
                raise RuntimeError(
                    "No healthy ComfyUI nodes available "
                    f"(checked {len(self._nodes)} nodes)"
                )

        # Parallel queue-depth fetch
        results = await asyncio.gather(
            *(node.ping() for node in candidates),
            return_exceptions=True,
        )

        # Mark nodes that failed the ping as unhealthy
        for node, result in zip(candidates, results):
            if isinstance(result, BaseException) or result is None:
                node.healthy = False
                logger.warning("ComfyUI node %s unreachable during selection", node.url)

        # Re-filter after pings
        reachable = [n for n in candidates if n.healthy]
        if not reachable:
            raise RuntimeError(
                "All healthy-seeming ComfyUI nodes failed queue ping "
                f"({len(candidates)} candidates)"
            )

        # All reachable nodes have the same queue depth → round-robin
        depths = {n.queue_depth for n in reachable}
        if len(depths) == 1:
            idx = next(self._rr_counter) % len(reachable)
            return reachable[idx]

        # Pick the least-loaded node
        return min(reachable, key=lambda n: n.queue_depth)

    # ------------------------------------------------------------------
    #  Health management
    # ------------------------------------------------------------------

    async def _get_healthy_nodes(
        self, *, lazy_recover: bool = False
    ) -> list[_Node]:
        """Return currently-healthy nodes, optionally re-pinging stale ones."""
        now = time.monotonic()

        if lazy_recover:
            # Re-ping unhealthy nodes whose last check exceeds the interval
            stale = [
                n
                for n in self._nodes
                if not n.healthy
                and (now - n.last_health_check) > self._health_check_interval
            ]
            if stale:
                results = await asyncio.gather(
                    *(n.ping() for n in stale),
                    return_exceptions=True,
                )
                for node, result in zip(stale, results):
                    if isinstance(result, int) and result >= 0:
                        node.healthy = True
                        logger.info(
                            "ComfyUI node %s recovered (queue depth=%d)",
                            node.url,
                            result,
                        )

        return [n for n in self._nodes if n.healthy]

    async def _ping_all_nodes(self) -> None:
        """Eagerly re-ping every node (used when no healthy nodes remain)."""
        results = await asyncio.gather(
            *(node.ping() for node in self._nodes),
            return_exceptions=True,
        )
        for node, result in zip(self._nodes, results):
            if isinstance(result, int) and result >= 0:
                node.healthy = True
                logger.info("ComfyUI node %s recovered (eager)", node.url)
            else:
                node.healthy = False
                node.last_health_check = time.monotonic()

    @staticmethod
    async def _cancel_all_on_node(node: _Node) -> None:
        """Best-effort: cancel everything in a node's queue.

        Fire-and-forget — if the node is dead this also fails silently.
        """
        try:
            http = await node.client.get_http()
            resp = await http.post(
                "/queue",
                json={"delete": []},  # empty list = clear all
                timeout=5,
            )
            resp.raise_for_status()
            logger.debug("Cancelled all queued prompts on %s", node.url)
        except Exception:
            logger.debug(
                "Could not cancel prompts on %s (node likely unreachable)",
                node.url,
            )

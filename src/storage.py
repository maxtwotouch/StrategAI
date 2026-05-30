import os
import io
import tempfile
import threading
from PIL import Image
from src.config import settings, BASE_DIR
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)


def _safe_filename(filename: str) -> str:
    """Strip directory components to prevent path traversal attacks."""
    return os.path.basename(filename)


def _atomic_write(path: str, data: bytes) -> None:
    """Write data to *path* atomically via a temp-file + rename.

    This prevents corrupted files if the process crashes mid-write, and
    avoids partial reads by concurrent consumers.
    """
    dirname = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dirname, suffix=".png")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp_path, 0o644)
        os.rename(tmp_path, path)
    except Exception:
        # Best-effort cleanup of the temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class AssetStore:
    def __init__(self, max_cache_size: int | None = None, max_cache_bytes: int | None = None):
        self._memory_cache: OrderedDict[str, bytes] = OrderedDict()
        self.max_cache_size = max_cache_size if max_cache_size is not None else settings.server.cache_max_entries
        self.max_cache_bytes = max_cache_bytes if max_cache_bytes is not None else (settings.server.cache_max_mb * 1024 * 1024)
        self._cache_bytes: int = 0
        self._lock = threading.Lock()
        self._output_dir = os.path.join(BASE_DIR, settings.paths.output_dir)

    def _evict_if_needed(self) -> None:
        """Evict oldest entries until both limits are satisfied."""
        while self._memory_cache and (
            len(self._memory_cache) > self.max_cache_size
            or self._cache_bytes > self.max_cache_bytes
        ):
            _, evicted = self._memory_cache.popitem(last=False)
            self._cache_bytes -= len(evicted)

    def save_image(self, filename: str, img: Image.Image):
        """Saves the image to both the in-memory cache and local disk.

        Uses atomic writes (temp file + rename) to avoid corrupted files
        on crash.  Sets explicit permissions (0o644).
        """
        filename = _safe_filename(filename)
        path = os.path.join(self._output_dir, filename)

        # Serialize once
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()

        # Atomic disk write
        try:
            _atomic_write(path, data)
        except OSError as exc:
            logger.error("Failed to write image to disk at %s: %s", path, exc)
            raise RuntimeError(f"Failed to persist asset to disk: {exc}") from exc

        # Memory cache
        with self._lock:
            self._memory_cache[filename] = data
            self._memory_cache.move_to_end(filename)
            self._cache_bytes += len(data)
            self._evict_if_needed()

        logger.info("Saved %s to memory cache and disk.", filename)

    def get_image_bytes(self, filename: str) -> bytes | None:
        """Retrieves image bytes, preferring memory cache then falling back to disk."""
        filename = _safe_filename(filename)
        with self._lock:
            if filename in self._memory_cache:
                self._memory_cache.move_to_end(filename)
                return self._memory_cache[filename]

        path = os.path.join(self._output_dir, filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read()
            with self._lock:
                self._memory_cache[filename] = data
                self._memory_cache.move_to_end(filename)
                self._cache_bytes += len(data)
                self._evict_if_needed()

            logger.info("Loaded %s from disk into memory cache.", filename)
            return data

        return None

    def get_image_pil(self, filename: str) -> Image.Image:
        """Helper to get a PIL Image for Copy-on-Write operations."""
        data = self.get_image_bytes(filename)
        if data:
            return Image.open(io.BytesIO(data)).convert("RGBA")
        raise FileNotFoundError(f"Asset {filename} not found.")

    def save_from_path(self, filename: str, src_path: str) -> None:
        """Convenience: open a PNG from disk and save it through the store."""
        img = Image.open(src_path).convert("RGBA")
        self.save_image(filename, img)

    def delete(self, filename: str) -> bool:
        """Remove an image from disk and the in-memory cache.

        Returns True if the file existed on disk and was removed.
        Returns False if the file was only in cache (or not found at all).
        Never raises — missing files are silently ignored.
        """
        filename = _safe_filename(filename)
        path = os.path.join(self._output_dir, filename)
        existed = False

        # Disk cleanup
        try:
            if os.path.exists(path):
                os.unlink(path)
                existed = True
                logger.info("Deleted asset from disk: %s", filename)
        except OSError as exc:
            logger.warning("Failed to delete asset from disk %s: %s", filename, exc)

        # Memory cache cleanup
        with self._lock:
            if filename in self._memory_cache:
                self._cache_bytes -= len(self._memory_cache[filename])
                del self._memory_cache[filename]

        return existed


def try_remove_asset(filename: str) -> None:
    """Best-effort deletion of an orphaned asset file after a DB failure.

    Delegates to ``store.delete()`` so both the on-disk file AND the
    in-memory LRU cache entry are cleaned up (avoids stale cache entries).
    All engine callers should import and use this shared helper.
    """
    try:
        store.delete(filename)
        logger.warning("Cleaned up orphaned asset: %s", filename)
    except Exception as exc:
        logger.error("Failed to clean up orphaned asset %s: %s", filename, exc)


# Global instance
store = AssetStore()

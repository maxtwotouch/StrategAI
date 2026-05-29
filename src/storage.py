import os
import io
import threading
from PIL import Image
from src.config import settings, BASE_DIR
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)


def _safe_filename(filename: str) -> str:
    """Strip directory components to prevent path traversal attacks."""
    return os.path.basename(filename)


class AssetStore:
    def __init__(self, max_cache_size: int | None = None):
        self._memory_cache = OrderedDict()
        self.max_cache_size = max_cache_size if max_cache_size is not None else settings.server.cache_max_entries
        self._lock = threading.Lock()
        self._output_dir = os.path.join(BASE_DIR, settings.paths.output_dir)

    def save_image(self, filename: str, img: Image.Image):
        """Saves the image to both the in-memory cache and local disk."""
        filename = _safe_filename(filename)
        # Save to disk
        path = os.path.join(self._output_dir, filename)
        try:
            img.save(path, format="PNG")
        except OSError as exc:
            logger.error("Failed to write image to disk at %s: %s", path, exc)
            raise RuntimeError(f"Failed to persist asset to disk: {exc}") from exc

        # Save to memory
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        with self._lock:
            self._memory_cache[filename] = buf.getvalue()
            self._memory_cache.move_to_end(filename)

            # Enforce LRU cap
            if len(self._memory_cache) > self.max_cache_size:
                self._memory_cache.popitem(last=False)

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

                # Enforce LRU cap
                if len(self._memory_cache) > self.max_cache_size:
                    self._memory_cache.popitem(last=False)

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

# Global instance
store = AssetStore()

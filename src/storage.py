import os
import io
from PIL import Image
from .config import settings
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)

class AssetStore:
    def __init__(self, max_cache_size=1000):
        self._memory_cache = OrderedDict()
        self.max_cache_size = max_cache_size

    def save_image(self, filename: str, img: Image.Image):
        """Saves the image to both the in-memory cache and local disk."""
        # Save to disk
        path = os.path.join(settings.output_dir, filename)
        img.save(path, format="PNG")

        # Save to memory
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self._memory_cache[filename] = buf.getvalue()
        self._memory_cache.move_to_end(filename)

        # Enforce LRU cap
        if len(self._memory_cache) > self.max_cache_size:
            self._memory_cache.popitem(last=False)

        logger.info(f"Saved {filename} to memory cache and disk.")

    def get_image_bytes(self, filename: str) -> bytes | None:
        """Retrieves image bytes, preferring memory cache then falling back to disk."""
        if filename in self._memory_cache:
            self._memory_cache.move_to_end(filename)
            return self._memory_cache[filename]

        path = os.path.join(settings.output_dir, filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read()
            self._memory_cache[filename] = data
            self._memory_cache.move_to_end(filename)

            # Enforce LRU cap
            if len(self._memory_cache) > self.max_cache_size:
                self._memory_cache.popitem(last=False)

            logger.info(f"Loaded {filename} from disk into memory cache.")
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

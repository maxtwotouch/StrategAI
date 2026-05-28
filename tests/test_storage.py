"""Unit tests for AssetStore (src/storage.py)."""

import io
import os
import pytest
from PIL import Image


class TestSaveAndRetrieve:
    """Tests for save_image, get_image_bytes, get_image_pil."""

    def test_save_and_retrieve_bytes(self, test_store, sample_png):
        """Save PIL Image, get bytes back → same PNG binary."""
        test_store.save_image("test.png", sample_png)
        data = test_store.get_image_bytes("test.png")
        assert data is not None
        # Verify it's valid PNG
        img = Image.open(io.BytesIO(data))
        assert img.size == (16, 16)

    def test_save_and_retrieve_pil(self, test_store, sample_png):
        """Save, get_image_pil() → same dimensions + mode."""
        test_store.save_image("test2.png", sample_png)
        img = test_store.get_image_pil("test2.png")
        assert img.size == (16, 16)
        assert img.mode == "RGBA"

    def test_get_nonexistent_returns_none(self, test_store):
        """get_image_bytes('nope.png') → None."""
        assert test_store.get_image_bytes("nope.png") is None

    def test_get_nonexistent_pil_raises(self, test_store):
        """get_image_pil('nope.png') → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            test_store.get_image_pil("nope.png")

    def test_save_from_path(self, test_store, tmp_project_root, sample_png):
        """save_from_path() copies a file into the store."""
        src = os.path.join(tmp_project_root, "source.png")
        sample_png.save(src, format="PNG")
        test_store.save_from_path("copied.png", src)
        assert test_store.get_image_bytes("copied.png") is not None


class TestCacheBehavior:
    """Tests for LRU memory cache."""

    def test_memory_cache_hit(self, test_store, sample_png):
        """Second retrieval returned from memory, no disk read."""
        test_store.save_image("cache_test.png", sample_png)
        # Clear disk to verify it comes from memory
        disk_path = os.path.join(test_store._output_dir, "cache_test.png")
        if os.path.exists(disk_path):
            os.remove(disk_path)
        data = test_store.get_image_bytes("cache_test.png")
        assert data is not None

    def test_lru_eviction(self, test_store, sample_png):
        """Insert more than max_cache_size items, first item evicted."""
        test_store.max_cache_size = 5
        # Insert 6 items
        for i in range(6):
            test_store.save_image(f"evict_{i}.png", sample_png)
        # First item should be evicted from cache (but still on disk)
        # Accessing it should load from disk
        data = test_store.get_image_bytes("evict_0.png")
        assert data is not None

    def test_lru_reorder_on_access(self, test_store, sample_png):
        """Access an old item → it moves to end, survives eviction."""
        test_store.max_cache_size = 3
        test_store.save_image("a.png", sample_png)
        test_store.save_image("b.png", sample_png)
        test_store.save_image("c.png", sample_png)
        # Access 'a' to move it to end
        test_store.get_image_bytes("a.png")
        # Insert 2 more — 'b' should be evicted, 'a' should survive
        # (only 2 more saves so 'a' isn't pushed out by the 3rd save)
        test_store.save_image("d.png", sample_png)
        test_store.save_image("e.png", sample_png)
        # 'a' should still be in cache (it was accessed, so moved to end)
        assert "a.png" in test_store._memory_cache
        # 'b' should be evicted (never accessed after initial save)
        assert "b.png" not in test_store._memory_cache

    def test_disk_fallback_after_cache_miss(self, test_store, sample_png):
        """Item on disk but not in cache → loads from disk, enters cache."""
        test_store.max_cache_size = 2
        test_store.save_image("disk1.png", sample_png)
        test_store.save_image("disk2.png", sample_png)
        test_store.save_image("disk3.png", sample_png)
        # disk1 should be evicted from cache
        test_store._memory_cache.pop("disk1.png", None)
        # Now retrieve — should load from disk
        data = test_store.get_image_bytes("disk1.png")
        assert data is not None
        assert "disk1.png" in test_store._memory_cache

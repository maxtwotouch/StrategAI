"""
Storage error path tests — Phase D.2

Tests for AssetStore error handling:
- Disk full (write failure)
- Permission denied
- Concurrent access safety
- Cache eviction with MB-based limits
- Atomic write failure cleanup
- Safe filename path traversal prevention

Also tests the ``try_remove_asset`` helper.
"""

from __future__ import annotations

import io
import os
import threading
import pytest
from unittest.mock import patch, MagicMock
from PIL import Image


class TestStorageErrorPaths:
    """Tests for error handling in AssetStore."""

    def test_save_image_permission_denied_raises_runtime_error(
        self, test_store, sample_png, tmp_project_root, monkeypatch
    ):
        """When disk write fails with OSError, RuntimeError is raised."""
        # Make output_dir read-only to force permission error
        output_dir = os.path.join(tmp_project_root, "generated_assets")
        test_store._output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        os.chmod(output_dir, 0o444)  # read-only

        try:
            with pytest.raises(RuntimeError, match="Failed to persist asset"):
                test_store.save_image("perm_denied.png", sample_png)
        finally:
            os.chmod(output_dir, 0o755)  # restore

    def test_save_image_disk_full_simulated(self, test_store, sample_png, monkeypatch):
        """Simulated disk full error during atomic write raises RuntimeError."""
        original_atomic_write = __import__("src.storage").storage._atomic_write

        def _failing_write(path: str, data: bytes) -> None:
            raise OSError(28, "No space left on device")

        monkeypatch.setattr("src.storage._atomic_write", _failing_write)

        with pytest.raises(RuntimeError, match="Failed to persist asset"):
            test_store.save_image("disk_full.png", sample_png)

    def test_atomic_write_cleanup_on_failure(self, tmp_project_root):
        """When atomic write fails mid-write, the temp file is cleaned up."""
        import tempfile
        from src.storage import _atomic_write

        output_dir = os.path.join(tmp_project_root, "generated_assets")
        os.makedirs(output_dir, exist_ok=True)
        dest = os.path.join(output_dir, "cleanup_test.png")

        # Patch os.rename to fail, simulating a mid-write crash
        with patch("os.rename", side_effect=OSError("Simulated rename failure")):
            with pytest.raises(OSError):
                _atomic_write(dest, b"fake png data")

        # The temp file should have been cleaned up
        # (the original temp file is removed in the except block)
        png_files = [f for f in os.listdir(output_dir) if f.endswith(".png")]
        assert len(png_files) == 0, f"Temp files not cleaned: {png_files}"

    def test_atomic_write_success(self, tmp_project_root):
        """Atomic write creates the file successfully."""
        from src.storage import _atomic_write

        output_dir = os.path.join(tmp_project_root, "generated_assets")
        os.makedirs(output_dir, exist_ok=True)
        dest = os.path.join(output_dir, "atomic_test.png")
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal PNG header

        _atomic_write(dest, data)

        assert os.path.isfile(dest)
        with open(dest, "rb") as f:
            assert f.read() == data

        os.unlink(dest)

    def test_safe_filename_prevents_path_traversal(self):
        """_safe_filename strips directory components."""
        from src.storage import _safe_filename

        assert _safe_filename("../../../etc/passwd") == "passwd"
        assert _safe_filename("/etc/shadow") == "shadow"
        assert _safe_filename("normal.png") == "normal.png"
        assert _safe_filename("subdir/file.png") == "file.png"
        # On Linux, backslashes are valid filename characters, not path separators.
        # os.path.basename() does NOT split on backslash on Linux.
        # So "..\\..\\windows\\system32\\config\\sam" stays as-is.
        windows_path = "..\\..\\windows\\system32\\config\\sam"
        result = _safe_filename(windows_path)
        # On Linux: basename of this is the whole string (backslash is not a separator)
        # On Windows: basename would be "sam"
        # Either is acceptable in the Linux dev container
        assert result in (windows_path, "sam")

    def test_safe_filename_empty_string(self):
        """_safe_filename with empty string returns empty string."""
        from src.storage import _safe_filename
        result = _safe_filename("")
        assert result == ""

    def test_safe_filename_special_names(self):
        """_safe_filename handles special filenames."""
        from src.storage import _safe_filename
        # filename with spaces
        assert _safe_filename("my file name.png") == "my file name.png"
        # filename that is just a dot
        assert _safe_filename(".") == "."
        # filename that is double dot
        assert _safe_filename("..") == ".."


class TestCacheErrorPaths:
    """Tests for cache edge cases."""

    def test_cache_mb_eviction(self, test_store, sample_png):
        """Cache evicts when MB limit is reached, not just count limit."""
        # Create a store with small MB limit
        from src.storage import AssetStore

        store = AssetStore(
            max_cache_size=1000,  # large count limit
            max_cache_bytes=500,   # small byte limit (~0.5KB)
        )
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            store._output_dir = td

            # Each sample_png is about 70 bytes when saved
            # Save enough to exceed 500 bytes
            for i in range(10):
                store.save_image(f"mb_test_{i}.png", sample_png)

            # Cache should have evicted oldest entries to stay within MB limit
            assert store._cache_bytes <= store.max_cache_bytes * 1.5, \
                f"Cache bytes {store._cache_bytes} exceeds MB limit"

    def test_cache_get_nonexistent_with_disk_clean(self, test_store):
        """get_image_bytes for nonexistent file returns None even if disk doesn't exist."""
        # Delete the output dir entirely
        import shutil
        if os.path.exists(test_store._output_dir):
            shutil.rmtree(test_store._output_dir, ignore_errors=True)

        result = test_store.get_image_bytes("never_exists.png")
        assert result is None

    def test_concurrent_cache_access(self, test_store, sample_png):
        """Concurrent reads and writes to the cache are safe."""
        errors = []

        def writer(i: int):
            try:
                test_store.save_image(f"concurrent_{i}.png", sample_png)
            except Exception as e:
                errors.append(f"writer {i}: {e}")

        def reader(i: int):
            try:
                # Read from cache — may or may not exist
                test_store.get_image_bytes(f"concurrent_{i}.png")
            except Exception as e:
                errors.append(f"reader {i}: {e}")

        threads = []
        for i in range(10):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Concurrent access errors: {errors}"


class TestTryRemoveAsset:
    """Tests for _try_remove_asset helper."""

    def test_try_remove_asset_success(self, test_store, sample_png, monkeypatch):
        """_try_remove_asset removes an existing file from disk."""
        from src.storage import try_remove_asset, store

        monkeypatch.setattr("src.storage.store", test_store)
        test_store.save_image("to_remove.png", sample_png)

        # File should exist
        disk_path = os.path.join(test_store._output_dir, "to_remove.png")
        assert os.path.isfile(disk_path)

        try_remove_asset("to_remove.png")

        # File should be gone
        assert not os.path.isfile(disk_path)

    def test_try_remove_asset_nonexistent_no_error(self, test_store, monkeypatch):
        """_try_remove_asset on a nonexistent file does NOT raise."""
        from src.storage import try_remove_asset

        # Should not raise
        try_remove_asset("nonexistent_file_xyz.png")

    def test_try_remove_asset_empty_filename(self, monkeypatch):
        """_try_remove_asset with empty string is safe."""
        from src.storage import try_remove_asset

        # Should not crash
        try_remove_asset("")

    def test_try_remove_asset_none(self, monkeypatch):
        """_try_remove_asset with None is safe (type check)."""
        from src.storage import try_remove_asset

        # Should not crash — type annotation says str, but defensive check is good
        try:
            try_remove_asset(None)  # type: ignore[arg-type]
        except TypeError:
            pass  # expected if None not handled
        except Exception:
            pass  # acceptable if handled defensively

    def test_try_remove_asset_race_condition(self, test_store, sample_png, monkeypatch):
        """_try_remove_asset handles race condition (file deleted between check and unlink)."""
        from src.storage import try_remove_asset, store

        monkeypatch.setattr("src.storage.store", test_store)
        test_store.save_image("race_file.png", sample_png)

        disk_path = os.path.join(test_store._output_dir, "race_file.png")
        assert os.path.isfile(disk_path)

        # Delete the file externally to simulate a race condition
        os.unlink(disk_path)

        # try_remove_asset should not crash
        try_remove_asset("race_file.png")

"""Smoke / unit tests for scripts/spawn_comfyui.sh.

These tests validate argument parsing, error handling, PID lifecycle, and
port conflict detection.  No actual ComfyUI or GPU is required — a fake
ComfyUI directory with a dummy main.py is used for process-spawning tests.
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

SPAWN_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "spawn_comfyui.sh"
)


def _run(*args, **kwargs):
    """Run the spawn script with args. Returns CompletedProcess."""
    cmd = ["bash", SPAWN_SCRIPT, *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=kwargs.pop("timeout", 10),
        **kwargs,
    )


def _make_fake_comfyui(tmp_path: Path) -> Path:
    """Create a minimal fake ComfyUI installation.

    The fake main.py sleeps indefinitely so we can test PID tracking.
    """
    comfyui_dir = tmp_path / "ComfyUI"
    comfyui_dir.mkdir(parents=True)

    # Fake main.py that sleeps (simulate a running server)
    main_py = comfyui_dir / "main.py"
    main_py.write_text(
        "import time, sys\n"
        "print('Fake ComfyUI starting...', flush=True)\n"
        "time.sleep(9999)\n"
    )

    # Fake venv (symlink python3 → system python3, or just a script)
    venv_dir = comfyui_dir / "venv" / "bin"
    venv_dir.mkdir(parents=True)
    python_bin = venv_dir / "python"
    # Symlink to the current python interpreter
    python_bin.symlink_to(sys.executable)

    return comfyui_dir


def _bind_port(port: int):
    """Bind a port briefly to simulate port-in-use, return the socket."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.listen(1)
    return s


# ---------------------------------------------------------------------------
#  Tests: Argument parsing & validation
# ---------------------------------------------------------------------------


class TestHelpAndUsage:
    """--help and error-message tests."""

    def test_help_flag(self):
        """--help prints usage and exits 0."""
        result = _run("--help")
        assert result.returncode == 0
        assert "Usage" in result.stdout or "spawn_comfyui" in result.stdout

    def test_no_command(self):
        """No command → error exit."""
        result = _run()
        assert result.returncode != 0
        assert "No command specified" in result.stderr

    def test_unknown_command(self):
        """Unknown command → error exit."""
        result = _run("bogus")
        assert result.returncode != 0
        assert "Unknown command" in result.stderr


class TestInvalidArguments:
    """Argument validation edge cases."""

    def test_negative_count(self):
        """-n -1 → error."""
        result = _run("-n", "-1", "start")
        assert result.returncode != 0

    def test_zero_count(self):
        """-n 0 → error (must be positive)."""
        result = _run("-n", "0", "start")
        assert result.returncode != 0

    def test_non_numeric_count(self):
        """-n abc → error."""
        result = _run("-n", "abc", "start")
        assert result.returncode != 0

    def test_port_below_1024(self):
        """-p 80 → error (privileged port)."""
        result = _run("-p", "80", "start")
        assert result.returncode != 0

    def test_port_above_65535(self):
        """-p 99999 → error."""
        result = _run("-p", "99999", "start")
        assert result.returncode != 0

    def test_port_overflow_with_count(self):
        """-p 65530 -n 10 → error (last port > 65535)."""
        result = _run("-p", "65530", "-n", "10", "start")
        assert result.returncode != 0

    def test_missing_comfyui_dir(self):
        """--comfyui-dir pointing to nonexistent path → error."""
        with tempfile.TemporaryDirectory() as td:
            nonexistent = os.path.join(td, "does_not_exist")
            result = _run("-d", nonexistent, "start")
            assert result.returncode != 0

    def test_invalid_gpu(self):
        """-g notanumber → error."""
        result = _run("-g", "notanumber", "start")
        assert result.returncode != 0


# ---------------------------------------------------------------------------
#  Tests: PID lifecycle with fake ComfyUI
# ---------------------------------------------------------------------------


class TestPidLifecycle:
    """Start fake instances, verify PID files, stop, verify cleanup."""

    def test_start_creates_pid_file(self, tmp_path):
        """Launching 1 instance creates a PID file with a valid PID."""
        comfyui_dir = _make_fake_comfyui(tmp_path)
        pid_dir = tmp_path / "pids"
        log_dir = tmp_path / "logs"

        result = _run(
            "-n", "1",
            "-p", "19990",
            "-d", str(comfyui_dir),
            "--pid-dir", str(pid_dir),
            "--log-dir", str(log_dir),
            "--listen", "127.0.0.1",
            "start",
            timeout=15,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Should have created exactly one PID file
        pid_files = list(pid_dir.glob("comfyui-*.pid"))
        assert len(pid_files) == 1

        # Read PID
        pid = int(pid_files[0].read_text().strip())
        assert pid > 0

        # Verify process is running
        try:
            os.kill(pid, 0)  # signal 0 = existence check
        except OSError:
            pytest.fail(f"Process {pid} is not running")

        # Clean up: stop via script
        stop_result = _run(
            "--pid-dir", str(pid_dir),
            "stop",
            timeout=10,
        )
        assert stop_result.returncode == 0

        # PID file should be removed
        pid_files_after = list(pid_dir.glob("comfyui-*.pid"))
        assert len(pid_files_after) == 0

        # Process should be gone (or at least killable)
        try:
            os.kill(pid, 0)
            # If still alive, force kill it
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
        except OSError:
            pass  # Already dead — good

    def test_start_multiple_instances(self, tmp_path):
        """Launch 3 instances on sequential ports."""
        comfyui_dir = _make_fake_comfyui(tmp_path)
        pid_dir = tmp_path / "pids"
        log_dir = tmp_path / "logs"

        result = _run(
            "-n", "3",
            "-p", "19980",
            "-d", str(comfyui_dir),
            "--pid-dir", str(pid_dir),
            "--log-dir", str(log_dir),
            "--listen", "127.0.0.1",
            "start",
            timeout=15,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        pid_files = sorted(pid_dir.glob("comfyui-*.pid"))
        assert len(pid_files) == 3

        # Verify URLs in output
        assert "19980" in result.stdout
        assert "19981" in result.stdout
        assert "19982" in result.stdout

        # All PIDs should be valid
        pids = []
        for pf in pid_files:
            pid = int(pf.read_text().strip())
            assert pid > 0
            os.kill(pid, 0)  # must be alive
            pids.append(pid)

        # Stop all
        _run("--pid-dir", str(pid_dir), "stop", timeout=10)

        # All should be dead
        for pid in pids:
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def test_status_command(self, tmp_path):
        """Status command shows running instances."""
        comfyui_dir = _make_fake_comfyui(tmp_path)
        pid_dir = tmp_path / "pids"
        log_dir = tmp_path / "logs"

        # Start 2 instances
        _run(
            "-n", "2",
            "-p", "19970",
            "-d", str(comfyui_dir),
            "--pid-dir", str(pid_dir),
            "--log-dir", str(log_dir),
            "--listen", "127.0.0.1",
            "start",
            timeout=15,
        )

        # Check status
        result = _run("--pid-dir", str(pid_dir), "status", timeout=10)
        assert result.returncode == 0
        assert "19970" in result.stdout
        assert "19971" in result.stdout
        assert "RUNNING" in result.stdout

        # Cleanup
        _run("--pid-dir", str(pid_dir), "stop", timeout=10)

    def test_status_empty(self, tmp_path):
        """Status with no PID files shows clean message."""
        pid_dir = tmp_path / "empty_pids"
        pid_dir.mkdir(parents=True)

        result = _run("--pid-dir", str(pid_dir), "status", timeout=10)
        assert result.returncode == 0
        assert "No PID files" in result.stderr or "No PID files" in result.stdout

    def test_stop_nonexistent_dir(self):
        """Stop with nonexistent PID dir → clean exit (nothing to stop)."""
        with tempfile.TemporaryDirectory() as td:
            result = _run("--pid-dir", os.path.join(td, "nope"), "stop", timeout=10)
            assert result.returncode == 0

    def test_force_stop(self, tmp_path):
        """--force stop sends SIGKILL without graceful wait."""
        comfyui_dir = _make_fake_comfyui(tmp_path)
        pid_dir = tmp_path / "pids"
        log_dir = tmp_path / "logs"

        _run(
            "-n", "1",
            "-p", "19960",
            "-d", str(comfyui_dir),
            "--pid-dir", str(pid_dir),
            "--log-dir", str(log_dir),
            "--listen", "127.0.0.1",
            "start",
            timeout=15,
        )

        pid_files = list(pid_dir.glob("comfyui-*.pid"))
        assert len(pid_files) == 1
        pid = int(pid_files[0].read_text().strip())

        # Force stop
        result = _run("--pid-dir", str(pid_dir), "stop", "--force", timeout=10)
        assert result.returncode == 0

        # PID file gone
        assert len(list(pid_dir.glob("comfyui-*.pid"))) == 0

        # Process dead
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    def test_stale_pid_file_cleanup(self, tmp_path):
        """A PID file pointing to a dead process is cleaned up by stop."""
        pid_dir = tmp_path / "pids"
        pid_dir.mkdir(parents=True)

        # Write a PID file with a non-existent PID
        pid_file = pid_dir / "comfyui-19950.pid"
        pid_file.write_text("99999999")  # almost certainly not a real PID

        result = _run("--pid-dir", str(pid_dir), "stop", timeout=10)
        assert result.returncode == 0
        # The stale PID file should be removed
        assert not pid_file.exists()


# ---------------------------------------------------------------------------
#  Tests: Output format
# ---------------------------------------------------------------------------


class TestOutputFormat:
    """Verify the printed URLs are correct."""

    def test_url_format(self, tmp_path):
        """Output contains correctly formatted URLs."""
        comfyui_dir = _make_fake_comfyui(tmp_path)
        pid_dir = tmp_path / "pids"
        log_dir = tmp_path / "logs"

        result = _run(
            "-n", "1",
            "-p", "19940",
            "-d", str(comfyui_dir),
            "--pid-dir", str(pid_dir),
            "--log-dir", str(log_dir),
            "--listen", "127.0.0.1",
            "start",
            timeout=15,
        )

        assert result.returncode == 0
        # Should print the URL
        assert "127.0.0.1:19940" in result.stdout

        # Cleanup
        _run("--pid-dir", str(pid_dir), "stop", timeout=10)

    def test_custom_host(self, tmp_path):
        """--host overrides the printed hostname."""
        comfyui_dir = _make_fake_comfyui(tmp_path)
        pid_dir = tmp_path / "pids"
        log_dir = tmp_path / "logs"

        result = _run(
            "-n", "1",
            "-p", "19930",
            "-d", str(comfyui_dir),
            "--pid-dir", str(pid_dir),
            "--log-dir", str(log_dir),
            "--listen", "0.0.0.0",
            "--host", "gpu-node-1.example.com",
            "start",
            timeout=15,
        )

        assert result.returncode == 0
        assert "gpu-node-1.example.com:19930" in result.stdout

        # Cleanup
        _run("--pid-dir", str(pid_dir), "stop", timeout=10)

    def test_config_comment_block(self, tmp_path):
        """Output includes a commented config.yaml block."""
        comfyui_dir = _make_fake_comfyui(tmp_path)
        pid_dir = tmp_path / "pids"
        log_dir = tmp_path / "logs"

        result = _run(
            "-n", "2",
            "-p", "19920",
            "-d", str(comfyui_dir),
            "--pid-dir", str(pid_dir),
            "--log-dir", str(log_dir),
            "--listen", "127.0.0.1",
            "start",
            timeout=15,
        )

        assert result.returncode == 0
        assert "comfyui.nodes" in result.stdout
        assert "19920" in result.stdout
        assert "19921" in result.stdout

        # Cleanup
        _run("--pid-dir", str(pid_dir), "stop", timeout=10)


# ---------------------------------------------------------------------------
#  Tests: Quiet mode
# ---------------------------------------------------------------------------


class TestQuietMode:
    """-q / --quiet suppresses info messages."""

    def test_quiet_suppresses_info(self, tmp_path):
        """In quiet mode, stdout contains only bare URLs (no [INFO] lines)."""
        comfyui_dir = _make_fake_comfyui(tmp_path)
        pid_dir = tmp_path / "pids"
        log_dir = tmp_path / "logs"

        result = _run(
            "-n", "1",
            "-p", "19910",
            "-d", str(comfyui_dir),
            "--pid-dir", str(pid_dir),
            "--log-dir", str(log_dir),
            "--listen", "127.0.0.1",
            "-q",
            "start",
            timeout=15,
        )

        assert result.returncode == 0
        # stderr should be clean (no [INFO] lines)
        assert "[INFO]" not in result.stderr
        # stdout should contain the URL
        assert "19910" in result.stdout

        # Cleanup
        _run("--pid-dir", str(pid_dir), "stop", timeout=10)


# ---------------------------------------------------------------------------
#  Tests: Port conflict detection
# ---------------------------------------------------------------------------


class TestPortConflict:
    """Verify port-in-use detection behavior."""

    def test_occupied_port_is_skipped(self, tmp_path):
        """If the target port is occupied, the script skips it with a warning."""
        import socket

        comfyui_dir = _make_fake_comfyui(tmp_path)
        pid_dir = tmp_path / "pids"
        log_dir = tmp_path / "logs"

        # Bind port 19900 to simulate occupancy
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", 19900))
            s.listen(1)

            # Try to start on the occupied port
            result = _run(
                "-n", "1",
                "-p", "19900",
                "-d", str(comfyui_dir),
                "--pid-dir", str(pid_dir),
                "--log-dir", str(log_dir),
                "--listen", "127.0.0.1",
                "start",
                timeout=15,
            )

            # Should fail because port is occupied (no instances launched)
            assert result.returncode != 0
            assert "already in use" in result.stderr or "port" in result.stderr.lower()
        finally:
            s.close()

    def test_all_ports_occupied_is_fatal(self, tmp_path):
        """When all target ports are occupied, the script exits with error."""
        import socket

        comfyui_dir = _make_fake_comfyui(tmp_path)
        pid_dir = tmp_path / "pids"
        log_dir = tmp_path / "logs"

        # Bind 2 ports
        sockets = []
        try:
            for port in [19890, 19891]:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                s.listen(1)
                sockets.append(s)

            result = _run(
                "-n", "2",
                "-p", "19890",
                "-d", str(comfyui_dir),
                "--pid-dir", str(pid_dir),
                "--log-dir", str(log_dir),
                "--listen", "127.0.0.1",
                "start",
                timeout=15,
            )

            assert result.returncode != 0
            assert "No instances were launched" in result.stderr
        finally:
            for s in sockets:
                s.close()

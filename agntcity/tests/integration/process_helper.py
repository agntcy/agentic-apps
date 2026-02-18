# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

# Lightweight threaded subprocess runner with prefixed logs + readiness gate.
# No external deps; perfect for pytest fixtures.

from __future__ import annotations
import subprocess
import threading
import sys
import re
from pathlib import Path
from datetime import datetime
from itertools import islice


class ProcessRunner:
    """
    Start a subprocess, stream logs (stdout+stderr) to console with a prefix
    and into a file, wait for a readiness pattern, and stop cleanly.
    """

    def __init__(
        self,
        name: str,
        cmd: list[str],
        cwd: str | None = None,
        env: dict | None = None,
        ready_pattern: str | None = None,
        timeout_s: float = 30.0,
        log_dir: Path | str = ".pytest-logs",
    ):
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self.timeout_s = timeout_s
        self.ready_re = re.compile(ready_pattern) if ready_pattern else None

        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / f"{name}.log"

    # --- public api ---------------------------------------------------------

    def start(self) -> "ProcessRunner":
        """Launch the process and begin streaming logs."""
        self._rotate_log_if_exists()
        self._proc = subprocess.Popen(
            self.cmd,
            cwd=self.cwd,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            start_new_session=True,  # so we can kill the whole process group
        )

        self._thread = threading.Thread(target=self._pump, name=f"{self.name}-logger", daemon=True)
        self._thread.start()
        return self

    def wait_ready(self):
        """Block until the ready pattern appears, or timeout."""
        if not self.ready_re:
            return
        if not self._ready.wait(timeout=self.timeout_s):
            # surface the last lines for easier debugging
            sys.stdout.write(f"\n==== {self.name} (last 200 lines) ====\n")
            sys.stdout.write(self.tail(200) + "\n")
            raise TimeoutError(
                f"{self.name} did not become ready within {self.timeout_s}s "
                f"(pattern: {self.ready_re.pattern!r})"
            )

    def stop(self):
        """Request stop and wait briefly for the process to exit."""
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def tail(self, n: int = 200) -> str:
        """Return the last N lines of the log file."""
        try:
            with open(self.log_path, "r", errors="replace") as f:
                total = sum(1 for _ in f)
                f.seek(0)
                return "".join(list(islice(f, max(0, total - n), None)))
        except Exception as e:
            return f"<could not read {self.log_path}: {e}>"

    # --- internals ----------------------------------------------------------

    def _pump(self):
        assert self._proc is not None
        assert self._proc.stdout is not None

        prefix = f"[{self.name}] "
        with open(self.log_path, "w", buffering=1, errors="replace") as lf:
            for line in self._proc.stdout:
                if line is None:
                    break
                sys.stdout.write(prefix + line)
                lf.write(line)
                if self.ready_re and not self._ready.is_set():
                    if self.ready_re.search(line):
                        self._ready.set()
                if self._stop.is_set():
                    break

    def _rotate_log_if_exists(self):
        if self.log_path.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_path.rename(self.log_dir / f"{self.name}.{ts}.log")

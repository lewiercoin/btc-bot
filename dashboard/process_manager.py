from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ProcessManager:
    """
    Manages a single bot subprocess. Thread-safe for concurrent API requests.

    Invariants:
    - At most one bot process alive at any time.
    - Start and stop are idempotent.
    - Every start and stop is written to an operator audit log.
    - uptime_seconds is computed from launch timestamp, not from DB state.
    """

    def __init__(self, *, project_root: Path, operator_log_path: Path) -> None:
        self.project_root = project_root
        self.operator_log_path = operator_log_path
        self._process: subprocess.Popen | None = None
        self._mode: str | None = None
        self._started_at: datetime | None = None
        self._lock = threading.Lock()

    def start(self, *, mode: str) -> dict[str, Any]:
        normalized_mode = mode.upper()
        if normalized_mode not in {"PAPER", "LIVE"}:
            raise ValueError(f"Unsupported mode: {mode!r}")

        with self._lock:
            current = self._status_locked()
            if current["running"]:
                return {
                    "started": False,
                    "reason": "already_running",
                    "pid": current["pid"],
                }

            process = subprocess.Popen(
                [sys.executable, "main.py", "--mode", normalized_mode],
                cwd=self.project_root,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            started_at = _now_utc()
            self._process = process
            self._mode = normalized_mode
            self._started_at = started_at

            self._append_operator_event(
                {
                    "event": "start",
                    "mode": normalized_mode,
                    "pid": process.pid,
                    "ts": started_at.isoformat(),
                }
            )
            return {
                "started": True,
                "pid": process.pid,
                "mode": normalized_mode,
                "ts": started_at.isoformat(),
            }

    def stop(self, *, reason: str = "operator_stop") -> dict[str, Any]:
        with self._lock:
            current = self._status_locked()
            if not current["running"]:
                return {
                    "stopped": False,
                    "reason": "not_running",
                }

            assert self._process is not None
            process = self._process
            pid = int(process.pid)
            graceful = True

            sig = signal.CTRL_C_EVENT if sys.platform == "win32" else signal.SIGTERM
            try:
                os.kill(pid, sig)
            except OSError:
                if process.poll() is None:
                    raise
            else:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    graceful = False
                    self._append_operator_event(
                        {
                            "event": "stop_hard",
                            "reason": reason,
                            "pid": pid,
                            "ts": _now_utc().isoformat(),
                        }
                    )
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass

            self._clear_locked()

            self._append_operator_event(
                {
                    "event": "stop",
                    "reason": reason,
                    "pid": pid,
                    "graceful": graceful,
                    "ts": _now_utc().isoformat(),
                }
            )
            return {
                "stopped": True,
                "graceful": graceful,
                "pid": pid,
            }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._status_locked()

    def _status_locked(self) -> dict[str, Any]:
        if self._process is None:
            return {
                "running": False,
                "uptime_seconds": None,
                "pid": None,
                "mode": None,
                "exit_code": None,
            }

        exit_code = self._process.poll()
        if exit_code is None:
            uptime_seconds = None
            if self._started_at is not None:
                uptime_seconds = max((_now_utc() - self._started_at).total_seconds(), 0.0)
            return {
                "running": True,
                "uptime_seconds": uptime_seconds,
                "pid": int(self._process.pid),
                "mode": self._mode,
                "exit_code": None,
            }

        self._clear_locked()
        return {
            "running": False,
            "uptime_seconds": None,
            "pid": None,
            "mode": None,
            "exit_code": int(exit_code),
        }

    def _clear_locked(self) -> None:
        self._process = None
        self._mode = None
        self._started_at = None

    def _append_operator_event(self, event: dict[str, Any]) -> None:
        self.operator_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.operator_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True))
            handle.write("\n")

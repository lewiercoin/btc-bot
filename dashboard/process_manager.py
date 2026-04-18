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

import psutil


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
            if not current["managed"]:
                return {
                    "stopped": False,
                    "reason": "not_managed",
                    "pid": current["pid"],
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
            return self._discover_external_or_idle_status()

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
                "managed": True,
            }

        self._clear_locked()
        return {
            "running": False,
            "uptime_seconds": None,
            "pid": None,
            "mode": None,
            "exit_code": int(exit_code),
            "managed": False,
        }

    def _clear_locked(self) -> None:
        self._process = None
        self._mode = None
        self._started_at = None

    def _discover_external_or_idle_status(self) -> dict[str, Any]:
        external = self._discover_external_process_status()
        if external is not None:
            return external
        return {
            "running": False,
            "uptime_seconds": None,
            "pid": None,
            "mode": None,
            "exit_code": None,
            "managed": False,
        }

    def _discover_external_process_status(self) -> dict[str, Any] | None:
        for process in psutil.process_iter(attrs=["pid", "cmdline", "create_time", "cwd"]):
            try:
                info = process.info
                cmdline = [str(part) for part in (info.get("cmdline") or []) if part]
                if not self._looks_like_bot_process(cmdline=cmdline, cwd=info.get("cwd")):
                    continue
                started_at = None
                create_time = info.get("create_time")
                if create_time is not None:
                    started_at = datetime.fromtimestamp(float(create_time), tz=timezone.utc)
                uptime_seconds = None
                if started_at is not None:
                    uptime_seconds = max((_now_utc() - started_at).total_seconds(), 0.0)
                return {
                    "running": True,
                    "uptime_seconds": uptime_seconds,
                    "pid": int(info["pid"]),
                    "mode": self._extract_mode(cmdline),
                    "exit_code": None,
                    "managed": False,
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError, ValueError):
                continue
        return None

    def _looks_like_bot_process(self, *, cmdline: list[str], cwd: str | None) -> bool:
        if not cmdline:
            return False
        cwd_path = Path(cwd) if cwd else None
        if cwd_path is not None and any(Path(part).name == "main.py" for part in cmdline):
            if self._same_path(cwd_path, self.project_root):
                return True
        for part in cmdline:
            part_path = Path(part)
            if part_path.name != "main.py":
                continue
            if part_path.is_absolute() and self._same_path(part_path.parent, self.project_root):
                return True
        return False

    @staticmethod
    def _extract_mode(cmdline: list[str]) -> str | None:
        for index, part in enumerate(cmdline):
            if part == "--mode" and index + 1 < len(cmdline):
                return str(cmdline[index + 1]).upper()
        return None

    @staticmethod
    def _same_path(left: Path, right: Path) -> bool:
        try:
            return left.resolve(strict=False) == right.resolve(strict=False)
        except OSError:
            return str(left) == str(right)

    def _append_operator_event(self, event: dict[str, Any]) -> None:
        self.operator_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.operator_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True))
            handle.write("\n")

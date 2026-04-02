from __future__ import annotations

import json
import signal
import subprocess
from pathlib import Path

import pytest

from dashboard.process_manager import ProcessManager


class FakeProcess:
    def __init__(self, *, pid: int = 1234, poll_values: list[int | None] | None = None, wait_side_effect: Exception | None = None) -> None:
        self.pid = pid
        self._poll_values = list(poll_values or [None])
        self._last_poll = self._poll_values[-1]
        self.wait_side_effect = wait_side_effect
        self.wait_calls: list[float | int | None] = []
        self.terminate_called = False

    def poll(self) -> int | None:
        if self._poll_values:
            self._last_poll = self._poll_values.pop(0)
        return self._last_poll

    def wait(self, timeout: float | int | None = None) -> int:
        self.wait_calls.append(timeout)
        if self.wait_side_effect is not None:
            raise self.wait_side_effect
        return 0

    def terminate(self) -> None:
        self.terminate_called = True


def _read_log_lines(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def test_start_launches_process_and_logs_event(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    process = FakeProcess(pid=2222)
    popen_calls: list[tuple] = []

    def fake_popen(args, cwd, creationflags):
        popen_calls.append((args, cwd, creationflags))
        return process

    monkeypatch.setattr("dashboard.process_manager.subprocess.Popen", fake_popen)

    manager = ProcessManager(
        project_root=tmp_path,
        operator_log_path=tmp_path / "operator.jsonl",
    )
    result = manager.start(mode="PAPER")

    assert result["started"] is True
    assert result["pid"] == 2222
    assert result["mode"] == "PAPER"
    assert popen_calls
    assert popen_calls[0][0][-2:] == ["--mode", "PAPER"]
    assert popen_calls[0][1] == tmp_path
    assert popen_calls[0][2] == getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    events = _read_log_lines(tmp_path / "operator.jsonl")
    assert events[0]["event"] == "start"
    assert events[0]["pid"] == 2222
    assert events[0]["mode"] == "PAPER"


def test_start_returns_already_running_when_process_alive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    process = FakeProcess(pid=3333, poll_values=[None, None])
    monkeypatch.setattr("dashboard.process_manager.subprocess.Popen", lambda *args, **kwargs: process)

    manager = ProcessManager(
        project_root=tmp_path,
        operator_log_path=tmp_path / "operator.jsonl",
    )
    first = manager.start(mode="PAPER")
    second = manager.start(mode="LIVE")

    assert first["started"] is True
    assert second == {"started": False, "reason": "already_running", "pid": 3333}


def test_stop_graceful_path_signals_process_and_logs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    process = FakeProcess(pid=4444)
    signals: list[tuple[int, int]] = []

    monkeypatch.setattr("dashboard.process_manager.subprocess.Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr("dashboard.process_manager.os.kill", lambda pid, sig: signals.append((pid, sig)))

    manager = ProcessManager(
        project_root=tmp_path,
        operator_log_path=tmp_path / "operator.jsonl",
    )
    manager.start(mode="PAPER")
    result = manager.stop()

    assert result == {"stopped": True, "graceful": True, "pid": 4444}
    assert signals == [(4444, signal.CTRL_C_EVENT)]
    assert process.wait_calls == [10]

    events = _read_log_lines(tmp_path / "operator.jsonl")
    assert events[-1]["event"] == "stop"
    assert events[-1]["graceful"] is True


def test_stop_hard_fallback_terminates_process_and_logs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    process = FakeProcess(pid=5555, wait_side_effect=subprocess.TimeoutExpired(cmd="main.py", timeout=10))
    signals: list[tuple[int, int]] = []

    monkeypatch.setattr("dashboard.process_manager.subprocess.Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr("dashboard.process_manager.os.kill", lambda pid, sig: signals.append((pid, sig)))

    manager = ProcessManager(
        project_root=tmp_path,
        operator_log_path=tmp_path / "operator.jsonl",
    )
    manager.start(mode="PAPER")
    result = manager.stop()

    assert result == {"stopped": True, "graceful": False, "pid": 5555}
    assert signals == [(5555, signal.CTRL_C_EVENT)]
    assert process.terminate_called is True

    events = _read_log_lines(tmp_path / "operator.jsonl")
    assert any(event["event"] == "stop_hard" for event in events)
    assert events[-1]["event"] == "stop"
    assert events[-1]["graceful"] is False


def test_stop_returns_not_running_when_idle(tmp_path: Path) -> None:
    manager = ProcessManager(
        project_root=tmp_path,
        operator_log_path=tmp_path / "operator.jsonl",
    )

    assert manager.stop() == {"stopped": False, "reason": "not_running"}


def test_status_reports_uptime_and_clears_exited_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    live_process = FakeProcess(pid=6666, poll_values=[None, None])
    exited_process = FakeProcess(pid=7777, poll_values=[0])
    popen_results = [live_process, exited_process]

    monkeypatch.setattr("dashboard.process_manager.subprocess.Popen", lambda *args, **kwargs: popen_results.pop(0))
    monkeypatch.setattr("dashboard.process_manager.os.kill", lambda pid, sig: None)

    manager = ProcessManager(
        project_root=tmp_path,
        operator_log_path=tmp_path / "operator.jsonl",
    )
    manager.start(mode="PAPER")
    running_status = manager.status()

    assert running_status["running"] is True
    assert running_status["pid"] == 6666
    assert running_status["mode"] == "PAPER"
    assert running_status["uptime_seconds"] is not None
    assert running_status["uptime_seconds"] >= 0.0

    manager.stop()
    manager.start(mode="LIVE")
    exited_status = manager.status()
    idle_status = manager.status()

    assert exited_status == {
        "running": False,
        "uptime_seconds": None,
        "pid": None,
        "mode": None,
        "exit_code": 0,
    }
    assert idle_status == {
        "running": False,
        "uptime_seconds": None,
        "pid": None,
        "mode": None,
        "exit_code": None,
    }


def test_start_rejects_invalid_mode(tmp_path: Path) -> None:
    manager = ProcessManager(
        project_root=tmp_path,
        operator_log_path=tmp_path / "operator.jsonl",
    )

    with pytest.raises(ValueError):
        manager.start(mode="SANDBOX")

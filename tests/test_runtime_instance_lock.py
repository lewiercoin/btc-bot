from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from main import DEFAULT_RUNTIME_LOCK_PATH, acquire_runtime_lock, runtime_lock_path


def test_runtime_lock_path_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BTC_BOT_RUNTIME_LOCK_PATH", raising=False)

    assert runtime_lock_path().as_posix() == DEFAULT_RUNTIME_LOCK_PATH


def test_runtime_lock_path_uses_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    lock_path = tmp_path / "custom.lock"
    monkeypatch.setenv("BTC_BOT_RUNTIME_LOCK_PATH", str(lock_path))

    assert runtime_lock_path() == lock_path


def test_acquire_runtime_lock_writes_pid_and_blocks_second_instance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    locked = False

    def fake_flock(_fd: int, _flags: int) -> None:
        nonlocal locked
        if locked:
            raise OSError("already locked")
        locked = True

    fake_fcntl = SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=fake_flock)
    monkeypatch.setitem(sys.modules, "fcntl", fake_fcntl)

    lock_path = tmp_path / "runtime.lock"
    lock_fd = acquire_runtime_lock(lock_path)
    try:
        assert lock_path.read_text(encoding="utf-8").strip().isdigit()
        with pytest.raises(SystemExit) as exc_info:
            acquire_runtime_lock(lock_path)
        assert exc_info.value.code == 1
    finally:
        lock_fd.close()

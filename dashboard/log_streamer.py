from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encode_event(line: str) -> str:
    payload = json.dumps({"line": line, "ts": _now_iso()})
    return f"data: {payload}\n\n"


def read_last_lines(log_path: Path, *, limit: int = 100) -> list[str]:
    if not log_path.exists():
        return []
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        return [line.rstrip("\r\n") for line in deque(handle, maxlen=limit)]


async def stream_log_lines(
    log_path: Path,
    *,
    disconnect_checker: Callable[[], Awaitable[bool]] | None = None,
    limit: int = 100,
    poll_interval: float = 0.5,
    keepalive_interval: float = 15.0,
) -> AsyncIterator[str]:
    for line in read_last_lines(log_path, limit=limit):
        yield _encode_event(line)

    file_position = log_path.stat().st_size if log_path.exists() else 0
    last_keepalive = asyncio.get_running_loop().time()

    while True:
        if disconnect_checker is not None and await disconnect_checker():
            return

        now = asyncio.get_running_loop().time()
        if now - last_keepalive >= keepalive_interval:
            yield ": keepalive\n\n"
            last_keepalive = now

        if not log_path.exists():
            file_position = 0
            await asyncio.sleep(poll_interval)
            continue

        file_size = log_path.stat().st_size
        if file_size < file_position:
            file_position = 0

        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(file_position)
            for line in handle:
                yield _encode_event(line.rstrip("\r\n"))
            file_position = handle.tell()

        await asyncio.sleep(poll_interval)


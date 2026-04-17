from __future__ import annotations

import re
from pathlib import Path

_CONFIG_HASH_RE = re.compile(r"\bconfig_hash=([0-9a-fA-F]{64})\b")
_TAIL_BYTES = 256 * 1024


def _tail_lines(path: Path, max_bytes: int = _TAIL_BYTES) -> list[str]:
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            offset = max(0, size - max_bytes)
            f.seek(offset)
            raw = f.read()
        return raw.decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def extract_runtime_config_hash(log_path: Path) -> str | None:
    """Read the config hash from the most recent runtime start line in the bot log."""
    for line in reversed(_tail_lines(log_path)):
        if "Starting bot" not in line:
            continue
        match = _CONFIG_HASH_RE.search(line)
        if match:
            return match.group(1)
    return None

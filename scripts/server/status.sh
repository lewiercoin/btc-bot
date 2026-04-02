#!/bin/sh

set -eu

[ -f settings.py ] || {
    echo "Run this script from the repository root." >&2
    exit 1
}

resolve_python() {
    if [ -x .venv/bin/python ]; then
        printf '%s\n' ".venv/bin/python"
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
    fi
    echo "Python interpreter not found. Run sh scripts/server/setup.sh first." >&2
    exit 1
}

load_env_if_present() {
    if [ -f .env ]; then
        set -a
        . ./.env
        set +a
    else
        echo "Warning: .env not found in repo root." >&2
    fi

    if [ -z "${BINANCE_API_KEY:-}" ]; then
        echo "Warning: BINANCE_API_KEY is empty. Status checks still work, but refresh tasks will run without server credentials." >&2
    fi
}

load_env_if_present
PYTHON_BIN=$(resolve_python)

"$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(".")
runs_dir = root / "research_lab" / "runs"
loop_reports = list(runs_dir.rglob("loop_report.json")) if runs_dir.exists() else []

print("Latest loop report:")
if loop_reports:
    latest_report = max(loop_reports, key=lambda path: path.stat().st_mtime)
    payload = json.loads(latest_report.read_text(encoding="utf-8"))
    print(f"path={latest_report.as_posix()}")
    print(f"run_id={payload.get('run_id', 'unknown')}")
    print(f"candidates_evaluated={payload.get('candidates_evaluated', 'unknown')}")
    print(f"stop_reason={payload.get('stop_reason', 'unknown')}")
    print(f"approval_bundle_written={payload.get('approval_bundle_written', False)}")
else:
    print("path=none")
    print("run_id=none")
    print("candidates_evaluated=0")
    print("stop_reason=none")
    print("approval_bundle_written=False")

db_path = root / "storage" / "btc_bot.db"
print("Source DB:")
if db_path.exists():
    stat = db_path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    print(f"path={db_path.as_posix()}")
    print(f"size_bytes={stat.st_size}")
    print(f"size_mb={stat.st_size / (1024 * 1024):.2f}")
    print(f"modified_utc={modified}")
else:
    print(f"path={db_path.as_posix()}")
    print("size_bytes=missing")
    print("size_mb=missing")
    print("modified_utc=missing")

snapshots_dir = root / "research_lab" / "snapshots"
snapshot_files = [path for path in snapshots_dir.rglob("*") if path.is_file()] if snapshots_dir.exists() else []
total_bytes = sum(path.stat().st_size for path in snapshot_files)
print("Snapshots:")
print(f"path={snapshots_dir.as_posix()}")
print(f"files={len(snapshot_files)}")
print(f"total_mb={total_bytes / (1024 * 1024):.2f}")
PY

echo "Processes:"
if command -v pgrep >/dev/null 2>&1; then
    if pgrep -af "python.*research_lab" >/dev/null 2>&1; then
        pgrep -af "python.*research_lab"
    else
        echo "none"
    fi
else
    echo "pgrep not available"
fi

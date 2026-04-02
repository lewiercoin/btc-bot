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
        echo "Warning: BINANCE_API_KEY is empty. bootstrap_history.py currently uses public endpoints, but keep server env aligned with operator policy." >&2
    fi
}

mkdir -p logs
load_env_if_present
PYTHON_BIN=$(resolve_python)
LOG_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG_FILE="logs/refresh_data_${LOG_STAMP}.log"

{
    echo "=== refresh_data.sh started at ${LOG_STAMP} ==="
    echo "cwd=$(pwd)"
    echo "python=${PYTHON_BIN}"
    echo "binance_api_key_present=$( [ -n "${BINANCE_API_KEY:-}" ] && echo yes || echo no )"
} >>"$LOG_FILE"

if "$PYTHON_BIN" scripts/bootstrap_history.py >>"$LOG_FILE" 2>&1; then
    echo "Data refresh completed successfully."
    echo "Log: $LOG_FILE"
    exit 0
else
    STATUS=$?
    echo "Data refresh failed with exit code $STATUS." >&2
    echo "Log: $LOG_FILE" >&2
    tail -n 20 "$LOG_FILE" >&2 || true
    exit "$STATUS"
fi

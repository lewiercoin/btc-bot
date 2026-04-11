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
}

run_step() {
    STEP_NAME=$1
    shift

    STEP_TMP=$(mktemp)
    printf '\n=== %s ===\n' "$STEP_NAME" | tee -a "$LOG_FILE"

    if "$@" >"$STEP_TMP" 2>&1; then
        cat "$STEP_TMP" | tee -a "$LOG_FILE"
        rm -f "$STEP_TMP"
        return 0
    else
        STATUS=$?
        cat "$STEP_TMP" | tee -a "$LOG_FILE"
        rm -f "$STEP_TMP"
        exit "$STATUS"
    fi
}

mkdir -p logs
load_env_if_present
PYTHON_BIN=$(resolve_python)
LOG_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG_FILE="logs/refresh_all_data_${LOG_STAMP}.log"

{
    echo "=== refresh_all_data.sh started at ${LOG_STAMP} ==="
    echo "cwd=$(pwd)"
    echo "python=${PYTHON_BIN}"
} | tee -a "$LOG_FILE"

run_step "bootstrap_history" "$PYTHON_BIN" scripts/bootstrap_history.py
run_step "daily_data_collector" "$PYTHON_BIN" scripts/server/run_daily_data_collector.py
run_step "force_order_bootstrap" "$PYTHON_BIN" scripts/server/run_force_order_collector.py --bootstrap-only

{
    echo
    echo "Refresh summary:"
    echo "- candles / aggtrades / open_interest / funding synced via scripts/bootstrap_history.py"
    echo "- dxy_close / etf_bias_5d refreshed via scripts/server/run_daily_data_collector.py"
    echo "- force_orders backfilled via scripts/server/run_force_order_collector.py --bootstrap-only"
    echo "- log file: ${LOG_FILE}"
} | tee -a "$LOG_FILE"

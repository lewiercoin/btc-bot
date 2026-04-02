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
        echo "Warning: BINANCE_API_KEY is empty. Research Lab can run without it, but server env is incomplete for data refresh tasks." >&2
    fi
}

sanitize_name() {
    printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_'
}

STUDY_NAME=${1:-short-rebuild-v1}
N_TRIALS=${2:-50}
START_DATE=${3:-2022-01-01}
END_DATE=${4:-2026-03-01}

case "$N_TRIALS" in
    ''|*[!0-9]*)
        echo "n-trials must be a positive integer." >&2
        exit 1
        ;;
esac
[ "$N_TRIALS" -ge 1 ] || {
    echo "n-trials must be >= 1." >&2
    exit 1
}

mkdir -p logs research_lab/runs research_lab/snapshots
load_env_if_present
PYTHON_BIN=$(resolve_python)
RUN_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
SAFE_STUDY=$(sanitize_name "$STUDY_NAME")
LOG_FILE="logs/optimize_${SAFE_STUDY}_${RUN_STAMP}.log"
REPORT_PATH="research_lab/runs/latest_report.json"
SUMMARY_TMP=$(mktemp)
REPORT_TMP=$(mktemp)

trap 'rm -f "$SUMMARY_TMP" "$REPORT_TMP"' EXIT HUP INT TERM

{
    echo "=== run_optimize.sh started at ${RUN_STAMP} ==="
    echo "study_name=${STUDY_NAME}"
    echo "n_trials=${N_TRIALS}"
    echo "start_date=${START_DATE}"
    echo "end_date=${END_DATE}"
    echo "python=${PYTHON_BIN}"
} >>"$LOG_FILE"

if "$PYTHON_BIN" -m research_lab optimize \
    --study-name "$STUDY_NAME" \
    --n-trials "$N_TRIALS" \
    --start-date "$START_DATE" \
    --end-date "$END_DATE" \
    >"$SUMMARY_TMP" 2>>"$LOG_FILE"; then
    :
else
    STATUS=$?
    [ -s "$SUMMARY_TMP" ] && cat "$SUMMARY_TMP" >>"$LOG_FILE"
    echo "Optimize run failed: status=failed requested_trials=$N_TRIALS study_name=$STUDY_NAME" >&2
    echo "Log: $LOG_FILE" >&2
    exit "$STATUS"
fi

[ -s "$SUMMARY_TMP" ] && cat "$SUMMARY_TMP" >>"$LOG_FILE"

if "$PYTHON_BIN" -m research_lab build-report \
    --output-json "$REPORT_PATH" \
    >"$REPORT_TMP" 2>>"$LOG_FILE"; then
    :
else
    STATUS=$?
    [ -s "$REPORT_TMP" ] && cat "$REPORT_TMP" >>"$LOG_FILE"
    echo "Optimize run finished, but build-report failed." >&2
    echo "Log: $LOG_FILE" >&2
    exit "$STATUS"
fi

[ -s "$REPORT_TMP" ] && cat "$REPORT_TMP" >>"$LOG_FILE"
[ -f "$REPORT_PATH" ] || {
    echo "build-report did not create $REPORT_PATH" >&2
    echo "Log: $LOG_FILE" >&2
    exit 1
}

"$PYTHON_BIN" - "$SUMMARY_TMP" <<'PY'
import json
import pathlib
import sys

summary_path = pathlib.Path(sys.argv[1])
payload = json.loads(summary_path.read_text(encoding="utf-8"))
print("Optimize summary:")
print(f"status=success")
print(f"trials_total={payload.get('trials_total', 'unknown')}")
print(f"walkforward_mode={payload.get('walkforward_mode', 'unknown')}")
print(f"pareto_candidates={payload.get('pareto_candidates', 'unknown')}")
print(f"recommendations_saved={payload.get('recommendations_saved', 'unknown')}")
PY

echo "requested_trials=$N_TRIALS"
echo "study_name=$STUDY_NAME"
echo "report_path=$REPORT_PATH"
echo "log_path=$LOG_FILE"

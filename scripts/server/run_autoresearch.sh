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

MAX_CANDIDATES=10
START_DATE=2022-01-01
END_DATE=2026-03-01

while [ $# -gt 0 ]; do
    case "$1" in
        --max-candidates)
            shift
            [ $# -gt 0 ] || {
                echo "--max-candidates requires a value." >&2
                exit 1
            }
            MAX_CANDIDATES=$1
            ;;
        --start-date)
            shift
            [ $# -gt 0 ] || {
                echo "--start-date requires a value." >&2
                exit 1
            }
            START_DATE=$1
            ;;
        --end-date)
            shift
            [ $# -gt 0 ] || {
                echo "--end-date requires a value." >&2
                exit 1
            }
            END_DATE=$1
            ;;
        *)
            echo "Unsupported argument: $1" >&2
            echo "Usage: sh scripts/server/run_autoresearch.sh [--max-candidates N] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]" >&2
            exit 1
            ;;
    esac
    shift
done

case "$MAX_CANDIDATES" in
    ''|*[!0-9]*)
        echo "max-candidates must be a positive integer." >&2
        exit 1
        ;;
esac
[ "$MAX_CANDIDATES" -ge 1 ] || {
    echo "max-candidates must be >= 1." >&2
    exit 1
}

mkdir -p logs research_lab/runs research_lab/snapshots
load_env_if_present
PYTHON_BIN=$(resolve_python)
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
OUTPUT_DIR="research_lab/runs/${RUN_ID}"
LOG_FILE="logs/autoresearch_${RUN_ID}.log"
LOOP_REPORT_PATH="${OUTPUT_DIR}/loop_report.json"
SUMMARY_TMP=$(mktemp)

trap 'rm -f "$SUMMARY_TMP"' EXIT HUP INT TERM

{
    echo "=== run_autoresearch.sh started at ${RUN_ID} ==="
    echo "output_dir=${OUTPUT_DIR}"
    echo "max_candidates=${MAX_CANDIDATES}"
    echo "start_date=${START_DATE}"
    echo "end_date=${END_DATE}"
    echo "python=${PYTHON_BIN}"
} >>"$LOG_FILE"

if "$PYTHON_BIN" -m research_lab autoresearch \
    --start-date "$START_DATE" \
    --end-date "$END_DATE" \
    --output-dir "$OUTPUT_DIR" \
    --max-candidates "$MAX_CANDIDATES" \
    >"$SUMMARY_TMP" 2>>"$LOG_FILE"; then
    :
else
    STATUS=$?
    [ -s "$SUMMARY_TMP" ] && cat "$SUMMARY_TMP" >>"$LOG_FILE"
    echo "Autoresearch failed: status=failed max_candidates=$MAX_CANDIDATES" >&2
    echo "Log: $LOG_FILE" >&2
    exit "$STATUS"
fi

[ -s "$SUMMARY_TMP" ] && cat "$SUMMARY_TMP" >>"$LOG_FILE"
[ -f "$LOOP_REPORT_PATH" ] || {
    echo "Autoresearch finished without writing $LOOP_REPORT_PATH" >&2
    echo "Log: $LOG_FILE" >&2
    exit 1
}

"$PYTHON_BIN" - "$LOOP_REPORT_PATH" "$OUTPUT_DIR" <<'PY'
import json
import pathlib
import sys

report_path = pathlib.Path(sys.argv[1])
output_dir = pathlib.Path(sys.argv[2])
payload = json.loads(report_path.read_text(encoding="utf-8"))
approval_dir = output_dir / "approval_bundle"

print("Autoresearch summary:")
print("status=success")
print(f"run_id={payload.get('run_id', 'unknown')}")
print(f"candidates_evaluated={payload.get('candidates_evaluated', 'unknown')}")
print(f"candidates_blocked={payload.get('candidates_blocked', 'unknown')}")
print(f"stop_reason={payload.get('stop_reason', 'unknown')}")
print(f"approval_bundle_written={payload.get('approval_bundle_written', False)}")
if approval_dir.is_dir():
    print(f"approval_bundle_path={approval_dir.as_posix()}")
else:
    print("approval_bundle_path=not_written")
PY

echo "loop_report_path=$LOOP_REPORT_PATH"
echo "requested_max_candidates=$MAX_CANDIDATES"
echo "log_path=$LOG_FILE"

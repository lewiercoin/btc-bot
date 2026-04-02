#!/bin/sh

set -eu

[ -f settings.py ] || {
    echo "Run this script from the repository root." >&2
    exit 1
}

DAYS=7
FORCE=0

load_env_if_present() {
    if [ -f .env ]; then
        set -a
        . ./.env
        set +a
    else
        echo "Warning: .env not found in repo root." >&2
    fi

    if [ -z "${BINANCE_API_KEY:-}" ]; then
        echo "Warning: BINANCE_API_KEY is empty. Cleanup works without it, but server env is incomplete for refresh tasks." >&2
    fi
}

while [ $# -gt 0 ]; do
    case "$1" in
        --force)
            FORCE=1
            ;;
        ''|*[!0-9]*)
            echo "Usage: sh scripts/server/cleanup_snapshots.sh [days] [--force]" >&2
            exit 1
            ;;
        *)
            DAYS=$1
            ;;
    esac
    shift
done

mkdir -p logs
load_env_if_present
SNAPSHOTS_DIR="research_lab/snapshots"
[ -d "$SNAPSHOTS_DIR" ] || {
    echo "Snapshots directory not found: $SNAPSHOTS_DIR" >&2
    exit 1
}

LOG_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG_FILE="logs/cleanup_snapshots_${LOG_STAMP}.log"
TARGETS_FILE=$(mktemp)
trap 'rm -f "$TARGETS_FILE"' EXIT HUP INT TERM

find "$SNAPSHOTS_DIR" -type f -mtime +"$DAYS" -print | sort >"$TARGETS_FILE"
COUNT=$(wc -l <"$TARGETS_FILE" | tr -d ' ')

if [ "$COUNT" -eq 0 ]; then
    echo "No snapshot files older than $DAYS days."
    exit 0
fi

echo "Usune $COUNT plikow. Kontynuowac? [y/N]"
if [ "$FORCE" -ne 1 ]; then
    read ANSWER
    case "$ANSWER" in
        y|Y|yes|YES)
            ;;
        *)
            echo "Cleanup cancelled."
            exit 0
            ;;
    esac
fi

{
    echo "=== cleanup_snapshots.sh started at ${LOG_STAMP} ==="
    echo "days=${DAYS}"
    echo "files=${COUNT}"
} >>"$LOG_FILE"

while IFS= read -r SNAPSHOT_PATH; do
    [ -n "$SNAPSHOT_PATH" ] || continue
    rm -f "$SNAPSHOT_PATH"
    echo "removed=${SNAPSHOT_PATH}" >>"$LOG_FILE"
done <"$TARGETS_FILE"

echo "Removed $COUNT snapshot files older than $DAYS days."
echo "Log: $LOG_FILE"

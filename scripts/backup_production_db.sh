#!/bin/bash
# Production Database Backup Script
# Usage: ./scripts/backup_production_db.sh [destination_dir]
#
# This script creates timestamped backups of the production database
# and can be run manually or via cron for automated backups.

set -euo pipefail

# Configuration
DB_PATH="${DB_PATH:-/home/btc-bot/btc-bot/storage/btc_bot.db}"
BACKUP_DIR="${1:-/home/btc-bot/backups/database}"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
BACKUP_NAME="btc_bot_${TIMESTAMP}.db"
BACKUP_TIMEOUT_SECONDS="${BACKUP_TIMEOUT_SECONDS:-1800}"
KEEP_DAYS=30  # Keep backups for 30 days
MIN_SQLITE_VERSION="3.27.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

version_ge() {
    local current="$1"
    local required="$2"
    [[ "$(printf '%s\n%s\n' "$required" "$current" | sort -V | head -n 1)" == "$required" ]]
}

sql_quote() {
    local raw="$1"
    printf "%s" "$raw" | sed "s/'/''/g"
}

sqlite_file_literal() {
    local raw="$1"
    if command -v cygpath >/dev/null 2>&1; then
        raw=$(cygpath -m "$raw" 2>/dev/null || printf "%s" "$raw")
    fi
    sql_quote "$raw"
}

cleanup_partial_backup() {
    local backup_path="$1"
    rm -f "$backup_path" "${backup_path}.gz"
}

capture_timeout_forensics() {
    local log_path="$1"
    local backup_path="$2"

    {
        echo "backup_timeout_timestamp_utc=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
        echo "db_path=$DB_PATH"
        echo "backup_path=$backup_path"
        echo "timeout_seconds=$BACKUP_TIMEOUT_SECONDS"
        echo
        echo "== sqlite3 process state =="
        ps -eo pid,ppid,state,pcpu,pmem,etime,comm,args 2>&1 | grep -E 'sqlite3|PID' || true
        echo
        echo "== lsof source/target =="
        if command -v lsof >/dev/null 2>&1; then
            lsof "$DB_PATH" "$backup_path" 2>&1 || true
        else
            echo "lsof not available"
        fi
        echo
        echo "== disk usage =="
        df -h "$BACKUP_DIR" "$DB_PATH" 2>&1 || true
        echo
        echo "== target file size =="
        if [[ -e "$backup_path" ]]; then
            ls -lah "$backup_path" 2>&1 || true
            stat "$backup_path" 2>&1 || true
        else
            echo "target file does not exist"
        fi
        echo
        echo "== source db size =="
        ls -lah "$DB_PATH" 2>&1 || true
        stat "$DB_PATH" 2>&1 || true
    } > "$log_path"
}

require_sqlite_version() {
    if ! command -v timeout >/dev/null 2>&1; then
        log_error "timeout command not found"
        exit 1
    fi

    if ! command -v sqlite3 >/dev/null 2>&1; then
        log_error "sqlite3 command not found"
        exit 1
    fi

    local sqlite_version
    sqlite_version=$(sqlite3 --version | awk '{print $1}')
    if ! version_ge "$sqlite_version" "$MIN_SQLITE_VERSION"; then
        log_error "sqlite3 version $sqlite_version is too old; VACUUM INTO requires >= $MIN_SQLITE_VERSION"
        exit 1
    fi
    log_info "sqlite3 version: $sqlite_version"
}

# Check sqlite3 supports VACUUM INTO
require_sqlite_version

# Check if database exists
if [[ ! -f "$DB_PATH" ]]; then
    log_error "Database not found at $DB_PATH"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
TIMEOUT_LOG="$BACKUP_DIR/backup_timeout_${TIMESTAMP}.log"

log_info "Starting backup..."
log_info "Source: $DB_PATH"
log_info "Destination: $BACKUP_PATH"
log_info "Backup method: VACUUM INTO"
log_info "Timeout: ${BACKUP_TIMEOUT_SECONDS}s"

# Get database size
DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
log_info "Database size: $DB_SIZE"

VACUUM_SQL="VACUUM INTO '$(sqlite_file_literal "$BACKUP_PATH")'"
set +e
timeout "$BACKUP_TIMEOUT_SECONDS" sqlite3 -cmd ".timeout $((BACKUP_TIMEOUT_SECONDS * 1000))" "$DB_PATH" "$VACUUM_SQL"
BACKUP_EXIT=$?
set -e

if [[ $BACKUP_EXIT -eq 124 ]]; then
    log_error "Backup timed out after ${BACKUP_TIMEOUT_SECONDS}s"
    capture_timeout_forensics "$TIMEOUT_LOG" "$BACKUP_PATH"
    cleanup_partial_backup "$BACKUP_PATH"
    log_error "Timeout forensics written to $TIMEOUT_LOG"
    exit 2
elif [[ $BACKUP_EXIT -ne 0 ]]; then
    log_error "Backup failed with exit code $BACKUP_EXIT"
    cleanup_partial_backup "$BACKUP_PATH"
    exit 1
fi

if [[ ! -f "$BACKUP_PATH" ]]; then
    log_error "Backup command completed but target file is missing"
    cleanup_partial_backup "$BACKUP_PATH"
    exit 1
fi

# Verify backup integrity
BACKUP_SIZE=$(du -h "$BACKUP_PATH" | cut -f1)
log_info "Backup created successfully: $BACKUP_SIZE"

INTEGRITY_RESULT=$(sqlite3 "$BACKUP_PATH" "PRAGMA integrity_check;" 2>/dev/null || true)
if [[ "$INTEGRITY_RESULT" == "ok" ]]; then
    log_info "Backup integrity check: PASS"
else
    log_error "Backup integrity check: FAIL (${INTEGRITY_RESULT:-no output})"
    cleanup_partial_backup "$BACKUP_PATH"
    exit 1
fi

# Create compressed version
log_info "Compressing backup..."
if ! gzip -9 "$BACKUP_PATH"; then
    log_error "Backup compression failed"
    cleanup_partial_backup "$BACKUP_PATH"
    exit 1
fi
COMPRESSED_PATH="${BACKUP_PATH}.gz"
COMPRESSED_SIZE=$(du -h "$COMPRESSED_PATH" | cut -f1)
log_info "Compressed size: $COMPRESSED_SIZE"

# Clean up old backups
log_info "Cleaning up backups older than $KEEP_DAYS days..."
find "$BACKUP_DIR" -name "btc_bot_*.db.gz" -type f -mtime +$KEEP_DAYS -delete

BACKUP_COUNT=$(find "$BACKUP_DIR" -name "btc_bot_*.db.gz" | wc -l)
log_info "Total backups retained: $BACKUP_COUNT"

# Create latest symlink
ln -sf "${BACKUP_NAME}.gz" "$BACKUP_DIR/btc_bot_latest.db.gz"

log_info "Backup completed successfully!"
echo ""
echo "Backup file: $COMPRESSED_PATH"
echo "Latest link: $BACKUP_DIR/btc_bot_latest.db.gz"

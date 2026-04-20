#!/bin/bash
# Production Database Restore Script
# Usage: ./scripts/restore_production_db.sh <backup_file> [--force]
#
# DANGER: This will replace the current production database!
# Bot service must be stopped before running this script.

set -euo pipefail

# Configuration
DB_PATH="/home/btc-bot/btc-bot/storage/btc_bot.db"
SERVICE_NAME="btc-bot.service"

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

# Check arguments
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <backup_file> [--force]"
    echo ""
    echo "Example:"
    echo "  $0 /home/btc-bot/backups/database/btc_bot_20260420T120000Z.db.gz"
    echo "  $0 /home/btc-bot/backups/database/btc_bot_latest.db.gz --force"
    exit 1
fi

BACKUP_FILE="$1"
FORCE="${2:-}"

# Check if backup file exists
if [[ ! -f "$BACKUP_FILE" ]]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Check if it's compressed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    COMPRESSED=true
else
    COMPRESSED=false
fi

log_warn "=========================================="
log_warn "⚠️  DATABASE RESTORE - DANGEROUS OPERATION"
log_warn "=========================================="
echo ""
log_warn "This will REPLACE the current production database!"
log_warn "Current DB: $DB_PATH"
log_warn "Backup file: $BACKUP_FILE"
echo ""

# Check if bot is running
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log_error "Bot service is RUNNING! Stop it first:"
    echo "  sudo systemctl stop $SERVICE_NAME"
    exit 1
fi

log_info "Bot service is stopped ✓"

# Safety check (unless --force)
if [[ "$FORCE" != "--force" ]]; then
    echo ""
    read -p "Are you ABSOLUTELY SURE you want to proceed? (type 'YES' to confirm): " CONFIRM
    if [[ "$CONFIRM" != "YES" ]]; then
        log_info "Restore cancelled."
        exit 0
    fi
fi

# Backup current database before restore
if [[ -f "$DB_PATH" ]]; then
    BACKUP_TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
    SAFETY_BACKUP="${DB_PATH}.before-restore-${BACKUP_TIMESTAMP}"
    log_info "Creating safety backup of current database..."
    cp "$DB_PATH" "$SAFETY_BACKUP"
    log_info "Safety backup: $SAFETY_BACKUP"
fi

# Extract if compressed
if [[ "$COMPRESSED" == true ]]; then
    log_info "Decompressing backup..."
    TEMP_DB="/tmp/btc_bot_restore_$$.db"
    gunzip -c "$BACKUP_FILE" > "$TEMP_DB"
    RESTORE_FILE="$TEMP_DB"
else
    RESTORE_FILE="$BACKUP_FILE"
fi

# Verify backup integrity
log_info "Verifying backup integrity..."
if ! sqlite3 "$RESTORE_FILE" "PRAGMA integrity_check;" > /dev/null 2>&1; then
    log_error "Backup integrity check FAILED!"
    [[ -n "${TEMP_DB:-}" ]] && rm -f "$TEMP_DB"
    exit 1
fi
log_info "Integrity check: PASS ✓"

# Get backup info
BACKUP_SIZE=$(du -h "$RESTORE_FILE" | cut -f1)
TRADE_COUNT=$(sqlite3 "$RESTORE_FILE" "SELECT COUNT(*) FROM trade_log;" 2>/dev/null || echo "N/A")
LAST_TRADE=$(sqlite3 "$RESTORE_FILE" "SELECT MAX(opened_at) FROM trade_log;" 2>/dev/null || echo "N/A")

log_info "Backup info:"
echo "  Size: $BACKUP_SIZE"
echo "  Trades: $TRADE_COUNT"
echo "  Last trade: $LAST_TRADE"

# Restore database
log_info "Restoring database..."
cp "$RESTORE_FILE" "$DB_PATH"
chown btc-bot:btc-bot "$DB_PATH"
chmod 644 "$DB_PATH"

# Clean up temp file
[[ -n "${TEMP_DB:-}" ]] && rm -f "$TEMP_DB"

log_info "Database restored successfully!"
echo ""
log_info "Next steps:"
echo "  1. Verify database: sqlite3 $DB_PATH 'SELECT COUNT(*) FROM trade_log;'"
echo "  2. Start bot: sudo systemctl start $SERVICE_NAME"
echo "  3. Check status: sudo systemctl status $SERVICE_NAME"
echo ""
log_warn "Safety backup available at: ${SAFETY_BACKUP:-N/A}"
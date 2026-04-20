#!/bin/bash
# Production Database Backup Script
# Usage: ./scripts/backup_production_db.sh [destination_dir]
#
# This script creates timestamped backups of the production database
# and can be run manually or via cron for automated backups.

set -euo pipefail

# Configuration
DB_PATH="/home/btc-bot/btc-bot/storage/btc_bot.db"
BACKUP_DIR="${1:-/home/btc-bot/backups/database}"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
BACKUP_NAME="btc_bot_${TIMESTAMP}.db"
KEEP_DAYS=30  # Keep backups for 30 days

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

# Check if database exists
if [[ ! -f "$DB_PATH" ]]; then
    log_error "Database not found at $DB_PATH"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

log_info "Starting backup..."
log_info "Source: $DB_PATH"
log_info "Destination: $BACKUP_DIR/$BACKUP_NAME"

# Get database size
DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
log_info "Database size: $DB_SIZE"

# SQLite backup using .backup command (safe for live database)
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/$BACKUP_NAME'"

if [[ $? -eq 0 ]]; then
    # Verify backup integrity
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME" | cut -f1)
    log_info "Backup created successfully: $BACKUP_SIZE"

    # Check if backup can be opened
    if sqlite3 "$BACKUP_DIR/$BACKUP_NAME" "PRAGMA integrity_check;" > /dev/null 2>&1; then
        log_info "Backup integrity check: PASS"
    else
        log_error "Backup integrity check: FAIL"
        rm -f "$BACKUP_DIR/$BACKUP_NAME"
        exit 1
    fi

    # Create compressed version
    log_info "Compressing backup..."
    gzip -9 "$BACKUP_DIR/$BACKUP_NAME"
    COMPRESSED_SIZE=$(du -h "$BACKUP_DIR/${BACKUP_NAME}.gz" | cut -f1)
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
    echo "Backup file: $BACKUP_DIR/${BACKUP_NAME}.gz"
    echo "Latest link: $BACKUP_DIR/btc_bot_latest.db.gz"

else
    log_error "Backup failed!"
    exit 1
fi
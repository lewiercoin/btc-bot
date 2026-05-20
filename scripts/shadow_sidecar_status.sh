#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/btc-bot/btc-bot}"
SHADOW_DB="${REPO_DIR}/research_lab/shadow/multi_asset_shadow.db"
PROD_DB="${REPO_DIR}/storage/btc_bot.db"

echo "== multi-asset-shadow.timer =="
systemctl status multi-asset-shadow.timer --no-pager || true

echo
echo "== timers =="
systemctl list-timers --all --no-pager | grep multi-asset-shadow || true

echo
echo "== service logs last hour =="
journalctl -u multi-asset-shadow.service --since "1 hour ago" -n 20 --no-pager || true

echo
echo "== shadow DB =="
if [[ -f "${SHADOW_DB}" ]]; then
  sqlite3 "${SHADOW_DB}" "SELECT COUNT(*) AS runs_last_24h FROM shadow_runs WHERE created_at_utc > datetime('now', '-24 hours');"
  sqlite3 "${SHADOW_DB}" "SELECT shadow_run_id, created_at_utc, dry_run FROM shadow_runs ORDER BY created_at_utc DESC LIMIT 5;"
else
  echo "shadow DB not found: ${SHADOW_DB}"
fi

echo
echo "== BTC PAPER process count =="
pgrep -af "main.py --mode PAPER" | grep -v grep || true
echo "count=$(pgrep -af "main.py --mode PAPER" | grep -v grep | wc -l | tr -d " ")"

echo
echo "== production DB info =="
if [[ -f "${PROD_DB}" ]]; then
  stat -c "size=%s mtime=%Y path=%n" "${PROD_DB}"
  sqlite3 "${PROD_DB}" ".dbinfo" >/dev/null
  echo "production DB readable"
else
  echo "production DB not found: ${PROD_DB}"
fi

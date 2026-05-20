#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/btc-bot/btc-bot}"
SERVICE_NAME="multi-asset-shadow.service"
TIMER_NAME="multi-asset-shadow.timer"
SHADOW_DB="${REPO_DIR}/research_lab/shadow/multi_asset_shadow.db"
PROD_DB="${REPO_DIR}/storage/btc_bot.db"
MIN_FREE_KB=$((12 * 1024 * 1024))

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

require_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    fail "run as root on the production server"
  fi
}

db_signature() {
  if [[ ! -f "${PROD_DB}" ]]; then
    echo "missing:0:0"
    return
  fi
  stat -c "%s:%Y:%n" "${PROD_DB}"
}

paper_process_count() {
  pgrep -af "main.py --mode PAPER" | grep -v grep | wc -l | tr -d " "
}

day0_checks() {
  echo "Day 0 pre-start checks"
  systemctl is-active --quiet btc-bot || fail "btc-bot.service is not active"

  local process_count
  process_count="$(paper_process_count)"
  [[ "${process_count}" == "1" ]] || fail "expected exactly one BTC PAPER process, got ${process_count}"

  local free_kb
  free_kb="$(df -Pk / | awk 'NR==2 {print $4}')"
  [[ "${free_kb}" -ge "${MIN_FREE_KB}" ]] || fail "disk free below 12GB guard: ${free_kb} KB"

  cd "${REPO_DIR}"
  local dry_json
  dry_json="$("${REPO_DIR}/.venv/bin/python" sidecar_main.py --dry-run)"
  echo "${dry_json}"
  echo "${dry_json}" | grep -q '"production_db_touched": false' || fail "dry-run touched production DB"

  git rev-parse --short HEAD
  sqlite3 "${PROD_DB}" ".dbinfo" >/dev/null
}

install_units() {
  install -m 0644 "${REPO_DIR}/${SERVICE_NAME}" "/etc/systemd/system/${SERVICE_NAME}"
  install -m 0644 "${REPO_DIR}/${TIMER_NAME}" "/etc/systemd/system/${TIMER_NAME}"
  systemctl daemon-reload
  systemctl enable "${TIMER_NAME}"
}

start_and_verify() {
  local before_sig after_sig
  before_sig="$(db_signature)"

  systemctl start "${TIMER_NAME}"
  systemctl start "${SERVICE_NAME}"

  after_sig="$(db_signature)"
  [[ "${before_sig}" == "${after_sig}" ]] || fail "production DB signature changed"

  sqlite3 "${SHADOW_DB}" "SELECT COUNT(*) FROM shadow_runs;" >/dev/null
  systemctl is-active --quiet btc-bot || fail "btc-bot.service stopped after sidecar cycle"

  local process_count
  process_count="$(paper_process_count)"
  [[ "${process_count}" == "1" ]] || fail "BTC PAPER process count changed: ${process_count}"
}

main() {
  require_root
  day0_checks
  install_units
  start_and_verify
  echo "DAY0_PASS: ${SERVICE_NAME}/${TIMER_NAME} installed, timer started, first cycle clean"
}

main "$@"

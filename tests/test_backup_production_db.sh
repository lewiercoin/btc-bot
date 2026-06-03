#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_SCRIPT="$REPO_ROOT/scripts/backup_production_db.sh"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

assert_file_exists() {
    local path="$1"
    [[ -f "$path" ]] || fail "expected file to exist: $path"
}

create_source_db() {
    local db_path="$1"
    sqlite3 "$db_path" >/dev/null <<'SQL'
PRAGMA journal_mode=WAL;
CREATE TABLE trade_log (
    trade_id TEXT PRIMARY KEY,
    opened_at TEXT NOT NULL,
    pnl_abs REAL NOT NULL
);
CREATE TABLE bot_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE decision_outcomes (
    id INTEGER PRIMARY KEY,
    cycle_timestamp TEXT NOT NULL,
    outcome_group TEXT NOT NULL,
    outcome_reason TEXT NOT NULL
);
WITH RECURSIVE cnt(x) AS (
    SELECT 1
    UNION ALL
    SELECT x + 1 FROM cnt WHERE x < 300
)
INSERT INTO trade_log(trade_id, opened_at, pnl_abs)
SELECT printf('trade-%03d', x), '2026-06-01T00:00:00+00:00', x * 0.1 FROM cnt;
INSERT INTO bot_state(key, value, updated_at)
VALUES ('mode', 'PAPER', '2026-06-01T00:00:00+00:00');
INSERT INTO decision_outcomes(cycle_timestamp, outcome_group, outcome_reason)
SELECT opened_at, 'no_signal', 'test_fixture' FROM trade_log;
SQL
}

test_success_path() {
    local tmp_dir source_db backup_dir backup_gz latest_link restored_db source_count backup_count integrity
    tmp_dir="$(mktemp -d)"
    source_db="$tmp_dir/source.db"
    backup_dir="$tmp_dir/backups"
    restored_db="$tmp_dir/restored.db"
    create_source_db "$source_db"
    source_count="$(sqlite3 "$source_db" "SELECT COUNT(*) FROM trade_log;")"

    DB_PATH="$source_db" "$BACKUP_SCRIPT" "$backup_dir" > "$tmp_dir/success.log" 2>&1

    backup_gz="$(find "$backup_dir" -name 'btc_bot_*.db.gz' -type f | head -n 1)"
    [[ -n "$backup_gz" ]] || fail "compressed backup was not created"
    assert_file_exists "$backup_gz"
    latest_link="$backup_dir/btc_bot_latest.db.gz"
    assert_file_exists "$latest_link"
    if [[ -L "$latest_link" ]]; then
        [[ "$(readlink "$latest_link")" == "$(basename "$backup_gz")" ]] || fail "latest symlink target mismatch"
    else
        cmp -s "$backup_gz" "$latest_link" || fail "latest pointer file does not match backup"
    fi
    [[ ! -f "${backup_gz%.gz}" ]] || fail "uncompressed backup should be removed after gzip"

    gunzip -c "$backup_gz" > "$restored_db"
    integrity="$(sqlite3 "$restored_db" "PRAGMA integrity_check;")"
    [[ "$integrity" == "ok" ]] || fail "backup integrity failed: $integrity"
    backup_count="$(sqlite3 "$restored_db" "SELECT COUNT(*) FROM trade_log;")"
    [[ "$backup_count" == "$source_count" ]] || fail "trade count mismatch: source=$source_count backup=$backup_count"
    [[ "$(sqlite3 "$source_db" "SELECT COUNT(*) FROM trade_log;")" == "$source_count" ]] || fail "source DB was modified"

    rm -rf "$tmp_dir"
}

test_timeout_path() {
    local tmp_dir source_db backup_dir lock_pid exit_code timeout_log partial_count mock_bin real_sqlite
    tmp_dir="$(mktemp -d)"
    source_db="$tmp_dir/source.db"
    backup_dir="$tmp_dir/backups"
    mock_bin="$tmp_dir/bin"
    real_sqlite="$(command -v sqlite3)"
    create_source_db "$source_db"
    mkdir -p "$mock_bin"
    cat > "$mock_bin/sqlite3" <<EOF
#!/usr/bin/env bash
if [[ "\$*" == *"VACUUM INTO"* ]]; then
    sleep 5
    exit 0
fi
exec "$real_sqlite" "\$@"
EOF
    chmod +x "$mock_bin/sqlite3"

    {
        printf 'BEGIN EXCLUSIVE;\n'
        printf "INSERT INTO bot_state(key, value, updated_at) VALUES ('lock', 'held', '2026-06-01T00:00:00+00:00');\n"
        sleep 5
        printf 'COMMIT;\n'
    } | sqlite3 "$source_db" &
    lock_pid=$!
    sleep 0.5

    set +e
    PATH="$mock_bin:$PATH" DB_PATH="$source_db" BACKUP_TIMEOUT_SECONDS=1 "$BACKUP_SCRIPT" "$backup_dir" > "$tmp_dir/timeout.log" 2>&1
    exit_code=$?
    set -e

    wait "$lock_pid" 2>/dev/null || true

    [[ "$exit_code" -eq 2 ]] || fail "expected timeout exit code 2, got $exit_code; log: $(cat "$tmp_dir/timeout.log")"
    timeout_log="$(find "$backup_dir" -name 'backup_timeout_*.log' -type f | head -n 1)"
    assert_file_exists "$timeout_log"
    grep -q "sqlite3 process state" "$timeout_log" || fail "forensics log missing process state"
    grep -q "disk usage" "$timeout_log" || fail "forensics log missing disk usage"
    partial_count="$(find "$backup_dir" -name 'btc_bot_*.db' -type f | wc -l)"
    [[ "$partial_count" -eq 0 ]] || fail "partial backup file was not removed"

    rm -rf "$tmp_dir"
}

test_sqlite_version_preflight() {
    local tmp_dir source_db backup_dir mock_bin real_sqlite exit_code
    tmp_dir="$(mktemp -d)"
    source_db="$tmp_dir/source.db"
    backup_dir="$tmp_dir/backups"
    mock_bin="$tmp_dir/bin"
    real_sqlite="$(command -v sqlite3)"
    create_source_db "$source_db"
    mkdir -p "$mock_bin"
    cat > "$mock_bin/sqlite3" <<EOF
#!/usr/bin/env bash
if [[ "\$1" == "--version" ]]; then
    echo "3.20.0 2017-08-01"
    exit 0
fi
exec "$real_sqlite" "\$@"
EOF
    chmod +x "$mock_bin/sqlite3"

    set +e
    PATH="$mock_bin:$PATH" DB_PATH="$source_db" "$BACKUP_SCRIPT" "$backup_dir" > "$tmp_dir/version.log" 2>&1
    exit_code=$?
    set -e

    [[ "$exit_code" -eq 1 ]] || fail "expected version preflight exit code 1, got $exit_code"
    grep -q "VACUUM INTO requires >= 3.27.0" "$tmp_dir/version.log" || fail "missing SQLite version failure message"

    rm -rf "$tmp_dir"
}

main() {
    command -v sqlite3 >/dev/null 2>&1 || fail "sqlite3 command is required"
    command -v timeout >/dev/null 2>&1 || fail "timeout command is required"
    command -v gzip >/dev/null 2>&1 || fail "gzip command is required"
    command -v gunzip >/dev/null 2>&1 || fail "gunzip command is required"

    bash -n "$BACKUP_SCRIPT"
    bash -n "$0"
    if command -v shellcheck >/dev/null 2>&1; then
        shellcheck "$BACKUP_SCRIPT" "$0"
    fi

    test_success_path
    test_timeout_path
    test_sqlite_version_preflight

    echo "backup_production_db.sh tests passed"
}

main "$@"

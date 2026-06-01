#!/usr/bin/env python3
"""Update deployment candidate metadata without changing strategy parameters.

This script is intentionally narrow. It updates only explicit candidate-id
metadata fields in either:

- a JSON settings file, for keys such as deployment.candidate_id and
  monitoring.candidate_id; or
- a SQLite table that already has a candidate_id column.

It does not create columns, change strategy fields, or touch unrelated tables.
"""

from __future__ import annotations

import argparse
import copy
import getpass
import json
import os
import socket
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_ID = "optuna-default-v3-trial-00095"
TARGET_ID = "experiment-profile-permissive-v1"
DEFAULT_JSON_PATHS = ("deployment.candidate_id", "monitoring.candidate_id")

EXIT_OK = 0
EXIT_DRIFT_REMAINS = 2
EXIT_UNEXPECTED_STATE = 3


@dataclass(frozen=True)
class Change:
    location: str
    prior: str | None
    new: str
    action: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _operations_dir() -> Path:
    return _repo_root() / "docs" / "operations"


def _log_path(timestamp: str) -> Path:
    safe = timestamp.replace(":", "").replace("+", "Z")
    return _operations_dir() / f"CANDIDATE_ID_UPDATE_{safe}.log"


def _write_log(changes: list[Change], *, mode: str, target: str) -> Path:
    timestamp = _utc_now()
    path = _log_path(timestamp)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp_utc": timestamp,
        "operator_user": getpass.getuser(),
        "operator_hostname": socket.gethostname(),
        "mode": mode,
        "target": target,
        "changes": [change.__dict__ for change in changes],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _get_path(data: dict[str, Any], dotted: str) -> str | None:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if current is None:
        return None
    if not isinstance(current, str):
        raise ValueError(f"{dotted} is not a string candidate-id field")
    return current


def _set_path(data: dict[str, Any], dotted: str, value: str) -> None:
    current: Any = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"{dotted} path is missing")
        current = current[part]
    leaf = parts[-1]
    if not isinstance(current, dict) or leaf not in current:
        raise ValueError(f"{dotted} path is missing")
    if not isinstance(current[leaf], str):
        raise ValueError(f"{dotted} is not a string candidate-id field")
    current[leaf] = value


def _atomic_json_write(path: Path, data: dict[str, Any]) -> None:
    encoded = json.dumps(data, indent=2, sort_keys=False) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False
    ) as handle:
        handle.write(encoded)
        tmp_name = handle.name
    os.replace(tmp_name, path)


def _json_changes(path: Path, json_paths: tuple[str, ...]) -> tuple[dict[str, Any], list[Change], bool]:
    data = json.loads(path.read_text(encoding="utf-8"))
    updated = copy.deepcopy(data)
    changes: list[Change] = []
    all_target = True
    for dotted in json_paths:
        prior = _get_path(data, dotted)
        if prior == TARGET_ID:
            changes.append(Change(dotted, prior, TARGET_ID, "noop"))
            continue
        all_target = False
        if prior != EXPECTED_ID:
            raise RuntimeError(f"{dotted} has unexpected candidate_id={prior!r}")
        _set_path(updated, dotted, TARGET_ID)
        changes.append(Change(dotted, prior, TARGET_ID, "update"))
    return updated, changes, all_target


def _run_json(args: argparse.Namespace) -> int:
    path = Path(args.settings_json)
    json_paths = tuple(args.json_path or DEFAULT_JSON_PATHS)
    try:
        updated, changes, all_target = _json_changes(path, json_paths)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED_STATE

    if args.verify_only:
        return EXIT_OK if all_target else EXIT_DRIFT_REMAINS

    if args.dry_run:
        for change in changes:
            print(f"DRY_RUN JSON {path}:{change.location} {change.prior!r} -> {change.new!r}")
        return EXIT_OK

    if all_target:
        log = _write_log(changes, mode="json-noop", target=str(path))
        print(log)
        return EXIT_OK

    _atomic_json_write(path, updated)
    log = _write_log(changes, mode="json-update", target=str(path))
    print(log)
    return EXIT_OK


def _sqlite_candidate_column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return any(row[1] == column for row in rows)


def _run_sqlite(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    table = args.table
    column = args.column
    where = args.where
    conn = sqlite3.connect(str(db_path))
    try:
        if not _sqlite_candidate_column_exists(conn, table, column):
            print(f"ERROR: {table}.{column} does not exist", file=sys.stderr)
            return EXIT_UNEXPECTED_STATE

        select_sql = f'SELECT "{column}" FROM "{table}" WHERE {where}'
        rows = conn.execute(select_sql).fetchall()
        if len(rows) != 1:
            print(f"ERROR: expected exactly one row for {table} WHERE {where}, got {len(rows)}", file=sys.stderr)
            return EXIT_UNEXPECTED_STATE
        prior = rows[0][0]
        if prior == TARGET_ID:
            changes = [Change(f"{table}.{column}", prior, TARGET_ID, "noop")]
            if args.verify_only:
                return EXIT_OK
            if args.dry_run:
                print(f"DRY_RUN SQL no-op: {table}.{column} already {TARGET_ID!r}")
                return EXIT_OK
            log = _write_log(changes, mode="sqlite-noop", target=str(db_path))
            print(log)
            return EXIT_OK
        if prior != EXPECTED_ID:
            print(f"ERROR: unexpected {table}.{column}={prior!r}", file=sys.stderr)
            return EXIT_UNEXPECTED_STATE
        if args.verify_only:
            return EXIT_DRIFT_REMAINS
        changes = [Change(f"{table}.{column}", prior, TARGET_ID, "update")]
        update_sql = f'UPDATE "{table}" SET "{column}" = ? WHERE {where}'
        if args.dry_run:
            print(f"DRY_RUN SQL: {update_sql} [{TARGET_ID!r}]")
            return EXIT_OK
        before = conn.total_changes
        conn.execute(update_sql, (TARGET_ID,))
        if conn.total_changes - before != 1:
            conn.rollback()
            print("ERROR: candidate-id update did not affect exactly one row", file=sys.stderr)
            return EXIT_UNEXPECTED_STATE
        conn.commit()
        log = _write_log(changes, mode="sqlite-update", target=str(db_path))
        print(log)
        return EXIT_OK
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--settings-json", help="JSON settings file to update")
    target.add_argument("--db", help="SQLite database to update")
    parser.add_argument("--dry-run", action="store_true", help="Print intended changes without writing")
    parser.add_argument("--verify-only", action="store_true", help="Verify target candidate id is already present")
    parser.add_argument(
        "--json-path",
        action="append",
        help="Dotted JSON candidate-id path. Defaults to deployment.candidate_id and monitoring.candidate_id.",
    )
    parser.add_argument("--table", default="bot_state", help="SQLite table name")
    parser.add_argument("--column", default="candidate_id", help="SQLite candidate-id column name")
    parser.add_argument("--where", default="id = 1", help="SQLite WHERE clause identifying the singleton row")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run and args.verify_only:
        print("ERROR: --dry-run and --verify-only are mutually exclusive", file=sys.stderr)
        return EXIT_UNEXPECTED_STATE
    if args.settings_json:
        return _run_json(args)
    return _run_sqlite(args)


if __name__ == "__main__":
    raise SystemExit(main())

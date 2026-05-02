from __future__ import annotations

import sqlite3
from pathlib import Path

from research_lab.constants import SQLITE_SOURCE_TABLES


def create_trial_snapshot(source_db_path: Path, snapshots_dir: Path, trial_id: str) -> Path:
    """Copies source SQLite DB to snapshots_dir/trial_id.db using the .backup() API.

    Uses sqlite3.Connection.backup() instead of shutil.copy2 so that WAL-mode databases
    are checkpointed atomically into the snapshot. A raw file copy misses any committed
    transactions still in the WAL file, producing an incomplete and silently wrong snapshot.
    """
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshots_dir / f"{trial_id}.db"
    src_conn = sqlite3.connect(f"file:{source_db_path.resolve().as_posix()}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(snapshot_path)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    return snapshot_path


def open_snapshot_connection(snapshot_path: Path) -> sqlite3.Connection:
    """Opens connection with row_factory=sqlite3.Row set."""

    conn = sqlite3.connect(snapshot_path)
    conn.row_factory = sqlite3.Row
    return conn


def verify_required_tables(conn: sqlite3.Connection) -> None:
    """Raises if any SQLITE_SOURCE_TABLES table is missing."""

    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    existing_tables = {str(row["name"]) if isinstance(row, sqlite3.Row) else str(row[0]) for row in rows}
    missing = [table for table in SQLITE_SOURCE_TABLES if table not in existing_tables]
    if missing:
        raise ValueError(f"Missing required table(s): {', '.join(sorted(missing))}")


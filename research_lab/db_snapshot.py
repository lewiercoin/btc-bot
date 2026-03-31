from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from research_lab.constants import SQLITE_SOURCE_TABLES


def create_trial_snapshot(source_db_path: Path, snapshots_dir: Path, trial_id: str) -> Path:
    """Copies source SQLite DB to snapshots_dir/trial_id.db. Returns snapshot path."""

    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshots_dir / f"{trial_id}.db"
    shutil.copy2(source_db_path, snapshot_path)
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


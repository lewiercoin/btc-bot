from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from storage.db import connect, connect_readonly, init_db


def test_connect_sets_wal_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "btc_bot.db"
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"

    conn = connect(db_path)
    try:
        init_db(conn, schema_path)
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    finally:
        conn.close()

    assert str(journal_mode).lower() == "wal"


def test_connect_readonly_opens_existing_db_and_rejects_missing_file(tmp_path: Path) -> None:
    db_path = tmp_path / "btc_bot.db"
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"

    conn = connect(db_path)
    try:
        init_db(conn, schema_path)
    finally:
        conn.close()

    ro_conn = connect_readonly(db_path)
    try:
        row = ro_conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'bot_state'").fetchone()
    finally:
        ro_conn.close()

    assert row is not None

    with pytest.raises(sqlite3.OperationalError):
        connect_readonly(tmp_path / "missing.db")

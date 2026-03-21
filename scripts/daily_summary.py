from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from settings import load_settings
from storage.db import connect


def load_daily_metrics(conn: sqlite3.Connection, day: date) -> dict | None:
    row = conn.execute("SELECT * FROM daily_metrics WHERE date = ?", (day.isoformat(),)).fetchone()
    return dict(row) if row else None


def main() -> None:
    settings = load_settings()
    assert settings.storage is not None

    conn = connect(settings.storage.db_path)
    metrics = load_daily_metrics(conn, date.today())
    print(metrics or "No daily metrics yet.")


if __name__ == "__main__":
    main()

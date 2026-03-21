from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from settings import load_settings
from storage.db import connect


def _row_to_json(row: object) -> str:
    if row is None:
        return "null"
    if isinstance(row, dict):
        return json.dumps(row, default=str)
    return json.dumps(dict(row), default=str)


def main() -> None:
    settings = load_settings()
    assert settings.storage is not None
    conn = connect(settings.storage.db_path)

    print("=== COUNTS: candles by timeframe ===")
    rows = conn.execute(
        """
        SELECT timeframe, COUNT(*) AS cnt
        FROM candles
        GROUP BY timeframe
        ORDER BY timeframe
        """
    ).fetchall()
    for row in rows:
        print(f"{row['timeframe']}: {row['cnt']}")

    print("\n=== TIME RANGES ===")
    ranges = {
        "candles": ("open_time",),
        "funding": ("funding_time",),
        "open_interest": ("timestamp",),
        "aggtrade_buckets": ("bucket_time",),
    }
    for table, (column,) in ranges.items():
        row = conn.execute(
            f"SELECT MIN({column}) AS min_ts, MAX({column}) AS max_ts, COUNT(*) AS cnt FROM {table}"
        ).fetchone()
        print(f"{table}: count={row['cnt']} min={row['min_ts']} max={row['max_ts']}")

    print("\n=== BUCKET COUNTS ===")
    rows = conn.execute(
        """
        SELECT timeframe, COUNT(*) AS cnt
        FROM aggtrade_buckets
        GROUP BY timeframe
        ORDER BY timeframe
        """
    ).fetchall()
    for row in rows:
        print(f"{row['timeframe']}: {row['cnt']}")

    print("\n=== SAMPLES (3 rows each) ===")
    sample_queries = {
        "candles": "SELECT * FROM candles ORDER BY open_time DESC LIMIT 3",
        "funding": "SELECT * FROM funding ORDER BY funding_time DESC LIMIT 3",
        "open_interest": "SELECT * FROM open_interest ORDER BY timestamp DESC LIMIT 3",
        "aggtrade_buckets": "SELECT * FROM aggtrade_buckets ORDER BY bucket_time DESC LIMIT 3",
    }
    for name, query in sample_queries.items():
        print(f"\n{name}:")
        for row in conn.execute(query).fetchall():
            print(_row_to_json(row))


if __name__ == "__main__":
    main()

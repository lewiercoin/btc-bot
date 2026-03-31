"""Download full funding rate history via Binance API and import into SQLite.

Binance API returns max 1000 records per call (3/day = ~333 days per page).
Paginates via startTime/endTime. Commit-per-page for crash resilience.

Usage:
    python scripts/bootstrap_funding_from_api.py --start-date 2020-09-01 --end-date 2025-12-31
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time as _time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from settings import load_settings
from storage.db import connect, init_db

LOG = logging.getLogger(__name__)

API_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
PAGE_LIMIT = 1000


def fetch_funding_page(symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    url = f"{API_URL}?symbol={symbol}&startTime={start_ms}&endTime={end_ms}&limit={PAGE_LIMIT}"
    with urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def upsert_funding(conn: sqlite3.Connection, rows: list[dict]) -> int:
    if not rows:
        return 0
    conn.executemany(
        """INSERT INTO funding (symbol, funding_time, funding_rate)
           VALUES (:symbol, :funding_time, :funding_rate)
           ON CONFLICT(symbol, funding_time) DO UPDATE SET
               funding_rate=excluded.funding_rate""",
        rows,
    )
    return len(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Bootstrap funding rates from Binance API.")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start-date", required=True, help="First day (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Last day inclusive (YYYY-MM-DD)")
    parser.add_argument("--sleep-ms", type=int, default=300, help="Sleep between API calls (ms)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    start_dt = datetime.combine(date.fromisoformat(args.start_date), datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(date.fromisoformat(args.end_date), datetime.max.time(), tzinfo=timezone.utc)

    settings = load_settings()
    assert settings.storage is not None
    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)

    cursor_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    total = 0
    pages = 0

    while cursor_ms < end_ms:
        raw = fetch_funding_page(symbol, cursor_ms, end_ms)
        if not raw:
            LOG.info("No more funding data after %s",
                     datetime.fromtimestamp(cursor_ms / 1000, tz=timezone.utc).isoformat())
            break

        rows = []
        for item in raw:
            ts = datetime.fromtimestamp(int(item["fundingTime"]) / 1000, tz=timezone.utc)
            rows.append({
                "symbol": symbol,
                "funding_time": ts.isoformat(),
                "funding_rate": float(item["fundingRate"]),
            })

        if args.dry_run:
            LOG.info("Dry-run page %d: %d records (%s -> %s)",
                     pages + 1, len(rows),
                     rows[0]["funding_time"], rows[-1]["funding_time"])
        else:
            written = upsert_funding(conn, rows)
            conn.commit()
            LOG.info("Committed page %d: %d records (%s -> %s)",
                     pages + 1, written,
                     rows[0]["funding_time"], rows[-1]["funding_time"])

        total += len(rows)
        pages += 1

        last_ts_ms = max(int(item["fundingTime"]) for item in raw)
        cursor_ms = last_ts_ms + 1

        if len(raw) < PAGE_LIMIT:
            break

        _time.sleep(args.sleep_ms / 1000.0)

    conn.close()
    LOG.info("Done: %d total funding records in %d pages", total, pages)


if __name__ == "__main__":
    main()

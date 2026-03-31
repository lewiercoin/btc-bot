"""Download klines ZIPs from data.binance.vision and import into SQLite.

Downloads daily kline ZIPs for multiple timeframes (15m, 1h, 4h) and upserts
into the candles table. Commit-per-day for crash resilience.

Usage:
    python scripts/bootstrap_candles_from_zip.py --start-date 2020-09-01 --end-date 2025-12-31
"""
from __future__ import annotations

import argparse
import csv
import io
import logging
import sqlite3
import sys
import time as _time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from settings import load_settings
from storage.db import connect, init_db

LOG = logging.getLogger(__name__)

BASE_URL = "https://data.binance.vision/data/futures/um/daily/klines"
TIMEFRAMES = ("15m", "1h", "4h")


def download_zip(symbol: str, timeframe: str, day: date, max_retries: int = 5) -> bytes | None:
    url = f"{BASE_URL}/{symbol}/{timeframe}/{symbol}-{timeframe}-{day.isoformat()}.zip"
    for attempt in range(max_retries):
        try:
            with urlopen(url, timeout=60) as resp:
                return resp.read()
        except HTTPError as exc:
            if exc.code == 404:
                LOG.warning("Not found (404): %s — skipping.", url)
                return None
            raise
        except Exception as exc:
            wait = 3 * (attempt + 1)
            if attempt < max_retries - 1:
                LOG.warning("Download failed (attempt %d/%d): %s. Retrying in %ds...",
                            attempt + 1, max_retries, exc, wait)
                _time.sleep(wait)
            else:
                LOG.error("Download failed after %d attempts: %s", max_retries, exc)
                return None
    return None


def parse_klines(zip_bytes: bytes, symbol: str, timeframe: str) -> list[dict]:
    rows: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            with zf.open(name) as f:
                reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    if len(row) < 6:
                        continue
                    try:
                        open_time_ms = int(row[0])
                    except ValueError:
                        continue
                    ts = datetime.fromtimestamp(open_time_ms / 1000.0, tz=timezone.utc)
                    rows.append({
                        "symbol": symbol.upper(),
                        "timeframe": timeframe,
                        "open_time": ts.isoformat(),
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]),
                    })
    return rows


def upsert_candles(conn: sqlite3.Connection, rows: list[dict]) -> int:
    if not rows:
        return 0
    conn.executemany(
        """INSERT INTO candles (symbol, timeframe, open_time, open, high, low, close, volume)
           VALUES (:symbol, :timeframe, :open_time, :open, :high, :low, :close, :volume)
           ON CONFLICT(symbol, timeframe, open_time) DO UPDATE SET
               open=excluded.open, high=excluded.high, low=excluded.low,
               close=excluded.close, volume=excluded.volume""",
        rows,
    )
    return len(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Bootstrap candles from data.binance.vision kline ZIPs.")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start-date", required=True, help="First day (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Last day inclusive (YYYY-MM-DD)")
    parser.add_argument("--timeframes", default=",".join(TIMEFRAMES),
                        help=f"Comma-separated timeframes (default: {','.join(TIMEFRAMES)})")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    timeframes = [tf.strip() for tf in args.timeframes.split(",")]

    settings = load_settings()
    assert settings.storage is not None
    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)

    total = 0
    day = start
    while day <= end:
        day_total = 0
        for tf in timeframes:
            zip_bytes = download_zip(symbol, tf, day)
            if zip_bytes is None:
                continue
            rows = parse_klines(zip_bytes, symbol, tf)
            if not rows:
                continue
            if args.dry_run:
                LOG.info("Dry-run %s %s: %d candles", day.isoformat(), tf, len(rows))
            else:
                upsert_candles(conn, rows)
            day_total += len(rows)

        if day_total > 0 and not args.dry_run:
            conn.commit()
            LOG.info("Committed %s: %d candles across %s", day.isoformat(), day_total, timeframes)

        total += day_total
        day += timedelta(days=1)

    conn.close()
    LOG.info("Done: %d total candles across %s..%s", total, start.isoformat(), end.isoformat())


if __name__ == "__main__":
    main()

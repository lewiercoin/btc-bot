"""Download aggTrades ZIPs from data.binance.vision and import into SQLite.

Usage:
    python scripts/bootstrap_from_zip.py --start-date 2026-02-09 --end-date 2026-02-28
"""
from __future__ import annotations

import argparse
import csv
import io
import logging
import sqlite3
import sys
import tempfile
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.bootstrap_history import build_aggtrade_buckets, upsert_aggtrade_buckets
from settings import load_settings
from storage.db import connect, init_db

LOG = logging.getLogger(__name__)

BASE_URL = "https://data.binance.vision/data/futures/um/daily/aggTrades"


def download_zip(symbol: str, day: date) -> bytes | None:
    """Download a single day's aggTrades ZIP. Returns bytes or None if 404."""
    url = f"{BASE_URL}/{symbol}/{symbol}-aggTrades-{day.isoformat()}.zip"
    LOG.info("Downloading %s ...", url)
    try:
        with urlopen(url, timeout=120) as resp:
            return resp.read()
    except HTTPError as exc:
        if exc.code == 404:
            LOG.warning("Not found (404): %s — skipping.", url)
            return None
        raise


def parse_csv_trades(zip_bytes: bytes, symbol: str) -> list[dict]:
    """Parse aggTrades CSV from ZIP into list of trade dicts."""
    trades: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            with zf.open(name) as f:
                reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    # Columns: agg_trade_id, price, quantity, first_trade_id,
                    #          last_trade_id, transact_time, is_buyer_maker
                    if len(row) < 7:
                        continue
                    try:
                        ts_ms = int(row[5])
                    except ValueError:
                        continue  # header row
                    trades.append({
                        "event_time": datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc),
                        "qty": float(row[2]),
                        "is_buyer_maker": row[6].strip().lower() in ("true", "1"),
                    })
    return trades


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Bootstrap aggTrades from data.binance.vision ZIPs.")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start-date", required=True, help="First day to download (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Last day to download inclusive (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)

    settings = load_settings()
    assert settings.storage is not None
    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)

    total_buckets = 0
    total_trades = 0
    day = start

    while day <= end:
        zip_bytes = download_zip(symbol, day)
        if zip_bytes is None:
            day += timedelta(days=1)
            continue

        LOG.info("Parsing %s trades for %s ...", symbol, day.isoformat())
        trades = parse_csv_trades(zip_bytes, symbol)
        if not trades:
            LOG.warning("No trades parsed for %s", day.isoformat())
            day += timedelta(days=1)
            continue

        buckets_60s = build_aggtrade_buckets(trades, symbol=symbol, timeframe="60s")
        buckets_15m = build_aggtrade_buckets(trades, symbol=symbol, timeframe="15m")
        all_buckets = buckets_60s + buckets_15m

        if args.dry_run:
            LOG.info("Dry-run %s: %d trades -> %d buckets (60s=%d, 15m=%d)",
                     day.isoformat(), len(trades), len(all_buckets), len(buckets_60s), len(buckets_15m))
        else:
            written = upsert_aggtrade_buckets(conn, all_buckets)
            conn.commit()
            LOG.info("Committed %s: %d trades -> %d buckets (60s=%d, 15m=%d)",
                     day.isoformat(), len(trades), written, len(buckets_60s), len(buckets_15m))

        total_buckets += len(all_buckets)
        total_trades += len(trades)
        day += timedelta(days=1)

    conn.close()
    LOG.info("Done: %d total trades, %d total buckets across %s..%s",
             total_trades, total_buckets, start.isoformat(), end.isoformat())


if __name__ == "__main__":
    main()

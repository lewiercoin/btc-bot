"""Download aggTrades ZIPs from data.binance.vision and import into SQLite.

Usage:
    python scripts/bootstrap_from_zip.py --start-date 2026-02-09 --end-date 2026-02-28
    python scripts/bootstrap_from_zip.py --mode monthly --start-date 2024-04-01 --end-date 2025-12-31
"""
from __future__ import annotations

import argparse
import csv
import io
import logging
import sqlite3
import sys
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.bootstrap_history import build_aggtrade_buckets, upsert_aggtrade_buckets  # noqa: E402
from settings import load_settings  # noqa: E402
from storage.db import connect, init_db  # noqa: E402

LOG = logging.getLogger(__name__)

BASE_URL_DAILY = "https://data.binance.vision/data/futures/um/daily/aggTrades"
BASE_URL_MONTHLY = "https://data.binance.vision/data/futures/um/monthly/aggTrades"


def _download_zip(url: str, *, skip_label: str, max_retries: int = 5) -> bytes | None:
    """Download aggTrades ZIP file. Returns bytes or None if 404/final failure."""
    import time as _time

    LOG.info("Downloading %s ...", url)
    for attempt in range(max_retries):
        try:
            with urlopen(url, timeout=180) as resp:
                return resp.read()
        except HTTPError as exc:
            if exc.code == 404:
                LOG.warning("Not found (404): %s — skipping.", url)
                return None
            raise
        except Exception as exc:
            wait = 5 * (attempt + 1)
            if attempt < max_retries - 1:
                LOG.warning("Download failed (attempt %d/%d): %s. Retrying in %ds...",
                            attempt + 1, max_retries, exc, wait)
                _time.sleep(wait)
            else:
                LOG.error("Download failed after %d attempts: %s — %s.", max_retries, exc, skip_label)
                return None
    return None


def download_daily_zip(symbol: str, day: date, max_retries: int = 5) -> bytes | None:
    """Download a single day's aggTrades ZIP. Returns bytes or None if unavailable."""
    url = f"{BASE_URL_DAILY}/{symbol}/{symbol}-aggTrades-{day.isoformat()}.zip"
    return _download_zip(url, skip_label="skipping day", max_retries=max_retries)


def download_monthly_zip(symbol: str, year: int, month: int, max_retries: int = 5) -> bytes | None:
    """Download a single month's aggTrades ZIP. Returns bytes or None if unavailable."""
    url = f"{BASE_URL_MONTHLY}/{symbol}/{symbol}-aggTrades-{year}-{month:02d}.zip"
    return _download_zip(url, skip_label="skipping month", max_retries=max_retries)


def iter_month_starts(start: date, end: date) -> list[date]:
    """Return month starts covering the inclusive date interval."""
    month_starts: list[date] = []
    current = date(start.year, start.month, 1)
    stop = date(end.year, end.month, 1)
    while current <= stop:
        month_starts.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return month_starts


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


def _bucket_floor(ts: datetime, bucket_seconds: int) -> datetime:
    unix = int(ts.timestamp())
    floored = unix - (unix % bucket_seconds)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def _finalize_buckets(
    *,
    symbol: str,
    timeframe: str,
    grouped_volumes: dict[datetime, list[float]],
) -> list[dict]:
    buckets: list[dict] = []
    for bucket_time, volumes in grouped_volumes.items():
        taker_buy_volume = volumes[0]
        taker_sell_volume = volumes[1]
        total = taker_buy_volume + taker_sell_volume
        cvd = taker_buy_volume - taker_sell_volume
        tfi = 0.0 if total == 0 else cvd / total
        buckets.append(
            {
                "symbol": symbol.upper(),
                "bucket_time": bucket_time,
                "timeframe": timeframe,
                "taker_buy_volume": taker_buy_volume,
                "taker_sell_volume": taker_sell_volume,
                "tfi": tfi,
                "cvd": cvd,
            }
        )
    buckets.sort(key=lambda item: item["bucket_time"])
    return buckets


def parse_zip_trades_streaming(zip_bytes: bytes, symbol: str) -> tuple[int, list[dict], list[dict]]:
    """Stream CSV rows from ZIP and build 60s/15m buckets without materializing all trades."""
    grouped_60s: dict[datetime, list[float]] = defaultdict(lambda: [0.0, 0.0])
    grouped_15m: dict[datetime, list[float]] = defaultdict(lambda: [0.0, 0.0])
    trade_count = 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            with zf.open(name) as f:
                reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    if len(row) < 7:
                        continue
                    try:
                        ts_ms = int(row[5])
                        qty = float(row[2])
                    except ValueError:
                        continue

                    event_time = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                    is_buyer_maker = row[6].strip().lower() in ("true", "1")

                    bucket_60s = _bucket_floor(event_time, 60)
                    bucket_15m = _bucket_floor(event_time, 15 * 60)
                    index = 1 if is_buyer_maker else 0
                    grouped_60s[bucket_60s][index] += qty
                    grouped_15m[bucket_15m][index] += qty
                    trade_count += 1

    buckets_60s = _finalize_buckets(symbol=symbol, timeframe="60s", grouped_volumes=grouped_60s)
    buckets_15m = _finalize_buckets(symbol=symbol, timeframe="15m", grouped_volumes=grouped_15m)
    return trade_count, buckets_60s, buckets_15m


def process_zip_payload(
    *,
    conn: sqlite3.Connection,
    symbol: str,
    period_label: str,
    zip_bytes: bytes,
    dry_run: bool,
    mode: str,
) -> tuple[int, int]:
    """Parse, bucketize and optionally persist one ZIP payload."""
    LOG.info("Parsing %s trades for %s ...", symbol, period_label)
    if mode == "monthly":
        trade_count, buckets_60s, buckets_15m = parse_zip_trades_streaming(zip_bytes, symbol)
    else:
        trades = parse_csv_trades(zip_bytes, symbol)
        if not trades:
            LOG.warning("No trades parsed for %s", period_label)
            return 0, 0
        trade_count = len(trades)
        buckets_60s = build_aggtrade_buckets(trades, symbol=symbol, timeframe="60s")
        buckets_15m = build_aggtrade_buckets(trades, symbol=symbol, timeframe="15m")

    if trade_count == 0:
        LOG.warning("No trades parsed for %s", period_label)
        return 0, 0

    all_buckets = buckets_60s + buckets_15m

    if dry_run:
        LOG.info("Dry-run %s: %d trades -> %d buckets (60s=%d, 15m=%d)",
                 period_label, trade_count, len(all_buckets), len(buckets_60s), len(buckets_15m))
    else:
        written = upsert_aggtrade_buckets(conn, all_buckets)
        conn.commit()
        LOG.info("Committed %s: %d trades -> %d buckets (60s=%d, 15m=%d)",
                 period_label, trade_count, written, len(buckets_60s), len(buckets_15m))
    return trade_count, len(all_buckets)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Bootstrap aggTrades from data.binance.vision ZIPs.")
    parser.add_argument("--mode", choices=("daily", "monthly"), default="daily")
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

    if args.mode == "daily":
        day = start
        while day <= end:
            zip_bytes = download_daily_zip(symbol, day)
            if zip_bytes is None:
                day += timedelta(days=1)
                continue

            day_trades, day_buckets = process_zip_payload(
                conn=conn,
                symbol=symbol,
                period_label=day.isoformat(),
                zip_bytes=zip_bytes,
                dry_run=args.dry_run,
                mode=args.mode,
            )
            total_trades += day_trades
            total_buckets += day_buckets
            day += timedelta(days=1)
    else:
        month_starts = iter_month_starts(start, end)
        total_months = len(month_starts)
        for index, month_start in enumerate(month_starts, start=1):
            month_label = f"{month_start.year}-{month_start.month:02d}"
            LOG.info("Processing month %s (%d/%d)", month_label, index, total_months)
            zip_bytes = download_monthly_zip(symbol, month_start.year, month_start.month)
            if zip_bytes is None:
                continue

            month_trades, month_buckets = process_zip_payload(
                conn=conn,
                symbol=symbol,
                period_label=month_label,
                zip_bytes=zip_bytes,
                dry_run=args.dry_run,
                mode=args.mode,
            )
            total_trades += month_trades
            total_buckets += month_buckets

    conn.close()
    LOG.info("Done (%s mode): %d total trades, %d total buckets across %s..%s",
             args.mode, total_trades, total_buckets, start.isoformat(), end.isoformat())


if __name__ == "__main__":
    main()

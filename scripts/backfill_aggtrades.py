#!/usr/bin/env python3
"""Backfill aggtrade_buckets (15m) from data.binance.vision monthly aggTrades files.

Downloads a monthly zip (500MB-1GB), streams trades without loading into RAM,
aggregates into 15-minute buckets, and inserts via INSERT OR IGNORE (idempotent).

Usage (production server):
    # Fill gap 2026-03-28 to 2026-03-31 from March monthly file
    python scripts/backfill_aggtrades.py \\
        --db-path /home/btc-bot/btc-bot/storage/btc_bot.db \\
        --year-month 2026-03 \\
        --start-date 2026-03-28 --end-date 2026-03-31

    # Fill gap 2026-04-01 to 2026-04-17 from April monthly file
    python scripts/backfill_aggtrades.py \\
        --db-path /home/btc-bot/btc-bot/storage/btc_bot.db \\
        --year-month 2026-04 \\
        --start-date 2026-04-01 --end-date 2026-04-17

Dry-run (no writes):
    python scripts/backfill_aggtrades.py ... --dry-run
"""
from __future__ import annotations

import argparse
import csv
import io
import logging
import sqlite3
import tempfile
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

LOG = logging.getLogger(__name__)

_BASE_URL = (
    "https://data.binance.vision/data/futures/um/monthly/aggTrades"
    "/{symbol}/{symbol}-aggTrades-{year_month}.zip"
)
_BUCKET_SECONDS = 15 * 60
_BUCKET_MS = _BUCKET_SECONDS * 1000
_CHUNK_SIZE = 10_000
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024
_RETRY_COUNT = 3
_RETRY_SLEEP_S = 5.0

_COL_QUANTITY = 2
_COL_TIMESTAMP_MS = 5
_COL_IS_BUYER_MAKER = 6


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw.strip(), "%Y-%m-%d").date()


def _ms_to_bucket_iso(ts_ms: int) -> str:
    bucket_ms = (ts_ms // _BUCKET_MS) * _BUCKET_MS
    dt = datetime.fromtimestamp(bucket_ms / 1000.0, tz=timezone.utc)
    return dt.isoformat()


def _date_to_ms(d: date) -> int:
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


@dataclass
class _BucketAccum:
    bucket_time: str
    buy_vol: float = 0.0
    sell_vol: float = 0.0


def _query_last_cvd(conn: sqlite3.Connection, symbol: str, before_iso: str) -> float:
    row = conn.execute(
        """
        SELECT cvd FROM aggtrade_buckets
        WHERE symbol = ? AND timeframe = '15m' AND bucket_time < ?
        ORDER BY bucket_time DESC LIMIT 1
        """,
        (symbol, before_iso),
    ).fetchone()
    return float(row[0]) if row is not None else 0.0


def _insert_buckets(
    conn: sqlite3.Connection,
    buckets: list[tuple[str, str, str, float, float, float, float]],
    *,
    dry_run: bool,
) -> int:
    if dry_run or not buckets:
        return 0
    cur = conn.executemany(
        """
        INSERT OR IGNORE INTO aggtrade_buckets
            (symbol, bucket_time, timeframe, taker_buy_volume, taker_sell_volume, tfi, cvd)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        buckets,
    )
    return cur.rowcount


def _download_to_tempfile(url: str, tmp_path: Path) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, _RETRY_COUNT + 1):
        try:
            LOG.info("Downloading %s (attempt %d/%d) ...", url, attempt, _RETRY_COUNT)
            with urllib.request.urlopen(url, timeout=300) as resp:
                downloaded = 0
                with open(tmp_path, "wb") as f:
                    while True:
                        chunk = resp.read(_DOWNLOAD_CHUNK_BYTES)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded % (50 * 1024 * 1024) == 0:
                            LOG.info("  ... %.0f MB downloaded", downloaded / 1024 / 1024)
            LOG.info("Download complete: %.1f MB", tmp_path.stat().st_size / 1024 / 1024)
            return
        except Exception as exc:
            last_exc = exc
            LOG.warning(
                "Download attempt %d/%d failed: %s", attempt, _RETRY_COUNT, exc
            )
            if attempt < _RETRY_COUNT:
                time.sleep(_RETRY_SLEEP_S)
    raise RuntimeError(
        f"Failed to download after {_RETRY_COUNT} attempts: {url}"
    ) from last_exc


def backfill_aggtrades(
    db_path: Path,
    symbol: str,
    year_month: str,
    start: date | None,
    end: date | None,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    url = _BASE_URL.format(symbol=symbol, year_month=year_month)
    start_ms = _date_to_ms(start) if start is not None else None
    end_ms = _date_to_ms(end + timedelta(days=1)) if end is not None else None
    first_bucket_iso = _ms_to_bucket_iso(start_ms) if start_ms is not None else None

    LOG.info(
        "Starting aggTrade backfill | symbol=%s | year_month=%s | filter=%s -> %s | dry_run=%s",
        symbol,
        year_month,
        start,
        end,
        dry_run,
    )

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")

    running_cvd = 0.0
    if first_bucket_iso is not None and not dry_run:
        running_cvd = _query_last_cvd(conn, symbol, first_bucket_iso)
        LOG.info("CVD initialized from DB: %.4f (before %s)", running_cvd, first_bucket_iso)

    total_trades = 0
    total_inserted = 0
    current_bucket: _BucketAccum | None = None
    pending_buckets: list[tuple[str, str, str, float, float, float, float]] = []

    def _flush_bucket(accum: _BucketAccum, cvd: float) -> float:
        total = accum.buy_vol + accum.sell_vol
        tfi = (accum.buy_vol - accum.sell_vol) / total if total > 0.0 else 0.0
        new_cvd = cvd + (accum.buy_vol - accum.sell_vol)
        pending_buckets.append(
            (symbol, accum.bucket_time, "15m", accum.buy_vol, accum.sell_vol, tfi, new_cvd)
        )
        return new_cvd

    def _flush_pending(force: bool = False) -> int:
        nonlocal pending_buckets
        inserted = 0
        if len(pending_buckets) >= _CHUNK_SIZE or force:
            with conn:
                inserted = _insert_buckets(conn, pending_buckets, dry_run=dry_run)
            LOG.info(
                "  Flushed %d buckets → %d inserted%s",
                len(pending_buckets),
                inserted,
                " [dry-run]" if dry_run else "",
            )
            pending_buckets = []
        return inserted

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        _download_to_tempfile(url, tmp_path)

        with zipfile.ZipFile(tmp_path) as zf:
            csv_name = zf.namelist()[0]
            LOG.info("Processing %s ...", csv_name)
            with zf.open(csv_name) as raw_f:
                reader = csv.reader(io.TextIOWrapper(raw_f, encoding="utf-8"))
                for row in reader:
                    if len(row) < 7:
                        continue
                    ts_ms = int(row[_COL_TIMESTAMP_MS])

                    if start_ms is not None and ts_ms < start_ms:
                        continue
                    if end_ms is not None and ts_ms >= end_ms:
                        break

                    total_trades += 1
                    qty = float(row[_COL_QUANTITY])
                    is_buyer_maker = row[_COL_IS_BUYER_MAKER].strip().lower() == "true"
                    bucket_iso = _ms_to_bucket_iso(ts_ms)

                    if current_bucket is None:
                        current_bucket = _BucketAccum(bucket_time=bucket_iso)
                    elif current_bucket.bucket_time != bucket_iso:
                        running_cvd = _flush_bucket(current_bucket, running_cvd)
                        total_inserted += _flush_pending()
                        current_bucket = _BucketAccum(bucket_time=bucket_iso)

                    if is_buyer_maker:
                        current_bucket.sell_vol += qty
                    else:
                        current_bucket.buy_vol += qty

        if current_bucket is not None:
            running_cvd = _flush_bucket(current_bucket, running_cvd)
        total_inserted += _flush_pending(force=True)

    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        conn.close()

    LOG.info(
        "aggTrade backfill complete | trades=%d | buckets_inserted=%d",
        total_trades,
        total_inserted,
    )
    return {
        "total_trades": total_trades,
        "total_inserted": total_inserted,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill aggtrade_buckets (15m) from data.binance.vision monthly files."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("/home/btc-bot/btc-bot/storage/btc_bot.db"),
        help="Path to btc_bot.db (default: production path)",
    )
    parser.add_argument(
        "--year-month",
        required=True,
        help="Monthly file to download, e.g. 2026-03",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Filter: only process trades from this date (YYYY-MM-DD), inclusive",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Filter: only process trades up to this date (YYYY-MM-DD), inclusive",
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download and parse but do not write to DB",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    args = _build_parser().parse_args(argv)
    start = _parse_date(args.start_date) if args.start_date else None
    end = _parse_date(args.end_date) if args.end_date else None
    if start is not None and end is not None and end < start:
        LOG.error("--end-date must be >= --start-date")
        return 1
    backfill_aggtrades(
        args.db_path,
        args.symbol,
        args.year_month,
        start,
        end,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

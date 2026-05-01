#!/usr/bin/env python3
"""Backfill open_interest table from data.binance.vision daily metrics files.

Downloads daily zip files for each date in the requested range, streams rows
without loading the full file into memory, and inserts via INSERT OR IGNORE
(idempotent — safe to run multiple times).

Usage (production server):
    python scripts/backfill_oi.py \\
        --db-path /home/btc-bot/btc-bot/storage/btc_bot.db \\
        --start-date 2025-06-05 --end-date 2026-01-01

Dry-run (no writes):
    python scripts/backfill_oi.py ... --dry-run
"""
from __future__ import annotations

import argparse
import csv
import io
import logging
import sqlite3
import time
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

LOG = logging.getLogger(__name__)

_BASE_URL = (
    "https://data.binance.vision/data/futures/um/daily/metrics"
    "/{symbol}/{symbol}-metrics-{date}.zip"
)
_CHUNK_SIZE = 10_000
_RETRY_COUNT = 3
_RETRY_SLEEP_S = 5.0
_REQUEST_SLEEP_S = 0.5


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw.strip(), "%Y-%m-%d").date()


def _date_range(start: date, end: date) -> list[date]:
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _download_zip(url: str) -> bytes:
    last_exc: Exception | None = None
    for attempt in range(1, _RETRY_COUNT + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return resp.read()
        except Exception as exc:
            last_exc = exc
            LOG.warning(
                "Download attempt %d/%d failed | url=%s | error=%s",
                attempt,
                _RETRY_COUNT,
                url,
                exc,
            )
            if attempt < _RETRY_COUNT:
                time.sleep(_RETRY_SLEEP_S)
    raise RuntimeError(
        f"Failed to download after {_RETRY_COUNT} attempts: {url}"
    ) from last_exc


def _parse_create_time(raw: str) -> str:
    dt = datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )
    return dt.isoformat()


def _stream_rows_from_zip(
    zip_bytes: bytes,
    symbol: str,
) -> list[tuple[str, str, float]]:
    rows: list[tuple[str, str, float]] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_name = zf.namelist()[0]
        with zf.open(csv_name) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
            for raw_row in reader:
                ts_iso = _parse_create_time(raw_row["create_time"])
                oi = float(raw_row["sum_open_interest"])
                rows.append((symbol, ts_iso, oi))
    return rows


def _insert_chunk(
    conn: sqlite3.Connection,
    rows: list[tuple[str, str, float]],
    *,
    dry_run: bool,
) -> int:
    if dry_run or not rows:
        return 0
    cur = conn.executemany(
        "INSERT OR IGNORE INTO open_interest (symbol, timestamp, oi_value) VALUES (?, ?, ?)",
        rows,
    )
    return cur.rowcount


def backfill_oi(
    db_path: Path,
    symbol: str,
    start: date,
    end: date,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    dates = _date_range(start, end)
    LOG.info(
        "Starting OI backfill | symbol=%s | %s -> %s | days=%d | dry_run=%s",
        symbol,
        start,
        end,
        len(dates),
        dry_run,
    )
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    total_parsed = 0
    total_inserted = 0
    skipped = 0
    try:
        for d in dates:
            date_str = d.strftime("%Y-%m-%d")
            url = _BASE_URL.format(symbol=symbol, date=date_str)
            try:
                zip_bytes = _download_zip(url)
            except RuntimeError as exc:
                LOG.warning("Skipping date %s: %s", date_str, exc)
                skipped += 1
                time.sleep(_REQUEST_SLEEP_S)
                continue

            rows = _stream_rows_from_zip(zip_bytes, symbol)
            total_parsed += len(rows)
            day_inserted = 0

            for i in range(0, len(rows), _CHUNK_SIZE):
                chunk = rows[i : i + _CHUNK_SIZE]
                with conn:
                    day_inserted += _insert_chunk(conn, chunk, dry_run=dry_run)

            total_inserted += day_inserted
            LOG.info(
                "  %s | parsed=%d | inserted=%d%s",
                date_str,
                len(rows),
                day_inserted,
                " [dry-run]" if dry_run else "",
            )
            time.sleep(_REQUEST_SLEEP_S)
    finally:
        conn.close()

    LOG.info(
        "OI backfill complete | parsed=%d | inserted=%d | skipped_dates=%d",
        total_parsed,
        total_inserted,
        skipped,
    )
    return {
        "total_parsed": total_parsed,
        "total_inserted": total_inserted,
        "skipped_dates": skipped,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill open_interest from data.binance.vision daily metrics."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("/home/btc-bot/btc-bot/storage/btc_bot.db"),
        help="Path to btc_bot.db (default: production path)",
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="Start date inclusive (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="End date inclusive (YYYY-MM-DD)",
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
    start = _parse_date(args.start_date)
    end = _parse_date(args.end_date)
    if end < start:
        LOG.error("--end-date must be >= --start-date")
        return 1
    backfill_oi(args.db_path, args.symbol, start, end, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

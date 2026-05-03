#!/usr/bin/env python3
"""Backfill force_orders from Tardis.dev free liquidation samples.

Tardis provides free liquidation data for the 1st of each month, Jan 2020 – Dec 2024
(60 files total). Files must be downloaded locally before running this script.

Download command (run once on server):
    mkdir -p /tmp/tardis_liquidations
    for year in 2020 2021 2022 2023 2024; do
      for month in 01 02 03 04 05 06 07 08 09 10 11 12; do
        FILE="/tmp/tardis_liquidations/binance-futures_liquidations_${year}_${month}_01_BTCUSDT.csv.gz"
        [ -f "$FILE" ] && continue
        curl -sf "https://datasets.tardis.dev/v1/binance-futures/liquidations/${year}/${month}/01/BTCUSDT.csv.gz" \
          -o "$FILE" && echo "OK: ${year}-${month}-01" || echo "FAIL: ${year}-${month}-01"
        sleep 0.5
      done
    done

Schema (verified 2026-05-03):
    exchange,symbol,timestamp,local_timestamp,id,side,price,amount
    timestamp = Unix microseconds → divide by 1000 → Unix ms → ISO-8601 UTC
    side      = lowercase "buy"/"sell" → .upper() → "BUY"/"SELL"
    amount    = BTC quantity (stored as qty)
    price     = USDT price

Note: Data is tick-level (individual liquidation events). Cross-source proxy:
feature engine counts events per 60s using relative rate vs rolling history
(avg + 2σ), so calibration adapts to source-specific density.

Usage:
    python scripts/backfill_force_orders_tardis.py \\
        --source-dir /tmp/tardis_liquidations \\
        --db-path /home/btc-bot/btc-bot/storage/btc_bot.db \\
        --dry-run

    python scripts/backfill_force_orders_tardis.py \\
        --source-dir /tmp/tardis_liquidations \\
        --db-path /home/btc-bot/btc-bot/storage/btc_bot.db
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

LOG = logging.getLogger(__name__)

_SYMBOL = "BTCUSDT"
_COL_TIMESTAMP_US = "timestamp"
_COL_SIDE = "side"
_COL_PRICE = "price"
_COL_AMOUNT = "amount"
_CHUNK_SIZE = 500


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _us_to_iso(ts_us: int) -> str:
    dt = datetime.fromtimestamp(ts_us / 1_000_000.0, tz=timezone.utc)
    return dt.isoformat()


_TARDIS_CUTOFF_ISO = "2025-01-01T00:00:00+00:00"


def _query_watermark(conn: sqlite3.Connection, symbol: str) -> str | None:
    """Returns MAX(event_time) already in DB for this symbol before 2025-01-01, or None.

    The cutoff prevents live-data rows (2026+) from acting as a watermark that
    would block all historical Tardis rows (2020-2024).
    """
    row = conn.execute(
        "SELECT MAX(event_time) FROM force_orders WHERE symbol = ? AND event_time < ?",
        (symbol, _TARDIS_CUTOFF_ISO),
    ).fetchone()
    return row[0] if row and row[0] else None


def _insert_events(
    conn: sqlite3.Connection,
    rows: list[tuple[str, str, str, float, float]],
    *,
    dry_run: bool,
) -> int:
    if dry_run or not rows:
        return 0
    conn.executemany(
        "INSERT INTO force_orders (symbol, event_time, side, qty, price) VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)


def _list_files(source_dir: Path, symbol: str) -> list[Path]:
    pattern = f"*{symbol}*.csv.gz"
    files = sorted(source_dir.glob(pattern))
    return files


def backfill_tardis(
    source_dir: Path,
    db_path: Path,
    symbol: str,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    files = _list_files(source_dir, symbol)
    if not files:
        LOG.error("No .csv.gz files found in %s matching symbol %s", source_dir, symbol)
        return {"files_processed": 0, "total_parsed": 0, "total_inserted": 0}

    LOG.info(
        "Starting Tardis force_orders backfill | symbol=%s | files=%d | dry_run=%s",
        symbol,
        len(files),
        dry_run,
    )

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")

    watermark = _query_watermark(conn, symbol)
    LOG.info("Watermark (MAX event_time in DB): %s", watermark)

    total_parsed = 0
    total_inserted = 0
    files_processed = 0

    for gz_path in files:
        LOG.info("Processing %s ...", gz_path.name)
        file_parsed = 0
        file_inserted = 0
        pending: list[tuple[str, str, str, float, float]] = []

        try:
            with gzip.open(gz_path, "rt", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts_us = int(row[_COL_TIMESTAMP_US])
                    event_time = _us_to_iso(ts_us)

                    if watermark is not None and event_time <= watermark:
                        continue

                    side = row[_COL_SIDE].strip().upper()
                    if side not in ("BUY", "SELL"):
                        LOG.warning("Unexpected side value '%s' — skipping row", side)
                        continue

                    qty = float(row[_COL_AMOUNT])
                    price = float(row[_COL_PRICE])

                    pending.append((symbol, event_time, side, qty, price))
                    file_parsed += 1

                    if len(pending) >= _CHUNK_SIZE:
                        with conn:
                            inserted = _insert_events(conn, pending, dry_run=dry_run)
                        file_inserted += inserted
                        pending = []

            if pending:
                with conn:
                    inserted = _insert_events(conn, pending, dry_run=dry_run)
                file_inserted += inserted

        except Exception as exc:
            LOG.error("Error processing %s: %s", gz_path.name, exc)
            conn.close()
            raise

        total_parsed += file_parsed
        total_inserted += file_inserted
        files_processed += 1
        LOG.info(
            "  %s → parsed=%d inserted=%d%s",
            gz_path.name,
            file_parsed,
            file_inserted,
            " [dry-run]" if dry_run else "",
        )

    conn.close()
    LOG.info(
        "Tardis backfill complete | files=%d | total_parsed=%d | total_inserted=%d",
        files_processed,
        total_parsed,
        total_inserted,
    )
    return {
        "files_processed": files_processed,
        "total_parsed": total_parsed,
        "total_inserted": total_inserted,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill force_orders from local Tardis liquidation .csv.gz files."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("/tmp/tardis_liquidations"),
        help="Directory containing downloaded .csv.gz files (default: /tmp/tardis_liquidations)",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("/home/btc-bot/btc-bot/storage/btc_bot.db"),
        help="Path to btc_bot.db (default: production path)",
    )
    parser.add_argument("--symbol", default=_SYMBOL)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files and log counts but do not write to DB",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    args = _build_parser().parse_args(argv)

    if not args.source_dir.is_dir():
        LOG.error("--source-dir does not exist: %s", args.source_dir)
        return 1
    if not args.db_path.exists() and not args.dry_run:
        LOG.error("--db-path does not exist: %s", args.db_path)
        return 1

    backfill_tardis(
        args.source_dir,
        args.db_path,
        args.symbol,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

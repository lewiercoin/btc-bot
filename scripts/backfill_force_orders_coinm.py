#!/usr/bin/env python3
"""Backfill force_orders from Binance COIN-M liquidationSnapshot daily files.

Data source: data.binance.vision/data/futures/cm/daily/liquidationSnapshot/BTCUSD_PERP/
Available range (confirmed 2026-05-03): 2023-06-25 → 2024-10-14 (472 daily files)

Schema (verified 2026-05-03):
    time,side,order_type,time_in_force,original_quantity,price,average_price,
    order_status,last_fill_quantity,accumulated_fill_quantity
    time              = Unix ms → ISO-8601 UTC
    side              = "BUY"/"SELL" — direct (no transform needed)
    original_quantity = contracts (1 contract = 100 USD) → BTC via qty*100/avg_price
    average_price     = USD price (stored as price)

Cross-market proxy note: COIN-M (BTC-margined) liquidations are used as a proxy
for USDM (BTCUSDT). The feature engine uses relative event rate (events per 60s vs
rolling history avg+2σ), so the calibration adapts to COIN-M density. Absolute qty
is stored but does not affect spike detection.

Usage:
    # Dry-run: 3 days
    python scripts/backfill_force_orders_coinm.py \\
        --db-path /home/btc-bot/btc-bot/storage/btc_bot.db \\
        --start-date 2023-06-25 --end-date 2023-06-28 \\
        --dry-run

    # Live run: full range
    python scripts/backfill_force_orders_coinm.py \\
        --db-path /home/btc-bot/btc-bot/storage/btc_bot.db \\
        --start-date 2023-06-25 --end-date 2024-10-14
"""
from __future__ import annotations

import argparse
import csv
import io
import logging
import sqlite3
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

LOG = logging.getLogger(__name__)

_BASE_URL = (
    "https://data.binance.vision/data/futures/cm/daily/liquidationSnapshot"
    "/BTCUSD_PERP/BTCUSD_PERP-liquidationSnapshot-{date_str}.zip"
)
_TARGET_SYMBOL = "BTCUSDT"
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024
_RETRY_COUNT = 3
_RETRY_SLEEP_S = 5.0
_CHUNK_SIZE = 500

_COL_TIME_MS = "time"
_COL_SIDE = "side"
_COL_ORIG_QTY = "original_quantity"
_COL_AVG_PRICE = "average_price"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw.strip(), "%Y-%m-%d").date()


def _ms_to_iso(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    return dt.isoformat()


def _day_has_data(conn: sqlite3.Connection, symbol: str, date_str: str) -> bool:
    """Returns True if force_orders already contains any rows for this symbol on this date.

    Used for per-day idempotency: skips days that already have data (from any source),
    so COIN-M does not duplicate Tardis-covered days (monthly 1st) and correctly
    resumes after a partial run.
    """
    next_day = (
        datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y-%m-%d")
    row = conn.execute(
        """
        SELECT COUNT(*) FROM force_orders
        WHERE symbol = ?
          AND event_time >= ?
          AND event_time < ?
        """,
        (symbol, f"{date_str}T00:00:00+00:00", f"{next_day}T00:00:00+00:00"),
    ).fetchone()
    return (row[0] if row else 0) > 0


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


def _download_to_tempfile(url: str, tmp_path: Path) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, _RETRY_COUNT + 1):
        try:
            LOG.info("Downloading %s (attempt %d/%d) ...", url, attempt, _RETRY_COUNT)
            with urllib.request.urlopen(url, timeout=120) as resp:
                downloaded = 0
                with open(tmp_path, "wb") as f:
                    while True:
                        chunk = resp.read(_DOWNLOAD_CHUNK_BYTES)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
            LOG.info("Download complete: %.1f KB", tmp_path.stat().st_size / 1024)
            return
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                raise  # propagate non-retryable HTTP errors; caller handles 404 as missing
            last_exc = exc
            LOG.warning("Download attempt %d/%d failed: %s", attempt, _RETRY_COUNT, exc)
            if attempt < _RETRY_COUNT:
                time.sleep(_RETRY_SLEEP_S)
        except Exception as exc:
            last_exc = exc
            LOG.warning("Download attempt %d/%d failed: %s", attempt, _RETRY_COUNT, exc)
            if attempt < _RETRY_COUNT:
                time.sleep(_RETRY_SLEEP_S)
    raise RuntimeError(
        f"Failed to download after {_RETRY_COUNT} attempts: {url}"
    ) from last_exc


def _process_zip(
    tmp_path: Path,
    watermark: str | None,
    symbol: str,
    conn: sqlite3.Connection,
    *,
    dry_run: bool,
) -> tuple[int, int]:
    """Returns (parsed, inserted) for one daily ZIP."""
    parsed = 0
    inserted = 0
    pending: list[tuple[str, str, str, float, float]] = []

    with zipfile.ZipFile(tmp_path) as zf:
        csv_name = zf.namelist()[0]
        with zf.open(csv_name) as raw_f:
            reader = csv.DictReader(io.TextIOWrapper(raw_f, encoding="utf-8"))
            for row in reader:
                ts_ms = int(row[_COL_TIME_MS])
                event_time = _ms_to_iso(ts_ms)

                if watermark is not None and event_time <= watermark:
                    continue

                side = row[_COL_SIDE].strip().upper()
                if side not in ("BUY", "SELL"):
                    LOG.warning("Unexpected side value '%s' — skipping row", side)
                    continue

                orig_qty = float(row[_COL_ORIG_QTY])
                avg_price = float(row[_COL_AVG_PRICE])
                if avg_price <= 0.0:
                    LOG.warning("avg_price=0 for row at %s — skipping", event_time)
                    continue

                qty_btc = orig_qty * 100.0 / avg_price
                price = avg_price

                pending.append((symbol, event_time, side, qty_btc, price))
                parsed += 1

                if len(pending) >= _CHUNK_SIZE:
                    with conn:
                        inserted += _insert_events(conn, pending, dry_run=dry_run)
                    pending = []

    if pending:
        with conn:
            inserted += _insert_events(conn, pending, dry_run=dry_run)

    return parsed, inserted


def backfill_coinm(
    db_path: Path,
    start: date,
    end: date,
    symbol: str,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    LOG.info(
        "Starting COIN-M force_orders backfill | symbol=%s | range=%s → %s | dry_run=%s",
        symbol,
        start,
        end,
        dry_run,
    )

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")

    total_parsed = 0
    total_inserted = 0
    days_ok = 0
    days_skipped = 0
    days_missing = 0
    days_error = 0

    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        url = _BASE_URL.format(date_str=date_str)

        if not dry_run and _day_has_data(conn, symbol, date_str):
            LOG.info("  %s → SKIP (data already present)", date_str)
            days_skipped += 1
            current += timedelta(days=1)
            continue

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            try:
                _download_to_tempfile(url, tmp_path)
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 404):
                    LOG.info("  %s → %d (no data for this date)", date_str, exc.code)
                    days_missing += 1
                    current += timedelta(days=1)
                    continue
                raise

            parsed, inserted = _process_zip(
                tmp_path, None, symbol, conn, dry_run=dry_run
            )
            total_parsed += parsed
            total_inserted += inserted
            days_ok += 1
            LOG.info(
                "  %s → parsed=%d inserted=%d%s",
                date_str,
                parsed,
                inserted,
                " [dry-run]" if dry_run else "",
            )

        except Exception as exc:
            LOG.error("  %s → ERROR: %s", date_str, exc)
            days_error += 1
            if days_error >= 10:
                LOG.error("Too many errors (%d) — aborting", days_error)
                conn.close()
                raise

        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

        current += timedelta(days=1)

    conn.close()
    LOG.info(
        "COIN-M backfill complete | days_ok=%d | days_skipped=%d | days_missing=%d"
        " | days_error=%d | total_parsed=%d | total_inserted=%d",
        days_ok,
        days_skipped,
        days_missing,
        days_error,
        total_parsed,
        total_inserted,
    )
    return {
        "days_ok": days_ok,
        "days_skipped": days_skipped,
        "days_missing": days_missing,
        "days_error": days_error,
        "total_parsed": total_parsed,
        "total_inserted": total_inserted,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill force_orders from Binance COIN-M liquidationSnapshot daily ZIPs."
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
        help="First date to backfill (YYYY-MM-DD), inclusive",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="Last date to backfill (YYYY-MM-DD), inclusive",
    )
    parser.add_argument("--symbol", default=_TARGET_SYMBOL)
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
    if not args.db_path.exists() and not args.dry_run:
        LOG.error("--db-path does not exist: %s", args.db_path)
        return 1
    backfill_coinm(
        args.db_path,
        start,
        end,
        args.symbol,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Download OI from data.binance.vision metrics ZIPs and import into SQLite.

The metrics CSV contains sum_open_interest at 5-minute intervals — the same data
as the openInterestHist API, but without the 27-day lookback limit.

Usage:
    python scripts/bootstrap_oi_from_zip.py --start-date 2026-01-01 --end-date 2026-03-01
"""
from __future__ import annotations

import argparse
import csv
import io
import logging
import sqlite3
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.bootstrap_history import upsert_open_interest
from settings import load_settings
from storage.db import connect, init_db

LOG = logging.getLogger(__name__)

BASE_URL = "https://data.binance.vision/data/futures/um/daily/metrics"


def download_zip(symbol: str, day: date, max_retries: int = 5) -> bytes | None:
    import time as _time
    url = f"{BASE_URL}/{symbol}/{symbol}-metrics-{day.isoformat()}.zip"
    LOG.info("Downloading %s ...", url)
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
                LOG.warning("Download failed (attempt %d/%d): %s. Retrying in %ds...", attempt + 1, max_retries, exc, wait)
                _time.sleep(wait)
            else:
                LOG.error("Download failed after %d attempts: %s", max_retries, exc)
                return None


def parse_oi_from_metrics(zip_bytes: bytes, symbol: str) -> list[dict]:
    """Extract OI rows from metrics CSV."""
    rows: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            with zf.open(name) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                for record in reader:
                    try:
                        ts = datetime.strptime(record["create_time"], "%Y-%m-%d %H:%M:%S")
                        ts = ts.replace(tzinfo=timezone.utc)
                        oi_value = float(record["sum_open_interest"])
                    except (KeyError, ValueError):
                        continue
                    rows.append({
                        "symbol": symbol.upper(),
                        "timestamp": ts,
                        "oi_value": oi_value,
                    })
    return rows


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Bootstrap OI from data.binance.vision metrics ZIPs.")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start-date", required=True, help="First day (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Last day inclusive (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)

    settings = load_settings()
    assert settings.storage is not None
    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)

    total_rows = 0
    day = start

    while day <= end:
        zip_bytes = download_zip(symbol, day)
        if zip_bytes is None:
            day += timedelta(days=1)
            continue

        rows = parse_oi_from_metrics(zip_bytes, symbol)
        if not rows:
            LOG.warning("No OI rows for %s", day.isoformat())
            day += timedelta(days=1)
            continue

        if args.dry_run:
            LOG.info("Dry-run %s: %d OI rows", day.isoformat(), len(rows))
        else:
            written = upsert_open_interest(conn, rows)
            conn.commit()
            LOG.info("Committed %s: %d OI rows", day.isoformat(), written)

        total_rows += len(rows)
        day += timedelta(days=1)

    conn.close()
    LOG.info("Done: %d total OI rows across %s..%s", total_rows, start.isoformat(), end.isoformat())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Migrate recent CVD history from research lab to production database.

Migrates last 7 days of CVD/TFI data to enable immediate signal generation.
Joins aggtrade_buckets with candles to get price_close.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def migrate_cvd_from_research_lab(
    research_db_path: Path,
    production_db_path: Path,
    symbol: str,
    bars_limit: int = 50,
) -> int:
    """Migrate CVD data from research lab DB to production DB.

    Args:
        research_db_path: Path to research lab database
        production_db_path: Path to production database
        symbol: Symbol to migrate (e.g., 'ETHUSDT')
        bars_limit: Number of most recent bars to migrate (default: 50)

    Returns:
        Number of rows migrated
    """
    print(f"Migrating {symbol} CVD data from {research_db_path.name} to production...")

    # Connect to both databases
    research_conn = sqlite3.connect(research_db_path)
    production_conn = sqlite3.connect(production_db_path)

    try:
        # Get current timestamp for captured_at
        captured_at = datetime.now(timezone.utc).isoformat()

        # Count existing rows in production for this symbol
        cursor = production_conn.execute(
            "SELECT COUNT(*) FROM cvd_price_history WHERE symbol = ? AND timeframe = '15m'",
            (symbol,)
        )
        existing_count = cursor.fetchone()[0]
        print(f"  Existing {symbol} CVD rows in production: {existing_count}")

        # Count rows in research lab (get most recent N bars)
        cursor = research_conn.execute(
            """SELECT COUNT(*)
               FROM aggtrade_buckets
               WHERE symbol = ? AND timeframe = '15m'""",
            (symbol,)
        )
        total_count = cursor.fetchone()[0]
        print(f"  Found {total_count} total rows in research lab for {symbol}")

        if total_count == 0:
            print(f"  ⚠ No data found for {symbol} in research lab")
            return 0

        # Get timestamp range from research lab (last N bars)
        cursor = research_conn.execute(
            """SELECT
                datetime(MIN(bucket_time)) as oldest,
                datetime(MAX(bucket_time)) as newest
               FROM (
                   SELECT bucket_time
                   FROM aggtrade_buckets
                   WHERE symbol = ? AND timeframe = '15m'
                   ORDER BY bucket_time DESC
                   LIMIT ?
               )""",
            (symbol, bars_limit)
        )
        oldest, newest = cursor.fetchone()
        print(f"  Migrating last {bars_limit} bars: {oldest} → {newest}")

        # Migrate data with schema conversion
        # Join aggtrade_buckets with candles to get price_close
        production_conn.execute("BEGIN TRANSACTION")

        cursor = research_conn.execute(
            """SELECT
                   a.symbol,
                   a.timeframe,
                   a.bucket_time as bar_time,
                   c.close as price_close,
                   a.cvd,
                   a.tfi
               FROM (
                   SELECT symbol, timeframe, bucket_time, cvd, tfi
                   FROM aggtrade_buckets
                   WHERE symbol = ? AND timeframe = '15m'
                   ORDER BY bucket_time DESC
                   LIMIT ?
               ) a
               JOIN candles c ON
                   a.symbol = c.symbol
                   AND a.timeframe = c.timeframe
                   AND a.bucket_time = c.open_time
               ORDER BY a.bucket_time""",
            (symbol, bars_limit)
        )

        rows_inserted = 0
        batch = []
        batch_size = 5000

        for row in cursor:
            symbol_val, timeframe, bar_time, price_close, cvd, tfi = row
            batch.append((symbol_val, timeframe, bar_time, price_close, cvd, tfi, "backfill", captured_at))

            if len(batch) >= batch_size:
                production_conn.executemany(
                    """INSERT OR IGNORE INTO cvd_price_history
                       (symbol, timeframe, bar_time, price_close, cvd, tfi, source, captured_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    batch
                )
                rows_inserted += len(batch)
                batch = []
                print(f"  Migrated {rows_inserted:,} rows...", end="\r")

        # Insert remaining rows
        if batch:
            production_conn.executemany(
                """INSERT OR IGNORE INTO cvd_price_history
                   (symbol, timeframe, bar_time, price_close, cvd, tfi, source, captured_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                batch
            )
            rows_inserted += len(batch)

        production_conn.commit()

        # Verify migration
        cursor = production_conn.execute(
            "SELECT COUNT(*) FROM cvd_price_history WHERE symbol = ? AND timeframe = '15m'",
            (symbol,)
        )
        final_count = cursor.fetchone()[0]
        newly_inserted = final_count - existing_count

        print(f"  ✅ Migration complete: {newly_inserted:,} new rows added (total: {final_count:,})")

        # Verify date range in production
        cursor = production_conn.execute(
            """SELECT
                datetime(MIN(bar_time)) as oldest,
                datetime(MAX(bar_time)) as newest
               FROM cvd_price_history
               WHERE symbol = ? AND timeframe = '15m'""",
            (symbol,)
        )
        prod_oldest, prod_newest = cursor.fetchone()
        print(f"  Production date range: {prod_oldest} → {prod_newest}")

        return newly_inserted

    finally:
        research_conn.close()
        production_conn.close()


def main() -> int:
    """Main migration entry point."""
    production_db = PROJECT_ROOT / "storage" / "btc_bot.db"

    migrations = [
        {
            "research_db": PROJECT_ROOT / "research_lab" / "snapshots" / "ethusdt_2022_2026_dataset_v1.db",
            "symbol": "ETHUSDT",
        },
        {
            "research_db": PROJECT_ROOT / "research_lab" / "snapshots" / "replay-run-sol-historical-2022-2026.db",
            "symbol": "SOLUSDT",
        },
    ]

    total_migrated = 0
    bars_limit = 50  # Migrate last 50 bars (more than 30-bar requirement)

    print("=" * 80)
    print(f"CVD DATA MIGRATION: Research Lab → Production (last {bars_limit} bars)")
    print("=" * 80)
    print()

    for migration in migrations:
        research_db = migration["research_db"]
        symbol = migration["symbol"]

        if not research_db.exists():
            print(f"⚠ Research DB not found: {research_db}")
            continue

        rows = migrate_cvd_from_research_lab(research_db, production_db, symbol, bars_limit)
        total_migrated += rows
        print()

    print("=" * 80)
    print(f"MIGRATION COMPLETE: {total_migrated:,} total rows migrated")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())

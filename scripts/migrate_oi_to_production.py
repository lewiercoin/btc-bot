#!/usr/bin/env python3
"""Migrate historical OI data from research lab to production database.

Converts research lab `open_interest` table to production `oi_samples` schema.
Adds source='backfill' and captured_at=NOW() for all migrated rows.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def migrate_oi_from_research_lab(
    research_db_path: Path,
    production_db_path: Path,
    symbol: str,
) -> int:
    """Migrate OI data from research lab DB to production DB.

    Args:
        research_db_path: Path to research lab database
        production_db_path: Path to production database
        symbol: Symbol to migrate (e.g., 'ETHUSDT')

    Returns:
        Number of rows migrated
    """
    print(f"Migrating {symbol} OI data from {research_db_path.name} to production...")

    # Connect to both databases
    research_conn = sqlite3.connect(research_db_path)
    production_conn = sqlite3.connect(production_db_path)

    try:
        # Get current timestamp for captured_at
        captured_at = datetime.now(timezone.utc).isoformat()

        # Count existing rows in production for this symbol
        cursor = production_conn.execute(
            "SELECT COUNT(*) FROM oi_samples WHERE symbol = ?",
            (symbol,)
        )
        existing_count = cursor.fetchone()[0]
        print(f"  Existing {symbol} rows in production: {existing_count}")

        # Count rows in research lab
        cursor = research_conn.execute(
            "SELECT COUNT(*) FROM open_interest WHERE symbol = ?",
            (symbol,)
        )
        research_count = cursor.fetchone()[0]
        print(f"  Found {research_count} rows in research lab for {symbol}")

        if research_count == 0:
            print(f"  ⚠ No data found for {symbol} in research lab")
            return 0

        # Get timestamp range from research lab
        cursor = research_conn.execute(
            """SELECT
                datetime(MIN(timestamp)) as oldest,
                datetime(MAX(timestamp)) as newest
               FROM open_interest
               WHERE symbol = ?""",
            (symbol,)
        )
        oldest, newest = cursor.fetchone()
        print(f"  Research lab date range: {oldest} → {newest}")

        # Migrate data with schema conversion
        # INSERT OR IGNORE to skip duplicates (same symbol + timestamp)
        production_conn.execute("BEGIN TRANSACTION")

        cursor = research_conn.execute(
            """SELECT symbol, timestamp, oi_value
               FROM open_interest
               WHERE symbol = ?
               ORDER BY timestamp""",
            (symbol,)
        )

        rows_inserted = 0
        batch = []
        batch_size = 10000

        for row in cursor:
            symbol_val, timestamp, oi_value = row
            batch.append((symbol_val, timestamp, oi_value, "backfill", captured_at))

            if len(batch) >= batch_size:
                production_conn.executemany(
                    """INSERT OR IGNORE INTO oi_samples
                       (symbol, timestamp, oi_value, source, captured_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    batch
                )
                rows_inserted += len(batch)
                batch = []
                print(f"  Migrated {rows_inserted:,} rows...", end="\r")

        # Insert remaining rows
        if batch:
            production_conn.executemany(
                """INSERT OR IGNORE INTO oi_samples
                   (symbol, timestamp, oi_value, source, captured_at)
                   VALUES (?, ?, ?, ?, ?)""",
                batch
            )
            rows_inserted += len(batch)

        production_conn.commit()

        # Verify migration
        cursor = production_conn.execute(
            "SELECT COUNT(*) FROM oi_samples WHERE symbol = ?",
            (symbol,)
        )
        final_count = cursor.fetchone()[0]
        newly_inserted = final_count - existing_count

        print(f"  ✅ Migration complete: {newly_inserted:,} new rows added (total: {final_count:,})")

        # Verify date range in production
        cursor = production_conn.execute(
            """SELECT
                datetime(MIN(timestamp)) as oldest,
                datetime(MAX(timestamp)) as newest
               FROM oi_samples
               WHERE symbol = ?""",
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

    print("=" * 80)
    print("OI DATA MIGRATION: Research Lab → Production")
    print("=" * 80)
    print()

    for migration in migrations:
        research_db = migration["research_db"]
        symbol = migration["symbol"]

        if not research_db.exists():
            print(f"⚠ Research DB not found: {research_db}")
            continue

        rows = migrate_oi_from_research_lab(research_db, production_db, symbol)
        total_migrated += rows
        print()

    print("=" * 80)
    print(f"MIGRATION COMPLETE: {total_migrated:,} total rows migrated")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())

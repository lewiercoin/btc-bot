#!/usr/bin/env python3
"""Verify first snapshot after quant-grade hardening deployment.

Usage:
    ssh root@204.168.146.253
    cd /home/btc-bot/btc-bot
    /home/btc-bot/btc-bot/.venv/bin/python scripts/verify_first_snapshot.py
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "storage" / "btc_bot.db"


def verify_first_snapshot():
    """Verify first snapshot has quant-grade lineage fields populated."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            snapshot_id,
            cycle_timestamp,
            candles_15m_exchange_ts,
            candles_1h_exchange_ts,
            candles_4h_exchange_ts,
            funding_exchange_ts,
            oi_exchange_ts,
            aggtrades_exchange_ts,
            force_orders_exchange_ts,
            snapshot_build_started_at,
            snapshot_build_finished_at
        FROM market_snapshots
        ORDER BY cycle_timestamp DESC
        LIMIT 1
    """)

    row = cursor.fetchone()
    if not row:
        print("❌ FAIL: No snapshots found in database")
        return False

    (
        snapshot_id,
        cycle_ts,
        candles_15m_ts,
        candles_1h_ts,
        candles_4h_ts,
        funding_ts,
        oi_ts,
        aggtrades_ts,
        force_orders_ts,
        build_start,
        build_finish,
    ) = row

    print(f"\n📊 Latest Snapshot: {snapshot_id}")
    print(f"   Cycle: {cycle_ts}\n")

    issues = []
    warnings = []

    # Check build timing
    if build_start is None:
        issues.append("❌ snapshot_build_started_at is NULL")
    if build_finish is None:
        issues.append("❌ snapshot_build_finished_at is NULL")
    elif build_start is not None:
        build_start_dt = datetime.fromisoformat(build_start)
        build_finish_dt = datetime.fromisoformat(build_finish)
        cycle_dt = datetime.fromisoformat(cycle_ts)

        if build_start_dt >= build_finish_dt:
            issues.append(f"❌ Build timing violation: start >= finish ({build_start} >= {build_finish})")
        elif build_finish_dt > cycle_dt:
            issues.append(f"❌ Future timestamp: build_finish > cycle_ts ({build_finish} > {cycle_ts})")
        else:
            build_duration = (build_finish_dt - build_start_dt).total_seconds()
            print(f"✅ Build timing: {build_duration:.2f}s")

            if build_duration > 5.0:
                warnings.append(f"⚠️  Build duration unusually high: {build_duration:.2f}s (expected < 5s)")

    # Check per-input timestamps
    inputs = {
        "candles_15m": candles_15m_ts,
        "candles_1h": candles_1h_ts,
        "candles_4h": candles_4h_ts,
        "funding": funding_ts,
        "OI": oi_ts,
        "aggTrades": aggtrades_ts,
        "force_orders": force_orders_ts,
    }

    print("\n📅 Per-Input Exchange Timestamps:")
    for name, ts in inputs.items():
        if ts is None:
            if name == "force_orders":
                print(f"   {name:15} = NULL (OK if no events in window)")
            else:
                warnings.append(f"⚠️  {name}_exchange_ts is NULL (may indicate data fetch issue)")
                print(f"   {name:15} = NULL ⚠️")
        else:
            ts_dt = datetime.fromisoformat(ts)
            cycle_dt = datetime.fromisoformat(cycle_ts)
            staleness_sec = (cycle_dt - ts_dt).total_seconds()

            if ts_dt > cycle_dt:
                issues.append(f"❌ {name} timestamp from future: {ts} > {cycle_ts}")
                print(f"   {name:15} = {ts} ❌ (FUTURE)")
            else:
                print(f"   {name:15} = {ts} (staleness: {staleness_sec:.0f}s)")

                # Staleness warnings
                if name.startswith("candles") and staleness_sec > 900:
                    warnings.append(f"⚠️  {name} stale (>{staleness_sec:.0f}s, expected ~15min)")
                elif name == "OI" and staleness_sec > 120:
                    warnings.append(f"⚠️  OI stale (>{staleness_sec:.0f}s, expected <2min)")

    # Print summary
    print("\n" + "=" * 60)
    if issues:
        print("\n❌ ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")

    if warnings:
        print("\n⚠️  WARNINGS:")
        for warning in warnings:
            print(f"   {warning}")

    if not issues and not warnings:
        print("\n✅ ALL CHECKS PASSED")
        print("\nQuant-grade lineage fields properly populated.")
        print("Ready for 200+ cycle validation.")

    conn.close()
    return len(issues) == 0


if __name__ == "__main__":
    success = verify_first_snapshot()
    exit(0 if success else 1)

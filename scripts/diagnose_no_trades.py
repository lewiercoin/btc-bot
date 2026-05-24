#!/usr/bin/env python3
"""Read-only production diagnostic for "why are there no trades?".

The report stays on the deterministic audit trail:
- decision_outcomes for the funnel stop reason
- signal_candidates / executable_signals / trade_log for downstream counts
- OI/CVD/snapshot ranges for runtime data availability
- settings.json for active sweep thresholds
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("storage/btc_bot.db")
DEFAULT_SETTINGS = Path("settings.json")


def _parse_json_dict(payload: Any) -> dict[str, Any]:
    if payload in (None, ""):
        return {}
    try:
        parsed = json.loads(str(payload))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _count_since(conn: sqlite3.Connection, table: str, column: str, since: str) -> int:
    if not _table_exists(conn, table):
        return 0
    row = conn.execute(
        f"SELECT COUNT(1) AS cnt FROM {table} WHERE {column} >= ?",
        (since,),
    ).fetchone()
    return int(row["cnt"] if row else 0)


def _symbol_ranges(
    conn: sqlite3.Connection,
    *,
    table: str,
    time_column: str,
) -> list[dict[str, Any]]:
    if not _table_exists(conn, table):
        return []
    rows = conn.execute(
        f"""
        SELECT symbol, COUNT(1) AS rows, MIN({time_column}) AS oldest, MAX({time_column}) AS newest
        FROM {table}
        GROUP BY symbol
        ORDER BY symbol
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _load_thresholds(settings_path: Path) -> dict[str, float]:
    if not settings_path.exists():
        return {}
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    strategy = payload.get("strategy", {})
    thresholds: dict[str, float] = {}
    base = strategy.get("min_sweep_depth_pct")
    if base is not None:
        thresholds[str(strategy.get("symbol", "BTCUSDT")).upper()] = float(base)
        thresholds.setdefault("BTCUSDT", float(base))
    for override in payload.get("multi_asset", {}).get("symbol_overrides", []):
        symbol = str(override.get("symbol", "")).upper()
        value = override.get("min_sweep_depth_pct")
        if symbol and value is not None:
            thresholds[symbol] = float(value)
    return thresholds


def build_report(conn: sqlite3.Connection, *, since: str, settings_path: Path) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    outcomes_by_symbol: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    sweep_depths: dict[str, list[float]] = defaultdict(list)
    recent_outcomes: list[dict[str, Any]] = []

    for row in conn.execute(
        """
        SELECT cycle_timestamp, outcome_group, outcome_reason, regime, details_json
        FROM decision_outcomes
        WHERE cycle_timestamp >= ?
        ORDER BY cycle_timestamp DESC
        """,
        (since,),
    ):
        details = _parse_json_dict(row["details_json"])
        symbol = str(details.get("symbol") or "UNKNOWN").upper()
        outcomes_by_symbol[symbol][str(row["outcome_reason"])] += 1
        depth = details.get("sweep_depth_pct")
        if depth is not None:
            sweep_depths[symbol].append(float(depth))
        if len(recent_outcomes) < 12:
            recent_outcomes.append(
                {
                    "timestamp": row["cycle_timestamp"],
                    "symbol": symbol,
                    "outcome_reason": row["outcome_reason"],
                    "regime": row["regime"],
                    "sweep_depth_pct": depth,
                    "sweep_detected": details.get("sweep_detected"),
                    "reclaim_detected": details.get("reclaim_detected"),
                }
            )

    depth_stats = {}
    for symbol, values in sweep_depths.items():
        ordered = sorted(values)
        depth_stats[symbol] = {
            "count": len(ordered),
            "min": ordered[0],
            "median": ordered[len(ordered) // 2],
            "mean": sum(ordered) / len(ordered),
            "max": ordered[-1],
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "since": since,
        "counts": {
            "decision_outcomes": _count_since(conn, "decision_outcomes", "cycle_timestamp", since),
            "signal_candidates": _count_since(conn, "signal_candidates", "timestamp", since),
            "executable_signals": _count_since(conn, "executable_signals", "timestamp", since),
            "trades": _count_since(conn, "trade_log", "opened_at", since),
        },
        "outcomes_by_symbol": {symbol: dict(counts) for symbol, counts in outcomes_by_symbol.items()},
        "sweep_depth_stats": depth_stats,
        "sweep_thresholds": _load_thresholds(settings_path),
        "data_ranges": {
            "oi_samples": _symbol_ranges(conn, table="oi_samples", time_column="timestamp"),
            "cvd_price_history": _symbol_ranges(conn, table="cvd_price_history", time_column="bar_time"),
            "market_snapshots": _symbol_ranges(conn, table="market_snapshots", time_column="cycle_timestamp"),
        },
        "recent_outcomes": recent_outcomes,
    }


def print_report(report: dict[str, Any]) -> None:
    print("=" * 80)
    print("NO-TRADES DIAGNOSTIC")
    print(f"Since: {report['since']}")
    print(f"Generated: {report['generated_at']}")
    print("=" * 80)

    counts = report["counts"]
    print("\nPipeline counts")
    for key in ("decision_outcomes", "signal_candidates", "executable_signals", "trades"):
        print(f"  {key:<20} {counts[key]}")

    print("\nOutcome reasons by symbol")
    for symbol, reasons in sorted(report["outcomes_by_symbol"].items()):
        rendered = ", ".join(f"{reason}={count}" for reason, count in sorted(reasons.items()))
        print(f"  {symbol:<10} {rendered}")

    print("\nSweep depth vs threshold")
    thresholds = report["sweep_thresholds"]
    for symbol, stats in sorted(report["sweep_depth_stats"].items()):
        threshold = thresholds.get(symbol)
        threshold_text = "n/a" if threshold is None else f"{threshold:.6f}"
        print(
            f"  {symbol:<10} count={stats['count']} "
            f"min={stats['min']:.6f} median={stats['median']:.6f} "
            f"max={stats['max']:.6f} threshold={threshold_text}"
        )

    print("\nData ranges")
    for table, rows in report["data_ranges"].items():
        print(f"  [{table}]")
        if not rows:
            print("    no rows")
            continue
        for row in rows:
            print(
                f"    {row['symbol']:<10} rows={row['rows']:<8} "
                f"oldest={row['oldest']} newest={row['newest']}"
            )

    print("\nRecent outcomes")
    for row in report["recent_outcomes"]:
        print(
            f"  {row['timestamp']} {row['symbol']:<10} "
            f"{row['outcome_reason']:<22} regime={row['regime']} "
            f"sweep_depth={row['sweep_depth_pct']} reclaim={row['reclaim_detected']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain why the bot has no trades.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS)
    parser.add_argument("--since", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        report = build_report(conn, since=str(args.since), settings_path=args.settings)
    finally:
        conn.close()

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

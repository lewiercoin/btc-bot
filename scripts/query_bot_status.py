#!/usr/bin/env python3
"""Query live bot status from storage database.

Usage:
    python scripts/query_bot_status.py [--trades N] [--signals N] [--alerts N]

Examples:
    python scripts/query_bot_status.py --trades 5
    python scripts/query_bot_status.py --signals 10 --alerts 20
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def query_recent_trades(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Query recent closed trades."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            trade_id,
            opened_at,
            closed_at,
            direction,
            regime,
            confluence_score,
            entry_price,
            exit_price,
            pnl_abs,
            pnl_r,
            exit_reason,
            size,
            fees_total,
            mae,
            mfe
        FROM trade_log
        WHERE closed_at IS NOT NULL
        ORDER BY closed_at DESC
        LIMIT ?
    """, (limit,))

    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def query_open_positions(conn: sqlite3.Connection) -> list[dict]:
    """Query currently open positions."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            position_id,
            signal_id,
            opened_at,
            direction,
            entry_price,
            size,
            stop_loss,
            take_profit_1,
            status
        FROM positions
        WHERE status = 'OPEN'
        ORDER BY opened_at DESC
    """)

    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def query_recent_signals(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Query recent signal candidates (promoted and blocked)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            signal_id,
            timestamp,
            direction,
            promoted,
            regime,
            confluence_score,
            entry_price,
            rr_ratio,
            block_reason
        FROM signal_candidates
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))

    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def query_recent_alerts(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Query recent alerts and errors."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            timestamp,
            severity,
            component,
            message
        FROM alerts_errors
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))

    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def query_bot_state(conn: sqlite3.Connection) -> dict | None:
    """Query current bot state."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            timestamp,
            mode,
            healthy,
            safe_mode,
            open_positions_count,
            consecutive_losses,
            daily_dd_pct,
            weekly_dd_pct,
            last_trade_at,
            safe_mode_entry_at
        FROM bot_state
        ORDER BY timestamp DESC
        LIMIT 1
    """)

    row = cursor.fetchone()
    if not row:
        return None

    cols = [d[0] for d in cursor.description]
    state = dict(zip(cols, row))

    # Get safe mode reason from safe_mode_events if in safe mode
    if state.get('safe_mode'):
        cursor.execute("""
            SELECT reason
            FROM safe_mode_events
            WHERE event_type = 'ENTRY'
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        reason_row = cursor.fetchone()
        state['safe_mode_reason'] = reason_row[0] if reason_row else None
    else:
        state['safe_mode_reason'] = None

    return state


def query_daily_metrics(conn: sqlite3.Connection, days: int = 7) -> list[dict]:
    """Query daily performance metrics."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            date,
            trades_count,
            wins,
            losses,
            pnl_abs,
            pnl_r_sum,
            expectancy_r,
            daily_dd_pct
        FROM daily_metrics
        ORDER BY date DESC
        LIMIT ?
    """, (days,))

    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def format_timestamp(ts_str: str | None) -> str:
    """Format ISO timestamp to readable string."""
    if not ts_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return ts_str


def print_summary(conn: sqlite3.Connection):
    """Print comprehensive bot status summary."""
    print("=" * 80)
    print("BOT STATUS SUMMARY")
    print("=" * 80)

    # Bot State
    state = query_bot_state(conn)
    if state:
        print(f"\n[BOT STATE] {format_timestamp(state['timestamp'])}")
        print(f"  Mode: {state['mode']}")
        print(f"  Healthy: {state['healthy']}")
        print(f"  Safe Mode: {state['safe_mode']} ({state['safe_mode_reason'] or 'N/A'})")
        print(f"  Open Positions: {state['open_positions_count']}")
        print(f"  Consecutive Losses: {state['consecutive_losses']}")
        print(f"  Daily DD: {state['daily_dd_pct']:.2f}%")
        print(f"  Weekly DD: {state['weekly_dd_pct']:.2f}%")

    # Open Positions
    positions = query_open_positions(conn)
    print(f"\n[OPEN POSITIONS] {len(positions)} active")
    for pos in positions:
        print(f"  {pos['direction']} @ {pos['entry_price']:.2f} | Size: {pos['size']:.4f} | SL: {pos['stop_loss']:.2f} | TP: {pos['take_profit_1']:.2f}")

    # Recent Trades
    trades = query_recent_trades(conn, limit=5)
    print(f"\n[RECENT TRADES] Last {len(trades)}")
    for trade in trades:
        pnl_sign = "+" if trade['pnl_abs'] >= 0 else ""
        print(f"  {trade['direction']} | Entry: {trade['entry_price']:.2f} | Exit: {trade['exit_price']:.2f} | "
              f"PnL: {pnl_sign}{trade['pnl_abs']:.2f} ({trade['pnl_r']:.2f}R) | {trade['exit_reason']} | "
              f"Closed: {format_timestamp(trade['closed_at'])}")

    # Daily Metrics
    metrics = query_daily_metrics(conn, days=7)
    print(f"\n[DAILY METRICS] Last {len(metrics)} days")
    for m in metrics:
        pnl_sign = "+" if m['pnl_abs'] >= 0 else ""
        wr = (m['wins'] / m['trades_count'] * 100) if m['trades_count'] > 0 else 0
        print(f"  {m['date']} | Trades: {m['trades_count']} (W:{m['wins']} L:{m['losses']}) | "
              f"WR: {wr:.0f}% | PnL: {pnl_sign}{m['pnl_abs']:.2f} | ExpR: {m['expectancy_r']:.2f} | DD: {m['daily_dd_pct']:.2f}%")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Query bot status from storage database")
    parser.add_argument("--db", default="storage/btc_bot.db", help="Path to database file")
    parser.add_argument("--trades", type=int, help="Show N recent trades")
    parser.add_argument("--signals", type=int, help="Show N recent signals")
    parser.add_argument("--alerts", type=int, help="Show N recent alerts")
    parser.add_argument("--summary", action="store_true", help="Show comprehensive summary (default)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Default to summary if no specific query
    if not any([args.trades, args.signals, args.alerts]):
        args.summary = True

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        if args.summary:
            print_summary(conn)

        result = {}

        if args.trades:
            trades = query_recent_trades(conn, args.trades)
            if args.json:
                result['trades'] = trades
            else:
                print(f"\n[RECENT TRADES] Last {len(trades)}")
                for t in trades:
                    print(json.dumps(t, indent=2, default=str))

        if args.signals:
            signals = query_recent_signals(conn, args.signals)
            if args.json:
                result['signals'] = signals
            else:
                print(f"\n[RECENT SIGNALS] Last {len(signals)}")
                for s in signals:
                    print(json.dumps(s, indent=2, default=str))

        if args.alerts:
            alerts = query_recent_alerts(conn, args.alerts)
            if args.json:
                result['alerts'] = alerts
            else:
                print(f"\n[RECENT ALERTS] Last {len(alerts)}")
                for a in alerts:
                    print(f"  [{a['timestamp']}] {a['severity']:10s} | {a['component']:15s} | {a['message']}")

        if args.json and result:
            print(json.dumps(result, indent=2, default=str))

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    exit(main())
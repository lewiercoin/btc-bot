#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REFERENCE_EQUITY = 10_000.0


def _parse_utc(raw: str) -> datetime:
    value = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _load_monitoring_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Settings file must be a JSON object: {path}")
    monitoring = payload.get("monitoring")
    if not isinstance(monitoring, dict):
        raise ValueError(f"Settings file has no monitoring object: {path}")
    return dict(monitoring)


def _fetch_closed_trades(conn: sqlite3.Connection, *, since: datetime) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT trade_id, opened_at, closed_at, pnl_abs, pnl_r, exit_reason, config_hash
        FROM trade_log
        WHERE closed_at IS NOT NULL
          AND closed_at >= ?
        ORDER BY closed_at ASC
        """,
        (since.isoformat(),),
    ).fetchall()
    return [dict(row) for row in rows]


def _fetch_bot_mode(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT mode FROM bot_state WHERE id = 1").fetchone()
    if row is None:
        return None
    return str(row[0])


def _profit_factor_r(trades: list[dict[str, Any]]) -> float:
    winners = [float(t["pnl_r"]) for t in trades if float(t["pnl_r"]) > 0]
    losers = [float(t["pnl_r"]) for t in trades if float(t["pnl_r"]) < 0]
    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))
    if gross_loss == 0:
        return math.inf if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _max_drawdown_pct(trades: list[dict[str, Any]]) -> float:
    peak = REFERENCE_EQUITY
    equity = REFERENCE_EQUITY
    max_dd = 0.0
    for trade in trades:
        equity += float(trade["pnl_abs"])
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / max(peak, 1e-8))
    return min(max(max_dd, 0.0), 1.0)


def _month_key(ts: datetime) -> str:
    return f"{ts.year:04d}-{ts.month:02d}"


def _month_add(year: int, month: int, offset: int) -> tuple[int, int]:
    idx = (year * 12 + (month - 1)) + offset
    return idx // 12, idx % 12 + 1


def _closed_month_counts(*, since: datetime, now: datetime, trades: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    first_year, first_month = since.year, since.month
    current_key = _month_key(now)
    offset = 0
    while True:
        year, month = _month_add(first_year, first_month, offset)
        key = f"{year:04d}-{month:02d}"
        if key >= current_key:
            break
        counts[key] = 0
        offset += 1
    for trade in trades:
        closed = _parse_utc(str(trade["closed_at"]))
        key = _month_key(closed)
        if key in counts:
            counts[key] += 1
    return counts


def _apply_safe_mode(conn: sqlite3.Connection, *, reason: str, now: datetime, dry_run: bool) -> None:
    if dry_run:
        return
    ts = now.isoformat()
    conn.execute(
        """
        UPDATE bot_state
        SET healthy = 0,
            safe_mode = 1,
            last_error = ?,
            safe_mode_entry_at = COALESCE(safe_mode_entry_at, ?),
            timestamp = ?
        WHERE id = 1
        """,
        (reason, ts, ts),
    )
    conn.execute(
        """
        INSERT INTO safe_mode_events (event_type, trigger, reason, timestamp)
        VALUES (?, ?, ?, ?)
        """,
        ("entered", "trial_00095_monitor", reason, ts),
    )
    conn.execute(
        """
        INSERT INTO alerts_errors (timestamp, type, severity, component, message, payload_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            ts,
            "TRIAL_MONITOR",
            "CRITICAL",
            "trial_00095_monitor",
            reason,
            json.dumps({"candidate_id": "optuna-default-v3-trial-00095"}, sort_keys=True),
        ),
    )
    conn.commit()


def evaluate(conn: sqlite3.Connection, config: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    start = _parse_utc(str(config["deployment_start_utc"]))
    trades = _fetch_closed_trades(conn, since=start)
    trade_count = len(trades)
    pnl_r_values = [float(t["pnl_r"]) for t in trades]
    expectancy_r = sum(pnl_r_values) / trade_count if trade_count else 0.0
    profit_factor = _profit_factor_r(trades)
    max_drawdown_pct = _max_drawdown_pct(trades)
    elapsed_days = max((now - start).total_seconds() / 86400.0, 0.0)
    elapsed_months = max(elapsed_days / 30.4375, 1.0 / 30.4375)
    trades_per_month = trade_count / elapsed_months
    closed_month_counts = _closed_month_counts(since=start, now=now, trades=trades)

    alerts: list[str] = []
    hard_stop = False

    mode = _fetch_bot_mode(conn)
    if config.get("paper_only", True) and mode != "PAPER":
        alerts.append(f"mode_not_paper:{mode}")

    if trade_count >= int(config["hard_stop_after_trades"]) and expectancy_r < float(config["hard_stop_min_expectancy_r"]):
        hard_stop = True
        alerts.append(
            f"hard_stop_expectancy_r:{expectancy_r:.4f}<"
            f"{float(config['hard_stop_min_expectancy_r']):.4f}"
        )

    if trade_count >= 30 and profit_factor < float(config["review_pf_after_30_trades_below"]):
        alerts.append(
            f"review_profit_factor:{profit_factor:.4f}<"
            f"{float(config['review_pf_after_30_trades_below']):.4f}"
        )

    if max_drawdown_pct > float(config["review_drawdown_pct_above"]):
        alerts.append(
            f"review_drawdown:{max_drawdown_pct:.4f}>"
            f"{float(config['review_drawdown_pct_above']):.4f}"
        )

    month_values = list(closed_month_counts.items())
    need_months = int(config["frequency_review_consecutive_months"])
    if len(month_values) >= need_months:
        recent = month_values[-need_months:]
        threshold = float(config["frequency_review_min_trades_per_month"])
        if all(count < threshold for _, count in recent):
            months = ",".join(month for month, _ in recent)
            alerts.append(f"review_low_frequency:{months}")

    if trade_count >= int(config["early_review_min_trades"]):
        alerts.append(f"early_review_trade_count:{trade_count}")

    if elapsed_months >= float(config["early_review_months_min"]):
        alerts.append(f"early_review_age_months:{elapsed_months:.2f}")

    return {
        "candidate_id": config["candidate_id"],
        "checked_at_utc": now.isoformat(),
        "deployment_start_utc": start.isoformat(),
        "mode": mode,
        "trade_count": trade_count,
        "trades_per_month": trades_per_month,
        "closed_month_counts": closed_month_counts,
        "expectancy_r": expectancy_r,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown_pct,
        "pnl_r_sum": sum(pnl_r_values),
        "pnl_abs_sum": sum(float(t["pnl_abs"]) for t in trades),
        "alerts": alerts,
        "hard_stop": hard_stop,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor trial-00095 paper-trading guardrails.")
    parser.add_argument("--db", type=Path, default=Path("storage/btc_bot.db"))
    parser.add_argument("--settings", type=Path, default=Path("settings.json"))
    parser.add_argument("--output-json", type=Path, default=Path("logs/trial_00095_monitoring.json"))
    parser.add_argument("--apply-safe-mode", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()

    config = _load_monitoring_config(args.settings)
    now = _now_utc()
    conn = sqlite3.connect(args.db)
    try:
        result = evaluate(conn, config, now=now)
        if result["hard_stop"] and args.apply_safe_mode:
            reason = "trial_00095_hard_stop:" + ";".join(result["alerts"])
            _apply_safe_mode(conn, reason=reason, now=now, dry_run=args.dry_run)
            result["safe_mode_applied"] = not args.dry_run
        else:
            result["safe_mode_applied"] = False
    finally:
        conn.close()

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Pre-registered, mechanical kill-test for trial-00095.

Criteria are FROZEN in docs/KILL_TEST_TRIAL_00095_PREREGISTRATION_2026-06-05.md
and hard-coded below. This script does not interpret; it compares live numbers
to frozen thresholds and prints a single verdict. No audit narrative is trusted.

Stdlib only. Run on the server where storage/btc_bot.db lives.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- FROZEN constants (do not edit after registration) ----------------------
DEPLOYMENT_CONFIG_HASH = (
    "afbd2eb052af3be748950d6b639880ef05c33a03380d8e6ba9fb243170b747d5"
)
DEPLOYMENT_SINCE = datetime(2026, 5, 8, tzinfo=timezone.utc)
REFERENCE_EQUITY = 10_000.0

# Stream A — live forward paper thresholds
A_MIN_TRADES = 20
A_MIN_EXPECTANCY_R = 0.0
A_MIN_PROFIT_FACTOR = 1.0

# Stream B — fresh historical holdout thresholds
B_MIN_TRADES = 20
B_MIN_EXPECTANCY_R = 0.05
B_MIN_PROFIT_FACTOR = 1.2
B_MIN_SHARPE = 0.5
B_MAX_DRAWDOWN = 0.25
# ----------------------------------------------------------------------------


def _profit_factor_r(pnl_r: list[float]) -> float:
    gross_profit = sum(x for x in pnl_r if x > 0)
    gross_loss = abs(sum(x for x in pnl_r if x < 0))
    if gross_loss == 0:
        return math.inf if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _expectancy_r(pnl_r: list[float]) -> float:
    return sum(pnl_r) / len(pnl_r) if pnl_r else 0.0


def _sharpe_r(pnl_r: list[float]) -> float:
    n = len(pnl_r)
    if n < 2:
        return 0.0
    mean = sum(pnl_r) / n
    var = sum((x - mean) ** 2 for x in pnl_r) / (n - 1)
    std = math.sqrt(var)
    return mean / std if std > 0 else 0.0


def _max_drawdown_pct(pnl_abs: list[float]) -> float:
    peak = equity = REFERENCE_EQUITY
    max_dd = 0.0
    for x in pnl_abs:
        equity += x
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / max(peak, 1e-8))
    return min(max(max_dd, 0.0), 1.0)


def stream_a_live_forward(db_path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT pnl_abs, pnl_r
            FROM trade_log
            WHERE closed_at IS NOT NULL
              AND closed_at >= ?
              AND config_hash = ?
            ORDER BY closed_at ASC
            """,
            (DEPLOYMENT_SINCE.isoformat(), DEPLOYMENT_CONFIG_HASH),
        ).fetchall()
    finally:
        conn.close()

    pnl_r = [float(r["pnl_r"]) for r in rows]
    pnl_abs = [float(r["pnl_abs"]) for r in rows]
    n = len(pnl_r)

    metrics = {
        "closed_trades": n,
        "expectancy_r": round(_expectancy_r(pnl_r), 6),
        "profit_factor": _profit_factor_r(pnl_r),
        "max_drawdown_pct": round(_max_drawdown_pct(pnl_abs), 6),
    }

    if n < A_MIN_TRADES:
        verdict = "INSUFFICIENT"
        passed = False
    else:
        passed = (
            metrics["expectancy_r"] > A_MIN_EXPECTANCY_R
            and metrics["profit_factor"] > A_MIN_PROFIT_FACTOR
        )
        verdict = "PASS" if passed else "FAIL"

    return {
        "stream": "A_live_forward",
        "thresholds": {
            "min_trades": A_MIN_TRADES,
            "min_expectancy_r": A_MIN_EXPECTANCY_R,
            "min_profit_factor": A_MIN_PROFIT_FACTOR,
        },
        "metrics": metrics,
        "passed": passed,
        "verdict": verdict,
    }


def stream_b_holdout(wf_json_path: Path) -> dict[str, Any]:
    payload = json.loads(wf_json_path.read_text(encoding="utf-8"))
    # Accept either a flat metrics dict or a WF report; prefer explicit holdout
    # validation metrics if present.
    m = payload.get("holdout_metrics") or payload.get("validation") or payload
    trades = int(m.get("trades_count", m.get("trades", 0)))
    expectancy = float(m.get("expectancy_r", m.get("er", 0.0)))
    pf = float(m.get("profit_factor", m.get("pf", 0.0)))
    sharpe = float(m.get("sharpe_ratio", m.get("sharpe", 0.0)))
    mdd = float(m.get("max_drawdown_pct", m.get("mdd", 1.0)))

    metrics = {
        "trades": trades,
        "expectancy_r": expectancy,
        "profit_factor": pf,
        "sharpe": sharpe,
        "max_drawdown_pct": mdd,
    }
    if trades < B_MIN_TRADES:
        verdict, passed = "INSUFFICIENT", False
    else:
        passed = (
            expectancy > B_MIN_EXPECTANCY_R
            and pf > B_MIN_PROFIT_FACTOR
            and sharpe > B_MIN_SHARPE
            and mdd < B_MAX_DRAWDOWN
        )
        verdict = "PASS" if passed else "FAIL"

    return {
        "stream": "B_fresh_holdout",
        "thresholds": {
            "min_trades": B_MIN_TRADES,
            "min_expectancy_r": B_MIN_EXPECTANCY_R,
            "min_profit_factor": B_MIN_PROFIT_FACTOR,
            "min_sharpe": B_MIN_SHARPE,
            "max_drawdown_pct": B_MAX_DRAWDOWN,
        },
        "metrics": metrics,
        "passed": passed,
        "verdict": verdict,
    }


def combine(a: dict[str, Any], b: dict[str, Any] | None) -> str:
    if a["verdict"] == "FAIL":
        return "FAIL"
    if b is not None and b["verdict"] == "FAIL":
        return "FAIL"
    if a["verdict"] == "PASS" and (b is not None and b["verdict"] == "PASS"):
        return "PASS"
    return "INSUFFICIENT"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="Path to btc_bot.db")
    parser.add_argument(
        "--holdout-wf-json",
        type=Path,
        default=None,
        help="Optional WF/backtest JSON over a fresh 2026 holdout (Stream B).",
    )
    args = parser.parse_args()

    result: dict[str, Any] = {
        "test": "kill_test_trial_00095",
        "preregistration": "docs/KILL_TEST_TRIAL_00095_PREREGISTRATION_2026-06-05.md",
        "predicted_verdict": "FAIL",
        "stream_a": stream_a_live_forward(args.db),
    }
    stream_b = None
    if args.holdout_wf_json is not None:
        stream_b = stream_b_holdout(args.holdout_wf_json)
        result["stream_b"] = stream_b
    else:
        result["stream_b"] = "NOT_PROVIDED — run WF on 2026 holdout and pass --holdout-wf-json"

    result["verdict"] = combine(result["stream_a"], stream_b)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

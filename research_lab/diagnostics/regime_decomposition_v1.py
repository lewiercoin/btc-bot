"""
regime_decomposition_v1.py — Trade-log regime decomposition for baseline-v3-trial-00195.

Deliverable D3 of SIGNAL-ANALYSIS-V1 milestone (CONDITIONAL).

Condition: run only if event_study_v1.json shows mean_forward_return (bar+4)
significantly positive (p < 0.05) in >= 3 SUFFICIENT segments for P1+MATURE.

What it does:
  1. Checks D2 condition gate (reads event_study_v1.json if present).
  2. Loads trial baseline-v3-trial-00195 from the experiment store.
     Re-evaluates using BacktestRunner if not found (full period 2022-01-01 -> 2026-03-01).
  3. Tags each trade by regime segment S1-S6 using trade opened_at timestamp.
  4. Per segment: expectancy_r, profit_factor, trade_count, win_rate, max_drawdown_pct.
  5. Outputs research_lab/runs/regime_decomposition_v1.json.

Usage:
    python -m research_lab.diagnostics.regime_decomposition_v1
    python -m research_lab.diagnostics.regime_decomposition_v1 --db-path storage/btc_bot.db
    python -m research_lab.diagnostics.regime_decomposition_v1 --force  # skip D2 gate
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_STUDY_START = "2022-01-01"
_STUDY_END = "2026-03-01"
_SYMBOL = "BTCUSDT"
_TARGET_TRIAL_ID = "baseline-v3-trial-00195"

_D2_CONDITION_P_THRESHOLD = 0.05
_D2_CONDITION_MIN_SEGMENTS = 3

_SEGMENTS: dict[str, tuple[str, str, str]] = {
    "S1": ("2022-01-01", "2022-06-30", "bear collapse"),
    "S2": ("2022-07-01", "2023-03-31", "bear range / bottoming"),
    "S3": ("2023-04-01", "2024-01-31", "recovery / pre-ETF"),
    "S4": ("2024-02-01", "2024-09-30", "ETF launch / halving"),
    "S5": ("2024-10-01", "2025-06-30", "rally to ATH / distribution"),
    "S6": ("2025-07-01", "2026-03-01", "recent regime"),
}

_SEG_BOUNDS: list[tuple[str, datetime, datetime]] = []
for _sid, (_s, _e, _d) in _SEGMENTS.items():
    _SEG_BOUNDS.append((
        _sid,
        datetime.fromisoformat(_s).replace(tzinfo=timezone.utc),
        datetime.fromisoformat(_e + "T23:59:59").replace(tzinfo=timezone.utc),
    ))


def _segment_for_ts(ts: datetime) -> str | None:
    ts_utc = ts.astimezone(timezone.utc)
    for seg_id, seg_start, seg_end in _SEG_BOUNDS:
        if seg_start <= ts_utc <= seg_end:
            return seg_id
    return None


def _check_d2_condition(d2_path: Path) -> tuple[bool, str]:
    """Check if D2 threshold is met. Returns (condition_met, reason_string)."""
    if not d2_path.exists():
        return False, f"D2 output not found at {d2_path} — run event_study_v1.py first"

    with open(d2_path, encoding="utf-8") as fh:
        d2 = json.load(fh)

    edge_count = d2.get("p1_mature_edge_count", 0)
    p1_mature = d2.get("p1_mature_summary", {})

    qualifying: list[str] = []
    for seg_id, stats in p1_mature.items():
        if (
            stats.get("status") == "OK"
            and stats.get("mean_forward_return_bar4", float("nan")) > 0
            and stats.get("p_value", 1.0) < _D2_CONDITION_P_THRESHOLD
            and stats.get("n_events", 0) >= 30
        ):
            qualifying.append(seg_id)

    met = len(qualifying) >= _D2_CONDITION_MIN_SEGMENTS
    reason = (
        f"D2 condition {'MET' if met else 'NOT MET'}: "
        f"{len(qualifying)}/{_D2_CONDITION_MIN_SEGMENTS} required segments qualify "
        f"(qualifying: {qualifying})"
    )
    return met, reason


def _load_trial_params(store_path: Path) -> dict[str, Any] | None:
    """Load params for the target trial from the experiment store."""
    if not store_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(store_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT params_json FROM trials WHERE trial_id = ?",
            (_TARGET_TRIAL_ID,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return json.loads(str(row["params_json"]))
    except Exception:
        return None


def _run_backtest_for_params(
    params: dict[str, Any] | None,
    db_path: Path,
) -> list[Any]:
    """Run backtest and return TradeLog list.

    Uses provided params override if available; otherwise uses default settings.
    """
    from backtest.backtest_runner import BacktestConfig, BacktestRunner
    from research_lab.settings_adapter import build_candidate_settings
    from settings import load_settings

    base_settings = load_settings()
    if params is not None:
        settings = build_candidate_settings(base_settings, params)
    else:
        settings = base_settings

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    runner = BacktestRunner(conn, settings=settings)
    config = BacktestConfig(
        start_date=_STUDY_START,
        end_date=_STUDY_END,
        symbol=_SYMBOL,
    )
    result = runner.run(config)
    conn.close()
    return result.trades


def _segment_stats(trades: list[Any]) -> dict[str, Any]:
    """Compute per-segment stats from TradeLog list."""
    from_segment: dict[str, list[Any]] = {sid: [] for sid in _SEGMENTS}

    for trade in trades:
        opened_at = trade.opened_at
        if opened_at is None:
            continue
        seg = _segment_for_ts(opened_at)
        if seg:
            from_segment[seg].append(trade)

    stats: dict[str, Any] = {}
    for seg_id, seg_trades in from_segment.items():
        n = len(seg_trades)
        if n == 0:
            stats[seg_id] = {
                "trade_count": 0,
                "description": _SEGMENTS[seg_id][2],
            }
            continue

        pnl_rs = [t.pnl_r for t in seg_trades]
        pnl_abs = [t.pnl_abs for t in seg_trades]
        wins = [t for t in seg_trades if t.pnl_abs > 0]
        losses = [t for t in seg_trades if t.pnl_abs <= 0]

        expectancy_r = sum(pnl_rs) / n
        gross_profit = sum(t.pnl_abs for t in wins)
        gross_loss = abs(sum(t.pnl_abs for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        win_rate = len(wins) / n

        # Max drawdown over cumulative PnL curve
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for pnl in pnl_abs:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / abs(peak) if peak != 0 else 0.0
            max_dd = max(max_dd, dd)

        stats[seg_id] = {
            "description": _SEGMENTS[seg_id][2],
            "trade_count": n,
            "expectancy_r": round(expectancy_r, 4),
            "profit_factor": round(profit_factor, 4) if not (profit_factor == float("inf")) else None,
            "win_rate": round(win_rate, 4),
            "max_drawdown_pct": round(max_dd, 4),
            "pnl_abs_sum": round(sum(pnl_abs), 2),
        }

    return stats


def run_regime_decomposition(
    db_path: Path,
    store_path: Path,
    d2_output_path: Path,
    output_path: Path,
    force: bool = False,
) -> dict[str, Any]:
    """Run regime decomposition. Returns results dict."""

    # Gate: check D2 condition
    if not force:
        condition_met, condition_reason = _check_d2_condition(d2_output_path)
        if not condition_met:
            print(f"[regime_decomposition_v1] SKIPPED: {condition_reason}")
            result: dict[str, Any] = {
                "status": "SKIPPED",
                "reason": condition_reason,
                "d2_condition_p_threshold": _D2_CONDITION_P_THRESHOLD,
                "d2_condition_min_segments": _D2_CONDITION_MIN_SEGMENTS,
            }
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2)
            return result
        print(f"[regime_decomposition_v1] {condition_reason}")
    else:
        condition_reason = "FORCED (--force flag; D2 gate bypassed)"
        print(f"[regime_decomposition_v1] {condition_reason}")

    # Load trial params
    params = _load_trial_params(store_path)
    if params is not None:
        print(f"[regime_decomposition_v1] Loaded params for {_TARGET_TRIAL_ID} from store.")
        trial_source = "store"
    else:
        print(
            f"[regime_decomposition_v1] Trial {_TARGET_TRIAL_ID} not found in store. "
            "Using default settings for backtest."
        )
        trial_source = "default_settings"

    print("[regime_decomposition_v1] Running backtest to collect trades ...")
    trades = _run_backtest_for_params(params, db_path)
    print(f"[regime_decomposition_v1] Backtest complete: {len(trades)} trades.")

    seg_stats = _segment_stats(trades)

    results: dict[str, Any] = {
        "meta": {
            "target_trial_id": _TARGET_TRIAL_ID,
            "trial_source": trial_source,
            "study_start": _STUDY_START,
            "study_end": _STUDY_END,
            "symbol": _SYMBOL,
            "total_trades": len(trades),
            "d2_condition": condition_reason,
        },
        "segment_stats": seg_stats,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    _print_summary(results)
    return results


def _print_summary(results: dict[str, Any]) -> None:
    if results.get("status") == "SKIPPED":
        print(f"[regime_decomposition_v1] Status: SKIPPED — {results.get('reason')}")
        return
    meta = results["meta"]
    print(f"\n{'=' * 70}")
    print("REGIME DECOMPOSITION V1 — SUMMARY")
    print(f"{'=' * 70}")
    print(f"Trial:    {meta['target_trial_id']} (source: {meta['trial_source']})")
    print(f"Period:   {meta['study_start']} -> {meta['study_end']}")
    print(f"Trades:   {meta['total_trades']}")
    print()
    print(f"{'Seg':<4} {'N':>5} {'ExpR':>7} {'PF':>6} {'WR':>6} {'MaxDD':>7}  Description")
    print(f"{'---':<4} {'---':>5} {'----':>7} {'---':>6} {'---':>6} {'-----':>7}  -----------")
    for seg_id, stats in results.get("segment_stats", {}).items():
        n = stats.get("trade_count", 0)
        if n == 0:
            print(f"{seg_id:<4} {n:>5}  [no trades]  {stats.get('description', '')}")
            continue
        exp_r = stats.get("expectancy_r", float("nan"))
        pf = stats.get("profit_factor")
        wr = stats.get("win_rate", float("nan"))
        dd = stats.get("max_drawdown_pct", float("nan"))
        pf_str = f"{pf:.3f}" if pf is not None else "inf"
        print(
            f"{seg_id:<4} {n:>5} {exp_r:>+7.3f} {pf_str:>6} {wr:>5.1%} {dd:>6.1%}  "
            f"{stats.get('description', '')}"
        )
    print(f"{'=' * 70}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Regime decomposition v1")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("storage/btc_bot.db"),
    )
    parser.add_argument(
        "--store-path",
        type=Path,
        default=Path("research_lab/research_lab.db"),
    )
    parser.add_argument(
        "--d2-output",
        type=Path,
        default=Path("research_lab/runs/event_study_v1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research_lab/runs/regime_decomposition_v1.json"),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip D2 condition gate and run regardless",
    )
    args = parser.parse_args()

    run_regime_decomposition(
        db_path=args.db_path,
        store_path=args.store_path,
        d2_output_path=args.d2_output,
        output_path=args.output,
        force=args.force,
    )


if __name__ == "__main__":
    main()

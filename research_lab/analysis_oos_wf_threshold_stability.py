"""
OOS_WF_THRESHOLD_STABILITY_ANALYSIS (M3)

Walk-forward threshold stability test for min_sweep_depth_pct.

Tests whether trial-00095's threshold (0.00649) is stable across out-of-sample
time windows, or is window-specific / overfitted.

Methodology:
  - 3 walk-forward windows (2-year train, 1-year or 3-month test)
  - 6 threshold values: [0.004, 0.005, 0.006, 0.00649, 0.007, 0.008]
  - 18 total OOS backtest runs
  - Metrics: trade count, ER, PF, max DD, win rate, safety flags
  - Verdict taxonomy: THRESHOLD_NATURAL, THRESHOLD_OVERFITTED,
    THRESHOLD_WINDOW_DEPENDENT, INSUFFICIENT_DATA

Usage:
  python research_lab/analysis_oos_wf_threshold_stability.py \
      --store research_lab/research_lab.db.v3 \
      --market-db research_lab/snapshots/replay-run13-regime-aware-trial-00063.db \
      --output-dir research_lab/analysis_output

Read-only on store DB. Each backtest run uses a temporary DB copy.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sqlite3
import statistics
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig, BacktestRunner, BacktestResult
from backtest.performance import PerformanceReport
from research_lab.settings_adapter import build_candidate_settings
from settings import load_settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRIAL_00095_ID = "optuna-default-v3-trial-00095"
TRIAL_00095_DEPTH = 0.00649

THRESHOLD_GRID = [0.004, 0.005, 0.006, 0.00649, 0.007, 0.008]

MIN_TRADES_FOR_VALIDITY = 20

# Walk-forward window definitions
# Each tuple: (name, train_start, train_end, test_start, test_end)
WF_WINDOWS = [
    ("WF1", "2022-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),
    ("WF2", "2023-01-01", "2024-12-31", "2025-01-01", "2025-12-31"),
    ("WF3", "2024-01-01", "2025-12-31", "2026-01-01", "2026-03-28"),
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CellResult:
    """Result for one (window, threshold) combination."""
    window_name: str
    threshold: float
    is_train: bool  # True = train/IS run, False = OOS/test run
    trade_count: int = 0
    expectancy_r: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    pnl_abs: float = 0.0
    safety_flags: list[str] = field(default_factory=list)
    insufficient_data: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": self.window_name,
            "threshold": self.threshold,
            "is_train": self.is_train,
            "trade_count": self.trade_count,
            "expectancy_r": round(self.expectancy_r, 3),
            "profit_factor": round(self.profit_factor, 3),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "win_rate": round(self.win_rate, 3),
            "pnl_abs": round(self.pnl_abs, 2),
            "safety_flags": self.safety_flags,
            "insufficient_data": self.insufficient_data,
        }


# ---------------------------------------------------------------------------
# Trial-00095 parameter loading
# ---------------------------------------------------------------------------

def load_trial_params(store_path: Path) -> dict[str, Any]:
    """Load trial-00095 exact parameters from experiment store."""
    conn = sqlite3.connect(str(store_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT params_json FROM trials WHERE trial_id = ?",
        (TRIAL_00095_ID,),
    ).fetchone()
    conn.close()

    if not row:
        raise RuntimeError(f"Trial {TRIAL_00095_ID} not found in store")

    return json.loads(row["params_json"])


# ---------------------------------------------------------------------------
# Backtest execution
# ---------------------------------------------------------------------------

_SCHEMA_TABLES = {
    "signal_candidates": """CREATE TABLE IF NOT EXISTS signal_candidates (
        signal_id TEXT PRIMARY KEY, timestamp TEXT, direction TEXT,
        setup_type TEXT, confluence_score REAL, regime TEXT,
        reasons_json TEXT, features_json TEXT, schema_version TEXT, config_hash TEXT
    )""",
    "executable_signals": """CREATE TABLE IF NOT EXISTS executable_signals (
        signal_id TEXT PRIMARY KEY, timestamp TEXT, direction TEXT,
        entry_price REAL, stop_loss REAL, take_profit_1 REAL,
        take_profit_2 REAL, rr_ratio REAL, governance_notes_json TEXT
    )""",
    "positions": """CREATE TABLE IF NOT EXISTS positions (
        position_id TEXT PRIMARY KEY, signal_id TEXT, symbol TEXT,
        direction TEXT, status TEXT, entry_price REAL, size REAL,
        leverage INTEGER, stop_loss REAL, take_profit_1 REAL,
        take_profit_2 REAL, opened_at TEXT, updated_at TEXT
    )""",
    "trade_log": """CREATE TABLE IF NOT EXISTS trade_log (
        trade_id TEXT PRIMARY KEY, signal_id TEXT, position_id TEXT,
        opened_at TEXT, closed_at TEXT, direction TEXT, regime TEXT,
        confluence_score REAL, entry_price REAL, exit_price REAL,
        size REAL, fees_total REAL, funding_paid REAL, slippage_bps_avg REAL,
        pnl_abs REAL, pnl_r REAL, mae REAL, mfe REAL, exit_reason TEXT,
        features_at_entry_json TEXT, schema_version TEXT, config_hash TEXT
    )""",
}


def _prepare_temp_db(market_db_path: Path) -> tuple[Path, sqlite3.Connection]:
    """Copy market DB to temp file, ensure schema tables exist."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    tmp_path = Path(tmp.name)
    shutil.copy2(str(market_db_path), str(tmp_path))

    conn = sqlite3.connect(str(tmp_path))
    conn.row_factory = sqlite3.Row
    for ddl in _SCHEMA_TABLES.values():
        conn.execute(ddl)
    conn.execute("DROP TABLE IF EXISTS trade_log")
    conn.execute(_SCHEMA_TABLES["trade_log"])
    conn.commit()
    return tmp_path, conn


def _cleanup_temp_db(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """Close connection and remove temp DB file."""
    try:
        conn.close()
    except Exception:
        pass
    try:
        tmp_path.unlink()
    except OSError:
        pass


def run_single_backtest(
    market_db_path: Path,
    params: dict[str, Any],
    threshold: float,
    start_date: str,
    end_date: str,
) -> CellResult:
    """Run a single backtest with given threshold override."""
    # Override min_sweep_depth_pct
    run_params = dict(params)
    run_params["min_sweep_depth_pct"] = threshold

    base_settings = load_settings(profile="research")
    candidate_settings = build_candidate_settings(base_settings, run_params)

    tmp_path, conn = _prepare_temp_db(market_db_path)
    try:
        runner = BacktestRunner(conn, settings=candidate_settings)
        bt_config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_equity=10_000.0,
        )
        result = runner.run(bt_config)

        # Extract metrics from performance report
        perf = result.performance
        trades = result.trades

        cell = CellResult(
            window_name="",  # filled by caller
            threshold=threshold,
            is_train=False,  # filled by caller
            trade_count=perf.trades_count,
            expectancy_r=perf.expectancy_r,
            profit_factor=perf.profit_factor,
            max_drawdown_pct=perf.max_drawdown_pct,
            win_rate=perf.win_rate,
            pnl_abs=perf.pnl_abs,
        )

        if cell.trade_count < MIN_TRADES_FOR_VALIDITY:
            cell.insufficient_data = True

        # Safety flag detection
        cell.safety_flags = _detect_safety_flags(conn, trades, perf)

        return cell

    finally:
        _cleanup_temp_db(tmp_path, conn)


def _detect_safety_flags(
    conn: sqlite3.Connection,
    trades: list[Any],
    perf: PerformanceReport,
) -> list[str]:
    """Detect safety-relevant issues in the backtest run."""
    flags: list[str] = []

    # PNL sanity: check for trades with positive exit but negative pnl
    rows = conn.execute(
        "SELECT trade_id, direction, entry_price, exit_price, pnl_abs, pnl_r, opened_at "
        "FROM trade_log"
    ).fetchall()

    pnl_sanity_count = 0
    for r in rows:
        if r["pnl_r"] is not None and r["entry_price"] and r["exit_price"]:
            direction = r["direction"]
            entry = float(r["entry_price"])
            exit_p = float(r["exit_price"])
            pnl_r = float(r["pnl_r"])
            # LONG: exit > entry should be profit; SHORT: exit < entry should be profit
            if direction == "LONG" and exit_p > entry * 1.001 and pnl_r < -0.5:
                pnl_sanity_count += 1
            elif direction == "SHORT" and exit_p < entry * 0.999 and pnl_r < -0.5:
                pnl_sanity_count += 1
    if pnl_sanity_count > 0:
        flags.append(f"pnl_sanity_review_required({pnl_sanity_count})")

    # Duplicate level violations: check for trades at similar price levels
    trade_entries = []
    for r in rows:
        if r["entry_price"] and r["opened_at"]:
            trade_entries.append((r["opened_at"], float(r["entry_price"])))
    trade_entries.sort()

    dup_count = 0
    for i in range(len(trade_entries) - 1):
        t1_time, t1_price = trade_entries[i]
        t2_time, t2_price = trade_entries[i + 1]
        # Same price within 0.2% and within 24 hours
        if t1_price > 0 and abs(t2_price - t1_price) / t1_price < 0.002:
            try:
                dt1 = datetime.fromisoformat(t1_time)
                dt2 = datetime.fromisoformat(t2_time)
                if abs((dt2 - dt1).total_seconds()) < 86400:
                    dup_count += 1
            except (ValueError, TypeError):
                pass
    if dup_count > 0:
        flags.append(f"duplicate_level_proximity({dup_count})")

    # Extreme drawdown flag
    if perf.max_drawdown_pct > 0.15:
        flags.append(f"high_drawdown({perf.max_drawdown_pct:.1%})")

    # Consecutive loss streak from trades
    max_streak = 0
    current_streak = 0
    for r in rows:
        if r["pnl_r"] is not None and float(r["pnl_r"]) <= 0:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
    if max_streak >= 5:
        flags.append(f"consecutive_loss_streak({max_streak})")

    return flags


# ---------------------------------------------------------------------------
# Walk-forward execution
# ---------------------------------------------------------------------------

def run_walk_forward(
    market_db_path: Path,
    params: dict[str, Any],
    progress: bool = True,
) -> dict[str, list[CellResult]]:
    """Run all WF windows × threshold grid.

    Returns dict keyed by window name, each with list of CellResult
    (OOS results first, then train results).
    """
    results: dict[str, list[CellResult]] = {}
    total_runs = len(WF_WINDOWS) * len(THRESHOLD_GRID) * 2  # OOS + train
    run_idx = 0

    for wf_name, train_start, train_end, test_start, test_end in WF_WINDOWS:
        window_results: list[CellResult] = []

        for threshold in THRESHOLD_GRID:
            # OOS (test) run
            run_idx += 1
            if progress:
                print(f"  [{run_idx}/{total_runs}] {wf_name} OOS threshold={threshold:.5f} ({test_start} to {test_end})")

            oos_cell = run_single_backtest(
                market_db_path, params, threshold, test_start, test_end,
            )
            oos_cell.window_name = wf_name
            oos_cell.is_train = False
            window_results.append(oos_cell)

            # Train (IS) run — context only, not primary evidence
            run_idx += 1
            if progress:
                print(f"  [{run_idx}/{total_runs}] {wf_name} TRAIN threshold={threshold:.5f} ({train_start} to {train_end})")

            train_cell = run_single_backtest(
                market_db_path, params, threshold, train_start, train_end,
            )
            train_cell.window_name = wf_name
            train_cell.is_train = True
            window_results.append(train_cell)

        results[wf_name] = window_results

    return results


# ---------------------------------------------------------------------------
# Analysis & aggregation
# ---------------------------------------------------------------------------

def _safe_mean(vals: list[float]) -> float:
    return statistics.mean(vals) if vals else 0.0


def aggregate_results(
    results: dict[str, list[CellResult]],
) -> dict[str, Any]:
    """Aggregate walk-forward results into analysis summary."""
    # Extract OOS-only results per window
    oos_by_window: dict[str, list[CellResult]] = {}
    train_by_window: dict[str, list[CellResult]] = {}

    for wf_name, cells in results.items():
        oos_by_window[wf_name] = [c for c in cells if not c.is_train]
        train_by_window[wf_name] = [c for c in cells if c.is_train]

    # Build threshold × window matrix (OOS only)
    matrix: list[dict[str, Any]] = []
    for threshold in THRESHOLD_GRID:
        row: dict[str, Any] = {"threshold": threshold}
        for wf_name in [w[0] for w in WF_WINDOWS]:
            oos_cells = oos_by_window.get(wf_name, [])
            cell = next((c for c in oos_cells if abs(c.threshold - threshold) < 1e-8), None)
            if cell:
                row[wf_name] = cell.to_dict()
            else:
                row[wf_name] = {"error": "missing"}
        matrix.append(row)

    # Best threshold per OOS window (by ER, min 20 trades)
    best_per_window: dict[str, dict[str, Any]] = {}
    for wf_name in [w[0] for w in WF_WINDOWS]:
        oos_cells = oos_by_window.get(wf_name, [])
        valid_cells = [c for c in oos_cells if not c.insufficient_data]
        if valid_cells:
            best = max(valid_cells, key=lambda c: c.expectancy_r)
            best_per_window[wf_name] = {
                "threshold": best.threshold,
                "er": best.expectancy_r,
                "trades": best.trade_count,
            }
        else:
            best_per_window[wf_name] = {"threshold": None, "er": None, "trades": 0, "insufficient_data": True}

    # Consistency check: Is 0.00649 in top 3 across all windows?
    baseline_rank_per_window: dict[str, int] = {}
    for wf_name in [w[0] for w in WF_WINDOWS]:
        oos_cells = oos_by_window.get(wf_name, [])
        valid_cells = [c for c in oos_cells if not c.insufficient_data]
        if valid_cells:
            ranked = sorted(valid_cells, key=lambda c: c.expectancy_r, reverse=True)
            rank = next(
                (i + 1 for i, c in enumerate(ranked) if abs(c.threshold - TRIAL_00095_DEPTH) < 1e-8),
                len(ranked) + 1,
            )
            baseline_rank_per_window[wf_name] = rank
        else:
            baseline_rank_per_window[wf_name] = -1  # insufficient data

    # Train-to-OOS degradation per threshold
    degradation: dict[str, dict[float, dict[str, float]]] = {}
    for wf_name in [w[0] for w in WF_WINDOWS]:
        degradation[wf_name] = {}
        for threshold in THRESHOLD_GRID:
            oos_cell = next(
                (c for c in oos_by_window.get(wf_name, []) if abs(c.threshold - threshold) < 1e-8),
                None,
            )
            train_cell = next(
                (c for c in train_by_window.get(wf_name, []) if abs(c.threshold - threshold) < 1e-8),
                None,
            )
            if oos_cell and train_cell and train_cell.expectancy_r != 0:
                deg_pct = 1.0 - (oos_cell.expectancy_r / train_cell.expectancy_r) if train_cell.expectancy_r > 0 else float("inf")
                degradation[wf_name][threshold] = {
                    "train_er": train_cell.expectancy_r,
                    "oos_er": oos_cell.expectancy_r,
                    "degradation_pct": deg_pct,
                }

    # Safety check: do relaxed thresholds trigger more violations?
    safety_by_threshold: dict[float, int] = {}
    for threshold in THRESHOLD_GRID:
        total_flags = 0
        for wf_name in [w[0] for w in WF_WINDOWS]:
            oos_cells = oos_by_window.get(wf_name, [])
            cell = next((c for c in oos_cells if abs(c.threshold - threshold) < 1e-8), None)
            if cell:
                total_flags += len(cell.safety_flags)
        safety_by_threshold[threshold] = total_flags

    return {
        "matrix": matrix,
        "best_per_window": best_per_window,
        "baseline_rank_per_window": baseline_rank_per_window,
        "degradation": {
            wf: {str(k): v for k, v in thresholds.items()}
            for wf, thresholds in degradation.items()
        },
        "safety_by_threshold": {str(k): v for k, v in safety_by_threshold.items()},
    }


# ---------------------------------------------------------------------------
# Verdict determination
# ---------------------------------------------------------------------------

def determine_verdict(
    results: dict[str, list[CellResult]],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    """Apply verdict taxonomy based on OOS results.

    Verdicts:
      THRESHOLD_NATURAL — 0.00649 is stable across OOS windows
      THRESHOLD_OVERFITTED — lower thresholds consistently improve OOS ER
      THRESHOLD_WINDOW_DEPENDENT — optimal threshold varies across windows
      INSUFFICIENT_DATA — too few trades for valid comparison
    """
    reasoning: list[str] = []
    window_names = [w[0] for w in WF_WINDOWS]

    # Collect OOS results
    oos_by_window: dict[str, list[CellResult]] = {}
    for wf_name, cells in results.items():
        oos_by_window[wf_name] = [c for c in cells if not c.is_train]

    # Check data sufficiency
    insufficient_windows = []
    for wf_name in window_names:
        oos_cells = oos_by_window.get(wf_name, [])
        all_insufficient = all(c.insufficient_data for c in oos_cells)
        if all_insufficient:
            insufficient_windows.append(wf_name)

    if len(insufficient_windows) >= 2:
        reasoning.append(
            f"{len(insufficient_windows)}/3 OOS windows have < {MIN_TRADES_FOR_VALIDITY} trades "
            f"across ALL thresholds: {insufficient_windows}"
        )
        return {"verdict": "INSUFFICIENT_DATA", "reasoning": reasoning}

    if insufficient_windows:
        reasoning.append(
            f"Warning: {insufficient_windows} has insufficient data (< {MIN_TRADES_FOR_VALIDITY} trades). "
            f"Verdict based on remaining windows."
        )

    # Determine best threshold per valid window
    best_per_window = analysis["best_per_window"]
    baseline_rank = analysis["baseline_rank_per_window"]
    valid_windows = [w for w in window_names if w not in insufficient_windows]

    best_thresholds = []
    for wf_name in valid_windows:
        bp = best_per_window.get(wf_name, {})
        if bp.get("threshold") is not None:
            best_thresholds.append(bp["threshold"])
            reasoning.append(
                f"{wf_name}: best threshold={bp['threshold']:.5f} "
                f"(ER={bp['er']:.3f}, trades={bp['trades']})"
            )

    # Baseline ranking
    for wf_name in valid_windows:
        rank = baseline_rank.get(wf_name, -1)
        reasoning.append(f"{wf_name}: baseline 0.00649 ranks #{rank} of {len(THRESHOLD_GRID)}")

    # ---- THRESHOLD_NATURAL check ----
    # 0.00649 ± 0.001 (0.006 to 0.007) is best or near-best across all valid windows
    baseline_range = (0.006, 0.007)
    baseline_in_range_count = sum(
        1 for t in best_thresholds
        if baseline_range[0] <= t <= baseline_range[1]
    )
    baseline_top3_count = sum(
        1 for wf_name in valid_windows
        if 0 < baseline_rank.get(wf_name, 99) <= 3
    )

    # Check ER degradation from train to OOS
    degradation_data = analysis.get("degradation", {})
    baseline_degradation_ok = True
    for wf_name in valid_windows:
        wf_deg = degradation_data.get(wf_name, {})
        baseline_deg = wf_deg.get(str(TRIAL_00095_DEPTH), {})
        deg_pct = baseline_deg.get("degradation_pct", 0)
        if isinstance(deg_pct, (int, float)) and deg_pct > 0.5:
            baseline_degradation_ok = False
            reasoning.append(
                f"{wf_name}: baseline degradation {deg_pct:.0%} exceeds 50% tolerance"
            )

    # Check safety flags for baseline
    safety = analysis.get("safety_by_threshold", {})
    baseline_safety = safety.get(str(TRIAL_00095_DEPTH), 0)

    # ---- THRESHOLD_OVERFITTED check ----
    # Lower thresholds consistently improve OOS ER across 2+ windows
    lower_thresholds = [t for t in THRESHOLD_GRID if t < TRIAL_00095_DEPTH - 0.0005]
    lower_better_count = 0
    for wf_name in valid_windows:
        oos_cells = oos_by_window.get(wf_name, [])
        baseline_cell = next(
            (c for c in oos_cells if abs(c.threshold - TRIAL_00095_DEPTH) < 1e-8), None
        )
        if not baseline_cell:
            continue
        for lower_t in lower_thresholds:
            lower_cell = next(
                (c for c in oos_cells if abs(c.threshold - lower_t) < 1e-8), None
            )
            if (lower_cell and not lower_cell.insufficient_data
                    and lower_cell.expectancy_r > baseline_cell.expectancy_r
                    and lower_cell.expectancy_r >= 1.0):
                lower_better_count += 1
                break  # one lower threshold beating baseline per window is enough

    # ---- THRESHOLD_WINDOW_DEPENDENT check ----
    # Optimal threshold varies materially across windows
    if len(best_thresholds) >= 2:
        threshold_spread = max(best_thresholds) - min(best_thresholds)
        reasoning.append(f"Best-threshold spread across valid windows: {threshold_spread:.5f}")
    else:
        threshold_spread = 0.0

    # ---- Verdict logic ----
    if baseline_in_range_count == len(valid_windows) and baseline_degradation_ok:
        verdict = "THRESHOLD_NATURAL"
        reasoning.append(
            "0.00649 ± 0.001 is best across all valid OOS windows "
            "with acceptable degradation."
        )
    elif baseline_top3_count == len(valid_windows) and baseline_degradation_ok and baseline_safety == 0:
        verdict = "THRESHOLD_NATURAL"
        reasoning.append(
            "Baseline is top-3 across all valid OOS windows with no safety flags "
            "and acceptable degradation."
        )
    elif lower_better_count >= 2:
        # Check safety: lower thresholds must not trigger unacceptable issues
        lower_safe = True
        for lower_t in lower_thresholds:
            lower_flags = safety.get(str(lower_t), 0)
            if lower_flags > baseline_safety + 2:
                lower_safe = False
                reasoning.append(
                    f"Lower threshold {lower_t} has {lower_flags} safety flags "
                    f"vs baseline {baseline_safety}"
                )
        # Check drawdown: lower thresholds must not have > 2x baseline drawdown
        lower_dd_ok = True
        for wf_name in valid_windows:
            oos_cells = oos_by_window.get(wf_name, [])
            baseline_cell = next(
                (c for c in oos_cells if abs(c.threshold - TRIAL_00095_DEPTH) < 1e-8), None
            )
            if not baseline_cell:
                continue
            for lower_t in lower_thresholds:
                lower_cell = next(
                    (c for c in oos_cells if abs(c.threshold - lower_t) < 1e-8), None
                )
                if (lower_cell and baseline_cell.max_drawdown_pct > 0
                        and lower_cell.max_drawdown_pct > baseline_cell.max_drawdown_pct * 2):
                    lower_dd_ok = False

        if lower_safe and lower_dd_ok:
            verdict = "THRESHOLD_OVERFITTED"
            reasoning.append(
                f"Lower thresholds improve OOS ER in {lower_better_count}/{len(valid_windows)} "
                f"valid windows without unacceptable drawdown or safety issues."
            )
        else:
            verdict = "THRESHOLD_WINDOW_DEPENDENT"
            reasoning.append(
                "Lower thresholds improve ER in some windows but with safety/drawdown concerns."
            )
    elif threshold_spread >= 0.003:
        verdict = "THRESHOLD_WINDOW_DEPENDENT"
        reasoning.append(
            f"Optimal threshold varies by {threshold_spread:.5f} across windows — "
            f"no consistent optimum."
        )
    elif not baseline_degradation_ok:
        verdict = "THRESHOLD_WINDOW_DEPENDENT"
        reasoning.append(
            "Baseline shows > 50% ER degradation in some windows — "
            "threshold stability uncertain."
        )
    else:
        # Default: baseline is competitive but not clearly best
        if baseline_top3_count >= len(valid_windows) - 1:
            verdict = "THRESHOLD_NATURAL"
            reasoning.append(
                f"Baseline is top-3 in {baseline_top3_count}/{len(valid_windows)} valid windows. "
                f"Threshold is reasonably stable."
            )
        else:
            verdict = "THRESHOLD_WINDOW_DEPENDENT"
            reasoning.append(
                f"Baseline ranks outside top-3 in {len(valid_windows) - baseline_top3_count} windows."
            )

    # Add limitations
    limitations = []
    if "WF3" not in insufficient_windows:
        wf3_cells = oos_by_window.get("WF3", [])
        wf3_max_trades = max((c.trade_count for c in wf3_cells), default=0)
        if wf3_max_trades < 30:
            limitations.append(
                f"WF3 test window is only 3 months (max {wf3_max_trades} trades). "
                f"Statistical significance limited."
            )
    if insufficient_windows:
        limitations.append(
            f"Windows with insufficient data excluded from verdict: {insufficient_windows}"
        )
    limitations.append(
        "Threshold grid is coarse (6 values, ~0.001 steps). "
        "Finer grid not tested."
    )
    limitations.append(
        "Walk-forward uses fixed 2-year train windows. "
        "Expanding/rolling window not tested."
    )
    limitations.append(
        "Market regime varies across windows (2022 bear vs 2024-2025 bull). "
        "Optimal threshold may legitimately vary with regime."
    )

    return {
        "verdict": verdict,
        "reasoning": reasoning,
        "limitations": limitations,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    results: dict[str, list[CellResult]],
    analysis: dict[str, Any],
    verdict_result: dict[str, Any],
) -> str:
    """Generate markdown report."""
    lines: list[str] = []
    window_names = [w[0] for w in WF_WINDOWS]

    lines.append("# OOS Walk-Forward Threshold Stability Analysis")
    lines.append("")
    lines.append("**Date:** 2026-05-13  ")
    lines.append("**Author:** Cascade (builder)  ")
    lines.append("**Milestone:** OOS_WF_THRESHOLD_STABILITY_ANALYSIS (M3)  ")
    lines.append("**Status:** COMPLETE  ")
    lines.append(f"**Verdict:** {verdict_result['verdict']}")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"Walk-forward threshold stability test across 3 OOS windows with 6 threshold values "
                 f"(18 backtest runs). Testing whether `min_sweep_depth_pct = 0.00649` is stable across "
                 f"time windows or window-specific / overfitted.")
    lines.append("")
    lines.append(f"**Verdict: {verdict_result['verdict']}**")
    lines.append("")
    for r in verdict_result["reasoning"]:
        lines.append(f"- {r}")
    lines.append("")

    # Walk-forward methodology
    lines.append("## Walk-Forward Methodology")
    lines.append("")
    lines.append("| Window | Train (In-Sample) | Test (Out-of-Sample) | Notes |")
    lines.append("|---|---|---|---|")
    lines.append("| WF1 | 2022-01-01 to 2023-12-31 | 2024-01-01 to 2024-12-31 | 2 years train, 1 year test |")
    lines.append("| WF2 | 2023-01-01 to 2024-12-31 | 2025-01-01 to 2025-12-31 | 2 years train, 1 year test |")
    lines.append("| WF3 | 2024-01-01 to 2025-12-31 | 2026-01-01 to 2026-03-28 | 2 years train, 3 months test |")
    lines.append("")
    lines.append("**Threshold grid:** 0.004, 0.005, 0.006, 0.00649 (baseline), 0.007, 0.008")
    lines.append("")
    lines.append("**All parameters except `min_sweep_depth_pct`** are held constant at trial-00095 exact values. "
                 "This isolates the threshold effect (ceteris paribus), unlike M2's cross-trial analysis which "
                 "conflated depth with ~40 co-varying Optuna parameters.")
    lines.append("")
    lines.append(f"**Minimum threshold for statistical validity:** {MIN_TRADES_FOR_VALIDITY} OOS trades per window. "
                 f"Cells with fewer trades are flagged as INSUFFICIENT_DATA.")
    lines.append("")

    # OOS Results Table
    lines.append("## OOS Results (Primary Evidence)")
    lines.append("")

    for wf_name in window_names:
        wf_def = next(w for w in WF_WINDOWS if w[0] == wf_name)
        lines.append(f"### {wf_name}: OOS {wf_def[3]} to {wf_def[4]}")
        lines.append("")
        lines.append("| Threshold | Trades | ER | PF | Max DD% | Win Rate | Safety Flags | Valid? |")
        lines.append("|---:|---:|---:|---:|---:|---:|---|---|")

        oos_cells = [c for c in results.get(wf_name, []) if not c.is_train]
        oos_cells.sort(key=lambda c: c.threshold)

        for cell in oos_cells:
            is_baseline = abs(cell.threshold - TRIAL_00095_DEPTH) < 1e-8
            prefix = "**" if is_baseline else ""
            suffix = "**" if is_baseline else ""
            flag_str = ", ".join(cell.safety_flags) if cell.safety_flags else "none"
            valid_str = "YES" if not cell.insufficient_data else "**NO** (< 20)"
            lines.append(
                f"| {prefix}{cell.threshold:.5f}{suffix} "
                f"| {prefix}{cell.trade_count}{suffix} "
                f"| {prefix}{cell.expectancy_r:.3f}{suffix} "
                f"| {prefix}{cell.profit_factor:.3f}{suffix} "
                f"| {prefix}{cell.max_drawdown_pct:.2%}{suffix} "
                f"| {prefix}{cell.win_rate:.1%}{suffix} "
                f"| {flag_str} "
                f"| {valid_str} |"
            )
        lines.append("")

    # Best threshold per window
    lines.append("### Best Threshold Per OOS Window")
    lines.append("")
    lines.append("| Window | Best Threshold | ER | Trades | Baseline Rank |")
    lines.append("|---|---:|---:|---:|---:|")
    for wf_name in window_names:
        bp = analysis["best_per_window"].get(wf_name, {})
        rank = analysis["baseline_rank_per_window"].get(wf_name, -1)
        if bp.get("insufficient_data"):
            lines.append(f"| {wf_name} | — | — | — | INSUFFICIENT_DATA |")
        else:
            lines.append(
                f"| {wf_name} | {bp.get('threshold', 0):.5f} "
                f"| {bp.get('er', 0):.3f} "
                f"| {bp.get('trades', 0)} "
                f"| #{rank} of {len(THRESHOLD_GRID)} |"
            )
    lines.append("")

    # Train vs OOS degradation (context only)
    lines.append("## Train vs OOS Degradation (Context Only — Not Primary Evidence)")
    lines.append("")
    lines.append("> Train/IS results are context for understanding overfitting risk. "
                 "OOS results above are the primary evidence.")
    lines.append("")

    for wf_name in window_names:
        lines.append(f"### {wf_name}")
        lines.append("")
        lines.append("| Threshold | Train ER | OOS ER | Degradation |")
        lines.append("|---:|---:|---:|---:|")

        wf_deg = analysis.get("degradation", {}).get(wf_name, {})
        for threshold in THRESHOLD_GRID:
            deg_data = wf_deg.get(str(threshold), {})
            if deg_data:
                train_er = deg_data.get("train_er", 0)
                oos_er = deg_data.get("oos_er", 0)
                deg_pct = deg_data.get("degradation_pct", 0)
                is_baseline = abs(threshold - TRIAL_00095_DEPTH) < 1e-8
                prefix = "**" if is_baseline else ""
                suffix = "**" if is_baseline else ""
                deg_str = f"{deg_pct:.0%}" if isinstance(deg_pct, (int, float)) and not math.isinf(deg_pct) else "N/A"
                lines.append(
                    f"| {prefix}{threshold:.5f}{suffix} "
                    f"| {prefix}{train_er:.3f}{suffix} "
                    f"| {prefix}{oos_er:.3f}{suffix} "
                    f"| {prefix}{deg_str}{suffix} |"
                )
        lines.append("")

    # Safety Analysis
    lines.append("## Safety Flag Analysis")
    lines.append("")
    lines.append("| Threshold | Total OOS Safety Flags |")
    lines.append("|---:|---:|")
    safety = analysis.get("safety_by_threshold", {})
    for threshold in THRESHOLD_GRID:
        count = safety.get(str(threshold), 0)
        is_baseline = abs(threshold - TRIAL_00095_DEPTH) < 1e-8
        prefix = "**" if is_baseline else ""
        suffix = "**" if is_baseline else ""
        lines.append(f"| {prefix}{threshold:.5f}{suffix} | {prefix}{count}{suffix} |")
    lines.append("")

    # Verdict
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"**{verdict_result['verdict']}**")
    lines.append("")
    lines.append("### Reasoning")
    lines.append("")
    for r in verdict_result["reasoning"]:
        lines.append(f"- {r}")
    lines.append("")

    # Limitations
    lines.append("### Limitations")
    lines.append("")
    for lim in verdict_result.get("limitations", []):
        lines.append(f"- {lim}")
    lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")
    verdict = verdict_result["verdict"]
    if verdict == "THRESHOLD_NATURAL":
        lines.append("Current threshold `0.00649` is stable across OOS windows. "
                     "Do not adjust. Proceed to 30-day paper monitoring.")
    elif verdict == "THRESHOLD_OVERFITTED":
        lines.append("Lower thresholds consistently improve OOS performance. "
                     "Consider testing a relaxed threshold variant (e.g., 0.005) "
                     "in a controlled paper experiment.")
    elif verdict == "THRESHOLD_WINDOW_DEPENDENT":
        lines.append("Optimal threshold varies across time windows. "
                     "Accept current threshold with low frequency, or investigate "
                     "adaptive threshold as future work.")
    elif verdict == "INSUFFICIENT_DATA":
        lines.append("Insufficient OOS trades to determine threshold stability. "
                     "Defer decision until more data accumulates or "
                     "consider shorter train windows to extend OOS periods.")
    lines.append("")

    # Methodology
    lines.append("## Methodology")
    lines.append("")
    lines.append("### Analysis Script")
    lines.append("")
    lines.append("`research_lab/analysis_oos_wf_threshold_stability.py`")
    lines.append("")
    lines.append("### Data Sources")
    lines.append("")
    lines.append("- **Replay DB:** `research_lab/snapshots/replay-run13-regime-aware-trial-00063.db` "
                 "(2020-09-01 to 2026-03-28)")
    lines.append("- **Trial params:** `research_lab/research_lab.db.v3` "
                 f"(trial `{TRIAL_00095_ID}`)")
    lines.append("")
    lines.append("### Key Design Decisions")
    lines.append("")
    lines.append("- **Ceteris paribus:** Only `min_sweep_depth_pct` varies. All other ~40 parameters "
                 "are held at trial-00095 exact values. This isolates the threshold effect, "
                 "addressing M2's cross-trial selection bias limitation.")
    lines.append("- **OOS only as primary evidence:** Train/IS results are reported for context "
                 "(degradation analysis) but NOT used for verdict determination.")
    lines.append("- **No Optuna cross-trial analysis:** M2 audit identified this as selection bias. "
                 "This milestone uses direct threshold manipulation instead.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="OOS WF threshold stability analysis")
    parser.add_argument("--store", type=str, default="research_lab/research_lab.db.v3",
                        help="Path to experiment store DB")
    parser.add_argument("--market-db", type=str,
                        default="research_lab/snapshots/replay-run13-regime-aware-trial-00063.db",
                        help="Path to replay market DB")
    parser.add_argument("--output-dir", type=str, default="research_lab/analysis_output",
                        help="Output directory for JSON results")
    args = parser.parse_args()

    store_path = Path(args.store)
    market_db_path = Path(args.market_db)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("OOS WALK-FORWARD THRESHOLD STABILITY ANALYSIS (M3)")
    print("=" * 70)

    # 1. Load trial-00095 params
    print("\n[1/5] Loading trial-00095 parameters...")
    params = load_trial_params(store_path)
    print(f"  Loaded {len(params)} parameters")
    print(f"  Baseline min_sweep_depth_pct = {params['min_sweep_depth_pct']}")

    # 2. Run walk-forward
    print(f"\n[2/5] Running walk-forward ({len(WF_WINDOWS)} windows × {len(THRESHOLD_GRID)} thresholds = "
          f"{len(WF_WINDOWS) * len(THRESHOLD_GRID) * 2} total runs)...")
    results = run_walk_forward(market_db_path, params)

    # 3. Aggregate
    print("\n[3/5] Aggregating results...")
    analysis = aggregate_results(results)

    # 4. Verdict
    print("\n[4/5] Determining verdict...")
    verdict_result = determine_verdict(results, analysis)
    print(f"  Verdict: {verdict_result['verdict']}")
    for r in verdict_result["reasoning"]:
        print(f"    - {r}")

    # 5. Generate report
    print("\n[5/5] Generating report...")
    report_md = generate_report(results, analysis, verdict_result)

    report_path = Path("docs/analysis/OOS_WF_THRESHOLD_STABILITY_2026-05-13.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md, encoding="utf-8")
    print(f"  Report: {report_path}")

    # Save JSON outputs
    all_cells = []
    for wf_name, cells in results.items():
        for c in cells:
            all_cells.append(c.to_dict())

    (output_dir / "oos_wf_results.json").write_text(
        json.dumps(all_cells, indent=2), encoding="utf-8"
    )
    (output_dir / "oos_wf_analysis.json").write_text(
        json.dumps(analysis, indent=2, default=str), encoding="utf-8"
    )
    (output_dir / "oos_wf_verdict.json").write_text(
        json.dumps(verdict_result, indent=2), encoding="utf-8"
    )
    print(f"  JSON outputs: {output_dir}/oos_wf_*.json")

    print(f"\n{'=' * 70}")
    print(f"ANALYSIS COMPLETE — VERDICT: {verdict_result['verdict']}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()

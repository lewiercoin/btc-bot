#!/usr/bin/env python3
"""BTC 15m trend pullback reaccept feasibility study.

Offline-only Research Lab script. It tests a LONG-only trend-pullback setup:
4h trend alignment, pre-frozen 15m equal-low support, multi-bar pullback into
that support, and 15m reacceptance close with optional fixed TFI confirmation.

No production, PAPER, runtime, settings, core, execution, or orchestrator files
are modified or imported by this script.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from research_lab.evaluators.gate_evaluator import Gate, evaluate_gates
from research_lab.experiments.api import create_experiment, record_result
from research_lab.experiments.manifest import create_manifest


SYMBOL = "BTCUSDT"
DB_REPLAY = Path("research_lab/snapshots/replay-run13-regime-aware-trial-00063.db")
REGISTRY_PATH = Path("research_lab/experiments/experiments.db")
HYPOTHESIS_PATH = Path("research_lab/hypotheses/active/trend_pullback_reaccept.json")
REPORT_PATH = Path("docs/analysis/TREND_PULLBACK_REACCEPT_FEASIBILITY_2026-05-18.md")
BASELINE_TRADES_PATH = Path("research_lab/analysis_output/trial_00095_trades.json")

ANALYSIS_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
ANALYSIS_END = datetime(2026, 3, 28, tzinfo=timezone.utc)
LOOKBACK_START = ANALYSIS_START - timedelta(days=120)

BASELINE = {
    "trade_count": 47,
    "expectancy_r": 2.110,
    "profit_factor": 3.95,
    "max_dd_r": 4.49,
    "trades_per_month": 1.8,
}

FEE_RATE = 0.0004
SLIPPAGE_BPS = 3.0
MAX_HOLD_BARS = 96


@dataclass(frozen=True)
class Candle:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class AggBucket:
    bucket_time: datetime
    taker_buy_volume: float
    taker_sell_volume: float
    tfi: float
    cvd: float


@dataclass(frozen=True)
class SetupVariant:
    variant_id: str
    ema_gap_pct_threshold: float
    pullback_max_bars: int
    reclaim_buffer_atr: float
    tfi_threshold: float | None

    def to_config(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "ema_gap_pct_threshold": self.ema_gap_pct_threshold,
            "pullback_max_bars": self.pullback_max_bars,
            "reclaim_buffer_atr": self.reclaim_buffer_atr,
            "tfi_threshold": self.tfi_threshold,
            "structure_lookback_bars": 50,
            "equal_level_tol_atr": 0.25,
            "equal_level_min_hits": 2,
            "equal_level_min_age_bars": 5,
            "stop_atr_below_level": 0.75,
            "target_r": 2.5,
            "max_hold_bars": MAX_HOLD_BARS,
        }


@dataclass(frozen=True)
class ReacceptSignal:
    variant_id: str
    trigger_idx: int
    entry_idx: int
    trigger_time: datetime
    entry_time: datetime
    frozen_level: float
    atr_15m: float
    ema50_4h: float
    ema200_4h: float
    ema_gap_pct: float
    tfi_15m: float
    entry_price: float
    stop_loss: float
    take_profit: float
    reasons: tuple[str, ...]
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReacceptTrade:
    signal: ReacceptSignal
    exit_idx: int
    exit_time: datetime
    exit_price: float
    pnl_r: float
    exit_reason: str
    mae_r: float
    mfe_r: float

    @property
    def entry_time(self) -> datetime:
        return self.signal.entry_time


@dataclass
class SetupRun:
    variant: SetupVariant
    bars_evaluated: int = 0
    trend_pass_count: int = 0
    frozen_level_count: int = 0
    pullback_count: int = 0
    reclaim_count: int = 0
    tfi_pass_count: int = 0
    signals: list[ReacceptSignal] = field(default_factory=list)
    trades: list[ReacceptTrade] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    gate_verdict: str = "BLOCKED"
    gate_summary: str = ""
    gate_results: list[dict[str, Any]] = field(default_factory=list)


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def compute_ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    if period <= 1:
        return float(values[-1])
    multiplier = 2 / (period + 1)
    ema = float(values[0])
    for value in values[1:]:
        ema = (float(value) - ema) * multiplier + ema
    return ema


def compute_atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    true_ranges: list[float] = []
    for idx in range(1, len(candles)):
        prev_close = candles[idx - 1].close
        true_ranges.append(max(
            candles[idx].high - candles[idx].low,
            abs(candles[idx].high - prev_close),
            abs(candles[idx].low - prev_close),
        ))
    window = true_ranges[-period:] if len(true_ranges) >= period else true_ranges
    return mean(window) if window else 0.0


def load_candles(conn: sqlite3.Connection, timeframe: str, start: datetime, end: datetime) -> list[Candle]:
    rows = conn.execute(
        """
        SELECT open_time, open, high, low, close, volume
        FROM candles
        WHERE symbol = ? AND timeframe = ?
          AND open_time >= ? AND open_time <= ?
        ORDER BY open_time ASC
        """,
        (SYMBOL, timeframe, start.isoformat(), end.isoformat()),
    ).fetchall()
    return [
        Candle(_parse_ts(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]))
        for r in rows
    ]


def load_agg_60s(conn: sqlite3.Connection, start: datetime, end: datetime) -> dict[datetime, AggBucket]:
    rows = conn.execute(
        """
        SELECT bucket_time, taker_buy_volume, taker_sell_volume, tfi, cvd
        FROM aggtrade_buckets
        WHERE symbol = ? AND timeframe = '60s'
          AND bucket_time >= ? AND bucket_time <= ?
        ORDER BY bucket_time ASC
        """,
        (SYMBOL, start.isoformat(), end.isoformat()),
    ).fetchall()
    return {
        _parse_ts(r[0]): AggBucket(_parse_ts(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]))
        for r in rows
    }


def aggregate_tfi_60s(agg_60s: dict[datetime, AggBucket], candle_open: datetime) -> float:
    buy = 0.0
    sell = 0.0
    for minute in range(15):
        bucket = agg_60s.get(candle_open + timedelta(minutes=minute))
        if bucket is None:
            continue
        buy += bucket.taker_buy_volume
        sell += bucket.taker_sell_volume
    total = buy + sell
    return (buy - sell) / total if total > 0 else 0.0


def completed_4h_context(candles_4h: list[Candle], target_open: datetime) -> list[Candle]:
    cutoff = target_open - timedelta(hours=4)
    times = _candle_times(candles_4h)
    return candles_4h[:bisect_right(times, cutoff)]


_TIMES_CACHE: dict[tuple[int, int], list[datetime]] = {}
_TREND_CACHE: dict[tuple[int, int, datetime], tuple[float, float, float]] = {}


def _candle_times(candles: list[Candle]) -> list[datetime]:
    key = (id(candles), len(candles))
    cached = _TIMES_CACHE.get(key)
    if cached is None:
        cached = [c.open_time for c in candles]
        _TIMES_CACHE[key] = cached
    return cached


def trend_context(candles_4h: list[Candle], target_open: datetime) -> tuple[float, float, float]:
    key = (id(candles_4h), len(candles_4h), target_open)
    if key in _TREND_CACHE:
        return _TREND_CACHE[key]
    context = completed_4h_context(candles_4h, target_open)
    if len(context) < 200:
        result = (0.0, 0.0, 0.0)
        _TREND_CACHE[key] = result
        return result
    closes = [c.close for c in context]
    ema50 = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200)
    gap = (ema50 - ema200) / ema200 if ema200 else 0.0
    result = (ema50, ema200, gap)
    _TREND_CACHE[key] = result
    return result


def detect_equal_low_levels(
    candles: list[Candle],
    trigger_idx: int,
    *,
    lookback_bars: int = 50,
    min_age_bars: int = 5,
    tolerance_atr: float = 0.25,
    min_hits: int = 2,
) -> list[float]:
    window_end = trigger_idx - min_age_bars
    if window_end <= 0:
        return []
    window_start = max(0, window_end - lookback_bars)
    prior = candles[window_start:window_end]
    atr = compute_atr(candles[max(0, window_end - 60):window_end])
    if len(prior) < min_hits or atr <= 0:
        return []
    tolerance = atr * tolerance_atr
    lows = sorted((window_start + idx, c.low) for idx, c in enumerate(prior))
    lows.sort(key=lambda item: item[1])
    clusters: list[list[tuple[int, float]]] = []
    current = [lows[0]]
    for item in lows[1:]:
        if abs(item[1] - current[-1][1]) <= tolerance:
            current.append(item)
        else:
            clusters.append(current)
            current = [item]
    clusters.append(current)

    levels: list[float] = []
    for cluster in clusters:
        if len(cluster) < min_hits:
            continue
        indices = [idx for idx, _ in cluster]
        if max(indices) - min(indices) < min_age_bars:
            continue
        levels.append(round(mean(price for _, price in cluster), 2))
    return levels


def find_reaccept_signal(
    candles_15m: list[Candle],
    candles_4h: list[Candle],
    agg_60s: dict[datetime, AggBucket],
    idx: int,
    variant: SetupVariant,
) -> ReacceptSignal | None:
    if idx + 1 >= len(candles_15m):
        return None
    trigger = candles_15m[idx]
    setup_context = candles_15m[max(0, idx - 80):idx]
    atr = compute_atr(setup_context)
    if atr <= 0:
        return None

    ema50, ema200, ema_gap = trend_context(candles_4h, trigger.open_time)
    if ema50 <= 0 or ema200 <= 0 or ema50 <= ema200 or ema_gap < variant.ema_gap_pct_threshold:
        return None

    levels = detect_equal_low_levels(candles_15m, idx)
    if not levels:
        return None

    reclaim_buffer = atr * variant.reclaim_buffer_atr
    pullback_start = max(0, idx - variant.pullback_max_bars)
    pullback_window = candles_15m[pullback_start:idx]
    if not pullback_window:
        return None

    eligible_levels: list[tuple[float, int]] = []
    for level in levels:
        pullback_hits = [bar_idx for bar_idx, bar in enumerate(pullback_window, start=pullback_start) if bar.low < level]
        if not pullback_hits:
            continue
        if trigger.close <= level + reclaim_buffer:
            continue
        # Avoid selecting stale levels far below the current reclaim.
        if trigger.close - level > 2.0 * atr:
            continue
        eligible_levels.append((level, max(pullback_hits)))
    if not eligible_levels:
        return None

    # Use the most recently tested level, then nearest to trigger close.
    level = sorted(eligible_levels, key=lambda item: (item[1], item[0]), reverse=True)[0][0]
    tfi = aggregate_tfi_60s(agg_60s, trigger.open_time)
    if variant.tfi_threshold is not None and tfi < variant.tfi_threshold:
        return None

    entry_bar = candles_15m[idx + 1]
    stop_loss = level - 0.75 * atr
    entry_price = entry_bar.open
    risk = entry_price - stop_loss
    if risk <= 0:
        return None
    take_profit = entry_price + 2.5 * risk
    return ReacceptSignal(
        variant_id=variant.variant_id,
        trigger_idx=idx,
        entry_idx=idx + 1,
        trigger_time=trigger.open_time,
        entry_time=entry_bar.open_time,
        frozen_level=level,
        atr_15m=atr,
        ema50_4h=ema50,
        ema200_4h=ema200,
        ema_gap_pct=ema_gap,
        tfi_15m=tfi,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reasons=(
            "4h_ema_trend_aligned",
            "frozen_equal_low_support",
            "prior_pullback_below_level",
            "15m_reaccept_close",
            "fixed_tfi_filter_pass" if variant.tfi_threshold is not None else "tfi_diagnostic_only",
        ),
        diagnostics={
            "reclaim_buffer_atr": variant.reclaim_buffer_atr,
            "pullback_max_bars": variant.pullback_max_bars,
        },
    )


def simulate_trade(
    signal: ReacceptSignal,
    candles_15m: list[Candle],
    *,
    cost_multiplier: float = 1.0,
) -> ReacceptTrade | None:
    future = candles_15m[signal.entry_idx:signal.entry_idx + MAX_HOLD_BARS]
    if not future:
        return None
    slip = signal.entry_price * SLIPPAGE_BPS / 10000 * cost_multiplier
    entry = signal.entry_price + slip
    stop = signal.stop_loss
    risk = entry - stop
    if risk <= 0:
        return None
    target = entry + 2.5 * risk
    mae = 0.0
    mfe = 0.0
    exit_price = future[-1].close
    exit_time = future[-1].open_time
    exit_idx = signal.entry_idx + len(future) - 1
    exit_reason = "timeout"
    for offset, candle in enumerate(future):
        mae = min(mae, (candle.low - entry) / risk)
        mfe = max(mfe, (candle.high - entry) / risk)
        if candle.low <= stop:
            exit_price = stop - slip
            exit_time = candle.open_time
            exit_idx = signal.entry_idx + offset
            exit_reason = "stop_loss"
            break
        if candle.high >= target:
            exit_price = target - slip
            exit_time = candle.open_time
            exit_idx = signal.entry_idx + offset
            exit_reason = "take_profit"
            break
    fee_cost = (entry * FEE_RATE + exit_price * FEE_RATE) * cost_multiplier
    pnl_r = ((exit_price - entry) - fee_cost) / risk
    return ReacceptTrade(signal, exit_idx, exit_time, exit_price, pnl_r, exit_reason, mae, mfe)


def run_variant(
    candles_15m: list[Candle],
    candles_4h: list[Candle],
    agg_60s: dict[datetime, AggBucket],
    variant: SetupVariant,
) -> SetupRun:
    run = SetupRun(variant)
    start_idx = next((idx for idx, candle in enumerate(candles_15m) if candle.open_time >= ANALYSIS_START), 0)
    idx = max(start_idx, 260)
    while idx < len(candles_15m) - 1:
        candle = candles_15m[idx]
        if candle.open_time > ANALYSIS_END:
            break
        run.bars_evaluated += 1
        ema50, ema200, gap = trend_context(candles_4h, candle.open_time)
        if ema50 > ema200 and gap >= variant.ema_gap_pct_threshold:
            run.trend_pass_count += 1
        levels = detect_equal_low_levels(candles_15m, idx)
        if levels:
            run.frozen_level_count += 1
        signal = find_reaccept_signal(candles_15m, candles_4h, agg_60s, idx, variant)
        if signal is None:
            idx += 1
            continue
        run.pullback_count += 1
        run.reclaim_count += 1
        if variant.tfi_threshold is None or signal.tfi_15m >= variant.tfi_threshold:
            run.tfi_pass_count += 1
        trade = simulate_trade(signal, candles_15m)
        if trade is None:
            idx += 1
            continue
        run.signals.append(signal)
        run.trades.append(trade)
        idx = max(idx + 1, trade.exit_idx + 1)
    return run


def max_drawdown_r(pnls: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        cumulative += pnl
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
    return max_dd


def load_baseline_entry_times(path: Path = BASELINE_TRADES_PATH) -> set[datetime]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {_parse_ts(item["opened_at"]) for item in payload if "opened_at" in item}


def concentration_by_count(trades: list[ReacceptTrade]) -> dict[str, Any]:
    monthly: dict[str, int] = defaultdict(int)
    quarterly: dict[str, int] = defaultdict(int)
    for trade in trades:
        month = trade.entry_time.strftime("%Y-%m")
        quarter = (trade.entry_time.month - 1) // 3 + 1
        monthly[month] += 1
        quarterly[f"{trade.entry_time.year}-Q{quarter}"] += 1
    total = len(trades)
    top_month = max(monthly, key=monthly.get) if monthly else ""
    top_quarter = max(quarterly, key=quarterly.get) if quarterly else ""
    return {
        "max_month_trade_share": monthly[top_month] / total if total and top_month else 0.0,
        "max_quarter_trade_share": quarterly[top_quarter] / total if total and top_quarter else 0.0,
        "top_month": top_month,
        "top_quarter": top_quarter,
    }


def fold_metrics(trades: list[ReacceptTrade]) -> dict[str, Any]:
    folds = [
        ("2024_H1", datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 7, 1, tzinfo=timezone.utc)),
        ("2024_H2", datetime(2024, 7, 1, tzinfo=timezone.utc), datetime(2025, 1, 1, tzinfo=timezone.utc)),
        ("2025_H1", datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 7, 1, tzinfo=timezone.utc)),
        ("2025_H2_2026_Q1", datetime(2025, 7, 1, tzinfo=timezone.utc), ANALYSIS_END + timedelta(days=1)),
    ]
    rows = []
    passing = 0
    for name, start, end in folds:
        subset = [trade for trade in trades if start <= trade.entry_time < end]
        metrics = compute_metrics(subset, baseline_times=set())
        er = metrics["expectancy_r"]
        if subset and er > 1.0:
            passing += 1
        rows.append({"fold": name, "start": start.date().isoformat(), "end": end.date().isoformat(), **metrics})
    return {"folds": rows, "folds_er_gt_1": passing}


def compute_metrics(trades: list[ReacceptTrade], *, baseline_times: set[datetime]) -> dict[str, Any]:
    if not trades:
        return {
            "trade_count": 0,
            "expectancy_r": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "max_dd_r": 0.0,
            "frequency_ratio_vs_baseline": 0.0,
            "er_at_15x_cost": 0.0,
            "er_at_2x_cost": 0.0,
            "timeout_share": 0.0,
            "overlap_vs_trial_00095": 0.0,
            "max_month_trade_share": 0.0,
            "max_quarter_trade_share": 0.0,
        }
    pnls = [trade.pnl_r for trade in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    # Recompute cost stress from base pnl by adding incremental costs per trade.
    stressed_15 = [_stress_pnl(trade, 1.5) for trade in trades]
    stressed_2 = [_stress_pnl(trade, 2.0) for trade in trades]
    concentration = concentration_by_count(trades)
    overlaps = sum(1 for trade in trades if trade.entry_time in baseline_times)
    return {
        "trade_count": len(trades),
        "expectancy_r": sum(pnls) / len(pnls),
        "profit_factor": gross_profit / gross_loss if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": len(wins) / len(trades) * 100.0,
        "max_dd_r": max_drawdown_r(pnls),
        "frequency_ratio_vs_baseline": len(trades) / BASELINE["trade_count"],
        "median_r": median(pnls),
        "avg_mae_r": sum(t.mae_r for t in trades) / len(trades),
        "avg_mfe_r": sum(t.mfe_r for t in trades) / len(trades),
        "er_at_15x_cost": sum(stressed_15) / len(stressed_15),
        "er_at_2x_cost": sum(stressed_2) / len(stressed_2),
        "timeout_share": sum(1 for t in trades if t.exit_reason == "timeout") / len(trades),
        "overlap_vs_trial_00095": overlaps / len(trades),
        **concentration,
    }


def _stress_pnl(trade: ReacceptTrade, multiplier: float) -> float:
    if multiplier <= 1:
        return trade.pnl_r
    entry = trade.signal.entry_price
    risk = abs(trade.signal.entry_price - trade.signal.stop_loss)
    if risk <= 0:
        return trade.pnl_r
    extra_fee = entry * FEE_RATE * (multiplier - 1) * 2
    extra_slip = entry * SLIPPAGE_BPS / 10000 * (multiplier - 1) * 2
    return trade.pnl_r - (extra_fee + extra_slip) / risk


def evaluate_run(run: SetupRun, baseline_times: set[datetime]) -> None:
    metrics = compute_metrics(run.trades, baseline_times=baseline_times)
    folds = fold_metrics(run.trades)
    metrics["folds_er_gt_1"] = folds["folds_er_gt_1"]
    run.metrics = metrics
    gates = [
        Gate("min_oos_trades", ">=", 60, "trade_count", "REQUIRED"),
        Gate("min_er", ">=", 1.5, "expectancy_r", "REQUIRED"),
        Gate("min_pf", ">=", 1.8, "profit_factor", "REQUIRED"),
        Gate("max_dd", "<=", 6.0, "max_dd_r", "REQUIRED"),
        Gate("cost_sensitivity_2x", ">", 0.5, "er_at_2x_cost", "REQUIRED"),
        Gate("timeout_share", "<=", 0.4, "timeout_share", "REQUIRED"),
        Gate("max_month_trade_share", "<=", 0.5, "max_month_trade_share", "REQUIRED"),
        Gate("wf_folds_er_gt_1", ">=", 3, "folds_er_gt_1", "REQUIRED"),
        Gate("overlap_vs_trial_00095", "<=", 0.3, "overlap_vs_trial_00095", "RECOMMENDED"),
    ]
    result = evaluate_gates(metrics, gates, experiment_id=run.variant.variant_id)
    run.gate_verdict = result.verdict
    run.gate_summary = result.summary
    run.gate_results = [gate.to_dict() for gate in result.gate_results]
    run.metrics["fold_metrics"] = folds


def variants() -> list[SetupVariant]:
    grid: list[SetupVariant] = []
    for ema_gap in (0.006, 0.01):
        for max_bars in (3, 5):
            for reclaim in (0.05, 0.08):
                grid.append(SetupVariant(
                    variant_id=f"TPR_G{ema_gap:.3f}_B{max_bars}_R{reclaim:.2f}_TFI",
                    ema_gap_pct_threshold=ema_gap,
                    pullback_max_bars=max_bars,
                    reclaim_buffer_atr=reclaim,
                    tfi_threshold=0.05,
                ))
    grid.append(SetupVariant("TPR_ABLATION_NO_TFI", 0.006, 5, 0.05, None))
    return grid


def audit_data_availability(db_path: Path) -> dict[str, Any]:
    audit = {"db_exists": db_path.exists(), "tables": [], "candles_15m": 0, "candles_4h": 0, "aggtrade_60s": 0}
    if not db_path.exists():
        return audit
    with sqlite3.connect(db_path) as conn:
        audit["tables"] = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        audit["candles_15m"] = conn.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND timeframe='15m'", (SYMBOL,)).fetchone()[0]
        audit["candles_4h"] = conn.execute("SELECT COUNT(*) FROM candles WHERE symbol=? AND timeframe='4h'", (SYMBOL,)).fetchone()[0]
        audit["aggtrade_60s"] = conn.execute("SELECT COUNT(*) FROM aggtrade_buckets WHERE symbol=? AND timeframe='60s'", (SYMBOL,)).fetchone()[0]
    return audit


def run_feasibility(db_path: Path) -> tuple[list[SetupRun], dict[str, Any]]:
    audit = audit_data_availability(db_path)
    if not audit["db_exists"]:
        raise FileNotFoundError(db_path)
    with sqlite3.connect(db_path) as conn:
        candles_15m = load_candles(conn, "15m", LOOKBACK_START, ANALYSIS_END)
        candles_4h = load_candles(conn, "4h", LOOKBACK_START - timedelta(days=60), ANALYSIS_END)
        agg_60s = load_agg_60s(conn, ANALYSIS_START - timedelta(days=2), ANALYSIS_END)
    baseline_times = load_baseline_entry_times()
    runs = [run_variant(candles_15m, candles_4h, agg_60s, variant) for variant in variants()]
    for run in runs:
        evaluate_run(run, baseline_times)
    return runs, audit


def choose_best(runs: list[SetupRun]) -> SetupRun:
    return sorted(
        runs,
        key=lambda r: (
            r.gate_verdict == "PASS",
            r.metrics.get("expectancy_r", 0.0),
            r.metrics.get("profit_factor", 0.0),
            r.metrics.get("trade_count", 0),
        ),
        reverse=True,
    )[0]


def generate_report(runs: list[SetupRun], audit: dict[str, Any], report_path: Path) -> str:
    best = choose_best(runs)
    lines: list[str] = []
    lines.append("# Trend Pullback Reaccept Feasibility")
    lines.append("")
    lines.append("**Milestone:** `TREND_PULLBACK_REACCEPT_FEASIBILITY_V1`")
    lines.append("**Status:** READY_FOR_AUDIT")
    lines.append("**Scope:** Research Lab offline-only; no runtime/core/orchestrator/settings/execution changes.")
    lines.append("**Baseline:** trial-00095 15m sweep/reclaim")
    lines.append("")
    lines.append("## Hypothesis")
    lines.append("")
    lines.append("BTC LONG-only trend pullback reacceptance: in a completed 4h EMA uptrend, price pulls back below a pre-frozen 15m equal-low support level and later closes back above that level on a 15m bar. Entry is next 15m open.")
    lines.append("")
    lines.append("## Data Audit")
    lines.append("")
    lines.append(f"- Source DB: `{DB_REPLAY}`")
    lines.append(f"- 15m candles: {audit.get('candles_15m', 0)}")
    lines.append(f"- 4h candles: {audit.get('candles_4h', 0)}")
    lines.append(f"- 60s aggtrade buckets: {audit.get('aggtrade_60s', 0)}")
    lines.append("")
    lines.append("## Variant Results")
    lines.append("")
    lines.append("| Variant | Verdict | Trades | ER | PF | Max DD R | 2x Cost ER | Timeout | Month Conc | WF Folds | Overlap |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for run in runs:
        m = run.metrics
        lines.append(
            f"| `{run.variant.variant_id}` | `{run.gate_verdict}` | {m['trade_count']} | "
            f"{m['expectancy_r']:.3f} | {m['profit_factor']:.2f} | {m['max_dd_r']:.2f} | "
            f"{m['er_at_2x_cost']:.3f} | {m['timeout_share']:.1%} | "
            f"{m['max_month_trade_share']:.1%} | {m['folds_er_gt_1']}/4 | {m['overlap_vs_trial_00095']:.1%} |"
        )
    lines.append("")
    lines.append("## Best Variant")
    lines.append("")
    lines.append(f"**Best:** `{best.variant.variant_id}`")
    lines.append(f"**Verdict:** `{best.gate_verdict}` - {best.gate_summary}")
    lines.append("")
    lines.append("## Gates")
    lines.append("")
    lines.append("| Gate | Actual | Required | Result |")
    lines.append("|---|---:|---:|---|")
    for gate in best.gate_results:
        lines.append(
            f"| {gate['name']} | {gate['actual_value']:.3f} | "
            f"{gate['operator']} {gate['threshold']} | {'PASS' if gate['passed'] else 'FAIL'} |"
        )
    lines.append("")
    lines.append("## Anti-Overfit Controls")
    lines.append("")
    lines.append("- LONG-only V1; SHORT is out of scope.")
    lines.append("- Coarse grid only: 8 candidate variants plus one no-TFI ablation.")
    lines.append("- Equal-low support is frozen at least 5 completed 15m bars before trigger.")
    lines.append("- 4h EMA trend uses completed 4h candles only.")
    lines.append("- Entry is next 15m open after reclaim close.")
    lines.append("- CVD, OI, funding, and force orders are not trigger or scoring inputs.")
    lines.append("- If the no-TFI ablation beats TFI variants, that is diagnostic evidence against flow confirmation, not automatic promotion.")
    lines.append("")
    lines.append("## Audit Questions")
    lines.append("")
    lines.append("1. Does the runner avoid lookahead in frozen equal-low and 4h trend calculations?")
    lines.append("2. Is the implementation research_lab-only with no runtime/core changes?")
    lines.append("3. Are gates applied exactly as pre-registered in the hypothesis card?")
    lines.append("4. Does TFI add incremental value versus the no-TFI ablation?")
    lines.append("5. Is overlap with trial-00095 low enough to support portfolio distinctness?")
    report = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return report


def record_best_experiment(best: SetupRun, db_path: Path, report_path: Path) -> str:
    with sqlite3.connect(db_path) as conn:
        row_count = conn.execute(
            "SELECT COUNT(*) FROM candles WHERE symbol=? AND timeframe='15m'",
            (SYMBOL,),
        ).fetchone()[0]
    manifest = create_manifest(
        dataset_id="btc_15m_replay_run13",
        path=db_path,
        timeframe="15m",
        symbol=SYMBOL,
        date_start=ANALYSIS_START.date().isoformat(),
        date_end=ANALYSIS_END.date().isoformat(),
        row_count=row_count,
        quality_status="PASS",
        source="replay-run13-regime-aware-trial-00063",
    )
    git_commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    experiment_id = create_experiment(
        registry_path=REGISTRY_PATH,
        hypothesis_id="trend_pullback_reaccept_v1",
        config=best.variant.to_config(),
        data_manifests=[manifest],
        baseline_reference="trial-00095",
        runner_name="analysis_trend_pullback_reaccept_feasibility",
        date_range_start=ANALYSIS_START.date().isoformat(),
        date_range_end=ANALYSIS_END.date().isoformat(),
        git_commit=git_commit,
    )
    gates = [
        Gate("min_oos_trades", ">=", 60, "trade_count", "REQUIRED"),
        Gate("min_er", ">=", 1.5, "expectancy_r", "REQUIRED"),
        Gate("min_pf", ">=", 1.8, "profit_factor", "REQUIRED"),
        Gate("max_dd", "<=", 6.0, "max_dd_r", "REQUIRED"),
        Gate("cost_sensitivity_2x", ">", 0.5, "er_at_2x_cost", "REQUIRED"),
        Gate("timeout_share", "<=", 0.4, "timeout_share", "REQUIRED"),
        Gate("max_month_trade_share", "<=", 0.5, "max_month_trade_share", "REQUIRED"),
        Gate("wf_folds_er_gt_1", ">=", 3, "folds_er_gt_1", "REQUIRED"),
        Gate("overlap_vs_trial_00095", "<=", 0.3, "overlap_vs_trial_00095", "RECOMMENDED"),
    ]
    evaluation = evaluate_gates(best.metrics, gates, experiment_id=experiment_id)
    record_result(
        registry_path=REGISTRY_PATH,
        experiment_id=experiment_id,
        verdict=evaluation.verdict,
        metrics=best.metrics,
        gates=list(evaluation.gate_results),
        artifacts={"report": str(report_path), "hypothesis": str(HYPOTHESIS_PATH)},
    )
    return experiment_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_REPLAY)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--skip-registry", action="store_true")
    args = parser.parse_args()

    runs, audit = run_feasibility(args.db)
    report = generate_report(runs, audit, args.report)
    best = choose_best(runs)
    print(report)
    if not args.skip_registry:
        experiment_id = record_best_experiment(best, args.db, args.report)
        print(f"Recorded experiment: {experiment_id}")


if __name__ == "__main__":
    main()

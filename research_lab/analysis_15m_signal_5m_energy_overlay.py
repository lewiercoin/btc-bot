#!/usr/bin/env python3
"""
15m Signal + 5m Energy Overlay Feasibility Study

Tests whether 5m energy/impulse confirmation improves 15m signal entry timing.
Preserves 15m signal detection (trial-00095 exact params) and adds a 5m timing
confirmation layer that waits for a high-energy candle before entry.

Hypothesis: When a 15m sweep+reclaim signal fires, waiting for a 5m "energy
confirmation" candle (high body/range + elevated volume) within the next 3 bars
can reduce MAE by ~40% without reducing signal count below 80% of baseline.

Energy Confirmation:
  body/range = abs(close - open) / (high - low)
  volume_zscore = (volume - rolling_mean_20) / rolling_std_20
  direction_consistency = 5m candle direction matches signal direction
  max_wait = 3 bars (15 minutes)

Timeout Modes:
  SKIP: no 5m confirmation within max_wait → skip trade (signal filtering)
  FALLBACK: no 5m confirmation → enter at baseline 15m entry price (timing only)

No-Lookahead Rule:
  5m search window starts at 15m candle close T, NOT before.

Matched-Subset Analysis:
  Every hybrid trade is matched to its baseline trade by signal timestamp.
  Quality comparison uses matched subset, not full baseline.

No production, PAPER, runtime, settings, or execution changes.

Usage:
    python research_lab/analysis_15m_signal_5m_energy_overlay.py
"""

from __future__ import annotations

import os as _os
import sys as _sys

# Fix sys.path: prevent research_lab/types.py from shadowing stdlib types
_script_dir = _os.path.dirname(_os.path.abspath(__file__))
if _script_dir in _sys.path:
    _sys.path.remove(_script_dir)
_project_root = _os.path.dirname(_script_dir)
if _project_root not in _sys.path:
    _sys.path.insert(0, _project_root)

import math
import sqlite3
import sys
import time as time_mod
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.context_engine import ContextEngine
from core.feature_engine import FeatureEngine, FeatureEngineConfig, compute_atr, detect_equal_levels, detect_sweep_reclaim
from core.governance import GovernanceConfig, GovernanceLayer
from core.models import (
    GovernanceRuntimeState,
    MarketSnapshot,
    RiskRuntimeState,
    SignalCandidate,
)
from core.regime_engine import RegimeConfig, RegimeEngine
from core.risk_engine import RiskConfig, RiskEngine
from core.signal_engine import SignalConfig, SignalEngine
from settings import ContextConfig


# ── Configuration ──────────────────────────────────────────────────────────────

DB_5M = Path("research_lab/snapshots/btc_5m_2022_2026.db")
DB_15M = Path("research_lab/snapshots/replay-run13-regime-aware-trial-00063.db")
REPORT_PATH = Path("docs/analysis/15M_SIGNAL_5M_ENERGY_OVERLAY_2026-05-15.md")
SYMBOL = "BTCUSDT"

ANALYSIS_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
ANALYSIS_END = datetime(2026, 3, 28, tzinfo=timezone.utc)

# Trial-00095 exact parameters
TRIAL_PARAMS = {
    "atr_period": 27,
    "ema_fast": 50,
    "ema_slow": 200,
    "equal_level_lookback": 276,
    "equal_level_tol_atr": 0.09,
    "sweep_buf_atr": 0.46,
    "sweep_proximity_atr": 0.4,
    "reclaim_buf_atr": 0.07,
    "wick_min_atr": 0.2,
    "level_min_age_bars": 5,
    "min_hits": 3,
    "funding_window_days": 130,
    "oi_z_window_days": 35,
    "min_sweep_depth_pct": 0.00649,
    "confluence_min": 3.9,
    "ema_trend_gap_pct": 0.017,
    "entry_offset_atr": 0.07,
    "invalidation_offset_atr": 0.14,
    "min_stop_distance_pct": 0.0019,
    "tp1_atr_mult": 2.2,
    "tp2_atr_mult": 6.5,
    "weight_sweep_detected": 2.2,
    "weight_reclaim_confirmed": 2.15,
    "weight_cvd_divergence": 3.2,
    "weight_tfi_impulse": 2.5,
    "weight_force_order_spike": 0.40,
    "weight_regime_special": 1.8,
    "weight_ema_trend_alignment": 3.35,
    "weight_funding_supportive": 1.1,
    "direction_tfi_threshold": 0.1,
    "direction_tfi_threshold_inverse": -0.05,
    "tfi_impulse_threshold": 0.31,
    "allow_uptrend_pullback": False,
    "allow_long_in_uptrend": True,
    "compression_atr_norm_max": 0.0039,
    "crowded_funding_extreme_pct": 85.0,
    "crowded_oi_zscore_min": 1.5,
    "post_liq_tfi_abs_min": 0.78,
}

RISK_PARAMS = {
    "risk_per_trade_pct": 0.005,
    "max_leverage": 2,
    "min_rr": 2.65,
    "max_open_positions": 1,
    "max_trades_per_day": 5,
    "max_consecutive_losses": 7,
    "daily_dd_limit": 0.106,
    "weekly_dd_limit": 0.12,
    "max_hold_hours": 34,
    "partial_exit_pct": 0.82,
    "trailing_atr_mult": 1.6,
    "cooldown_minutes_after_loss": 125,
    "duplicate_level_tolerance_pct": 0.0016,
    "duplicate_level_window_hours": 123,
}

FEE_RATE = 0.0004
SLIPPAGE_BPS = 3.0
BAR_MINUTES_15M = 15
MAX_HOLD_BARS_15M = int(RISK_PARAMS["max_hold_hours"] * 60 / BAR_MINUTES_15M)


# ── Energy Variant Definitions ────────────────────────────────────────────────

@dataclass(frozen=True)
class EnergyVariant:
    name: str
    body_range_min: float
    volume_zscore_min: float
    direction_required: bool
    max_wait_bars: int


ENERGY_VARIANTS = [
    EnergyVariant("E1", body_range_min=0.6, volume_zscore_min=1.0, direction_required=True, max_wait_bars=3),
    EnergyVariant("E2", body_range_min=0.6, volume_zscore_min=1.0, direction_required=False, max_wait_bars=3),
    EnergyVariant("E3", body_range_min=0.7, volume_zscore_min=1.5, direction_required=True, max_wait_bars=3),
    EnergyVariant("E4", body_range_min=0.5, volume_zscore_min=0.5, direction_required=True, max_wait_bars=3),
]

TIMEOUT_MODES = ["SKIP", "FALLBACK"]


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class SimTrade:
    entry_time: datetime
    exit_time: datetime
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit_1: float
    pnl_r: float
    exit_reason: str
    regime: str
    confluence: float
    sweep_depth_pct: float
    reasons: list[str]
    mae_r: float = 0.0
    mfe_r: float = 0.0


@dataclass
class SignalEvent:
    """A 15m signal that passed all gates and produced a baseline trade."""
    signal_time: datetime          # 15m candle close T (no-lookahead boundary)
    direction: str                 # LONG or SHORT
    entry_reference: float         # baseline entry price
    invalidation_level: float      # stop loss level
    tp_reference_1: float          # TP1 level
    tp_reference_2: float          # TP2 level
    baseline_trade: SimTrade       # baseline trade outcome
    candle_idx: int                # index in 15m setup_candles
    regime: str
    confluence: float
    sweep_depth_pct: float
    reasons: list[str]


@dataclass
class HybridTrade:
    """A trade from the hybrid 15m signal + 5m energy overlay."""
    signal_event: SignalEvent
    confirmed: bool               # did 5m energy confirm?
    confirmation_bar: int         # which 5m bar confirmed (0-indexed), -1 if timeout
    wait_bars: int                # how many 5m bars waited
    entry_price: float            # actual entry price (5m close if confirmed, baseline if fallback)
    entry_time: datetime          # actual entry time
    trade: SimTrade | None        # simulated trade outcome (None if SKIP + timeout)
    entry_price_delta_pct: float  # (hybrid_entry - baseline_entry) / baseline_entry
    missed_move_cost: float       # adverse price movement during wait (R units)


@dataclass
class FunnelMetrics:
    total_bars: int = 0
    sweep_detected: int = 0
    sweep_too_shallow: int = 0
    reclaim_detected: int = 0
    no_sweep: int = 0
    no_reclaim: int = 0
    direction_unresolved: int = 0
    regime_blocked: int = 0
    confluence_below_min: int = 0
    signal_candidates: int = 0
    governance_rejected: int = 0
    risk_rejected: int = 0
    trades_executed: int = 0
    blocked_by_counts: dict = field(default_factory=lambda: defaultdict(int))


@dataclass
class PerformanceMetrics:
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_r: float = 0.0
    avg_winner_r: float = 0.0
    avg_loser_r: float = 0.0
    median_r: float = 0.0
    trades_per_month: float = 0.0
    avg_mae_r: float = 0.0
    avg_mfe_r: float = 0.0
    max_consecutive_losses: int = 0


@dataclass
class OverlayResult:
    """Results for one variant + timeout mode configuration."""
    variant: EnergyVariant
    timeout_mode: str
    hybrid_trades: list[HybridTrade]
    baseline_events: list[SignalEvent]
    # Computed after init
    executed_trades: list[SimTrade] = field(default_factory=list)
    matched_baseline_trades: list[SimTrade] = field(default_factory=list)
    metrics_hybrid: PerformanceMetrics | None = None
    metrics_matched_baseline: PerformanceMetrics | None = None
    metrics_full_baseline: PerformanceMetrics | None = None
    # Fairness
    avg_entry_price_delta_pct: float = 0.0
    avg_missed_move_cost: float = 0.0
    avg_wait_bars: float = 0.0
    timeout_rate: float = 0.0
    frequency_ratio: float = 0.0
    verdict: str = ""


# ── Data Loading (reused from M5 harness) ────────────────────────────────────

def _parse_ts(val) -> datetime:
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    ts = datetime.fromisoformat(str(val))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def load_candles(conn: sqlite3.Connection, timeframe: str, start: datetime, end: datetime,
                 lookback_bars: int = 0) -> list[dict]:
    if timeframe == "5m":
        lookback_delta = timedelta(minutes=5 * lookback_bars)
    elif timeframe == "15m":
        lookback_delta = timedelta(minutes=15 * lookback_bars)
    elif timeframe == "1h":
        lookback_delta = timedelta(hours=lookback_bars)
    elif timeframe == "4h":
        lookback_delta = timedelta(hours=4 * lookback_bars)
    else:
        lookback_delta = timedelta()

    actual_start = start - lookback_delta
    rows = conn.execute(
        """SELECT open_time, open, high, low, close, volume
           FROM candles WHERE symbol=? AND timeframe=?
           AND open_time >= ? AND open_time <= ?
           ORDER BY open_time ASC""",
        (SYMBOL, timeframe, actual_start.isoformat(), end.isoformat()),
    ).fetchall()
    return [
        {
            "open_time": _parse_ts(r[0]),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
        }
        for r in rows
    ]


def load_funding(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT funding_time, funding_rate FROM funding WHERE symbol=? ORDER BY funding_time ASC",
        (SYMBOL,),
    ).fetchall()
    return [{"funding_time": _parse_ts(r[0]), "funding_rate": float(r[1])} for r in rows]


def load_oi(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT timestamp, oi_value FROM open_interest WHERE symbol=? ORDER BY timestamp ASC",
        (SYMBOL,),
    ).fetchall()
    return [{"timestamp": _parse_ts(r[0]), "oi_value": float(r[1])} for r in rows]


def load_aggtrade_buckets(conn: sqlite3.Connection, timeframe: str) -> dict[datetime, dict]:
    rows = conn.execute(
        """SELECT bucket_time, taker_buy_volume, taker_sell_volume, tfi, cvd
           FROM aggtrade_buckets WHERE symbol=? AND timeframe=?
           ORDER BY bucket_time ASC""",
        (SYMBOL, timeframe),
    ).fetchall()
    result = {}
    for r in rows:
        ts = _parse_ts(r[0])
        result[ts] = {
            "bucket_time": ts,
            "taker_buy_volume": float(r[1]),
            "taker_sell_volume": float(r[2]),
            "tfi": float(r[3]),
            "cvd": float(r[4]),
        }
    return result


# ── Preloaded Indexed Data ────────────────────────────────────────────────────

@dataclass
class PreloadedData:
    oi_timestamps: list[datetime]
    oi_values: list[float]
    funding_times: list[datetime]
    funding_rows: list[dict]
    agg_15m: dict[datetime, dict]
    agg_60s: dict[datetime, dict]
    candles_1h_times: list[datetime]
    candles_1h_rows: list[dict]
    candles_4h_times: list[datetime]
    candles_4h_rows: list[dict]

    @classmethod
    def build(cls, candles_1h, candles_4h, funding, oi, agg_15m, agg_60s) -> "PreloadedData":
        return cls(
            oi_timestamps=[r["timestamp"] for r in oi],
            oi_values=[r["oi_value"] for r in oi],
            funding_times=[r["funding_time"] for r in funding],
            funding_rows=funding,
            agg_15m=agg_15m, agg_60s=agg_60s,
            candles_1h_times=[c["open_time"] for c in candles_1h],
            candles_1h_rows=candles_1h,
            candles_4h_times=[c["open_time"] for c in candles_4h],
            candles_4h_rows=candles_4h,
        )

    def get_oi(self, target: datetime) -> float:
        if not self.oi_timestamps:
            return 0.0
        idx = bisect_right(self.oi_timestamps, target) - 1
        return self.oi_values[max(0, idx)]

    def get_funding(self, target: datetime, lookback: int = 200) -> list[dict]:
        idx = bisect_right(self.funding_times, target)
        return self.funding_rows[max(0, idx - lookback):idx]

    def get_1h(self, target: datetime, lookback: int = 300) -> list[dict]:
        idx = bisect_right(self.candles_1h_times, target)
        return self.candles_1h_rows[max(0, idx - lookback):idx]

    def get_4h(self, target: datetime, lookback: int = 300) -> list[dict]:
        idx = bisect_right(self.candles_4h_times, target)
        return self.candles_4h_rows[max(0, idx - lookback):idx]

    def get_agg_15m(self, target: datetime) -> dict:
        if target in self.agg_15m:
            return self.agg_15m[target]
        for delta_min in range(1, 16):
            for sign in [-1, 1]:
                candidate = target + timedelta(minutes=sign * delta_min)
                if candidate in self.agg_15m:
                    return self.agg_15m[candidate]
        return {"taker_buy_volume": 0, "taker_sell_volume": 0, "tfi": 0, "cvd": 0}

    def get_agg_60s(self, target: datetime) -> dict:
        if target in self.agg_60s:
            return self.agg_60s[target]
        for delta_min in range(1, 6):
            for sign in [-1, 1]:
                candidate = target + timedelta(minutes=sign * delta_min)
                if candidate in self.agg_60s:
                    return self.agg_60s[candidate]
        return {"taker_buy_volume": 0, "taker_sell_volume": 0, "tfi": 0, "cvd": 0}


# ── 5m Volume Z-Score Pre-computation ─────────────────────────────────────────

@dataclass
class Candle5mIndex:
    """Pre-indexed 5m candle data with rolling volume statistics."""
    times: list[datetime]
    candles: list[dict]
    vol_zscore: list[float]  # pre-computed volume z-score per bar

    @classmethod
    def build(cls, candles_5m: list[dict], rolling_window: int = 20) -> "Candle5mIndex":
        times = [c["open_time"] for c in candles_5m]
        volumes = [c["volume"] for c in candles_5m]
        vol_zscore = []
        for i in range(len(volumes)):
            if i < rolling_window:
                vol_zscore.append(0.0)
                continue
            window = volumes[i - rolling_window:i]
            mean_v = sum(window) / rolling_window
            std_v = math.sqrt(sum((x - mean_v) ** 2 for x in window) / rolling_window) if len(window) > 1 else 1.0
            if std_v < 1e-12:
                vol_zscore.append(0.0)
            else:
                vol_zscore.append((volumes[i] - mean_v) / std_v)
        return cls(times=times, candles=candles_5m, vol_zscore=vol_zscore)

    def get_bars_from(self, start_time: datetime, count: int) -> list[tuple[dict, float]]:
        """Get up to `count` 5m bars with open_time >= start_time.
        Returns list of (candle_dict, volume_zscore) tuples.
        NO-LOOKAHEAD: only bars with open_time >= start_time are returned.
        """
        idx = bisect_left(self.times, start_time)
        end_idx = min(idx + count, len(self.candles))
        return [(self.candles[i], self.vol_zscore[i]) for i in range(idx, end_idx)]


# ── Trade Simulation ──────────────────────────────────────────────────────────

def simulate_trade(
    direction: str,
    entry_price: float,
    entry_time: datetime,
    stop_loss: float,
    take_profit_1: float,
    future_candles: list[dict],
    max_hold_bars: int,
    fee_rate: float,
    slippage_bps: float,
    regime: str,
    confluence: float,
    sweep_depth_pct: float,
    reasons: list[str],
) -> SimTrade | None:
    """Simulate trade outcome using future candles after entry."""
    if not future_candles:
        return None

    slip = entry_price * slippage_bps / 10000
    if direction == "LONG":
        entry_price += slip
    else:
        entry_price -= slip

    risk = abs(entry_price - stop_loss)
    if risk <= 0:
        return None

    mae = 0.0
    mfe = 0.0
    exit_price = entry_price
    exit_reason = "max_hold"
    exit_time = future_candles[0]["open_time"]

    for candle in future_candles[:max_hold_bars]:
        h = float(candle["high"])
        l = float(candle["low"])
        c = float(candle["close"])

        if direction == "LONG":
            mae = min(mae, (l - entry_price) / risk)
            mfe = max(mfe, (h - entry_price) / risk)
            if l <= stop_loss:
                exit_price = stop_loss - slip
                exit_reason = "stop_loss"
                exit_time = candle["open_time"]
                break
            if h >= take_profit_1:
                exit_price = take_profit_1 - slip
                exit_reason = "take_profit"
                exit_time = candle["open_time"]
                break
        else:
            mae = min(mae, (entry_price - h) / risk)
            mfe = max(mfe, (entry_price - l) / risk)
            if h >= stop_loss:
                exit_price = stop_loss + slip
                exit_reason = "stop_loss"
                exit_time = candle["open_time"]
                break
            if l <= take_profit_1:
                exit_price = take_profit_1 + slip
                exit_reason = "take_profit"
                exit_time = candle["open_time"]
                break
        exit_price = c
        exit_time = candle["open_time"]

    if direction == "LONG":
        raw_pnl = exit_price - entry_price
    else:
        raw_pnl = entry_price - exit_price

    fee_cost = entry_price * fee_rate + exit_price * fee_rate
    net_pnl = raw_pnl - fee_cost
    pnl_r = net_pnl / risk if risk > 0 else 0.0

    return SimTrade(
        entry_time=entry_time,
        exit_time=exit_time,
        direction=direction,
        entry_price=entry_price,
        exit_price=exit_price,
        stop_loss=stop_loss,
        take_profit_1=take_profit_1,
        pnl_r=pnl_r,
        exit_reason=exit_reason,
        regime=regime,
        confluence=confluence,
        sweep_depth_pct=sweep_depth_pct,
        reasons=reasons,
        mae_r=mae,
        mfe_r=mfe,
    )


# ── Metrics Computation ──────────────────────────────────────────────────────

def compute_metrics(trades: list[SimTrade], months: float) -> PerformanceMetrics:
    if not trades:
        return PerformanceMetrics()

    m = PerformanceMetrics()
    m.trade_count = len(trades)
    winners = [t for t in trades if t.pnl_r > 0]
    losers = [t for t in trades if t.pnl_r <= 0]
    m.win_count = len(winners)
    m.loss_count = len(losers)
    m.win_rate = m.win_count / m.trade_count * 100

    pnls = [t.pnl_r for t in trades]
    m.expectancy_r = sum(pnls) / len(pnls)
    m.median_r = sorted(pnls)[len(pnls) // 2]

    gross_profit = sum(t.pnl_r for t in winners) if winners else 0
    gross_loss = abs(sum(t.pnl_r for t in losers)) if losers else 0
    m.profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0)

    m.avg_winner_r = sum(t.pnl_r for t in winners) / len(winners) if winners else 0
    m.avg_loser_r = sum(t.pnl_r for t in losers) / len(losers) if losers else 0
    m.avg_mae_r = sum(t.mae_r for t in trades) / len(trades)
    m.avg_mfe_r = sum(t.mfe_r for t in trades) / len(trades)
    m.trades_per_month = m.trade_count / max(months, 0.1)

    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        cumulative += t.pnl_r
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
    m.max_drawdown_r = max_dd

    streak = 0
    max_streak = 0
    for t in trades:
        if t.pnl_r <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    m.max_consecutive_losses = max_streak

    return m


def overtrading_analysis(trades: list[SimTrade]) -> dict:
    if not trades:
        return {"daily_max": 0, "min_gap_minutes": 0, "days_over_5": 0, "gap_under_30min": 0}
    daily: dict[date, int] = defaultdict(int)
    for t in trades:
        daily[t.entry_time.date()] += 1
    daily_max = max(daily.values()) if daily else 0
    days_over_5 = sum(1 for v in daily.values() if v > 5)
    gaps = []
    for i in range(1, len(trades)):
        gaps.append((trades[i].entry_time - trades[i - 1].entry_time).total_seconds() / 60)
    min_gap = min(gaps) if gaps else float("inf")
    gap_under_30 = sum(1 for g in gaps if g < 30)
    return {"daily_max": daily_max, "min_gap_minutes": round(min_gap, 1),
            "days_over_5": days_over_5, "gap_under_30min": gap_under_30}


def concentration_analysis(trades: list[SimTrade]) -> dict:
    if not trades:
        return {"max_month_pct": 0, "concentrated": False}
    monthly_pnl: dict[str, float] = defaultdict(float)
    for t in trades:
        monthly_pnl[t.entry_time.strftime("%Y-%m")] += t.pnl_r
    total_pnl = sum(abs(v) for v in monthly_pnl.values())
    if total_pnl == 0:
        return {"max_month_pct": 0, "concentrated": False}
    max_month_pnl = max(abs(v) for v in monthly_pnl.values())
    max_pct = max_month_pnl / total_pnl * 100
    return {"max_month_pct": round(max_pct, 1), "concentrated": max_pct > 50}


# ── 15m Baseline Signal Detection ─────────────────────────────────────────────

def run_baseline_15m(
    setup_candles: list[dict],
    preloaded: PreloadedData,
    oi_data: list[dict],
) -> tuple[FunnelMetrics, list[SignalEvent]]:
    """Run 15m sweep/reclaim detection and return signal events with baseline trades."""

    params = TRIAL_PARAMS
    lookback_bars = params["equal_level_lookback"] + 50

    print(f"\n{'='*60}")
    print(f"Running 15m BASELINE signal detection")
    print(f"Period: {ANALYSIS_START.date()} to {ANALYSIS_END.date()}")
    print(f"Setup candles: {len(setup_candles)}")
    print(f"{'='*60}")

    feature_config = FeatureEngineConfig(
        atr_period=params["atr_period"], ema_fast=params["ema_fast"], ema_slow=params["ema_slow"],
        equal_level_lookback=params["equal_level_lookback"], equal_level_tol_atr=params["equal_level_tol_atr"],
        sweep_buf_atr=params["sweep_buf_atr"], sweep_proximity_atr=params["sweep_proximity_atr"],
        reclaim_buf_atr=params["reclaim_buf_atr"], wick_min_atr=params["wick_min_atr"],
        level_min_age_bars=params["level_min_age_bars"], min_hits=params["min_hits"],
        funding_window_days=params["funding_window_days"], oi_z_window_days=params["oi_z_window_days"],
    )
    feature_engine = FeatureEngine(feature_config)

    regime_config = RegimeConfig(
        ema_trend_gap_pct=params["ema_trend_gap_pct"],
        compression_atr_norm_max=params["compression_atr_norm_max"],
        crowded_funding_extreme_pct=params["crowded_funding_extreme_pct"],
        crowded_oi_zscore_min=params["crowded_oi_zscore_min"],
        post_liq_tfi_abs_min=params["post_liq_tfi_abs_min"],
    )
    regime_engine = RegimeEngine(regime_config)
    context_engine = ContextEngine(config=ContextConfig(neutral_mode=True))

    regime_whitelist = {
        "normal": ("LONG",), "compression": ("LONG",),
        "downtrend": ("LONG", "SHORT"),
        "uptrend": ("LONG",) if params.get("allow_long_in_uptrend") else (),
        "crowded_leverage": ("SHORT",), "post_liquidation": ("LONG",),
    }
    signal_config = SignalConfig(
        confluence_min=params["confluence_min"], min_sweep_depth_pct=params["min_sweep_depth_pct"],
        ema_trend_gap_pct=params["ema_trend_gap_pct"],
        entry_offset_atr=params["entry_offset_atr"], invalidation_offset_atr=params["invalidation_offset_atr"],
        min_stop_distance_pct=params["min_stop_distance_pct"],
        tp1_atr_mult=params["tp1_atr_mult"], tp2_atr_mult=params["tp2_atr_mult"],
        weight_sweep_detected=params["weight_sweep_detected"],
        weight_reclaim_confirmed=params["weight_reclaim_confirmed"],
        weight_cvd_divergence=params["weight_cvd_divergence"],
        weight_tfi_impulse=params["weight_tfi_impulse"],
        weight_force_order_spike=params["weight_force_order_spike"],
        weight_regime_special=params["weight_regime_special"],
        weight_ema_trend_alignment=params["weight_ema_trend_alignment"],
        weight_funding_supportive=params["weight_funding_supportive"],
        direction_tfi_threshold=params["direction_tfi_threshold"],
        direction_tfi_threshold_inverse=params["direction_tfi_threshold_inverse"],
        tfi_impulse_threshold=params["tfi_impulse_threshold"],
        allow_uptrend_pullback=params.get("allow_uptrend_pullback", False),
        regime_direction_whitelist=regime_whitelist,
    )
    signal_engine = SignalEngine(signal_config)

    gov_state = GovernanceRuntimeState()
    risk_state = RiskRuntimeState()
    trades_today_date_holder: list[date | None] = [None]
    trades_today_count_holder: list[int] = [0]

    governance = GovernanceLayer(
        GovernanceConfig(
            cooldown_minutes_after_loss=RISK_PARAMS["cooldown_minutes_after_loss"],
            duplicate_level_tolerance_pct=RISK_PARAMS["duplicate_level_tolerance_pct"],
            duplicate_level_window_hours=RISK_PARAMS["duplicate_level_window_hours"],
            max_trades_per_day=RISK_PARAMS["max_trades_per_day"],
            max_consecutive_losses=RISK_PARAMS["max_consecutive_losses"],
        ),
        state_provider=lambda: gov_state,
    )
    risk_engine = RiskEngine(
        RiskConfig(
            risk_per_trade_pct=RISK_PARAMS["risk_per_trade_pct"],
            max_leverage=RISK_PARAMS["max_leverage"],
            min_rr=RISK_PARAMS["min_rr"],
            max_open_positions=RISK_PARAMS["max_open_positions"],
        ),
        state_provider=lambda: risk_state,
    )

    feature_engine.bootstrap_oi_history(oi_data)

    funnel = FunnelMetrics()
    signal_events: list[SignalEvent] = []

    setup_candle_times = [c["open_time"] for c in setup_candles]
    start_idx = bisect_left(setup_candle_times, ANALYSIS_START)
    end_idx = bisect_right(setup_candle_times, ANALYSIS_END)
    analysis_indices = list(range(start_idx, end_idx))
    total = len(analysis_indices)
    report_interval = max(total // 20, 1)

    full_engine_calls = 0

    for progress_idx, candle_idx in enumerate(analysis_indices):
        candle = setup_candles[candle_idx]
        candle_time = candle["open_time"]
        snapshot_ts = candle_time + timedelta(minutes=BAR_MINUTES_15M)

        if progress_idx % report_interval == 0:
            pct = progress_idx / max(total, 1) * 100
            print(f"  [{pct:5.1f}%] {candle_time.date()} | signals: {len(signal_events)} | engine: {full_engine_calls}")

        lb_start = max(0, candle_idx + 1 - lookback_bars)
        setup_lookback = setup_candles[lb_start:candle_idx + 1]
        if len(setup_lookback) < 20:
            continue

        funnel.total_bars += 1

        # PHASE 1: Lightweight sweep pre-filter
        atr_setup = compute_atr(setup_lookback, feature_config.atr_period)
        if atr_setup <= 0:
            funnel.no_sweep += 1
            funnel.blocked_by_counts["no_sweep"] += 1
            continue

        level_tolerance = atr_setup * feature_config.equal_level_tol_atr
        recent = setup_lookback[-feature_config.equal_level_lookback:]
        lows = [(i, float(c["low"])) for i, c in enumerate(recent)]
        highs = [(i, float(c["high"])) for i, c in enumerate(recent)]
        equal_lows = detect_equal_levels(lows, level_tolerance, feature_config.min_hits, feature_config.level_min_age_bars)
        equal_highs = detect_equal_levels(highs, level_tolerance, feature_config.min_hits, feature_config.level_min_age_bars)

        (sweep_det, reclaim_det, sweep_level, sweep_depth,
         sweep_side, _, _, _) = detect_sweep_reclaim(
            setup_lookback, equal_lows, equal_highs, atr_setup, feature_config)

        if not sweep_det:
            funnel.no_sweep += 1
            funnel.blocked_by_counts["no_sweep"] += 1
            continue

        funnel.sweep_detected += 1

        if sweep_depth is not None and sweep_depth < params["min_sweep_depth_pct"]:
            funnel.sweep_too_shallow += 1
            funnel.blocked_by_counts["sweep_too_shallow"] += 1
            continue

        if reclaim_det:
            funnel.reclaim_detected += 1

        # PHASE 2: Full FeatureEngine
        full_engine_calls += 1
        close_price = float(candle["close"])
        snapshot = MarketSnapshot(
            symbol=SYMBOL, timestamp=snapshot_ts, price=close_price,
            bid=close_price, ask=close_price,
            candles_15m=setup_lookback,
            candles_1h=preloaded.get_1h(snapshot_ts),
            candles_4h=preloaded.get_4h(snapshot_ts),
            funding_history=preloaded.get_funding(snapshot_ts),
            open_interest=preloaded.get_oi(snapshot_ts),
            aggtrades_bucket_60s=preloaded.get_agg_60s(snapshot_ts),
            aggtrades_bucket_15m=preloaded.get_agg_15m(candle_time),
            force_order_events_60s=[],
        )

        features = feature_engine.compute(snapshot, schema_version="v1.0", config_hash="overlay")
        regime = regime_engine.classify(features)
        context = context_engine.classify(features)

        diagnostics = signal_engine.diagnose(features, regime, context)
        if diagnostics.blocked_by:
            funnel.blocked_by_counts[diagnostics.blocked_by] += 1
            if diagnostics.blocked_by == "no_reclaim":
                funnel.no_reclaim += 1
            elif diagnostics.blocked_by == "direction_unresolved":
                funnel.direction_unresolved += 1
            elif diagnostics.blocked_by == "regime_direction_whitelist":
                funnel.regime_blocked += 1
            continue

        candidate = signal_engine.generate(features, regime, diagnostics=diagnostics, context=context)
        if candidate is None:
            continue

        funnel.signal_candidates += 1

        trade_date = candle_time.date()
        if trade_date != trades_today_date_holder[0]:
            trades_today_date_holder[0] = trade_date
            trades_today_count_holder[0] = 0
        gov_state.trades_today = trades_today_count_holder[0]

        gov_decision = governance.evaluate(candidate)
        if not gov_decision.approved:
            funnel.governance_rejected += 1
            continue

        executable = governance.to_executable(candidate, gov_decision)
        risk_decision = risk_engine.evaluate(signal=executable, equity=10000.0, open_positions=0)
        if not risk_decision.allowed:
            funnel.risk_rejected += 1
            continue

        # Simulate baseline trade
        future_idx = candle_idx + 1
        future_candles = setup_candles[future_idx:future_idx + MAX_HOLD_BARS_15M]

        baseline_trade = simulate_trade(
            direction=candidate.direction,
            entry_price=candidate.entry_reference,
            entry_time=candidate.timestamp,
            stop_loss=candidate.invalidation_level,
            take_profit_1=candidate.tp_reference_1,
            future_candles=future_candles,
            max_hold_bars=MAX_HOLD_BARS_15M,
            fee_rate=FEE_RATE,
            slippage_bps=SLIPPAGE_BPS,
            regime=candidate.regime.value,
            confluence=candidate.confluence_score,
            sweep_depth_pct=float(candidate.features_json.get("sweep_depth_pct", 0) or 0),
            reasons=candidate.reasons,
        )
        if baseline_trade is None:
            continue

        funnel.trades_executed += 1

        event = SignalEvent(
            signal_time=snapshot_ts,  # 15m candle close = no-lookahead boundary
            direction=candidate.direction,
            entry_reference=candidate.entry_reference,
            invalidation_level=candidate.invalidation_level,
            tp_reference_1=candidate.tp_reference_1,
            tp_reference_2=candidate.tp_reference_2,
            baseline_trade=baseline_trade,
            candle_idx=candle_idx,
            regime=candidate.regime.value,
            confluence=candidate.confluence_score,
            sweep_depth_pct=float(candidate.features_json.get("sweep_depth_pct", 0) or 0),
            reasons=candidate.reasons,
        )
        signal_events.append(event)

        # Update governance/risk state
        gov_state.last_trade_at = baseline_trade.entry_time
        if baseline_trade.pnl_r < 0:
            gov_state.last_loss_at = baseline_trade.entry_time
            gov_state.consecutive_losses += 1
            risk_state.consecutive_losses += 1
        else:
            gov_state.consecutive_losses = 0
            risk_state.consecutive_losses = 0
        trades_today_count_holder[0] += 1

    print(f"  [100.0%] Complete | signals: {len(signal_events)} | engine: {full_engine_calls}")
    return funnel, signal_events


# ── 5m Energy Confirmation ───────────────────────────────────────────────────

def check_energy_confirmation(
    variant: EnergyVariant,
    signal_direction: str,
    bars_5m: list[tuple[dict, float]],  # (candle, vol_zscore)
) -> tuple[bool, int, dict | None]:
    """Check if any 5m bar in the window meets energy criteria.

    Returns (confirmed, bar_index, confirmed_candle_dict).
    bar_index is 0-indexed within the search window. -1 if not confirmed.
    """
    for i, (candle, vol_z) in enumerate(bars_5m[:variant.max_wait_bars]):
        h = float(candle["high"])
        l = float(candle["low"])
        o = float(candle["open"])
        c = float(candle["close"])

        # body/range ratio
        candle_range = h - l
        if candle_range < 1e-12:
            body_range = 0.0
        else:
            body_range = abs(c - o) / candle_range

        if body_range < variant.body_range_min:
            continue

        # volume z-score
        if vol_z < variant.volume_zscore_min:
            continue

        # direction consistency
        if variant.direction_required:
            if signal_direction == "LONG" and c <= o:
                continue
            if signal_direction == "SHORT" and c >= o:
                continue

        return True, i, candle

    return False, -1, None


def apply_energy_overlay(
    signal_events: list[SignalEvent],
    candle_5m_index: Candle5mIndex,
    setup_candles_15m: list[dict],
    variant: EnergyVariant,
    timeout_mode: str,
) -> list[HybridTrade]:
    """Apply 5m energy overlay to baseline signal events."""
    hybrid_trades: list[HybridTrade] = []

    for event in signal_events:
        # NO-LOOKAHEAD: 5m search starts at 15m candle close T
        search_start = event.signal_time
        bars_5m = candle_5m_index.get_bars_from(search_start, variant.max_wait_bars)

        confirmed, bar_idx, conf_candle = check_energy_confirmation(
            variant, event.direction, bars_5m,
        )

        baseline_entry = event.baseline_trade.entry_price
        baseline_risk = abs(baseline_entry - event.invalidation_level)

        if confirmed and conf_candle is not None:
            # Enter at 5m close price when energy confirmed
            hybrid_entry_price = float(conf_candle["close"])
            hybrid_entry_time = conf_candle["open_time"] + timedelta(minutes=5)
            wait_bars = bar_idx + 1

            # Missed move cost: how much price moved adversely during wait
            if wait_bars > 0 and baseline_risk > 0:
                if event.direction == "LONG":
                    missed = (hybrid_entry_price - event.entry_reference) / baseline_risk
                else:
                    missed = (event.entry_reference - hybrid_entry_price) / baseline_risk
            else:
                missed = 0.0

            entry_delta_pct = (hybrid_entry_price - event.entry_reference) / event.entry_reference * 100

            # Simulate hybrid trade with 15m TP/SL levels, 15m future candles
            future_idx = event.candle_idx + 1
            future_candles = setup_candles_15m[future_idx:future_idx + MAX_HOLD_BARS_15M]

            trade = simulate_trade(
                direction=event.direction,
                entry_price=hybrid_entry_price,
                entry_time=hybrid_entry_time,
                stop_loss=event.invalidation_level,
                take_profit_1=event.tp_reference_1,
                future_candles=future_candles,
                max_hold_bars=MAX_HOLD_BARS_15M,
                fee_rate=FEE_RATE,
                slippage_bps=SLIPPAGE_BPS,
                regime=event.regime,
                confluence=event.confluence,
                sweep_depth_pct=event.sweep_depth_pct,
                reasons=event.reasons,
            )

            hybrid_trades.append(HybridTrade(
                signal_event=event, confirmed=True, confirmation_bar=bar_idx,
                wait_bars=wait_bars, entry_price=hybrid_entry_price,
                entry_time=hybrid_entry_time, trade=trade,
                entry_price_delta_pct=entry_delta_pct, missed_move_cost=missed,
            ))
        else:
            # Timeout: no energy confirmation within max_wait
            wait_bars = len(bars_5m)

            if timeout_mode == "SKIP":
                hybrid_trades.append(HybridTrade(
                    signal_event=event, confirmed=False, confirmation_bar=-1,
                    wait_bars=wait_bars, entry_price=0.0,
                    entry_time=event.signal_time, trade=None,
                    entry_price_delta_pct=0.0, missed_move_cost=0.0,
                ))
            else:
                # FALLBACK: enter at baseline price
                future_idx = event.candle_idx + 1
                future_candles = setup_candles_15m[future_idx:future_idx + MAX_HOLD_BARS_15M]

                trade = simulate_trade(
                    direction=event.direction,
                    entry_price=event.entry_reference,
                    entry_time=event.signal_time,
                    stop_loss=event.invalidation_level,
                    take_profit_1=event.tp_reference_1,
                    future_candles=future_candles,
                    max_hold_bars=MAX_HOLD_BARS_15M,
                    fee_rate=FEE_RATE,
                    slippage_bps=SLIPPAGE_BPS,
                    regime=event.regime,
                    confluence=event.confluence,
                    sweep_depth_pct=event.sweep_depth_pct,
                    reasons=event.reasons,
                )

                hybrid_trades.append(HybridTrade(
                    signal_event=event, confirmed=False, confirmation_bar=-1,
                    wait_bars=wait_bars, entry_price=event.entry_reference,
                    entry_time=event.signal_time, trade=trade,
                    entry_price_delta_pct=0.0, missed_move_cost=0.0,
                ))

    return hybrid_trades


# ── Matched-Subset + Verdict ──────────────────────────────────────────────────

def compute_overlay_result(
    variant: EnergyVariant,
    timeout_mode: str,
    hybrid_trades: list[HybridTrade],
    signal_events: list[SignalEvent],
    months: float,
) -> OverlayResult:
    """Compute metrics, matched-subset analysis, and verdict for one configuration."""
    result = OverlayResult(
        variant=variant, timeout_mode=timeout_mode,
        hybrid_trades=hybrid_trades, baseline_events=signal_events,
    )

    # Extract executed trades (non-None)
    result.executed_trades = [ht.trade for ht in hybrid_trades if ht.trade is not None]

    # Matched baseline subset: baseline trades for signals that produced hybrid trades
    executed_signal_times = {ht.signal_event.signal_time for ht in hybrid_trades if ht.trade is not None}
    result.matched_baseline_trades = [
        ev.baseline_trade for ev in signal_events if ev.signal_time in executed_signal_times
    ]

    # Full baseline
    all_baseline_trades = [ev.baseline_trade for ev in signal_events]

    result.metrics_hybrid = compute_metrics(result.executed_trades, months)
    result.metrics_matched_baseline = compute_metrics(result.matched_baseline_trades, months)
    result.metrics_full_baseline = compute_metrics(all_baseline_trades, months)

    # Fairness metrics
    confirmed_trades = [ht for ht in hybrid_trades if ht.confirmed]
    if confirmed_trades:
        result.avg_entry_price_delta_pct = sum(ht.entry_price_delta_pct for ht in confirmed_trades) / len(confirmed_trades)
        result.avg_missed_move_cost = sum(ht.missed_move_cost for ht in confirmed_trades) / len(confirmed_trades)
        result.avg_wait_bars = sum(ht.wait_bars for ht in confirmed_trades) / len(confirmed_trades)

    total_signals = len(signal_events)
    timeouts = sum(1 for ht in hybrid_trades if not ht.confirmed)
    result.timeout_rate = timeouts / total_signals * 100 if total_signals > 0 else 0

    baseline_count = result.metrics_full_baseline.trade_count
    result.frequency_ratio = result.metrics_hybrid.trade_count / baseline_count if baseline_count > 0 else 0

    # Verdict taxonomy
    result.verdict = _compute_verdict(result)

    return result


def _compute_verdict(r: OverlayResult) -> str:
    """Apply 5-level verdict taxonomy."""
    hybrid = r.metrics_hybrid
    matched = r.metrics_matched_baseline
    full_base = r.metrics_full_baseline

    if hybrid is None or hybrid.trade_count < 20:
        return "HYBRID_INCONCLUSIVE"

    freq = r.frequency_ratio

    # Matched-subset MAE improvement
    # MAE is negative (adverse excursion). Less negative = better.
    # Positive mae_improvement means hybrid has less adverse excursion.
    if matched and matched.avg_mae_r != 0:
        mae_improvement = (hybrid.avg_mae_r - matched.avg_mae_r) / abs(matched.avg_mae_r)
    else:
        mae_improvement = 0.0

    # Matched-subset ER comparison
    er_not_degraded = hybrid.expectancy_r >= matched.expectancy_r * 0.95 if matched else True

    # Entry price favorable (for LONG: lower is better, for SHORT: higher is better)
    entry_favorable = r.avg_entry_price_delta_pct <= 0  # negative = lower entry = better for LONG-biased

    # HYBRID_TIMING_PASS gates
    if (freq >= 0.80 and mae_improvement >= 0.10 and er_not_degraded and entry_favorable):
        return "HYBRID_TIMING_PASS"

    # HYBRID_FILTER_PASS gates
    if full_base and full_base.expectancy_r > 0:
        er_improvement = (hybrid.expectancy_r - full_base.expectancy_r) / abs(full_base.expectancy_r)
    else:
        er_improvement = 0.0

    if (0.60 <= freq < 0.80 and er_improvement >= 0.20):
        return "HYBRID_FILTER_PASS"

    # HYBRID_MARGINAL
    if (freq >= 0.70 and 0 < mae_improvement < 0.10):
        return "HYBRID_MARGINAL"

    return "HYBRID_FAIL"


# ── Report Generation ────────────────────────────────────────────────────────

def generate_report(
    funnel: FunnelMetrics,
    signal_events: list[SignalEvent],
    overlay_results: list[OverlayResult],
    months: float,
) -> str:
    lines = []
    baseline_trades = [ev.baseline_trade for ev in signal_events]
    baseline_metrics = compute_metrics(baseline_trades, months)

    # Header
    lines.append("# 15m Signal + 5m Energy Overlay Feasibility Study")
    lines.append("")
    lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Milestone:** 15M_SIGNAL_5M_ENERGY_OVERLAY_FEASIBILITY")
    lines.append(f"**Analysis Period:** {ANALYSIS_START.date()} to {ANALYSIS_END.date()} ({months:.1f} months)")
    lines.append(f"**Baseline:** trial-00095 exact parameters (15m)")
    lines.append(f"**Overlay:** 5m energy confirmation (body/range + volume z-score)")
    lines.append("")
    lines.append("> **IMPORTANT CAVEAT:** Uses standalone research harness (same as M5 study).")
    lines.append("> Results should NOT be compared with official BacktestRunner metrics.")
    lines.append("> Trade simulation uses simplified fills (no partial exits, no trailing stop).")
    lines.append("")

    # Best verdict
    best = min(overlay_results, key=lambda r: (
        {"HYBRID_TIMING_PASS": 0, "HYBRID_FILTER_PASS": 1, "HYBRID_MARGINAL": 2,
         "HYBRID_FAIL": 3, "HYBRID_INCONCLUSIVE": 4}.get(r.verdict, 5),
        -r.frequency_ratio,
    ))

    lines.append(f"## Verdict: `{best.verdict}`")
    lines.append("")
    lines.append(f"**Best configuration:** {best.variant.name} + {best.timeout_mode}")
    lines.append(f"- Frequency: {best.frequency_ratio:.0%} of baseline ({best.metrics_hybrid.trade_count}/{baseline_metrics.trade_count} trades)")
    lines.append(f"- Hybrid ER: {best.metrics_hybrid.expectancy_r:.3f} vs baseline ER: {baseline_metrics.expectancy_r:.3f}")
    if best.metrics_matched_baseline:
        lines.append(f"- Matched-subset MAE: {best.metrics_hybrid.avg_mae_r:.3f} vs {best.metrics_matched_baseline.avg_mae_r:.3f}")
    lines.append(f"- Timeout rate: {best.timeout_rate:.1f}%")
    lines.append(f"- Avg entry price delta: {best.avg_entry_price_delta_pct:+.4f}%")
    lines.append("")

    # Signal Funnel
    lines.append("## Signal Funnel (15m Baseline)")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---:|")
    lines.append(f"| Total bars | {funnel.total_bars:,} |")
    lines.append(f"| sweep_detected | {funnel.sweep_detected:,} |")
    lines.append(f"| sweep_too_shallow | {funnel.sweep_too_shallow:,} |")
    lines.append(f"| reclaim_detected | {funnel.reclaim_detected:,} |")
    lines.append(f"| signal_candidates | {funnel.signal_candidates:,} |")
    lines.append(f"| governance_rejected | {funnel.governance_rejected:,} |")
    lines.append(f"| risk_rejected | {funnel.risk_rejected:,} |")
    lines.append(f"| **baseline_trades** | **{funnel.trades_executed}** |")
    lines.append("")

    # 15m Baseline Performance
    lines.append("## 15m Baseline Performance")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Trade count | {baseline_metrics.trade_count} |")
    lines.append(f"| Expectancy R | {baseline_metrics.expectancy_r:.3f} |")
    lines.append(f"| Profit Factor | {baseline_metrics.profit_factor:.2f} |")
    lines.append(f"| Win Rate | {baseline_metrics.win_rate:.1f}% |")
    lines.append(f"| Max DD (R) | {baseline_metrics.max_drawdown_r:.2f} |")
    lines.append(f"| Avg MAE (R) | {baseline_metrics.avg_mae_r:.3f} |")
    lines.append(f"| Avg MFE (R) | {baseline_metrics.avg_mfe_r:.3f} |")
    lines.append(f"| Trades/month | {baseline_metrics.trades_per_month:.1f} |")
    lines.append("")

    # Energy Variant Grid
    lines.append("## Energy Variant Grid (E1-E4 x SKIP/FALLBACK)")
    lines.append("")
    lines.append("| Variant | Mode | Trades | Freq% | ER | PF | WR% | MAE(R) | Timeout% | Verdict |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in overlay_results:
        m = r.metrics_hybrid
        lines.append(
            f"| {r.variant.name} | {r.timeout_mode} | {m.trade_count} | "
            f"{r.frequency_ratio:.0%} | {m.expectancy_r:.3f} | {m.profit_factor:.2f} | "
            f"{m.win_rate:.1f} | {m.avg_mae_r:.3f} | {r.timeout_rate:.1f} | "
            f"`{r.verdict}` |"
        )
    lines.append("")

    # Entry Price Fairness Metrics
    lines.append("## Entry Price Fairness Metrics")
    lines.append("")
    lines.append("| Variant | Mode | Entry Delta% | Missed Move (R) | Avg Wait (bars) | Timeout% |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for r in overlay_results:
        lines.append(
            f"| {r.variant.name} | {r.timeout_mode} | {r.avg_entry_price_delta_pct:+.4f} | "
            f"{r.avg_missed_move_cost:+.3f} | {r.avg_wait_bars:.1f} | {r.timeout_rate:.1f} |"
        )
    lines.append("")

    # Matched-Subset Analysis
    lines.append("## Matched-Subset Analysis")
    lines.append("")
    lines.append("For each configuration, hybrid trades are paired with their baseline counterparts by signal timestamp.")
    lines.append("This isolates timing effect from filtering effect.")
    lines.append("")
    lines.append("| Variant | Mode | Hybrid ER | Matched Base ER | Hybrid MAE | Matched Base MAE | MAE Improv% |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for r in overlay_results:
        mh = r.metrics_hybrid
        mb = r.metrics_matched_baseline
        if mb and mb.avg_mae_r != 0:
            mae_imp = (mh.avg_mae_r - mb.avg_mae_r) / abs(mb.avg_mae_r) * 100
        else:
            mae_imp = 0.0
        lines.append(
            f"| {r.variant.name} | {r.timeout_mode} | {mh.expectancy_r:.3f} | "
            f"{mb.expectancy_r:.3f} | {mh.avg_mae_r:.3f} | {mb.avg_mae_r:.3f} | "
            f"{mae_imp:+.1f}% |"
        )
    lines.append("")

    # Verdict Taxonomy Reference
    lines.append("## Verdict Taxonomy")
    lines.append("")
    lines.append("| Verdict | Definition |")
    lines.append("|---|---|")
    lines.append("| `HYBRID_TIMING_PASS` | Freq >= 80%, matched MAE improvement >= 10%, ER not degraded, entry favorable |")
    lines.append("| `HYBRID_FILTER_PASS` | Freq 60-79%, full ER improvement >= 20% (skips bad trades) |")
    lines.append("| `HYBRID_MARGINAL` | Freq >= 70%, MAE improvement < 10% |")
    lines.append("| `HYBRID_FAIL` | No meaningful improvement |")
    lines.append("| `HYBRID_INCONCLUSIVE` | < 20 trades |")
    lines.append("")

    # Energy variant definitions
    lines.append("## Energy Variant Definitions")
    lines.append("")
    lines.append("| Variant | body/range min | vol_zscore min | direction required | max_wait (5m bars) |")
    lines.append("|---|---:|---:|---|---:|")
    for v in ENERGY_VARIANTS:
        lines.append(f"| {v.name} | {v.body_range_min} | {v.volume_zscore_min} | {'yes' if v.direction_required else 'no'} | {v.max_wait_bars} |")
    lines.append("")

    # Methodology
    lines.append("## Methodology Notes")
    lines.append("")
    lines.append("- **15m signal:** trial-00095 exact parameters (same as M5 baseline)")
    lines.append("- **5m energy:** body/range + volume z-score (rolling 20-bar window)")
    lines.append("- **No-lookahead:** 5m search starts at 15m candle close T")
    lines.append("- **Exit logic:** 15m TP1/SL (no 5m exit logic)")
    lines.append(f"- **Fees:** {FEE_RATE*100:.2f}% per side (taker)")
    lines.append(f"- **Slippage:** {SLIPPAGE_BPS} bps per side")
    lines.append(f"- **Max hold:** {RISK_PARAMS['max_hold_hours']}h ({MAX_HOLD_BARS_15M} bars @15m)")
    lines.append("- **SKIP mode:** Skip trade if no 5m confirmation")
    lines.append("- **FALLBACK mode:** Enter at baseline 15m price if no 5m confirmation")
    lines.append("- **Matched-subset:** Hybrid trades paired with baseline by signal timestamp")
    lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")
    verdicts = [r.verdict for r in overlay_results]
    if "HYBRID_TIMING_PASS" in verdicts:
        timing_pass = [r for r in overlay_results if r.verdict == "HYBRID_TIMING_PASS"]
        best_tp = max(timing_pass, key=lambda r: r.frequency_ratio)
        lines.append(f"5m energy confirmation improves entry timing. Best configuration: "
                      f"{best_tp.variant.name} + {best_tp.timeout_mode} "
                      f"(freq {best_tp.frequency_ratio:.0%}, MAE improvement observed). "
                      f"Consider integration into production execution layer.")
    elif "HYBRID_FILTER_PASS" in verdicts:
        lines.append("5m energy confirmation improves metrics by filtering bad trades, "
                      "but reduces frequency materially. Consider as optional signal quality gate.")
    elif "HYBRID_MARGINAL" in verdicts:
        lines.append("5m energy confirmation shows weak improvement. "
                      "Further research needed with different energy definitions or longer wait windows.")
    else:
        lines.append("5m energy confirmation does not meaningfully improve 15m signal quality. "
                      "Energy overlay adds complexity without benefit. Defer.")
    lines.append("")

    lines.append("---")
    lines.append("*Generated by research_lab/analysis_15m_signal_5m_energy_overlay.py*")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    t_start = time_mod.time()

    if not DB_5M.exists():
        print(f"ERROR: 5m database not found: {DB_5M}")
        return 1
    if not DB_15M.exists():
        print(f"ERROR: 15m database not found: {DB_15M}")
        return 1

    conn_5m = sqlite3.connect(str(DB_5M))
    conn_15m = sqlite3.connect(str(DB_15M))

    print("Loading data...")

    candles_15m = load_candles(conn_15m, "15m", ANALYSIS_START, ANALYSIS_END, lookback_bars=330)
    candles_5m = load_candles(conn_5m, "5m", ANALYSIS_START, ANALYSIS_END, lookback_bars=100)
    candles_1h = load_candles(conn_15m, "1h", ANALYSIS_START, ANALYSIS_END, lookback_bars=300)
    candles_4h = load_candles(conn_15m, "4h", ANALYSIS_START, ANALYSIS_END, lookback_bars=300)
    funding = load_funding(conn_15m)
    oi = load_oi(conn_15m)
    agg_15m = load_aggtrade_buckets(conn_15m, "15m")
    agg_60s = load_aggtrade_buckets(conn_15m, "60s")

    print(f"  15m candles: {len(candles_15m)}")
    print(f"  5m candles: {len(candles_5m)}")
    print(f"  1h: {len(candles_1h)}, 4h: {len(candles_4h)}")
    print(f"  Funding: {len(funding)}, OI: {len(oi)}")
    print(f"  Agg 15m: {len(agg_15m)}, Agg 60s: {len(agg_60s)}")

    conn_5m.close()
    conn_15m.close()

    print("Building pre-indexed data...")
    preloaded = PreloadedData.build(candles_1h, candles_4h, funding, oi, agg_15m, agg_60s)

    print("Building 5m candle index (volume z-scores)...")
    candle_5m_index = Candle5mIndex.build(candles_5m, rolling_window=20)
    print(f"  5m indexed: {len(candle_5m_index.times)} bars")

    months = (ANALYSIS_END - ANALYSIS_START).days / 30.44

    # Phase 1: Run 15m baseline signal detection
    funnel, signal_events = run_baseline_15m(candles_15m, preloaded, oi)

    baseline_trades = [ev.baseline_trade for ev in signal_events]
    baseline_metrics = compute_metrics(baseline_trades, months)
    print(f"\n15m baseline: {baseline_metrics.trade_count} trades, ER={baseline_metrics.expectancy_r:.3f}, "
          f"PF={baseline_metrics.profit_factor:.2f}, MAE={baseline_metrics.avg_mae_r:.3f}")

    # Phase 2: Apply 5m energy overlay (4 variants x 2 timeout modes)
    overlay_results: list[OverlayResult] = []

    for variant in ENERGY_VARIANTS:
        for timeout_mode in TIMEOUT_MODES:
            print(f"\nOverlay: {variant.name} + {timeout_mode} "
                  f"(body>={variant.body_range_min}, vol_z>={variant.volume_zscore_min}, "
                  f"dir={'req' if variant.direction_required else 'any'})")

            hybrid_trades = apply_energy_overlay(
                signal_events, candle_5m_index, candles_15m, variant, timeout_mode,
            )

            result = compute_overlay_result(variant, timeout_mode, hybrid_trades, signal_events, months)
            overlay_results.append(result)

            m = result.metrics_hybrid
            print(f"  -> {m.trade_count} trades ({result.frequency_ratio:.0%}), "
                  f"ER={m.expectancy_r:.3f}, MAE={m.avg_mae_r:.3f}, "
                  f"timeout={result.timeout_rate:.1f}%, verdict={result.verdict}")

    # Phase 3: Generate report
    report = generate_report(funnel, signal_events, overlay_results, months)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    elapsed = time_mod.time() - t_start
    print(f"\nReport written to: {REPORT_PATH}")
    print(f"Total runtime: {elapsed:.0f}s")

    # Summary
    best = min(overlay_results, key=lambda r: (
        {"HYBRID_TIMING_PASS": 0, "HYBRID_FILTER_PASS": 1, "HYBRID_MARGINAL": 2,
         "HYBRID_FAIL": 3, "HYBRID_INCONCLUSIVE": 4}.get(r.verdict, 5),
        -r.frequency_ratio,
    ))
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Baseline: {baseline_metrics.trade_count} trades, ER={baseline_metrics.expectancy_r:.3f}, MAE={baseline_metrics.avg_mae_r:.3f}")
    print(f"Best: {best.variant.name}+{best.timeout_mode} -> {best.metrics_hybrid.trade_count} trades, "
          f"ER={best.metrics_hybrid.expectancy_r:.3f}, MAE={best.metrics_hybrid.avg_mae_r:.3f}")
    print(f"VERDICT: {best.verdict}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

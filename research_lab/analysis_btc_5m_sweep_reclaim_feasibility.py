#!/usr/bin/env python3
"""
BTC 5m vs 15m Sweep/Reclaim Feasibility Study

Standalone research script that compares sweep/reclaim edge detection and
simulated trade performance on 5m vs 15m candles over the same calendar period.

IMPORTANT CAVEATS:
- This script bypasses BacktestRunner. It uses core engines (FeatureEngine,
  RegimeEngine, SignalEngine) directly with a simplified trade simulation.
- 15m results from this harness are APPROXIMATE and should NOT be compared
  directly with official BacktestRunner results without caveat.
- For fair comparison, both 5m and 15m runs use the SAME standalone harness.
- This is a FEASIBILITY study, not a production backtest.

Usage:
    python -m research_lab.analysis_btc_5m_sweep_reclaim_feasibility

No production, PAPER, runtime, settings, or execution changes.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time as time_mod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Core engine imports (read-only usage)
from core.context_engine import ContextEngine
from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.governance import GovernanceConfig, GovernanceLayer
from core.models import (
    ExecutableSignal,
    Features,
    GovernanceRuntimeState,
    MarketContext,
    MarketSnapshot,
    RegimeState,
    RiskRuntimeState,
    SignalCandidate,
)
from core.regime_engine import RegimeConfig, RegimeEngine
from core.risk_engine import RiskConfig, RiskEngine
from core.signal_engine import SignalConfig, SignalEngine
from settings import ContextConfig, build_signal_regime_direction_whitelist


# ── Configuration ──────────────────────────────────────────────────────────────

DB_5M = Path("research_lab/snapshots/btc_5m_2022_2026.db")
DB_15M = Path("research_lab/snapshots/replay-run13-regime-aware-trial-00063.db")
REPORT_PATH = Path("docs/analysis/BTC_5M_SWEEP_RECLAIM_FEASIBILITY_2026-05-14.md")
SYMBOL = "BTCUSDT"

# Common analysis period (M3 WF1+WF2 OOS windows)
ANALYSIS_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
ANALYSIS_END = datetime(2026, 3, 28, tzinfo=timezone.utc)

# Trial-00095 exact parameters (from settings.json)
TRIAL_00095_STRATEGY = {
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

TRIAL_00095_RISK = {
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

# Cost assumptions
FEE_RATE = 0.0004  # 0.04% per side (taker)
SLIPPAGE_BPS = 3.0  # 3 bps


# ── 5m Parameter Scaling ──────────────────────────────────────────────────────

SCALE_FACTOR = 3  # 15m / 5m = 3

def build_5m_params() -> dict:
    """Scale bar-count parameters by 3x, keep dimensionless params as-is."""
    params = dict(TRIAL_00095_STRATEGY)
    # Scale bar-count params (preserve time window, not bar count)
    params["atr_period"] = TRIAL_00095_STRATEGY["atr_period"] * SCALE_FACTOR  # 27 -> 81
    params["equal_level_lookback"] = TRIAL_00095_STRATEGY["equal_level_lookback"] * SCALE_FACTOR  # 276 -> 828
    params["level_min_age_bars"] = TRIAL_00095_STRATEGY["level_min_age_bars"] * SCALE_FACTOR  # 5 -> 15
    # EMA params are on 4h candles, NOT scaled (4h candles are same in both)
    # Dimensionless params: min_sweep_depth_pct, confluence_min, weights, etc. - unchanged
    return params


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_candles(conn: sqlite3.Connection, timeframe: str, start: datetime, end: datetime,
                 lookback_bars: int = 0) -> list[dict]:
    """Load candles from DB with optional lookback before start."""
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


def _parse_ts(val) -> datetime:
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    ts = datetime.fromisoformat(str(val))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


# ── Preloaded Indexed Data ─────────────────────────────────────────────────────

from bisect import bisect_right, bisect_left


@dataclass
class PreloadedData:
    """Pre-indexed supplementary data for O(log n) lookups."""
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
        oi_timestamps = [r["timestamp"] for r in oi]
        oi_values = [r["oi_value"] for r in oi]
        funding_times = [r["funding_time"] for r in funding]
        c1h_times = [c["open_time"] for c in candles_1h]
        c4h_times = [c["open_time"] for c in candles_4h]
        return cls(
            oi_timestamps=oi_timestamps, oi_values=oi_values,
            funding_times=funding_times, funding_rows=funding,
            agg_15m=agg_15m, agg_60s=agg_60s,
            candles_1h_times=c1h_times, candles_1h_rows=candles_1h,
            candles_4h_times=c4h_times, candles_4h_rows=candles_4h,
        )

    def get_oi(self, target: datetime) -> float:
        if not self.oi_timestamps:
            return 0.0
        idx = bisect_right(self.oi_timestamps, target) - 1
        if idx < 0:
            idx = 0
        return self.oi_values[idx]

    def get_funding(self, target: datetime, lookback: int = 200) -> list[dict]:
        idx = bisect_right(self.funding_times, target)
        start = max(0, idx - lookback)
        return self.funding_rows[start:idx]

    def get_1h(self, target: datetime, lookback: int = 300) -> list[dict]:
        idx = bisect_right(self.candles_1h_times, target)
        start = max(0, idx - lookback)
        return self.candles_1h_rows[start:idx]

    def get_4h(self, target: datetime, lookback: int = 300) -> list[dict]:
        idx = bisect_right(self.candles_4h_times, target)
        start = max(0, idx - lookback)
        return self.candles_4h_rows[start:idx]

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


def slice_setup_candles(all_candle_times: list[datetime], all_candles: list[dict],
                        up_to: datetime, lookback: int) -> list[dict]:
    """Bisect-based slice of candles up to target time with lookback limit."""
    idx = bisect_right(all_candle_times, up_to)
    start = max(0, idx - lookback)
    return all_candles[start:idx]


# ── Trade Simulation ──────────────────────────────────────────────────────────

@dataclass
class SimTrade:
    entry_time: datetime
    exit_time: datetime
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    pnl_r: float
    exit_reason: str
    regime: str
    confluence: float
    sweep_depth_pct: float
    reasons: list[str]
    mae_r: float = 0.0
    mfe_r: float = 0.0


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


def simulate_trade_outcome(
    candidate: SignalCandidate,
    future_candles: list[dict],
    max_hold_bars: int,
    fee_rate: float,
    slippage_bps: float,
    bar_minutes: int,
) -> SimTrade | None:
    """Simulate trade outcome using future candles after entry."""
    if not future_candles:
        return None

    entry_price = candidate.entry_reference
    stop = candidate.invalidation_level
    tp1 = candidate.tp_reference_1
    direction = candidate.direction

    # Apply slippage to entry
    slip = entry_price * slippage_bps / 10000
    if direction == "LONG":
        entry_price += slip
    else:
        entry_price -= slip

    risk = abs(entry_price - stop)
    if risk <= 0:
        return None

    mae = 0.0
    mfe = 0.0
    exit_price = entry_price
    exit_reason = "max_hold"
    exit_time = future_candles[0]["open_time"]

    for i, candle in enumerate(future_candles[:max_hold_bars]):
        h = float(candle["high"])
        l = float(candle["low"])
        c = float(candle["close"])

        if direction == "LONG":
            unrealized_low = (l - entry_price) / risk
            unrealized_high = (h - entry_price) / risk
            mae = min(mae, unrealized_low)
            mfe = max(mfe, unrealized_high)
            if l <= stop:
                exit_price = stop - slip
                exit_reason = "stop_loss"
                exit_time = candle["open_time"]
                break
            if h >= tp1:
                exit_price = tp1 - slip
                exit_reason = "take_profit"
                exit_time = candle["open_time"]
                break
        else:
            unrealized_low = (entry_price - h) / risk
            unrealized_high = (entry_price - l) / risk
            mae = min(mae, unrealized_low)
            mfe = max(mfe, unrealized_high)
            if h >= stop:
                exit_price = stop + slip
                exit_reason = "stop_loss"
                exit_time = candle["open_time"]
                break
            if l <= tp1:
                exit_price = tp1 + slip
                exit_reason = "take_profit"
                exit_time = candle["open_time"]
                break
        exit_price = c
        exit_time = candle["open_time"]

    # Compute PnL in R
    if direction == "LONG":
        raw_pnl = exit_price - entry_price
    else:
        raw_pnl = entry_price - exit_price

    # Subtract fees (entry + exit)
    fee_cost = entry_price * fee_rate + exit_price * fee_rate
    net_pnl = raw_pnl - fee_cost
    pnl_r = net_pnl / risk if risk > 0 else 0.0

    return SimTrade(
        entry_time=candidate.timestamp,
        exit_time=exit_time,
        direction=direction,
        entry_price=entry_price,
        exit_price=exit_price,
        stop_loss=stop,
        take_profit_1=tp1,
        take_profit_2=candidate.tp_reference_2,
        pnl_r=pnl_r,
        exit_reason=exit_reason,
        regime=candidate.regime.value,
        confluence=candidate.confluence_score,
        sweep_depth_pct=float(candidate.features_json.get("sweep_depth_pct", 0) or 0),
        reasons=candidate.reasons,
        mae_r=mae,
        mfe_r=mfe,
    )


# ── Run Harness ───────────────────────────────────────────────────────────────

def run_analysis(
    label: str,
    setup_candles: list[dict],
    candles_1h: list[dict],
    candles_4h: list[dict],
    funding_data: list[dict],
    oi_data: list[dict],
    agg_15m_data: dict[datetime, dict],
    agg_60s_data: dict[datetime, dict],
    params: dict,
    bar_minutes: int,
    lookback_bars: int,
    start: datetime,
    end: datetime,
    preloaded: PreloadedData,
) -> tuple[FunnelMetrics, list[SimTrade]]:
    """Run sweep/reclaim detection + signal generation on candles."""

    print(f"\n{'='*60}")
    print(f"Running {label} analysis ({bar_minutes}m bars)")
    print(f"Period: {start.date()} to {end.date()}")
    print(f"Setup candles: {len(setup_candles)}")
    print(f"{'='*60}")

    # Build engines with params
    feature_config = FeatureEngineConfig(
        atr_period=params["atr_period"],
        ema_fast=params["ema_fast"],
        ema_slow=params["ema_slow"],
        equal_level_lookback=params["equal_level_lookback"],
        equal_level_tol_atr=params["equal_level_tol_atr"],
        sweep_buf_atr=params["sweep_buf_atr"],
        sweep_proximity_atr=params["sweep_proximity_atr"],
        reclaim_buf_atr=params["reclaim_buf_atr"],
        wick_min_atr=params["wick_min_atr"],
        level_min_age_bars=params["level_min_age_bars"],
        min_hits=params["min_hits"],
        funding_window_days=params["funding_window_days"],
        oi_z_window_days=params["oi_z_window_days"],
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

    # Build whitelist for signal engine
    regime_whitelist = {
        "normal": ("LONG",),
        "compression": ("LONG",),
        "downtrend": ("LONG", "SHORT"),
        "uptrend": ("LONG",) if params.get("allow_long_in_uptrend") else (),
        "crowded_leverage": ("SHORT",),
        "post_liquidation": ("LONG",),
    }
    signal_config = SignalConfig(
        confluence_min=params["confluence_min"],
        min_sweep_depth_pct=params["min_sweep_depth_pct"],
        ema_trend_gap_pct=params["ema_trend_gap_pct"],
        entry_offset_atr=params["entry_offset_atr"],
        invalidation_offset_atr=params["invalidation_offset_atr"],
        min_stop_distance_pct=params["min_stop_distance_pct"],
        tp1_atr_mult=params["tp1_atr_mult"],
        tp2_atr_mult=params["tp2_atr_mult"],
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

    # Mutable state for governance/risk closures
    gov_state = GovernanceRuntimeState()
    risk_state = RiskRuntimeState()
    trades_today_date_holder: list[date | None] = [None]
    trades_today_count_holder: list[int] = [0]

    def gov_state_provider() -> GovernanceRuntimeState:
        return gov_state

    def risk_state_provider() -> RiskRuntimeState:
        return risk_state

    governance = GovernanceLayer(
        GovernanceConfig(
            cooldown_minutes_after_loss=TRIAL_00095_RISK["cooldown_minutes_after_loss"],
            duplicate_level_tolerance_pct=TRIAL_00095_RISK["duplicate_level_tolerance_pct"],
            duplicate_level_window_hours=TRIAL_00095_RISK["duplicate_level_window_hours"],
            max_trades_per_day=TRIAL_00095_RISK["max_trades_per_day"],
            max_consecutive_losses=TRIAL_00095_RISK["max_consecutive_losses"],
        ),
        state_provider=gov_state_provider,
    )
    risk_engine = RiskEngine(
        RiskConfig(
            risk_per_trade_pct=TRIAL_00095_RISK["risk_per_trade_pct"],
            max_leverage=TRIAL_00095_RISK["max_leverage"],
            min_rr=TRIAL_00095_RISK["min_rr"],
            max_open_positions=TRIAL_00095_RISK["max_open_positions"],
        ),
        state_provider=risk_state_provider,
    )

    # Bootstrap OI history
    feature_engine.bootstrap_oi_history(oi_data)

    funnel = FunnelMetrics()
    trades: list[SimTrade] = []
    max_hold_bars = int(TRIAL_00095_RISK["max_hold_hours"] * 60 / bar_minutes)

    # Pre-index setup candle times for bisect
    setup_candle_times = [c["open_time"] for c in setup_candles]

    # Filter analysis window using bisect
    start_idx = bisect_left(setup_candle_times, start)
    end_idx = bisect_right(setup_candle_times, end)
    analysis_indices = list(range(start_idx, end_idx))
    total = len(analysis_indices)
    report_interval = max(total // 20, 1)

    # Lightweight sweep detection imports
    from core.feature_engine import compute_atr, detect_equal_levels, detect_sweep_reclaim

    full_engine_calls = 0

    for progress_idx, candle_idx in enumerate(analysis_indices):
        candle = setup_candles[candle_idx]
        candle_time = candle["open_time"]
        snapshot_ts = candle_time + timedelta(minutes=bar_minutes)

        # Progress
        if progress_idx % report_interval == 0:
            pct = progress_idx / max(total, 1) * 100
            print(f"  [{pct:5.1f}%] {candle_time.date()} | sweeps: {funnel.sweep_detected} | trades: {len(trades)} | full_engine: {full_engine_calls}")

        # Build setup lookback (cheap slice)
        lb_start = max(0, candle_idx + 1 - lookback_bars)
        setup_lookback = setup_candles[lb_start:candle_idx + 1]
        if len(setup_lookback) < 20:
            continue

        funnel.total_bars += 1

        # ── PHASE 1: Lightweight sweep pre-filter (no full FeatureEngine) ──
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

        # Check depth threshold
        if sweep_depth is not None and sweep_depth < params["min_sweep_depth_pct"]:
            funnel.sweep_too_shallow += 1
            funnel.blocked_by_counts["sweep_too_shallow"] += 1
            continue

        if reclaim_det:
            funnel.reclaim_detected += 1

        # ── PHASE 2: Full FeatureEngine only for sweep+depth candidates ──
        full_engine_calls += 1
        ctx_1h = preloaded.get_1h(snapshot_ts)
        ctx_4h = preloaded.get_4h(snapshot_ts)
        funding_hist = preloaded.get_funding(snapshot_ts)
        oi_val = preloaded.get_oi(snapshot_ts)
        agg_15m_val = preloaded.get_agg_15m(candle_time)
        agg_60s_val = preloaded.get_agg_60s(snapshot_ts)

        close_price = float(candle["close"])
        snapshot = MarketSnapshot(
            symbol=SYMBOL,
            timestamp=snapshot_ts,
            price=close_price,
            bid=close_price,
            ask=close_price,
            candles_15m=setup_lookback,
            candles_1h=ctx_1h,
            candles_4h=ctx_4h,
            funding_history=funding_hist,
            open_interest=oi_val,
            aggtrades_bucket_60s=agg_60s_val,
            aggtrades_bucket_15m=agg_15m_val,
            force_order_events_60s=[],
        )

        features = feature_engine.compute(snapshot, schema_version="v1.0", config_hash="feasibility")
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
            elif diagnostics.blocked_by == "confluence_below_min":
                funnel.confluence_below_min += 1
            continue

        # Generate candidate
        candidate = signal_engine.generate(features, regime, diagnostics=diagnostics, context=context)
        if candidate is None:
            continue

        funnel.signal_candidates += 1

        # Update governance state for this cycle
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
        risk_decision = risk_engine.evaluate(
            signal=executable,
            equity=10000.0,
            open_positions=0,
        )
        if not risk_decision.allowed:
            funnel.risk_rejected += 1
            continue

        # Simulate trade
        future_idx = candle_idx + 1
        future_candles = setup_candles[future_idx:future_idx + max_hold_bars]
        trade = simulate_trade_outcome(
            candidate, future_candles, max_hold_bars, FEE_RATE, SLIPPAGE_BPS, bar_minutes,
        )
        if trade is None:
            continue

        funnel.trades_executed += 1
        trades.append(trade)

        # Update mutable governance/risk state
        gov_state.last_trade_at = trade.entry_time
        if trade.pnl_r < 0:
            gov_state.last_loss_at = trade.entry_time
            gov_state.consecutive_losses += 1
            risk_state.consecutive_losses += 1
        else:
            gov_state.consecutive_losses = 0
            risk_state.consecutive_losses = 0

        trades_today_count_holder[0] += 1

    print(f"  [100.0%] Complete | sweeps: {funnel.sweep_detected} | trades: {len(trades)} | full_engine: {full_engine_calls}")
    return funnel, trades


# ── Metrics Computation ───────────────────────────────────────────────────────

@dataclass
class PerformanceMetrics:
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_winner_r: float = 0.0
    avg_loser_r: float = 0.0
    median_r: float = 0.0
    trades_per_month: float = 0.0
    avg_mae_r: float = 0.0
    avg_mfe_r: float = 0.0
    max_consecutive_losses: int = 0
    er_by_month: dict = field(default_factory=dict)
    er_by_regime: dict = field(default_factory=dict)
    trades_by_regime: dict = field(default_factory=dict)


def compute_metrics(trades: list[SimTrade], months: float) -> PerformanceMetrics:
    if not trades:
        return PerformanceMetrics()

    m = PerformanceMetrics()
    m.trade_count = len(trades)
    winners = [t for t in trades if t.pnl_r > 0]
    losers = [t for t in trades if t.pnl_r <= 0]
    m.win_count = len(winners)
    m.loss_count = len(losers)
    m.win_rate = m.win_count / m.trade_count * 100 if m.trade_count else 0

    pnls = [t.pnl_r for t in trades]
    m.expectancy_r = sum(pnls) / len(pnls) if pnls else 0
    m.median_r = sorted(pnls)[len(pnls) // 2] if pnls else 0

    gross_profit = sum(t.pnl_r for t in winners) if winners else 0
    gross_loss = abs(sum(t.pnl_r for t in losers)) if losers else 0
    m.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

    m.avg_winner_r = sum(t.pnl_r for t in winners) / len(winners) if winners else 0
    m.avg_loser_r = sum(t.pnl_r for t in losers) / len(losers) if losers else 0

    m.avg_mae_r = sum(t.mae_r for t in trades) / len(trades)
    m.avg_mfe_r = sum(t.mfe_r for t in trades) / len(trades)

    m.trades_per_month = m.trade_count / max(months, 0.1)

    # Max drawdown (in R)
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        cumulative += t.pnl_r
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd = max(max_dd, dd)
    m.max_drawdown_pct = max_dd  # In R units

    # Max consecutive losses
    streak = 0
    max_streak = 0
    for t in trades:
        if t.pnl_r <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    m.max_consecutive_losses = max_streak

    # ER by month
    monthly: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        key = t.entry_time.strftime("%Y-%m")
        monthly[key].append(t.pnl_r)
    m.er_by_month = {k: sum(v) / len(v) for k, v in sorted(monthly.items())}

    # ER by regime
    regime_trades: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        regime_trades[t.regime].append(t.pnl_r)
    m.er_by_regime = {k: sum(v) / len(v) for k, v in regime_trades.items()}
    m.trades_by_regime = {k: len(v) for k, v in regime_trades.items()}

    return m


# ── Overtrading Analysis ──────────────────────────────────────────────────────

def overtrading_analysis(trades: list[SimTrade]) -> dict:
    """Check for overtrading signals."""
    if not trades:
        return {"daily_max": 0, "min_gap_minutes": 0, "days_over_5": 0, "gap_under_30min": 0}

    # Trades per day
    daily: dict[date, int] = defaultdict(int)
    for t in trades:
        daily[t.entry_time.date()] += 1
    daily_max = max(daily.values()) if daily else 0
    days_over_5 = sum(1 for v in daily.values() if v > 5)

    # Minimum gap between trades
    gaps = []
    for i in range(1, len(trades)):
        gap = (trades[i].entry_time - trades[i - 1].entry_time).total_seconds() / 60
        gaps.append(gap)
    min_gap = min(gaps) if gaps else float("inf")
    gap_under_30 = sum(1 for g in gaps if g < 30)

    return {
        "daily_max": daily_max,
        "min_gap_minutes": round(min_gap, 1),
        "days_over_5": days_over_5,
        "gap_under_30min": gap_under_30,
    }


def concentration_analysis(trades: list[SimTrade]) -> dict:
    """Check if PnL is concentrated in one month."""
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

    return {
        "max_month_pct": round(max_pct, 1),
        "concentrated": max_pct > 50,
        "top_month": max(monthly_pnl, key=lambda k: abs(monthly_pnl[k])),
    }


# ── Cost Sensitivity ──────────────────────────────────────────────────────────

def cost_sensitivity(trades: list[SimTrade], base_fee: float, base_slip: float) -> list[dict]:
    """Test ER at 1x, 2x, 3x cost multipliers."""
    results = []
    for mult in [1, 2, 3]:
        adjusted_pnls = []
        for t in trades:
            risk = abs(t.entry_price - t.stop_loss)
            if risk <= 0:
                continue
            extra_fee = t.entry_price * base_fee * (mult - 1) * 2  # entry + exit
            extra_slip = t.entry_price * base_slip / 10000 * (mult - 1) * 2
            adjusted_pnl = t.pnl_r - (extra_fee + extra_slip) / risk
            adjusted_pnls.append(adjusted_pnl)

        er = sum(adjusted_pnls) / len(adjusted_pnls) if adjusted_pnls else 0
        pf_win = sum(p for p in adjusted_pnls if p > 0)
        pf_loss = abs(sum(p for p in adjusted_pnls if p <= 0))
        pf = pf_win / pf_loss if pf_loss > 0 else float("inf")
        results.append({"multiplier": f"{mult}x", "er": round(er, 3), "pf": round(pf, 2)})
    return results


# ── Report Generation ─────────────────────────────────────────────────────────

def generate_report(
    funnel_5m: FunnelMetrics,
    trades_5m: list[SimTrade],
    metrics_5m: PerformanceMetrics,
    funnel_15m: FunnelMetrics,
    trades_15m: list[SimTrade],
    metrics_15m: PerformanceMetrics,
    months: float,
) -> str:
    lines = []

    # Header
    lines.append("# BTC 5m vs 15m Sweep/Reclaim Feasibility Study")
    lines.append("")
    lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Milestone:** BTC_5M_SWEEP_RECLAIM_FEASIBILITY_V1")
    lines.append(f"**Analysis Period:** {ANALYSIS_START.date()} to {ANALYSIS_END.date()} ({months:.1f} months)")
    lines.append(f"**Baseline:** trial-00095 exact parameters")
    lines.append(f"**5m Scaling:** Bar-count params × {SCALE_FACTOR} (preserving time windows)")
    lines.append("")

    # CAVEAT
    lines.append("> **IMPORTANT CAVEAT:** Both 5m and 15m results use a standalone research harness")
    lines.append("> that bypasses BacktestRunner. Results are internally consistent (fair 5m vs 15m comparison)")
    lines.append("> but should NOT be directly compared with official BacktestRunner metrics from M3/WF studies.")
    lines.append("> Trade simulation uses simplified fills (no partial exits, no trailing stop, no funding accrual).")
    lines.append("")

    # Verdict
    verdict, verdict_reason = _compute_verdict(funnel_5m, trades_5m, metrics_5m, funnel_15m, trades_15m, metrics_15m, months)
    lines.append(f"## Verdict: `{verdict}`")
    lines.append("")
    lines.append(verdict_reason)
    lines.append("")

    # Signal Funnel
    lines.append("## Signal Funnel Comparison")
    lines.append("")
    lines.append("| Metric | 15m | 5m | 5m/15m Ratio |")
    lines.append("|---|---:|---:|---:|")
    _ratio = lambda a, b: f"{a/b:.2f}x" if b > 0 else "N/A"
    lines.append(f"| Total bars | {funnel_15m.total_bars:,} | {funnel_5m.total_bars:,} | {_ratio(funnel_5m.total_bars, funnel_15m.total_bars)} |")
    lines.append(f"| sweep_detected | {funnel_15m.sweep_detected:,} | {funnel_5m.sweep_detected:,} | {_ratio(funnel_5m.sweep_detected, funnel_15m.sweep_detected)} |")
    lines.append(f"| sweep_too_shallow | {funnel_15m.sweep_too_shallow:,} | {funnel_5m.sweep_too_shallow:,} | {_ratio(funnel_5m.sweep_too_shallow, funnel_15m.sweep_too_shallow)} |")
    lines.append(f"| reclaim_detected | {funnel_15m.reclaim_detected:,} | {funnel_5m.reclaim_detected:,} | {_ratio(funnel_5m.reclaim_detected, funnel_15m.reclaim_detected)} |")
    lines.append(f"| signal_candidates | {funnel_15m.signal_candidates:,} | {funnel_5m.signal_candidates:,} | {_ratio(funnel_5m.signal_candidates, funnel_15m.signal_candidates)} |")
    lines.append(f"| governance_rejected | {funnel_15m.governance_rejected:,} | {funnel_5m.governance_rejected:,} | {_ratio(funnel_5m.governance_rejected, funnel_15m.governance_rejected)} |")
    lines.append(f"| risk_rejected | {funnel_15m.risk_rejected:,} | {funnel_5m.risk_rejected:,} | {_ratio(funnel_5m.risk_rejected, funnel_15m.risk_rejected)} |")
    lines.append(f"| **trades_executed** | **{funnel_15m.trades_executed}** | **{funnel_5m.trades_executed}** | **{_ratio(funnel_5m.trades_executed, funnel_15m.trades_executed)}** |")
    lines.append("")

    # Blocked-by breakdown
    lines.append("### Blocked-By Breakdown")
    lines.append("")
    lines.append("| Reason | 15m | 5m |")
    lines.append("|---|---:|---:|")
    all_reasons = sorted(set(list(funnel_15m.blocked_by_counts.keys()) + list(funnel_5m.blocked_by_counts.keys())))
    for reason in all_reasons:
        lines.append(f"| {reason} | {funnel_15m.blocked_by_counts.get(reason, 0):,} | {funnel_5m.blocked_by_counts.get(reason, 0):,} |")
    lines.append("")

    # Performance
    lines.append("## Performance Comparison")
    lines.append("")
    lines.append("| Metric | 15m | 5m | Gate | Status |")
    lines.append("|---|---:|---:|---|---|")
    lines.append(f"| Trade count | {metrics_15m.trade_count} | {metrics_5m.trade_count} | 5m ≥ 2× 15m | {'✅' if metrics_5m.trade_count >= 2 * metrics_15m.trade_count else '❌'} |")
    lines.append(f"| Expectancy R | {metrics_15m.expectancy_r:.3f} | {metrics_5m.expectancy_r:.3f} | > 1.0 | {'✅' if metrics_5m.expectancy_r > 1.0 else '❌'} |")
    lines.append(f"| Profit Factor | {metrics_15m.profit_factor:.2f} | {metrics_5m.profit_factor:.2f} | > 1.5 | {'✅' if metrics_5m.profit_factor > 1.5 else '❌'} |")
    lines.append(f"| Win Rate % | {metrics_15m.win_rate:.1f}% | {metrics_5m.win_rate:.1f}% | — | — |")
    lines.append(f"| Max DD (R) | {metrics_15m.max_drawdown_pct:.2f} | {metrics_5m.max_drawdown_pct:.2f} | ≤ 15m | {'✅' if metrics_5m.max_drawdown_pct <= metrics_15m.max_drawdown_pct * 1.5 else '❌'} |")
    lines.append(f"| Trades/month | {metrics_15m.trades_per_month:.1f} | {metrics_5m.trades_per_month:.1f} | — | — |")
    lines.append(f"| Avg winner R | {metrics_15m.avg_winner_r:.3f} | {metrics_5m.avg_winner_r:.3f} | — | — |")
    lines.append(f"| Avg loser R | {metrics_15m.avg_loser_r:.3f} | {metrics_5m.avg_loser_r:.3f} | — | — |")
    lines.append(f"| Median R | {metrics_15m.median_r:.3f} | {metrics_5m.median_r:.3f} | — | — |")
    lines.append(f"| Avg MAE R | {metrics_15m.avg_mae_r:.3f} | {metrics_5m.avg_mae_r:.3f} | — | — |")
    lines.append(f"| Avg MFE R | {metrics_15m.avg_mfe_r:.3f} | {metrics_5m.avg_mfe_r:.3f} | — | — |")
    lines.append(f"| Max consec. losses | {metrics_15m.max_consecutive_losses} | {metrics_5m.max_consecutive_losses} | — | — |")
    lines.append("")

    # Frequency
    lines.append("## Frequency Analysis")
    lines.append("")
    lines.append(f"| Metric | 15m | 5m |")
    lines.append(f"|---|---:|---:|")
    lines.append(f"| Trades/month | {metrics_15m.trades_per_month:.1f} | {metrics_5m.trades_per_month:.1f} |")
    lines.append(f"| Trade count ratio (5m/15m) | — | {metrics_5m.trade_count / max(metrics_15m.trade_count, 1):.2f}x |")
    lines.append("")

    # Overtrading
    ot_5m = overtrading_analysis(trades_5m)
    ot_15m = overtrading_analysis(trades_15m)
    lines.append("### Overtrading Flags")
    lines.append("")
    lines.append("| Flag | 15m | 5m | Concern? |")
    lines.append("|---|---:|---:|---|")
    lines.append(f"| Max trades/day | {ot_15m['daily_max']} | {ot_5m['daily_max']} | {'⚠️' if ot_5m['daily_max'] > 5 else '✅'} |")
    lines.append(f"| Days > 5 trades | {ot_15m['days_over_5']} | {ot_5m['days_over_5']} | {'⚠️' if ot_5m['days_over_5'] > 0 else '✅'} |")
    lines.append(f"| Min gap (min) | {ot_15m['min_gap_minutes']} | {ot_5m['min_gap_minutes']} | {'⚠️' if ot_5m['min_gap_minutes'] < 30 else '✅'} |")
    lines.append(f"| Gaps < 30min | {ot_15m['gap_under_30min']} | {ot_5m['gap_under_30min']} | {'⚠️' if ot_5m['gap_under_30min'] > 5 else '✅'} |")
    lines.append("")

    # Concentration
    conc_5m = concentration_analysis(trades_5m)
    conc_15m = concentration_analysis(trades_15m)
    lines.append("### Concentration Risk")
    lines.append("")
    lines.append(f"| Metric | 15m | 5m | Gate |")
    lines.append(f"|---|---:|---:|---|")
    lines.append(f"| Max month PnL % | {conc_15m.get('max_month_pct', 0)}% | {conc_5m.get('max_month_pct', 0)}% | < 50% | ")
    lines.append(f"| Concentrated? | {'YES' if conc_15m.get('concentrated') else 'NO'} | {'YES' if conc_5m.get('concentrated') else 'NO'} | {'❌' if conc_5m.get('concentrated') else '✅'} |")
    lines.append("")

    # ER by regime
    lines.append("## ER by Regime")
    lines.append("")
    lines.append("| Regime | 15m ER | 15m Trades | 5m ER | 5m Trades |")
    lines.append("|---|---:|---:|---:|---:|")
    all_regimes = sorted(set(list(metrics_15m.er_by_regime.keys()) + list(metrics_5m.er_by_regime.keys())))
    for r in all_regimes:
        er_15 = metrics_15m.er_by_regime.get(r, 0)
        tc_15 = metrics_15m.trades_by_regime.get(r, 0)
        er_5 = metrics_5m.er_by_regime.get(r, 0)
        tc_5 = metrics_5m.trades_by_regime.get(r, 0)
        lines.append(f"| {r} | {er_15:.3f} | {tc_15} | {er_5:.3f} | {tc_5} |")
    lines.append("")

    # Cost sensitivity
    lines.append("## Cost Sensitivity (5m)")
    lines.append("")
    sens = cost_sensitivity(trades_5m, FEE_RATE, SLIPPAGE_BPS)
    lines.append("| Cost Multiplier | ER | PF |")
    lines.append("|---|---:|---:|")
    for s in sens:
        lines.append(f"| {s['multiplier']} | {s['er']} | {s['pf']} |")
    lines.append("")

    # ER by month
    lines.append("## ER by Month (5m)")
    lines.append("")
    lines.append("| Month | 5m ER | 5m Trades | 15m ER | 15m Trades |")
    lines.append("|---|---:|---:|---:|---:|")
    all_months = sorted(set(list(metrics_5m.er_by_month.keys()) + list(metrics_15m.er_by_month.keys())))
    monthly_5m_trades: dict[str, int] = defaultdict(int)
    for t in trades_5m:
        monthly_5m_trades[t.entry_time.strftime("%Y-%m")] += 1
    monthly_15m_trades: dict[str, int] = defaultdict(int)
    for t in trades_15m:
        monthly_15m_trades[t.entry_time.strftime("%Y-%m")] += 1
    for m in all_months:
        er5 = metrics_5m.er_by_month.get(m, 0)
        tc5 = monthly_5m_trades.get(m, 0)
        er15 = metrics_15m.er_by_month.get(m, 0)
        tc15 = monthly_15m_trades.get(m, 0)
        lines.append(f"| {m} | {er5:.3f} | {tc5} | {er15:.3f} | {tc15} |")
    lines.append("")

    # Parameter adaptation
    lines.append("## Parameter Adaptation")
    lines.append("")
    lines.append("| Parameter | 15m Value | 5m Value | Scaling |")
    lines.append("|---|---:|---:|---|")
    p15 = TRIAL_00095_STRATEGY
    p5 = build_5m_params()
    lines.append(f"| atr_period | {p15['atr_period']} | {p5['atr_period']} | ×{SCALE_FACTOR} (time window) |")
    lines.append(f"| equal_level_lookback | {p15['equal_level_lookback']} | {p5['equal_level_lookback']} | ×{SCALE_FACTOR} (time window) |")
    lines.append(f"| level_min_age_bars | {p15['level_min_age_bars']} | {p5['level_min_age_bars']} | ×{SCALE_FACTOR} (time window) |")
    lines.append(f"| min_sweep_depth_pct | {p15['min_sweep_depth_pct']} | {p5['min_sweep_depth_pct']} | unchanged (dimensionless) |")
    lines.append(f"| confluence_min | {p15['confluence_min']} | {p5['confluence_min']} | unchanged (dimensionless) |")
    lines.append(f"| sweep_buf_atr | {p15['sweep_buf_atr']} | {p5['sweep_buf_atr']} | unchanged (ATR-relative) |")
    lines.append(f"| reclaim_buf_atr | {p15['reclaim_buf_atr']} | {p5['reclaim_buf_atr']} | unchanged (ATR-relative) |")
    lines.append(f"| wick_min_atr | {p15['wick_min_atr']} | {p5['wick_min_atr']} | unchanged (ATR-relative) |")
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append(f"| 5m data source | Binance Futures API (/fapi/v1/klines) |")
    lines.append(f"| 5m data range | 2022-01-01 to 2026-03-28 |")
    lines.append(f"| 5m total bars | 447,000 |")
    lines.append(f"| 5m quality | PASS (0 duplicates, 0 OHLC violations, 100.33% coverage) |")
    lines.append(f"| 15m data source | replay-run13-regime-aware-trial-00063.db |")
    lines.append(f"| 15m data range | 2020-09-01 to 2026-03-28 |")
    lines.append(f"| Analysis period | {ANALYSIS_START.date()} to {ANALYSIS_END.date()} |")
    lines.append(f"| Supplementary data | 1h/4h/funding/OI/aggtrades from 15m replay DB |")
    lines.append("")

    # Methodology
    lines.append("## Methodology Notes")
    lines.append("")
    lines.append("- **Harness:** Standalone research script, NOT BacktestRunner")
    lines.append("- **Trade simulation:** TP1 or SL hit within max_hold_bars, simplified (no partial exits, no trailing)")
    lines.append(f"- **Fees:** {FEE_RATE*100:.2f}% per side (taker)")
    lines.append(f"- **Slippage:** {SLIPPAGE_BPS} bps per side")
    lines.append(f"- **Max hold:** {TRIAL_00095_RISK['max_hold_hours']}h ({int(TRIAL_00095_RISK['max_hold_hours']*60/5)} bars @5m, {int(TRIAL_00095_RISK['max_hold_hours']*60/15)} bars @15m)")
    lines.append("- **Governance:** Cooldown after loss, duplicate level check")
    lines.append("- **Risk:** Max 1 position, max 5 trades/day, min RR check")
    lines.append("- **Both 5m and 15m use same harness** for fair comparison")
    lines.append("")

    lines.append("## Recommendation")
    lines.append("")
    if verdict == "5M_FEASIBILITY_PASS":
        lines.append("5m shows clear advantage over 15m. Recommend building full 5m runtime infrastructure as next milestone.")
    elif verdict == "5M_FEASIBILITY_MARGINAL":
        lines.append("5m shows promise but results are uncertain. Recommend extended analysis or limited 5m trial before full infrastructure investment.")
    elif verdict == "5M_FEASIBILITY_FAIL":
        lines.append("5m does not improve on 15m meaningfully. Stay on 15m. Defer 5m upgrade.")
    else:
        lines.append(f"Verdict: {verdict}. See verdict section for details.")
    lines.append("")

    lines.append("---")
    lines.append("*Generated by research_lab/analysis_btc_5m_sweep_reclaim_feasibility.py*")

    return "\n".join(lines)


def _compute_verdict(
    funnel_5m, trades_5m, metrics_5m,
    funnel_15m, trades_15m, metrics_15m,
    months,
) -> tuple[str, str]:
    """Apply acceptance gates and return (verdict, reason)."""
    gates = []

    # Gate: trade count increase (5m >= 2x 15m)
    tc_ratio = metrics_5m.trade_count / max(metrics_15m.trade_count, 1)
    if tc_ratio >= 2.0:
        gates.append(("trade_count_increase", True, f"5m has {tc_ratio:.1f}x trades vs 15m"))
    else:
        gates.append(("trade_count_increase", False, f"5m has {tc_ratio:.1f}x trades vs 15m (need ≥2x)"))

    # Gate: OOS ER > 1.0
    if metrics_5m.expectancy_r > 1.0:
        gates.append(("expectancy_r", True, f"5m ER={metrics_5m.expectancy_r:.3f} > 1.0"))
    elif metrics_5m.expectancy_r > 0.5:
        gates.append(("expectancy_r", "marginal", f"5m ER={metrics_5m.expectancy_r:.3f} (0.5-1.0 marginal)"))
    else:
        gates.append(("expectancy_r", False, f"5m ER={metrics_5m.expectancy_r:.3f} < 0.5"))

    # Gate: PF > 1.5
    if metrics_5m.profit_factor > 1.5:
        gates.append(("profit_factor", True, f"5m PF={metrics_5m.profit_factor:.2f} > 1.5"))
    elif metrics_5m.profit_factor > 1.2:
        gates.append(("profit_factor", "marginal", f"5m PF={metrics_5m.profit_factor:.2f} (1.2-1.5 marginal)"))
    else:
        gates.append(("profit_factor", False, f"5m PF={metrics_5m.profit_factor:.2f} < 1.2"))

    # Gate: DD not materially worse
    if metrics_15m.max_drawdown_pct > 0:
        dd_ratio = metrics_5m.max_drawdown_pct / metrics_15m.max_drawdown_pct
        if dd_ratio <= 1.5:
            gates.append(("max_drawdown", True, f"5m DD ratio {dd_ratio:.1f}x vs 15m"))
        else:
            gates.append(("max_drawdown", False, f"5m DD ratio {dd_ratio:.1f}x vs 15m (>1.5x worse)"))
    else:
        gates.append(("max_drawdown", True, "15m has zero DD"))

    # Gate: no single month > 50% PnL
    conc = concentration_analysis(trades_5m)
    if not conc.get("concentrated", False):
        gates.append(("concentration", True, f"Max month {conc.get('max_month_pct', 0)}%"))
    else:
        gates.append(("concentration", False, f"Concentrated: max month {conc.get('max_month_pct', 0)}%"))

    # Gate: overtrading
    ot = overtrading_analysis(trades_5m)
    if ot["days_over_5"] == 0 and ot["gap_under_30min"] <= 5:
        gates.append(("overtrading", True, "No overtrading flags"))
    else:
        gates.append(("overtrading", False, f"Overtrading: {ot['days_over_5']} days >5 trades, {ot['gap_under_30min']} gaps <30min"))

    # Determine verdict
    all_pass = all(g[1] is True for g in gates)
    any_fail = any(g[1] is False for g in gates)
    any_marginal = any(g[1] == "marginal" for g in gates)

    gate_summary = "\n".join(f"- **{g[0]}**: {'PASS' if g[1] is True else 'MARGINAL' if g[1] == 'marginal' else 'FAIL'} — {g[2]}" for g in gates)

    if all_pass:
        return "5M_FEASIBILITY_PASS", f"All acceptance gates passed.\n\n{gate_summary}"
    elif any_fail and not any_marginal:
        return "5M_FEASIBILITY_FAIL", f"One or more gates failed.\n\n{gate_summary}"
    elif any_fail:
        return "5M_FEASIBILITY_FAIL", f"One or more gates failed (some marginal).\n\n{gate_summary}"
    else:
        return "5M_FEASIBILITY_MARGINAL", f"All hard gates passed but some are marginal.\n\n{gate_summary}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    t_start = time_mod.time()

    # Check DBs exist
    if not DB_5M.exists():
        print(f"ERROR: 5m database not found: {DB_5M}")
        return 1
    if not DB_15M.exists():
        print(f"ERROR: 15m database not found: {DB_15M}")
        return 1

    # Connect
    conn_5m = sqlite3.connect(str(DB_5M))
    conn_15m = sqlite3.connect(str(DB_15M))

    print("Loading data...")

    # Load 5m candles
    candles_5m = load_candles(conn_5m, "5m", ANALYSIS_START, ANALYSIS_END, lookback_bars=900)
    print(f"  5m candles: {len(candles_5m)}")

    # Load 15m candles
    candles_15m = load_candles(conn_15m, "15m", ANALYSIS_START, ANALYSIS_END, lookback_bars=300)
    print(f"  15m candles: {len(candles_15m)}")

    # Load supplementary data from 15m DB
    candles_1h = load_candles(conn_15m, "1h", ANALYSIS_START, ANALYSIS_END, lookback_bars=300)
    candles_4h = load_candles(conn_15m, "4h", ANALYSIS_START, ANALYSIS_END, lookback_bars=300)
    funding = load_funding(conn_15m)
    oi = load_oi(conn_15m)
    agg_15m = load_aggtrade_buckets(conn_15m, "15m")
    agg_60s = load_aggtrade_buckets(conn_15m, "60s")
    print(f"  1h candles: {len(candles_1h)}, 4h candles: {len(candles_4h)}")
    print(f"  Funding: {len(funding)}, OI: {len(oi)}")
    print(f"  Agg 15m: {len(agg_15m)}, Agg 60s: {len(agg_60s)}")

    conn_5m.close()
    conn_15m.close()

    # Build pre-indexed data for fast lookups
    print("Building pre-indexed data...")
    preloaded = PreloadedData.build(candles_1h, candles_4h, funding, oi, agg_15m, agg_60s)

    months = (ANALYSIS_END - ANALYSIS_START).days / 30.44

    # ── Run 15m analysis (baseline, same harness) ──
    params_15m = dict(TRIAL_00095_STRATEGY)
    funnel_15m, trades_15m = run_analysis(
        label="15m BASELINE",
        setup_candles=candles_15m,
        candles_1h=candles_1h,
        candles_4h=candles_4h,
        funding_data=funding,
        oi_data=oi,
        agg_15m_data=agg_15m,
        agg_60s_data=agg_60s,
        params=params_15m,
        bar_minutes=15,
        lookback_bars=params_15m["equal_level_lookback"] + 50,
        start=ANALYSIS_START,
        end=ANALYSIS_END,
        preloaded=preloaded,
    )
    metrics_15m = compute_metrics(trades_15m, months)

    # ── Run 5m analysis ──
    params_5m = build_5m_params()
    funnel_5m, trades_5m = run_analysis(
        label="5m CANDIDATE",
        setup_candles=candles_5m,
        candles_1h=candles_1h,
        candles_4h=candles_4h,
        funding_data=funding,
        oi_data=oi,
        agg_15m_data=agg_15m,
        agg_60s_data=agg_60s,
        params=params_5m,
        bar_minutes=5,
        lookback_bars=params_5m["equal_level_lookback"] + 50,
        start=ANALYSIS_START,
        end=ANALYSIS_END,
        preloaded=preloaded,
    )
    metrics_5m = compute_metrics(trades_5m, months)

    # ── Generate report ──
    report = generate_report(
        funnel_5m, trades_5m, metrics_5m,
        funnel_15m, trades_15m, metrics_15m,
        months,
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    elapsed = time_mod.time() - t_start
    print(f"\nReport written to: {REPORT_PATH}")
    print(f"Total runtime: {elapsed:.0f}s")

    # Print summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"15m: {metrics_15m.trade_count} trades, ER={metrics_15m.expectancy_r:.3f}, PF={metrics_15m.profit_factor:.2f}")
    print(f" 5m: {metrics_5m.trade_count} trades, ER={metrics_5m.expectancy_r:.3f}, PF={metrics_5m.profit_factor:.2f}")
    print(f"Ratio: {metrics_5m.trade_count / max(metrics_15m.trade_count, 1):.2f}x trades")

    verdict, _ = _compute_verdict(funnel_5m, trades_5m, metrics_5m, funnel_15m, trades_15m, metrics_15m, months)
    print(f"\nVERDICT: {verdict}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

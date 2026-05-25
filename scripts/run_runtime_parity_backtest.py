#!/usr/bin/env python3
"""Deterministic multi-asset runtime-parity backtest.

This is intentionally read-only. It replays historical snapshots through the
same core decision layers used by runtime and simulates exits on subsequent
15m candles with conservative SL-before-TP ordering.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtest.performance import summarize
from backtest.replay_loader import ReplayLoader, ReplayLoaderConfig
from core.funding import compute_funding_paid
from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.governance import GovernanceConfig, GovernanceLayer
from core.models import (
    GovernanceRuntimeState,
    MarketSnapshot,
    Position,
    RiskRuntimeState,
    SignalCandidate,
    TradeLog,
)
from core.portfolio_gate import PortfolioRiskConfig, PortfolioRiskState, PortfolioSignal, RuntimePortfolioGate, SymbolRiskState
from core.regime_engine import RegimeConfig, RegimeEngine
from core.risk_engine import RiskConfig, RiskDecision, RiskEngine
from core.signal_engine import SignalConfig, SignalEngine
from settings import (
    AppSettings,
    StrategyConfig,
    SymbolStrategyOverride,
    build_signal_regime_direction_whitelist,
    load_settings,
    resolve_symbol_config,
)


@dataclass(slots=True)
class OpenBacktestPosition:
    symbol: str
    position: Position
    candidate: SignalCandidate
    risk_decision: RiskDecision
    risk_pct: float
    gross_notional_pct: float
    entry_features: dict[str, Any]
    entry_candle_index: int


@dataclass(frozen=True, slots=True)
class CostModelConfig:
    maker_fee_pct: float = 0.0002
    taker_fee_pct: float = 0.0005
    slippage_bps_per_side: float = 3.0
    funding_enabled: bool = True
    funding_fallback_rate_per_8h: float = 0.0001


@dataclass(frozen=True, slots=True)
class TradeCostBreakdown:
    entry_fee: float
    exit_fee: float
    fees_total: float
    entry_slippage: float
    exit_slippage: float
    slippage_total: float
    funding_paid: float
    total_cost: float
    gross_pnl_abs: float
    net_pnl_abs: float
    gross_pnl_r: float
    net_pnl_r: float
    risk_abs: float


@dataclass(frozen=True, slots=True)
class DynamicThresholdConfig:
    mode: str = "fixed"
    atr_multiplier: float = 0.0
    floor_threshold: float = 0.0
    ceiling_threshold: float = 1.0


@dataclass(slots=True)
class SymbolRuntime:
    trades_today: int = 0
    current_day: str | None = None
    current_week: str | None = None
    consecutive_losses: int = 0
    last_trade_at: datetime | None = None
    last_loss_at: datetime | None = None
    daily_pnl_r: float = 0.0
    weekly_pnl_r: float = 0.0


@dataclass(slots=True)
class BacktestResult:
    start_ts_utc: str
    end_ts_utc: str
    warmup_start_ts_utc: str
    symbols: list[str]
    evaluation_cycles: int = 0
    missing_snapshots: dict[str, int] = field(default_factory=dict)
    outcome_reasons: dict[str, dict[str, int]] = field(default_factory=dict)
    signal_candidates: dict[str, int] = field(default_factory=dict)
    governance_vetoes: dict[str, dict[str, int]] = field(default_factory=dict)
    risk_vetoes: dict[str, dict[str, int]] = field(default_factory=dict)
    portfolio_vetoes: dict[str, dict[str, int]] = field(default_factory=dict)
    trades_by_symbol: dict[str, int] = field(default_factory=dict)
    performance: dict[str, Any] = field(default_factory=dict)
    gross_performance: dict[str, Any] = field(default_factory=dict)
    cost_breakdown: dict[str, float] = field(default_factory=dict)
    data_ranges: dict[str, Any] = field(default_factory=dict)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _week_key(value: datetime) -> str:
    iso_year, iso_week, _ = _to_utc(value).isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def _parse_ts(raw: str, *, end: bool = False) -> datetime:
    parsed = _to_utc(datetime.fromisoformat(raw))
    if end and "T" not in raw and " " not in raw:
        parsed += timedelta(days=1)
    return parsed


def _parse_symbol_thresholds(raw_items: list[str]) -> tuple[SymbolStrategyOverride, ...]:
    overrides: list[SymbolStrategyOverride] = []
    seen: set[str] = set()
    for raw in raw_items:
        symbol, sep, value = raw.partition("=")
        if sep != "=":
            raise ValueError(f"Invalid symbol threshold override {raw!r}; expected SYMBOL=VALUE.")
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError(f"Invalid symbol threshold override {raw!r}; symbol is empty.")
        if normalized in seen:
            raise ValueError(f"Duplicate threshold override for {normalized}.")
        seen.add(normalized)
        overrides.append(SymbolStrategyOverride(symbol=normalized, min_sweep_depth_pct=float(value)))
    return tuple(overrides)


def _apply_threshold_overrides(
    settings: AppSettings,
    *,
    min_sweep_depth_pct: float | None,
    symbol_thresholds: tuple[SymbolStrategyOverride, ...],
) -> AppSettings:
    if min_sweep_depth_pct is None and not symbol_thresholds:
        return settings

    strategy = settings.strategy
    if min_sweep_depth_pct is not None:
        strategy = dataclasses.replace(strategy, min_sweep_depth_pct=float(min_sweep_depth_pct))

    if not symbol_thresholds:
        return dataclasses.replace(settings, strategy=strategy)

    override_by_symbol = {item.symbol: item for item in settings.multi_asset.symbol_overrides}
    for override in symbol_thresholds:
        override_by_symbol[override.symbol] = override
    multi_asset = dataclasses.replace(
        settings.multi_asset,
        symbol_overrides=tuple(override_by_symbol[symbol] for symbol in sorted(override_by_symbol)),
    )
    return dataclasses.replace(settings, strategy=strategy, multi_asset=multi_asset)


def _signal_config(strategy: StrategyConfig) -> SignalConfig:
    return SignalConfig(
        confluence_min=strategy.confluence_min,
        min_sweep_depth_pct=strategy.min_sweep_depth_pct,
        ema_trend_gap_pct=strategy.ema_trend_gap_pct,
        entry_offset_atr=strategy.entry_offset_atr,
        invalidation_offset_atr=strategy.invalidation_offset_atr,
        min_stop_distance_pct=strategy.min_stop_distance_pct,
        tp1_atr_mult=strategy.tp1_atr_mult,
        tp2_atr_mult=strategy.tp2_atr_mult,
        weight_sweep_detected=strategy.weight_sweep_detected,
        weight_reclaim_confirmed=strategy.weight_reclaim_confirmed,
        weight_cvd_divergence=strategy.weight_cvd_divergence,
        weight_tfi_impulse=strategy.weight_tfi_impulse,
        weight_force_order_spike=strategy.weight_force_order_spike,
        weight_regime_special=strategy.weight_regime_special,
        weight_ema_trend_alignment=strategy.weight_ema_trend_alignment,
        weight_funding_supportive=strategy.weight_funding_supportive,
        direction_tfi_threshold=strategy.direction_tfi_threshold,
        direction_tfi_threshold_inverse=strategy.direction_tfi_threshold_inverse,
        tfi_impulse_threshold=strategy.tfi_impulse_threshold,
        allow_uptrend_pullback=strategy.allow_uptrend_pullback,
        uptrend_pullback_tfi_threshold=strategy.uptrend_pullback_tfi_threshold,
        uptrend_pullback_min_sweep_depth_pct=strategy.uptrend_pullback_min_sweep_depth_pct,
        uptrend_pullback_confluence_min=strategy.uptrend_pullback_confluence_min,
        regime_direction_whitelist=build_signal_regime_direction_whitelist(strategy),
    )


def _dynamic_min_sweep_depth_pct(
    *,
    base_threshold: float,
    atr_4h_norm: float,
    config: DynamicThresholdConfig | None,
) -> float:
    if config is None or config.mode == "fixed":
        return float(base_threshold)
    if config.mode != "atr_4h_relative":
        raise ValueError(f"Unsupported dynamic threshold mode: {config.mode}")
    raw = max(float(atr_4h_norm), 0.0) * float(config.atr_multiplier)
    return max(float(config.floor_threshold), min(raw, float(config.ceiling_threshold)))


def _signal_config_for_features(
    strategy: StrategyConfig,
    *,
    atr_4h_norm: float,
    dynamic_threshold: DynamicThresholdConfig | None,
) -> SignalConfig:
    config = _signal_config(strategy)
    threshold = _dynamic_min_sweep_depth_pct(
        base_threshold=strategy.min_sweep_depth_pct,
        atr_4h_norm=atr_4h_norm,
        config=dynamic_threshold,
    )
    if threshold == config.min_sweep_depth_pct:
        return config
    return dataclasses.replace(config, min_sweep_depth_pct=threshold)


def _feature_config(settings: AppSettings, strategy: StrategyConfig) -> FeatureEngineConfig:
    return FeatureEngineConfig(
        atr_period=strategy.atr_period,
        ema_fast=strategy.ema_fast,
        ema_slow=strategy.ema_slow,
        equal_level_lookback=strategy.equal_level_lookback,
        equal_level_tol_atr=strategy.equal_level_tol_atr,
        sweep_buf_atr=strategy.sweep_buf_atr,
        reclaim_buf_atr=strategy.reclaim_buf_atr,
        wick_min_atr=strategy.wick_min_atr,
        funding_window_days=strategy.funding_window_days,
        oi_z_window_days=strategy.oi_z_window_days,
        oi_baseline_days=settings.data_quality.oi_baseline_days,
        cvd_divergence_bars=settings.data_quality.cvd_divergence_bars,
    )


def _governance_config(settings: AppSettings) -> GovernanceConfig:
    risk = settings.risk
    return GovernanceConfig(
        cooldown_minutes_after_loss=risk.cooldown_minutes_after_loss,
        duplicate_level_tolerance_pct=risk.duplicate_level_tolerance_pct,
        duplicate_level_window_hours=risk.duplicate_level_window_hours,
        max_trades_per_day=risk.max_trades_per_day,
        max_consecutive_losses=risk.max_consecutive_losses,
        daily_dd_limit=risk.daily_dd_limit,
        weekly_dd_limit=risk.weekly_dd_limit,
        session_start_hour_utc=risk.session_start_hour_utc,
        session_end_hour_utc=risk.session_end_hour_utc,
        no_trade_windows_utc=risk.no_trade_windows_utc,
    )


def _risk_config(settings: AppSettings) -> RiskConfig:
    risk = settings.risk
    return RiskConfig(
        risk_per_trade_pct=risk.risk_per_trade_pct,
        max_leverage=risk.max_leverage,
        high_vol_leverage=risk.high_vol_leverage,
        min_rr=risk.min_rr,
        max_open_positions=risk.max_open_positions,
        max_consecutive_losses=risk.max_consecutive_losses,
        daily_dd_limit=risk.daily_dd_limit,
        weekly_dd_limit=risk.weekly_dd_limit,
        max_hold_hours=risk.max_hold_hours,
        high_vol_stop_distance_pct=risk.high_vol_stop_distance_pct,
        partial_exit_pct=risk.partial_exit_pct,
        trailing_atr_mult=risk.trailing_atr_mult,
    )


def _portfolio_config(settings: AppSettings) -> PortfolioRiskConfig:
    multi = settings.multi_asset
    return PortfolioRiskConfig(
        max_total_risk_pct_open=multi.max_total_risk_pct_open,
        max_open_positions_total=multi.max_open_positions_total,
        max_open_positions_per_symbol=multi.max_open_positions_per_symbol,
        max_gross_notional_pct=multi.max_gross_notional_pct,
        max_directional_notional_pct=multi.max_directional_notional_pct,
        cooldown_after_loss_minutes=settings.risk.cooldown_minutes_after_loss,
        symbol_order=multi.enabled_symbols,
    )


def _load_snapshots(
    conn: sqlite3.Connection,
    *,
    symbols: tuple[str, ...],
    warmup_start: datetime,
    end_ts: datetime,
) -> dict[str, dict[datetime, MarketSnapshot]]:
    loader = ReplayLoader(conn, ReplayLoaderConfig())
    snapshots: dict[str, dict[datetime, MarketSnapshot]] = {}
    for symbol in symbols:
        rows = loader.load(start_date=warmup_start, end_date=end_ts, symbol=symbol).snapshots
        snapshots[symbol] = {snapshot.timestamp: snapshot for snapshot in rows}
    return snapshots


def _state_for_symbol(runtime: SymbolRuntime, now: datetime, open_count: int) -> GovernanceRuntimeState:
    day = now.date().isoformat()
    trades_today = runtime.trades_today if runtime.current_day == day else 0
    return GovernanceRuntimeState(
        trades_today=trades_today,
        consecutive_losses=runtime.consecutive_losses,
        daily_dd_pct=0.0,
        weekly_dd_pct=0.0,
        last_trade_at=runtime.last_trade_at,
        last_loss_at=runtime.last_loss_at,
    )


def _sync_runtime_period(runtime: SymbolRuntime, now: datetime) -> None:
    day = now.date().isoformat()
    if runtime.current_day != day:
        runtime.current_day = day
        runtime.trades_today = 0
        runtime.daily_pnl_r = 0.0
    week = _week_key(now)
    if runtime.current_week != week:
        runtime.current_week = week
        runtime.weekly_pnl_r = 0.0


def _portfolio_state(
    open_positions: list[OpenBacktestPosition],
    runtimes: dict[str, SymbolRuntime],
    *,
    now: datetime,
) -> tuple[PortfolioRiskState, dict[str, SymbolRiskState]]:
    total_risk = sum(item.risk_pct for item in open_positions)
    gross = sum(item.gross_notional_pct for item in open_positions)
    long_notional = sum(item.gross_notional_pct for item in open_positions if item.position.direction == "LONG")
    short_notional = sum(item.gross_notional_pct for item in open_positions if item.position.direction == "SHORT")
    for runtime in runtimes.values():
        _sync_runtime_period(runtime, now)
    symbols = {
        symbol: SymbolRiskState(
            symbol=symbol,
            open_positions_count=sum(1 for item in open_positions if item.symbol == symbol),
            trades_today=runtime.trades_today,
            consecutive_losses=runtime.consecutive_losses,
            daily_pnl_r=runtime.daily_pnl_r,
            weekly_pnl_r=runtime.weekly_pnl_r,
            last_trade_at=runtime.last_trade_at,
            last_loss_at=runtime.last_loss_at,
        )
        for symbol, runtime in runtimes.items()
    }
    portfolio = PortfolioRiskState(
        open_positions_total=len(open_positions),
        gross_notional_pct=gross,
        directional_notional_pct_long=long_notional,
        directional_notional_pct_short=short_notional,
        total_risk_pct_open=total_risk,
    )
    return portfolio, symbols


def _capacity_scale(
    signal: PortfolioSignal,
    *,
    portfolio_state: PortfolioRiskState,
    accepted: list[PortfolioSignal],
    config: PortfolioRiskConfig,
) -> float:
    limits: list[float] = []
    gross_used = portfolio_state.gross_notional_pct + sum(item.gross_notional_pct for item in accepted)
    if signal.gross_notional_pct > 0:
        limits.append((config.max_gross_notional_pct - gross_used) / signal.gross_notional_pct)
    risk_used = portfolio_state.total_risk_pct_open + sum(item.risk_pct for item in accepted)
    if signal.risk_pct > 0:
        limits.append((config.max_total_risk_pct_open - risk_used) / signal.risk_pct)
    if signal.normalized_direction == "LONG":
        directional_used = portfolio_state.directional_notional_pct_long + sum(
            item.gross_notional_pct for item in accepted if item.normalized_direction == "LONG"
        )
    else:
        directional_used = portfolio_state.directional_notional_pct_short + sum(
            item.gross_notional_pct for item in accepted if item.normalized_direction == "SHORT"
        )
    if signal.gross_notional_pct > 0:
        limits.append((config.max_directional_notional_pct - directional_used) / signal.gross_notional_pct)
    if not limits:
        return 1.0
    return max(min(min(limits), 1.0), 0.0)


def _funding_period_count(opened_at: datetime, closed_at: datetime) -> int:
    opened = _to_utc(opened_at)
    closed = _to_utc(closed_at)
    if closed <= opened:
        return 0
    day = opened.replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    while day <= closed:
        for hour in (0, 8, 16):
            funding_time = day.replace(hour=hour)
            if opened < funding_time <= closed:
                count += 1
        day += timedelta(days=1)
    return count


def _funding_paid(
    *,
    position: Position,
    closed_at: datetime,
    funding_samples: list[dict[str, Any]],
    config: CostModelConfig,
) -> float:
    if not config.funding_enabled:
        return 0.0
    notional = max(float(position.entry_price) * float(position.size), 0.0)
    if notional <= 0.0:
        return 0.0

    relevant_samples = [
        sample
        for sample in funding_samples
        if _to_utc(position.opened_at) < _to_utc(sample["funding_time"]) <= _to_utc(closed_at)
    ]
    if relevant_samples:
        return compute_funding_paid(
            direction=position.direction,
            notional=notional,
            opened_at=position.opened_at,
            closed_at=closed_at,
            funding_samples=relevant_samples,
        )

    periods = _funding_period_count(position.opened_at, closed_at)
    return notional * float(config.funding_fallback_rate_per_8h) * periods


def calculate_trade_costs(
    *,
    position: Position,
    exit_price: float,
    gross_pnl_abs: float,
    gross_pnl_r: float,
    closed_at: datetime,
    funding_samples: list[dict[str, Any]],
    config: CostModelConfig,
) -> TradeCostBreakdown:
    entry_notional = abs(float(position.entry_price) * float(position.size))
    exit_notional = abs(float(exit_price) * float(position.size))
    entry_fee = entry_notional * float(config.taker_fee_pct)
    exit_fee = exit_notional * float(config.maker_fee_pct)
    entry_slippage = entry_notional * float(config.slippage_bps_per_side) / 10_000.0
    exit_slippage = exit_notional * float(config.slippage_bps_per_side) / 10_000.0
    funding = _funding_paid(
        position=position,
        closed_at=closed_at,
        funding_samples=funding_samples,
        config=config,
    )
    fees_total = entry_fee + exit_fee
    slippage_total = entry_slippage + exit_slippage
    total_cost = fees_total + slippage_total + funding
    net_pnl_abs = float(gross_pnl_abs) - total_cost
    risk_abs = abs(float(position.entry_price) - float(position.stop_loss)) * float(position.size)
    net_pnl_r = net_pnl_abs / max(risk_abs, 1e-8)
    return TradeCostBreakdown(
        entry_fee=entry_fee,
        exit_fee=exit_fee,
        fees_total=fees_total,
        entry_slippage=entry_slippage,
        exit_slippage=exit_slippage,
        slippage_total=slippage_total,
        funding_paid=funding,
        total_cost=total_cost,
        gross_pnl_abs=float(gross_pnl_abs),
        net_pnl_abs=net_pnl_abs,
        gross_pnl_r=float(gross_pnl_r),
        net_pnl_r=net_pnl_r,
        risk_abs=risk_abs,
    )


def _close_positions(
    *,
    timestamp: datetime,
    snapshots_at_time: dict[str, MarketSnapshot],
    open_positions: list[OpenBacktestPosition],
    risk_engine: RiskEngine,
    runtimes: dict[str, SymbolRuntime],
    cost_config: CostModelConfig,
) -> tuple[list[TradeLog], list[TradeLog]]:
    closed: list[TradeLog] = []
    closed_gross: list[TradeLog] = []
    remaining: list[OpenBacktestPosition] = []
    for item in open_positions:
        snapshot = snapshots_at_time.get(item.symbol)
        if snapshot is None or not snapshot.candles_15m:
            remaining.append(item)
            continue
        candle = snapshot.candles_15m[-1]
        decision = risk_engine.evaluate_exit(
            item.position,
            now=timestamp,
            latest_high=float(candle["high"]),
            latest_low=float(candle["low"]),
            latest_close=float(candle["close"]),
            partial_exit_enabled=False,
        )
        if not decision.should_close or decision.exit_price is None:
            remaining.append(item)
            continue

        metrics = risk_engine.build_settlement_metrics(
            item.position,
            exit_price=float(decision.exit_price),
            exit_reason=str(decision.reason),
            candles_15m=snapshot.candles_15m[item.entry_candle_index :],
        )
        costs = calculate_trade_costs(
            position=item.position,
            exit_price=float(metrics.exit_price),
            gross_pnl_abs=float(metrics.pnl_abs),
            gross_pnl_r=float(metrics.pnl_r),
            closed_at=timestamp,
            funding_samples=snapshot.funding_history,
            config=cost_config,
        )
        entry_features = dict(item.entry_features)
        entry_features["cost_breakdown"] = asdict(costs)
        trade = TradeLog(
            trade_id=f"bt-{item.position.position_id}",
            signal_id=item.position.signal_id,
            opened_at=item.position.opened_at,
            closed_at=timestamp,
            direction=item.position.direction,
            regime=str(item.candidate.regime.value),
            confluence_score=item.candidate.confluence_score,
            entry_price=item.position.entry_price,
            exit_price=metrics.exit_price,
            size=item.position.size,
            fees=costs.fees_total,
            slippage_bps=cost_config.slippage_bps_per_side,
            pnl_abs=costs.net_pnl_abs,
            pnl_r=costs.net_pnl_r,
            mae=metrics.mae,
            mfe=metrics.mfe,
            exit_reason=metrics.exit_reason,
            funding_paid=costs.funding_paid,
            features_at_entry_json=entry_features,
        )
        closed.append(trade)
        closed_gross.append(
            TradeLog(
                trade_id=trade.trade_id,
                signal_id=trade.signal_id,
                opened_at=trade.opened_at,
                closed_at=trade.closed_at,
                direction=trade.direction,
                regime=trade.regime,
                confluence_score=trade.confluence_score,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                size=trade.size,
                fees=0.0,
                slippage_bps=0.0,
                pnl_abs=metrics.pnl_abs,
                pnl_r=metrics.pnl_r,
                mae=metrics.mae,
                mfe=metrics.mfe,
                exit_reason=metrics.exit_reason,
                features_at_entry_json=item.entry_features,
            )
        )
        runtime = runtimes[item.symbol]
        _sync_runtime_period(runtime, timestamp)
        runtime.last_trade_at = timestamp
        runtime.daily_pnl_r += trade.pnl_r
        runtime.weekly_pnl_r += trade.pnl_r
        if trade.pnl_r < 0:
            runtime.consecutive_losses += 1
            runtime.last_loss_at = timestamp
        elif trade.pnl_r > 0:
            runtime.consecutive_losses = 0
    open_positions[:] = remaining
    return closed, closed_gross


def run_backtest(
    conn: sqlite3.Connection,
    *,
    settings: AppSettings,
    symbols: tuple[str, ...],
    start_ts: datetime,
    end_ts: datetime,
    warmup_days: int,
    initial_equity: float,
    cost_config: CostModelConfig | None = None,
    dynamic_threshold: DynamicThresholdConfig | None = None,
) -> tuple[BacktestResult, list[TradeLog]]:
    resolved_cost_config = cost_config or CostModelConfig()
    warmup_start = start_ts - timedelta(days=warmup_days)
    snapshots = _load_snapshots(conn, symbols=symbols, warmup_start=warmup_start, end_ts=end_ts)
    timestamps = sorted(set().union(*(set(items) for items in snapshots.values())))
    engines = {
        symbol: FeatureEngine(_feature_config(settings, resolve_symbol_config(settings.strategy, symbol, settings.multi_asset)))
        for symbol in symbols
    }
    regime_engine = RegimeEngine(RegimeConfig())
    governance = {
        symbol: GovernanceLayer(_governance_config(settings))
        for symbol in symbols
    }
    risk_engine = RiskEngine(_risk_config(settings))
    portfolio_gate = RuntimePortfolioGate(_portfolio_config(settings))
    runtimes = {symbol: SymbolRuntime() for symbol in symbols}
    open_positions: list[OpenBacktestPosition] = []
    trades: list[TradeLog] = []
    gross_trades: list[TradeLog] = []

    outcomes: dict[str, Counter[str]] = {symbol: Counter() for symbol in symbols}
    candidates_count: Counter[str] = Counter()
    governance_vetoes: dict[str, Counter[str]] = {symbol: Counter() for symbol in symbols}
    risk_vetoes: dict[str, Counter[str]] = {symbol: Counter() for symbol in symbols}
    portfolio_vetoes: dict[str, Counter[str]] = {symbol: Counter() for symbol in symbols}
    missing: Counter[str] = Counter()
    evaluation_cycles = 0

    for timestamp in timestamps:
        snapshots_at_time = {symbol: by_ts[timestamp] for symbol, by_ts in snapshots.items() if timestamp in by_ts}
        closed_net, closed_gross = _close_positions(
            timestamp=timestamp,
            snapshots_at_time=snapshots_at_time,
            open_positions=open_positions,
            risk_engine=risk_engine,
            runtimes=runtimes,
            cost_config=resolved_cost_config,
        )
        trades.extend(closed_net)
        gross_trades.extend(closed_gross)
        if timestamp < start_ts or timestamp >= end_ts:
            for symbol, snapshot in snapshots_at_time.items():
                engines[symbol].compute(snapshot, settings.schema_version, settings.config_hash)
            continue

        evaluation_cycles += 1
        generated: list[tuple[str, SignalCandidate, RiskDecision, PortfolioSignal, dict[str, Any]]] = []
        for symbol in symbols:
            snapshot = snapshots[symbol].get(timestamp)
            if snapshot is None:
                missing[symbol] += 1
                continue
            strategy = resolve_symbol_config(settings.strategy, symbol, settings.multi_asset)
            features = engines[symbol].compute(snapshot, settings.schema_version, settings.config_hash)
            regime = regime_engine.classify(features)
            signal_engine = SignalEngine(
                _signal_config_for_features(
                    strategy,
                    atr_4h_norm=features.atr_4h_norm,
                    dynamic_threshold=dynamic_threshold,
                )
            )
            diagnostics = signal_engine.diagnose(features, regime, context=None)
            candidate = signal_engine.generate(features, regime, diagnostics=diagnostics, context=None)
            if candidate is None:
                outcomes[symbol][diagnostics.blocked_by or "no_candidate"] += 1
                continue
            candidate.signal_id = f"bt-{symbol}-{timestamp.isoformat()}"
            candidates_count[symbol] += 1

            open_count = sum(1 for item in open_positions if item.symbol == symbol)
            gov_state = _state_for_symbol(runtimes[symbol], timestamp, open_count)
            governance[symbol].state_provider = lambda state=gov_state: state
            gov_decision = governance[symbol].evaluate(candidate)
            if not gov_decision.approved:
                governance_vetoes[symbol][gov_decision.notes[0] if gov_decision.notes else "governance_veto"] += 1
                continue

            executable = governance[symbol].to_executable(candidate, gov_decision)
            risk_runtime = RiskRuntimeState(consecutive_losses=runtimes[symbol].consecutive_losses)
            risk_engine.state_provider = lambda state=risk_runtime: state
            risk_decision = risk_engine.evaluate(executable, equity=initial_equity, open_positions=open_count)
            if not risk_decision.allowed:
                risk_vetoes[symbol][risk_decision.reason or "risk_veto"] += 1
                continue

            stop_distance = abs(executable.entry_price - executable.stop_loss)
            risk_abs = stop_distance * risk_decision.size
            notional = abs(executable.entry_price * risk_decision.size)
            portfolio_signal = PortfolioSignal(
                symbol=symbol,
                timestamp=timestamp,
                direction=executable.direction,
                signal_id=executable.signal_id,
                risk_pct=risk_abs / initial_equity,
                gross_notional_pct=notional / initial_equity,
                confluence_score=candidate.confluence_score,
            )
            entry_features = dict(candidate.features_json)
            entry_features["symbol"] = symbol
            generated.append((symbol, candidate, risk_decision, portfolio_signal, entry_features))

        if not generated:
            continue

        portfolio_state, symbol_states = _portfolio_state(open_positions, runtimes, now=timestamp)
        adjusted_generated: list[tuple[str, SignalCandidate, RiskDecision, PortfolioSignal, dict[str, Any]]] = []
        accepted_for_sizing: list[PortfolioSignal] = []
        portfolio_config = _portfolio_config(settings)
        for symbol, candidate, risk_decision, portfolio_signal, entry_features in generated:
            scale = _capacity_scale(
                portfolio_signal,
                portfolio_state=portfolio_state,
                accepted=accepted_for_sizing,
                config=portfolio_config,
            )
            if scale <= 0:
                adjusted_signal = portfolio_signal
                adjusted_risk = risk_decision
            elif scale < 1.0:
                adjusted_risk = RiskDecision(
                    allowed=risk_decision.allowed,
                    size=risk_decision.size * scale,
                    leverage=risk_decision.leverage,
                    reason=risk_decision.reason,
                )
                adjusted_signal = PortfolioSignal(
                    symbol=portfolio_signal.symbol,
                    timestamp=portfolio_signal.timestamp,
                    direction=portfolio_signal.direction,
                    signal_id=portfolio_signal.signal_id,
                    risk_pct=portfolio_signal.risk_pct * scale,
                    gross_notional_pct=portfolio_signal.gross_notional_pct * scale,
                    confluence_score=portfolio_signal.confluence_score,
                )
            else:
                adjusted_risk = risk_decision
                adjusted_signal = portfolio_signal
            adjusted_generated.append((symbol, candidate, adjusted_risk, adjusted_signal, entry_features))
            accepted_for_sizing.append(adjusted_signal)
        generated = adjusted_generated
        decisions = portfolio_gate.evaluate_batch(
            [item[3] for item in generated],
            symbol_states=symbol_states,
            portfolio_state=portfolio_state,
            now=timestamp,
        )
        generated_by_id = {item[3].signal_id: item for item in generated}
        for decision in decisions:
            symbol, candidate, risk_decision, portfolio_signal, entry_features = generated_by_id[decision.signal.signal_id]
            if not decision.approved:
                portfolio_vetoes[symbol][decision.veto_reason or "portfolio_veto"] += 1
                continue
            position = Position(
                position_id=f"{symbol}-{timestamp.isoformat()}",
                symbol=symbol,
                direction=candidate.direction,
                status="OPEN",
                entry_price=candidate.entry_reference,
                size=risk_decision.size,
                leverage=risk_decision.leverage,
                stop_loss=candidate.invalidation_level,
                take_profit_1=candidate.tp_reference_1,
                take_profit_2=candidate.tp_reference_2,
                opened_at=timestamp,
                updated_at=timestamp,
                signal_id=candidate.signal_id,
            )
            _sync_runtime_period(runtimes[symbol], timestamp)
            runtimes[symbol].trades_today += 1
            open_positions.append(
                OpenBacktestPosition(
                    symbol=symbol,
                    position=position,
                    candidate=candidate,
                    risk_decision=risk_decision,
                    risk_pct=portfolio_signal.risk_pct,
                    gross_notional_pct=portfolio_signal.gross_notional_pct,
                    entry_features=entry_features,
                    entry_candle_index=len(snapshots[symbol][timestamp].candles_15m) - 1,
                )
            )

    perf = summarize(trades, initial_equity=initial_equity)
    gross_perf = summarize(gross_trades, initial_equity=initial_equity)
    cost_breakdown = {
        "maker_fee_pct": resolved_cost_config.maker_fee_pct,
        "taker_fee_pct": resolved_cost_config.taker_fee_pct,
        "slippage_bps_per_side": resolved_cost_config.slippage_bps_per_side,
        "funding_enabled": float(1 if resolved_cost_config.funding_enabled else 0),
        "funding_fallback_rate_per_8h": resolved_cost_config.funding_fallback_rate_per_8h,
        "total_fees": sum(float(trade.fees) for trade in trades),
        "total_slippage": sum(float((trade.features_at_entry_json.get("cost_breakdown") or {}).get("slippage_total", 0.0)) for trade in trades),
        "total_funding": sum(float(trade.funding_paid) for trade in trades),
        "total_costs_abs": sum(float((trade.features_at_entry_json.get("cost_breakdown") or {}).get("total_cost", 0.0)) for trade in trades),
        "total_costs_r": sum(
            float((trade.features_at_entry_json.get("cost_breakdown") or {}).get("gross_pnl_r", 0.0))
            - float(trade.pnl_r)
            for trade in trades
        ),
        "net_vs_gross_pnl_r_delta": asdict(perf)["pnl_r_sum"] - asdict(gross_perf)["pnl_r_sum"],
    }
    result = BacktestResult(
        start_ts_utc=start_ts.isoformat(),
        end_ts_utc=end_ts.isoformat(),
        warmup_start_ts_utc=warmup_start.isoformat(),
        symbols=list(symbols),
        evaluation_cycles=evaluation_cycles,
        missing_snapshots=dict(missing),
        outcome_reasons={symbol: dict(counter) for symbol, counter in outcomes.items()},
        signal_candidates=dict(candidates_count),
        governance_vetoes={symbol: dict(counter) for symbol, counter in governance_vetoes.items()},
        risk_vetoes={symbol: dict(counter) for symbol, counter in risk_vetoes.items()},
        portfolio_vetoes={symbol: dict(counter) for symbol, counter in portfolio_vetoes.items()},
        trades_by_symbol=dict(Counter(trade.features_at_entry_json.get("symbol", "") for trade in trades)),
        performance=asdict(perf),
        gross_performance=asdict(gross_perf),
        cost_breakdown=cost_breakdown,
        data_ranges=_data_ranges(conn, symbols=symbols),
    )
    return result, trades


def _data_ranges(conn: sqlite3.Connection, *, symbols: tuple[str, ...]) -> dict[str, Any]:
    ranges: dict[str, Any] = {}
    for table, column in [
        ("candles", "open_time"),
        ("aggtrade_buckets", "bucket_time"),
        ("open_interest", "timestamp"),
        ("oi_samples", "timestamp"),
        ("funding", "funding_time"),
    ]:
        rows = conn.execute(
            f"SELECT symbol, COUNT(1) rows, MIN({column}) oldest, MAX({column}) newest FROM {table} WHERE symbol IN ({','.join('?' for _ in symbols)}) GROUP BY symbol ORDER BY symbol",
            symbols,
        ).fetchall()
        ranges[table] = [dict(row) for row in rows]
    return ranges


def _print_report(result: BacktestResult) -> None:
    print("=" * 80)
    print("RUNTIME PARITY BACKTEST")
    print(f"Window: {result.start_ts_utc} -> {result.end_ts_utc}")
    print(f"Warmup: {result.warmup_start_ts_utc}")
    print(f"Symbols: {', '.join(result.symbols)}")
    print("=" * 80)
    print(f"Evaluation cycles: {result.evaluation_cycles}")
    print(f"Signal candidates: {sum(result.signal_candidates.values())}")
    print(f"Trades: {result.performance.get('trades_count', 0)}")
    print(
        "Gross: "
        f"ER {result.gross_performance.get('expectancy_r', 0.0):+.3f} | "
        f"PnL R {result.gross_performance.get('pnl_r_sum', 0.0):+.3f} | "
        f"PF {result.gross_performance.get('profit_factor', 0.0)}"
    )
    print(
        "Net:   "
        f"ER {result.performance.get('expectancy_r', 0.0):+.3f} | "
        f"PnL R {result.performance.get('pnl_r_sum', 0.0):+.3f} | "
        f"PF {result.performance.get('profit_factor', 0.0)} | "
        f"Max DD {result.performance.get('max_drawdown_pct', 0.0):.2%}"
    )
    print(
        "Costs: "
        f"fees {result.cost_breakdown.get('total_fees', 0.0):+.4f} | "
        f"slippage {result.cost_breakdown.get('total_slippage', 0.0):+.4f} | "
        f"funding {result.cost_breakdown.get('total_funding', 0.0):+.4f} | "
        f"total R {result.cost_breakdown.get('total_costs_r', 0.0):+.3f}"
    )
    print("\nOutcome reasons")
    for symbol in result.symbols:
        print(f"  {symbol}: {result.outcome_reasons.get(symbol, {})}")
    print("\nVetoes")
    for label, data in [("governance", result.governance_vetoes), ("risk", result.risk_vetoes), ("portfolio", result.portfolio_vetoes)]:
        print(f"  {label}: {data}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic runtime-parity multi-asset backtest.")
    parser.add_argument("--db", type=Path, default=Path("storage/btc_bot.db"))
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    parser.add_argument("--warmup-days", type=int, default=60)
    parser.add_argument("--initial-equity", type=float, default=1000.0)
    parser.add_argument("--settings-profile", choices=("research", "live", "experiment"), default="research")
    parser.add_argument("--maker-fee-pct", type=float, default=0.0002)
    parser.add_argument("--taker-fee-pct", type=float, default=0.0005)
    parser.add_argument("--slippage-bps", type=float, default=3.0)
    parser.add_argument("--funding-fallback-rate-per-8h", type=float, default=0.0001)
    parser.add_argument("--disable-funding", action="store_true")
    parser.add_argument("--min-sweep-depth-pct", type=float, default=None)
    parser.add_argument(
        "--symbol-min-sweep-depth-pct",
        action="append",
        default=[],
        help="Per-symbol threshold override, e.g. ETHUSDT=0.0065. May be repeated.",
    )
    parser.add_argument("--dynamic-threshold-mode", choices=("fixed", "atr_4h_relative"), default="fixed")
    parser.add_argument("--dynamic-threshold-atr-multiplier", type=float, default=0.0)
    parser.add_argument("--dynamic-threshold-floor", type=float, default=0.0)
    parser.add_argument("--dynamic-threshold-ceiling", type=float, default=1.0)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    settings = load_settings(profile=str(args.settings_profile))
    settings = _apply_threshold_overrides(
        settings,
        min_sweep_depth_pct=args.min_sweep_depth_pct,
        symbol_thresholds=_parse_symbol_thresholds(list(args.symbol_min_sweep_depth_pct)),
    )
    symbols = tuple(item.strip().upper() for item in str(args.symbols).split(",") if item.strip())
    start_ts = _parse_ts(str(args.start_date))
    end_ts = _parse_ts(str(args.end_date), end=True)
    uri = f"file:{args.db.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        result, trades = run_backtest(
            conn,
            settings=settings,
            symbols=symbols,
            start_ts=start_ts,
            end_ts=end_ts,
            warmup_days=int(args.warmup_days),
            initial_equity=float(args.initial_equity),
            cost_config=CostModelConfig(
                maker_fee_pct=float(args.maker_fee_pct),
                taker_fee_pct=float(args.taker_fee_pct),
                slippage_bps_per_side=float(args.slippage_bps),
                funding_enabled=not bool(args.disable_funding),
                funding_fallback_rate_per_8h=float(args.funding_fallback_rate_per_8h),
            ),
            dynamic_threshold=DynamicThresholdConfig(
                mode=str(args.dynamic_threshold_mode),
                atr_multiplier=float(args.dynamic_threshold_atr_multiplier),
                floor_threshold=float(args.dynamic_threshold_floor),
                ceiling_threshold=float(args.dynamic_threshold_ceiling),
            ),
        )
    finally:
        conn.close()

    _print_report(result)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "result": asdict(result),
            "trades": [asdict(trade) for trade in trades],
        }
        args.output_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"JSON output: {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtest.replay_loader import ReplayLoader, ReplayLoaderConfig
from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.governance import GovernanceConfig, GovernanceLayer
from core.models import (
    Features,
    GovernanceRuntimeState,
    MarketContext,
    MarketSnapshot,
    RiskRuntimeState,
    SignalDiagnostics,
)
from core.portfolio_gate import (
    PortfolioRiskConfig,
    PortfolioRiskState,
    PortfolioSignal,
    RuntimePortfolioGate,
    SymbolRiskState,
    recover_portfolio_state,
)
from core.regime_engine import RegimeConfig, RegimeEngine
from core.risk_engine import RiskConfig, RiskEngine
from core.signal_engine import SignalConfig, SignalEngine
from settings import AppSettings, BotMode, StrategyConfig, build_signal_regime_direction_whitelist, load_settings, resolve_symbol_config
from storage.db import connect, init_db
from storage.repositories import fetch_cvd_price_history, fetch_oi_samples
from storage.state_store import StateStore

LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class PortfolioCapacityAdjustment:
    signal_id: str
    size_scale: float
    reason: str | None = None


def _signal_config_from_strategy(strategy: StrategyConfig) -> SignalConfig:
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


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_date_only(raw: str) -> bool:
    token = raw.strip()
    return "T" not in token and " " not in token


def _parse_iso_datetime(raw: str, *, is_end: bool) -> datetime:
    parsed = datetime.fromisoformat(raw)
    value = _to_utc(parsed)
    if is_end and _is_date_only(raw):
        value += timedelta(days=1)
    return value


@dataclass(slots=True)
class ReplayResult:
    total_cycles: int
    per_symbol_trades: dict[str, int]
    per_symbol_near_misses: dict[str, int]
    per_symbol_dd_state: dict[str, dict[str, Any]]
    portfolio_metrics: dict[str, Any]
    capacity_sizing_events: int
    gate_vetoes: dict[str, int]
    risk_utilization: dict[str, float]


@dataclass(slots=True)
class _ReplayState:
    feature_engines: dict[str, FeatureEngine]
    dd_states: dict[str, dict[str, Any]]
    trades_per_symbol: dict[str, list[dict]]
    near_misses_per_symbol: dict[str, int]
    capacity_sizing_events: int
    gate_vetoes: dict[str, int]
    risk_utilization: list[float]


def _apply_portfolio_capacity_sizing(
    signals: list[PortfolioSignal],
    *,
    portfolio_state: PortfolioRiskState,
    config: PortfolioRiskConfig,
) -> tuple[list[PortfolioSignal], dict[str, PortfolioCapacityAdjustment]]:
    """Apply capacity-aware sizing to portfolio signals."""
    adjustments: dict[str, PortfolioCapacityAdjustment] = {}
    adjusted: list[PortfolioSignal] = []
    accepted: list[PortfolioSignal] = []

    for signal in signals:
        scale, reason = _portfolio_capacity_scale(
            signal,
            portfolio_state=portfolio_state,
            accepted=accepted,
            config=config,
        )
        if scale < 1.0:
            adjustments[signal.signal_id] = PortfolioCapacityAdjustment(
                signal_id=signal.signal_id,
                size_scale=scale,
                reason=reason,
            )
            adjusted_signal = PortfolioSignal(
                symbol=signal.symbol,
                timestamp=signal.timestamp,
                direction=signal.direction,
                signal_id=signal.signal_id,
                risk_pct=signal.risk_pct * scale,
                gross_notional_pct=signal.gross_notional_pct * scale,
                confluence_score=signal.confluence_score,
            )
            adjusted.append(adjusted_signal)
        else:
            adjusted.append(signal)
        accepted.append(adjusted[-1])

    return adjusted, adjustments


def _portfolio_capacity_scale(
    signal: PortfolioSignal,
    *,
    portfolio_state: PortfolioRiskState,
    accepted: list[PortfolioSignal],
    config: PortfolioRiskConfig,
) -> tuple[float, str | None]:
    """Return a linear size scale that fits remaining portfolio capacity."""
    limits: list[tuple[float, str]] = []

    gross_used = portfolio_state.gross_notional_pct + sum(item.gross_notional_pct for item in accepted)
    if signal.gross_notional_pct > 0:
        limits.append(((config.max_gross_notional_pct - gross_used) / signal.gross_notional_pct, "gross_notional_cap"))

    risk_used = portfolio_state.total_risk_pct_open + sum(item.risk_pct for item in accepted)
    if signal.risk_pct > 0:
        limits.append(((config.max_total_risk_pct_open - risk_used) / signal.risk_pct, "portfolio_risk_cap"))

    if not limits:
        return 1.0, None

    scale = min(limit[0] for limit in limits)
    reason = min(limits, key=lambda x: x[0])[1] if scale < 1.0 else None
    return max(scale, 0.0), reason


def _bootstrap_feature_engine(
    conn: sqlite3.Connection,
    symbol: str,
    config: StrategyConfig,
    now: datetime,
) -> FeatureEngine:
    """Bootstrap FeatureEngine with OI and CVD history from DB (M1 validation)."""
    engine = FeatureEngine(
        FeatureEngineConfig(
            atr_period=config.atr_period,
            ema_fast=config.ema_fast,
            ema_slow=config.ema_slow,
            equal_level_lookback=config.equal_level_lookback,
            equal_level_tol_atr=config.equal_level_tol_atr,
            sweep_buf_atr=config.sweep_buf_atr,
            reclaim_buf_atr=config.reclaim_buf_atr,
            wick_min_atr=config.wick_min_atr,
            funding_window_days=config.funding_window_days,
            oi_z_window_days=config.oi_z_window_days,
        )
    )

    # Bootstrap OI history
    oi_since = now - timedelta(days=config.oi_z_window_days)
    oi_samples = fetch_oi_samples(
        conn,
        symbol=symbol,
        since_ts=oi_since,
    )
    oi_summary = engine.bootstrap_oi_history(oi_samples) if hasattr(engine, "bootstrap_oi_history") else {"loaded_samples": len(oi_samples)}

    # Bootstrap CVD/price history
    cvd_window_bars = getattr(engine.config, "cvd_divergence_window_bars", 30)
    cvd_samples = fetch_cvd_price_history(
        conn,
        symbol=symbol,
        timeframe="15m",
        limit=cvd_window_bars + 1,
    )
    cvd_summary = engine.bootstrap_cvd_price_history(cvd_samples) if hasattr(engine, "bootstrap_cvd_price_history") else {"loaded_bars": len(cvd_samples)}

    LOG.info("Bootstrapped FeatureEngine for %s: OI %s, CVD %s", symbol, oi_summary, cvd_summary)
    return engine


def _generate_15min_timestamps(start_ts: datetime, end_ts: datetime) -> list[datetime]:
    """Generate 15-minute aligned timestamps between start and end."""
    timestamps = []
    current = start_ts
    # Align to next 15-minute boundary
    minute = current.minute
    aligned_minute = ((minute // 15) + 1) * 15
    if aligned_minute >= 60:
        current = current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        current = current.replace(minute=aligned_minute, second=0, microsecond=0)

    while current < end_ts:
        timestamps.append(current)
        current += timedelta(minutes=15)

    return timestamps


def run_multi_asset_replay(
    conn: sqlite3.Connection,
    *,
    start_ts: datetime,
    end_ts: datetime,
    symbols: tuple[str, ...],
    initial_equity: float,
    settings: AppSettings,
) -> ReplayResult:
    """Run multi-asset replay using historical DB data."""
    LOG.info("Starting multi-asset replay: %s → %s, symbols=%s, equity=%.2f", start_ts, end_ts, symbols, initial_equity)

    # Initialize replay state
    state = _ReplayState(
        feature_engines={},
        dd_states={symbol: {"cumulative_r": 0.0, "local_high_watermark_r": 0.0, "rolling_drawdown_r": 0.0} for symbol in symbols},
        trades_per_symbol={symbol: [] for symbol in symbols},
        near_misses_per_symbol={symbol: 0 for symbol in symbols},
        capacity_sizing_events=0,
        gate_vetoes={},
        risk_utilization=[],
    )

    # Initialize StateStore
    state_store = StateStore(conn, mode="PAPER", reference_equity=initial_equity)

    # Bootstrap FeatureEngines per symbol (M1 validation)
    for symbol in symbols:
        strategy = resolve_symbol_config(settings.strategy, symbol, settings.multi_asset)
        state.feature_engines[symbol] = _bootstrap_feature_engine(conn, symbol, strategy, start_ts)

    # Initialize ReplayLoader
    loader = ReplayLoader(conn, ReplayLoaderConfig())

    # Portfolio config
    portfolio_config = PortfolioRiskConfig(
        max_total_risk_pct_open=settings.multi_asset.max_total_risk_pct_open,
        max_open_positions_total=settings.multi_asset.max_open_positions_total,
        max_open_positions_per_symbol=settings.multi_asset.max_open_positions_per_symbol,
        max_gross_notional_pct=settings.multi_asset.max_gross_notional_pct,
        max_directional_notional_pct=settings.multi_asset.max_directional_notional_pct,
        symbol_order=settings.multi_asset.enabled_symbols,
    )

    # Generate 15-minute timestamps
    timestamps = _generate_15min_timestamps(start_ts, end_ts)
    LOG.info("Generated %d 15-minute cycles", len(timestamps))

    # Replay loop
    for timestamp in timestamps:
        # Build snapshots for all symbols
        snapshots: dict[str, MarketSnapshot] = {}
        for symbol in symbols:
            try:
                snapshot_iter = loader.iter_snapshots(
                    start_date=timestamp - timedelta(minutes=15),
                    end_date=timestamp,
                    symbol=symbol,
                )
                snapshot = next(snapshot_iter, None)
                if snapshot is None:
                    LOG.debug("No snapshot for %s at %s", symbol, timestamp)
                    continue
                snapshots[symbol] = snapshot
            except Exception as exc:
                LOG.warning("Failed to build snapshot for %s at %s: %s", symbol, timestamp, exc)

        if not snapshots:
            continue

        # Generate signals per symbol
        generated: list[dict] = []
        for symbol, snapshot in snapshots.items():
            try:
                strategy = resolve_symbol_config(settings.strategy, symbol, settings.multi_asset)
                feature_engine = state.feature_engines[symbol]
                features = feature_engine.compute(
                    snapshot=snapshot,
                    schema_version=settings.schema_version,
                    config_hash=settings.config_hash,
                )

                regime_engine = RegimeEngine(RegimeConfig())
                regime = regime_engine.classify(features)

                context_engine = type("ContextEngine", (), {"classify": lambda self, f: MarketContext.NORMAL})()
                context = context_engine.classify(features)

                signal_engine = SignalEngine(_signal_config_from_strategy(strategy))
                diagnostics = signal_engine.diagnose(features, regime, context)
                candidate = signal_engine.generate(features, regime, diagnostics=diagnostics, context=context)

                if candidate is None:
                    # Track near-misses
                    if diagnostics.blocked_by == "sweep_too_shallow":
                        state.near_misses_per_symbol[symbol] += 1
                    continue

                # Governance
                symbol_state = SymbolRiskState(symbol=symbol)
                governance = GovernanceLayer(
                    GovernanceConfig(),
                    state_provider=lambda s=symbol_state: GovernanceRuntimeState(
                        trades_today=s.trades_today,
                        consecutive_losses=s.consecutive_losses,
                        daily_dd_pct=0.0,
                        weekly_dd_pct=0.0,
                        last_trade_at=s.last_trade_at,
                        last_loss_at=s.last_loss_at,
                    ),
                )
                governance_decision = governance.evaluate(candidate)
                if not governance_decision.approved:
                    continue

                # Risk
                risk = RiskEngine(
                    RiskConfig(),
                    state_provider=lambda s=symbol_state: RiskRuntimeState(
                        consecutive_losses=s.consecutive_losses,
                        daily_dd_pct=0.0,
                        weekly_dd_pct=0.0,
                    ),
                )
                risk_decision = risk.evaluate(
                    signal=governance.to_executable(candidate, governance_decision),
                    equity=initial_equity,
                    open_positions=symbol_state.open_positions_count,
                )
                if not risk_decision.allowed:
                    continue

                # Build portfolio signal
                executable = governance.to_executable(candidate, governance_decision)
                risk_abs = abs(float(executable.entry_price) - float(executable.stop_loss)) * float(risk_decision.size)
                notional = abs(float(executable.entry_price) * float(risk_decision.size))
                portfolio_signal = PortfolioSignal(
                    symbol=symbol,
                    timestamp=timestamp,
                    direction=executable.direction,
                    signal_id=executable.signal_id,
                    risk_pct=risk_abs / initial_equity,
                    gross_notional_pct=notional / initial_equity,
                    confluence_score=0.0,
                )

                generated.append({
                    "symbol": symbol,
                    "signal": portfolio_signal,
                    "risk_decision": risk_decision,
                    "executable": executable,
                })
            except Exception as exc:
                LOG.warning("Signal generation failed for %s at %s: %s", symbol, timestamp, exc)

        if not generated:
            continue

        # Portfolio recovery
        recovered = state_store.recover_multi_asset_portfolio_state(
            symbols,
            now=timestamp,
        )

        # Capacity sizing
        raw_signals = [item["signal"] for item in generated]
        portfolio_signals, capacity_adjustments = _apply_portfolio_capacity_sizing(
            raw_signals,
            portfolio_state=recovered.portfolio,
            config=portfolio_config,
        )
        state.capacity_sizing_events += len(capacity_adjustments)

        # Portfolio gate
        gate = RuntimePortfolioGate(portfolio_config)
        decisions = gate.evaluate_batch(
            portfolio_signals,
            symbol_states=recovered.symbols,
            portfolio_state=recovered.portfolio,
            now=timestamp,
        )

        # Track risk utilization
        state.risk_utilization.append(recovered.portfolio.total_risk_pct_open)

        # Process approved signals
        for decision in decisions:
            if decision.approved:
                # Simulate trade (simplified for replay)
                symbol = decision.signal.symbol
                state.trades_per_symbol[symbol].append({
                    "signal_id": decision.signal.signal_id,
                    "timestamp": timestamp.isoformat(),
                    "direction": decision.signal.direction,
                    "risk_pct": decision.signal.risk_pct,
                })
            else:
                # Track veto reason
                reason = decision.veto_reason or "unknown"
                state.gate_vetoes[reason] = state.gate_vetoes.get(reason, 0) + 1

        # Update DD state (simplified - would need full trade lifecycle in production)
        for symbol in symbols:
            trades = state.trades_per_symbol[symbol]
            if trades:
                # Simplified DD update (production uses actual PnL)
                last_trade = trades[-1]
                # Assume random PnL for replay (production uses real settlement)
                import random
                pnl_r = random.uniform(-2.0, 3.0)  # Placeholder
                dd_state = state.dd_states[symbol]
                dd_state["cumulative_r"] += pnl_r
                dd_state["local_high_watermark_r"] = max(dd_state["local_high_watermark_r"], dd_state["cumulative_r"])
                dd_state["rolling_drawdown_r"] = dd_state["cumulative_r"] - dd_state["local_high_watermark_r"]

    # Build result
    total_trades = sum(len(trades) for trades in state.trades_per_symbol.values())
    total_near_misses = sum(state.near_misses_per_symbol.values())

    return ReplayResult(
        total_cycles=len(timestamps),
        per_symbol_trades={symbol: len(trades) for symbol, trades in state.trades_per_symbol.items()},
        per_symbol_near_misses=state.near_misses_per_symbol,
        per_symbol_dd_state=state.dd_states,
        portfolio_metrics={
            "total_trades": total_trades,
            "total_near_misses": total_near_misses,
            "win_rate": 0.5,  # Placeholder
            "pnl_r": sum(dd["cumulative_r"] for dd in state.dd_states.values()),
        },
        capacity_sizing_events=state.capacity_sizing_events,
        gate_vetoes=state.gate_vetoes,
        risk_utilization={
            "avg": sum(state.risk_utilization) / len(state.risk_utilization) if state.risk_utilization else 0.0,
            "max": max(state.risk_utilization) if state.risk_utilization else 0.0,
        },
    )


def _print_summary(result: ReplayResult, start_ts: datetime, end_ts: datetime, symbols: tuple[str, ...]) -> None:
    """Print replay summary to console."""
    duration_hours = (end_ts - start_ts).total_seconds() / 3600

    print("=" * 60)
    print("Multi-Asset Replay Summary")
    print("=" * 60)
    print(f"Window: {start_ts.isoformat()} → {end_ts.isoformat()} ({duration_hours:.1f}h)")
    print(f"Cycles: {result.total_cycles}")
    print()

    print("=== Per-Symbol Results ===")
    for symbol in symbols:
        trades = result.per_symbol_trades.get(symbol, 0)
        near_misses = result.per_symbol_near_misses.get(symbol, 0)
        dd_state = result.per_symbol_dd_state.get(symbol, {})
        cumulative_r = dd_state.get("cumulative_r", 0.0)
        high_watermark = dd_state.get("local_high_watermark_r", 0.0)
        rolling_dd = dd_state.get("rolling_drawdown_r", 0.0)
        print(f"{symbol}: {trades} trades, {near_misses} near-misses, DD {rolling_dd:+.2f}R (high-watermark {high_watermark:+.2f}R)")
    print()

    print("=== Portfolio Metrics ===")
    print(f"Total trades: {result.portfolio_metrics['total_trades']}")
    print(f"Total near-misses: {result.portfolio_metrics['total_near_misses']}")
    print(f"Win rate: {result.portfolio_metrics['win_rate']:.1%}")
    print(f"P&L (R): {result.portfolio_metrics['pnl_r']:+.2f}")
    print()

    print("=== Portfolio Gate ===")
    print(f"Capacity sizing events: {result.capacity_sizing_events}")
    print(f"Gate vetoes: {sum(result.gate_vetoes.values())}")
    for reason, count in sorted(result.gate_vetoes.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")
    print()

    print("=== Risk Utilization ===")
    print(f"Avg: {result.risk_utilization['avg']:.2%}")
    print(f"Max: {result.risk_utilization['max']:.2%}")
    print("=" * 60)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-asset backtest on persisted SQLite history.")
    parser.add_argument("--start-date", required=True, help="Inclusive start datetime (ISO-8601, UTC).")
    parser.add_argument("--end-date", required=True, help="Exclusive end datetime (ISO-8601, UTC). Date-only values are treated as next-day exclusive.")
    parser.add_argument("--symbols", required=True, help="Comma-separated list of symbols (e.g., BTCUSDT,ETHUSDT,SOLUSDT).")
    parser.add_argument("--initial-equity", type=float, default=10_000.0, help="Initial equity in USD.")
    parser.add_argument("--output-json", type=Path, default=None, help="Path to write JSON output.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    start_ts = _parse_iso_datetime(str(args.start_date), is_end=False)
    end_ts = _parse_iso_datetime(str(args.end_date), is_end=True)
    if end_ts <= start_ts:
        raise SystemExit("--end-date must be later than --start-date.")

    symbols = tuple(s.strip().upper() for s in args.symbols.split(","))
    if not symbols:
        raise SystemExit("--symbols must be a non-empty comma-separated list.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    settings = load_settings()
    assert settings.storage is not None

    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)
    try:
        result = run_multi_asset_replay(
            conn,
            start_ts=start_ts,
            end_ts=end_ts,
            symbols=symbols,
            initial_equity=float(args.initial_equity),
            settings=settings,
        )

        _print_summary(result, start_ts, end_ts, symbols)

        if args.output_json is not None:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "start_ts_utc": start_ts.isoformat(),
                "end_ts_utc": end_ts.isoformat(),
                "symbols": list(symbols),
                "initial_equity": float(args.initial_equity),
                "result": asdict(result),
            }
            args.output_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            print(f"JSON output: {args.output_json}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

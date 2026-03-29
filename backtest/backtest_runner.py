from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from backtest.fill_model import FillModel, FillModelConfig, SimpleFillModel
from backtest.performance import PerformanceReport, summarize
from backtest.replay_loader import ReplayLoader, ReplayLoaderConfig
from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.governance import GovernanceConfig, GovernanceLayer
from core.models import (
    ExecutableSignal,
    GovernanceRuntimeState,
    Position,
    RiskRuntimeState,
    SignalCandidate,
    TradeLog,
)
from core.regime_engine import RegimeConfig, RegimeEngine
from core.risk_engine import RiskConfig, RiskEngine
from core.signal_engine import SignalConfig, SignalEngine
from settings import AppSettings, load_settings


@dataclass(slots=True)
class BacktestConfig:
    start_date: datetime | date | str
    end_date: datetime | date | str
    initial_equity: float = 10_000.0
    symbol: str = "BTCUSDT"
    slippage_bps_limit: float = 1.0
    slippage_bps_market: float = 3.0
    fee_rate_maker: float = 0.0004
    fee_rate_taker: float = 0.0004
    entry_order_type: str = "LIMIT"
    candles_15m_lookback: int = 300
    candles_1h_lookback: int = 300
    candles_4h_lookback: int = 300
    funding_lookback: int = 200


@dataclass(slots=True)
class BacktestResult:
    performance: PerformanceReport
    trades: list[TradeLog]
    equity_curve: list[tuple[datetime, float]]


@dataclass(slots=True)
class _RuntimeState:
    now: datetime
    trades_today: int = 0
    consecutive_losses: int = 0
    daily_dd_pct: float = 0.0
    weekly_dd_pct: float = 0.0
    last_trade_at: datetime | None = None
    last_loss_at: datetime | None = None


@dataclass(slots=True)
class _OpenPositionRecord:
    trade_id: str
    position: Position
    candidate: SignalCandidate
    executable: ExecutableSignal
    entry_fee: float
    entry_slippage_bps: float
    initial_size: float
    initial_stop_loss: float
    atr_15m: float
    total_fees: float = 0.0
    realized_pnl_abs_gross: float = 0.0
    closed_qty: float = 0.0
    exit_notional_sum: float = 0.0
    partial_exit_done: bool = False
    trailing_stop: float | None = None
    highest_high_since_partial: float | None = None
    lowest_low_since_partial: float | None = None
    slippage_samples: list[float] = field(default_factory=list)
    candles_path: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class _ClosedTradeRecord:
    position: Position
    position_id: str
    candidate: SignalCandidate
    executable: ExecutableSignal
    trade: TradeLog


class BacktestRunner:
    """Runs historical replay using the same core decision engines as live runtime.

    Known limitation (tracked issue #2): each run creates a fresh FeatureEngine.
    Early bars can have degraded feature values until internal rolling windows warm up.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        settings: AppSettings | None = None,
        replay_loader: ReplayLoader | None = None,
        fill_model: FillModel | None = None,
    ) -> None:
        self.connection = connection
        if self.connection.row_factory is None:
            self.connection.row_factory = sqlite3.Row
        self.settings = settings or load_settings()
        self._custom_replay_loader = replay_loader
        self._custom_fill_model = fill_model

        self._runtime = _RuntimeState(now=datetime.now(timezone.utc))
        self._signal_counter = 0
        self._position_counter = 0
        self._trade_counter = 0

    def run(self, config: BacktestConfig) -> BacktestResult:
        symbol = config.symbol.upper()
        initial_equity = max(float(config.initial_equity), 1e-8)

        self._signal_counter = 0
        self._position_counter = 0
        self._trade_counter = 0

        replay_loader = self._custom_replay_loader or ReplayLoader(
            self.connection,
            ReplayLoaderConfig(
                candles_15m_lookback=config.candles_15m_lookback,
                candles_1h_lookback=config.candles_1h_lookback,
                candles_4h_lookback=config.candles_4h_lookback,
                funding_lookback=config.funding_lookback,
            ),
        )
        fill_model = self._custom_fill_model or SimpleFillModel(
            FillModelConfig(
                slippage_bps_limit=config.slippage_bps_limit,
                slippage_bps_market=config.slippage_bps_market,
                fee_rate_maker=config.fee_rate_maker,
                fee_rate_taker=config.fee_rate_taker,
            )
        )
        feature_engine, regime_engine, signal_engine, governance, risk_engine = self._build_engines()

        open_positions: list[_OpenPositionRecord] = []
        closed_records: list[_ClosedTradeRecord] = []
        opened_trade_times: list[datetime] = []
        closed_pnl_events: list[tuple[datetime, float]] = []

        equity = initial_equity
        equity_curve: list[tuple[datetime, float]] = []
        last_snapshot_ts: datetime | None = None
        last_close_price: float | None = None

        for snapshot in replay_loader.iter_snapshots(
            start_date=config.start_date,
            end_date=config.end_date,
            symbol=symbol,
        ):
            now = _to_utc(snapshot.timestamp)
            self._runtime = self._compute_runtime_state(
                now=now,
                opened_trade_times=opened_trade_times,
                closed_records=closed_records,
                closed_pnl_events=closed_pnl_events,
                initial_equity=initial_equity,
            )
            last_snapshot_ts = now
            last_close_price = float(snapshot.price)

            equity += self._close_positions_if_needed(
                snapshot=snapshot,
                open_positions=open_positions,
                closed_records=closed_records,
                closed_pnl_events=closed_pnl_events,
                fill_model=fill_model,
                risk_engine=risk_engine,
            )
            self._runtime = self._compute_runtime_state(
                now=now,
                opened_trade_times=opened_trade_times,
                closed_records=closed_records,
                closed_pnl_events=closed_pnl_events,
                initial_equity=initial_equity,
            )

            features = feature_engine.compute(
                snapshot=snapshot,
                schema_version=self.settings.schema_version,
                config_hash=self.settings.config_hash,
            )
            regime = regime_engine.classify(features)
            candidate = signal_engine.generate(features, regime)
            if candidate is not None:
                self._signal_counter += 1
                candidate.signal_id = self._make_signal_id(now, self._signal_counter)
                governance_decision = governance.evaluate(candidate)
                if governance_decision.approved:
                    executable = governance.to_executable(candidate, governance_decision)
                    risk_decision = risk_engine.evaluate(
                        signal=executable,
                        equity=equity,
                        open_positions=len(open_positions),
                    )
                    if risk_decision.allowed:
                        open_positions.append(
                            self._open_position(
                                now=now,
                                candidate=candidate,
                                executable=executable,
                                risk_decision_size=risk_decision.size,
                                risk_decision_leverage=risk_decision.leverage,
                                fill_model=fill_model,
                                entry_order_type=config.entry_order_type,
                            )
                        )
                        opened_trade_times.append(now)

            equity_curve.append((now, equity))

        if open_positions and last_snapshot_ts is not None and last_close_price is not None:
            equity += self._force_close_remaining_positions(
                now=last_snapshot_ts,
                close_price=last_close_price,
                open_positions=open_positions,
                closed_records=closed_records,
                closed_pnl_events=closed_pnl_events,
                fill_model=fill_model,
                risk_engine=risk_engine,
            )
            equity_curve.append((last_snapshot_ts, equity))

        trades = [record.trade for record in closed_records]
        self._persist_closed_trades(closed_records)
        performance = summarize(trades, initial_equity=initial_equity)
        return BacktestResult(
            performance=performance,
            trades=trades,
            equity_curve=equity_curve,
        )

    def _build_engines(self) -> tuple[FeatureEngine, RegimeEngine, SignalEngine, GovernanceLayer, RiskEngine]:
        strategy = self.settings.strategy
        risk = self.settings.risk

        # Fresh FeatureEngine per run ensures no cross-run deque contamination.
        feature_engine = FeatureEngine(
            FeatureEngineConfig(
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
            )
        )
        regime_engine = RegimeEngine(
            RegimeConfig(
                ema_trend_gap_pct=strategy.ema_trend_gap_pct,
                compression_atr_norm_max=strategy.compression_atr_norm_max,
                crowded_funding_extreme_pct=strategy.crowded_funding_extreme_pct,
                crowded_oi_zscore_min=strategy.crowded_oi_zscore_min,
                post_liq_tfi_abs_min=strategy.post_liq_tfi_abs_min,
            )
        )
        signal_engine = SignalEngine(
            SignalConfig(
                confluence_min=strategy.confluence_min,
                min_sweep_depth_pct=strategy.min_sweep_depth_pct,
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
                regime_direction_whitelist={
                    regime: set(allowed_directions)
                    for regime, allowed_directions in strategy.regime_direction_whitelist.items()
                },
            )
        )
        governance = GovernanceLayer(
            GovernanceConfig(
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
            ),
            state_provider=self._governance_state_provider,
        )
        risk_engine = RiskEngine(
            RiskConfig(
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
            ),
            state_provider=self._risk_state_provider,
        )
        return feature_engine, regime_engine, signal_engine, governance, risk_engine

    def _governance_state_provider(self) -> GovernanceRuntimeState:
        return GovernanceRuntimeState(
            trades_today=self._runtime.trades_today,
            consecutive_losses=self._runtime.consecutive_losses,
            daily_dd_pct=self._runtime.daily_dd_pct,
            weekly_dd_pct=self._runtime.weekly_dd_pct,
            last_trade_at=self._runtime.last_trade_at,
            last_loss_at=self._runtime.last_loss_at,
        )

    def _risk_state_provider(self) -> RiskRuntimeState:
        return RiskRuntimeState(
            consecutive_losses=self._runtime.consecutive_losses,
            daily_dd_pct=self._runtime.daily_dd_pct,
            weekly_dd_pct=self._runtime.weekly_dd_pct,
        )

    def _open_position(
        self,
        *,
        now: datetime,
        candidate: SignalCandidate,
        executable: ExecutableSignal,
        risk_decision_size: float,
        risk_decision_leverage: int,
        fill_model: FillModel,
        entry_order_type: str,
    ) -> _OpenPositionRecord:
        self._position_counter += 1
        self._trade_counter += 1

        side = "BUY" if executable.direction == "LONG" else "SELL"
        entry_fill = fill_model.simulate(
            executable.entry_price,
            risk_decision_size,
            order_type=_normalize_order_type(entry_order_type),
            side=side,
        )
        position_id = f"bt-pos-{self._position_counter:08d}"
        trade_id = f"bt-trd-{self._trade_counter:08d}"
        position = Position(
            position_id=position_id,
            symbol=self.settings.strategy.symbol.upper(),
            direction=executable.direction,
            status="OPEN",
            entry_price=entry_fill.filled_price,
            size=float(risk_decision_size),
            leverage=int(risk_decision_leverage),
            stop_loss=executable.stop_loss,
            take_profit_1=executable.take_profit_1,
            take_profit_2=executable.take_profit_2,
            opened_at=now,
            updated_at=now,
            signal_id=executable.signal_id,
        )
        atr_15m = float(candidate.features_json.get("atr_15m", 0.0))
        initial_size = float(risk_decision_size)
        return _OpenPositionRecord(
            trade_id=trade_id,
            position=position,
            candidate=candidate,
            executable=executable,
            entry_fee=entry_fill.fee_paid,
            entry_slippage_bps=entry_fill.slippage_bps,
            initial_size=initial_size,
            initial_stop_loss=executable.stop_loss,
            atr_15m=max(atr_15m, 0.0),
            total_fees=entry_fill.fee_paid,
            slippage_samples=[entry_fill.slippage_bps],
        )

    def _close_positions_if_needed(
        self,
        *,
        snapshot,
        open_positions: list[_OpenPositionRecord],
        closed_records: list[_ClosedTradeRecord],
        closed_pnl_events: list[tuple[datetime, float]],
        fill_model: FillModel,
        risk_engine: RiskEngine,
    ) -> float:
        if not open_positions:
            return 0.0
        if snapshot.candles_15m:
            latest_candle = snapshot.candles_15m[-1]
            latest_high = float(latest_candle["high"])
            latest_low = float(latest_candle["low"])
            latest_close = float(latest_candle["close"])
        else:
            latest_candle = {
                "open_time": snapshot.timestamp - timedelta(minutes=15),
                "open": float(snapshot.price),
                "high": float(snapshot.price),
                "low": float(snapshot.price),
                "close": float(snapshot.price),
                "volume": 0.0,
            }
            latest_high = float(snapshot.price)
            latest_low = float(snapshot.price)
            latest_close = float(snapshot.price)

        remaining: list[_OpenPositionRecord] = []
        equity_delta = 0.0
        for record in open_positions:
            _append_candle(record.candles_path, latest_candle)
            self._update_trailing_stop(
                record=record,
                latest_high=latest_high,
                latest_low=latest_low,
                trailing_atr_mult=risk_engine.config.trailing_atr_mult,
            )
            decision = risk_engine.evaluate_exit(
                record.position,
                now=snapshot.timestamp,
                latest_high=latest_high,
                latest_low=latest_low,
                latest_close=latest_close,
                partial_exit_enabled=True,
                partial_exit_done=record.partial_exit_done,
            )
            if not decision.should_close or decision.exit_price is None or decision.reason is None:
                remaining.append(record)
                continue

            if decision.reason == "TP_PARTIAL":
                partial_pct = decision.partial_pct if decision.partial_pct is not None else risk_engine.config.partial_exit_pct
                partial_qty = max(min(record.position.size * partial_pct, record.position.size), 0.0)
                if partial_qty <= 0.0:
                    remaining.append(record)
                    continue
                close_side = "SELL" if record.position.direction == "LONG" else "BUY"
                exit_fill = fill_model.simulate(
                    decision.exit_price,
                    partial_qty,
                    order_type="MARKET",
                    side=close_side,
                )
                partial_position = replace(record.position, size=partial_qty)
                partial_settlement = risk_engine.build_settlement_metrics(
                    partial_position,
                    exit_price=exit_fill.filled_price,
                    exit_reason=decision.reason,
                    candles_15m=record.candles_path,
                )
                record.realized_pnl_abs_gross += partial_settlement.pnl_abs
                record.total_fees += exit_fill.fee_paid
                record.closed_qty += partial_qty
                record.exit_notional_sum += partial_settlement.exit_price * partial_qty
                record.slippage_samples.append(exit_fill.slippage_bps)

                record.position.size = max(record.position.size - partial_qty, 0.0)
                record.position.status = "PARTIAL"
                record.position.stop_loss = record.position.entry_price
                record.position.updated_at = snapshot.timestamp
                record.partial_exit_done = True
                record.trailing_stop = record.position.stop_loss
                if record.position.direction == "LONG":
                    record.highest_high_since_partial = latest_high
                else:
                    record.lowest_low_since_partial = latest_low

                if record.position.size <= 0.0:
                    continue

                remaining.append(record)
                continue

            close_side = "SELL" if record.position.direction == "LONG" else "BUY"
            exit_fill = fill_model.simulate(
                decision.exit_price,
                record.position.size,
                order_type="MARKET",
                side=close_side,
            )
            closing_position = replace(record.position, size=record.position.size)
            settlement = risk_engine.build_settlement_metrics(
                closing_position,
                exit_price=exit_fill.filled_price,
                exit_reason=decision.reason,
                candles_15m=record.candles_path,
            )
            total_gross_pnl_abs = record.realized_pnl_abs_gross + settlement.pnl_abs
            fees_total = record.total_fees + exit_fill.fee_paid
            pnl_abs_net = total_gross_pnl_abs - fees_total
            total_closed_qty = record.closed_qty + closing_position.size
            total_exit_notional = record.exit_notional_sum + (settlement.exit_price * closing_position.size)
            effective_exit_price = total_exit_notional / max(total_closed_qty, 1e-8)
            final_position_metrics = replace(
                record.position,
                size=record.initial_size,
                stop_loss=record.initial_stop_loss,
            )
            final_metrics = risk_engine.build_settlement_metrics(
                final_position_metrics,
                exit_price=effective_exit_price,
                exit_reason=decision.reason,
                candles_15m=record.candles_path,
            )
            risk_notional = abs(record.position.entry_price - record.initial_stop_loss) * record.initial_size
            pnl_r_net = pnl_abs_net / max(risk_notional, 1e-8)
            slippage_values = record.slippage_samples + [exit_fill.slippage_bps]
            slippage_avg = sum(slippage_values) / max(len(slippage_values), 1)
            trade = TradeLog(
                trade_id=record.trade_id,
                signal_id=record.position.signal_id,
                opened_at=record.position.opened_at,
                closed_at=snapshot.timestamp,
                direction=record.position.direction,
                regime=record.candidate.regime.value,
                confluence_score=record.candidate.confluence_score,
                entry_price=record.position.entry_price,
                exit_price=effective_exit_price,
                size=record.initial_size,
                fees=fees_total,
                slippage_bps=slippage_avg,
                pnl_abs=pnl_abs_net,
                pnl_r=pnl_r_net,
                mae=final_metrics.mae,
                mfe=final_metrics.mfe,
                exit_reason=final_metrics.exit_reason,
                features_at_entry_json=record.candidate.features_json,
            )
            closed_position = replace(
                record.position,
                size=record.initial_size,
                stop_loss=record.initial_stop_loss,
                status="CLOSED",
                updated_at=snapshot.timestamp,
            )
            closed_records.append(
                _ClosedTradeRecord(
                    position=closed_position,
                    position_id=closed_position.position_id,
                    candidate=record.candidate,
                    executable=record.executable,
                    trade=trade,
                )
            )
            closed_pnl_events.append((snapshot.timestamp, pnl_abs_net))
            equity_delta += pnl_abs_net

        open_positions[:] = remaining
        return equity_delta

    @staticmethod
    def _update_trailing_stop(
        *,
        record: _OpenPositionRecord,
        latest_high: float,
        latest_low: float,
        trailing_atr_mult: float,
    ) -> None:
        if not record.partial_exit_done:
            return
        atr_value = max(record.atr_15m, 1e-8)
        trail_distance = max(float(trailing_atr_mult), 0.0) * atr_value
        if record.position.direction == "LONG":
            reference_high = max(record.highest_high_since_partial or latest_high, latest_high)
            record.highest_high_since_partial = reference_high
            candidate_stop = reference_high - trail_distance
            current_stop = record.trailing_stop if record.trailing_stop is not None else record.position.stop_loss
            record.trailing_stop = max(current_stop, candidate_stop)
        else:
            reference_low = min(record.lowest_low_since_partial or latest_low, latest_low)
            record.lowest_low_since_partial = reference_low
            candidate_stop = reference_low + trail_distance
            current_stop = record.trailing_stop if record.trailing_stop is not None else record.position.stop_loss
            record.trailing_stop = min(current_stop, candidate_stop)
        record.position.stop_loss = record.trailing_stop

    def _force_close_remaining_positions(
        self,
        *,
        now: datetime,
        close_price: float,
        open_positions: list[_OpenPositionRecord],
        closed_records: list[_ClosedTradeRecord],
        closed_pnl_events: list[tuple[datetime, float]],
        fill_model: FillModel,
        risk_engine: RiskEngine,
    ) -> float:
        synthetic_snapshot = {
            "open_time": now - timedelta(minutes=15),
            "open": close_price,
            "high": close_price,
            "low": close_price,
            "close": close_price,
            "volume": 0.0,
        }
        equity_delta = 0.0
        for record in list(open_positions):
            _append_candle(record.candles_path, synthetic_snapshot)
            close_side = "SELL" if record.position.direction == "LONG" else "BUY"
            exit_fill = fill_model.simulate(
                close_price,
                record.position.size,
                order_type="MARKET",
                side=close_side,
            )
            closing_position = replace(record.position, size=record.position.size)
            settlement = risk_engine.build_settlement_metrics(
                closing_position,
                exit_price=exit_fill.filled_price,
                exit_reason="END_OF_BACKTEST",
                candles_15m=record.candles_path,
            )
            total_gross_pnl_abs = record.realized_pnl_abs_gross + settlement.pnl_abs
            fees_total = record.total_fees + exit_fill.fee_paid
            pnl_abs_net = total_gross_pnl_abs - fees_total
            total_closed_qty = record.closed_qty + closing_position.size
            total_exit_notional = record.exit_notional_sum + (settlement.exit_price * closing_position.size)
            effective_exit_price = total_exit_notional / max(total_closed_qty, 1e-8)
            final_position_metrics = replace(
                record.position,
                size=record.initial_size,
                stop_loss=record.initial_stop_loss,
            )
            final_metrics = risk_engine.build_settlement_metrics(
                final_position_metrics,
                exit_price=effective_exit_price,
                exit_reason="END_OF_BACKTEST",
                candles_15m=record.candles_path,
            )
            risk_notional = abs(record.position.entry_price - record.initial_stop_loss) * record.initial_size
            pnl_r_net = pnl_abs_net / max(risk_notional, 1e-8)
            slippage_values = record.slippage_samples + [exit_fill.slippage_bps]
            slippage_avg = sum(slippage_values) / max(len(slippage_values), 1)
            trade = TradeLog(
                trade_id=record.trade_id,
                signal_id=record.position.signal_id,
                opened_at=record.position.opened_at,
                closed_at=now,
                direction=record.position.direction,
                regime=record.candidate.regime.value,
                confluence_score=record.candidate.confluence_score,
                entry_price=record.position.entry_price,
                exit_price=effective_exit_price,
                size=record.initial_size,
                fees=fees_total,
                slippage_bps=slippage_avg,
                pnl_abs=pnl_abs_net,
                pnl_r=pnl_r_net,
                mae=final_metrics.mae,
                mfe=final_metrics.mfe,
                exit_reason=final_metrics.exit_reason,
                features_at_entry_json=record.candidate.features_json,
            )
            closed_position = replace(
                record.position,
                size=record.initial_size,
                stop_loss=record.initial_stop_loss,
                status="CLOSED",
                updated_at=now,
            )
            closed_records.append(
                _ClosedTradeRecord(
                    position=closed_position,
                    position_id=closed_position.position_id,
                    candidate=record.candidate,
                    executable=record.executable,
                    trade=trade,
                )
            )
            closed_pnl_events.append((now, pnl_abs_net))
            equity_delta += pnl_abs_net

        open_positions.clear()
        return equity_delta

    def _compute_runtime_state(
        self,
        *,
        now: datetime,
        opened_trade_times: list[datetime],
        closed_records: list[_ClosedTradeRecord],
        closed_pnl_events: list[tuple[datetime, float]],
        initial_equity: float,
    ) -> _RuntimeState:
        trades_today = sum(1 for ts in opened_trade_times if _to_utc(ts).date() == now.date())
        last_trade_at = max(opened_trade_times) if opened_trade_times else None
        losses = [record.trade for record in closed_records if record.trade.pnl_abs < 0 and record.trade.closed_at is not None]
        last_loss_at = max((trade.closed_at for trade in losses if trade.closed_at is not None), default=None)

        day_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        week_start_date = now.date() - timedelta(days=now.weekday())
        week_start = datetime.combine(week_start_date, time.min, tzinfo=timezone.utc)
        week_end = week_start + timedelta(days=7)
        return _RuntimeState(
            now=now,
            trades_today=trades_today,
            consecutive_losses=_consecutive_losses(closed_records, now=now),
            daily_dd_pct=_compute_period_drawdown_pct(
                closed_pnl_events=closed_pnl_events,
                start_ts=day_start,
                end_ts=day_end,
                initial_equity=initial_equity,
            ),
            weekly_dd_pct=_compute_period_drawdown_pct(
                closed_pnl_events=closed_pnl_events,
                start_ts=week_start,
                end_ts=week_end,
                initial_equity=initial_equity,
            ),
            last_trade_at=last_trade_at,
            last_loss_at=last_loss_at,
        )

    def _persist_closed_trades(self, closed_records: list[_ClosedTradeRecord]) -> None:
        if not closed_records:
            return

        for record in closed_records:
            candidate = record.candidate
            executable = record.executable
            trade = record.trade
            if trade.closed_at is None or trade.exit_price is None or trade.exit_reason is None:
                continue

            self.connection.execute(
                """
                INSERT OR REPLACE INTO signal_candidates (
                    signal_id, timestamp, direction, setup_type, confluence_score, regime,
                    reasons_json, features_json, schema_version, config_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.signal_id,
                    candidate.timestamp.isoformat(),
                    candidate.direction,
                    candidate.setup_type,
                    candidate.confluence_score,
                    candidate.regime.value,
                    json.dumps(candidate.reasons),
                    json.dumps(candidate.features_json),
                    self.settings.schema_version,
                    self.settings.config_hash,
                ),
            )
            self.connection.execute(
                """
                INSERT OR REPLACE INTO executable_signals (
                    signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
                    take_profit_2, rr_ratio, governance_notes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    executable.signal_id,
                    executable.timestamp.isoformat(),
                    executable.direction,
                    executable.entry_price,
                    executable.stop_loss,
                    executable.take_profit_1,
                    executable.take_profit_2,
                    executable.rr_ratio,
                    json.dumps(executable.governance_notes),
                ),
            )
            self.connection.execute(
                """
                INSERT OR REPLACE INTO positions (
                    position_id, signal_id, symbol, direction, status, entry_price, size,
                    leverage, stop_loss, take_profit_1, take_profit_2, opened_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.position_id,
                    trade.signal_id,
                    record.position.symbol,
                    record.position.direction,
                    "CLOSED",
                    record.position.entry_price,
                    record.position.size,
                    record.position.leverage,
                    record.position.stop_loss,
                    record.position.take_profit_1,
                    record.position.take_profit_2,
                    trade.opened_at.isoformat(),
                    trade.closed_at.isoformat(),
                ),
            )
            self.connection.execute(
                """
                INSERT OR REPLACE INTO trade_log (
                    trade_id, signal_id, position_id, opened_at, closed_at, direction, regime,
                    confluence_score, entry_price, exit_price, size, fees_total, slippage_bps_avg,
                    pnl_abs, pnl_r, mae, mfe, exit_reason, features_at_entry_json, schema_version, config_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.trade_id,
                    trade.signal_id,
                    record.position_id,
                    trade.opened_at.isoformat(),
                    trade.closed_at.isoformat(),
                    trade.direction,
                    trade.regime,
                    trade.confluence_score,
                    trade.entry_price,
                    trade.exit_price,
                    trade.size,
                    trade.fees,
                    trade.slippage_bps,
                    trade.pnl_abs,
                    trade.pnl_r,
                    trade.mae,
                    trade.mfe,
                    trade.exit_reason,
                    json.dumps(trade.features_at_entry_json),
                    self.settings.schema_version,
                    self.settings.config_hash,
                ),
            )
        self.connection.commit()

    @staticmethod
    def _make_signal_id(ts: datetime, index: int) -> str:
        normalized = _to_utc(ts).strftime("%Y%m%dT%H%M%S")
        return f"bt-sig-{normalized}-{index:06d}"


def _normalize_order_type(raw: str) -> str:
    normalized = raw.upper()
    if normalized not in ("LIMIT", "MARKET"):
        raise ValueError(f"Unsupported entry_order_type={raw!r}; expected LIMIT or MARKET.")
    return normalized


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _append_candle(candles_path: list[dict[str, Any]], candle: dict[str, Any]) -> None:
    open_time = candle.get("open_time")
    if not isinstance(open_time, datetime):
        candles_path.append(dict(candle))
        return
    open_time_utc = _to_utc(open_time)
    if candles_path:
        last = candles_path[-1].get("open_time")
        if isinstance(last, datetime) and _to_utc(last) >= open_time_utc:
            return
    copy = dict(candle)
    copy["open_time"] = open_time_utc
    candles_path.append(copy)


def _consecutive_losses(closed_records: list[_ClosedTradeRecord], *, now: datetime) -> int:
    now_date = _to_utc(now).date()
    losses = 0
    for record in reversed(closed_records):
        closed_at = record.trade.closed_at
        if closed_at is None:
            continue
        if _to_utc(closed_at).date() != now_date:
            break
        pnl_abs = float(record.trade.pnl_abs)
        if pnl_abs < 0:
            losses += 1
            continue
        if pnl_abs > 0:
            break
    return losses


def _compute_period_drawdown_pct(
    *,
    closed_pnl_events: list[tuple[datetime, float]],
    start_ts: datetime,
    end_ts: datetime,
    initial_equity: float,
) -> float:
    start_utc = _to_utc(start_ts)
    end_utc = _to_utc(end_ts)

    closed_before = sum(pnl for ts, pnl in closed_pnl_events if _to_utc(ts) < start_utc)
    starting_equity = max(initial_equity + closed_before, 1e-8)
    peak_equity = starting_equity
    current_equity = starting_equity
    max_drawdown = 0.0

    for ts, pnl in sorted(closed_pnl_events, key=lambda item: _to_utc(item[0])):
        ts_utc = _to_utc(ts)
        if ts_utc < start_utc or ts_utc >= end_utc:
            continue
        current_equity += float(pnl)
        if current_equity > peak_equity:
            peak_equity = current_equity
        drawdown = (peak_equity - current_equity) / max(peak_equity, 1e-8)
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return min(max(max_drawdown, 0.0), 1.0)

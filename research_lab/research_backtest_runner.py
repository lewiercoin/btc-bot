from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backtest.backtest_runner import BacktestConfig, BacktestResult, BacktestRunner
from core.models import Features, RegimeState, SignalCandidate
from core.signal_engine import SignalEngine


@dataclass(slots=True)
class UptrendContinuationConfig:
    allow_uptrend_continuation: bool = False
    uptrend_continuation_reclaim_strength_min: float = 0.5
    uptrend_continuation_participation_min: float = 0.3
    uptrend_continuation_confluence_multiplier: float = 1.2


def build_uptrend_continuation_config(params: dict[str, Any]) -> UptrendContinuationConfig:
    return UptrendContinuationConfig(
        allow_uptrend_continuation=bool(params.get("allow_uptrend_continuation", False)),
        uptrend_continuation_reclaim_strength_min=float(
            params.get("uptrend_continuation_reclaim_strength_min", 0.5)
        ),
        uptrend_continuation_participation_min=float(
            params.get("uptrend_continuation_participation_min", 0.3)
        ),
        uptrend_continuation_confluence_multiplier=float(
            params.get("uptrend_continuation_confluence_multiplier", 1.2)
        ),
    )


class ResearchBacktestRunner(BacktestRunner):
    def __init__(
        self,
        connection,
        *,
        settings=None,
        replay_loader=None,
        fill_model=None,
        uptrend_continuation: UptrendContinuationConfig | None = None,
    ) -> None:
        super().__init__(connection, settings=settings, replay_loader=replay_loader, fill_model=fill_model)
        self.uptrend_continuation = uptrend_continuation or UptrendContinuationConfig()
        self.signals_generated = 0
        self.signals_regime_blocked = 0
        self.signals_governance_rejected = 0
        self.signals_risk_rejected = 0

    def run(self, config: BacktestConfig) -> BacktestResult:
        symbol = config.symbol.upper()
        initial_equity = max(float(config.initial_equity), 1e-8)

        self._signal_counter = 0
        self._position_counter = 0
        self._trade_counter = 0
        self.signals_generated = 0
        self.signals_regime_blocked = 0
        self.signals_governance_rejected = 0
        self.signals_risk_rejected = 0

        replay_loader = self._custom_replay_loader or self._build_default_replay_loader(config)
        fill_model = self._custom_fill_model or self._build_default_fill_model(config)
        feature_engine, regime_engine, signal_engine, governance, risk_engine = self._build_engines()

        open_positions: list[Any] = []
        closed_records: list[Any] = []
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
            now = self._to_utc(snapshot.timestamp)
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
            if candidate is None:
                candidate = self._generate_uptrend_continuation_candidate(
                    snapshot=snapshot,
                    features=features,
                    regime=regime,
                    signal_engine=signal_engine,
                )
                if candidate is None and self._is_regime_blocked(features, regime, signal_engine):
                    self.signals_generated += 1
                    self.signals_regime_blocked += 1
            else:
                self.signals_generated += 1

            if candidate is not None:
                if candidate.setup_type == "uptrend_continuation_long":
                    self.signals_generated += 1
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
                    else:
                        self.signals_risk_rejected += 1
                else:
                    self.signals_governance_rejected += 1

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
        performance = self._summarize_trades(trades, initial_equity=initial_equity)
        return BacktestResult(
            performance=performance,
            trades=trades,
            equity_curve=equity_curve,
        )

    def _build_default_replay_loader(self, config: BacktestConfig):
        from backtest.backtest_runner import ReplayLoader, ReplayLoaderConfig

        return ReplayLoader(
            self.connection,
            ReplayLoaderConfig(
                candles_15m_lookback=config.candles_15m_lookback,
                candles_1h_lookback=config.candles_1h_lookback,
                candles_4h_lookback=config.candles_4h_lookback,
                funding_lookback=config.funding_lookback,
            ),
        )

    def _build_default_fill_model(self, config: BacktestConfig):
        from backtest.backtest_runner import FillModelConfig, SimpleFillModel

        return SimpleFillModel(
            FillModelConfig(
                slippage_bps_limit=config.slippage_bps_limit,
                slippage_bps_market=config.slippage_bps_market,
                fee_rate_maker=config.fee_rate_maker,
                fee_rate_taker=config.fee_rate_taker,
            )
        )

    def _summarize_trades(self, trades: list[Any], *, initial_equity: float):
        from backtest.performance import summarize

        return summarize(trades, initial_equity=initial_equity)

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _is_regime_blocked(self, features: Features, regime: RegimeState, signal_engine: SignalEngine) -> bool:
        if not features.sweep_detected:
            return False
        if not features.reclaim_detected:
            return False
        if features.sweep_level is None:
            return False
        if (
            features.sweep_depth_pct is not None
            and float(features.sweep_depth_pct) < float(signal_engine.config.min_sweep_depth_pct)
        ):
            return False
        direction = signal_engine._infer_direction(features)
        if direction is None:
            return False
        return not signal_engine._is_direction_allowed_for_regime(direction=direction, regime=regime)

    def _generate_uptrend_continuation_candidate(
        self,
        *,
        snapshot: Any,
        features: Features,
        regime: RegimeState,
        signal_engine: SignalEngine,
    ) -> SignalCandidate | None:
        cfg = self.uptrend_continuation
        if not cfg.allow_uptrend_continuation:
            return None
        if regime is not RegimeState.UPTREND:
            return None
        if not features.sweep_detected or not features.reclaim_detected:
            return None
        if features.sweep_level is None or features.sweep_side != "HIGH":
            return None
        if (
            features.sweep_depth_pct is not None
            and float(features.sweep_depth_pct) < float(signal_engine.config.min_sweep_depth_pct)
        ):
            return None
        if float(features.tfi_60s) < float(cfg.uptrend_continuation_participation_min):
            return None

        latest_close = float(snapshot.candles_15m[-1]["close"]) if snapshot.candles_15m else float(snapshot.price)
        atr = max(float(features.atr_15m), 1e-8)
        reclaim_strength = (latest_close - float(features.sweep_level)) / atr
        if reclaim_strength < float(cfg.uptrend_continuation_reclaim_strength_min):
            return None

        confluence_score, reasons = signal_engine._confluence_score(features, regime, "LONG")
        required_confluence = float(signal_engine.config.confluence_min) * float(
            cfg.uptrend_continuation_confluence_multiplier
        )
        if confluence_score < required_confluence:
            return None

        entry, invalidation, tp1, tp2 = signal_engine._build_levels(features, "LONG")
        return SignalCandidate(
            signal_id="research-uptrend-continuation",
            timestamp=features.timestamp,
            direction="LONG",
            setup_type="uptrend_continuation_long",
            entry_reference=entry,
            invalidation_level=invalidation,
            tp_reference_1=tp1,
            tp_reference_2=tp2,
            confluence_score=confluence_score,
            regime=regime,
            reasons=[
                *reasons,
                "uptrend_continuation_acceptance",
                "uptrend_continuation_participation",
            ],
            features_json={
                "atr_15m": features.atr_15m,
                "sweep_depth_pct": features.sweep_depth_pct,
                "sweep_side": features.sweep_side,
                "funding_pct_60d": features.funding_pct_60d,
                "oi_zscore_60d": features.oi_zscore_60d,
                "cvd_15m": features.cvd_15m,
                "tfi_60s": features.tfi_60s,
                "force_order_rate_60s": features.force_order_rate_60s,
                "force_order_spike": features.force_order_spike,
                "uptrend_continuation_reclaim_strength": reclaim_strength,
                "uptrend_continuation_required_confluence": required_confluence,
            },
        )

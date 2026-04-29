from __future__ import annotations

import sqlite3
from typing import Any

from backtest.backtest_runner import BacktestConfig, BacktestResult, BacktestRunner
from settings import AppSettings

from research_lab.research_backtest_runner import ResearchBacktestRunner, build_uptrend_continuation_config
from research_lab.settings_adapter import extract_research_params
from research_lab.types import SignalFunnel


class _SignalCountingProxy:
    def __init__(self, wrapped: Any, runner: "InstrumentedBacktestRunner") -> None:
        self._wrapped = wrapped
        self._runner = runner

    def _is_regime_blocked(self, features: Any, regime: Any) -> bool:
        if not bool(getattr(features, "sweep_detected", False)):
            return False
        if not bool(getattr(features, "reclaim_detected", False)):
            return False
        if getattr(features, "sweep_level", None) is None:
            return False

        sweep_depth_pct = getattr(features, "sweep_depth_pct", None)
        min_depth = getattr(self._wrapped.config, "min_sweep_depth_pct", None)
        if sweep_depth_pct is not None and min_depth is not None and float(sweep_depth_pct) < float(min_depth):
            return False

        infer_direction = getattr(self._wrapped, "_infer_direction", None)
        direction_allowed = getattr(self._wrapped, "_is_direction_allowed_for_regime", None)
        if infer_direction is None or direction_allowed is None:
            return False

        direction = infer_direction(features)
        if direction is None:
            return False
        return not bool(direction_allowed(direction=direction, regime=regime))

    def generate(self, features: Any, regime: Any, *, context: Any | None = None) -> Any:
        if self._is_regime_blocked(features, regime):
            self._runner.signals_regime_blocked += 1
            self._runner.signals_generated += 1
            return None
        candidate = self._wrapped.generate(features, regime, context=context)
        if candidate is not None:
            self._runner.signals_generated += 1
        return candidate

    def __getattr__(self, item: str) -> Any:
        return getattr(self._wrapped, item)


class _GovernanceCountingProxy:
    def __init__(self, wrapped: Any, runner: "InstrumentedBacktestRunner") -> None:
        self._wrapped = wrapped
        self._runner = runner

    def evaluate(self, candidate: Any) -> Any:
        decision = self._wrapped.evaluate(candidate)
        if not bool(getattr(decision, "approved", False)):
            self._runner.signals_governance_rejected += 1
        return decision

    def __getattr__(self, item: str) -> Any:
        return getattr(self._wrapped, item)


class _RiskCountingProxy:
    def __init__(self, wrapped: Any, runner: "InstrumentedBacktestRunner") -> None:
        self._wrapped = wrapped
        self._runner = runner

    def evaluate(self, signal: Any, equity: float, open_positions: int) -> Any:
        decision = self._wrapped.evaluate(signal, equity=equity, open_positions=open_positions)
        if not bool(getattr(decision, "allowed", False)):
            self._runner.signals_risk_rejected += 1
        return decision

    def __getattr__(self, item: str) -> Any:
        return getattr(self._wrapped, item)


class InstrumentedBacktestRunner(BacktestRunner):
    def __init__(self, connection: sqlite3.Connection, **kwargs: Any) -> None:
        super().__init__(connection, **kwargs)
        self.signals_generated = 0
        self.signals_regime_blocked = 0
        self.signals_governance_rejected = 0
        self.signals_risk_rejected = 0

    def _build_engines(self):  # type: ignore[override]
        feature_engine, regime_engine, context_engine, signal_engine, governance, risk_engine = super()._build_engines()
        return (
            feature_engine,
            regime_engine,
            context_engine,
            _SignalCountingProxy(signal_engine, self),
            _GovernanceCountingProxy(governance, self),
            _RiskCountingProxy(risk_engine, self),
        )


def run_backtest_with_funnel(
    connection: sqlite3.Connection,
    *,
    settings: AppSettings,
    candidate_params: dict[str, Any] | None = None,
    backtest_config: BacktestConfig,
) -> tuple[BacktestResult, SignalFunnel]:
    research_params = extract_research_params(candidate_params or {})
    if research_params:
        runner: Any = ResearchBacktestRunner(
            connection,
            settings=settings,
            uptrend_continuation=build_uptrend_continuation_config(research_params),
        )
    else:
        runner = InstrumentedBacktestRunner(connection, settings=settings)
    result = runner.run(backtest_config)
    funnel = SignalFunnel(
        signals_generated=runner.signals_generated,
        signals_regime_blocked=runner.signals_regime_blocked,
        signals_governance_rejected=runner.signals_governance_rejected,
        signals_risk_rejected=runner.signals_risk_rejected,
        signals_executed=len(result.trades),
    )
    return result, funnel

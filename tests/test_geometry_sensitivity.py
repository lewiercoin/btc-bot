from __future__ import annotations

from types import SimpleNamespace

from backtest.backtest_runner import BacktestConfig
from research_lab import geometry_sensitivity
from settings import load_settings


class _FakeRunner:
    def __init__(self, conn, *, settings):  # type: ignore[no-untyped-def]
        self.conn = conn
        self.settings = settings
        self.signals_generated = 4
        self.signals_regime_blocked = 1
        self.signals_governance_rejected = 1
        self.signals_risk_rejected = 1

    def run(self, config):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            performance=SimpleNamespace(
                expectancy_r=0.25,
                profit_factor=1.4,
                max_drawdown_pct=2.0,
                trades_count=2,
                sharpe_ratio=0.8,
                pnl_abs=120.0,
                win_rate=0.5,
            ),
            trades=[object(), object()],
        )


def test_geometry_variant_evaluation_uses_explicit_params(monkeypatch) -> None:
    monkeypatch.setattr(geometry_sensitivity, "_ReadOnlyInstrumentedBacktestRunner", _FakeRunner)
    settings = load_settings(profile="experiment")

    evaluation, result = geometry_sensitivity._evaluate_geometry_variant(
        object(),  # type: ignore[arg-type]
        base_settings=settings,
        variant_name="signal_defaults_geometry",
        variant_params={
            "entry_offset_atr": 0.05,
            "invalidation_offset_atr": 0.75,
            "min_stop_distance_pct": 0.0015,
            "tp1_atr_mult": 2.5,
            "min_rr": 1.6,
        },
        backtest_config=BacktestConfig(start_date="2026-01-01", end_date="2026-02-01"),
        min_trades=0,
    )

    assert evaluation.params == {
        "entry_offset_atr": 0.05,
        "invalidation_offset_atr": 0.75,
        "min_stop_distance_pct": 0.0015,
        "tp1_atr_mult": 2.5,
        "min_rr": 1.6,
    }
    assert evaluation.metrics.expectancy_r == 0.25
    assert evaluation.funnel.signals_executed == 2
    assert evaluation.rejected_reason is None
    assert result is not None


def test_geometry_variant_rejects_invalid_geometry_without_running(monkeypatch) -> None:
    def _raise_if_called(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("runner should not execute invalid variants")

    monkeypatch.setattr(geometry_sensitivity, "_ReadOnlyInstrumentedBacktestRunner", _raise_if_called)
    settings = load_settings(profile="experiment")

    evaluation, result = geometry_sensitivity._evaluate_geometry_variant(
        object(),  # type: ignore[arg-type]
        base_settings=settings,
        variant_name="invalid_tp_order",
        variant_params={"tp1_atr_mult": 4.0},
        backtest_config=BacktestConfig(start_date="2026-01-01", end_date="2026-02-01"),
        min_trades=0,
    )

    assert evaluation.metrics.trades_count == 0
    assert evaluation.rejected_reason == "tp1_atr_mult must be < tp2_atr_mult"
    assert result is None


def test_evaluation_to_dict_includes_extended_metrics() -> None:
    evaluation = geometry_sensitivity._reject_evaluation(
        "trial",
        {
            "entry_offset_atr": 0.01,
            "invalidation_offset_atr": 0.01,
            "min_stop_distance_pct": 0.0015,
            "tp1_atr_mult": 1.9,
            "min_rr": 1.6,
        },
        "blocked",
    )

    payload = geometry_sensitivity._evaluation_to_dict(
        {
            "name": "blocked_variant",
            "description": "Blocked variant.",
            "params": evaluation.params,
        },
        evaluation,
        None,
        1.25,
        slippage_stress_multiplier=2.0,
    )

    assert payload["slippage_stress_multiplier"] == 2.0
    assert payload["extended_metrics"] == {}
    assert payload["per_regime"] == {}

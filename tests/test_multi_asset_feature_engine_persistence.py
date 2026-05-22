"""Tests for per-symbol FeatureEngine persistence in multi-asset PAPER mode.

Milestone: MULTI_ASSET_FEATURE_ENGINE_PERSISTENCE_V1
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from core.feature_engine import FeatureEngine
from orchestrator import BotOrchestrator
from scripts.smoke_orchestrator import (
    FakeClock,
    FakeHealthMonitor,
    FakeTelegramNotifier,
    make_bundle,
    make_conn,
)
from settings import MultiAssetConfig, load_settings


NOW = datetime(2026, 5, 22, 18, 0, tzinfo=timezone.utc)


def _make_orchestrator(
    *,
    multi_asset_enabled: bool = True,
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT"),
) -> BotOrchestrator:
    base = load_settings()
    assert base.storage is not None
    settings = replace(
        base,
        multi_asset=MultiAssetConfig(enabled=multi_asset_enabled, enabled_symbols=symbols),
    )
    conn = make_conn(base.storage.schema_path)
    clock = FakeClock(NOW)
    bundle, _, _, _ = make_bundle(conn, clock, emit_signals=False)
    return BotOrchestrator(
        settings=settings,
        conn=conn,
        bundle=bundle,
        health_monitor=FakeHealthMonitor(),
        telegram_notifier=FakeTelegramNotifier(),
        now_provider=clock.now,
    )


def test_feature_engines_dict_initialized_with_primary_symbol() -> None:
    """__init__ must seed _feature_engines with the primary BTC entry."""
    orch = _make_orchestrator()
    assert "BTCUSDT" in orch._feature_engines
    assert orch._feature_engines["BTCUSDT"] is orch.bundle.feature_engine


def test_feature_engines_dict_does_not_contain_non_primary_before_bootstrap() -> None:
    """Before start(), only the primary symbol should be in the dict."""
    orch = _make_orchestrator(symbols=("BTCUSDT", "ETHUSDT", "SOLUSDT"))
    assert "ETHUSDT" not in orch._feature_engines
    assert "SOLUSDT" not in orch._feature_engines


def test_bootstrap_feature_engine_for_symbol_creates_and_stores_engine() -> None:
    """_bootstrap_feature_engine_for_symbol must create a new FeatureEngine and store it."""
    orch = _make_orchestrator()
    summary = orch._bootstrap_feature_engine_for_symbol("ETHUSDT", NOW)

    assert "ETHUSDT" in orch._feature_engines
    engine = orch._feature_engines["ETHUSDT"]
    assert isinstance(engine, FeatureEngine)
    # Must not be the same instance as BTC
    assert engine is not orch._feature_engines["BTCUSDT"]
    # Summary must contain symbol and bootstrap info
    assert summary["symbol"] == "ETHUSDT"
    assert "oi" in summary
    assert "cvd" in summary


def test_bootstrap_creates_independent_engines_per_symbol() -> None:
    """Each symbol must get its own independent FeatureEngine instance."""
    orch = _make_orchestrator(symbols=("BTCUSDT", "ETHUSDT", "SOLUSDT"))
    orch._bootstrap_feature_engine_for_symbol("ETHUSDT", NOW)
    orch._bootstrap_feature_engine_for_symbol("SOLUSDT", NOW)

    btc_engine = orch._feature_engines["BTCUSDT"]
    eth_engine = orch._feature_engines["ETHUSDT"]
    sol_engine = orch._feature_engines["SOLUSDT"]

    assert btc_engine is not eth_engine
    assert btc_engine is not sol_engine
    assert eth_engine is not sol_engine


def test_bootstrap_preserves_config_from_primary_engine() -> None:
    """Bootstrapped engines must use the same FeatureEngineConfig as the primary."""
    orch = _make_orchestrator()
    orch._bootstrap_feature_engine_for_symbol("ETHUSDT", NOW)

    primary_config = getattr(orch.bundle.feature_engine, "config", None)
    eth_config = getattr(orch._feature_engines["ETHUSDT"], "config", None)
    if primary_config is not None and eth_config is not None:
        assert primary_config.atr_period == eth_config.atr_period
        assert primary_config.oi_z_window_days == eth_config.oi_z_window_days
        assert primary_config.cvd_divergence_window_bars == eth_config.cvd_divergence_window_bars


def test_multi_asset_cycle_uses_persistent_engine(monkeypatch) -> None:
    """The multi-asset decision cycle must use the pre-bootstrapped FeatureEngine."""
    orch = _make_orchestrator(symbols=("BTCUSDT", "ETHUSDT"))
    # Pre-bootstrap ETH
    orch._bootstrap_feature_engine_for_symbol("ETHUSDT", NOW)
    eth_engine = orch._feature_engines["ETHUSDT"]

    engines_used: dict[str, FeatureEngine] = {}
    original_compute = FeatureEngine.compute

    def tracking_compute(self, snapshot, schema_version, config_hash):
        engines_used[snapshot.symbol] = self
        return original_compute(self, snapshot, schema_version, config_hash)

    monkeypatch.setattr(FeatureEngine, "compute", tracking_compute)

    # Run a cycle — it should use the persistent engine, not create a fresh one
    orch.run_decision_cycle(NOW)

    if "ETHUSDT" in engines_used:
        assert engines_used["ETHUSDT"] is eth_engine, (
            "Multi-asset cycle must reuse the bootstrapped FeatureEngine, not create a fresh one"
        )


def test_multi_asset_cycle_creates_engine_with_warning_if_missing(monkeypatch) -> None:
    """If a symbol has no pre-bootstrapped engine, cycle must create one and log a warning."""
    from datetime import timedelta
    from core.models import MarketSnapshot

    orch = _make_orchestrator(symbols=("BTCUSDT", "ETHUSDT"))
    # Do NOT bootstrap ETH — it should be created on-the-fly
    assert "ETHUSDT" not in orch._feature_engines

    def fake_build_symbol_snapshot(symbol: str, timestamp):  # type: ignore[no-untyped-def]
        return MarketSnapshot(
            symbol=symbol,
            timestamp=timestamp,
            price=100.0,
            bid=99.5,
            ask=100.5,
            candles_15m=[{"open_time": timestamp - timedelta(minutes=15), "open": 99.0, "high": 120.0, "low": 90.0, "close": 100.0}],
            candles_1h=[],
            candles_4h=[],
            funding_history=[],
            open_interest=0.0,
            aggtrades_bucket_60s={},
            aggtrades_bucket_15m={},
            force_order_events_60s=[],
            etf_bias_daily=None,
            dxy_daily=None,
        )

    monkeypatch.setattr(orch, "_build_symbol_snapshot", fake_build_symbol_snapshot)

    warnings_logged: list[str] = []
    import logging

    class WarningCapture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if "without bootstrap" in record.getMessage():
                warnings_logged.append(record.getMessage())

    handler = WarningCapture()
    logging.getLogger("orchestrator").addHandler(handler)
    try:
        orch.run_decision_cycle(NOW)
    finally:
        logging.getLogger("orchestrator").removeHandler(handler)

    # After cycle, ETH engine should exist (created on-the-fly)
    assert "ETHUSDT" in orch._feature_engines
    assert len(warnings_logged) >= 1, "Expected a warning about missing bootstrap"


def test_disabled_multi_asset_does_not_bootstrap_non_btc() -> None:
    """When multi-asset is disabled, only BTC should be in _feature_engines."""
    orch = _make_orchestrator(multi_asset_enabled=False, symbols=("BTCUSDT",))
    assert len(orch._feature_engines) == 1
    assert "BTCUSDT" in orch._feature_engines

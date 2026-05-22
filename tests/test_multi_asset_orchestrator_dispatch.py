from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from orchestrator import BotOrchestrator
from scripts.smoke_orchestrator import FakeClock, FakeHealthMonitor, FakeTelegramNotifier, make_bundle, make_conn
from settings import MultiAssetConfig, PaperSimulationConfig, load_settings


NOW = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)


def test_disabled_multi_asset_config_uses_existing_single_symbol_cycle(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    base = load_settings()
    assert base.storage is not None
    settings = replace(base, multi_asset=MultiAssetConfig(enabled=False, enabled_symbols=("BTCUSDT",)))
    conn = make_conn(base.storage.schema_path)
    clock = FakeClock(NOW)
    bundle, _, _, _ = make_bundle(conn, clock, emit_signals=False)
    orchestrator = BotOrchestrator(
        settings=settings,
        conn=conn,
        bundle=bundle,
        health_monitor=FakeHealthMonitor(),
        telegram_notifier=FakeTelegramNotifier(),
        now_provider=clock.now,
    )

    assert orchestrator._multi_asset_paper_enabled() is False


def test_enabled_multi_asset_config_dispatches_to_separate_loop(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    base = load_settings()
    assert base.storage is not None
    settings = replace(
        base,
        multi_asset=MultiAssetConfig(enabled=True, enabled_symbols=("BTCUSDT", "ETHUSDT")),
    )
    conn = make_conn(base.storage.schema_path)
    clock = FakeClock(NOW)
    bundle, signal_engine, _, _ = make_bundle(conn, clock, emit_signals=False)
    calls = {"multi": 0}

    def record_call(self, *, timestamp, cycle_started):  # type: ignore[no-untyped-def]
        calls["multi"] += 1
        assert timestamp == NOW
        assert cycle_started > 0

    monkeypatch.setattr(BotOrchestrator, "_run_multi_asset_paper_decision_cycle", record_call)
    orchestrator = BotOrchestrator(
        settings=settings,
        conn=conn,
        bundle=bundle,
        health_monitor=FakeHealthMonitor(),
        telegram_notifier=FakeTelegramNotifier(),
        now_provider=clock.now,
    )

    orchestrator.run_decision_cycle(NOW)

    assert calls["multi"] == 1
    assert signal_engine.generate_calls == 0


def test_multi_asset_position_monitor_routes_lifecycle_by_position_symbol(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    base = load_settings()
    assert base.storage is not None
    settings = replace(
        base,
        multi_asset=MultiAssetConfig(enabled=True, enabled_symbols=("BTCUSDT", "ETHUSDT", "SOLUSDT")),
    )
    conn = make_conn(base.storage.schema_path)
    clock = FakeClock(NOW)
    bundle, _, _, _ = make_bundle(conn, clock, emit_signals=False)
    orchestrator = BotOrchestrator(
        settings=settings,
        conn=conn,
        bundle=bundle,
        health_monitor=FakeHealthMonitor(),
        telegram_notifier=FakeTelegramNotifier(),
        now_provider=clock.now,
    )
    monkeypatch.setattr(
        orchestrator.state_store,
        "get_open_trade_records",
        lambda: [
            SimpleNamespace(position=SimpleNamespace(symbol="ETHUSDT")),
            SimpleNamespace(position=SimpleNamespace(symbol="SOLUSDT")),
        ],
    )
    routed_symbols: list[str] = []
    lifecycle_symbols: list[str | None] = []

    def fail_btc_snapshot(now):  # type: ignore[no-untyped-def]
        raise AssertionError("multi-asset monitor must not use BTC-only snapshot")

    def build_symbol_snapshot(symbol, timestamp):  # type: ignore[no-untyped-def]
        routed_symbols.append(symbol)
        return SimpleNamespace(symbol=symbol, timestamp=timestamp)

    def process_lifecycle(snapshot, *, symbol=None):  # type: ignore[no-untyped-def]
        lifecycle_symbols.append(symbol)
        assert snapshot.symbol == symbol
        return []

    monkeypatch.setattr(orchestrator, "_build_snapshot", fail_btc_snapshot)
    monkeypatch.setattr(orchestrator, "_build_symbol_snapshot", build_symbol_snapshot)
    monkeypatch.setattr(orchestrator, "_process_trade_lifecycle", process_lifecycle)

    orchestrator._run_position_monitor_cycle(NOW)

    assert routed_symbols == ["ETHUSDT", "SOLUSDT"]
    assert lifecycle_symbols == ["ETHUSDT", "SOLUSDT"]


def test_paper_simulation_account_balance_overrides_reference_equity_for_sizing() -> None:
    base = load_settings()
    assert base.storage is not None
    settings = replace(
        base,
        paper_simulation=PaperSimulationConfig(
            enabled=True,
            starting_balance_usd=1000.0,
            compound_pnl=True,
        ),
    )
    conn = make_conn(base.storage.schema_path)
    clock = FakeClock(NOW)
    bundle, _, _, _ = make_bundle(conn, clock, emit_signals=False)
    orchestrator = BotOrchestrator(
        settings=settings,
        conn=conn,
        bundle=bundle,
        health_monitor=FakeHealthMonitor(),
        telegram_notifier=FakeTelegramNotifier(),
        now_provider=clock.now,
    )

    assert orchestrator._risk_equity(NOW) == 1000.0

    orchestrator.state_store.apply_paper_simulation_pnl(
        pnl_abs=-125.0,
        compound_pnl=True,
        now=NOW,
    )

    assert orchestrator._risk_equity(NOW) == 875.0

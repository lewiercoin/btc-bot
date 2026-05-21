from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from orchestrator import BotOrchestrator
from scripts.smoke_orchestrator import FakeClock, FakeHealthMonitor, FakeTelegramNotifier, make_bundle, make_conn
from settings import MultiAssetConfig, load_settings


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

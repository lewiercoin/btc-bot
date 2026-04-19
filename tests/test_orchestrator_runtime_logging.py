from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.models import MarketSnapshot, RegimeState, SignalDiagnostics
from dashboard.db_reader import read_config_snapshot_from_conn, read_decision_funnel_from_conn
from monitoring.audit_logger import AuditLogger
from monitoring.health import HealthStatus
from orchestrator import BotOrchestrator, EngineBundle
from settings import load_settings
from storage.db import init_db
from storage.repositories import get_runtime_metrics


def make_conn(schema_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn, schema_path)
    return conn


@dataclass
class FakeClock:
    current: datetime

    def now(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.current += timedelta(seconds=float(seconds))


class FakeWebsocketClient:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.started = False
        self.stopped = False
        self.last_message_at: datetime | None = None
        self.config = SimpleNamespace(heartbeat_seconds=30)

    @property
    def is_connected(self) -> bool:
        return self.started and not self.stopped

    def start(self, symbol: str = "BTCUSDT") -> None:
        _ = symbol
        self.started = True
        self.stopped = False
        self.last_message_at = self.clock.now()

    def stop(self) -> None:
        self.stopped = True


class FakeMarketData:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.websocket_client = FakeWebsocketClient(clock)
        self.rest_client = SimpleNamespace(ping=lambda: True)

    def build_snapshot(self, symbol: str, timestamp: datetime) -> MarketSnapshot:
        return MarketSnapshot(
            symbol=symbol,
            timestamp=timestamp,
            price=100.0,
            bid=99.5,
            ask=100.5,
            candles_15m=[
                {
                    "open_time": timestamp - timedelta(minutes=15),
                    "open": 99.0,
                    "high": 101.0,
                    "low": 98.0,
                    "close": 100.0,
                }
            ],
            candles_1h=[
                {
                    "open_time": timestamp.replace(minute=0, second=0, microsecond=0),
                    "open": 98.0,
                    "high": 101.0,
                    "low": 97.0,
                    "close": 100.0,
                }
            ],
            candles_4h=[
                {
                    "open_time": timestamp.replace(hour=(timestamp.hour // 4) * 4, minute=0, second=0, microsecond=0),
                    "open": 96.0,
                    "high": 102.0,
                    "low": 95.0,
                    "close": 100.0,
                }
            ],
            funding_history=[],
            open_interest=0.0,
            aggtrades_bucket_60s={},
            aggtrades_bucket_15m={},
            force_order_events_60s=[],
            etf_bias_daily=None,
            dxy_daily=None,
        )


class FakeFeatureEngine:
    def compute(self, snapshot, schema_version: str, config_hash: str):  # type: ignore[no-untyped-def]
        _ = schema_version
        _ = config_hash
        return {"timestamp": snapshot.timestamp}


class FakeRegimeEngine:
    def classify(self, features):  # type: ignore[no-untyped-def]
        _ = features
        return RegimeState.NORMAL


class FakeSignalEngine:
    def diagnose(self, features, regime):  # type: ignore[no-untyped-def]
        return SignalDiagnostics(
            timestamp=features["timestamp"],
            config_hash="test-config",
            regime=regime,
            blocked_by="no_reclaim",
            sweep_detected=True,
            reclaim_detected=False,
            sweep_side="HIGH",
            sweep_level=100.0,
            sweep_depth_pct=0.001,
            direction_inferred="SHORT",
            direction_allowed=True,
            confluence_preview=None,
            close_vs_reclaim_buffer_atr=-0.25,
            wick_vs_min_atr=0.5,
            sweep_vs_buffer_atr=0.75,
            candidate_reasons_preview=[],
        )

    def generate(self, features, regime, diagnostics=None):  # type: ignore[no-untyped-def]
        _ = features
        _ = regime
        _ = diagnostics
        return None


class UnusedGovernance:
    def evaluate(self, candidate: Any) -> Any:
        raise AssertionError("governance should not be called when no signal is generated")

    def to_executable(self, candidate: Any, decision: Any) -> Any:
        raise AssertionError("governance should not be called when no signal is generated")


class UnusedRiskEngine:
    def evaluate(self, signal: Any, equity: float, open_positions: int) -> Any:
        raise AssertionError("risk engine should not be called when no signal is generated")

    def evaluate_exit(self, position: Any, **kwargs: Any) -> Any:
        raise AssertionError("exit evaluation should not be called without open positions")

    def build_settlement_metrics(self, position: Any, **kwargs: Any) -> Any:
        raise AssertionError("settlement should not be called without open positions")


class UnusedExecutionEngine:
    def execute_signal(self, signal: Any, size: float, leverage: int) -> None:
        raise AssertionError("execution should not be called when no signal is generated")


class FakeHealthMonitor:
    def check(self) -> HealthStatus:
        return HealthStatus(websocket_alive=True, db_writable=True, exchange_reachable=True)


class DegradedHealthMonitor:
    def check(self) -> HealthStatus:
        return HealthStatus(websocket_alive=False, db_writable=True, exchange_reachable=True)


class DummyTelegramNotifier:
    def send_alert(self, alert_type: str, payload: dict[str, object]) -> bool:
        _ = alert_type
        _ = payload
        return True


def make_bundle(conn: sqlite3.Connection, clock: FakeClock) -> EngineBundle:
    return EngineBundle(
        market_data=FakeMarketData(clock),  # type: ignore[arg-type]
        feature_engine=FakeFeatureEngine(),  # type: ignore[arg-type]
        regime_engine=FakeRegimeEngine(),  # type: ignore[arg-type]
        signal_engine=FakeSignalEngine(),  # type: ignore[arg-type]
        governance=UnusedGovernance(),  # type: ignore[arg-type]
        risk_engine=UnusedRiskEngine(),  # type: ignore[arg-type]
        execution_engine=UnusedExecutionEngine(),  # type: ignore[arg-type]
        audit_logger=AuditLogger(conn),
    )


@pytest.fixture
def paper_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BOT_MODE", "PAPER")
    base_settings = load_settings()
    return replace(
        base_settings,
        execution=replace(
            base_settings.execution,
            position_monitor_interval_seconds=5,
            health_check_interval_seconds=5,
            loop_idle_sleep_seconds=1.0,
        ),
    )


def test_start_logs_runtime_loop_schedule(caplog: pytest.LogCaptureFixture, paper_settings) -> None:
    assert paper_settings.storage is not None
    conn = make_conn(paper_settings.storage.schema_path)
    clock = FakeClock(datetime(2026, 4, 15, 12, 33, 5, tzinfo=timezone.utc))
    bundle = make_bundle(conn, clock)

    holder: dict[str, BotOrchestrator] = {}
    stop_at = clock.now() + timedelta(seconds=1)

    def sleep_fn(seconds: float) -> None:
        clock.sleep(seconds)
        if clock.now() >= stop_at:
            holder["orchestrator"].stop("test_stop")

    orchestrator = BotOrchestrator(
        settings=paper_settings,
        conn=conn,
        bundle=bundle,
        health_monitor=FakeHealthMonitor(),  # type: ignore[arg-type]
        telegram_notifier=DummyTelegramNotifier(),  # type: ignore[arg-type]
        now_provider=clock.now,
        sleep_fn=sleep_fn,
    )
    holder["orchestrator"] = orchestrator

    with caplog.at_level(logging.INFO):
        orchestrator.start()

    messages = [record.getMessage() for record in caplog.records if record.name == "orchestrator"]
    assert any("Market data feed thread started for BTCUSDT." in message for message in messages)
    assert any("Runtime loop started | mode=PAPER | symbol=BTCUSDT" in message for message in messages)


def test_decision_cycle_logs_no_signal_outcome(caplog: pytest.LogCaptureFixture, paper_settings) -> None:
    assert paper_settings.storage is not None
    conn = make_conn(paper_settings.storage.schema_path)
    clock = FakeClock(datetime(2026, 4, 15, 12, 14, 59, tzinfo=timezone.utc))
    bundle = make_bundle(conn, clock)

    holder: dict[str, BotOrchestrator] = {}
    stop_at = datetime(2026, 4, 15, 12, 15, 2, tzinfo=timezone.utc)

    def sleep_fn(seconds: float) -> None:
        clock.sleep(seconds)
        if clock.now() >= stop_at:
            holder["orchestrator"].stop("test_stop")

    orchestrator = BotOrchestrator(
        settings=paper_settings,
        conn=conn,
        bundle=bundle,
        health_monitor=FakeHealthMonitor(),  # type: ignore[arg-type]
        telegram_notifier=DummyTelegramNotifier(),  # type: ignore[arg-type]
        now_provider=clock.now,
        sleep_fn=sleep_fn,
    )
    holder["orchestrator"] = orchestrator

    with caplog.at_level(logging.INFO):
        orchestrator.start()

    messages = [record.getMessage() for record in caplog.records if record.name == "orchestrator"]
    assert any("Decision cycle started | timestamp=2026-04-15T12:15:00+00:00" in message for message in messages)
    assert any(
        "Decision diagnostics | timestamp=2026-04-15T12:15:00+00:00 | outcome=no_signal | blocked_by=no_reclaim"
        in message
        for message in messages
    )
    assert any(
        "close_vs_buf_atr=-0.250 | wick_vs_min_atr=0.500 | sweep_vs_buf_atr=0.750" in message
        for message in messages
    )
    assert any(
        "Decision cycle finished | timestamp=2026-04-15T12:15:00+00:00 | outcome=no_signal" in message
        for message in messages
    )


def test_decision_cycle_persists_runtime_metrics(paper_settings) -> None:
    assert paper_settings.storage is not None
    conn = make_conn(paper_settings.storage.schema_path)
    clock = FakeClock(datetime(2026, 4, 15, 12, 14, 59, tzinfo=timezone.utc))
    bundle = make_bundle(conn, clock)

    holder: dict[str, BotOrchestrator] = {}
    stop_at = datetime(2026, 4, 15, 12, 15, 2, tzinfo=timezone.utc)

    def sleep_fn(seconds: float) -> None:
        clock.sleep(seconds)
        if clock.now() >= stop_at:
            holder["orchestrator"].stop("test_stop")

    orchestrator = BotOrchestrator(
        settings=paper_settings,
        conn=conn,
        bundle=bundle,
        health_monitor=FakeHealthMonitor(),  # type: ignore[arg-type]
        telegram_notifier=DummyTelegramNotifier(),  # type: ignore[arg-type]
        now_provider=clock.now,
        sleep_fn=sleep_fn,
    )
    holder["orchestrator"] = orchestrator

    orchestrator.start()

    runtime_metrics = get_runtime_metrics(conn)
    assert runtime_metrics is not None
    assert runtime_metrics["decision_cycle_status"] == "idle"
    assert runtime_metrics["last_decision_outcome"] == "no_signal"
    assert runtime_metrics["last_snapshot_symbol"] == "BTCUSDT"
    assert runtime_metrics["last_decision_cycle_started_at"] == "2026-04-15T12:15:00+00:00"
    assert runtime_metrics["last_decision_cycle_finished_at"] == "2026-04-15T12:15:00+00:00"
    assert runtime_metrics["last_snapshot_built_at"] == "2026-04-15T12:15:00+00:00"
    assert runtime_metrics["last_15m_candle_open_at"] == "2026-04-15T12:00:00+00:00"
    assert runtime_metrics["last_1h_candle_open_at"] == "2026-04-15T12:00:00+00:00"
    assert runtime_metrics["last_4h_candle_open_at"] == "2026-04-15T12:00:00+00:00"
    assert runtime_metrics["last_ws_message_at"] == "2026-04-15T12:14:59+00:00"
    assert runtime_metrics["last_health_check_at"] == "2026-04-15T12:14:59+00:00"
    assert runtime_metrics["last_runtime_warning"] is None
    assert runtime_metrics["config_hash"] == paper_settings.config_hash


def test_health_check_persists_runtime_warning(paper_settings) -> None:
    assert paper_settings.storage is not None
    conn = make_conn(paper_settings.storage.schema_path)
    clock = FakeClock(datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc))
    bundle = make_bundle(conn, clock)
    orchestrator = BotOrchestrator(
        settings=paper_settings,
        conn=conn,
        bundle=bundle,
        health_monitor=DegradedHealthMonitor(),  # type: ignore[arg-type]
        telegram_notifier=DummyTelegramNotifier(),  # type: ignore[arg-type]
        now_provider=clock.now,
        sleep_fn=clock.sleep,
    )
    orchestrator.state_store.ensure_initialized()

    orchestrator._run_health_check(clock.now())

    runtime_metrics = get_runtime_metrics(conn)
    assert runtime_metrics is not None
    assert runtime_metrics["last_health_check_at"] == "2026-04-15T12:00:00+00:00"
    assert runtime_metrics["last_runtime_warning"] == "websocket_alive=false"


def test_start_persists_config_snapshot(paper_settings) -> None:
    assert paper_settings.storage is not None
    conn = make_conn(paper_settings.storage.schema_path)
    clock = FakeClock(datetime(2026, 4, 15, 12, 33, 5, tzinfo=timezone.utc))
    bundle = make_bundle(conn, clock)

    holder: dict[str, BotOrchestrator] = {}
    stop_at = clock.now() + timedelta(seconds=1)

    def sleep_fn(seconds: float) -> None:
        clock.sleep(seconds)
        if clock.now() >= stop_at:
            holder["orchestrator"].stop("test_stop")

    orchestrator = BotOrchestrator(
        settings=paper_settings,
        conn=conn,
        bundle=bundle,
        health_monitor=FakeHealthMonitor(),  # type: ignore[arg-type]
        telegram_notifier=DummyTelegramNotifier(),  # type: ignore[arg-type]
        now_provider=clock.now,
        sleep_fn=sleep_fn,
    )
    holder["orchestrator"] = orchestrator

    orchestrator.start()

    payload = read_config_snapshot_from_conn(conn, config_hash=paper_settings.config_hash)

    assert payload["config_hash"] == paper_settings.config_hash
    assert payload["captured_at"] == "2026-04-15T12:33:05+00:00"
    assert payload["strategy"] is not None
    assert payload["strategy"]["allow_uptrend_pullback"] is False


def test_decision_cycle_records_decision_outcome_counts(paper_settings) -> None:
    assert paper_settings.storage is not None
    conn = make_conn(paper_settings.storage.schema_path)
    clock = FakeClock(datetime(2026, 4, 15, 12, 14, 59, tzinfo=timezone.utc))
    bundle = make_bundle(conn, clock)

    holder: dict[str, BotOrchestrator] = {}
    stop_at = datetime(2026, 4, 15, 12, 15, 2, tzinfo=timezone.utc)

    def sleep_fn(seconds: float) -> None:
        clock.sleep(seconds)
        if clock.now() >= stop_at:
            holder["orchestrator"].stop("test_stop")

    orchestrator = BotOrchestrator(
        settings=paper_settings,
        conn=conn,
        bundle=bundle,
        health_monitor=FakeHealthMonitor(),  # type: ignore[arg-type]
        telegram_notifier=DummyTelegramNotifier(),  # type: ignore[arg-type]
        now_provider=clock.now,
        sleep_fn=sleep_fn,
    )
    holder["orchestrator"] = orchestrator

    orchestrator.start()

    payload = read_decision_funnel_from_conn(
        conn,
        config_hash=paper_settings.config_hash,
        now=stop_at,
    )

    assert payload["windows"]["24h"]["total"] == 1
    assert payload["windows"]["24h"]["by_outcome"] == {"no_signal": 1}
    assert payload["windows"]["24h"]["by_reason"] == {"no_reclaim": 1}

from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.models import ExecutableSignal, MarketSnapshot, RegimeState, SettlementMetrics, SignalCandidate, SignalDiagnostics
from core.risk_engine import ExitDecision, RiskDecision
from execution.execution_engine import ExecutionEngine
from monitoring.audit_logger import AuditLogger
from monitoring.health import HealthStatus
from monitoring.telegram_notifier import TelegramNotifier
from orchestrator import BotOrchestrator, EngineBundle
from settings import load_settings
from storage.db import init_db


def make_conn(schema_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn, schema_path)
    return conn


def reset_runtime_tables(conn: sqlite3.Connection) -> None:
    for table in (
        "executions",
        "trade_log",
        "positions",
        "executable_signals",
        "signal_candidates",
        "daily_metrics",
        "bot_state",
        "alerts_errors",
    ):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


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
    def __init__(self, clock: FakeClock, *, high_price: float = 120.0, low_price: float = 90.0, close_price: float = 100.0) -> None:
        self.clock = clock
        self.high_price = high_price
        self.low_price = low_price
        self.close_price = close_price
        self.websocket_client = FakeWebsocketClient(clock)
        self.rest_client = SimpleNamespace(ping=lambda: True)

    def build_snapshot(self, symbol: str, timestamp: datetime) -> MarketSnapshot:
        return MarketSnapshot(
            symbol=symbol,
            timestamp=timestamp,
            price=self.close_price,
            bid=self.close_price - 0.5,
            ask=self.close_price + 0.5,
            candles_15m=[
                {
                    "open_time": timestamp - timedelta(minutes=15),
                    "open": self.close_price - 1.0,
                    "high": self.high_price,
                    "low": self.low_price,
                    "close": self.close_price,
                }
            ],
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
    def __init__(self, *, emit_signals: bool = True) -> None:
        self.emit_signals = emit_signals
        self.diagnose_calls = 0
        self.generate_calls = 0

    def diagnose(self, features, regime):  # type: ignore[no-untyped-def]
        self.diagnose_calls += 1
        return SignalDiagnostics(
            timestamp=features["timestamp"],
            config_hash="smoke",
            regime=regime,
            blocked_by=None if self.emit_signals else "smoke_blocked",
            sweep_detected=True,
            reclaim_detected=True,
            sweep_side="LOW",
            sweep_level=100.0,
            sweep_depth_pct=0.01,
            direction_inferred="LONG" if self.emit_signals else None,
            direction_allowed=True if self.emit_signals else None,
            confluence_preview=4.0 if self.emit_signals else None,
            candidate_reasons_preview=["smoke"] if self.emit_signals else [],
        )

    def generate(self, features, regime, diagnostics=None):  # type: ignore[no-untyped-def]
        self.generate_calls += 1
        if diagnostics is not None and diagnostics.blocked_by is not None:
            return None
        if not self.emit_signals:
            return None
        ts = features["timestamp"]
        return SignalCandidate(
            signal_id=f"sig-{uuid4().hex[:12]}",
            timestamp=ts,
            direction="LONG",
            setup_type="smoke_orchestrator",
            entry_reference=100.0,
            invalidation_level=95.0,
            tp_reference_1=105.0,
            tp_reference_2=110.0,
            confluence_score=4.0,
            regime=regime,
            reasons=["smoke"],
            features_json={"smoke": True},
        )


@dataclass
class _FakeGovDecision:
    approved: bool
    notes: list[str]


class FakeGovernance:
    def evaluate(self, candidate: SignalCandidate) -> _FakeGovDecision:
        _ = candidate
        return _FakeGovDecision(approved=True, notes=["ok"])

    def to_executable(self, candidate: SignalCandidate, decision: _FakeGovDecision) -> ExecutableSignal:
        _ = decision
        return ExecutableSignal(
            signal_id=candidate.signal_id,
            timestamp=candidate.timestamp,
            direction=candidate.direction,
            entry_price=candidate.entry_reference,
            stop_loss=candidate.invalidation_level,
            take_profit_1=candidate.tp_reference_1,
            take_profit_2=candidate.tp_reference_2,
            rr_ratio=3.0,
            approved_by_governance=True,
            governance_notes=["ok"],
        )


class FakeRiskEngine:
    def evaluate(self, signal: ExecutableSignal, equity: float, open_positions: int) -> RiskDecision:
        _ = signal
        _ = equity
        _ = open_positions
        return RiskDecision(allowed=True, size=0.1, leverage=3, reason=None)

    def evaluate_exit(
        self,
        position,
        *,
        now: datetime,
        latest_high: float,
        latest_low: float,
        latest_close: float,
    ) -> ExitDecision:
        _ = now
        _ = latest_low
        _ = latest_close
        if position.direction == "LONG" and latest_high >= position.take_profit_1:
            return ExitDecision(should_close=True, reason="TP", exit_price=position.take_profit_1)
        return ExitDecision(should_close=False, reason=None, exit_price=None)

    def build_settlement_metrics(
        self,
        position,
        *,
        exit_price: float,
        exit_reason: str,
        candles_15m,
    ) -> SettlementMetrics:
        _ = candles_15m
        pnl_abs = (exit_price - position.entry_price) * position.size
        pnl_r = (exit_price - position.entry_price) / max(abs(position.entry_price - position.stop_loss), 1e-8)
        return SettlementMetrics(
            exit_price=exit_price,
            pnl_abs=pnl_abs,
            pnl_r=pnl_r,
            mae=0.0,
            mfe=max(pnl_abs, 0.0),
            exit_reason=exit_reason,
        )


class FakeExecutionEngine(ExecutionEngine):
    def __init__(self, conn: sqlite3.Connection, clock: FakeClock, *, should_fail: bool = False) -> None:
        self.conn = conn
        self.clock = clock
        self.should_fail = should_fail
        self.execute_calls = 0

    def execute_signal(
        self,
        signal: ExecutableSignal,
        size: float,
        leverage: int,
        *,
        snapshot_price: float | None = None,
    ) -> None:
        self.execute_calls += 1
        if self.should_fail:
            raise RuntimeError("forced_execution_failure")
        if snapshot_price is None:
            raise RuntimeError("snapshot_price_required")
        now = self.clock.now().isoformat()
        position_id = f"pos-{uuid4().hex[:12]}"
        filled_price = float(snapshot_price)
        self.conn.execute(
            """
            INSERT INTO positions (
                position_id, signal_id, symbol, direction, status, entry_price, size,
                leverage, stop_loss, take_profit_1, take_profit_2, opened_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                position_id,
                signal.signal_id,
                "BTCUSDT",
                signal.direction,
                "OPEN",
                filled_price,
                size,
                leverage,
                signal.stop_loss,
                signal.take_profit_1,
                signal.take_profit_2,
                now,
                now,
            ),
        )
        slippage_bps = abs(filled_price - signal.entry_price) / max(abs(signal.entry_price), 1e-8) * 10_000.0
        self.conn.execute(
            """
            INSERT INTO executions (
                execution_id, position_id, order_type, side, requested_price, filled_price,
                qty, fees, slippage_bps, executed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"exe-{uuid4().hex[:12]}",
                position_id,
                "MARKET",
                "BUY" if signal.direction == "LONG" else "SELL",
                signal.entry_price,
                filled_price,
                size,
                0.0,
                slippage_bps,
                now,
            ),
        )
        self.conn.commit()


class FakeHealthMonitor:
    def __init__(self, statuses: list[HealthStatus] | None = None) -> None:
        self.statuses = statuses or [HealthStatus(websocket_alive=True, db_writable=True, exchange_reachable=True)]
        self.calls = 0

    def check(self) -> HealthStatus:
        idx = min(self.calls, len(self.statuses) - 1)
        self.calls += 1
        return self.statuses[idx]


class FakeTelegramNotifier(TelegramNotifier):
    def __init__(self) -> None:
        self.alerts: list[tuple[str, dict]] = []

    def send_alert(self, alert_type: str, payload: dict[str, object]) -> bool:  # type: ignore[override]
        self.alerts.append((alert_type, dict(payload)))
        return True


def seed_open_trade(conn: sqlite3.Connection, settings, opened_at: datetime) -> str:  # type: ignore[no-untyped-def]
    signal_id = f"sig-{uuid4().hex[:12]}"
    position_id = f"pos-{uuid4().hex[:12]}"
    trade_id = f"trd-{uuid4().hex[:12]}"
    ts = opened_at.isoformat()

    conn.execute(
        """
        INSERT INTO signal_candidates (
            signal_id, timestamp, direction, setup_type, confluence_score, regime,
            reasons_json, features_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            ts,
            "LONG",
            "seed_open_trade",
            3.5,
            "normal",
            "[]",
            "{}",
            settings.schema_version,
            settings.config_hash,
        ),
    )
    conn.execute(
        """
        INSERT INTO executable_signals (
            signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1, take_profit_2, rr_ratio, governance_notes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            ts,
            "LONG",
            100.0,
            95.0,
            105.0,
            110.0,
            3.0,
            "[]",
        ),
    )
    conn.execute(
        """
        INSERT INTO positions (
            position_id, signal_id, symbol, direction, status, entry_price, size, leverage,
            stop_loss, take_profit_1, take_profit_2, opened_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            position_id,
            signal_id,
            "BTCUSDT",
            "LONG",
            "OPEN",
            100.0,
            0.1,
            3,
            95.0,
            105.0,
            110.0,
            ts,
            ts,
        ),
    )
    conn.execute(
        """
        INSERT INTO trade_log (
            trade_id, signal_id, position_id, opened_at, closed_at, direction, regime,
            confluence_score, entry_price, exit_price, size, fees_total, slippage_bps_avg,
            pnl_abs, pnl_r, mae, mfe, exit_reason, features_at_entry_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            signal_id,
            position_id,
            ts,
            None,
            "LONG",
            "normal",
            3.5,
            100.0,
            None,
            0.1,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            None,
            "{}",
            settings.schema_version,
            settings.config_hash,
        ),
    )
    conn.commit()
    return trade_id


def seed_closed_loss_trade(conn: sqlite3.Connection, settings, closed_at: datetime, loss_abs: float = -500.0) -> None:  # type: ignore[no-untyped-def]
    signal_id = f"sig-{uuid4().hex[:12]}"
    position_id = f"pos-{uuid4().hex[:12]}"
    trade_id = f"trd-{uuid4().hex[:12]}"
    opened_ts = (closed_at - timedelta(minutes=30)).isoformat()
    closed_ts = closed_at.isoformat()

    conn.execute(
        """
        INSERT INTO signal_candidates (
            signal_id, timestamp, direction, setup_type, confluence_score, regime,
            reasons_json, features_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            opened_ts,
            "LONG",
            "seed_closed_loss",
            3.5,
            "normal",
            "[]",
            "{}",
            settings.schema_version,
            settings.config_hash,
        ),
    )
    conn.execute(
        """
        INSERT INTO executable_signals (
            signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1, take_profit_2, rr_ratio, governance_notes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            opened_ts,
            "LONG",
            100.0,
            95.0,
            105.0,
            110.0,
            3.0,
            "[]",
        ),
    )
    conn.execute(
        """
        INSERT INTO positions (
            position_id, signal_id, symbol, direction, status, entry_price, size, leverage,
            stop_loss, take_profit_1, take_profit_2, opened_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            position_id,
            signal_id,
            "BTCUSDT",
            "LONG",
            "CLOSED",
            100.0,
            1.0,
            3,
            95.0,
            105.0,
            110.0,
            opened_ts,
            closed_ts,
        ),
    )
    conn.execute(
        """
        INSERT INTO trade_log (
            trade_id, signal_id, position_id, opened_at, closed_at, direction, regime,
            confluence_score, entry_price, exit_price, size, fees_total, slippage_bps_avg,
            pnl_abs, pnl_r, mae, mfe, exit_reason, features_at_entry_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            signal_id,
            position_id,
            opened_ts,
            closed_ts,
            "LONG",
            "normal",
            3.5,
            100.0,
            95.0,
            1.0,
            0.0,
            0.0,
            loss_abs,
            -1.0,
            0.0,
            0.0,
            "SL",
            "{}",
            settings.schema_version,
            settings.config_hash,
        ),
    )
    conn.commit()


def make_bundle(conn: sqlite3.Connection, clock: FakeClock, *, emit_signals: bool = True, execution_should_fail: bool = False) -> tuple[EngineBundle, FakeSignalEngine, FakeExecutionEngine, FakeMarketData]:
    signal_engine = FakeSignalEngine(emit_signals=emit_signals)
    execution_engine = FakeExecutionEngine(conn=conn, clock=clock, should_fail=execution_should_fail)
    market_data = FakeMarketData(clock)
    bundle = EngineBundle(
        market_data=market_data,  # type: ignore[arg-type]
        feature_engine=FakeFeatureEngine(),  # type: ignore[arg-type]
        regime_engine=FakeRegimeEngine(),  # type: ignore[arg-type]
        signal_engine=signal_engine,  # type: ignore[arg-type]
        governance=FakeGovernance(),  # type: ignore[arg-type]
        risk_engine=FakeRiskEngine(),  # type: ignore[arg-type]
        execution_engine=execution_engine,
        audit_logger=AuditLogger(conn),
    )
    return bundle, signal_engine, execution_engine, market_data


def run_event_loop_smoke(conn: sqlite3.Connection, settings) -> None:  # type: ignore[no-untyped-def]
    reset_runtime_tables(conn)
    clock = FakeClock(datetime(2026, 3, 26, 0, 14, 50, tzinfo=timezone.utc))
    bundle, signal_engine, execution_engine, market_data = make_bundle(conn, clock, emit_signals=True)
    health = FakeHealthMonitor()
    telegram = FakeTelegramNotifier()

    holder: dict[str, BotOrchestrator] = {}
    stop_at = datetime(2026, 3, 26, 0, 15, 20, tzinfo=timezone.utc)

    def sleep_fn(seconds: float) -> None:
        clock.sleep(seconds)
        if clock.now() >= stop_at:
            holder["orchestrator"].stop("smoke_stop")

    orchestrator = BotOrchestrator(
        settings=settings,
        conn=conn,
        bundle=bundle,
        health_monitor=health,  # type: ignore[arg-type]
        telegram_notifier=telegram,
        now_provider=clock.now,
        sleep_fn=sleep_fn,
    )
    holder["orchestrator"] = orchestrator
    orchestrator.start()

    assert signal_engine.generate_calls >= 1
    assert execution_engine.execute_calls >= 1
    assert market_data.websocket_client.started is True
    assert market_data.websocket_client.stopped is True
    assert any(alert_type == TelegramNotifier.ALERT_ENTRY for alert_type, _ in telegram.alerts)
    print("event loop + 15m trigger smoke: OK")


def run_safe_mode_lifecycle_smoke(conn: sqlite3.Connection, settings) -> None:  # type: ignore[no-untyped-def]
    reset_runtime_tables(conn)
    clock = FakeClock(datetime(2026, 3, 26, 1, 0, 0, tzinfo=timezone.utc))
    bundle, signal_engine, execution_engine, _ = make_bundle(conn, clock, emit_signals=True)
    health = FakeHealthMonitor()
    telegram = FakeTelegramNotifier()

    opened_at = clock.now() - timedelta(minutes=20)
    seed_open_trade(conn, settings, opened_at=opened_at)

    holder: dict[str, BotOrchestrator] = {}
    stop_at = datetime(2026, 3, 26, 1, 0, 25, tzinfo=timezone.utc)

    def sleep_fn(seconds: float) -> None:
        clock.sleep(seconds)
        if clock.now() >= stop_at:
            holder["orchestrator"].stop("smoke_stop")

    orchestrator = BotOrchestrator(
        settings=settings,
        conn=conn,
        bundle=bundle,
        health_monitor=health,  # type: ignore[arg-type]
        telegram_notifier=telegram,
        now_provider=clock.now,
        sleep_fn=sleep_fn,
    )
    holder["orchestrator"] = orchestrator
    orchestrator.state_store.set_safe_mode(True, reason="manual_safe_mode", now=clock.now())
    orchestrator.start()

    closed = conn.execute(
        "SELECT COUNT(*) AS cnt FROM trade_log WHERE closed_at IS NOT NULL"
    ).fetchone()["cnt"]
    assert int(closed) >= 1
    assert execution_engine.execute_calls == 0
    assert signal_engine.generate_calls == 0
    assert any(alert_type == TelegramNotifier.ALERT_EXIT for alert_type, _ in telegram.alerts)
    print("safe mode lifecycle smoke: OK")


def run_kill_switch_smoke(conn: sqlite3.Connection, settings) -> None:  # type: ignore[no-untyped-def]
    reset_runtime_tables(conn)
    clock = FakeClock(datetime(2026, 3, 26, 2, 0, 0, tzinfo=timezone.utc))
    bundle, _, _, _ = make_bundle(conn, clock, emit_signals=False)
    health = FakeHealthMonitor()
    telegram = FakeTelegramNotifier()

    loss_abs = -(BotOrchestrator.REFERENCE_EQUITY * settings.risk.daily_dd_limit + 100.0)
    seed_closed_loss_trade(conn, settings, closed_at=clock.now(), loss_abs=loss_abs)

    holder: dict[str, BotOrchestrator] = {}
    stop_at = datetime(2026, 3, 26, 2, 0, 5, tzinfo=timezone.utc)

    def sleep_fn(seconds: float) -> None:
        clock.sleep(seconds)
        if clock.now() >= stop_at:
            holder["orchestrator"].stop("smoke_stop")

    orchestrator = BotOrchestrator(
        settings=settings,
        conn=conn,
        bundle=bundle,
        health_monitor=health,  # type: ignore[arg-type]
        telegram_notifier=telegram,
        now_provider=clock.now,
        sleep_fn=sleep_fn,
    )
    holder["orchestrator"] = orchestrator
    orchestrator.start()

    state = orchestrator.state_store.load()
    assert state is not None and state.safe_mode is True
    assert any(alert_type == TelegramNotifier.ALERT_KILL_SWITCH for alert_type, _ in telegram.alerts)
    print("kill-switch smoke: OK")


def run_daily_summary_smoke(conn: sqlite3.Connection, settings) -> None:  # type: ignore[no-untyped-def]
    reset_runtime_tables(conn)
    start = datetime(2026, 3, 26, 23, 59, 50, tzinfo=timezone.utc)
    clock = FakeClock(start)
    bundle, _, _, _ = make_bundle(conn, clock, emit_signals=False)
    health = FakeHealthMonitor()
    telegram = FakeTelegramNotifier()

    seed_closed_loss_trade(conn, settings, closed_at=start - timedelta(minutes=10), loss_abs=-50.0)

    holder: dict[str, BotOrchestrator] = {}
    stop_at = datetime(2026, 3, 27, 0, 0, 20, tzinfo=timezone.utc)

    def sleep_fn(seconds: float) -> None:
        clock.sleep(seconds)
        if clock.now() >= stop_at:
            holder["orchestrator"].stop("smoke_stop")

    orchestrator = BotOrchestrator(
        settings=settings,
        conn=conn,
        bundle=bundle,
        health_monitor=health,  # type: ignore[arg-type]
        telegram_notifier=telegram,
        now_provider=clock.now,
        sleep_fn=sleep_fn,
    )
    holder["orchestrator"] = orchestrator
    orchestrator.start()

    assert any(alert_type == TelegramNotifier.ALERT_DAILY_SUMMARY for alert_type, _ in telegram.alerts)
    print("daily summary smoke: OK")


def main() -> None:
    os.environ["BOT_MODE"] = "PAPER"
    base_settings = load_settings()
    assert base_settings.storage is not None
    settings = replace(
        base_settings,
        execution=replace(
            base_settings.execution,
            position_monitor_interval_seconds=5,
            health_check_interval_seconds=5,
            health_failures_before_safe_mode=3,
            loop_idle_sleep_seconds=1.0,
        ),
    )

    conn = make_conn(base_settings.storage.schema_path)
    run_event_loop_smoke(conn, settings)
    run_safe_mode_lifecycle_smoke(conn, settings)
    run_kill_switch_smoke(conn, settings)
    run_daily_summary_smoke(conn, settings)
    print("orchestrator smoke: OK")


if __name__ == "__main__":
    main()

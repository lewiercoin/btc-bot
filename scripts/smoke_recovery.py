from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.recovery import ExchangeOrder, ExchangePosition, RecoveryCoordinator
from monitoring.audit_logger import AuditLogger
from orchestrator import BotOrchestrator
from settings import load_settings
from storage.db import init_db
from storage.state_store import StateStore


SCENARIO_TS = datetime(2026, 3, 26, 12, 0, 0, tzinfo=timezone.utc)


def make_conn(schema_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn, schema_path)
    return conn


def reset_runtime_tables(conn) -> None:
    for table in (
        "executions",
        "trade_log",
        "positions",
        "executable_signals",
        "signal_candidates",
        "daily_metrics",
        "bot_state",
        "alerts_errors",
        "oi_samples",
        "cvd_price_history",
    ):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


class FakeExchangeSyncSource:
    def __init__(self, positions: list[ExchangePosition], orders: list[ExchangeOrder]) -> None:
        self._positions = list(positions)
        self._orders = list(orders)

    def fetch_active_positions(self, symbol: str) -> list[ExchangePosition]:
        _ = symbol
        return list(self._positions)

    def fetch_open_orders(self, symbol: str) -> list[ExchangeOrder]:
        _ = symbol
        return list(self._orders)


class FailingExchangeSyncSource:
    def __init__(self, error_message: str) -> None:
        self._error_message = error_message

    def fetch_active_positions(self, symbol: str) -> list[ExchangePosition]:
        _ = symbol
        raise RuntimeError(self._error_message)

    def fetch_open_orders(self, symbol: str) -> list[ExchangeOrder]:
        _ = symbol
        raise AssertionError("fetch_open_orders should not run after fetch_active_positions failure")


def assert_recovery_audit_log(
    conn,
    *,
    expected_severity: str,
    expected_message: str,
    expected_issues: tuple[str, ...] = (),
    expected_issue: str | None = None,
) -> None:
    records = AuditLogger(conn).query_recent(component="recovery", limit=1)
    assert len(records) == 1
    record = records[0]
    assert record["severity"] == expected_severity
    assert record["message"] == expected_message
    payload = record["payload"]
    if expected_issue is not None:
        assert payload["issue"] == expected_issue
    if expected_issues:
        assert tuple(payload["issues"]) == expected_issues


def seed_local_open_position(conn, *, signal_id: str, opened_at: datetime, direction: str = "LONG") -> None:
    conn.execute(
        """
        INSERT INTO signal_candidates (
            signal_id, timestamp, direction, setup_type, confluence_score, regime,
            reasons_json, features_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            opened_at.isoformat(),
            direction,
            "recovery_smoke",
            3.5,
            "normal",
            "[]",
            "{}",
            "v1.0",
            "smoke",
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
            opened_at.isoformat(),
            direction,
            80000.0,
            79800.0,
            80600.0,
            81000.0,
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
            f"pos-{uuid4().hex[:12]}",
            signal_id,
            "BTCUSDT",
            direction,
            "OPEN",
            80000.0,
            0.1,
            3,
            79800.0,
            80600.0,
            81000.0,
            opened_at.isoformat(),
            opened_at.isoformat(),
        ),
    )
    conn.commit()


def run_scenario(
    *,
    conn,
    settings,
    name: str,
    local_position: bool,
    exchange_sync,
    expected_safe_mode: bool,
    expected_issues: tuple[str, ...],
    expected_log_severity: str,
    expected_log_message: str,
) -> None:
    reset_runtime_tables(conn)
    state_store = StateStore(connection=conn, mode=settings.mode.value)
    state_store.ensure_initialized()

    now = SCENARIO_TS
    if local_position:
        seed_local_open_position(conn, signal_id=f"sig-{uuid4().hex[:12]}", opened_at=now, direction="LONG")

    coordinator = RecoveryCoordinator(
        symbol="BTCUSDT",
        max_allowed_leverage=settings.risk.max_leverage,
        isolated_only=settings.exchange.isolated_only,
        state_store=state_store,
        audit_logger=AuditLogger(conn),
        exchange_sync=exchange_sync,
    )
    report = coordinator.run_startup_sync()
    persisted = state_store.load()
    assert persisted is not None

    print(f"[{name}] report={report}")
    assert report.safe_mode is expected_safe_mode
    assert persisted.safe_mode is expected_safe_mode
    assert persisted.healthy is (not expected_safe_mode)
    assert tuple(report.issues) == expected_issues

    if expected_safe_mode:
        if expected_log_message == "Exchange sync failed during startup recovery.":
            expected_issue = f"exchange_sync_failed:forced_{name}"
            assert persisted.last_error == expected_issue
            assert_recovery_audit_log(
                conn,
                expected_severity=expected_log_severity,
                expected_message=expected_log_message,
                expected_issue=expected_issue,
            )
        else:
            expected_last_error = "recovery_inconsistency:" + ",".join(expected_issues)
            assert persisted.last_error == expected_last_error
            assert_recovery_audit_log(
                conn,
                expected_severity=expected_log_severity,
                expected_message=expected_log_message,
                expected_issues=expected_issues,
            )
        return

    assert persisted.last_error is None
    assert_recovery_audit_log(
        conn,
        expected_severity=expected_log_severity,
        expected_message=expected_log_message,
    )


def main() -> None:
    settings = load_settings()
    assert settings.storage is not None

    conn = make_conn(settings.storage.schema_path)
    orchestrator = BotOrchestrator(settings=settings, conn=conn)
    assert orchestrator.recovery.exchange_sync.__class__.__name__ == "NoOpRecoverySyncSource"

    run_scenario(
        conn=conn,
        settings=settings,
        name="happy_path",
        local_position=True,
        exchange_sync=FakeExchangeSyncSource(
            positions=[
                ExchangePosition(
                    symbol="BTCUSDT",
                    direction="LONG",
                    size=0.1,
                    leverage=3,
                    isolated=True,
                )
            ],
            orders=[],
        ),
        expected_safe_mode=False,
        expected_issues=(),
        expected_log_severity=AuditLogger.SEVERITY_INFO,
        expected_log_message="Startup recovery sync completed without inconsistencies.",
    )
    run_scenario(
        conn=conn,
        settings=settings,
        name="unknown_position",
        local_position=False,
        exchange_sync=FakeExchangeSyncSource(
            positions=[
                ExchangePosition(
                    symbol="BTCUSDT",
                    direction="LONG",
                    size=0.1,
                    leverage=3,
                    isolated=True,
                )
            ],
            orders=[],
        ),
        expected_safe_mode=True,
        expected_issues=("unknown_position",),
        expected_log_severity=AuditLogger.SEVERITY_CRITICAL,
        expected_log_message="Startup recovery found state inconsistency.",
    )
    run_scenario(
        conn=conn,
        settings=settings,
        name="phantom_position",
        local_position=True,
        exchange_sync=FakeExchangeSyncSource(positions=[], orders=[]),
        expected_safe_mode=True,
        expected_issues=("phantom_position",),
        expected_log_severity=AuditLogger.SEVERITY_CRITICAL,
        expected_log_message="Startup recovery found state inconsistency.",
    )
    run_scenario(
        conn=conn,
        settings=settings,
        name="orphan_orders",
        local_position=False,
        exchange_sync=FakeExchangeSyncSource(
            positions=[],
            orders=[
                ExchangeOrder(
                    symbol="BTCUSDT",
                    order_id="12345",
                    side="BUY",
                    position_side="BOTH",
                )
            ],
        ),
        expected_safe_mode=True,
        expected_issues=("orphan_orders",),
        expected_log_severity=AuditLogger.SEVERITY_CRITICAL,
        expected_log_message="Startup recovery found state inconsistency.",
    )
    run_scenario(
        conn=conn,
        settings=settings,
        name="exchange_sync_failed",
        local_position=False,
        exchange_sync=FailingExchangeSyncSource("forced_exchange_sync_failed"),
        expected_safe_mode=True,
        expected_issues=("exchange_sync_failed:forced_exchange_sync_failed",),
        expected_log_severity=AuditLogger.SEVERITY_CRITICAL,
        expected_log_message="Exchange sync failed during startup recovery.",
    )
    run_scenario(
        conn=conn,
        settings=settings,
        name="isolated_mode_mismatch",
        local_position=True,
        exchange_sync=FakeExchangeSyncSource(
            positions=[
                ExchangePosition(
                    symbol="BTCUSDT",
                    direction="LONG",
                    size=0.1,
                    leverage=3,
                    isolated=False,
                )
            ],
            orders=[],
        ),
        expected_safe_mode=True,
        expected_issues=("isolated_mode_mismatch",),
        expected_log_severity=AuditLogger.SEVERITY_CRITICAL,
        expected_log_message="Startup recovery found state inconsistency.",
    )
    run_scenario(
        conn=conn,
        settings=settings,
        name="leverage_mismatch",
        local_position=True,
        exchange_sync=FakeExchangeSyncSource(
            positions=[
                ExchangePosition(
                    symbol="BTCUSDT",
                    direction="LONG",
                    size=0.1,
                    leverage=settings.risk.max_leverage + 1,
                    isolated=True,
                )
            ],
            orders=[],
        ),
        expected_safe_mode=True,
        expected_issues=("leverage_mismatch",),
        expected_log_severity=AuditLogger.SEVERITY_CRITICAL,
        expected_log_message="Startup recovery found state inconsistency.",
    )
    run_scenario(
        conn=conn,
        settings=settings,
        name="combined_issues",
        local_position=False,
        exchange_sync=FakeExchangeSyncSource(
            positions=[
                ExchangePosition(
                    symbol="BTCUSDT",
                    direction="LONG",
                    size=0.1,
                    leverage=settings.risk.max_leverage + 1,
                    isolated=False,
                )
            ],
            orders=[
                ExchangeOrder(
                    symbol="BTCUSDT",
                    order_id="67890",
                    side="SELL",
                    position_side="SHORT",
                )
            ],
        ),
        expected_safe_mode=True,
        expected_issues=(
            "isolated_mode_mismatch",
            "leverage_mismatch",
            "orphan_orders",
            "unknown_position",
        ),
        expected_log_severity=AuditLogger.SEVERITY_CRITICAL,
        expected_log_message="Startup recovery found state inconsistency.",
    )

    print("recovery smoke: OK")


if __name__ == "__main__":
    main()

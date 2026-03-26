from __future__ import annotations

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
from storage.db import connect, init_db
from storage.state_store import StateStore


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
    exchange_positions: list[ExchangePosition],
    exchange_orders: list[ExchangeOrder],
    expected_safe_mode: bool,
    expected_issues: set[str],
) -> None:
    reset_runtime_tables(conn)
    state_store = StateStore(connection=conn, mode=settings.mode.value)
    state_store.ensure_initialized()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    if local_position:
        seed_local_open_position(conn, signal_id=f"sig-{uuid4().hex[:12]}", opened_at=now, direction="LONG")

    coordinator = RecoveryCoordinator(
        symbol="BTCUSDT",
        max_allowed_leverage=settings.risk.max_leverage,
        isolated_only=settings.exchange.isolated_only,
        state_store=state_store,
        audit_logger=AuditLogger(conn),
        exchange_sync=FakeExchangeSyncSource(exchange_positions, exchange_orders),
    )
    report = coordinator.run_startup_sync()
    persisted = state_store.load()
    assert persisted is not None

    print(f"[{name}] report={report}")
    assert report.safe_mode is expected_safe_mode
    assert persisted.safe_mode is expected_safe_mode
    assert set(report.issues) == expected_issues


def main() -> None:
    settings = load_settings()
    assert settings.storage is not None

    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)
    orchestrator = BotOrchestrator(settings=settings, conn=conn)
    assert orchestrator.recovery.exchange_sync.__class__.__name__ == "NoOpRecoverySyncSource"

    run_scenario(
        conn=conn,
        settings=settings,
        name="happy_path",
        local_position=True,
        exchange_positions=[
            ExchangePosition(
                symbol="BTCUSDT",
                direction="LONG",
                size=0.1,
                leverage=3,
                isolated=True,
            )
        ],
        exchange_orders=[],
        expected_safe_mode=False,
        expected_issues=set(),
    )
    run_scenario(
        conn=conn,
        settings=settings,
        name="unknown_position",
        local_position=False,
        exchange_positions=[
            ExchangePosition(
                symbol="BTCUSDT",
                direction="LONG",
                size=0.1,
                leverage=3,
                isolated=True,
            )
        ],
        exchange_orders=[],
        expected_safe_mode=True,
        expected_issues={"unknown_position"},
    )
    run_scenario(
        conn=conn,
        settings=settings,
        name="phantom_position",
        local_position=True,
        exchange_positions=[],
        exchange_orders=[],
        expected_safe_mode=True,
        expected_issues={"phantom_position"},
    )
    run_scenario(
        conn=conn,
        settings=settings,
        name="orphan_orders",
        local_position=False,
        exchange_positions=[],
        exchange_orders=[
            ExchangeOrder(
                symbol="BTCUSDT",
                order_id="12345",
                side="BUY",
                position_side="BOTH",
            )
        ],
        expected_safe_mode=True,
        expected_issues={"orphan_orders"},
    )

    print("recovery smoke: OK")


if __name__ == "__main__":
    main()

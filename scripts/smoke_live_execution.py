from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.execution_types import OrderRequest
from core.models import ExecutableSignal
from data.rest_client import BinanceRequestError
from execution.live_execution_engine import LiveExecutionEngine, LiveExecutionError
from execution.order_manager import OrderManager, OrderManagerError
from monitoring.audit_logger import AuditLogger
from settings import load_settings
from storage.db import connect, init_db


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


class FakeRestClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._queue: dict[tuple[str, str], list[Any]] = {}

    def enqueue(self, method: str, path: str, response_or_exc: Any) -> None:
        key = (method.upper(), path)
        self._queue.setdefault(key, []).append(response_or_exc)

    def signed_request(self, path: str, params: dict[str, Any] | None = None, method: str = "GET") -> Any:
        key = (method.upper(), path)
        self.calls.append({"method": method.upper(), "path": path, "params": dict(params or {})})
        if key not in self._queue or not self._queue[key]:
            raise AssertionError(f"No fake response queued for {method.upper()} {path}")
        item = self._queue[key].pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _ms_now() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def make_order_snapshot(
    *,
    client_order_id: str,
    side: str,
    order_type: str,
    status: str,
    orig_qty: float,
    executed_qty: float,
    avg_price: float,
    price: float,
) -> dict[str, Any]:
    return {
        "symbol": "BTCUSDT",
        "clientOrderId": client_order_id,
        "side": side,
        "type": order_type,
        "status": status,
        "origQty": str(orig_qty),
        "executedQty": str(executed_qty),
        "avgPrice": str(avg_price),
        "price": str(price),
        "updateTime": _ms_now(),
    }


def seed_signal_rows(conn, signal: ExecutableSignal) -> None:
    ts = signal.timestamp.isoformat()
    conn.execute(
        """
        INSERT INTO signal_candidates (
            signal_id, timestamp, direction, setup_type, confluence_score, regime,
            reasons_json, features_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal.signal_id,
            ts,
            signal.direction,
            "smoke_live_execution",
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
            signal.signal_id,
            ts,
            signal.direction,
            signal.entry_price,
            signal.stop_loss,
            signal.take_profit_1,
            signal.take_profit_2,
            signal.rr_ratio,
            "[]",
        ),
    )
    conn.commit()


def run_order_manager_submit_cancel_smoke(conn) -> None:
    fake = FakeRestClient()
    audit = AuditLogger(conn)
    manager = OrderManager(rest_client=fake, audit_logger=audit, symbol="BTCUSDT")

    fake.enqueue(
        "POST",
        "/fapi/v1/order",
        make_order_snapshot(
            client_order_id="ord-smoke-1",
            side="BUY",
            order_type="LIMIT",
            status="NEW",
            orig_qty=0.1,
            executed_qty=0.0,
            avg_price=0.0,
            price=80000.0,
        ),
    )
    order_id = manager.submit(
        OrderRequest(
            client_order_id="ord-smoke-1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            qty=0.1,
            price=80000.0,
            time_in_force="GTC",
        )
    )
    assert order_id == "ord-smoke-1"

    fake.enqueue(
        "DELETE",
        "/fapi/v1/order",
        make_order_snapshot(
            client_order_id="ord-smoke-1",
            side="BUY",
            order_type="LIMIT",
            status="CANCELED",
            orig_qty=0.1,
            executed_qty=0.0,
            avg_price=0.0,
            price=80000.0,
        ),
    )
    manager.cancel("ord-smoke-1")
    print("order manager submit/cancel smoke: OK")


def run_live_execution_flow_smoke(conn) -> None:
    fake = FakeRestClient()
    audit = AuditLogger(conn)
    manager = OrderManager(rest_client=fake, audit_logger=audit, symbol="BTCUSDT")
    engine = LiveExecutionEngine(
        connection=conn,
        rest_client=fake,
        order_manager=manager,
        audit_logger=audit,
        symbol="BTCUSDT",
        entry_order_type="LIMIT",
        entry_timeout_seconds=5,
        poll_interval_seconds=0.0,
    )

    signal = ExecutableSignal(
        signal_id=f"sig-{uuid4().hex[:12]}",
        timestamp=datetime.now(timezone.utc).replace(microsecond=0),
        direction="LONG",
        entry_price=80000.0,
        stop_loss=79750.0,
        take_profit_1=80500.0,
        take_profit_2=80800.0,
        rr_ratio=3.0,
        approved_by_governance=True,
        governance_notes=["smoke"],
    )
    seed_signal_rows(conn, signal)

    fake.enqueue("POST", "/fapi/v1/leverage", {"symbol": "BTCUSDT", "leverage": 3})
    fake.enqueue(
        "POST",
        "/fapi/v1/order",
        make_order_snapshot(
            client_order_id="entry-order-1",
            side="BUY",
            order_type="LIMIT",
            status="NEW",
            orig_qty=0.2,
            executed_qty=0.0,
            avg_price=0.0,
            price=80000.0,
        ),
    )
    fake.enqueue(
        "GET",
        "/fapi/v1/order",
        make_order_snapshot(
            client_order_id="entry-order-1",
            side="BUY",
            order_type="LIMIT",
            status="PARTIALLY_FILLED",
            orig_qty=0.2,
            executed_qty=0.1,
            avg_price=80010.0,
            price=80000.0,
        ),
    )
    fake.enqueue(
        "GET",
        "/fapi/v1/order",
        make_order_snapshot(
            client_order_id="entry-order-1",
            side="BUY",
            order_type="LIMIT",
            status="FILLED",
            orig_qty=0.2,
            executed_qty=0.2,
            avg_price=80005.0,
            price=80000.0,
        ),
    )
    fake.enqueue(
        "POST",
        "/fapi/v1/order",
        make_order_snapshot(
            client_order_id="sl-order-1",
            side="SELL",
            order_type="STOP_MARKET",
            status="NEW",
            orig_qty=0.2,
            executed_qty=0.0,
            avg_price=0.0,
            price=79750.0,
        ),
    )
    fake.enqueue(
        "POST",
        "/fapi/v1/order",
        make_order_snapshot(
            client_order_id="tp-order-1",
            side="SELL",
            order_type="TAKE_PROFIT_MARKET",
            status="NEW",
            orig_qty=0.2,
            executed_qty=0.0,
            avg_price=0.0,
            price=80500.0,
        ),
    )
    fake.enqueue(
        "GET",
        "/fapi/v1/order",
        make_order_snapshot(
            client_order_id="sl-order-1",
            side="SELL",
            order_type="STOP_MARKET",
            status="NEW",
            orig_qty=0.2,
            executed_qty=0.0,
            avg_price=0.0,
            price=79750.0,
        ),
    )
    fake.enqueue(
        "GET",
        "/fapi/v1/order",
        make_order_snapshot(
            client_order_id="tp-order-1",
            side="SELL",
            order_type="TAKE_PROFIT_MARKET",
            status="NEW",
            orig_qty=0.2,
            executed_qty=0.0,
            avg_price=0.0,
            price=80500.0,
        ),
    )

    engine.execute_signal(signal, size=0.2, leverage=3)

    position = conn.execute(
        """
        SELECT signal_id, symbol, direction, status, entry_price, size, leverage
        FROM positions
        WHERE signal_id = ?
        """,
        (signal.signal_id,),
    ).fetchone()
    executions_cnt = conn.execute(
        "SELECT COUNT(*) AS cnt FROM executions",
    ).fetchone()["cnt"]
    assert position is not None
    assert position["symbol"] == "BTCUSDT"
    assert position["direction"] == "LONG"
    assert float(position["size"]) == 0.2
    assert int(position["leverage"]) == 3
    assert int(executions_cnt) >= 4
    print("live execution flow smoke: OK")


def run_rejected_order_smoke(conn) -> None:
    fake = FakeRestClient()
    audit = AuditLogger(conn)
    manager = OrderManager(rest_client=fake, audit_logger=audit, symbol="BTCUSDT")
    engine = LiveExecutionEngine(
        connection=conn,
        rest_client=fake,
        order_manager=manager,
        audit_logger=audit,
        symbol="BTCUSDT",
        entry_order_type="LIMIT",
        entry_timeout_seconds=5,
        poll_interval_seconds=0.0,
    )
    signal = ExecutableSignal(
        signal_id=f"sig-{uuid4().hex[:12]}",
        timestamp=datetime.now(timezone.utc).replace(microsecond=0),
        direction="LONG",
        entry_price=80000.0,
        stop_loss=79750.0,
        take_profit_1=80500.0,
        take_profit_2=80800.0,
        rr_ratio=3.0,
        approved_by_governance=True,
        governance_notes=["smoke"],
    )
    seed_signal_rows(conn, signal)

    fake.enqueue("POST", "/fapi/v1/leverage", {"symbol": "BTCUSDT", "leverage": 3})
    fake.enqueue(
        "POST",
        "/fapi/v1/order",
        BinanceRequestError(
            path="/fapi/v1/order",
            method="POST",
            status_code=400,
            code=-2019,
            message="Margin is insufficient.",
        ),
    )

    failed = False
    try:
        engine.execute_signal(signal, size=0.2, leverage=3)
    except LiveExecutionError:
        failed = True
    assert failed

    # Direct OrderManager error mapping smoke.
    fake2 = FakeRestClient()
    manager2 = OrderManager(rest_client=fake2, audit_logger=audit, symbol="BTCUSDT")
    fake2.enqueue(
        "POST",
        "/fapi/v1/order",
        BinanceRequestError(
            path="/fapi/v1/order",
            method="POST",
            status_code=400,
            code=-2019,
            message="Margin is insufficient.",
        ),
    )
    mapped = False
    try:
        manager2.submit(
            OrderRequest(
                client_order_id="reject-1",
                symbol="BTCUSDT",
                side="BUY",
                order_type="LIMIT",
                qty=0.1,
                price=80000.0,
            )
        )
    except OrderManagerError as exc:
        mapped = exc.reason == "insufficient_margin"
    assert mapped
    print("rejected order smoke: OK")


def main() -> None:
    settings = load_settings()
    assert settings.storage is not None

    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)

    reset_runtime_tables(conn)
    run_order_manager_submit_cancel_smoke(conn)
    reset_runtime_tables(conn)
    run_live_execution_flow_smoke(conn)
    reset_runtime_tables(conn)
    run_rejected_order_smoke(conn)
    print("live execution smoke: OK")


if __name__ == "__main__":
    main()

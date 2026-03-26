from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from monitoring.audit_logger import AuditLogger
from monitoring.health import HealthMonitor
from monitoring.metrics import (
    CYCLE_DURATION_MS,
    ERRORS_TOTAL,
    GOVERNANCE_VETOES,
    MetricsRegistry,
    RISK_BLOCKS,
    SIGNALS_GENERATED,
    TRADES_CLOSED,
    TRADES_OPENED,
)
from monitoring.telegram_notifier import TelegramConfig, TelegramNotifier
from settings import load_settings
from storage.db import connect, init_db


def reset_alerts_table(conn) -> None:
    conn.execute("DELETE FROM alerts_errors")
    conn.commit()


def run_audit_logger_smoke(conn) -> None:
    reset_alerts_table(conn)
    logger = AuditLogger(conn)
    logger.log_info("smoke", "info message", {"n": 1})
    logger.log_warning("smoke", "warning message", {"n": 2})
    logger.log_decision("smoke", "decision message", {"n": 3})
    logger.log_trade("smoke", "trade message", {"n": 4})
    logger.log_error("smoke", "error message", {"n": 5})

    rows = logger.query_recent(component="smoke", limit=10)
    severities = {row["severity"] for row in rows}
    assert {"info", "warning", "decision", "trade", "critical"} <= severities

    decision_rows = logger.query_recent(component="smoke", severity="decision", limit=5)
    assert len(decision_rows) >= 1
    print("audit logger smoke: OK")


@dataclass
class FakeResponse:
    status_code: int
    payload: dict[str, Any] | None = None
    text: str = ""

    def json(self) -> dict[str, Any]:
        if self.payload is None:
            raise ValueError("No JSON payload.")
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, json: dict[str, Any], timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "json": dict(json), "timeout": timeout})
        if not self.responses:
            raise RuntimeError("No fake response queued.")
        return self.responses.pop(0)


def run_telegram_smoke(conn) -> None:
    logger = AuditLogger(conn)

    disabled_session = FakeSession([])
    disabled_notifier = TelegramNotifier(
        TelegramConfig(enabled=False, bot_token="x", chat_id="y"),
        session=disabled_session,
        audit_logger=logger,
    )
    assert disabled_notifier.send("hello") is False
    assert disabled_session.calls == []

    enabled_session = FakeSession([FakeResponse(status_code=200, payload={"ok": True, "result": {"message_id": 1}})])
    enabled_notifier = TelegramNotifier(
        TelegramConfig(enabled=True, bot_token="token", chat_id="chat"),
        session=enabled_session,
        audit_logger=logger,
    )
    sent = enabled_notifier.send_alert(
        "entry",
        {"symbol": "BTCUSDT", "direction": "LONG", "entry_price": 80000.0, "size": 0.1},
    )
    assert sent is True
    assert len(enabled_session.calls) == 1
    call = enabled_session.calls[0]
    assert call["url"].endswith("/sendMessage")
    assert call["json"]["chat_id"] == "chat"
    assert "[ENTRY]" in call["json"]["text"]

    failing_session = FakeSession([FakeResponse(status_code=500, text="server error")])
    failing_notifier = TelegramNotifier(
        TelegramConfig(enabled=True, bot_token="token", chat_id="chat"),
        session=failing_session,
        audit_logger=logger,
    )
    assert failing_notifier.send("will fail") is False
    print("telegram notifier smoke: OK")


@dataclass
class FakeThread:
    alive: bool

    def is_alive(self) -> bool:
        return self.alive


@dataclass
class FakeWsConfig:
    heartbeat_seconds: int = 30


class FakeWebsocketClient:
    def __init__(self, *, alive: bool, last_message_at: datetime | None) -> None:
        self._thread = FakeThread(alive=alive)
        self.last_message_at = last_message_at
        self.config = FakeWsConfig()


class FakeRestClient:
    def __init__(self, ok: bool) -> None:
        self.ok = ok

    def ping(self) -> bool:
        if not self.ok:
            raise RuntimeError("ping failed")
        return True


def run_health_smoke(conn) -> None:
    healthy_monitor = HealthMonitor(
        websocket_client=FakeWebsocketClient(
            alive=True,
            last_message_at=datetime.now(timezone.utc),
        ),
        connection=conn,
        rest_client=FakeRestClient(ok=True),
    )
    healthy = healthy_monitor.check()
    assert healthy.websocket_alive is True
    assert healthy.db_writable is True
    assert healthy.exchange_reachable is True
    assert healthy.healthy is True

    unhealthy_monitor = HealthMonitor(
        websocket_client=FakeWebsocketClient(
            alive=False,
            last_message_at=None,
        ),
        connection=conn,
        rest_client=FakeRestClient(ok=False),
    )
    unhealthy = unhealthy_monitor.check()
    assert unhealthy.websocket_alive is False
    assert unhealthy.exchange_reachable is False
    assert unhealthy.healthy is False
    print("health monitor smoke: OK")


def run_metrics_smoke() -> None:
    metrics = MetricsRegistry()
    metrics.inc(SIGNALS_GENERATED)
    metrics.inc(TRADES_OPENED, 2)
    metrics.inc(TRADES_CLOSED, 1)
    metrics.inc(GOVERNANCE_VETOES, 3)
    metrics.inc(RISK_BLOCKS, 4)
    metrics.inc(ERRORS_TOTAL, 5)
    metrics.set_gauge(CYCLE_DURATION_MS, 123.45)

    snap = metrics.snapshot()
    assert snap["counters"][SIGNALS_GENERATED] == 1
    assert snap["counters"][TRADES_OPENED] == 2
    assert snap["counters"][TRADES_CLOSED] == 1
    assert snap["counters"][GOVERNANCE_VETOES] == 3
    assert snap["counters"][RISK_BLOCKS] == 4
    assert snap["counters"][ERRORS_TOTAL] == 5
    assert snap["gauges"][CYCLE_DURATION_MS] == 123.45
    print("metrics smoke: OK")


def main() -> None:
    settings = load_settings()
    assert settings.storage is not None

    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)

    run_audit_logger_smoke(conn)
    run_telegram_smoke(conn)
    run_health_smoke(conn)
    run_metrics_smoke()
    print("monitoring smoke: OK")


if __name__ == "__main__":
    main()

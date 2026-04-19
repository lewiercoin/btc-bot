from __future__ import annotations

import asyncio
import importlib
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType
from dashboard.runtime_config import extract_runtime_config_hash
from storage.db import init_db


def test_extract_runtime_config_hash_returns_latest_start_entry(tmp_path: Path) -> None:
    log_path = tmp_path / "btc_bot.log"
    log_path.write_text(
        "\n".join(
            [
                "2026-04-17 19:09:15 | INFO | __main__ | Starting bot | mode=PAPER | symbol=BTCUSDT | config_hash=e8c7180d829d8c9c8296b09ba7ad8d0316251d4161d36be26fccc2051d4e5718",
                "2026-04-17 19:15:00 | INFO | orchestrator | Decision cycle started",
                "2026-04-17 19:09:54 | INFO | __main__ | Starting bot | mode=PAPER | symbol=BTCUSDT | config_hash=cf15d9e5326ee5a4af27d2afa3ef57ce153c542aac1238656f130b38ca2420f5",
            ]
        ),
        encoding="utf-8",
    )

    assert extract_runtime_config_hash(log_path) == "cf15d9e5326ee5a4af27d2afa3ef57ce153c542aac1238656f130b38ca2420f5"


def test_extract_runtime_config_hash_returns_none_without_start_line(tmp_path: Path) -> None:
    log_path = tmp_path / "btc_bot.log"
    log_path.write_text(
        "2026-04-17 19:15:00 | INFO | orchestrator | Decision cycle started",
        encoding="utf-8",
    )

    assert extract_runtime_config_hash(log_path) is None


class DummyProcessManager:
    def __init__(self, **_: object) -> None:
        pass

    def status(self) -> dict[str, object]:
        return {
            "running": True,
            "uptime_seconds": 321.0,
            "pid": 4321,
            "mode": "PAPER",
            "exit_code": None,
            "managed": True,
        }

    def start(self, *, mode: str) -> dict[str, object]:
        return {"started": True, "mode": mode, "pid": 4321}

    def stop(self, *, reason: str = "operator_stop") -> dict[str, object]:
        return {"stopped": True, "reason": reason, "pid": 4321, "graceful": True}


def _load_dashboard_server_with_stubs(monkeypatch) -> ModuleType:
    class DummyFastAPI:
        def __init__(self, *args, **kwargs) -> None:
            _ = args
            _ = kwargs
            self.state = SimpleNamespace()

        def mount(self, *args, **kwargs) -> None:
            _ = args
            _ = kwargs

        def get(self, *args, **kwargs):
            _ = args
            _ = kwargs

            def decorator(func):
                return func

            return decorator

        def post(self, *args, **kwargs):
            _ = args
            _ = kwargs

            def decorator(func):
                return func

            return decorator

    fastapi_module = ModuleType("fastapi")
    fastapi_module.FastAPI = DummyFastAPI
    fastapi_module.Query = lambda default=None, **kwargs: default
    fastapi_module.Request = object

    responses_module = ModuleType("fastapi.responses")
    responses_module.FileResponse = object
    responses_module.StreamingResponse = object

    staticfiles_module = ModuleType("fastapi.staticfiles")

    class DummyStaticFiles:
        def __init__(self, *args, **kwargs) -> None:
            _ = args
            _ = kwargs

    staticfiles_module.StaticFiles = DummyStaticFiles

    pydantic_module = ModuleType("pydantic")

    class DummyBaseModel:
        def __init__(self, **kwargs) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    pydantic_module.BaseModel = DummyBaseModel

    psutil_module = ModuleType("psutil")
    psutil_module.cpu_percent = lambda interval=0.1: 0.0
    psutil_module.virtual_memory = lambda: SimpleNamespace(percent=0.0, total=0, used=0)
    psutil_module.getloadavg = lambda: (0.0, 0.0, 0.0)
    psutil_module.disk_usage = lambda path: SimpleNamespace(percent=0.0, total=0, used=0)

    monkeypatch.setitem(sys.modules, "fastapi", fastapi_module)
    monkeypatch.setitem(sys.modules, "fastapi.responses", responses_module)
    monkeypatch.setitem(sys.modules, "fastapi.staticfiles", staticfiles_module)
    monkeypatch.setitem(sys.modules, "pydantic", pydantic_module)
    monkeypatch.setitem(sys.modules, "psutil", psutil_module)
    sys.modules.pop("dashboard.server", None)
    return importlib.import_module("dashboard.server")


def test_runtime_freshness_endpoint_returns_expected_schema(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "btc_bot.db"
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "btc_bot.log"
    log_path.write_text("", encoding="utf-8")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
        init_db(conn, schema_path)
        conn.execute(
            """
            INSERT INTO runtime_metrics (
                id, updated_at, last_decision_cycle_started_at, last_decision_cycle_finished_at,
                last_decision_outcome, decision_cycle_status, last_snapshot_built_at, last_snapshot_symbol,
                last_15m_candle_open_at, last_1h_candle_open_at, last_4h_candle_open_at,
                last_ws_message_at, last_health_check_at, last_runtime_warning, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                now.isoformat(),
                (now - timedelta(seconds=30)).isoformat(),
                (now - timedelta(seconds=29)).isoformat(),
                "no_signal",
                "idle",
                (now - timedelta(seconds=30)).isoformat(),
                "BTCUSDT",
                (now - timedelta(seconds=30)).isoformat(),
                (now - timedelta(minutes=15, seconds=30)).isoformat(),
                (now - timedelta(hours=2, seconds=30)).isoformat(),
                (now - timedelta(seconds=5)).isoformat(),
                (now - timedelta(seconds=25)).isoformat(),
                None,
                "cfg-123",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    fake_settings = SimpleNamespace(
        storage=SimpleNamespace(db_path=db_path, logs_dir=logs_dir),
        execution=SimpleNamespace(ws_heartbeat_seconds=30),
    )

    dashboard_server = _load_dashboard_server_with_stubs(monkeypatch)
    monkeypatch.setattr(dashboard_server, "load_settings", lambda project_root=None: fake_settings)
    monkeypatch.setattr(dashboard_server, "ProcessManager", DummyProcessManager)

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                reader=dashboard_server.DashboardReader(db_path),
                process_manager=DummyProcessManager(),
                settings=fake_settings,
            )
        )
    )
    payload = asyncio.run(dashboard_server.get_runtime_freshness(request))

    assert payload["runtime_available"] is True
    assert payload["decision_cycle"]["status"] == "idle"
    assert payload["decision_cycle"]["last_outcome"] == "no_signal"
    assert payload["rest_snapshot"]["symbol"] == "BTCUSDT"
    assert payload["websocket"]["healthy"] is True
    assert payload["process"]["running"] is True
    assert payload["process"]["pid"] == 4321
    assert payload["process"]["managed"] is True


def test_decision_funnel_and_config_snapshot_endpoints_return_expected_payloads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_hash = "a" * 64
    db_path = tmp_path / "btc_bot.db"
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "btc_bot.log"
    log_path.write_text(
        f"2026-04-19 11:00:00 | INFO | __main__ | Starting bot | mode=PAPER | symbol=BTCUSDT | config_hash={config_hash}",
        encoding="utf-8",
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
        init_db(conn, schema_path)
        conn.execute(
            """
            INSERT INTO decision_outcomes (
                cycle_timestamp, outcome_group, outcome_reason, regime, config_hash, signal_id, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-04-19T10:30:00+00:00", "no_signal", "uptrend_pullback_weak", "uptrend", config_hash, None, "{}"),
        )
        conn.execute(
            """
            INSERT INTO config_snapshots (config_hash, captured_at, strategy_json)
            VALUES (?, ?, ?)
            """,
            (config_hash, "2026-04-19T10:00:00+00:00", '{"allow_uptrend_pullback": true}'),
        )
        conn.commit()
    finally:
        conn.close()

    fake_settings = SimpleNamespace(
        storage=SimpleNamespace(db_path=db_path, logs_dir=logs_dir),
        execution=SimpleNamespace(ws_heartbeat_seconds=30),
    )

    dashboard_server = _load_dashboard_server_with_stubs(monkeypatch)
    monkeypatch.setattr(dashboard_server, "load_settings", lambda project_root=None: fake_settings)
    monkeypatch.setattr(dashboard_server, "ProcessManager", DummyProcessManager)

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                reader=dashboard_server.DashboardReader(db_path),
                process_manager=DummyProcessManager(),
                settings=fake_settings,
                log_path=log_path,
            )
        )
    )

    funnel_payload = asyncio.run(dashboard_server.get_decision_funnel(request))
    config_payload = asyncio.run(dashboard_server.get_config_snapshot(request, config_hash))

    assert funnel_payload["config_hash"] == config_hash
    assert funnel_payload["windows"]["24h"]["by_reason"] == {"uptrend_pullback_weak": 1}
    assert config_payload["config_hash"] == config_hash
    assert config_payload["strategy"] == {"allow_uptrend_pullback": True}

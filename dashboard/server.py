from __future__ import annotations

import csv
import io
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import psutil
from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dashboard.db_reader import DashboardReader
from dashboard.log_streamer import stream_log_lines
from dashboard.process_manager import ProcessManager
from dashboard.runtime_config import extract_runtime_config_hash
from settings import load_settings

_LOG_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
_TAIL_BYTES = 256 * 1024


def _extract_log_ts(line: str) -> datetime | None:
    m = _LOG_TS_RE.match(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _tail_lines(path: Path, max_bytes: int = _TAIL_BYTES) -> list[str]:
    """Read last max_bytes of file and return lines (avoids loading entire file)."""
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            offset = max(0, size - max_bytes)
            f.seek(offset)
            raw = f.read()
        return raw.decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _parse_egress_events(log_path: Path) -> dict[str, Any]:
    """Parse proxy/egress events from bot log tail. No import of ProxyTransport."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    last_session_start: datetime | None = None
    last_ban_at: datetime | None = None
    last_rotation_at: datetime | None = None
    fail_count_24h = 0

    for line in _tail_lines(log_path):
        ts = _extract_log_ts(line)

        if "Proxy transport enabled" in line or "Proxy session expired, reinitializing" in line:
            if ts:
                last_session_start = ts

        elif "CloudFront ban detected" in line:
            if ts and ts >= cutoff:
                fail_count_24h += 1
            if ts:
                last_ban_at = ts

        elif "Proxy rotation:" in line:
            if ts:
                last_rotation_at = ts

    session_age_minutes: float | None = None
    if last_session_start is not None:
        session_age_minutes = round((now - last_session_start).total_seconds() / 60, 1)

    def _iso(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None

    return {
        "last_session_start": _iso(last_session_start),
        "session_age_minutes": session_age_minutes,
        "fail_count_24h": fail_count_24h,
        "last_ban_at": _iso(last_ban_at),
        "last_rotation_at": _iso(last_rotation_at),
    }
PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "dashboard" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings(project_root=PROJECT_ROOT)
    assert settings.storage is not None
    app.state.settings = settings
    app.state.reader = DashboardReader(settings.storage.db_path)
    app.state.log_path = settings.storage.logs_dir / "btc_bot.log"
    app.state.process_manager = ProcessManager(
        project_root=PROJECT_ROOT,
        operator_log_path=settings.storage.logs_dir / "dashboard_operator.jsonl",
    )
    yield


class StartBotRequest(BaseModel):
    mode: Literal["PAPER", "LIVE"]


class StopBotRequest(BaseModel):
    reason: str = "operator_stop"


app = FastAPI(title="BTC Bot Dashboard", version="m4", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def get_status(request: Request) -> dict:
    payload = request.app.state.reader.read_status()
    process_status = request.app.state.process_manager.status()
    payload["uptime_seconds"] = process_status["uptime_seconds"]
    payload["process"] = {
        "running": process_status["running"],
        "pid": process_status["pid"],
        "mode": process_status["mode"],
        "exit_code": process_status["exit_code"],
        "managed": process_status["managed"],
    }
    payload["dashboard_version"] = "m3"
    return payload


@app.get("/api/positions")
async def get_positions(request: Request) -> dict:
    return request.app.state.reader.read_positions()


@app.get("/api/runtime-freshness")
async def get_runtime_freshness(request: Request) -> dict:
    payload = request.app.state.reader.read_runtime_freshness(
        heartbeat_seconds=request.app.state.settings.execution.ws_heartbeat_seconds
    )
    process_status = request.app.state.process_manager.status()
    payload["process"] = {
        "running": process_status["running"],
        "pid": process_status["pid"],
        "mode": process_status["mode"],
        "exit_code": process_status["exit_code"],
        "uptime_seconds": process_status["uptime_seconds"],
        "managed": process_status["managed"],
    }
    return payload


@app.get("/api/trades")
async def get_trades(request: Request, limit: int = Query(default=50, ge=1, le=200)) -> dict:
    runtime_config_hash = extract_runtime_config_hash(request.app.state.log_path)
    return request.app.state.reader.read_trades(limit=limit, config_hash=runtime_config_hash)


@app.get("/api/logs/stream")
async def get_logs_stream(request: Request) -> StreamingResponse:
    generator = stream_log_lines(
        request.app.state.log_path,
        disconnect_checker=request.is_disconnected,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/bot/start")
async def start_bot(request: Request, payload: StartBotRequest) -> dict:
    return request.app.state.process_manager.start(mode=payload.mode)


@app.post("/api/bot/stop")
async def stop_bot(request: Request, payload: StopBotRequest | None = None) -> dict:
    body = payload or StopBotRequest()
    return request.app.state.process_manager.stop(reason=body.reason)


@app.get("/api/signals")
async def get_signals(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> dict:
    runtime_config_hash = extract_runtime_config_hash(request.app.state.log_path)
    return request.app.state.reader.read_signals(limit=limit, config_hash=runtime_config_hash)


@app.get("/api/metrics")
async def get_metrics(request: Request, days: int = Query(default=14, ge=1, le=90)) -> dict:
    return request.app.state.reader.read_daily_metrics(days=days)


@app.get("/api/alerts")
async def get_alerts(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return request.app.state.reader.read_alerts(limit=limit)


@app.get("/api/trades/export")
async def export_trades(request: Request, limit: int = Query(default=200, ge=1, le=1000)) -> StreamingResponse:
    runtime_config_hash = extract_runtime_config_hash(request.app.state.log_path)
    payload = request.app.state.reader.read_trades(limit=limit, config_hash=runtime_config_hash)
    trades = payload["trades"]
    output = io.StringIO()
    if trades:
        writer = csv.DictWriter(output, fieldnames=trades[0].keys())
        writer.writeheader()
        writer.writerows(trades)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )


@app.get("/api/egress")
async def get_egress(request: Request) -> dict:
    settings = request.app.state.settings
    proxy = settings.proxy

    proxy_host: str | None = None
    proxy_port: int | None = None
    raw_url = proxy.proxy_url
    if raw_url and ":" in raw_url:
        parts = raw_url.rsplit(":", 1)
        proxy_host = parts[0] or None
        try:
            proxy_port = int(parts[1])
        except (ValueError, IndexError):
            proxy_port = None

    events = _parse_egress_events(request.app.state.log_path)

    safe_mode: bool | None = None
    safe_mode_reason: str | None = None
    try:
        status = request.app.state.reader.read_status()
        bot_state = status.get("bot_state")
        if bot_state:
            safe_mode = bool(bot_state.get("safe_mode", False))
            safe_mode_reason = bot_state.get("safe_mode_reason")
    except Exception:
        pass

    return {
        "proxy_enabled": proxy.proxy_enabled,
        "proxy_type": proxy.proxy_type if proxy.proxy_enabled else None,
        "proxy_host": proxy_host,
        "proxy_port": proxy_port,
        "sticky_minutes": proxy.sticky_minutes if proxy.proxy_enabled else None,
        "failover_count": len(proxy.failover_list),
        "last_session_start": events["last_session_start"],
        "session_age_minutes": events["session_age_minutes"],
        "fail_count_24h": events["fail_count_24h"],
        "last_ban_at": events["last_ban_at"],
        "last_rotation_at": events["last_rotation_at"],
        "safe_mode": safe_mode,
        "safe_mode_reason": safe_mode_reason,
    }


@app.get("/api/risk")
async def get_risk(request: Request) -> dict:
    settings = request.app.state.settings
    risk = settings.risk
    strategy = settings.strategy

    risk_limits = {
        "daily_dd_limit_pct": risk.daily_dd_limit,
        "weekly_dd_limit_pct": risk.weekly_dd_limit,
        "max_consecutive_losses": risk.max_consecutive_losses,
        "max_open_positions": risk.max_open_positions,
        "max_trades_per_day": risk.max_trades_per_day,
        "confluence_min": strategy.confluence_min,
        "min_rr": risk.min_rr,
    }

    risk_usage: dict = {
        "daily_dd_pct": 0.0,
        "weekly_dd_pct": 0.0,
        "consecutive_losses": 0,
        "open_positions_count": 0,
    }
    safe_mode = False

    try:
        status = request.app.state.reader.read_status()
        bot_state = status.get("bot_state")
        if bot_state:
            risk_usage["daily_dd_pct"] = float(bot_state.get("daily_dd_pct", 0.0))
            risk_usage["weekly_dd_pct"] = float(bot_state.get("weekly_dd_pct", 0.0))
            risk_usage["consecutive_losses"] = int(bot_state.get("consecutive_losses", 0))
            risk_usage["open_positions_count"] = int(bot_state.get("open_positions_count", 0))
            safe_mode = bool(bot_state.get("safe_mode", False))
    except Exception:
        pass

    latest_signal: dict | None = None
    regime: str | None = None
    regime_as_of: str | None = None
    governance_blocked = False

    try:
        runtime_config_hash = extract_runtime_config_hash(request.app.state.log_path)
        signals_payload = request.app.state.reader.read_signals(limit=1, config_hash=runtime_config_hash)
        signals = signals_payload.get("signals", [])
        if signals:
            sig = signals[0]
            latest_signal = {
                "signal_id": sig.get("signal_id"),
                "timestamp": sig.get("timestamp"),
                "direction": sig.get("direction"),
                "setup_type": sig.get("setup_type"),
                "confluence_score": sig.get("confluence_score"),
                "reasons": sig.get("reasons", []),
                "promoted": sig.get("promoted", False),
                "governance_notes": sig.get("governance_notes", []),
                "entry_price": sig.get("entry_price"),
                "rr_ratio": sig.get("rr_ratio"),
            }
            regime = sig.get("regime")
            regime_as_of = sig.get("timestamp")
            governance_blocked = not sig.get("promoted", True)
    except Exception:
        pass

    daily_pct = risk_usage["daily_dd_pct"] / risk_limits["daily_dd_limit_pct"] if risk_limits["daily_dd_limit_pct"] else 0.0
    weekly_pct = risk_usage["weekly_dd_pct"] / risk_limits["weekly_dd_limit_pct"] if risk_limits["weekly_dd_limit_pct"] else 0.0
    losses_pct = risk_usage["consecutive_losses"] / risk_limits["max_consecutive_losses"] if risk_limits["max_consecutive_losses"] else 0.0
    positions_pct = risk_usage["open_positions_count"] / risk_limits["max_open_positions"] if risk_limits["max_open_positions"] else 0.0
    risk_blocked = any(v >= 1.0 for v in (daily_pct, weekly_pct, losses_pct, positions_pct)) or safe_mode

    return {
        "regime": regime,
        "regime_as_of": regime_as_of,
        "latest_signal": latest_signal,
        "risk_limits": risk_limits,
        "risk_usage": risk_usage,
        "governance_blocked": governance_blocked,
        "risk_blocked": risk_blocked,
        "safe_mode": safe_mode,
    }


@app.get("/api/server-resources")
async def get_server_resources(request: Request) -> dict:
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    load_avg = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0.0, 0.0, 0.0)
    disk = psutil.disk_usage("/")

    return {
        "cpu_percent": round(cpu_percent, 1),
        "memory_percent": round(memory.percent, 1),
        "memory_total_gb": round(memory.total / (1024**3), 2),
        "memory_used_gb": round(memory.used / (1024**3), 2),
        "load_avg": {
            "1m": round(load_avg[0], 2),
            "5m": round(load_avg[1], 2),
            "15m": round(load_avg[2], 2),
        },
        "disk_percent": round(disk.percent, 1),
        "disk_total_gb": round(disk.total / (1024**3), 2),
        "disk_used_gb": round(disk.used / (1024**3), 2),
    }


@app.get("/api/signals/export")
async def export_signals(request: Request, limit: int = Query(default=200, ge=1, le=1000)) -> StreamingResponse:
    runtime_config_hash = extract_runtime_config_hash(request.app.state.log_path)
    payload = request.app.state.reader.read_signals(limit=limit, config_hash=runtime_config_hash)
    signals = payload["signals"]
    output = io.StringIO()
    if signals:
        rows = []
        for sig in signals:
            row = {k: v for k, v in sig.items() if k not in ("reasons", "governance_notes")}
            row["reasons"] = "; ".join(str(r) for r in sig.get("reasons", []))
            row["governance_notes"] = "; ".join(str(n) for n in sig.get("governance_notes", []))
            rows.append(row)
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=signals.csv"},
    )

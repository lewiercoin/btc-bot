from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dashboard.db_reader import DashboardReader
from dashboard.log_streamer import stream_log_lines
from dashboard.process_manager import ProcessManager
from settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "dashboard" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings(project_root=PROJECT_ROOT)
    assert settings.storage is not None
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


app = FastAPI(title="BTC Bot Dashboard", version="m3", lifespan=lifespan)
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
    }
    payload["dashboard_version"] = "m3"
    return payload


@app.get("/api/positions")
async def get_positions(request: Request) -> dict:
    return request.app.state.reader.read_positions()


@app.get("/api/trades")
async def get_trades(request: Request, limit: int = Query(default=50, ge=1, le=200)) -> dict:
    return request.app.state.reader.read_trades(limit=limit)


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
    return request.app.state.reader.read_signals(limit=limit)


@app.get("/api/metrics")
async def get_metrics(request: Request, days: int = Query(default=14, ge=1, le=90)) -> dict:
    return request.app.state.reader.read_daily_metrics(days=days)


@app.get("/api/alerts")
async def get_alerts(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> dict:
    return request.app.state.reader.read_alerts(limit=limit)


@app.get("/api/trades/export")
async def export_trades(request: Request, limit: int = Query(default=200, ge=1, le=1000)) -> StreamingResponse:
    payload = request.app.state.reader.read_trades(limit=limit)
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


@app.get("/api/signals/export")
async def export_signals(request: Request, limit: int = Query(default=200, ge=1, le=1000)) -> StreamingResponse:
    payload = request.app.state.reader.read_signals(limit=limit)
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

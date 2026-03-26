from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import websockets

LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class WebsocketClientConfig:
    ws_base_url: str
    heartbeat_seconds: int
    reconnect_seconds: int
    agg_trade_buffer_size: int = 20_000
    force_order_buffer_size: int = 5_000


def _ms_to_utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def normalize_ws_agg_trade_event(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(payload["s"]).upper(),
        "event_time": _ms_to_utc(int(payload["T"])),
        "price": float(payload["p"]),
        "qty": float(payload["q"]),
        "is_buyer_maker": bool(payload["m"]),
    }


def normalize_ws_force_order_event(payload: dict[str, Any]) -> dict[str, Any]:
    order = payload["o"]
    return {
        "symbol": str(order["s"]).upper(),
        "event_time": _ms_to_utc(int(order["T"])),
        "side": str(order["S"]).upper(),
        "qty": float(order["q"]),
        "price": float(order["p"]),
    }


class BinanceFuturesWebsocketClient:
    def __init__(self, config: WebsocketClientConfig) -> None:
        self.config = config
        self._symbol = "BTCUSDT"
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._agg_trade_events: deque[dict[str, Any]] = deque(maxlen=self.config.agg_trade_buffer_size)
        self._force_order_events: deque[dict[str, Any]] = deque(maxlen=self.config.force_order_buffer_size)
        self._last_message_at: datetime | None = None

    def start(self, symbol: str = "BTCUSDT") -> None:
        if self._thread and self._thread.is_alive():
            return
        self._symbol = symbol.upper()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def get_recent_agg_trades(self, window_seconds: int) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        with self._lock:
            return [event for event in self._agg_trade_events if event["event_time"] >= cutoff]

    def get_recent_force_orders(self, window_seconds: int) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        with self._lock:
            return [event for event in self._force_order_events if event["event_time"] >= cutoff]

    @property
    def last_message_at(self) -> datetime | None:
        return self._last_message_at

    @property
    def is_connected(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop_event.is_set())

    def _thread_main(self) -> None:
        asyncio.run(self._run_forever())

    def _build_stream_url(self) -> str:
        base = self.config.ws_base_url.rstrip("/")
        symbol = self._symbol.lower()

        if base.endswith("/ws"):
            root = base[: -len("/ws")]
            return f"{root}/stream?streams={symbol}@aggTrade/{symbol}@forceOrder"
        if base.endswith("/stream"):
            return f"{base}?streams={symbol}@aggTrade/{symbol}@forceOrder"
        return f"{base}/stream?streams={symbol}@aggTrade/{symbol}@forceOrder"

    async def _run_forever(self) -> None:
        stream_url = self._build_stream_url()

        while not self._stop_event.is_set():
            try:
                async with websockets.connect(
                    stream_url,
                    ping_interval=self.config.heartbeat_seconds,
                    ping_timeout=self.config.heartbeat_seconds,
                    close_timeout=5,
                    max_queue=4096,
                ) as socket:
                    LOG.info("Connected websocket stream: %s", stream_url)
                    await self._consume(socket)
            except Exception as exc:
                LOG.warning("Websocket stream failure: %s", exc)
                if self._stop_event.is_set():
                    break
                await asyncio.sleep(self.config.reconnect_seconds)

    async def _consume(self, socket: websockets.ClientConnection) -> None:
        while not self._stop_event.is_set():
            try:
                raw_message = await asyncio.wait_for(socket.recv(), timeout=self.config.heartbeat_seconds * 2)
            except asyncio.TimeoutError:
                await socket.ping()
                continue

            self._last_message_at = datetime.now(timezone.utc)
            self._handle_message(raw_message)

    def _handle_message(self, raw_message: str) -> None:
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            return

        if "data" in payload and isinstance(payload["data"], dict):
            data = payload["data"]
        else:
            data = payload

        event_type = data.get("e")
        if event_type == "aggTrade":
            event = normalize_ws_agg_trade_event(data)
            with self._lock:
                self._agg_trade_events.append(event)
            return

        if event_type == "forceOrder":
            event = normalize_ws_force_order_event(data)
            with self._lock:
                self._force_order_events.append(event)

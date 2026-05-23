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
    ws_market_base_url: str
    heartbeat_seconds: int
    reconnect_seconds: int
    agg_trade_buffer_size: int = 20_000
    force_order_buffer_size: int = 5_000


def _ms_to_utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def normalize_ws_agg_trade_event(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(payload["s"]).upper(),
        "aggregate_trade_id": int(payload["a"]),
        "event_time": _ms_to_utc(int(payload["T"])),
        "price": float(payload["p"]),
        "qty": float(payload["q"]),
        "is_buyer_maker": bool(payload["m"]),
        "_exchange_raw": dict(payload),
    }


def normalize_ws_force_order_event(payload: dict[str, Any]) -> dict[str, Any]:
    order = payload["o"]
    return {
        "symbol": str(order["s"]).upper(),
        "event_time": _ms_to_utc(int(order["T"])),
        "side": str(order["S"]).upper(),
        "qty": float(order["q"]),
        "price": float(order["p"]),
        "_exchange_raw": dict(payload),
    }


class BinanceFuturesWebsocketClient:
    def __init__(self, config: WebsocketClientConfig, symbols: list[str] | None = None) -> None:
        self.config = config
        self._symbols = [s.upper() for s in (symbols or ["BTCUSDT"])]
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        # Per-symbol buffers for multi-symbol support
        self._agg_trade_events: dict[str, deque[dict[str, Any]]] = {
            sym: deque(maxlen=self.config.agg_trade_buffer_size) for sym in self._symbols
        }
        self._force_order_events: dict[str, deque[dict[str, Any]]] = {
            sym: deque(maxlen=self.config.force_order_buffer_size) for sym in self._symbols
        }
        self._last_message_at: datetime | None = None

    def start(self, symbols: list[str] | None = None) -> None:
        if self._thread and self._thread.is_alive():
            return
        if symbols:
            self._symbols = [s.upper() for s in symbols]
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def get_recent_agg_trades(self, window_seconds: int, symbol: str | None = None) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        target_symbol = symbol.upper() if symbol else None
        with self._lock:
            if target_symbol:
                buffer = self._agg_trade_events.get(target_symbol)
                if buffer is None:
                    return []
                return [event for event in buffer if event["event_time"] >= cutoff]
            # Return all symbols if no specific symbol requested
            all_events = []
            for buffer in self._agg_trade_events.values():
                all_events.extend([event for event in buffer if event["event_time"] >= cutoff])
            return all_events

    def get_recent_force_orders(self, window_seconds: int, symbol: str | None = None) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        target_symbol = symbol.upper() if symbol else None
        with self._lock:
            if target_symbol:
                buffer = self._force_order_events.get(target_symbol)
                if buffer is None:
                    return []
                return [event for event in buffer if event["event_time"] >= cutoff]
            # Return all symbols if no specific symbol requested
            all_events = []
            for buffer in self._force_order_events.values():
                all_events.extend([event for event in buffer if event["event_time"] >= cutoff])
            return all_events

    @property
    def last_message_at(self) -> datetime | None:
        return self._last_message_at

    @property
    def is_connected(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop_event.is_set())

    def _thread_main(self) -> None:
        asyncio.run(self._run_forever())

    def _build_market_stream_url(self) -> str:
        base = self.config.ws_market_base_url.rstrip("/")
        if base.endswith("/market"):
            base = base[: -len("/market")] + "/stream"
        elif base.endswith("/ws"):
            base = base[: -len("/ws")] + "/stream"
        elif not base.endswith("/stream"):
            base = f"{base}/stream"
        # Build streams for all symbols: btcusdt@aggTrade/ethusdt@aggTrade/...
        streams = []
        for sym in self._symbols:
            sym_lower = sym.lower()
            streams.append(f"{sym_lower}@aggTrade")
            streams.append(f"{sym_lower}@forceOrder")
        return f"{base}?streams={'/'.join(streams)}"

    def _build_legacy_stream_url(self) -> str:
        base = self.config.ws_base_url.rstrip("/")

        if base.endswith("/ws"):
            root = base[: -len("/ws")]
        elif base.endswith("/stream"):
            root = base
        else:
            root = f"{base}/stream"
        # Build streams for all symbols
        streams = []
        for sym in self._symbols:
            sym_lower = sym.lower()
            streams.append(f"{sym_lower}@aggTrade")
            streams.append(f"{sym_lower}@forceOrder")
        return f"{root}?streams={'/'.join(streams)}"

    def _build_stream_url(self) -> str:
        return self._build_market_stream_url()

    async def _run_forever(self) -> None:
        use_market = True

        while not self._stop_event.is_set():
            stream_url = self._build_market_stream_url() if use_market else self._build_legacy_stream_url()
            url_type = "market" if use_market else "legacy"

            try:
                async with websockets.connect(
                    stream_url,
                    ping_interval=self.config.heartbeat_seconds,
                    ping_timeout=self.config.heartbeat_seconds,
                    close_timeout=5,
                    max_queue=4096,
                ) as socket:
                    LOG.info("Connected websocket stream (%s): %s", url_type, stream_url)
                    await self._consume(socket)
            except Exception as exc:
                LOG.warning("Websocket stream failure (%s): %s", url_type, exc)
                if self._stop_event.is_set():
                    break

                if use_market:
                    LOG.info("Falling back to legacy /stream/ path")
                    use_market = False
                else:
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

        # Extract stream name for routing (e.g., "ethusdt@aggTrade")
        stream_name = payload.get("stream", "")
        # Extract symbol from stream name (part before @)
        target_symbol = None
        if stream_name and "@" in stream_name:
            target_symbol = stream_name.split("@")[0].upper()

        if "data" in payload and isinstance(payload["data"], dict):
            data = payload["data"]
        else:
            data = payload

        event_type = data.get("e")
        if event_type == "aggTrade":
            event = normalize_ws_agg_trade_event(data)
            # Use symbol from event data if stream routing failed
            event_symbol = target_symbol or event.get("symbol", "BTCUSDT").upper()
            with self._lock:
                if event_symbol in self._agg_trade_events:
                    self._agg_trade_events[event_symbol].append(event)
                else:
                    # Fallback to first symbol buffer if unknown
                    self._agg_trade_events[self._symbols[0]].append(event)
            return

        if event_type == "forceOrder":
            event = normalize_ws_force_order_event(data)
            event_symbol = target_symbol or event.get("symbol", "BTCUSDT").upper()
            with self._lock:
                if event_symbol in self._force_order_events:
                    self._force_order_events[event_symbol].append(event)
                else:
                    self._force_order_events[self._symbols[0]].append(event)

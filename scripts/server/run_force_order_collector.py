from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
import websockets

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from settings import load_settings
from storage.db import connect, init_db, transaction

LOG = logging.getLogger(__name__)

BINANCE_FORCE_ORDERS_URL = "https://fapi.binance.com/fapi/v1/forceOrders"
BINANCE_FORCE_ORDER_STREAM_URL = "wss://fstream.binance.com/stream?streams=btcusdt@forceOrder"
DEFAULT_BOOTSTRAP_DAYS = 7
DEFAULT_FORCE_ORDER_LIMIT = 100
MAX_FORCE_ORDER_LIMIT = 100
REST_TIMEOUT_SECONDS = 10
REST_MAX_RETRIES = 3
REST_RETRY_BACKOFF_SECONDS = 1.0
RECONNECT_DELAYS_SECONDS = (5, 10, 30, 60)


class UtcFormatter(logging.Formatter):
    converter = time.gmtime


class BinanceApiError(RuntimeError):
    def __init__(self, *, status_code: int, code: int | None, message: str) -> None:
        self.status_code = int(status_code)
        self.code = code
        self.message = message
        super().__init__(self.__str__())

    def __str__(self) -> str:
        parts = [f"http={self.status_code}"]
        if self.code is not None:
            parts.append(f"code={self.code}")
        parts.append(f"msg={self.message}")
        return "BinanceApiError(" + ", ".join(parts) + ")"


@dataclass(slots=True)
class BootstrapSummary:
    fetched: int = 0
    inserted: int = 0
    pages: int = 0
    effective_limit: int = DEFAULT_FORCE_ORDER_LIMIT


def configure_logging(level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(
        UtcFormatter(
            fmt="%(asctime)sZ %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root_logger.addHandler(handler)


def _ms_to_utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _to_ms(value: datetime) -> int:
    dt = value.astimezone(timezone.utc)
    return int(dt.timestamp() * 1000)


def normalize_ws_force_order_event(payload: dict[str, Any]) -> dict[str, Any]:
    order = payload["o"]
    return {
        "symbol": str(order["s"]).upper(),
        "event_time": _ms_to_utc(int(order["T"])),
        "side": str(order["S"]).upper(),
        "qty": float(order["q"]),
        "price": float(order["p"]),
    }


def normalize_rest_force_order_event(payload: dict[str, Any]) -> dict[str, Any]:
    raw_event_time = payload.get("updateTime") or payload.get("time") or payload.get("T")
    if raw_event_time in (None, ""):
        raise ValueError("Force-order REST payload is missing event time.")

    raw_avg_price = payload.get("avgPrice")
    avg_price = float(raw_avg_price) if raw_avg_price not in (None, "") else 0.0
    raw_price = payload.get("price") or payload.get("p")
    if raw_price in (None, ""):
        raise ValueError("Force-order REST payload is missing price.")

    raw_qty = payload.get("executedQty") or payload.get("origQty") or payload.get("q")
    if raw_qty in (None, ""):
        raise ValueError("Force-order REST payload is missing quantity.")

    return {
        "symbol": str(payload["symbol"]).upper(),
        "event_time": _ms_to_utc(int(raw_event_time)),
        "side": str(payload["side"]).upper(),
        "qty": float(raw_qty),
        "price": avg_price if avg_price > 0.0 else float(raw_price),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persist Binance BTCUSDT force-order events into SQLite.")
    parser.add_argument("--bootstrap-only", action="store_true", help="Backfill the last 7 days via REST, then exit.")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    return parser.parse_args(argv)


def _parse_binance_error(response: requests.Response) -> BinanceApiError:
    code: int | None = None
    message = response.text.strip() or "Binance request failed."
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        raw_code = payload.get("code")
        raw_message = payload.get("msg")
        if raw_code is not None:
            try:
                code = int(raw_code)
            except (TypeError, ValueError):
                code = None
        if raw_message:
            message = str(raw_message)

    return BinanceApiError(status_code=response.status_code, code=code, message=message)


class BinanceForceOrdersRestClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_API_SECRET", "")

    def close(self) -> None:
        self.session.close()

    def fetch_force_orders_page(
        self,
        *,
        symbol: str,
        start_time_ms: int,
        end_time_ms: int,
        limit: int = DEFAULT_FORCE_ORDER_LIMIT,
    ) -> tuple[list[dict[str, Any]], int]:
        if not self.api_key or not self.api_secret:
            raise RuntimeError("Binance force-orders endpoint requires API credentials.")

        requested_limit = int(limit)
        effective_limit = max(1, min(requested_limit, MAX_FORCE_ORDER_LIMIT))
        if effective_limit != requested_limit:
            LOG.warning(
                "event=force_orders_rest_limit_clamped requested_limit=%s effective_limit=%s symbol=%s",
                requested_limit,
                effective_limit,
                symbol.upper(),
            )

        params = {
            "symbol": symbol.upper(),
            "startTime": int(start_time_ms),
            "endTime": int(end_time_ms),
            "limit": int(effective_limit),
        }
        payload = self._request(params, signed=True)
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected Binance force-order payload.")
        return payload, effective_limit

    def _request(self, params: dict[str, Any], *, signed: bool) -> Any:
        headers: dict[str, str] = {}
        base_params = dict(params)
        if signed:
            if not self.api_key or not self.api_secret:
                raise RuntimeError("Signed Binance request requires API credentials.")
            base_params["recvWindow"] = 5000
            headers["X-MBX-APIKEY"] = self.api_key

        last_error: Exception | None = None
        for attempt in range(REST_MAX_RETRIES + 1):
            request_params = dict(base_params)
            if signed:
                request_params["timestamp"] = int(datetime.now(timezone.utc).timestamp() * 1000)
                query = urlencode(request_params, doseq=True)
                request_params["signature"] = hmac.new(
                    self.api_secret.encode("utf-8"),
                    query.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()

            try:
                response = self.session.get(
                    BINANCE_FORCE_ORDERS_URL,
                    params=request_params,
                    headers=headers or None,
                    timeout=REST_TIMEOUT_SECONDS,
                )
                if response.status_code >= 400:
                    error = _parse_binance_error(response)
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < REST_MAX_RETRIES:
                        delay = REST_RETRY_BACKOFF_SECONDS * (2**attempt)
                        LOG.warning(
                            "event=force_orders_rest_retry attempt=%s method=GET signed=%s http=%s delay_seconds=%.1f",
                            attempt + 1,
                            str(bool(signed)).lower(),
                            response.status_code,
                            delay,
                        )
                        time.sleep(delay)
                        continue
                    raise error

                if not response.text:
                    return []
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= REST_MAX_RETRIES:
                    break
                delay = REST_RETRY_BACKOFF_SECONDS * (2**attempt)
                LOG.warning(
                    "event=force_orders_rest_retry attempt=%s method=GET signed=%s error=%s delay_seconds=%.1f",
                    attempt + 1,
                    str(bool(signed)).lower(),
                    str(exc).replace(" ", "_"),
                    delay,
                )
                time.sleep(delay)

        raise RuntimeError("Binance force-orders request failed after retries.") from last_error


FORCE_ORDER_INSERT_SQL = """
INSERT INTO force_orders (symbol, event_time, side, qty, price)
SELECT ?, ?, ?, ?, ?
WHERE NOT EXISTS (
    SELECT 1
    FROM force_orders
    WHERE symbol = ? AND event_time = ?
)
"""


def insert_force_orders(conn: sqlite3.Connection, events: list[dict[str, Any]]) -> int:
    if not events:
        return 0

    before = conn.total_changes
    conn.executemany(
        FORCE_ORDER_INSERT_SQL,
        [
            (
                item["symbol"],
                item["event_time"].isoformat(),
                item["side"],
                item["qty"],
                item["price"],
                item["symbol"],
                item["event_time"].isoformat(),
            )
            for item in events
        ],
    )
    return conn.total_changes - before


def insert_force_order_immediately(conn: sqlite3.Connection, event: dict[str, Any]) -> int:
    with transaction(conn):
        return insert_force_orders(conn, [event])


def bootstrap_force_orders(
    conn: sqlite3.Connection,
    client: BinanceForceOrdersRestClient,
    *,
    symbol: str,
    start_time: datetime,
    end_time: datetime,
    stop_requested: threading.Event,
) -> BootstrapSummary:
    summary = BootstrapSummary()
    cursor_ms = _to_ms(start_time)
    end_ms = _to_ms(end_time)

    LOG.info(
        "event=force_orders_bootstrap_start symbol=%s start=%s end=%s requested_limit=%s",
        symbol.upper(),
        start_time.isoformat(),
        end_time.isoformat(),
        DEFAULT_FORCE_ORDER_LIMIT,
    )

    while cursor_ms <= end_ms and not stop_requested.is_set():
        batch, effective_limit = client.fetch_force_orders_page(
            symbol=symbol,
            start_time_ms=cursor_ms,
            end_time_ms=end_ms,
            limit=summary.effective_limit,
        )
        summary.effective_limit = int(effective_limit)
        if not batch:
            break

        normalized = [
            normalize_rest_force_order_event(item)
            for item in batch
            if str(item.get("symbol", "")).upper() == symbol.upper()
        ]
        normalized.sort(key=lambda item: item["event_time"])

        with transaction(conn):
            page_inserted = insert_force_orders(conn, normalized)

        summary.pages += 1
        summary.fetched += len(normalized)
        summary.inserted += page_inserted

        LOG.info(
            "event=force_orders_bootstrap_page symbol=%s page=%s fetched=%s inserted=%s next_limit=%s",
            symbol.upper(),
            summary.pages,
            len(normalized),
            page_inserted,
            summary.effective_limit,
        )

        if len(batch) < summary.effective_limit:
            break

        if normalized:
            last_event_ms = _to_ms(normalized[-1]["event_time"])
        else:
            last_payload = batch[-1]
            raw_last_ms = last_payload.get("updateTime") or last_payload.get("time") or last_payload.get("T")
            if raw_last_ms in (None, ""):
                break
            last_event_ms = int(raw_last_ms)

        next_cursor = last_event_ms + 1
        if next_cursor <= cursor_ms:
            break
        cursor_ms = next_cursor

    LOG.info(
        "event=force_orders_bootstrap_complete symbol=%s pages=%s fetched=%s inserted=%s effective_limit=%s",
        symbol.upper(),
        summary.pages,
        summary.fetched,
        summary.inserted,
        summary.effective_limit,
    )
    return summary


def parse_ws_force_order_message(raw_message: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError:
        return None

    data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return None
    if data.get("e") != "forceOrder":
        return None
    return normalize_ws_force_order_event(data)


def reconnect_delay(attempt: int) -> int:
    index = min(max(attempt, 0), len(RECONNECT_DELAYS_SECONDS) - 1)
    return int(RECONNECT_DELAYS_SECONDS[index])


class ForceOrderStreamCollector:
    def __init__(self, *, conn: sqlite3.Connection, heartbeat_seconds: int) -> None:
        self.conn = conn
        self.heartbeat_seconds = max(int(heartbeat_seconds), 10)
        self.stop_requested = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._socket: websockets.ClientConnection | None = None
        self._persisted_events = 0

    def request_stop(self, reason: str) -> None:
        if self.stop_requested.is_set():
            return
        LOG.warning("event=force_orders_shutdown_requested reason=%s", reason.replace(" ", "_"))
        self.stop_requested.set()
        if self._loop is not None:
            self._loop.call_soon_threadsafe(lambda: None)
        if self._loop is not None and self._socket is not None:
            try:
                asyncio.run_coroutine_threadsafe(self._socket.close(), self._loop)
            except RuntimeError:
                pass

    async def run_forever(self) -> None:
        self._loop = asyncio.get_running_loop()
        attempt = 0

        while not self.stop_requested.is_set():
            try:
                async with websockets.connect(
                    BINANCE_FORCE_ORDER_STREAM_URL,
                    ping_interval=self.heartbeat_seconds,
                    ping_timeout=self.heartbeat_seconds,
                    close_timeout=5,
                    max_queue=4096,
                ) as socket:
                    self._socket = socket
                    attempt = 0
                    LOG.info("event=force_orders_ws_connected stream=%s", BINANCE_FORCE_ORDER_STREAM_URL)
                    await self._consume(socket)
            except Exception as exc:
                self._socket = None
                if self.stop_requested.is_set():
                    break
                delay = reconnect_delay(attempt)
                attempt += 1
                LOG.warning(
                    "event=force_orders_ws_reconnect error=%s delay_seconds=%s",
                    str(exc).replace(" ", "_"),
                    delay,
                )
                await asyncio.sleep(delay)

        LOG.info("event=force_orders_ws_stopped persisted_events=%s", self._persisted_events)

    async def _consume(self, socket: websockets.ClientConnection) -> None:
        while not self.stop_requested.is_set():
            try:
                raw_message = await asyncio.wait_for(socket.recv(), timeout=self.heartbeat_seconds * 2)
            except asyncio.TimeoutError:
                await socket.ping()
                continue

            event = parse_ws_force_order_message(raw_message)
            if event is None:
                continue

            inserted = insert_force_order_immediately(self.conn, event)
            self._persisted_events += inserted
            if inserted and self._persisted_events % 100 == 0:
                LOG.info(
                    "event=force_orders_ws_progress persisted_events=%s last_event_time=%s",
                    self._persisted_events,
                    event["event_time"].isoformat(),
                )


def install_signal_handlers(
    *,
    stop_requested: threading.Event,
    collector: ForceOrderStreamCollector | None = None,
) -> None:
    def _handle_signal(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        stop_requested.set()
        if collector is not None:
            collector.request_stop(f"signal:{signum}")
            return
        LOG.warning("event=force_orders_shutdown_requested reason=signal:%s", signum)

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    configure_logging(args.log_level)

    settings = load_settings()
    assert settings.storage is not None
    symbol = settings.strategy.symbol.upper()
    heartbeat_seconds = int(settings.execution.ws_heartbeat_seconds)

    conn = connect(settings.storage.db_path)
    conn.execute("PRAGMA busy_timeout = 5000;")
    init_db(conn, settings.storage.schema_path)

    rest_client = BinanceForceOrdersRestClient()
    stop_requested = threading.Event()
    install_signal_handlers(stop_requested=stop_requested)

    try:
        now_utc = datetime.now(timezone.utc)
        bootstrap_start = now_utc - timedelta(days=DEFAULT_BOOTSTRAP_DAYS)
        bootstrap_force_orders(
            conn,
            rest_client,
            symbol=symbol,
            start_time=bootstrap_start,
            end_time=now_utc,
            stop_requested=stop_requested,
        )

        if args.bootstrap_only:
            LOG.info("event=force_orders_bootstrap_only_exit symbol=%s", symbol)
            return

        if stop_requested.is_set():
            LOG.info("event=force_orders_bootstrap_interrupted symbol=%s", symbol)
            return

        collector = ForceOrderStreamCollector(conn=conn, heartbeat_seconds=heartbeat_seconds)
        install_signal_handlers(stop_requested=stop_requested, collector=collector)
        asyncio.run(collector.run_forever())
    except KeyboardInterrupt:
        LOG.warning("event=force_orders_keyboard_interrupt")
    finally:
        rest_client.close()
        try:
            conn.close()
        except Exception:
            pass
        LOG.info("event=force_orders_collector_exit")


if __name__ == "__main__":
    main()

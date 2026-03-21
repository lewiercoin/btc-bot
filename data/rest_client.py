from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class RestClientConfig:
    base_url: str
    timeout_seconds: int
    max_retries: int = 3
    retry_backoff_seconds: float = 0.75


class RestClientError(RuntimeError):
    pass


def _ms_to_utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def normalize_kline(payload: list[Any], symbol: str, timeframe: str) -> dict[str, Any]:
    if len(payload) < 6:
        raise ValueError("Invalid kline payload.")
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "open_time": _ms_to_utc(int(payload[0])),
        "open": float(payload[1]),
        "high": float(payload[2]),
        "low": float(payload[3]),
        "close": float(payload[4]),
        "volume": float(payload[5]),
    }


def normalize_funding(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol.upper(),
        "funding_time": _ms_to_utc(int(payload["fundingTime"])),
        "funding_rate": float(payload["fundingRate"]),
    }


def normalize_open_interest(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
    timestamp_ms = int(payload.get("time") or payload.get("timestamp") or int(datetime.now(timezone.utc).timestamp() * 1000))
    return {
        "symbol": symbol.upper(),
        "timestamp": _ms_to_utc(timestamp_ms),
        "oi_value": float(payload["openInterest"]),
    }


def normalize_open_interest_hist(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol.upper(),
        "timestamp": _ms_to_utc(int(payload["timestamp"])),
        "oi_value": float(payload["sumOpenInterest"]),
    }


def normalize_book_ticker(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(payload["symbol"]).upper(),
        "bid": float(payload["bidPrice"]),
        "ask": float(payload["askPrice"]),
    }


def normalize_agg_trade(payload: dict[str, Any], symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol.upper(),
        "event_time": _ms_to_utc(int(payload["T"])),
        "price": float(payload["p"]),
        "qty": float(payload["q"]),
        "is_buyer_maker": bool(payload["m"]),
    }


class BinanceFuturesRestClient:
    def __init__(self, config: RestClientConfig, session: requests.Session | None = None) -> None:
        self.config = config
        self.session = session or requests.Session()

    def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.config.base_url.rstrip('/')}{path}"
        error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.config.timeout_seconds)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                error = exc
                if attempt >= self.config.max_retries:
                    break
                sleep_seconds = self.config.retry_backoff_seconds * (2**attempt)
                LOG.warning("REST retry %s/%s for %s after error: %s", attempt + 1, self.config.max_retries, path, exc)
                time.sleep(sleep_seconds)

        raise RestClientError(f"Failed request {path} after retries") from error

    def fetch_klines(self, symbol: str, interval: str, limit: int = 500) -> list[dict[str, Any]]:
        payload = self._request(
            "/fapi/v1/klines",
            {"symbol": symbol.upper(), "interval": interval, "limit": int(limit)},
        )
        return [normalize_kline(item, symbol=symbol, timeframe=interval) for item in payload]

    def fetch_funding_history(self, symbol: str, limit: int = 200) -> list[dict[str, Any]]:
        payload = self._request(
            "/fapi/v1/fundingRate",
            {"symbol": symbol.upper(), "limit": int(limit)},
        )
        return [normalize_funding(item, symbol=symbol) for item in payload]

    def fetch_open_interest(self, symbol: str) -> dict[str, Any]:
        payload = self._request("/fapi/v1/openInterest", {"symbol": symbol.upper()})
        return normalize_open_interest(payload, symbol=symbol)

    def fetch_open_interest_history(self, symbol: str, period: str = "5m", limit: int = 200) -> list[dict[str, Any]]:
        payload = self._request(
            "/futures/data/openInterestHist",
            {"symbol": symbol.upper(), "period": period, "limit": int(limit)},
        )
        if not isinstance(payload, list):
            raise RestClientError("Unexpected openInterestHist response payload.")
        return [normalize_open_interest_hist(item, symbol=symbol) for item in payload]

    def fetch_book_ticker(self, symbol: str) -> dict[str, Any]:
        payload = self._request("/fapi/v1/ticker/bookTicker", {"symbol": symbol.upper()})
        return normalize_book_ticker(payload)

    def fetch_exchange_info(self) -> dict[str, Any]:
        return self._request("/fapi/v1/exchangeInfo")

    def fetch_agg_trades(
        self,
        symbol: str,
        limit: int = 1000,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"symbol": symbol.upper(), "limit": int(limit)}
        if start_time_ms is not None:
            params["startTime"] = int(start_time_ms)
        if end_time_ms is not None:
            params["endTime"] = int(end_time_ms)

        payload = self._request("/fapi/v1/aggTrades", params)
        return [normalize_agg_trade(item, symbol=symbol) for item in payload]

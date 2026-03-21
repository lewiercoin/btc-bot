from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any, Iterable

from core.models import MarketSnapshot
from data.rest_client import BinanceFuturesRestClient
from data.websocket_client import BinanceFuturesWebsocketClient


@dataclass(slots=True)
class MarketDataConfig:
    candles_limit: int = 300
    funding_limit: int = 200
    agg_trades_limit: int = 1000


def aggregate_aggtrade_bucket(
    trades: Iterable[dict[str, Any]],
    symbol: str,
    timeframe: str,
    now: datetime,
) -> dict[str, Any]:
    trade_list = list(trades)
    taker_buy_volume = 0.0
    taker_sell_volume = 0.0

    for trade in trade_list:
        qty = float(trade["qty"])
        if bool(trade["is_buyer_maker"]):
            taker_sell_volume += qty
        else:
            taker_buy_volume += qty

    total = taker_buy_volume + taker_sell_volume
    cvd = taker_buy_volume - taker_sell_volume
    tfi = 0.0 if total == 0 else cvd / total

    return {
        "symbol": symbol.upper(),
        "bucket_time": now.astimezone(timezone.utc),
        "timeframe": timeframe,
        "taker_buy_volume": taker_buy_volume,
        "taker_sell_volume": taker_sell_volume,
        "tfi": tfi,
        "cvd": cvd,
        "trades_count": len(trade_list),
    }


def filter_events_by_window(events: Iterable[dict[str, Any]], now: datetime, window_seconds: int) -> list[dict[str, Any]]:
    now_utc = now.astimezone(timezone.utc)
    cutoff = now_utc.timestamp() - window_seconds
    return [event for event in events if event["event_time"].timestamp() >= cutoff]


class MarketDataAssembler:
    def __init__(
        self,
        rest_client: BinanceFuturesRestClient,
        websocket_client: BinanceFuturesWebsocketClient | None = None,
        config: MarketDataConfig | None = None,
        db_connection: sqlite3.Connection | None = None,
    ) -> None:
        self.rest_client = rest_client
        self.websocket_client = websocket_client
        self.config = config or MarketDataConfig()
        self.db_connection = db_connection

    def build_snapshot(self, symbol: str, timestamp: datetime) -> MarketSnapshot:
        now = timestamp.astimezone(timezone.utc)

        ticker = self.rest_client.fetch_book_ticker(symbol)
        candles_15m = self.rest_client.fetch_klines(symbol, "15m", limit=self.config.candles_limit)
        candles_1h = self.rest_client.fetch_klines(symbol, "1h", limit=self.config.candles_limit)
        candles_4h = self.rest_client.fetch_klines(symbol, "4h", limit=self.config.candles_limit)
        funding_history = self.rest_client.fetch_funding_history(symbol, limit=self.config.funding_limit)
        open_interest = self.rest_client.fetch_open_interest(symbol)

        agg_60s, agg_15m = self._load_agg_trade_windows(symbol=symbol, now=now)
        force_orders_60s = self._load_force_order_window(now=now)
        etf_bias_daily, dxy_daily = self._load_external_bias(now=now)

        bid = float(ticker["bid"])
        ask = float(ticker["ask"])
        return MarketSnapshot(
            symbol=symbol.upper(),
            timestamp=now,
            price=(bid + ask) / 2,
            bid=bid,
            ask=ask,
            candles_15m=candles_15m,
            candles_1h=candles_1h,
            candles_4h=candles_4h,
            funding_history=funding_history,
            open_interest=float(open_interest["oi_value"]),
            aggtrades_bucket_60s=agg_60s,
            aggtrades_bucket_15m=agg_15m,
            force_order_events_60s=force_orders_60s,
            etf_bias_daily=etf_bias_daily,
            dxy_daily=dxy_daily,
        )

    def _load_agg_trade_windows(self, symbol: str, now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
        ws_events: list[dict[str, Any]] = []
        if self.websocket_client is not None:
            ws_events = self.websocket_client.get_recent_agg_trades(15 * 60)

        if not ws_events:
            ws_events = self.rest_client.fetch_agg_trades(symbol=symbol, limit=self.config.agg_trades_limit)

        trades_60s = filter_events_by_window(ws_events, now=now, window_seconds=60)
        trades_15m = filter_events_by_window(ws_events, now=now, window_seconds=15 * 60)

        bucket_60s = aggregate_aggtrade_bucket(trades_60s, symbol=symbol, timeframe="60s", now=now)
        bucket_15m = aggregate_aggtrade_bucket(trades_15m, symbol=symbol, timeframe="15m", now=now)
        return bucket_60s, bucket_15m

    def _load_force_order_window(self, now: datetime) -> list[dict[str, Any]]:
        if self.websocket_client is None:
            return []
        events = self.websocket_client.get_recent_force_orders(60)
        return filter_events_by_window(events, now=now, window_seconds=60)

    def _load_external_bias(self, now: datetime) -> tuple[float | None, float | None]:
        if self.db_connection is None:
            return None, None

        row = self.db_connection.execute(
            """
            SELECT etf_bias_5d, dxy_close
            FROM daily_external_bias
            WHERE date <= ?
            ORDER BY date DESC
            LIMIT 1
            """,
            (now.date().isoformat(),),
        ).fetchone()
        if row is None:
            return None, None
        return row["etf_bias_5d"], row["dxy_close"]

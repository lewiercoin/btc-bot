from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import timezone
from typing import Any, Iterable

from core.models import FeatureQuality, MarketSnapshot
from data.rest_client import BinanceFuturesRestClient
from data.websocket_client import BinanceFuturesWebsocketClient
from storage.repositories import save_cvd_price_bar, save_oi_sample


@dataclass(slots=True)
class MarketDataConfig:
    candles_limit: int = 300
    funding_limit: int = 200
    agg_trades_limit: int = 1000
    flow_coverage_ready: float = 0.90
    flow_coverage_degraded: float = 0.70


def aggregate_aggtrade_bucket(
    trades: Iterable[dict[str, Any]],
    symbol: str,
    timeframe: str,
    now: datetime,
    metadata: dict[str, Any] | None = None,
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

    bucket = {
        "symbol": symbol.upper(),
        "bucket_time": now.astimezone(timezone.utc),
        "timeframe": timeframe,
        "taker_buy_volume": taker_buy_volume,
        "taker_sell_volume": taker_sell_volume,
        "tfi": tfi,
        "cvd": cvd,
        "trades_count": len(trade_list),
    }
    if metadata:
        bucket.update(metadata)
    return bucket


def filter_events_by_window(events: Iterable[dict[str, Any]], now: datetime, window_seconds: int) -> list[dict[str, Any]]:
    now_utc = now.astimezone(timezone.utc)
    cutoff = now_utc.timestamp() - window_seconds
    return [
        event
        for event in events
        if _event_time(event) is not None and _event_time(event).timestamp() >= cutoff
    ]


def _event_time(event: dict[str, Any]) -> datetime | None:
    raw = event.get("event_time")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        parsed = raw
    else:
        try:
            parsed = datetime.fromisoformat(str(raw))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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

        self._persist_oi_sample(symbol=symbol, sample=open_interest, captured_at=now)

        agg_60s, agg_15m, flow_quality = self._load_agg_trade_windows(symbol=symbol, now=now)
        force_orders_60s = self._load_force_order_window(now=now)
        etf_bias_daily, dxy_daily = self._load_external_bias(now=now)

        bid = float(ticker["bid"])
        ask = float(ticker["ask"])
        price = (bid + ask) / 2
        self._persist_cvd_price_bar(
            symbol=symbol,
            bucket=agg_15m,
            price_close=price,
            captured_at=now,
        )
        return MarketSnapshot(
            symbol=symbol.upper(),
            timestamp=now,
            price=price,
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
            quality=flow_quality,
        )

    def _load_agg_trade_windows(self, symbol: str, now: datetime) -> tuple[dict[str, Any], dict[str, Any], dict[str, FeatureQuality]]:
        ws_events: list[dict[str, Any]] = []
        source = "ws"
        if self.websocket_client is not None:
            ws_events = self.websocket_client.get_recent_agg_trades(15 * 60)

        if not ws_events:
            source = "rest"
            ws_events = self.rest_client.fetch_agg_trades_window(
                symbol=symbol,
                start_time=now - timedelta(seconds=15 * 60),
                end_time=now,
                limit=self.config.agg_trades_limit,
            )

        trades_60s = filter_events_by_window(ws_events, now=now, window_seconds=60)
        trades_15m = filter_events_by_window(ws_events, now=now, window_seconds=15 * 60)

        coverage_60s = self._flow_window_metadata(
            trades_60s,
            now=now,
            window_seconds=60,
            source=source,
            limit_reached=len(ws_events) >= self.config.agg_trades_limit,
        )
        coverage_15m = self._flow_window_metadata(
            trades_15m,
            now=now,
            window_seconds=15 * 60,
            source=source,
            limit_reached=len(ws_events) >= self.config.agg_trades_limit,
        )

        bucket_60s = aggregate_aggtrade_bucket(
            trades_60s,
            symbol=symbol,
            timeframe="60s",
            now=now,
            metadata=coverage_60s,
        )
        bucket_15m = aggregate_aggtrade_bucket(
            trades_15m,
            symbol=symbol,
            timeframe="15m",
            now=now,
            metadata=coverage_15m,
        )
        return bucket_60s, bucket_15m, {
            "flow_60s": self._quality_from_flow_metadata(coverage_60s),
            "flow_15m": self._quality_from_flow_metadata(coverage_15m),
        }

    def _flow_window_metadata(
        self,
        trades: Iterable[dict[str, Any]],
        *,
        now: datetime,
        window_seconds: int,
        source: str,
        limit_reached: bool,
    ) -> dict[str, Any]:
        trade_times = sorted(ts for event in trades if (ts := _event_time(event)) is not None)
        window_end = now.astimezone(timezone.utc)
        window_start = window_end - timedelta(seconds=window_seconds)
        if not trade_times:
            coverage_ratio = 0.0
            first_ts = None
            last_ts = None
        else:
            first_ts = trade_times[0]
            last_ts = trade_times[-1]
            covered_start = max(first_ts, window_start)
            covered_end = min(last_ts, window_end)
            covered_seconds = max((covered_end - covered_start).total_seconds(), 0.0)
            coverage_ratio = min(covered_seconds / max(float(window_seconds), 1.0), 1.0)
        clipped_by_limit = bool(limit_reached and first_ts is not None and first_ts > window_start)
        return {
            "source": source,
            "coverage_ratio": coverage_ratio,
            "first_event_time": first_ts.isoformat() if first_ts else None,
            "last_event_time": last_ts.isoformat() if last_ts else None,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "limit_reached": limit_reached,
            "clipped_by_limit": clipped_by_limit,
        }

    def _quality_from_flow_metadata(self, metadata: dict[str, Any]) -> FeatureQuality:
        coverage_ratio = float(metadata.get("coverage_ratio", 0.0))
        provenance = str(metadata.get("source", "unknown"))
        if metadata.get("clipped_by_limit"):
            return FeatureQuality.degraded(
                reason="flow_window_rest_limit_clipped",
                metadata=metadata,
                provenance=provenance,
            )
        if coverage_ratio >= self.config.flow_coverage_ready:
            return FeatureQuality.ready(
                reason="flow_window_complete",
                metadata=metadata,
                provenance=provenance,
            )
        if coverage_ratio >= self.config.flow_coverage_degraded:
            return FeatureQuality.degraded(
                reason="flow_window_partial",
                metadata=metadata,
                provenance=provenance,
            )
        return FeatureQuality.unavailable(
            reason="flow_window_insufficient",
            metadata=metadata,
            provenance=provenance,
        )

    def _persist_oi_sample(self, *, symbol: str, sample: dict[str, Any], captured_at: datetime) -> None:
        if self.db_connection is None:
            return
        try:
            save_oi_sample(
                self.db_connection,
                symbol=symbol,
                timestamp=sample["timestamp"],
                oi_value=float(sample["oi_value"]),
                source="rest",
                captured_at=captured_at,
            )
            self.db_connection.commit()
        except Exception:
            self.db_connection.rollback()
            raise

    def _persist_cvd_price_bar(
        self,
        *,
        symbol: str,
        bucket: dict[str, Any],
        price_close: float,
        captured_at: datetime,
    ) -> None:
        if self.db_connection is None:
            return
        try:
            save_cvd_price_bar(
                self.db_connection,
                symbol=symbol,
                timeframe="15m",
                bar_time=bucket["bucket_time"],
                price_close=price_close,
                cvd=float(bucket.get("cvd", 0.0)),
                tfi=None if bucket.get("tfi") is None else float(bucket.get("tfi", 0.0)),
                source=str(bucket.get("source", "unknown")),
                captured_at=captured_at,
            )
            self.db_connection.commit()
        except Exception:
            self.db_connection.rollback()
            raise

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

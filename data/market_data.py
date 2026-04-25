from __future__ import annotations

import sqlite3
import time
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
    funding_window_days: int = 60
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
        build_started_at = now
        build_started = time.perf_counter()

        ticker_started = time.perf_counter()
        ticker = self.rest_client.fetch_book_ticker(symbol)
        ticker_latency_ms = (time.perf_counter() - ticker_started) * 1000.0
        candles_15m_started = time.perf_counter()
        candles_15m = self.rest_client.fetch_klines(symbol, "15m", limit=self.config.candles_limit)
        candles_15m_latency_ms = (time.perf_counter() - candles_15m_started) * 1000.0
        candles_1h_started = time.perf_counter()
        candles_1h = self.rest_client.fetch_klines(symbol, "1h", limit=self.config.candles_limit)
        candles_1h_latency_ms = (time.perf_counter() - candles_1h_started) * 1000.0
        candles_4h_started = time.perf_counter()
        candles_4h = self.rest_client.fetch_klines(symbol, "4h", limit=self.config.candles_limit)
        candles_4h_latency_ms = (time.perf_counter() - candles_4h_started) * 1000.0
        funding_started = time.perf_counter()
        funding_history = self._load_funding_window(symbol=symbol, now=now)
        funding_latency_ms = (time.perf_counter() - funding_started) * 1000.0
        oi_started = time.perf_counter()
        open_interest = self.rest_client.fetch_open_interest(symbol)
        open_interest_latency_ms = (time.perf_counter() - oi_started) * 1000.0

        self._persist_oi_sample(symbol=symbol, sample=open_interest, captured_at=now)

        (
            agg_60s,
            agg_15m,
            agg_events_60s,
            agg_events_15m,
            flow_quality,
            agg_meta,
        ) = self._load_agg_trade_windows(symbol=symbol, now=now)
        force_orders_60s = self._load_force_order_window(now=now)
        etf_bias_daily, dxy_daily = self._load_external_bias(now=now)
        total_latency_ms = (time.perf_counter() - build_started) * 1000.0
        build_finished_at = datetime.now(timezone.utc)

        bid = float(ticker["bid"])
        ask = float(ticker["ask"])
        price = (bid + ask) / 2
        self._persist_cvd_price_bar(
            symbol=symbol,
            bucket=agg_15m,
            price_close=price,
            captured_at=now,
        )
        exchange_timestamp = self._resolve_exchange_timestamp(
            candles_15m=candles_15m,
            open_interest=open_interest,
            agg_events_15m=agg_events_15m,
            force_orders_60s=force_orders_60s,
        )

        # Extract per-input exchange timestamps for quant-grade lineage
        candles_15m_exchange_ts = candles_15m[-1]["open_time"] if candles_15m else None
        candles_1h_exchange_ts = candles_1h[-1]["open_time"] if candles_1h else None
        candles_4h_exchange_ts = candles_4h[-1]["open_time"] if candles_4h else None
        funding_exchange_ts = funding_history[-1]["funding_time"] if funding_history else None
        oi_exchange_ts = open_interest.get("timestamp")
        aggtrades_exchange_ts = agg_events_15m[-1]["event_time"] if agg_events_15m else None
        force_orders_exchange_ts = force_orders_60s[-1]["event_time"] if force_orders_60s else None

        data_quality_flag = self._rollup_quality_flag(flow_quality)
        return MarketSnapshot(
            symbol=symbol.upper(),
            timestamp=now,
            price=price,
            bid=bid,
            ask=ask,
            exchange_timestamp=exchange_timestamp,
            source="mixed",
            latency_ms=total_latency_ms,
            data_quality_flag=data_quality_flag,
            book_ticker=ticker,
            open_interest_payload=open_interest,
            candles_15m=candles_15m,
            candles_1h=candles_1h,
            candles_4h=candles_4h,
            funding_history=funding_history,
            open_interest=float(open_interest["oi_value"]),
            aggtrade_events_60s=agg_events_60s,
            aggtrade_events_15m=agg_events_15m,
            aggtrades_bucket_60s=agg_60s,
            aggtrades_bucket_15m=agg_15m,
            force_order_events_60s=force_orders_60s,
            etf_bias_daily=etf_bias_daily,
            dxy_daily=dxy_daily,
            quality=flow_quality,
            source_meta={
                "book_ticker": {"source": "rest", "latency_ms": ticker_latency_ms},
                "candles_15m": {"source": "rest", "latency_ms": candles_15m_latency_ms},
                "candles_1h": {"source": "rest", "latency_ms": candles_1h_latency_ms},
                "candles_4h": {"source": "rest", "latency_ms": candles_4h_latency_ms},
                "funding_history": {"source": "rest", "latency_ms": funding_latency_ms},
                "open_interest": {"source": "rest", "latency_ms": open_interest_latency_ms},
                "aggtrade_60s": agg_meta["aggtrade_60s"],
                "aggtrade_15m": agg_meta["aggtrade_15m"],
                "force_orders_60s": {
                    "source": "ws" if force_orders_60s else "none",
                    "events_count": len(force_orders_60s),
                    "last_event_time": force_orders_60s[-1]["event_time"].isoformat() if force_orders_60s else None,
                },
                "build_latency_ms": total_latency_ms,
                "ws_last_message_at": self._last_ws_message_at_iso(),
            },
            # Quant-grade lineage fields
            candles_15m_exchange_ts=candles_15m_exchange_ts,
            candles_1h_exchange_ts=candles_1h_exchange_ts,
            candles_4h_exchange_ts=candles_4h_exchange_ts,
            funding_exchange_ts=funding_exchange_ts,
            oi_exchange_ts=oi_exchange_ts,
            aggtrades_exchange_ts=aggtrades_exchange_ts,
            force_orders_exchange_ts=force_orders_exchange_ts,
            snapshot_build_started_at=build_started_at,
            snapshot_build_finished_at=build_finished_at,
        )

    def _load_agg_trade_windows(
        self,
        symbol: str,
        now: datetime,
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
        dict[str, FeatureQuality],
        dict[str, dict[str, Any]],
    ]:
        ws_events: list[dict[str, Any]] = []
        source = "ws"
        if self.websocket_client is not None:
            ws_events = self.websocket_client.get_recent_agg_trades(15 * 60)

        if not ws_events:
            source = "rest"
            ws_events = self._load_rest_agg_trade_window(
                symbol=symbol,
                start_time=now - timedelta(seconds=15 * 60),
                end_time=now,
            )

        trades_60s = filter_events_by_window(ws_events, now=now, window_seconds=60)
        trades_15m = filter_events_by_window(ws_events, now=now, window_seconds=15 * 60)
        limit_reached = bool(source == "rest" and len(ws_events) >= self.config.agg_trades_limit)

        coverage_60s = self._flow_window_metadata(
            trades_60s,
            now=now,
            window_seconds=60,
            source=source,
            limit_reached=limit_reached,
        )
        coverage_15m = self._flow_window_metadata(
            trades_15m,
            now=now,
            window_seconds=15 * 60,
            source=source,
            limit_reached=limit_reached,
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
        return (
            bucket_60s,
            bucket_15m,
            trades_60s,
            trades_15m,
            {
                "flow_60s": self._quality_from_flow_metadata(coverage_60s),
                "flow_15m": self._quality_from_flow_metadata(coverage_15m),
            },
            {
                "aggtrade_60s": coverage_60s,
                "aggtrade_15m": coverage_15m,
            },
        )

    def _load_rest_agg_trade_window(
        self,
        *,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        start_utc = start_time.astimezone(timezone.utc)
        end_utc = end_time.astimezone(timezone.utc)
        batch_limit = max(int(self.config.agg_trades_limit), 1)
        seen_ids: set[int] = set()
        all_trades: list[dict[str, Any]] = []

        batch = self.rest_client.fetch_agg_trades_window(
            symbol=symbol,
            start_time=start_utc,
            end_time=end_utc,
            limit=batch_limit,
        )
        all_trades.extend(self._dedupe_agg_trades(batch, seen_ids))
        if len(batch) < batch_limit:
            return all_trades

        while batch:
            last_id = self._agg_trade_id(batch[-1])
            if last_id is None:
                break
            batch = self.rest_client.fetch_agg_trades(
                symbol=symbol,
                from_id=last_id + 1,
                limit=batch_limit,
            )
            if not batch:
                break
            in_window = [
                trade
                for trade in batch
                if start_utc <= trade["event_time"].astimezone(timezone.utc) <= end_utc
            ]
            all_trades.extend(self._dedupe_agg_trades(in_window, seen_ids))
            if len(batch) < batch_limit:
                break
            if batch[0]["event_time"].astimezone(timezone.utc) > end_utc:
                break

        return sorted(all_trades, key=lambda item: item["event_time"])

    def _load_funding_window(self, *, symbol: str, now: datetime) -> list[dict[str, Any]]:
        window_end = now.astimezone(timezone.utc)
        window_start = window_end - timedelta(days=self.config.funding_window_days)
        batch_limit = max(min(int(self.config.funding_limit), 1000), 1)
        cursor_ms = int(window_start.timestamp() * 1000)
        end_ms = int(window_end.timestamp() * 1000)
        seen_times: set[str] = set()
        rows: list[dict[str, Any]] = []

        while cursor_ms <= end_ms:
            batch = self.rest_client.fetch_funding_history(
                symbol,
                limit=batch_limit,
                start_time_ms=cursor_ms,
                end_time_ms=end_ms,
            )
            if not batch:
                break

            new_rows = 0
            last_ts_ms: int | None = None
            for row in batch:
                funding_time = row["funding_time"].astimezone(timezone.utc)
                key = funding_time.isoformat()
                if key in seen_times:
                    continue
                seen_times.add(key)
                rows.append(row)
                new_rows += 1
                last_ts_ms = int(funding_time.timestamp() * 1000)

            if last_ts_ms is None or new_rows == 0 or len(batch) < batch_limit:
                break
            cursor_ms = last_ts_ms + 1

        return sorted(rows, key=lambda item: item["funding_time"])

    @staticmethod
    def _agg_trade_id(trade: dict[str, Any]) -> int | None:
        raw = trade.get("_exchange_raw")
        if isinstance(raw, dict) and raw.get("a") is not None:
            return int(raw["a"])
        aggregate_trade_id = trade.get("aggregate_trade_id")
        if aggregate_trade_id is None:
            return None
        return int(aggregate_trade_id)

    def _dedupe_agg_trades(
        self,
        trades: Iterable[dict[str, Any]],
        seen_ids: set[int],
    ) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        for trade in trades:
            trade_id = self._agg_trade_id(trade)
            if trade_id is not None:
                if trade_id in seen_ids:
                    continue
                seen_ids.add(trade_id)
            deduped.append(trade)
        return deduped

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

    def _resolve_exchange_timestamp(
        self,
        *,
        candles_15m: list[dict[str, Any]],
        open_interest: dict[str, Any],
        agg_events_15m: list[dict[str, Any]],
        force_orders_60s: list[dict[str, Any]],
    ) -> datetime | None:
        candidates: list[datetime] = []
        oi_ts = open_interest.get("timestamp")
        if isinstance(oi_ts, datetime):
            candidates.append(oi_ts.astimezone(timezone.utc))
        if candles_15m:
            candle_open = candles_15m[-1].get("open_time")
            if isinstance(candle_open, datetime):
                candidates.append(candle_open.astimezone(timezone.utc))
        if agg_events_15m:
            event_time = agg_events_15m[-1].get("event_time")
            if isinstance(event_time, datetime):
                candidates.append(event_time.astimezone(timezone.utc))
        if force_orders_60s:
            force_event_time = force_orders_60s[-1].get("event_time")
            if isinstance(force_event_time, datetime):
                candidates.append(force_event_time.astimezone(timezone.utc))
        if not candidates:
            return None
        return max(candidates)

    @staticmethod
    def _rollup_quality_flag(quality: dict[str, FeatureQuality]) -> str:
        if not quality:
            return "unknown"
        statuses = {item.status for item in quality.values()}
        if "unavailable" in statuses:
            return "unavailable"
        if "degraded" in statuses:
            return "degraded"
        return "ready"

    def _last_ws_message_at_iso(self) -> str | None:
        if self.websocket_client is None or self.websocket_client.last_message_at is None:
            return None
        return self.websocket_client.last_message_at.astimezone(timezone.utc).isoformat()

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

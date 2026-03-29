from __future__ import annotations

import sqlite3
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterator

from core.models import MarketSnapshot


@dataclass(slots=True)
class ReplayLoaderConfig:
    candles_15m_lookback: int = 300
    candles_1h_lookback: int = 300
    candles_4h_lookback: int = 300
    funding_lookback: int = 200


@dataclass(slots=True)
class ReplayBatch:
    snapshots: list[MarketSnapshot]


@dataclass(slots=True)
class _ReplaySeries:
    timestamps: list[datetime]
    rows: list[dict[str, Any]]


@dataclass(slots=True)
class _PreloadedReplayData:
    candles_15m: _ReplaySeries
    candles_1h: _ReplaySeries
    candles_4h: _ReplaySeries
    funding: _ReplaySeries
    open_interest_timestamps: list[datetime]
    open_interest_values: list[float]
    agg_15m: _ReplaySeries
    agg_60s: _ReplaySeries
    agg_15m_exact: dict[datetime, dict[str, Any]]
    agg_60s_exact: dict[datetime, dict[str, Any]]
    force_orders: _ReplaySeries
    bias_dates: list[date]
    bias_values: list[tuple[float | None, float | None]]


class ReplayLoader:
    """Builds historical MarketSnapshot objects from persisted SQLite history."""

    def __init__(self, connection: sqlite3.Connection, config: ReplayLoaderConfig | None = None) -> None:
        self.connection = connection
        if self.connection.row_factory is None:
            self.connection.row_factory = sqlite3.Row
        self.config = config or ReplayLoaderConfig()

    def load(
        self,
        *,
        start_date: datetime | date | str,
        end_date: datetime | date | str,
        symbol: str,
    ) -> ReplayBatch:
        return ReplayBatch(
            snapshots=list(
                self.iter_snapshots(
                    start_date=start_date,
                    end_date=end_date,
                    symbol=symbol,
                )
            )
        )

    def iter_snapshots(
        self,
        *,
        start_date: datetime | date | str,
        end_date: datetime | date | str,
        symbol: str,
    ) -> Iterator[MarketSnapshot]:
        start_ts = _as_utc_datetime(start_date)
        end_ts = _as_utc_datetime(end_date)
        if end_ts < start_ts:
            return

        symbol_upper = symbol.upper()
        preloaded = self._preload(symbol=symbol_upper, start_ts=start_ts, end_ts=end_ts)

        for candle in preloaded.candles_15m.rows:
            candle_open_time = candle["open_time"]
            snapshot_ts = candle_open_time + timedelta(minutes=15)
            if snapshot_ts < start_ts or snapshot_ts > end_ts:
                continue

            close_price = float(candle["close"])
            candles_15m = self._slice_lookback(
                preloaded.candles_15m,
                up_to_time=candle_open_time,
                limit=self.config.candles_15m_lookback,
            )
            candles_1h = self._slice_lookback(
                preloaded.candles_1h,
                up_to_time=snapshot_ts,
                limit=self.config.candles_1h_lookback,
            )
            candles_4h = self._slice_lookback(
                preloaded.candles_4h,
                up_to_time=snapshot_ts,
                limit=self.config.candles_4h_lookback,
            )
            funding_history = self._slice_lookback(
                preloaded.funding,
                up_to_time=snapshot_ts,
                limit=self.config.funding_lookback,
            )
            agg_15m = self._resolve_agg_bucket(
                symbol=symbol_upper,
                timeframe="15m",
                at_time=candle_open_time,
                fallback_time=snapshot_ts,
                exact_index=preloaded.agg_15m_exact,
                series=preloaded.agg_15m,
            )
            agg_60s = self._resolve_agg_bucket(
                symbol=symbol_upper,
                timeframe="60s",
                at_time=_floor_60s(snapshot_ts - timedelta(seconds=1)),
                fallback_time=snapshot_ts,
                exact_index=preloaded.agg_60s_exact,
                series=preloaded.agg_60s,
            )
            force_orders_60s = self._force_orders_window(
                preloaded.force_orders,
                end_time=snapshot_ts,
            )
            etf_bias_daily, dxy_daily = self._external_bias(preloaded, at_time=snapshot_ts)

            yield MarketSnapshot(
                symbol=symbol_upper,
                timestamp=snapshot_ts,
                price=close_price,
                bid=close_price,
                ask=close_price,
                candles_15m=candles_15m,
                candles_1h=candles_1h,
                candles_4h=candles_4h,
                funding_history=funding_history,
                open_interest=self._open_interest(preloaded, up_to_time=snapshot_ts),
                aggtrades_bucket_60s=agg_60s,
                aggtrades_bucket_15m=agg_15m,
                force_order_events_60s=force_orders_60s,
                etf_bias_daily=etf_bias_daily,
                dxy_daily=dxy_daily,
            )

    def _preload(self, *, symbol: str, start_ts: datetime, end_ts: datetime) -> _PreloadedReplayData:
        lookback_start = min(
            start_ts - timedelta(minutes=15 * max(int(self.config.candles_15m_lookback), 0)),
            start_ts - timedelta(hours=max(int(self.config.candles_1h_lookback), 0)),
            start_ts - timedelta(hours=4 * max(int(self.config.candles_4h_lookback), 0)),
        )

        candle_rows = self.connection.execute(
            """
            SELECT timeframe, open_time, open, high, low, close, volume
            FROM candles
            WHERE symbol = ?
              AND timeframe IN ('15m', '1h', '4h')
              AND open_time >= ?
              AND open_time <= ?
            ORDER BY timeframe ASC, open_time ASC
            """,
            (symbol, lookback_start.isoformat(), end_ts.isoformat()),
        ).fetchall()
        candles_15m_rows: list[dict[str, Any]] = []
        candles_1h_rows: list[dict[str, Any]] = []
        candles_4h_rows: list[dict[str, Any]] = []
        candles_15m_times: list[datetime] = []
        candles_1h_times: list[datetime] = []
        candles_4h_times: list[datetime] = []
        for row in candle_rows:
            parsed = {
                "open_time": _parse_timestamp(row["open_time"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            timeframe = row["timeframe"]
            if timeframe == "15m":
                candles_15m_rows.append(parsed)
                candles_15m_times.append(parsed["open_time"])
            elif timeframe == "1h":
                candles_1h_rows.append(parsed)
                candles_1h_times.append(parsed["open_time"])
            elif timeframe == "4h":
                candles_4h_rows.append(parsed)
                candles_4h_times.append(parsed["open_time"])

        funding_rows = self.connection.execute(
            """
            SELECT funding_time, funding_rate
            FROM funding
            WHERE symbol = ?
              AND funding_time <= ?
            ORDER BY funding_time ASC
            """,
            (symbol, end_ts.isoformat()),
        ).fetchall()
        funding_series_rows: list[dict[str, Any]] = []
        funding_series_times: list[datetime] = []
        for row in funding_rows:
            funding_time = _parse_timestamp(row["funding_time"])
            funding_series_times.append(funding_time)
            funding_series_rows.append(
                {
                    "funding_time": funding_time,
                    "funding_rate": float(row["funding_rate"]),
                }
            )

        open_interest_rows = self.connection.execute(
            """
            SELECT timestamp, oi_value
            FROM open_interest
            WHERE symbol = ?
              AND timestamp <= ?
            ORDER BY timestamp ASC
            """,
            (symbol, end_ts.isoformat()),
        ).fetchall()
        open_interest_timestamps = [_parse_timestamp(row["timestamp"]) for row in open_interest_rows]
        open_interest_values = [float(row["oi_value"]) for row in open_interest_rows]

        agg_rows = self.connection.execute(
            """
            SELECT bucket_time, timeframe, taker_buy_volume, taker_sell_volume, tfi, cvd
            FROM aggtrade_buckets
            WHERE symbol = ?
              AND timeframe IN ('15m', '60s')
              AND bucket_time <= ?
            ORDER BY timeframe ASC, bucket_time ASC
            """,
            (symbol, end_ts.isoformat()),
        ).fetchall()
        agg_15m_rows: list[dict[str, Any]] = []
        agg_60s_rows: list[dict[str, Any]] = []
        agg_15m_times: list[datetime] = []
        agg_60s_times: list[datetime] = []
        agg_15m_exact: dict[datetime, dict[str, Any]] = {}
        agg_60s_exact: dict[datetime, dict[str, Any]] = {}
        for row in agg_rows:
            bucket_time = _parse_timestamp(row["bucket_time"])
            parsed = {
                "bucket_time": bucket_time,
                "taker_buy_volume": float(row["taker_buy_volume"]),
                "taker_sell_volume": float(row["taker_sell_volume"]),
                "tfi": float(row["tfi"]),
                "cvd": float(row["cvd"]),
            }
            timeframe = row["timeframe"]
            if timeframe == "15m":
                agg_15m_rows.append(parsed)
                agg_15m_times.append(bucket_time)
                agg_15m_exact[bucket_time] = parsed
            elif timeframe == "60s":
                agg_60s_rows.append(parsed)
                agg_60s_times.append(bucket_time)
                agg_60s_exact[bucket_time] = parsed

        force_orders_rows = self.connection.execute(
            """
            SELECT event_time, side, qty, price
            FROM force_orders
            WHERE symbol = ?
              AND event_time > ?
              AND event_time <= ?
            ORDER BY event_time ASC
            """,
            (symbol, (start_ts - timedelta(seconds=60)).isoformat(), end_ts.isoformat()),
        ).fetchall()
        force_orders_series_rows: list[dict[str, Any]] = []
        force_orders_series_times: list[datetime] = []
        for row in force_orders_rows:
            event_time = _parse_timestamp(row["event_time"])
            force_orders_series_times.append(event_time)
            force_orders_series_rows.append(
                {
                    "event_time": event_time,
                    "side": row["side"],
                    "qty": float(row["qty"]),
                    "price": float(row["price"]),
                }
            )

        bias_rows = self.connection.execute(
            """
            SELECT date, etf_bias_5d, dxy_close
            FROM daily_external_bias
            WHERE date <= ?
            ORDER BY date ASC
            """,
            (end_ts.date().isoformat(),),
        ).fetchall()
        bias_dates: list[date] = []
        bias_values: list[tuple[float | None, float | None]] = []
        for row in bias_rows:
            bias_dates.append(date.fromisoformat(row["date"]))
            bias_values.append(
                (
                    float(row["etf_bias_5d"]) if row["etf_bias_5d"] is not None else None,
                    float(row["dxy_close"]) if row["dxy_close"] is not None else None,
                )
            )

        return _PreloadedReplayData(
            candles_15m=_ReplaySeries(timestamps=candles_15m_times, rows=candles_15m_rows),
            candles_1h=_ReplaySeries(timestamps=candles_1h_times, rows=candles_1h_rows),
            candles_4h=_ReplaySeries(timestamps=candles_4h_times, rows=candles_4h_rows),
            funding=_ReplaySeries(timestamps=funding_series_times, rows=funding_series_rows),
            open_interest_timestamps=open_interest_timestamps,
            open_interest_values=open_interest_values,
            agg_15m=_ReplaySeries(timestamps=agg_15m_times, rows=agg_15m_rows),
            agg_60s=_ReplaySeries(timestamps=agg_60s_times, rows=agg_60s_rows),
            agg_15m_exact=agg_15m_exact,
            agg_60s_exact=agg_60s_exact,
            force_orders=_ReplaySeries(timestamps=force_orders_series_times, rows=force_orders_series_rows),
            bias_dates=bias_dates,
            bias_values=bias_values,
        )

    @staticmethod
    def _slice_lookback(series: _ReplaySeries, *, up_to_time: datetime, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        upper = bisect_right(series.timestamps, up_to_time)
        lower = max(0, upper - int(limit))
        return [row.copy() for row in series.rows[lower:upper]]

    @staticmethod
    def _open_interest(preloaded: _PreloadedReplayData, *, up_to_time: datetime) -> float:
        index = bisect_right(preloaded.open_interest_timestamps, up_to_time) - 1
        if index < 0:
            return 0.0
        return float(preloaded.open_interest_values[index])

    @staticmethod
    def _resolve_agg_bucket(
        *,
        symbol: str,
        timeframe: str,
        at_time: datetime,
        fallback_time: datetime,
        exact_index: dict[datetime, dict[str, Any]],
        series: _ReplaySeries,
    ) -> dict[str, Any]:
        row = exact_index.get(at_time)
        if row is None:
            index = bisect_right(series.timestamps, fallback_time) - 1
            if index < 0:
                return {}
            row = series.rows[index]
        return {
            "symbol": symbol,
            "bucket_time": row["bucket_time"],
            "timeframe": timeframe,
            "taker_buy_volume": row["taker_buy_volume"],
            "taker_sell_volume": row["taker_sell_volume"],
            "tfi": row["tfi"],
            "cvd": row["cvd"],
        }

    @staticmethod
    def _force_orders_window(series: _ReplaySeries, *, end_time: datetime) -> list[dict[str, Any]]:
        start_time = end_time - timedelta(seconds=60)
        lower = bisect_right(series.timestamps, start_time)
        upper = bisect_right(series.timestamps, end_time)
        return [row.copy() for row in series.rows[lower:upper]]

    @staticmethod
    def _external_bias(preloaded: _PreloadedReplayData, *, at_time: datetime) -> tuple[float | None, float | None]:
        index = bisect_right(preloaded.bias_dates, at_time.date()) - 1
        if index < 0:
            return None, None
        return preloaded.bias_values[index]


def _as_utc_datetime(value: datetime | date | str) -> datetime:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    elif isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        raise TypeError(f"Unsupported date value type: {type(value)!r}")

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_timestamp(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _floor_60s(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(second=0, microsecond=0)

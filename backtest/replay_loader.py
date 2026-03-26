from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterator

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
        candle_rows = self.connection.execute(
            """
            SELECT open_time, open, high, low, close, volume
            FROM candles
            WHERE symbol = ?
              AND timeframe = '15m'
            ORDER BY open_time ASC
            """,
            (symbol_upper,),
        ).fetchall()

        for row in candle_rows:
            candle_open_time = _parse_timestamp(row["open_time"])
            snapshot_ts = candle_open_time + timedelta(minutes=15)
            if snapshot_ts < start_ts or snapshot_ts > end_ts:
                continue

            close_price = float(row["close"])
            candles_15m = self._load_candles(
                symbol=symbol_upper,
                timeframe="15m",
                limit=self.config.candles_15m_lookback,
                up_to_time=candle_open_time,
            )
            candles_1h = self._load_candles(
                symbol=symbol_upper,
                timeframe="1h",
                limit=self.config.candles_1h_lookback,
                up_to_time=snapshot_ts,
            )
            candles_4h = self._load_candles(
                symbol=symbol_upper,
                timeframe="4h",
                limit=self.config.candles_4h_lookback,
                up_to_time=snapshot_ts,
            )
            funding_history = self._load_funding(
                symbol=symbol_upper,
                up_to_time=snapshot_ts,
                limit=self.config.funding_lookback,
            )
            agg_15m = self._load_agg_bucket(
                symbol=symbol_upper,
                timeframe="15m",
                at_time=candle_open_time,
                fallback_time=snapshot_ts,
            )
            agg_60s = self._load_agg_bucket(
                symbol=symbol_upper,
                timeframe="60s",
                at_time=_floor_60s(snapshot_ts - timedelta(seconds=1)),
                fallback_time=snapshot_ts,
            )
            force_orders_60s = self._load_force_orders_window(
                symbol=symbol_upper,
                end_time=snapshot_ts,
            )
            etf_bias_daily, dxy_daily = self._load_external_bias(snapshot_ts)

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
                open_interest=self._load_open_interest(symbol=symbol_upper, up_to_time=snapshot_ts),
                aggtrades_bucket_60s=agg_60s,
                aggtrades_bucket_15m=agg_15m,
                force_order_events_60s=force_orders_60s,
                etf_bias_daily=etf_bias_daily,
                dxy_daily=dxy_daily,
            )

    def _load_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
        up_to_time: datetime,
    ) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT open_time, open, high, low, close, volume
            FROM candles
            WHERE symbol = ?
              AND timeframe = ?
              AND open_time <= ?
            ORDER BY open_time DESC
            LIMIT ?
            """,
            (symbol, timeframe, up_to_time.isoformat(), int(limit)),
        ).fetchall()
        result = [
            {
                "open_time": _parse_timestamp(row["open_time"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            for row in reversed(rows)
        ]
        return result

    def _load_funding(self, *, symbol: str, up_to_time: datetime, limit: int) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT funding_time, funding_rate
            FROM funding
            WHERE symbol = ?
              AND funding_time <= ?
            ORDER BY funding_time DESC
            LIMIT ?
            """,
            (symbol, up_to_time.isoformat(), int(limit)),
        ).fetchall()
        return [
            {
                "funding_time": _parse_timestamp(row["funding_time"]),
                "funding_rate": float(row["funding_rate"]),
            }
            for row in reversed(rows)
        ]

    def _load_open_interest(self, *, symbol: str, up_to_time: datetime) -> float:
        row = self.connection.execute(
            """
            SELECT oi_value
            FROM open_interest
            WHERE symbol = ?
              AND timestamp <= ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (symbol, up_to_time.isoformat()),
        ).fetchone()
        if row is None:
            return 0.0
        return float(row["oi_value"])

    def _load_agg_bucket(
        self,
        *,
        symbol: str,
        timeframe: str,
        at_time: datetime,
        fallback_time: datetime,
    ) -> dict:
        exact = self.connection.execute(
            """
            SELECT bucket_time, taker_buy_volume, taker_sell_volume, tfi, cvd
            FROM aggtrade_buckets
            WHERE symbol = ?
              AND timeframe = ?
              AND bucket_time = ?
            LIMIT 1
            """,
            (symbol, timeframe, at_time.isoformat()),
        ).fetchone()
        row = exact
        if row is None:
            row = self.connection.execute(
                """
                SELECT bucket_time, taker_buy_volume, taker_sell_volume, tfi, cvd
                FROM aggtrade_buckets
                WHERE symbol = ?
                  AND timeframe = ?
                  AND bucket_time <= ?
                ORDER BY bucket_time DESC
                LIMIT 1
                """,
                (symbol, timeframe, fallback_time.isoformat()),
            ).fetchone()
        if row is None:
            return {}
        return {
            "symbol": symbol,
            "bucket_time": _parse_timestamp(row["bucket_time"]),
            "timeframe": timeframe,
            "taker_buy_volume": float(row["taker_buy_volume"]),
            "taker_sell_volume": float(row["taker_sell_volume"]),
            "tfi": float(row["tfi"]),
            "cvd": float(row["cvd"]),
        }

    def _load_force_orders_window(self, *, symbol: str, end_time: datetime) -> list[dict]:
        start_time = end_time - timedelta(seconds=60)
        rows = self.connection.execute(
            """
            SELECT event_time, side, qty, price
            FROM force_orders
            WHERE symbol = ?
              AND event_time > ?
              AND event_time <= ?
            ORDER BY event_time ASC
            """,
            (symbol, start_time.isoformat(), end_time.isoformat()),
        ).fetchall()
        return [
            {
                "event_time": _parse_timestamp(row["event_time"]),
                "side": row["side"],
                "qty": float(row["qty"]),
                "price": float(row["price"]),
            }
            for row in rows
        ]

    def _load_external_bias(self, at_time: datetime) -> tuple[float | None, float | None]:
        row = self.connection.execute(
            """
            SELECT etf_bias_5d, dxy_close
            FROM daily_external_bias
            WHERE date <= ?
            ORDER BY date DESC
            LIMIT 1
            """,
            (at_time.date().isoformat(),),
        ).fetchone()
        if row is None:
            return None, None
        etf_bias = float(row["etf_bias_5d"]) if row["etf_bias_5d"] is not None else None
        dxy_close = float(row["dxy_close"]) if row["dxy_close"] is not None else None
        return etf_bias, dxy_close


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

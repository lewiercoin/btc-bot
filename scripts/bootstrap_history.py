from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.rest_client import BinanceFuturesRestClient, RestClientConfig, RestClientError
from settings import load_settings
from storage.db import connect, init_db

LOG = logging.getLogger(__name__)


def _bucket_seconds(timeframe: str) -> int:
    if timeframe == "60s":
        return 60
    if timeframe == "15m":
        return 15 * 60
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def _bucket_floor(ts: datetime, timeframe: str) -> datetime:
    bucket = _bucket_seconds(timeframe)
    unix = int(ts.timestamp())
    floored = unix - (unix % bucket)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def build_aggtrade_buckets(trades: list[dict], symbol: str, timeframe: str) -> list[dict]:
    groups: dict[datetime, list[dict]] = defaultdict(list)
    for trade in trades:
        groups[_bucket_floor(trade["event_time"], timeframe)].append(trade)

    buckets: list[dict] = []
    for bucket_time, group in groups.items():
        taker_buy_volume = 0.0
        taker_sell_volume = 0.0
        for trade in group:
            qty = float(trade["qty"])
            if bool(trade["is_buyer_maker"]):
                taker_sell_volume += qty
            else:
                taker_buy_volume += qty
        total = taker_buy_volume + taker_sell_volume
        cvd = taker_buy_volume - taker_sell_volume
        tfi = 0.0 if total == 0 else cvd / total
        buckets.append(
            {
                "symbol": symbol.upper(),
                "bucket_time": bucket_time,
                "timeframe": timeframe,
                "taker_buy_volume": taker_buy_volume,
                "taker_sell_volume": taker_sell_volume,
                "tfi": tfi,
                "cvd": cvd,
            }
        )

    buckets.sort(key=lambda item: item["bucket_time"])
    return buckets


def upsert_candles(conn: sqlite3.Connection, candles: list[dict]) -> int:
    conn.executemany(
        """
        INSERT INTO candles (symbol, timeframe, open_time, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, timeframe, open_time) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume
        """,
        [
            (
                item["symbol"],
                item["timeframe"],
                item["open_time"].isoformat(),
                item["open"],
                item["high"],
                item["low"],
                item["close"],
                item["volume"],
            )
            for item in candles
        ],
    )
    return len(candles)


def upsert_funding(conn: sqlite3.Connection, rows: list[dict]) -> int:
    conn.executemany(
        """
        INSERT INTO funding (symbol, funding_time, funding_rate)
        VALUES (?, ?, ?)
        ON CONFLICT(symbol, funding_time) DO UPDATE SET
            funding_rate = excluded.funding_rate
        """,
        [(item["symbol"], item["funding_time"].isoformat(), item["funding_rate"]) for item in rows],
    )
    return len(rows)


def upsert_open_interest(conn: sqlite3.Connection, rows: list[dict]) -> int:
    conn.executemany(
        """
        INSERT INTO open_interest (symbol, timestamp, oi_value)
        VALUES (?, ?, ?)
        ON CONFLICT(symbol, timestamp) DO UPDATE SET
            oi_value = excluded.oi_value
        """,
        [(item["symbol"], item["timestamp"].isoformat(), item["oi_value"]) for item in rows],
    )
    return len(rows)


def upsert_aggtrade_buckets(conn: sqlite3.Connection, rows: list[dict]) -> int:
    conn.executemany(
        """
        INSERT INTO aggtrade_buckets (
            symbol, bucket_time, timeframe, taker_buy_volume, taker_sell_volume, tfi, cvd
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, timeframe, bucket_time) DO UPDATE SET
            taker_buy_volume = excluded.taker_buy_volume,
            taker_sell_volume = excluded.taker_sell_volume,
            tfi = excluded.tfi,
            cvd = excluded.cvd
        """,
        [
            (
                item["symbol"],
                item["bucket_time"].isoformat(),
                item["timeframe"],
                item["taker_buy_volume"],
                item["taker_sell_volume"],
                item["tfi"],
                item["cvd"],
            )
            for item in rows
        ],
    )
    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap market history into SQLite.")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--limit-candles", type=int, default=500)
    parser.add_argument("--limit-funding", type=int, default=300)
    parser.add_argument("--limit-open-interest", type=int, default=200)
    parser.add_argument("--limit-aggtrades", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    settings = load_settings()
    assert settings.storage is not None
    symbol = (args.symbol or settings.strategy.symbol).upper()

    conn = connect(settings.storage.db_path)
    init_db(conn, settings.storage.schema_path)
    rest_client = BinanceFuturesRestClient(
        RestClientConfig(
            base_url=settings.exchange.futures_rest_base_url,
            timeout_seconds=settings.execution.rest_timeout_seconds,
            max_retries=3,
            retry_backoff_seconds=0.75,
        )
    )

    try:
        candles_15m = rest_client.fetch_klines(symbol, "15m", limit=args.limit_candles)
        candles_1h = rest_client.fetch_klines(symbol, "1h", limit=args.limit_candles)
        candles_4h = rest_client.fetch_klines(symbol, "4h", limit=args.limit_candles)
        funding = rest_client.fetch_funding_history(symbol, limit=args.limit_funding)
        agg_trades = rest_client.fetch_agg_trades(symbol, limit=args.limit_aggtrades)

        try:
            open_interest = rest_client.fetch_open_interest_history(symbol, period="5m", limit=args.limit_open_interest)
        except RestClientError:
            LOG.warning("openInterestHist unavailable; using single openInterest snapshot.")
            open_interest = [rest_client.fetch_open_interest(symbol)]
    except RestClientError as exc:
        raise SystemExit(f"Bootstrap failed due to REST error: {exc}") from exc

    bucket_60s = build_aggtrade_buckets(agg_trades, symbol=symbol, timeframe="60s")
    bucket_15m = build_aggtrade_buckets(agg_trades, symbol=symbol, timeframe="15m")

    LOG.info(
        "Fetched: candles15m=%s candles1h=%s candles4h=%s funding=%s oi=%s agg_trades=%s bucket60=%s bucket15m=%s",
        len(candles_15m),
        len(candles_1h),
        len(candles_4h),
        len(funding),
        len(open_interest),
        len(agg_trades),
        len(bucket_60s),
        len(bucket_15m),
    )

    if args.dry_run:
        LOG.info("Dry-run mode: no database write.")
        return

    written_candles = upsert_candles(conn, candles_15m + candles_1h + candles_4h)
    written_funding = upsert_funding(conn, funding)
    written_oi = upsert_open_interest(conn, open_interest)
    written_agg = upsert_aggtrade_buckets(conn, bucket_60s + bucket_15m)
    conn.commit()

    LOG.info(
        "Bootstrap written: candles=%s funding=%s open_interest=%s aggtrade_buckets=%s",
        written_candles,
        written_funding,
        written_oi,
        written_agg,
    )


if __name__ == "__main__":
    main()

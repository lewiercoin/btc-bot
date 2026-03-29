from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

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


def _kline_interval_seconds(interval: str) -> int:
    token = interval.strip().lower()
    if len(token) < 2:
        raise ValueError(f"Invalid interval: {interval!r}")
    unit = token[-1]
    amount = int(token[:-1])
    if amount <= 0:
        raise ValueError(f"Invalid interval amount: {interval!r}")
    if unit == "s":
        return amount
    if unit == "m":
        return amount * 60
    if unit == "h":
        return amount * 3600
    if unit == "d":
        return amount * 86400
    if unit == "w":
        return amount * 7 * 86400
    raise ValueError(f"Unsupported interval unit: {interval!r}")


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_ms(value: datetime) -> int:
    return int(_to_utc(value).timestamp() * 1000)


def _is_date_only(raw: str) -> bool:
    token = raw.strip()
    return "T" not in token and " " not in token


def _parse_iso_datetime(raw: str, *, is_end: bool) -> datetime:
    parsed = datetime.fromisoformat(raw)
    value = _to_utc(parsed)
    if is_end and _is_date_only(raw):
        value += timedelta(days=1)
    return value


def _sleep_ms(ms: int) -> None:
    if ms > 0:
        time.sleep(ms / 1000.0)


def _is_rate_limit_error(exc: RestClientError) -> bool:
    message = str(exc)
    return "code=-1003" in message or "Too many requests" in message


def _call_with_rate_limit_retry(
    fn: Callable[[], Any],
    *,
    sleep_ms: int,
    context: str,
    max_attempts: int = 6,
) -> Any:
    last_error: RestClientError | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except RestClientError as exc:
            if not _is_rate_limit_error(exc):
                raise
            last_error = exc
            wait_ms = max(int(sleep_ms), 200) * (attempt + 1) * 5
            LOG.warning("Rate limited during %s (attempt %s/%s). Sleeping %sms.", context, attempt + 1, max_attempts, wait_ms)
            _sleep_ms(wait_ms)
    if last_error is not None:
        raise last_error
    raise RestClientError(f"Rate-limited call failed without explicit exception for context={context!r}.")


def _dedupe_rows(rows: Iterable[dict[str, Any]], key_fn: Callable[[dict[str, Any]], tuple[Any, ...]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        deduped[key_fn(row)] = row
    return list(deduped.values())


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


def fetch_klines_paginated(
    rest_client: BinanceFuturesRestClient,
    *,
    symbol: str,
    interval: str,
    start_ts: datetime,
    end_ts: datetime,
    limit: int,
    sleep_ms: int,
) -> list[dict[str, Any]]:
    start_ms = _to_ms(start_ts)
    end_ms = _to_ms(end_ts)
    interval_ms = _kline_interval_seconds(interval) * 1000
    cursor_ms = start_ms
    result: list[dict[str, Any]] = []

    while cursor_ms < end_ms:
        batch = _call_with_rate_limit_retry(
            lambda: rest_client.fetch_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                start_time_ms=cursor_ms,
                end_time_ms=end_ms - 1,
            ),
            sleep_ms=sleep_ms,
            context=f"fetch_klines[{interval}]",
        )
        if not batch:
            break
        result.extend(batch)
        last_open_ms = _to_ms(batch[-1]["open_time"])
        next_cursor = last_open_ms + interval_ms
        if next_cursor <= cursor_ms:
            break
        cursor_ms = next_cursor
        _sleep_ms(sleep_ms)

    in_range = [row for row in result if start_ts <= row["open_time"] < end_ts]
    deduped = _dedupe_rows(
        in_range,
        key_fn=lambda item: (item["symbol"], item["timeframe"], item["open_time"].isoformat()),
    )
    deduped.sort(key=lambda item: item["open_time"])
    return deduped


_OI_MAX_LOOKBACK_DAYS = 27


def fetch_open_interest_paginated(
    rest_client: BinanceFuturesRestClient,
    *,
    symbol: str,
    start_ts: datetime,
    end_ts: datetime,
    period: str,
    limit: int,
    sleep_ms: int,
) -> list[dict[str, Any]]:
    """Fetch OI history with automatic clipping to Binance's ~27-day lookback limit."""
    now_utc = datetime.now(timezone.utc)
    earliest_available = now_utc - timedelta(days=_OI_MAX_LOOKBACK_DAYS)

    if end_ts <= earliest_available:
        LOG.warning(
            "OI range %s..%s is entirely beyond Binance %d-day lookback. Skipping.",
            start_ts.isoformat(), end_ts.isoformat(), _OI_MAX_LOOKBACK_DAYS,
        )
        return []

    effective_start = max(start_ts, earliest_available)
    if effective_start != start_ts:
        LOG.warning(
            "OI start clipped from %s to %s (Binance %d-day lookback limit).",
            start_ts.isoformat(), effective_start.isoformat(), _OI_MAX_LOOKBACK_DAYS,
        )

    start_ms = _to_ms(effective_start)
    end_ms = _to_ms(end_ts)
    cursor_ms = start_ms
    result: list[dict[str, Any]] = []

    while cursor_ms < end_ms:
        _cursor_ms = cursor_ms
        _end_ms = end_ms
        batch = _call_with_rate_limit_retry(
            lambda: rest_client.fetch_open_interest_history(
                symbol=symbol,
                period=period,
                limit=limit,
                start_time_ms=_cursor_ms,
                end_time_ms=_end_ms - 1,
            ),
            sleep_ms=sleep_ms,
            context=f"fetch_open_interest_history[{period}]",
        )
        if not batch:
            break
        result.extend(batch)
        last_ts_ms = _to_ms(batch[-1]["timestamp"])
        if len(batch) < limit or last_ts_ms >= (end_ms - 1):
            break
        next_cursor = last_ts_ms + 1
        if next_cursor <= cursor_ms:
            break
        cursor_ms = next_cursor
        _sleep_ms(sleep_ms)

    in_range = [row for row in result if effective_start <= row["timestamp"] < end_ts]
    deduped = _dedupe_rows(
        in_range,
        key_fn=lambda item: (item["symbol"], item["timestamp"].isoformat()),
    )
    deduped.sort(key=lambda item: item["timestamp"])
    return deduped


def fetch_aggtrade_buckets_paginated(
    rest_client: BinanceFuturesRestClient,
    *,
    symbol: str,
    start_ts: datetime,
    end_ts: datetime,
    limit: int,
    sleep_ms: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    start_ms = _to_ms(start_ts)
    end_ms = _to_ms(end_ts)
    window_ms = 60 * 60 * 1000

    buckets_60s: list[dict[str, Any]] = []
    buckets_15m: list[dict[str, Any]] = []
    total_trades = 0

    window_start = start_ms
    while window_start < end_ms:
        window_end = min(window_start + window_ms, end_ms)
        cursor_ms = window_start
        window_trades: list[dict[str, Any]] = []

        while cursor_ms < window_end:
            batch = _call_with_rate_limit_retry(
                lambda: rest_client.fetch_agg_trades(
                    symbol=symbol,
                    limit=limit,
                    start_time_ms=cursor_ms,
                    end_time_ms=window_end - 1,
                ),
                sleep_ms=sleep_ms,
                context="fetch_agg_trades",
            )
            if not batch:
                break
            window_trades.extend(batch)
            total_trades += len(batch)

            last_event_ms = _to_ms(batch[-1]["event_time"])
            if len(batch) < limit or last_event_ms >= (window_end - 1):
                break
            next_cursor = last_event_ms + 1
            if next_cursor <= cursor_ms:
                break
            cursor_ms = next_cursor
            _sleep_ms(sleep_ms)

        if window_trades:
            buckets_60s.extend(build_aggtrade_buckets(window_trades, symbol=symbol, timeframe="60s"))
            buckets_15m.extend(build_aggtrade_buckets(window_trades, symbol=symbol, timeframe="15m"))
        window_start = window_end

    deduped_60s = _dedupe_rows(
        buckets_60s,
        key_fn=lambda item: (item["symbol"], item["timeframe"], item["bucket_time"].isoformat()),
    )
    deduped_15m = _dedupe_rows(
        buckets_15m,
        key_fn=lambda item: (item["symbol"], item["timeframe"], item["bucket_time"].isoformat()),
    )
    deduped_60s.sort(key=lambda item: item["bucket_time"])
    deduped_15m.sort(key=lambda item: item["bucket_time"])
    return deduped_60s, deduped_15m, total_trades


def iter_aggtrade_windows(
    rest_client: BinanceFuturesRestClient,
    *,
    symbol: str,
    start_ts: datetime,
    end_ts: datetime,
    limit: int,
    sleep_ms: int,
) -> Iterator[tuple[list[dict[str, Any]], list[dict[str, Any]], int]]:
    window_start = _to_utc(start_ts)
    end_utc = _to_utc(end_ts)

    while window_start < end_utc:
        window_end = min(window_start + timedelta(hours=1), end_utc)
        buckets_60s, buckets_15m, trade_count = fetch_aggtrade_buckets_paginated(
            rest_client,
            symbol=symbol,
            start_ts=window_start,
            end_ts=window_end,
            limit=limit,
            sleep_ms=sleep_ms,
        )
        yield buckets_60s, buckets_15m, trade_count
        window_start = window_end


def fetch_funding_paginated(
    rest_client: BinanceFuturesRestClient,
    *,
    symbol: str,
    start_ts: datetime,
    end_ts: datetime,
    limit: int,
    sleep_ms: int,
) -> list[dict[str, Any]]:
    """Fetch funding rate history with pagination using startTime/endTime."""
    start_ms = _to_ms(start_ts)
    end_ms = _to_ms(end_ts)
    cursor_ms = start_ms
    result: list[dict[str, Any]] = []

    while cursor_ms < end_ms:
        _cursor_ms = cursor_ms
        _end_ms = end_ms
        batch = _call_with_rate_limit_retry(
            lambda: rest_client.fetch_funding_history(
                symbol=symbol,
                limit=limit,
                start_time_ms=_cursor_ms,
                end_time_ms=_end_ms - 1,
            ),
            sleep_ms=sleep_ms,
            context="fetch_funding_history",
        )
        if not batch:
            break
        result.extend(batch)
        last_ts_ms = _to_ms(batch[-1]["funding_time"])
        if len(batch) < limit or last_ts_ms >= (end_ms - 1):
            break
        next_cursor = last_ts_ms + 1
        if next_cursor <= cursor_ms:
            break
        cursor_ms = next_cursor
        _sleep_ms(sleep_ms)

    in_range = [row for row in result if start_ts <= row["funding_time"] < end_ts]
    deduped = _dedupe_rows(
        in_range,
        key_fn=lambda item: (item["symbol"], item["funding_time"].isoformat()),
    )
    deduped.sort(key=lambda item: item["funding_time"])
    return deduped


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
    parser = argparse.ArgumentParser(description="Bootstrap paginated market history into SQLite.")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--start-date", default=None, help="Inclusive start datetime (ISO-8601, UTC).")
    parser.add_argument("--end-date", default=None, help="Exclusive end datetime (ISO-8601, UTC). Date-only values are treated as next-day exclusive.")
    parser.add_argument("--sleep-ms", type=int, default=200, help="Sleep between paginated API calls.")
    parser.add_argument("--limit-candles", type=int, default=1000, help="Per-call kline limit.")
    parser.add_argument("--limit-funding", type=int, default=300, help="Funding history fetch limit.")
    parser.add_argument("--limit-open-interest", type=int, default=500, help="Per-call open interest history limit.")
    parser.add_argument("--limit-aggtrades", type=int, default=1000, help="Per-call agg trades limit.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _resolve_range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    if args.start_date is None and args.end_date is None:
        end_ts = datetime.now(timezone.utc)
        start_ts = end_ts - timedelta(days=30)
        return start_ts, end_ts
    if args.start_date is None or args.end_date is None:
        raise ValueError("Both --start-date and --end-date are required when one is provided.")
    start_ts = _parse_iso_datetime(str(args.start_date), is_end=False)
    end_ts = _parse_iso_datetime(str(args.end_date), is_end=True)
    if end_ts <= start_ts:
        raise ValueError("--end-date must be later than --start-date.")
    return start_ts, end_ts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    settings = load_settings()
    assert settings.storage is not None
    symbol = (args.symbol or settings.strategy.symbol).upper()
    start_ts, end_ts = _resolve_range(args)

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

    LOG.info(
        "Bootstrap range: symbol=%s start=%s end=%s sleep_ms=%s",
        symbol,
        start_ts.isoformat(),
        end_ts.isoformat(),
        int(args.sleep_ms),
    )

    candle_written_by_interval: dict[str, int] = {}
    funding_written = 0
    oi_written = 0
    agg_written_total = 0
    agg_trade_total = 0
    agg_windows_total = 0

    try:
        for interval in ("15m", "1h", "4h"):
            candles = fetch_klines_paginated(
                rest_client,
                symbol=symbol,
                interval=interval,
                start_ts=start_ts,
                end_ts=end_ts,
                limit=int(args.limit_candles),
                sleep_ms=int(args.sleep_ms),
            )
            if args.dry_run:
                candle_written_by_interval[interval] = len(candles)
                LOG.info(
                    "Dry-run candles[%s]: fetched=%s range=%s..%s",
                    interval,
                    len(candles),
                    start_ts.isoformat(),
                    end_ts.isoformat(),
                )
            else:
                written = upsert_candles(conn, candles)
                conn.commit()
                candle_written_by_interval[interval] = written
                LOG.info(
                    "Committed candles[%s]: wrote=%s range=%s..%s",
                    interval,
                    written,
                    start_ts.isoformat(),
                    end_ts.isoformat(),
                )

        funding = fetch_funding_paginated(
            rest_client,
            symbol=symbol,
            start_ts=start_ts,
            end_ts=end_ts,
            limit=int(args.limit_funding),
            sleep_ms=int(args.sleep_ms),
        )
        if args.dry_run:
            funding_written = len(funding)
            LOG.info(
                "Dry-run funding: fetched=%s range=%s..%s",
                len(funding),
                start_ts.isoformat(),
                end_ts.isoformat(),
            )
        else:
            funding_written = upsert_funding(conn, funding)
            conn.commit()
            LOG.info(
                "Committed funding: wrote=%s range=%s..%s",
                funding_written,
                start_ts.isoformat(),
                end_ts.isoformat(),
            )

        open_interest = fetch_open_interest_paginated(
            rest_client,
            symbol=symbol,
            start_ts=start_ts,
            end_ts=end_ts,
            period="5m",
            limit=int(args.limit_open_interest),
            sleep_ms=int(args.sleep_ms),
        )
        if args.dry_run:
            oi_written = len(open_interest)
            LOG.info(
                "Dry-run open_interest: fetched=%s range=%s..%s",
                len(open_interest),
                start_ts.isoformat(),
                end_ts.isoformat(),
            )
        else:
            oi_written = upsert_open_interest(conn, open_interest)
            conn.commit()
            LOG.info(
                "Committed open_interest: wrote=%s range=%s..%s",
                oi_written,
                start_ts.isoformat(),
                end_ts.isoformat(),
            )

        window_start = start_ts
        for bucket_60s, bucket_15m, trade_count in iter_aggtrade_windows(
            rest_client,
            symbol=symbol,
            start_ts=start_ts,
            end_ts=end_ts,
            limit=int(args.limit_aggtrades),
            sleep_ms=int(args.sleep_ms),
        ):
            window_end = min(window_start + timedelta(hours=1), end_ts)
            rows = bucket_60s + bucket_15m
            if args.dry_run:
                written_window = len(rows)
                LOG.info(
                    "Dry-run aggtrades window: range=%s..%s fetched_buckets=%s trades=%s",
                    window_start.isoformat(),
                    window_end.isoformat(),
                    written_window,
                    trade_count,
                )
            else:
                written_window = upsert_aggtrade_buckets(conn, rows)
                conn.commit()
                LOG.info(
                    "Committed aggtrades window: range=%s..%s wrote_buckets=%s trades=%s",
                    window_start.isoformat(),
                    window_end.isoformat(),
                    written_window,
                    trade_count,
                )
            agg_written_total += written_window
            agg_trade_total += trade_count
            agg_windows_total += 1
            window_start = window_end
    except RestClientError as exc:
        raise SystemExit(f"Bootstrap failed due to REST error: {exc}") from exc
    finally:
        conn.close()

    LOG.info(
        "Bootstrap complete: dry_run=%s candles15m=%s candles1h=%s candles4h=%s funding=%s oi=%s aggtrade_buckets=%s aggtrade_trades=%s aggtrade_windows=%s",
        args.dry_run,
        candle_written_by_interval.get("15m", 0),
        candle_written_by_interval.get("1h", 0),
        candle_written_by_interval.get("4h", 0),
        funding_written,
        oi_written,
        agg_written_total,
        agg_trade_total,
        agg_windows_total,
    )


if __name__ == "__main__":
    main()

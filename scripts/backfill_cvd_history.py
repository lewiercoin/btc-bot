from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.proxy_transport import ProxyTransport
from data.rest_client import BinanceFuturesRestClient, RestClientConfig
from settings import AppSettings, load_settings
from storage.db import connect, init_db

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class CVDBackfillResult:
    symbol: str
    timeframe: str
    inserted_bars: int
    total_bars: int
    real_cvd_bars: int
    placeholder_bars: int
    oldest_bar_time: datetime | None
    newest_bar_time: datetime | None
    used_rest_klines: bool
    rest_error: str | None
    ready: bool


def run_backfill(
    *,
    conn: Any | None = None,
    settings: AppSettings | None = None,
    rest_client: Any | None = None,
    now: datetime | None = None,
    symbol: str | None = None,
    timeframe: str = "15m",
) -> CVDBackfillResult:
    settings = settings or load_settings()
    if settings.storage is None:
        raise RuntimeError("Storage settings are required for CVD backfill.")

    owns_conn = conn is None
    db_conn = conn or connect(settings.storage.db_path)
    try:
        init_db(db_conn, settings.storage.schema_path)
        ts_now = _to_utc(now or datetime.now(timezone.utc))
        target_symbol = (symbol or settings.strategy.symbol).upper()
        required_bars = max(int(settings.data_quality.cvd_divergence_bars), 1)
        captured_at = ts_now

        client = rest_client or _build_rest_client(settings)
        rest_error: str | None = None
        used_rest_klines = True
        try:
            bars = client.fetch_klines(target_symbol, timeframe, limit=required_bars)
        except Exception as exc:
            rest_error = str(exc)
            used_rest_klines = False
            LOG.warning("CVD kline REST backfill failed, falling back to local candles: %s", exc)
            bars = _fetch_local_candles(db_conn, symbol=target_symbol, timeframe=timeframe, limit=required_bars)

        if len(bars) < required_bars:
            raise RuntimeError(f"Only {len(bars)} {timeframe} price bars available; required {required_bars}.")

        inserted = 0
        real_cvd = 0
        placeholders = 0
        for bar in sorted(bars[-required_bars:], key=lambda item: str(item.get("open_time", ""))):
            bar_time = _to_utc(_parse_datetime(bar["open_time"]))
            flow = _fetch_matching_flow(db_conn, symbol=target_symbol, timeframe=timeframe, bar_time=bar_time)
            if flow:
                cvd = float(flow["cvd"])
                tfi = None if flow["tfi"] is None else float(flow["tfi"])
                real_cvd += 1
            else:
                cvd = 0.0
                tfi = None
                placeholders += 1
            inserted += _insert_cvd_bar(
                db_conn,
                symbol=target_symbol,
                timeframe=timeframe,
                bar_time=bar_time,
                price_close=float(bar["close"]),
                cvd=cvd,
                tfi=tfi,
                source="historical_backfill",
                captured_at=captured_at,
            )

        db_conn.commit()
        summary = summarize_readiness(
            db_conn,
            symbol=target_symbol,
            timeframe=timeframe,
            required_bars=required_bars,
        )
        result = CVDBackfillResult(
            symbol=target_symbol,
            timeframe=timeframe,
            inserted_bars=inserted,
            total_bars=summary["count"],
            real_cvd_bars=real_cvd,
            placeholder_bars=placeholders,
            oldest_bar_time=summary["oldest"],
            newest_bar_time=summary["newest"],
            used_rest_klines=used_rest_klines,
            rest_error=rest_error,
            ready=bool(summary["ready"]),
        )
        LOG.info(
            "CVD backfill complete | symbol=%s timeframe=%s inserted=%d total=%d real_cvd=%d placeholder=%d oldest=%s newest=%s ready=%s",
            result.symbol,
            result.timeframe,
            result.inserted_bars,
            result.total_bars,
            result.real_cvd_bars,
            result.placeholder_bars,
            result.oldest_bar_time.isoformat() if result.oldest_bar_time else None,
            result.newest_bar_time.isoformat() if result.newest_bar_time else None,
            result.ready,
        )
        return result
    except Exception:
        db_conn.rollback()
        raise
    finally:
        if owns_conn:
            db_conn.close()


def summarize_readiness(
    conn: Any,
    *,
    symbol: str,
    timeframe: str,
    required_bars: int,
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS count, MIN(bar_time) AS oldest, MAX(bar_time) AS newest
        FROM cvd_price_history
        WHERE symbol = ? AND timeframe = ?
        """,
        (symbol.upper(), timeframe),
    ).fetchone()
    count = int(row["count"] or 0) if row else 0
    return {
        "count": count,
        "oldest": _parse_optional_datetime(row["oldest"]) if row else None,
        "newest": _parse_optional_datetime(row["newest"]) if row else None,
        "required_bars": max(int(required_bars), 1),
        "ready": count >= max(int(required_bars), 1),
    }


def _fetch_local_candles(conn: Any, *, symbol: str, timeframe: str, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT symbol, timeframe, open_time, open, high, low, close, volume
        FROM candles
        WHERE symbol = ? AND timeframe = ?
        ORDER BY open_time DESC
        LIMIT ?
        """,
        (symbol.upper(), timeframe, max(int(limit), 1)),
    ).fetchall()
    return list(reversed([dict(row) for row in rows]))


def _fetch_matching_flow(conn: Any, *, symbol: str, timeframe: str, bar_time: datetime) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT cvd, tfi
        FROM aggtrade_buckets
        WHERE symbol = ? AND timeframe = ? AND bucket_time = ?
        LIMIT 1
        """,
        (symbol.upper(), timeframe, _format_datetime(bar_time)),
    ).fetchone()
    return dict(row) if row else None


def _insert_cvd_bar(
    conn: Any,
    *,
    symbol: str,
    timeframe: str,
    bar_time: datetime,
    price_close: float,
    cvd: float,
    tfi: float | None,
    source: str,
    captured_at: datetime,
) -> int:
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO cvd_price_history (
            symbol, timeframe, bar_time, price_close, cvd, tfi, source, captured_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            symbol.upper(),
            timeframe,
            _format_datetime(bar_time),
            float(price_close),
            float(cvd),
            None if tfi is None else float(tfi),
            source,
            _format_datetime(captured_at),
        ),
    )
    return max(int(cursor.rowcount or 0), 0)


def _build_rest_client(settings: AppSettings) -> BinanceFuturesRestClient:
    proxy_transport = None
    if settings.proxy.proxy_enabled and settings.proxy.proxy_url:
        proxy_transport = ProxyTransport(
            proxy_url=settings.proxy.proxy_url,
            proxy_type=settings.proxy.proxy_type,
            sticky_minutes=settings.proxy.sticky_minutes,
            failover_list=settings.proxy.failover_list,
        )
    return BinanceFuturesRestClient(
        RestClientConfig(
            base_url=settings.exchange.futures_rest_base_url,
            timeout_seconds=settings.execution.rest_timeout_seconds,
            api_key=settings.exchange.api_key,
            api_secret=settings.exchange.api_secret,
            recv_window_ms=settings.exchange.recv_window_ms,
            proxy_transport=proxy_transport,
        )
    )


def _parse_optional_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    return _to_utc(_parse_datetime(value))


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_datetime(value: datetime) -> str:
    return _to_utc(value).isoformat()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill cvd_price_history from fresh 15m klines.")
    parser.add_argument("--symbol", default=None, help="Trading symbol. Defaults to settings.strategy.symbol.")
    parser.add_argument("--timeframe", default="15m", help="Candle timeframe. Default: 15m.")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args()
    try:
        run_backfill(symbol=args.symbol, timeframe=args.timeframe)
    except Exception as exc:
        LOG.error("CVD backfill failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

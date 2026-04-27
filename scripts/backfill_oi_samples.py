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
class OIBackfillResult:
    symbol: str
    inserted_historical: int
    inserted_current: int
    current_error: str | None
    total_samples: int
    oldest_timestamp: datetime | None
    newest_timestamp: datetime | None
    days_covered: float
    ready: bool


def run_backfill(
    *,
    conn: Any | None = None,
    settings: AppSettings | None = None,
    rest_client: Any | None = None,
    now: datetime | None = None,
    symbol: str | None = None,
) -> OIBackfillResult:
    settings = settings or load_settings()
    if settings.storage is None:
        raise RuntimeError("Storage settings are required for OI backfill.")

    owns_conn = conn is None
    db_conn = conn or connect(settings.storage.db_path)
    try:
        init_db(db_conn, settings.storage.schema_path)
        ts_now = _to_utc(now or datetime.now(timezone.utc))
        target_symbol = (symbol or settings.strategy.symbol).upper()
        horizon = ts_now - _days_delta(settings.data_quality.oi_baseline_days)
        captured_at = ts_now

        inserted_historical = _copy_historical_open_interest(
            db_conn,
            symbol=target_symbol,
            horizon=horizon,
            captured_at=captured_at,
        )
        current_error: str | None = None
        inserted_current = 0
        client = rest_client or _build_rest_client(settings)
        try:
            current = client.fetch_open_interest(target_symbol)
            inserted_current = _insert_oi_sample(
                db_conn,
                symbol=target_symbol,
                timestamp=_to_utc(_parse_datetime(current["timestamp"])),
                oi_value=float(current["oi_value"]),
                source="rest_current_backfill",
                captured_at=captured_at,
            )
        except Exception as exc:
            current_error = str(exc)
            LOG.warning("Current OI REST backfill failed: %s", exc)

        db_conn.commit()
        summary = _summarize_oi_samples(db_conn, symbol=target_symbol, since_ts=horizon)
        result = OIBackfillResult(
            symbol=target_symbol,
            inserted_historical=inserted_historical,
            inserted_current=inserted_current,
            current_error=current_error,
            total_samples=summary["count"],
            oldest_timestamp=summary["oldest"],
            newest_timestamp=summary["newest"],
            days_covered=summary["days_covered"],
            ready=summary["count"] >= 2 and summary["days_covered"] >= float(settings.data_quality.oi_baseline_days),
        )
        LOG.info(
            "OI backfill complete | symbol=%s inserted_historical=%d inserted_current=%d total=%d oldest=%s newest=%s days_covered=%.2f ready=%s",
            result.symbol,
            result.inserted_historical,
            result.inserted_current,
            result.total_samples,
            result.oldest_timestamp.isoformat() if result.oldest_timestamp else None,
            result.newest_timestamp.isoformat() if result.newest_timestamp else None,
            result.days_covered,
            result.ready,
        )
        return result
    except Exception:
        db_conn.rollback()
        raise
    finally:
        if owns_conn:
            db_conn.close()


def _copy_historical_open_interest(conn: Any, *, symbol: str, horizon: datetime, captured_at: datetime) -> int:
    rows = conn.execute(
        """
        SELECT timestamp, oi_value
        FROM open_interest
        WHERE symbol = ? AND timestamp >= ?
        ORDER BY timestamp ASC
        """,
        (symbol.upper(), _format_datetime(horizon)),
    ).fetchall()
    inserted = 0
    for row in rows:
        inserted += _insert_oi_sample(
            conn,
            symbol=symbol,
            timestamp=_to_utc(_parse_datetime(row["timestamp"])),
            oi_value=float(row["oi_value"]),
            source="historical_backfill",
            captured_at=captured_at,
        )
    return inserted


def _insert_oi_sample(
    conn: Any,
    *,
    symbol: str,
    timestamp: datetime,
    oi_value: float,
    source: str,
    captured_at: datetime,
) -> int:
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO oi_samples (symbol, timestamp, oi_value, source, captured_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            symbol.upper(),
            _format_datetime(timestamp),
            float(oi_value),
            source,
            _format_datetime(captured_at),
        ),
    )
    return max(int(cursor.rowcount or 0), 0)


def summarize_readiness(
    conn: Any,
    *,
    symbol: str,
    required_days: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    ts_now = _to_utc(now or datetime.now(timezone.utc))
    horizon = ts_now - _days_delta(required_days)
    summary = _summarize_oi_samples(conn, symbol=symbol, since_ts=horizon)
    summary["required_days"] = int(required_days)
    summary["ready"] = summary["count"] >= 2 and summary["days_covered"] >= float(required_days)
    return summary


def _summarize_oi_samples(conn: Any, *, symbol: str, since_ts: datetime) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS count, MIN(timestamp) AS oldest, MAX(timestamp) AS newest
        FROM oi_samples
        WHERE symbol = ? AND timestamp >= ?
        """,
        (symbol.upper(), _format_datetime(since_ts)),
    ).fetchone()
    oldest = _parse_optional_datetime(row["oldest"]) if row else None
    newest = _parse_optional_datetime(row["newest"]) if row else None
    days_covered = 0.0
    if oldest is not None and newest is not None:
        days_covered = max((newest - oldest).total_seconds() / 86_400.0, 0.0)
    return {
        "count": int(row["count"] or 0) if row else 0,
        "oldest": oldest,
        "newest": newest,
        "days_covered": days_covered,
    }


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


def _days_delta(days: int) -> Any:
    from datetime import timedelta

    return timedelta(days=max(int(days), 0))


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
    parser = argparse.ArgumentParser(description="Backfill oi_samples from historical open_interest data.")
    parser.add_argument("--symbol", default=None, help="Trading symbol. Defaults to settings.strategy.symbol.")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args()
    try:
        result = run_backfill(symbol=args.symbol)
    except Exception as exc:
        LOG.error("OI backfill failed: %s", exc)
        return 1
    if result.current_error:
        LOG.warning("OI backfill used historical data without fresh REST snapshot: %s", result.current_error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

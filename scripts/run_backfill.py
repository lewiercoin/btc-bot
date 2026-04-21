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

from scripts import backfill_cvd_history, backfill_oi_samples
from settings import AppSettings, load_settings
from storage.db import connect, init_db

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackfillReadiness:
    oi_ready: bool
    cvd_ready: bool
    ready: bool
    oi_count: int
    oi_days_covered: float
    cvd_count: int
    required_oi_days: int
    required_cvd_bars: int


def run_all(
    *,
    conn: Any | None = None,
    settings: AppSettings | None = None,
    oi_rest_client: Any | None = None,
    cvd_rest_client: Any | None = None,
    now: datetime | None = None,
    symbol: str | None = None,
) -> BackfillReadiness:
    settings = settings or load_settings()
    if settings.storage is None:
        raise RuntimeError("Storage settings are required for historical backfill.")

    owns_conn = conn is None
    db_conn = conn or connect(settings.storage.db_path)
    try:
        init_db(db_conn, settings.storage.schema_path)
        ts_now = _to_utc(now or datetime.now(timezone.utc))
        target_symbol = (symbol or settings.strategy.symbol).upper()

        LOG.info("Starting historical data backfill | symbol=%s", target_symbol)
        backfill_oi_samples.run_backfill(
            conn=db_conn,
            settings=settings,
            rest_client=oi_rest_client,
            now=ts_now,
            symbol=target_symbol,
        )
        backfill_cvd_history.run_backfill(
            conn=db_conn,
            settings=settings,
            rest_client=cvd_rest_client,
            now=ts_now,
            symbol=target_symbol,
            timeframe="15m",
        )
        readiness = verify_readiness(db_conn, settings=settings, now=ts_now, symbol=target_symbol)
        if readiness.ready:
            LOG.info(
                "READY: OI=%.2f days (%d samples), CVD=%d bars",
                readiness.oi_days_covered,
                readiness.oi_count,
                readiness.cvd_count,
            )
        else:
            LOG.warning(
                "NOT READY: OI ready=%s %.2f/%d days (%d samples), CVD ready=%s %d/%d bars",
                readiness.oi_ready,
                readiness.oi_days_covered,
                readiness.required_oi_days,
                readiness.oi_count,
                readiness.cvd_ready,
                readiness.cvd_count,
                readiness.required_cvd_bars,
            )
        return readiness
    finally:
        if owns_conn:
            db_conn.close()


def verify_readiness(
    conn: Any,
    *,
    settings: AppSettings,
    now: datetime | None = None,
    symbol: str | None = None,
) -> BackfillReadiness:
    ts_now = _to_utc(now or datetime.now(timezone.utc))
    target_symbol = (symbol or settings.strategy.symbol).upper()
    oi_required = int(settings.data_quality.oi_baseline_days)
    cvd_required = int(settings.data_quality.cvd_divergence_bars)
    oi = backfill_oi_samples.summarize_readiness(
        conn,
        symbol=target_symbol,
        required_days=oi_required,
        now=ts_now,
    )
    cvd = backfill_cvd_history.summarize_readiness(
        conn,
        symbol=target_symbol,
        timeframe="15m",
        required_bars=cvd_required,
    )
    oi_ready = bool(oi["ready"])
    cvd_ready = bool(cvd["ready"])
    return BackfillReadiness(
        oi_ready=oi_ready,
        cvd_ready=cvd_ready,
        ready=oi_ready and cvd_ready,
        oi_count=int(oi["count"]),
        oi_days_covered=float(oi["days_covered"]),
        cvd_count=int(cvd["count"]),
        required_oi_days=oi_required,
        required_cvd_bars=cvd_required,
    )


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one-time historical OI/CVD backfill.")
    parser.add_argument("--symbol", default=None, help="Trading symbol. Defaults to settings.strategy.symbol.")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args()
    try:
        readiness = run_all(symbol=args.symbol)
    except Exception as exc:
        LOG.error("Historical backfill failed: %s", exc)
        return 1

    if readiness.ready:
        print(
            "READY: OI={:.2f} days ({} samples), CVD={} bars".format(
                readiness.oi_days_covered,
                readiness.oi_count,
                readiness.cvd_count,
            )
        )
        return 0

    print(
        "NOT READY: OI={:.2f}/{} days ({} samples), CVD={}/{} bars".format(
            readiness.oi_days_covered,
            readiness.required_oi_days,
            readiness.oi_count,
            readiness.cvd_count,
            readiness.required_cvd_bars,
        )
    )
    print("Recommendation: do not restart the bot for experiment-v2 until backfill readiness is READY.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

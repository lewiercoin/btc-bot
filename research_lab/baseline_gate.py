from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from backtest.backtest_runner import BacktestConfig, BacktestRunner
from settings import AppSettings


class BaselineGateError(ValueError):
    """Raised when baseline backtest contract is not satisfied."""


def _to_range_value(value: datetime | date | str) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _open_read_only_connection(source_db_path: Path) -> sqlite3.Connection:
    db_uri = f"file:{source_db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def check_baseline(
    *,
    source_db_path: Path,
    backtest_config: BacktestConfig,
    base_settings: AppSettings,
    min_trades: int = 5,
) -> None:
    """Run a single baseline backtest. Raise BaselineGateError if trades < min_trades."""
    conn = _open_read_only_connection(source_db_path)
    try:
        runner = BacktestRunner(conn, settings=base_settings)
        # Prevent baseline gate from persisting trade rows into the source DB.
        runner._persist_closed_trades = lambda _closed_records: None  # type: ignore[method-assign]
        result = runner.run(backtest_config)
    finally:
        conn.close()

    trades_count = len(result.trades)
    if trades_count >= int(min_trades):
        return

    start = _to_range_value(backtest_config.start_date)
    end = _to_range_value(backtest_config.end_date)
    raise BaselineGateError(
        "Baseline gate failed: "
        f"trades={trades_count} (min_trades={min_trades}) "
        f"for date range {start}..{end}. "
        "Check aggtrade_buckets data coverage for this date range."
    )


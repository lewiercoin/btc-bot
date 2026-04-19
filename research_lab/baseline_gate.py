from __future__ import annotations

import math
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

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


def _run_baseline_backtest(
    *,
    source_db_path: Path,
    backtest_config: BacktestConfig,
    base_settings: AppSettings,
) -> dict[str, Any]:
    conn = _open_read_only_connection(source_db_path)
    try:
        runner = BacktestRunner(conn, settings=base_settings)
        runner._persist_closed_trades = lambda _closed_records: None  # type: ignore[method-assign]
        result = runner.run(backtest_config)
    finally:
        conn.close()

    performance = result.performance
    return {
        "trades_count": int(len(result.trades)),
        "expectancy_r": float(performance.expectancy_r),
        "profit_factor": float(performance.profit_factor),
        "max_drawdown_pct": float(performance.max_drawdown_pct),
        "sharpe_ratio": float(performance.sharpe_ratio),
        "pnl_abs": float(performance.pnl_abs),
        "win_rate": float(performance.win_rate),
    }


def _baseline_range_error(backtest_config: BacktestConfig, trades_count: int, reason: str) -> BaselineGateError:
    start = _to_range_value(backtest_config.start_date)
    end = _to_range_value(backtest_config.end_date)
    return BaselineGateError(
        "Baseline gate failed: "
        f"trades={trades_count} for date range {start}..{end}. "
        f"{reason}"
    )


def check_baseline_hard(
    *,
    source_db_path: Path,
    backtest_config: BacktestConfig,
    base_settings: AppSettings,
) -> None:
    try:
        metrics = _run_baseline_backtest(
            source_db_path=source_db_path,
            backtest_config=backtest_config,
            base_settings=base_settings,
        )
    except Exception as exc:
        raise _baseline_range_error(backtest_config, 0, f"Broken baseline pipeline: {exc}") from exc

    trades_count = int(metrics["trades_count"])
    if trades_count <= 0:
        raise _baseline_range_error(
            backtest_config,
            trades_count,
            "Check aggtrade_buckets data coverage for this date range.",
        )

    numeric_fields = (
        "expectancy_r",
        "profit_factor",
        "max_drawdown_pct",
        "sharpe_ratio",
        "pnl_abs",
        "win_rate",
    )
    for field_name in numeric_fields:
        if not math.isfinite(float(metrics[field_name])):
            raise _baseline_range_error(
                backtest_config,
                trades_count,
                f"Nonsensical baseline metric detected: {field_name}={metrics[field_name]!r}",
            )

    if float(metrics["profit_factor"]) < 0.0 or float(metrics["max_drawdown_pct"]) < 0.0:
        raise _baseline_range_error(
            backtest_config,
            trades_count,
            "Nonsensical baseline metric detected: negative profit_factor or max_drawdown_pct.",
        )


def check_baseline_soft(
    *,
    source_db_path: Path,
    backtest_config: BacktestConfig,
    base_settings: AppSettings,
) -> dict[str, Any]:
    metrics = _run_baseline_backtest(
        source_db_path=source_db_path,
        backtest_config=backtest_config,
        base_settings=base_settings,
    )
    warning: str | None = None
    if float(metrics["expectancy_r"]) < 0.0 or float(metrics["profit_factor"]) < 1.0:
        warning = "weak_baseline"
    return {
        "warning": warning,
        "metrics": metrics,
    }


def check_baseline(
    *,
    source_db_path: Path,
    backtest_config: BacktestConfig,
    base_settings: AppSettings,
) -> None:
    check_baseline_hard(
        source_db_path=source_db_path,
        backtest_config=backtest_config,
        base_settings=base_settings,
    )


from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtest.backtest_runner import BacktestConfig, BacktestRunner
from backtest.fill_model import SimpleFillModel
from backtest.replay_loader import ReplayLoader, ReplayLoaderConfig
from settings import load_settings
from storage.db import init_db


def make_conn(schema_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn, schema_path)
    return conn


def seed_history(conn: sqlite3.Connection, *, symbol: str, start_open: datetime, bars_15m: int) -> None:
    candles_15m: list[tuple] = []
    candles_1h: list[tuple] = []
    candles_4h: list[tuple] = []
    funding_rows: list[tuple] = []
    oi_rows: list[tuple] = []
    agg_rows: list[tuple] = []
    force_rows: list[tuple] = []

    for index in range(bars_15m):
        open_time = start_open + timedelta(minutes=15 * index)
        close_time = open_time + timedelta(minutes=15)
        close_price = 100.0 + index * 0.5
        open_price = close_price - 0.2
        high = close_price + 1.0
        low = close_price - 1.0
        volume = 1000.0 + index
        candles_15m.append(
            (
                symbol,
                "15m",
                open_time.isoformat(),
                open_price,
                high,
                low,
                close_price,
                volume,
            )
        )
        oi_rows.append((symbol, close_time.isoformat(), 50_000.0 + index * 10.0))

        bucket_15m_time = open_time
        bucket_60s_time = (close_time - timedelta(seconds=1)).replace(second=0, microsecond=0)
        agg_rows.append((symbol, bucket_15m_time.isoformat(), "15m", 5.0 + index, 4.0 + index, 0.05, 1.0 + index))
        agg_rows.append((symbol, bucket_60s_time.isoformat(), "60s", 1.0 + index, 0.8 + index, 0.1, 0.2 + index))

        force_rows.append(
            (
                symbol,
                (close_time - timedelta(seconds=30)).isoformat(),
                "BUY" if index % 2 == 0 else "SELL",
                0.1 + index * 0.01,
                close_price,
            )
        )

    for index in range(max((bars_15m + 3) // 4, 1)):
        open_time = start_open + timedelta(hours=index)
        close_price = 100.0 + index * 1.0
        candles_1h.append(
            (
                symbol,
                "1h",
                open_time.isoformat(),
                close_price - 0.5,
                close_price + 1.5,
                close_price - 1.5,
                close_price,
                2000.0 + index,
            )
        )

    for index in range(max((bars_15m + 15) // 16, 1)):
        open_time = start_open + timedelta(hours=4 * index)
        close_price = 100.0 + index * 2.0
        candles_4h.append(
            (
                symbol,
                "4h",
                open_time.isoformat(),
                close_price - 1.0,
                close_price + 2.0,
                close_price - 2.0,
                close_price,
                4000.0 + index,
            )
        )

    for index in range(max((bars_15m + 31) // 32, 1)):
        funding_time = start_open + timedelta(hours=8 * index)
        funding_rows.append((symbol, funding_time.isoformat(), 0.0001 * (index + 1)))

    conn.executemany(
        """
        INSERT INTO candles (symbol, timeframe, open_time, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        candles_15m + candles_1h + candles_4h,
    )
    conn.executemany(
        """
        INSERT INTO funding (symbol, funding_time, funding_rate)
        VALUES (?, ?, ?)
        """,
        funding_rows,
    )
    conn.executemany(
        """
        INSERT INTO open_interest (symbol, timestamp, oi_value)
        VALUES (?, ?, ?)
        """,
        oi_rows,
    )
    conn.executemany(
        """
        INSERT INTO aggtrade_buckets (
            symbol, bucket_time, timeframe, taker_buy_volume, taker_sell_volume, tfi, cvd
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        agg_rows,
    )
    conn.executemany(
        """
        INSERT INTO force_orders (symbol, event_time, side, qty, price)
        VALUES (?, ?, ?, ?, ?)
        """,
        force_rows,
    )
    day = start_open.date().isoformat()
    conn.execute(
        """
        INSERT INTO daily_external_bias (date, etf_bias_5d, dxy_close, notes)
        VALUES (?, ?, ?, ?)
        """,
        (day, 0.15, 102.0, "smoke"),
    )
    conn.commit()


def assert_almost_equal(actual: float, expected: float, eps: float = 1e-9) -> None:
    if abs(actual - expected) > eps:
        raise AssertionError(f"{actual} != {expected}")


def run_replay_loader_smoke(conn: sqlite3.Connection, *, start_open: datetime, bars: int, symbol: str) -> None:
    first_close = start_open + timedelta(minutes=15)
    last_close = start_open + timedelta(minutes=15 * bars)
    loader = ReplayLoader(
        conn,
        ReplayLoaderConfig(
            candles_15m_lookback=50,
            candles_1h_lookback=50,
            candles_4h_lookback=50,
            funding_lookback=50,
        ),
    )
    snapshots = list(loader.iter_snapshots(start_date=first_close, end_date=last_close, symbol=symbol))
    assert len(snapshots) == bars
    first = snapshots[0]
    assert first.symbol == symbol
    assert first.timestamp == first_close
    assert first.price == first.ask == first.bid
    assert len(first.candles_15m) >= 1
    print("replay loader smoke: OK")


def run_fill_model_smoke() -> None:
    model = SimpleFillModel()
    market_buy = model.simulate(100.0, 2.0, order_type="MARKET", side="BUY")
    limit_sell = model.simulate(100.0, 2.0, order_type="LIMIT", side="SELL")

    assert_almost_equal(market_buy.filled_price, 100.0 * (1.0 + 3.0 / 10_000.0))
    assert_almost_equal(limit_sell.filled_price, 100.0 * (1.0 - 1.0 / 10_000.0))
    assert_almost_equal(market_buy.fee_paid, market_buy.filled_price * 2.0 * 0.0004)
    assert_almost_equal(limit_sell.fee_paid, limit_sell.filled_price * 2.0 * 0.0004)
    print("fill model smoke: OK")


def run_backtest_runner_smoke(conn: sqlite3.Connection, *, start_open: datetime, bars: int, symbol: str) -> None:
    settings = load_settings()
    runner = BacktestRunner(conn, settings=settings)
    first_close = start_open + timedelta(minutes=15)
    last_close = start_open + timedelta(minutes=15 * bars)
    result = runner.run(
        BacktestConfig(
            start_date=first_close,
            end_date=last_close,
            initial_equity=10_000.0,
            symbol=symbol,
            entry_order_type="LIMIT",
        )
    )
    assert result.performance is not None
    assert hasattr(result.performance, "win_rate")
    assert hasattr(result.performance, "profit_factor")
    assert isinstance(result.trades, list)
    assert len(result.equity_curve) >= 1

    persisted = conn.execute("SELECT COUNT(*) AS cnt FROM trade_log").fetchone()["cnt"]
    assert int(persisted) == len(result.trades)
    print("backtest runner smoke: OK")


def run_empty_dataset_smoke(schema_path: Path, symbol: str) -> None:
    conn = make_conn(schema_path)
    runner = BacktestRunner(conn, settings=load_settings())
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    result = runner.run(
        BacktestConfig(
            start_date=start,
            end_date=start + timedelta(hours=1),
            symbol=symbol,
        )
    )
    assert result.performance.trades_count == 0
    assert result.trades == []
    print("empty dataset smoke: OK")


def run_single_bar_smoke(schema_path: Path, symbol: str) -> None:
    conn = make_conn(schema_path)
    start_open = datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc)
    seed_history(conn, symbol=symbol, start_open=start_open, bars_15m=1)
    runner = BacktestRunner(conn, settings=load_settings())
    result = runner.run(
        BacktestConfig(
            start_date=start_open + timedelta(minutes=15),
            end_date=start_open + timedelta(minutes=15),
            symbol=symbol,
        )
    )
    assert result.performance.trades_count >= 0
    assert len(result.equity_curve) >= 1
    print("single bar smoke: OK")


def main() -> None:
    os.environ["BOT_MODE"] = "PAPER"
    settings = load_settings()
    assert settings.storage is not None

    symbol = settings.strategy.symbol.upper()
    start_open = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    bars = 20

    conn = make_conn(settings.storage.schema_path)
    seed_history(conn, symbol=symbol, start_open=start_open, bars_15m=bars)

    run_replay_loader_smoke(conn, start_open=start_open, bars=bars, symbol=symbol)
    run_fill_model_smoke()
    run_backtest_runner_smoke(conn, start_open=start_open, bars=bars, symbol=symbol)
    run_empty_dataset_smoke(settings.storage.schema_path, symbol)
    run_single_bar_smoke(settings.storage.schema_path, symbol)
    print("backtest smoke: OK")


if __name__ == "__main__":
    main()

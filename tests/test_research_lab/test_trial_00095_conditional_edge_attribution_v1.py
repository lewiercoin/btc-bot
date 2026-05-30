from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_lab.diagnostics.trial_00095_conditional_edge_attribution_v1 import (
    DiagnosticConfig,
    attribute_trades,
    inspect_schema,
    load_candles,
    load_trade_records,
    merge_entries,
    parse_ts,
    run_diagnostic,
)


def _ts(index: int) -> datetime:
    return datetime(2022, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * index)


def _write_inputs(tmp_path: Path, *, n_trades: int = 32) -> tuple[Path, Path, Path]:
    trades_path = tmp_path / "trades.json"
    entries_path = tmp_path / "entries.json"
    db_path = tmp_path / "market.db"
    trades = []
    entries = []
    for i in range(n_trades):
        opened_at = _ts(40 + i * 4)
        pnl = 4.0 if i % 2 == 0 else -1.0
        depth = 0.0066 + i * 0.00002
        trades.append(
            {
                "trade_id": f"t-{i:03d}",
                "opened_at": opened_at.isoformat(),
                "direction": "LONG",
                "regime": "uptrend" if i % 3 else "downtrend",
                "pnl_r": pnl,
                "sweep_depth_pct": depth,
                "exit_reason": "TP_TRAIL" if pnl > 0 else "SL",
                "mae": 50.0 if pnl > 0 else 120.0,
                "mfe": 300.0 if pnl > 0 else 30.0,
                "session_hour": opened_at.hour,
            }
        )
        entries.append(
            {
                "trade_id": f"t-{i:03d}",
                "signal_id": f"s-{i:03d}",
                "opened_at": opened_at.isoformat(),
                "closed_at": (opened_at + timedelta(minutes=45)).isoformat(),
                "direction": "LONG",
                "regime": "uptrend",
                "entry_price": 100.0,
                "stop_loss": 99.0,
                "tp1": 102.0,
                "tp2": 104.0,
                "baseline_pnl_r": pnl,
                "baseline_exit_reason": "TP_TRAIL" if pnl > 0 else "SL",
            }
        )
    trades_path.write_text(json.dumps(trades), encoding="utf-8")
    entries_path.write_text(json.dumps(entries), encoding="utf-8")
    _create_market_db(db_path, max_index=40 + n_trades * 4 + 20)
    return trades_path, entries_path, db_path


def _create_market_db(path: Path, *, max_index: int = 220) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE candles (
                symbol TEXT,
                timeframe TEXT,
                open_time TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE aggtrade_buckets (
                symbol TEXT,
                bucket_time TEXT,
                timeframe TEXT,
                taker_buy_volume REAL,
                taker_sell_volume REAL,
                tfi REAL,
                cvd REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE funding (
                symbol TEXT,
                funding_time TEXT,
                funding_rate REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE open_interest (
                symbol TEXT,
                timestamp TEXT,
                oi_value REAL
            )
            """
        )
        candle_rows = []
        agg_rows = []
        oi_rows = []
        for i in range(max_index):
            price = 100.0 + i * 0.1
            candle_rows.append(
                (
                    "BTCUSDT",
                    "15m",
                    _ts(i).isoformat(),
                    price,
                    price + 1.0,
                    price - 1.0,
                    price + 0.3,
                    1000.0 + i,
                )
            )
            agg_rows.append(("BTCUSDT", _ts(i).isoformat(), "15m", 60.0, 40.0, 0.2 if i % 2 == 0 else -0.2, i))
            oi_rows.append(("BTCUSDT", _ts(i).isoformat(), 10000.0 + i))
        conn.executemany("INSERT INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?)", candle_rows)
        conn.executemany("INSERT INTO aggtrade_buckets VALUES (?, ?, ?, ?, ?, ?, ?)", agg_rows)
        conn.executemany("INSERT INTO funding VALUES (?, ?, ?)", [("BTCUSDT", _ts(0).isoformat(), 0.0001)])
        conn.executemany("INSERT INTO open_interest VALUES (?, ?, ?)", oi_rows)


def test_market_context_uses_prior_completed_bar(tmp_path: Path) -> None:
    trades_path, entries_path, db_path = _write_inputs(tmp_path, n_trades=4)
    trades = merge_entries(load_trade_records(trades_path), {})
    with sqlite3.connect(db_path) as conn:
        candles = load_candles(conn, DiagnosticConfig())
        attributed = attribute_trades(trades, candles, {_ts(39): 0.75, _ts(40): -0.75}, [], [], DiagnosticConfig())

    assert attributed[0].opened_at == _ts(40)
    assert attributed[0].tfi_15m_prev == 0.75
    assert attributed[0].tfi_alignment == "aligned"


def test_schema_reports_rejected_population_availability(tmp_path: Path) -> None:
    _, _, db_path = _write_inputs(tmp_path, n_trades=4)
    with sqlite3.connect(db_path) as conn:
        schema = inspect_schema(conn)

    assert schema["required_tables_present"]["candles"] is True
    assert schema["optional_tables_present"]["decision_outcomes"] is False
    assert schema["optional_tables_present"]["feature_snapshots"] is False


def test_diagnostic_recommends_reconstruction_not_threshold_change(tmp_path: Path) -> None:
    trades_path, entries_path, db_path = _write_inputs(tmp_path, n_trades=32)
    payload = run_diagnostic(
        trades_path=trades_path,
        entries_path=entries_path,
        market_db_path=db_path,
        report_path=tmp_path / "report.md",
        json_path=tmp_path / "report.json",
        config=DiagnosticConfig(min_decision_trades=20, near_threshold_min_trades=8),
    )

    assert payload["data_availability"]["rejected_backtest_candidates_available"] is False
    assert payload["next_recommendation"]["recommendation"] == "PLAN_NEAR_MISS_RECONSTRUCTION_DIAGNOSTIC"
    assert "reconstruct" in payload["next_recommendation"]["reason"]
    assert "threshold" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_diagnostic_is_deterministic(tmp_path: Path) -> None:
    trades_path, entries_path, db_path = _write_inputs(tmp_path, n_trades=32)
    kwargs = {
        "trades_path": trades_path,
        "entries_path": entries_path,
        "market_db_path": db_path,
        "config": DiagnosticConfig(min_decision_trades=20, near_threshold_min_trades=8),
    }
    first = run_diagnostic(report_path=tmp_path / "r1.md", json_path=tmp_path / "r1.json", **kwargs)
    second = run_diagnostic(report_path=tmp_path / "r2.md", json_path=tmp_path / "r2.json", **kwargs)

    assert first["baseline_metrics"] == second["baseline_metrics"]
    assert first["bucket_metrics"] == second["bucket_metrics"]
    assert first["next_recommendation"] == second["next_recommendation"]


def test_parse_ts_normalizes_to_utc() -> None:
    assert parse_ts("2022-01-01T00:00:00Z").tzinfo == timezone.utc

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.analyze_trades import AnalyzeTradesConfig, analyze_closed_trades
from research.llm_post_trade_review import ReviewBuildConfig, build_llm_review_package
from settings import load_settings
from storage.db import init_db


def _make_conn(schema_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn, schema_path)
    return conn


def _seed_closed_trade(
    conn: sqlite3.Connection,
    *,
    settings,
    index: int,
    opened_at: datetime,
    hold_minutes: int,
    direction: str,
    regime: str,
    confluence_score: float,
    pnl_abs: float,
    pnl_r: float,
    exit_reason: str,
) -> None:
    closed_at = opened_at + timedelta(minutes=hold_minutes)
    signal_id = f"sig-smoke-{index:03d}"
    position_id = f"pos-smoke-{index:03d}"
    trade_id = f"trd-smoke-{index:03d}"
    entry_price = 100.0 + index
    if direction == "LONG":
        exit_price = entry_price + pnl_abs
    else:
        exit_price = entry_price - pnl_abs

    conn.execute(
        """
        INSERT INTO signal_candidates (
            signal_id, timestamp, direction, setup_type, confluence_score, regime,
            reasons_json, features_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            opened_at.isoformat(),
            direction,
            "smoke_research",
            confluence_score,
            regime,
            "[\"smoke_reason\"]",
            "{\"atr_15m\":1.2,\"tfi_60s\":0.2,\"force_order_spike\":true}",
            settings.schema_version,
            settings.config_hash,
        ),
    )
    conn.execute(
        """
        INSERT INTO executable_signals (
            signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
            take_profit_2, rr_ratio, governance_notes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal_id,
            opened_at.isoformat(),
            direction,
            entry_price,
            entry_price - 1.0 if direction == "LONG" else entry_price + 1.0,
            entry_price + 2.0 if direction == "LONG" else entry_price - 2.0,
            entry_price + 3.0 if direction == "LONG" else entry_price - 3.0,
            3.0,
            "[\"governance_pass\"]",
        ),
    )
    conn.execute(
        """
        INSERT INTO positions (
            position_id, signal_id, symbol, direction, status, entry_price, size, leverage,
            stop_loss, take_profit_1, take_profit_2, opened_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            position_id,
            signal_id,
            settings.strategy.symbol.upper(),
            direction,
            "CLOSED",
            entry_price,
            1.0,
            3,
            entry_price - 1.0 if direction == "LONG" else entry_price + 1.0,
            entry_price + 2.0 if direction == "LONG" else entry_price - 2.0,
            entry_price + 3.0 if direction == "LONG" else entry_price - 3.0,
            opened_at.isoformat(),
            closed_at.isoformat(),
        ),
    )
    conn.execute(
        """
        INSERT INTO trade_log (
            trade_id, signal_id, position_id, opened_at, closed_at, direction, regime,
            confluence_score, entry_price, exit_price, size, fees_total, slippage_bps_avg,
            pnl_abs, pnl_r, mae, mfe, exit_reason, features_at_entry_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            signal_id,
            position_id,
            opened_at.isoformat(),
            closed_at.isoformat(),
            direction,
            regime,
            confluence_score,
            entry_price,
            exit_price,
            1.0,
            1.5,
            2.0,
            pnl_abs,
            pnl_r,
            10.0,
            20.0,
            exit_reason,
            "{\"atr_15m\":1.2,\"tfi_60s\":0.2,\"force_order_spike\":true}",
            settings.schema_version,
            settings.config_hash,
        ),
    )


def _seed_dataset(conn: sqlite3.Connection, settings) -> None:  # type: ignore[no-untyped-def]
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    rows = [
        ("LONG", "normal", 3.4, 120.0, 1.20, "TP"),
        ("SHORT", "normal", 3.1, -70.0, -0.70, "SL"),
        ("LONG", "post_liquidation", 4.2, 90.0, 0.90, "TP"),
        ("SHORT", "crowded_leverage", 3.7, -30.0, -0.30, "TIMEOUT"),
        ("LONG", "normal", 2.9, 0.0, 0.00, "TIMEOUT"),
        ("SHORT", "normal", 3.8, 55.0, 0.55, "TP"),
    ]
    for index, (direction, regime, confluence, pnl_abs, pnl_r, reason) in enumerate(rows, start=1):
        _seed_closed_trade(
            conn,
            settings=settings,
            index=index,
            opened_at=base + timedelta(minutes=45 * index),
            hold_minutes=30 + index,
            direction=direction,
            regime=regime,
            confluence_score=confluence,
            pnl_abs=pnl_abs,
            pnl_r=pnl_r,
            exit_reason=reason,
        )
    conn.commit()


def main() -> None:
    os.environ["BOT_MODE"] = "PAPER"
    settings = load_settings()
    assert settings.storage is not None
    conn = _make_conn(settings.storage.schema_path)
    try:
        _seed_dataset(conn, settings)
        fixed_now = datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc)
        query = AnalyzeTradesConfig(symbol=settings.strategy.symbol.upper())

        report = analyze_closed_trades(conn, query, now_provider=lambda: fixed_now)
        report_repeat = analyze_closed_trades(conn, query, now_provider=lambda: fixed_now)
        assert report.to_dict() == report_repeat.to_dict()
        assert report.trades_count == 6
        assert report.wins == 3
        assert report.losses == 2
        assert report.breakeven == 1
        assert abs(report.pnl_abs_sum - 165.0) < 1e-8
        assert abs(report.pnl_r_sum - 1.65) < 1e-8
        assert report.max_consecutive_losses == 1
        assert any(item.key == "TP" for item in report.exit_reason_breakdown)
        print("analyze_trades smoke: OK")

        package = build_llm_review_package(
            conn,
            query,
            build_config=ReviewBuildConfig(
                winners_sample_size=2,
                losers_sample_size=2,
                max_feature_keys_per_trade=4,
            ),
            now_provider=lambda: fixed_now,
        )
        payload = package.to_dict()
        assert payload["analysis"]["trades_count"] == 6
        assert len(payload["sampled_trades"]["winners"]) == 2
        assert len(payload["sampled_trades"]["losers"]) == 2
        assert "summary" in payload["response_schema"]
        assert "strict JSON" in payload["system_prompt"]
        print("llm_post_trade_review smoke: OK")
        print("research smoke: OK")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

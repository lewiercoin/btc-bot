from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.models import Features, MarketSnapshot
from storage.db import init_db
from storage.state_store import StateStore
from validation.recompute_features import recompute_snapshot


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "storage" / "schema.sql"


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, _schema_path())
    return conn


def _candle(ts: datetime, open_: float, high: float, low: float, close: float) -> dict[str, object]:
    return {
        "open_time": ts,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1.0,
    }


def test_state_store_creates_market_truth_tables_and_links_decision_outcomes() -> None:
    conn = _make_conn()
    try:
        store = StateStore(conn, mode="PAPER")
        store.ensure_initialized()

        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "market_snapshots" in tables
        assert "feature_snapshots" in tables

        decision_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(decision_outcomes)").fetchall()
        }
        assert "snapshot_id" in decision_columns
        assert "feature_snapshot_id" in decision_columns
    finally:
        conn.close()


def test_market_truth_persistence_and_recompute_round_trip() -> None:
    conn = _make_conn()
    try:
        now = datetime(2026, 4, 23, 12, 15, tzinfo=timezone.utc)
        candles_15m = [
            _candle(now - timedelta(minutes=45), 100.0, 101.0, 99.0, 100.0),
            _candle(now - timedelta(minutes=30), 100.0, 102.0, 99.0, 101.0),
            _candle(now - timedelta(minutes=15), 101.0, 103.0, 98.0, 102.0),
        ]
        candles_4h = [
            _candle(now - timedelta(hours=12), 90.0, 100.0, 88.0, 95.0),
            _candle(now - timedelta(hours=8), 95.0, 105.0, 94.0, 100.0),
            _candle(now - timedelta(hours=4), 100.0, 110.0, 99.0, 102.0),
        ]
        snapshot = MarketSnapshot(
            symbol="BTCUSDT",
            timestamp=now,
            price=102.0,
            bid=101.5,
            ask=102.5,
            exchange_timestamp=now,
            source="mixed",
            latency_ms=42.0,
            data_quality_flag="ready",
            book_ticker={"symbol": "BTCUSDT", "bid": 101.5, "ask": 102.5, "_exchange_raw": {"bidPrice": "101.5", "askPrice": "102.5"}},
            open_interest_payload={"symbol": "BTCUSDT", "timestamp": now, "oi_value": 1000.0, "_exchange_raw": {"openInterest": "1000"}},
            candles_15m=candles_15m,
            candles_1h=[],
            candles_4h=candles_4h,
            funding_history=[{"funding_time": now - timedelta(hours=8), "funding_rate": 0.0001, "_exchange_raw": {"fundingRate": "0.0001"}}],
            open_interest=1000.0,
            aggtrade_events_60s=[
                {"event_time": now - timedelta(seconds=20), "qty": 2.0, "is_buyer_maker": False},
                {"event_time": now - timedelta(seconds=5), "qty": 1.0, "is_buyer_maker": True},
            ],
            aggtrade_events_15m=[],
            aggtrades_bucket_60s={"tfi": 1.0 / 3.0},
            aggtrades_bucket_15m={"cvd": 12.0},
            force_order_events_60s=[{"event_time": now - timedelta(seconds=10), "side": "BUY", "qty": 1.0, "price": 102.0}],
            source_meta={"build_latency_ms": 42.0},
        )

        features = Features(
            schema_version="v1.0",
            config_hash="hash-truth",
            timestamp=now,
            atr_15m=3.5,
            atr_4h=11.0,
            atr_4h_norm=11.0 / 102.0,
            ema50_4h=95.275390625,
            ema200_4h=95.06930420711974,
            sweep_detected=False,
            reclaim_detected=False,
            sweep_level=None,
            sweep_depth_pct=None,
            sweep_side=None,
            funding_8h=0.0001,
            funding_sma3=0.0001,
            funding_sma9=0.0001,
            funding_pct_60d=100.0,
            oi_value=1000.0,
            oi_zscore_60d=0.0,
            oi_delta_pct=0.0,
            cvd_15m=12.0,
            cvd_bullish_divergence=False,
            cvd_bearish_divergence=False,
            tfi_60s=1.0 / 3.0,
            force_order_rate_60s=1.0 / 60.0,
            force_order_spike=False,
            force_order_decreasing=False,
        )

        store = StateStore(conn, mode="PAPER")
        store.ensure_initialized()
        store.persist_config_snapshot(
            config_hash="hash-truth",
            captured_at=now,
            strategy_snapshot={
                "atr_period": 14,
                "ema_fast": 50,
                "ema_slow": 200,
                "equal_level_lookback": 50,
                "equal_level_tol_atr": 0.25,
                "sweep_buf_atr": 0.15,
                "reclaim_buf_atr": 0.05,
                "wick_min_atr": 0.4,
            },
        )
        snapshot_id = store.record_market_snapshot(snapshot)
        feature_snapshot_id = store.record_feature_snapshot(snapshot_id=snapshot_id, features=features)
        store.record_decision_outcome(
            cycle_timestamp=now,
            outcome_group="no_signal",
            outcome_reason="no_reclaim",
            config_hash="hash-truth",
            snapshot_id=snapshot_id,
            feature_snapshot_id=feature_snapshot_id,
            details={"blocked_by": "no_reclaim"},
        )

        decision_row = conn.execute(
            "SELECT snapshot_id, feature_snapshot_id FROM decision_outcomes LIMIT 1"
        ).fetchone()
        assert decision_row["snapshot_id"] == snapshot_id
        assert decision_row["feature_snapshot_id"] == feature_snapshot_id

        payload = recompute_snapshot(conn, snapshot_id)
        comparisons = {item["field"]: item for item in payload["comparisons"]}
        assert comparisons["atr_4h"]["status"] == "ok"
        assert comparisons["atr_4h_norm"]["status"] == "ok"
        assert comparisons["tfi_60s"]["status"] == "ok"

        market_row = conn.execute(
            "SELECT candles_15m_json, book_ticker_json FROM market_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        assert json.loads(market_row["candles_15m_json"])[-1]["close"] == 102.0
        assert json.loads(market_row["book_ticker_json"])["bid"] == 101.5
    finally:
        conn.close()

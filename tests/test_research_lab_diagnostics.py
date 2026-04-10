"""
Smoke tests for SIGNAL-ANALYSIS-V1 diagnostics deliverables (D1, D2, D3).
"""

from __future__ import annotations

import json
import math
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# D1: ParamSpec volume lever fields
# ---------------------------------------------------------------------------


def test_paramspec_has_volume_lever_fields() -> None:
    from research_lab.types import ParamSpec

    spec = ParamSpec(
        name="test_param",
        target_section="strategy",
        default_value=1.0,
        status="ACTIVE",
        domain_type="float",
    )
    assert spec.volume_lever is False
    assert spec.volume_direction is None


def test_paramspec_volume_lever_set() -> None:
    from research_lab.types import ParamSpec

    spec = ParamSpec(
        name="test_lever",
        target_section="strategy",
        default_value=1.0,
        status="ACTIVE",
        domain_type="float",
        volume_lever=True,
        volume_direction="up",
    )
    assert spec.volume_lever is True
    assert spec.volume_direction == "up"


def test_registry_volume_lever_confirmed_set() -> None:
    from research_lab.param_registry import build_param_registry

    build_param_registry.cache_clear()
    registry = build_param_registry()

    confirmed_up = [
        "sweep_proximity_atr",
        "equal_level_lookback",
        "equal_level_tol_atr",
        "direction_tfi_threshold",
        "max_trades_per_day",
        "max_open_positions",
        "max_consecutive_losses",
        "weight_cvd_divergence",
        "weight_tfi_impulse",
        "weight_regime_special",
        "weight_ema_trend_alignment",
        "weight_funding_supportive",
    ]
    confirmed_down = [
        "level_min_age_bars",
        "min_hits",
        "wick_min_atr",
        "min_sweep_depth_pct",
        "confluence_min",
        "cooldown_minutes_after_loss",
    ]

    for name in confirmed_up:
        spec = registry[name]
        assert spec.volume_lever is True, f"{name} should be volume_lever=True"
        assert spec.volume_direction == "up", f"{name} should have volume_direction='up'"

    for name in confirmed_down:
        spec = registry[name]
        assert spec.volume_lever is True, f"{name} should be volume_lever=True"
        assert spec.volume_direction == "down", f"{name} should have volume_direction='down'"


def test_registry_non_levers_are_false() -> None:
    from research_lab.param_registry import build_param_registry

    build_param_registry.cache_clear()
    registry = build_param_registry()

    non_levers = [
        "atr_period",
        "entry_offset_atr",
        "invalidation_offset_atr",
        "tp1_atr_mult",
        "tp2_atr_mult",
        "risk_per_trade_pct",
        "max_leverage",
        "partial_exit_pct",
        "trailing_atr_mult",
        "max_hold_hours",
    ]
    for name in non_levers:
        spec = registry[name]
        assert spec.volume_lever is False, f"{name} should be volume_lever=False"
        assert spec.volume_direction is None, f"{name} should have volume_direction=None"


def test_registry_frozen_weight_levers() -> None:
    from research_lab.param_registry import build_param_registry

    build_param_registry.cache_clear()
    registry = build_param_registry()

    for name in ("weight_sweep_detected", "weight_reclaim_confirmed"):
        spec = registry[name]
        assert spec.volume_lever is True, f"FROZEN {name} should still be volume_lever=True"
        assert spec.volume_direction == "up"


def test_active_lever_count() -> None:
    from research_lab.constants import PARAM_STATUS_ACTIVE
    from research_lab.param_registry import build_param_registry

    build_param_registry.cache_clear()
    registry = build_param_registry()

    active_levers = [
        name for name, spec in registry.items()
        if spec.status == PARAM_STATUS_ACTIVE and spec.volume_lever
    ]
    assert len(active_levers) >= 14, (
        f"Expected at least 14 ACTIVE volume levers (confirmed minimum set), got {len(active_levers)}: "
        f"{active_levers}"
    )


# ---------------------------------------------------------------------------
# D2: event_study_v1 helpers (unit tests without DB)
# ---------------------------------------------------------------------------


def test_proximity_bucket_boundaries() -> None:
    from research_lab.diagnostics.event_study_v1 import _proximity_bucket

    assert _proximity_bucket(0.0) == "P1"
    assert _proximity_bucket(0.4) == "P1"
    assert _proximity_bucket(0.4001) == "P2"
    assert _proximity_bucket(0.8) == "P2"
    assert _proximity_bucket(0.8001) == "P3"
    assert _proximity_bucket(1.2) == "P3"
    assert _proximity_bucket(1.2001) == "P4"
    assert _proximity_bucket(5.0) == "P4"


def test_structure_bucket() -> None:
    from research_lab.diagnostics.event_study_v1 import _structure_bucket

    assert _structure_bucket(5, 3) == "MATURE"
    assert _structure_bucket(10, 5) == "MATURE"
    assert _structure_bucket(4, 3) == "IMMATURE"
    assert _structure_bucket(5, 2) == "IMMATURE"
    assert _structure_bucket(0, 0) == "IMMATURE"


def test_segment_for_ts() -> None:
    from research_lab.diagnostics.event_study_v1 import _segment_for_ts

    assert _segment_for_ts(datetime(2022, 3, 15, tzinfo=timezone.utc)) == "S1"
    assert _segment_for_ts(datetime(2022, 10, 1, tzinfo=timezone.utc)) == "S2"
    assert _segment_for_ts(datetime(2023, 6, 15, tzinfo=timezone.utc)) == "S3"
    assert _segment_for_ts(datetime(2024, 5, 1, tzinfo=timezone.utc)) == "S4"
    assert _segment_for_ts(datetime(2025, 1, 1, tzinfo=timezone.utc)) == "S5"
    assert _segment_for_ts(datetime(2025, 9, 1, tzinfo=timezone.utc)) == "S6"
    assert _segment_for_ts(datetime(2021, 1, 1, tzinfo=timezone.utc)) is None


def test_t_test_1samp_positive_mean() -> None:
    from research_lab.diagnostics.event_study_v1 import _t_test_1samp

    values = [0.1] * 50
    t, p = _t_test_1samp(values)
    assert t == float("inf") or t > 100
    assert p < 0.001


def test_t_test_1samp_zero_mean() -> None:
    from research_lab.diagnostics.event_study_v1 import _t_test_1samp

    values = [1.0, -1.0] * 20
    t, p = _t_test_1samp(values)
    assert abs(t) < 1e-10
    assert p > 0.9


def test_t_test_1samp_insufficient() -> None:
    from research_lab.diagnostics.event_study_v1 import _t_test_1samp

    t, p = _t_test_1samp([])
    assert math.isnan(t)
    assert math.isnan(p)

    t2, p2 = _t_test_1samp([1.0])
    assert math.isnan(t2)
    assert math.isnan(p2)


def test_cluster_metadata_for_level_low() -> None:
    from research_lab.diagnostics.event_study_v1 import _cluster_metadata_for_level

    # 6 candles, 5 with similar lows around 100.0 (indices 0-4), 1 outlier
    candles = [
        {"open": 101.0, "high": 102.0, "low": 100.0, "close": 101.0},
        {"open": 101.0, "high": 102.5, "low": 100.1, "close": 101.5},
        {"open": 101.5, "high": 103.0, "low": 100.05, "close": 102.0},
        {"open": 102.0, "high": 103.5, "low": 99.95, "close": 103.0},
        {"open": 103.0, "high": 104.0, "low": 100.08, "close": 103.5},
        {"open": 103.5, "high": 104.5, "low": 95.0, "close": 104.0},  # outlier
    ]
    hit_count, age_bars = _cluster_metadata_for_level(
        candles_lookback=candles,
        level_price=100.05,
        sweep_side="LOW",
        tolerance=0.5,
        min_hits=3,
        lookback=50,
    )
    assert hit_count >= 3
    assert age_bars >= 3


def test_cluster_metadata_no_cluster() -> None:
    from research_lab.diagnostics.event_study_v1 import _cluster_metadata_for_level

    candles = [
        {"open": 100.0, "high": 101.0, "low": 100.0, "close": 100.5},
        {"open": 101.0, "high": 102.0, "low": 101.0, "close": 101.5},
    ]
    hit_count, age_bars = _cluster_metadata_for_level(
        candles_lookback=candles,
        level_price=100.0,
        sweep_side="LOW",
        tolerance=0.1,
        min_hits=5,
        lookback=50,
    )
    assert hit_count == 0
    assert age_bars == 0


def test_bucket_stats_insufficient_sample() -> None:
    from research_lab.diagnostics.event_study_v1 import _bucket_stats

    events: list[dict[str, Any]] = [
        {"fwd_ret_bar4": 0.1, "fixed_exit_outcome": "WIN"} for _ in range(10)
    ]
    result = _bucket_stats(events)
    assert result["status"] == "INSUFFICIENT_SAMPLE"
    assert result["n_events"] == 10


def test_bucket_stats_sufficient_sample() -> None:
    from research_lab.diagnostics.event_study_v1 import _bucket_stats

    events = [
        {"fwd_ret_bar4": 0.2, "fixed_exit_outcome": "WIN"} for _ in range(20)
    ] + [
        {"fwd_ret_bar4": -0.1, "fixed_exit_outcome": "LOSS"} for _ in range(10)
    ]
    result = _bucket_stats(events)
    assert result["status"] == "OK"
    assert result["n_events"] == 30
    assert result["mean_forward_return_bar4"] > 0
    assert 0.0 < result["hit_rate"] <= 1.0
    assert not math.isnan(result["t_statistic"])
    assert 0.0 <= result["p_value"] <= 1.0


def test_fixed_exit_win() -> None:
    from research_lab.diagnostics.event_study_v1 import _compute_fixed_exit

    atr = 100.0
    close = 30000.0
    # bars: first bar has high = close + 2.1 * ATR → TP hit
    all_bars = [
        (close, close + 0.5 * atr, close - 0.1 * atr, atr),  # bar 0 = event bar
        (close + 2.5 * atr, close + 2.5 * atr, close - 0.1 * atr, atr),  # bar 1: TP hit
    ]
    mfe, mae, outcome = _compute_fixed_exit(0, all_bars, close, atr, "LONG")
    assert outcome == "WIN"
    assert mfe >= 2.0


def test_fixed_exit_loss() -> None:
    from research_lab.diagnostics.event_study_v1 import _compute_fixed_exit

    atr = 100.0
    close = 30000.0
    all_bars = [
        (close, close + 0.1 * atr, close - 0.1 * atr, atr),
        (close - 1.5 * atr, close - 0.5 * atr, close - 1.5 * atr, atr),  # SL hit
    ]
    mfe, mae, outcome = _compute_fixed_exit(0, all_bars, close, atr, "LONG")
    assert outcome == "LOSS"
    assert mae <= -1.0


def test_fixed_exit_timeout() -> None:
    from research_lab.diagnostics.event_study_v1 import _compute_fixed_exit

    atr = 100.0
    close = 30000.0
    # 17 bars of no movement
    all_bars = [(close, close + 0.1 * atr, close - 0.1 * atr, atr)] * 17
    mfe, mae, outcome = _compute_fixed_exit(0, all_bars, close, atr, "LONG")
    assert outcome == "TIMEOUT"


def test_run_event_study_smoke(tmp_path: Path) -> None:
    """End-to-end smoke test with a minimal in-memory database."""
    from research_lab.diagnostics.event_study_v1 import run_event_study

    db_path = tmp_path / "test_market.db"
    conn = sqlite3.connect(str(db_path))
    _create_minimal_market_db(conn)
    conn.close()

    output_path = tmp_path / "event_study_v1.json"
    results = run_event_study(db_path=db_path, output_path=output_path)

    assert output_path.exists()
    assert "meta" in results
    assert "by_segment" in results
    assert "events" in results
    assert results["meta"]["total_bars"] > 0

    loaded = json.loads(output_path.read_text())
    assert loaded["meta"]["total_bars"] == results["meta"]["total_bars"]


# ---------------------------------------------------------------------------
# D3: regime_decomposition helpers
# ---------------------------------------------------------------------------


def test_d3_skips_when_no_d2_output(tmp_path: Path) -> None:
    from research_lab.diagnostics.regime_decomposition_v1 import run_regime_decomposition

    result = run_regime_decomposition(
        db_path=tmp_path / "missing.db",
        store_path=tmp_path / "missing_store.db",
        d2_output_path=tmp_path / "no_d2.json",
        output_path=tmp_path / "d3_out.json",
        force=False,
    )
    assert result["status"] == "SKIPPED"
    assert (tmp_path / "d3_out.json").exists()


def test_d3_skips_when_d2_condition_not_met(tmp_path: Path) -> None:
    from research_lab.diagnostics.regime_decomposition_v1 import run_regime_decomposition

    # Write D2 output with no qualifying segments
    d2_path = tmp_path / "event_study_v1.json"
    d2_data = {
        "p1_mature_edge_count": 0,
        "p1_mature_summary": {
            "S1": {"status": "INSUFFICIENT_SAMPLE", "n_events": 5},
            "S2": {"status": "INSUFFICIENT_SAMPLE", "n_events": 3},
            "S3": {"status": "OK", "mean_forward_return_bar4": -0.1, "p_value": 0.3, "n_events": 40},
            "S4": {"status": "OK", "mean_forward_return_bar4": 0.05, "p_value": 0.2, "n_events": 35},
            "S5": {"status": "OK", "mean_forward_return_bar4": -0.2, "p_value": 0.01, "n_events": 50},
            "S6": {"status": "INSUFFICIENT_SAMPLE", "n_events": 8},
        },
    }
    d2_path.write_text(json.dumps(d2_data))

    result = run_regime_decomposition(
        db_path=tmp_path / "missing.db",
        store_path=tmp_path / "missing_store.db",
        d2_output_path=d2_path,
        output_path=tmp_path / "d3_out.json",
        force=False,
    )
    assert result["status"] == "SKIPPED"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_minimal_market_db(conn: sqlite3.Connection) -> None:
    """Create minimal DB schema with a few candles to allow smoke run."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS candles (
            symbol TEXT, timeframe TEXT, open_time TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS funding (
            symbol TEXT, funding_time TEXT, funding_rate REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS open_interest (
            symbol TEXT, timestamp TEXT, oi_value REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS aggtrade_buckets (
            symbol TEXT, timeframe TEXT, bucket_time TEXT,
            taker_buy_volume REAL, taker_sell_volume REAL, tfi REAL, cvd REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS force_orders (
            symbol TEXT, event_time TEXT, side TEXT, qty REAL, price REAL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS daily_external_bias (
            date TEXT, etf_bias_5d REAL, dxy_close REAL
        )"""
    )

    base_ts = datetime(2022, 1, 2, 0, 0, tzinfo=timezone.utc)
    price = 46000.0
    for i in range(20):
        for tf, bar_minutes in [("15m", 15), ("1h", 60), ("4h", 240)]:
            tf_ts = (base_ts + timedelta(minutes=bar_minutes * i)).isoformat()
            conn.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?)",
                ("BTCUSDT", tf, tf_ts, price, price + 50, price - 50, price + 10, 1.0),
            )
        ts = base_ts + timedelta(minutes=15 * i)
        conn.execute(
            "INSERT INTO funding VALUES (?,?,?)",
            ("BTCUSDT", ts.isoformat(), 0.0001),
        )
        conn.execute(
            "INSERT INTO open_interest VALUES (?,?,?)",
            ("BTCUSDT", ts.isoformat(), 1_000_000.0),
        )
    conn.commit()

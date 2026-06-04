from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_lab.level_scanner import (  # noqa: E402
    OUTPUT_COLUMNS,
    ScannerConfig,
    SessionWindow,
    make_level_id,
    scan_levels,
)


def _ohlcv(periods: int = 96 * 3) -> pd.DataFrame:
    index = pd.date_range("2025-06-01T00:00:00Z", periods=periods, freq="15min")
    rows = []
    for idx, ts in enumerate(index):
        day = idx // 96
        intraday = idx % 96
        base = 10000.0 + day * 100.0
        high = base + 10.0
        low = base - 10.0
        close = base
        open_ = base

        if day == 0 and intraday == 10:
            high = 10150.0
        if day == 0 and intraday == 32:
            high = 10500.0  # 08:00 UTC, outside [00:00,08:00) Asia
        if day == 0 and intraday == 20:
            low = 9900.0

        # Two close swing highs and lows for equal-cluster tests.
        if idx == 110:
            high = 10300.0
            close = 10280.0
        if idx == 114:
            high = 10304.0
            close = 10282.0
        if idx == 118:
            high = 10450.0  # future sweep of the high cluster
        if idx == 130:
            low = 9800.0
            close = 9820.0
        if idx == 134:
            low = 9798.0
            close = 9822.0
        if idx == 138:
            low = 9600.0  # future sweep of the low cluster beyond ATR tolerance

        rows.append(
            {
                "Open": open_,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": 100.0 + (idx % 10),
            }
        )
    return pd.DataFrame(rows, index=index)


def _config(**kwargs) -> ScannerConfig:
    defaults = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "sessions": (SessionWindow("asia", "00:00", "08:00"),),
        "swing_left_bars": 1,
        "swing_right_bars": 1,
        "equal_cluster_min_hits": 2,
        "equal_cluster_lookback_bars": 20,
        "equal_cluster_tolerance_atr": 1.0,
        "round_intervals": (1000.0,),
    }
    defaults.update(kwargs)
    return ScannerConfig(**defaults)


def test_scan_levels_emits_fixed_26_column_schema() -> None:
    levels = scan_levels(_ohlcv(), _config())

    assert list(levels.columns) == OUTPUT_COLUMNS
    assert len(levels.columns) == 26
    assert levels["level_id"].is_unique
    assert {"session_extreme", "previous_period", "equal_cluster", "anchored_vwap", "round_number"} <= set(
        levels["category"]
    )


def test_level_id_hash_is_deterministic_and_uses_milestone_formula() -> None:
    formed_at = pd.Timestamp("2025-06-01T07:45:00Z")

    first = make_level_id(
        source="local",
        category="session_extreme",
        symbol="BTCUSDT",
        timeframe="15m",
        price=10150.0,
        formed_at=formed_at,
    )
    second = make_level_id(
        source="local",
        category="session_extreme",
        symbol="BTCUSDT",
        timeframe="15m",
        price=10150.0,
        formed_at=formed_at,
    )

    assert first == second
    assert len(first) == 16
    assert first != make_level_id(
        source="local",
        category="session_extreme",
        symbol="BTCUSDT",
        timeframe="15m",
        price=10151.0,
        formed_at=formed_at,
    )


def test_session_extremes_use_utc_start_inclusive_end_exclusive() -> None:
    config = _config(
        include_previous_periods=False,
        include_equal_clusters=False,
        include_anchored_vwap=False,
        include_round_numbers=False,
    )
    levels = scan_levels(_ohlcv(), config)
    asia_highs = levels[(levels["category"] == "session_extreme") & (levels["session_tag"] == "asia_high")]

    first_asia = asia_highs.iloc[0]
    assert first_asia["price"] == 10150.0
    assert first_asia["price"] != 10500.0
    assert first_asia["formed_at"] == pd.Timestamp("2025-06-01T07:45:00Z")
    assert first_asia["available_at"] == pd.Timestamp("2025-06-01T08:00:00Z")
    assert json.loads(first_asia["metadata_json"])["interval"] == "[start,end)"


def test_previous_day_levels_are_available_at_next_utc_day() -> None:
    config = _config(
        include_session_extremes=False,
        include_equal_clusters=False,
        include_anchored_vwap=False,
        include_round_numbers=False,
    )
    levels = scan_levels(_ohlcv(), config)
    pdh = levels[(levels["category"] == "previous_period") & (levels["period_tag"] == "PDH")].iloc[0]
    pdl = levels[(levels["category"] == "previous_period") & (levels["period_tag"] == "PDL")].iloc[0]

    assert pdh["price"] == 10500.0
    assert pdl["price"] == 9900.0
    assert pdh["available_at"] == pd.Timestamp("2025-06-02T00:00:00Z")
    assert pdl["available_at"] == pd.Timestamp("2025-06-02T00:00:00Z")


def test_equal_clusters_use_confirmed_pivots_and_record_swept_at() -> None:
    config = _config(
        include_session_extremes=False,
        include_previous_periods=False,
        include_anchored_vwap=False,
        include_round_numbers=False,
    )
    levels = scan_levels(_ohlcv(), config)
    high_cluster = levels[(levels["category"] == "equal_cluster") & (levels["side"] == "HIGH")].iloc[0]
    low_cluster = levels[(levels["category"] == "equal_cluster") & (levels["side"] == "LOW")].iloc[0]

    assert 10300.0 <= high_cluster["price"] <= 10304.0
    assert high_cluster["available_at"] > high_cluster["formed_at"]
    assert high_cluster["swept_at"] == pd.Timestamp("2025-06-02T05:30:00Z")
    assert json.loads(high_cluster["metadata_json"])["hit_count"] == 2
    assert 9798.0 <= low_cluster["price"] <= 9800.0
    assert low_cluster["swept_at"] == pd.Timestamp("2025-06-02T10:30:00Z")


def test_round_numbers_are_static_and_bounded_around_price_range() -> None:
    config = _config(
        include_session_extremes=False,
        include_previous_periods=False,
        include_equal_clusters=False,
        include_anchored_vwap=False,
        round_intervals=(1000.0,),
        round_padding_intervals=0,
    )
    levels = scan_levels(_ohlcv(), config)
    prices = set(levels["price"].tolist())

    assert levels["category"].unique().tolist() == ["round_number"]
    assert {9000.0, 10000.0}.issubset(prices)
    assert 12000.0 not in prices
    assert levels["formed_at"].nunique() == 1


def test_liquidation_placeholder_returns_empty_schema() -> None:
    config = _config(
        include_session_extremes=False,
        include_previous_periods=False,
        include_equal_clusters=False,
        include_anchored_vwap=False,
        include_round_numbers=False,
        include_liquidation_placeholder=True,
    )
    levels = scan_levels(_ohlcv(), config)

    assert levels.empty
    assert list(levels.columns) == OUTPUT_COLUMNS


def test_scanner_accepts_timestamp_column_and_normalizes_to_utc() -> None:
    frame = _ohlcv(12).reset_index().rename(columns={"index": "timestamp"})
    levels = scan_levels(frame, _config(include_previous_periods=False, include_equal_clusters=False))

    assert not levels.empty
    assert levels["formed_at"].iloc[0].tzinfo is not None


def test_scanner_module_does_not_import_trading_decision_models() -> None:
    source = Path("research_lab/level_scanner.py").read_text(encoding="utf-8")

    forbidden = ["SignalCandidate", "ExecutableSignal", "RiskGate", "Execution"]
    assert all(token not in source for token in forbidden)

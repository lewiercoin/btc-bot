from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_lab.analysis_trend_pullback_reaccept_feasibility import (
    AggBucket,
    Candle,
    SetupVariant,
    aggregate_tfi_60s,
    completed_4h_context,
    detect_equal_low_levels,
    find_reaccept_signal,
)
from research_lab.hypotheses.spec import load_hypothesis_spec


def _bar(index: int, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(
        open_time=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * index),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


def _h4(index: int, close: float) -> Candle:
    return Candle(
        open_time=datetime(2023, 11, 1, tzinfo=timezone.utc) + timedelta(hours=4 * index),
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1.0,
    )


def test_aggregate_tfi_60s_uses_only_current_15m_bucket() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    agg = {
        start + timedelta(minutes=i): AggBucket(start + timedelta(minutes=i), 2.0, 1.0, 0.0, 0.0)
        for i in range(15)
    }
    agg[start + timedelta(minutes=15)] = AggBucket(start + timedelta(minutes=15), 100.0, 0.0, 1.0, 1.0)

    assert aggregate_tfi_60s(agg, start) == 1 / 3


def test_completed_4h_context_excludes_current_unclosed_4h_candle() -> None:
    candles = [_h4(i, 100 + i) for i in range(205)]
    target = candles[-1].open_time + timedelta(hours=1)

    context = completed_4h_context(candles, target)

    assert candles[-1] not in context
    assert context[-1].open_time <= target - timedelta(hours=4)


def test_detect_equal_low_levels_respects_min_age_cutoff() -> None:
    candles = [_bar(i, 100, 102, 99 + (i % 2) * 0.02, 101) for i in range(60)]
    candles[54] = _bar(54, 100, 102, 80, 101)
    candles[55] = _bar(55, 100, 102, 80.01, 101)

    levels = detect_equal_low_levels(candles, trigger_idx=58, min_age_bars=5)

    assert all(level > 90 for level in levels)


def test_find_reaccept_signal_uses_prior_pullback_and_next_open_entry() -> None:
    candles_15m = [_bar(i, 100 + i * 0.1, 102 + i * 0.1, 99.0, 101 + i * 0.1) for i in range(80)]
    # Build a frozen equal-low cluster old enough to be known before trigger.
    candles_15m[45] = _bar(45, 105, 106, 100.0, 105)
    candles_15m[50] = _bar(50, 106, 107, 100.02, 106)
    # Prior pullback below frozen support, then trigger close back above it.
    candles_15m[72] = _bar(72, 104, 105, 99.7, 100.2)
    candles_15m[73] = _bar(73, 100.5, 103, 100.1, 101.5)
    candles_15m[74] = _bar(74, 101.6, 104, 101.2, 103)

    candles_4h = [_h4(i, 100 + i * 0.2) for i in range(230)]
    trigger_open = candles_15m[73].open_time
    candles_4h = [
        Candle(trigger_open - timedelta(hours=4 * (230 - i)), 100 + i, 101 + i, 99 + i, 100 + i, 1.0)
        for i in range(230)
    ]
    agg = {
        candles_15m[73].open_time + timedelta(minutes=i): AggBucket(
            candles_15m[73].open_time + timedelta(minutes=i), 2.0, 1.0, 0.0, 0.0
        )
        for i in range(15)
    }
    variant = SetupVariant("TEST", 0.001, 3, 0.05, 0.05)

    signal = find_reaccept_signal(candles_15m, candles_4h, agg, 73, variant)

    assert signal is not None
    assert signal.entry_idx == 74
    assert signal.entry_time == candles_15m[74].open_time
    assert "15m_reaccept_close" in signal.reasons


def test_find_reaccept_signal_rejects_without_prior_pullback() -> None:
    candles_15m = [_bar(i, 100, 102, 100.4, 101.5) for i in range(80)]
    candles_15m[45] = _bar(45, 100, 102, 100.0, 101)
    candles_15m[50] = _bar(50, 100, 102, 100.02, 101)
    candles_15m[73] = _bar(73, 101, 103, 99.7, 101.8)
    candles_15m[74] = _bar(74, 102, 104, 101, 103)
    trigger_open = candles_15m[73].open_time
    candles_4h = [
        Candle(trigger_open - timedelta(hours=4 * (230 - i)), 100 + i, 101 + i, 99 + i, 100 + i, 1.0)
        for i in range(230)
    ]
    agg = {
        candles_15m[73].open_time + timedelta(minutes=i): AggBucket(
            candles_15m[73].open_time + timedelta(minutes=i), 2.0, 1.0, 0.0, 0.0
        )
        for i in range(15)
    }

    assert find_reaccept_signal(candles_15m, candles_4h, agg, 73, SetupVariant("TEST", 0.001, 3, 0.05, 0.05)) is None


def test_trend_pullback_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/trend_pullback_reaccept.json"))

    assert spec.hypothesis_id == "trend_pullback_reaccept_v1"
    assert spec.status == "ACTIVE"
    assert "SHORT direction." in spec.out_of_scope

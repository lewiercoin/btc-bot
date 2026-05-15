from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from research_lab.analysis_btc_5m_multi_candle_event_setup_feasibility import (
    Candle,
    compute_range,
    find_reclaim_confirmation,
    find_snapback_confirmation,
    is_compressed,
)
from research_lab.hypotheses.spec import load_hypothesis_spec


def _bar(index: int, open_: float, high: float, low: float, close: float, volume: float = 1.0) -> Candle:
    return Candle(
        open_time=datetime(2024, 1, 1, 0, index * 5, tzinfo=timezone.utc),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def test_compute_range_uses_half_open_window() -> None:
    candles = [
        _bar(0, 100, 105, 99, 101),
        _bar(1, 101, 104, 98, 102),
        _bar(2, 102, 103, 97, 100),
    ]

    assert compute_range(candles, 0, 2) == (105, 98)


def test_reclaim_confirmation_starts_after_event_bar() -> None:
    candles = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 100, 102, 95, 96),
        _bar(2, 96, 99, 95, 98),
        _bar(3, 98, 103, 97, 101),
    ]

    confirm_idx = find_reclaim_confirmation(
        candles,
        event_idx=1,
        window_bars=2,
        direction="LONG",
        range_high=104,
        range_low=96,
    )

    assert confirm_idx == 3


def test_reclaim_confirmation_times_out_without_future_reclaim() -> None:
    candles = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 100, 102, 95, 96),
        _bar(2, 96, 99, 95, 98),
    ]

    assert (
        find_reclaim_confirmation(
            candles,
            event_idx=1,
            window_bars=1,
            direction="LONG",
            range_high=104,
            range_low=96,
        )
        is None
    )


def test_snapback_confirmation_uses_event_midpoint_after_event() -> None:
    candles = [
        _bar(0, 100, 101, 99, 100),
        _bar(1, 100, 101, 90, 92),
        _bar(2, 92, 94, 91, 93),
        _bar(3, 93, 98, 92, 97),
    ]

    assert find_snapback_confirmation(candles, event_idx=1, window_bars=3, direction="LONG") == 3


def test_is_compressed_uses_only_prior_widths() -> None:
    widths = [1.0] * 120
    widths[119] = 0.1

    assert is_compressed(widths, event_idx=120, lookback=96, threshold_quantile=0.25)

    widths[119] = 2.0
    assert not is_compressed(widths, event_idx=120, lookback=96, threshold_quantile=0.25)


def test_multi_candle_hypothesis_specs_are_valid() -> None:
    for path in (
        "research_lab/hypotheses/active/btc_5m_compression_fakeout_reclaim.json",
        "research_lab/hypotheses/active/btc_5m_crowded_unwind_reversal.json",
    ):
        spec = load_hypothesis_spec(Path(path))
        assert spec.status == "ACTIVE"
        assert spec.baseline_reference == "trial-00095"

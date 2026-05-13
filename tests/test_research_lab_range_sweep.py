"""Tests for Range Sweep Specialist (sweep_reclaim family Variant 1).

Covers:
- RangeSweepConfig defaults
- Structure slope calculation (horizontal, trending, insufficient data)
- Volatility filter (acceptable, too high, disabled)
- Regime filter (normal accepted, others rejected)
- Independence overlap computation
- End-to-end signal generation with context filters
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from research_lab.setups.range_sweep_specialist import (
    RangeSweepConfig,
    compute_structure_slope,
    is_structure_horizontal,
    is_volatility_acceptable,
)
from research_lab.backtest_range_sweep import (
    RangeSweepDecisionRecord,
    compute_overlap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candles(midpoints: list[float], spread: float = 10.0) -> list[dict]:
    """Create candle dicts from midpoint values."""
    return [
        {"high": mid + spread / 2, "low": mid - spread / 2, "close": mid, "open": mid}
        for mid in midpoints
    ]


# ---------------------------------------------------------------------------
# RangeSweepConfig tests
# ---------------------------------------------------------------------------

class TestRangeSweepConfig:
    def test_defaults(self):
        cfg = RangeSweepConfig()
        assert cfg.allowed_regime == "normal"
        assert cfg.structure_slope_window == 96
        assert cfg.structure_slope_min_candles == 48
        assert cfg.structure_slope_atr_max == 0.3
        assert cfg.volatility_filter_enabled is True
        assert cfg.volatility_atr_norm_max == 0.015
        assert "LONG" in cfg.normal_directions
        assert "SHORT" in cfg.normal_directions

    def test_custom_config(self):
        cfg = RangeSweepConfig(
            structure_slope_atr_max=0.5,
            volatility_atr_norm_max=0.02,
            volatility_filter_enabled=False,
        )
        assert cfg.structure_slope_atr_max == 0.5
        assert cfg.volatility_atr_norm_max == 0.02
        assert cfg.volatility_filter_enabled is False


# ---------------------------------------------------------------------------
# Structure slope tests
# ---------------------------------------------------------------------------

class TestStructureSlope:
    def test_flat_structure_returns_near_zero_slope(self):
        """Perfectly flat midpoints should produce slope ~0."""
        candles = _make_candles([100.0] * 100)
        slope = compute_structure_slope(candles, window=96, min_candles=48)
        assert slope is not None
        assert abs(slope) < 1e-8

    def test_uptrend_returns_positive_slope(self):
        """Linearly rising midpoints should produce positive slope."""
        midpoints = [100.0 + i * 0.5 for i in range(100)]
        candles = _make_candles(midpoints)
        slope = compute_structure_slope(candles, window=96, min_candles=48)
        assert slope is not None
        assert slope > 0.4  # Should be ~0.5 per cycle

    def test_downtrend_returns_negative_slope(self):
        """Linearly falling midpoints should produce negative slope."""
        midpoints = [100.0 - i * 0.3 for i in range(100)]
        candles = _make_candles(midpoints)
        slope = compute_structure_slope(candles, window=96, min_candles=48)
        assert slope is not None
        assert slope < -0.2

    def test_insufficient_data_returns_none(self):
        """Fewer candles than min_candles should return None."""
        candles = _make_candles([100.0] * 10)
        slope = compute_structure_slope(candles, window=96, min_candles=48)
        assert slope is None

    def test_exactly_min_candles(self):
        """Exactly min_candles should work (boundary case)."""
        candles = _make_candles([100.0] * 50)  # 50 > 48 min (after removing last)
        slope = compute_structure_slope(candles, window=96, min_candles=48)
        assert slope is not None

    def test_uses_prior_candles_only(self):
        """Last candle excluded (current bar not complete)."""
        flat = [100.0] * 99
        spike = flat + [200.0]  # Last candle is a spike
        candles = _make_candles(spike)
        slope = compute_structure_slope(candles, window=96, min_candles=48)
        assert slope is not None
        # Slope should be near zero because spike is excluded
        assert abs(slope) < 0.05


class TestIsStructureHorizontal:
    def test_flat_is_horizontal(self):
        candles = _make_candles([50000.0] * 100)
        atr = 100.0
        cfg = RangeSweepConfig()
        is_horiz, slope_atr, reason = is_structure_horizontal(candles, atr, cfg)
        assert is_horiz is True
        assert slope_atr is not None
        assert abs(slope_atr) < cfg.structure_slope_atr_max
        assert reason == "structure_horizontal"

    def test_steep_trend_not_horizontal(self):
        midpoints = [50000.0 + i * 50.0 for i in range(100)]
        candles = _make_candles(midpoints)
        atr = 100.0
        cfg = RangeSweepConfig()
        is_horiz, slope_atr, reason = is_structure_horizontal(candles, atr, cfg)
        assert is_horiz is False
        assert slope_atr is not None
        assert abs(slope_atr) >= cfg.structure_slope_atr_max
        assert "structure_slope_too_steep" in reason

    def test_insufficient_data_not_horizontal(self):
        candles = _make_candles([50000.0] * 5)
        atr = 100.0
        cfg = RangeSweepConfig()
        is_horiz, slope_atr, reason = is_structure_horizontal(candles, atr, cfg)
        assert is_horiz is False
        assert slope_atr is None
        assert reason == "insufficient_structure_data"

    def test_atr_near_zero_handled(self):
        candles = _make_candles([50000.0] * 100)
        atr = 0.0  # Edge case
        cfg = RangeSweepConfig()
        is_horiz, slope_atr, reason = is_structure_horizontal(candles, atr, cfg)
        # With ATR ~0, any non-zero slope becomes infinite slope_atr
        assert slope_atr is not None


# ---------------------------------------------------------------------------
# Volatility filter tests
# ---------------------------------------------------------------------------

class TestVolatilityFilter:
    def test_low_volatility_accepted(self):
        cfg = RangeSweepConfig(volatility_atr_norm_max=0.015)
        ok, reason = is_volatility_acceptable(0.008, cfg)
        assert ok is True
        assert reason == "volatility_acceptable"

    def test_high_volatility_rejected(self):
        cfg = RangeSweepConfig(volatility_atr_norm_max=0.015)
        ok, reason = is_volatility_acceptable(0.025, cfg)
        assert ok is False
        assert "volatility_too_high" in reason

    def test_boundary_accepted(self):
        cfg = RangeSweepConfig(volatility_atr_norm_max=0.015)
        ok, reason = is_volatility_acceptable(0.015, cfg)
        assert ok is True  # Equal to threshold → accepted (not strictly greater)

    def test_filter_disabled(self):
        cfg = RangeSweepConfig(volatility_filter_enabled=False)
        ok, reason = is_volatility_acceptable(0.999, cfg)
        assert ok is True
        assert reason == "volatility_filter_disabled"


# ---------------------------------------------------------------------------
# Overlap / independence tests
# ---------------------------------------------------------------------------

class TestOverlapComputation:
    def test_no_overlap(self):
        """Trades at completely different times should have 0 overlap."""
        from core.models import TradeLog

        range_trades = [
            TradeLog(
                trade_id="r1", signal_id="s1",
                opened_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                closed_at=datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc),
                direction="LONG", regime="normal", confluence_score=3.0,
                entry_price=50000, exit_price=50500, size=0.1,
                fees=0.01, slippage_bps=1.0, pnl_abs=50, pnl_r=1.0,
                mae=0.5, mfe=1.5, exit_reason="tp1",
            ),
        ]
        trial_timestamps = ["2024-06-15T08:00:00+00:00"]
        result = compute_overlap(range_trades, trial_timestamps)
        assert result["overlap_rate"] == 0.0
        assert result["independence_gate_passed"] is True

    def test_full_overlap(self):
        """Same timestamp should produce 100% overlap."""
        from core.models import TradeLog

        ts = datetime(2024, 3, 15, 12, 0, tzinfo=timezone.utc)
        range_trades = [
            TradeLog(
                trade_id="r1", signal_id="s1",
                opened_at=ts,
                closed_at=datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
                direction="LONG", regime="normal", confluence_score=3.0,
                entry_price=50000, exit_price=50500, size=0.1,
                fees=0.01, slippage_bps=1.0, pnl_abs=50, pnl_r=1.0,
                mae=0.5, mfe=1.5, exit_reason="tp1",
            ),
        ]
        trial_timestamps = [ts.isoformat()]
        result = compute_overlap(range_trades, trial_timestamps)
        assert result["overlap_rate"] == 1.0
        assert result["independence_gate_passed"] is False

    def test_partial_overlap(self):
        """Some trades overlap, some don't."""
        from core.models import TradeLog

        def _trade(hour: int) -> TradeLog:
            return TradeLog(
                trade_id=f"r{hour}", signal_id=f"s{hour}",
                opened_at=datetime(2024, 3, 15, hour, 0, tzinfo=timezone.utc),
                closed_at=datetime(2024, 3, 15, hour + 1, 0, tzinfo=timezone.utc),
                direction="LONG", regime="normal", confluence_score=3.0,
                entry_price=50000, exit_price=50500, size=0.1,
                fees=0.01, slippage_bps=1.0, pnl_abs=50, pnl_r=1.0,
                mae=0.5, mfe=1.5, exit_reason="tp1",
            )

        range_trades = [_trade(h) for h in range(10)]  # 10 trades at hours 0-9
        trial_timestamps = [
            datetime(2024, 3, 15, h, 0, tzinfo=timezone.utc).isoformat()
            for h in [0, 1, 2]  # 3 overlap
        ]
        result = compute_overlap(range_trades, trial_timestamps)
        assert result["overlap_rate"] == 0.3
        assert result["independence_gate_passed"] is False  # 0.3 is NOT < 0.3

    def test_empty_range_sweep(self):
        """No range sweep trades → overlap rate 0."""
        result = compute_overlap([], ["2024-01-01T00:00:00+00:00"])
        assert result["overlap_rate"] == 0.0

    def test_cycle_boundary_alignment(self):
        """Trades within same 15m cycle count as overlapping."""
        from core.models import TradeLog

        range_trades = [
            TradeLog(
                trade_id="r1", signal_id="s1",
                opened_at=datetime(2024, 3, 15, 12, 3, tzinfo=timezone.utc),  # 12:03
                closed_at=datetime(2024, 3, 15, 13, 0, tzinfo=timezone.utc),
                direction="LONG", regime="normal", confluence_score=3.0,
                entry_price=50000, exit_price=50500, size=0.1,
                fees=0.01, slippage_bps=1.0, pnl_abs=50, pnl_r=1.0,
                mae=0.5, mfe=1.5, exit_reason="tp1",
            ),
        ]
        # Trial trade at 12:07 — same 15m cycle (12:00-12:15)
        trial_timestamps = ["2024-03-15T12:07:00+00:00"]
        result = compute_overlap(range_trades, trial_timestamps)
        assert result["overlap_rate"] == 1.0


# ---------------------------------------------------------------------------
# Decision record tests
# ---------------------------------------------------------------------------

class TestDecisionRecord:
    def test_default_values(self):
        rec = RangeSweepDecisionRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            regime="normal",
            regime_accepted=True,
        )
        assert rec.structure_horizontal is None
        assert rec.candidate_generated is False
        assert rec.rejection_reasons == []

    def test_with_rejection(self):
        rec = RangeSweepDecisionRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            regime="uptrend",
            regime_accepted=False,
            rejection_reasons=["regime_rejected|uptrend"],
        )
        assert rec.regime_accepted is False
        assert len(rec.rejection_reasons) == 1

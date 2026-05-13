"""Tests for Trend Sweep Specialist (sweep_reclaim family Variant 2).

Covers:
- TrendSweepConfig defaults
- Regime trending filter (downtrend/uptrend accepted, others rejected)
- Direction mapping (counter-trend: downtrend→LONG, uptrend→SHORT)
- Volatility sufficient filter (enabled/disabled/boundary)
- Decision record defaults
"""

from __future__ import annotations

import pytest

from research_lab.setups.trend_sweep_specialist import (
    TrendSweepConfig,
    get_trend_directions,
    is_regime_trending,
    is_volatility_sufficient,
)
from research_lab.backtest_trend_sweep import TrendSweepDecisionRecord


# ---------------------------------------------------------------------------
# TrendSweepConfig tests
# ---------------------------------------------------------------------------

class TestTrendSweepConfig:
    def test_defaults(self):
        cfg = TrendSweepConfig()
        assert cfg.allowed_regimes == ("downtrend", "uptrend")
        assert cfg.downtrend_directions == ("LONG",)
        assert cfg.uptrend_directions == ("SHORT",)
        assert cfg.min_trend_cycles == 0
        assert cfg.volatility_filter_enabled is False
        assert cfg.volatility_atr_norm_min == 0.006

    def test_custom_config(self):
        cfg = TrendSweepConfig(
            min_trend_cycles=10,
            volatility_filter_enabled=True,
            volatility_atr_norm_min=0.01,
        )
        assert cfg.min_trend_cycles == 10
        assert cfg.volatility_filter_enabled is True
        assert cfg.volatility_atr_norm_min == 0.01


# ---------------------------------------------------------------------------
# Regime filter tests
# ---------------------------------------------------------------------------

class TestRegimeTrending:
    def test_downtrend_accepted(self):
        cfg = TrendSweepConfig()
        ok, reason = is_regime_trending("downtrend", cfg)
        assert ok is True
        assert "regime_accepted" in reason

    def test_uptrend_accepted(self):
        cfg = TrendSweepConfig()
        ok, reason = is_regime_trending("uptrend", cfg)
        assert ok is True
        assert "regime_accepted" in reason

    def test_normal_rejected(self):
        cfg = TrendSweepConfig()
        ok, reason = is_regime_trending("normal", cfg)
        assert ok is False
        assert "regime_rejected" in reason

    def test_compression_rejected(self):
        cfg = TrendSweepConfig()
        ok, reason = is_regime_trending("compression", cfg)
        assert ok is False

    def test_crowded_leverage_rejected(self):
        cfg = TrendSweepConfig()
        ok, reason = is_regime_trending("crowded_leverage", cfg)
        assert ok is False

    def test_post_liquidation_rejected(self):
        cfg = TrendSweepConfig()
        ok, reason = is_regime_trending("post_liquidation", cfg)
        assert ok is False


# ---------------------------------------------------------------------------
# Direction mapping tests (counter-trend)
# ---------------------------------------------------------------------------

class TestGetTrendDirections:
    def test_downtrend_gives_long(self):
        cfg = TrendSweepConfig()
        dirs = get_trend_directions("downtrend", cfg)
        assert dirs == ("LONG",)

    def test_uptrend_gives_short(self):
        cfg = TrendSweepConfig()
        dirs = get_trend_directions("uptrend", cfg)
        assert dirs == ("SHORT",)

    def test_normal_gives_empty(self):
        cfg = TrendSweepConfig()
        dirs = get_trend_directions("normal", cfg)
        assert dirs == ()

    def test_unknown_gives_empty(self):
        cfg = TrendSweepConfig()
        dirs = get_trend_directions("unknown_regime", cfg)
        assert dirs == ()

    def test_custom_directions(self):
        cfg = TrendSweepConfig(
            downtrend_directions=("LONG", "SHORT"),
            uptrend_directions=("LONG",),
        )
        assert get_trend_directions("downtrend", cfg) == ("LONG", "SHORT")
        assert get_trend_directions("uptrend", cfg) == ("LONG",)


# ---------------------------------------------------------------------------
# Volatility filter tests
# ---------------------------------------------------------------------------

class TestVolatilitySufficient:
    def test_filter_disabled(self):
        cfg = TrendSweepConfig(volatility_filter_enabled=False)
        ok, reason = is_volatility_sufficient(0.001, cfg)
        assert ok is True
        assert reason == "volatility_filter_disabled"

    def test_sufficient_volatility(self):
        cfg = TrendSweepConfig(volatility_filter_enabled=True, volatility_atr_norm_min=0.006)
        ok, reason = is_volatility_sufficient(0.01, cfg)
        assert ok is True
        assert reason == "volatility_sufficient"

    def test_insufficient_volatility(self):
        cfg = TrendSweepConfig(volatility_filter_enabled=True, volatility_atr_norm_min=0.006)
        ok, reason = is_volatility_sufficient(0.003, cfg)
        assert ok is False
        assert "volatility_too_low" in reason

    def test_boundary_accepted(self):
        cfg = TrendSweepConfig(volatility_filter_enabled=True, volatility_atr_norm_min=0.006)
        ok, reason = is_volatility_sufficient(0.006, cfg)
        assert ok is True  # Equal to threshold → accepted (not strictly less)


# ---------------------------------------------------------------------------
# Decision record tests
# ---------------------------------------------------------------------------

class TestTrendDecisionRecord:
    def test_default_values(self):
        rec = TrendSweepDecisionRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            regime="downtrend",
            regime_accepted=True,
        )
        assert rec.volatility_accepted is None
        assert rec.candidate_generated is False
        assert rec.rejection_reasons == []

    def test_with_rejection(self):
        rec = TrendSweepDecisionRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            regime="normal",
            regime_accepted=False,
            rejection_reasons=["regime_rejected|normal"],
        )
        assert rec.regime_accepted is False
        assert len(rec.rejection_reasons) == 1

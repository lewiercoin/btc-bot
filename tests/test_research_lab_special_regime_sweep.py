"""Tests for Special Regime Sweep Specialist (sweep_reclaim family Variant 3).

Covers:
- SpecialRegimeSweepConfig defaults
- Regime special filter (crowded_leverage/post_liquidation accepted, others rejected)
- Direction mapping (LONG only per V1+V2 evidence)
- Decision record defaults
- Overlap computation
"""

from __future__ import annotations

import pytest

from research_lab.setups.special_regime_sweep_specialist import (
    SpecialRegimeSweepConfig,
    get_special_directions,
    is_regime_special,
)
from research_lab.backtest_special_regime_sweep import (
    SpecialRegimeDecisionRecord,
    compute_overlap,
)


# ---------------------------------------------------------------------------
# SpecialRegimeSweepConfig tests
# ---------------------------------------------------------------------------

class TestSpecialRegimeSweepConfig:
    def test_defaults(self):
        cfg = SpecialRegimeSweepConfig()
        assert cfg.allowed_regimes == ("crowded_leverage", "post_liquidation")
        assert cfg.directions == ("LONG",)
        assert cfg.min_regime_cycles == 0

    def test_custom_config(self):
        cfg = SpecialRegimeSweepConfig(
            min_regime_cycles=5,
            directions=("LONG", "SHORT"),
        )
        assert cfg.min_regime_cycles == 5
        assert cfg.directions == ("LONG", "SHORT")


# ---------------------------------------------------------------------------
# Regime filter tests
# ---------------------------------------------------------------------------

class TestRegimeSpecial:
    def test_crowded_leverage_accepted(self):
        cfg = SpecialRegimeSweepConfig()
        ok, reason = is_regime_special("crowded_leverage", cfg)
        assert ok is True
        assert "regime_accepted" in reason

    def test_post_liquidation_accepted(self):
        cfg = SpecialRegimeSweepConfig()
        ok, reason = is_regime_special("post_liquidation", cfg)
        assert ok is True
        assert "regime_accepted" in reason

    def test_normal_rejected(self):
        cfg = SpecialRegimeSweepConfig()
        ok, reason = is_regime_special("normal", cfg)
        assert ok is False
        assert "regime_rejected" in reason

    def test_downtrend_rejected(self):
        cfg = SpecialRegimeSweepConfig()
        ok, reason = is_regime_special("downtrend", cfg)
        assert ok is False

    def test_uptrend_rejected(self):
        cfg = SpecialRegimeSweepConfig()
        ok, reason = is_regime_special("uptrend", cfg)
        assert ok is False

    def test_compression_rejected(self):
        cfg = SpecialRegimeSweepConfig()
        ok, reason = is_regime_special("compression", cfg)
        assert ok is False


# ---------------------------------------------------------------------------
# Direction mapping tests
# ---------------------------------------------------------------------------

class TestGetSpecialDirections:
    def test_default_long_only(self):
        cfg = SpecialRegimeSweepConfig()
        dirs = get_special_directions(cfg)
        assert dirs == ("LONG",)

    def test_custom_directions(self):
        cfg = SpecialRegimeSweepConfig(directions=("LONG", "SHORT"))
        dirs = get_special_directions(cfg)
        assert dirs == ("LONG", "SHORT")


# ---------------------------------------------------------------------------
# Decision record tests
# ---------------------------------------------------------------------------

class TestSpecialRegimeDecisionRecord:
    def test_default_values(self):
        rec = SpecialRegimeDecisionRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            regime="crowded_leverage",
            regime_accepted=True,
        )
        assert rec.candidate_generated is False
        assert rec.candidate_direction is None
        assert rec.rejection_reasons == []

    def test_with_rejection(self):
        rec = SpecialRegimeDecisionRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            regime="normal",
            regime_accepted=False,
            rejection_reasons=["regime_rejected|normal"],
        )
        assert rec.regime_accepted is False
        assert len(rec.rejection_reasons) == 1


# ---------------------------------------------------------------------------
# Overlap computation tests
# ---------------------------------------------------------------------------

class TestOverlapComputation:
    def _make_mock_trade(self, opened_at_iso: str):
        """Create a minimal mock trade object with opened_at."""
        from unittest.mock import MagicMock
        from datetime import datetime, timezone
        trade = MagicMock()
        trade.opened_at = datetime.fromisoformat(opened_at_iso.replace("Z", "+00:00"))
        return trade

    def test_no_overlap(self):
        trades = [self._make_mock_trade("2024-01-01T00:00:00+00:00")]
        trial_ts = ["2024-06-01T00:00:00+00:00"]
        result = compute_overlap(trades, trial_ts)
        assert result["overlap_rate"] == 0.0
        assert result["independence_gate_passed"] is True

    def test_full_overlap(self):
        trades = [self._make_mock_trade("2024-01-01T00:00:00+00:00")]
        trial_ts = ["2024-01-01T00:00:00+00:00"]
        result = compute_overlap(trades, trial_ts)
        assert result["overlap_rate"] == 1.0
        assert result["independence_gate_passed"] is False

    def test_partial_overlap(self):
        trades = [
            self._make_mock_trade("2024-01-01T00:00:00+00:00"),
            self._make_mock_trade("2024-01-01T01:00:00+00:00"),
            self._make_mock_trade("2024-01-01T02:00:00+00:00"),
            self._make_mock_trade("2024-01-01T03:00:00+00:00"),
        ]
        trial_ts = ["2024-01-01T00:00:00+00:00"]
        result = compute_overlap(trades, trial_ts)
        assert result["overlap_rate"] == 0.25
        assert result["independence_gate_passed"] is True

    def test_empty_trades(self):
        result = compute_overlap([], ["2024-01-01T00:00:00+00:00"])
        assert result["overlap_rate"] == 0.0
        assert result["independence_gate_passed"] is True

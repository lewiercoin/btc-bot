"""Tests for Session Sweep Specialist (sweep_reclaim family Variant 4).

Covers:
- SessionSweepConfig defaults and custom settings
- Session time-of-day filter (Asia hours 00:00-08:00 UTC)
- Wrapping session windows (e.g. 22:00-06:00)
- Direction mapping (LONG only per V1-V3 evidence)
- Decision record defaults
- Overlap computation
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from research_lab.setups.session_sweep_specialist import (
    SessionSweepConfig,
    get_session_directions,
    is_in_session,
)
from research_lab.backtest_session_sweep import (
    SessionDecisionRecord,
    compute_overlap,
)


# ---------------------------------------------------------------------------
# SessionSweepConfig tests
# ---------------------------------------------------------------------------

class TestSessionSweepConfig:
    def test_defaults(self):
        cfg = SessionSweepConfig()
        assert cfg.session_start_hour == 0
        assert cfg.session_end_hour == 8
        assert cfg.directions == ("LONG",)
        assert cfg.session_label == "asia"

    def test_custom_config(self):
        cfg = SessionSweepConfig(
            session_start_hour=13,
            session_end_hour=21,
            directions=("LONG", "SHORT"),
            session_label="us",
        )
        assert cfg.session_start_hour == 13
        assert cfg.session_end_hour == 21
        assert cfg.directions == ("LONG", "SHORT")
        assert cfg.session_label == "us"


# ---------------------------------------------------------------------------
# Session filter tests
# ---------------------------------------------------------------------------

class TestIsInSession:
    def test_asia_hour_0_accepted(self):
        cfg = SessionSweepConfig()
        ts = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        ok, reason = is_in_session(ts, cfg)
        assert ok is True
        assert "session_accepted" in reason

    def test_asia_hour_7_accepted(self):
        cfg = SessionSweepConfig()
        ts = datetime(2024, 1, 1, 7, 30, tzinfo=timezone.utc)
        ok, reason = is_in_session(ts, cfg)
        assert ok is True

    def test_asia_hour_8_rejected(self):
        """Hour 8 is exclusive end — should be rejected."""
        cfg = SessionSweepConfig()
        ts = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
        ok, reason = is_in_session(ts, cfg)
        assert ok is False
        assert "session_rejected" in reason

    def test_asia_hour_12_rejected(self):
        cfg = SessionSweepConfig()
        ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        ok, reason = is_in_session(ts, cfg)
        assert ok is False

    def test_asia_hour_23_rejected(self):
        cfg = SessionSweepConfig()
        ts = datetime(2024, 1, 1, 23, 0, tzinfo=timezone.utc)
        ok, reason = is_in_session(ts, cfg)
        assert ok is False

    def test_us_session_accepted(self):
        cfg = SessionSweepConfig(session_start_hour=13, session_end_hour=21, session_label="us")
        ts = datetime(2024, 1, 1, 15, 0, tzinfo=timezone.utc)
        ok, reason = is_in_session(ts, cfg)
        assert ok is True
        assert "us" in reason

    def test_us_session_rejected(self):
        cfg = SessionSweepConfig(session_start_hour=13, session_end_hour=21, session_label="us")
        ts = datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc)
        ok, reason = is_in_session(ts, cfg)
        assert ok is False

    def test_wrapping_session_late_accepted(self):
        """Test wrapping window e.g. 22:00-06:00 UTC — hour 23 should be accepted."""
        cfg = SessionSweepConfig(session_start_hour=22, session_end_hour=6, session_label="wrap")
        ts = datetime(2024, 1, 1, 23, 0, tzinfo=timezone.utc)
        ok, reason = is_in_session(ts, cfg)
        assert ok is True

    def test_wrapping_session_early_accepted(self):
        """Test wrapping window — hour 3 should be accepted."""
        cfg = SessionSweepConfig(session_start_hour=22, session_end_hour=6, session_label="wrap")
        ts = datetime(2024, 1, 2, 3, 0, tzinfo=timezone.utc)
        ok, reason = is_in_session(ts, cfg)
        assert ok is True

    def test_wrapping_session_midday_rejected(self):
        """Test wrapping window — hour 12 should be rejected."""
        cfg = SessionSweepConfig(session_start_hour=22, session_end_hour=6, session_label="wrap")
        ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        ok, reason = is_in_session(ts, cfg)
        assert ok is False

    def test_naive_timestamp_uses_hour_directly(self):
        """Naive (no tzinfo) timestamps use .hour directly."""
        cfg = SessionSweepConfig()
        ts = datetime(2024, 1, 1, 3, 0)  # naive
        ok, reason = is_in_session(ts, cfg)
        assert ok is True

    def test_non_utc_timezone_converted(self):
        """Non-UTC timezone should be converted to UTC before checking."""
        cfg = SessionSweepConfig()
        # 10:00 UTC+5 = 05:00 UTC → in Asia session
        tz_plus5 = timezone(timedelta(hours=5))
        ts = datetime(2024, 1, 1, 10, 0, tzinfo=tz_plus5)
        ok, reason = is_in_session(ts, cfg)
        assert ok is True

    def test_reason_includes_hour(self):
        cfg = SessionSweepConfig()
        ts = datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc)
        ok, reason = is_in_session(ts, cfg)
        assert "hour=3" in reason


# ---------------------------------------------------------------------------
# Direction mapping tests
# ---------------------------------------------------------------------------

class TestGetSessionDirections:
    def test_default_long_only(self):
        cfg = SessionSweepConfig()
        dirs = get_session_directions(cfg)
        assert dirs == ("LONG",)

    def test_custom_directions(self):
        cfg = SessionSweepConfig(directions=("LONG", "SHORT"))
        dirs = get_session_directions(cfg)
        assert dirs == ("LONG", "SHORT")


# ---------------------------------------------------------------------------
# Decision record tests
# ---------------------------------------------------------------------------

class TestSessionDecisionRecord:
    def test_default_values(self):
        rec = SessionDecisionRecord(
            timestamp="2024-01-01T00:00:00+00:00",
            utc_hour=0,
            regime="normal",
            session_accepted=True,
        )
        assert rec.candidate_generated is False
        assert rec.candidate_direction is None
        assert rec.rejection_reasons == []
        assert rec.utc_hour == 0

    def test_with_rejection(self):
        rec = SessionDecisionRecord(
            timestamp="2024-01-01T12:00:00+00:00",
            utc_hour=12,
            regime="downtrend",
            session_accepted=False,
            rejection_reasons=["session_rejected|asia|hour=12"],
        )
        assert rec.session_accepted is False
        assert len(rec.rejection_reasons) == 1


# ---------------------------------------------------------------------------
# Overlap computation tests
# ---------------------------------------------------------------------------

class TestOverlapComputation:
    def _make_mock_trade(self, opened_at_iso: str):
        from unittest.mock import MagicMock
        trade = MagicMock()
        trade.opened_at = datetime.fromisoformat(opened_at_iso.replace("Z", "+00:00"))
        return trade

    def test_no_overlap(self):
        trades = [self._make_mock_trade("2024-01-01T03:00:00+00:00")]
        trial_ts = ["2024-06-01T15:00:00+00:00"]
        result = compute_overlap(trades, trial_ts)
        assert result["overlap_rate"] == 0.0
        assert result["independence_gate_passed"] is True

    def test_full_overlap(self):
        trades = [self._make_mock_trade("2024-01-01T03:00:00+00:00")]
        trial_ts = ["2024-01-01T03:00:00+00:00"]
        result = compute_overlap(trades, trial_ts)
        assert result["overlap_rate"] == 1.0
        assert result["independence_gate_passed"] is False

    def test_partial_overlap(self):
        trades = [
            self._make_mock_trade("2024-01-01T01:00:00+00:00"),
            self._make_mock_trade("2024-01-01T02:00:00+00:00"),
            self._make_mock_trade("2024-01-01T03:00:00+00:00"),
            self._make_mock_trade("2024-01-01T04:00:00+00:00"),
        ]
        trial_ts = ["2024-01-01T01:00:00+00:00"]
        result = compute_overlap(trades, trial_ts)
        assert result["overlap_rate"] == 0.25
        assert result["independence_gate_passed"] is True

    def test_empty_trades(self):
        result = compute_overlap([], ["2024-01-01T03:00:00+00:00"])
        assert result["overlap_rate"] == 0.0
        assert result["independence_gate_passed"] is True

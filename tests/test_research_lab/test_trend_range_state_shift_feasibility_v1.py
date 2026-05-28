"""Smoke tests for TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1 diagnostic.

Tests cover:
- ADX/CHOP calculation correctness (completed bars only)
- State machine determinism (latched range/trend, staleness)
- First eligible event after 150-candle warmup
- Entry and return start equal i+1
- ADX lag audit computation
- Controls are isolated and deterministic
- Reproducibility
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from research_lab.diagnostics.trend_range_state_shift_feasibility_v1 import (
    Candle,
    DiagnosticConfig,
    IndicatorState,
    TransitionEvent,
    build_all_cohorts,
    build_main_event,
    compute_indicators,
    compute_lag_audit,
    favorable_move,
    adverse_move,
    run_state_machine,
)


def _make_candle(index: int, open_: float, high: float, low: float, close: float, minutes_offset: int = 0) -> Candle:
    """Helper to create a candle at a given index."""
    return Candle(
        index=index,
        open_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100.0,
    )


def _make_trending_candles(n: int, start_price: float = 50000.0, trend: float = 50.0) -> list[Candle]:
    """Create n candles with a clear uptrend for testing indicator warmup."""
    base_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    candles = []
    for i in range(n):
        base = start_price + i * trend
        candles.append(Candle(
            index=i,
            open_time=base_time + timedelta(minutes=i * 15),
            open=base,
            high=base + abs(trend) * 0.8,
            low=base - abs(trend) * 0.3,
            close=base + trend * 0.5,
            volume=100.0,
        ))
    return candles


def _make_range_then_trend_candles(
    n_range: int = 200,
    n_trend: int = 50,
    range_price: float = 50000.0,
    trend_magnitude: float = 200.0,
) -> list[Candle]:
    """Create candles that start in a range and then break into a trend."""
    base_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    candles = []
    idx = 0

    # Range phase: small oscillation
    for i in range(n_range):
        noise = 20.0 * (1 if i % 2 == 0 else -1)
        candles.append(Candle(
            index=idx,
            open_time=base_time + timedelta(minutes=idx * 15),
            open=range_price + noise,
            high=range_price + abs(noise) + 10,
            low=range_price - abs(noise) - 10,
            close=range_price - noise,
            volume=100.0,
        ))
        idx += 1

    # Trend phase: strong uptrend
    base = range_price
    for i in range(n_trend):
        base += trend_magnitude
        candles.append(Candle(
            index=idx,
            open_time=base_time + timedelta(minutes=idx * 15),
            open=base - trend_magnitude * 0.2,
            high=base + trend_magnitude * 0.3,
            low=base - trend_magnitude * 0.4,
            close=base,
            volume=150.0,
        ))
        idx += 1

    return candles


class TestIndicatorComputation:
    """Test ADX and CHOP calculations."""

    def test_indicators_none_during_warmup(self):
        """Indicators should be None for bars that lack sufficient history."""
        candles = _make_trending_candles(30)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        # First valid ADX requires di_period + adx_smoothing - 1 = 27 bars
        # But CHOP needs chop_period - 1 = 13 bars
        # So first fully valid bar is at index 27
        for i in range(config.di_period + config.adx_smoothing - 1):
            assert indicators[i] is None, f"Expected None at bar {i}"

    def test_indicators_valid_after_warmup(self):
        """Indicators should be non-None after sufficient bars."""
        candles = _make_trending_candles(200)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        first_valid = config.di_period + config.adx_smoothing - 1
        # At least some bars after first_valid should have valid indicators
        valid_count = sum(1 for ind in indicators[first_valid:] if ind is not None)
        assert valid_count > 0, "No valid indicators after warmup"

    def test_adx_non_negative(self):
        """ADX should always be >= 0."""
        candles = _make_trending_candles(200)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        for ind in indicators:
            if ind is not None:
                assert ind.adx >= 0, f"ADX negative: {ind.adx}"

    def test_chop_in_range(self):
        """CHOP should be in [0, 100] range."""
        candles = _make_trending_candles(200)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        for ind in indicators:
            if ind is not None:
                assert 0 <= ind.chop <= 100, f"CHOP out of range: {ind.chop}"

    def test_di_non_negative(self):
        """+DI and -DI should be >= 0."""
        candles = _make_trending_candles(200)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        for ind in indicators:
            if ind is not None:
                assert ind.plus_di >= 0, f"+DI negative: {ind.plus_di}"
                assert ind.minus_di >= 0, f"-DI negative: {ind.minus_di}"

    def test_indicators_use_only_completed_bars(self):
        """Indicator at bar i should not change if future bars are added."""
        candles = _make_trending_candles(200)
        config = DiagnosticConfig()
        indicators_200 = compute_indicators(candles, config)

        # Add 50 more bars
        extended = candles + _make_trending_candles(50, start_price=60000.0)
        for i, c in enumerate(extended):
            extended[i] = Candle(i, c.open_time, c.open, c.high, c.low, c.close, c.volume)
        indicators_250 = compute_indicators(extended, config)

        # First 200 bars should have same indicators
        for i in range(200):
            if indicators_200[i] is None:
                assert indicators_250[i] is None
            else:
                assert indicators_250[i] is not None
                assert abs(indicators_200[i].adx - indicators_250[i].adx) < 1e-10
                assert abs(indicators_200[i].chop - indicators_250[i].chop) < 1e-10


class TestStateMachine:
    """Test the latched state machine."""

    def test_no_events_before_warmup(self):
        """No events should be generated before 150-candle warmup."""
        candles = _make_range_then_trend_candles(n_range=100, n_trend=50)
        config = DiagnosticConfig(warmup_bars=150)
        indicators = compute_indicators(candles, config)
        events = run_state_machine(candles, indicators, config)
        for evt in events:
            assert evt.detection_bar >= config.warmup_bars, (
                f"Event at bar {evt.detection_bar} before warmup {config.warmup_bars}"
            )

    def test_state_machine_deterministic(self):
        """Running state machine twice on same data gives same results."""
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        events1 = run_state_machine(candles, indicators, config)
        events2 = run_state_machine(candles, indicators, config)
        assert len(events1) == len(events2)
        for e1, e2 in zip(events1, events2):
            assert e1.detection_bar == e2.detection_bar
            assert e1.direction == e2.direction

    def test_staleness_limit_enforced(self):
        """Events with stale range (> 12 bars ago) should not be generated."""
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        events = run_state_machine(candles, indicators, config)
        for evt in events:
            gap = evt.detection_bar - evt.last_explicit_range_bar
            assert gap <= config.staleness_limit, (
                f"Staleness {gap} exceeds limit {config.staleness_limit}"
            )

    def test_transition_requires_prior_range(self):
        """Events should only fire when prior latched state was RANGE."""
        # All events have a last_explicit_range_bar that was in latched RANGE state
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        events = run_state_machine(candles, indicators, config)
        for evt in events:
            # The last_explicit_range_bar should have indicators that satisfy range state
            ind = indicators[evt.last_explicit_range_bar]
            if ind is not None:
                assert ind.adx <= config.adx_range_threshold or ind.chop >= config.chop_range_threshold


class TestEntryTiming:
    """Test that entry and returns start at i+1."""

    def test_entry_at_i_plus_1(self):
        """Entry candidate bar should be detection_bar + 1."""
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        events = run_state_machine(candles, indicators, config)
        for te in events:
            evt = build_main_event(candles, te, config)
            if evt:
                assert evt.entry_candidate_bar == te.detection_bar + 1
                assert evt.return_start_bar == te.detection_bar + 1

    def test_return_start_equals_entry(self):
        """Return start bar should equal entry candidate bar."""
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        events = run_state_machine(candles, indicators, config)
        for te in events:
            evt = build_main_event(candles, te, config)
            if evt:
                assert evt.return_start_bar == evt.entry_candidate_bar


class TestLagAudit:
    """Test ADX lag audit computation."""

    def test_lag_audit_computed_for_main(self):
        """Main events should have lag_audit field populated."""
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        events = run_state_machine(candles, indicators, config)
        for te in events:
            evt = build_main_event(candles, te, config)
            if evt:
                assert evt.lag_audit is not None
                assert "adx_lag_bars" in evt.lag_audit
                assert "raw_move_start_bar" in evt.lag_audit
                assert "lag_mfe_consumed_pct" in evt.lag_audit

    def test_lag_audit_non_negative(self):
        """ADX lag bars should be >= 0."""
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        events = run_state_machine(candles, indicators, config)
        for te in events:
            evt = build_main_event(candles, te, config)
            if evt and evt.lag_audit:
                assert evt.lag_audit["adx_lag_bars"] >= 0

    def test_lag_consumed_in_valid_range(self):
        """Lag MFE consumed should be in [0, 1]."""
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        events = run_state_machine(candles, indicators, config)
        for te in events:
            evt = build_main_event(candles, te, config)
            if evt and evt.lag_audit:
                assert 0 <= evt.lag_audit["lag_mfe_consumed_pct"] <= 1.0


class TestControlsIsolation:
    """Test that controls are isolated and deterministic."""

    def test_controls_reproducible(self):
        """Running build_all_cohorts twice should give identical counts."""
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        cohorts1 = build_all_cohorts(candles, indicators, config)
        cohorts2 = build_all_cohorts(candles, indicators, config)
        for name in cohorts1:
            assert len(cohorts1[name]) == len(cohorts2[name]), f"Cohort {name} not reproducible"

    def test_shifted_entry_uses_i_plus_3(self):
        """Shifted entry control should have entry at detection_bar + 3."""
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        cohorts = build_all_cohorts(candles, indicators, config)
        for evt in cohorts["control_shifted_entry"]:
            assert evt.entry_candidate_bar == evt.detection_bar + config.shifted_entry_delay_bars

    def test_random_offset_shifted_by_137(self):
        """Random offset events should be shifted by +137 from a main event."""
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        cohorts = build_all_cohorts(candles, indicators, config)
        main_bars = {e.detection_bar for e in cohorts["main_range_to_trend"]}
        for evt in cohorts["control_random_offset"]:
            source = evt.metadata.get("source_detection_bar")
            if source is not None:
                assert evt.detection_bar == source + config.random_offset_bars


class TestMFECalculation:
    """Test MFE/MAE helper functions."""

    def test_favorable_move_long(self):
        """Long favorable move should be max high - reference."""
        candles = [
            _make_candle(0, 100, 110, 90, 105),
            _make_candle(1, 105, 120, 95, 115),
            _make_candle(2, 115, 130, 100, 125),
        ]
        result = favorable_move(candles, 0, 2, 100.0, "LONG")
        assert result == 30.0  # 130 - 100

    def test_favorable_move_short(self):
        """Short favorable move should be reference - min low."""
        candles = [
            _make_candle(0, 100, 110, 90, 95),
            _make_candle(1, 95, 100, 80, 85),
            _make_candle(2, 85, 90, 70, 75),
        ]
        result = favorable_move(candles, 0, 2, 100.0, "SHORT")
        assert result == 30.0  # 100 - 70

    def test_adverse_move_long(self):
        """Long adverse move should be reference - min low."""
        candles = [
            _make_candle(0, 100, 110, 85, 105),
            _make_candle(1, 105, 115, 90, 110),
        ]
        result = adverse_move(candles, 0, 1, 100.0, "LONG")
        assert result == 15.0  # 100 - 85

    def test_adverse_move_short(self):
        """Short adverse move should be max high - reference."""
        candles = [
            _make_candle(0, 100, 115, 90, 95),
            _make_candle(1, 95, 110, 85, 90),
        ]
        result = adverse_move(candles, 0, 1, 100.0, "SHORT")
        assert result == 15.0  # 115 - 100


class TestDiagnosticReproducibility:
    """Test that the full diagnostic produces reproducible results."""

    def test_full_pipeline_no_crash(self):
        """Full pipeline should run without errors on synthetic data."""
        candles = _make_range_then_trend_candles(n_range=200, n_trend=100)
        config = DiagnosticConfig()
        indicators = compute_indicators(candles, config)
        cohorts = build_all_cohorts(candles, indicators, config)
        # Should not crash; cohorts dict should have expected keys
        expected_keys = {
            "main_range_to_trend",
            "control_simple_volatility",
            "control_adx_only",
            "control_chop_only",
            "control_shifted_entry",
            "control_same_state_non_transition",
            "control_opposite_regime",
            "control_random_offset",
        }
        assert set(cohorts.keys()) == expected_keys

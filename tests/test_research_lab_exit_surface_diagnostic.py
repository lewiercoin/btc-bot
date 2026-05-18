from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_lab.analysis_trial_00095_exit_surface_diagnostic import (
    Candle,
    ExitVariant,
    FrozenEntry,
    compute_metrics,
    simulate_variant,
)
from research_lab.hypotheses.spec import load_hypothesis_spec


def _entry(direction: str = "LONG") -> FrozenEntry:
    entry = 100.0
    stop = 90.0 if direction == "LONG" else 110.0
    return FrozenEntry(
        trade_id="t1",
        signal_id="s1",
        opened_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        closed_at=datetime(2024, 1, 1, 1, tzinfo=timezone.utc),
        direction=direction,
        regime="uptrend",
        entry_price=entry,
        stop_loss=stop,
        tp1=120.0 if direction == "LONG" else 80.0,
        tp2=130.0 if direction == "LONG" else 70.0,
        baseline_pnl_r=1.0,
        baseline_exit_reason="TP",
    )


def _candle(index: int, high: float, low: float, close: float = 100.0) -> Candle:
    return Candle(
        open_time=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * index),
        open=100.0,
        high=high,
        low=low,
        close=close,
    )


def test_adverse_first_intrabar_conflict_uses_stop_before_target() -> None:
    entry = _entry("LONG")
    candles = [_candle(0, high=130.0, low=89.0)]

    trade = simulate_variant(entry, candles, ExitVariant("FIXED", "fixed_r", target_r=2.0, max_hold_bars=1))

    assert trade.exit_reason == "stop_loss"
    assert trade.ambiguous_bar_count == 1
    assert trade.pnl_r < 0


def test_baseline_control_keeps_frozen_entry_population_and_pnl() -> None:
    entries = [_entry("LONG"), _entry("SHORT")]
    trades = [simulate_variant(entry, [], ExitVariant("BASELINE_CONTROL", "baseline")) for entry in entries]
    metrics = compute_metrics(trades, trades)

    assert metrics["trade_count"] == 2
    assert metrics["entry_count_match"] == 1.0
    assert metrics["delta_er"] == 0.0


def test_exit_surface_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/trial_00095_exit_surface_diagnostic.json"))

    assert spec.hypothesis_id == "trial_00095_exit_surface_diagnostic_v1"
    assert spec.status == "ACTIVE"
    assert "Changing entry logic." in spec.out_of_scope

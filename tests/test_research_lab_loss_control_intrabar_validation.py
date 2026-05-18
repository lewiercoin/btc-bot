from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_lab.analysis_trial_00095_loss_control_intrabar_validation import (
    Candle,
    FrozenTrade,
    LossControlVariant,
    builder_verdict,
    compute_metrics,
    loss_threshold_price,
    simulate_variant,
)
from research_lab.hypotheses.spec import load_hypothesis_spec


def _entry(direction: str = "LONG", baseline_pnl_r: float = 2.0) -> FrozenTrade:
    opened = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return FrozenTrade(
        trade_id=f"t-{direction}",
        signal_id=f"s-{direction}",
        opened_at=opened,
        closed_at=opened + timedelta(minutes=30),
        direction=direction,
        regime="normal",
        entry_price=100.0,
        stop_loss=90.0 if direction == "LONG" else 110.0,
        tp1=120.0 if direction == "LONG" else 80.0,
        tp2=130.0 if direction == "LONG" else 70.0,
        baseline_pnl_r=baseline_pnl_r,
        baseline_exit_reason="TP" if baseline_pnl_r > 0 else "SL",
    )


def _candle(index: int, high: float, low: float) -> Candle:
    return Candle(
        open_time=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * index),
        open=100.0,
        high=high,
        low=low,
        close=100.0,
    )


def test_loss_control_hits_long_threshold_before_baseline_close() -> None:
    entry = _entry("LONG", baseline_pnl_r=-1.5)
    candles = {_candle(1, high=101.0, low=90.9).open_time: _candle(1, high=101.0, low=90.9)}

    trade = simulate_variant(entry, candles, LossControlVariant("HARD_STOP_0_90R", 0.90))

    assert trade.threshold_touched is True
    assert trade.exit_reason == "loss_control_0.90R"
    assert trade.pnl_r < -0.90
    assert trade.pnl_r > entry.baseline_pnl_r


def test_loss_control_short_symmetry_uses_high_threshold() -> None:
    entry = _entry("SHORT", baseline_pnl_r=-1.5)
    threshold = loss_threshold_price(entry, 0.75)
    candles = {_candle(1, high=threshold + 0.01, low=99.0).open_time: _candle(1, high=threshold + 0.01, low=99.0)}

    trade = simulate_variant(entry, candles, LossControlVariant("HARD_STOP_0_75R", 0.75))

    assert trade.threshold_touched is True
    assert trade.exit_reason == "loss_control_0.75R"
    assert trade.pnl_r < -0.75


def test_variant_preserves_baseline_when_threshold_not_touched() -> None:
    entry = _entry("LONG", baseline_pnl_r=3.0)
    candles = {_candle(1, high=130.0, low=95.0).open_time: _candle(1, high=130.0, low=95.0)}

    trade = simulate_variant(entry, candles, LossControlVariant("HARD_STOP_0_90R", 0.90))

    assert trade.threshold_touched is False
    assert trade.pnl_r == 3.0
    assert trade.exit_reason == "TP"


def test_metrics_track_stopped_winners_and_saved_losers() -> None:
    loser = _entry("LONG", baseline_pnl_r=-1.5)
    winner = _entry("LONG", baseline_pnl_r=2.0)
    baseline = [
        simulate_variant(loser, {}, LossControlVariant("BASELINE_REPLAY", None)),
        simulate_variant(winner, {}, LossControlVariant("BASELINE_REPLAY", None)),
    ]
    candles = {_candle(1, high=101.0, low=91.0).open_time: _candle(1, high=101.0, low=91.0)}
    trades = [
        simulate_variant(loser, candles, LossControlVariant("HARD_STOP_0_90R", 0.90)),
        simulate_variant(winner, candles, LossControlVariant("HARD_STOP_0_90R", 0.90)),
    ]

    metrics = compute_metrics(trades, baseline, prior_artifact_count=2)

    assert metrics["entry_count_match"] == 1.0
    assert metrics["saved_loser_count"] == 1
    assert metrics["stopped_winner_count"] == 1


def test_builder_verdict_blocks_replay_mismatch() -> None:
    entry = _entry("LONG", baseline_pnl_r=1.0)
    baseline_trade = simulate_variant(entry, {}, LossControlVariant("BASELINE_REPLAY", None))
    rows = [
        {
            "variant": LossControlVariant("BASELINE_REPLAY", None),
            "metrics": compute_metrics([baseline_trade], [baseline_trade], prior_artifact_count=2),
        },
        {
            "variant": LossControlVariant("HARD_STOP_0_90R", 0.90),
            "metrics": compute_metrics([baseline_trade], [baseline_trade], prior_artifact_count=2),
        },
    ]

    assert builder_verdict(rows) == "INCONCLUSIVE_REPLAY_MISMATCH"


def test_loss_control_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/trial_00095_loss_control_intrabar_validation.json"))

    assert spec.hypothesis_id == "trial_00095_loss_control_intrabar_validation_v1"
    assert spec.status == "ACTIVE"
    assert "Deployment recommendation." in spec.out_of_scope

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace

from backtest.backtest_runner import BacktestConfig
from core.models import Features, MarketSnapshot, RegimeState, SignalCandidate
from research_lab.research_backtest_runner import ResearchBacktestRunner, UptrendContinuationConfig
from settings import load_settings


def _features() -> Features:
    return Features(
        schema_version="v1.0",
        config_hash="hash",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        atr_15m=10.0,
        atr_4h=50.0,
        atr_4h_norm=0.01,
        ema50_4h=110.0,
        ema200_4h=100.0,
        sweep_detected=True,
        reclaim_detected=True,
        sweep_level=100.0,
        sweep_depth_pct=0.001,
        sweep_side="LOW",
        funding_8h=0.0,
        funding_sma3=0.0,
        funding_sma9=0.0,
        funding_pct_60d=50.0,
        oi_value=1.0,
        oi_zscore_60d=0.0,
        oi_delta_pct=0.0,
        cvd_15m=0.0,
        cvd_bullish_divergence=True,
        cvd_bearish_divergence=False,
        tfi_60s=0.25,
        force_order_rate_60s=0.0,
        force_order_spike=False,
        force_order_decreasing=False,
    )


def _candidate(*, setup_type: str, confluence_score: float) -> SignalCandidate:
    return SignalCandidate(
        signal_id=f"candidate-{setup_type}",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        direction="LONG",
        setup_type=setup_type,
        entry_reference=101.0,
        invalidation_level=95.0,
        tp_reference_1=111.0,
        tp_reference_2=121.0,
        confluence_score=confluence_score,
        regime=RegimeState.UPTREND,
        reasons=[setup_type],
        features_json={"atr_15m": 10.0},
    )


def _snapshot() -> MarketSnapshot:
    ts = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    return MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=ts,
        price=101.0,
        bid=100.5,
        ask=101.5,
        candles_15m=[
            {
                "open_time": ts,
                "open": 100.0,
                "high": 102.0,
                "low": 99.5,
                "close": 101.0,
                "volume": 10.0,
            }
        ],
        candles_1h=[],
        candles_4h=[],
    )


class _SingleSnapshotLoader:
    def __init__(self, snapshot: MarketSnapshot) -> None:
        self.snapshot = snapshot

    def iter_snapshots(self, **kwargs):
        yield self.snapshot


class _EmptySnapshotLoader:
    def iter_snapshots(self, **kwargs):
        yield from ()


def _runner(
    tmp_path,
    *,
    replay_loader=None,
    uptrend_continuation: UptrendContinuationConfig | None = None,
) -> ResearchBacktestRunner:
    conn = sqlite3.connect(":memory:")
    settings = load_settings(project_root=tmp_path)
    return ResearchBacktestRunner(
        conn,
        settings=settings,
        replay_loader=replay_loader,
        uptrend_continuation=uptrend_continuation,
    )


def test_select_signal_candidate_prefers_higher_confluence_overlay(tmp_path) -> None:
    runner = _runner(tmp_path)
    base_candidate = _candidate(setup_type="liquidity_sweep_reclaim_long", confluence_score=3.0)
    overlay_candidate = _candidate(setup_type="uptrend_continuation_long", confluence_score=4.2)

    selected = runner._select_signal_candidate(base_candidate, overlay_candidate)

    assert selected is overlay_candidate


def test_select_signal_candidate_prefers_base_on_equal_confluence(tmp_path) -> None:
    runner = _runner(tmp_path)
    base_candidate = _candidate(setup_type="liquidity_sweep_reclaim_long", confluence_score=3.5)
    overlay_candidate = _candidate(setup_type="uptrend_continuation_long", confluence_score=3.5)

    selected = runner._select_signal_candidate(base_candidate, overlay_candidate)

    assert selected is base_candidate


def test_select_signal_candidate_returns_overlay_when_base_missing(tmp_path) -> None:
    runner = _runner(tmp_path)
    overlay_candidate = _candidate(setup_type="uptrend_continuation_long", confluence_score=3.8)

    selected = runner._select_signal_candidate(None, overlay_candidate)

    assert selected is overlay_candidate


def test_select_signal_candidate_returns_base_when_overlay_missing(tmp_path) -> None:
    runner = _runner(tmp_path)
    base_candidate = _candidate(setup_type="liquidity_sweep_reclaim_long", confluence_score=3.4)

    selected = runner._select_signal_candidate(base_candidate, None)

    assert selected is base_candidate


def test_select_signal_candidate_returns_none_when_both_candidates_missing(tmp_path) -> None:
    runner = _runner(tmp_path)

    selected = runner._select_signal_candidate(None, None)

    assert selected is None


def test_run_evaluates_overlay_even_when_base_candidate_exists(tmp_path, monkeypatch) -> None:
    snapshot = _snapshot()
    runner = _runner(
        tmp_path,
        replay_loader=_SingleSnapshotLoader(snapshot),
        uptrend_continuation=UptrendContinuationConfig(allow_uptrend_continuation=True),
    )
    features = _features()
    base_candidate = _candidate(setup_type="liquidity_sweep_reclaim_long", confluence_score=3.0)
    overlay_candidate = _candidate(setup_type="uptrend_continuation_long", confluence_score=4.0)
    overlay_calls: list[datetime] = []
    evaluated_candidates: list[SignalCandidate] = []

    monkeypatch.setattr(
        runner,
        "_build_engines",
            lambda: (
                SimpleNamespace(compute=lambda **kwargs: features),
                SimpleNamespace(classify=lambda current_features: RegimeState.UPTREND),
                SimpleNamespace(classify=lambda current_features: None),
                SimpleNamespace(generate=lambda current_features, current_regime, **kwargs: base_candidate),
                SimpleNamespace(
                    evaluate=lambda candidate: evaluated_candidates.append(candidate)
                    or SimpleNamespace(approved=False)
            ),
            SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(
        runner,
        "_generate_uptrend_continuation_candidate",
        lambda **kwargs: overlay_calls.append(kwargs["features"].timestamp) or overlay_candidate,
    )
    monkeypatch.setattr(
        runner,
        "_summarize_trades",
        lambda trades, *, initial_equity: SimpleNamespace(total_trades=len(trades)),
    )

    result = runner.run(
        BacktestConfig(
            start_date="2026-01-01",
            end_date="2026-01-02",
            symbol="BTCUSDT",
        )
    )

    assert overlay_calls == [features.timestamp]
    assert evaluated_candidates[0] is overlay_candidate
    assert runner.signals_generated == 2
    assert result.trades == []


def test_run_logs_overlay_config_for_trial_validation(tmp_path, monkeypatch, caplog) -> None:
    runner = _runner(
        tmp_path,
        replay_loader=_EmptySnapshotLoader(),
        uptrend_continuation=UptrendContinuationConfig(
            allow_uptrend_continuation=True,
            uptrend_continuation_reclaim_strength_min=0.7,
            uptrend_continuation_participation_min=0.45,
            uptrend_continuation_confluence_multiplier=1.35,
        ),
    )
    monkeypatch.setattr(
        runner,
        "_build_engines",
            lambda: (
                SimpleNamespace(),
                SimpleNamespace(),
                SimpleNamespace(),
                SimpleNamespace(),
                SimpleNamespace(),
                SimpleNamespace(),
            ),
        )
    monkeypatch.setattr(
        runner,
        "_summarize_trades",
        lambda trades, *, initial_equity: SimpleNamespace(total_trades=len(trades)),
    )

    with caplog.at_level(logging.INFO):
        runner.run(
            BacktestConfig(
                start_date="2026-01-01",
                end_date="2026-01-02",
                symbol="BTCUSDT",
            )
        )

    assert "selection_policy=higher_confluence_base_tie_break" in caplog.text
    assert "uptrend_continuation_reclaim_strength_min=0.7000" in caplog.text
    assert "uptrend_continuation_participation_min=0.4500" in caplog.text
    assert "uptrend_continuation_confluence_multiplier=1.3500" in caplog.text

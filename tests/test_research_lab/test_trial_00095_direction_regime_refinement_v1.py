from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from research_lab.diagnostics.trial_00095_conditional_edge_attribution_v1 import AttributedTrade
from research_lab.diagnostics.trial_00095_direction_regime_refinement_v1 import (
    A1_COHORT,
    A2_COHORT,
    A3_COHORT,
    BASELINE_COHORT,
    FOLDS,
    build_fold_table,
    build_full_sample_table,
    build_payload,
    cohort_members,
    evaluate_gates,
    fold_label,
    run_diagnostic,
)


def _trade(
    trade_id: str,
    *,
    direction: str = "LONG",
    regime: str = "uptrend",
    pnl_r: float = 1.0,
    opened_at: datetime | None = None,
) -> AttributedTrade:
    ts = opened_at or datetime(2022, 1, 1, tzinfo=timezone.utc)
    return AttributedTrade(
        trade_id=trade_id,
        opened_at=ts,
        direction=direction,
        regime=regime,
        pnl_r=pnl_r,
        is_winner=pnl_r > 0,
        sweep_depth_pct=0.007,
        depth_band="test",
        depth_quartile="test",
        session="test",
        year=ts.year,
        fold=fold_label(type("T", (), {"opened_at": ts})()),
        exit_reason="TP_TRAIL" if pnl_r > 0 else "SL",
        risk_pct=0.002,
        mae_r=0.0,
        mfe_r=2.0,
        hold_bars=4,
        atr14_pct=0.01,
        realized_vol20=0.01,
        range_width20_pct=0.01,
        volume_z20=1.0,
        tfi_15m_prev=0.2,
        tfi_alignment="aligned",
        funding_rate=0.0001,
        oi_change_24h_pct=0.01,
        loss_archetype="winner" if pnl_r > 0 else "direct_stop_loss",
    )


def _write_trades(path: Path, trades: list[AttributedTrade]) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "direction": trade.direction,
                    "exit_reason": trade.exit_reason,
                    "mae": 1.0,
                    "mfe": 2.0,
                    "opened_at": trade.opened_at.isoformat(),
                    "pnl_r": trade.pnl_r,
                    "regime": trade.regime,
                    "session_hour": trade.opened_at.hour,
                    "sweep_depth_pct": trade.sweep_depth_pct,
                    "trade_id": trade.trade_id,
                }
                for trade in trades
            ],
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _gate_payload(a3_fold_pnls: tuple[list[float], list[float], list[float]]) -> tuple[dict, dict]:
    starts = (
        datetime(2022, 1, 1, tzinfo=timezone.utc),
        datetime(2023, 7, 1, tzinfo=timezone.utc),
        datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    trades: list[AttributedTrade] = []
    idx = 0
    for fold_idx, pnls in enumerate(a3_fold_pnls):
        for pnl in pnls:
            trades.append(_trade(f"a3-{idx}", pnl_r=pnl, opened_at=starts[fold_idx]))
            idx += 1
        trades.append(_trade(f"short-{fold_idx}", direction="SHORT", regime="downtrend", pnl_r=-1.0, opened_at=starts[fold_idx]))
    members = cohort_members(trades)
    return build_full_sample_table(members), build_fold_table(members)


def test_cohort_filters_are_frozen() -> None:
    trades = [
        _trade("long-up", direction="LONG", regime="uptrend"),
        _trade("long-down", direction="LONG", regime="downtrend"),
        _trade("short-up", direction="SHORT", regime="uptrend"),
        _trade("short-down", direction="SHORT", regime="downtrend"),
    ]

    members = cohort_members(trades)

    assert {trade.trade_id for trade in members[BASELINE_COHORT]} == {"long-up", "long-down", "short-up", "short-down"}
    assert {trade.trade_id for trade in members[A1_COHORT]} == {"long-up", "long-down"}
    assert {trade.trade_id for trade in members[A2_COHORT]} == {"long-up", "short-up"}
    assert {trade.trade_id for trade in members[A3_COHORT]} == {"long-up"}


def test_short_and_non_uptrend_rows_are_not_mutated() -> None:
    short = _trade("short", direction="SHORT", regime="uptrend", pnl_r=-2.0)
    non_uptrend = _trade("normal", direction="LONG", regime="normal", pnl_r=-1.0)
    original = (short.direction, short.regime, short.pnl_r, non_uptrend.direction, non_uptrend.regime, non_uptrend.pnl_r)

    members = cohort_members([short, non_uptrend])

    assert members[A3_COHORT] == []
    assert (short.direction, short.regime, short.pnl_r, non_uptrend.direction, non_uptrend.regime, non_uptrend.pnl_r) == original


def test_fold_assignment_reuses_existing_helper() -> None:
    assert fold_label(_trade("f1", opened_at=datetime(2023, 6, 30, 23, 45, tzinfo=timezone.utc))) == "fold_1_2022_2023H1"
    assert fold_label(_trade("f2", opened_at=datetime(2023, 7, 1, tzinfo=timezone.utc))) == "fold_2_2023H2_2024"
    assert fold_label(_trade("f3", opened_at=datetime(2025, 1, 1, tzinfo=timezone.utc))) == "fold_3_2025_2026Q1"


def test_metric_summary_matches_existing_attribution_math() -> None:
    trades = [_trade("a", pnl_r=4.0), _trade("b", pnl_r=-1.0), _trade("c", pnl_r=2.0)]
    metrics = build_full_sample_table(cohort_members(trades))[BASELINE_COHORT]

    assert metrics["count"] == 3
    assert metrics["expectancy_r"] == pytest.approx(5.0 / 3.0)
    assert metrics["profit_factor"] == pytest.approx(6.0)
    assert metrics["win_rate"] == pytest.approx(2.0 / 3.0)
    assert metrics["median_r"] == pytest.approx(2.0)
    assert metrics["total_r"] == pytest.approx(5.0)


def test_delta_vs_baseline_is_computed_per_fold_and_full_sample() -> None:
    trades = [
        _trade("a", direction="LONG", regime="uptrend", pnl_r=4.0),
        _trade("b", direction="SHORT", regime="downtrend", pnl_r=-1.0),
    ]
    full = build_full_sample_table(cohort_members(trades))
    delta = full[A3_COHORT]["delta_vs_baseline"]

    assert delta["count_removed"] == 1
    assert delta["count_retained"] == 1
    assert delta["retained_share"] == pytest.approx(0.5)
    assert delta["er_delta"] == pytest.approx(4.0 - 1.5)


@pytest.mark.parametrize(
    ("fold_pnls", "failed_rule"),
    [
        (([2.0], [2.0], [2.0]), "G-1"),
        (([3.0, -1.0], [3.0, -1.0], [3.0, -1.0]), "G-2"),
        (([4.0], [4.0], [-0.5]), "G-3"),
        (([6.0], [6.0], [0.5]), "G-4"),
    ],
)
def test_gate_evaluation_invalidates_on_any_required_a3_failure(fold_pnls: tuple[list[float], list[float], list[float]], failed_rule: str) -> None:
    full, folds = _gate_payload(fold_pnls)

    gates = evaluate_gates(full, folds)

    assert gates["final_verdict"] == "HYPOTHESIS_INVALIDATED"
    assert any(rule["rule"] == failed_rule and rule["status"] == "FAIL" for rule in gates["rules"])


def test_inconclusive_data_gap_when_required_fold_missing() -> None:
    full, folds = _gate_payload(([4.0], [4.0], []))

    gates = evaluate_gates(full, folds)

    assert gates["final_verdict"] == "INCONCLUSIVE_DATA_GAP"
    assert gates["missing_a3_folds"] == ["fold_3_2025_2026Q1"]


def test_deterministic_json_sha256(tmp_path: Path) -> None:
    trades = [
        _trade("a", opened_at=datetime(2022, 1, 1, tzinfo=timezone.utc), pnl_r=4.0),
        _trade("b", opened_at=datetime(2023, 7, 1, tzinfo=timezone.utc), pnl_r=4.0),
        _trade("c", opened_at=datetime(2025, 1, 1, tzinfo=timezone.utc), pnl_r=4.0),
        _trade("d", direction="SHORT", regime="downtrend", opened_at=datetime(2025, 1, 2, tzinfo=timezone.utc), pnl_r=-1.0),
    ]
    trades_path = tmp_path / "trades.json"
    _write_trades(trades_path, trades)

    first_json = tmp_path / "first.json"
    second_json = tmp_path / "second.json"
    run_diagnostic(trades_path=trades_path, output_json=first_json, output_sha=tmp_path / "first.sha256", report_path=tmp_path / "first.md")
    run_diagnostic(trades_path=trades_path, output_json=second_json, output_sha=tmp_path / "second.sha256", report_path=tmp_path / "second.md")

    assert hashlib.sha256(first_json.read_bytes()).hexdigest() == hashlib.sha256(second_json.read_bytes()).hexdigest()
    assert json.loads(first_json.read_text(encoding="utf-8")) == json.loads(second_json.read_text(encoding="utf-8"))

from __future__ import annotations

from pathlib import Path

from research_lab.sol_asset_specific_optimization import (
    SolOptGates,
    baseline_variant,
    build_predeclared_grid,
    builder_verdict,
    evaluate_oos_gates,
    train_passes,
    train_score,
)
from research_lab.hypotheses.spec import load_hypothesis_spec


def _metrics(*, trades: int, er: float, pf: float, dd: float) -> dict[str, float | int]:
    return {
        "trades_count": trades,
        "expectancy_r": er,
        "profit_factor": pf,
        "max_drawdown_pct": dd,
    }


def test_predeclared_grid_is_fixed_and_contains_baseline_point() -> None:
    grid = build_predeclared_grid()
    ids = {variant.variant_id for variant in grid}

    assert len(grid) == 3
    assert len(ids) == 3
    assert "SOL_OPT_D0.00649" in ids
    assert all(set(variant.overrides) == {"min_sweep_depth_pct"} for variant in grid)


def test_baseline_variant_uses_trial_00095_transfer_knobs() -> None:
    variant = baseline_variant(
        {
            "min_sweep_depth_pct": 0.00649,
            "confluence_min": 3.9,
            "direction_tfi_threshold": 0.1,
        }
    )

    assert variant.variant_id == "SOL_BASELINE_FROZEN_TRIAL_00095"
    assert variant.overrides == {
        "min_sweep_depth_pct": 0.00649,
        "confluence_min": 3.9,
        "direction_tfi_threshold": 0.1,
    }


def test_train_passes_requires_all_train_gates() -> None:
    gates = SolOptGates()

    assert train_passes(_metrics(trades=250, er=1.5, pf=2.0, dd=0.15), gates) is True
    assert train_passes(_metrics(trades=249, er=3.0, pf=4.0, dd=0.01), gates) is False
    assert train_passes(_metrics(trades=250, er=1.49, pf=4.0, dd=0.01), gates) is False
    assert train_passes(_metrics(trades=250, er=3.0, pf=1.99, dd=0.01), gates) is False
    assert train_passes(_metrics(trades=250, er=3.0, pf=4.0, dd=0.151), gates) is False


def test_train_score_rewards_er_and_penalizes_drawdown() -> None:
    strong = train_score(_metrics(trades=300, er=2.0, pf=3.0, dd=0.05))
    weaker = train_score(_metrics(trades=300, er=2.0, pf=3.0, dd=0.10))

    assert strong > weaker


def test_oos_gates_require_improvement_over_baseline_and_cost_robustness() -> None:
    gates = SolOptGates()
    result = evaluate_oos_gates(
        selected_oos=_metrics(trades=100, er=1.69, pf=2.4, dd=0.08),
        baseline_oos=_metrics(trades=90, er=1.6, pf=2.2, dd=0.09),
        selected_cost_2x_oos=_metrics(trades=100, er=1.1, pf=2.0, dd=0.08),
        wf_folds=[
            _metrics(trades=25, er=1.2, pf=2.0, dd=0.05),
            _metrics(trades=25, er=1.1, pf=2.0, dd=0.05),
            _metrics(trades=25, er=1.3, pf=2.0, dd=0.05),
            _metrics(trades=25, er=1.4, pf=2.0, dd=0.05),
        ],
        gates=gates,
    )

    assert all(item["pass"] for item in result.values())


def test_builder_verdict_blocks_when_any_oos_gate_fails() -> None:
    gates = {
        "oos_min_trades": {"pass": True},
        "oos_er_improvement_vs_baseline": {"pass": False},
    }

    assert builder_verdict(gates, selected_variant_id="SOL_OPT") == "SOL_OPTIMIZATION_NO_PROMOTION"
    assert builder_verdict({}, selected_variant_id=None) == "SOL_OPTIMIZATION_FAILED_NO_TRAIN_CANDIDATE"


def test_sol_asset_specific_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/sol_asset_specific_optimization.json"))

    assert spec.hypothesis_id == "SOL_ASSET_SPECIFIC_OPTIMIZATION_V1"
    assert spec.status == "ACTIVE"
    assert "Runtime deployment." in spec.out_of_scope

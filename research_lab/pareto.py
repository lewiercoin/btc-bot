from __future__ import annotations

from research_lab.types import TrialEvaluation


def _dominates(left: TrialEvaluation, right: TrialEvaluation) -> bool:
    left_expectancy = left.metrics.expectancy_r
    right_expectancy = right.metrics.expectancy_r
    left_pf = left.metrics.profit_factor
    right_pf = right.metrics.profit_factor
    left_dd = left.metrics.max_drawdown_pct
    right_dd = right.metrics.max_drawdown_pct

    no_worse = (
        left_expectancy >= right_expectancy
        and left_pf >= right_pf
        and left_dd <= right_dd
    )
    strictly_better = (
        left_expectancy > right_expectancy
        or left_pf > right_pf
        or left_dd < right_dd
    )
    return no_worse and strictly_better


def compute_pareto_frontier(trials: list[TrialEvaluation]) -> list[TrialEvaluation]:
    """3-objective Pareto: maximize expectancy_r, maximize profit_factor, minimize max_drawdown_pct.
    Only includes trials where rejected_reason is None."""

    accepted = [trial for trial in trials if trial.rejected_reason is None]
    frontier: list[TrialEvaluation] = []
    for candidate in accepted:
        dominated = False
        for other in accepted:
            if other is candidate:
                continue
            if _dominates(other, candidate):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return frontier


def rank_pareto_candidates(frontier: list[TrialEvaluation]) -> list[TrialEvaluation]:
    """Secondary ranking within frontier. Does NOT collapse to scalar — preserves Pareto structure."""

    return sorted(
        frontier,
        key=lambda trial: (
            -trial.metrics.expectancy_r,
            -trial.metrics.profit_factor,
            trial.metrics.max_drawdown_pct,
            -trial.metrics.trades_count,
            trial.trial_id,
        ),
    )


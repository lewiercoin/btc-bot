from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from settings import AppSettings

from research_lab.settings_adapter import diff_settings
from research_lab.types import RecommendationDraft, TrialEvaluation, WalkForwardReport


def build_recommendation(
    *,
    base_settings: AppSettings,
    candidate_settings: AppSettings,
    evaluation: TrialEvaluation,
    walkforward_report: WalkForwardReport,
) -> RecommendationDraft:
    params_diff = diff_settings(base_settings, candidate_settings)

    risks: list[str] = []
    if evaluation.rejected_reason is not None:
        risks.append(evaluation.rejected_reason)
    if not walkforward_report.passed:
        risks.append("walkforward_not_passed")
    if walkforward_report.fragile:
        risks.append("walkforward_fragile")
    risks.extend(walkforward_report.reasons)

    summary = (
        f"Candidate {evaluation.trial_id}: expectancy_r={evaluation.metrics.expectancy_r:.4f}, "
        f"profit_factor={evaluation.metrics.profit_factor:.4f}, "
        f"max_drawdown_pct={evaluation.metrics.max_drawdown_pct:.4f}, "
        f"walkforward_passed={walkforward_report.passed}"
    )
    return RecommendationDraft(
        candidate_id=evaluation.trial_id,
        summary=summary,
        params_diff=params_diff,
        expected_improvement={
            "expectancy_r": evaluation.metrics.expectancy_r,
            "profit_factor": evaluation.metrics.profit_factor,
            "max_drawdown_pct": -evaluation.metrics.max_drawdown_pct,
            "pnl_abs": evaluation.metrics.pnl_abs,
            "win_rate": evaluation.metrics.win_rate,
        },
        risks=tuple(dict.fromkeys(risks)),
        approval_required=True,
    )


def write_approval_bundle(
    *,
    recommendation: RecommendationDraft,
    output_dir: Path,
) -> Path:
    """Writes: recommendation.json, params_diff.json, candidate_settings.json.
    Does NOT write to settings.py. Human applies changes manually."""

    output_dir.mkdir(parents=True, exist_ok=True)

    recommendation_payload = dataclasses.asdict(recommendation)
    (output_dir / "recommendation.json").write_text(
        json.dumps(recommendation_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "params_diff.json").write_text(
        json.dumps(recommendation.params_diff, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    # Candidate settings snapshot is derived from params_diff `to` values.
    candidate_settings_payload = {
        "candidate_id": recommendation.candidate_id,
        "changed_params_to": {
            name: payload.get("to")
            for name, payload in recommendation.params_diff.items()
        },
    }
    (output_dir / "candidate_settings.json").write_text(
        json.dumps(candidate_settings_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_dir


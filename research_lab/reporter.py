from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from research_lab.experiment_store import load_trials
from research_lab.pareto import compute_pareto_frontier, rank_pareto_candidates


def _connect(store_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(store_path)
    conn.row_factory = sqlite3.Row
    return conn


def build_experiment_report(store_path: Path) -> dict[str, Any]:
    trials = load_trials(store_path)
    accepted = [trial for trial in trials if trial.rejected_reason is None]
    rejected = [trial for trial in trials if trial.rejected_reason is not None]

    pareto_frontier = compute_pareto_frontier(trials)
    ranked_pareto = rank_pareto_candidates(pareto_frontier)

    walkforward_rows: list[dict[str, Any]] = []
    recommendation_rows: list[dict[str, Any]] = []
    if store_path.exists():
        with _connect(store_path) as conn:
            walkforward_query = (
                "SELECT candidate_id, report_json, created_at_utc "
                "FROM walkforward_reports ORDER BY created_at_utc ASC"
            )
            walkforward_rows = [
                {
                    "candidate_id": str(row["candidate_id"]),
                    "report_json": json.loads(str(row["report_json"])),
                    "created_at_utc": str(row["created_at_utc"]),
                }
                for row in conn.execute(walkforward_query).fetchall()
            ]
            recommendations_query = (
                "SELECT candidate_id, recommendation_json, created_at_utc "
                "FROM recommendations ORDER BY created_at_utc ASC"
            )
            recommendation_rows = [
                {
                    "candidate_id": str(row["candidate_id"]),
                    "recommendation_json": json.loads(str(row["recommendation_json"])),
                    "created_at_utc": str(row["created_at_utc"]),
                }
                for row in conn.execute(recommendations_query).fetchall()
            ]

    return {
        "trials_total": len(trials),
        "trials_accepted": len(accepted),
        "trials_rejected": len(rejected),
        "pareto_count": len(pareto_frontier),
        "pareto_ranked": [
            {
                "trial_id": trial.trial_id,
                "expectancy_r": trial.metrics.expectancy_r,
                "profit_factor": trial.metrics.profit_factor,
                "max_drawdown_pct": trial.metrics.max_drawdown_pct,
                "trades_count": trial.metrics.trades_count,
                "rejected_reason": trial.rejected_reason,
            }
            for trial in ranked_pareto
        ],
        "walkforward_reports": walkforward_rows,
        "recommendations": recommendation_rows,
    }


def write_experiment_report(*, report: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path

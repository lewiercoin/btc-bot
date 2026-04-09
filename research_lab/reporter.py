from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from research_lab.experiment_store import init_store, load_trials
from research_lab.pareto import compute_pareto_frontier, rank_pareto_candidates


def _connect(store_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(store_path)
    conn.row_factory = sqlite3.Row
    return conn


def _compute_funnel_summary(trials: list[Any]) -> dict[str, Any]:
    accepted = [t for t in trials if t.rejected_reason is None]
    if not accepted:
        return {"trials_with_funnel": 0}

    total = len(accepted)
    total_generated = sum(t.funnel.signals_generated for t in accepted)
    total_regime_blocked = sum(t.funnel.signals_regime_blocked for t in accepted)
    total_governance_rejected = sum(t.funnel.signals_governance_rejected for t in accepted)
    total_risk_rejected = sum(t.funnel.signals_risk_rejected for t in accepted)
    total_executed = sum(t.funnel.signals_executed for t in accepted)

    def _safe_rate(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 4) if denominator > 0 else 0.0

    return {
        "trials_with_funnel": total,
        "avg_signals_generated": round(total_generated / total, 2),
        "avg_signals_executed": round(total_executed / total, 2),
        "regime_blocked_rate": _safe_rate(total_regime_blocked, total_generated),
        "governance_rejected_rate": _safe_rate(total_governance_rejected, total_generated),
        "risk_rejected_rate": _safe_rate(total_risk_rejected, total_generated),
        "executed_rate": _safe_rate(total_executed, total_generated),
    }


def build_experiment_report(store_path: Path) -> dict[str, Any]:
    trials = load_trials(store_path)
    accepted = [trial for trial in trials if trial.rejected_reason is None]
    rejected = [trial for trial in trials if trial.rejected_reason is not None]

    pareto_frontier = compute_pareto_frontier(trials)
    ranked_pareto = rank_pareto_candidates(pareto_frontier)

    walkforward_rows: list[dict[str, Any]] = []
    recommendation_rows: list[dict[str, Any]] = []
    if store_path.exists():
        init_store(store_path)
        with _connect(store_path) as conn:
            walkforward_query = (
                "SELECT candidate_id, report_json, created_at_utc, protocol_hash "
                "FROM walkforward_reports ORDER BY created_at_utc ASC"
            )
            walkforward_rows = [
                {
                    "candidate_id": str(row["candidate_id"]),
                    "report_json": json.loads(str(row["report_json"])),
                    "created_at_utc": str(row["created_at_utc"]),
                    "protocol_hash": str(row["protocol_hash"]) if row["protocol_hash"] is not None else None,
                }
                for row in conn.execute(walkforward_query).fetchall()
            ]
            recommendations_query = (
                "SELECT candidate_id, recommendation_json, created_at_utc, protocol_hash "
                "FROM recommendations ORDER BY created_at_utc ASC"
            )
            recommendation_rows = [
                {
                    "candidate_id": str(row["candidate_id"]),
                    "recommendation_json": json.loads(str(row["recommendation_json"])),
                    "created_at_utc": str(row["created_at_utc"]),
                    "protocol_hash": str(row["protocol_hash"]) if row["protocol_hash"] is not None else None,
                }
                for row in conn.execute(recommendations_query).fetchall()
            ]

    return {
        "trials_total": len(trials),
        "trials_accepted": len(accepted),
        "trials_rejected": len(rejected),
        "pareto_count": len(pareto_frontier),
        "signal_funnel_summary": _compute_funnel_summary(trials),
        "pareto_ranked": [
            {
                "trial_id": trial.trial_id,
                "expectancy_r": trial.metrics.expectancy_r,
                "profit_factor": trial.metrics.profit_factor,
                "max_drawdown_pct": trial.metrics.max_drawdown_pct,
                "trades_count": trial.metrics.trades_count,
                "rejected_reason": trial.rejected_reason,
                "protocol_hash": trial.protocol_hash,
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

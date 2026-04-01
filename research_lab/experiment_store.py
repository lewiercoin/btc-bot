from __future__ import annotations

import dataclasses
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_lab.types import NestedWalkForwardReport, ObjectiveMetrics, RecommendationDraft, SignalFunnel, TrialEvaluation, WalkForwardReport


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(store_path: Path) -> sqlite3.Connection:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(store_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _ensure_protocol_hash_columns(conn: sqlite3.Connection) -> None:
    for table_name in ("trials", "walkforward_reports", "recommendations"):
        if "protocol_hash" not in _table_columns(conn, table_name):
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN protocol_hash TEXT NULL")


def init_store(store_path: Path) -> None:
    with _connect(store_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trials (
                trial_id TEXT PRIMARY KEY,
                params_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                funnel_json TEXT NOT NULL,
                rejected_reason TEXT NULL,
                created_at_utc TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS walkforward_reports (
                candidate_id TEXT PRIMARY KEY,
                report_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendations (
                candidate_id TEXT PRIMARY KEY,
                recommendation_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL
            )
            """
        )
        _ensure_protocol_hash_columns(conn)
        conn.commit()


def save_trial(evaluation: TrialEvaluation, store_path: Path) -> None:
    init_store(store_path)
    with _connect(store_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO trials (
                trial_id, params_json, metrics_json, funnel_json, rejected_reason, created_at_utc, protocol_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation.trial_id,
                json.dumps(evaluation.params, sort_keys=True),
                json.dumps(
                    {
                        "expectancy_r": evaluation.metrics.expectancy_r,
                        "profit_factor": evaluation.metrics.profit_factor,
                        "max_drawdown_pct": evaluation.metrics.max_drawdown_pct,
                        "trades_count": evaluation.metrics.trades_count,
                        "sharpe_ratio": evaluation.metrics.sharpe_ratio,
                        "pnl_abs": evaluation.metrics.pnl_abs,
                        "win_rate": evaluation.metrics.win_rate,
                    },
                    sort_keys=True,
                ),
                json.dumps(
                    {
                        "signals_generated": evaluation.funnel.signals_generated,
                        "signals_regime_blocked": evaluation.funnel.signals_regime_blocked,
                        "signals_governance_rejected": evaluation.funnel.signals_governance_rejected,
                        "signals_risk_rejected": evaluation.funnel.signals_risk_rejected,
                        "signals_executed": evaluation.funnel.signals_executed,
                    },
                    sort_keys=True,
                ),
                evaluation.rejected_reason,
                _utc_now_iso(),
                evaluation.protocol_hash,
            ),
        )
        conn.commit()


def save_walkforward(candidate_id: str, report: WalkForwardReport | NestedWalkForwardReport, store_path: Path) -> None:
    init_store(store_path)
    with _connect(store_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO walkforward_reports (candidate_id, report_json, created_at_utc, protocol_hash)
            VALUES (?, ?, ?, ?)
            """,
            (
                candidate_id,
                json.dumps(dataclasses.asdict(report), sort_keys=True),
                _utc_now_iso(),
                report.protocol_hash,
            ),
        )
        conn.commit()


def save_recommendation(rec: RecommendationDraft, store_path: Path) -> None:
    init_store(store_path)
    with _connect(store_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO recommendations (candidate_id, recommendation_json, created_at_utc, protocol_hash)
            VALUES (?, ?, ?, ?)
            """,
            (
                rec.candidate_id,
                json.dumps(
                    {
                        "candidate_id": rec.candidate_id,
                        "summary": rec.summary,
                        "params_diff": rec.params_diff,
                        "expected_improvement": rec.expected_improvement,
                        "risks": list(rec.risks),
                        "approval_required": rec.approval_required,
                        "protocol_hash": rec.protocol_hash,
                    },
                    sort_keys=True,
                ),
                _utc_now_iso(),
                rec.protocol_hash,
            ),
        )
        conn.commit()


def _parse_trial_row(row: sqlite3.Row) -> TrialEvaluation:
    params = json.loads(str(row["params_json"]))
    metrics_payload: dict[str, Any] = json.loads(str(row["metrics_json"]))
    funnel_payload: dict[str, Any] = json.loads(str(row["funnel_json"]))
    return TrialEvaluation(
        trial_id=str(row["trial_id"]),
        params=params,
        metrics=ObjectiveMetrics(
            expectancy_r=float(metrics_payload["expectancy_r"]),
            profit_factor=float(metrics_payload["profit_factor"]),
            max_drawdown_pct=float(metrics_payload["max_drawdown_pct"]),
            trades_count=int(metrics_payload["trades_count"]),
            sharpe_ratio=float(metrics_payload["sharpe_ratio"]),
            pnl_abs=float(metrics_payload["pnl_abs"]),
            win_rate=float(metrics_payload["win_rate"]),
        ),
        funnel=SignalFunnel(
            signals_generated=int(funnel_payload["signals_generated"]),
            signals_regime_blocked=int(funnel_payload["signals_regime_blocked"]),
            signals_governance_rejected=int(funnel_payload["signals_governance_rejected"]),
            signals_risk_rejected=int(funnel_payload["signals_risk_rejected"]),
            signals_executed=int(funnel_payload["signals_executed"]),
        ),
        rejected_reason=str(row["rejected_reason"]) if row["rejected_reason"] is not None else None,
        protocol_hash=str(row["protocol_hash"]) if row["protocol_hash"] is not None else None,
    )


def load_trials(store_path: Path) -> list[TrialEvaluation]:
    if not store_path.exists():
        return []
    init_store(store_path)
    with _connect(store_path) as conn:
        rows = conn.execute(
            """
            SELECT trial_id, params_json, metrics_json, funnel_json, rejected_reason, protocol_hash
            FROM trials
            ORDER BY created_at_utc ASC, trial_id ASC
            """
        ).fetchall()
    return [_parse_trial_row(row) for row in rows]

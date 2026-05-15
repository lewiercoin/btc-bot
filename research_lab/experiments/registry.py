from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUSES = {"CREATED", "RUNNING", "COMPLETED", "FAILED", "REJECTED", "AUDIT_READY"}
VERDICTS = {"PASS", "MARGINAL", "FAIL", "INCONCLUSIVE", "BLOCKED"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_registry(registry_path: Path) -> sqlite3.Connection:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(registry_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_experiment_registry(registry_path: Path) -> None:
    with connect_registry(registry_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                experiment_fingerprint TEXT NOT NULL,
                hypothesis_id TEXT NOT NULL,
                run_id TEXT,
                git_commit TEXT NOT NULL,
                data_manifest_hash TEXT NOT NULL,
                config_hash TEXT NOT NULL,
                runner_name TEXT NOT NULL,
                date_range_start TEXT NOT NULL,
                date_range_end TEXT NOT NULL,
                baseline_reference TEXT NOT NULL,
                status TEXT NOT NULL,
                verdict TEXT,
                metrics_json TEXT,
                gates_json TEXT,
                artifacts_json TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_experiments_hypothesis ON experiments(hypothesis_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_experiments_verdict ON experiments(verdict)")
        conn.commit()


def insert_experiment(registry_path: Path, row: dict[str, Any]) -> None:
    _validate_status(row["status"])
    if row.get("verdict") is not None:
        _validate_verdict(row["verdict"])
    init_experiment_registry(registry_path)
    with connect_registry(registry_path) as conn:
        conn.execute(
            """
            INSERT INTO experiments (
                experiment_id, experiment_fingerprint, hypothesis_id, run_id, git_commit,
                data_manifest_hash, config_hash, runner_name, date_range_start, date_range_end,
                baseline_reference, status, verdict, metrics_json, gates_json, artifacts_json,
                created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["experiment_id"],
                row["experiment_fingerprint"],
                row["hypothesis_id"],
                row.get("run_id"),
                row["git_commit"],
                row["data_manifest_hash"],
                row["config_hash"],
                row["runner_name"],
                row["date_range_start"],
                row["date_range_end"],
                row["baseline_reference"],
                row["status"],
                row.get("verdict"),
                _json_or_none(row.get("metrics")),
                _json_or_none(row.get("gates")),
                _json_or_none(row.get("artifacts")),
                row["created_at"],
                row.get("completed_at"),
            ),
        )
        conn.commit()


def update_experiment_result(
    registry_path: Path,
    *,
    experiment_id: str,
    status: str,
    verdict: str | None,
    metrics: dict[str, Any] | None,
    gates: dict[str, Any] | None,
    artifacts: dict[str, Any] | None,
) -> None:
    _validate_status(status)
    if verdict is not None:
        _validate_verdict(verdict)
    init_experiment_registry(registry_path)
    with connect_registry(registry_path) as conn:
        conn.execute(
            """
            UPDATE experiments
            SET status = ?, verdict = ?, metrics_json = ?, gates_json = ?,
                artifacts_json = ?, completed_at = ?
            WHERE experiment_id = ?
            """,
            (
                status,
                verdict,
                _json_or_none(metrics),
                _json_or_none(gates),
                _json_or_none(artifacts),
                utc_now_iso(),
                experiment_id,
            ),
        )
        if conn.total_changes == 0:
            raise KeyError(f"Unknown experiment_id: {experiment_id}")
        conn.commit()


def fetch_experiment(registry_path: Path, experiment_id: str) -> dict[str, Any] | None:
    init_experiment_registry(registry_path)
    with connect_registry(registry_path) as conn:
        row = conn.execute(
            "SELECT * FROM experiments WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
    return _row_to_dict(row) if row is not None else None


def query_experiments(
    registry_path: Path,
    *,
    hypothesis_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    init_experiment_registry(registry_path)
    clauses = []
    params: list[str] = []
    if hypothesis_id is not None:
        clauses.append("hypothesis_id = ?")
        params.append(hypothesis_id)
    if status is not None:
        _validate_status(status)
        clauses.append("status = ?")
        params.append(status)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect_registry(registry_path) as conn:
        rows = conn.execute(f"SELECT * FROM experiments{where} ORDER BY created_at, experiment_id", params).fetchall()
    return [_row_to_dict(row) for row in rows]


def _validate_status(status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"Invalid experiment status: {status}")


def _validate_verdict(verdict: str) -> None:
    if verdict not in VERDICTS:
        raise ValueError(f"Invalid experiment verdict: {verdict}")


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    for json_key, output_key in (
        ("metrics_json", "metrics"),
        ("gates_json", "gates"),
        ("artifacts_json", "artifacts"),
    ):
        value = payload.pop(json_key)
        payload[output_key] = json.loads(value) if value else None
    return payload

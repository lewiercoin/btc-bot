from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from research_lab.evaluators.gate_evaluator import GateResult
from research_lab.experiments.manifest import DataManifest, compute_combined_manifest_hash
from research_lab.experiments.registry import (
    fetch_experiment,
    insert_experiment,
    query_experiments,
    update_experiment_result,
    utc_now_iso,
)
from research_lab.reports.experiment_report import generate_report


def create_experiment(
    *,
    registry_path: Path,
    hypothesis_id: str,
    config: dict[str, Any],
    data_manifests: list[DataManifest],
    baseline_reference: str,
    runner_name: str,
    date_range_start: str,
    date_range_end: str,
    git_commit: str,
    run_id: str | None = None,
) -> str:
    config_hash = _hash_json(config)
    data_manifest_hash = compute_combined_manifest_hash(data_manifests)
    fingerprint = _hash_json(
        {
            "hypothesis_id": hypothesis_id,
            "config_hash": config_hash,
            "data_manifest_hash": data_manifest_hash,
            "runner_name": runner_name,
            "date_range_start": date_range_start,
            "date_range_end": date_range_end,
            "baseline_reference": baseline_reference,
        }
    )
    experiment_id = f"exp-{fingerprint[:16]}"
    insert_experiment(
        registry_path,
        {
            "experiment_id": experiment_id,
            "experiment_fingerprint": fingerprint,
            "hypothesis_id": hypothesis_id,
            "run_id": run_id,
            "git_commit": git_commit,
            "data_manifest_hash": data_manifest_hash,
            "config_hash": config_hash,
            "runner_name": runner_name,
            "date_range_start": date_range_start,
            "date_range_end": date_range_end,
            "baseline_reference": baseline_reference,
            "status": "CREATED",
            "created_at": utc_now_iso(),
        },
    )
    return experiment_id


def record_result(
    *,
    registry_path: Path,
    experiment_id: str,
    verdict: str,
    metrics: dict[str, Any],
    gates: list[GateResult],
    artifacts: dict[str, Any],
    status: str = "COMPLETED",
) -> None:
    update_experiment_result(
        registry_path,
        experiment_id=experiment_id,
        status=status,
        verdict=verdict,
        metrics=metrics,
        gates={"results": [gate.to_dict() for gate in gates]},
        artifacts=artifacts,
    )


def get_experiment(registry_path: Path, experiment_id: str) -> dict[str, Any]:
    experiment = fetch_experiment(registry_path, experiment_id)
    if experiment is None:
        raise KeyError(f"Unknown experiment_id: {experiment_id}")
    return experiment


def list_experiments(
    registry_path: Path,
    *,
    hypothesis_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    return query_experiments(registry_path, hypothesis_id=hypothesis_id, status=status)


def generate_experiment_report(
    *,
    registry_path: Path,
    experiment_id: str,
    hypothesis: dict[str, Any],
    baseline_metrics: dict[str, Any],
    data_manifests: list[DataManifest],
) -> str:
    experiment = get_experiment(registry_path, experiment_id)
    gates_payload = experiment.get("gates") or {}
    return generate_report(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        metrics=experiment.get("metrics") or {},
        baseline_metrics=baseline_metrics,
        gate_results=gates_payload.get("results", []),
        verdict=experiment.get("verdict") or "INCONCLUSIVE",
        data_manifests=data_manifests,
        artifacts=experiment.get("artifacts") or {},
    )


def _hash_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

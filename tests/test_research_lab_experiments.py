from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_lab.evaluators.gate_evaluator import Gate, evaluate_gates
from research_lab.experiments.api import (
    create_experiment,
    generate_experiment_report,
    get_experiment,
    list_experiments,
    record_result,
)
from research_lab.experiments.manifest import DataManifest, compute_combined_manifest_hash, create_manifest
from research_lab.hypotheses.spec import HypothesisSpec, ResearchProgram, validate_hypothesis_spec


def _valid_hypothesis_payload() -> dict:
    return {
        "hypothesis_id": "test_hypothesis_v1",
        "name": "Test Hypothesis",
        "class": "timing_overlay",
        "edge_rationale": "A deterministic timing overlay may reduce MAE.",
        "counterparty_or_market_mechanism": "Late momentum entrants.",
        "required_data": ["btc_15m", "btc_5m"],
        "timeframe": ["15m", "5m"],
        "baseline_reference": "trial-00095",
        "variables": [{"name": "threshold", "values": [0.5, 0.6]}],
        "frozen_assumptions": ["No production changes."],
        "expected_observation": "MAE improves without ER degradation.",
        "acceptance_criteria": {"min_trades": 20, "min_er": 1.0},
        "kill_criteria": {"max_timeout_rate": 0.9},
        "failure_modes": ["Signal arrives too late."],
        "out_of_scope": ["Runtime deployment."],
        "author": "Codex",
        "created_at": "2026-05-15T00:00:00+00:00",
        "status": "DRAFT",
    }


def _manifest(dataset_id: str = "btc_15m") -> DataManifest:
    return DataManifest(
        dataset_id=dataset_id,
        path=f"research_lab/snapshots/{dataset_id}.db",
        timeframe="15m",
        symbol="BTCUSDT",
        date_start="2024-01-01",
        date_end="2026-03-28",
        row_count=100,
        content_hash="abc123",
        quality_status="PASS",
        source="unit_test",
    )


def test_hypothesis_spec_validation_pass() -> None:
    payload = _valid_hypothesis_payload()

    validate_hypothesis_spec(payload)
    spec = HypothesisSpec.from_dict(payload)

    assert spec.hypothesis_id == "test_hypothesis_v1"
    assert spec.hypothesis_class == "timing_overlay"
    assert spec.to_dict()["class"] == "timing_overlay"


def test_hypothesis_spec_validation_missing_required_field() -> None:
    payload = _valid_hypothesis_payload()
    payload.pop("edge_rationale")

    with pytest.raises(ValueError, match="Missing required fields"):
        validate_hypothesis_spec(payload)


def test_hypothesis_spec_no_arbitrary_code() -> None:
    payload = _valid_hypothesis_payload()
    payload["variables"].append({"name": "unsafe", "python_code": "print('unsafe')"})

    with pytest.raises(ValueError, match="Executable field"):
        validate_hypothesis_spec(payload)


def test_research_program_validation_pass() -> None:
    program = ResearchProgram.from_dict(
        {
            "research_program_id": "program_v1",
            "title": "Program",
            "objective": "Standardize tests.",
            "constraints": ["No runtime changes."],
            "allowed_data": ["btc_15m"],
            "allowed_hypothesis_classes": ["timing_overlay", "entry_filter"],
            "disallowed_actions": ["No production changes."],
            "baseline_reference": "trial-00095",
            "validation_protocol": "OOS_WF",
            "owner": "user",
            "builder": "Codex",
            "auditor": "Claude Code",
            "status": "ACTIVE",
        }
    )

    assert program.to_dict()["status"] == "ACTIVE"


def test_data_manifest_hash_is_deterministic(tmp_path: Path) -> None:
    data_path = tmp_path / "data.txt"
    data_path.write_text("fixture", encoding="utf-8")

    manifest_a = create_manifest(
        dataset_id="fixture",
        path=data_path,
        timeframe="15m",
        symbol="BTCUSDT",
        date_start="2024-01-01",
        date_end="2024-01-02",
        row_count=1,
        quality_status="PASS",
        source="unit_test",
    )
    manifest_b = create_manifest(
        dataset_id="fixture",
        path=data_path,
        timeframe="15m",
        symbol="BTCUSDT",
        date_start="2024-01-01",
        date_end="2024-01-02",
        row_count=1,
        quality_status="PASS",
        source="unit_test",
    )

    assert manifest_a.compute_hash() == manifest_b.compute_hash()


def test_combined_manifest_hash_stable_for_multi_dataset() -> None:
    manifest_a = _manifest("btc_15m")
    manifest_b = _manifest("btc_5m")

    assert compute_combined_manifest_hash([manifest_a, manifest_b]) == compute_combined_manifest_hash(
        [manifest_b, manifest_a]
    )


def test_gate_evaluator_pass() -> None:
    result = evaluate_gates(
        {"trade_count": 47, "expectancy_r": 2.1, "profit_factor": 3.9},
        [
            Gate("min_trades", ">=", 20, "trade_count"),
            Gate("min_er", ">=", 1.0, "expectancy_r"),
            Gate("min_pf", ">=", 1.5, "profit_factor"),
        ],
    )

    assert result.verdict == "PASS"


def test_gate_evaluator_fail() -> None:
    result = evaluate_gates(
        {"trade_count": 47, "expectancy_r": 0.2},
        [
            Gate("min_trades", ">=", 20, "trade_count"),
            Gate("min_er", ">=", 1.0, "expectancy_r"),
        ],
    )

    assert result.verdict == "FAIL"


def test_gate_evaluator_marginal() -> None:
    result = evaluate_gates(
        {"trade_count": 47, "expectancy_r": 2.1, "profit_factor": 1.2},
        [
            Gate("min_trades", ">=", 20, "trade_count"),
            Gate("min_er", ">=", 1.0, "expectancy_r"),
            Gate("recommended_pf", ">=", 1.5, "profit_factor", "RECOMMENDED"),
        ],
    )

    assert result.verdict == "MARGINAL"


def test_gate_evaluator_inconclusive() -> None:
    result = evaluate_gates(
        {"trade_count": 7, "expectancy_r": 2.1},
        [
            Gate("min_trades", ">=", 20, "trade_count"),
            Gate("min_er", ">=", 1.0, "expectancy_r"),
        ],
    )

    assert result.verdict == "INCONCLUSIVE"


def test_gate_evaluator_blocked_when_metric_missing() -> None:
    result = evaluate_gates(
        {"trade_count": 47},
        [
            Gate("min_trades", ">=", 20, "trade_count"),
            Gate("min_er", ">=", 1.0, "expectancy_r"),
        ],
    )

    assert result.verdict == "BLOCKED"


def test_experiment_registry_create_query_and_deterministic_id(tmp_path: Path) -> None:
    registry_path = tmp_path / "experiments.db"
    manifest = _manifest()
    kwargs = {
        "registry_path": registry_path,
        "hypothesis_id": "test_hypothesis_v1",
        "config": {"threshold": 0.6},
        "data_manifests": [manifest],
        "baseline_reference": "trial-00095",
        "runner_name": "unit_runner",
        "date_range_start": "2024-01-01",
        "date_range_end": "2024-12-31",
        "git_commit": "abc123",
    }

    experiment_id = create_experiment(**kwargs)
    fetched = get_experiment(registry_path, experiment_id)

    assert fetched["experiment_id"] == experiment_id
    assert fetched["status"] == "CREATED"
    assert list_experiments(registry_path, hypothesis_id="test_hypothesis_v1")[0]["experiment_id"] == experiment_id

    with pytest.raises(Exception):
        create_experiment(**kwargs)


def test_experiment_registry_has_no_delete_api() -> None:
    import research_lab.experiments.api as api

    assert not hasattr(api, "delete_experiment")


def test_report_generation_has_required_sections(tmp_path: Path) -> None:
    registry_path = tmp_path / "experiments.db"
    manifest = _manifest()
    experiment_id = create_experiment(
        registry_path=registry_path,
        hypothesis_id="test_hypothesis_v1",
        config={"threshold": 0.6},
        data_manifests=[manifest],
        baseline_reference="trial-00095",
        runner_name="unit_runner",
        date_range_start="2024-01-01",
        date_range_end="2024-12-31",
        git_commit="abc123",
    )
    evaluation = evaluate_gates(
        {"trade_count": 47, "expectancy_r": 2.1},
        [Gate("min_trades", ">=", 20, "trade_count"), Gate("min_er", ">=", 1.0, "expectancy_r")],
        experiment_id=experiment_id,
    )
    record_result(
        registry_path=registry_path,
        experiment_id=experiment_id,
        verdict=evaluation.verdict,
        metrics={"trade_count": 47, "expectancy_r": 2.1},
        gates=list(evaluation.gate_results),
        artifacts={"report": "docs/analysis/test.md"},
    )

    report = generate_experiment_report(
        registry_path=registry_path,
        experiment_id=experiment_id,
        hypothesis=_valid_hypothesis_payload(),
        baseline_metrics={"trade_count": 40, "expectancy_r": 1.5},
        data_manifests=[manifest],
    )

    for section in (
        "## Executive Summary",
        "## Hypothesis",
        "## Data Sources / Manifests",
        "## Baseline Comparison",
        "## Metrics",
        "## Gates",
        "## Verdict",
        "## Limitations",
        "## Artifacts",
        "## Next-Step Recommendation",
    ):
        assert section in report


def test_example_hypothesis_file_valid() -> None:
    path = Path("research_lab/hypotheses/examples/15m_signal_5m_energy_overlay.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    validate_hypothesis_spec(payload)
    assert payload["status"] == "CLOSED"

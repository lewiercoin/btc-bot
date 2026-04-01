from __future__ import annotations

import dataclasses
import json
import random
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from backtest.backtest_runner import BacktestConfig
from settings import AppSettings

from research_lab.approval import build_recommendation, write_approval_bundle
from research_lab.baseline_gate import BaselineGateError, check_baseline
from research_lab.constants import MIN_TRADES_DEFAULT, PROMOTION_BLOCKING_RISKS
from research_lab.constraints import validate_param_vector
from research_lab.db_snapshot import create_trial_snapshot, open_snapshot_connection, verify_required_tables
from research_lab.experiment_store import (
    init_store,
    load_recommendations,
    load_trials,
    save_recommendation,
    save_trial,
    save_walkforward,
)
from research_lab.objective import evaluate_candidate
from research_lab.param_registry import build_param_registry, get_active_params
from research_lab.protocol import hash_protocol, load_protocol
from research_lab.settings_adapter import build_candidate_settings
from research_lab.types import (
    AutoresearchCandidateResult,
    AutoresearchLoopReport,
    ParamSpec,
    RecommendationDraft,
    TrialEvaluation,
)
from research_lab.walkforward import build_windows, run_walkforward


_STORE_ERROR_TYPES = (OSError, sqlite3.Error)
_MAX_CANDIDATES_HARD_LIMIT = 50


def _to_range_value(value: datetime | date | str) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _default_protocol_path() -> Path:
    return Path(__file__).resolve().parent / "configs" / "default_protocol.json"


def _canonical_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _canonical_vector(params: Mapping[str, Any]) -> str:
    return json.dumps(dict(params), sort_keys=True, separators=(",", ":"))


def _float_precision(step: float | None) -> int:
    if step is None:
        return 6
    token = f"{float(step):.12f}".rstrip("0").rstrip(".")
    if "." not in token:
        return 0
    return len(token.split(".", maxsplit=1)[1])


def _base_active_vector(base_settings: AppSettings, active_params: Mapping[str, ParamSpec]) -> dict[str, Any]:
    base_values = {}
    base_values.update(dataclasses.asdict(base_settings.strategy))
    base_values.update(dataclasses.asdict(base_settings.risk))
    return {
        name: base_values.get(name, spec.default_value)
        for name, spec in sorted(active_params.items())
    }


def _history_value_counts(historical_vectors: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for vector in historical_vectors:
        for name, value in vector.items():
            values = counts.setdefault(name, {})
            key = _canonical_value(value)
            values[key] = values.get(key, 0) + 1
    return counts


def _sample_int(
    spec: ParamSpec,
    rng: random.Random,
    *,
    current_value: int | None,
    history_counts: dict[str, int],
) -> int:
    if spec.low is None or spec.high is None:
        raise ValueError(f"Missing int bounds for active parameter {spec.name}")
    low = int(spec.low)
    high = int(spec.high)
    step = int(spec.step or 1)
    count = ((high - low) // step) + 1
    candidates = [low + step * rng.randrange(count) for _ in range(8)]
    candidates.extend([low, high])
    filtered = [value for value in candidates if current_value is None or value != current_value]
    pool = filtered or candidates
    best_score = min(history_counts.get(_canonical_value(value), 0) for value in pool)
    best_pool = [value for value in pool if history_counts.get(_canonical_value(value), 0) == best_score]
    return best_pool[0]


def _sample_float(
    spec: ParamSpec,
    rng: random.Random,
    *,
    current_value: float | None,
    history_counts: dict[str, int],
    low_override: float | None = None,
) -> float:
    if spec.low is None or spec.high is None:
        raise ValueError(f"Missing float bounds for active parameter {spec.name}")
    low = float(spec.low) if low_override is None else max(float(spec.low), float(low_override))
    high = float(spec.high)
    if low > high:
        raise ValueError(f"Invalid float sampling bounds for active parameter {spec.name}")
    step = float(spec.step) if spec.step is not None else None
    precision = _float_precision(step)

    candidates: list[float] = []
    if step is None:
        for _ in range(8):
            candidates.append(round(rng.uniform(low, high), precision))
    else:
        count = int(round((high - low) / step)) + 1
        for _ in range(8):
            candidates.append(round(low + step * rng.randrange(count), precision))
        candidates.extend([round(low, precision), round(high, precision)])

    filtered = [value for value in candidates if current_value is None or abs(value - current_value) > 1e-12]
    pool = filtered or candidates
    best_score = min(history_counts.get(_canonical_value(value), 0) for value in pool)
    best_pool = [value for value in pool if history_counts.get(_canonical_value(value), 0) == best_score]
    return best_pool[0]


def _sample_bool(spec: ParamSpec, rng: random.Random, *, current_value: bool | None) -> bool:
    candidates = [False, True]
    if current_value is not None and len(candidates) > 1:
        candidates = [value for value in candidates if value != current_value]
    return rng.choice(candidates or [False, True])


def _sample_categorical(spec: ParamSpec, rng: random.Random, *, current_value: Any) -> Any:
    choices = list(spec.choices if spec.choices is not None else (spec.default_value,))
    if current_value is not None and len(choices) > 1:
        choices = [value for value in choices if value != current_value]
    return rng.choice(choices or list(spec.choices or (spec.default_value,)))


def _sample_param_value(
    spec: ParamSpec,
    rng: random.Random,
    *,
    current_value: Any,
    history_counts: dict[str, int],
    low_override: float | None = None,
) -> Any:
    if spec.domain_type == "int":
        return _sample_int(spec, rng, current_value=None if current_value is None else int(current_value), history_counts=history_counts)
    if spec.domain_type == "float":
        return _sample_float(
            spec,
            rng,
            current_value=None if current_value is None else float(current_value),
            history_counts=history_counts,
            low_override=low_override,
        )
    if spec.domain_type == "bool":
        return _sample_bool(spec, rng, current_value=None if current_value is None else bool(current_value))
    if spec.domain_type == "categorical":
        return _sample_categorical(spec, rng, current_value=current_value)
    raise ValueError(f"Unsupported active domain type for autoresearch sampling: {spec.name}={spec.domain_type}")


def _repair_direct_constraints(
    vector: dict[str, Any],
    active_params: Mapping[str, ParamSpec],
    rng: random.Random,
    history_value_counts: Mapping[str, dict[str, int]],
) -> dict[str, Any]:
    candidate = dict(vector)
    if "tp1_atr_mult" in candidate and "tp2_atr_mult" in candidate:
        tp1 = float(candidate["tp1_atr_mult"])
        tp2 = float(candidate["tp2_atr_mult"])
        if tp1 >= tp2:
            tp2_spec = active_params["tp2_atr_mult"]
            step = float(tp2_spec.step or 0.1)
            candidate["tp2_atr_mult"] = _sample_param_value(
                tp2_spec,
                rng,
                current_value=tp2,
                history_counts=dict(history_value_counts.get("tp2_atr_mult", {})),
                low_override=round(tp1 + step, _float_precision(step)),
            )
    return candidate


def _normalize_active_vector(
    params: Mapping[str, Any],
    *,
    base_vector: Mapping[str, Any],
    active_params: Mapping[str, ParamSpec],
) -> dict[str, Any]:
    vector = dict(base_vector)
    for name in active_params:
        if name in params:
            vector[name] = params[name]
    return vector


def _recommendation_priority(recommendations: list[RecommendationDraft]) -> dict[str, int]:
    priority: dict[str, int] = {}
    for index, recommendation in enumerate(reversed(recommendations)):
        priority.setdefault(recommendation.candidate_id, index)
    return priority


def _history_trial_sort_key(trial: TrialEvaluation, recommendation_priority: Mapping[str, int]) -> tuple[Any, ...]:
    return (
        recommendation_priority.get(trial.trial_id, 10**9),
        -trial.metrics.expectancy_r,
        -trial.metrics.profit_factor,
        trial.metrics.max_drawdown_pct,
        -trial.metrics.trades_count,
        trial.trial_id,
    )


def _generate_random_vector(
    *,
    active_params: Mapping[str, ParamSpec],
    history_value_counts: Mapping[str, dict[str, int]],
    rng: random.Random,
) -> dict[str, Any]:
    vector: dict[str, Any] = {}
    for name, spec in sorted(active_params.items()):
        low_override: float | None = None
        if name == "tp2_atr_mult" and "tp1_atr_mult" in vector:
            step = float(spec.step or 0.1)
            low_override = round(float(vector["tp1_atr_mult"]) + step, _float_precision(step))
        vector[name] = _sample_param_value(
            spec,
            rng,
            current_value=None,
            history_counts=dict(history_value_counts.get(name, {})),
            low_override=low_override,
        )
    return _repair_direct_constraints(vector, active_params, rng, history_value_counts)


def _mutate_vector(
    *,
    seed_vector: Mapping[str, Any],
    active_params: Mapping[str, ParamSpec],
    history_value_counts: Mapping[str, dict[str, int]],
    rng: random.Random,
) -> dict[str, Any]:
    candidate = dict(seed_vector)
    names = sorted(active_params)
    mutations = min(len(names), 1 + rng.randrange(3))
    for name in rng.sample(names, mutations):
        candidate[name] = _sample_param_value(
            active_params[name],
            rng,
            current_value=seed_vector.get(name),
            history_counts=dict(history_value_counts.get(name, {})),
        )
    return _repair_direct_constraints(candidate, active_params, rng, history_value_counts)


def _generate_candidate_vectors(
    *,
    base_settings: AppSettings,
    seed: int,
    max_candidates: int,
    trials: list[TrialEvaluation],
    recommendations: list[RecommendationDraft],
) -> list[dict[str, Any]]:
    build_param_registry()
    active_params = get_active_params()
    base_vector = _base_active_vector(base_settings, active_params)
    recommendation_priority = _recommendation_priority(recommendations)

    accepted_trials = [trial for trial in trials if trial.rejected_reason is None]
    ordered_history = sorted(accepted_trials, key=lambda trial: _history_trial_sort_key(trial, recommendation_priority))

    historical_vectors: list[dict[str, Any]] = []
    historical_keys: set[str] = set()
    for trial in ordered_history:
        vector = _normalize_active_vector(trial.params, base_vector=base_vector, active_params=active_params)
        key = _canonical_vector(vector)
        if key in historical_keys:
            continue
        historical_vectors.append(vector)
        historical_keys.add(key)

    history_value_counts = _history_value_counts(historical_vectors)
    rng = random.Random(seed)
    generated: list[dict[str, Any]] = []
    generated_keys: set[str] = set()
    attempts = 0
    max_attempts = max(max_candidates * 25, 100)

    while len(generated) < max_candidates and attempts < max_attempts:
        attempts += 1
        if historical_vectors:
            seed_vector = historical_vectors[(attempts - 1) % len(historical_vectors)]
            candidate = _mutate_vector(
                seed_vector=seed_vector,
                active_params=active_params,
                history_value_counts=history_value_counts,
                rng=rng,
            )
        else:
            candidate = _generate_random_vector(
                active_params=active_params,
                history_value_counts=history_value_counts,
                rng=rng,
            )

        key = _canonical_vector(candidate)
        if key in historical_keys or key in generated_keys:
            continue
        generated.append(candidate)
        generated_keys.add(key)

    while len(generated) < max_candidates and attempts < max_attempts * 2:
        attempts += 1
        candidate = _generate_random_vector(
            active_params=active_params,
            history_value_counts=history_value_counts,
            rng=rng,
        )
        key = _canonical_vector(candidate)
        if key in historical_keys or key in generated_keys:
            continue
        generated.append(candidate)
        generated_keys.add(key)

    return generated


def _apply_llm_advisory(
    vectors: list[dict[str, Any]],
    llm_advisory_fn: Callable[[list[dict]], list[str]] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if llm_advisory_fn is None or not vectors:
        return [dict(vector) for vector in vectors], [""] * len(vectors)

    advisory_vectors = [dict(vector) for vector in vectors]
    expected = sorted(_canonical_vector(vector) for vector in advisory_vectors)
    rationales = llm_advisory_fn(advisory_vectors)
    observed = sorted(_canonical_vector(vector) for vector in advisory_vectors)
    if observed != expected:
        raise ValueError("llm_advisory_fn may reorder vectors only; adding, removing, or mutating candidates is not allowed.")
    if len(rationales) != len(advisory_vectors):
        raise ValueError("llm_advisory_fn must return one rationale string per candidate.")
    return advisory_vectors, [str(rationale) for rationale in rationales]


def _blocking_risks(report) -> tuple[str, ...]:
    risks: list[str] = []
    if not report.passed:
        risks.append("walkforward_not_passed")
    if report.fragile:
        risks.append("walkforward_fragile")
    risks.extend(reason for reason in report.reasons if reason in PROMOTION_BLOCKING_RISKS)
    return tuple(dict.fromkeys(risks))


def _rank_key(result: AutoresearchCandidateResult) -> tuple[Any, ...]:
    metrics = result.evaluation.metrics
    return (
        not result.walkforward_report.passed,
        result.walkforward_report.fragile,
        -metrics.expectancy_r,
        -metrics.profit_factor,
        metrics.max_drawdown_pct,
        -metrics.trades_count,
        result.candidate_id,
    )


def _rank_results(results: list[AutoresearchCandidateResult]) -> tuple[AutoresearchCandidateResult, ...]:
    ranked = sorted(results, key=_rank_key)
    return tuple(dataclasses.replace(result, rank=index) for index, result in enumerate(ranked, start=1))


def _write_loop_report(*, report: AutoresearchLoopReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "loop_report.json"
    output_path.write_text(
        json.dumps(dataclasses.asdict(report), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def _build_loop_report(
    *,
    run_id: str,
    protocol_hash: str,
    seed: int,
    date_range_start: str,
    date_range_end: str,
    candidates_generated: int,
    stop_reason: str,
    results: tuple[AutoresearchCandidateResult, ...],
    approval_bundle_written: bool,
    approval_bundle_candidate_id: str | None,
) -> AutoresearchLoopReport:
    return AutoresearchLoopReport(
        run_id=run_id,
        protocol_hash=protocol_hash,
        seed=seed,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        candidates_generated=candidates_generated,
        candidates_evaluated=len(results),
        candidates_blocked=sum(1 for result in results if result.blocking_risks),
        stop_reason=stop_reason,
        results=results,
        approval_bundle_written=approval_bundle_written,
        approval_bundle_candidate_id=approval_bundle_candidate_id,
    )


def run_autoresearch_loop(
    *,
    source_db_path: Path,
    store_path: Path,
    snapshots_dir: Path,
    output_dir: Path,
    backtest_config: BacktestConfig,
    base_settings: AppSettings,
    protocol_path: Path | None = None,
    seed: int = 42,
    max_candidates: int = 10,
    llm_advisory_fn: Callable[[list[dict]], list[str]] | None = None,
) -> AutoresearchLoopReport:
    if max_candidates <= 0:
        raise ValueError("max_candidates must be >= 1")
    if max_candidates > _MAX_CANDIDATES_HARD_LIMIT:
        raise ValueError(f"max_candidates must be <= {_MAX_CANDIDATES_HARD_LIMIT}")

    protocol_file = protocol_path or _default_protocol_path()
    protocol = load_protocol(protocol_file)
    walkforward_mode = str(protocol.get("walkforward_mode", "post_hoc")).strip().lower()
    if walkforward_mode != "post_hoc":
        raise ValueError("autoresearch v1 requires walkforward_mode=post_hoc")

    protocol_hash = hash_protocol(protocol)
    run_id = uuid.uuid4().hex
    date_range_start = _to_range_value(backtest_config.start_date)
    date_range_end = _to_range_value(backtest_config.end_date)

    try:
        init_store(store_path)
        historical_trials = load_trials(store_path)
        historical_recommendations = load_recommendations(store_path)
    except _STORE_ERROR_TYPES:
        report = _build_loop_report(
            run_id=run_id,
            protocol_hash=protocol_hash,
            seed=int(seed),
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            candidates_generated=0,
            stop_reason="store_not_writable",
            results=(),
            approval_bundle_written=False,
            approval_bundle_candidate_id=None,
        )
        _write_loop_report(report=report, output_dir=output_dir)
        return report

    try:
        check_baseline(
            source_db_path=source_db_path,
            backtest_config=backtest_config,
            base_settings=base_settings,
        )
    except BaselineGateError:
        report = _build_loop_report(
            run_id=run_id,
            protocol_hash=protocol_hash,
            seed=int(seed),
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            candidates_generated=0,
            stop_reason="baseline_gate_failed",
            results=(),
            approval_bundle_written=False,
            approval_bundle_candidate_id=None,
        )
        _write_loop_report(report=report, output_dir=output_dir)
        return report

    generated_vectors = _generate_candidate_vectors(
        base_settings=base_settings,
        seed=int(seed),
        max_candidates=int(max_candidates),
        trials=historical_trials,
        recommendations=historical_recommendations,
    )
    generated_vectors, rationales = _apply_llm_advisory(generated_vectors, llm_advisory_fn)

    filtered_vectors: list[tuple[dict[str, Any], str]] = []
    for vector, rationale in zip(generated_vectors, rationales):
        if validate_param_vector(vector):
            continue
        filtered_vectors.append((vector, rationale))
        if len(filtered_vectors) >= int(max_candidates):
            break

    windows = build_windows(
        data_start=date_range_start,
        data_end=date_range_end,
        protocol=protocol,
    )
    min_trades_full_candidate = int(protocol.get("min_trades_full_candidate", MIN_TRADES_DEFAULT))

    stop_reason = "completed"
    results: list[AutoresearchCandidateResult] = []

    for index, (vector, rationale) in enumerate(filtered_vectors):
        candidate_settings = build_candidate_settings(base_settings, vector)
        snapshot_path = create_trial_snapshot(source_db_path, snapshots_dir, f"autoresearch-{run_id[:8]}-{index:03d}")
        conn = open_snapshot_connection(snapshot_path)
        try:
            verify_required_tables(conn)
            evaluation_raw = evaluate_candidate(
                conn,
                settings=candidate_settings,
                backtest_config=backtest_config,
                min_trades=min_trades_full_candidate,
            )
        finally:
            conn.close()

        evaluation = dataclasses.replace(
            evaluation_raw,
            params=dict(vector),
            protocol_hash=protocol_hash,
        )
        try:
            save_trial(evaluation, store_path)
        except _STORE_ERROR_TYPES:
            stop_reason = "store_not_writable"
            break

        walkforward_report = run_walkforward(
            base_settings=base_settings,
            candidate_params=vector,
            windows=windows,
            source_db_path=source_db_path,
            snapshots_dir=snapshots_dir,
            protocol=protocol,
        )
        try:
            save_walkforward(evaluation.trial_id, walkforward_report, store_path)
        except _STORE_ERROR_TYPES:
            stop_reason = "store_not_writable"
            break

        results.append(
            AutoresearchCandidateResult(
                candidate_id=evaluation.trial_id,
                params=dict(vector),
                hypothesis_rationale=rationale,
                evaluation=evaluation,
                walkforward_report=walkforward_report,
                blocking_risks=_blocking_risks(walkforward_report),
                rank=0,
            )
        )

    ranked_results = _rank_results(results)
    recommendations_by_candidate_id: dict[str, RecommendationDraft] = {}

    if stop_reason != "store_not_writable":
        for result in ranked_results:
            candidate_settings = build_candidate_settings(base_settings, result.params)
            recommendation = build_recommendation(
                base_settings=base_settings,
                candidate_settings=candidate_settings,
                evaluation=result.evaluation,
                walkforward_report=result.walkforward_report,
            )
            recommendations_by_candidate_id[result.candidate_id] = recommendation
            try:
                save_recommendation(recommendation, store_path)
            except _STORE_ERROR_TYPES:
                stop_reason = "store_not_writable"
                recommendations_by_candidate_id.clear()
                break

    approval_bundle_written = False
    approval_bundle_candidate_id: str | None = None
    if stop_reason != "store_not_writable" and ranked_results:
        top_result = ranked_results[0]
        if not top_result.blocking_risks:
            write_approval_bundle(
                recommendation=recommendations_by_candidate_id[top_result.candidate_id],
                output_dir=output_dir / "approval_bundle",
            )
            approval_bundle_written = True
            approval_bundle_candidate_id = top_result.candidate_id

    if stop_reason == "completed" and len(filtered_vectors) >= int(max_candidates):
        stop_reason = "max_candidates_reached"

    report = _build_loop_report(
        run_id=run_id,
        protocol_hash=protocol_hash,
        seed=int(seed),
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        candidates_generated=len(generated_vectors),
        stop_reason=stop_reason,
        results=ranked_results,
        approval_bundle_written=approval_bundle_written,
        approval_bundle_candidate_id=approval_bundle_candidate_id,
    )
    _write_loop_report(report=report, output_dir=output_dir)
    return report

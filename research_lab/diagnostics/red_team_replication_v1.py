"""M6 RED_TEAM_REPLICATION_V1 orchestrator.

Part A imports the existing SMC sequence diagnostic as-is and varies only the
approved `DiagnosticConfig` fields. Part B delegates to the independent
trial-00095 SQL replication module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Any

from research_lab import analysis_smc_sequence_edge_feasibility_v1 as smc
from research_lab.diagnostics import trial_00095_sql_replication_v1 as trial95


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_JSON = PROJECT_ROOT / "research_lab" / "reports" / "red_team_replication_v1.json"
DEFAULT_REPORT_SHA = PROJECT_ROOT / "research_lab" / "reports" / "red_team_replication_v1.sha256"
DEFAULT_REPORT_MD = PROJECT_ROOT / "research_lab" / "reports" / "red_team_replication_v1.md"
DEFAULT_PART_B_JSON = PROJECT_ROOT / "research_lab" / "reports" / "trial_00095_sql_replication_v1.json"
PRIOR_BASELINE_RAW_FILE_SHA_INFORMATIONAL = "8CA802FD610DFE552225C9318A455345D8917D688ABBD2B3647CA69C4B6A78A4"
EXPECTED_SMC_BASELINE_ANALYTICAL_CONTENT = {
    "event_count": 1271,
    "net_5b_pf": 1.061059,
    "net_5b_median": -0.000442,
    "mfe_before_entry_median": 0.011565,
    "mfe_after_entry_5b_median": 0.004916,
    "mfe_before_after_ratio": 2.352473,
}
ANALYTICAL_CONTENT_ABS_TOLERANCE = 1e-6


PART_A_RUN_ORDER = ["A1_BASELINE", "P1", "P2", "P3", "P4", "P5", "A3_RAW_SWEEP_RECLAIM"]
PART_A_PERTURBATIONS: dict[str, dict[str, Any]] = {
    "P1": {"sweep_proximity_atr": 0.20},
    "P2": {"sweep_proximity_atr": 0.80},
    "P3": {"mitigation_window_bars": 5},
    "P4": {"displacement_body_atr": 0.30},
    "P5": {"round_trip_cost_pct": 0.0000},
}

PRE_DATA_INTERPRETATIONS = {
    "P1": "If this flips the verdict, the original sweep proximity was too loose and admitted noisy sweeps that diluted a narrower edge.",
    "P2": "If this flips the verdict, the original sweep proximity was too strict and rejected valid sweep contexts.",
    "P3": "If this flips the verdict, the prior invalidation was materially driven by waiting too long for mitigation entry.",
    "P4": "If this flips the verdict, the original displacement gate was too aggressive and excluded softer but tradable sequences.",
    "P5": "If this alone flips the verdict, SMC_SEQUENCE has gross edge that transaction costs destroy rather than no structural edge.",
    "A3_RAW_SWEEP_RECLAIM": "If this flips while gated SMC remains invalidated, the SMC gates destroyed a simpler raw edge and prior sweep-reclaim closure must be reconciled.",
}


def config_as_dict(config: smc.DiagnosticConfig) -> dict[str, Any]:
    return smc.json_ready(config)


def build_run_configs(base: smc.DiagnosticConfig | None = None) -> dict[str, smc.DiagnosticConfig]:
    base_config = base or smc.DiagnosticConfig()
    configs = {"A1_BASELINE": base_config}
    for run_id, overrides in PART_A_PERTURBATIONS.items():
        configs[run_id] = replace(base_config, **overrides)
    return configs


def changed_config_fields(base: smc.DiagnosticConfig, candidate: smc.DiagnosticConfig) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for field in fields(base):
        old = getattr(base, field.name)
        new = getattr(candidate, field.name)
        if old != new:
            changes[field.name] = {"baseline": old, "candidate": new}
    return changes


def verify_single_parameter_isolation(base: smc.DiagnosticConfig) -> dict[str, Any]:
    configs = build_run_configs(base)
    rows: dict[str, Any] = {}
    for run_id, overrides in PART_A_PERTURBATIONS.items():
        changes = changed_config_fields(base, configs[run_id])
        rows[run_id] = {
            "expected_override": overrides,
            "changed_fields": changes,
            "is_isolated": len(changes) == 1 and set(changes) == set(overrides),
        }
    return rows


def _stable_smc_payload(payload: dict[str, Any]) -> dict[str, Any]:
    stable = json.loads(json.dumps(payload, sort_keys=True, default=str))
    manifest = stable.get("manifest", {})
    manifest["generated_at_utc"] = "DETERMINISTIC_NO_WALL_CLOCK"
    manifest["db_path"] = "<EXPLICIT_DB_PATH>"
    stable["events"] = []
    stable["events_truncated_for_m6_hash"] = True
    return stable


def stable_sha(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()


def _extract_analytical_content(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload["summary"]["full_sequence"]
    before = summary.get("median_mfe_before_entry")
    after = summary.get("entry_5_mfe_median")
    ratio = (before / after) if before is not None and after not in (None, 0) else None
    return {
        "event_count": summary.get("count"),
        "net_5b_pf": summary.get("entry_5_profit_factor_proxy"),
        "net_5b_median": summary.get("entry_5_net_return_median"),
        "mfe_before_entry_median": before,
        "mfe_after_entry_5b_median": after,
        "mfe_before_after_ratio": ratio,
    }


def analytical_content_matches(baseline_payload: dict[str, Any]) -> tuple[bool, dict[str, dict[str, Any]]]:
    observed = _extract_analytical_content(baseline_payload)
    report: dict[str, dict[str, Any]] = {}
    for field_name, expected in EXPECTED_SMC_BASELINE_ANALYTICAL_CONTENT.items():
        value = observed.get(field_name)
        if field_name == "event_count":
            delta = None if value is None else abs(value - expected)
            in_tolerance = value == expected
        else:
            delta = None if value is None else abs(value - expected)
            in_tolerance = delta is not None and delta < ANALYTICAL_CONTENT_ABS_TOLERANCE
        report[field_name] = {
            "observed": value,
            "expected": expected,
            "abs_delta": delta,
            "in_tolerance": in_tolerance,
        }
    return all(row["in_tolerance"] for row in report.values()), report


def extract_part_a_row(
    *,
    run_id: str,
    description: str,
    payload: dict[str, Any],
    observed_sha: str | None,
    expected_sha: str | None,
    config_changes: dict[str, Any],
) -> dict[str, Any]:
    content = _extract_analytical_content(payload)
    pf = content["net_5b_pf"]
    median_net = content["net_5b_median"]
    ratio = content["mfe_before_after_ratio"]
    flips = bool(pf is not None and median_net is not None and ratio is not None and pf >= 1.5 and median_net >= 0 and ratio <= 1.0)
    return {
        "run_id": run_id,
        "description": description,
        "status": "RUN",
        "config_changes": config_changes,
        "observed_stable_sha256": observed_sha,
        "expected_prior_sha256": expected_sha,
        "sha_matches_expected": observed_sha == expected_sha if expected_sha else None,
        "source_verdict": payload["invalidation_checks"]["verdict"],
        "m6_flip_gate_passed": flips,
        "event_count": content["event_count"],
        "net_5b_pf": pf,
        "net_5b_median": median_net,
        "mfe_before_entry_median": content["mfe_before_entry_median"],
        "mfe_after_entry_5b_median": content["mfe_after_entry_5b_median"],
        "mfe_before_after_ratio": ratio,
    }


def _not_run_row(run_id: str, reason: str, config_changes: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "description": run_id,
        "status": "NOT_RUN",
        "reason": reason,
        "config_changes": config_changes,
        "observed_stable_sha256": None,
        "expected_prior_sha256": None,
        "sha_matches_expected": None,
        "source_verdict": None,
        "m6_flip_gate_passed": False,
        "event_count": None,
        "net_5b_pf": None,
        "net_5b_median": None,
        "mfe_before_entry_median": None,
        "mfe_after_entry_5b_median": None,
        "mfe_before_after_ratio": None,
    }


def run_smc_analysis_once(
    *,
    db_path: Path,
    config: smc.DiagnosticConfig,
    run_id: str,
    temp_dir: Path,
) -> tuple[dict[str, Any], str]:
    output_path = temp_dir / f"{run_id}.json"
    report_path = temp_dir / f"{run_id}.md"
    payload = smc.run_analysis(
        db_path=db_path,
        output_path=output_path,
        report_path=report_path,
        config=config,
        start=None,
        end=None,
    )
    return payload, stable_sha(_stable_smc_payload(payload))


def build_raw_sweep_reclaim_events(
    candles: list[smc.Candle],
    sweeps: list[smc.SweepEvent],
    config: smc.DiagnosticConfig,
) -> list[smc.SequenceEvent]:
    events: list[smc.SequenceEvent] = []
    max_window = max(config.forward_windows)
    max_entry = len(candles) - max_window - 1
    for sweep in sweeps:
        entry_bar = None
        for idx in range(sweep.detection_bar + 1, max_entry + 1):
            close = candles[idx].close
            if sweep.direction == "LONG" and close >= sweep.level:
                entry_bar = idx
                break
            if sweep.direction == "SHORT" and close <= sweep.level:
                entry_bar = idx
                break
        if entry_bar is None:
            continue
        event = smc.SequenceEvent(
            symbol=sweep.symbol,
            timeframe=sweep.timeframe,
            direction=sweep.direction,
            sequence_source="RAW_SWEEP_RECLAIM",
            detection_bar=sweep.detection_bar,
            displacement_bar=entry_bar,
            structure_shift_bar=entry_bar,
            fvg_created_bar=entry_bar,
            confirmation_bar=entry_bar,
            mitigation_bar=entry_bar,
            entry_candidate_bar=entry_bar,
            label_available_bar=entry_bar,
            return_start_bar_detection=sweep.detection_bar,
            return_start_bar_entry_candidate=entry_bar,
            return_start_bar_label_available=entry_bar,
            detection_time_utc=candles[sweep.detection_bar].open_time.isoformat(),
            entry_candidate_time_utc=candles[entry_bar].open_time.isoformat(),
            level=sweep.level,
            sweep_side=sweep.sweep_side,
            sweep_depth_atr=sweep.sweep_depth_atr,
            structure_level=sweep.level,
            fvg_zone_low=sweep.level,
            fvg_zone_high=sweep.level,
            fvg_gap_atr=0.0,
            displacement_body_atr=0.0,
            displacement_range_atr=0.0,
            entry_price=candles[entry_bar].open,
            metadata={
                "ablation": "displacement_structure_fvg_mitigation_gates_disabled",
                "pre_data_interpretation": PRE_DATA_INTERPRETATIONS["A3_RAW_SWEEP_RECLAIM"],
            },
        )
        event.forward_detection = smc.forward_metrics(
            candles,
            start_bar=sweep.detection_bar,
            windows=config.forward_windows,
            direction=sweep.direction,
            cost_pct=config.round_trip_cost_pct,
        )
        event.forward_entry_candidate = smc.forward_metrics(
            candles,
            start_bar=entry_bar,
            windows=config.forward_windows,
            direction=sweep.direction,
            cost_pct=config.round_trip_cost_pct,
        )
        event.forward_label_available = dict(event.forward_entry_candidate)
        event.mfe_before_entry = smc.mfe_between(
            candles,
            start_bar=sweep.detection_bar,
            end_bar=entry_bar - 1,
            direction=sweep.direction,
        )
        events.append(event)
    return events


def run_raw_sweep_reclaim_ablation(db_path: Path, config: smc.DiagnosticConfig) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        candles = smc.load_candles(conn, symbol=config.symbol, timeframe=config.timeframe, start=None, end=None)
    quality = smc.validate_candles(candles)
    atr = smc.compute_atr_series(candles, config.atr_period)
    sweeps = smc.detect_sweep_events(candles, atr, config)
    events = build_raw_sweep_reclaim_events(candles, sweeps, config)
    sequence_summary = smc.summarize_group(events, config)
    sweep_summary = smc.summarize_sweeps_as_baseline(sweeps, candles, config)
    control = smc.deterministic_control(events, candles, config)
    wf = smc.walk_forward_summary(events, candles, config)
    invalidation = smc.invalidation_checks(
        sequence_summary=sequence_summary,
        sweep_summary=sweep_summary,
        control_summary=control,
        walk_forward=wf,
    )
    return {
        "manifest": {
            "milestone": "M6_RED_TEAM_REPLICATION_V1",
            "run_id": "A3_RAW_SWEEP_RECLAIM",
            "generated_at_utc": "DETERMINISTIC_NO_WALL_CLOCK",
            "research_only": True,
            "production_changes": False,
            "config": smc.json_ready(config),
        },
        "data_quality": smc.json_ready(quality),
        "sweep_events_total": len(sweeps),
        "sequence_events_total": len(events),
        "summary": {
            "full_sequence": sequence_summary,
            "sweep_only": sweep_summary,
            "walk_forward": wf,
        },
        "control_cohort": control,
        "invalidation_checks": invalidation,
        "events": [],
    }


def evaluate_part_a(
    rows: list[dict[str, Any]],
    *,
    baseline_analytical_content_match: bool,
    baseline_analytical_content_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row_by_id = {row["run_id"]: row for row in rows}
    notes: list[str] = []
    if row_by_id.get("P1", {}).get("m6_flip_gate_passed") and row_by_id.get("P2", {}).get("m6_flip_gate_passed"):
        notes.append("METRIC_HYPERSENSITIVE")
    if not baseline_analytical_content_match:
        return {
            "verdict": "BASELINE_ANALYTICAL_CONTENT_MISMATCH",
            "reason": "A.1 analytical content did not match locked baseline fields.",
            "baseline_analytical_content_report": baseline_analytical_content_report or {},
            "diagnostic_notes": notes,
        }
    perturbation_flips = [
        run_id
        for run_id in ("P1", "P2", "P3", "P4", "P5")
        if row_by_id.get(run_id, {}).get("m6_flip_gate_passed")
    ]
    a3_flip = bool(row_by_id.get("A3_RAW_SWEEP_RECLAIM", {}).get("m6_flip_gate_passed"))
    if perturbation_flips == ["P5"] and not a3_flip:
        verdict = "SMC_SEQUENCE_EDGE_IS_GROSS_ONLY"
    elif a3_flip and not perturbation_flips:
        verdict = "SMC_GATES_DESTROYED_RAW_EDGE"
    elif perturbation_flips:
        verdict = "SMC_SEQUENCE_VERDICT_NOT_ROBUST"
    else:
        verdict = "SMC_SEQUENCE_INVALIDATION_ROBUST"
    return {
        "verdict": verdict,
        "reason": "Computed mechanically from Part A flip gates.",
        "perturbation_flips": perturbation_flips,
        "a3_flip": a3_flip,
        "diagnostic_notes": notes,
    }


def run_part_a(
    *,
    db_path: Path,
    continue_after_baseline_mismatch: bool = False,
) -> dict[str, Any]:
    base = smc.DiagnosticConfig()
    configs = build_run_configs(base)
    isolation = verify_single_parameter_isolation(base)
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="m6_part_a_") as tmp:
        temp_dir = Path(tmp)
        baseline_payload, baseline_sha = run_smc_analysis_once(
            db_path=db_path,
            config=configs["A1_BASELINE"],
            run_id="A1_BASELINE",
            temp_dir=temp_dir,
        )
        baseline_match, baseline_analytical_report = analytical_content_matches(baseline_payload)
        rows.append(
            extract_part_a_row(
                run_id="A1_BASELINE",
                description="baseline default DiagnosticConfig",
                payload=baseline_payload,
                observed_sha=baseline_sha,
                expected_sha=PRIOR_BASELINE_RAW_FILE_SHA_INFORMATIONAL,
                config_changes={},
            )
        )
        if baseline_match or continue_after_baseline_mismatch:
            for run_id in ("P1", "P2", "P3", "P4", "P5"):
                payload, observed_sha = run_smc_analysis_once(
                    db_path=db_path,
                    config=configs[run_id],
                    run_id=run_id,
                    temp_dir=temp_dir,
                )
                rows.append(
                    extract_part_a_row(
                        run_id=run_id,
                        description=run_id,
                        payload=payload,
                        observed_sha=observed_sha,
                        expected_sha=None,
                        config_changes=isolation[run_id]["changed_fields"],
                    )
                )
            a3_payload = run_raw_sweep_reclaim_ablation(db_path, base)
            rows.append(
                extract_part_a_row(
                    run_id="A3_RAW_SWEEP_RECLAIM",
                    description="raw sweep reclaim ablation",
                    payload=a3_payload,
                    observed_sha=stable_sha(_stable_smc_payload(a3_payload)),
                    expected_sha=None,
                    config_changes={
                        "disabled_gates": [
                            "displacement",
                            "structure_shift",
                            "fvg",
                            "mitigation",
                        ]
                    },
                )
            )
        else:
            for run_id in ("P1", "P2", "P3", "P4", "P5"):
                rows.append(_not_run_row(run_id, "BASELINE_ANALYTICAL_CONTENT_MISMATCH_STOP", isolation[run_id]["changed_fields"]))
            rows.append(_not_run_row("A3_RAW_SWEEP_RECLAIM", "BASELINE_ANALYTICAL_CONTENT_MISMATCH_STOP", {"disabled_gates": []}))
    baseline = rows[0]
    for row in rows[1:]:
        row["delta_vs_baseline"] = {
            key: (
                row.get(key) - baseline.get(key)
                if isinstance(row.get(key), (int, float)) and isinstance(baseline.get(key), (int, float))
                else None
            )
            for key in (
                "event_count",
                "net_5b_pf",
                "net_5b_median",
                "mfe_before_entry_median",
                "mfe_after_entry_5b_median",
                "mfe_before_after_ratio",
            )
        }
    return {
        "prior_baseline_raw_file_sha_informational": PRIOR_BASELINE_RAW_FILE_SHA_INFORMATIONAL,
        "stable_sha_note": (
            "M6 stable SHA canonicalizes the SMC payload wall-clock and db_path fields and omits "
            "raw events for deterministic comparison. It is lineage metadata only; the Part A "
            "baseline stop condition is the analytical-content check."
        ),
        "analytical_content_baseline_check": {
            "expected": EXPECTED_SMC_BASELINE_ANALYTICAL_CONTENT,
            "observed": baseline_analytical_report,
            "match": baseline_match,
            "tolerance": ANALYTICAL_CONTENT_ABS_TOLERANCE,
        },
        "single_parameter_isolation": isolation,
        "runs": rows,
        "verdict": evaluate_part_a(
            rows,
            baseline_analytical_content_match=baseline_match,
            baseline_analytical_content_report=baseline_analytical_report,
        ),
    }


def final_m6_verdict(part_a: dict[str, Any], part_b: dict[str, Any]) -> dict[str, Any]:
    part_a_verdict = part_a["verdict"]["verdict"]
    part_b_verdict = part_b["database_binding"]["verdict"]
    if part_a_verdict == "BASELINE_ANALYTICAL_CONTENT_MISMATCH":
        verdict = "BASELINE_NOT_REPRODUCIBLE"
    elif part_b_verdict == "DATABASE_LINEAGE_MISMATCH":
        verdict = "DATABASE_LINEAGE_MISMATCH"
    elif part_b_verdict == "VALIDATED_EDGE_NOT_REPRODUCIBLE":
        verdict = "VALIDATED_EDGE_NOT_REPRODUCIBLE"
    elif part_b_verdict == "PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL":
        verdict = "PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL"
    elif part_a_verdict == "SMC_SEQUENCE_INVALIDATION_ROBUST" and part_b_verdict == "FULL_REPRODUCTION":
        verdict = "REPLICATION_VERIFIES_PRIOR_VERDICTS"
    else:
        verdict = "PRIOR_VERDICT_NOT_ROBUST"
    return {
        "verdict": verdict,
        "part_a_verdict": part_a_verdict,
        "part_b_verdict": part_b_verdict,
        "computed_mechanically": True,
    }


def build_payload(
    *,
    db_path: Path,
    snapshot_db_path: Path | None,
    continue_after_baseline_mismatch: bool = False,
) -> dict[str, Any]:
    part_a = run_part_a(
        db_path=db_path,
        continue_after_baseline_mismatch=continue_after_baseline_mismatch,
    )
    part_b = trial95.run_replication(
        canonical_db_path=db_path,
        snapshot_db_path=snapshot_db_path,
    )
    return {
        "manifest": {
            "diagnostic": "RED_TEAM_REPLICATION_V1",
            "generated_at_utc": "DETERMINISTIC_NO_WALL_CLOCK",
            "research_only": True,
            "production_changes": False,
            "canonical_db_path": str(db_path),
            "snapshot_db_path": str(snapshot_db_path) if snapshot_db_path else None,
            "continue_after_baseline_mismatch": continue_after_baseline_mismatch,
            "analytical_content_baseline_check": part_a["analytical_content_baseline_check"],
            "prior_baseline_raw_file_sha_informational": PRIOR_BASELINE_RAW_FILE_SHA_INFORMATIONAL,
        },
        "pre_data_interpretations": PRE_DATA_INTERPRETATIONS,
        "part_a": part_a,
        "part_b": part_b,
        "final_verdict": final_m6_verdict(part_a, part_b),
    }


def render_markdown(payload: dict[str, Any], sha256_value: str) -> str:
    final = payload["final_verdict"]
    part_a = payload["part_a"]
    part_b = payload["part_b"]
    lines = [
        "# RED_TEAM_REPLICATION_V1",
        "",
        "## Final Verdict",
        "",
        f"- M6 verdict: `{final['verdict']}`",
        f"- Part A verdict: `{final['part_a_verdict']}`",
        f"- Part B verdict: `{final['part_b_verdict']}`",
        f"- JSON SHA256: `{sha256_value}`",
        "",
        "## Part A Comparison",
        "",
        "| Run | Status | Event N | Net 5b PF | Net 5b Median | MFE Before/After | Flip Gate |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in part_a["runs"]:
        lines.append(
            "| {run_id} | {status} | {event_count} | {pf} | {median} | {ratio} | {flip} |".format(
                run_id=row["run_id"],
                status=row["status"],
                event_count=_fmt(row.get("event_count")),
                pf=_fmt(row.get("net_5b_pf")),
                median=_fmt(row.get("net_5b_median")),
                ratio=_fmt(row.get("mfe_before_after_ratio")),
                flip=row.get("m6_flip_gate_passed"),
            )
        )
    lines.extend([
        "",
        "## Part A Notes",
        "",
        f"- Analytical baseline check: `{part_a['analytical_content_baseline_check']['match']}`",
        f"- Analytical tolerance: `{part_a['analytical_content_baseline_check']['tolerance']}`",
        f"- Prior raw baseline SHA (informational only): `{part_a['prior_baseline_raw_file_sha_informational']}`",
        f"- Observed A.1 stable SHA: `{part_a['runs'][0]['observed_stable_sha256']}`",
    ])
    for note in part_a["verdict"].get("diagnostic_notes", []):
        lines.append(f"- Diagnostic note: `{note}`")
    canon = part_b["canonical_result"]
    correlations = canon["correlations"]
    lines.extend([
        "",
        "## Part B Canonical Result",
        "",
        f"- Canonical DB path: `{part_b['manifest']['canonical_db_path']}`",
        f"- Trail rule classification: `{part_b['trail_rule_reconnaissance']['classification']}`",
        f"- Canonical verdict: `{canon['verdict']['verdict']}`",
        f"- Full Pearson: `{_fmt(correlations['full']['pearson'])}`",
        f"- SL Pearson: `{_fmt(correlations['sl']['pearson'])}`",
        f"- TP_TRAIL Pearson: `{_fmt(correlations['tp_trail']['pearson'])}`",
        f"- Count: `{canon['metrics']['count']}`",
        f"- ER: `{_fmt(canon['metrics']['expectancy_r'])}`",
        f"- PF: `{_fmt(canon['metrics']['profit_factor'])}`",
        f"- WR: `{_fmt(canon['metrics']['win_rate'])}`",
        "",
        "This is not a re-derivation of the edge; it is a reproduction check that the recorded trades behave as recorded.",
        "",
        "## Database Binding",
        "",
        f"- Bound verdict: `{part_b['database_binding']['verdict']}`",
        f"- Canonical binds: `{part_b['database_binding']['canonical_binds']}`",
        "- Snapshot results, if present, are comparison-only and never substitute for canonical results.",
        "",
    ])
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_outputs(payload: dict[str, Any], json_path: Path, sha_path: Path, report_path: Path, part_b_json_path: Path) -> str:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    sha = hashlib.sha256(json_path.read_bytes()).hexdigest().upper()
    sha_path.write_text(sha + "\n", encoding="utf-8")
    report_path.write_text(render_markdown(payload, sha), encoding="utf-8")
    trial95.write_json(payload["part_b"], part_b_json_path)
    return sha


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--snapshot-db-path", type=Path, default=trial95.DEFAULT_SNAPSHOT_DB_PATH)
    parser.add_argument("--json-path", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--sha-path", type=Path, default=DEFAULT_REPORT_SHA)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--part-b-json-path", type=Path, default=DEFAULT_PART_B_JSON)
    parser.add_argument("--no-snapshot", action="store_true")
    parser.add_argument("--continue-after-baseline-mismatch", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_payload(
        db_path=args.db_path,
        snapshot_db_path=None if args.no_snapshot else args.snapshot_db_path,
        continue_after_baseline_mismatch=args.continue_after_baseline_mismatch,
    )
    sha = write_outputs(payload, args.json_path, args.sha_path, args.report_path, args.part_b_json_path)
    print(json.dumps({
        "json_path": str(args.json_path),
        "sha256": sha,
        "report_path": str(args.report_path),
        "final_verdict": payload["final_verdict"]["verdict"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

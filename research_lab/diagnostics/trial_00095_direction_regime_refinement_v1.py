"""Research-only direction/regime refinement diagnostic for trial-00095.

This module implements TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1:

    accepted trial-00095 trades only
    frozen A1/A2/A3 amendment cohorts
    no new entries, no threshold changes, no production writes

It intentionally reuses the accepted-trade attribution primitives from
trial_00095_conditional_edge_attribution_v1.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

if __name__ == "__main__" and sys.path:
    script_dir = Path(__file__).resolve().parent
    if Path(sys.path[0]).resolve() == script_dir:
        sys.path.pop(0)
        sys.path.insert(0, str(script_dir.parents[1]))

from research_lab.diagnostics.trial_00095_conditional_edge_attribution_v1 import (  # noqa: E402
    DEPTH_THRESHOLD,
    TRIAL_ID,
    AttributedTrade,
    Candle,
    DiagnosticConfig,
    FrozenEntry,
    TradeRecord,
    attribute_trades,
    fold_bucket,
    load_aggtrade_prev_tfi,
    load_candles,
    load_frozen_entries,
    load_funding,
    load_open_interest,
    load_trade_records,
    max_drawdown,
    merge_entries,
    summarize_metrics,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRADES_PATH = PROJECT_ROOT / "research_lab" / "analysis_output" / "trial_00095_trades.json"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "research_lab" / "reports" / "trial_00095_direction_regime_refinement_v1.json"
DEFAULT_OUTPUT_SHA = PROJECT_ROOT / "research_lab" / "reports" / "trial_00095_direction_regime_refinement_v1.sha256"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "research_lab" / "reports" / "trial_00095_direction_regime_refinement_v1.md"

BASELINE_COHORT = "BASELINE_all_274"
A1_COHORT = "A1_long_only"
A2_COHORT = "A2_uptrend_only"
A3_COHORT = "A3_long_and_uptrend"
ALL_COHORTS = (BASELINE_COHORT, A1_COHORT, A2_COHORT, A3_COHORT)
FOLDS = ("fold_1_2022_2023H1", "fold_2_2023H2_2024", "fold_3_2025_2026Q1")

REFERENCE_BASELINE_ER = 2.121
REFERENCE_BASELINE_PF = 4.216
G1_MIN_A3_ER = 2.621
G2_MIN_A3_PF = 4.638


TradeLike = AttributedTrade | TradeRecord


@dataclass(frozen=True, slots=True)
class CohortSpec:
    name: str
    description: str
    predicate: Callable[[TradeLike], bool]


COHORT_SPECS = (
    CohortSpec(BASELINE_COHORT, "Full accepted trial-00095 population.", lambda trade: True),
    CohortSpec(A1_COHORT, "Accepted trades with direction == LONG.", lambda trade: trade.direction == "LONG"),
    CohortSpec(A2_COHORT, "Accepted trades with regime == uptrend.", lambda trade: trade.regime == "uptrend"),
    CohortSpec(
        A3_COHORT,
        "Accepted trades with direction == LONG and regime == uptrend.",
        lambda trade: trade.direction == "LONG" and trade.regime == "uptrend",
    ),
)


def select_cohort(trades: Iterable[TradeLike], spec: CohortSpec) -> list[TradeLike]:
    return [trade for trade in trades if spec.predicate(trade)]


def cohort_members(trades: list[TradeLike]) -> dict[str, list[TradeLike]]:
    return {spec.name: select_cohort(trades, spec) for spec in COHORT_SPECS}


def fold_label(trade: TradeLike) -> str:
    return getattr(trade, "fold", None) or fold_bucket(trade.opened_at)


def trades_for_fold(trades: Iterable[TradeLike], fold: str) -> list[TradeLike]:
    return [trade for trade in trades if fold_label(trade) == fold]


def metric_row(trades: list[TradeLike]) -> dict[str, Any]:
    return summarize_metrics(trades)  # type: ignore[arg-type]


def delta_metrics(cohort: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    baseline_count = int(baseline["count"])
    cohort_count = int(cohort["count"])
    return {
        "count_removed": baseline_count - cohort_count,
        "count_retained": cohort_count,
        "er_delta": cohort["expectancy_r"] - baseline["expectancy_r"],
        "max_drawdown_r_delta": cohort["max_drawdown_r"] - baseline["max_drawdown_r"],
        "pf_delta": cohort["profit_factor"] - baseline["profit_factor"],
        "retained_share": cohort_count / baseline_count if baseline_count else 0.0,
        "total_r_delta": cohort["total_r"] - baseline["total_r"],
        "wr_delta": cohort["win_rate"] - baseline["win_rate"],
    }


def build_full_sample_table(members: dict[str, list[TradeLike]]) -> dict[str, dict[str, Any]]:
    baseline = metric_row(members[BASELINE_COHORT])
    rows: dict[str, dict[str, Any]] = {}
    for cohort in ALL_COHORTS:
        metrics = metric_row(members[cohort])
        row = {"cohort": cohort, **metrics}
        if cohort != BASELINE_COHORT:
            row["delta_vs_baseline"] = delta_metrics(metrics, baseline)
        rows[cohort] = row
    return rows


def build_fold_table(members: dict[str, list[TradeLike]]) -> dict[str, dict[str, dict[str, Any]]]:
    table: dict[str, dict[str, dict[str, Any]]] = {}
    for fold in FOLDS:
        baseline_metrics = metric_row(trades_for_fold(members[BASELINE_COHORT], fold))
        table[fold] = {}
        for cohort in ALL_COHORTS:
            metrics = metric_row(trades_for_fold(members[cohort], fold))
            row = {"cohort": cohort, "fold": fold, **metrics}
            if cohort != BASELINE_COHORT:
                row["delta_vs_baseline"] = delta_metrics(metrics, baseline_metrics)
            table[fold][cohort] = row
    return table


def gate_result(rule: str, measurement: str, value: Any, threshold: str, status: str) -> dict[str, Any]:
    return {
        "measurement": measurement,
        "rule": rule,
        "status": status,
        "threshold": threshold,
        "value": value,
    }


def evaluate_gates(
    full_sample: dict[str, dict[str, Any]],
    fold_table: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    a3 = full_sample[A3_COHORT]
    a3_er = a3["expectancy_r"]
    a3_pf = a3["profit_factor"]
    a3_fold_rows = [fold_table[fold][A3_COHORT] for fold in FOLDS]
    missing_folds = [row["fold"] for row in a3_fold_rows if row["count"] <= 0]
    min_allowed_fold_er = a3_er * 0.5
    fold_er_values = {row["fold"]: row["expectancy_r"] for row in a3_fold_rows}

    rules = [
        gate_result("G-1", "A3 full-sample ER vs baseline ER", a3_er, ">= 2.621", "PASS" if a3_er >= G1_MIN_A3_ER else "FAIL"),
        gate_result("G-2", "A3 full-sample PF vs baseline PF", a3_pf, ">= 4.638", "PASS" if a3_pf >= G2_MIN_A3_PF else "FAIL"),
        gate_result(
            "G-3",
            "A3 per-fold sign stability",
            fold_er_values,
            "A3 ER > 0 in all 3 folds",
            "PASS" if not missing_folds and all(row["expectancy_r"] > 0 for row in a3_fold_rows) else "FAIL",
        ),
        gate_result(
            "G-4",
            "A3 per-fold consistency",
            {"fold_er": fold_er_values, "minimum_allowed_fold_er": min_allowed_fold_er},
            "No per-fold A3 ER more than 50% below A3 full-sample ER",
            "PASS" if not missing_folds and all(row["expectancy_r"] >= min_allowed_fold_er for row in a3_fold_rows) else "FAIL",
        ),
        gate_result("G-5", "A3 max drawdown R", a3["max_drawdown_r"], "reported, informational only", "INFO"),
    ]

    if missing_folds:
        final_verdict = "INCONCLUSIVE_DATA_GAP"
        data_quality_status = "MISSING_A3_FOLD"
    elif any(rule["status"] == "FAIL" for rule in rules if rule["rule"] in {"G-1", "G-2", "G-3", "G-4"}):
        final_verdict = "HYPOTHESIS_INVALIDATED"
        data_quality_status = "OK"
    else:
        final_verdict = "HYPOTHESIS_PASSED_REQUIRES_CLAUDE_AUDIT"
        data_quality_status = "OK"

    sign_stability = sum(1 for fold in FOLDS if fold_table[fold][A3_COHORT]["expectancy_r"] > fold_table[fold][BASELINE_COHORT]["expectancy_r"]) / len(FOLDS)

    return {
        "data_quality_status": data_quality_status,
        "final_verdict": final_verdict,
        "missing_a3_folds": missing_folds,
        "rules": rules,
        "sign_stability_vs_baseline_fraction": sign_stability,
    }


def build_payload(trades_path: Path = DEFAULT_TRADES_PATH) -> dict[str, Any]:
    trades = load_trade_records(trades_path)
    members = cohort_members(trades)
    full_sample = build_full_sample_table(members)
    fold_table = build_fold_table(members)
    gates = evaluate_gates(full_sample, fold_table)
    if len(trades) != 274:
        gates = {
            **gates,
            "data_quality_status": "UNEXPECTED_ACCEPTED_POPULATION_COUNT",
            "final_verdict": "INCONCLUSIVE_DATA_GAP",
            "unexpected_accepted_population_count": len(trades),
        }
    return {
        "accepted_population": {
            "count": len(trades),
            "expected_count": 274,
            "source": str(trades_path),
        },
        "cohort_definitions": {
            BASELINE_COHORT: "all accepted trial-00095 trades",
            A1_COHORT: "trade.direction == 'LONG'",
            A2_COHORT: "trade.regime == 'uptrend'",
            A3_COHORT: "trade.direction == 'LONG' and trade.regime == 'uptrend'",
        },
        "depth_threshold": DEPTH_THRESHOLD,
        "diagnostic": "TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1",
        "falsification_gates": gates,
        "folds": list(FOLDS),
        "full_sample": full_sample,
        "manifest": {
            "deterministic_generation": True,
            "generated_at_utc": "DETERMINISTIC_NO_WALL_CLOCK",
            "no_new_entries": True,
            "no_production_changes": True,
            "no_threshold_changes": True,
            "reused_primitives": [
                "DEPTH_THRESHOLD",
                "TRIAL_ID",
                "AttributedTrade",
                "Candle",
                "DiagnosticConfig",
                "FrozenEntry",
                "TradeRecord",
                "attribute_trades",
                "fold_bucket",
                "load_aggtrade_prev_tfi",
                "load_candles",
                "load_frozen_entries",
                "load_funding",
                "load_open_interest",
                "load_trade_records",
                "max_drawdown",
                "merge_entries",
                "summarize_metrics",
            ],
            "research_only": True,
            "trial_id": TRIAL_ID,
        },
        "per_fold": fold_table,
        "reference_baseline": {
            "expectancy_r": REFERENCE_BASELINE_ER,
            "profit_factor": REFERENCE_BASELINE_PF,
            "source": "TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1",
        },
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def metrics_table(rows: Iterable[dict[str, Any]]) -> list[str]:
    lines = [
        "| Cohort | N | ER | PF | WR | Median R | Total R | Max DD R | Count Removed | Retained |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        delta = row.get("delta_vs_baseline", {})
        lines.append(
            f"| `{row['cohort']}` | {row['count']} | {fmt(row['expectancy_r'])} | {fmt(row['profit_factor'])} | "
            f"{row['win_rate']:.2%} | {fmt(row['median_r'])} | {fmt(row['total_r'])} | {fmt(row['max_drawdown_r'])} | "
            f"{delta.get('count_removed', 0)} | {delta.get('retained_share', 1.0):.2%} |"
        )
    return lines


def fold_table_lines(per_fold: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    lines = [
        "| Fold | Cohort | N | ER | PF | WR | Median R | Total R | Max DD R | ER Delta | Count Removed |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for fold in FOLDS:
        for cohort in ALL_COHORTS:
            row = per_fold[fold][cohort]
            delta = row.get("delta_vs_baseline", {})
            lines.append(
                f"| `{fold}` | `{cohort}` | {row['count']} | {fmt(row['expectancy_r'])} | {fmt(row['profit_factor'])} | "
                f"{row['win_rate']:.2%} | {fmt(row['median_r'])} | {fmt(row['total_r'])} | {fmt(row['max_drawdown_r'])} | "
                f"{fmt(delta.get('er_delta', 0.0))} | {delta.get('count_removed', 0)} |"
            )
    return lines


def render_report(payload: dict[str, Any], sha256_value: str) -> str:
    gates = payload["falsification_gates"]
    lines = [
        "# TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1",
        "",
        "**Status:** READY_FOR_CLAUDE_AUDIT",
        "**Type:** Research-only accepted-trade refinement diagnostic",
        f"**Final verdict:** `{gates['final_verdict']}`",
        "",
        "## Scope",
        "",
        "Accepted trial-00095 trades only. No new entries, no threshold changes, no production changes.",
        "",
        "## Data",
        "",
        f"- Trade source: `{payload['accepted_population']['source']}`",
        f"- Accepted population count: {payload['accepted_population']['count']}",
        f"- Expected accepted population count: {payload['accepted_population']['expected_count']}",
        f"- Depth threshold preserved: {payload['depth_threshold']}",
        "",
        "## Full-Sample Metrics",
        "",
    ]
    lines.extend(metrics_table(payload["full_sample"][cohort] for cohort in ALL_COHORTS))
    lines.extend(["", "## Per-Fold Metrics", ""])
    lines.extend(fold_table_lines(payload["per_fold"]))
    lines.extend(["", "## Falsification Gates", ""])
    lines.extend([
        "| Gate | Measurement | Value | Threshold | Status |",
        "|---|---|---:|---|---|",
    ])
    for rule in gates["rules"]:
        lines.append(
            f"| {rule['rule']} | {rule['measurement']} | {fmt(rule['value'])} | {rule['threshold']} | {rule['status']} |"
        )
    lines.extend(
        [
            "",
            "## Stability",
            "",
            f"- A3 sign stability versus baseline folds: {gates['sign_stability_vs_baseline_fraction']:.2%}",
            f"- Missing A3 folds: {gates['missing_a3_folds']}",
            f"- Data quality status: `{gates['data_quality_status']}`",
            "",
            "## Methodology Notes",
            "",
            "- A1/A2/A3 are the only amendment cohorts.",
            "- A3 is the only hard-gated combined refinement.",
            "- A1 or A2 cannot replace A3 after results.",
            "- TFI alignment, exit timing, and near-miss reconstruction are out of scope.",
            "- Verdict is computed mechanically from G-1 through G-4 and data-gap checks.",
            "",
            "## Artifacts",
            "",
            f"- JSON SHA256: `{sha256_value}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(payload: dict[str, Any], output_json: Path, output_sha: Path, report_path: Path) -> str:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False)
    output_json.write_text(json_text + "\n", encoding="utf-8")
    sha = hashlib.sha256(output_json.read_bytes()).hexdigest().upper()
    output_sha.write_text(f"{sha}  {output_json.name}\n", encoding="utf-8")
    report_path.write_text(render_report(payload, sha), encoding="utf-8")
    return sha


def run_diagnostic(
    *,
    trades_path: Path = DEFAULT_TRADES_PATH,
    output_json: Path = DEFAULT_OUTPUT_JSON,
    output_sha: Path = DEFAULT_OUTPUT_SHA,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    payload = build_payload(trades_path=trades_path)
    sha = write_artifacts(payload, output_json, output_sha, report_path)
    return {**payload, "artifact_sha256": sha}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades-path", type=Path, default=DEFAULT_TRADES_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-sha", type=Path, default=DEFAULT_OUTPUT_SHA)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_diagnostic(
        trades_path=args.trades_path,
        output_json=args.output_json,
        output_sha=args.output_sha,
        report_path=args.report_path,
    )
    print(
        json.dumps(
            {
                "a3_count": payload["full_sample"][A3_COHORT]["count"],
                "final_verdict": payload["falsification_gates"]["final_verdict"],
                "output_json": str(args.output_json),
                "output_sha": str(args.output_sha),
                "report_path": str(args.report_path),
                "sha256": payload["artifact_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

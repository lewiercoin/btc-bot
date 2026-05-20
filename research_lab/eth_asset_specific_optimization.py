#!/usr/bin/env python3
"""ETH asset-specific coarse optimization around frozen trial-00095.

Research Lab only. This milestone asks whether ETH improves with a small,
predeclared parameter grid versus the frozen BTC trial-00095 transfer baseline.
It does not change runtime settings, sidecar behavior, PAPER, LIVE, or M4.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import sqlite3
import statistics
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig, BacktestRunner
from backtest.performance import PerformanceReport
from research_lab.eth_trial_00095_transfer_feasibility import (
    DEFAULT_ETH_DB,
    DEFAULT_STORE,
    END,
    START,
    SYMBOL,
    TRIAL_00095_ID,
    _derive_1h_candles,
    _ensure_runtime_tables,
    fold_windows,
    load_trial_params,
    resolve_trial_store_path,
)
from research_lab.settings_adapter import build_candidate_settings
from settings import AppSettings, load_settings


DEFAULT_REPORT = Path("docs/analysis/ETH_ASSET_SPECIFIC_OPTIMIZATION_2026-05-20.md")
DEFAULT_CACHE = Path("research_lab/snapshots/eth_asset_specific_optimization_v1_cache.json")
TRAIN_START = "2022-01-01"
TRAIN_END = "2025-01-01"
OOS_START = "2025-01-01"
OOS_END = END


@dataclass(frozen=True, slots=True)
class EthOptVariant:
    variant_id: str
    overrides: dict[str, float]


@dataclass(frozen=True, slots=True)
class EthOptGates:
    train_min_trades: int = 250
    train_min_er: float = 1.5
    train_min_pf: float = 2.0
    train_max_dd: float = 0.15
    oos_min_trades: int = 80
    oos_min_er: float = 1.5
    oos_min_pf: float = 2.0
    oos_max_dd: float = 0.12
    min_oos_er_improvement_pct: float = 0.05
    min_oos_pf_improvement_pct: float = 0.0
    min_positive_wf_folds: int = 4
    min_2x_cost_oos_er: float = 1.0


@dataclass(frozen=True, slots=True)
class VariantEvaluation:
    variant: EthOptVariant
    train: dict[str, Any]
    oos: dict[str, Any]
    train_pass: bool
    train_score: float


def build_predeclared_grid() -> tuple[EthOptVariant, ...]:
    """Return the fixed ETH coarse grid.

    The grid deliberately changes only the high-leverage sweep-depth threshold.
    Other trial-00095 parameters remain frozen for this first ETH pass.
    """

    variants: list[EthOptVariant] = []
    for min_depth in (0.0055, 0.00649, 0.0075):
        suffix = f"D{min_depth:.5f}"
        variants.append(
            EthOptVariant(
                variant_id=f"ETH_OPT_{suffix}",
                overrides={
                    "min_sweep_depth_pct": min_depth,
                },
            )
        )
    return tuple(variants)


def baseline_variant(trial_params: dict[str, Any]) -> EthOptVariant:
    return EthOptVariant(
        variant_id="ETH_BASELINE_FROZEN_TRIAL_00095",
        overrides={
            "min_sweep_depth_pct": float(trial_params["min_sweep_depth_pct"]),
            "confluence_min": float(trial_params["confluence_min"]),
            "direction_tfi_threshold": float(trial_params["direction_tfi_threshold"]),
        },
    )


def build_eth_settings(
    base_settings: AppSettings,
    trial_params: dict[str, Any],
    overrides: dict[str, float],
) -> AppSettings:
    merged = {**trial_params, **overrides}
    candidate = build_candidate_settings(base_settings, merged)
    strategy = dataclasses.replace(candidate.strategy, symbol=SYMBOL)
    return dataclasses.replace(candidate, strategy=strategy)


def prepare_replay_db(source_db: Path, target_db: Path) -> None:
    shutil.copy2(str(source_db), str(target_db))
    conn = sqlite3.connect(str(target_db))
    try:
        _ensure_runtime_tables(conn)
        _derive_1h_candles(conn, symbol=SYMBOL)
        conn.commit()
    finally:
        conn.close()


def reset_replay_artifact_tables(conn: sqlite3.Connection) -> None:
    """Clear mutable replay artifact tables inside a temporary DB."""

    _ensure_runtime_tables(conn)
    conn.execute("DELETE FROM signal_candidates")
    conn.execute("DELETE FROM executable_signals")
    conn.execute("DELETE FROM positions")
    conn.execute("DELETE FROM trade_log")
    conn.commit()


def run_variant_replay_on_db(
    *,
    replay_db: Path,
    settings: AppSettings,
    start: str,
    end: str,
    fee_multiplier: float = 1.0,
) -> tuple[PerformanceReport, list[Any]]:
    conn = sqlite3.connect(str(replay_db))
    conn.row_factory = sqlite3.Row
    try:
        reset_replay_artifact_tables(conn)
        runner = BacktestRunner(conn, settings=settings)
        result = runner.run(
            BacktestConfig(
                start_date=start,
                end_date=end,
                symbol=SYMBOL,
                initial_equity=10_000.0,
                fee_rate_maker=0.0004 * fee_multiplier,
                fee_rate_taker=0.0004 * fee_multiplier,
            )
        )
        return result.performance, result.trades
    finally:
        conn.close()


def run_variant_replay(
    *,
    source_db: Path,
    settings: AppSettings,
    start: str,
    end: str,
    fee_multiplier: float = 1.0,
) -> tuple[PerformanceReport, list[Any]]:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        prepare_replay_db(source_db, tmp_path)
        return run_variant_replay_on_db(
            replay_db=tmp_path,
            settings=settings,
            start=start,
            end=end,
            fee_multiplier=fee_multiplier,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
        tmp_path.with_name(tmp_path.name + "-wal").unlink(missing_ok=True)
        tmp_path.with_name(tmp_path.name + "-shm").unlink(missing_ok=True)


def _perf_dict(report: PerformanceReport) -> dict[str, Any]:
    return asdict(report)


def train_passes(metrics: dict[str, Any], gates: EthOptGates) -> bool:
    return (
        metrics["trades_count"] >= gates.train_min_trades
        and metrics["expectancy_r"] >= gates.train_min_er
        and metrics["profit_factor"] >= gates.train_min_pf
        and metrics["max_drawdown_pct"] <= gates.train_max_dd
    )


def train_score(metrics: dict[str, Any]) -> float:
    trade_quality = min(float(metrics["trades_count"]) / 300.0, 1.0)
    return float(metrics["expectancy_r"]) * trade_quality - float(metrics["max_drawdown_pct"]) * 5.0


def pct_delta(value: float, reference: float) -> float:
    if abs(reference) < 1e-12:
        return 0.0
    return (value - reference) / reference


def evaluate_oos_gates(
    *,
    selected_oos: dict[str, Any],
    baseline_oos: dict[str, Any],
    selected_cost_2x_oos: dict[str, Any],
    wf_folds: list[dict[str, Any]],
    gates: EthOptGates,
) -> dict[str, dict[str, Any]]:
    positive_folds = sum(1 for fold in wf_folds if fold["expectancy_r"] > 1.0 and fold["trades_count"] >= 20)
    er_improvement = pct_delta(float(selected_oos["expectancy_r"]), float(baseline_oos["expectancy_r"]))
    pf_improvement = pct_delta(float(selected_oos["profit_factor"]), float(baseline_oos["profit_factor"]))
    return {
        "oos_min_trades": {
            "value": selected_oos["trades_count"],
            "threshold": gates.oos_min_trades,
            "pass": selected_oos["trades_count"] >= gates.oos_min_trades,
        },
        "oos_min_er": {
            "value": selected_oos["expectancy_r"],
            "threshold": gates.oos_min_er,
            "pass": selected_oos["expectancy_r"] >= gates.oos_min_er,
        },
        "oos_min_pf": {
            "value": selected_oos["profit_factor"],
            "threshold": gates.oos_min_pf,
            "pass": selected_oos["profit_factor"] >= gates.oos_min_pf,
        },
        "oos_max_dd": {
            "value": selected_oos["max_drawdown_pct"],
            "threshold": gates.oos_max_dd,
            "pass": selected_oos["max_drawdown_pct"] <= gates.oos_max_dd,
        },
        "oos_er_improvement_vs_baseline": {
            "value": er_improvement,
            "threshold": gates.min_oos_er_improvement_pct,
            "pass": er_improvement >= gates.min_oos_er_improvement_pct,
        },
        "oos_pf_improvement_vs_baseline": {
            "value": pf_improvement,
            "threshold": gates.min_oos_pf_improvement_pct,
            "pass": pf_improvement >= gates.min_oos_pf_improvement_pct,
        },
        "wf_positive_folds": {
            "value": positive_folds,
            "threshold": gates.min_positive_wf_folds,
            "pass": positive_folds >= gates.min_positive_wf_folds,
        },
        "cost_2x_oos_er": {
            "value": selected_cost_2x_oos["expectancy_r"],
            "threshold": gates.min_2x_cost_oos_er,
            "pass": selected_cost_2x_oos["expectancy_r"] >= gates.min_2x_cost_oos_er,
        },
    }


def builder_verdict(gates: dict[str, dict[str, Any]], *, selected_variant_id: str | None) -> str:
    if selected_variant_id is None:
        return "ETH_OPTIMIZATION_FAILED_NO_TRAIN_CANDIDATE"
    if all(item["pass"] for item in gates.values()):
        return "ETH_ASSET_SPECIFIC_CANDIDATE_FOR_AUDIT"
    return "ETH_OPTIMIZATION_NO_PROMOTION"


def evaluate_variant(
    *,
    source_db: Path,
    base_settings: AppSettings,
    trial_params: dict[str, Any],
    variant: EthOptVariant,
    gates: EthOptGates,
    replay_db: Path | None = None,
) -> VariantEvaluation:
    settings = build_eth_settings(base_settings, trial_params, variant.overrides)
    runner = run_variant_replay_on_db if replay_db is not None else run_variant_replay
    kwargs: dict[str, Any] = {"replay_db": replay_db} if replay_db is not None else {"source_db": source_db}
    train_perf, _ = runner(**kwargs, settings=settings, start=TRAIN_START, end=TRAIN_END)
    oos_perf, _ = runner(**kwargs, settings=settings, start=OOS_START, end=OOS_END)
    train = _perf_dict(train_perf)
    oos = _perf_dict(oos_perf)
    passed = train_passes(train, gates)
    return VariantEvaluation(
        variant=variant,
        train=train,
        oos=oos,
        train_pass=passed,
        train_score=train_score(train) if passed else float("-inf"),
    )


def fold_metrics(
    *,
    source_db: Path | None = None,
    replay_db: Path | None = None,
    settings: AppSettings,
) -> list[dict[str, Any]]:
    folds: list[dict[str, Any]] = []
    runner = run_variant_replay_on_db if replay_db is not None else run_variant_replay
    kwargs: dict[str, Any] = {"replay_db": replay_db} if replay_db is not None else {"source_db": source_db}
    for label, start, end in fold_windows():
        perf, _ = runner(**kwargs, settings=settings, start=start, end=end)
        payload = _perf_dict(perf)
        payload.update({"label": label, "start": start, "end": end})
        folds.append(payload)
    return folds


def run_analysis(
    *,
    source_db: Path,
    store_path: Path,
    report_path: Path,
    cache_path: Path = DEFAULT_CACHE,
) -> dict[str, Any]:
    resolved_store = resolve_trial_store_path(store_path, trial_id=TRIAL_00095_ID)
    trial_params = load_trial_params(resolved_store, trial_id=TRIAL_00095_ID)
    base_settings = load_settings(profile="research")
    gates = EthOptGates()
    baseline = baseline_variant(trial_params)
    cache = load_cache(cache_path)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        replay_db = Path(tmp.name)
    try:
        prepare_replay_db(source_db, replay_db)
        baseline_settings = build_eth_settings(base_settings, trial_params, baseline.overrides)
        if "baseline_train" in cache and "baseline_oos" in cache:
            baseline_train = cache["baseline_train"]
            baseline_oos = cache["baseline_oos"]
        else:
            baseline_train_perf, _ = run_variant_replay_on_db(
                replay_db=replay_db,
                settings=baseline_settings,
                start=TRAIN_START,
                end=TRAIN_END,
            )
            baseline_oos_perf, _ = run_variant_replay_on_db(
                replay_db=replay_db,
                settings=baseline_settings,
                start=OOS_START,
                end=OOS_END,
            )
            baseline_train = _perf_dict(baseline_train_perf)
            baseline_oos = _perf_dict(baseline_oos_perf)
            cache["baseline_train"] = baseline_train
            cache["baseline_oos"] = baseline_oos
            save_cache(cache_path, cache)

        evaluations: list[VariantEvaluation] = []
        cache.setdefault("variants", {})
        variants_cache: dict[str, Any] = cache["variants"]
        grid = build_predeclared_grid()
        for index, variant in enumerate(grid, start=1):
            cached = variants_cache.get(variant.variant_id)
            if cached is not None:
                evaluations.append(_evaluation_from_cache(cached))
                print(f"[cache] {index}/{len(grid)} {variant.variant_id}", flush=True)
                continue
            print(f"[run] {index}/{len(grid)} {variant.variant_id}", flush=True)
            evaluation = evaluate_variant(
                source_db=source_db,
                replay_db=replay_db,
                base_settings=base_settings,
                trial_params=trial_params,
                variant=variant,
                gates=gates,
            )
            variants_cache[variant.variant_id] = _evaluation_to_cache(evaluation)
            save_cache(cache_path, cache)
            evaluations.append(evaluation)

        train_candidates = [item for item in evaluations if item.train_pass]
        selected = max(train_candidates, key=lambda item: (item.train_score, item.train["trades_count"], item.variant.variant_id), default=None)

        selected_cost_2x_oos: dict[str, Any] = {}
        wf: list[dict[str, Any]] = []
        gate_results: dict[str, dict[str, Any]] = {}
        if selected is not None:
            selected_settings = build_eth_settings(base_settings, trial_params, selected.variant.overrides)
            selected_cache = cache.setdefault("selected_diagnostics", {}).setdefault(selected.variant.variant_id, {})
            if "cost_2x_oos" in selected_cache and "wf_folds" in selected_cache:
                selected_cost_2x_oos = selected_cache["cost_2x_oos"]
                wf = selected_cache["wf_folds"]
            else:
                cost_2x_perf, _ = run_variant_replay_on_db(
                    replay_db=replay_db,
                    settings=selected_settings,
                    start=OOS_START,
                    end=OOS_END,
                    fee_multiplier=2.0,
                )
                selected_cost_2x_oos = _perf_dict(cost_2x_perf)
                wf = fold_metrics(replay_db=replay_db, settings=selected_settings)
                selected_cache["cost_2x_oos"] = selected_cost_2x_oos
                selected_cache["wf_folds"] = wf
                save_cache(cache_path, cache)
            gate_results = evaluate_oos_gates(
                selected_oos=selected.oos,
                baseline_oos=baseline_oos,
                selected_cost_2x_oos=selected_cost_2x_oos,
                wf_folds=wf,
                gates=gates,
            )
    finally:
        replay_db.unlink(missing_ok=True)
        replay_db.with_name(replay_db.name + "-wal").unlink(missing_ok=True)
        replay_db.with_name(replay_db.name + "-shm").unlink(missing_ok=True)

    payload: dict[str, Any] = {
        "milestone": "ETH_ASSET_SPECIFIC_OPTIMIZATION_V1",
        "builder_verdict": builder_verdict(gate_results, selected_variant_id=selected.variant.variant_id if selected else None),
        "source_db": str(source_db),
        "store_path": str(resolved_store),
        "trial_id": TRIAL_00095_ID,
        "symbol": SYMBOL,
        "train_window": {"start": TRAIN_START, "end": TRAIN_END},
        "oos_window": {"start": OOS_START, "end": OOS_END},
        "grid_size": len(evaluations),
        "gate_contract": asdict(gates),
        "baseline": {
            "variant": asdict(baseline),
            "train": baseline_train,
            "oos": baseline_oos,
        },
        "selected": {
            "variant": asdict(selected.variant),
            "train": selected.train,
            "oos": selected.oos,
            "train_score": selected.train_score,
            "cost_2x_oos": selected_cost_2x_oos,
            "wf_folds": wf,
        }
        if selected
        else None,
        "gates": gate_results,
        "variants": [
            {
                "variant": asdict(item.variant),
                "train": item.train,
                "oos": item.oos,
                "train_pass": item.train_pass,
                "train_score": item.train_score,
            }
            for item in evaluations
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    generate_report(payload, report_path)
    return payload


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    lines = [
        "# ETH Asset-Specific Optimization V1",
        "",
        "**Milestone:** `ETH_ASSET_SPECIFIC_OPTIMIZATION_V1`",
        f"**Status:** `{payload['builder_verdict']}`",
        "**Scope:** Research Lab offline optimization only. No runtime, PAPER, LIVE, sidecar, M4, core, execution, orchestrator, settings, or production DB changes.",
        "",
        "## Methodology",
        "",
        "- Baseline: frozen BTC `trial-00095` transferred to ETH.",
        "- Search: fixed depth-only coarse grid over `min_sweep_depth_pct`; all other trial-00095 parameters remain frozen.",
        "- Selection: train window only (`2022-01-01` to `2025-01-01`).",
        "- Evaluation: untouched OOS window (`2025-01-01` to `2026-03-28`).",
        "- Full-year walk-forward and 2x cost stress are diagnostics/gates for the selected train champion only.",
        "- No post-hoc threshold rescue: if train champion fails OOS gates, verdict remains no promotion.",
        "",
        "## Baseline OOS",
        "",
        _metrics_line(payload["baseline"]["oos"]),
        "",
    ]
    selected = payload["selected"]
    if selected is None:
        lines.extend(["## Selected Variant", "", "No train-window candidate passed the predeclared train gates.", ""])
    else:
        lines.extend(
            [
                "## Selected Train Champion",
                "",
                f"- Variant: `{selected['variant']['variant_id']}`",
                f"- Overrides: `{json.dumps(selected['variant']['overrides'], sort_keys=True)}`",
                f"- Train score: `{selected['train_score']:.4f}`",
                "",
                "### Train Metrics",
                "",
                _metrics_line(selected["train"]),
                "",
                "### OOS Metrics",
                "",
                _metrics_line(selected["oos"]),
                "",
                "### 2x Cost OOS Metrics",
                "",
                _metrics_line(selected["cost_2x_oos"]),
                "",
                "## Gates",
                "",
                "| Gate | Value | Threshold | Result |",
                "|---|---:|---:|---|",
            ]
        )
        for name, item in payload["gates"].items():
            lines.append(f"| {name} | {item['value']:.4g} | {item['threshold']:.4g} | {'PASS' if item['pass'] else 'FAIL'} |")
        lines.extend(
            [
                "",
                "## Walk-Forward Folds For Selected Variant",
                "",
                "| Fold | Window | Trades | ER | PF | Win Rate | Max DD |",
                "|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        for fold in selected["wf_folds"]:
            lines.append(
                f"| {fold['label']} | {fold['start']} to {fold['end']} | {fold['trades_count']} | "
                f"{fold['expectancy_r']:.3f} | {fold['profit_factor']:.2f} | "
                f"{fold['win_rate']:.1%} | {fold['max_drawdown_pct']:.2%} |"
            )

    lines.extend(
        [
            "",
            "## Grid Summary",
            "",
            f"- Variants evaluated: {payload['grid_size']}",
            f"- Train-pass variants: {sum(1 for item in payload['variants'] if item['train_pass'])}",
            "",
            "| Variant | Train Pass | Train ER | Train PF | Train DD | OOS Trades | OOS ER | OOS PF | OOS DD |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in sorted(payload["variants"], key=lambda value: value["train_score"], reverse=True):
        lines.append(
            f"| `{item['variant']['variant_id']}` | {'YES' if item['train_pass'] else 'NO'} | "
            f"{item['train']['expectancy_r']:.3f} | {item['train']['profit_factor']:.2f} | "
            f"{item['train']['max_drawdown_pct']:.2%} | {item['oos']['trades_count']} | "
            f"{item['oos']['expectancy_r']:.3f} | {item['oos']['profit_factor']:.2f} | "
            f"{item['oos']['max_drawdown_pct']:.2%} |"
        )

    lines.extend(
        [
            "",
            "## Audit Questions",
            "",
            "1. Did the milestone remain research-only with no runtime/sidecar/M4 changes?",
            "2. Was the grid fixed before results and limited to coarse ETH asset-specific variants?",
            "3. Was the selected variant chosen from train metrics only?",
            "4. Were OOS and cost/WF gates applied without post-hoc rescue?",
            "5. Is any candidate recommendation supported by OOS improvement over frozen ETH transfer baseline?",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    report_path.write_text(text, encoding="utf-8")
    return text


def load_cache(cache_path: Path) -> dict[str, Any]:
    if not cache_path.exists():
        return {}
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid ETH optimization cache payload: {cache_path}")
    return payload


def save_cache(cache_path: Path, payload: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _evaluation_to_cache(evaluation: VariantEvaluation) -> dict[str, Any]:
    return {
        "variant": asdict(evaluation.variant),
        "train": evaluation.train,
        "oos": evaluation.oos,
        "train_pass": evaluation.train_pass,
        "train_score": evaluation.train_score,
    }


def _evaluation_from_cache(payload: dict[str, Any]) -> VariantEvaluation:
    return VariantEvaluation(
        variant=EthOptVariant(
            variant_id=payload["variant"]["variant_id"],
            overrides={key: float(value) for key, value in payload["variant"]["overrides"].items()},
        ),
        train=payload["train"],
        oos=payload["oos"],
        train_pass=bool(payload["train_pass"]),
        train_score=float(payload["train_score"]),
    )


def _metrics_line(metrics: dict[str, Any]) -> str:
    return (
        f"Trades `{metrics['trades_count']}`, ER `{metrics['expectancy_r']:.3f}`, "
        f"PF `{metrics['profit_factor']:.2f}`, WR `{metrics['win_rate']:.1%}`, "
        f"max DD `{metrics['max_drawdown_pct']:.2%}`"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, default=DEFAULT_ETH_DB)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_analysis(source_db=args.source_db, store_path=args.store, report_path=args.report, cache_path=args.cache)
    print(
        json.dumps(
            {
                "verdict": payload["builder_verdict"],
                "selected": payload["selected"]["variant"]["variant_id"] if payload["selected"] else None,
                "report": str(args.report),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

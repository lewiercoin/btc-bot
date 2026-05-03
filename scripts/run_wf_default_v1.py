#!/usr/bin/env python3
"""
WALKFORWARD-DEFAULT-V1 runner.

Phase 1: Hard-filter 32 PASSED trials from optuna-default-v1-run2.
Phase 2: Param inspection for flagged candidates (00052, 00135).
Phase 3: Walk-forward run on filtered pool using default_protocol.json.

Usage (on server):
  python3 run_wf_default_v1.py --inspect-only       # Phase 1+2 only (fast)
  python3 run_wf_default_v1.py --run-wf              # All phases
  python3 run_wf_default_v1.py --run-wf --trial-ids 00000,00097  # Specific trials
"""

import argparse
import json
import math
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path("/home/btc-bot/btc-bot")
sys.path.insert(0, str(PROJECT_ROOT))

STORE_PATH = PROJECT_ROOT / "research_lab" / "research_lab.db"
PROTOCOL_PATH = PROJECT_ROOT / "research_lab" / "configs" / "default_protocol.json"
SNAPSHOTS_DIR = PROJECT_ROOT / "research_lab" / "snapshots"
STUDY_PREFIX = "optuna-default-v1-run2"
START_DATE = "2022-01-01"
END_DATE = "2026-03-28"

HARD_FILTER_MAX_PF = 50.0
HARD_FILTER_MAX_WR = 0.85
HARD_FILTER_MIN_ER = 0.0

PRIORITY_ORDER = [
    "00000", "00097", "00099", "00104", "00123",
    "00052", "00135", "00098",
]

PARAM_INSPECT = {
    "00052": ("confluence_min", 0.5, "lt"),
    "00135": ("invalidation_offset_atr", 4.0, "gt"),
}

from backtest.backtest_runner import BacktestConfig
from settings import load_settings
from research_lab.db_snapshot import (
    create_trial_snapshot,
    open_snapshot_connection,
    verify_required_tables,
)
from research_lab.objective import evaluate_candidate
from research_lab.protocol import hash_protocol
from research_lab.settings_adapter import build_candidate_settings
from research_lab.types import TrialEvaluation, WalkForwardReport, WalkForwardWindow
from research_lab.walkforward import build_windows


def _load_filtered_trials(store_path: Path) -> tuple[list[dict], list[dict]]:
    conn = sqlite3.connect(store_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT trial_id, params_json, metrics_json FROM trials "
        "WHERE trial_id LIKE ? AND rejected_reason IS NULL "
        "ORDER BY trial_id",
        (f"{STUDY_PREFIX}%",),
    ).fetchall()
    conn.close()

    passed: list[dict] = []
    rejected: list[dict] = []
    for row in rows:
        trial_id = str(row["trial_id"])
        params: dict[str, Any] = json.loads(str(row["params_json"]))
        metrics: dict[str, Any] = json.loads(str(row["metrics_json"]))
        er = float(metrics.get("expectancy_r", 0))
        pf = float(metrics.get("profit_factor", 0))
        wr = float(metrics.get("win_rate", 0))

        reject_reasons: list[str] = []
        if er < HARD_FILTER_MIN_ER:
            reject_reasons.append(f"er={er:.4f} < min_er={HARD_FILTER_MIN_ER}")
        if pf > HARD_FILTER_MAX_PF:
            reject_reasons.append(f"pf={pf:.3f} > max_pf={HARD_FILTER_MAX_PF}")
        if wr > HARD_FILTER_MAX_WR:
            reject_reasons.append(f"wr={wr:.4f} > max_wr={HARD_FILTER_MAX_WR}")

        trial_num = trial_id.split("-trial-")[-1]
        record: dict[str, Any] = {
            "trial_id": trial_id,
            "trial_num": trial_num,
            "params": params,
            "metrics": metrics,
        }
        if reject_reasons:
            record["reject_reasons"] = reject_reasons
            rejected.append(record)
        else:
            passed.append(record)

    return passed, rejected


def _inspect_params(trials: list[dict]) -> dict[str, dict]:
    flags: dict[str, dict] = {}
    trial_map = {t["trial_num"]: t for t in trials}

    for trial_num, (param_name, threshold, direction) in PARAM_INSPECT.items():
        if trial_num not in trial_map:
            flags[trial_num] = {
                "param": param_name,
                "value": "NOT_IN_FILTERED_POOL",
                "threshold": threshold,
                "direction": direction,
                "flagged": False,
            }
            continue
        trial = trial_map[trial_num]
        raw = trial["params"].get(param_name)
        if raw is None:
            flags[trial_num] = {
                "param": param_name,
                "value": "NOT_IN_PARAMS",
                "threshold": threshold,
                "direction": direction,
                "flagged": False,
            }
            continue
        value = float(raw)
        if direction == "lt":
            flagged = value < threshold
        else:
            flagged = value > threshold
        flags[trial_num] = {
            "param": param_name,
            "value": value,
            "threshold": threshold,
            "direction": direction,
            "flagged": flagged,
        }
    return flags


def _evaluate_segment(
    *,
    candidate_settings: Any,
    candidate_params: dict[str, Any],
    source_db_path: Path,
    snapshots_dir: Path,
    segment_id: str,
    start_ts: str,
    end_ts: str,
    min_trades: int,
) -> TrialEvaluation:
    snapshot_path = create_trial_snapshot(source_db_path, snapshots_dir, segment_id)
    conn = open_snapshot_connection(snapshot_path)
    try:
        verify_required_tables(conn)
        return evaluate_candidate(
            conn,
            settings=candidate_settings,
            candidate_params=candidate_params,
            backtest_config=BacktestConfig(
                start_date=start_ts,
                end_date=end_ts,
                symbol=candidate_settings.strategy.symbol,
            ),
            min_trades=min_trades,
        )
    finally:
        conn.close()
        snapshot_path.unlink(missing_ok=True)


def _segment_failures(evaluation: TrialEvaluation, protocol: dict) -> list[str]:
    min_er = float(protocol.get("min_expectancy_r_per_window", 0.0))
    min_pf = float(protocol.get("min_profit_factor_per_window", 1.0))
    max_dd = float(protocol.get("max_drawdown_pct_per_window", 50.0))
    min_sharpe = float(protocol.get("min_sharpe_ratio_per_window", 0.0))

    failures: list[str] = []
    if evaluation.rejected_reason is not None:
        failures.append(evaluation.rejected_reason)
    m = evaluation.metrics
    if m.expectancy_r < min_er:
        failures.append(f"expectancy_r={m.expectancy_r:.4f} < {min_er}")
    if m.profit_factor < min_pf:
        failures.append(f"profit_factor={m.profit_factor:.4f} < {min_pf}")
    if m.max_drawdown_pct > max_dd:
        failures.append(f"max_drawdown_pct={m.max_drawdown_pct:.4f} > {max_dd}")
    if m.sharpe_ratio < min_sharpe:
        failures.append(f"sharpe_ratio={m.sharpe_ratio:.4f} < {min_sharpe}")
    return failures


def _metrics_dict(evaluation: TrialEvaluation) -> dict[str, Any]:
    m = evaluation.metrics
    return {
        "er": round(m.expectancy_r, 6),
        "pf": round(m.profit_factor, 6),
        "mdd": round(m.max_drawdown_pct, 6),
        "sharpe": round(m.sharpe_ratio, 6),
        "trades": m.trades_count,
        "win_rate": round(m.win_rate, 6),
    }


def run_wf_with_detail(
    *,
    base_settings: Any,
    candidate_params: dict[str, Any],
    windows: list[WalkForwardWindow],
    source_db_path: Path,
    snapshots_dir: Path,
    protocol: dict,
    trial_num: str,
) -> tuple[WalkForwardReport, list[dict]]:
    candidate_settings = build_candidate_settings(base_settings, candidate_params)
    min_trades_per_window = int(protocol["min_trades_per_window"])
    fragile_threshold = float(protocol["fragility_degradation_threshold_pct"])
    require_all = bool(protocol["promotion_requires_all_windows_pass"])
    require_median = bool(protocol["promotion_requires_median_pass"])
    protocol_hash = hash_protocol(protocol)

    windows_total = len(windows)
    windows_passed = 0
    degradations: list[float] = []
    reasons: list[str] = []
    window_details: list[dict] = []

    for index, window in enumerate(windows):
        print(
            f"  [trial-{trial_num}] window {index}: "
            f"train {window.train_start[:10]}→{window.train_end[:10]}",
            flush=True,
        )
        train_eval = _evaluate_segment(
            candidate_settings=candidate_settings,
            candidate_params=candidate_params,
            source_db_path=source_db_path,
            snapshots_dir=snapshots_dir,
            segment_id=f"wfv1-{trial_num}-t{index}",
            start_ts=window.train_start,
            end_ts=window.train_end,
            min_trades=min_trades_per_window,
        )
        print(
            f"  [trial-{trial_num}] window {index}: "
            f"val {window.validation_start[:10]}→{window.validation_end[:10]}",
            flush=True,
        )
        val_eval = _evaluate_segment(
            candidate_settings=candidate_settings,
            candidate_params=candidate_params,
            source_db_path=source_db_path,
            snapshots_dir=snapshots_dir,
            segment_id=f"wfv1-{trial_num}-v{index}",
            start_ts=window.validation_start,
            end_ts=window.validation_end,
            min_trades=min_trades_per_window,
        )

        train_failures = _segment_failures(train_eval, protocol)
        val_failures = _segment_failures(val_eval, protocol)
        window_passed = not train_failures and not val_failures

        if window_passed:
            windows_passed += 1
            in_er = train_eval.metrics.expectancy_r
            oos_er = val_eval.metrics.expectancy_r
            deg = (in_er - oos_er) / max(abs(in_er), 1e-12) * 100.0
            degradations.append(deg)
        else:
            for detail in train_failures:
                reasons.append(f"window_{index:03d}_train_failed: {detail}")
            for detail in val_failures:
                reasons.append(f"window_{index:03d}_validation_failed: {detail}")

        window_details.append(
            {
                "window_index": index,
                "train_start": window.train_start[:10],
                "train_end": window.train_end[:10],
                "validation_start": window.validation_start[:10],
                "validation_end": window.validation_end[:10],
                "window_passed": window_passed,
                "train": dict(_metrics_dict(train_eval), failures=train_failures),
                "validation": dict(_metrics_dict(val_eval), failures=val_failures),
            }
        )

        print(
            f"  [trial-{trial_num}] window {index}: "
            f"train_pass={not bool(train_failures)} val_pass={not bool(val_failures)} "
            f"train_trades={train_eval.metrics.trades_count} val_trades={val_eval.metrics.trades_count}",
            flush=True,
        )

    if windows_total == 0:
        reasons.append("no_windows_available")

    avg_degradation = sum(degradations) / len(degradations) if degradations else 0.0
    fragile = avg_degradation > fragile_threshold
    if fragile:
        reasons.append(
            f"fragility_threshold_exceeded: {avg_degradation:.2f}% > {fragile_threshold:.2f}%"
        )

    if require_all:
        passed = windows_total > 0 and windows_passed == windows_total and not fragile
    elif require_median:
        median_required = math.ceil(windows_total / 2) if windows_total else 0
        passed = windows_total > 0 and windows_passed >= median_required and not fragile
        if windows_total > 0 and windows_passed < median_required:
            reasons.append(f"median_windows_not_met: {windows_passed}/{windows_total}")
    else:
        passed = windows_total > 0 and windows_passed > 0 and not fragile

    if windows_total > 0 and windows_passed == 0:
        reasons.append("no_window_passed")

    report = WalkForwardReport(
        passed=passed,
        windows_total=windows_total,
        windows_passed=windows_passed,
        is_degradation_pct=avg_degradation,
        fragile=fragile,
        reasons=tuple(reasons),
        protocol_hash=protocol_hash,
    )
    return report, window_details


def main() -> None:
    parser = argparse.ArgumentParser(description="WALKFORWARD-DEFAULT-V1 runner")
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--run-wf", action="store_true")
    parser.add_argument("--trial-ids", type=str, default=None)
    parser.add_argument("--output-dir", type=str, default="/tmp/wf_default_v1_results")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    protocol = json.loads(PROTOCOL_PATH.read_text())

    print("=" * 70, flush=True)
    print("PHASE 1: HARD FILTER", flush=True)
    print("=" * 70, flush=True)
    print(f"Rules: pf>{HARD_FILTER_MAX_PF} | wr>{HARD_FILTER_MAX_WR} | er<{HARD_FILTER_MIN_ER}", flush=True)

    passed_trials, rejected_trials = _load_filtered_trials(STORE_PATH)
    pre_count = len(passed_trials) + len(rejected_trials)

    print(f"Pre-filter:  {pre_count} PASSED trials in {STUDY_PREFIX}", flush=True)
    print(f"Post-filter: {len(passed_trials)} passed | {len(rejected_trials)} rejected", flush=True)
    print(flush=True)
    print("REJECTED:", flush=True)
    for t in rejected_trials:
        print(f"  {t['trial_id']} — {'; '.join(t['reject_reasons'])}", flush=True)
    print(flush=True)
    print("PASSED (WF candidates):", flush=True)
    for t in passed_trials:
        m = t["metrics"]
        print(
            f"  {t['trial_id']} "
            f"er={m['expectancy_r']:.3f} pf={m['profit_factor']:.3f} "
            f"wr={m['win_rate']:.3f} mdd={m['max_drawdown_pct']:.3f}",
            flush=True,
        )

    filter_report = {
        "study": STUDY_PREFIX,
        "pre_filter_count": pre_count,
        "post_filter_count": len(passed_trials),
        "rejected_count": len(rejected_trials),
        "hard_filter_rules": {
            "max_profit_factor": HARD_FILTER_MAX_PF,
            "max_win_rate": HARD_FILTER_MAX_WR,
            "min_expectancy_r": HARD_FILTER_MIN_ER,
        },
        "rejected_trials": [
            {"trial_id": t["trial_id"], "trial_num": t["trial_num"], "reject_reasons": t["reject_reasons"], "metrics": t["metrics"]}
            for t in rejected_trials
        ],
        "passed_trials": [
            {"trial_id": t["trial_id"], "trial_num": t["trial_num"], "metrics": t["metrics"]}
            for t in passed_trials
        ],
    }
    (output_dir / "filter_report.json").write_text(json.dumps(filter_report, indent=2))
    print(f"\nFilter report → {output_dir}/filter_report.json", flush=True)

    print(flush=True)
    print("=" * 70, flush=True)
    print("PHASE 2: PARAM INSPECTION", flush=True)
    print("=" * 70, flush=True)

    flags = _inspect_params(passed_trials)
    for trial_num, fi in flags.items():
        val = fi.get("value", "N/A")
        thr = fi.get("threshold", "N/A")
        direction = fi.get("direction", "")
        status = "FLAGGED ⚠️" if fi.get("flagged") else "OK"
        print(
            f"  trial-{trial_num}: {fi['param']}={val} "
            f"(flag if {direction} {thr}) → {status}",
            flush=True,
        )

    (output_dir / "param_inspection.json").write_text(json.dumps(flags, indent=2))
    print(f"Param inspection → {output_dir}/param_inspection.json", flush=True)

    if args.inspect_only or not args.run_wf:
        print("\n[inspect-only mode] Done. Run with --run-wf to execute walk-forward.", flush=True)
        return

    print(flush=True)
    print("=" * 70, flush=True)
    print("PHASE 3: WALK-FORWARD RUN", flush=True)
    print("=" * 70, flush=True)

    settings = load_settings(profile="research")
    if settings.storage is None:
        print("ERROR: settings.storage is None — cannot resolve source DB path", flush=True)
        sys.exit(1)
    source_db_path = settings.storage.db_path

    windows = build_windows(START_DATE, END_DATE, protocol)
    print(f"WF windows: {len(windows)}", flush=True)
    for i, w in enumerate(windows):
        print(
            f"  Window {i}: train {w.train_start[:10]}→{w.train_end[:10]} "
            f"| val {w.validation_start[:10]}→{w.validation_end[:10]}",
            flush=True,
        )

    trial_map = {t["trial_num"]: t for t in passed_trials}

    if args.trial_ids:
        order = [x.strip() for x in args.trial_ids.split(",") if x.strip() in trial_map]
    else:
        order = []
        for num in PRIORITY_ORDER:
            if num in trial_map:
                order.append(num)
        for t in passed_trials:
            if t["trial_num"] not in order:
                order.append(t["trial_num"])

    print(f"\nExecution order ({len(order)} trials): {order}", flush=True)

    summary_rows: list[dict] = []

    for trial_num in order:
        if trial_num not in trial_map:
            print(f"\n[SKIP] trial-{trial_num} not in filtered pool", flush=True)
            continue

        trial = trial_map[trial_num]
        m_is = trial["metrics"]
        flag_info = flags.get(trial_num)
        flag_str = ""
        if flag_info and flag_info.get("flagged"):
            flag_str = f"{flag_info['param']}={flag_info['value']} ⚠️"

        print(f"\n{'─' * 60}", flush=True)
        print(
            f"[trial-{trial_num}] is_er={m_is['expectancy_r']:.3f} "
            f"is_pf={m_is['profit_factor']:.3f} is_wr={m_is['win_rate']:.3f} "
            f"is_mdd={m_is['max_drawdown_pct']:.3f} is_trades={m_is['trades_count']}",
            flush=True,
        )
        if flag_str:
            print(f"  PARAM FLAG: {flag_str}", flush=True)

        try:
            report, window_details = run_wf_with_detail(
                base_settings=settings,
                candidate_params=trial["params"],
                windows=windows,
                source_db_path=source_db_path,
                snapshots_dir=SNAPSHOTS_DIR,
                protocol=protocol,
                trial_num=trial_num,
            )

            verdict = "PASS" if report.passed else "FAIL"
            print(
                f"  WF verdict: {verdict} | windows: {report.windows_passed}/{report.windows_total} "
                f"| degradation: {report.is_degradation_pct:.1f}% | fragile: {report.fragile}",
                flush=True,
            )
            for reason in report.reasons:
                print(f"    {reason}", flush=True)

            oos_er = oos_sharpe = 0.0
            is_wf_er = is_wf_sharpe = 0.0
            if window_details:
                last = window_details[-1]
                oos_er = last["validation"]["er"]
                oos_sharpe = last["validation"]["sharpe"]
                is_wf_er = last["train"]["er"]
                is_wf_sharpe = last["train"]["sharpe"]

            artifact: dict[str, Any] = {
                "trial_id": trial["trial_id"],
                "trial_num": trial_num,
                "in_sample_metrics": m_is,
                "param_flag": flag_info,
                "wf_report": {
                    "passed": report.passed,
                    "windows_total": report.windows_total,
                    "windows_passed": report.windows_passed,
                    "is_degradation_pct": round(report.is_degradation_pct, 4),
                    "fragile": report.fragile,
                    "reasons": list(report.reasons),
                    "protocol_hash": report.protocol_hash,
                },
                "window_details": window_details,
            }
            artifact_path = output_dir / f"wf_trial_{trial_num}.json"
            artifact_path.write_text(json.dumps(artifact, indent=2))
            print(f"  Artifact → {artifact_path}", flush=True)

            summary_rows.append(
                {
                    "trial": f"trial-{trial_num}",
                    "is_er": round(m_is["expectancy_r"], 4),
                    "oos_er": round(oos_er, 4),
                    "is_sharpe": round(m_is["sharpe_ratio"], 4),
                    "oos_sharpe": round(oos_sharpe, 4),
                    "wf_verdict": verdict,
                    "windows": f"{report.windows_passed}/{report.windows_total}",
                    "degradation_pct": round(report.is_degradation_pct, 2),
                    "fragile": report.fragile,
                    "param_flag": flag_str,
                    "is_mdd": round(m_is["max_drawdown_pct"], 4),
                    "is_trades": m_is["trades_count"],
                    "oos_trades": last["validation"]["trades"] if window_details else 0,
                }
            )

        except Exception as exc:
            import traceback
            print(f"  ERROR: {exc}", flush=True)
            traceback.print_exc()
            summary_rows.append(
                {
                    "trial": f"trial-{trial_num}",
                    "is_er": round(m_is["expectancy_r"], 4),
                    "oos_er": "ERROR",
                    "is_sharpe": round(m_is["sharpe_ratio"], 4),
                    "oos_sharpe": "ERROR",
                    "wf_verdict": "ERROR",
                    "windows": "?/?",
                    "degradation_pct": 0.0,
                    "fragile": False,
                    "param_flag": flag_str,
                    "is_mdd": round(m_is["max_drawdown_pct"], 4),
                    "is_trades": m_is["trades_count"],
                    "oos_trades": 0,
                }
            )

    (output_dir / "summary.json").write_text(json.dumps(summary_rows, indent=2))

    print(flush=True)
    print("=" * 70, flush=True)
    print("WALKFORWARD-DEFAULT-V1 — FINAL SUMMARY", flush=True)
    print("=" * 70, flush=True)
    hdr = f"{'Trial':<20} {'IS_ER':>8} {'OOS_ER':>8} {'IS_Sh':>8} {'OOS_Sh':>8} {'Verdict':>8} {'Win':>5} {'Deg%':>6}  Flag"
    print(hdr, flush=True)
    print("-" * 90, flush=True)
    for row in summary_rows:
        is_er = f"{row['is_er']:.3f}" if isinstance(row["is_er"], float) else str(row["is_er"])
        oos_er = f"{row['oos_er']:.3f}" if isinstance(row["oos_er"], float) else str(row["oos_er"])
        is_sh = f"{row['is_sharpe']:.2f}" if isinstance(row["is_sharpe"], float) else str(row["is_sharpe"])
        oos_sh = f"{row['oos_sharpe']:.2f}" if isinstance(row["oos_sharpe"], float) else str(row["oos_sharpe"])
        deg = f"{row['degradation_pct']:.1f}" if isinstance(row["degradation_pct"], float) else "0.0"
        print(
            f"{row['trial']:<20} {is_er:>8} {oos_er:>8} {is_sh:>8} {oos_sh:>8} "
            f"{row['wf_verdict']:>8} {row['windows']:>5} {deg:>6}%  {row['param_flag']}",
            flush=True,
        )

    print(f"\nAll artifacts → {output_dir}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()

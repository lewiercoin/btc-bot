from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig
from settings import load_settings

from research_lab.approval import write_approval_bundle
from research_lab.autoresearch_loop import run_autoresearch_loop
from research_lab.constants import PROMOTION_BLOCKING_RISKS
from research_lab.reporter import build_experiment_report, write_experiment_report
from research_lab.types import RecommendationDraft
from research_lab.workflows.optimize_loop import run_optimize_loop
from research_lab.workflows.replay_candidate import replay_candidate


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_date_only(raw: str) -> bool:
    token = raw.strip()
    return "T" not in token and " " not in token


def _parse_iso_datetime(raw: str, *, is_end: bool) -> datetime:
    parsed = _to_utc(datetime.fromisoformat(raw))
    if is_end and _is_date_only(raw):
        return parsed + timedelta(days=1)
    return parsed


def _default_paths() -> tuple[Path, Path, Path]:
    settings = load_settings()
    if settings.storage is None:
        raise ValueError("settings.storage is required for research_lab CLI defaults.")
    root = settings.storage.project_root
    source_db_path = settings.storage.db_path
    store_path = root / "research_lab" / "research_lab.db"
    snapshots_dir = root / "research_lab" / "snapshots"
    return source_db_path, store_path, snapshots_dir


def _load_recommendation(store_path: Path, candidate_id: str) -> RecommendationDraft:
    if not store_path.exists():
        raise ValueError(f"Store not found: {store_path}")
    conn = sqlite3.connect(store_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT recommendation_json FROM recommendations WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"Recommendation not found for candidate_id={candidate_id!r}")
    payload: dict[str, Any] = json.loads(str(row["recommendation_json"]))
    return RecommendationDraft(
        candidate_id=str(payload["candidate_id"]),
        summary=str(payload["summary"]),
        params_diff=dict(payload.get("params_diff", {})),
        expected_improvement={k: float(v) for k, v in dict(payload.get("expected_improvement", {})).items()},
        risks=tuple(payload.get("risks", [])),
        approval_required=bool(payload.get("approval_required", True)),
        protocol_hash=str(payload["protocol_hash"]) if payload.get("protocol_hash") is not None else None,
    )


def _get_blocking_promotion_risks(risks: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(risk for risk in risks if risk in PROMOTION_BLOCKING_RISKS))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research Lab v0.1 offline optimization CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    optimize = sub.add_parser("optimize", help="Run full Optuna search + walk-forward on Pareto candidates.")
    optimize.add_argument("--source-db-path", type=Path, default=None)
    optimize.add_argument("--store-path", type=Path, default=None)
    optimize.add_argument("--snapshots-dir", type=Path, default=None)
    optimize.add_argument("--protocol-path", type=Path, default=None)
    optimize.add_argument("--start-date", required=True, type=str)
    optimize.add_argument("--end-date", required=True, type=str)
    optimize.add_argument("--n-trials", type=int, default=50)
    optimize.add_argument("--study-name", type=str, default="research-lab-v0_1")
    optimize.add_argument("--seed", type=int, default=42)
    optimize.add_argument("--max-sweep-rate", type=float, default=0.5)
    optimize.add_argument("--optuna-storage-path", type=Path, default=None)
    optimize.add_argument("--warm-start-from-store", action="store_true", default=False)
    optimize.add_argument("--multivariate-tpe", action="store_true", default=False)

    replay = sub.add_parser("replay-candidate", help="Replay one candidate and rebuild walk-forward artifacts.")
    replay.add_argument("--candidate-id", required=True, type=str)
    replay.add_argument("--source-db-path", type=Path, default=None)
    replay.add_argument("--store-path", type=Path, default=None)
    replay.add_argument("--snapshots-dir", type=Path, default=None)
    replay.add_argument("--protocol-path", type=Path, default=None)
    replay.add_argument("--start-date", required=True, type=str)
    replay.add_argument("--end-date", required=True, type=str)

    autoresearch = sub.add_parser("autoresearch", help="Run single-pass autoresearch loop and write loop artifacts.")
    autoresearch.add_argument("--start-date", required=True, type=str)
    autoresearch.add_argument("--end-date", required=True, type=str)
    autoresearch.add_argument("--output-dir", required=True, type=Path)
    autoresearch.add_argument("--source-db-path", type=Path, default=None)
    autoresearch.add_argument("--store-path", type=Path, default=None)
    autoresearch.add_argument("--snapshots-dir", type=Path, default=None)
    autoresearch.add_argument("--protocol-path", type=Path, default=None)
    autoresearch.add_argument("--seed", type=int, default=42)
    autoresearch.add_argument("--max-candidates", type=int, default=10)

    report = sub.add_parser("build-report", help="Build experiment report from store.")
    report.add_argument("--store-path", type=Path, default=None)
    report.add_argument("--output-json", type=Path, required=True)

    approval = sub.add_parser("build-approval-bundle", help="Generate human approval artifacts.")
    approval.add_argument("--candidate-id", required=True, type=str)
    approval.add_argument("--store-path", type=Path, default=None)
    approval.add_argument("--output-dir", required=True, type=Path)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    settings = load_settings()
    if settings.storage is None:
        raise ValueError("settings.storage is required to run research_lab CLI.")

    default_source_db, default_store_path, default_snapshots_dir = _default_paths()
    source_db_path = args.source_db_path if getattr(args, "source_db_path", None) is not None else default_source_db
    store_path = args.store_path if getattr(args, "store_path", None) is not None else default_store_path
    snapshots_dir = args.snapshots_dir if getattr(args, "snapshots_dir", None) is not None else default_snapshots_dir

    if args.command == "optimize":
        start_ts = _parse_iso_datetime(args.start_date, is_end=False)
        end_ts = _parse_iso_datetime(args.end_date, is_end=True)
        if end_ts <= start_ts:
            raise ValueError("--end-date must be later than --start-date.")
        summary = run_optimize_loop(
            source_db_path=source_db_path,
            store_path=store_path,
            snapshots_dir=snapshots_dir,
            backtest_config=BacktestConfig(
                start_date=start_ts,
                end_date=end_ts,
                symbol=settings.strategy.symbol,
            ),
            base_settings=settings,
            n_trials=int(args.n_trials),
            study_name=str(args.study_name),
            seed=int(args.seed),
            protocol_path=args.protocol_path,
            max_sweep_rate=float(args.max_sweep_rate),
            optuna_storage_path=args.optuna_storage_path,
            warm_start_from_store=bool(args.warm_start_from_store),
            multivariate_tpe=bool(args.multivariate_tpe),
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    if args.command == "replay-candidate":
        start_ts = _parse_iso_datetime(args.start_date, is_end=False)
        end_ts = _parse_iso_datetime(args.end_date, is_end=True)
        if end_ts <= start_ts:
            raise ValueError("--end-date must be later than --start-date.")
        summary = replay_candidate(
            candidate_id=args.candidate_id,
            base_settings=settings,
            source_db_path=source_db_path,
            snapshots_dir=snapshots_dir,
            store_path=store_path,
            backtest_config=BacktestConfig(
                start_date=start_ts,
                end_date=end_ts,
                symbol=settings.strategy.symbol,
            ),
            protocol_path=args.protocol_path,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    if args.command == "autoresearch":
        start_ts = _parse_iso_datetime(args.start_date, is_end=False)
        end_ts = _parse_iso_datetime(args.end_date, is_end=True)
        if end_ts <= start_ts:
            raise ValueError("--end-date must be later than --start-date.")
        report = run_autoresearch_loop(
            source_db_path=source_db_path,
            store_path=store_path,
            snapshots_dir=snapshots_dir,
            output_dir=args.output_dir,
            backtest_config=BacktestConfig(
                start_date=start_ts,
                end_date=end_ts,
                symbol=settings.strategy.symbol,
            ),
            base_settings=settings,
            protocol_path=args.protocol_path,
            seed=int(args.seed),
            max_candidates=int(args.max_candidates),
        )
        summary = {
            "run_id": report.run_id,
            "candidates_evaluated": report.candidates_evaluated,
            "candidates_blocked": report.candidates_blocked,
            "stop_reason": report.stop_reason,
            "approval_bundle_written": report.approval_bundle_written,
            "approval_bundle_candidate_id": report.approval_bundle_candidate_id,
        }
        print(json.dumps(summary, indent=2))
        return

    if args.command == "build-report":
        report = build_experiment_report(store_path)
        output_path = write_experiment_report(report=report, output_path=args.output_json)
        print(output_path)
        return

    if args.command == "build-approval-bundle":
        recommendation = _load_recommendation(store_path, args.candidate_id)
        blocking_risks = _get_blocking_promotion_risks(recommendation.risks)
        if blocking_risks:
            blocking_str = ", ".join(blocking_risks)
            print(
                "Cannot build approval bundle: blocking promotion risks detected "
                f"for candidate {recommendation.candidate_id}: {blocking_str}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        bundle_path = write_approval_bundle(recommendation=recommendation, output_dir=args.output_dir)
        print(bundle_path)
        return

    raise ValueError(f"Unsupported command: {args.command}")

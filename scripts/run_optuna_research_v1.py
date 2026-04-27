"""
RESEARCH-OPTUNA-V1 offline optimization runner.

IMPORTANT:
- All output is labeled RESEARCH_ONLY.
- No parameters are promoted to production automatically.
- Context breakdown is diagnostic only — NOT an optimization objective.
- Do NOT activate context gating based on these results.
- Do NOT change neutral_mode.
- Production config change requires a separate MODELING-V1-ACTIVATION milestone.

Usage:
    python scripts/run_optuna_research_v1.py \\
        --source-db-path /path/to/btc_bot.db \\
        --start-date 2024-01-01 \\
        --end-date 2026-04-01 \\
        --n-trials 50 \\
        --output-dir docs/analysis
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backtest.backtest_runner import BacktestConfig, BacktestRunner
from settings import load_settings

from research_lab.context_diagnostics import compute_context_diagnostics
from research_lab.protocol import load_protocol
from research_lab.settings_adapter import build_candidate_settings
from research_lab.workflows.optimize_loop import run_optimize_loop


_DEFAULT_PROTOCOL = Path(__file__).resolve().parents[1] / "research_lab" / "configs" / "reclaim_edge_v1.json"
_DEFAULT_STORE = Path(__file__).resolve().parents[1] / "research_lab" / "research_lab.db"
_DEFAULT_SNAPSHOTS = Path(__file__).resolve().parents[1] / "research_lab" / "snapshots"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="RESEARCH-OPTUNA-V1: offline reclaim edge optimization. RESEARCH_ONLY."
    )
    p.add_argument("--source-db-path", type=Path, required=True, help="Path to production btc_bot.db snapshot.")
    p.add_argument("--start-date", required=True, type=str, help="Backtest start date ISO (e.g. 2024-01-01).")
    p.add_argument("--end-date", required=True, type=str, help="Backtest end date ISO (e.g. 2026-04-01).")
    p.add_argument("--n-trials", type=int, default=50)
    p.add_argument("--output-dir", type=Path, default=Path("docs/analysis"))
    p.add_argument("--protocol-path", type=Path, default=_DEFAULT_PROTOCOL)
    p.add_argument("--store-path", type=Path, default=_DEFAULT_STORE)
    p.add_argument("--snapshots-dir", type=Path, default=_DEFAULT_SNAPSHOTS)
    p.add_argument("--study-name", type=str, default="research-optuna-v1")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--max-sweep-rate", type=float, default=0.5)
    return p.parse_args(argv)


def _parse_iso(raw: str, *, is_end: bool) -> datetime:
    token = raw.strip()
    dt = datetime.fromisoformat(token)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    if is_end and "T" not in token and " " not in token:
        dt = dt + timedelta(days=1)
    return dt


def _replay_candidate_trades(
    source_db_path: Path,
    settings: Any,
    candidate_params: dict[str, Any],
    backtest_config: BacktestConfig,
) -> list[Any]:
    """Run a quick replay backtest to get individual trade records for context diagnostics."""
    candidate_settings = build_candidate_settings(settings, candidate_params)
    db_uri = f"file:{source_db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        runner = BacktestRunner(conn, settings=candidate_settings)
        runner._persist_closed_trades = lambda _: None  # type: ignore[method-assign]
        result = runner.run(backtest_config)
    finally:
        conn.close()
    return list(result.trades)


def _fmt_bucket_row(name: str, stats: dict[str, Any]) -> str:
    n = stats["n"]
    wr = f"{stats['win_rate'] * 100:.1f}%"
    exp = f"{stats['expectancy_r']:+.3f}R"
    pf = f"{stats['profit_factor']:.2f}" if stats["profit_factor"] is not None else "∞"
    return f"| {name} | {n} | {wr} | {exp} | {pf} |"


def _build_markdown_report(
    *,
    run_date: str,
    start_date: str,
    end_date: str,
    n_trials: int,
    protocol_path: Path,
    optimize_result: dict[str, Any],
    candidate_diagnostics: list[dict[str, Any]],
) -> str:
    protocol_hash = optimize_result.get("protocol_hash", "N/A")
    trials_total = optimize_result.get("trials_total", 0)
    pareto_count = optimize_result.get("pareto_candidates", 0)
    wf_windows = optimize_result.get("walkforward_windows", 0)
    baseline_warn = optimize_result.get("baseline_warning") or "none"
    baseline_metrics = optimize_result.get("baseline_metrics") or {}
    pareto_ranked = optimize_result.get("pareto_ranked") or []

    lines = [
        "# RESEARCH-OPTUNA-V1: Offline Reclaim Edge Optimization",
        "",
        "> **Status:** ⚠️ RESEARCH_ONLY — no parameters promoted to production",
        "> Context breakdown is **diagnostic only** — not used as optimization objective.",
        "> Do NOT activate context gating based on these results.",
        "> Production config change requires a separate **MODELING-V1-ACTIVATION** milestone.",
        "",
        f"**Run date:** {run_date}",
        f"**Data range:** {start_date} → {end_date}",
        f"**Trials:** {n_trials} requested / {trials_total} completed",
        f"**Protocol:** `{protocol_path.name}` (hash: `{protocol_hash}`)",
        f"**Walk-forward windows:** {wf_windows}",
        f"**Pareto candidates:** {pareto_count}",
        f"**Baseline warning:** {baseline_warn}",
        "",
        "---",
        "",
        "## Baseline Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
    ]
    for key, val in sorted(baseline_metrics.items()):
        lines.append(f"| {key} | {val} |")

    lines += [
        "",
        "---",
        "",
        "## Pareto Frontier Candidates",
        "",
        "| Rank | Candidate ID | Expectancy R | Profit Factor | Max DD% | Trades |",
        "|------|-------------|-------------|--------------|---------|--------|",
    ]
    for rank, c in enumerate(pareto_ranked, 1):
        cid = str(c.get("candidate_id", c.get("trial_id", "??")))[:16]
        exp = float(c.get("expectancy_r", 0))
        pf = float(c.get("profit_factor", 0))
        dd = float(c.get("max_drawdown_pct", 0))
        tc = int(c.get("trades_count", 0))
        lines.append(f"| {rank} | `{cid}` | {exp:+.4f}R | {pf:.3f} | {dd * 100:.1f}% | {tc} |")

    lines += [
        "",
        "---",
        "",
        "## Context Diagnostics by Candidate _(RESEARCH_ONLY)_",
        "",
        "> Session and volatility breakdown is informational only.",
        "> These buckets must NOT be used as hard filters until MODELING-V1-ACTIVATION is approved.",
        "",
    ]

    for diag in candidate_diagnostics:
        cid = diag.get("candidate_id", "??")
        ctx = diag.get("context_diagnostics", {})
        grade = ctx.get("grade", "UNKNOWN")
        unk_pct = ctx.get("unknown_volatility_pct", 100.0)
        n_total = ctx.get("trades_total", 0)
        grade_icon = "⚠️" if grade in ("PARTIAL", "EMPTY") else "✅"

        lines += [
            f"### Candidate `{cid}` — Context Grade: {grade_icon} {grade}",
            "",
            f"Trades: {n_total} | UNKNOWN volatility: {unk_pct:.1f}%",
            "",
        ]

        session_buckets = ctx.get("session_buckets", {})
        if session_buckets:
            lines += [
                "**Session breakdown:**",
                "",
                "| Session | N | Win Rate | Expectancy R | Profit Factor |",
                "|---------|---|----------|-------------|--------------|",
            ]
            for bname, bstats in sorted(session_buckets.items()):
                lines.append(_fmt_bucket_row(bname, bstats))
            lines.append("")

        vol_buckets = ctx.get("volatility_buckets", {})
        vol_header = "**Volatility breakdown:**" if grade == "FULL" else "**Volatility breakdown** _(⚠️ PARTIAL — not decision-grade)_:"
        if vol_buckets:
            lines += [
                vol_header,
                "",
                "| Volatility | N | Win Rate | Expectancy R | Profit Factor |",
                "|------------|---|----------|-------------|--------------|",
            ]
            for bname, bstats in sorted(vol_buckets.items()):
                lines.append(_fmt_bucket_row(bname, bstats))
            lines.append("")

    lines += [
        "---",
        "",
        "## Verdict",
        "",
        "⚠️ **RESEARCH_ONLY — no production action taken.**",
        "",
        "Gates required before any production config change:",
        "",
        "- [ ] Walk-forward pass (all windows) — see optimization log",
        "- [ ] min_trades ≥ 30 per candidate",
        "- [ ] profit_factor ≥ 1.1 per window",
        "- [ ] max_drawdown_pct ≤ 40% per window",
        "- [ ] No single context bucket dominates without warning",
        "- [ ] Fees/slippage/funding included in backtest ✅ (always on)",
        "- [ ] Human review and approval bundle generated",
        "- [ ] Separate MODELING-V1-ACTIVATION milestone opened",
        "",
        "---",
        "",
        "## Notes",
        "",
        "- Context engine running in `neutral_mode=True` (no trade blocking).",
        "- Fees, spread, and funding costs included in backtest via `fill_model.py`.",
        "- Config lineage hash recorded in JSON artifact for reproducibility.",
        f"- Protocol: `{protocol_path.name}` | Hash: `{protocol_hash}`",
    ]

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    start_ts = _parse_iso(args.start_date, is_end=False)
    end_ts = _parse_iso(args.end_date, is_end=True)
    if end_ts <= start_ts:
        print("ERROR: --end-date must be later than --start-date.", file=sys.stderr)
        sys.exit(1)

    if not args.source_db_path.exists():
        print(f"ERROR: source DB not found: {args.source_db_path}", file=sys.stderr)
        sys.exit(1)

    settings = load_settings(profile="research")
    backtest_config = BacktestConfig(
        start_date=start_ts,
        end_date=end_ts,
        symbol=settings.strategy.symbol,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.snapshots_dir.mkdir(parents=True, exist_ok=True)

    print(f"[RESEARCH-OPTUNA-V1] Starting offline optimization")
    print(f"  Source DB:  {args.source_db_path}")
    print(f"  Date range: {args.start_date} → {args.end_date}")
    print(f"  Protocol:   {args.protocol_path}")
    print(f"  Trials:     {args.n_trials}")
    print(f"  Study:      {args.study_name}")
    print(f"  RESEARCH_ONLY — no parameters promoted automatically.")
    print()

    optimize_result = run_optimize_loop(
        source_db_path=args.source_db_path,
        store_path=args.store_path,
        snapshots_dir=args.snapshots_dir,
        backtest_config=backtest_config,
        base_settings=settings,
        n_trials=args.n_trials,
        study_name=args.study_name,
        seed=args.seed,
        protocol_path=args.protocol_path,
        max_sweep_rate=args.max_sweep_rate,
    )

    protocol = load_protocol(args.protocol_path)
    pareto_ranked: list[dict[str, Any]] = optimize_result.get("pareto_ranked") or []

    print(f"[RESEARCH-OPTUNA-V1] Optimization complete.")
    print(f"  Trials total:      {optimize_result.get('trials_total', 0)}")
    print(f"  Pareto candidates: {optimize_result.get('pareto_candidates', 0)}")
    print(f"  WF windows:        {optimize_result.get('walkforward_windows', 0)}")
    print(f"  Baseline warning:  {optimize_result.get('baseline_warning') or 'none'}")
    print()

    candidate_diagnostics: list[dict[str, Any]] = []
    max_diag_candidates = min(len(pareto_ranked), 5)
    if max_diag_candidates > 0:
        print(f"[RESEARCH-OPTUNA-V1] Computing context diagnostics for top {max_diag_candidates} Pareto candidates...")
    for c in pareto_ranked[:max_diag_candidates]:
        cid = str(c.get("candidate_id", c.get("trial_id", "??")))
        params = dict(c.get("params", {}))
        try:
            trades = _replay_candidate_trades(args.source_db_path, settings, params, backtest_config)
            ctx_diag = compute_context_diagnostics(trades)
        except Exception as exc:
            ctx_diag = {"grade": "ERROR", "error": str(exc), "trades_total": 0}
        candidate_diagnostics.append({"candidate_id": cid, "context_diagnostics": ctx_diag})
        print(f"  {cid[:16]}: {ctx_diag.get('trades_total', 0)} trades, "
              f"grade={ctx_diag.get('grade', '?')}, "
              f"UNKNOWN_vol={ctx_diag.get('unknown_volatility_pct', 100):.1f}%")

    run_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    md_content = _build_markdown_report(
        run_date=run_date,
        start_date=args.start_date,
        end_date=args.end_date,
        n_trials=args.n_trials,
        protocol_path=args.protocol_path,
        optimize_result=optimize_result,
        candidate_diagnostics=candidate_diagnostics,
    )

    md_path = args.output_dir / f"OPTUNA_RESEARCH_V1_{run_date}.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"\n[RESEARCH-OPTUNA-V1] Markdown report: {md_path}")

    json_artifact: dict[str, Any] = {
        "research_milestone": "RESEARCH-OPTUNA-V1",
        "status": "RESEARCH_ONLY",
        "run_date": run_date,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "n_trials": args.n_trials,
        "study_name": args.study_name,
        "seed": args.seed,
        "protocol_hash": optimize_result.get("protocol_hash"),
        "protocol_file": str(args.protocol_path),
        "active_params": protocol.get("active_params_whitelist", []),
        "optimize_summary": {
            k: v for k, v in optimize_result.items() if k != "pareto_ranked"
        },
        "pareto_ranked": pareto_ranked,
        "candidate_context_diagnostics": candidate_diagnostics,
        "promotion_gates": {
            "note": "Candidate is RESEARCH_ONLY until ALL gates pass.",
            "required": [
                "walkforward_pass_all_windows",
                "min_trades_per_candidate_30",
                "profit_factor_per_window_gte_1.1",
                "max_drawdown_per_window_lte_40pct",
                "human_review_approval_bundle",
                "MODELING-V1-ACTIVATION_milestone_opened",
            ],
        },
    }

    json_path = args.output_dir / f"OPTUNA_RESEARCH_V1_{run_date}.json"
    json_path.write_text(json.dumps(json_artifact, indent=2, default=str), encoding="utf-8")
    print(f"[RESEARCH-OPTUNA-V1] JSON artifact:    {json_path}")

    print()
    print("=" * 60)
    print("RESEARCH-OPTUNA-V1 COMPLETE — STATUS: RESEARCH_ONLY")
    print("No parameters have been promoted to production.")
    print("Review the Markdown report before opening any activation milestone.")
    print("=" * 60)


if __name__ == "__main__":
    main()

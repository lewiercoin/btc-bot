#!/usr/bin/env python3
"""MODELING-V1-VALIDATION: Offline Retrospective Analysis

Reconstructs session_bucket and volatility_bucket from historical clean data
(pre-MODELING-V1 deploy) and calculates edge quality metrics by context bucket.

This is OFFLINE RETROSPECTIVE analysis — context fields are reconstructed
from existing trade_log.features_at_entry_json and timestamps, NOT from
runtime context telemetry (which only starts after Modeling V1 deploy).

Usage:
    python scripts/modeling_v1_validation.py
    python scripts/modeling_v1_validation.py --db /path/to/btc_bot.db
    python scripts/modeling_v1_validation.py --db /path/to/btc_bot.db --since 2026-01-01

Output:
    docs/analysis/MODELING_V1_VALIDATION_YYYY-MM-DD.md
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "storage" / "btc_bot.db"
OUTPUT_DIR = REPO_ROOT / "docs" / "analysis"

# ---------------------------------------------------------------------------
# Context classification (mirrors ContextEngine defaults)
# ---------------------------------------------------------------------------
ATR_LOW_THRESHOLD = 0.002
ATR_HIGH_THRESHOLD = 0.004


def classify_session(ts_str: str) -> str:
    """Classify UTC session from ISO timestamp string."""
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        h = ts.hour
        if h >= 22 or h < 7:
            return "ASIA"
        if 7 <= h < 14:
            return "EU"
        if 14 <= h < 16:
            return "EU_US"
        return "US"
    except Exception:
        return "UNKNOWN"


def classify_volatility(atr_norm: float | None) -> str:
    if atr_norm is None:
        return "UNKNOWN"
    if atr_norm < ATR_LOW_THRESHOLD:
        return "LOW"
    if atr_norm > ATR_HIGH_THRESHOLD:
        return "HIGH"
    return "NORMAL"


# ---------------------------------------------------------------------------
# Chi-square p-value (no scipy dependency)
# ---------------------------------------------------------------------------
def chi2_pvalue_2x2(a: int, b: int, c: int, d: int) -> float:
    """Two-sided chi-square test for 2x2 contingency table.

    Table:
        | win  | loss |
        | a    | b    |  context bucket
        | c    | d    |  baseline (other)

    Returns p-value. Returns 1.0 if insufficient data.
    """
    n = a + b + c + d
    if n == 0 or (a + b) == 0 or (c + d) == 0:
        return 1.0
    row1 = a + b
    row2 = c + d
    col1 = a + c
    col2 = b + d
    expected_a = row1 * col1 / n
    expected_b = row1 * col2 / n
    expected_c = row2 * col1 / n
    expected_d = row2 * col2 / n
    if min(expected_a, expected_b, expected_c, expected_d) < 1:
        return 1.0
    chi2 = 0.0
    for obs, exp in [(a, expected_a), (b, expected_b), (c, expected_c), (d, expected_d)]:
        chi2 += (obs - exp) ** 2 / exp
    # Approximate p-value from chi-square CDF with df=1 using regularized gamma
    return _chi2_sf(chi2, df=1)


def _chi2_sf(x: float, df: int = 1) -> float:
    """Survival function of chi-square distribution (1 - CDF). df=1 only."""
    if x <= 0:
        return 1.0
    # P(chi2 > x) = P(Z > sqrt(x)) * 2  for df=1 = erfc(sqrt(x/2))
    return math.erfc(math.sqrt(x / 2))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_closed_trades(conn: sqlite3.Connection, since: str | None) -> list[dict]:
    where = "closed_at IS NOT NULL AND exit_price IS NOT NULL"
    params: list = []
    if since:
        where += " AND opened_at >= ?"
        params.append(since)
    rows = conn.execute(
        f"""
        SELECT trade_id, opened_at, closed_at, direction, regime,
               pnl_r, pnl_abs, exit_reason, features_at_entry_json
        FROM trade_log
        WHERE {where}
        ORDER BY opened_at
        """,
        params,
    ).fetchall()

    trades = []
    for row in rows:
        try:
            feats = json.loads(row["features_at_entry_json"] or "{}")
        except Exception:
            feats = {}
        atr_norm = feats.get("atr_4h_norm")
        trades.append(
            {
                "trade_id": row["trade_id"],
                "opened_at": row["opened_at"],
                "pnl_r": row["pnl_r"],
                "pnl_abs": row["pnl_abs"],
                "exit_reason": row["exit_reason"],
                "direction": row["direction"],
                "regime": row["regime"],
                "session": classify_session(row["opened_at"]),
                "volatility": classify_volatility(atr_norm),
                "atr_4h_norm": atr_norm,
                "win": (row["pnl_r"] is not None and row["pnl_r"] > 0),
            }
        )
    return trades


def load_decision_cycles(conn: sqlite3.Connection, since: str | None) -> list[dict]:
    """Load decision cycles with reconstructed context."""
    where = "1=1"
    params: list = []
    if since:
        where += " AND do.cycle_timestamp >= ?"
        params.append(since)
    rows = conn.execute(
        f"""
        SELECT
            do.id,
            do.cycle_timestamp,
            do.outcome_group,
            do.outcome_reason,
            do.signal_id,
            do.regime,
            do.feature_snapshot_id,
            fs.features_json
        FROM decision_outcomes do
        LEFT JOIN feature_snapshots fs ON do.feature_snapshot_id = fs.feature_snapshot_id
        WHERE {where}
        ORDER BY do.cycle_timestamp
        """,
        params,
    ).fetchall()

    cycles = []
    for row in rows:
        feats_json = row["features_json"]
        atr_norm = None
        if feats_json:
            try:
                feats = json.loads(feats_json)
                atr_norm = feats.get("atr_4h_norm")
            except Exception:
                pass
        session = classify_session(row["cycle_timestamp"])
        volatility = classify_volatility(atr_norm)
        edge_present = row["outcome_group"] in (
            "signal_generated", "governance_veto", "risk_block", "execution_failed"
        )
        cycles.append(
            {
                "cycle_timestamp": row["cycle_timestamp"],
                "outcome_group": row["outcome_group"],
                "outcome_reason": row["outcome_reason"],
                "signal_id": row["signal_id"],
                "regime": row["regime"],
                "session": session,
                "volatility": volatility,
                "atr_4h_norm": atr_norm,
                "edge_present": edge_present,
            }
        )
    return cycles


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------
def compute_trade_metrics(trades: list[dict], group_key: str) -> dict[str, dict]:
    """Group trades by group_key and compute metrics per bucket."""
    groups: dict[str, list] = defaultdict(list)
    for t in trades:
        groups[t[group_key]].append(t)

    result = {}
    for bucket, bucket_trades in sorted(groups.items()):
        wins = [t for t in bucket_trades if t["win"]]
        losses = [t for t in bucket_trades if not t["win"]]
        n = len(bucket_trades)
        win_rate = len(wins) / n * 100 if n > 0 else 0.0
        r_values = [t["pnl_r"] for t in bucket_trades if t["pnl_r"] is not None]
        expectancy = sum(r_values) / len(r_values) if r_values else 0.0
        gross_profit = sum(t["pnl_r"] for t in wins if t["pnl_r"] is not None)
        gross_loss = abs(sum(t["pnl_r"] for t in losses if t["pnl_r"] is not None))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0
        result[bucket] = {
            "n": n,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "expectancy_r": expectancy,
            "profit_factor": profit_factor,
            "gross_profit_r": gross_profit,
            "gross_loss_r": gross_loss,
        }
    return result


def compute_session_x_volatility_matrix(trades: list[dict]) -> dict[tuple, dict]:
    groups: dict[tuple, list] = defaultdict(list)
    for t in trades:
        groups[(t["session"], t["volatility"])].append(t)

    result = {}
    for key, bucket_trades in sorted(groups.items()):
        wins = [t for t in bucket_trades if t["win"]]
        n = len(bucket_trades)
        r_values = [t["pnl_r"] for t in bucket_trades if t["pnl_r"] is not None]
        result[key] = {
            "n": n,
            "wins": len(wins),
            "win_rate": len(wins) / n * 100 if n > 0 else 0.0,
            "expectancy_r": sum(r_values) / len(r_values) if r_values else 0.0,
        }
    return result


def compute_edge_presence_by_context(cycles: list[dict], group_key: str) -> dict[str, dict]:
    groups: dict[str, list] = defaultdict(list)
    for c in cycles:
        groups[c[group_key]].append(c)

    result = {}
    for bucket, bucket_cycles in sorted(groups.items()):
        total = len(bucket_cycles)
        edge = sum(1 for c in bucket_cycles if c["edge_present"])
        result[bucket] = {
            "total_cycles": total,
            "edge_cycles": edge,
            "no_edge_cycles": total - edge,
            "edge_rate_pct": edge / total * 100 if total > 0 else 0.0,
        }
    return result


def compute_activation_criteria(
    trades: list[dict],
    session_metrics: dict[str, dict],
    volatility_metrics: dict[str, dict],
) -> list[dict]:
    """Check activation criteria per bucket vs overall baseline."""
    all_wins = sum(1 for t in trades if t["win"])
    all_n = len(trades)
    baseline_wr = all_wins / all_n * 100 if all_n > 0 else 0.0
    baseline_losses = all_n - all_wins

    results = []
    all_buckets = {}
    for k, v in session_metrics.items():
        all_buckets[f"session:{k}"] = v
    for k, v in volatility_metrics.items():
        all_buckets[f"volatility:{k}"] = v

    for label, m in all_buckets.items():
        n_bucket = m["n"]
        wins_bucket = m["wins"]
        losses_bucket = m["losses"]
        wr_bucket = m["win_rate"]
        wr_delta = wr_bucket - baseline_wr

        # Chi-square: bucket vs rest
        rest_wins = all_wins - wins_bucket
        rest_losses = baseline_losses - losses_bucket
        rest_n = all_n - n_bucket
        p_val = chi2_pvalue_2x2(wins_bucket, losses_bucket, rest_wins, rest_losses)

        criteria_win_rate = wr_delta >= 10.0
        criteria_pvalue = p_val < 0.05
        activated = criteria_win_rate and criteria_pvalue

        results.append(
            {
                "bucket": label,
                "n": n_bucket,
                "win_rate": wr_bucket,
                "wr_delta_vs_baseline": wr_delta,
                "p_value": p_val,
                "criteria_win_rate_pass": criteria_win_rate,
                "criteria_pvalue_pass": criteria_pvalue,
                "activation_eligible": activated,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Markdown report generation
# ---------------------------------------------------------------------------
def _fmt_pct(v: float) -> str:
    return f"{v:.1f}%"


def _fmt_r(v: float) -> str:
    return f"{v:+.3f}R"


def _fmt_pf(v: float) -> str:
    if v == float("inf"):
        return "∞"
    return f"{v:.2f}"


def _fmt_p(v: float) -> str:
    if v >= 0.999:
        return ">0.99"
    if v < 0.001:
        return "<0.001"
    return f"{v:.3f}"


SESSION_ORDER = ["ASIA", "EU", "EU_US", "US", "UNKNOWN"]
VOLATILITY_ORDER = ["LOW", "NORMAL", "HIGH", "UNKNOWN"]


def generate_report(
    trades: list[dict],
    cycles: list[dict],
    session_metrics: dict,
    volatility_metrics: dict,
    matrix: dict,
    edge_by_session: dict,
    edge_by_volatility: dict,
    activation_results: list,
    since: str | None,
    db_path: str,
) -> str:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    n_trades = len(trades)
    n_cycles = len(cycles)
    all_wins = sum(1 for t in trades if t["win"])
    baseline_wr = all_wins / n_trades * 100 if n_trades > 0 else 0.0
    all_r = [t["pnl_r"] for t in trades if t["pnl_r"] is not None]
    baseline_expectancy = sum(all_r) / len(all_r) if all_r else 0.0

    lines = [
        f"# MODELING-V1-VALIDATION: Offline Retrospective Analysis",
        f"",
        f"> **Type:** OFFLINE RETROSPECTIVE — context reconstructed from historical data",
        f"> **NOT** runtime telemetry (context fields start populating after Modeling V1 deploy)",
        f"",
        f"**Date:** {date_str}",
        f"**DB:** `{db_path}`",
        f"**Since filter:** `{since or 'all time'}`",
        f"**Total closed trades analyzed:** {n_trades}",
        f"**Total decision cycles analyzed:** {n_cycles}",
        f"**Baseline win rate (all trades):** {_fmt_pct(baseline_wr)} ({all_wins}W / {n_trades - all_wins}L)",
        f"**Baseline expectancy:** {_fmt_r(baseline_expectancy)}",
        f"",
        f"**Context classification thresholds (mirrors ContextConfig defaults):**",
        f"- Session: ASIA 22:00–06:59 UTC | EU 07:00–13:59 | EU_US 14:00–15:59 | US 16:00–21:59",
        f"- Volatility LOW: atr_4h_norm < {ATR_LOW_THRESHOLD} | HIGH: > {ATR_HIGH_THRESHOLD} | NORMAL: between",
        f"",
        f"---",
        f"",
    ]

    # -----------------------------------------------------------------------
    # 1-4: Session metrics
    # -----------------------------------------------------------------------
    lines += [
        f"## 1–4. Trade Metrics by Session Bucket",
        f"",
        f"| Session | Trades | Wins | Win Rate | Expectancy R | Profit Factor |",
        f"|---------|--------|------|----------|--------------|---------------|",
    ]
    for s in SESSION_ORDER:
        if s in session_metrics:
            m = session_metrics[s]
            lines.append(
                f"| {s} | {m['n']} | {m['wins']} | {_fmt_pct(m['win_rate'])} "
                f"| {_fmt_r(m['expectancy_r'])} | {_fmt_pf(m['profit_factor'])} |"
            )
    lines += [
        f"| **BASELINE** | {n_trades} | {all_wins} | {_fmt_pct(baseline_wr)} "
        f"| {_fmt_r(baseline_expectancy)} | — |",
        f"",
    ]

    # -----------------------------------------------------------------------
    # 5-7: Volatility metrics
    # -----------------------------------------------------------------------
    lines += [
        f"## 5–7. Trade Metrics by Volatility Bucket",
        f"",
        f"| Volatility | Trades | Wins | Win Rate | Expectancy R | Profit Factor |",
        f"|------------|--------|------|----------|--------------|---------------|",
    ]
    for v in VOLATILITY_ORDER:
        if v in volatility_metrics:
            m = volatility_metrics[v]
            lines.append(
                f"| {v} | {m['n']} | {m['wins']} | {_fmt_pct(m['win_rate'])} "
                f"| {_fmt_r(m['expectancy_r'])} | {_fmt_pf(m['profit_factor'])} |"
            )
    lines += [f""]

    # -----------------------------------------------------------------------
    # 8: Session x Volatility matrix
    # -----------------------------------------------------------------------
    lines += [
        f"## 8. Session × Volatility Matrix (Win Rate)",
        f"",
        f"| Session \\ Volatility | LOW | NORMAL | HIGH |",
        f"|---------------------|-----|--------|------|",
    ]
    for s in SESSION_ORDER:
        if s == "UNKNOWN":
            continue
        cells = []
        for v in ["LOW", "NORMAL", "HIGH"]:
            key = (s, v)
            if key in matrix:
                m = matrix[key]
                cells.append(f"{_fmt_pct(m['win_rate'])} ({m['n']})")
            else:
                cells.append("—")
        lines.append(f"| {s} | {' | '.join(cells)} |")
    lines += [f""]

    # -----------------------------------------------------------------------
    # 9: Edge presence by context
    # -----------------------------------------------------------------------
    lines += [
        f"## 9. Base Edge Present vs No Edge by Context",
        f"",
        f"*Edge present = outcome_group in (signal_generated, governance_veto, risk_block, execution_failed)*",
        f"",
        f"### By Session",
        f"",
        f"| Session | Total Cycles | Edge Cycles | No-Edge Cycles | Edge Rate |",
        f"|---------|-------------|-------------|----------------|-----------|",
    ]
    for s in SESSION_ORDER:
        if s in edge_by_session:
            m = edge_by_session[s]
            lines.append(
                f"| {s} | {m['total_cycles']} | {m['edge_cycles']} "
                f"| {m['no_edge_cycles']} | {_fmt_pct(m['edge_rate_pct'])} |"
            )
    lines += [
        f"",
        f"### By Volatility",
        f"",
        f"| Volatility | Total Cycles | Edge Cycles | No-Edge Cycles | Edge Rate |",
        f"|------------|-------------|-------------|----------------|-----------|",
    ]
    for v in VOLATILITY_ORDER:
        if v in edge_by_volatility:
            m = edge_by_volatility[v]
            lines.append(
                f"| {v} | {m['total_cycles']} | {m['edge_cycles']} "
                f"| {m['no_edge_cycles']} | {_fmt_pct(m['edge_rate_pct'])} |"
            )
    lines += [f""]

    # -----------------------------------------------------------------------
    # 10: Activation criteria
    # -----------------------------------------------------------------------
    lines += [
        f"## 10. Activation Criteria Assessment",
        f"",
        f"**Criteria (from BLUEPRINT_MODELING_V1.md):**",
        f"- win_rate_delta ≥ 10.0 percentage points vs baseline",
        f"- p_value < 0.05 (chi-square test vs rest of trades)",
        f"- **Both** must pass to propose MODELING-V1-ACTIVATION milestone",
        f"",
        f"| Bucket | N | Win Rate | Δ vs Baseline | p-value | WR≥10pp | p<0.05 | Eligible |",
        f"|--------|---|----------|---------------|---------|---------|--------|---------|",
    ]
    eligible_buckets = []
    for r in sorted(activation_results, key=lambda x: -x["wr_delta_vs_baseline"]):
        wr_mark = "✅" if r["criteria_win_rate_pass"] else "❌"
        pv_mark = "✅" if r["criteria_pvalue_pass"] else "❌"
        elig_mark = "🟢 YES" if r["activation_eligible"] else "🔴 NO"
        if r["activation_eligible"]:
            eligible_buckets.append(r["bucket"])
        lines.append(
            f"| {r['bucket']} | {r['n']} | {_fmt_pct(r['win_rate'])} "
            f"| {r['wr_delta_vs_baseline']:+.1f}pp | {_fmt_p(r['p_value'])} "
            f"| {wr_mark} | {pv_mark} | {elig_mark} |"
        )
    lines += [f""]

    # -----------------------------------------------------------------------
    # Verdict
    # -----------------------------------------------------------------------
    lines += [f"## Verdict", f""]
    if not trades:
        lines += [
            f"⚠️ **INSUFFICIENT DATA** — no closed trades found in analyzed period.",
            f"Deploy Modeling V1, collect more trades, re-run analysis.",
        ]
    elif eligible_buckets:
        lines += [
            f"🟢 **ACTIVATION CRITERIA MET** for: {', '.join(eligible_buckets)}",
            f"",
            f"Both win_rate_delta ≥ 10pp AND p < 0.05 satisfied.",
            f"→ Propose **MODELING-V1-ACTIVATION** milestone for these buckets.",
            f"→ Define whitelist for eligible session/volatility combinations.",
            f"→ Keep `neutral_mode=True` until activation milestone is reviewed and approved.",
        ]
    else:
        lines += [
            f"🔴 **ACTIVATION CRITERIA NOT MET** — no bucket satisfies both conditions.",
            f"",
            f"→ Keep `neutral_mode=True` (no change to production config).",
            f"→ Collect more data, re-run after ~200 additional cycles.",
            f"→ Do NOT activate context blocking based on this analysis.",
        ]

    lines += [
        f"",
        f"---",
        f"",
        f"## Data Notes",
        f"",
        f"- Source: `trade_log.features_at_entry_json` (atr_4h_norm) + `trade_log.opened_at` (session UTC hour)",
        f"- Cycle analysis: `decision_outcomes` LEFT JOIN `feature_snapshots`",
        f"- Context classification uses same thresholds as `ContextConfig` defaults",
        f"- p-values: chi-square 2×2 (bucket vs rest), df=1",
        f"- Trades with missing `atr_4h_norm` assigned UNKNOWN volatility bucket",
        f"- This is retrospective analysis, NOT runtime telemetry",
        f"- Runtime context telemetry (from Modeling V1 deploy) will provide cleaner future data",
        f"",
        f"**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S')} UTC",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="MODELING-V1-VALIDATION offline analysis")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to btc_bot.db")
    parser.add_argument(
        "--since",
        default=None,
        help="Only include data from this date onwards (ISO format: 2026-01-01)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown path (default: docs/analysis/MODELING_V1_VALIDATION_YYYY-MM-DD.md)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    print(f"Loading trades from: {db_path}")
    trades = load_closed_trades(conn, args.since)
    print(f"  Closed trades: {len(trades)}")

    print("Loading decision cycles...")
    cycles = load_decision_cycles(conn, args.since)
    print(f"  Decision cycles: {len(cycles)}")

    conn.close()

    if not trades:
        print("WARNING: No closed trades found. Report will show insufficient data.")

    # Compute metrics
    session_metrics = compute_trade_metrics(trades, "session")
    volatility_metrics = compute_trade_metrics(trades, "volatility")
    matrix = compute_session_x_volatility_matrix(trades)
    edge_by_session = compute_edge_presence_by_context(cycles, "session")
    edge_by_volatility = compute_edge_presence_by_context(cycles, "volatility")
    activation_results = compute_activation_criteria(trades, session_metrics, volatility_metrics)

    report = generate_report(
        trades=trades,
        cycles=cycles,
        session_metrics=session_metrics,
        volatility_metrics=volatility_metrics,
        matrix=matrix,
        edge_by_session=edge_by_session,
        edge_by_volatility=edge_by_volatility,
        activation_results=activation_results,
        since=args.since,
        db_path=str(db_path),
    )

    # Determine output path
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if args.output:
        out_path = Path(args.output)
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / f"MODELING_V1_VALIDATION_{date_str}.md"

    out_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to: {out_path}")

    # Print summary to stdout
    all_wins = sum(1 for t in trades if t["win"])
    n = len(trades)
    print(f"\nSummary:")
    print(f"  Trades: {n}, Wins: {all_wins}, Baseline WR: {all_wins/n*100:.1f}%" if n else "  No trades.")
    for r in sorted(activation_results, key=lambda x: -x["wr_delta_vs_baseline"])[:5]:
        elig = "✅ ELIGIBLE" if r["activation_eligible"] else "❌"
        print(f"  {r['bucket']:30s} WR={r['win_rate']:.1f}% Δ={r['wr_delta_vs_baseline']:+.1f}pp p={_fmt_p(r['p_value'])} {elig}")


if __name__ == "__main__":
    main()

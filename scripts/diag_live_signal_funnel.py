"""
Read-only diagnostic: Live signal funnel analysis for trial-00095.

Queries production DB to build the full decision funnel:
  cycles -> no_sweep / sweep_too_shallow / no_reclaim / candidate / governance / risk / trade

Uses only columns that exist in production schema:
  - decision_outcomes: outcome_group, outcome_reason, regime, config_hash, details_json
  - signal_candidates: signal_id, timestamp, direction, setup_type, confluence_score, regime
  - trade_log: trade_id, opened_at, closed_at, direction, regime, pnl_r, exit_reason

Usage:
  python scripts/diag_live_signal_funnel.py [--since YYYY-MM-DD] [--db PATH]
"""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path("storage/btc_bot.db")
DEFAULT_SINCE = "2026-05-08"


def run(db_path: Path, since: str) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    results: dict = {"since": since, "db_path": str(db_path), "generated_at": datetime.now(timezone.utc).isoformat()}

    # --- 1. Total decision cycles ---
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM decision_outcomes WHERE cycle_timestamp >= ?",
        (since,),
    ).fetchone()
    total_cycles = row["cnt"]
    results["total_cycles"] = total_cycles

    # --- 2. Outcome reason breakdown ---
    rows = conn.execute(
        """SELECT outcome_reason, COUNT(*) as cnt 
           FROM decision_outcomes 
           WHERE cycle_timestamp >= ? 
           GROUP BY outcome_reason 
           ORDER BY cnt DESC""",
        (since,),
    ).fetchall()
    reason_breakdown = {r["outcome_reason"]: r["cnt"] for r in rows}
    results["outcome_reason_breakdown"] = reason_breakdown

    # --- 3. Outcome group breakdown ---
    rows = conn.execute(
        """SELECT outcome_group, COUNT(*) as cnt 
           FROM decision_outcomes 
           WHERE cycle_timestamp >= ? 
           GROUP BY outcome_group 
           ORDER BY cnt DESC""",
        (since,),
    ).fetchall()
    group_breakdown = {r["outcome_group"]: r["cnt"] for r in rows}
    results["outcome_group_breakdown"] = group_breakdown

    # --- 4. Regime distribution in decision cycles ---
    rows = conn.execute(
        """SELECT regime, COUNT(*) as cnt 
           FROM decision_outcomes 
           WHERE cycle_timestamp >= ? AND regime IS NOT NULL
           GROUP BY regime 
           ORDER BY cnt DESC""",
        (since,),
    ).fetchall()
    regime_dist = {r["regime"]: r["cnt"] for r in rows}
    results["regime_distribution"] = regime_dist

    # --- 5. Config hash verification ---
    rows = conn.execute(
        """SELECT config_hash, COUNT(*) as cnt 
           FROM decision_outcomes 
           WHERE cycle_timestamp >= ? 
           GROUP BY config_hash 
           ORDER BY cnt DESC""",
        (since,),
    ).fetchall()
    config_hashes = {r["config_hash"]: r["cnt"] for r in rows}
    results["config_hashes"] = config_hashes

    # --- 6. Signal candidates since deployment ---
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM signal_candidates WHERE timestamp >= ?",
        (since,),
    ).fetchone()
    results["signal_candidates_count"] = row["cnt"]

    rows = conn.execute(
        """SELECT signal_id, timestamp, direction, setup_type, confluence_score, regime
           FROM signal_candidates 
           WHERE timestamp >= ? 
           ORDER BY timestamp""",
        (since,),
    ).fetchall()
    results["signal_candidates"] = [dict(r) for r in rows]

    # --- 7. Trades since deployment ---
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM trade_log WHERE opened_at >= ?",
        (since,),
    ).fetchone()
    results["trades_count"] = row["cnt"]

    rows = conn.execute(
        """SELECT trade_id, signal_id, opened_at, closed_at, direction, regime, 
                  confluence_score, entry_price, exit_price, pnl_r, exit_reason
           FROM trade_log 
           WHERE opened_at >= ? 
           ORDER BY opened_at""",
        (since,),
    ).fetchall()
    results["trades"] = [dict(r) for r in rows]

    # --- 8. Cycles per day ---
    rows = conn.execute(
        """SELECT date(cycle_timestamp) as d, COUNT(*) as cnt
           FROM decision_outcomes 
           WHERE cycle_timestamp >= ? 
           GROUP BY d 
           ORDER BY d""",
        (since,),
    ).fetchall()
    results["cycles_per_day"] = {r["d"]: r["cnt"] for r in rows}

    # --- 9. sweep_too_shallow detail: regime distribution ---
    rows = conn.execute(
        """SELECT regime, COUNT(*) as cnt
           FROM decision_outcomes 
           WHERE cycle_timestamp >= ? AND outcome_reason = 'sweep_too_shallow'
           GROUP BY regime 
           ORDER BY cnt DESC""",
        (since,),
    ).fetchall()
    results["sweep_too_shallow_by_regime"] = {r["regime"]: r["cnt"] for r in rows}

    # --- 10. sweep_too_shallow: details_json — ALL rows (no LIMIT) ---
    rows = conn.execute(
        """SELECT details_json 
           FROM decision_outcomes 
           WHERE cycle_timestamp >= ? AND outcome_reason = 'sweep_too_shallow'
                 AND details_json IS NOT NULL
           ORDER BY cycle_timestamp""",
        (since,),
    ).fetchall()
    depths = []
    for r in rows:
        try:
            d = json.loads(r["details_json"])
            if "sweep_depth_pct" in d:
                depths.append(d["sweep_depth_pct"])
        except (json.JSONDecodeError, TypeError):
            pass
    results["sweep_too_shallow_depth_samples"] = depths
    if depths:
        results["sweep_depth_stats"] = {
            "count": len(depths),
            "min": min(depths),
            "max": max(depths),
            "mean": sum(depths) / len(depths),
            "median": sorted(depths)[len(depths) // 2],
        }

    # --- 11. Executable signals (governance-approved) ---
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM executable_signals WHERE timestamp >= ?",
        (since,),
    ).fetchone()
    results["executable_signals_count"] = row["cnt"]

    # --- 12. Governance veto details ---
    rows = conn.execute(
        """SELECT cycle_timestamp, regime, signal_id, details_json
           FROM decision_outcomes 
           WHERE cycle_timestamp >= ? AND outcome_reason = 'governance_veto'
           ORDER BY cycle_timestamp""",
        (since,),
    ).fetchall()
    results["governance_vetoes"] = [dict(r) for r in rows]

    # --- 13. Risk block details ---
    rows = conn.execute(
        """SELECT cycle_timestamp, regime, signal_id, details_json
           FROM decision_outcomes 
           WHERE cycle_timestamp >= ? AND outcome_reason = 'risk_block'
           ORDER BY cycle_timestamp""",
        (since,),
    ).fetchall()
    results["risk_blocks"] = [dict(r) for r in rows]

    conn.close()
    return results


def print_report(r: dict) -> None:
    print("=" * 70)
    print("LIVE SIGNAL FUNNEL DIAGNOSTIC")
    print(f"Since: {r['since']}  |  DB: {r['db_path']}")
    print(f"Generated: {r['generated_at']}")
    print("=" * 70)

    total = r["total_cycles"]
    print(f"\nTotal decision cycles: {total}")

    print(f"\n--- Outcome Reason Breakdown ---")
    for reason, cnt in sorted(r["outcome_reason_breakdown"].items(), key=lambda x: -x[1]):
        pct = cnt / total * 100 if total else 0
        print(f"  {reason:<35} {cnt:>5}  ({pct:5.1f}%)")

    print(f"\n--- Outcome Group Breakdown ---")
    for group, cnt in sorted(r["outcome_group_breakdown"].items(), key=lambda x: -x[1]):
        pct = cnt / total * 100 if total else 0
        print(f"  {group:<35} {cnt:>5}  ({pct:5.1f}%)")

    print(f"\n--- Regime Distribution (in cycles with regime) ---")
    for regime, cnt in sorted(r.get("regime_distribution", {}).items(), key=lambda x: -x[1]):
        print(f"  {regime:<25} {cnt:>5}")

    print(f"\n--- Config Hash Verification ---")
    for h, cnt in r["config_hashes"].items():
        print(f"  {h}: {cnt} cycles")

    # Funnel
    no_sweep = r["outcome_reason_breakdown"].get("no_sweep", 0)
    sweep_shallow = r["outcome_reason_breakdown"].get("sweep_too_shallow", 0)
    no_reclaim = r["outcome_reason_breakdown"].get("no_reclaim", 0)
    uptrend_weak = r["outcome_reason_breakdown"].get("uptrend_continuation_weak", 0)
    uptrend_pb_weak = r["outcome_reason_breakdown"].get("uptrend_pullback_weak", 0)
    direction_unresolved = r["outcome_reason_breakdown"].get("direction_unresolved", 0)
    regime_whitelist = r["outcome_reason_breakdown"].get("regime_direction_whitelist", 0)
    confluence_low = r["outcome_reason_breakdown"].get("confluence_below_min", 0)
    gov_veto = r["outcome_reason_breakdown"].get("governance_veto", 0)
    risk_block = r["outcome_reason_breakdown"].get("risk_block", 0)
    signal_gen = r["outcome_reason_breakdown"].get("signal_generated", 0)
    safe_skip = r["outcome_reason_breakdown"].get("safe_mode_skip", 0)
    snap_fail = r["outcome_reason_breakdown"].get("snapshot_failed", 0)

    sweep_layer = no_sweep + sweep_shallow
    reclaim_layer = no_reclaim + uptrend_weak + uptrend_pb_weak + direction_unresolved + regime_whitelist + confluence_low
    candidates = gov_veto + risk_block + signal_gen

    print(f"\n{'='*70}")
    print("DECISION FUNNEL")
    print(f"{'='*70}")
    print(f"  Total cycles:             {total:>5}")
    if snap_fail:
        print(f"  - snapshot_failed:        {snap_fail:>5}")
    if safe_skip:
        print(f"  - safe_mode_skip:         {safe_skip:>5}")
    print(f"  Sweep detection layer:    {sweep_layer:>5}  ({sweep_layer/total*100:.1f}% rejected)")
    print(f"    - no_sweep:             {no_sweep:>5}")
    print(f"    - sweep_too_shallow:    {sweep_shallow:>5}")
    print(f"  Reclaim / direction layer:{reclaim_layer:>5}  ({reclaim_layer/total*100:.1f}% rejected)")
    if no_reclaim:
        print(f"    - no_reclaim:           {no_reclaim:>5}")
    if uptrend_weak:
        print(f"    - uptrend_cont_weak:    {uptrend_weak:>5}")
    if uptrend_pb_weak:
        print(f"    - uptrend_pb_weak:      {uptrend_pb_weak:>5}")
    if direction_unresolved:
        print(f"    - direction_unresolved: {direction_unresolved:>5}")
    if regime_whitelist:
        print(f"    - regime_whitelist:     {regime_whitelist:>5}")
    if confluence_low:
        print(f"    - confluence_below_min: {confluence_low:>5}")
    print(f"  Signal candidates:        {candidates:>5}  ({candidates/total*100:.1f}% pass signal layer)")
    print(f"    - governance_veto:      {gov_veto:>5}")
    print(f"    - risk_block:           {risk_block:>5}")
    print(f"    - signal_generated:     {signal_gen:>5}  -> TRADE EXECUTED")
    print()

    print(f"Signal candidates in DB: {r['signal_candidates_count']}")
    for sc in r["signal_candidates"]:
        print(f"  {sc['timestamp']} | {sc['direction']} | {sc['regime']} | conf={sc['confluence_score']}")

    print(f"\nExecutable signals in DB: {r['executable_signals_count']}")

    print(f"\nTrades: {r['trades_count']}")
    for t in r["trades"]:
        print(f"  {t['opened_at']} -> {t['closed_at']} | {t['direction']} | {t['regime']} | pnl_r={t['pnl_r']} | {t['exit_reason']}")

    if r.get("governance_vetoes"):
        print(f"\nGovernance vetoes:")
        for gv in r["governance_vetoes"]:
            print(f"  {gv['cycle_timestamp']} | regime={gv['regime']} | signal={gv['signal_id']} | {gv['details_json']}")

    if r.get("risk_blocks"):
        print(f"\nRisk blocks:")
        for rb in r["risk_blocks"]:
            print(f"  {rb['cycle_timestamp']} | regime={rb['regime']} | signal={rb['signal_id']} | {rb['details_json']}")

    if r.get("sweep_too_shallow_by_regime"):
        print(f"\nsweep_too_shallow by regime:")
        for regime, cnt in sorted(r["sweep_too_shallow_by_regime"].items(), key=lambda x: -x[1]):
            print(f"  {regime:<25} {cnt:>5}")

    if r.get("sweep_depth_stats"):
        s = r["sweep_depth_stats"]
        print(f"\nsweep_depth_pct from ALL sweep_too_shallow cycles ({s['count']} rows):")
        print(f"  min={s['min']:.4f}  max={s['max']:.4f}  mean={s['mean']:.4f}  median={s['median']:.4f}")
        if r.get("sweep_too_shallow_depth_samples"):
            depths = sorted(r["sweep_too_shallow_depth_samples"])
            print(f"  all values: {[round(d, 4) for d in depths]}")

    print(f"\n--- Cycles per day ---")
    for d, cnt in sorted(r.get("cycles_per_day", {}).items()):
        print(f"  {d}: {cnt}")

    print(f"\n{'='*70}")
    print("END DIAGNOSTIC")
    print(f"{'='*70}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live signal funnel diagnostic")
    parser.add_argument("--since", default=DEFAULT_SINCE, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to btc_bot.db")
    args = parser.parse_args()
    result = run(Path(args.db), args.since)
    print_report(result)

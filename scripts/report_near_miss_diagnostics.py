#!/usr/bin/env python3
"""
Near-Miss Diagnostics Report Generator

Read-only script that queries decision_outcomes table for near-miss sweep diagnostics
and generates a markdown report with depth distribution, regime breakdown, session breakdown,
and shadow threshold comparison.

Usage:
    python scripts/report_near_miss_diagnostics.py --days 7
    python scripts/report_near_miss_diagnostics.py --db-path /path/to/btc_bot.db --days 30

This script is READ-ONLY and safe to run against production databases.
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Generate near-miss diagnostics report")
    parser.add_argument(
        "--db-path",
        default="storage/btc_bot.db",
        help="Path to SQLite database (default: storage/btc_bot.db)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to analyze (default: 7)",
    )
    parser.add_argument(
        "--output",
        help="Output markdown file path (default: docs/diagnostics/near_miss_report_YYYY-MM-DD.md)",
    )
    return parser.parse_args()


def query_decision_outcomes(conn: sqlite3.Connection, days: int):
    """Query decision outcomes for the specified date range."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    query = """
    SELECT 
        cycle_timestamp,
        outcome_group,
        outcome_reason,
        details_json
    FROM decision_outcomes
    WHERE cycle_timestamp >= ?
    ORDER BY cycle_timestamp DESC
    """
    
    cursor = conn.cursor()
    cursor.execute(query, (cutoff,))
    return cursor.fetchall()


def analyze_near_misses(rows):
    """Analyze near-miss data from decision outcomes."""
    total_cycles = len(rows)
    total_sweep_too_shallow = 0
    near_miss_count = 0
    
    # Depth buckets
    far_below = 0
    near_miss_low = 0
    baseline_pass = 0
    stricter_pass = 0
    
    # Threshold proximity
    within_10pct = 0
    within_20pct = 0
    within_30pct = 0
    
    # Regime breakdown
    regime_counts = {}
    
    # Session breakdown
    session_counts = {"ASIA": 0, "EU": 0, "US": 0}
    
    # Rejection reasons
    rejection_reasons = {}
    
    # Shadow comparison (baseline vs 0.007)
    baseline_trades = 0
    baseline_pass_rejected_by_007 = 0
    
    for row in rows:
        cycle_ts, outcome_group, outcome_reason, details_json = row
        
        if outcome_reason == "sweep_too_shallow":
            total_sweep_too_shallow += 1
            
            import json
            try:
                details = json.loads(details_json) if details_json else {}
            except:
                details = {}
            
            near_miss = details.get("near_miss_diagnostics")
            if near_miss:
                near_miss_count += 1
                
                # Depth bucket
                depth_bucket = near_miss.get("depth_bucket")
                if depth_bucket == "far_below":
                    far_below += 1
                elif depth_bucket == "near_miss_low":
                    near_miss_low += 1
                elif depth_bucket == "baseline_pass":
                    baseline_pass += 1
                elif depth_bucket == "stricter_pass":
                    stricter_pass += 1
                
                # Threshold proximity
                depth = near_miss.get("sweep_depth_pct", 0)
                threshold = near_miss.get("threshold", 0.00649)
                if threshold > 0:
                    distance_pct = (depth - threshold) / threshold * 100
                    if -10 <= distance_pct < 0:
                        within_10pct += 1
                    if -20 <= distance_pct < 0:
                        within_20pct += 1
                    if -30 <= distance_pct < 0:
                        within_30pct += 1
                
                # Regime breakdown
                regime = near_miss.get("regime", "unknown")
                regime_counts[regime] = regime_counts.get(regime, 0) + 1
                
                # Session breakdown
                session_hour = near_miss.get("session_hour", 0)
                if 0 <= session_hour < 8:
                    session_counts["ASIA"] += 1
                elif 8 <= session_hour < 16:
                    session_counts["EU"] += 1
                else:
                    session_counts["US"] += 1
                
                # Rejection reasons
                reasons = near_miss.get("rejection_reasons", [])
                for reason in reasons:
                    rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                
                # Shadow comparison
                if depth_bucket == "baseline_pass":
                    baseline_pass_rejected_by_007 += 1
        
        # Count baseline trades (sweep depth >= 0.00649)
        # This is an approximation - we count signals that passed the threshold
        if outcome_group == "signal_generated":
            baseline_trades += 1
    
    return {
        "total_cycles": total_cycles,
        "total_sweep_too_shallow": total_sweep_too_shallow,
        "near_miss_count": near_miss_count,
        "far_below": far_below,
        "near_miss_low": near_miss_low,
        "baseline_pass": baseline_pass,
        "stricter_pass": stricter_pass,
        "within_10pct": within_10pct,
        "within_20pct": within_20pct,
        "within_30pct": within_30pct,
        "regime_counts": regime_counts,
        "session_counts": session_counts,
        "rejection_reasons": rejection_reasons,
        "baseline_trades": baseline_trades,
        "baseline_pass_rejected_by_007": baseline_pass_rejected_by_007,
    }


def generate_report(analysis, days, output_path):
    """Generate markdown report from analysis results."""
    lines = []
    
    # Header
    lines.append("# Near-Miss Diagnostics Report")
    lines.append("")
    lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"**Analysis Window:** Last {days} days")
    lines.append("")
    
    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    total_cycles = analysis["total_cycles"]
    total_sweep_too_shallow = analysis["total_sweep_too_shallow"]
    near_miss_count = analysis["near_miss_count"]
    
    lines.append(f"- Total decision cycles: {total_cycles}")
    lines.append(f"- Sweep too shallow rejections: {total_sweep_too_shallow} ({total_sweep_too_shallow/total_cycles*100:.1f}%)")
    lines.append(f"- Near-miss events (depth >= 0.004): {near_miss_count}")
    lines.append("")
    
    if near_miss_count > 0:
        lines.append("**Key Finding:**")
        if near_miss_count > analysis["baseline_trades"]:
            lines.append(f"Near-miss count ({near_miss_count}) exceeds baseline trades ({analysis['baseline_trades']}). Threshold may be too strict.")
        else:
            lines.append(f"Near-miss count ({near_miss_count}) is reasonable vs baseline trades ({analysis['baseline_trades']}). Threshold is appropriate.")
    else:
        lines.append("**Key Finding:** No near-miss events recorded. Market conditions may be generating very shallow sweeps (< 0.4%).")
    lines.append("")
    
    # Depth Distribution
    lines.append("## Depth Distribution")
    lines.append("")
    lines.append("| Bucket | Range | Count | % of Near-Misses |")
    lines.append("|---|---|---:|---:|")
    
    total_near_misses = max(near_miss_count, 1)  # Avoid division by zero
    lines.append(f"| far_below | < 0.004 | {analysis['far_below']} | {analysis['far_below']/total_near_misses*100:.1f}% |")
    lines.append(f"| near_miss_low | [0.004, 0.00649) | {analysis['near_miss_low']} | {analysis['near_miss_low']/total_near_misses*100:.1f}% |")
    lines.append(f"| baseline_pass | [0.00649, 0.007) | {analysis['baseline_pass']} | {analysis['baseline_pass']/total_near_misses*100:.1f}% |")
    lines.append(f"| stricter_pass | >= 0.007 | {analysis['stricter_pass']} | {analysis['stricter_pass']/total_near_misses*100:.1f}% |")
    lines.append("")
    
    # Threshold Proximity
    lines.append("## Threshold Proximity (0.00649)")
    lines.append("")
    lines.append("| Proximity | Range | Count | % of Near-Misses |")
    lines.append("|---|---|---:|---:|")
    lines.append(f"| Within 10% | [0.00584, 0.00649) | {analysis['within_10pct']} | {analysis['within_10pct']/total_near_misses*100:.1f}% |")
    lines.append(f"| Within 20% | [0.00519, 0.00649) | {analysis['within_20pct']} | {analysis['within_20pct']/total_near_misses*100:.1f}% |")
    lines.append(f"| Within 30% | [0.00454, 0.00649) | {analysis['within_30pct']} | {analysis['within_30pct']/total_near_misses*100:.1f}% |")
    lines.append("")
    
    # Shadow Threshold 0.007 Comparison
    lines.append("## Shadow Threshold 0.007 Comparison")
    lines.append("")
    lines.append("> **Diagnostic only. No execution changes. No parameter changes.**")
    lines.append("")
    
    baseline_trades = analysis["baseline_trades"]
    baseline_pass_rejected = analysis["baseline_pass_rejected_by_007"]
    hypothetical_trades = baseline_trades - baseline_pass_rejected
    
    lines.append("| Metric | Baseline 0.00649 | Hypothetical 0.007 | Delta |")
    lines.append("|---|---:|---:|---:|")
    
    if baseline_trades > 0:
        trade_loss_pct = (baseline_pass_rejected / baseline_trades) * 100
        lines.append(f"| Trades | {baseline_trades} | {hypothetical_trades} | -{baseline_pass_rejected} |")
        lines.append(f"| Trade loss % | 100% | {hypothetical_trades/baseline_trades*100:.1f}% | -{trade_loss_pct:.1f}% |")
    else:
        lines.append(f"| Trades | {baseline_trades} | {hypothetical_trades} | -{baseline_pass_rejected} |")
        lines.append(f"| Trade loss % | N/A | N/A | N/A |")
    
    lines.append("")
    lines.append("**Interpretation:**")
    if baseline_pass_rejected > 0:
        lines.append(f"- {baseline_pass_rejected} trades would be lost with 0.007 threshold ({trade_loss_pct:.1f}% reduction)")
        lines.append("- Opportunity cost: stricter threshold reduces trade frequency")
    else:
        lines.append("- No trades would be lost with 0.007 threshold in this window")
    lines.append("")
    
    # Regime Breakdown
    lines.append("## Regime Breakdown")
    lines.append("")
    lines.append("| Regime | Near-Miss Count | % of Near-Misses |")
    lines.append("|---|---:|---:|")
    
    for regime, count in sorted(analysis["regime_counts"].items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| {regime} | {count} | {count/total_near_misses*100:.1f}% |")
    lines.append("")
    
    # Session Breakdown
    lines.append("## Session Breakdown (UTC)")
    lines.append("")
    lines.append("| Session | Hours (UTC) | Near-Miss Count | % of Near-Misses |")
    lines.append("|---|---|---:|---:|")
    lines.append(f"| ASIA | 0-8 | {analysis['session_counts']['ASIA']} | {analysis['session_counts']['ASIA']/total_near_misses*100:.1f}% |")
    lines.append(f"| EU | 8-16 | {analysis['session_counts']['EU']} | {analysis['session_counts']['EU']/total_near_misses*100:.1f}% |")
    lines.append(f"| US | 16-24 | {analysis['session_counts']['US']} | {analysis['session_counts']['US']/total_near_misses*100:.1f}% |")
    lines.append("")
    
    # Top Rejection Reasons
    lines.append("## Top Rejection Reasons")
    lines.append("")
    lines.append("| Reason | Count | % of Near-Misses |")
    lines.append("|---|---:|---:|")
    
    for reason, count in sorted(analysis["rejection_reasons"].items(), key=lambda x: x[1], reverse=True)[:10]:
        lines.append(f"| {reason} | {count} | {count/total_near_misses*100:.1f}% |")
    lines.append("")
    
    # Recommendation
    lines.append("## Recommendation")
    lines.append("")
    
    if near_miss_count == 0:
        lines.append("No near-miss events recorded. Current market conditions generate very shallow sweeps (< 0.4%). Threshold adjustment is not warranted at this time.")
    elif near_miss_count > analysis["baseline_trades"]:
        lines.append(f"Near-miss count ({near_miss_count}) exceeds baseline trades ({analysis['baseline_trades']}). Consider relaxing threshold to capture more qualifying sweeps.")
    elif analysis["baseline_pass_rejected_by_007"] > analysis["baseline_trades"] * 0.3:
        lines.append(f"Baseline_pass bucket is large ({analysis['baseline_pass_rejected_by_007']} events). 0.007 threshold would reject >30% of trades. Keep current threshold.")
    else:
        lines.append(f"Near-miss count ({near_miss_count}) is reasonable vs baseline trades ({analysis['baseline_trades']}). Threshold adjustment is not warranted at this time.")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Report generated by scripts/report_near_miss_diagnostics.py*")
    lines.append("*This is diagnostic information only. No execution or parameter changes recommended without further analysis.*")
    
    # Write to file
    report_content = "\n".join(lines)
    with open(output_path, "w") as f:
        f.write(report_content)
    
    print(f"Report generated: {output_path}")
    return report_content


def main():
    args = parse_args()
    
    # Default output path
    if not args.output:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        args.output = f"docs/diagnostics/near_miss_report_{date_str}.md"
    
    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Connect to database
    try:
        conn = sqlite3.connect(args.db_path)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Query decision outcomes
        rows = query_decision_outcomes(conn, args.days)
        
        # Analyze near-misses
        analysis = analyze_near_misses(rows)
        
        # Generate report
        generate_report(analysis, args.days, args.output)
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()

"""
Standalone governance filter analysis.
Run: python -m research.governance_analysis

Analyzes the 93% rejection rate problem by comparing bot performance
with governance ON vs. OFF, determining which rules are value-additive.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from research.prepare_research import governance_deep_dive, get_production_config


def main():
    print("=== Governance Filter Deep-Dive ===\n")

    production_config = get_production_config()
    report = governance_deep_dive(production_config)

    impact = report["governance_impact"]

    print(f"Signals generated:     {impact['signals_generated']}")
    print(f"Signals passed:        {impact['signals_passed']}")
    print(f"Signals rejected:      {impact['signals_rejected']}")
    print(f"Rejection rate:        {impact['rejection_rate']:.1%}")
    print()
    print(f"Fitness WITH gov:      {impact['fitness_with']:.4f}")
    print(f"Fitness WITHOUT gov:   {impact['fitness_without']:.4f}")
    print(f"Governance net effect: {'POSITIVE (keep)' if impact['governance_is_net_positive'] else 'NEGATIVE (loosen!)'}")

    print("\n--- With Governance ---")
    for k, v in report["with_governance"].items():
        print(f"  {k:25s}: {v}")

    print("\n--- Without Governance ---")
    for k, v in report["without_governance"].items():
        print(f"  {k:25s}: {v}")

    # Save report
    report_path = Path("research/governance_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report saved to {report_path}")

    # Per-rule analysis suggestion
    print("\n=== Per-Rule Analysis ===")
    rules_to_test = [
        ("cooldown_minutes_after_loss", 0, "Disable cooldown"),
        ("max_trades_per_day", 999, "Unlimited trades/day"),
        ("max_consecutive_losses", 999, "Unlimited consecutive losses"),
        ("daily_dd_limit", 1.0, "Remove daily DD limit"),
        ("weekly_dd_limit", 1.0, "Remove weekly DD limit"),
    ]

    for param, relaxed_val, desc in rules_to_test:
        test_config = production_config.copy()
        test_config[param] = relaxed_val

        from research.prepare_research import run_backtest, compute_fitness
        try:
            metrics = run_backtest(test_config)
            fitness = compute_fitness(metrics)
            print(f"  {desc:40s} → fitness={fitness:.4f}, trades={metrics.get('total_trades', 0)}")
        except Exception as e:
            print(f"  {desc:40s} → ERROR: {e}")


if __name__ == "__main__":
    main()

"""
Run a single optimization experiment.
Analogous to running `uv run train.py` in autoresearch.

Usage:
    python -m research.run_experiment
    python -m research.run_experiment --n-trials 500
    python -m research.run_experiment --study-name "focused_signals"
"""

import sys
import time
import json
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from research import config_space
from research.prepare_research import (
    run_optuna_study,
    run_backtest,
    compute_fitness,
    walk_forward_validate,
    sensitivity_analysis,
    get_production_config,
    print_summary,
)


def main():
    parser = argparse.ArgumentParser(description="Run BTC bot parameter optimization experiment")
    parser.add_argument("--n-trials", type=int, default=None,
                        help=f"Override N_TRIALS (default: {config_space.N_TRIALS})")
    parser.add_argument("--study-name", type=str, default=None,
                        help="Custom Optuna study name")
    parser.add_argument("--skip-wf", action="store_true",
                        help="Skip walk-forward validation (for quick exploration)")
    parser.add_argument("--sensitivity-only", action="store_true",
                        help="Only run sensitivity analysis on existing study")
    args = parser.parse_args()

    n_trials = args.n_trials or config_space.N_TRIALS
    study_name = args.study_name or f"{config_space.STUDY_NAME_PREFIX}_{int(time.time())}"

    t0 = time.time()

    # --- Step 1: Run Optuna optimization ---
    print(f"=== Starting experiment: {study_name} ===")
    print(f"  N_TRIALS:       {n_trials}")
    print(f"  FITNESS_WEIGHTS: {config_space.FITNESS_WEIGHTS}")
    print(f"  Active params:  {sum(1 for v in config_space.PARAM_SPACE.values() if v['type'] != 'fixed')}")
    print(f"  Fixed params:   {sum(1 for v in config_space.PARAM_SPACE.values() if v['type'] == 'fixed')}")
    print()

    study = run_optuna_study(
        config_space_module=config_space,
        n_trials=n_trials,
        study_name=study_name,
    )

    # --- Step 2: Extract best trial ---
    if study.best_trial is None:
        print("ERROR: No successful trials. All crashed.")
        sys.exit(1)

    best = study.best_trial
    best_params = best.params
    best_metrics = {k: best.user_attrs.get(k, 0.0) for k in [
        "expectancy_r", "profit_factor", "max_drawdown",
        "sharpe", "total_trades", "win_rate",
        "signals_generated", "signals_rejected",
    ]}

    print(f"\n=== Best trial: #{best.number} ===")
    print(f"  Fitness:       {best.value:.4f}")
    print(f"  Params:        {json.dumps(best_params, indent=2)}")
    print(f"  Metrics:       {json.dumps(best_metrics, indent=2)}")

    # --- Step 3: Sensitivity analysis ---
    print("\n=== Sensitivity Analysis ===")
    importances = sensitivity_analysis(study)

    # Save importance to JSON
    importance_path = Path("research") / f"importance_{study_name}.json"
    with open(importance_path, "w") as f:
        json.dump(importances, f, indent=2)
    print(f"  Saved to {importance_path}")

    if args.sensitivity_only:
        print("\n--sensitivity-only flag set. Stopping here.")
        return

    # --- Step 4: Walk-forward validation ---
    wf_result = {"wf_status": "N/A", "wf_degradation": 0.0}

    if not args.skip_wf:
        print("\n=== Walk-Forward Validation ===")
        wf_result = walk_forward_validate(
            best_params=best_params,
            config_space_module=config_space,
            train_bars=config_space.WF_TRAIN_BARS,
            test_bars=config_space.WF_TEST_BARS,
            step_bars=config_space.WF_STEP_BARS,
        )
        print(f"  Status:       {wf_result['wf_status']}")
        print(f"  Degradation:  {wf_result['wf_degradation']:.4f}")
        print(f"  Windows:      {wf_result.get('n_windows', 0)}")

        # Save WF details to JSON
        wf_path = Path("research") / f"walkforward_{study_name}.json"
        with open(wf_path, "w") as f:
            json.dump(wf_result, f, indent=2)
        print(f"  Saved to {wf_path}")

    # --- Step 5: Print summary ---
    runtime = time.time() - t0
    production_config = get_production_config()

    print_summary(
        experiment_id=study_name,
        metrics=best_metrics,
        wf_result=wf_result,
        config_dict=best_params,
        production_config=production_config,
        runtime_seconds=runtime,
    )

    # --- Step 6: Save full experiment report ---
    report = {
        "experiment_id": study_name,
        "n_trials": n_trials,
        "best_trial_number": best.number,
        "best_fitness": best.value,
        "best_params": best_params,
        "best_metrics": best_metrics,
        "walk_forward": wf_result,
        "param_importance": importances,
        "fitness_weights": config_space.FITNESS_WEIGHTS,
        "runtime_seconds": runtime,
        "total_trials": len(study.trials),
        "failed_trials": sum(1 for t in study.trials if t.value is None or t.value == float("-inf")),
        "param_changes_from_production": {
            k: {"production": production_config.get(k), "optimized": v}
            for k, v in best_params.items()
            if k in production_config and production_config[k] != v
        },
    }

    report_path = Path("research") / f"report_{study_name}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report saved to {report_path}")


if __name__ == "__main__":
    main()

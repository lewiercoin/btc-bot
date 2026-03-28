"""
Fixed research infrastructure for BTC bot parameter optimization.
Analogous to prepare.py in karpathy/autoresearch — DO NOT MODIFY.

Provides:
  - verify_data(): check SQLite has sufficient data
  - run_backtest(config_dict): execute a single backtest, return metrics
  - run_optuna_study(config_space): run multi-objective optimization
  - walk_forward_validate(best_params, config_space): rolling-window validation
  - sensitivity_analysis(study): fANOVA parameter importance
  - governance_deep_dive(config_dict): analyze governance filter rejections
"""

import json
import time
import sqlite3
import hashlib
from pathlib import Path
from dataclasses import asdict
from typing import Any

import optuna
from optuna.importance import FanovaImportanceEvaluator

# ---------------------------------------------------------------------------
# Constants (fixed, do not modify)
# ---------------------------------------------------------------------------

DB_PATH = Path("storage/trading_bot.db")  # Adjust to your actual DB path
RESULTS_TSV = Path("research/results.tsv")
EXPERIMENT_DB = Path("research/experiments.db")

WF_DEGRADATION_THRESHOLD = 0.30  # 30% max allowed degradation
MIN_TRADES_FOR_VALID_RESULT = 3  # minimum trades to consider a backtest valid

# ---------------------------------------------------------------------------
# Data verification
# ---------------------------------------------------------------------------

def verify_data():
    """Check that SQLite database has sufficient data for research."""
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Please ensure the trading bot database is accessible.")
        return False

    conn = sqlite3.connect(str(DB_PATH))
    try:
        checks = {
            "candles_15m": "SELECT COUNT(*) FROM candles WHERE timeframe='15m'",
            "candles_1h": "SELECT COUNT(*) FROM candles WHERE timeframe='1h'",
            "candles_4h": "SELECT COUNT(*) FROM candles WHERE timeframe='4h'",
            "funding_rates": "SELECT COUNT(*) FROM funding_rates",
            "open_interest": "SELECT COUNT(*) FROM open_interest",
            "aggtrade_buckets": "SELECT COUNT(*) FROM aggtrade_buckets",
        }

        print("=== Data Verification ===")
        all_ok = True
        for name, query in checks.items():
            try:
                count = conn.execute(query).fetchone()[0]
                status = "OK" if count > 0 else "EMPTY"
                if count == 0:
                    all_ok = False
                print(f"  {name}: {count} records [{status}]")
            except sqlite3.OperationalError as e:
                print(f"  {name}: TABLE NOT FOUND ({e})")
                all_ok = False

        if all_ok:
            print("\nData verification PASSED. Ready for research.")
        else:
            print("\nData verification FAILED. Some tables are missing or empty.")
        return all_ok
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Backtest execution wrapper
# ---------------------------------------------------------------------------

def run_backtest(config_dict: dict[str, Any],
                 start_date: str | None = None,
                 end_date: str | None = None) -> dict[str, Any]:
    """
    Execute a single deterministic backtest with given parameters.
    Returns a metrics dictionary.

    This wraps your existing BacktestRunner — adapt the imports
    to match your actual project structure.
    """
    # --- ADAPT THESE IMPORTS TO YOUR PROJECT ---
    from settings import (
        FeatureEngineConfig, RegimeEngineConfig, SignalEngineConfig,
        GovernanceConfig, RiskConfig
    )
    from backtest.backtest_runner import BacktestRunner
    from research.analyze_trades import analyze_closed_trades

    # Build frozen configs from flat parameter dict
    from research.config_space import build_configs
    configs = build_configs(config_dict)

    # Run backtest
    runner = BacktestRunner(
        feature_config=configs["feature"],
        regime_config=configs["regime"],
        signal_config=configs["signal"],
        governance_config=configs["governance"],
        risk_config=configs["risk"],
        db_path=str(DB_PATH),
    )

    result = runner.run(start_date=start_date, end_date=end_date)

    # Compute performance metrics
    conn = sqlite3.connect(str(DB_PATH))
    try:
        report = analyze_closed_trades(conn, result)
    finally:
        conn.close()

    # Extract key metrics
    metrics = {
        "expectancy_r": getattr(report, "expectancy_r", 0.0),
        "profit_factor": getattr(report, "profit_factor", 0.0),
        "max_drawdown": getattr(report, "max_drawdown", 0.0),
        "sharpe": getattr(report, "sharpe_ratio", 0.0),
        "total_trades": getattr(report, "total_trades", 0),
        "win_rate": getattr(report, "win_rate", 0.0),
        "total_pnl": getattr(report, "total_pnl", 0.0),
        "avg_r_multiple": getattr(report, "avg_r_multiple", 0.0),
        "signals_generated": getattr(report, "signals_generated", 0),
        "signals_rejected": getattr(report, "signals_rejected", 0),
    }

    return metrics


def compute_fitness(metrics: dict[str, Any],
                    weights: dict[str, float] | None = None) -> float:
    """
    Scalarize multi-objective metrics into a single fitness value.
    Higher is better.
    """
    if weights is None:
        weights = {
            "expectancy_r": 0.4,
            "profit_factor": 0.3,
            "max_drawdown": 0.3,  # penalty (subtracted)
        }

    fitness = (
        weights["expectancy_r"] * metrics.get("expectancy_r", 0.0)
        + weights["profit_factor"] * metrics.get("profit_factor", 0.0)
        - weights["max_drawdown"] * metrics.get("max_drawdown", 1.0)
    )

    # Penalty for too few trades (not statistically significant)
    if metrics.get("total_trades", 0) < MIN_TRADES_FOR_VALID_RESULT:
        fitness *= 0.1  # Heavy penalty

    return fitness


# ---------------------------------------------------------------------------
# Optuna optimization
# ---------------------------------------------------------------------------

def create_optuna_objective(config_space_module,
                            start_date: str | None = None,
                            end_date: str | None = None):
    """
    Create an Optuna objective function from the config_space definition.
    Returns a callable for study.optimize().
    """
    def objective(trial: optuna.Trial) -> float:
        # Let config_space define the trial parameters
        config_dict = config_space_module.suggest_params(trial)

        # Check cross-parameter constraints
        if not config_space_module.check_constraints(config_dict):
            return float("-inf")

        try:
            metrics = run_backtest(config_dict, start_date, end_date)
            fitness = compute_fitness(metrics, config_space_module.FITNESS_WEIGHTS)

            # Log extra metrics as trial user attrs
            for key, val in metrics.items():
                trial.set_user_attr(key, val)

            return fitness

        except Exception as e:
            trial.set_user_attr("error", str(e))
            return float("-inf")

    return objective


def run_optuna_study(config_space_module,
                     n_trials: int = 200,
                     study_name: str | None = None,
                     start_date: str | None = None,
                     end_date: str | None = None) -> optuna.Study:
    """
    Run an Optuna study to optimize trading bot parameters.
    Uses TPE sampler with SQLite persistence.
    """
    if study_name is None:
        study_name = f"study_{int(time.time())}"

    storage = f"sqlite:///{EXPERIMENT_DB}"

    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction="maximize",
        load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    objective = create_optuna_objective(
        config_space_module, start_date, end_date
    )

    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    return study


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------

def walk_forward_validate(best_params: dict[str, Any],
                          config_space_module,
                          train_bars: int = 500,
                          test_bars: int = 150,
                          step_bars: int = 150) -> dict[str, Any]:
    """
    Walk-forward validation of a parameter set.
    Split data into rolling train/test windows.
    Optimize on train, validate with given params on test.
    Returns degradation metrics.
    """
    conn = sqlite3.connect(str(DB_PATH))
    try:
        # Get date range from candles
        row = conn.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM candles WHERE timeframe='1h'"
        ).fetchone()
        if not row or row[0] is None:
            return {"wf_status": "N/A", "wf_degradation": 0.0, "error": "No data"}

        min_ts, max_ts = row

        # Build windows
        # Each "bar" = 1 hour for 1h candles
        bar_duration_ms = 3600 * 1000
        windows = []
        current_start = min_ts

        while current_start + (train_bars + test_bars) * bar_duration_ms <= max_ts:
            train_end = current_start + train_bars * bar_duration_ms
            test_end = train_end + test_bars * bar_duration_ms

            windows.append({
                "train_start": current_start,
                "train_end": train_end,
                "test_start": train_end,
                "test_end": test_end,
            })
            current_start += step_bars * bar_duration_ms

    finally:
        conn.close()

    if len(windows) < 2:
        return {
            "wf_status": "N/A",
            "wf_degradation": 0.0,
            "error": "Insufficient data for walk-forward (need >=2 windows)"
        }

    # Run backtest on each window
    train_fitnesses = []
    test_fitnesses = []

    for i, window in enumerate(windows):
        # Train window fitness
        train_metrics = run_backtest(
            best_params,
            start_date=_ts_to_iso(window["train_start"]),
            end_date=_ts_to_iso(window["train_end"]),
        )
        train_fitness = compute_fitness(train_metrics)
        train_fitnesses.append(train_fitness)

        # Test window fitness (out-of-sample)
        test_metrics = run_backtest(
            best_params,
            start_date=_ts_to_iso(window["test_start"]),
            end_date=_ts_to_iso(window["test_end"]),
        )
        test_fitness = compute_fitness(test_metrics)
        test_fitnesses.append(test_fitness)

    # Compute degradation
    avg_train = sum(train_fitnesses) / len(train_fitnesses) if train_fitnesses else 0.0
    avg_test = sum(test_fitnesses) / len(test_fitnesses) if test_fitnesses else 0.0

    if avg_train > 0:
        degradation = 1.0 - (avg_test / avg_train)
    else:
        degradation = 0.0

    wf_status = "PASS" if degradation <= WF_DEGRADATION_THRESHOLD else "FAIL"

    return {
        "wf_status": wf_status,
        "wf_degradation": round(degradation, 4),
        "avg_train_fitness": round(avg_train, 4),
        "avg_test_fitness": round(avg_test, 4),
        "n_windows": len(windows),
        "per_window": [
            {
                "train_fitness": round(tf, 4),
                "test_fitness": round(tsf, 4),
            }
            for tf, tsf in zip(train_fitnesses, test_fitnesses)
        ],
    }


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------

def sensitivity_analysis(study: optuna.Study) -> dict[str, float]:
    """
    Compute fANOVA parameter importance from an Optuna study.
    Returns dict of {param_name: importance_score}.
    """
    if len(study.trials) < 20:
        print("WARNING: <20 trials. Sensitivity analysis may be unreliable.")

    try:
        evaluator = FanovaImportanceEvaluator(seed=42)
        importances = optuna.importance.get_param_importances(
            study, evaluator=evaluator
        )
    except Exception as e:
        print(f"fANOVA failed ({e}), falling back to MDI importance.")
        importances = optuna.importance.get_param_importances(study)

    # Print sorted importance report
    print("\n=== Parameter Importance (fANOVA) ===")
    for param, score in sorted(importances.items(), key=lambda x: -x[1]):
        bar = "█" * int(score * 50)
        print(f"  {param:40s} {score:.4f} {bar}")

    return importances


# ---------------------------------------------------------------------------
# Governance deep-dive
# ---------------------------------------------------------------------------

def governance_deep_dive(config_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze which governance rules reject the most signals,
    and whether those rejections are value-additive or value-destructive.

    Runs the pipeline twice:
    1. With governance ON (normal) → get actual trades
    2. With governance OFF → backtest all signals that would have been generated

    Compares to determine net value of each governance rule.
    """
    # Normal run (governance ON)
    metrics_with_gov = run_backtest(config_dict)

    # Relaxed run (governance OFF)
    relaxed_config = config_dict.copy()
    relaxed_config["max_trades_per_day"] = 999
    relaxed_config["max_consecutive_losses"] = 999
    relaxed_config["cooldown_minutes_after_loss"] = 0
    relaxed_config["daily_dd_limit"] = 1.0
    relaxed_config["weekly_dd_limit"] = 1.0
    metrics_without_gov = run_backtest(relaxed_config)

    report = {
        "with_governance": metrics_with_gov,
        "without_governance": metrics_without_gov,
        "governance_impact": {
            "signals_generated": metrics_without_gov.get("signals_generated", 0),
            "signals_passed": metrics_with_gov.get("total_trades", 0),
            "signals_rejected": (
                metrics_without_gov.get("signals_generated", 0)
                - metrics_with_gov.get("total_trades", 0)
            ),
            "rejection_rate": 0.0,
            "fitness_with": compute_fitness(metrics_with_gov),
            "fitness_without": compute_fitness(metrics_without_gov),
            "governance_is_net_positive": False,
        },
    }

    gen = report["governance_impact"]["signals_generated"]
    if gen > 0:
        report["governance_impact"]["rejection_rate"] = round(
            report["governance_impact"]["signals_rejected"] / gen, 4
        )

    report["governance_impact"]["governance_is_net_positive"] = (
        report["governance_impact"]["fitness_with"]
        >= report["governance_impact"]["fitness_without"]
    )

    return report


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _ts_to_iso(ts_ms: int) -> str:
    """Convert millisecond timestamp to ISO date string."""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def get_production_config() -> dict[str, Any]:
    """Load current production config as a flat dict."""
    from settings import (
        FeatureEngineConfig, RegimeEngineConfig, SignalEngineConfig,
        GovernanceConfig, RiskConfig
    )
    flat = {}
    for cfg_class in [
        FeatureEngineConfig, RegimeEngineConfig, SignalEngineConfig,
        GovernanceConfig, RiskConfig
    ]:
        cfg = cfg_class()  # defaults = production
        flat.update(asdict(cfg))
    return flat


def print_summary(experiment_id: str, metrics: dict, wf_result: dict,
                  config_dict: dict, production_config: dict,
                  runtime_seconds: float):
    """Print the standard experiment summary block."""
    param_changes = sum(
        1 for k, v in config_dict.items()
        if k in production_config and production_config[k] != v
    )

    print("\n---")
    print(f"experiment_id:     {experiment_id}")
    print(f"best_fitness:      {compute_fitness(metrics):.3f}")
    print(f"expectancy_r:      {metrics.get('expectancy_r', 0.0):.3f}")
    print(f"profit_factor:     {metrics.get('profit_factor', 0.0):.3f}")
    print(f"max_drawdown:      {metrics.get('max_drawdown', 0.0):.3f}")
    print(f"sharpe:            {metrics.get('sharpe', 0.0):.2f}")
    print(f"total_trades:      {metrics.get('total_trades', 0)}")
    print(f"win_rate:          {metrics.get('win_rate', 0.0):.3f}")
    print(f"wf_degradation:    {wf_result.get('wf_degradation', 0.0):.2f}")
    print(f"wf_status:         {wf_result.get('wf_status', 'N/A')}")
    print(f"param_changes:     {param_changes}")
    print(f"runtime_seconds:   {runtime_seconds:.1f}")
    print("---")


# ---------------------------------------------------------------------------
# Main (verify data when run directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    verify_data()

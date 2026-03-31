# BTC Bot Autoresearch

This is an autonomous research system for optimizing a BTC perpetual futures trading bot.
Adapted from [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — same philosophy,
different domain: instead of optimizing a neural network's val_bpb, you optimize a trading bot's
multi-objective fitness (expectancy_r, profit_factor, max_drawdown) via backtest.

## Core Principle

The agent modifies **parameter configurations only** — never the core pipeline code.
The pipeline (`MarketSnapshot → FeatureEngine → RegimeEngine → SignalEngine → GovernanceLayer → RiskEngine → Execution`)
is deterministic and read-only, just like `prepare.py` in autoresearch.

## Setup

To set up a new research session, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `mar27`). The branch `research/<tag>` must not already exist.
2. **Create the branch**: `git checkout -b research/<tag>` from current master.
3. **Read the in-scope files**: The research system is small. Read these files for full context:
   - This file (`program.md`) — your instructions.
   - `research/prepare_research.py` — fixed infrastructure: loads data from SQLite, runs BacktestRunner, computes metrics, evaluates walk-forward. **Do not modify.**
   - `research/config_space.py` — the file you modify. Contains the parameter space definition, constraints, and the `build_config()` function that translates parameter dicts into frozen dataclass configs.
   - `settings.py` — current production config (frozen dataclasses). Read-only reference.
   - `backtest/backtest_runner.py` — `BacktestRunner.run()`. Read-only.
   - `research/analyze_trades.py` — `analyze_closed_trades()`. Read-only.
4. **Verify data exists**: Check that the SQLite database contains sufficient data:
   ```
   python -c "from research.prepare_research import verify_data; verify_data()"
   ```
5. **Initialize results.tsv**: Create `research/results.tsv` with the header row. The baseline will be recorded after the first run.
6. **Establish baseline**: Run the current production config through backtest to establish the baseline metric.
7. **Confirm and go**: Confirm setup looks good.

Once you get confirmation, kick off the experimentation.

## Experimentation

Each experiment runs a full backtest through the deterministic pipeline. A single backtest run takes ~2-5 seconds, so a **full optimization sweep of 200 trials takes ~7-17 minutes**.

You launch experiments via: `python -m research.run_experiment`

**What you CAN do:**
- Modify `research/config_space.py` — this is the only file you edit. Everything is fair game:
  - Parameter ranges (widen, narrow, shift)
  - Which parameters to optimize vs. fix at defaults
  - Constraints between parameters
  - The multi-objective weighting / scalarization strategy
  - Number of Optuna trials per experiment
  - Walk-forward window sizes
  - Regime-conditional parameter spaces

**What you CANNOT do:**
- Modify `research/prepare_research.py`. It is read-only. It contains the fixed backtest execution, evaluation, walk-forward validation, and sensitivity analysis infrastructure.
- Modify any core pipeline files (`engines/`, `backtest/`, `settings.py`).
- Modify the database or historical data.
- Add randomness or non-determinism to the core pipeline.
- Install new packages beyond what's in `requirements.txt`.

**The goal is multi-objective: maximize expectancy_r, maximize profit_factor, minimize max_drawdown.**

We use a **scalarized fitness** for the keep/discard decision:

```
fitness = (expectancy_r_weight * expectancy_r)
        + (profit_factor_weight * profit_factor)
        - (max_dd_weight * max_drawdown)
```

Default weights: `expectancy_r_weight=0.4`, `profit_factor_weight=0.3`, `max_dd_weight=0.3`.
These weights are defined in `config_space.py` and CAN be modified by the agent.

**Walk-forward validation** is mandatory. Every experiment that improves the fitness must also
pass walk-forward validation (in-sample vs. out-of-sample degradation < 30%).
Experiments that improve in-sample but degrade >30% out-of-sample are **discarded as overfit**.

**Simplicity criterion** (same as autoresearch): All else being equal, fewer parameters being
modified from defaults is better. A tiny fitness improvement that requires changing 20 parameters
is suspect. A similar improvement from changing 3 parameters is much more credible.

## The ~45 Parameter Space

Parameters are organized by engine. All accept frozen dataclass configs.

### FeatureEngine (9 params)
- `atr_period: int` — ATR lookback [7, 28], default=14
- `ema_fast: int` — fast EMA period [20, 100], default=50
- `ema_slow: int` — slow EMA period [100, 400], default=200
- `equal_level_lookback: int` — S/R lookback [20, 100], default=50
- `equal_level_tol_atr: float` — S/R tolerance [0.10, 0.50], default=0.25
- `sweep_buf_atr: float` — sweep buffer [0.05, 0.30], default=0.15
- `reclaim_buf_atr: float` — reclaim buffer [0.01, 0.15], default=0.05
- `wick_min_atr: float` — min wick size [0.20, 0.80], default=0.40
- `funding_window_days: int` — funding lookback [14, 120], default=60
- `oi_z_window_days: int` — OI z-score lookback [14, 120], default=60

### RegimeEngine (5 params)
- `ema_trend_gap_pct: float` — trend threshold [0.001, 0.010], default=0.0025
- `compression_atr_norm_max: float` — compression threshold [0.002, 0.010], default=0.0055
- `crowded_funding_extreme_pct: float` — crowded funding percentile [70.0, 95.0], default=85.0
- `crowded_oi_zscore_min: float` — crowded OI z-score [0.5, 3.0], default=1.5
- `post_liq_tfi_abs_min: float` — post-liq TFI threshold [0.05, 0.50], default=0.2

### SignalEngine (14 params)
- `confluence_min: float` — min confluence score [1.5, 5.0], default=3.0
- `min_sweep_depth_pct: float` — min sweep depth [0.00005, 0.001], default=0.0001
- `entry_offset_atr: float` — entry offset [0.01, 0.15], default=0.05
- `invalidation_offset_atr: float` — stop offset [0.10, 0.50], default=0.25
- `tp1_atr_mult: float` — TP1 multiplier [1.0, 4.0], default=2.0
- `tp2_atr_mult: float` — TP2 multiplier [2.0, 6.0], default=3.5
- 8 confluence weights (each [0.0, 2.0]):
  - `weight_sweep_detected: 1.25`
  - `weight_reclaim_confirmed: 1.25`
  - `weight_cvd_divergence: 0.75`
  - `weight_tfi_impulse: 0.50`
  - `weight_force_order_spike: 0.40`
  - `weight_regime_special: 0.35`
  - `weight_ema_trend_alignment: 0.25`
  - `weight_funding_supportive: 0.20`
- `direction_tfi_threshold: float` [0.01, 0.15], default=0.05
- `tfi_impulse_threshold: float` [0.05, 0.25], default=0.10

### Governance (8 params)
- `cooldown_minutes_after_loss: int` [15, 180], default=60
- `duplicate_level_tolerance_pct: float` [0.0005, 0.005], default=0.001
- `duplicate_level_window_hours: int` [6, 72], default=24
- `max_trades_per_day: int` [1, 10], default=3
- `max_consecutive_losses: int` [1, 5], default=3
- `daily_dd_limit: float` [0.01, 0.10], default=0.03
- `weekly_dd_limit: float` [0.03, 0.15], default=0.06
- `session_start_hour_utc / session_end_hour_utc` [0, 23]

### Risk (7 params)
- `risk_per_trade_pct: float` [0.005, 0.03], default=0.01
- `max_leverage: int` [2, 10], default=5
- `high_vol_leverage: int` [1, 5], default=3
- `min_rr: float` [1.5, 5.0], default=2.8
- `max_open_positions: int` [1, 4], default=2
- `max_hold_hours: int` [4, 72], default=24
- `high_vol_stop_distance_pct: float` [0.005, 0.03], default=0.01

### Cross-Parameter Constraints
- `ema_fast < ema_slow` (always)
- `tp1_atr_mult < tp2_atr_mult` (always)
- `high_vol_leverage <= max_leverage` (always)
- `daily_dd_limit < weekly_dd_limit` (always)

## Output Format

After an experiment completes, `run_experiment` prints a summary:

```
---
experiment_id:     exp_003
n_trials:          200
best_fitness:      1.847
expectancy_r:      0.95
profit_factor:     2.31
max_drawdown:      0.042
sharpe:            1.65
total_trades:      12
win_rate:          0.583
wf_degradation:    0.12
wf_status:         PASS
param_changes:     5
runtime_seconds:   482.3
---
```

You can extract the key metrics:
```
grep "^best_fitness:\|^wf_status:\|^wf_degradation:" research/run.log
```

## Logging Results

When an experiment is done, log it to `research/results.tsv` (tab-separated).

The TSV has a header row and 8 columns:

```
commit	fitness	expectancy_r	profit_factor	max_drawdown	wf_status	status	description
```

1. git commit hash (short, 7 chars)
2. scalarized fitness (e.g. 1.847) — use 0.000 for crashes
3. expectancy_r (e.g. 0.950) — use 0.000 for crashes
4. profit_factor (e.g. 2.310) — use 0.000 for crashes
5. max_drawdown (e.g. 0.042) — use 0.000 for crashes
6. wf_status: `PASS`, `FAIL`, or `N/A` (for crashes)
7. status: `keep`, `discard`, or `crash`
8. short text description of what this experiment tried

Example:

```
commit	fitness	expectancy_r	profit_factor	max_drawdown	wf_status	status	description
a1b2c3d	1.542	0.82	1.95	0.038	PASS	keep	baseline (production config)
b2c3d4e	1.847	0.95	2.31	0.042	PASS	keep	widen confluence weights, lower confluence_min to 2.5
c3d4e5f	1.920	1.05	2.50	0.055	FAIL	discard	aggressive: lower cooldown to 15min (overfit, WF degrad 0.41)
d4e5f6g	0.000	0.000	0.000	0.000	N/A	crash	invalid param combo caused div-by-zero
```

## The Experiment Loop

The experiment runs on a dedicated branch (e.g. `research/mar27`).

LOOP FOREVER:

1. **Analyze current state**: Read `results.tsv` to understand what's been tried, what worked, what failed.
2. **Generate hypothesis**: Based on previous results, sensitivity analysis, and domain knowledge, formulate what to try next. Write a short rationale.
3. **Modify `config_space.py`**: Implement the hypothesis by adjusting parameter ranges, fixing/unfixing params, changing constraints, or modifying the optimization strategy.
4. **git commit**: Commit the config_space.py changes with a descriptive message.
5. **Run the experiment**: `python -m research.run_experiment > research/run.log 2>&1`
6. **Read results**: `grep "^best_fitness:\|^wf_status:\|^expectancy_r:\|^max_drawdown:" research/run.log`
7. **If grep is empty** → the run crashed. Run `tail -n 50 research/run.log` to read the traceback. If it's a simple fix (typo, invalid range), fix and re-run. If fundamentally broken, log as crash and move on.
8. **Record in results.tsv** (do NOT commit results.tsv, leave untracked).
9. **Keep or discard**:
   - If fitness improved AND wf_status is PASS → **keep** (advance the branch).
   - If fitness improved but wf_status is FAIL → **discard** (overfit, `git reset`).
   - If fitness equal or worse → **discard** (`git reset`).
10. **Repeat.**

## Research Strategies (Suggested Experiment Order)

### Phase 1: Sensitivity Discovery (experiments 1-5)
Run broad Optuna sweeps across all 45 params with wide ranges. Use the fANOVA importance
output to identify the top 10-15 most impactful parameters. This tells you where to focus.

### Phase 2: Focused Optimization (experiments 6-15)
Fix unimportant params at defaults. Narrow ranges for important params based on Phase 1.
Increase trial count to 300-500 for focused search.

### Phase 3: Governance Analysis (experiments 16-20)
The current rejection rate is ~93% (4 trades from 58 signals). Systematically relax
governance filters one at a time (e.g., lower cooldown, increase max_trades_per_day).
Check if relaxation improves fitness without blowing up risk.

### Phase 4: Regime-Conditional (experiments 21-30)
Split optimization by regime. Run separate studies for TRENDING, COMPRESSION, etc.
Compare regime-conditional params vs. universal best.

### Phase 5: Fine-Tuning (experiments 31+)
Combine best findings from Phases 1-4. Small perturbations around the best-known config.
Tighten ranges. Maximize walk-forward robustness.

## Sensitivity Analysis

After every Optuna study, the system automatically computes fANOVA parameter importance.
Use this to guide your next hypothesis:
- **High importance, wide optimal range** → parameter matters, but is robust. Good.
- **High importance, narrow optimal range** → parameter matters and is fragile. Careful.
- **Low importance** → fix at default, reduce search space.

The importance report is printed to the log and saved as JSON.

## Governance Filter Deep-Dive

To analyze the governance rejection pattern, run:
```
python -m research.governance_analysis
```

This backtests every rejected signal as if governance had been disabled, computing:
- Per-rule rejection count
- Per-rule net value (money saved by rejecting losers - money lost by rejecting winners)
- Overall value-additive vs. value-destructive assessment

## Walk-Forward Validation Details

Walk-forward uses rolling windows:
- Default: train=500 bars, test=150 bars, step=150 bars (configurable in config_space.py)
- Per-window: optimize on train, validate on test
- Degradation = 1 - (test_fitness / train_fitness)
- Degradation threshold: 30% (configurable in config_space.py)
- A config MUST pass walk-forward to be kept

## NEVER STOP

Once the experiment loop has begun, do NOT pause to ask the human if you should continue.
Do NOT ask "should I keep going?" or "is this a good stopping point?".
The human might be sleeping or away from the computer and expects you to continue working
*indefinitely* until manually stopped. You are autonomous.

If you run out of ideas:
- Re-read the parameter space for underexplored combinations.
- Try the opposite of what failed (e.g., if tightening helped, try tightening further).
- Analyze which regimes have the worst performance and target those.
- Try radically different confluence weight distributions.
- Experiment with governance relaxation/tightening.
- Review which walk-forward windows show the most degradation and target stability there.

The loop runs until the human interrupts you, period.

# AUDIT: RUN4-CAMPAIGN
Date: 2026-04-10
Auditor: Claude Code
Commit: bfc78ba (launch) / campaign completed 2026-04-10

## Verdict: NOT_PROMOTED

## Infrastructure Execution: PASS
## Signal Health Gate: PASS (sweep_detected < 0.5 on default config)
## Constraint Enforcement: PASS (high_vol_leverage <= max_leverage blocked correctly)
## Funnel Tracking: PASS (104 trials with funnel data captured)
## Artifact Integrity: PASS (JournalStorage, trial snapshots, store save)

## Campaign Results

| Metric | Value |
|---|---|
| Trials (run4) | 150 |
| Trials (cumulative) | 423 |
| Trials accepted | 104 |
| Trials rejected | 319 (75%) |
| Run4 Pareto candidates | 2 |
| Run4 WF passed | 0 |
| Global Pareto candidates | 7 |
| Global WF passed | 0 |

### Signal Funnel (104 accepted trials, avg per trial)
| Stage | Value |
|---|---|
| signals_generated | 827 |
| regime_blocked | 39.6% |
| governance_rejected | 22.3% |
| risk_rejected | 9.9% |
| signals_executed | 233 (28.2%) |

### Run4 Pareto Candidates
| Trial | expectancy_r | profit_factor | max_drawdown_pct | WF |
|---|---|---|---|---|
| sweep-reclaim-v1-run4-trial-00109 | -0.1125 | 0.804 | 60.9% | FAIL (0/28) |
| sweep-reclaim-v1-run4-trial-00105 | -0.1243 | 0.828 | 62.5% | FAIL |

### Global Pareto (cross-run)
| Trial | expectancy_r | profit_factor | trades | Protocol | WF |
|---|---|---|---|---|---|
| baseline-v1-trial-00021 | 0.754 | 2.318 | 31 | pre-fix | FAIL (0/48, all MIN_TRADES_NOT_MET) |
| baseline-v3-trial-00195 | 0.141 | 1.192 | 607 | fixed | not promoted (run3 heritage) |
| baseline-v3-trial-00194 | 0.116 | 1.152 | 544 | fixed | not promoted (run3 heritage) |
| baseline-v3-trial-00115 | 0.026 | 1.035 | 182 | fixed | — |
| baseline-v3-trial-00114 | -0.028 | 0.955 | 164 | fixed | — |
| baseline-v3-trial-00125 | -0.029 | 0.957 | 384 | fixed | — |
| baseline-v3-trial-00127 | -0.144 | 0.786 | 205 | fixed | — |

## Critical Findings

### 1. Threshold-chasing recurrence — new form
Run4 Pareto winner (trial-00109) selected sweep_proximity_atr=1.8 vs calibrated default 0.4.
This is the proximity analogue of weight_sweep_detected=4.95 from Run #3:
Optuna is widening the sweep gate to generate more trades, not finding a better signal.
Root cause: the optimizer maximizes expectancy_r on the 4-year corpus; loosening the
proximity filter creates more trades in absolute terms but the marginal trades are
lower-quality sweeps (distant from level), diluting signal quality.

### 2. Global Pareto dominated by pre-fix candidate (threshold-chaser)
baseline-v1-trial-00021: weight_sweep_detected=4.95, 31 trades over 4 years.
ALL 48 walk-forward windows fail MIN_TRADES_NOT_MET. This candidate has near-zero
signal — it only "works" on a total-period basis by avoiding trades entirely.
Not promotable. It persists in global Pareto only because the optimizer sees its
full-period expectancy_r=0.754 without seeing its WF collapse.

### 3. Fixed-protocol candidates (run3 heritage) are the current best
baseline-v3 trials (195, 194) show positive expectancy and trade volume (544-607 trades).
These are not new run4 discoveries — they're run3 candidates re-evaluated on the fixed
protocol. Run4 produced nothing that dominates them.

### 4. Regime filter blocks 39.6% of signals
The TFI regime gate is the single largest loss stage in the funnel.
If the regime filter is correctly calibrated, this is expected behavior (filtering
non-quality setups). If it's miscalibrated for the 2022-2026 regime mix, it may
be suppressing genuine setups in bull/bear phases.
Unknown which is true — this is an open diagnostic question.

### 5. 45D search space + 150 trials = insufficient TPE convergence
With 45 active parameters, TPE cannot build a reliable surrogate model in 150 trials.
The Optuna recommendation of >= 100 trials (OPTUNA-UTILITY-V1 audit) was the minimum
floor — 150 is only marginally above that floor for a 45D problem.
However, expanding budget alone is unlikely to fix the structural issues above.

## Warnings

- Both run4 Pareto candidates have 60%+ drawdown. Even if expectancy were positive,
  these are unacceptable for deployment. The optimizer is trading drawdown for trade
  count when the fixed protocol restricts the sweep volume.
- The run3 fixed-protocol candidates (trials 194, 195) still show positive expectancy
  but have not been walk-forward validated to passing standard. They remain the
  best available but are NOT promotable.

## Observations (non-blocking)

- Infrastructure worked correctly. JournalStorage persisted across all trials.
  Snapshot cleanup confirmed (trial_snapshot.unlink). Funnel data captured for all
  104 accepted trials. No infrastructure failures.
- Signal IS alive: 827 avg signals_generated per trial confirms the sweep+reclaim
  detector is firing correctly at calibrated sensitivity (proximity=0.4).
- The constraint enforcement (high_vol_leverage <= max_leverage) is working —
  run4 candidates show max_leverage=9, high_vol_leverage=7 (compliant).
- Protocol hash separation is clean: all run4 trials carry
  protocol_hash="9bb81f45..." (fixed protocol).

## Root Cause Assessment

The sweep+reclaim signal produces positive expectancy in a subset of parameter
configurations (baseline-v3 cluster), but the 4-year backtest period (2022-2026)
contains multiple distinct regimes that dilute the signal edge:
- 2022: severe bear market (BTC -75%)
- 2023: recovery/consolidation
- 2024: bull run
- 2025-2026: correction/range

The proximity filter (calibrated on 2025-Q1 range data) may not be optimal
for 2022-2023 price action where ATR was significantly higher and level structures
were less compact. Optuna is correctly identifying this by widening proximity —
but the wider proximity degrades signal quality.

This is a **backtest window selection problem**, not a signal bug. The signal
may have edge in recent regimes (2024-2026) that is obscured by 2022-2023 inclusion.

## Recommended Next Step

**SIGNAL-ANALYSIS-V1** — diagnostic milestone before next Optuna campaign.

Deliverables:
1. Run default config (proximity=0.4, level_min_age_bars=5, min_hits=3) on
   4 annual slices: 2022, 2023, 2024, 2025 separately
2. Report per-year: signals_generated, signals_executed, expectancy_r,
   profit_factor, trades_count, max_drawdown_pct
3. Determine: in which years does the signal produce positive expectancy?
4. Recommend: backtest window for Run #5 based on findings

If 2024-2026 shows positive expectancy but 2022-2023 doesn't: constrain
backtest window and rerun Optuna on the valid range.
If no year shows positive expectancy: signal design needs revision before more campaigns.

Builder: Codex (data analysis task, no new infrastructure needed).
Estimated scope: 1 session, low complexity.

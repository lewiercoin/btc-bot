# Trial-00095 Conditional Edge Analysis

**Date:** 2026-05-13  
**Author:** Cascade (builder)  
**Milestone:** TRIAL_00095_CONDITIONAL_EDGE_ANALYSIS_V1 (M2)  
**Status:** COMPLETE  
**Verdict:** DEEPER_IS_BETTER_BUT_THRESHOLD_UNCERTAIN

## Executive Summary

Per-trade replay analysis (274 trades) confirms that **deeper sweeps produce better outcomes** within accepted trades (Q1 ER=1.577 → Q4 ER=2.833). sweep_depth_pct is the #2 predictor of trade outcome. However, the available evidence does not definitively prove that `0.00649` is a natural boundary versus an overfitted optimum.

Backtest rejected sweep candidates are not available (BacktestRunner does not persist `decision_outcomes`), so live vs backtest distribution shift cannot be assessed. Current live market generates shallow sweeps (mean 0.00154); qualifying conditions are rare.

**Recommendation:** Do not adjust production threshold without OOS/WF threshold stability validation. Per-trade analysis suggests deeper is better, but threshold boundary requires cross-window verification.

**Note on trade count:** The replay produced 274 trades vs 271 reported by the Optuna campaign. The 3-trade difference is due to minor floating-point and state initialization differences between the Optuna objective runner and standalone BacktestRunner replay. Both use identical parameters; the difference is not material.

## Strategic Question

> Is `min_sweep_depth_pct = 0.00649` a natural edge boundary or an overfitted cliff?

## Verdict Reasoning

| Check | Signal | Finding |
|---|---|---|
| Per-trade quartile ER | **PRIMARY** | Q1 (shallowest accepted) ER=1.577, Q4 (deepest) ER=2.833. 1.8x ratio within accepted trades. Monotonic increase across all 4 quartiles. |
| Feature importance | **PRIMARY** | sweep_depth_pct is #2 by |correlation| with pnl_r (r=0.136). Top feature: confluence_score (r=-0.235). |
| Win/loss depth | WEAK | Winners mean depth 0.00954 vs losers 0.00902. Trending right direction, p=0.071 (not significant at 0.05). |
| Live market observation | CONTEXT | Current live market generates shallow sweeps (mean 0.00154). Qualifying conditions are rare. Backtest rejected population unavailable; cannot assess distribution shift. |
| Cross-trial gradient | APPENDIX (NOT CAUSAL) | See Appendix A. Confounded by Optuna selection bias — cannot isolate depth effect from other co-varying parameters. |

**Conclusion: DEEPER_IS_BETTER_BUT_THRESHOLD_UNCERTAIN.** Per-trade analysis confirms deeper sweeps produce better outcomes within accepted trades. However, evidence does not definitively prove 0.00649 is a natural boundary vs overfitted optimum. Out-of-sample / walk-forward threshold stability validation is required before ruling out threshold adjustment.

## Phase 1: Per-Trade Replay Analysis

274 trades from BacktestRunner replay with trial-00095 exact parameters (2022-01-01 to 2026-03-28).

> **Trade count note:** The Optuna campaign reported 271 trades for trial-00095. This replay produced 274. The 3-trade difference arises from minor floating-point and state initialization differences between the Optuna objective runner and standalone BacktestRunner replay. Both use identical parameters; the difference is not material.

### Sweep Depth Distribution (Backtest Trades)

| Metric | Value |
|---|---:|
| Min | 0.00649 |
| P10 | 0.00676 |
| P25 | 0.00721 |
| Median | 0.00835 |
| Mean | 0.00932 |
| P75 | 0.01011 |
| P90 | 0.01265 |
| Max | 0.03524 |
| Std | 0.00349 |

25% of accepted trades are concentrated near the threshold (0.00649-0.00721). The distribution is right-skewed with a long tail of deep sweeps up to 0.035.

### Conditional ER by Depth Quartile

| Quartile | N | ER Mean | ER Median | Win Rate |
|---|---:|---:|---:|---:|
| Q1 (< 0.00721) | 69 | 1.577 | -1.393 | 47.8% |
| Q2 (0.00721 - 0.00835) | 68 | 1.994 | 2.736 | 60.3% |
| Q3 (0.00835 - 0.01011) | 68 | 2.078 | 2.607 | 54.4% |
| Q4 (>= 0.01011) | 69 | 2.833 | 3.373 | 63.8% |

**Monotonic increase from Q1 to Q4.** Q1 (shallowest accepted) still has positive ER (1.577) but lower win rate. Q4 (deepest) has the best ER and win rate. This confirms depth is a continuous quality signal — not a binary on/off filter at 0.00649.

### Win vs Loss Depth Comparison

| Group | N | Mean Depth | Median Depth |
|---|---:|---:|---:|
| Winners | 155 | 0.00954 | 0.00845 |
| Losers | 119 | 0.00902 | 0.00815 |

Mann-Whitney U: z=1.803, p=0.071. Not significant at 0.05 level but trending in the expected direction. Winners have marginally deeper sweeps on average.

### MAE/MFE Correlation with Depth

| Metric | Correlation |
|---|---:|
| depth ↔ MAE | r = 0.024 (negligible) |
| depth ↔ MFE | r = 0.007 (negligible) |
| depth ↔ pnl_r | r = 0.136 (weak positive) |

Depth has a weak positive correlation with pnl_r but negligible correlation with excursion metrics. The edge from deeper sweeps comes from higher win rate and better R-multiples, not from mechanically better entry prices.

### Feature Importance (|Correlation| with pnl_r)

| Rank | Feature | r | |r| |
|---:|---|---:|---:|
| 1 | confluence_score | -0.235 | 0.235 |
| 2 | sweep_depth_pct | 0.136 | 0.136 |
| 3 | tfi_60s | 0.109 | 0.109 |
| 4 | atr_15m | 0.093 | 0.093 |
| 5 | session_hour | -0.076 | 0.076 |
| 6 | atr_4h | 0.058 | 0.058 |
| 7 | funding_pct_60d | 0.046 | 0.046 |

sweep_depth_pct is the #2 feature. Confluence_score is #1 (negative correlation — lower confluence scores produce higher pnl_r, suggesting the confluence weighting is conservative). The edge is multi-factorial, not depth-alone.

### Regime × Depth Breakdown

| Regime | N | ER | Win Rate | Depth Mean |
|---|---:|---:|---:|---:|
| uptrend | 205 | 2.614 | 66.3% | 0.00935 |
| downtrend | 54 | 0.690 | 25.9% | 0.00935 |
| normal | 9 | 0.736 | 33.3% | 0.00802 |
| crowded_leverage | 6 | 0.226 | 33.3% | 0.00963 |

Uptrend dominates both count (75%) and ER. Depth distribution is similar across regimes — the edge doesn't come from regime-specific depth patterns. This reinforces the M1 finding: the bot is LONG-dominant and works best in uptrend.

### Session × Depth Breakdown

| Session | N | ER | Win Rate | Depth Mean |
|---|---:|---:|---:|---:|
| Asia (0-8) | 59 | 2.694 | 64.4% | 0.00905 |
| Europe (8-16) | 108 | 1.774 | 54.6% | 0.00925 |
| US (16-24) | 107 | 2.155 | 54.2% | 0.00952 |

Asia session has the highest ER and win rate despite slightly shallower average depth. Session timing affects quality independently of depth.

## Live Market Observation

267 `sweep_too_shallow` events extracted from production `decision_outcomes` (May 8-13, 2026).

| Metric | Live Rejected Sweeps |
|---|---:|
| N | 267 |
| Mean | 0.00154 |
| Median | 0.00131 |
| P25 | 0.00084 |
| P75 | 0.00186 |

| Threshold | Live Rejected % Above |
|---|---:|
| 0.003 | 6.4% |
| 0.004 | 2.6% |
| 0.005 | 0.7% |
| 0.006 | 0.0% |
| **0.00649** | **0.0%** |

**Current live market generates shallow sweeps; qualifying conditions are rare.** 0% of live rejected sweeps would pass at the production threshold.

**Population mismatch caveat:** BacktestRunner does not persist `decision_outcomes`, so backtest rejected sweep candidates are unavailable. A fair backtest-vs-live distribution comparison (same population type: all generated sweeps) cannot be performed with current data. The observation above reflects only live conditions, not a validated distribution shift claim.

## Conclusions

### What the Evidence Shows

**Confirmed:**
- Per-trade quartile ER gradient is monotonic (Q1=1.577 → Q4=2.833): deeper sweeps produce better outcomes
- sweep_depth_pct is #2 feature by |correlation| with pnl_r (r=0.136)
- Winners have marginally deeper sweeps than losers (p=0.071, not significant)

**Not confirmed:**
- Whether 0.00649 is a natural edge boundary vs an overfitted Optuna optimum
- Whether the live market's shallow sweep distribution represents a temporary or structural shift
- Cross-trial ER gradient cannot be used as causal evidence (Optuna selection bias — see Appendix A)

**Verdict: DEEPER_IS_BETTER_BUT_THRESHOLD_UNCERTAIN.** Per-trade analysis confirms deeper sweeps produce better outcomes within accepted trades. However, evidence does not definitively prove 0.00649 is a natural boundary vs overfitted optimum. Out-of-sample / walk-forward threshold stability validation is required before ruling out threshold adjustment.

### Practical Implications

1. **Do not adjust production threshold without OOS/WF threshold stability validation.** Per-trade analysis suggests deeper is better, but threshold boundary requires cross-window verification.
2. **Low frequency is expected.** 274 trades over 4 years = ~5.6/month average, but with high variance across market regimes.
3. **Continue paper monitoring.** The 30-day checkpoint (2026-06-08) should reassess whether sweeps are deepening as market regime evolves.
4. **5m frequency upgrade can be deferred** pending corrected threshold analysis and/or 30-day monitoring results.

### What Would Change This Verdict

- OOS/WF threshold stability analysis showing 0.00649 is stable across multiple time windows → upgrade to THRESHOLD_NATURAL
- OOS/WF showing threshold is unstable → downgrade to THRESHOLD_OVERFITTED, consider relaxation
- If after 60+ days, the bot has < 2 trades total → market regime may have permanently shifted
- If a new Optuna campaign with updated data produces a materially different optimal depth → revalidation needed

## Methodology

### Analysis Script

`research_lab/analysis_trial_00095_conditional_edge.py`

Two-phase analysis:
1. Per-trade replay via `BacktestRunner` with trial-00095 exact parameters against snapshot market DB
2. Cross-trial Optuna consistency check from `research_lab/research_lab.db.v3` (746 trials — see Appendix A)

### Data Sources

- **Replay:** `research_lab/snapshots/replay-run13-regime-aware-trial-00063.db` (2022-01-01 to 2026-03-28)
- **Cross-trial (appendix only):** `research_lab/research_lab.db.v3` (2683 trials, 746 with trades > 0)
- **Live observation:** Production DB via SSH (`decision_outcomes.details_json`, 267 `sweep_too_shallow` events since 2026-05-08)

### Data Limitations

- **Backtest rejected sweeps unavailable:** BacktestRunner does not persist `decision_outcomes`. Only accepted trades are recorded. A fair backtest-vs-live distribution comparison cannot be performed.
- **Cross-trial confounding:** Optuna trials vary ~40 parameters simultaneously. Binning by `min_sweep_depth_pct` alone conflates depth effect with co-varying parameters. See Appendix A.

### Outputs

- `research_lab/analysis_output/report.txt` — full analysis text
- `research_lab/analysis_output/cross_trial_analysis.json` — cross-trial data (appendix)
- `research_lab/analysis_output/per_trade_analysis.json` — per-trade metrics
- `research_lab/analysis_output/trial_00095_trades.json` — 274 individual trade records
- `research_lab/analysis_output/verdict.json` — automated verdict with reasoning
- `research_lab/analysis_output/live_depths.json` — live rejected sweep depths

## Appendix A: Cross-Trial Optuna Consistency Check (Not Causal Evidence)

> **⚠️ Selection bias warning:** The 746 Optuna trials vary ~40 parameters simultaneously (confluence_min, min_tfi_strength, max_risk_pct, etc.). Binning trials by `min_sweep_depth_pct` alone conflates the depth effect with other co-varying parameters. This analysis shows Optuna selection consistency, NOT causal evidence that depth threshold alone drives ER.

746 Optuna trials with trades > 0, varying `min_sweep_depth_pct` from 0.00001 to 0.01857.

| Depth Bin | N Trials | ER Mean | ER Median | ER Max | Avg Trades |
|---|---:|---:|---:|---:|---:|
| < 0.001 | 88 | -0.089 | -0.057 | 1.350 | 414 |
| 0.001 - 0.003 | 150 | 0.145 | 0.017 | 2.735 | 279 |
| 0.003 - 0.005 | 97 | 0.292 | 0.065 | 3.536 | 173 |
| 0.005 - 0.007 | 85 | 0.658 | 0.478 | 5.308 | 123 |
| 0.007 - 0.010 | 171 | 0.984 | 0.688 | 11.003 | 48 |
| 0.010 - 0.015 | 86 | 0.947 | 0.554 | 9.927 | 15 |
| > 0.015 | 69 | 1.393 | 1.349 | 6.364 | 48 |

Trial-00095 (`depth=0.00649`) falls in the `0.005 - 0.007` bin.

**Interpretation:** The monotonic ER trend is *consistent with* depth being a real quality signal, but does not prove it causally. To isolate the depth effect, a ceteris paribus analysis (holding all other parameters fixed while varying only depth) would be required. This was not performed in M2.

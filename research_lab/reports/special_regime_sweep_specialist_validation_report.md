# Special Regime Sweep Specialist — Validation Report

**Milestone:** `SWEEP-RECLAIM-FAMILY-EXPANSION-V1`
**Variant:** `special_regime_sweep_specialist`
**Date range:** `2022-01-01` → `2026-03-29`
**Hypothesis:** Sweeps in forced positioning regimes (crowded_leverage, post_liquidation) have higher reversion probability due to asymmetric pressure

## Builder Verdict: **HYPOTHESIS_FAILED**

- HARD_STOP: ER 0.3011 < 1.0 (with adequate sample of 34 trades)
- All 34 trades in crowded_leverage (post_liquidation = 0 cycles, infrastructure gap)
- LONG only (SHORT dropped per V1+V2 evidence)
- 3/3 regime variants failed — regime-based family expansion conclusively not viable

## Gates

| Gate | Value | Pass |
|---|---|---|
| er_above_1_5 | 0.3011 | FAIL |
| er_above_1_0 | 0.3011 | FAIL |
| min_trades_20 | 34 | PASS |
| overlap_below_30 | — | MOOT (hypothesis failed; crowded_leverage LONG overlaps trial-00095) |
| win_rate_above_50 | 38.24% | FAIL |
| pf_above_2_5 | 1.3303 | FAIL |

## Overall Performance

- **Trades:** 34
- **Expectancy R:** 0.3011
- **Profit factor:** 1.3303
- **Win rate:** 38.24%
- **Max drawdown:** 8.36%
- **Sharpe:** 2.32
- **PnL abs:** +$706

## Regime Cycle Distribution

| Regime | Cycles | % of Total |
|---|---:|---:|
| downtrend | 59,496 | 40.0% |
| uptrend | 58,992 | 39.7% |
| crowded_leverage | 16,825 | 11.3% |
| normal | 13,296 | 8.9% |
| post_liquidation | 0 | 0.0% |

## Decision Funnel

- Total cycles: 148,609
- Regime rejected: 131,784 (88.7%)
- Context passed: 16,825 (11.3%) — all crowded_leverage
- Signal generated: 49 (0.29% of context-passed)
- Governance rejected: 8
- Risk rejected: 7
- Trades opened: 34

## Per Regime

| Regime | Trades | ER | PF | Max DD |
|---|---:|---:|---:|---:|
| crowded_leverage | 34 | 0.30 | 1.33 | 8.36% |
| post_liquidation | 0 | — | — | — |

## Per Direction

| Direction | Trades | ER | PF | Max DD |
|---|---:|---:|---:|---:|
| LONG | 34 | 0.30 | 1.33 | 8.36% |

## Root Cause Analysis

1. **Crowded leverage LONG has weak edge.** 34 trades with ER 0.30, PF 1.33. The asymmetric pressure hypothesis (funding extremes create forced positioning → flush → snap-back) produces marginal positive outcomes but far below the ER 1.0 hard stop.

2. **Post-liquidation = 0 cycles.** The regime engine never classifies post_liquidation in the entire 4-year window. This is an infrastructure gap — the force_orders data may not integrate into regime classification, or the thresholds are never met.

3. **Win rate 38.24% is too low.** Even with avg_winner_r = 2.94 (large winners), only 13/34 trades win. The sweep_reclaim signal in crowded_leverage produces many small losers (avg_loser_r = -1.33) that erode the rare large winners.

4. **Overlap with trial-00095 is high.** Trial-00095 already allows LONG in crowded_leverage. These 34 trades are a subset of trial-00095's trade set — no independence.

## Cross-Variant Summary (V1 + V2 + V3) — DEFINITIVE

| Variant | Context | Direction | Trades | ER | PF | Finding |
|---|---|---|---:|---:|---:|---|
| V1 | Normal | LONG | 16 | 0.02 | 1.00 | Zero edge |
| V1 | Normal | SHORT | 5 | -0.92 | 0.13 | Destructive |
| V2 | Downtrend | LONG | 127 | 0.76 | 2.10 | Moderate (overlaps trial-00095) |
| V2 | Uptrend | SHORT | 32 | 0.09 | 1.09 | Zero edge |
| V3 | Crowded_leverage | LONG | 34 | 0.30 | 1.33 | Below threshold |

### LONG ER by Regime (ranked)

| Regime | Trades | ER | PF |
|---|---:|---:|---:|
| downtrend | 127 | 0.76 | 2.10 |
| crowded_leverage | 34 | 0.30 | 1.33 |
| normal | 16 | 0.02 | 1.00 |
| uptrend | — | — | — |
| post_liquidation | 0 | — | — |

**None reach ER 1.0.** Trial-00095's ER 2.1 is NOT driven by any single regime. It comes from the COMBINED effect across ALL regimes with Optuna-optimized parameters.

## Conclusive Findings

1. **Regime-based family expansion is NOT viable.** 3/3 variants failed. No single regime produces ER > 1.0 independently.

2. **SHORT direction is universally unprofitable** for sweep_reclaim signals (tested in normal and uptrend).

3. **The sweep_reclaim edge is parameter-dependent, not context-dependent.** Trial-00095's ER 2.1 comes from optimized confluence thresholds, TFI parameters, and risk management — not from regime filtering.

4. **No independent alpha available from regime context.** All LONG trades in any regime overlap with trial-00095's existing behavior. Context filtering only subsets the existing trade set — it cannot create new independent entries.

## Strategic Recommendation

Regime-based family expansion exhausted. Future expansion should pivot to:
- **Parameter-based variants:** Conservative/aggressive threshold tuning (Optuna re-optimization with different objectives)
- **Microstructure-based variants:** Session timing, order book depth, liquidation heatmaps (requires new data infrastructure)
- **Frequency upgrade:** 5m/1m timeframe (requires significant infrastructure investment)
- OR accept trial-00095 as the single sweep_reclaim deployment and focus on portfolio diversification through entirely new edge families

## Next Step

This is the FINAL regime test. 3/3 failed. Regime-based family expansion conclusively not viable. Awaiting strategic direction.

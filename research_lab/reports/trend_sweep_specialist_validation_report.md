# Trend Sweep Specialist — Validation Report

**Milestone:** `SWEEP-RECLAIM-FAMILY-EXPANSION-V1`
**Variant:** `trend_sweep_specialist`
**Date range:** `2022-01-01` → `2026-03-29`
**Hypothesis:** Sweeps in trending regimes (downtrend, uptrend) have higher reversion probability due to exhaustion dynamics

## Builder Verdict: **HYPOTHESIS_FAILED**

- HARD_STOP: ER 0.6281 < 1.0 (with adequate sample of 159 trades)
- Uptrend SHORT (the novel independent component) has zero edge: ER 0.089
- Downtrend LONG has moderate edge (ER 0.76) but overlaps with trial-00095

## Gates

| Gate | Value | Pass |
|---|---|---|
| er_above_1_5 | 0.6281 | FAIL |
| er_above_1_0 | 0.6281 | FAIL |
| min_trades_20 | 159 | PASS |
| overlap_below_30 | — | MOOT (hypothesis failed; downtrend LONG fully overlaps trial-00095) |
| win_rate_above_50 | 47.80% | FAIL |
| pf_above_2_5 | 1.8872 | FAIL |

## Overall Performance

- **Trades:** 159
- **Expectancy R:** 0.6281
- **Profit factor:** 1.8872
- **Win rate:** 47.80%
- **Max drawdown:** 12.38%
- **Sharpe:** 4.75 (estimated from direction data)
- **PnL abs:** +$9,915

## Decision Funnel

- Total cycles: 148,609
- Regime rejected: 30,121 (20.3%)
- Volatility rejected: 0 (filter disabled)
- Context passed: 118,488 (79.7%)
- Signal generated: 233 (0.20% of context-passed)
- Governance rejected: 26
- Risk rejected: 48
- Trades opened: 159

## Per Regime

| Regime | Trades | ER | PF | Max DD | Sharpe |
|---|---:|---:|---:|---:|---:|
| downtrend | 127 | 0.76 | 2.10 | 6.58% | 5.34 |
| uptrend | 32 | 0.09 | 1.09 | 12.38% | 0.92 |

## Per Direction

| Direction | Trades | ER | PF | Max DD | Sharpe |
|---|---:|---:|---:|---:|---:|
| LONG | 127 | 0.76 | 2.10 | 6.58% | 5.34 |
| SHORT | 32 | 0.09 | 1.09 | 12.38% | 0.92 |

## Root Cause Analysis

1. **Uptrend SHORT (novel entry) has zero edge.** 32 trades with ER 0.089, PF 1.09. Counter-trend SHORT in uptrend produces essentially random outcomes. The exhaustion dynamic hypothesis does NOT hold for shorts in uptrends — trends persist more than they reverse from sweeps.

2. **Downtrend LONG has moderate edge but is NOT independent.** 127 trades with ER 0.76, PF 2.10. This edge already exists in trial-00095 (which allows LONG in downtrend). The overlap rate would be very high (~100% since trial-00095's downtrend whitelist = ("LONG", "SHORT")).

3. **Combined ER 0.63 < 1.0 hard stop.** Adequate sample (159 trades) provides statistical confidence in this result. The uptrend SHORT component drags down the overall performance and provides zero independent value.

4. **PF 1.89 and positive PnL are misleading.** Raw PnL is positive ($9,915) because downtrend LONG wins are large (avg_winner_r = 3.01). But losers are frequent enough (52.2% loss rate) that ER is subpar. The edge exists but is insufficiently sharp for promotion.

## Comparison: V1 vs V2

| Variant | Context | Trades | ER | PF | Novel Component |
|---|---|---:|---:|---:|---|
| V1 (Range Sweep) | Normal regime | 21 | -0.20 | 0.76 | SHORT in normal = destructive |
| V2 (Trend Sweep) | Trending regimes | 159 | 0.63 | 1.89 | SHORT in uptrend = zero edge |

**Key pattern:** SHORT sweep_reclaim signals consistently fail across all regime contexts. The edge is LONG-only.

## Independence Assessment

Even if ER were sufficient, the downtrend LONG trades (127 of 159) fully overlap with trial-00095's existing behavior. The uptrend SHORT trades (32) would be independent but have no edge. Therefore, no independent alpha is available from trending regime context alone.

## Strategic Implication

Across two variants, a clear pattern emerges:
- **LONG sweep_reclaim in downtrend:** ER 0.76, PF 2.10 — real but sub-threshold edge
- **LONG sweep_reclaim in normal:** ER 0.02 — no edge
- **SHORT sweep_reclaim anywhere:** ER negative or zero — no edge
- **trial-00095 overall:** ER 2.1 — driven by LONG in multiple regimes with optimized parameters

The sweep_reclaim edge is LONG-biased and NOT regime-specific. Trial-00095's superior ER comes from Optuna-optimized parameters (confluence thresholds, TFI, etc.), not from regime filtering. Family expansion through regime context alone cannot produce independent alpha.

## Next Step

Per handoff discipline: This is the second consecutive HYPOTHESIS_FAILED. The evidence suggests:
- Regime filtering alone cannot create independent alpha from sweep_reclaim
- The edge is parameter-dependent, not context-dependent
- Variant 3 (special regimes: crowded_leverage, post_liquidation) is the final regime test

Recommendation: **Move to Variant 3 (Special Regime Sweep Specialist)** OR acknowledge that context-based family expansion is not viable and pivot strategy entirely.

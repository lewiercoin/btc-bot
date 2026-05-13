# Range Sweep Specialist — Validation Report

**Milestone:** `SWEEP-RECLAIM-FAMILY-EXPANSION-V1`
**Variant:** `range_sweep_specialist`
**Date range:** `2022-01-01` → `2026-03-29`
**Hypothesis:** Sweeps in range-bound (normal regime, horizontal structure) markets have higher reversion probability

## Builder Verdict: **HYPOTHESIS_FAILED**

- HARD_STOP: ER -0.2026 < 1.0 (with adequate sample of 21 trades)
- SHORT direction ER -0.92 (clearly destructive)
- LONG direction ER 0.02 (no edge in normal regime)

## Gates

| Gate | Value | Pass |
|---|---|---|
| er_above_1_5 | -0.2026 | ❌ |
| er_above_1_0 | -0.2026 | ❌ |
| min_trades_20 | 21 | ✅ |
| overlap_below_30 | — | ⏳ (moot — hypothesis failed) |
| win_rate_above_50 | 28.57% | ❌ |
| pf_above_2_5 | 0.7648 | ❌ |

## Iteration Summary

| Run | Config | Trades | ER | PF | Win Rate | Verdict |
|---|---|---:|---:|---:|---:|---|
| 1 | Default (all filters) | 3 | 0.63 | 1.66 | 33.3% | INSUFFICIENT_SAMPLE |
| 2 | No volatility filter | 21 | -0.20 | 0.76 | 28.6% | HYPOTHESIS_FAILED |
| 3 | Regime-only (no struct/vol) | 21 | -0.20 | 0.76 | 28.6% | HYPOTHESIS_FAILED |

Run 2 and Run 3 are identical — the structure slope filter rejected 97 cycles that contained zero signal candidates. The volatility filter is the only filter with material impact (removed 3,296 cycles containing 2-3 potential trades).

## Overall Performance (Run 2 — definitive)

- **Trades:** 21
- **Expectancy R:** -0.2026
- **Profit factor:** 0.7648
- **Win rate:** 28.57%
- **Max drawdown:** 8.25%
- **Sharpe:** -2.26
- **PnL abs:** -326.73

## Decision Funnel (Run 2)

- Total cycles: 148,609
- Regime rejected: 135,313 (91.1%)
- Structure rejected: 97 (0.07%)
- Volatility rejected: 0 (disabled)
- Context passed: 13,199 (8.9%)
- Signal generated: 32 (0.24% of context-passed)
- Governance rejected: 3
- Risk rejected: 8
- Trades opened: 21

## Per Direction (Run 2)

| Direction | Trades | ER | PF | Win Rate | Max DD |
|---|---:|---:|---:|---:|---:|
| LONG | 16 | 0.02 | 1.00 | 31.25% | 8.25% |
| SHORT | 5 | -0.92 | 0.13 | 20.00% | 3.25% |

## Per Regime (Run 2)

| Regime | Trades | ER | PF |
|---|---:|---:|---:|
| normal | 21 | -0.20 | 0.76 |

## Root Cause Analysis

1. **The sweep_reclaim edge does NOT concentrate in normal/range-bound regime.** With 21 trades in normal regime, ER is -0.20. Trial-00095 achieves ER 2.1 across ALL regimes, meaning the edge is driven by non-normal regimes (downtrend, compression, crowded_leverage, post_liquidation).

2. **SHORT in normal regime is destructive.** ER -0.92, PF 0.13. The default whitelist (LONG only in normal) was correct — bidirectional reversion in ranges doesn't work with this signal engine.

3. **LONG in normal regime has zero edge.** 16 trades with ER 0.02, PF 1.00. The sweep_reclaim pattern in range-bound conditions produces random outcomes, not mean-reversion profit.

4. **Structure slope filter has no practical impact.** Only 97 cycles rejected (0.07%), none containing trade candidates. The hypothesis that "horizontal structure = clearer boundaries" doesn't meaningfully filter sweep events.

## Strategic Implication

The Range Sweep Specialist hypothesis is conclusively falsified. The sweep_reclaim edge is NOT enhanced by restricting to normal/range-bound context — it is actively degraded. This suggests:

- The edge may concentrate in **trending** or **special** regimes (downtrend, crowded_leverage, post_liquidation)
- **Variant 2 (Trend Sweep Specialist)** should test the opposite hypothesis: sweeps in trending regimes have higher reversion probability
- This is consistent with the mean-reversion thesis: overshoots in trending markets may produce stronger snap-back when a trend continuation fails to follow through

## Next Step

Per handoff fast failure discipline: **Move immediately to Variant 2 (Trend Sweep Specialist).**

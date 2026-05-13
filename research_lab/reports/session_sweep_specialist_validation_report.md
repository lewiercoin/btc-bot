# Session Sweep Specialist — Validation Report

**Milestone:** `SWEEP-RECLAIM-FAMILY-EXPANSION-V1`
**Variant:** `session_sweep_specialist` (Variant 4 — Microstructure)
**Date range:** `2022-01-01` → `2026-03-29`
**Hypothesis:** Sweeps during low-liquidity sessions (Asia 00:00-08:00 UTC) have higher reversion probability due to thinner order books

## Builder Verdict: **HYPOTHESIS_FAILED**

- HARD_STOP: ER 0.7778 < 1.0 (with adequate sample of 126 trades)
- Best metrics of any variant tested (ER 0.78, PF 2.42, Win 57%)
- Still below ER 1.0 hard stop — microstructure session filtering insufficient
- 4/4 context variants failed — 15m context expansion conclusively exhausted

## Gates

| Gate | Value | Pass |
|---|---|---|
| er_above_1_5 | 0.7778 | FAIL |
| er_above_1_0 | 0.7778 | FAIL |
| min_trades_20 | 126 | PASS |
| overlap_below_30 | — | Not computed (hypothesis failed; overlap analysis moot) |
| win_rate_above_50 | 57.14% | PASS |
| pf_above_2_5 | 2.4209 | FAIL (marginal) |

## Overall Performance

- **Trades:** 126
- **Expectancy R:** 0.7778
- **Profit factor:** 2.4209
- **Win rate:** 57.14%
- **Max drawdown:** 3.55%
- **Sharpe:** 6.93
- **PnL abs:** +$9,934
- **Avg winner R:** 2.29
- **Avg loser R:** -1.24
- **Max consecutive losses:** 4

## Hour Distribution (session window: 00:00-08:00 UTC)

| UTC Hour | Cycles | Trades | Trade Rate |
|---:|---:|---:|---:|
| 00 | 6,193 | 35 | 0.57% |
| 01 | 6,192 | 20 | 0.32% |
| 02 | 6,192 | 13 | 0.21% |
| 03 | 6,192 | 12 | 0.19% |
| 04 | 6,192 | 15 | 0.24% |
| 05 | 6,192 | 11 | 0.18% |
| 06 | 6,192 | 11 | 0.18% |
| 07 | 6,192 | 9 | 0.15% |

Trade concentration at hour 00 (28% of session trades). Declining through session.

## Decision Funnel

- Total cycles: 148,609
- Session rejected: 99,072 (66.7%)
- Session passed: 49,537 (33.3%)
- Signal generated: 335 (0.68% of session-passed)
- Governance rejected: 51
- Risk rejected: 158
- **Trades opened: 126** (37.6% of signals survived governance+risk)

Post-signal rejection rate: 62.4% (209/335 signals rejected by governance+risk). Higher than V1-V3 — governance/risk constraints more binding during Asia hours.

## Per Regime (within Asia session)

| Regime | Trades | ER | PF | Win% | Max DD | Assessment |
|---|---:|---:|---:|---:|---:|---|
| **uptrend** | **90** | **0.89** | **2.85** | **62.2%** | 4.1% | Best single-regime result across ALL variants |
| downtrend | 30 | 0.86 | 2.37 | 53.3% | 3.9% | Moderate (overlaps V2 downtrend LONG) |
| crowded_leverage | 3 | -1.33 | 0.00 | 0% | 4.3% | Destructive (tiny sample) |
| normal | 3 | -1.34 | 0.00 | 0% | 3.0% | Destructive (tiny sample) |

**Key finding:** Asia session is dominated by uptrend LONG (71% of trades). Uptrend LONG during Asia achieves ER 0.89, PF 2.85 — strongest single result across all 4 variants, but still < 1.0.

## Per Direction

| Direction | Trades | ER | PF | Max DD |
|---|---:|---:|---:|---:|
| LONG | 126 | 0.78 | 2.42 | 3.55% |

## Root Cause Analysis

1. **Asia session concentrates the better part of the signal.** ER 0.78 during Asia vs trial-00095's overall ER 2.1. The session filter selects ~33% of cycles but captures a proportional share of edge — it does NOT concentrate the edge.

2. **Uptrend dominance in Asia hours.** 71% of Asia trades are in uptrend regimes (ER 0.89). This correlates with Asia-hour BTC behavior (continuation bias during Asian trading).

3. **Post-signal rejection is high.** 62.4% of generated signals are rejected by governance (51) and risk (158). The ER 0.78 is after governance/risk filtering — the raw signal quality during Asia hours may be lower.

4. **Still below ER 1.0.** Despite being the best variant tested, microstructure session timing alone cannot elevate sweep_reclaim ER above the hard stop. The edge is parameter-dependent (Optuna thresholds), not context-dependent (regime or session).

## Cross-Variant Summary (V1 + V2 + V3 + V4) — DEFINITIVE

| Variant | Mechanism | Context | Direction | Trades | ER | PF | Win% | Finding |
|---|---|---|---|---:|---:|---:|---:|---|
| V1 | Regime | Normal | LONG | 16 | 0.02 | 1.00 | — | Zero edge |
| V1 | Regime | Normal | SHORT | 5 | -0.92 | 0.13 | — | Destructive |
| V2 | Regime | Downtrend | LONG | 127 | 0.76 | 2.10 | — | Moderate (overlaps) |
| V2 | Regime | Uptrend | SHORT | 32 | 0.09 | 1.09 | — | Zero edge |
| V3 | Regime | Crowded_leverage | LONG | 34 | 0.30 | 1.33 | 38% | Below threshold |
| **V4** | **Microstructure** | **Asia session** | **LONG** | **126** | **0.78** | **2.42** | **57%** | **Best, still < 1.0** |

## Conclusive Findings (4/4 variants)

1. **15m context expansion is NOT viable.** 4/4 variants failed (3 regime + 1 microstructure). No context filter produces ER > 1.0 independently.

2. **sweep_reclaim is a singular, parameter-optimized edge.** Trial-00095's ER 2.1 comes from Optuna-tuned thresholds across ALL regimes and ALL sessions — not from any specific context.

3. **Session timing shows marginal improvement** (ER 0.78 vs V1 0.02, V3 0.30) but insufficient to cross ER 1.0.

4. **Uptrend + Asia = best micro-context** (ER 0.89, PF 2.85) but still parameter-dependent, not independently viable.

## Strategic Recommendation

All 15m context expansion exhausted. Next steps per audit roadmap:
- **Accept singular edge:** trial-00095 IS the sweep_reclaim edge at 15m
- **Focus on live validation:** 30-50 trades over 6-10 months
- **Defer 5m upgrade:** Until live ER stability confirmed (expensive, 6-8 weeks)

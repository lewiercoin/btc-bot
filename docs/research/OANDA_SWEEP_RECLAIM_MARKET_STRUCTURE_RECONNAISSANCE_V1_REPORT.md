# OANDA_SWEEP_RECLAIM_MARKET_STRUCTURE_RECONNAISSANCE_V1

**Date:** 2026-05-31T19:43:26.240986+00:00
**Type:** Market-structure reconnaissance, not profitability diagnostic
**Recommendation:** PROCEED_TO_FULL_PLANNING

## Executive Summary

This reconnaissance preserves the prior `OANDA_XAUUSD_SWEEP_RECLAIM_TRANSFER_FEASIBILITY_V1` STOP result.
It does not claim that OANDA has edge, does not validate SMC, and does not modify production code.

Result: `PROCEED_TO_FULL_PLANNING`.

EUR_USD M15 same-bar close reclaim has 3419 candidates with median MFE consumed 11.96%, making it the earliest decision-grade OANDA structure candidate. The 5-bar windows confirm structure is not sparse but should not be selected solely for higher count.

The strict `XAU_USD H1` BTC transfer failed because it produced only 11 decision events. This report asks whether OANDA sweep/reclaim structure is absent or whether another pre-declared instrument/timeframe has enough structure to justify a separate planning document.

## 1. Prior Diagnostic Boundary

- Prior diagnostic remains `STOP` for strict `XAU_USD H1` BTC-style transfer.
- This report does not reinterpret that result as passing.
- This report measures structure only: sweep frequency, reclaim timing, depth distribution, and MFE accessibility.
- No PnL validation, threshold tuning, SMC rescue, or production change is in scope.

## 2. Data Inventory

| Instrument | TF | Candles | First | Last | OHLC Bad | Duplicates | Gaps >72h | Max Gap Hours | Gate |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| `EUR_USD` | `H1` | 14998 | 2024-01-01T22:00:00+00:00 | 2026-05-29T20:00:00+00:00 | 0 | 0 | 0 | 50.0 | `PASS` |
| `EUR_USD` | `M15` | 59989 | 2024-01-01T22:00:00+00:00 | 2026-05-29T20:45:00+00:00 | 0 | 0 | 0 | 49.25 | `PASS` |
| `EUR_USD` | `M30` | 29995 | 2024-01-01T22:00:00+00:00 | 2026-05-29T20:30:00+00:00 | 0 | 0 | 0 | 49.5 | `PASS` |
| `XAU_USD` | `H1` | 14260 | 2024-01-01T23:00:00+00:00 | 2026-05-29T20:00:00+00:00 | 0 | 0 | 3 | 74.0 | `PASS` |
| `XAU_USD` | `M15` | 57002 | 2024-01-01T23:00:00+00:00 | 2026-05-29T20:45:00+00:00 | 0 | 0 | 3 | 73.25 | `PASS` |
| `XAU_USD` | `M30` | 28504 | 2024-01-01T23:00:00+00:00 | 2026-05-29T20:30:00+00:00 | 0 | 0 | 3 | 73.5 | `PASS` |

## 3. Instrument/Timeframe Structure Matrix

Primary descriptive window below is reclaim within 5 bars. Same/1/2/3-bar windows are reported separately.

| Instrument | TF | Candles | Raw Sweeps | Sweeps/mo | Reclaims | Reclaim Rate | Median MFE Consumed | >70% Consumed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `EUR_USD` | `H1` | 14998 | 5652 | 195.9 | 3152 | 55.77% | 41.29% | 18.53% |
| `EUR_USD` | `M15` | 59989 | 23922 | 829.3 | 13327 | 55.71% | 44.13% | 21.46% |
| `EUR_USD` | `M30` | 29995 | 11690 | 405.3 | 6670 | 57.06% | 43.48% | 20.79% |
| `XAU_USD` | `H1` | 14260 | 5328 | 184.7 | 2892 | 54.28% | 44.43% | 20.92% |
| `XAU_USD` | `M15` | 57002 | 23027 | 798.3 | 12781 | 55.50% | 43.39% | 20.35% |
| `XAU_USD` | `M30` | 28504 | 11143 | 386.3 | 6112 | 54.85% | 44.09% | 20.78% |

## 4. Reclaim Timing Windows

### EUR_USD H1

| Window Bars | Reclaims | Reclaim Rate | Median Delay | Median MFE Consumed | >70% Consumed |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 878 | 15.53% | 0.0 | 13.90% | 5.24% |
| 1 | 1760 | 31.14% | 1.0 | 29.99% | 12.61% |
| 2 | 2301 | 40.71% | 1.0 | 35.97% | 15.69% |
| 3 | 2667 | 47.19% | 1.0 | 38.46% | 16.76% |
| 5 | 3152 | 55.77% | 1.0 | 41.29% | 18.53% |

### EUR_USD M15

| Window Bars | Reclaims | Reclaim Rate | Median Delay | Median MFE Consumed | >70% Consumed |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 3419 | 14.29% | 0.0 | 11.96% | 5.73% |
| 1 | 7244 | 30.28% | 1.0 | 32.43% | 15.74% |
| 2 | 9656 | 40.36% | 1.0 | 38.89% | 18.86% |
| 3 | 11261 | 47.07% | 1.0 | 41.80% | 20.14% |
| 5 | 13327 | 55.71% | 1.0 | 44.13% | 21.46% |

### EUR_USD M30

| Window Bars | Reclaims | Reclaim Rate | Median Delay | Median MFE Consumed | >70% Consumed |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1800 | 15.40% | 0.0 | 13.04% | 5.50% |
| 1 | 3670 | 31.39% | 1.0 | 31.50% | 15.67% |
| 2 | 4809 | 41.14% | 1.0 | 37.93% | 18.24% |
| 3 | 5633 | 48.19% | 1.0 | 40.68% | 19.72% |
| 5 | 6670 | 57.06% | 1.0 | 43.48% | 20.79% |

### XAU_USD H1

| Window Bars | Reclaims | Reclaim Rate | Median Delay | Median MFE Consumed | >70% Consumed |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 733 | 13.76% | 0.0 | 17.24% | 5.59% |
| 1 | 1584 | 29.73% | 1.0 | 34.38% | 16.35% |
| 2 | 2102 | 39.45% | 1.0 | 39.80% | 18.65% |
| 3 | 2443 | 45.85% | 1.0 | 42.05% | 19.65% |
| 5 | 2892 | 54.28% | 1.0 | 44.43% | 20.92% |

### XAU_USD M15

| Window Bars | Reclaims | Reclaim Rate | Median Delay | Median MFE Consumed | >70% Consumed |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 3294 | 14.30% | 0.0 | 12.70% | 4.31% |
| 1 | 6843 | 29.72% | 1.0 | 31.51% | 13.82% |
| 2 | 9149 | 39.73% | 1.0 | 37.92% | 17.03% |
| 3 | 10741 | 46.65% | 1.0 | 40.67% | 18.58% |
| 5 | 12781 | 55.50% | 1.0 | 43.39% | 20.35% |

### XAU_USD M30

| Window Bars | Reclaims | Reclaim Rate | Median Delay | Median MFE Consumed | >70% Consumed |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1569 | 14.08% | 0.0 | 13.91% | 4.91% |
| 1 | 3272 | 29.36% | 1.0 | 31.89% | 14.27% |
| 2 | 4391 | 39.41% | 1.0 | 38.86% | 17.47% |
| 3 | 5140 | 46.13% | 1.0 | 41.53% | 19.18% |
| 5 | 6112 | 54.85% | 1.0 | 44.09% | 20.78% |

## 5. Sweep Depth Distribution

| Instrument | TF | Depth p10 | p25 | p50 | p75 | p90 | ATR p50 | ATR p90 | Strict BTC Same-Bar Reclaims |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `EUR_USD` | `H1` | 0.04% | 0.06% | 0.08% | 0.12% | 0.18% | 0.76 | 1.64 | 0 |
| `EUR_USD` | `M15` | 0.02% | 0.03% | 0.04% | 0.06% | 0.09% | 0.75 | 1.50 | 0 |
| `EUR_USD` | `M30` | 0.03% | 0.04% | 0.06% | 0.08% | 0.13% | 0.77 | 1.55 | 0 |
| `XAU_USD` | `H1` | 0.12% | 0.16% | 0.22% | 0.34% | 0.51% | 0.75 | 1.55 | 11 |
| `XAU_USD` | `M15` | 0.05% | 0.07% | 0.10% | 0.16% | 0.25% | 0.75 | 1.48 | 5 |
| `XAU_USD` | `M30` | 0.07% | 0.10% | 0.15% | 0.24% | 0.37% | 0.76 | 1.55 | 9 |

## 6. Direction and Session Observations

### EUR_USD H1

- Direction counts: `{'SHORT': 2457, 'LONG': 3195}`
- Session counts: `{'asia': 1738, 'london': 1677, 'new_york': 1814, 'rollover': 423}`
- 5-bar reclaim direction counts: `{'LONG': 1831, 'SHORT': 1321}`
- 5-bar reclaim session counts: `{'london': 1067, 'new_york': 889, 'rollover': 187, 'asia': 1009}`

### EUR_USD M15

- Direction counts: `{'LONG': 13076, 'SHORT': 10846}`
- Session counts: `{'new_york': 7385, 'rollover': 2637, 'asia': 7496, 'london': 6404}`
- 5-bar reclaim direction counts: `{'LONG': 7684, 'SHORT': 5643}`
- 5-bar reclaim session counts: `{'new_york': 3730, 'asia': 4400, 'london': 3767, 'rollover': 1430}`

### EUR_USD M30

- Direction counts: `{'LONG': 6431, 'SHORT': 5259}`
- Session counts: `{'rollover': 1050, 'asia': 3650, 'london': 3503, 'new_york': 3487}`
- 5-bar reclaim direction counts: `{'LONG': 3785, 'SHORT': 2885}`
- 5-bar reclaim session counts: `{'rollover': 538, 'asia': 2213, 'london': 2201, 'new_york': 1718}`

### XAU_USD H1

- Direction counts: `{'SHORT': 2558, 'LONG': 2770}`
- Session counts: `{'asia': 1716, 'london': 1472, 'new_york': 1838, 'rollover': 302}`
- 5-bar reclaim direction counts: `{'LONG': 1686, 'SHORT': 1206}`
- 5-bar reclaim session counts: `{'london': 903, 'new_york': 949, 'asia': 867, 'rollover': 173}`

### XAU_USD M15

- Direction counts: `{'LONG': 12284, 'SHORT': 10743}`
- Session counts: `{'london': 6585, 'new_york': 7428, 'rollover': 1767, 'asia': 7247}`
- 5-bar reclaim direction counts: `{'LONG': 7464, 'SHORT': 5317}`
- 5-bar reclaim session counts: `{'london': 3906, 'new_york': 3861, 'asia': 4033, 'rollover': 981}`

### XAU_USD M30

- Direction counts: `{'SHORT': 5279, 'LONG': 5864}`
- Session counts: `{'asia': 3554, 'london': 3301, 'new_york': 3577, 'rollover': 711}`
- 5-bar reclaim direction counts: `{'LONG': 3566, 'SHORT': 2546}`
- 5-bar reclaim session counts: `{'asia': 2007, 'london': 1941, 'new_york': 1774, 'rollover': 390}`

## 7. Interpretation

- The prior strict H1 transfer remains invalidated; this reconnaissance is not a retry of that diagnostic.
- H1 scarcity is not proof that OANDA lacks structure; lower timeframes and EUR_USD materially change the structural sample size.
- The previous sample collapse came from the strict BTC-style same-bar/depth definition, not from absence of raw OANDA sweeps.
- OANDA sweep depths are materially smaller than the BTC depth threshold, especially on EUR_USD; any future plan must freeze an OANDA-specific structural rule before testing returns.
- Reclaim windows are descriptive only. A later diagnostic would need one frozen mechanism and audited controls before any PnL claims.
- MFE accessibility is evaluated from realistic entry after reclaim confirmation, not from sweep detection.

## 8. Artifact

- JSON path: `C:/development/btc-bot/research_lab/reports/oanda_sweep_reclaim_market_structure_reconnaissance_v1.json`
- JSON SHA256: `7b1ddacbf781894e1ae854389b8594bdc09fa539b87e7bc98dbee2973428e234`

## 9. Recommendation

### Verdict: PROCEED_TO_FULL_PLANNING

**Reason:** EUR_USD M15 same-bar close reclaim has 3419 candidates with median MFE consumed 11.96%, making it the earliest decision-grade OANDA structure candidate. The 5-bar windows confirm structure is not sparse but should not be selected solely for higher count.

**Next:** Create a separate full planning document for exactly one OANDA diagnostic candidate. Do not implement or tune in this reconnaissance milestone.

Candidate: `EUR_USD M15` with reclaim window `0` bars, count `3419`, reclaim rate `14.29%`, median MFE consumed `11.96%`.

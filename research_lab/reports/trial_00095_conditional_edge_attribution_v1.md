# TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1

**Date:** 2026-05-30
**Researcher:** Codex
**Type:** Research-only accepted-trade attribution diagnostic
**Recommendation:** PLAN_NEAR_MISS_RECONSTRUCTION_DIAGNOSTIC

## Executive Summary

This diagnostic analyzes the frozen accepted trade population for `optuna-default-v3-trial-00095`. It does not change thresholds, generate rejected candidates, alter settings, or promote anything.

The shallowest accepted depth quartile is still strongly positive, but rejected candidates are not persisted, so the next step must reconstruct near-miss candidates rather than relax thresholds.

Critical caveat: rejected backtest candidates are not available in the market snapshot used here. Therefore this diagnostic can support only a separate near-miss reconstruction plan, not a direct claim that near-miss entries are profitable.

## Data Availability

- Accepted trade records: 274
- Frozen entries with stop/target context: 274
- Attributed trades: 274
- BTCUSDT 15m candles: 195347
- 15m aggtrade TFI buckets loaded: 195150
- Funding samples: 6105
- Open-interest samples: 524971
- Rejected backtest candidates available: False
- Rejected backtest candidate count: None

## Methodology Guardrails

- Primary returns use frozen `pnl_r` from accepted trial-00095 trades.
- Reconstructed market context uses the prior completed 15m bar before `opened_at`.
- No detection-bar returns are introduced.
- No failed standalone regime/HMM/breakout/liquidation signal is used as an entry signal.
- No threshold is relaxed in this milestone.

## Baseline Metrics

| Metric | Value |
| --- | ---: |
| Count | 274 |
| Expectancy R | 2.1211 |
| Profit factor | 4.2165 |
| Win rate | 56.57% |
| Median R | 2.6568 |
| Total R | 581.19 |
| Max drawdown R | 14.68 |

WF reference: 271 trades, ER=2.1294, PF=4.6625, WR=56.46% from `WF_VALIDATION_TRIAL_00095_2026-05-08`. This diagnostic uses the existing 274-trade accepted replay artifact; the 3-trade replay difference is previously documented and is not treated as a new strategy result.

## Key Findings

- Shallowest accepted depth quartile remains positive: N=69, ER=1.577, PF=2.981, WR=47.8%.
- Near-threshold accepted trades remain positive: N=63, ER=1.635, PF=3.046; this supports reconstruction research, not threshold relaxation.
- Direction split is asymmetric: LONG ER=2.377 across 252 trades, SHORT ER=-0.805 across 22 trades.
- Regime split favors uptrend: uptrend ER=2.614, downtrend ER=0.690.
- Prior-bar TFI alignment separates outcomes: aligned ER=2.391, opposed ER=0.816.
- Most losses had at least 1R favorable excursion before closing red: 110 losses (92.4% of losses).
- Rejected backtest candidates are unavailable, so no near-miss profitability claim is made.

## Bucket Attribution

### Depth Quartile

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `Q1_low_depth_lt_0.007207` | 69 | 1.577 | 2.981 | 47.8% | -1.393 | 108.84 | True |
| `Q2_depth_0.007207_0.008346` | 68 | 1.994 | 4.269 | 60.3% | 2.736 | 135.56 | True |
| `Q3_depth_0.008346_0.010110` | 68 | 2.078 | 3.990 | 54.4% | 2.607 | 141.28 | True |
| `Q4_high_depth_ge_0.010110` | 69 | 2.833 | 6.280 | 63.8% | 3.373 | 195.51 | True |

### Depth Band

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `deep_0.01000_0.01500` | 59 | 2.782 | 6.267 | 64.4% | 3.265 | 164.16 | True |
| `mid_depth_0.00714_0.01000` | 139 | 1.951 | 3.952 | 56.8% | 2.581 | 271.17 | True |
| `near_threshold_0.00649_0.00714` | 63 | 1.635 | 3.046 | 47.6% | -1.393 | 102.99 | True |
| `very_deep_ge_0.01500` | 13 | 3.298 | 6.831 | 61.5% | 4.662 | 42.87 | False |

### Regime

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `crowded_leverage` | 6 | 0.226 | 1.229 | 33.3% | -1.409 | 1.36 | False |
| `downtrend` | 54 | 0.690 | 1.631 | 25.9% | -1.458 | 37.25 | True |
| `normal` | 9 | 0.736 | 1.712 | 33.3% | -1.549 | 6.62 | False |
| `uptrend` | 205 | 2.614 | 6.034 | 66.3% | 3.030 | 535.96 | True |

### Direction

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `LONG` | 252 | 2.377 | 4.929 | 60.3% | 2.801 | 598.90 | True |
| `SHORT` | 22 | -0.805 | 0.373 | 13.6% | -1.551 | -17.71 | True |

### Session

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `Asia_00_08` | 59 | 2.694 | 5.908 | 64.4% | 2.685 | 158.93 | True |
| `Europe_08_16` | 108 | 1.774 | 3.551 | 54.6% | 2.504 | 191.62 | True |
| `US_16_24` | 107 | 2.155 | 4.151 | 54.2% | 2.681 | 230.64 | True |

### Year

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `2022` | 70 | 1.233 | 2.376 | 40.0% | -1.391 | 86.30 | True |
| `2023` | 56 | 2.316 | 5.387 | 66.1% | 2.782 | 129.67 | True |
| `2024` | 107 | 2.475 | 4.940 | 58.9% | 2.815 | 264.85 | True |
| `2025` | 36 | 2.862 | 7.756 | 72.2% | 2.904 | 103.05 | True |
| `2026` | 5 | -0.535 | 0.552 | 20.0% | -1.549 | -2.67 | False |

### Fold

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `fold_1_2022_2023H1` | 110 | 1.584 | 3.024 | 48.2% | -1.261 | 174.23 | True |
| `fold_2_2023H2_2024` | 123 | 2.493 | 5.176 | 61.0% | 2.919 | 306.58 | True |
| `fold_3_2025_2026Q1` | 41 | 2.448 | 5.731 | 65.9% | 2.784 | 100.37 | True |

### Exit Reason

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `SL` | 119 | -1.518 | 0.000 | 0.0% | -1.549 | -180.69 | True |
| `TP_TRAIL` | 155 | 4.915 | 999.000 | 100.0% | 4.330 | 761.88 | True |

### TFI Alignment

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `aligned` | 227 | 2.391 | 4.963 | 60.4% | 2.815 | 542.82 | True |
| `opposed` | 47 | 0.816 | 1.877 | 38.3% | -1.480 | 38.37 | True |

### ATR14 Percentile

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `Q1_low_atr14_pct_lt_0.003995` | 69 | 2.038 | 6.651 | 76.8% | 2.685 | 140.65 | True |
| `Q2_atr14_pct_0.003995_0.005480` | 68 | 2.591 | 6.152 | 67.6% | 3.698 | 176.20 | True |
| `Q3_atr14_pct_0.005480_0.007904` | 68 | 1.639 | 2.937 | 45.6% | -1.547 | 111.49 | True |
| `Q4_high_atr14_pct_ge_0.007904` | 69 | 2.215 | 3.387 | 36.2% | -1.366 | 152.85 | True |

### Volume Z-Score Percentile

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `Q1_low_volume_z20_lt_0.203970` | 69 | 1.715 | 2.873 | 37.7% | -1.366 | 118.32 | True |
| `Q2_volume_z20_0.203970_1.668315` | 68 | 2.833 | 5.775 | 61.8% | 3.501 | 192.64 | True |
| `Q3_volume_z20_1.668315_4.232499` | 68 | 2.028 | 4.084 | 57.4% | 2.596 | 137.91 | True |
| `Q4_high_volume_z20_ge_4.232499` | 69 | 1.918 | 5.079 | 69.6% | 2.685 | 132.32 | True |

### Risk Percentile

| Bucket | N | ER | PF | WR | Median R | Total R | Decision-grade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `Q1_low_risk_pct_lt_0.002000` | 69 | 2.078 | 4.270 | 59.4% | 2.685 | 143.36 | True |
| `Q2_risk_pct_0.002000_0.002000` | 68 | 2.746 | 7.343 | 72.1% | 3.302 | 186.72 | True |
| `Q3_risk_pct_0.002000_0.002000` | 68 | 2.182 | 4.529 | 60.3% | 2.844 | 148.40 | True |
| `Q4_high_risk_pct_ge_0.002000` | 69 | 1.489 | 2.571 | 34.8% | -1.390 | 102.71 | True |

## Numeric Winner/Loser Attribution

| Feature | N | Corr vs R | Winner median | Loser median | Median delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| `mfe_r` | 274 | 0.7352 | 10.113718 | 3.959126 | 6.154593 |
| `mae_r` | 274 | -0.3753 | 0.000000 | 2.057795 | -2.057795 |
| `hold_bars` | 274 | 0.2989 | 4.000000 | 2.000000 | 2.000000 |
| `tfi_15m_prev` | 274 | 0.2268 | 0.138136 | 0.050191 | 0.087945 |
| `sweep_depth_pct` | 274 | 0.1362 | 0.008448 | 0.008154 | 0.000294 |
| `oi_change_24h_pct` | 274 | 0.1270 | 0.000000 | -0.010204 | 0.010204 |
| `funding_rate` | 274 | 0.1111 | 0.000100 | 0.000100 | 0.000000 |
| `risk_pct` | 274 | -0.0834 | 0.002000 | 0.002000 | -0.000000 |
| `range_width20_pct` | 274 | -0.0469 | 0.022924 | 0.032988 | -0.010064 |
| `atr14_pct` | 274 | -0.0384 | 0.004865 | 0.006627 | -0.001762 |
| `realized_vol20` | 274 | 0.0282 | 0.002975 | 0.004007 | -0.001032 |
| `volume_z20` | 274 | -0.0032 | 2.276936 | 0.919539 | 1.357397 |

## Loss Archetypes

| Archetype | Losses | Loss share | ER | PF | Median R |
| --- | ---: | ---: | ---: | ---: | ---: |
| `direct_stop_loss` | 9 | 7.6% | -1.503 | 0.000 | -1.549 |
| `loss_after_1r_mfe` | 110 | 92.4% | -1.520 | 0.000 | -1.549 |

## Scarcity Map

- Months with at least one accepted trade: 43
- Monthly accepted trades: min=1, median=4, mean=6.37, max=30
- Zero-trade months are not inferred from accepted-only data.
- Near-threshold accepted definition: 0.00649 to 0.00714
- Near-threshold accepted trades: 63 (23.0% of accepted population)
- Near-threshold ER: 1.635
- Near-threshold PF: 3.046
- Near-threshold win rate: 47.6%

## Invalidation Criteria Evaluation

- Stop reasons: None
- Explore/context reasons: ['rejected backtest population unavailable; near-miss edge cannot be claimed in this diagnostic']
- Rejected-candidate edge claim: NOT MADE

## Recommendation

### Verdict: PLAN_NEAR_MISS_RECONSTRUCTION_DIAGNOSTIC

The shallowest accepted depth quartile is still strongly positive, but rejected candidates are not persisted, so the next step must reconstruct near-miss candidates rather than relax thresholds.

Next diagnostic must reconstruct rejected near-miss candidates before any BTC threshold expansion is considered. The current evidence supports investigation, not deployment or threshold relaxation.

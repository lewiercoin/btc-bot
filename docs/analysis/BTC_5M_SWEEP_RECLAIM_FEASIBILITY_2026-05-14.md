# BTC 5m vs 15m Sweep/Reclaim Feasibility Study

**Date:** 2026-05-14 15:36 UTC
**Milestone:** BTC_5M_SWEEP_RECLAIM_FEASIBILITY_V1
**Analysis Period:** 2024-01-01 to 2026-03-28 (26.8 months)
**Baseline:** trial-00095 exact parameters
**5m Scaling:** Bar-count params × 3 (preserving time windows)

> **IMPORTANT CAVEAT:** Both 5m and 15m results use a standalone research harness
> that bypasses BacktestRunner. Results are internally consistent (fair 5m vs 15m comparison)
> but should NOT be directly compared with official BacktestRunner metrics from M3/WF studies.
> Trade simulation uses simplified fills (no partial exits, no trailing stop, no funding accrual).

## Verdict: `5M_FREQUENCY_FAIL_QUALITY_PASS`

Frequency gate failed; all quality gates passed.

- **trade_count_increase**: FAIL — 5m has 1.3x trades vs 15m (need ≥2x)
- **expectancy_r**: PASS — 5m ER=2.351 > 1.0 (+11% vs 15m)
- **profit_factor**: PASS — 5m PF=6.63 > 1.5 (+68% vs 15m)
- **win_rate**: PASS — 5m WR=72.1% (+21pp vs 15m)
- **max_drawdown**: PASS — 5m DD ratio 1.0x vs 15m
- **mae_improvement**: PASS — 5m MAE -0.669R vs 15m -1.109R (-40%)
- **concentration**: PASS — Max month 40.0%
- **overtrading**: PASS — No overtrading flags

## Signal Funnel Comparison

| Metric | 15m | 5m | 5m/15m Ratio |
|---|---:|---:|---:|
| Total bars | 78,433 | 235,297 | 3.00x |
| sweep_detected | 48,606 | 127,533 | 2.62x |
| sweep_too_shallow | 45,649 | 126,108 | 2.76x |
| reclaim_detected | 102 | 23 | 0.23x |
| signal_candidates | 206 | 73 | 0.35x |
| governance_rejected | 32 | 4 | 0.12x |
| risk_rejected | 127 | 8 | 0.06x |
| **trades_executed** | **47** | **61** | **1.30x** |

### Blocked-By Breakdown

| Reason | 15m | 5m |
|---|---:|---:|
| direction_unresolved | 59 | 15 |
| no_reclaim | 1,802 | 903 |
| no_sweep | 29,827 | 107,764 |
| regime_direction_whitelist | 5 | 1 |
| sweep_too_shallow | 45,649 | 126,108 |
| uptrend_continuation_weak | 885 | 433 |

## Performance Comparison

| Metric | 15m | 5m | Gate | Status |
|---|---:|---:|---|---|
| Trade count | 47 | 61 | 5m ≥ 2× 15m | ❌ |
| Expectancy R | 2.110 | 2.351 | > 1.0 | ✅ |
| Profit Factor | 3.95 | 6.63 | > 1.5 | ✅ |
| Win Rate % | 51.1% | 72.1% | — | — |
| Max DD (R) | 4.49 | 4.50 | ≤ 15m | ✅ |
| Trades/month | 1.8 | 2.3 | — | — |
| Avg winner R | 5.533 | 3.839 | — | — |
| Avg loser R | -1.462 | -1.500 | — | — |
| Median R | 1.832 | 2.594 | — | — |
| Avg MAE R | -1.109 | -0.669 | — | — |
| Avg MFE R | 6.220 | 5.058 | — | — |
| Max consec. losses | 3 | 3 | — | — |

## Frequency Analysis

| Metric | 15m | 5m |
|---|---:|---:|
| Trades/month | 1.8 | 2.3 |
| Trade count ratio (5m/15m) | — | 1.30x |

### Overtrading Flags

| Flag | 15m | 5m | Concern? |
|---|---:|---:|---|
| Max trades/day | 4 | 4 | ✅ |
| Days > 5 trades | 0 | 0 | ✅ |
| Min gap (min) | 30.0 | 35.0 | ✅ |
| Gaps < 30min | 0 | 0 | ✅ |

### Concentration Risk

| Metric | 15m | 5m | Gate |
|---|---:|---:|---|
| Max month PnL % | 39.3% | 40.0% | < 50% | 
| Concentrated? | NO | NO | ✅ |

## ER by Regime

| Regime | 15m ER | 15m Trades | 5m ER | 5m Trades |
|---|---:|---:|---:|---:|
| downtrend | -1.500 | 1 | -1.500 | 1 |
| normal | 0.000 | 0 | 0.846 | 2 |
| uptrend | 2.188 | 46 | 2.469 | 58 |

## Cost Sensitivity (5m)

| Cost Multiplier | ER | PF |
|---|---:|---:|
| 1x | 2.351 | 6.63 |
| 2x | 1.715 | 3.88 |
| 3x | 1.079 | 2.4 |

## ER by Month (5m)

| Month | 5m ER | 5m Trades | 15m ER | 15m Trades |
|---|---:|---:|---:|---:|
| 2024-01 | 1.963 | 7 | 1.993 | 14 |
| 2024-02 | 3.067 | 4 | 2.932 | 11 |
| 2024-03 | 2.487 | 25 | 1.773 | 22 |
| 2024-04 | 5.050 | 2 | 0.000 | 0 |
| 2024-05 | 2.594 | 1 | 0.000 | 0 |
| 2024-07 | 2.485 | 1 | 0.000 | 0 |
| 2024-08 | -1.500 | 1 | 0.000 | 0 |
| 2024-11 | 2.254 | 5 | 0.000 | 0 |
| 2024-12 | 3.033 | 6 | 0.000 | 0 |
| 2025-01 | 2.567 | 4 | 0.000 | 0 |
| 2025-02 | 3.192 | 1 | 0.000 | 0 |
| 2025-05 | 3.113 | 1 | 0.000 | 0 |
| 2025-10 | -1.500 | 3 | 0.000 | 0 |

## Parameter Adaptation

| Parameter | 15m Value | 5m Value | Scaling |
|---|---:|---:|---|
| atr_period | 27 | 81 | ×3 (time window) |
| equal_level_lookback | 276 | 828 | ×3 (time window) |
| level_min_age_bars | 5 | 15 | ×3 (time window) |
| min_sweep_depth_pct | 0.00649 | 0.00649 | unchanged (dimensionless) |
| confluence_min | 3.9 | 3.9 | unchanged (dimensionless) |
| sweep_buf_atr | 0.46 | 0.46 | unchanged (ATR-relative) |
| reclaim_buf_atr | 0.07 | 0.07 | unchanged (ATR-relative) |
| wick_min_atr | 0.2 | 0.2 | unchanged (ATR-relative) |

## Data Quality

| Item | Value |
|---|---|
| 5m data source | Binance Futures API (/fapi/v1/klines) |
| 5m data range | 2022-01-01 to 2026-03-28 |
| 5m total bars | 447,000 |
| 5m quality | PASS (0 duplicates, 0 OHLC violations, 100.33% coverage) |
| 15m data source | replay-run13-regime-aware-trial-00063.db |
| 15m data range | 2020-09-01 to 2026-03-28 |
| Analysis period | 2024-01-01 to 2026-03-28 |
| Supplementary data | 1h/4h/funding/OI/aggtrades from 15m replay DB |

## Methodology Notes

- **Harness:** Standalone research script, NOT BacktestRunner
- **Trade simulation:** TP1 or SL hit within max_hold_bars, simplified (no partial exits, no trailing)
- **Fees:** 0.04% per side (taker)
- **Slippage:** 3.0 bps per side
- **Max hold:** 34h (408 bars @5m, 136 bars @15m)
- **Governance:** Cooldown after loss, duplicate level check
- **Risk:** Max 1 position, max 5 trades/day, min RR check
- **Both 5m and 15m use same harness** for fair comparison

## Recommendation

5m shows clear quality improvement across all edge metrics (ER +11%, PF +68%, WR +21pp, MAE -40%) but insufficient frequency gain (1.30x < 2.0x gate). The frequency bottleneck is structural: 5m candles have smaller range, making single-bar sweep+reclaim less likely (reclaim detection dropped 102 → 23, a 0.23x ratio).

**Defer full 5m runtime upgrade.** The marginal frequency gain does not justify the integration complexity of replacing the 15m decision engine.

**Consider hybrid architecture:** 15m signal detection (proven frequency) + 5m execution timing layer (proven quality). This preserves the 15m signal pipeline while exploiting 5m's superior entry precision. Recommended next study: `15M_SIGNAL_5M_EXECUTION_OVERLAY_FEASIBILITY`.

## Strategic Interpretation

### A. 5m as Standalone Runtime: FAIL

5m cannot replace 15m as the primary signal timeframe. The trade count increase is only 1.30x (61 vs 47 trades over 26.8 months), far below the 2.0x gate required to justify a full runtime migration. The root cause is a **reclaim detection bottleneck**: 5m candles detect 2.62x more raw sweeps but reclaim detection *drops* from 102 to 23 (0.23x). Smaller candle bodies are less likely to sweep a level AND reclaim it within a single bar.

### B. 5m as Quality/Timing Layer: PASS

All quality metrics improve on 5m, indicating the edge is *sharper* at higher resolution:

| Metric | 15m | 5m | Change |
|---|---:|---:|---:|
| Expectancy R | 2.110 | 2.351 | +11% |
| Profit Factor | 3.95 | 6.63 | +68% |
| Win Rate | 51.1% | 72.1% | +21pp |
| Avg MAE (R) | -1.109 | -0.669 | -40% |
| Avg MFE (R) | 6.220 | 5.058 | -19% |

The MAE improvement (-40%) is particularly significant: 5m entries experience substantially less adverse excursion before reaching profit targets. This suggests 5m provides better entry timing precision even if it doesn't generate more signals.

### C. Full 5m Runtime Upgrade: Not Justified

A full 5m runtime replacement would require:
- Modifying BacktestRunner, ReplayLoader, and data pipeline for 5m candle support
- Re-running Optuna optimization campaigns on 5m data
- Revalidating walk-forward evidence on 5m timeframe
- Updating production data collection (market_data.py) for 5m candles

This infrastructure cost is not justified by a 1.30x frequency gain. The 5m edge quality improvement alone does not increase trade count sufficiently to compound returns faster.

### D. Hybrid Direction: Recommended

**Proposed study:** `15M_SIGNAL_5M_EXECUTION_OVERLAY_FEASIBILITY`

Concept: Preserve the 15m signal detection pipeline (proven frequency, validated parameters) but add a 5m execution timing layer that refines entry price after a 15m signal fires.

Hypothesis: When a 15m signal is generated, waiting for a 5m sweep+reclaim confirmation within the same or next 15m bar could reduce MAE by ~40% (as observed in this study) without reducing signal count.

This hybrid approach:
- **Preserves** 15m signal frequency (no reclaim bottleneck — 15m still decides when to trade)
- **Exploits** 5m entry precision (MAE -40%, WR +21pp)
- **Avoids** full infrastructure migration (5m layer is execution-only, not signal-generating)
- **Scope:** Research-only feasibility study, same offline methodology as this report

---
*Generated by research_lab/analysis_btc_5m_sweep_reclaim_feasibility.py*
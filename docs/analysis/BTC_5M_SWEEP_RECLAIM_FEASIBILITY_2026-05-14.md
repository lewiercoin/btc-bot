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

## Verdict: `5M_FEASIBILITY_FAIL`

One or more gates failed.

- **trade_count_increase**: FAIL — 5m has 1.3x trades vs 15m (need ≥2x)
- **expectancy_r**: PASS — 5m ER=2.351 > 1.0
- **profit_factor**: PASS — 5m PF=6.63 > 1.5
- **max_drawdown**: PASS — 5m DD ratio 1.0x vs 15m
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

5m does not improve on 15m meaningfully. Stay on 15m. Defer 5m upgrade.

---
*Generated by research_lab/analysis_btc_5m_sweep_reclaim_feasibility.py*
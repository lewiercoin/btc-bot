# TREND SWEEP SPECIALIST — AUDIT PACKAGE

**Builder:** Cascade
**Milestone:** SWEEP-RECLAIM-FAMILY-EXPANSION-V1
**Variant:** trend_sweep_specialist (Variant 2 of 3-5)
**Date:** 2026-05-13
**Checkpoint:** 2

## Verdict: **HYPOTHESIS_FAILED**

ER 0.6281 with 159 trades (adequate sample). Hard stop triggered.
Novel component (uptrend SHORT) has zero edge (ER 0.089).

### Key Metrics

| Metric | Value |
|---|---|
| Trades | 159 |
| Expectancy R | 0.6281 |
| Profit Factor | 1.8872 |
| Win Rate | 47.80% |
| Max Drawdown | 12.38% |
| PnL abs | +$9,915 |

### Validation Gates

| Gate | Result |
|---|---|
| er_above_1_5 | FAIL |
| er_above_1_0 | FAIL |
| min_trades_20 | PASS |
| overlap_below_30 | MOOT (downtrend LONG fully overlaps trial-00095) |
| win_rate_above_50 | FAIL |
| pf_above_2_5 | FAIL |

### Issues

- HARD_STOP: ER 0.6281 < 1.0 with 159 trades
- Uptrend SHORT (novel independent entry): ER 0.089, zero edge
- Downtrend LONG: ER 0.76, PF 2.10 — real edge but already in trial-00095
- No independent alpha available from trending regime context alone

### Decision Funnel

- Cycles total: 148,609
- Regime rejected: 30,121 (20.3%)
- Volatility rejected: 0 (disabled)
- Context passed: 118,488 (79.7%)
- Signal generated: 233 (0.20% of context-passed)
- Governance rejected: 26
- Risk rejected: 48
- Trades opened: 159

### Independence Analysis

MOOT — downtrend LONG (127/159 trades) fully overlaps with trial-00095's whitelist.
Uptrend SHORT (32 trades) would be independent but has zero edge (ER 0.089).

### Config

```json
{
  "allowed_regimes": ["downtrend", "uptrend"],
  "downtrend_directions": ["LONG"],
  "min_trend_cycles": 0,
  "uptrend_directions": ["SHORT"],
  "volatility_atr_norm_min": 0.006,
  "volatility_filter_enabled": false
}
```

### Per-Direction Breakdown

| Direction | Trades | ER | PF | Win Rate | Sharpe |
|---|---:|---:|---:|---:|---:|
| LONG | 127 | 0.76 | 2.10 | 48.03% | 5.34 |
| SHORT | 32 | 0.09 | 1.09 | 46.88% | 0.92 |

### Per-Regime Breakdown

| Regime | Trades | ER | PF | Win Rate | Sharpe |
|---|---:|---:|---:|---:|---:|
| downtrend | 127 | 0.76 | 2.10 | 48.03% | 5.34 |
| uptrend | 32 | 0.09 | 1.09 | 46.88% | 0.92 |

### Emerging Pattern (V1 + V2)

| Context | Direction | Trades | ER | Assessment |
|---|---|---:|---:|---|
| Normal | LONG | 16 | 0.02 | Zero edge |
| Normal | SHORT | 5 | -0.92 | Destructive |
| Downtrend | LONG | 127 | 0.76 | Moderate (already in trial-00095) |
| Uptrend | SHORT | 32 | 0.09 | Zero edge |

**Pattern:** SHORT sweep_reclaim signals consistently fail. The sweep_reclaim edge is LONG-biased and NOT regime-specific. Trial-00095's ER 2.1 comes from Optuna-optimized parameters, not regime context.

### Root Cause

The sweep_reclaim edge is:
1. LONG-biased (SHORT never works in any regime)
2. Parameter-dependent (trial-00095 uses optimized confluence/TFI thresholds)
3. NOT context-dependent (regime filtering alone cannot create independent alpha)

Context-based family expansion through regime filtering is not a viable path to independent alpha.

### Deliverables

- `research_lab/setups/trend_sweep_specialist.py` — Config + filters
- `research_lab/backtest_trend_sweep.py` — Backtest runner + reports
- `tests/test_research_lab_trend_sweep.py` — 19 tests (all pass)
- `research_lab/reports/trend_sweep_specialist_validation_report.md` — Full report
- `research_lab/reports/TREND_SWEEP_SPECIALIST_AUDIT_PACKAGE.md` — This file

### Fast Failure Discipline

ER < 1.0 with 159 trades → REJECT immediately.
Two consecutive HYPOTHESIS_FAILED (V1 + V2) suggests regime-based family expansion may be exhausted.
Variant 3 (special regimes) is the final regime test before concluding this approach.

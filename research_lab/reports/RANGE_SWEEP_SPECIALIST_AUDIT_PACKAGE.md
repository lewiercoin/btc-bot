# RANGE SWEEP SPECIALIST — AUDIT PACKAGE

**Builder:** Cascade
**Milestone:** SWEEP-RECLAIM-FAMILY-EXPANSION-V1
**Variant:** range_sweep_specialist (Variant 1 of 3-5)
**Date:** 2026-05-13
**Checkpoint:** 1

## Verdict: **HYPOTHESIS_FAILED**

ER -0.20 with 21 trades (adequate sample). Hard stop triggered. Move to Variant 2.

### Key Metrics (Run 2 — definitive, no volatility filter)

| Metric | Value |
|---|---|
| Trades | 21 |
| Expectancy R | -0.2026 |
| Profit Factor | 0.7648 |
| Win Rate | 28.57% |
| Max Drawdown | 8.25% |
| Sharpe | -2.26 |

### Validation Gates

| Gate | Result |
|---|---|
| er_above_1_5 | FAIL |
| er_above_1_0 | FAIL |
| min_trades_20 | PASS |
| overlap_below_30 | MOOT (hypothesis failed) |
| win_rate_above_50 | FAIL |
| pf_above_2_5 | FAIL |

### Issues

- HARD_STOP: ER -0.2026 < 1.0 with adequate sample (21 trades)
- SHORT in normal regime: ER -0.92, clearly destructive
- LONG in normal regime: ER 0.02, no edge
- Structure slope filter: zero practical impact (97 rejected cycles, 0 trade candidates)

### Iteration Log

| Run | Config Changes | Trades | ER | PF | Verdict |
|---|---|---:|---:|---:|---|
| 1 | Default (all filters) | 3 | 0.63 | 1.66 | INSUFFICIENT_SAMPLE |
| 2 | volatility_filter_enabled=False | 21 | -0.20 | 0.76 | HYPOTHESIS_FAILED |
| 3 | slope_threshold=999 + no vol | 21 | -0.20 | 0.76 | HYPOTHESIS_FAILED |

Run 2 is the definitive result: volatility filter was the only filter with material impact on sample size.

### Decision Funnel (Run 2)

- Cycles total: 148,609
- Regime rejected: 135,313 (91.1%)
- Structure rejected: 97 (0.07%)
- Volatility rejected: 0 (disabled)
- Context passed: 13,199 (8.9%)
- Signal generated: 32 (0.24% of context-passed)
- Governance rejected: 3
- Risk rejected: 8
- Trades opened: 21

### Per-Direction Breakdown (Run 2)

| Direction | Trades | ER | PF | Win Rate |
|---|---:|---:|---:|---:|
| LONG | 16 | 0.02 | 1.00 | 31.25% |
| SHORT | 5 | -0.92 | 0.13 | 20.00% |

### Per-Regime Breakdown (Run 2)

| Regime | Trades | ER | PF | Win Rate |
|---|---:|---:|---:|---:|
| normal | 21 | -0.20 | 0.76 | 28.57% |

### Independence Analysis

Not computed — moot because hypothesis failed. Overlap measurement deferred to Variant 2 (if it reaches CANDIDATE status).

### Config (Run 2)

```json
{
  "allowed_regime": "normal",
  "normal_directions": ["LONG", "SHORT"],
  "structure_slope_atr_max": 0.3,
  "structure_slope_min_candles": 48,
  "structure_slope_window": 96,
  "volatility_atr_norm_max": 0.015,
  "volatility_filter_enabled": false
}
```

### Root Cause

The sweep_reclaim edge does NOT concentrate in normal/range-bound markets. Trial-00095 (ER 2.1) achieves its edge across all regimes. Restricting to normal regime removes the regimes where the edge actually exists — likely downtrend, compression, crowded_leverage, or post_liquidation.

### Strategic Finding

This is a meaningful negative result:
- **Normal regime is the WEAKEST context** for sweep_reclaim, not the strongest
- The edge is likely driven by structural asymmetries in non-normal regimes
- Variant 2 (Trend Sweep Specialist) should test the opposite hypothesis

### Deliverables

- `research_lab/setups/range_sweep_specialist.py` — Config + filters
- `research_lab/backtest_range_sweep.py` — Backtest runner + reports
- `tests/test_research_lab_range_sweep.py` — 23 tests (all pass)
- `research_lab/reports/range_sweep_specialist_validation_report.md` — Full report
- `research_lab/reports/RANGE_SWEEP_SPECIALIST_AUDIT_PACKAGE.md` — This file

### Fast Failure Discipline

Per handoff protocol: ER < 1.0 (hard stop) → REJECT immediately → move to Variant 2.
This is NOT project failure — it is efficient search through structure context space.

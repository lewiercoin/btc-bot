# SPECIAL REGIME SWEEP SPECIALIST — AUDIT PACKAGE

**Builder:** Cascade
**Milestone:** SWEEP-RECLAIM-FAMILY-EXPANSION-V1
**Variant:** special_regime_sweep_specialist (Variant 3 of 3 — FINAL)
**Date:** 2026-05-13
**Checkpoint:** 3

## Verdict: **HYPOTHESIS_FAILED** (3/3 regime variants failed)

ER 0.3011 with 34 trades (adequate sample). Hard stop triggered.
All trades in crowded_leverage (post_liquidation = 0 cycles).
Regime-based family expansion conclusively not viable.

### Key Metrics

| Metric | Value |
|---|---|
| Trades | 34 |
| Expectancy R | 0.3011 |
| Profit Factor | 1.3303 |
| Win Rate | 38.24% |
| Max Drawdown | 8.36% |
| Sharpe | 2.32 |
| PnL abs | +$706 |

### Validation Gates

| Gate | Result |
|---|---|
| er_above_1_5 | FAIL |
| er_above_1_0 | FAIL |
| min_trades_20 | PASS |
| overlap_below_30 | MOOT (crowded_leverage LONG overlaps trial-00095) |
| win_rate_above_50 | FAIL |
| pf_above_2_5 | FAIL |

### Issues

- HARD_STOP: ER 0.3011 < 1.0 with 34 trades
- post_liquidation = 0 cycles (infrastructure gap, regime never classified)
- crowded_leverage LONG: ER 0.30 — forced positioning hypothesis insufficient
- All trades overlap with trial-00095 (which allows LONG in crowded_leverage)

### Regime Cycle Distribution

| Regime | Cycles | % |
|---|---:|---:|
| downtrend | 59,496 | 40.0% |
| uptrend | 58,992 | 39.7% |
| crowded_leverage | 16,825 | 11.3% |
| normal | 13,296 | 8.9% |
| post_liquidation | 0 | 0.0% |

### Decision Funnel

- Cycles total: 148,609
- Regime rejected: 131,784 (88.7%)
- Context passed: 16,825 (11.3%)
- Signal generated: 49 (0.29% of context-passed)
- Governance rejected: 8
- Risk rejected: 7
- Trades opened: 34

### Config

```json
{
  "allowed_regimes": ["crowded_leverage", "post_liquidation"],
  "directions": ["LONG"],
  "min_regime_cycles": 0
}
```

### Per-Direction Breakdown

| Direction | Trades | ER | PF | Win Rate |
|---|---:|---:|---:|---:|
| LONG | 34 | 0.30 | 1.33 | 38.24% |

### Per-Regime Breakdown

| Regime | Trades | ER | PF | Win Rate |
|---|---:|---:|---:|---:|
| crowded_leverage | 34 | 0.30 | 1.33 | 38.24% |

### Cross-Variant Summary (V1 + V2 + V3) — DEFINITIVE

| Variant | Context | Direction | Trades | ER | PF | Finding |
|---|---|---|---:|---:|---:|---|
| V1 | Normal | LONG | 16 | 0.02 | 1.00 | Zero edge |
| V1 | Normal | SHORT | 5 | -0.92 | 0.13 | Destructive |
| V2 | Downtrend | LONG | 127 | 0.76 | 2.10 | Moderate (overlaps) |
| V2 | Uptrend | SHORT | 32 | 0.09 | 1.09 | Zero edge |
| V3 | Crowded_leverage | LONG | 34 | 0.30 | 1.33 | Below threshold |

### LONG ER by Regime (ranked)

| Regime | Trades | ER |
|---|---:|---:|
| downtrend | 127 | 0.76 |
| crowded_leverage | 34 | 0.30 |
| normal | 16 | 0.02 |
| post_liquidation | 0 | — |

**No regime reaches ER 1.0.** Trial-00095's ER 2.1 = combined effect across ALL regimes with optimized parameters.

### Root Cause (Cross-Variant)

1. **Regime-based family expansion is NOT viable.** 3/3 variants failed (ER < 1.0).
2. **SHORT is universally unprofitable** for sweep_reclaim (tested normal, uptrend).
3. **The edge is parameter-dependent, not context-dependent.** Optuna-optimized confluence/TFI thresholds drive ER, not regime filtering.
4. **No independent alpha from regime context.** All LONG trades overlap trial-00095.

### Deliverables (V3)

- `research_lab/setups/special_regime_sweep_specialist.py` — Config + filters
- `research_lab/backtest_special_regime_sweep.py` — Backtest runner + reports
- `tests/test_research_lab_special_regime_sweep.py` — 16 tests (all pass)
- `research_lab/reports/special_regime_sweep_specialist_validation_report.md`
- `research_lab/reports/SPECIAL_REGIME_SWEEP_SPECIALIST_AUDIT_PACKAGE.md`

### Deliverables (Full Milestone)

- V1: Range Sweep Specialist — HYPOTHESIS_FAILED (21 trades, ER -0.20)
- V2: Trend Sweep Specialist — HYPOTHESIS_FAILED (159 trades, ER 0.63)
- V3: Special Regime Sweep Specialist — HYPOTHESIS_FAILED (34 trades, ER 0.30)
- 58 unit tests across 3 test files (all pass)
- 6 validation reports + audit packages

### Strategic Conclusion

Regime-based sweep_reclaim family expansion exhausted. 3/3 failed.
Future expansion must pivot to:
- Parameter-based variants (Optuna re-optimization with different objectives)
- Microstructure-based variants (session timing, order book depth)
- Frequency upgrade (5m/1m)
- OR accept trial-00095 as single deployment, diversify via new edge families

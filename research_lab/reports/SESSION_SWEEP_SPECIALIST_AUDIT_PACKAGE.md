# SESSION SWEEP SPECIALIST — AUDIT PACKAGE

**Builder:** Cascade
**Milestone:** SWEEP-RECLAIM-FAMILY-EXPANSION-V1
**Variant:** session_sweep_specialist (Variant 4 — Microstructure, FINAL 15m test)
**Date:** 2026-05-13
**Checkpoint:** 4

## Verdict: **HYPOTHESIS_FAILED** (4/4 context variants failed — 15m expansion exhausted)

ER 0.7778 with 126 trades (adequate sample). Hard stop triggered.
Best metrics of any variant (PF 2.42, Win 57%, Sharpe 6.93) but still ER < 1.0.
Microstructure session filtering insufficient — edge is parameter-dependent.

### Key Metrics

| Metric | Value |
|---|---|
| Trades | 126 |
| Expectancy R | 0.7778 |
| Profit Factor | 2.4209 |
| Win Rate | 57.14% |
| Max Drawdown | 3.55% |
| Sharpe | 6.93 |
| PnL abs | +$9,934 |
| Avg Winner R | 2.29 |
| Avg Loser R | -1.24 |
| Max Consecutive Losses | 4 |

### Validation Gates

| Gate | Result |
|---|---|
| er_above_1_5 | FAIL |
| er_above_1_0 | FAIL |
| min_trades_20 | PASS (126) |
| overlap_below_30 | MOOT (hypothesis failed) |
| win_rate_above_50 | PASS (57.14%) |
| pf_above_2_5 | FAIL (2.42, marginal) |

### Issues

- HARD_STOP: ER 0.7778 < 1.0 with 126 trades
- Post-signal rejection 62.4% (governance: 51, risk: 158 of 335 signals)
- Asia session dominated by uptrend trades (90/126 = 71%)
- No independence — session filter subsets trial-00095's time-agnostic trade set

### Config

```json
{
  "directions": ["LONG"],
  "session_end_hour": 8,
  "session_label": "asia",
  "session_start_hour": 0
}
```

### Decision Funnel

- Cycles total: 148,609
- Session rejected: 99,072 (66.7%)
- Session passed: 49,537 (33.3%)
- Signal generated: 335 (0.68% of session-passed)
- Governance rejected: 51
- Risk rejected: 158
- Trades opened: 126

### Trades Per Hour (session window)

| UTC Hour | Trades |
|---:|---:|
| 00 | 35 |
| 01 | 20 |
| 02 | 13 |
| 03 | 12 |
| 04 | 15 |
| 05 | 11 |
| 06 | 11 |
| 07 | 9 |

### Per-Direction Breakdown

| Direction | Trades | ER | PF | Win Rate |
|---|---:|---:|---:|---:|
| LONG | 126 | 0.78 | 2.42 | 57.14% |

### Per-Regime Breakdown (within Asia session)

| Regime | Trades | ER | PF | Win Rate |
|---|---:|---:|---:|---:|
| uptrend | 90 | 0.89 | 2.85 | 62.2% |
| downtrend | 30 | 0.86 | 2.37 | 53.3% |
| crowded_leverage | 3 | -1.33 | 0.00 | 0% |
| normal | 3 | -1.34 | 0.00 | 0% |

### Independence Analysis

Not computed — hypothesis failed (ER < 1.0). Session-filtered trades are a subset
of trial-00095's time-agnostic trade set. No independence possible by construction
(same signal engine, same parameters, time filter only removes trades).

### Cross-Variant Summary (V1 + V2 + V3 + V4) — DEFINITIVE

| Variant | Mechanism | Context | Direction | Trades | ER | PF | Finding |
|---|---|---|---|---:|---:|---:|---|
| V1 | Regime | Normal | LONG | 16 | 0.02 | 1.00 | Zero edge |
| V1 | Regime | Normal | SHORT | 5 | -0.92 | 0.13 | Destructive |
| V2 | Regime | Downtrend | LONG | 127 | 0.76 | 2.10 | Moderate (overlaps) |
| V2 | Regime | Uptrend | SHORT | 32 | 0.09 | 1.09 | Zero edge |
| V3 | Regime | Crowded_leverage | LONG | 34 | 0.30 | 1.33 | Below threshold |
| V4 | Microstructure | Asia session | LONG | 126 | 0.78 | 2.42 | Best, still < 1.0 |

### LONG ER by Context (ranked across all variants)

| Context | Mechanism | Trades | ER | PF |
|---|---|---:|---:|---:|
| Asia + Uptrend | Micro+Regime | 90 | 0.89 | 2.85 |
| Asia + Downtrend | Micro+Regime | 30 | 0.86 | 2.37 |
| Asia session | Microstructure | 126 | 0.78 | 2.42 |
| Downtrend | Regime | 127 | 0.76 | 2.10 |
| Crowded_leverage | Regime | 34 | 0.30 | 1.33 |
| Normal | Regime | 16 | 0.02 | 1.00 |

**No context reaches ER 1.0.** Trial-00095 ER 2.1 = Optuna parameter optimization, not context specialization.

### Root Cause (Cross-Variant, Final)

1. **15m context expansion NOT viable.** 4/4 variants tested (3 regime + 1 microstructure). None produce ER > 1.0 independently.

2. **sweep_reclaim = singular, parameter-optimized edge.** ER 2.1 from Optuna-tuned confluence, TFI, and risk thresholds — not from any regime, session, or microstructure context.

3. **Context filtering can only subset the trade set.** It cannot create new independent entries. All context-filtered trades are subsets of trial-00095's behavior.

4. **SHORT universally unprofitable** (normal: -0.92, uptrend: 0.09). LONG-only correct.

5. **Session timing shows marginal improvement** (best PF, win rate) but insufficient. The edge is in the parameters, not the context.

### Deliverables (V4)

- `research_lab/setups/session_sweep_specialist.py` — Config + session filter
- `research_lab/backtest_session_sweep.py` — Backtest runner + reports
- `tests/test_research_lab_session_sweep.py` — 23 tests (all pass)
- `research_lab/reports/session_sweep_specialist_validation_report.md`
- `research_lab/reports/SESSION_SWEEP_SPECIALIST_AUDIT_PACKAGE.md`

### Deliverables (Full Milestone — V1 through V4)

| Variant | Verdict | Trades | ER | Tests |
|---|---|---:|---:|---:|
| V1 Range Sweep | HYPOTHESIS_FAILED | 21 | -0.20 | 23 |
| V2 Trend Sweep | HYPOTHESIS_FAILED | 159 | 0.63 | 19 |
| V3 Special Regime | HYPOTHESIS_FAILED | 34 | 0.30 | 16 |
| V4 Session Sweep | HYPOTHESIS_FAILED | 126 | 0.78 | 23 |
| **Total** | **4/4 failed** | **340** | — | **81** |

- 81 unit tests across 4 test files (all pass)
- 8 validation reports + audit packages (4 builder + 4 auditor)
- 340 trades analyzed across 4 hypotheses

### Strategic Conclusion

15m sweep_reclaim context expansion **conclusively exhausted** (4/4 failures, 340 trades).

**Recommended next step: Accept singular edge (Option 2)**
- trial-00095 IS the sweep_reclaim edge at 15m
- Focus on live validation (30-50 trades, 6-10 months)
- Monitor ER convergence (backtest 2.1 vs live)
- Defer 5m frequency upgrade until edge stability confirmed

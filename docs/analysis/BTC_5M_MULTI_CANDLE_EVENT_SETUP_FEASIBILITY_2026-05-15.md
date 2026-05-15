# BTC 5m Multi-Candle Event Setup Feasibility

**Date:** 2026-05-15
**Milestone:** BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_V1
**Verdict:** `MULTI_CANDLE_FAIL`
**Analysis Period:** 2024-01-01 to 2026-03-28
**Baseline:** trial-00095 M5 15m baseline, same analysis period

> Offline research only. No production, PAPER, runtime, settings, core, execution, or orchestrator changes.

## Executive Summary

- **Key Finding:** No tested 5m multi-candle setup passed the quality and frequency gates.
- **Recommendation:** Claude Code audit required before scheduling follow-up research.

## Data Sources / Manifests

| Dataset | Status | Rows | Notes |
|---|---|---:|---|
| 5m candles DB | PASS | 447000 | `research_lab/snapshots/btc_5m_2022_2026.db` |
| Replay DB OI | PASS | 524971 | Used by Setup B precondition when available |
| Replay DB funding | PASS | 6105 | Used by Setup B precondition when available |
| Historical force_orders | PASS | 146864 | research_lab\data\crowded_unwind_backtest.db; 2022-01-01T00:02:07.244000+00:00 to 2024-12-01T23:58:59.379000+00:00 |

**Data manifest hash:** `ca7d6158606706dc`
**Setup B data mode:** `OI_FUNDING_FORCE_ORDERS`

## Hypotheses

| Setup | Mechanism | Verdict | Best Variant |
|---|---|---|---|
| Compression Fakeout Reclaim | Compression -> fakeout -> reclaim | `FAIL` | `CFR_V3` |
| Crowded Unwind Reversal | Crowding -> forced move -> snapback | `FAIL` | `CUR_V1` |

## Baseline Comparison

| Metric | 15m Baseline | Compression Candidate | Crowded Candidate |
|---|---:|---:|---:|
| Trade Count | 47 | 73 | 174 |
| Expectancy R | 2.110 | -0.192 | -0.415 |
| Profit Factor | 3.950 | 0.371 | 0.224 |
| Win Rate % | 51.100 | 57.534 | 45.977 |
| Max DD R | 4.490 | 14.044 | 72.432 |
| Avg MAE R | -1.109 | -0.538 | -0.750 |
| Avg MFE R | 6.220 | 0.441 | 0.434 |

## All Tested Variants

| Setup | Variant | Trades | ER | PF | WR% | DD R | Freq Ratio | 2x Cost ER | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| compression_fakeout_reclaim | CFR_V1 | 280 | -0.385 | 0.149 | 35.714 | 107.994 | 5.957 | -0.814 | `FAIL` |
| compression_fakeout_reclaim | CFR_V2 | 123 | -0.290 | 0.254 | 47.154 | 36.285 | 2.617 | -0.633 | `FAIL` |
| compression_fakeout_reclaim | CFR_V3 | 73 | -0.192 | 0.371 | 57.534 | 14.044 | 1.553 | -0.495 | `FAIL` |
| crowded_unwind_reversal | CUR_V1 | 174 | -0.415 | 0.224 | 45.977 | 72.432 | 3.702 | -0.808 | `FAIL` |
| crowded_unwind_reversal | CUR_V2 | 109 | -0.422 | 0.243 | 48.624 | 46.292 | 2.319 | -0.771 | `FAIL` |
| crowded_unwind_reversal | CUR_V3 | 186 | -0.416 | 0.216 | 44.086 | 77.697 | 3.957 | -0.799 | `FAIL` |

## Signal Funnels

| Setup | Variant | Precondition | Event | Confirmation | Raw Signals | Trades | Overlap Skipped |
|---|---|---:|---:|---:|---:|---:|---:|
| compression_fakeout_reclaim | CFR_V1 | 71907 | 7178 | 329 | 304 | 280 | 24 |
| compression_fakeout_reclaim | CFR_V2 | 69887 | 4669 | 144 | 133 | 123 | 10 |
| compression_fakeout_reclaim | CFR_V3 | 60330 | 2743 | 84 | 78 | 73 | 5 |
| crowded_unwind_reversal | CUR_V1 | 74611 | 628 | 298 | 174 | 174 | 0 |
| crowded_unwind_reversal | CUR_V2 | 76390 | 376 | 157 | 109 | 109 | 0 |
| crowded_unwind_reversal | CUR_V3 | 74611 | 601 | 316 | 186 | 186 | 0 |

## Direction Split

| Setup | Direction | Trades | ER | PF | WR% |
|---|---|---:|---:|---:|---:|
| compression_fakeout_reclaim | LONG | 41 | -0.147 | 0.456 | 60.976 |
| compression_fakeout_reclaim | SHORT | 32 | -0.250 | 0.287 | 53.125 |
| crowded_unwind_reversal | LONG | 108 | -0.363 | 0.278 | 50.000 |
| crowded_unwind_reversal | SHORT | 66 | -0.499 | 0.148 | 39.394 |

## Concentration And OOS

| Setup | Max Month % | Top Month | Max Day % | Top Day | OOS Available | Test ER |
|---|---:|---|---:|---|---|---:|
| compression_fakeout_reclaim | 16.3% | 2025-07 | 5.2% | 2024-06-29 | True | -0.159 |
| crowded_unwind_reversal | 16.0% | 2024-06 | 5.7% | 2024-09-26 | True | 0.000 |

## Baseline Overlap

| Setup | Overlap With trial-00095 | Status |
|---|---:|---|
| compression_fakeout_reclaim | N/A | Official trial-00095 signal timestamps are unavailable in this standalone harness |
| crowded_unwind_reversal | N/A | Official trial-00095 signal timestamps are unavailable in this standalone harness |

## Gate Evaluation

### compression_fakeout_reclaim - CFR_V3

| Gate | Threshold | Actual | Status | Severity |
|---|---:|---:|---|---|
| min_trades | >= 20 | 73.000 | PASS | REQUIRED |
| min_er | >= 1.0 | -0.192 | FAIL | REQUIRED |
| min_pf | >= 1.5 | 0.371 | FAIL | REQUIRED |
| min_frequency_ratio | >= 1.5 | 1.553 | PASS | REQUIRED |
| max_dd_ratio | <= 1.5 | 3.128 | FAIL | REQUIRED |
| cost_sensitivity_2x | >= 0.5 | -0.495 | FAIL | REQUIRED |
| max_concentration_month | <= 0.6 | 0.163 | PASS | RECOMMENDED |
| max_concentration_day | <= 0.4 | 0.052 | PASS | RECOMMENDED |

### crowded_unwind_reversal - CUR_V1

| Gate | Threshold | Actual | Status | Severity |
|---|---:|---:|---|---|
| min_trades | >= 20 | 174.000 | PASS | REQUIRED |
| min_er | >= 1.0 | -0.415 | FAIL | REQUIRED |
| min_pf | >= 1.5 | 0.224 | FAIL | REQUIRED |
| min_frequency_ratio | >= 1.5 | 3.702 | PASS | REQUIRED |
| max_dd_ratio | <= 1.5 | 16.132 | FAIL | REQUIRED |
| cost_sensitivity_2x | >= 0.5 | -0.808 | FAIL | REQUIRED |
| max_concentration_month | <= 0.6 | 0.160 | PASS | RECOMMENDED |
| max_concentration_day | <= 0.4 | 0.057 | PASS | RECOMMENDED |

## Experiment Registry

| Setup | Experiment ID |
|---|---|
| compression_fakeout_reclaim | `exp-3e43a9d6d5a174b4` |
| crowded_unwind_reversal | `exp-fcfe67f74a383d11` |

## Verdict Taxonomy

- `MULTI_CANDLE_PASS`: at least one setup passes all gates and materially increases trade count.
- `MULTI_CANDLE_MARGINAL`: one setup improves frequency but quality is borderline or sample is fragile.
- `MULTI_CANDLE_FAIL`: no setup passes quality and frequency gates.
- `MULTI_CANDLE_BLOCKED`: required data unavailable for both setups.
- `PARTIAL_BLOCKED`: one setup blocked, one tested.

## Limitations

- Standalone research harness, not BacktestRunner.
- Simplified TP/SL simulation: no partial exits, no trailing, no funding accrual.
- Crowded unwind uses historical force orders from `research_lab/data/crowded_unwind_backtest.db`; coverage ends 2024-12-01, so that setup is evaluated only through the available force-order period.
- Official trial-00095 signal timestamps are not available in this harness, so direct overlap with baseline is not decision-grade.
- No parameter rescue was performed; all predefined variants are reported.

## Artifacts

- Hypothesis A: `research_lab/hypotheses/active/btc_5m_compression_fakeout_reclaim.json`
- Hypothesis B: `research_lab/hypotheses/active/btc_5m_crowded_unwind_reversal.json`
- Script: `research_lab/analysis_btc_5m_multi_candle_event_setup_feasibility.py`
- Report: `docs/analysis/BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_2026-05-15.md`

## Next-Step Recommendation

Close this branch unless Claude identifies a methodology issue. Do not rescue failed variants by expanding the grid.

---
*Generated by research_lab/analysis_btc_5m_multi_candle_event_setup_feasibility.py*
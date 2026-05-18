# Trend Pullback Reaccept Feasibility

**Milestone:** `TREND_PULLBACK_REACCEPT_FEASIBILITY_V1`
**Status:** READY_FOR_AUDIT
**Scope:** Research Lab offline-only; no runtime/core/orchestrator/settings/execution changes.
**Baseline:** trial-00095 15m sweep/reclaim

## Hypothesis

BTC LONG-only trend pullback reacceptance: in a completed 4h EMA uptrend, price pulls back below a pre-frozen 15m equal-low support level and later closes back above that level on a 15m bar. Entry is next 15m open.

## Data Audit

- Source DB: `research_lab\snapshots\replay-run13-regime-aware-trial-00063.db`
- 15m candles: 195347
- 4h candles: 12210
- 60s aggtrade buckets: 2927122

## Variant Results

| Variant | Verdict | Trades | ER | PF | Max DD R | 2x Cost ER | Timeout | Month Conc | WF Folds | Overlap |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `TPR_G0.006_B3_R0.05_TFI` | `FAIL` | 1450 | -0.421 | 0.57 | 617.36 | -0.869 | 2.1% | 8.6% | 0/4 | 0.7% |
| `TPR_G0.006_B3_R0.08_TFI` | `FAIL` | 1410 | -0.409 | 0.57 | 583.01 | -0.844 | 2.1% | 8.7% | 0/4 | 0.7% |
| `TPR_G0.006_B5_R0.05_TFI` | `FAIL` | 1414 | -0.408 | 0.57 | 583.91 | -0.846 | 2.8% | 8.9% | 0/4 | 0.6% |
| `TPR_G0.006_B5_R0.08_TFI` | `FAIL` | 1371 | -0.395 | 0.58 | 548.58 | -0.821 | 2.8% | 8.8% | 0/4 | 0.7% |
| `TPR_G0.010_B3_R0.05_TFI` | `FAIL` | 1336 | -0.421 | 0.57 | 566.04 | -0.862 | 2.0% | 9.4% | 0/4 | 0.7% |
| `TPR_G0.010_B3_R0.08_TFI` | `FAIL` | 1296 | -0.405 | 0.58 | 528.88 | -0.833 | 2.0% | 9.4% | 0/4 | 0.8% |
| `TPR_G0.010_B5_R0.05_TFI` | `FAIL` | 1301 | -0.406 | 0.58 | 533.10 | -0.837 | 2.7% | 9.7% | 0/4 | 0.7% |
| `TPR_G0.010_B5_R0.08_TFI` | `FAIL` | 1257 | -0.392 | 0.59 | 500.57 | -0.810 | 2.8% | 9.6% | 0/4 | 0.7% |
| `TPR_ABLATION_NO_TFI` | `FAIL` | 1605 | -0.408 | 0.57 | 664.18 | -0.843 | 3.0% | 8.7% | 0/4 | 0.7% |

## Best Variant

**Best:** `TPR_G0.010_B5_R0.08_TFI`
**Verdict:** `FAIL` - Required gates failed: ['min_er', 'min_pf', 'max_dd', 'cost_sensitivity_2x', 'wf_folds_er_gt_1']

## Gates

| Gate | Actual | Required | Result |
|---|---:|---:|---|
| min_oos_trades | 1257.000 | >= 60 | PASS |
| min_er | -0.392 | >= 1.5 | FAIL |
| min_pf | 0.587 | >= 1.8 | FAIL |
| max_dd | 500.570 | <= 6.0 | FAIL |
| cost_sensitivity_2x | -0.810 | > 0.5 | FAIL |
| timeout_share | 0.028 | <= 0.4 | PASS |
| max_month_trade_share | 0.096 | <= 0.5 | PASS |
| wf_folds_er_gt_1 | 0.000 | >= 3 | FAIL |
| overlap_vs_trial_00095 | 0.007 | <= 0.3 | PASS |

## Anti-Overfit Controls

- LONG-only V1; SHORT is out of scope.
- Coarse grid only: 8 candidate variants plus one no-TFI ablation.
- Equal-low support is frozen at least 5 completed 15m bars before trigger.
- 4h EMA trend uses completed 4h candles only.
- Entry is next 15m open after reclaim close.
- CVD, OI, funding, and force orders are not trigger or scoring inputs.
- If the no-TFI ablation beats TFI variants, that is diagnostic evidence against flow confirmation, not automatic promotion.

## Audit Questions

1. Does the runner avoid lookahead in frozen equal-low and 4h trend calculations?
2. Is the implementation research_lab-only with no runtime/core changes?
3. Are gates applied exactly as pre-registered in the hypothesis card?
4. Does TFI add incremental value versus the no-TFI ablation?
5. Is overlap with trial-00095 low enough to support portfolio distinctness?

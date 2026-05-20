# ETH Asset-Specific Optimization V1

**Milestone:** `ETH_ASSET_SPECIFIC_OPTIMIZATION_V1`
**Status:** `ETH_ASSET_SPECIFIC_CANDIDATE_FOR_AUDIT`
**Scope:** Research Lab offline optimization only. No runtime, PAPER, LIVE, sidecar, M4, core, execution, orchestrator, settings, or production DB changes.

## Methodology

- Baseline: frozen BTC `trial-00095` transferred to ETH.
- Search: fixed depth-only coarse grid over `min_sweep_depth_pct`; all other trial-00095 parameters remain frozen.
- Selection: train window only (`2022-01-01` to `2025-01-01`).
- Evaluation: untouched OOS window (`2025-01-01` to `2026-03-28`).
- Full-year walk-forward and 2x cost stress are diagnostics/gates for the selected train champion only.
- No post-hoc threshold rescue: if train champion fails OOS gates, verdict remains no promotion.

## Baseline OOS

Trades `162`, ER `1.766`, PF `2.73`, WR `44.4%`, max DD `6.04%`

## Selected Train Champion

- Variant: `ETH_OPT_D0.00750`
- Overrides: `{"min_sweep_depth_pct": 0.0075}`
- Train score: `1.7711`

### Train Metrics

Trades `269`, ER `2.288`, PF `3.93`, WR `52.4%`, max DD `5.61%`

### OOS Metrics

Trades `127`, ER `2.190`, PF `3.50`, WR `50.4%`, max DD `4.88%`

### 2x Cost OOS Metrics

Trades `127`, ER `1.808`, PF `2.66`, WR `50.4%`, max DD `5.94%`

## Gates

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| oos_min_trades | 127 | 80 | PASS |
| oos_min_er | 2.19 | 1.5 | PASS |
| oos_min_pf | 3.504 | 2 | PASS |
| oos_max_dd | 0.04882 | 0.12 | PASS |
| oos_er_improvement_vs_baseline | 0.2404 | 0.05 | PASS |
| oos_pf_improvement_vs_baseline | 0.2834 | 0 | PASS |
| wf_positive_folds | 4 | 4 | PASS |
| cost_2x_oos_er | 1.808 | 1 | PASS |

## Walk-Forward Folds For Selected Variant

| Fold | Window | Trades | ER | PF | Win Rate | Max DD |
|---|---|---:|---:|---:|---:|---:|
| 2022 | 2022-01-01 to 2023-01-01 | 130 | 2.248 | 3.38 | 46.2% | 5.61% |
| 2023 | 2023-01-01 to 2024-01-01 | 63 | 2.423 | 5.07 | 66.7% | 1.86% |
| 2024 | 2024-01-01 to 2025-01-01 | 77 | 2.412 | 3.96 | 53.2% | 3.15% |
| 2025_to_2026Q1 | 2025-01-01 to 2026-03-28 | 127 | 2.190 | 3.50 | 50.4% | 4.88% |

## Grid Summary

- Variants evaluated: 3
- Train-pass variants: 3

| Variant | Train Pass | Train ER | Train PF | Train DD | OOS Trades | OOS ER | OOS PF | OOS DD |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ETH_OPT_D0.00750` | YES | 2.288 | 3.93 | 5.61% | 127 | 2.190 | 3.50 | 4.88% |
| `ETH_OPT_D0.00649` | YES | 1.820 | 3.04 | 6.72% | 162 | 1.766 | 2.73 | 6.04% |
| `ETH_OPT_D0.00550` | YES | 1.629 | 2.99 | 9.13% | 235 | 1.604 | 2.47 | 8.53% |

## Audit Questions

1. Did the milestone remain research-only with no runtime/sidecar/M4 changes?
2. Was the grid fixed before results and limited to coarse ETH asset-specific variants?
3. Was the selected variant chosen from train metrics only?
4. Were OOS and cost/WF gates applied without post-hoc rescue?
5. Is any candidate recommendation supported by OOS improvement over frozen ETH transfer baseline?

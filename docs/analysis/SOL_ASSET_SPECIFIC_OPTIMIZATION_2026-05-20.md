# SOL Asset-Specific Optimization V1

**Milestone:** `SOL_ASSET_SPECIFIC_OPTIMIZATION_V1`
**Status:** `SOL_ASSET_SPECIFIC_CANDIDATE_FOR_AUDIT`
**Scope:** Research Lab offline optimization only. No runtime, PAPER, LIVE, sidecar, M4, core, execution, orchestrator, settings, or production DB changes.

## Methodology

- Baseline: frozen BTC `trial-00095` transferred to SOL.
- Search: fixed depth-only coarse grid over `min_sweep_depth_pct`; all other trial-00095 parameters remain frozen.
- Selection: train window only (`2022-01-01` to `2025-01-01`).
- Evaluation: untouched OOS window (`2025-01-01` to `2026-03-28`).
- Full-year walk-forward and 2x cost stress are diagnostics/gates for the selected train champion only.
- No post-hoc threshold rescue: if train champion fails OOS gates, verdict remains no promotion.

## Baseline OOS

Trades `213`, ER `2.041`, PF `3.32`, WR `45.5%`, max DD `7.92%`

## Selected Train Champion

- Variant: `SOL_OPT_D0.00750`
- Overrides: `{"min_sweep_depth_pct": 0.0075}`
- Train score: `2.2274`

### Train Metrics

Trades `794`, ER `2.546`, PF `4.90`, WR `43.2%`, max DD `6.38%`

### OOS Metrics

Trades `156`, ER `2.573`, PF `4.29`, WR `51.3%`, max DD `3.57%`

### 2x Cost OOS Metrics

Trades `156`, ER `2.204`, PF `3.26`, WR `51.3%`, max DD `4.28%`

## Gates

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| oos_min_trades | 156 | 80 | PASS |
| oos_min_er | 2.573 | 1.5 | PASS |
| oos_min_pf | 4.289 | 2 | PASS |
| oos_max_dd | 0.03569 | 0.12 | PASS |
| oos_er_improvement_vs_baseline | 0.2607 | 0.05 | PASS |
| oos_pf_improvement_vs_baseline | 0.2932 | 0 | PASS |
| wf_positive_folds | 4 | 4 | PASS |
| cost_2x_oos_er | 2.204 | 1 | PASS |

## Walk-Forward Folds For Selected Variant

| Fold | Window | Trades | ER | PF | Win Rate | Max DD |
|---|---|---:|---:|---:|---:|---:|
| 2022 | 2022-01-01 to 2023-01-01 | 212 | 2.198 | 3.32 | 36.8% | 6.38% |
| 2023 | 2023-01-01 to 2024-01-01 | 305 | 2.562 | 3.95 | 43.3% | 4.35% |
| 2024 | 2024-01-01 to 2025-01-01 | 269 | 2.839 | 4.97 | 48.7% | 5.89% |
| 2025_to_2026Q1 | 2025-01-01 to 2026-03-28 | 156 | 2.573 | 4.29 | 51.3% | 3.57% |

## Grid Summary

- Variants evaluated: 3
- Train-pass variants: 1

| Variant | Train Pass | Train ER | Train PF | Train DD | OOS Trades | OOS ER | OOS PF | OOS DD |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `SOL_OPT_D0.00750` | YES | 2.546 | 4.90 | 6.38% | 156 | 2.573 | 4.29 | 3.57% |
| `SOL_OPT_D0.00550` | NO | 1.706 | 2.87 | 17.92% | 289 | 1.822 | 2.93 | 11.98% |
| `SOL_OPT_D0.00649` | NO | 2.163 | 3.62 | 15.46% | 213 | 2.041 | 3.32 | 7.92% |

## Audit Questions

1. Did the milestone remain research-only with no runtime/sidecar/M4 changes?
2. Was the grid fixed before results and limited to coarse SOL asset-specific variants?
3. Was the selected variant chosen from train metrics only?
4. Were OOS and cost/WF gates applied without post-hoc rescue?
5. Is any candidate recommendation supported by OOS improvement over frozen SOL transfer baseline?

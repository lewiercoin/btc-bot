# TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1

**Status:** READY_FOR_CLAUDE_AUDIT
**Type:** Research-only accepted-trade refinement diagnostic
**Final verdict:** `HYPOTHESIS_INVALIDATED`

## Scope

Accepted trial-00095 trades only. No new entries, no threshold changes, no production changes.

## Data

- Trade source: `C:\Users\lewie\Projects\btc-bot\research_lab\analysis_output\trial_00095_trades.json`
- Accepted population count: 274
- Expected accepted population count: 274
- Depth threshold preserved: 0.00649

## Full-Sample Metrics

| Cohort | N | ER | PF | WR | Median R | Total R | Max DD R | Count Removed | Retained |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `BASELINE_all_274` | 274 | 2.12113 | 4.21646 | 56.57% | 2.6568 | 581.191 | 14.6765 | 0 | 100.00% |
| `A1_long_only` | 252 | 2.3766 | 4.92882 | 60.32% | 2.80091 | 598.903 | 10.8827 | 22 | 91.97% |
| `A2_uptrend_only` | 205 | 2.61446 | 6.03385 | 66.34% | 3.03 | 535.964 | 10.8827 | 69 | 74.82% |
| `A3_long_and_uptrend` | 205 | 2.61446 | 6.03385 | 66.34% | 3.03 | 535.964 | 10.8827 | 69 | 74.82% |

## Per-Fold Metrics

| Fold | Cohort | N | ER | PF | WR | Median R | Total R | Max DD R | ER Delta | Count Removed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fold_1_2022_2023H1` | `BASELINE_all_274` | 110 | 1.58393 | 3.02443 | 48.18% | -1.26061 | 174.232 | 14.6765 | 0 | 0 |
| `fold_1_2022_2023H1` | `A1_long_only` | 94 | 1.95145 | 3.76597 | 53.19% | 2.40232 | 183.436 | 10.3816 | 0.367519 | 16 |
| `fold_1_2022_2023H1` | `A2_uptrend_only` | 62 | 2.29725 | 5.41306 | 66.13% | 3.16969 | 142.43 | 4.5312 | 0.713322 | 48 |
| `fold_1_2022_2023H1` | `A3_long_and_uptrend` | 62 | 2.29725 | 5.41306 | 66.13% | 3.16969 | 142.43 | 4.5312 | 0.713322 | 48 |
| `fold_2_2023H2_2024` | `BASELINE_all_274` | 123 | 2.49256 | 5.17611 | 60.98% | 2.91891 | 306.585 | 10.8827 | 0 | 0 |
| `fold_2_2023H2_2024` | `A1_long_only` | 120 | 2.58783 | 5.4708 | 62.50% | 2.98589 | 310.539 | 10.8827 | 0.095269 | 3 |
| `fold_2_2023H2_2024` | `A2_uptrend_only` | 114 | 2.63095 | 5.61084 | 63.16% | 3.15528 | 299.929 | 10.8827 | 0.138394 | 9 |
| `fold_2_2023H2_2024` | `A3_long_and_uptrend` | 114 | 2.63095 | 5.61084 | 63.16% | 3.15528 | 299.929 | 10.8827 | 0.138394 | 9 |
| `fold_3_2025_2026Q1` | `BASELINE_all_274` | 41 | 2.44814 | 5.73142 | 65.85% | 2.78415 | 100.374 | 7.51133 | 0 | 0 |
| `fold_3_2025_2026Q1` | `A1_long_only` | 38 | 2.76126 | 7.29813 | 71.05% | 2.90433 | 104.928 | 7.51133 | 0.31312 | 3 |
| `fold_3_2025_2026Q1` | `A2_uptrend_only` | 29 | 3.22777 | 11.2314 | 79.31% | 2.90725 | 93.6054 | 3.09859 | 0.779632 | 12 |
| `fold_3_2025_2026Q1` | `A3_long_and_uptrend` | 29 | 3.22777 | 11.2314 | 79.31% | 2.90725 | 93.6054 | 3.09859 | 0.779632 | 12 |

## Falsification Gates

| Gate | Measurement | Value | Threshold | Status |
|---|---|---:|---|---|
| G-1 | A3 full-sample ER vs baseline ER | 2.61446 | >= 2.621 | FAIL |
| G-2 | A3 full-sample PF vs baseline PF | 6.03385 | >= 4.638 | PASS |
| G-3 | A3 per-fold sign stability | {'fold_1_2022_2023H1': 2.29725008103397, 'fold_2_2023H2_2024': 2.6309533879147495, 'fold_3_2025_2026Q1': 3.227771692358091} | A3 ER > 0 in all 3 folds | PASS |
| G-4 | A3 per-fold consistency | {'fold_er': {'fold_1_2022_2023H1': 2.29725008103397, 'fold_2_2023H2_2024': 2.6309533879147495, 'fold_3_2025_2026Q1': 3.227771692358091}, 'minimum_allowed_fold_er': 1.3072282203043226} | No per-fold A3 ER more than 50% below A3 full-sample ER | PASS |
| G-5 | A3 max drawdown R | 10.8827 | reported, informational only | INFO |

## Stability

- A3 sign stability versus baseline folds: 100.00%
- Missing A3 folds: []
- Data quality status: `OK`

## Methodology Notes

- A1/A2/A3 are the only amendment cohorts.
- A3 is the only hard-gated combined refinement.
- A1 or A2 cannot replace A3 after results.
- TFI alignment, exit timing, and near-miss reconstruction are out of scope.
- Verdict is computed mechanically from G-1 through G-4 and data-gap checks.

## Artifacts

- JSON SHA256: `A9E8CB0096F565D10BEF4FBCD427448D962B85D2671FC709F5B54B99871BB4D0`

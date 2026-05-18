# Trial-00095 Exit Surface Diagnostic

**Milestone:** `TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_V1`
**Status:** READY_FOR_AUDIT
**Scope:** Research Lab offline diagnostic only; frozen trial-00095 realized R distribution; no runtime/core changes.

> Methodology limit: this first diagnostic uses the existing `trial_00095_trades.json` realized-R artifact. It is a distribution clipping study, not a full intrabar exit replay. It can identify whether simple winner/loser clipping is worth future validation, but it cannot approve an exit policy.

Frozen entries replayed: 274

## Variant Results

| Variant | Verdict | ER | Delta ER | Delta % | PF | DD Ratio | Median Delta | Folds+ | 2x ER | Top Delta Share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `LOSS_CAP_1.00R` | `PASS` | 2.346 | 0.225 | 10.6% | 6.40 | 0.68 | 0.000 | 9 | 2.064 | 1.2% |
| `LOSS_CAP_1.25R` | `MARGINAL` | 2.238 | 0.117 | 5.5% | 5.12 | 0.85 | 0.000 | 9 | 1.956 | 1.6% |
| `LOSS_CAP_1.50R` | `MARGINAL` | 2.140 | 0.019 | 0.9% | 4.34 | 0.98 | 0.000 | 9 | 1.858 | 5.1% |
| `BASELINE_CONTROL` | `MARGINAL` | 2.121 | 0.000 | 0.0% | 4.22 | 1.00 | 0.000 | 0 | 1.839 | 0.0% |
| `SYMMETRIC_CAP_3.0R` | `MARGINAL` | 1.006 | -1.115 | -52.6% | 2.57 | 1.06 | 0.000 | 0 | 0.725 | 5.1% |
| `WIN_CAP_3.0R` | `MARGINAL` | 0.987 | -1.134 | -53.5% | 2.50 | 1.08 | 0.000 | 0 | 0.706 | 0.0% |
| `SYMMETRIC_CAP_2.5R` | `MARGINAL` | 0.765 | -1.356 | -63.9% | 2.20 | 1.18 | -0.157 | 0 | 0.485 | 5.1% |
| `WIN_CAP_2.5R` | `MARGINAL` | 0.746 | -1.375 | -64.8% | 2.13 | 1.21 | -0.157 | 0 | 0.466 | 0.0% |
| `SYMMETRIC_CAP_2.0R` | `MARGINAL` | 0.491 | -1.630 | -76.9% | 1.77 | 1.31 | -0.657 | 0 | 0.210 | 5.1% |
| `WIN_CAP_2.0R` | `MARGINAL` | 0.472 | -1.649 | -77.8% | 1.72 | 1.35 | -0.657 | 0 | 0.191 | 0.0% |
| `WIN_CAP_1.5R` | `MARGINAL` | 0.189 | -1.932 | -91.1% | 1.29 | 1.71 | -1.157 | 0 | -0.091 | 0.0% |

## Builder Interpretation

Best aggregate variant: `LOSS_CAP_1.00R`.
This diagnostic cannot produce a promotion-ready verdict. A useful result must show a broad, stable exit family rather than a single sharp optimum.

## Audit Questions

1. Are trial-00095 entries frozen and identical across variants?
2. Does baseline control preserve the replayed baseline entry population?
3. Are intrabar conflicts handled adverse-first?
4. Are results diagnostic-only with no runtime/settings promotion path?
5. Are improvements fold-stable and not dominated by one outlier trade?

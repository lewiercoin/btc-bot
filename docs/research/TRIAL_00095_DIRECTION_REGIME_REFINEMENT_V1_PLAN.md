# TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1 Plan

**Date:** 2026-06-04  
**Status:** PLAN_READY_FOR_CLAUDE_AUDIT  
**Builder:** Codex  
**Auditor:** Claude Code  
**Type:** Research-only accepted-trade refinement diagnostic  

## 1. Executive Summary And Scope Guards

`TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1` tests whether two deterministic
amendments to the validated `optuna-default-v3-trial-00095` edge can improve
expectancy without changing entries, thresholds, exits, or production code.

The diagnostic will operate only on the existing frozen accepted-trade
population from `TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1`:

- 274 accepted trial-00095 trades.
- Frozen intrabar entry context already produced for those trades.
- Existing attribution context reconstructed from the prior completed 15m bar.

No rejected candidates will be reconstructed in this milestone. No new entries
will be generated. No threshold, regime, direction, confluence, risk, exit, or
position-sizing parameter will be optimized or tuned.

Frozen amendment cohorts:

| Cohort | Filter |
|---|---|
| `BASELINE_all_274` | Full accepted population, no amendment |
| `A1_long_only` | `trade.direction == "LONG"` |
| `A2_uptrend_only` | `regime_at_open == "uptrend"` |
| `A3_long_and_uptrend` | `trade.direction == "LONG" AND regime_at_open == "uptrend"` |

Research-only no-touch areas:

- no `core/**`;
- no `execution/**`;
- no `orchestrator.py`;
- no `settings.py`;
- no schema or database migrations;
- no dependency manifests;
- no live/PAPER runtime changes;
- no production deployment or promotion.

The implementation commit, if this plan is approved, must report a computed
verdict only:

- `HYPOTHESIS_PASSED_REQUIRES_CLAUDE_AUDIT`; or
- `HYPOTHESIS_INVALIDATED`.

Codex will not self-audit or mark the milestone complete.

## 2. Why M5 Versus Cancelled M4 And Closed Setup Families

M4 (`CONFLUENCE_GATE_ACCESSIBILITY_DIAGNOSTIC_V1`) was cancelled after the
2026-06-04 research landscape reset concluded that the existing
`MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` diagnostic had already tested
the relevant post-sweep confluence/timing states. That prior diagnostic found
no early knowable state with positive net expectancy after costs, and the reset
memo judged another confluence-accessibility diagnostic to have low incremental
value.

M5 is different. It is not another setup-discovery attempt in the closed
sweep/SMC/liquidity/order-flow family. It is a bounded refinement diagnostic
on the single validated edge, trial-00095. The attribution audit found that
the accepted trade population is not uniform:

| Cohort | N | ER | PF | WR |
|---|---:|---:|---:|---:|
| Baseline all accepted trades | 274 | 2.121 | 4.216 | 56.57% |
| LONG only | 252 | 2.377 | 4.929 | 60.3% |
| SHORT only | 22 | -0.805 | 0.373 | 13.6% |
| Uptrend only | 205 | 2.614 | 6.034 | 66.3% |
| Downtrend | 54 | 0.690 | 1.631 | 25.9% |
| Crowded leverage | 6 | 0.226 | 1.229 | 33.3% |
| Normal regime | 9 | 0.736 | 1.712 | 33.3% |

Direction asymmetry and regime concentration are directly measurable on the
validated accepted-trade surface. M5 tests whether combining those two
observations into frozen amendments survives walk-forward stability checks.

This is not threshold relaxation. The attribution audit explicitly reported
that rejected backtest candidates are unavailable and that any threshold
expansion requires a separate reconstruction milestone. M5 does not attempt
that work.

## 3. Repository Inventory

The implementation must reuse the existing accepted-trade attribution module:

`research_lab/diagnostics/trial_00095_conditional_edge_attribution_v1.py`

Reusable contracts and constants:

- `DiagnosticConfig`
- `Candle`
- `FrozenEntry`
- `TradeRecord`
- `AttributedTrade`
- `DEPTH_THRESHOLD = 0.00649`
- `TRIAL_ID`
- `SYMBOL`
- `TIMEFRAME`
- default frozen accepted-trade artifact paths

Reusable functions and surfaces:

- `load_trade_records()`
- `load_frozen_entries()`
- `merge_entries()`
- `load_candles()`
- `load_aggtrade_prev_tfi()`
- `load_funding()`
- `load_open_interest()`
- `attribute_trades()`
- `summarize_metrics()`
- `max_drawdown()`
- `fold_bucket()`
- existing `regime` attribution carried into `TradeRecord` and
  `AttributedTrade`

The future diagnostic must import and reuse these primitives. It must not
copy or re-implement the regime classification surface or the fold assignment
helper. If a helper needs a new public wrapper for clarity, that wrapper must
delegate to the imported helper without changing semantics.

Primary evidence sources:

- `docs/audits/AUDIT_TRIAL_00095_ATTRIBUTION_V1_2026-05-30.md`
- `research_lab/reports/trial_00095_conditional_edge_attribution_v1.md`
- `research_lab/diagnostics/trial_00095_conditional_edge_attribution_v1.py`
- `docs/research/RESEARCH_LANDSCAPE_RESET_2026-06-04.md` from the Claude
  audit branch, which cancelled M4 and selected D1 as the next operator
  direction.
- `docs/QUANT_RESEARCH_OPERATING_MODEL.md`

## 4. Cohort Specification

The diagnostic will load and attribute the same accepted-trade population used
by `TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1`.

### `BASELINE_all_274`

Reference baseline. Contains every accepted trial-00095 trade in the frozen
artifact. Expected reference metrics from the attribution report:

- count: 274;
- ER: 2.121;
- PF: 4.216;
- WR: 56.57%;
- median R: 2.6568;
- total R: 581.19;
- max drawdown R: 14.68.

### `A1_long_only`

Filter:

```text
trade.direction == "LONG"
```

Expected reference from attribution:

- count around 252;
- ER around 2.377;
- PF around 4.929;
- WR around 60.3%.

### `A2_uptrend_only`

Filter:

```text
trade.regime == "uptrend"
```

`trade.regime` must be the existing attribution classification. The
implementation must not infer a new uptrend definition from candles,
indicators, or runtime modules.

Expected reference from attribution:

- count around 205;
- ER around 2.614;
- PF around 6.034;
- WR around 66.3%.

### `A3_long_and_uptrend`

Filter:

```text
trade.direction == "LONG" AND trade.regime == "uptrend"
```

This is the combined amendment cohort and the only cohort with hard
production-refinement gates in this milestone. A1 and A2 are reported to
explain the decomposition of the lift, but A3 determines the final verdict.

## 5. Walk-Forward Structure

Use the exact fold assignment already used by
`trial_00095_conditional_edge_attribution_v1.py` through `fold_bucket()`.

Frozen folds:

| Fold | Window | Baseline N | Baseline ER |
|---|---|---:|---:|
| `fold_1_2022_2023H1` | 2022-01-01 to 2023-06-30 | 110 | 1.584 |
| `fold_2_2023H2_2024` | 2023-07-01 to 2024-12-31 | 123 | 2.493 |
| `fold_3_2025_2026Q1` | 2025-01-01 to 2026-03-31 | 41 | 2.448 |

For `BASELINE_all_274`, A1, A2, and A3, report per fold:

- count;
- ER;
- PF;
- WR;
- median R;
- total R;
- max drawdown R.

For A1, A2, and A3, report deltas versus baseline:

- ER delta;
- PF delta;
- WR delta;
- count retained;
- count removed;
- retained share;
- total R delta;
- max drawdown R delta.

For A3, report sign stability:

```text
number of folds with A3 ER > baseline fold ER / 3
```

Also report the stricter pass/fail stability gates defined in Section 7.

## 6. Pre-Data Hypotheses

These hypotheses are frozen before implementation and cannot be revised after
results are known.

| ID | Hypothesis | Expected direction |
|---|---|---|
| H1 | A1 LONG-only removes the weak SHORT drag while preserving most of the sample. | `ER_A1 >= ER_baseline + 0.25R` |
| H2 | A2 uptrend-only isolates the strongest regime concentration. | `ER_A2 >= ER_baseline + 0.45R` |
| H3 | A3 LONG and uptrend is the combined refinement. | `ER_A3 >= 2.6` and `PF_A3 >= 5.0` |
| H4 | The A3 lift is not a single-period artifact. | `A3 ER > 0` in every fold, and no fold ER is more than 50% below full-sample A3 ER |

H1 and H2 are explanatory hypotheses. H3 and H4 drive the final A3 gate
evaluation alongside G-1 through G-5.

## 7. Pre-Data Acceptance Criteria

These gates are frozen before implementation. They cannot be softened,
reweighted, or replaced after results are known.

Reference constants:

- baseline ER: 2.121;
- baseline PF: 4.216.

| Gate | Measurement | PASS threshold |
|---|---|---|
| G-1 | A3 full-sample ER vs baseline ER | A3 ER >= baseline ER + 0.5R, i.e. >= 2.621 |
| G-2 | A3 full-sample PF vs baseline PF | A3 PF >= baseline PF * 1.10, i.e. >= 4.638 |
| G-3 | A3 per-fold sign stability | A3 ER > 0 in all 3 folds |
| G-4 | A3 per-fold consistency | No per-fold A3 ER is more than 50% below A3 full-sample ER |
| G-5 | A3 max drawdown R | Reported, informational only |

Additional non-softening completion checks:

- A3 must be derived only from the frozen A1/A2 filters.
- A3 must report retained count and retained share.
- A3 must report all three folds, even if a fold has small sample size.
- Any missing fold must produce `INCONCLUSIVE_DATA_GAP`, not a pass.
- Any implementation that changes the accepted-trade population, depth
  threshold, regime assignment, fold assignment, or exit values is invalid.

Final verdict rules:

- If G-1, G-2, G-3, or G-4 fails, final verdict is
  `HYPOTHESIS_INVALIDATED`.
- If a required data surface is missing or a fold cannot be evaluated, final
  verdict is `INCONCLUSIVE_DATA_GAP`.
- Only if G-1 through G-4 pass may the diagnostic report
  `HYPOTHESIS_PASSED_REQUIRES_CLAUDE_AUDIT`.
- G-5 is reported for audit context but does not block the verdict.

No production recommendation may be made by the builder. A pass means only
that Claude Code can audit whether this refinement deserves a later promotion
plan.

## 8. Test Plan

Focused unit tests for the implementation commit:

1. `test_cohort_filters_are_frozen`
   - Synthetic `AttributedTrade` rows verify:
     - A1 includes only `direction == "LONG"`;
     - A2 includes only `regime == "uptrend"`;
     - A3 includes only rows satisfying both predicates.

2. `test_short_and_non_uptrend_rows_are_not_mutated`
   - Filtering removes rows from amendment cohorts but does not alter their
     original metrics, direction, regime, timestamps, or `pnl_r`.

3. `test_fold_assignment_reuses_existing_helper`
   - Boundary timestamps verify the diagnostic delegates to imported
     `fold_bucket()` and produces the three frozen fold labels.

4. `test_metric_summary_matches_existing_attribution_math`
   - Synthetic PnL rows compare amendment metrics to imported
     `summarize_metrics()` outputs for ER, PF, WR, median R, total R, and max
     drawdown R.

5. `test_delta_vs_baseline_is_computed_per_fold_and_full_sample`
   - Synthetic baseline/amendment rows verify ER/PF/WR/count/total R/DD deltas.

6. `test_gate_evaluation_invalidates_on_any_required_a3_failure`
   - Parameterized cases fail G-1, G-2, G-3, and G-4 independently and assert
     final verdict `HYPOTHESIS_INVALIDATED`.

7. `test_inconclusive_data_gap_when_required_fold_missing`
   - A3 with no rows in one fold returns `INCONCLUSIVE_DATA_GAP`.

8. `test_deterministic_json_sha256`
   - Running the diagnostic twice on the same synthetic accepted population
     produces byte-identical JSON and SHA256.

Validation commands for implementation commit:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_research_lab\test_trial_00095_direction_regime_refinement_v1.py -v -o addopts=
.\.venv\Scripts\python.exe -m compileall research_lab\diagnostics\trial_00095_direction_regime_refinement_v1.py tests\test_research_lab\test_trial_00095_direction_regime_refinement_v1.py
.\.venv\Scripts\python.exe research_lab\diagnostics\trial_00095_direction_regime_refinement_v1.py
```

No tests are added in the plan commit.

## 9. Acceptance Criteria For Diagnostic Completion

Implementation completion, after plan approval, requires:

- diagnostic file:
  `research_lab/diagnostics/trial_00095_direction_regime_refinement_v1.py`;
- focused tests:
  `tests/test_research_lab/test_trial_00095_direction_regime_refinement_v1.py`;
- deterministic JSON report:
  `research_lab/reports/trial_00095_direction_regime_refinement_v1.json`;
- SHA256 file:
  `research_lab/reports/trial_00095_direction_regime_refinement_v1.sha256`;
- markdown report:
  `research_lab/reports/trial_00095_direction_regime_refinement_v1.md`;
- per-cohort full-sample metrics for baseline, A1, A2, A3;
- per-fold metrics for baseline, A1, A2, A3;
- A1/A2/A3 deltas versus baseline;
- sign stability and gate table for A3;
- final verdict computed mechanically from G-1 through G-4 plus data-gap
  checks;
- all tests pass;
- compile validation passes;
- no production modules touched;
- no threshold, filter, fold, regime, or exit methodology changed after
  results.

Plan-commit completion requires only this plan file committed with
`STATUS=PLAN_READY_FOR_CLAUDE_AUDIT`, then stop for Claude audit.

## 10. Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| A3 overfits the accepted-trade attribution sample | 3/5 | 5/5 | Frozen 3-fold walk-forward gates G-3/G-4; fail closed if lift is unstable. |
| SHORT sample is small and its removal looks stronger than it is | 4/5 | 3/5 | A1 is explanatory only; final gates use A3 plus fold stability, not SHORT-only claims. |
| Uptrend regime definition drifts from attribution diagnostic | 2/5 | 5/5 | Import and reuse existing attribution `regime` surface; do not reclassify. |
| Fold assignment drifts | 2/5 | 4/5 | Import and reuse `fold_bucket()`; boundary tests required. |
| Sample collapse in A3 | 3/5 | 4/5 | Report retained count/share and every fold; missing folds produce `INCONCLUSIVE_DATA_GAP`. |
| Metric delta hides total R loss from fewer trades | 3/5 | 3/5 | Report ER, PF, WR, median R, total R, max DD, retained count, and count removed. |
| M5 becomes a gateway to threshold relaxation | 2/5 | 5/5 | Explicitly out of scope; D3 reconstruction remains separate prerequisite. |
| TFI alignment or exit timing gets added after seeing results | 3/5 | 5/5 | Frozen cohorts A1/A2/A3 only; no post-data filters or exit changes. |
| Builder accidentally modifies production path | 1/5 | 5/5 | Research-only write scope; no `core/**`, `execution/**`, `orchestrator.py`, `settings.py`, or schema changes. |

## 11. Open Questions For Operator

None blocking for the plan.

Non-blocking notes for later audit or operator decision:

1. If A3 passes all gates, a separate promotion-planning milestone would still
   be required before any PAPER/LIVE behavior changes.
2. If A3 fails but A1 or A2 individually looks strong, that is evidence for a
   future plan only; M5 must not rescue itself by switching final gates from
   A3 to A1 or A2 after results.
3. TFI alignment and exit timing remain plausible future directions, but they
   are separate D/M milestones and intentionally excluded from M5.

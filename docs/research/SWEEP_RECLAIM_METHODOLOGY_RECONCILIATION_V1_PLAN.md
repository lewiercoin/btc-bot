# SWEEP_RECLAIM_METHODOLOGY_RECONCILIATION_V1 Plan

## 1. Scope And Mode

M7 is a research-only methodology reconciliation milestone. It is not
edge discovery, not prior-closure rescue, not production work, and not a
parameter search.

The question is:

> Did M6.1 A.3 test the same sweep/reclaim primitive as the prior
> SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1 closure, or did it test a
> different primitive whose result must be interpreted separately?

No production files may be modified. No `core/`, `bot/`, `execution/`,
`orchestrator.py`, settings, schema, or dependency manifests are in
scope. The prior sweep/reclaim module and M6 modules must not be edited.

Commit split:

- Commit 1: this Phase 1 plan and methodology mapping document only.
  No code, no tests, no artifacts. STATUS=`PLAN_READY_FOR_CLAUDE_AUDIT`.
- Commit 2: after Claude plan approval, Phase 2 empirical reconciliation,
  Phase 3 stability check, tests, and report artifacts. STATUS=
  `READY_FOR_CLAUDE_AUDIT`.

## 2. Operator-Locked Constraints

These four constraints come from the operator's M7 approval message
(2026-06-05). They override builder convenience choices.

1. **M6.1 A.3 numbers are LOCKED.** Specifically:
   - event_count = 14,236
   - net_5b_pf = 2.847
   - net_5b_median = +0.001811
   - mfe_before_after_ratio = 0.385

   These numbers cannot be changed by M7. If M7 reruns A.3 with
   different parameters and produces different metrics, those new
   metrics are a DIFFERENT diagnostic, not "the same A.3 finding
   refined."

2. **Prior closure is QUESTIONED, not OBALONA.** Phase 1 must assume
   prior `SWEEP_RECLAIM_EVENT_TAXONOMY` closure is valid as scoped and
   ask "did A.3 test what prior tested?" -- not "was prior wrong?"

3. **Methodology first, edge second.** Phase 1 (methodology mapping)
   must commit + audit before any Phase 2 empirical reconciliation run.
   No empirical re-run before the methodology axes are formally
   classified.

4. **Edge verdict is conditional on methodology classification.** M7's
   final verdict is mechanically derived from Phase 1 classification +
   Phase 2 empirical reconciliation + Phase 3 stability. No post-data
   verdict invention.

## 3. Source Material Read For Phase 1

Required sources inspected for this plan:

- `docs/audits/AUDIT_M6.1_PART_A_SHA_FIX_2026-06-05.md`
- `research_lab/diagnostics/red_team_replication_v1.py` from
  `origin/research/m6-red-team-replication`, specifically
  `build_raw_sweep_reclaim_events` and `run_raw_sweep_reclaim_ablation`
- `research_lab/analysis_smc_sequence_edge_feasibility_v1.py`,
  specifically `DiagnosticConfig`, `detect_equal_levels`,
  `_retired_match`, `detect_sweep_events`, `forward_metrics`,
  `mfe_between`, and `summarize_group`
- `research_lab/analysis_sweep_reclaim_event_taxonomy_diagnostic_v1.py`
- `docs/research/SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_PLAN.md`
- `docs/audits/AUDIT_SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27.md`
- `docs/analysis/SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27.md`

## 4. Locked M6.1 A.3 Result

M6.1 A.3 is the fixed finding M7 reconciles. It is not re-estimated in
Phase 1.

| Run | Events | Net 5b PF | Net 5b median | MFE before | MFE after | MFE ratio | Flip? |
|---|---:|---:|---:|---:|---:|---:|---|
| A.3 raw_sweep_reclaim | 14,236 | 2.847 | +0.001811 | 0.003038 | 0.007891 | 0.385 | TRUE |

The four operator-locked headline values are event count, PF, median,
and ratio. The before/after components are retained as supporting
lineage from the deterministic M6.1 JSON, not as replacement headline
numbers.

Locked M6.1 pre-data interpretation triggered:

> If this flips while gated SMC remains invalidated, the SMC gates
> destroyed a simpler raw edge and prior sweep-reclaim closure must be
> reconciled.

## 5. A.3 Methodology Extracted From M6.1

### A.3 Source

A.3 is implemented in the M6 red-team orchestrator as
`build_raw_sweep_reclaim_events` plus `run_raw_sweep_reclaim_ablation`.
It imports `analysis_smc_sequence_edge_feasibility_v1` as-is.

### A.3 Axis Definitions

| Axis | A.3 definition |
|---|---|
| Sweep detection | `BTCUSDT` `15m`; equal-level clusters from the previous 276 bars; ATR period 27; equal-level tolerance 0.09 ATR; min hits 3; min age 5 bars; sweep candle open must be within 0.40 ATR of the equal level; low-side sweep requires `low < level - 0.46 * ATR`; high-side sweep requires `high > level + 0.46 * ATR`; recent duplicate swept levels are retired for 492 bars within 0.16 percent level tolerance. |
| Direction logic | Low-side sweep creates `LONG`; high-side sweep creates `SHORT`. This is reversal direction after liquidity take. |
| Entry timing | For each sweep, scan bars after the sweep. LONG entry candidate is the first later bar whose close is `>= level`; SHORT entry candidate is the first later bar whose close is `<= level`. M6.1 code sets `entry_candidate_bar`, `label_available_bar`, and return start to that reclaim bar. The event records `entry_price` as that reclaim bar's open while the reclaim condition is known from that bar's close. This exact timing/price basis is part of the A.3 methodology and must not be silently rewritten in M7. |
| Forward window | Uses SMC `forward_windows=(3,5,10,20)` on `15m` candles. The M6.1 flip gate uses entry-timed 5-bar net return metrics, i.e. a 75-minute 5-bar horizon. |
| Cost model | Uses SMC `round_trip_cost_pct=0.0010`; net returns subtract the full round-trip cost before PF/median computation. |

## 6. Prior SWEEP_RECLAIM Taxonomy Extracted Definitions

The prior diagnostic is `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1`
from 2026-05-27. It classifies confirmed-pivot liquidity interactions
on `BTCUSDT` `5m`.

Prior default config:

- `timeframe="5m"`
- `PivotConfig(left=2,right=2,strict=True,touch_tolerance=0.0)`
- `atr_period=14`
- `reclaim_window_bars=4`
- `forward_windows=(3,5,10,20)`
- `cluster_tolerance_atr=0.25`
- no public cost field; report metrics are signed returns, not
  cost-normalized net returns

Prior shared level source:

- A pivot high/low at index `i` is usable only after `i + right`.
- Confirmed pivot high/low becomes an active liquidity level at
  `confirmed_at_index`.
- High-side level is taken when `high[current] > level_price`.
- Low-side level is taken when `low[current] < level_price`.
- A level is evaluated as a confirmed pivot/active liquidity event, then
  its first take/touch is classified into decision events.

Prior direction logic:

- `wick_crossed_liquidity`, `immediate_wick_sweep_reclaim`, and
  `delayed_close_reclaim`: HIGH-side level implies reversal short;
  LOW-side level implies reversal long.
- `close_based_bos` and `true_breakout`: HIGH-side level implies
  breakout long; LOW-side level implies breakout short.
- Lifecycle events such as `confirmed_pivot` have no trade direction.

Prior forward measurement:

- `forward_metrics` starts from the selected `detection_bar` or
  `label_available_bar`.
- The entry basis is `candles[start_bar].close`.
- MFE/MAE use future bars after the start bar.
- Delayed labels are reported from both detection timing and
  label-available timing to prevent unknowable-label edge.

## 7. Prior Variant Definitions

| Prior variant | Extracted definition |
|---|---|
| `confirmed_pivot` | Lifecycle event only. Strict confirmed pivot high/low, available after `pivot_index + right`. No sweep, reclaim, or trade direction. |
| `wick_cross` | Decision event `wick_crossed_liquidity`. First active confirmed-pivot level take: HIGH if `high > pivot_high`, LOW if `low < pivot_low`. Label available on take bar. Reversal direction. |
| `close_bos` | Decision event `close_based_bos`. Same active confirmed-pivot take bar, but candle close is beyond the pivot level: bullish `close > pivot_high` or bearish `close < pivot_low`. Label available on take bar. Breakout direction. |
| `immediate_reclaim` | Decision event `immediate_wick_sweep_reclaim`. Same take candle both crosses and closes back inside the pivot level: HIGH sweep rejected if `high > pivot_high AND close < pivot_high`; LOW sweep rejected if `low < pivot_low AND close > pivot_low`. Label available on take bar. Reversal direction. |
| `delayed_reclaim` | Decision event `delayed_close_reclaim`. After a wick cross or close break, price closes back inside the pivot level within `reclaim_window_bars=4`. Label available at the reclaim close. Reversal direction. |
| `true_breakout_no_reclaim` | Decision event `true_breakout`. Price crosses and closes beyond the pivot level, and no reclaim occurs within the 4-bar reclaim window. Label available only after the window closes. Breakout direction. |

## 8. Classification Labels

Allowed labels:

| Label | Meaning |
|---|---|
| `EQUIVALENT` | Same definition on this axis |
| `A3_NARROWER` | A.3 is a subset of prior's definition on this axis |
| `A3_WIDER` | A.3 is a superset of prior's definition on this axis |
| `DISJOINT` | A.3 tests a definition prior did not include |
| `INCOMPARABLE` | Definitions cannot be aligned, e.g. different conceptual primitive |

## 9. Phase 1 Methodology Mapping Table

| Prior variant | Sweep detection | Direction logic | Entry timing | Forward window | Cost model |
|---|---|---|---|---|---|
| `confirmed_pivot` | `DISJOINT` | `INCOMPARABLE` | `INCOMPARABLE` | `DISJOINT` | `DISJOINT` |
| `wick_cross` | `DISJOINT` | `EQUIVALENT` | `DISJOINT` | `DISJOINT` | `DISJOINT` |
| `close_bos` | `DISJOINT` | `DISJOINT` | `DISJOINT` | `DISJOINT` | `DISJOINT` |
| `immediate_reclaim` | `DISJOINT` | `EQUIVALENT` | `DISJOINT` | `DISJOINT` | `DISJOINT` |
| `delayed_reclaim` | `DISJOINT` | `EQUIVALENT` | `A3_WIDER` | `DISJOINT` | `DISJOINT` |
| `true_breakout_no_reclaim` | `DISJOINT` | `DISJOINT` | `DISJOINT` | `DISJOINT` | `DISJOINT` |

## 10. Classification Rationale

### Sweep Detection

All six prior variants use confirmed-pivot active liquidity levels.
A.3 uses equal-level clusters of recent highs/lows with ATR tolerance,
min-hit, min-age, open-proximity, sweep-buffer, and retired-level
guards. A confirmed pivot and an equal-level cluster can overlap in
market data, but neither is definitionally a subset of the other.
Therefore the sweep-detection axis is `DISJOINT` for every prior
variant.

This is the most important Phase 1 finding. It means M6.1 A.3 did not
directly retest the same level-source primitive closed by the prior
taxonomy diagnostic.

### Direction Logic

A.3 reversal direction matches prior reversal variants:

- low sweep -> LONG
- high sweep -> SHORT

That is `EQUIVALENT` for `wick_cross`, `immediate_reclaim`, and
`delayed_reclaim`.

It is `DISJOINT` for `close_bos` and `true_breakout_no_reclaim`, because
those variants use breakout direction. It is `INCOMPARABLE` for
`confirmed_pivot`, which is a lifecycle label without trade direction.

### Entry Timing

A.3 waits for a later close to re-enter the level after the sweep, but
the M6.1 implementation uses the reclaim bar as the return-start bar and
records the reclaim bar open as `entry_price`. The prior taxonomy uses
close-based `forward_metrics` from `detection_bar` or
`label_available_bar`.

`delayed_reclaim` is the closest conceptual timing analog because both
look for a post-sweep close back inside the level. A.3 is classified
`A3_WIDER` on this axis because it has no 4-bar reclaim-window cap and
can accept later reclaims. The open-vs-close return basis remains a
Phase 2 risk item and must be reported explicitly.

`immediate_reclaim` is `DISJOINT` because it requires same-candle
reclaim, while A.3 starts scanning after the sweep bar.

`wick_cross` has no reclaim entry; `close_bos` and
`true_breakout_no_reclaim` are breakout/non-reclaim constructs;
`confirmed_pivot` has no entry primitive.

### Forward Window

A.3 uses `15m` candles and the 5-bar flip metric is therefore a
75-minute horizon. The prior original diagnostic used `5m` candles and
the 5-bar report horizon was 25 minutes. Even though both configs expose
`forward_windows=(3,5,10,20)`, the actual time horizon is not
equivalent. This axis is `DISJOINT` for all prior variants.

Phase 2 will rerun prior variants on the canonical M7 data surface with
M6.1's `15m` timeframe and `forward_windows=(3,5,10,20)` for
methodology reconciliation, while preserving the prior original 5m
results as locked historical context.

### Cost Model

A.3 computes net 5-bar returns after `round_trip_cost_pct=0.0010`.
The prior taxonomy module has no public cost parameter and reports raw
signed returns. Therefore the original cost axis is `DISJOINT` for all
prior variants.

Phase 2 will import the prior module as-is. Because the prior module has
no public cost field to adjust, the reconciliation runner will compute
M6.1 cost-normalized net metrics outside the imported module from the
prior event return fields. This preserves the no-edit constraint while
making the comparison cost-aligned.

## 11. Direct And Near Analog Classification

Direct analog rule:

- A prior variant is a direct analog only if all five axes are
  `EQUIVALENT`.

Near analog rule:

- A prior variant is a near analog only if the core axes
  (sweep detection, entry timing, direction logic) are `EQUIVALENT` or
  `A3_NARROWER`, and cost/window are `EQUIVALENT`.

Phase 1 classification result:

- Direct analog candidates: none.
- Near analog candidates: none.
- Closest conceptual comparator: `delayed_reclaim`, because its
  direction logic is `EQUIVALENT` and its entry timing is the only axis
  classified as `A3_WIDER` rather than fully `DISJOINT` or
  `INCOMPARABLE`.

Interpretation before data:

- A.3 is `DISJOINT` from all prior variants on the sweep-detection core
  axis.
- Prior closure remains valid as scoped unless later phases show a
  direct equivalence that Phase 1 missed.
- The default reconciliation hypothesis after Phase 1 is that M6.1 A.3
  tested an equal-level-cluster reclaim primitive that prior confirmed
  pivot taxonomy did not test.

## 12. Phase 2 Empirical Reconciliation Specification

Phase 2 will happen only after Claude approves this plan.

### Inputs

- Canonical DB: `F:\crowded_unwind_backtest.db`
- Symbol/timeframe for reconciliation reruns: `BTCUSDT` `15m`
- Study window: `2022-01-01..2026-03-01`
- Prior module: `research_lab.analysis_sweep_reclaim_event_taxonomy_diagnostic_v1`
  imported as-is
- Prior original locked report:
  `docs/analysis/SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27.md`
- M6.1 A.3 locked metrics from Section 4

### Rerun Order

Although Phase 1 identifies no direct or near analog, Phase 2 will
rerun all prior decision variants under M6.1-aligned data/cost/window
settings to document whether the prior closure remains valid as scoped:

1. `wick_cross`
2. `immediate_reclaim`
3. `delayed_reclaim`
4. `close_bos`
5. `true_breakout_no_reclaim`
6. `confirmed_pivot` as lifecycle/control context only

This extends the handoff requirement and does not weaken it. No new
variants are introduced.

### Rerun Mechanics

The runner will:

1. Import the prior taxonomy module as-is.
2. Build `DiagnosticConfig(symbol="BTCUSDT", timeframe="15m",
   forward_windows=(3,5,10,20), reclaim_window_bars=4)` using public
   config fields.
3. Run the prior classifier against the canonical DB.
4. Extract the required prior cohorts from the prior module's summary.
5. Apply M6.1 cost normalization externally when computing net metrics,
   because the prior module has no public cost parameter.
6. Record raw signed and cost-normalized net metrics separately so the
   cost transformation is auditable.

### Metrics Recorded

For each variant:

- event_count
- net_5b_pf
- net_5b_median
- mfe_before_entry_median if derivable
- mfe_after_entry_5b_median
- mfe_before_after_ratio if derivable
- raw signed 5-bar median
- label timing used: detection or label_available
- source DB and timeframe

### Comparison Table Shape

| Variant | Source | event_count | net_5b_pf | net_5b_median | MFE_before | MFE_after | MFE ratio |
|---|---|---:|---:|---:|---:|---:|---:|
| A.3 raw_sweep_reclaim | M6.1 locked | 14236 | 2.847 | +0.001811 | 0.003038 | 0.007891 | 0.385 |
| prior_original raw_wick_cross | 2026-05-27 locked | 117953 | n/a | 0.000237 raw | n/a | n/a | n/a |
| prior_original immediate_reclaim | 2026-05-27 locked | 56340 | n/a | 0.000184 raw | n/a | n/a | n/a |
| prior_original delayed_reclaim | 2026-05-27 locked | 35368 | n/a | 0.000054 label raw | n/a | n/a | n/a |
| prior_original close_bos | 2026-05-27 locked | 61370 | n/a | -0.000288 raw | n/a | n/a | n/a |
| prior_original true_breakout | 2026-05-27 locked | 26192 | n/a | -0.000268 label raw | n/a | n/a | n/a |
| prior_rerun_m6.1_settings rows | M7 new | TBD | TBD | TBD | TBD | TBD | TBD |

No Phase 2 result will be interpreted until Phase 3 is complete and the
mechanical verdict rules are applied.

## 13. Phase 3 A.3 Stability Specification

Phase 3 will happen only after Claude approves this plan.

Phase 3 reruns the A.3 implementation on disjoint sub-windows of the
same canonical DB. These sub-window results are stability diagnostics;
they do not replace the locked full-window M6.1 A.3 numbers.

Sub-windows:

| Window | Start UTC | End UTC |
|---|---|---|
| Sub-1 | 2022-01-01 | 2023-04-30 |
| Sub-2 | 2023-05-01 | 2024-08-31 |
| Sub-3 | 2024-09-01 | 2026-03-01 |

Per-window metrics:

- event_count
- net_5b_pf
- net_5b_median
- mfe_before_entry_median
- mfe_after_entry_5b_median
- mfe_before_after_ratio

Stability passes if all three sub-windows satisfy:

- net_5b_pf >= 1.5
- net_5b_median >= 0
- mfe_before_after_ratio <= 1.0

Stability fails if any sub-window misses any one of the three
thresholds.

If a sub-window has too few events to compute meaningful metrics, the
diagnostic returns `RECONCILIATION_INCONCLUSIVE` rather than inventing a
sample-size rescue rule. The Phase 2/3 implementation test suite will
include this mechanical behavior.

## 14. Pre-Data Verdict Rules

These labels are frozen before Phase 2/3 data.

| Verdict | Triggered when |
|---|---|
| `METHODOLOGY_ARTIFACT_PRIOR_CLOSURE_STANDS` | Phase 1: at least one axis where A.3 differs from prior in a way that conceptually explains a metric-level gap, such as A.3's equal-level-cluster sweep source being different from prior confirmed pivots. Phase 2: prior_rerun_m6.1_settings reproduces prior_original invalidation. Phase 3: A.3 stability may pass or fail. Outcome: A.3 tests a different conceptual primitive than prior; prior closure stands as scoped. |
| `METHODOLOGY_GAP_PRIOR_CLOSURE_INCOMPLETE` | Phase 1: at least one axis classified as `DISJOINT` or `A3_WIDER` in a core axis, meaning prior did not include the A.3 case or A.3 is a broader version. Phase 2: prior_rerun_m6.1_settings stays invalidated on its own variants. Phase 3: A.3 stability passes on at least 2 of 3 sub-windows. Outcome: prior closure was narrow, not wrong; A.3 is a new candidate primitive. |
| `METHODOLOGY_EQUIVALENT_PRIOR_CLOSURE_WAS_WRONG` | Phase 1: at least one prior variant is `EQUIVALENT` on all five axes. Phase 2: that direct analog, rerun under M6.1 settings, produces A.3-compatible metrics: PF and median in the same positive direction and MFE ratio under 1.0. Phase 3: A.3 stability passes on all 3 sub-windows. Outcome: prior closure must be reopened. |
| `RECONCILIATION_INCONCLUSIVE` | Phase 1 cannot proceed because prior code/artifacts are missing, Phase 2 reruns crash on data incompatibility, Phase 3 cannot run due to sample-size issues, or required MFE/PF quantities cannot be mechanically computed. Diagnostic limitation, not a finding. |

Downgrade rule:

- If A.3 stability fails but Phase 1 + Phase 2 would otherwise support
  `METHODOLOGY_EQUIVALENT_PRIOR_CLOSURE_WAS_WRONG`, the final verdict
  downgrades to `METHODOLOGY_GAP_PRIOR_CLOSURE_INCOMPLETE` with an
  explicit note that A.3 is unstable across sub-periods.

No post-data rescue interpretation may change these rules.

## 15. Test Plan For Commit 2

Commit 2 tests will cover:

- Axis label enum accepts only `EQUIVALENT`, `A3_NARROWER`,
  `A3_WIDER`, `DISJOINT`, `INCOMPARABLE`.
- Phase 1 classification table contains all six required prior variants
  and all five required axes.
- Direct analog detection requires all five axes `EQUIVALENT`.
- Near analog detection requires core axes `EQUIVALENT` or
  `A3_NARROWER` and cost/window `EQUIVALENT`.
- No direct/near analog is produced from the committed Phase 1 table.
- Phase 2 comparison rows preserve locked A.3 metrics and do not
  overwrite them with sub-window values.
- Cost-normalized metrics subtract `0.0010` without mutating the prior
  taxonomy module.
- Sub-window splitting returns the declared three disjoint windows.
- Stability passes only when all required thresholds pass per window.
- Stability failure downgrades the equivalent-prior-wrong path per the
  pre-data downgrade rule.
- Final verdict computation is mechanical from Phase 1 + Phase 2 +
  Phase 3 inputs.

Validation commands:

- `.\\.venv\\Scripts\\python.exe -m pytest -o addopts= tests/test_research_lab/test_sweep_reclaim_methodology_reconciliation_v1.py -q`
- `.\\.venv\\Scripts\\python.exe -m compileall research_lab/diagnostics/sweep_reclaim_methodology_reconciliation_v1.py tests/test_research_lab/test_sweep_reclaim_methodology_reconciliation_v1.py`

## 16. Acceptance Criteria

Commit 1 acceptance:

- Single file added:
  `docs/research/SWEEP_RECLAIM_METHODOLOGY_RECONCILIATION_V1_PLAN.md`.
- Operator-locked constraints included verbatim.
- Phase 1 mapping table filled for all six prior variants and five
  axes using only allowed labels.
- A.3 definitions and prior definitions are extracted from code/plan,
  not inferred from post-data preference.
- Direct/near analog criteria are declared before Phase 2 data.
- Phase 2 and Phase 3 specs are declared before implementation.
- Verdict labels and triggers are frozen before data.
- No code, tests, DB runs, or generated artifacts in commit 1.
- Five unrelated PC untracked files remain unstaged.

Commit 2 acceptance after plan audit:

- `research_lab/diagnostics/sweep_reclaim_methodology_reconciliation_v1.py`
- `tests/test_research_lab/test_sweep_reclaim_methodology_reconciliation_v1.py`
- `research_lab/reports/sweep_reclaim_methodology_reconciliation_v1.json`
- `research_lab/reports/sweep_reclaim_methodology_reconciliation_v1.sha256`
- `research_lab/reports/sweep_reclaim_methodology_reconciliation_v1.md`
- Prior taxonomy module imported as-is and not modified.
- M6/M6.1 modules not modified.
- Locked A.3 full-window numbers preserved exactly in output.
- Canonical DB path explicitly recorded.
- Mechanical verdict reported.
- Focused tests and compile validation pass.
- STATUS=`READY_FOR_CLAUDE_AUDIT`.

## 17. Risk Register

| Risk | Mitigation |
|---|---|
| A.3 return-start uses reclaim bar while reclaim condition is known from the same bar close. | Do not rewrite A.3. Document exact timing in Phase 1 and test/report it explicitly in Phase 2/3. Any alternate timing is a different diagnostic. |
| Prior module has no public cost parameter. | Import prior module as-is and compute M6.1 cost-normalized comparison metrics in the M7 wrapper from prior return fields. Report raw and net metrics separately. |
| Prior original used 5m while M6.1 A.3 used 15m. | Treat original as locked historical context. Phase 2 reruns prior logic on canonical 15m data for reconciliation and marks timeframe change explicitly. |
| No direct or near analog exists after Phase 1. | Rerun all prior variants under M6.1 settings for scoped closure evidence; final verdict rules already allow methodology-gap or artifact outcomes. |
| Builder over-interprets A.3 as real edge before reconciliation. | Commit 1 contains no data runs; Phase 2 produces tables only; final verdict is computed only after Phase 3. |
| Prior closure is accidentally declared wrong in wording. | Use "QUESTIONED, not OBALONA" framing throughout; prior closure remains valid as scoped unless mechanical rules say otherwise after all phases. |
| Untracked PC files enter commit. | Stage explicit file paths only; never use `git add .` or `git add -A`. |

## 18. Open Questions

None blocking commit 1.

The main audit-sensitive implementation detail for commit 2 is the cost
model: the prior taxonomy module has no public cost config, so M7 must
cost-normalize in the reconciliation wrapper while leaving the prior
module untouched.

## 19. Commit 1 Stop Condition

After this plan is committed and pushed with
STATUS=`PLAN_READY_FOR_CLAUDE_AUDIT`, Codex stops. Phase 2/3 code does
not begin until Claude approves or returns fix-required items.


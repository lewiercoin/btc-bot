# RED_TEAM_REPLICATION_V1_PLAN

## 1. Executive Summary

`RED_TEAM_REPLICATION_V1` is a research-only red-team replication milestone.
It does not search for a new edge, tune a strategy, promote a candidate, or
modify the live trading path.

The milestone has two parts:

- Part A: adversarially replicate `SMC_SEQUENCE_EDGE_FEASIBILITY_V1` by
  replaying the deterministic baseline, then running five frozen
  single-parameter perturbations and one confluence-off raw sweep-reclaim
  ablation.
- Part B: independently reproduce the trial-00095 accepted-trade baseline
  metrics using frozen accepted entries, SQL candle replay, and a minimal exit
  simulator written from scratch.

Adversarial framing is mandatory: the default position is that prior verdicts
are wrong unless replication confirms them.

Scope guards:

- Research-only.
- No production code changes.
- No `core/`, `bot/`, `execution/`, `orchestrator.py`, settings, schema, or
  dependency manifest changes.
- No new hypothesis, new setup family, new entry geometry, new confluence
  proxy, or new exit model beyond the independent reproduction simulator.
- No threshold tuning beyond the five listed Part A perturbations.
- No generated database, snapshot, approval bundle, or ad hoc report commits.
- No implementation before Claude Code approves this plan.

## 2. Why M6

M6 exists because the operator no longer fully trusts the prior audit chain.
The trigger concerns are process-level and evidence-level:

- M3 initially used a non-canonical DB through a silent fallback. The final
  verdict was later re-run on canonical data and remained analytically correct,
  but the process failed to detect the substitution early.
- Five consecutive `HYPOTHESIS_INVALIDATED` verdicts occurred under one
  auditor in a short period. They may all be correct, but M6 treats that as a
  claim to be tested rather than trusted.
- Prior audits verified compliance with approved plans. M6 asks whether the
  prior plans themselves may have been too narrow, over-gated, or too dependent
  on one parameterization.

M6 is therefore an audit-of-the-audits. Its output has higher epistemic weight
than the prior invalidation reports because it is designed to challenge them
directly.

## 3. Repository Inventory

Base branch and commit:

- Branch: `deploy/multi-asset-paper-v1`
- Base commit: `683d0ca282386824d8255ec3005579668955dfd7`
- Expected subject:
  `research: reclaim_rejection diagnostic V1 re-run on canonical DB`

Part A source artifacts:

- `research_lab/analysis_smc_sequence_edge_feasibility_v1.py`
- `tests/test_research_lab_smc_sequence_edge_feasibility_v1.py`
- `docs/research/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_PLAN.md`
- `docs/audits/AUDIT_SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md`
- `docs/analysis/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md`

Part A baseline facts to reproduce:

- Prior JSON SHA256:
  `8CA802FD610DFE552225C9318A455345D8917D688ABBD2B3647CA69C4B6A78A4`
- Full sequence event count: `1271`
- Net 5-bar PF proxy: `1.061059`
- Net 5-bar median return: `-0.000442`
- Median MFE before entry: `0.011565`
- Median post-entry 5-bar MFE: `0.004916`
- Prior verdict: `FAIL_OR_INCONCLUSIVE_REVIEW_REQUIRED`, interpreted as
  `HYPOTHESIS_INVALIDATED`.

Part B source artifacts:

- `research_lab/analysis_output/trial_00095_trades.json`
- `research_lab/analysis_output/trial_00095_intrabar_frozen_entries.json`
- `research_lab/diagnostics/trial_00095_conditional_edge_attribution_v1.py`
  is reference-only. It may be read for schema understanding but must not be
  imported by the Part B simulator.
- `research_lab/reports/trial_00095_conditional_edge_attribution_v1.json`
- `research_lab/reports/trial_00095_conditional_edge_attribution_v1.md`
- `docs/audits/AUDIT_TRIAL_00095_ATTRIBUTION_V1_2026-05-30.md`

Part B baseline facts to reproduce:

- Count: `274`
- ER: `2.1211338666525608`
- PF: `4.216455510596996`
- WR: `0.5656934306569343`
- Total R: `581.1906794628017`

Canonical DB:

- Preferred explicit path during PC run:
  `F:\crowded_unwind_backtest.db`
- Expected repository-relative canonical path if copied locally:
  `research_lab/data/crowded_unwind_backtest.db`
- M6 will use an explicit CLI/config DB path and will not allow silent fallback.

Pre-flight checks already passed on the PC:

- `aggtrade_buckets.cvd IS NOT NULL`: `3122272`
- `cvd_price_history`: `0`
- BTCUSDT 15m candles in `2022-01-01T00:00:00+00:00` through
  `2026-03-01T00:00:00+00:00`: `145921`
- Frozen trial-00095 trades: `274`
- Frozen intrabar entries: `274`
- Replay run13 DB snapshot: present, `701.4 MB`
- Python env: imports for `pandas`, `sqlite3`, `pytest`, `hashlib`, `json`,
  and `pathlib` pass.

## 4. Part A Specification

Part A will implement
`research_lab/diagnostics/red_team_replication_v1.py` after plan approval.
The orchestrator will import `research_lab.analysis_smc_sequence_edge_feasibility_v1`
as-is and call its public analysis path with explicit `DiagnosticConfig`
instances.

The baseline and perturbation runs are:

| Run | Configuration | Purpose |
|---|---|---|
| A.1 baseline | default `DiagnosticConfig` | Deterministic replay and SHA check |
| P1 | `sweep_proximity_atr=0.20` | Tighten sweep proximity |
| P2 | `sweep_proximity_atr=0.80` | Loosen sweep proximity |
| P3 | `mitigation_window_bars=5` | Force earlier mitigation timing |
| P4 | `displacement_body_atr=0.30` | Lower displacement body threshold |
| P5 | `round_trip_cost_pct=0.0000` | Cost-blind gross edge check |
| A.3 | raw sweep-reclaim ablation | Disable displacement, structure shift, FVG, and mitigation gates |

For P1-P5, each run changes exactly one parameter. All other config values
remain default. The implementation must verify this isolation mechanically.

For A.3, the raw sweep-reclaim ablation will be implemented in the M6
orchestrator, not by editing the original SMC module. Entry candidate becomes
the first bar after a sweep where close re-enters the swept zone. Timing, costs,
forward windows, deterministic output, and summary fields remain aligned with
the SMC comparison table.

Fields recorded for every Part A run:

- run id and config override
- verdict
- event count
- net 5-bar PF
- net 5-bar median return
- median MFE before entry
- median post-entry 5-bar MFE
- MFE before/after ratio
- delta versus A.1 baseline

Locked pre-data interpretations:

- P1 `sweep_proximity_atr=0.20`: If this flips the verdict, the original sweep proximity was too loose and admitted noisy sweeps that diluted a narrower edge.
- P2 `sweep_proximity_atr=0.80`: If this flips the verdict, the original sweep proximity was too strict and rejected valid sweep contexts.
- P3 `mitigation_window_bars=5`: If this flips the verdict, the prior invalidation was materially driven by waiting too long for mitigation entry.
- P4 `displacement_body_atr=0.30`: If this flips the verdict, the original displacement gate was too aggressive and excluded softer but tradable sequences.
- P5 `round_trip_cost_pct=0.0000`: If this alone flips the verdict, SMC_SEQUENCE has gross edge that transaction costs destroy rather than no structural edge.
- A.3 raw sweep-reclaim ablation: If this flips while gated SMC remains invalidated, the SMC gates destroyed a simpler raw edge and prior sweep-reclaim closure must be reconciled.

## 5. Part B Specification

Part B will implement
`research_lab/diagnostics/trial_00095_sql_replication_v1.py` after plan
approval.

The simulator will:

1. Load frozen accepted trades from
   `research_lab/analysis_output/trial_00095_trades.json`.
2. Load frozen entry context from
   `research_lab/analysis_output/trial_00095_intrabar_frozen_entries.json`.
3. Connect read-only to the explicit market DB path.
4. Query BTCUSDT 15m candles ordered by `open_time`.
5. Match each accepted trade to its entry timestamp and replay candles starting
   at entry bar + 1.
6. Apply an independent SL/TP/trailing-stop simulator written in this file.
7. Produce realized R per trade.
8. Compute count, ER, PF, WR, total R, and per-trade `pnl_r` Pearson
   correlation against the frozen baseline values.

Frozen trade artifact schema observed during pre-flight:

- `trade_id`
- `opened_at`
- `direction`
- `regime`
- `pnl_r`
- `sweep_depth_pct`
- `exit_reason`
- `mae`
- `mfe`
- `session_hour`

Frozen entry artifact schema observed during pre-flight:

- `trade_id`
- `signal_id`
- `opened_at`
- `closed_at`
- `direction`
- `regime`
- `entry_price`
- `stop_loss`
- `tp1`
- `tp2`
- `baseline_pnl_r`
- `baseline_exit_reason`

Exit simulation design:

- Risk is `abs(entry_price - stop_loss)`.
- Direction-aware price crossing determines SL and TP hits.
- The simulator must infer all usable exit fields from the frozen entry and
  trade artifacts.
- If an intrabar candle hits both SL and TP/trail-relevant levels, the
  implementation must use a deterministic pessimistic ordering and report the
  assumption.
- Any trade whose independent replay cannot reproduce baseline `pnl_r` within
  tolerance must be listed by `trade_id`, baseline value, replicated value,
  absolute delta, direction, entry time, and exit reason.

Trail rule reconnaissance:

- Before implementing the exit simulator, the implementation must inspect the
  full frozen trade and entry artifacts and list every field present.
- The implementation must explicitly classify whether a closed-form TP_TRAIL
  rule is derivable from those fields alone.
- If the trail rule is derivable, the report must document the exact rule and
  continue with full-population reproduction.
- If the trail rule is not derivable, Part B must use the stratified verdict
  rules in Section 6. Simulator incompleteness on TP_TRAIL trades is then
  reported as `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`, not as edge
  falsification.
- Recovering trail logic from bot or strategy source is an action item only
  after the stratified result; it is not allowed as an import or hidden
  dependency in this independent simulator.

This is not a re-derivation of the edge. It is a reproduction check that the
recorded trades behave as recorded.

Database choice for Part B:

- Primary: canonical DB at the explicit path supplied via CLI, expected on PC
  as `F:\crowded_unwind_backtest.db`. All Part B verdict computation is bound
  to canonical-DB results.
- Comparison: replay-run13 snapshot at
  `research_lab/snapshots/replay-run13-regime-aware-trial-00063.db`. The
  simulator may also run against the snapshot to produce a side-by-side
  comparison table, but the snapshot result never substitutes for the
  canonical result in verdict computation.
- If canonical-DB Part B produces `VALIDATED_EDGE_NOT_REPRODUCIBLE` while
  snapshot-DB Part B passes acceptance, the report classifies the divergence as
  `DATABASE_LINEAGE_MISMATCH`. The canonical verdict still stands as the M6
  result.
- Silent substitution is forbidden. The simulator must record which DB produced
  which result in the JSON output.

## 6. Pre-Data Verdict Rules

Part A verdict rules:

- If A.1 baseline SHA does not match
  `8CA802FD610DFE552225C9318A455345D8917D688ABBD2B3647CA69C4B6A78A4`, return
  `BASELINE_NOT_REPRODUCIBLE` and stop.
- If all five perturbations plus A.3 remain invalidated, Part A returns
  `SMC_SEQUENCE_INVALIDATION_ROBUST`.
- If any perturbation produces net 5-bar PF >= `1.5`, net 5-bar median >= `0`,
  and MFE ratio <= `1.0`, Part A returns
  `SMC_SEQUENCE_VERDICT_NOT_ROBUST`.
- If P5 is the only run that flips, Part A returns
  `SMC_SEQUENCE_EDGE_IS_GROSS_ONLY`.
- If A.3 flips but A.1-P5 do not, Part A returns
  `SMC_GATES_DESTROYED_RAW_EDGE`.
- If contradictory perturbations such as P1 and P2 both flip, the report must
  add `METRIC_HYPERSENSITIVE` as a diagnostic note alongside the primary Part A
  verdict.

Part B acceptance rules:

| Metric | Attribution baseline | Required independent replication |
|---|---:|---|
| Count | 274 | within +/- 2 trades |
| ER | 2.121 | within +/- 5%, range 1.965 to 2.227 |
| PF | 4.216 | within +/- 5%, range 4.005 to 4.427 |
| WR | 56.57% | within +/- 3pp, range 53.5% to 59.5% |
| Per-trade `pnl_r` Pearson | 1.0 | >= 0.95 |

Part B must compute Pearson correlation for:

- full population;
- SL-exit subset;
- TP_TRAIL-exit subset.

Part B stratified verdict rules:

- If full population, SL subset, and TP_TRAIL subset all have Pearson >=
  `0.95`, and count/ER/PF/WR remain inside acceptance bounds, Part B returns
  full reproduction and contributes to `REPLICATION_VERIFIES_PRIOR_VERDICTS`.
- If SL-subset Pearson >= `0.95` and TP_TRAIL-subset Pearson < `0.95`, Part B
  returns `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`. This is an actionable
  simulator/artifact limitation, not edge falsification.
- If SL-subset Pearson < `0.95`, Part B returns
  `VALIDATED_EDGE_NOT_REPRODUCIBLE`, because the unambiguous stop-loss subset
  failed independently of trailing-stop ambiguity.
- If count, ER, PF, or WR fail acceptance while subset correlations pass, Part
  B returns `VALIDATED_EDGE_NOT_REPRODUCIBLE` and reports the failing metric.

Final M6 verdict:

- `REPLICATION_VERIFIES_PRIOR_VERDICTS`: Part A returns
  `SMC_SEQUENCE_INVALIDATION_ROBUST` and Part B passes all acceptance rules.
- `PRIOR_VERDICT_NOT_ROBUST`: Part A returns
  `SMC_SEQUENCE_VERDICT_NOT_ROBUST`, `SMC_SEQUENCE_EDGE_IS_GROSS_ONLY`, or
  `SMC_GATES_DESTROYED_RAW_EDGE`.
- `VALIDATED_EDGE_NOT_REPRODUCIBLE`: Part B fails canonical count/ER/PF/WR
  acceptance or the SL-exit subset fails Pearson >= `0.95`.
- `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`: Part B reproduces the SL subset but
  cannot reproduce TP_TRAIL trades from the frozen artifact fields. This does
  not trigger edge falsification or production-pause verdict by itself; it
  triggers trail-rule recovery and a follow-up reproduction pass.
- `DATABASE_LINEAGE_MISMATCH`: canonical-DB and snapshot-DB Part B results
  materially disagree. The canonical-DB result binds the M6 verdict, and the
  mismatch is reported as lineage evidence.
- `BASELINE_NOT_REPRODUCIBLE`: A.1 SHA mismatch prevents meaningful Part A
  replication.

No post-data rescue interpretation may change these rules.

## 7. Test Plan

Commit 2 will include focused tests after plan approval.

Part A tests:

- Baseline config construction uses default `DiagnosticConfig`.
- P1-P5 each mutate exactly one field and preserve all other defaults.
- Comparison rows are deterministic and sorted in the declared run order.
- Verdict evaluator applies the A.5 thresholds mechanically.
- A.3 ablation disables displacement, structure shift, FVG, and mitigation
  gates without editing the original SMC module.
- Deterministic output hashing is stable for the same payload.

Part B tests:

- Synthetic LONG trade hits SL and reports negative R.
- Synthetic LONG trade hits TP/trail and reports positive R.
- Synthetic SHORT trade mirrors LONG behavior correctly.
- Both-hit intrabar ordering uses the declared deterministic pessimistic rule.
- Trade/entry artifact joins fail explicitly on missing required entry fields.
- Acceptance evaluator passes when metrics are inside frozen bounds.
- Acceptance evaluator fails count, ER, PF, WR, and correlation independently.
- Pearson correlation handles exact reproduction and divergent reproduction.
- SL-subset Pearson is computed independently from full-population Pearson.
- TP_TRAIL-subset Pearson is computed independently from full-population
  Pearson.
- Stratified verdict evaluator returns full reproduction when full, SL, and
  TP_TRAIL correlations all pass.
- Stratified verdict evaluator returns
  `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` when SL passes and TP_TRAIL fails.
- Stratified verdict evaluator returns `VALIDATED_EDGE_NOT_REPRODUCIBLE` when
  SL-subset Pearson fails.
- DB-binding test verifies canonical-DB results control verdict computation and
  snapshot results are comparison-only.

Validation commands for commit 2:

- Focused pytest for M6 tests.
- Compile validation for M6 diagnostic modules.
- Deterministic run that writes JSON, SHA256, and Markdown report artifacts.

## 8. Acceptance Criteria For Diagnostic Completion

Commit 1 acceptance criteria:

- Only `docs/research/RED_TEAM_REPLICATION_V1_PLAN.md` is committed.
- The plan contains all 11 required sections from the handoff.
- Locked pre-data interpretations are present verbatim.
- No code, tests, reports, artifacts, snapshots, or unrelated files are
  committed.
- Commit message includes WHAT, WHY, and
  `STATUS: PLAN_READY_FOR_CLAUDE_AUDIT`.

Commit 2 acceptance criteria after Claude plan approval:

- Part A orchestrator imports the SMC module as-is and uses
  `DiagnosticConfig` overrides only.
- Part A baseline SHA check is hard-fail.
- P1-P5 perturbation isolation is test-covered.
- A.3 ablation is implemented and reported separately.
- Part B simulator is independent and imports no bot/strategy/prior attribution
  engine code.
- Part B reports artifact schemas, used exit fields, DB choice, and per-trade
  divergences.
- Final report computes M6 verdict mechanically from frozen rules.
- Focused tests and compile validation pass.
- No production modules or settings are modified.

## 9. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| A.1 SHA mismatch due to environment or serialization drift | Part A cannot compare to prior verdict | Hard-stop as `BASELINE_NOT_REPRODUCIBLE`; investigate before perturbations |
| Canonical DB path differs across PC/laptop | Silent data substitution | Require explicit DB path and record sanity counts in report |
| A.3 ablation accidentally becomes a new hypothesis | Scope drift | Treat any flip as verdict-robustness failure, not edge discovery |
| P1-P5 combined accidentally | Invalid perturbation evidence | Unit test exactly-one override per run |
| Part B simulator under-specifies trailing behavior | False non-reproduction | Report exact exit fields used and every divergence; do not import old engine to hide ambiguity |
| Both SL and TP hit in one candle | Intrabar ambiguity | Use deterministic pessimistic ordering and disclose assumption |
| Existing untracked PC files contaminate commit | Bad audit checkpoint | Stage only named files; never use `git add .` |
| Snapshot fallback hides canonical DB issue | Repeat of M3 process failure | Document DB choice and forbid silent fallback |

## 10. Open Questions For Operator

None blocking for commit 1.

Implementation-phase question to resolve in the commit 2 report if needed:

- If canonical DB replay diverges but replay-run13 snapshot reproduces, the
  report must classify the divergence as a database lineage issue rather than
  silently accepting the fallback.

## 11. Commit Plan

Commit 1:

- File: `docs/research/RED_TEAM_REPLICATION_V1_PLAN.md`
- No code.
- No tests.
- No generated artifacts.
- Commit status: `PLAN_READY_FOR_CLAUDE_AUDIT`
- Stop after push and wait for Claude Code plan audit.

Commit 2, only after Claude approval:

- `research_lab/diagnostics/red_team_replication_v1.py`
- `research_lab/diagnostics/trial_00095_sql_replication_v1.py`
- `tests/test_research_lab/test_red_team_replication_v1.py`
- `tests/test_research_lab/test_trial_00095_sql_replication_v1.py`
- `research_lab/reports/red_team_replication_v1.json`
- `research_lab/reports/red_team_replication_v1.sha256`
- `research_lab/reports/red_team_replication_v1.md`
- `research_lab/reports/trial_00095_sql_replication_v1.json`

Commit 2 status:

- `READY_FOR_CLAUDE_AUDIT`

Claude Code audits both checkpoints. Builder does not self-audit.

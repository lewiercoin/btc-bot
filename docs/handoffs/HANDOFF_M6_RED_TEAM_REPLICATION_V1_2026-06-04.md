# HANDOFF: M6 RED_TEAM_REPLICATION_V1

Date: 2026-06-04
From: Claude Code (auditor, adversarial framing)
To: Codex (builder)
Branch base: `deploy/multi-asset-paper-v1` @ `683d0ca`
Builder commit branch: `research/m6-red-team-replication` (Codex creates if absent)

---

## CLAUDE HANDOFF -> CODEX (RED-TEAM MODE)

### Why this milestone exists

The operator no longer fully trusts the chain of prior audit and research
verdicts. Specific concerns:

1. M3 silent-fallback regression (Codex used non-canonical DB; verdict was
   accepted by Claude audit; only later operator question + data-equivalence
   check revealed the issue). Even though the verdict turned out to be
   correct on the canonical data, the **process** failed to detect the
   substitution.
2. Five `HYPOTHESIS_INVALIDATED` verdicts in 8 days under a single auditor.
   Possible that the auditor has a blind spot. Possible that every plan
   shared a hidden bias.
3. Audit framing is compliance-with-plan, not adversarial. A plan with a
   subtly over-restrictive parameter (e.g., a frozen threshold that
   excludes the true edge region) will receive PASS on procedure even if
   the underlying scientific question was answered wrong.

M6 is the explicit test: replay prior work with adversarial framing and
see if the verdicts survive. Output of M6 has higher epistemic weight than
all prior audits combined, because it is designed to break them.

### Checkpoint

- Last commit: `683d0ca` (`research: reclaim_rejection diagnostic V1 re-run on canonical DB`)
- Branch base: `deploy/multi-asset-paper-v1`
- M5 status: PAUSED at db03609 (plan approved, commit 2 not started)
- Working tree expected clean before start.

### Before you code

Read (mandatory):

1. `docs/research/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_PLAN.md`
2. `docs/audits/AUDIT_SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md`
3. `docs/analysis/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md`
4. `research_lab/analysis_smc_sequence_edge_feasibility_v1.py`
5. `docs/audits/AUDIT_TRIAL_00095_ATTRIBUTION_V1_2026-05-30.md`
6. `research_lab/diagnostics/trial_00095_conditional_edge_attribution_v1.py`
7. `research_lab/reports/trial_00095_conditional_edge_attribution_v1.json`
8. `docs/research/RESEARCH_LANDSCAPE_RESET_2026-06-04.md` (from
   `claude/festive-maxwell-iciBo`)
9. `AGENTS.md`
10. `docs/QUANT_RESEARCH_OPERATING_MODEL.md`

### Milestone: M6 RED_TEAM_REPLICATION_V1

**Research-only.** No production code, no settings, no schema, no new
hypothesis, no new setup family. M6 ONLY replicates and challenges prior
work.

**Commit split (mandatory, do not collapse):**

1. **Commit 1 — Plan document.** Single file:
   `docs/research/RED_TEAM_REPLICATION_V1_PLAN.md`.
   STATUS: `PLAN_READY_FOR_CLAUDE_AUDIT`. No code, no tests, no artifacts.
   STOP after this commit and wait for Claude audit + plan approval.
2. **Commit 2 — Implementation.** After plan approval, implement Part A
   + Part B + tests + artifacts in a single commit. STATUS:
   `READY_FOR_CLAUDE_AUDIT`. Do not self-audit.

---

## PART A — SMC_SEQUENCE Adversarial Replication

### A.1 — Deterministic baseline replay

Re-run `research_lab/analysis_smc_sequence_edge_feasibility_v1.py` with its
default `DiagnosticConfig` on the canonical DB. Verify the SHA256 of the
JSON output matches the prior commit
(`docs/analysis/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md` records
SHA `8CA802FD610DFE552225C9318A455345D8917D688ABBD2B3647CA69C4B6A78A4`).

PASS = SHA matches. This is a determinism check. Failure means something
changed in the environment, data, or code that we are unaware of.

### A.2 — Single-parameter perturbations

Re-run the diagnostic with each of these 5 perturbations applied one at a
time (5 separate runs, never combined). All other parameters stay at
defaults.

| ID | Parameter | Baseline | Perturbation | Rationale |
|---|---|---:|---|---|
| P1 | `sweep_proximity_atr` | 0.40 | **0.20** | Tighten sweep proximity. If verdict flips, the gate was too loose, accepting noise sweeps. |
| P2 | `sweep_proximity_atr` | 0.40 | **0.80** | Loosen sweep proximity. If verdict flips, the gate was too strict, rejecting valid sweeps. |
| P3 | `mitigation_window_bars` | 20 | **5** | Earlier mitigation entry. Tests whether invalidation was driven by entry-too-late, which is the documented prior conclusion. |
| P4 | `displacement_body_atr` | 0.50 | **0.30** | Lower displacement bar. Tests whether invalidation was driven by requiring too aggressive displacement and missing softer-but-valid sequences. |
| P5 | `round_trip_cost_pct` | 0.0010 | **0.0000** | Cost-blind PnL. Tests whether invalidation was cost-driven. If cost-blind also fails, no edge structurally; if cost-blind passes, entry geometry has gross edge that fees eat. |

For each perturbation, record:
- final verdict (INVALIDATED / passes invalidation gates);
- per-rule status (median MFE before, median MFE after, net 5-bar PF, net 5-bar median return);
- delta vs baseline;
- event count (validates that perturbation actually moved the surface).

### A.3 — Confluence-off ablation

Construct a `RAW_SWEEP_RECLAIM` ablation by **disabling** the
displacement + structure shift + FVG + mitigation gates entirely. Entry
candidate becomes: first bar after sweep where close re-enters the swept
zone. Everything else stays default (timing, cost, exits).

Purpose: simplest possible "sweep + reclaim" baseline. If it also fails
the invalidation gates, that is consistent with prior
`SWEEP_RECLAIM_EVENT_TAXONOMY` closure. If it passes, the SMC sequence
gates were destroying a raw edge that exists at simpler structure — which
contradicts both prior closures.

Record the same fields as A.2.

### A.4 — Verdict comparison

Build a single comparison table:

| Run | Verdict | Event N | Net 5b PF | Net 5b median | MFE_before/MFE_after |
|---|---|---:|---:|---:|---:|
| A.1 baseline | INVALIDATED (expected) | … | 1.061 (expected) | -0.000442 (expected) | 2.35 (expected) |
| A.2 P1 sweep_prox=0.20 | ? | ? | ? | ? | ? |
| A.2 P2 sweep_prox=0.80 | ? | ? | ? | ? | ? |
| A.2 P3 mitig_window=5 | ? | ? | ? | ? | ? |
| A.2 P4 disp_body=0.30 | ? | ? | ? | ? | ? |
| A.2 P5 cost=0 | ? | ? | ? | ? | ? |
| A.3 RAW_SWEEP_RECLAIM | ? | ? | ? | ? | ? |

### A.5 — Pre-data verdict rules

- If A.1 baseline SHA does NOT match prior, raise
  `BASELINE_NOT_REPRODUCIBLE`. Stop. Critical investigation.
- If ALL 5 perturbations + ablation remain INVALIDATED, A returns
  `SMC_SEQUENCE_INVALIDATION_ROBUST`.
- If ANY perturbation produces net 5b PF ≥ 1.5 AND net 5b median ≥ 0
  AND MFE ratio ≤ 1.0, A returns `SMC_SEQUENCE_VERDICT_NOT_ROBUST` —
  document which perturbation flipped and by how much.
- If P5 (cost=0) is the only run that flips, return
  `SMC_SEQUENCE_EDGE_IS_GROSS_ONLY` — gross edge exists, cost destroys
  it. This is materially different from "no edge."
- If A.3 ablation flips but A.1-A.2 do not, return
  `SMC_GATES_DESTROYED_RAW_EDGE` — the SMC sequence gates removed a
  simpler edge that existed at sweep+reclaim level. This contradicts
  prior SWEEP_RECLAIM closure and reopens that family.

### A.6 — Honest disclosure requirements

The implementation report MUST include:
- A statement of which prior conclusion the perturbation set was designed
  to challenge (verbatim from this handoff).
- For each perturbation, a one-sentence interpretation of what the result
  means — written BEFORE seeing the result, encoded in the plan.
- No post-data interpretation rescue. If a flip happens that the plan did
  not anticipate, report it neutrally and let the audit interpret.

---

## PART B — Trial-00095 Independent SQL Replication

### B.1 — Pure-SQL + minimal simulator

Build a minimal Python script
(`research_lab/diagnostics/trial_00095_sql_replication_v1.py`) that:

1. Connects to canonical DB
   (`research_lab/data/crowded_unwind_backtest.db` via pendrive).
2. Loads the 274 trial-00095 accepted entry timestamps + entry prices +
   SL + TP + direction from the existing frozen accepted-trade artifact.
3. For each trade, replays the candle stream from
   `candles WHERE symbol='BTCUSDT' AND timeframe='15m'` starting at
   entry_bar + 1, applying a minimal independent SL/TP/trail-stop
   simulator written from scratch in this file (NO imports from
   `core/`, `bot/`, `execution/`, or
   `research_lab/diagnostics/trial_00095_conditional_edge_attribution_v1.py`).
4. Records realized R per trade.
5. Computes ER, PF, WR independently.

Exit logic (SL distance, TP distance, trail rules) must be inferred from
the same frozen accepted-trade artifact (one of the recorded fields is
`exit_reason` = `SL` or `TP_TRAIL`; artifact also records final `pnl_r`).
If the independent simulator reproduces these `pnl_r` values within
tolerance, the validated edge is empirically real.

### B.2 — Acceptance criteria (pre-data, frozen)

| Metric | Attribution baseline | Independent SQL replication target |
|---|---:|---|
| Count | 274 | within ±2 trades (allow data margin) |
| ER | 2.121 | within ±5% (1.965 - 2.227) |
| PF | 4.216 | within ±5% (4.005 - 4.427) |
| WR | 56.57% | within ±3pp (53.5% - 59.5%) |
| Per-trade `pnl_r` correlation | 1.0 | ≥ 0.95 (Pearson) |

If divergence exceeds any criterion, B returns
`VALIDATED_EDGE_NOT_REPRODUCIBLE` — critical, all production decisions
paused pending root cause.

### B.3 — Honest disclosure

Report MUST include:
- Schema of the frozen accepted-trade artifact (which fields exist).
- Which exit fields the simulator used.
- Any trades where independent simulator could not exactly reproduce
  `pnl_r` — list trade_id and divergence.
- Explicit statement: "this is not a re-derivation of the edge — it is a
  reproduction check that the recorded trades behave as recorded."

---

## Cross-cutting Forbidden Patterns

- Do not tune any threshold beyond the 5 explicit perturbations + 1
  ablation listed in Part A.
- Do not introduce new entry geometry, new confluence proxy, new exit
  model, or new feature in Part A. The diagnostic must remain the same
  SMC_SEQUENCE code path with only the listed parameter changes.
- Do not import any bot/strategy code in Part B. Independent reproduction
  means independent.
- Do not interpret a Part A flip as a new edge discovery. Flips return
  `_NOT_ROBUST` verdict — they trigger Claude+operator reconciliation,
  not a new milestone.
- Do not modify `core/`, `bot/`, `execution/`, settings, schema, or
  dependency manifests.

## Deliverables

**Commit 1 — Plan only:**

- `docs/research/RED_TEAM_REPLICATION_V1_PLAN.md` with sections:
  1. Executive summary + scope guards + adversarial framing statement.
  2. Why M6 (operator audit-distrust context).
  3. Repository inventory (smc_sequence module + trial_00095 attribution
     module + canonical DB).
  4. Part A specification (baseline + 5 perturbations + 1 ablation, each
     with pre-data interpretation sentence).
  5. Part B specification (SQL replication with frozen acceptance
     criteria).
  6. Pre-data verdict rules for both parts.
  7. Test plan.
  8. Acceptance criteria for diagnostic completion.
  9. Risk register.
  10. Open questions for operator (if any).

**Commit 2 — Implementation:**

- `research_lab/diagnostics/red_team_replication_v1.py` — orchestrator
  for Part A perturbations + ablation (imports
  `analysis_smc_sequence_edge_feasibility_v1` and overrides
  `DiagnosticConfig` per run).
- `research_lab/diagnostics/trial_00095_sql_replication_v1.py` — Part B
  independent simulator.
- `tests/test_research_lab/test_red_team_replication_v1.py` — unit tests
  covering perturbation isolation, ablation gate removal, deterministic
  comparison table generation.
- `tests/test_research_lab/test_trial_00095_sql_replication_v1.py` — unit
  tests covering exit simulator correctness on synthetic candles and
  acceptance-criteria evaluator.
- `research_lab/reports/red_team_replication_v1.json` — deterministic JSON
  with comparison table for Part A.
- `research_lab/reports/red_team_replication_v1.sha256`.
- `research_lab/reports/red_team_replication_v1.md` — markdown report
  with both Part A and Part B results plus final M6 verdict computed
  mechanically from A.5 and B.2 rules.
- `research_lab/reports/trial_00095_sql_replication_v1.json` — raw Part B
  per-trade results.

## Database

Canonical DB only:
`research_lab/data/crowded_unwind_backtest.db` (operator pendrive).

Pre-run sanity (must match exactly, same as M3/M5):
- `aggtrade_buckets` non-null cvd count: `3,122,272`
- BTCUSDT 15m row SHA256 (window `2022-01-01..2026-03-01`):
  `F6BD821E4C829B0B7259B6F0F442607FA213A2D66BCB4D201E6EDCBF07FA79DC`

Hard-fail guard from M3 must be respected. No `--allow-fallback`.

## Your first response must contain

1. Confirmed milestone scope (Part A perturbations P1-P5 + ablation A.3,
   Part B SQL replication).
2. Acceptance criteria you propose (may extend; cannot weaken any
   threshold in this handoff).
3. Confirmation that Part A will use `analysis_smc_sequence_edge_feasibility_v1`
   imported as-is, with `DiagnosticConfig` overrides only.
4. Confirmation that Part B will write an **independent** exit simulator,
   not import from `trial_00095_conditional_edge_attribution_v1`.
5. Pre-data interpretation sentence for each of P1-P5 + ablation (one
   sentence each, encoded in the plan document — Claude audit will verify
   these are written BEFORE any data look).
6. Plan implementation outline (ordered steps).
7. Only then: start drafting the plan document.

## Commit discipline

- Single plan file in commit 1. WHAT / WHY / STATUS = `PLAN_READY_FOR_CLAUDE_AUDIT`.
- After audit approval, single implementation commit. WHAT / WHY / STATUS =
  `READY_FOR_CLAUDE_AUDIT`.
- Do NOT self-mark as "done". Claude Code audits after push.

## Time budget guidance

- Plan draft: 2-3 hours.
- Plan audit: 1-2 hours.
- Part A implementation (5 perturbations + ablation + tests + run): 8-14
  hours.
- Part B implementation (SQL simulator + tests + run): 3-5 hours.
- Implementation audit: 4-8 hours.

Total milestone budget: 18-32 hours from start to verdict.

## Notes on auditor framing

For this milestone, the auditor (Claude Code) commits to using
**adversarial framing** during commit 2 audit:

- Default position: prior verdicts are wrong unless replication says
  otherwise.
- Specifically searches for: edge that prior diagnostic destroyed via gate
  composition; cost-blind gross edge; flipped verdicts under bounded
  perturbation; trial-00095 baseline that fails to reproduce.
- Builder should expect harder audit questions on Part B (validated edge),
  not easier — the validated edge has more downstream consequence if false.

---

## End of handoff.

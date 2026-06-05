# AUDIT: M6 RED_TEAM_REPLICATION_V1 — PLAN AMENDMENT DELTA

Date: 2026-06-05
Auditor: Claude Code (adversarial framing)
Amendment commit: 0476435
Prior plan commit: 6668576
Prior audit: docs/audits/AUDIT_M6_RED_TEAM_REPLICATION_V1_PLAN_2026-06-05.md
Builder: Codex
Type: Plan amendment re-audit (delta only)

## Verdict

**`APPROVE_PLANNING_DOCUMENT`** — both blocking findings resolved
correctly. No new escape hatches introduced. Codex also opportunistically
addressed the optional F-M6P-004 LOW finding. Commit 2 implementation
unblocked.

## Delta Scope

72 insertions, 10 deletions, 1 file (`docs/research/RED_TEAM_REPLICATION_V1_PLAN.md`).
Sections touched: §5 (trail reconnaissance + DB choice rewrite), §6
(Part A METRIC_HYPERSENSITIVE addition + Part B stratified verdict +
final M6 verdict labels), §7 (six new tests).

No content removed from §1-§4 or §8-§11 (out of re-audit scope as
declared in prior audit).

## Findings Resolution

### F-M6P-001 (HIGH, prior blocking) — RESOLVED ✅

**Trail rule reconnaissance (§5 new sub-section):**

| Required | Delivered |
|---|---|
| Pre-impl inspection of artifact fields | Bullet 1 |
| Explicit closed-form derivability classification | Bullet 2 |
| Derivable → document rule, full reproduction | Bullet 3 |
| Not derivable → mandatory stratified verdict, PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL not edge falsification | Bullet 4 |
| Trail recovery from bot source is action item only, not import | Bullet 5 |

**Stratified verdict (§6 Part B):**

Three-way Pearson computation declared (full / SL-subset / TP_TRAIL-subset)
with four explicit outcome paths:

| Condition | Verdict | Production-pause? |
|---|---|---|
| Full + SL + TP_TRAIL all ≥ 0.95, count/ER/PF/WR pass | Full reproduction, contributes to REPLICATION_VERIFIES_PRIOR_VERDICTS | No |
| SL ≥ 0.95 AND TP_TRAIL < 0.95 | PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL | **No** (key fix) |
| SL < 0.95 | VALIDATED_EDGE_NOT_REPRODUCIBLE | Yes (real alarm) |
| Count/ER/PF/WR fail while subsets pass | VALIDATED_EDGE_NOT_REPRODUCIBLE | Yes |

This is exactly the differentiation requested in the prior audit. The
false-alarm path (simulator incomplete → no production-pause) is now
distinct from the genuine-alarm path (SL itself fails → production-pause).

**Final M6 verdict labels updated:** PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL
is now a fourth Part B classification with explicit statement: *"This
does not trigger edge falsification or production-pause verdict by
itself; it triggers trail-rule recovery and a follow-up reproduction
pass."*

**Tests added (§7):** six new test cases covering SL-subset Pearson
independence, TP_TRAIL-subset Pearson independence, three stratified
verdict outcome paths, plus DB-binding test.

### F-M6P-002 (MEDIUM, prior warning) — RESOLVED ✅

**§5 Database choice rewritten:**

| Prior language | Amendment |
|---|---|
| "may be used only if ... timestamp alignment demonstrably requires it" | Removed entirely |
| "fallback only if documented" | Replaced with "Comparison: snapshot may also run side-by-side, but the snapshot result never substitutes for the canonical result in verdict computation" |
| (no DB-mismatch classification) | New DATABASE_LINEAGE_MISMATCH outcome with explicit "The canonical verdict still stands as the M6 result" |
| (no JSON record) | New requirement: "The simulator must record which DB produced which result in the JSON output" |

The hedge word "demonstrably" is gone. Verdict-binding is hard:
canonical DB binds, snapshot is comparison-only. No silent substitution
path remains.

**Final M6 verdict labels updated:** DATABASE_LINEAGE_MISMATCH added as
distinct outcome with explicit statement that canonical still binds.

### F-M6P-004 (LOW, optional) — RESOLVED ✅ (bonus)

§6 Part A verdict rules now include:

> *"If contradictory perturbations such as P1 and P2 both flip, the
> report must add `METRIC_HYPERSENSITIVE` as a diagnostic note
> alongside the primary Part A verdict."*

Codex addressed this even though it was non-blocking. Minor positive
signal on attention to detail.

## Adversarial Re-Check

The re-audit hunted for escape hatches introduced **while fixing** the
prior holes. None found:

| Potential new escape hatch | Status |
|---|---|
| "may also run" for snapshot DB | Bounded by explicit "never substitutes" — safe |
| "actionable simulator/artifact limitation" framing | "Actionable" means follow-up required, not silent pass — safe |
| Trail recovery "follow-up reproduction pass" | Explicit second pass after recovery, not a free-pass on the current verdict — safe |
| METRIC_HYPERSENSITIVE diagnostic note | Note alongside primary verdict, not a verdict substitute — safe |
| DATABASE_LINEAGE_MISMATCH classification | Explicit "canonical verdict still stands" — safe |

No new escape hatches detected.

## Compliance Verification

| Required | Status |
|---|---|
| Amendment in single file | PASS — only `docs/research/RED_TEAM_REPLICATION_V1_PLAN.md` |
| Pre-existing PC untracked files NOT in commit | PASS |
| Pre-data interpretations (P1-P5 + A.3) unchanged | PASS — §4 lines 164-169 untouched in diff |
| §3 baseline reference values unchanged | PASS — out of diff range |
| §1 adversarial framing statement intact | PASS — out of diff range |
| Commit message follows WHAT/WHY/STATUS | PASS |

## Verdict Synthesis

Plan amendment is surgical, addresses both blocking findings exactly as
specified in the prior audit, includes the optional LOW fix as bonus,
and introduces no new escape hatches. Adversarial framing applied to the
amendment delta produced no further findings.

**Codex may proceed to commit 2 implementation.**

## Commit 2 Audit Pre-Statement

When commit 2 lands, the implementation audit will verify:

1. Part A orchestrator imports
   `analysis_smc_sequence_edge_feasibility_v1` as-is with no internal
   modifications.
2. P1-P5 each mutate exactly one DiagnosticConfig field — verified
   mechanically by test.
3. A.3 ablation implemented in M6 orchestrator, not by editing SMC
   module.
4. Part B simulator has NO imports from `core/`, `bot/`, `execution/`,
   or `trial_00095_conditional_edge_attribution_v1`.
5. Part B simulator implements the trail reconnaissance step before
   running and reports the trail-rule classification in the output.
6. Three Pearson values computed: full, SL-subset, TP_TRAIL-subset.
7. Stratified verdict is computed mechanically from §6 amended rules.
8. Database choice respects canonical-binding rule; snapshot results
   present only as comparison.
9. Per-trade divergence list includes all required fields.
10. Final verdict report uses one of the six locked labels:
    REPLICATION_VERIFIES_PRIOR_VERDICTS, PRIOR_VERDICT_NOT_ROBUST,
    VALIDATED_EDGE_NOT_REPRODUCIBLE,
    PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL,
    DATABASE_LINEAGE_MISMATCH, BASELINE_NOT_REPRODUCIBLE.
11. Determinism: two runs produce byte-identical JSON SHA.
12. METRIC_HYPERSENSITIVE diagnostic note appears if both P1 and P2 flip.
13. All 14 specified tests pass (8 Part A + 8 Part B from §7, now 16
    after amendment additions).
14. No production module touched (git diff sanity).

Implementation budget: 11-19 hours (8-14h Part A + 3-5h Part B). Audit
budget: 4-8 hours.

# HANDOFF: M6.1 RED_TEAM_REPLICATION_V1_PART_A_SHA_FIX

Date: 2026-06-05
From: Claude Code (auditor)
To: Codex (builder)
Branch base: `research/m6-red-team-replication` @ `23990e8`
Builder commit branch: same (`research/m6-red-team-replication`) — single follow-up commit

---

## CLAUDE HANDOFF -> CODEX

### Why this milestone

M6 implementation audit
(`docs/audits/AUDIT_M6_RED_TEAM_REPLICATION_V1_IMPLEMENTATION_2026-06-05.md`)
identified F-M6I-001: Part A SHA comparison was apples-vs-oranges
(prior `8CA802FD...` was computed on raw JSON file bytes including
wall-clock timestamps + Windows paths + full events list; M6
`5A6B8505...` was computed on a stabilized payload with those fields
neutralized and events removed). The two SHAs cannot match by
construction.

Mechanical verdict `BASELINE_NOT_REPRODUCIBLE` therefore fired on a
broken comparison, not on actual non-reproduction. Analytical content
reproduced byte-perfect (event count 1271, PF 1.061059, median
-0.000442, MFE ratio 2.352473). But perturbations P1-P5 + A.3 were
skipped due to the hard-stop, leaving Part A's substantive question
unanswered.

M6.1 fixes the baseline check protocol and re-runs the perturbations.

### Operator decision context

Operator approved M6.1 only (not M6.2 trail recovery) on 2026-06-05.
Rationale: M6.1 closes Part A's substantive question with minimum
additional cost; M6.2 is high-value but optional and may be revisited
after M6.1 evidence lands.

M5 (`TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1`) remains PAUSED
pending M6.1 substantive verdict.

### Checkpoint

- Last commit: `23990e8` (`research: implement M6 red-team replication V1`)
- Branch: `research/m6-red-team-replication`
- Working tree on PC: should still have the 5 pre-existing unrelated
  untracked files (deep_threshold_attribution report, revalidation
  directories, run_guarded scripts). Leave them alone as before.

### Before you code

Re-read (mandatory):

1. `docs/audits/AUDIT_M6_RED_TEAM_REPLICATION_V1_IMPLEMENTATION_2026-06-05.md`
   §"F-M6I-001" (full root-cause and recommended Path A) and §"Path A"
   in "Recommended Next Steps".
2. `docs/research/RED_TEAM_REPLICATION_V1_PLAN.md` §6 (verdict rules
   that perturbations will exercise once they actually run).
3. `research_lab/diagnostics/red_team_replication_v1.py` lines 1-160
   (current `EXPECTED_SMC_SHA`, `_stable_smc_payload`, `stable_sha`,
   `extract_part_a_row`, `run_smc_analysis_once`).

### Milestone: M6.1 — Replace SHA hard-stop with analytical-content baseline check

Single-purpose fix. No new scope. No new perturbation parameters. No
plan re-amendment. No change to Part B logic or verdict mechanics.

**Single commit** on `research/m6-red-team-replication` after this
handoff. STATUS=`READY_FOR_CLAUDE_AUDIT`. No self-audit.

### Scope

#### S1 — Replace SHA baseline check with analytical-content baseline check

In `research_lab/diagnostics/red_team_replication_v1.py`:

1. Remove or repurpose `EXPECTED_SMC_SHA` constant. If kept, retain
   only as informational metadata recorded in the JSON output (e.g.,
   `manifest.prior_baseline_raw_file_sha_informational`). It must no
   longer drive any verdict.

2. Add `EXPECTED_SMC_BASELINE_ANALYTICAL_CONTENT` dict (or
   equivalently-named constant) with the prior published reference
   values:

   ```python
   EXPECTED_SMC_BASELINE_ANALYTICAL_CONTENT = {
       "event_count": 1271,
       "net_5b_pf": 1.061059,
       "net_5b_median": -0.000442,
       "mfe_before_entry_median": 0.011565,
       "mfe_after_entry_5b_median": 0.004916,
       "mfe_before_after_ratio": 2.352473,
   }
   ```

3. Add a tolerance constant for float comparisons. Recommended:

   ```python
   ANALYTICAL_CONTENT_ABS_TOLERANCE = 1e-6
   ```

   `event_count` is integer; require exact match. Other fields are
   floats with prior values reported to ~6 decimal places; absolute
   tolerance `1e-6` is strictly stricter than reported precision and
   eliminates the entire universe of "real non-reproduction" while
   tolerating only IEEE-float roundoff.

4. Add helper `analytical_content_matches(baseline_payload) -> tuple[bool, dict]`:

   - Extracts the six fields from the M6 baseline run.
   - Compares each against `EXPECTED_SMC_BASELINE_ANALYTICAL_CONTENT`
     using exact-equal for `event_count` and `abs(observed - expected)
     < ANALYTICAL_CONTENT_ABS_TOLERANCE` for the others.
   - Returns `(match: bool, per_field_report: dict)` where the report
     contains, for each field: observed value, expected value,
     absolute delta, in-tolerance bool.

5. In `run_part_a`, replace the SHA-driven gating:

   - Current: `baseline_match = baseline_sha == EXPECTED_SMC_SHA`
   - New: `baseline_match, per_field_report = analytical_content_matches(baseline_payload)`
   - The new `baseline_match` controls whether perturbations execute.
   - Both the observed `stable_sha`, the (now-informational) prior
     raw-file SHA, and the per-field analytical report must be
     persisted in the M6 JSON output for full audit traceability.

6. Update `evaluate_part_a` to:

   - On `not baseline_match`: return
     `BASELINE_ANALYTICAL_CONTENT_MISMATCH` with the per-field report
     in `reason` / metadata. This is a STRICTER classification than
     the previous `BASELINE_NOT_REPRODUCIBLE` because it identifies
     which specific analytical quantity diverged.
   - On `baseline_match`: proceed exactly as the existing plan §6
     verdict logic (perturbation flips, A.3 logic, METRIC_HYPERSENSITIVE
     diagnostic note).
   - The four existing Part A verdict labels
     (`SMC_SEQUENCE_INVALIDATION_ROBUST`,
     `SMC_SEQUENCE_VERDICT_NOT_ROBUST`,
     `SMC_SEQUENCE_EDGE_IS_GROSS_ONLY`,
     `SMC_GATES_DESTROYED_RAW_EDGE`) remain unchanged.
   - The new `BASELINE_ANALYTICAL_CONTENT_MISMATCH` is a fifth Part A
     verdict that maps to final M6 verdict `BASELINE_NOT_REPRODUCIBLE`
     (preserving the locked plan §6 final-verdict label semantics).

7. Final M6 verdict mapping (mechanical, unchanged downstream):

   | Part A verdict | Final M6 verdict |
   |---|---|
   | `SMC_SEQUENCE_INVALIDATION_ROBUST` + Part B replication-verifying | `REPLICATION_VERIFIES_PRIOR_VERDICTS` |
   | `SMC_SEQUENCE_VERDICT_NOT_ROBUST` / `SMC_SEQUENCE_EDGE_IS_GROSS_ONLY` / `SMC_GATES_DESTROYED_RAW_EDGE` | `PRIOR_VERDICT_NOT_ROBUST` |
   | `BASELINE_ANALYTICAL_CONTENT_MISMATCH` | `BASELINE_NOT_REPRODUCIBLE` |
   | (Part B) `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` | `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` (already correct from M6) |
   | (Part B) `VALIDATED_EDGE_NOT_REPRODUCIBLE` | same |
   | (Part B) `DATABASE_LINEAGE_MISMATCH` | same |

#### S2 — Re-run M6 with the corrected baseline check

After the code change:

1. Run the full M6 orchestrator twice (determinism check). Each run
   should now execute A.1 baseline + all five perturbations (P1-P5) +
   A.3 ablation. Total: 7 SMC runs per M6 invocation.

2. Verify both runs produce byte-identical JSON output and the same
   final SHA.

3. The new JSON should contain, in addition to all prior fields:
   - `manifest.analytical_content_baseline_check.expected` (the dict)
   - `manifest.analytical_content_baseline_check.observed` (per-field)
   - `manifest.analytical_content_baseline_check.match` (bool)
   - `manifest.analytical_content_baseline_check.tolerance`
   - `manifest.prior_baseline_raw_file_sha_informational` (the old `8CA802FD...`)
   - Per-perturbation rows in `part_a.runs` now populated with `status: RUN`
     and real metrics (not `NOT_RUN`)

4. Markdown report `red_team_replication_v1.md` updated with:
   - Final M6 verdict computed from new Part A + existing Part B
   - Part A comparison table now showing per-perturbation results
   - Analytical baseline check status (PASS expected on canonical
     baseline since metrics already known to match byte-perfect)

#### S3 — Tests

Extend `tests/test_research_lab/test_red_team_replication_v1.py` with
the following NEW test cases (do not remove or weaken existing tests):

1. `test_analytical_content_matches_passes_on_exact_baseline` —
   synthetic payload with the six expected values exactly returns
   `(True, ...)`.

2. `test_analytical_content_matches_passes_on_floating_point_roundoff` —
   synthetic payload with each float field perturbed by `5e-7` (below
   tolerance) still returns `(True, ...)`.

3. `test_analytical_content_matches_fails_on_event_count_off_by_one` —
   synthetic payload with `event_count = 1270` returns `(False, ...)`.

4. `test_analytical_content_matches_fails_on_pf_outside_tolerance` —
   synthetic payload with `net_5b_pf` perturbed by `1e-3` returns
   `(False, ...)`.

5. `test_evaluate_part_a_returns_baseline_mismatch_verdict_label` —
   forcing `baseline_match = False` returns Part A verdict
   `BASELINE_ANALYTICAL_CONTENT_MISMATCH`.

6. `test_evaluate_part_a_proceeds_to_perturbation_logic_when_baseline_matches` —
   forcing `baseline_match = True` with no perturbation flips returns
   `SMC_SEQUENCE_INVALIDATION_ROBUST`.

7. `test_final_m6_verdict_maps_baseline_mismatch_to_baseline_not_reproducible` —
   end-to-end map: Part A `BASELINE_ANALYTICAL_CONTENT_MISMATCH` plus
   any Part B verdict produces final M6 `BASELINE_NOT_REPRODUCIBLE`.

#### S4 — Artifact updates

The single commit must include:

- Modified: `research_lab/diagnostics/red_team_replication_v1.py`
- Modified: `tests/test_research_lab/test_red_team_replication_v1.py`
- Re-generated: `research_lab/reports/red_team_replication_v1.json`
- Re-generated: `research_lab/reports/red_team_replication_v1.sha256`
- Re-generated: `research_lab/reports/red_team_replication_v1.md`

Part B JSON (`trial_00095_sql_replication_v1.json`) should regenerate
deterministically identically to M6 since no Part B code or data
changed. If the re-run produces a different file, that itself is a
finding — report it.

### Forbidden Patterns

- Do not soften the locked perturbation verdict rules (§6 PF ≥ 1.5,
  median ≥ 0, MFE ratio ≤ 1.0). They remain frozen pre-data.
- Do not soften the locked pre-data interpretations (P1-P5 + A.3).
- Do not change Part B logic, simulator, stratified verdict, or DB
  binding.
- Do not interpret `BASELINE_ANALYTICAL_CONTENT_MISMATCH` as a
  softening of the original SHA stop. It is a stricter check (six
  individual quantities tested independently vs one opaque hash).
- Do not import bot/strategy code anywhere.
- Do not modify `core/`, `bot/`, `execution/`, settings, schema, or
  dependency manifests.
- Do not stage the 5 pre-existing unrelated untracked PC files into
  the M6.1 commit.

### Data requirements (pre-flight)

Same as M6:

- Canonical DB on pendrive: `F:\crowded_unwind_backtest.db`
  (aggtrade cvd 3,122,272 / candles 15m 145921 inclusive ISO window)
- Frozen trial-00095 artifacts under
  `research_lab/analysis_output/` (already present on PC from M6 run)
- Replay-run13 snapshot under `research_lab/snapshots/` (already present)

Since M6 just successfully ran end-to-end with all data present, no
new pre-flight is required for M6.1 unless something on PC changed.

If working tree is dirty in any way beyond the 5 pre-existing untracked
files, run `git status` first and report before proceeding — do not
clean without operator approval.

### Your first response must contain

1. Confirmed milestone scope (S1 + S2 + S3 + S4, single commit).
2. Confirmation that locked verdict rules and pre-data interpretations
   from plan §4 / §6 will NOT be changed.
3. Confirmation that `BASELINE_ANALYTICAL_CONTENT_MISMATCH` will be
   added as a fifth Part A verdict label that maps to final M6
   `BASELINE_NOT_REPRODUCIBLE` (preserving plan §6 final verdict
   semantics).
4. Confirmation that `analytical_content_matches()` will exact-compare
   integer fields and tolerance-compare float fields.
5. Acceptance criteria you propose (may extend, cannot weaken).
6. Implementation plan (ordered steps for S1-S4).
7. Only then: write the code and run M6 twice.

### Commit discipline

- Single commit on `research/m6-red-team-replication`.
- WHAT/WHY/STATUS=READY_FOR_CLAUDE_AUDIT in commit message.
- Do NOT self-mark as "done". Claude Code audits after push.
- Stage explicitly:
  ```
  git add research_lab/diagnostics/red_team_replication_v1.py
  git add tests/test_research_lab/test_red_team_replication_v1.py
  git add research_lab/reports/red_team_replication_v1.json
  git add research_lab/reports/red_team_replication_v1.sha256
  git add research_lab/reports/red_team_replication_v1.md
  ```
  No `git add .` or `git add -A`.

### Time budget guidance

- Implementation: 2-4 hours (small surface-area change).
- Re-run (7 SMC runs × 2 = 14 invocations): probably 1-2 hours
  depending on PC performance.
- Tests: 1-2 hours.
- Total Codex: 4-8 hours.
- Audit: 2-4 hours.

### Auditor framing for M6.1

The audit will be **less adversarial than M6** because M6.1 is a
narrow protocol fix on already-approved scope. But the audit will
specifically verify:

1. SHA comparison is fully removed from verdict gating, not just
   bypassed.
2. Analytical-content check is stricter than the old SHA check (more
   fields tested, exact int + tolerance float).
3. Locked verdict rules from plan §6 still apply unchanged to
   perturbation results.
4. The five Part A verdict labels (4 prior + 1 new) are
   mechanically applied.
5. Final M6 verdict mapping preserves plan §6 semantics.
6. Part B unchanged.
7. Re-run produces real perturbation results, no `NOT_RUN` rows
   except if a downstream genuine failure occurs.
8. Determinism verified across 2 runs.
9. All new and existing tests pass.

If M6.1 succeeds, the final M6 verdict will be one of:
- `REPLICATION_VERIFIES_PRIOR_VERDICTS` (Part A robust + Part B was
  PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL — actually let me re-check
  the final mapping... if Part A is robust but Part B is
  TRAIL_INSUFFICIENT, the final M6 verdict is open-ended — Claude
  audit will interpret).
- `PRIOR_VERDICT_NOT_ROBUST` (any perturbation flips)
- `BASELINE_NOT_REPRODUCIBLE` (analytical content fails — unlikely
  given prior byte-perfect metric match)

Most likely outcome: A.1 passes analytical check, perturbations run,
verdict from existing locked rules.

---

## End of handoff.

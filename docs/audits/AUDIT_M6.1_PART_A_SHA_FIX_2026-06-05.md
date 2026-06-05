# AUDIT: M6.1 RED_TEAM_REPLICATION_V1_PART_A_SHA_FIX — IMPLEMENTATION

Date: 2026-06-05
Auditor: Claude Code (adversarial framing)
Commit: 2375b3924f98197c5761b30fac94da646ebafa7a
Branch: research/m6-red-team-replication
Prior audits:
- M6 plan: docs/audits/AUDIT_M6_RED_TEAM_REPLICATION_V1_PLAN_2026-06-05.md
- M6 amendment: docs/audits/AUDIT_M6_RED_TEAM_REPLICATION_V1_PLAN_AMENDMENT_2026-06-05.md
- M6 implementation: docs/audits/AUDIT_M6_RED_TEAM_REPLICATION_V1_IMPLEMENTATION_2026-06-05.md
Builder: Codex
Type: M6.1 protocol-fix implementation audit

## Verdict

**`DONE_WITH_MAJOR_FINDING`**

Implementation is correct per all locked rules. Tests pass (27/27).
Determinism verified (SHA `96128632...` stable across 2 runs). The
analytical-content baseline check correctly replaced the broken SHA
comparison and the perturbations actually ran.

**M6.1 produced the most consequential research finding of the entire
research-lab cycle.** A.3 raw sweep+reclaim ablation **flipped the
verdict by a wide margin** (PF 2.847, net median +0.001811, MFE ratio
0.385 — all three flip-criteria thresholds satisfied with strong
margin), while P1-P5 SMC-sequence parametric perturbations did not.

**Mechanical Part A verdict: `SMC_GATES_DESTROYED_RAW_EDGE`.**
**Pre-data interpretation triggered (locked in plan §4 line 169):**

> *"If this flips while gated SMC remains invalidated, the SMC gates
> destroyed a simpler raw edge and prior sweep-reclaim closure must be
> reconciled."*

This is the adversarial finding M6 was designed to surface. The audit
chain that closed `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1`
(2026-05-27) as INVALIDATED may have done so on a methodology that did
not test the simplest primitive correctly. M6.1 evidence indicates the
simpler primitive has edge characteristics under the same flip criteria.

One implementation observation (F-M6.1I-002): the Codex priority logic
in `final_m6_verdict` buries `SMC_GATES_DESTROYED_RAW_EDGE` under
`PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` for the final M6 label. The
substantive Part A finding is technically correct but operator-facing
"final verdict" label is misleading.

## Critical M6.1 Numerical Results

### Part A — Perturbation comparison

| Run | Status | Event N | Net 5b PF | Net 5b Median | MFE Before/After | Flip? |
|---|---|---:|---:|---:|---:|---|
| A.1 baseline | RUN | 1271 | 1.061 | -0.000442 | 2.352 | False |
| P1 sweep_prox=0.20 | RUN | 1212 | 0.967 | -0.000469 | 2.420 | False |
| P2 sweep_prox=0.80 | RUN | 1306 | 0.986 | -0.000477 | 2.439 | False |
| P3 mitig_window=5 | RUN | 903 | 1.216 | -0.000206 | 1.939 | False |
| P4 disp_body=0.30 | RUN | 1312 | 1.071 | -0.000428 | 2.350 | False |
| P5 cost=0 | RUN | 1271 | 1.458 | **+0.000558** | 2.352 | False (PF 0.04 short, MFE ratio still 2.35) |
| **A.3 raw sweep+reclaim** | RUN | **14236** | **2.847** | **+0.001811** | **0.385** | **TRUE** |

Flip criteria (locked plan §6): `PF ≥ 1.5 AND median ≥ 0 AND MFE ratio ≤ 1.0`.

### Interpretation per pre-data sentences (locked)

| Run | Locked pre-data interpretation | Triggered? |
|---|---|---|
| P1 (tighter) | "if flip → 0.40 gate was too loose admitting noise" | No flip → 0.40 gate is not too loose |
| P2 (looser) | "if flip → 0.40 gate was too strict rejecting valid" | No flip → 0.40 gate is not too strict |
| P3 (faster mitig) | "if flip → invalidation driven by waiting too long" | No flip → entry-too-late is not THE bottleneck under SMC gates (but see A.3) |
| P4 (lower displacement) | "if flip → displacement gate too aggressive" | No flip → displacement gate is not the bottleneck |
| P5 (cost=0) | "if alone flips → edge is gross only" | No flip on full criteria, but **PF jumped to 1.458 and median went positive** — partial signal that cost is biting an otherwise marginal edge |
| **A.3 (raw sweep+reclaim)** | **"if flips while gated stays invalidated → SMC gates destroyed simpler edge; prior sweep-reclaim closure must be reconciled"** | **TRIGGERED** |

The locked sentence for A.3 is now operative. Plan §6 explicitly stated
that this outcome requires reconciliation with the prior
`SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1` closure.

### Part B — unchanged from M6

Codex did not re-touch Part B logic; values byte-identical to M6 run:

- Trail rule classification: `NOT_DERIVABLE_FROM_FROZEN_ARTIFACT`
- Full Pearson: 0.785963
- SL-subset Pearson: 0.954062 (passes ≥0.95)
- TP_TRAIL-subset Pearson: 0.611562 (fails)
- Verdict: `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`

## Standard Audit Axes

| Axis | Status |
|---|---|
| Layer Separation | PASS |
| Contract Compliance | PASS |
| Determinism | PASS (2-run SHA stable) |
| Error Handling | PASS |
| Smoke Coverage | PASS (27/27 tests) |
| Tech Debt | LOW |
| AGENTS.md Compliance | PASS |

## Research Lab Audit Axes

| Axis | Status |
|---|---|
| Methodology Integrity | PASS (baseline check is stricter than prior SHA) |
| Promotion Safety | PASS (no production change) |
| Reproducibility & Lineage | PASS (analytical check passed, prior raw SHA kept as informational metadata) |
| Data Isolation | PASS |
| Search Space Governance | PASS (no new perturbations) |
| Artifact Consistency | PASS |
| Boundary Coupling | PASS |

## Quant Research Audit Axes

| Axis | Status |
|---|---|
| Methodology Rigor | PASS |
| Source Coverage | PASS |
| Repo/Code Inspection | PASS (Codex did not modify SMC module; A.3 ablation lives in M6 orchestrator) |
| Timing Discipline | PASS |
| Lookahead Risk | PASS for the M6.1 mechanism (entry on close-reclaim, no future bars) |
| Novelty vs Rescue | PASS (no rescue; A.3 flip honored locked rule) |
| Creativity vs Cherry-Picking | PASS (pre-data interpretations encoded in code, not rewritten) |

## Compliance Verification

| Required | Status |
|---|---|
| Analytical baseline check replaces SHA hard-stop | PASS — `analytical_content_matches` lines |
| Six fields tested: event_count, net_5b_pf, net_5b_median, mfe_before, mfe_after, ratio | PASS |
| Exact-int for event_count, 1e-6 abs tolerance for floats | PASS |
| Old `EXPECTED_SMC_SHA` kept as informational metadata (`prior_baseline_raw_file_sha_informational`) | PASS — visible in report |
| Fifth Part A verdict `BASELINE_ANALYTICAL_CONTENT_MISMATCH` added | PASS |
| Locked plan §6 perturbation flip rules unchanged | PASS |
| Pre-data interpretations P1-P5 + A.3 unchanged in `PRE_DATA_INTERPRETATIONS` dict | PASS |
| Part B logic untouched | PASS — file `trial_00095_sql_replication_v1.py` not in commit diff |
| Locked Part B amended verdict rules unchanged | PASS |
| 7 new tests added | PASS — 27 - 20 = 7 new |
| Determinism verified across 2 runs | PASS |
| Single commit on existing branch | PASS |
| Only 5 named files staged | PASS |
| 5 pre-existing PC untracked files NOT in commit | PASS |

## Findings

### F-M6.1I-001 — MAJOR SUBSTANTIVE FINDING — A.3 raw sweep+reclaim flips verdict by wide margin

Severity: **MAJOR_SUBSTANTIVE_FINDING** | Confidence: 4/5

**Numbers:**

A.3 ablation (sweep detected, then entry on first bar where close
re-enters the swept level) produces:

| Metric | A.3 | A.1 baseline | A.3 / A.1 |
|---|---:|---:|---:|
| Event count | 14,236 | 1,271 | 11.2× |
| Net 5b PF | 2.847 | 1.061 | 2.68× |
| Net 5b median | +0.001811 | -0.000442 | flip sign + factor ~4 |
| MFE before/after ratio | 0.385 | 2.352 | **6.1× better timing** |

All three flip-criteria thresholds passed with strong margin:
- PF: 2.847 vs threshold 1.5 (1.9× above)
- median: +0.001811 vs threshold 0 (positive)
- MFE ratio: 0.385 vs threshold 1.0 (2.6× below)

The MFE ratio in particular is decisive. **MFE ratio 0.385 means the
median favorable excursion AFTER entry is 2.6× larger than the
favorable excursion BEFORE entry.** Entry timing is GOOD for the raw
sweep+reclaim primitive — exactly the opposite of the SMC sequence
fingerprint (ratio 2.35× the wrong way).

**Per locked pre-data interpretation:** "the SMC gates destroyed a
simpler raw edge and prior sweep-reclaim closure must be reconciled."

**This contradicts prior `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1`
closure** (2026-05-27, audit
`docs/audits/AUDIT_SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27.md`,
verdict "IMPLEMENTATION APPROVED; HYPOTHESIS INVALIDATED").

**Caveat on confidence (rated 4/5, not 5/5):**

The flip is mechanically correct under M6's locked rules and M6's A.3
implementation. But before declaring "raw sweep+reclaim edge confirmed
real", an independent reconciliation milestone (M7 recommended below)
must verify:

1. **Methodology equivalence:** A.3 uses SMC module's sweep detection
   (equal-level cluster sweeps with proximity 0.40 ATR, depth, age
   constraints). The prior SWEEP_RECLAIM diagnostic may have used a
   different sweep definition. If sweep definitions differ, the
   comparison is not apples-to-apples and the flip may be an artifact
   of definition rather than a real reopening of the closed family.

2. **Entry timing equivalence:** A.3 entry is "first bar after sweep
   where close re-enters the swept level." Prior SWEEP_RECLAIM
   variants tested confirmed pivots, wick cross, close BoS, immediate
   reclaim, delayed reclaim, true breakout/no-reclaim. The A.3 entry
   may correspond to one specific prior variant that flipped, while
   the others did not.

3. **Cost and forward-window equivalence:** A.3 uses `round_trip_cost_pct
   = 0.0010` and `forward_windows = (3, 5, 10, 20)` from SMC sequence
   defaults. Prior SWEEP_RECLAIM may have used different settings.

4. **Sample inflation effect:** A.3 has 11.2× more events than A.1
   (14,236 vs 1,271). PF improvements on larger samples are sometimes
   driven by statistical effects rather than real edge. A walk-forward
   or sub-period stability test would clarify.

5. **Lookahead audit on A.3:** the M6 audit (this one) verifies A.3's
   timing is sane (entry only after close re-enters level, future bars
   not used in entry decision). But the broader question — is the
   sweep detection itself free of lookahead? — relies on SMC module's
   sweep detection being lookahead-clean. That was prior-audited.
   Worth verifying once more under adversarial framing in M7.

**Operator-relevant interpretation:**

If reconciliation in M7 confirms the flip is real (i.e., methodology
differences from prior SWEEP_RECLAIM closure DO explain why the prior
verdict was wrong), then:

- The closed family `SWEEP_RECLAIM` is REOPENED with a candidate
  primitive that has positive edge characteristics under M6 flip
  criteria.
- The "sweep+reclaim doesn't work" conclusion from 2026-05-27 was
  wrong. Specifically: it was wrong because prior SWEEP_RECLAIM
  implementations added gates or filters that destroyed a simpler
  edge.
- This is a genuinely new candidate setup family for further research.
- Operator-level trust in audit chain RESTORATION takes a hit — one
  prior verdict was wrong — but also gets a strong positive: the
  audit-of-audits design CAUGHT this miss.

If reconciliation reveals the flip is a methodology artifact, then:

- A.3 is informative as "the prior SWEEP_RECLAIM tests should have
  included this exact variant" but does not invalidate prior closure.
- M6.1 has still delivered substantive value by surfacing the
  methodology gap.

Either outcome is research progress. The bad outcome (prior verdict
silently wrong without M6 catching it) was avoided.

### F-M6.1I-002 — Final M6 verdict priority logic buries the substantive finding

Severity: MEDIUM | Confidence: 4/5

In `red_team_replication_v1.py` lines 482-499, the `final_m6_verdict`
function applies this priority order:

1. `BASELINE_ANALYTICAL_CONTENT_MISMATCH` (Part A) → `BASELINE_NOT_REPRODUCIBLE`
2. `DATABASE_LINEAGE_MISMATCH` (Part B) → same
3. `VALIDATED_EDGE_NOT_REPRODUCIBLE` (Part B) → same
4. `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` (Part B) → same
5. Both robust → `REPLICATION_VERIFIES_PRIOR_VERDICTS`
6. Else → `PRIOR_VERDICT_NOT_ROBUST`

Under M6.1 results:
- Part A: `SMC_GATES_DESTROYED_RAW_EDGE` (substantive finding)
- Part B: `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` (documentation gap)

The priority cascade hits rule 4 first and returns
`PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` as the final M6 label.

**Problem:** The Part B verdict was explicitly framed in plan §6 as
*"actionable simulator/artifact limitation, not edge falsification...
not edge falsification or production-pause verdict by itself."* It is
a documentation gap. Meanwhile Part A `SMC_GATES_DESTROYED_RAW_EDGE`
is a real research finding that reopens a closed family.

The current priority hides the bigger finding behind the smaller one.
An operator skimming the M6 final label would see "simulator gap" and
miss "closed family must be reopened."

**This is not a violation of locked rules** — the plan listed the
verdict labels but did not specify a priority order. Codex implemented
something defensible. But the current implementation choice
deprioritizes the Part A substantive finding.

**Recommended fix (not blocking M6.1 itself; record for M7 handoff):**

Either:
- (a) Change priority so Part A substantive findings
  (`SMC_SEQUENCE_VERDICT_NOT_ROBUST`,
  `SMC_SEQUENCE_EDGE_IS_GROSS_ONLY`, `SMC_GATES_DESTROYED_RAW_EDGE`)
  outrank Part B documentation gaps
  (`PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`); or
- (b) Make the final label a compound: e.g.
  `PRIOR_VERDICT_NOT_ROBUST + PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`.

The report markdown already shows both Part A and Part B verdicts
explicitly, so the substance isn't hidden — only the top-line label is
misleading. Audit and operator who read the full report see everything.

### F-M6.1I-003 — Analytical baseline check is correctly stricter than prior SHA check (INSIGHT)

Severity: INSIGHT | Confidence: 5/5

Old check: one opaque hash equality.
New check: six independent quantities, with exact-int for count and
1e-6 absolute tolerance for floats.

The new check is strictly stricter because:
- It identifies WHICH specific quantity diverged if mismatch occurs
  (not just "the hash failed")
- 1e-6 tolerance on floats reported to 6 decimal places is tighter
  than reported precision — only IEEE-float roundoff is tolerated
- Integer count is exact-match

The prior raw-file SHA is retained as informational metadata in the
JSON output (`manifest.prior_baseline_raw_file_sha_informational`),
preserving lineage without using it as a verdict gate.

### F-M6.1I-004 — Pre-data interpretation lock honored in mechanically-derived verdict (INSIGHT)

Severity: INSIGHT | Confidence: 5/5

The pre-data interpretation for A.3 (plan §4 line 169) is verbatim
encoded in `PRE_DATA_INTERPRETATIONS["A3_RAW_SWEEP_RECLAIM"]` in the
M6 module. The flip outcome triggered the locked sentence as written.
No post-data rewording. This is exactly the discipline pre-data
interpretation locking is meant to enforce.

The A.3 metadata in each event also embeds the interpretation
sentence, so any downstream consumer of the events list has the
pre-data lock visible.

### F-M6.1I-005 — P5 (cost=0) showed informative partial-flip (OBSERVATION)

Severity: OBSERVATION | Confidence: 3/5

P5 (cost-blind) is the only perturbation that pushed median net into
positive territory (+0.000558). PF rose to 1.458 (just 0.04 below the
1.5 flip threshold). But MFE ratio stayed at 2.352 (well above 1.0
threshold), so two of three flip conditions were missed and the run
did NOT flip mechanically.

This is informative: SMC sequence has a marginal positive gross edge
that cost destroys. But even cost-blind, the MFE accessibility
remains the structural problem — favorable move happens before entry.
So P5 alone does not change the SMC-sequence verdict.

(Pre-data interpretation says "if P5 alone flips → edge is gross
only." Since P5 did NOT flip on all criteria, this label was not
triggered. The locked sentence stays neutral.)

### F-M6.1I-006 — Tests cover the new analytical check and verdict mapping (INSIGHT)

Severity: INSIGHT | Confidence: 5/5

Seven new tests added:
1. Analytical content matches on exact baseline → passes
2. Analytical content matches on float roundoff (5e-7) → passes
3. Analytical content fails on event_count off-by-one → fails
4. Analytical content fails on PF outside tolerance → fails
5. Part A verdict mapping to BASELINE_ANALYTICAL_CONTENT_MISMATCH on
   mismatch
6. Part A proceeds to perturbation logic when match
7. Final M6 verdict maps BASELINE_ANALYTICAL_CONTENT_MISMATCH to
   BASELINE_NOT_REPRODUCIBLE

All seven align with the M6.1 handoff specification.

## Critical Issues

None. Implementation correctly applies all locked rules.

The substantive finding (F-M6.1I-001) is a research finding, not an
implementation defect.

## Warnings

F-M6.1I-002 — Final M6 verdict priority logic buries the substantive
Part A finding behind the Part B documentation gap. Non-blocking for
M6.1 audit; should be addressed in any future verdict aggregation work.

## Observations / Insights

F-M6.1I-003, F-M6.1I-004, F-M6.1I-005, F-M6.1I-006.

## Operator Trust Impact

This is the biggest M6.1 result and the reason adversarial framing
existed.

| Question | Answer |
|---|---|
| Did M6.1 close Part A's substantive question? | **YES** — perturbations + ablation ran, all under locked rules |
| Was a prior verdict potentially wrong? | **YES** — `SMC_GATES_DESTROYED_RAW_EDGE` is mechanically triggered, and the locked interpretation says "prior sweep-reclaim closure must be reconciled" |
| Was the wrong verdict caught? | **YES** — by the adversarial-framing milestone explicitly designed to test it |
| Should operator trust the new finding? | **Conditionally** — pending M7 methodology reconciliation, see F-M6.1I-001 caveats |
| Should the closed `SWEEP_RECLAIM` family be reopened immediately? | **NO** — first reconcile A.3 methodology vs prior SWEEP_RECLAIM. M7 milestone proposed |
| Was the prior `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` closure also possibly wrong? | **UNKNOWN** — that diagnostic measured 27 knowable states on a different framework. A.3's positive result does not directly invalidate it. Worth one more adversarial pass eventually |

**Net assessment:** the audit chain found one substantive prior-verdict
problem under adversarial test. This is exactly what the operator
requested when raising distrust. The system worked.

## M5 Resumption Question

The resumption gate for M5 was: "M6.1 must return a substantive Part A
verdict before M5 resumes."

M6.1 has returned a substantive Part A verdict: `SMC_GATES_DESTROYED_RAW_EDGE`.
The gate technically opens.

**However**, the substantive M6.1 finding redirects the most valuable
next research effort. M5 (trial-00095 LONG-only + uptrend gating) is
still a valid refinement, but it sits on top of a research foundation
that just got destabilized. Operator should decide:

- **Path A:** Resume M5 as-is. The validated trial-00095 edge is
  independently produced (Part B SL-subset reproduces) and M5 refines
  it. M7 reconciliation runs in parallel or after.
- **Path B:** Defer M5; run M7 (SWEEP_RECLAIM reconciliation) first.
  The new candidate primitive may be a stronger candidate than M5's
  refinement.
- **Path C:** Pause both M5 and M7; reconsider research priorities at
  blueprint level (the user-mentioned blueprint reverse-engineering
  exercise).

Auditor recommendation: **Path B** is highest expected value. M5
refines a known winner (low ceiling on incremental ER); M7 may unlock
a previously-closed family (high ceiling, higher risk). The
adversarial M6 was about restoring trust enough to choose the higher
ceiling work.

## Recommended Next Milestone

### M7 — SWEEP_RECLAIM_METHODOLOGY_RECONCILIATION_V1

**Goal:** Determine whether A.3's flip represents (a) a real reopening
of the closed SWEEP_RECLAIM family or (b) a methodology artifact
relative to prior `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1`.

**Scope (research-only, deterministic):**

1. Read and document M6 A.3 exact methodology:
   - Sweep definition (which SMC module function, parameters)
   - Direction logic (LONG sweep below → LONG entry; SHORT sweep above
     → SHORT entry)
   - Entry timing (first bar after sweep where close re-enters level)
   - Forward window (5-bar)
   - Cost (0.10% round-trip)

2. Read and document prior `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1`
   exact methodology from
   `research_lab/analysis_sweep_reclaim_event_taxonomy_diagnostic_v1.py`.

3. Build comparison table mapping each prior SWEEP_RECLAIM variant
   (confirmed pivots, wick cross, close BoS, immediate reclaim,
   delayed reclaim, true breakout/no-reclaim) to A.3's specific
   definition. Identify which prior variant is the closest analog.

4. Re-run the closest-analog prior variant on M6.1's exact cost +
   forward-window settings (single-run, no perturbations). Compare to
   A.3 numbers.

5. If A.3 metrics match the re-run analog → methodology equivalence
   confirmed → real reopening of SWEEP_RECLAIM family. Issue M8
   handoff for next-step setup-candidate research.

6. If A.3 metrics diverge from the re-run analog → methodology artifact
   → identify which specific definition difference produced the flip.
   Document and close M7.

7. Independent walk-forward on A.3 across 2-3 disjoint windows for
   stability check.

**Budget:** 12-20 hours implementation + 4-8 hours audit.

**Builder:** Codex. Adversarial framing inherited from M6.

### Optional M6.2 — Trail rule recovery

Still deferred per operator's M6.1-only decision. Independent value;
not blocking M7.

## Final M6 Reporting Cleanup (recommended, low priority)

The M6 markdown report shows
`M6 verdict: PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` as the headline,
which under-represents the actual substantive M6 result. Consider:

- Either patch the report markdown render to surface Part A finding
  first when Part A is non-robust.
- Or accept the current report and rely on operator reading the full
  table.

Non-blocking. Documentation cleanup only. Worth one line in M7 plan if
M7 happens.

## Verdict Summary

| | |
|---|---|
| M6.1 implementation | DONE |
| All locked rules honored | YES |
| Substantive Part A verdict produced | YES — `SMC_GATES_DESTROYED_RAW_EDGE` |
| Operator-facing final M6 label | Misleading due to priority logic, but full report is accurate |
| Research-meaningful outcome | YES — major finding |
| Trust restoration | Partial restoration via finding + audit-chain-validation; pending M7 reconciliation |
| Next milestone recommended | M7 SWEEP_RECLAIM_METHODOLOGY_RECONCILIATION_V1 |
| M5 status | Resumption gate technically opens, but operator should consider M7 priority |

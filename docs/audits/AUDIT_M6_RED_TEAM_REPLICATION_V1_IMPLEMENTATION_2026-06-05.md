# AUDIT: M6 RED_TEAM_REPLICATION_V1 — IMPLEMENTATION

Date: 2026-06-05
Auditor: Claude Code (adversarial framing)
Implementation commit: 23990e8
Branch: research/m6-red-team-replication
Plan: docs/research/RED_TEAM_REPLICATION_V1_PLAN.md (commit 0476435, audit-approved d8f1275)
Prior audits:
- docs/audits/AUDIT_M6_RED_TEAM_REPLICATION_V1_PLAN_2026-06-05.md (commit 11b2ae5)
- docs/audits/AUDIT_M6_RED_TEAM_REPLICATION_V1_PLAN_AMENDMENT_2026-06-05.md (commit d8f1275)
Builder: Codex
Type: Final M6 implementation audit (commit 2 of 2)

## Verdict

**`DONE_WITH_CRITICAL_CAVEAT`**

Implementation is **technically correct** per the locked plan rules and tests
pass. **But the Part A verdict `BASELINE_NOT_REPRODUCIBLE` is mechanically
fired by a broken SHA comparison (apples-vs-oranges), not by actual
non-reproduction.** Analytical content of A.1 is reproduced byte-for-byte
(1271 events, PF 1.061059, net median -0.000442, MFE ratio 2.352473 —
all identical to prior). Perturbations P1-P5 + A.3 were skipped due to
the hard-stop on a comparison that was never going to match.

**Part A's substantive question — "does SMC_SEQUENCE invalidation
survive adversarial perturbation?" — was NOT answered** because the
perturbations didn't run. The informal evidence (metrics-level
reproduction) suggests the prior verdict is analytically robust at
baseline, but perturbation evidence does not exist.

**Part B verdict `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` is correct
and important.** It confirms the F-M6P-001 plan-audit prediction:
trail rule is not derivable from frozen artifact, simulator partially
reproduces (SL subset Pearson 0.954, TP_TRAIL subset 0.612). The
stratification amendment **successfully prevented a false
`VALIDATED_EDGE_NOT_REPRODUCIBLE` alarm**. Production-pause did not
trigger.

This is the most epistemically honest M6 outcome possible: it surfaced
a real implementation-level methodology gap that nobody caught in
two prior audits.

## Standard Audit Axes

| Axis | Status |
|---|---|
| Layer Separation | PASS |
| Contract Compliance | PASS |
| Determinism | PASS (2-run SHA stable: `AAE5A20A...`) |
| Error Handling | PASS |
| Smoke Coverage | PASS (20/20 tests passed) |
| Tech Debt | LOW |
| AGENTS.md Compliance | PASS |

## Research Lab Audit Axes

| Axis | Status |
|---|---|
| Methodology Integrity | WARN (SHA methodology gap, see F-M6I-001) |
| Promotion Safety | PASS (no production change, no rescue) |
| Reproducibility & Lineage | WARN (SHA comparison broken) |
| Data Isolation | PASS |
| Search Space Governance | PASS |
| Artifact Consistency | PASS |
| Boundary Coupling | PASS |

## Quant Research Audit Axes

| Axis | Status |
|---|---|
| Methodology Rigor | PASS (deterministic, frozen verdict rules honored) |
| Source Coverage | PASS |
| Repo/Code Inspection | PASS (no copy of SMC module, only import + replace()) |
| Lookahead Risk | PASS |
| Novelty vs Rescue | PASS (no post-data interpretation rewrite) |
| Creativity vs Cherry-Picking | PASS |

## Compliance Verification

### Plan adherence (locked rules)

| Required | Status |
|---|---|
| Part A imports `analysis_smc_sequence_edge_feasibility_v1` as-is | PASS — line 19, no module modification |
| P1-P5 each mutate exactly one field | PASS — `replace(base_config, **overrides)` with single-key dicts in `PART_A_PERTURBATIONS` |
| `verify_single_parameter_isolation` mechanical check | PASS — line 72 |
| A.3 ablation in M6 orchestrator, not SMC module | PASS — `build_raw_sweep_reclaim_events` in M6 file, SMC module untouched |
| Pre-data interpretations embedded verbatim | PASS — `PRE_DATA_INTERPRETATIONS` dict matches plan §4 word-for-word |
| Part B simulator has NO imports from bot/strategy/attribution | PASS — verified import block (stdlib + sqlite3 + dataclasses + statistics only) |
| Part B trail reconnaissance step | PASS — classification `NOT_DERIVABLE_FROM_FROZEN_ARTIFACT` reported in JSON |
| Three Pearson values computed (full, SL, TP_TRAIL) | PASS — 0.785963 / 0.954062 / 0.611562 reported |
| Stratified verdict from §6 amended rules | PASS — `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` correctly returned |
| Database choice: canonical binds, snapshot comparison | PASS — `Canonical DB binds verdict: True` in report |
| METRIC_HYPERSENSITIVE diagnostic note | PASS — encoded in `evaluate_part_a` lines 296-298 |
| Determinism: 2 runs byte-identical | PASS — SHA `AAE5A20A...` on both runs |
| Staging only named M6 files | PASS — 8 files in commit, 5 pre-existing untracked NOT included |
| 14+ tests covering plan §7 | PASS — 20 tests total, 20 pass |

All locked rules honored. Codex did not soften, did not rescue, did
not interpret post-data.

### Anti-rescue verification

| Potential rescue | Observed |
|---|---|
| Verdict swap from PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL to something softer | NO |
| SHA comparison loosened after seeing mismatch | NO (hard-stop fired as written) |
| Aggregate metric failures (ER, WR outside bounds) re-interpreted to avoid VALIDATED_EDGE_NOT_REPRODUCIBLE | DEFENSIBLE — see F-M6I-002 |
| Snapshot DB substituted for canonical | NO |
| Perturbations forced to run despite stop rule | NO — `continue_after_baseline_mismatch` flag exists but defaults False and wasn't overridden |

## Findings

### F-M6I-001 — Part A SHA comparison is structurally broken (apples vs oranges)

Severity: **CRITICAL** | Confidence: 5/5

**The expected SHA `8CA802FD610DFE552225C9318A455345D8917D688ABBD2B3647CA69C4B6A78A4`
was computed in the prior 2026-05-27 commit on the RAW JSON file bytes**
(via `hashlib.sha256(json_path.read_bytes()).hexdigest().upper()`).
That payload included wall-clock `generated_at_utc`, machine-specific
`db_path`, and the full events list (~thousands of entries).

**The observed SHA `5A6B8505C1726EE1527FBF1131A75C4E053AF3E0188696F53FABA8E369B5482F`
was computed by M6 on a STABILIZED payload** where (see
`red_team_replication_v1.py:85-93`):

```python
manifest["generated_at_utc"] = "DETERMINISTIC_NO_WALL_CLOCK"
manifest["db_path"] = "<EXPLICIT_DB_PATH>"
stable["events"] = []
stable["events_truncated_for_m6_hash"] = True
```

**These two SHAs were computed over fundamentally different payloads and
cannot possibly match.** The comparison was guaranteed to fail before
the first run.

The mechanical verdict `BASELINE_NOT_REPRODUCIBLE` is therefore not
evidence of actual non-reproduction. It is evidence that the SHA
comparison methodology was never aligned between the prior commit and
this milestone.

**Analytical content IS reproduced exactly:**

| Field | Prior (2026-05-27) | M6 A.1 baseline |
|---|---:|---:|
| Event count | 1271 | 1271 ✅ |
| Net 5b PF | 1.061059 | 1.061059 ✅ |
| Net 5b median return | -0.000442 | -0.000442 ✅ |
| MFE before median | 0.011565 | 0.011565 ✅ |
| MFE after 5b median | 0.004916 | 0.004916 ✅ |
| MFE before/after ratio | 2.352473 | 2.352473 ✅ |

Every meaningful number matches to all reported decimal places. SMC
sequence diagnostic at baseline configuration is **analytically
reproducible**.

**Root cause analysis: where did this fall through?**

1. Plan §6 locked rule: *"If A.1 baseline SHA does not match
   `8CA802FD...`, return `BASELINE_NOT_REPRODUCIBLE` and stop."*
   Did not specify SHA computation methodology.
2. Plan audit (my first M6 audit) did not flag this. The methodology
   gap was invisible at planning time because both the original SHA
   and any future SHA were just "the SHA" — no one looked at how each
   was constructed.
3. Plan amendment (F-M6P-001 fix) did not address this either, because
   the trail-stratification finding dominated attention.
4. Implementation correctly chose to stabilize the new payload
   (good engineering against timestamp/path drift), but had no
   re-computed stabilized prior SHA to compare against. The
   implementation chose to compare new-stable against old-raw because
   the plan didn't tell it otherwise.

**This is the M3 silent-fallback failure mode at a different layer.**
M3: process failure (silent DB substitution). M6: process failure
(silent SHA methodology divergence). Same shape — both were lurking
assumptions that nobody validated until reality forced them open.

**Adversarial irony:** the milestone explicitly designed to challenge
prior audit chain reliability has itself revealed a new gap in the
audit chain. This is exactly what adversarial framing is for.

**Implication for Part A substantive question:**

Perturbations P1-P5 and ablation A.3 did not run (hard-stop honored
the locked rule). Therefore Part A did not produce evidence that:
- P1 (tighter sweep proximity) does/does-not flip the verdict
- P2 (looser sweep proximity) does/does-not flip
- P3 (faster mitigation entry) does/does-not flip
- P4 (lower displacement bar) does/does-not flip
- P5 (cost-blind) does/does-not flip → "edge is gross only" untested
- A.3 (raw sweep+reclaim) does/does-not flip → "SMC gates destroyed raw edge" untested

The substantive question of M6 Part A remains open.

**Informal evidence (not substitute for perturbation tests):**

Since the baseline metrics reproduce byte-perfectly, the SMC diagnostic
is at least running consistently with prior. This is necessary-but-not-
sufficient for prior verdict robustness. The perturbation tests are still
needed to verify robustness.

### F-M6I-002 — Part B aggregate metric divergences are consistent with trail incompleteness

Severity: MEDIUM | Confidence: 4/5

Part B reproduced count = 274 (matches), but:

| Metric | Baseline | M6 simulator | Delta | Bound | Inside? |
|---|---:|---:|---:|---|---|
| ER | 2.121 | 2.348 | +10.7% | ±5% (1.965-2.227) | **OUT** |
| PF | 4.216 | 4.101 | -2.7% | ±5% (4.005-4.427) | IN |
| WR | 56.57% | 48.91% | -7.66pp | ±3pp (53.5-59.5%) | **OUT** |

Per plan §6 amended rules, two paths exist:

> *"If SL-subset Pearson >= 0.95 and TP_TRAIL-subset Pearson < 0.95,
> Part B returns `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`."*

> *"If count, ER, PF, or WR fail acceptance while subset correlations
> pass, Part B returns `VALIDATED_EDGE_NOT_REPRODUCIBLE`."*

Codex applied the first rule because SL-subset Pearson 0.954 ≥ 0.95
AND TP_TRAIL-subset 0.612 < 0.95. The aggregate metric failures (ER
and WR outside bounds) were absorbed under "simulator incompleteness
causes aggregate drift."

**This interpretation is defensible** and internally consistent:

If the simulator cannot reproduce TP_TRAIL exits (155 of 274 trades
= 57%), it must be exiting those trades by some surrogate rule (e.g.,
hold-until-tp2-or-sl). Compared to original TP_TRAIL behavior:

- **More trades end at SL** → WR drops (observed: 48.9% vs 56.6%, -7.7pp)
- **Surviving winners run further without trail interruption** → average winning R
  is larger → ER rises (observed: 2.348 vs 2.121, +10.7%)
- **PF stays close** because gains-up + losses-up roughly offset
  (observed: 4.101 vs 4.216, -2.7%)

The pattern (lower WR, higher ER, similar PF) is the **expected
fingerprint of "simulator runs longer than original because it has no
trail logic"**. This is independent evidence that
`PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL` is the correct verdict, not
`VALIDATED_EDGE_NOT_REPRODUCIBLE`.

**Plan ambiguity (informational):**

The two amended rules above are not strictly disjoint. Codex chose the
narrower-cause interpretation (trail incompleteness explains everything
downstream). An alternative interpretation could have chosen
`VALIDATED_EDGE_NOT_REPRODUCIBLE` based on aggregate failures alone.

I confirm Codex's interpretation. Production-pause is not warranted on
this evidence. The aggregate divergence pattern is consistent with the
known simulator gap.

**For future plan amendments:** when stratified verdict rules can
overlap, declare a priority order (more specific cause wins over
aggregate cause). Codex applied implicit priority correctly here.

### F-M6I-003 — F-M6P-001 plan amendment was vindicated by reality

Severity: INSIGHT | Confidence: 5/5

The plan-amendment trail-stratification fix from
`AUDIT_M6_RED_TEAM_REPLICATION_V1_PLAN_2026-06-05.md` (F-M6P-001)
turned out to be **decisive in preventing a false alarm**.

Without the stratification:
- Pre-amendment rule: "If any Part B criterion fails, return `VALIDATED_EDGE_NOT_REPRODUCIBLE`"
- Observed: full Pearson 0.786, ER outside ±5%, WR outside ±3pp
- Verdict would have been: **`VALIDATED_EDGE_NOT_REPRODUCIBLE`**
- Plan §6 final verdict rule then: **"critical, all production decisions paused pending root cause"**
- Production-pause would have triggered on a simulator-incompleteness signal

With the stratification (post-amendment):
- SL Pearson 0.954 ≥ 0.95 ✅
- TP_TRAIL Pearson 0.612 < 0.95 ❌
- Verdict: `PARTB_SIMULATOR_INSUFFICIENT_FOR_TRAIL`
- No production-pause. Trail logic recovery becomes a documented action item.

**The audit chain caught a false alarm before it fired**. This is the
intended function of adversarial framing.

The trail recovery action item is now real and concrete:
- 155 of 274 trades exit via `TP_TRAIL`
- Frozen artifact (`trial_00095_intrabar_frozen_entries.json`) exposes
  entry/SL/tp1/tp2/baseline_pnl_r but no trail rule fields
- Recovery requires inspecting strategy source (likely
  `core/signal_engine.py` trailing-stop logic)
- Separate milestone if operator wants full Part B reproduction

### F-M6I-004 — Test discipline and reuse-not-rewrite are properly executed

Severity: INSIGHT | Confidence: 5/5

- 20 tests pass (16 plan-mandated + 4 supporting). No skipped, no xfailed.
- Compileall passes for both M6 modules.
- Part A uses `from research_lab import analysis_smc_sequence_edge_feasibility_v1 as smc` plus `dataclasses.replace()` only. No copy of SMC detection logic.
- Part B imports stdlib only + `statistics`. Verified no bot/strategy/attribution imports.
- 8 named M6 files staged, 5 pre-existing untracked PC files correctly NOT included.

### F-M6I-005 — Pre-data interpretations encoded in code, locked

Severity: INSIGHT | Confidence: 5/5

`red_team_replication_v1.py:39-46` contains `PRE_DATA_INTERPRETATIONS`
dict with all 6 sentences (P1-P5 + A.3) verbatim from plan §4 lines
164-169.

Since perturbations didn't run, these interpretations were not invoked
on actual results. But the encoding-in-code lock ensures that any
future re-run on this commit (or any commit derived from it) would
apply the same locked interpretations. Pre-data discipline preserved
through code, not just markdown.

## Critical Issues

F-M6I-001 — SHA comparison structurally broken. Hard-stop fired on a
guaranteed-mismatch, not on actual non-reproduction. Part A
substantive question unanswered.

## Warnings

None beyond F-M6I-001 itself.

## Observations

F-M6I-002 — Part B aggregate divergences are interpretable as trail
incompleteness, not edge falsification.

## Insights (positive)

F-M6I-003 — F-M6P-001 amendment vindicated, false alarm prevented.
F-M6I-004 — Test discipline + reuse-not-rewrite properly executed.
F-M6I-005 — Pre-data interpretations encoded in code, locked.

## Operator Trust Impact

**Operator's original concern was that the audit chain might be
producing false verdicts.**

M6 results bear on that concern with mixed evidence:

| Question | Answer from M6 |
|---|---|
| Is SMC_SEQUENCE invalidation analytically reproducible? | **YES** — every metric matches byte-perfectly |
| Does SMC_SEQUENCE invalidation survive perturbation? | **UNKNOWN** — perturbations didn't run due to SHA stop |
| Is the validated trial-00095 edge SL-subset independently reproducible? | **YES** — SL Pearson 0.954 |
| Is the validated trial-00095 edge TP_TRAIL-subset independently reproducible? | **NO** — trail logic not in frozen artifacts |
| Did the audit chain catch a real false-alarm path? | **YES** — F-M6P-001 amendment prevented production-pause |
| Did the audit chain miss a methodology gap? | **YES** — SHA comparison was broken end-to-end across plan, amendment, implementation |

**Net assessment:** trust in audit chain should be **partially
restored** (false-alarm catch is a strong signal) but **further
calibrated** (SHA gap is a new failure mode worth one more follow-up).

This is honest. The chain is not perfect. The adversarial milestone
caught one false alarm before it fired and surfaced one new gap that
nobody saw in two prior plan/amendment audits. Both findings have
direct value.

## Recommended Next Steps

Two parallel follow-ups, neither urgent, both small.

### Path A — Complete Part A perturbation evidence (M6.1, 4-8h)

**Goal:** Actually answer M6's substantive question by running the
perturbations under a corrected SHA protocol.

Implementation:

1. Drop `EXPECTED_SMC_SHA` constant (or replace with a `None` sentinel
   meaning "no comparable prior SHA available; baseline check uses
   analytical-content match instead").
2. Add `analytical_content_baseline` dict to expected: `{event_count: 1271, net_5b_pf: 1.061059, net_5b_median: -0.000442, mfe_ratio: 2.352473}` with float tolerance (e.g., abs delta < 1e-6).
3. Replace SHA-hard-stop with "analytical-content-hard-stop": baseline
   passes if all four numbers match within tolerance.
4. Re-run M6 — A.1 will now pass (numbers match), perturbations P1-P5
   + A.3 will execute.
5. Apply existing locked verdict rules to perturbation results.
6. Final verdict per plan §6 (SMC_SEQUENCE_INVALIDATION_ROBUST /
   SMC_SEQUENCE_VERDICT_NOT_ROBUST / SMC_SEQUENCE_EDGE_IS_GROSS_ONLY /
   SMC_GATES_DESTROYED_RAW_EDGE).

This is NOT a softening of the locked verdict rules. The amended
baseline check is methodologically stricter than the prior SHA check
because it tests every analytical quantity individually, not just an
opaque hash. The hash check was meaningful only if same methodology
applied on both sides; since that condition can never be retroactively
satisfied for the 2026-05-27 prior commit, analytical comparison is
the correct path forward.

### Path B — Trail rule recovery for full Part B reproduction (M6.2, 4-6h)

**Goal:** Recover trailing-stop logic from strategy source so simulator
can reproduce 155 TP_TRAIL trades.

Implementation:

1. Read `core/signal_engine.py` (or equivalent) trailing-stop code path.
2. Document the exact trail rule (activation level, trail distance,
   trail-step, partial-fill behavior).
3. Add trail rule to the Part B simulator.
4. Re-run Part B. Verify TP_TRAIL Pearson rises to ≥ 0.95.
5. Final Part B verdict per plan §6 (REPLICATION_VERIFIES_PRIOR_VERDICTS
   or VALIDATED_EDGE_NOT_REPRODUCIBLE).

If trail rule is recovered AND TP_TRAIL Pearson reaches 0.95, the
validated trial-00095 edge is fully independently reproducible. This
would be the strongest possible evidence that the production edge is real.

If trail rule is recovered AND TP_TRAIL Pearson still fails 0.95,
that IS evidence the edge depends on something not derivable from
explicit code, which is a genuine production-relevant finding.

### Operator Decision

- **Approve M6.1 only** — fixes Part A, leaves Part B as informative
  (SL-subset reproduces, trail logic is acknowledged debt).
- **Approve M6.1 + M6.2** — complete both. Recommended for full M6
  closure.
- **Approve neither, accept M6 as-is** — Part A baseline reproduces
  metrics-wise, Part B SL-subset reproduces, sufficient evidence to
  partially restore trust in audit chain. Documented gaps remain as
  technical debt.
- **Pause research lab pending broader review** — operator's
  prerogative if M6 evidence still doesn't restore enough trust.

This auditor recommends M6.1. M6.2 is optional but high-value.

## Conditions for M6 Closure

For M6 to be closed as a milestone (independent of follow-up choice):

- ✅ Implementation correct per plan rules
- ✅ Tests pass
- ✅ Deterministic outputs
- ✅ No production code touched
- ✅ Anti-rescue discipline held
- ⚠️ Part A substantive question unanswered — explicitly documented
- ⚠️ Part B simulator-incomplete on trail — explicitly documented

Milestone state in `docs/MILESTONE_TRACKER.md` should be updated to
reflect this nuance: **M6 DONE WITH CAVEATS**, two follow-ups proposed
to operator.

## Handoff

No new builder handoff at this audit checkpoint. Operator decides on
M6.1 / M6.2 / accept-as-is. If a follow-up is approved, handoff issued
at that point.

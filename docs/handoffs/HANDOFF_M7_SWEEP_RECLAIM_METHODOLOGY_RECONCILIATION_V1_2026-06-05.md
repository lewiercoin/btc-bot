# HANDOFF: M7 SWEEP_RECLAIM_METHODOLOGY_RECONCILIATION_V1

Date: 2026-06-05
From: Claude Code (auditor)
To: Codex (builder)
Branch base: `deploy/multi-asset-paper-v1` @ `683d0ca`
Builder commit branch: `research/m7-sweep-reclaim-methodology-reconciliation` (Codex creates if absent)

---

## CLAUDE HANDOFF -> CODEX

### Why this milestone exists

M6.1 produced a major substantive finding (audit
`docs/audits/AUDIT_M6.1_PART_A_SHA_FIX_2026-06-05.md` §F-M6.1I-001):
A.3 raw sweep+reclaim ablation flipped the verdict by wide margin
(PF 2.847, net 5b median +0.001811, MFE before/after ratio 0.385,
14,236 events). The locked pre-data interpretation triggered:
*"the SMC gates destroyed a simpler raw edge and prior sweep-reclaim
closure must be reconciled."*

Prior `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1` (2026-05-27, audit
`docs/audits/AUDIT_SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27.md`,
verdict "HYPOTHESIS INVALIDATED") closed the sweep+reclaim setup
family. If A.3 represents a real edge inside that family, the prior
closure was wrong. If A.3 represents a primitive prior didn't test,
the prior closure was narrow but not wrong. If A.3 is a methodology
artifact, prior closure stands.

**M7 is the reconciliation milestone. It is not edge discovery and it
is not prior-closure-rescue. It is independent methodology audit of
both M6.1 A.3 and prior SWEEP_RECLAIM_EVENT_TAXONOMY against the same
canonical data under the same cost/forward settings.**

### Operator-locked constraints (cannot be softened or relaxed)

These four constraints come from the operator's M7 approval message
(2026-06-05). They override any builder convenience choice.

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
   prior `SWEEP_RECLAIM_EVENT_TAXONOMY` closure is valid as scoped
   and ask "did A.3 test what prior tested?" — not "was prior wrong?"

3. **Methodology first, edge second.** Phase 1 (methodology mapping)
   must commit + audit before any Phase 2 empirical reconciliation
   run. No empirical re-run before the methodology axes are formally
   classified.

4. **Edge verdict is conditional on methodology classification.** M7's
   final verdict is mechanically derived from Phase 1 classification
   + Phase 2 empirical reconciliation + Phase 3 stability. No
   post-data verdict invention.

### Checkpoint

- Last shared commit: `683d0ca` (`research: reclaim_rejection diagnostic V1 re-run on canonical DB`)
- Current M6.1 commit: `2375b39` on `research/m6-red-team-replication`
- Branch base for M7: `deploy/multi-asset-paper-v1` @ `683d0ca`
- New branch: `research/m7-sweep-reclaim-methodology-reconciliation`
- Working tree: should be clean apart from the 5 pre-existing untracked
  files. Leave them alone as before.

### Before you code

Read (mandatory):

1. `docs/audits/AUDIT_M6.1_PART_A_SHA_FIX_2026-06-05.md` — full
   substantive finding context.
2. `research_lab/diagnostics/red_team_replication_v1.py` lines 176-294
   (`build_raw_sweep_reclaim_events`, `run_raw_sweep_reclaim_ablation`)
   — the exact A.3 implementation.
3. `research_lab/analysis_smc_sequence_edge_feasibility_v1.py` lines
   356-420 (`detect_sweep_events`, sweep definition used by A.3).
4. `research_lab/analysis_sweep_reclaim_event_taxonomy_diagnostic_v1.py`
   in full — the prior SWEEP_RECLAIM taxonomy.
5. `docs/research/SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_PLAN.md`
   — prior plan including which variants were tested.
6. `docs/audits/AUDIT_SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27.md`
   — prior closure audit.
7. `docs/analysis/SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27.md`
   — prior analytical output for reference numbers.

### Commit split (mandatory, do not collapse)

1. **Commit 1 — Phase 1 plan + methodology mapping document.**
   Single file:
   `docs/research/SWEEP_RECLAIM_METHODOLOGY_RECONCILIATION_V1_PLAN.md`.
   Must contain:
   - Plan scope guards (research-only, no production, etc.)
   - Operator-locked constraints from above (verbatim)
   - Phase 1 methodology mapping table (five axes filled in for both
     A.3 and each prior taxonomy variant)
   - Phase 2 reconciliation specification (which prior variants get
     re-run under M6.1 settings, in what order, with what reporting)
   - Phase 3 stability check specification (walk-forward windows
     declared)
   - Pre-data verdict label conditions (four verdicts, each with
     specific triggering rules)
   - Test plan
   - Acceptance criteria for diagnostic completion
   - Risk register
   - Open questions for operator (if any)

   STATUS: `PLAN_READY_FOR_CLAUDE_AUDIT`. No code, no tests, no
   artifacts. STOP after this commit and wait for Claude plan audit.

2. **Commit 2 — Implementation (Phases 2 + 3 + report).** After plan
   approval. Single commit. STATUS: `READY_FOR_CLAUDE_AUDIT`. No
   self-audit.

### Phase 1 specification — Methodology Mapping

The Phase 1 deliverable in commit 1 is a markdown table classifying
A.3 against each prior SWEEP_RECLAIM taxonomy variant on five axes.

#### Axes

| Axis | What it measures |
|---|---|
| Sweep detection | Which sweep events qualify (equal-level cluster sweeps? specific level types? proximity rules? depth rules? age rules?) |
| Direction logic | How is trade direction inferred from sweep? LONG on sweep-below + reclaim-above? SHORT on sweep-above + reclaim-below? Other? |
| Entry timing | When exactly does entry occur after sweep? First close re-enters level? First close beyond level? Some other condition? |
| Forward window | What time horizon is used for return measurement? 5-bar? Multi-window? Fixed-exit? |
| Cost model | What round-trip cost is applied? 10 bps? Other? |

#### Classification labels per axis

For each axis, classify A.3 vs each prior variant as one of:

| Label | Meaning |
|---|---|
| `EQUIVALENT` | Same definition on this axis |
| `A3_NARROWER` | A.3 is a subset of prior's definition on this axis |
| `A3_WIDER` | A.3 is a superset of prior's definition on this axis |
| `DISJOINT` | A.3 tests a definition prior did not include |
| `INCOMPARABLE` | Definitions cannot be aligned (e.g., different conceptual primitive) |

#### Required mapping table

| Prior variant | Sweep detection | Direction logic | Entry timing | Forward window | Cost model |
|---|---|---|---|---|---|
| `confirmed_pivot` | ? | ? | ? | ? | ? |
| `wick_cross` | ? | ? | ? | ? | ? |
| `close_bos` | ? | ? | ? | ? | ? |
| `immediate_reclaim` | ? | ? | ? | ? | ? |
| `delayed_reclaim` | ? | ? | ? | ? | ? |
| `true_breakout_no_reclaim` | ? | ? | ? | ? | ? |

Each cell must be one of the five labels. The plan markdown must
include the actual extracted definition from the prior code + the
A.3 definition for each axis as supporting evidence.

If any prior variant is `EQUIVALENT` on all five axes, that variant
is the "direct analog" candidate for Phase 2 re-run.

If no variant is `EQUIVALENT` on all five axes but at least one is
`EQUIVALENT` or `A3_NARROWER` on the core axes (sweep + entry +
direction) with cost/window as `EQUIVALENT`, that variant is a "near
analog" candidate.

If A.3 is `DISJOINT` on at least one core axis vs all prior variants,
A.3 represents a primitive prior did not test.

### Phase 2 specification — Empirical Reconciliation

In commit 2 (after plan approval):

1. For each "direct analog" or "near analog" identified in Phase 1,
   write a reconciliation runner that re-executes that prior variant's
   exact logic against the canonical DB under M6.1's cost (0.0010) +
   forward windows (3, 5, 10, 20) — using prior implementation code
   imported as-is, only adjusting cost/window parameters via its
   public config.

2. Run each analog and record:
   - event_count
   - net_5b_pf
   - net_5b_median
   - mfe_before_entry_median (if prior reports it)
   - mfe_after_entry_5b_median
   - mfe_before_after_ratio

3. Build comparison table:

   | Variant | Source | event_count | net_5b_pf | net_5b_median | MFE_before | MFE_after | MFE ratio |
   |---|---|---:|---:|---:|---:|---:|---:|
   | A.3 raw_sweep_reclaim | M6.1 (locked) | 14236 | 2.847 | +0.001811 | ? | ? | 0.385 |
   | prior_original | 2026-05-27 (locked) | ? | ? | ? | ? | ? | ? |
   | prior_rerun_m6.1_settings | M7 (new) | ? | ? | ? | ? | ? | ? |

4. **Do not interpret the empirical results yet.** Phase 2 produces
   the comparison table only. Verdict computation is mechanical from
   Phase 1 + Phase 2 + Phase 3 outputs together.

### Phase 3 specification — Stability check on A.3

In commit 2:

1. Split the canonical DB study window
   (`2022-01-01..2026-03-01`) into three disjoint sub-windows. Suggest:
   - Sub-1: 2022-01-01 to 2023-04-30 (~16 months)
   - Sub-2: 2023-05-01 to 2024-08-31 (~16 months)
   - Sub-3: 2024-09-01 to 2026-03-01 (~18 months)

2. Re-run M6.1 A.3 on each sub-window with all other parameters
   identical to M6.1.

3. Record per-sub-window: event_count, net_5b_pf, net_5b_median,
   MFE before/after, ratio.

4. **Stability passes** if all three sub-windows produce:
   - net_5b_pf ≥ 1.5
   - net_5b_median ≥ 0
   - mfe_before_after_ratio ≤ 1.0

   (i.e., A.3's flip-criteria gate holds in each sub-window
   independently)

5. **Stability fails** if any sub-window misses any of the three
   thresholds.

### Pre-data verdict rules (frozen, cannot be softened post-data)

| Verdict | Triggered when |
|---|---|
| `METHODOLOGY_ARTIFACT_PRIOR_CLOSURE_STANDS` | Phase 1: at least one axis where A.3 differs from prior in a way that conceptually explains a metric-level gap (e.g., A.3 sweep detection is much wider than prior, capturing low-quality sweeps prior intentionally excluded). Phase 2: prior_rerun_m6.1_settings reproduces prior_original invalidation. Phase 3: A.3 stability check may pass or fail; outcome is "A.3 tests a different conceptual primitive than prior" — prior closure stands as scoped. |
| `METHODOLOGY_GAP_PRIOR_CLOSURE_INCOMPLETE` | Phase 1: at least one axis classified as `DISJOINT` (prior did not include the A.3 case) OR `A3_WIDER` (A.3 is a superset that may admit cases prior excluded). Phase 2: prior_rerun_m6.1_settings stays invalidated (prior closure was correct on what it tested). Phase 3: A.3 stability passes on at least 2 of 3 sub-windows. Prior closure was narrow, not wrong; A.3 is a new candidate primitive. |
| `METHODOLOGY_EQUIVALENT_PRIOR_CLOSURE_WAS_WRONG` | Phase 1: at least one prior variant is `EQUIVALENT` on all five axes (the "direct analog"). Phase 2: that direct-analog prior variant, when rerun under M6.1 settings, produces A.3-compatible metrics (PF and median in same direction, ratio under 1.0). Phase 3: A.3 stability passes on all 3 sub-windows. The prior closure must be REOPENED. |
| `RECONCILIATION_INCONCLUSIVE` | Phase 1 cannot proceed (missing prior code/artifacts), or Phase 2 reruns crash on data incompatibility, or Phase 3 cannot run due to sample-size issues in sub-windows. Diagnostic limitation, not a finding. |

If A.3 stability check (Phase 3) FAILS but Phase 1 + Phase 2 would
otherwise support `METHODOLOGY_EQUIVALENT_PRIOR_CLOSURE_WAS_WRONG`,
final verdict downgrades to `METHODOLOGY_GAP_PRIOR_CLOSURE_INCOMPLETE`
with explicit note that A.3 is unstable across sub-periods.

### Forbidden Patterns

- Do not change M6.1 A.3 numbers. Operator-locked.
- Do not modify the SMC sequence module or M6 modules.
- Do not modify prior `SWEEP_RECLAIM_EVENT_TAXONOMY` module. Imported
  as-is for Phase 2 reruns.
- Do not introduce new sweep definitions, new entry timings, or new
  forward windows beyond Phase 1's mapped variants.
- Do not interpret Phase 1 results before they're tabled.
- Do not interpret Phase 2 results before all reruns complete and
  Phase 3 stability is computed.
- Do not modify `core/`, `bot/`, `execution/`, settings, schema, or
  dependency manifests.
- Do not stage the 5 pre-existing untracked PC files into M7 commits.
- Do not use `git add .` or `git add -A`.

### Deliverables

**Commit 1 (plan + Phase 1 methodology mapping):**

- `docs/research/SWEEP_RECLAIM_METHODOLOGY_RECONCILIATION_V1_PLAN.md`
  containing all sections specified above.
- STATUS=`PLAN_READY_FOR_CLAUDE_AUDIT`

**Commit 2 (implementation):**

- `research_lab/diagnostics/sweep_reclaim_methodology_reconciliation_v1.py`
  — Phase 2 reconciliation runner + Phase 3 stability checker + final
  verdict computation.
- `tests/test_research_lab/test_sweep_reclaim_methodology_reconciliation_v1.py`
  — unit tests for axis classification, reconciliation comparison,
  sub-window splitting, mechanical verdict computation.
- `research_lab/reports/sweep_reclaim_methodology_reconciliation_v1.json`
  — deterministic JSON with comparison table + stability table + final
  verdict.
- `research_lab/reports/sweep_reclaim_methodology_reconciliation_v1.sha256`
- `research_lab/reports/sweep_reclaim_methodology_reconciliation_v1.md`
  — markdown report with verdict + reasoning summary.

- STATUS=`READY_FOR_CLAUDE_AUDIT`

### Database

Canonical DB only: `F:\crowded_unwind_backtest.db` on PC pendrive.
Same hard-fail guard as M3/M6/M6.1. No `--allow-fallback`.

Pre-flight sanity (same as M6.1):
- `aggtrade_buckets` non-null cvd: 3,122,272
- BTCUSDT 15m candles in inclusive ISO window: 145,921

### Your first response must contain

1. Confirmed milestone scope (Phase 1 commit 1, Phase 2 + 3 commit 2).
2. Acceptance criteria you propose (may extend, cannot weaken).
3. Confirmation that M6.1 A.3 numbers will be treated as locked,
   never recomputed, never replaced in M7 outputs.
4. Confirmation that prior `SWEEP_RECLAIM_EVENT_TAXONOMY` module
   will be imported as-is for Phase 2 reruns (only cost + window
   parameters may differ).
5. Pre-Phase-1 reading list: which files you will inspect to build
   the axis-classification table, in order.
6. Plan implementation outline (ordered steps for commit 1).
7. Only then: start drafting the plan document.

### Commit discipline

- Single plan file in commit 1.
- After Claude plan audit, single implementation commit.
- WHAT/WHY/STATUS in commit messages.
- Do not self-mark as "done". Claude audits after push.
- Stage explicitly. Do not sweep up pre-existing untracked files.

### Time budget

- Phase 1 plan + mapping draft: 3-5 hours
- Plan audit: 1-2 hours
- Phase 2 implementation (reconciliation runners): 4-6 hours
- Phase 3 implementation (sub-window stability): 2-3 hours
- Tests + reports: 2-3 hours
- Implementation audit: 4-8 hours

Total: 16-27 hours from start to verdict.

### Notes on auditor framing

Adversarial framing inherited from M6. For M7 specifically:

- Default position: M6.1 A.3 finding is real until reconciliation
  proves otherwise.
- Auditor will hunt for: hidden methodology equivalence that Codex
  missed (could turn `METHODOLOGY_ARTIFACT` into `METHODOLOGY_EQUIVALENT`);
  hidden methodology disjointness that Codex missed (vice versa);
  rescue patterns trying to soften the A.3 finding to fit prior
  closure; rescue patterns trying to harden prior closure beyond
  what its original scope justified.
- Phase 1 axis-classification table will be the highest-scrutiny
  document. Get it right.

---

## End of handoff.

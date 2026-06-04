# AUDIT: M5 TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1 — PLAN

Date: 2026-06-04
Auditor: Claude Code
Commit: db03609e8b433fbf77f642f5a578c9cb76cb7409
Branch: research/m5-trial-00095-direction-regime
Plan file: docs/research/TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1_PLAN.md
Builder: Codex
Type: Plan-only commit audit (commit 1 of 2)

## Verdict

**`APPROVE_PLANNING_DOCUMENT`** — proceed to commit 2 implementation.

No critical or high findings. Five small observations recorded for
implementation-commit audit awareness; none block proceeding.

## Standard Audit Axes

| Axis | Status |
|---|---|
| Layer Separation | PASS |
| Contract Compliance | PASS |
| Determinism | PASS |
| State Integrity | N/A (plan only) |
| Error Handling | PASS |
| Smoke Coverage | PASS (8 named unit tests + 3 validation commands) |
| Tech Debt | LOW |
| AGENTS.md Compliance | PASS |

## Research Lab Audit Axes

| Axis | Status |
|---|---|
| Methodology Integrity | PASS |
| Promotion Safety | PASS |
| Reproducibility & Lineage | PASS |
| Data Isolation | PASS |
| Search Space Governance | PASS |
| Artifact Consistency | PASS |
| Boundary Coupling | PASS |

## Quant Research Audit Axes

| Axis | Status |
|---|---|
| Methodology Rigor | PASS |
| Source Coverage | PASS |
| Repo/Code Inspection | PASS |
| Timing Discipline | PASS |
| Entry Realism | PASS |
| Lookahead Risk | PASS |
| Edge Accessibility | N/A (M5 does not change entry timing) |
| Novelty vs Rescue | PASS |
| Exploration Suppression | N/A |
| Creativity vs Cherry-Picking | PASS |

## Compliance Verification

### Handoff fidelity

| Handoff requirement | Plan section | Status |
|---|---|---|
| A1/A2/A3 cohort definitions frozen | §1, §4 | PASS — verbatim |
| 3-fold walk-forward identical to attribution | §5 | PASS — verbatim windows + baseline numbers |
| G-1: A3 ER ≥ baseline ER + 0.5R (≥ 2.621) | §7 | PASS |
| G-2: A3 PF ≥ baseline PF × 1.10 (≥ 4.638) | §7 | PASS |
| G-3: A3 ER > 0 in all 3 folds | §7 | PASS |
| G-4: per-fold A3 ER ≥ 50% full-sample A3 ER | §7 | PASS |
| G-5: max drawdown R reported informational | §7 | PASS |
| Verdict computed mechanically, not by builder | §7 lines 286-298 | PASS |
| Reuse existing regime classifier, do not reimplement | §3 lines 123-126, §4 lines 179-181, Risk 3 | PASS |
| Reuse `fold_bucket()` | §3, §5, Risk 4, test 3 | PASS |
| Reuse `summarize_metrics()` for ER/PF/WR/median R/total R/max DD | §3, test 4 | PASS |
| Forbidden: threshold change | §1, §7, §9, Risk 7 | PASS |
| Forbidden: new entry generation | §1, §9, Risk 7 | PASS |
| Forbidden: post-data filter additions (TFI, exit) | Risk 8, §11 NOTE 3 | PASS |
| Forbidden: production module modification | §1 lines 35-45, §9 | PASS |
| Plan-only commit (no code/tests/artifacts) | commit stat: 1 file 402 lines, plan only | PASS |
| STATUS=PLAN_READY_FOR_CLAUDE_AUDIT | commit msg + plan header | PASS |
| Single plan file in commit 1 | git show db03609 --stat: 1 file | PASS |

### Primitive existence verification

Verified against
`research_lab/diagnostics/trial_00095_conditional_edge_attribution_v1.py`
@ `683d0ca` on `deploy/multi-asset-paper-v1`:

| Primitive | Plan reference | Verified |
|---|---|---|
| `DiagnosticConfig` dataclass | §3 | PASS (line 72-93 in attribution) |
| `AttributedTrade.direction: str` | §4 cohort A1 filter | PASS (line 115) |
| `AttributedTrade.regime: str` | §4 cohort A2 filter | PASS (line 116) |
| `AttributedTrade.pnl_r: float` | §6 metric input | PASS (line 117) |
| `AttributedTrade.fold: str` | §5 grouping | PASS (line 125) |
| `fold_bucket(ts) -> str` | §3, §5, test 3 | PASS (line 955-959; returns exact strings `fold_1_2022_2023H1`, `fold_2_2023H2_2024`, `fold_3_2025_2026Q1`) |
| `summarize_metrics(trades) -> dict` | §3, test 4 | PASS (line 371) |
| `max_drawdown(pnls) -> float` | §3, §5 | PASS (line 905) |
| `load_trade_records()` | §3 | PASS (line 149) |
| `load_frozen_entries()` | §3 | PASS (line 171) |
| `merge_entries()` | §3 | PASS (line 194) |
| `attribute_trades()` | §3 | PASS (line 302) |
| `DEPTH_THRESHOLD = 0.00649` | §3 | PASS (verified in attribution constants) |

All primitives the plan promises to reuse exist as public functions /
dataclass fields. No silent rewrite risk.

### Naming reconciliation

Handoff used `regime_at_open` informally; plan correctly uses `trade.regime`
to match the actual field on `AttributedTrade`. This is correct — plan
must align to source code, not to the handoff's loose naming. No
behavioral drift.

## Findings

### F-M5P-001 — Anti-rescue clause on A3-to-A1/A2 verdict swap

Severity: INSIGHT | Confidence: 5/5

Plan §11 NOTE 2: *"If A3 fails but A1 or A2 individually looks strong,
that is evidence for a future plan only; M5 must not rescue itself by
switching final gates from A3 to A1 or A2 after results."*

This is the most subtle rescue pattern available to a builder facing a
borderline result. Codex pre-emptively forbade it in the plan, before
any data look. Strong methodology discipline. This is exactly the kind
of pre-data anti-rescue commitment that the quant research operating
model rewards.

### F-M5P-002 — Hard INCONCLUSIVE_DATA_GAP gate on missing fold

Severity: INSIGHT | Confidence: 5/5

Plan §7 line 282: *"Any missing fold must produce
`INCONCLUSIVE_DATA_GAP`, not a pass."*

Prevents the silent-pass failure mode where a thin fold (e.g.,
`fold_3_2025_2026Q1` with baseline N=41) might be ignored if it
contains zero A3 events. Codex correctly hard-coded this guard.

### F-M5P-003 — Reuse-not-rewrite directive is explicit and enforceable

Severity: INSIGHT | Confidence: 5/5

Plan §3 lines 123-126: *"The future diagnostic must import and reuse
these primitives. It must not copy or re-implement the regime
classification surface or the fold assignment helper. If a helper needs
a new public wrapper for clarity, that wrapper must delegate to the
imported helper without changing semantics."*

This is the right pattern. Combined with Risk 3 ("Uptrend regime
definition drifts from attribution diagnostic"), implementation-commit
audit will be able to verify reuse fidelity by reading the import
statements alone. No silent re-implementation can slip through.

### F-M5P-004 — Fold-3 sample size risk acknowledged but underspecified

Severity: OBSERVATION | Confidence: 4/5

Fold 3 baseline N=41. A3 = LONG ∩ uptrend, expected to retain roughly
75% (uptrend share) × 92% (LONG share) ≈ 69% of trades. Projected A3
fold-3 N ≈ 28-30 trades.

G-4 ("no per-fold A3 ER more than 50% below A3 full-sample ER") on ~30
trades is statistically tight. Reasonable variance on a sample that
small can flip the gate.

Plan acknowledges via Risk 5 ("Sample collapse in A3"). Mitigation
correctly defaults to `INCONCLUSIVE_DATA_GAP` rather than auto-pass or
auto-fail. This is the right discipline.

Action for implementation audit: verify that the implementation produces
an explicit per-fold A3 count in the report, so a thin-fold result is
visible immediately rather than hidden behind aggregate ER.

Not blocking for plan approval.

### F-M5P-005 — H3 expectation "ER_A3 ≥ 2.6" is approximate, not derivable

Severity: OBSERVATION | Confidence: 3/5

H3 expects `ER_A3 ≥ 2.6`. Attribution report does not publish the
LONG ∩ uptrend cell directly — only LONG-only (2.377) and uptrend-only
(2.614). The 2.6 expectation in H3 assumes the intersection lifts above
the LONG-only number but does not strictly exceed the uptrend-only
number.

H3 is an explanatory hypothesis, not a gate. Verdict gates G-1 through
G-4 are independent of H3's specific number. So this is methodologically
safe.

Action for implementation audit: when A3 metrics are computed for the
first time, the actual A3 ER number will be a new datum. Report should
present it without retroactively claiming H3 was met or missed — H3 is
expected-direction, not a threshold.

Not blocking.

### F-M5P-006 — Reset memo is on Claude audit branch only

Severity: OBSERVATION | Confidence: 3/5

Plan §3 line 133-135 cites
`docs/research/RESEARCH_LANDSCAPE_RESET_2026-06-04.md` as evidence,
correctly noting it lives "from the Claude audit branch." That file is
on `claude/festive-maxwell-iciBo`, not yet merged into
`deploy/multi-asset-paper-v1`.

Codex correctly handled the cross-branch reference. No action required;
just worth noting that the reset memo will need to be cherry-picked or
merged into `deploy/multi-asset-paper-v1` at some point so that the
implementation commit's lineage citations resolve on the same branch.

Not blocking for plan approval. Operator can decide merge timing later.

## Critical Issues

None.

## Warnings

None.

## Observations

See F-M5P-001 through F-M5P-006.

## Recommended Next Step

**Codex proceeds to commit 2 (implementation + tests + run + artifacts).**

Single commit. STATUS=`READY_FOR_CLAUDE_AUDIT`. No self-audit. Reuse
imports as specified in plan §3.

Implementation-commit audit will verify:
1. Import statements actually import the named primitives without
   reimplementation.
2. Per-fold A3 counts are visible in the report.
3. Verdict is computed mechanically from G-1..G-4 and INCONCLUSIVE_DATA_GAP
   data-surface checks, with no builder opinion.
4. JSON SHA256 is deterministic across two runs.
5. All 8 named unit tests pass.
6. No production module touched (git diff sanity check).
7. A1, A2, A3 metric tables match handoff math when applied to the same
   274-trade frozen artifact.

## Handoff Continuation

No new handoff document required — the existing
`docs/handoffs/HANDOFF_M5_TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1_2026-06-04.md`
on `claude/festive-maxwell-iciBo` covers commit 2 deliverables and
forbidden patterns. Codex proceeds directly to implementation.

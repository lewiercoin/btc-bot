# HANDOFF: M5 TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1

Date: 2026-06-04
From: Claude Code (auditor)
To: Codex (builder)
Branch base: `deploy/multi-asset-paper-v1` @ `683d0ca`
Builder commit branch: `research/m5-trial-00095-direction-regime` (Codex creates if absent)

Replaces the cancelled M4 (`CONFLUENCE_GATE_ACCESSIBILITY_DIAGNOSTIC_V1`).
See `docs/research/RESEARCH_LANDSCAPE_RESET_2026-06-04.md` for the
landscape review that justified the M4 cancellation and the D1-D5 option
list. The operator selected D1.

---

## CLAUDE HANDOFF -> CODEX

### Checkpoint

- Last commit: `683d0ca` (`research: reclaim_rejection diagnostic V1 re-run on canonical DB`)
- Branch base: `deploy/multi-asset-paper-v1`
- M3 audit: `docs/audits/AUDIT_M3_RECLAIM_REJECTION_DIAGNOSTIC_V1_2026-06-04.md`
- M4 cancellation memo: `docs/research/RESEARCH_LANDSCAPE_RESET_2026-06-04.md`
- Trial-00095 attribution audit: `docs/audits/AUDIT_TRIAL_00095_ATTRIBUTION_V1_2026-05-30.md`
- Working tree expected clean before start.

### Why this milestone

The trial-00095 conditional edge attribution audit
(`AUDIT_TRIAL_00095_ATTRIBUTION_V1_2026-05-30.md`) surfaced four
**actionable refinements** on the validated production edge. Two of them
(direction asymmetry, regime concentration) are measurable subsets of the
existing 274-trade accepted population — no new entries need to be
generated, no thresholds change, no production code is touched.

Numbers from the attribution report:

| Cohort | N | ER | PF | WR |
|---|---:|---:|---:|---:|
| Baseline (all 274) | 274 | 2.121 | 4.216 | 56.57% |
| LONG only | 252 | 2.377 | 4.929 | 60.3% |
| SHORT only | 22 | -0.805 | 0.373 | 13.6% |
| Uptrend only | 205 | 2.614 | 6.034 | 66.3% |
| Downtrend | 54 | 0.690 | 1.631 | 25.9% |
| Crowded leverage | 6 | 0.226 | 1.229 | 33.3% |
| Normal regime | 9 | 0.736 | 1.712 | 33.3% |
| TFI aligned | 227 | 2.391 | 4.963 | 60.4% |
| TFI opposed | 47 | 0.816 | 1.877 | 38.3% |

The full sample is dragged down by 22 SHORT trades with ER -0.805 and
~70 non-uptrend trades with ER between 0.226 and 0.736. Removing them on
a forward-deterministic basis (not data-snooping) should lift production
ER materially. Walk-forward is required to confirm the lift is not an
artifact of the fold structure.

### Before you code

Read (mandatory):

1. `docs/audits/AUDIT_TRIAL_00095_ATTRIBUTION_V1_2026-05-30.md` — full
   audit with all attribution numbers and methodology.
2. `research_lab/reports/trial_00095_conditional_edge_attribution_v1.md` —
   raw cohort tables (this is the source of the numbers above).
3. `research_lab/diagnostics/trial_00095_conditional_edge_attribution_v1.py` —
   existing primitives to reuse (`Candle`, `FrozenEntry`, `TradeRecord`,
   `AttributedTrade`, `DiagnosticConfig`, depth threshold constant, regime
   classification logic, fold assignment logic). DO NOT duplicate; import.
4. `docs/research/RESEARCH_LANDSCAPE_RESET_2026-06-04.md` — D1 option text
   and pre-data hypothesis framing.
5. `AGENTS.md`, `docs/MILESTONE_TRACKER.md` (M5 entry).
6. `docs/QUANT_RESEARCH_OPERATING_MODEL.md`.

### Milestone: M5 TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1

**Research-only.** No production code, no settings, no schema, no
SignalEngine, no FeatureEngine, no Governance, no Risk, no execution, no
threshold changes, no new entries generated.

**Commit split (mandatory, do not collapse):**

1. **Commit 1 — Plan document.** Single file:
   `docs/research/TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1_PLAN.md`.
   STATUS: `PLAN_READY_FOR_CLAUDE_AUDIT`. No code, no tests, no artifacts.
   STOP after this commit and wait for Claude audit + plan approval.
2. **Commit 2 — Implementation.** After plan approval, implement diagnostic
   + tests + run + artifacts in a single commit. STATUS:
   `READY_FOR_CLAUDE_AUDIT`. Do not self-audit.

### Frozen Amendment Specification

Three deterministic amendment cohorts on the existing 274-trade accepted
population (no new candidate generation, no threshold movement):

| Cohort | Filter |
|---|---|
| `A1_long_only` | `trade.direction == 'LONG'` |
| `A2_uptrend_only` | `regime_at_open == 'uptrend'` (use existing attribution classification) |
| `A3_long_and_uptrend` | `A1 AND A2` |

Reference baseline:
- `BASELINE_all_274` — full unfiltered population, ER 2.121, PF 4.216, WR 56.57%.

Regime classification MUST reuse the existing classifier from
`trial_00095_conditional_edge_attribution_v1.py`. Do not re-implement.
Re-implementing would risk silent definition drift.

### Walk-Forward Structure (Frozen Pre-Data)

Use the exact 3-fold structure from the attribution report:

| Fold | Window | Baseline N | Baseline ER |
|---|---|---:|---:|
| `fold_1_2022_2023H1` | 2022-01-01 to 2023-06-30 | 110 | 1.584 |
| `fold_2_2023H2_2024` | 2023-07-01 to 2024-12-31 | 123 | 2.493 |
| `fold_3_2025_2026Q1` | 2025-01-01 to 2026-03-31 | 41 | 2.448 |

For each amendment cohort (A1, A2, A3) report:
- per-fold count, ER, PF, WR, median R, total R, max drawdown R;
- full-sample count, ER, PF, WR, median R, total R, max drawdown R;
- delta vs baseline (per-fold and full-sample);
- "sign stability": fraction of folds where amendment ER > baseline ER.

### Pre-Data Hypotheses (Frozen, Cannot Be Changed Post-Data)

| ID | Hypothesis | Expected direction |
|---|---|---|
| H1 | A1 (LONG-only, N≈252) ER lifts from baseline 2.121 toward 2.377. | ER_A1 > ER_baseline by ≥ 0.25R. |
| H2 | A2 (uptrend-only, N≈205) ER lifts toward 2.614. | ER_A2 > ER_baseline by ≥ 0.45R. |
| H3 | A3 (LONG ∧ uptrend) is the combined refinement. | ER_A3 ≥ 2.6, PF_A3 ≥ 5.0. |
| H4 | Lift is consistent across the 3 walk-forward folds. | A3 ER > 0 in every fold; per-fold A3 ER not more than 50% below A3 full-sample ER. |

### Pre-Data Acceptance Criteria (Frozen, Cannot Be Softened Post-Data)

These are the gate. If any gate fails, the milestone returns
`HYPOTHESIS_INVALIDATED` and the amendments are NOT recommended for
production. No post-data threshold relaxation.

| Gate | Measurement | PASS threshold |
|---|---|---|
| G-1 | A3 full-sample ER vs baseline ER | A3 ER ≥ baseline ER + 0.5R (i.e., ≥ 2.621) |
| G-2 | A3 full-sample PF vs baseline PF | A3 PF ≥ baseline PF × 1.10 (i.e., ≥ 4.638) |
| G-3 | A3 per-fold sign stability | A3 ER > 0 in every one of the 3 folds |
| G-4 | A3 per-fold consistency | Per-fold A3 ER not more than 50% below A3 full-sample ER |
| G-5 | A3 max drawdown R | Reported, informational only. Not gated. |

Drawdown is reported but not a gate, because the milestone is about
expectancy refinement, not risk-of-ruin re-evaluation.

### Forbidden Patterns

- Do not change `DEPTH_THRESHOLD = 0.00649` or any other entry threshold.
- Do not generate new candidate trades. M5 operates only on the existing
  274 accepted population.
- Do not introduce post-data filters (no "add a TFI filter after seeing
  results"). All filters are A1/A2/A3 as frozen above.
- Do not modify the regime classifier. Reuse the existing one.
- Do not modify `core/`, `bot/`, `execution/`, settings, schema, or
  dependency manifests.
- Do not produce per-bucket optimization (no "find the regime cutoff that
  maximizes ER" — regime is binary uptrend / not-uptrend, frozen).
- Do not perform parameter sweeps.
- Do not include random-seed-based exits. Deterministic only.

### Deliverables

**Commit 1 — Plan only:**

- `docs/research/TRIAL_00095_DIRECTION_REGIME_REFINEMENT_V1_PLAN.md`
  with sections:
  1. Executive summary + scope guards.
  2. Why M5 vs the cancelled M4 / closed setup families (cite reset memo).
  3. Repository inventory (primitives reused from
     `trial_00095_conditional_edge_attribution_v1.py`).
  4. Cohort specification (A1, A2, A3, baseline).
  5. Walk-forward structure (3 folds, identical to attribution).
  6. Pre-data hypotheses H1–H4.
  7. Pre-data acceptance criteria G-1..G-5.
  8. Test plan (unit tests for cohort filtering, fold assignment,
     deterministic SHA, walk-forward ER consistency).
  9. Acceptance criteria for diagnostic completion.
  10. Risk register.
  11. Open questions for operator (if any).

**Commit 2 — Implementation:**

- `research_lab/diagnostics/trial_00095_direction_regime_refinement_v1.py` —
  reuse `trial_00095_conditional_edge_attribution_v1` via import.
- `tests/test_research_lab/test_trial_00095_direction_regime_refinement_v1.py` —
  unit tests covering plan Section 8.
- `research_lab/reports/trial_00095_direction_regime_refinement_v1.json` —
  deterministic JSON output with per-cohort + per-fold tables.
- `research_lab/reports/trial_00095_direction_regime_refinement_v1.sha256`.
- `research_lab/reports/trial_00095_direction_regime_refinement_v1.md` —
  markdown report including:
  - G-1..G-5 verdict table (PASS / FAIL per gate);
  - per-cohort metrics table;
  - per-fold metrics table;
  - final verdict: `HYPOTHESIS_PASSED_REQUIRES_CLAUDE_AUDIT` or
    `HYPOTHESIS_INVALIDATED` (computed by gate evaluation, not by builder
    opinion).

### Data Source (mandatory)

Frozen artifacts from the existing trial-00095 accepted-replay snapshot.
Path/name owned by `trial_00095_conditional_edge_attribution_v1.py`. Do
NOT redirect to a new path. Do NOT re-run the original trial.

Canonical market DB: `research_lab/data/crowded_unwind_backtest.db` (only
needed if the attribution diagnostic needs market context replay). Pendrive
required as in M3. Hard-fail guard from M3 must be respected.

If the diagnostic can run **purely from the 274-trade accepted artifact**
without market DB access, prefer that path — it eliminates DB dependency
and simplifies the milestone.

### Known Issues from prior audits (for awareness, not in M5 scope)

| # | Issue | In M5 scope? |
|---|---|---|
| 1 | Rejected backtest candidates not persisted | NO — that is option D3, separate milestone |
| 2 | Exit timing leakage: 92.4% losers had ≥1R MFE before red | NO — that is option D2, separate milestone |
| 3 | TFI alignment lift (aligned ER 2.391 vs opposed 0.816) | NO — keep cohort frozen at A1/A2/A3. TFI alignment is a candidate for a future M6 if M5 passes |
| 4 | Production threshold relaxation | NO — explicitly forbidden until D3 reconstruction lands |

### Your first response must contain

1. Confirmed milestone scope (what you will implement in commit 1 vs 2).
2. Acceptance criteria you propose (may extend Claude's G-1..G-5; cannot
   weaken).
3. Which known issues are in-scope vs out-of-scope (with reasoning).
4. Plan implementation outline (ordered steps to produce commit 1).
5. Confirmation that the diagnostic will reuse the existing regime
   classifier and existing fold-assignment helper from
   `trial_00095_conditional_edge_attribution_v1.py` without modification.
6. Only then: start drafting the plan document.

### Commit discipline

- Single plan file in commit 1. WHAT / WHY / STATUS = `PLAN_READY_FOR_CLAUDE_AUDIT`.
- After audit approval, single implementation commit. WHAT / WHY / STATUS =
  `READY_FOR_CLAUDE_AUDIT`.
- Do NOT self-mark as "done". Claude Code audits after push.

### Time budget guidance

- Plan draft: 1-2 hours.
- Plan audit + revisions: 1-2 hours.
- Implementation + tests + run + artifacts: 4-8 hours.
- Implementation audit: 2-4 hours.

Total milestone budget: 8-16 hours from start to verdict. Faster than M3
because most primitives are already written.

---

## End of handoff.

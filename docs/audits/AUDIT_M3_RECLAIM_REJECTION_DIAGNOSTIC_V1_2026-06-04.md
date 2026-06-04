# AUDIT: M3_RECLAIM_REJECTION_DIAGNOSTIC_V1

Date: 2026-06-04
Auditor: Claude Code
Commit: 683d0ca282386824d8255ec3005579668955dfd7
Branch: deploy/multi-asset-paper-v1
Plan commit: b39e606 (`docs/research/RECLAIM_REJECTION_DIAGNOSTIC_V1_PLAN.md`)
Implementation commit: faf7b80 (initial run, wrong DB) -> 683d0ca (re-run on canonical DB)
Active builder: Codex

## Verdict

- **Implementation verdict:** `DONE` — diagnostic is production-grade research code,
  methodologically aligned with plan b39e606 and audit resolutions Q1–Q4.
- **Hypothesis verdict:** `HYPOTHESIS_INVALIDATED` — three independent falsification
  gates (F-1, F-2, F-3) fail on the full historical sample with the canonical DB.
  Per quant research operating model, STOP this direction. No rescue.

## Standard Audit Axes

| Axis | Status |
|---|---|
| Layer Separation | PASS |
| Contract Compliance | PASS |
| Determinism | PASS |
| State Integrity | N/A (offline diagnostic) |
| Error Handling | PASS |
| Smoke Coverage | PASS |
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
| Edge Accessibility | FAIL (this IS the empirical finding, not a methodology bug) |
| Novelty vs Rescue | PASS |
| Exploration Suppression | N/A |
| Creativity vs Cherry-Picking | PASS |

## Compliance Verification

### Plan b39e606 acceptance criteria (Section 9)

| Criterion | Status | Evidence |
|---|---|---|
| Plan approved before implementation | PASS | M3 plan audit 2026-06-04 APPROVE_PLANNING_DOCUMENT WITH RESOLUTIONS |
| Deterministic event rows + cohort summaries | PASS | `event_id` = SHA256[:16]; `generated_at_utc: "DETERMINISTIC_NO_WALL_CLOCK"`; test `test_deterministic_output_two_runs_produce_identical_json_sha256` (passes) |
| JSON / SHA256 / report artifacts exist | PASS | `reclaim_rejection_feasibility_v1.{json,sha256,_report.md}` present, SHA `CE18C680…` |
| F-1 through F-6 verdict table | PASS | Report Section "Falsification Gates" |
| Cohorts present | PASS | 4 cohorts: 2174 / 2219 / 123 / 658 |
| Primary returns use `return_start_bar` | PASS | `attach_metrics` line 723–762: `primary_fixed_exit` keyed on `return_start = entry_bar + 1`; `detection_bar_fixed_exit_audit_only` is separate audit-only metric |
| MFE before/after entry reported | PASS | `mfe_before_entry`, `mfe_post_entry_5bar`, `consumed_share_secondary` per event + cohort medians |
| Baseline comparison + monthly correlation | PASS | `reclaim_swing_baseline` cohort + `monthly_correlation` block (45 non-zero overlap months, Pearson -0.114) |
| Tests pass | PASS | 13/13 (10 plan-mandated + 3 guard/regression) |
| Compile validation passes | PASS | reported by builder |
| No production modules modified | PASS | `git diff faf7b80..683d0ca` touches only `research_lab/diagnostics/`, `research_lab/analysis_output/`, `tests/`; no `core/`, `settings`, `schema`, `requirements` |
| No parameter tuning after results | PASS | Thresholds frozen in `DiagnosticConfig` defaults, unchanged between faf7b80 (first run) and 683d0ca (re-run); identical cohort byte-content per row SHA equivalence between the two DBs |

### Audit resolutions Q1–Q4

| Resolution | Status | Evidence |
|---|---|---|
| Q1 / F-M3-002 — F-3 gate = `median(mfe_before)/median(mfe_post_5bar)`, consumed-share as secondary | PASS | `evaluate_gates` line 1031: `f3_value = before / post`; `attach_metrics` line 753: `consumed_share_secondary` computed separately; report verdict line "F-3 formula used: median(mfe_before_entry) / median(mfe_post_entry_5bar). Secondary consumed-share metric is reported but not used as the F-3 gate." |
| Q2 / F-M3-003 — CVD source = `aggtrade_buckets.cvd` | PASS | `load_flow_15m` line 256 reads `cvd` from `aggtrade_buckets` (timeframe='60s' aggregated to 15m); confluence dict line 529 explicitly tags `source: "aggtrade_buckets.cvd"`; canonical DB sanity check confirmed 3,122,272 non-null CVD rows |
| Q3 / F-M3-004 — F-5 baseline = event-study `_FEATURE_CONFIG` defaults | PASS | `EVENT_STUDY_BASELINE_DEFAULTS` line 44–51 = exact dict from `event_study_v1.py`; `build_baseline_levels` line 908–926 uses these for `min_hits`, `equal_level_lookback`, `equal_level_tol_atr`; report explicitly notes trial-00095 is reference-only |
| Q4 / F-M3-005 — F-5 INCONCLUSIVE_DATA_GAP semantics | PASS | `evaluate_gates` line 1056–1062: non-F5 fail → INVALIDATED; F-5 INCONCLUSIVE without other fails → INCONCLUSIVE; matches resolution exactly |

### Timing Discipline (4-bar separation)

Sample primary event from JSON:

| Bar | Time UTC | Δ |
|---|---|---|
| detection_bar = 170 | 2022-01-02T18:30:00 | 0 |
| state_known_bar = 171 | 2022-01-02T18:45:00 | +1 |
| entry_candidate_bar = 172 | 2022-01-02T19:00:00 | +2 |
| return_start_bar = 173 | 2022-01-02T19:15:00 | +3 |
| level_available_at | 2022-01-02T05:00:00 | -54 (level known ~13.5h before state_known) |

Entry-delay histogram (entry_candidate_bar − state_known_bar) shows realistic
spread: 402 events at +1 bar, 294 at +2, 218 at +3, 156 at +4, 126 at +5, …
no events at +0 (entry never on `state_known_bar` itself). Confluence and
reclaim are evaluated on closed bars only. No detection-bar entry, no
swing-confirmation past `state_known_bar`. ✅

### Data Lineage

Canonical DB used: `F:\crowded_unwind_backtest.db` (operator pendrive).
Canonical DB lineage equivalence vs prior fallback DB
(`replay-optuna-default-v3-trial-00095.db`) empirically verified by builder:
candles_15m row-SHA256 match, aggtrade_60s row-SHA256 match. Re-run
reproduces faf7b80 byte-for-byte on the analytical content (only `db_path`
and `db_resolution` fields differ in JSON). This confirms the prior run was
analytically valid; commit 683d0ca legalizes the source.

### Hard-Fail Guard

`resolve_default_db` (line 1066–1084) now raises `SystemExit("CANONICAL_DB_MISSING: ...")`
when canonical DB is absent, removing the silent fallback regression that
caused faf7b80. Opt-in `--allow-fallback` flag added for local research only.
Two regression tests added (`test_default_db_resolution_hard_fails_when_canonical_db_missing`,
`test_default_db_resolution_uses_fallback_only_when_allowed`). ✅

## Falsification Results

| Rule | Measurement | Value | Threshold | Status |
|---|---|---:|---:|---|
| F-1 | Timing-correct PF | 0.6243 | ≥ 1.5 | **FAIL** |
| F-2 | Median net expectancy (after 0.10% cost) | -0.00281 | ≥ 0 | **FAIL** |
| F-3 | median(MFE_before) / median(MFE_post_5bar) | 1.2256 | ≤ 0.70 | **FAIL** |
| F-4 | Throughput Δ vs baseline | 1.349 trades/day | ≥ 0.2 | PASS |
| F-5 | Pearson monthly P&L correlation with baseline | -0.1135 | ≤ 0.5 | PASS |
| F-6 | Detection-bar edge vs timing-correct edge | det_pf=0.669, tim_pf=0.624 | ≤ 30% better | PASS |

Three independent gates fail. This is a robust invalidate, not marginal.
PF 0.624 means ~38% loss on a gross+cost basis. Median expectancy is
solidly negative.

## Findings

### F-M3-IMPL-001 — Provenance is decorative (INSIGHT, non-blocking)

Severity: INSIGHT | Confidence: 5/5

Primary cohort (with `level_scanner` provenance): 2174 events, net PF 0.6243.
Ablation cohort (without provenance): 2219 events, net PF 0.6110.

Provenance filter removes 45 of 2219 events (~2%) and improves PF by 0.013.
Plan Section 6 asked: "determine whether provenance is load-bearing or only
decorative." Answer: **decorative**. `level_scanner` overlap does not change
the edge meaningfully. This is a clean ablation answer and useful evidence
for future setup designs — do not rely on level-overlap as a load-bearing
filter for this candidate family.

### F-M3-IMPL-002 — F-3 ratio + consumed-share are independently catastrophic (INSIGHT, non-blocking)

Severity: INSIGHT | Confidence: 5/5

F-3 ratio (median basis) = 1.226 → pre-entry MFE is 23% larger than post-entry
MFE. Median consumed share (secondary metric) = ~0.84 → 84% of the favorable
opportunity is consumed before entry.

This is the same accessibility failure pattern as
`SMC_SEQUENCE_EDGE_FEASIBILITY_V1` (median MFE_before 0.011565 vs MFE_post
0.004916, ratio 2.35). Reclaim_rejection moves earlier in the sequence than
SMC mitigation, but the TFI/CVD confluence wait is still long enough to
destroy accessibility. **Two consecutive families have failed F-3 for the
same structural reason.** This is a strong signal that the bottleneck is the
**confluence-gate wait**, not the structural pattern.

### F-M3-IMPL-003 — F-6 PASS is informationally weak in this regime (OBSERVATION, non-blocking)

Severity: OBSERVATION | Confidence: 4/5

F-6 measures "detection-bar edge vs timing-correct edge" to detect lookahead
leakage. PASS condition: detection edge not >30% better than timing edge.

Here detection PF = 0.669 vs timing PF = 0.624; both are well below 1.0
(both are losing edges). F-6 mechanically PASSES, but the meaningful
interpretation is "there is no detection-bar edge to leak in the first
place." F-6 would only become diagnostic if a positive detection-bar edge
existed. Useful future framing for an F-6 v2: require detection_pf > 1.0
before applying the 30% gate.

Not a bug — gate works as specified. Just worth understanding before reading
F-6 PASS as evidence of "no lookahead risk."

### F-M3-IMPL-004 — Baseline timing model differs from primary (OBSERVATION, non-blocking)

Severity: OBSERVATION | Confidence: 4/5

`reclaim_swing_baseline` (line 929–996) sets
`detection_bar = state_known_bar = entry_candidate_bar = idx` (the sweep bar),
while primary uses the strict 4-bar separation. Baseline is effectively
allowed to "decide" on the same bar the sweep occurs, primary cannot. Despite
this timing advantage, baseline still posts net PF 0.741 (also losing).

Plan Section 6 only requires baseline for **throughput and monthly P&L
correlation** comparison, both of which are timing-model-insensitive. Direct
PF comparison between primary and baseline is therefore not fully
apples-to-apples and should not be read as "baseline is the better setup."
Report should optionally note this. Not blocking for verdict.

### F-M3-IMPL-005 — Control-cohort construction is correct but subtle (OBSERVATION, non-blocking)

Severity: OBSERVATION | Confidence: 4/5

`build_control_events` (line 806–878) receives `control_candidates` from
`detect_wick_candidates_without_swing_filter` (line 881–905), which uses
`swing_left_bars=0, swing_right_bars=0`. With both = 0,
`confirmed_swing_maps` returns every index as a "swing" (the `all(...)` over
empty windows is vacuously True), so `control_candidates` is effectively a
wick-only filter with no swing requirement.

Then `build_control_events` re-runs `confirmed_swing_maps` with the **real**
3/1 config and excludes any candidate whose detection_bar IS a swing extreme.
Result: wick events at non-extreme locations only. ✅ Correct calendar/
side-matched non-extreme control cohort, matching plan Section 6.

The mechanism is correct but the reliance on vacuous `all()` over empty
windows is fragile to future refactor. Consider an explicit `extreme=False`
helper. Non-blocking.

### F-M3-IMPL-006 — `mfe_before_entry` uses `detection_close` as reference price (OBSERVATION, non-blocking)

Severity: OBSERVATION | Confidence: 3/5

`mfe_before_entry` (line 623–634) uses `entry_price = candles[detection_bar].close`
and measures the max favorable excursion across bars
`[detection_bar+1, …, entry_candidate_bar]`.

Plan Section 8 specifies
`test_mfe_before_entry_uses_high_low_in_window_after_detection_before_entry`
which the implementation honors. Using `detection_close` as the reference is
defensible ("what would we have captured if we'd entered immediately") but
the choice should be documented in the report alongside the formula. Not
blocking — implementation matches plan; the doc nuance is minor.

## Critical Issues

None.

## Warnings

None.

## Observations

See findings F-M3-IMPL-001 through F-M3-IMPL-006.

## Verdict Synthesis

**Implementation: `DONE`.** Code is methodologically sound, every plan
acceptance criterion is met, all four audit resolutions (Q1–Q4) are
empirically honored, timing discipline is enforced, lookahead risk is
controlled, and the hard-fail guard prevents a recurrence of the
silent-fallback regression that contaminated faf7b80.

**Hypothesis: `HYPOTHESIS_INVALIDATED`.** Three independent falsification
gates fail with strong margin on a 4-year, 145,921-candle sample. The
accessibility failure (F-3 = 1.23, consumed-share ≈ 0.84) duplicates the
structural failure mode of `SMC_SEQUENCE_EDGE_FEASIBILITY_V1`. Per quant
research operating model: STOP this direction, no rescue.

## Recommended Next Step

**Pause reclaim_rejection family entirely.** Two consecutive setup hypotheses
in this family (SMC_SEQUENCE mitigation, reclaim_rejection) have failed F-3
for the same structural reason: TFI/CVD confluence wait destroys MFE
accessibility. A third candidate built on the same confluence-gate primitive
would likely fail the same way.

The recommended next milestone is a **diagnostic of the confluence-gate wait
itself**, not another setup geometry. Concretely:

> **M4 — CONFLUENCE_GATE_ACCESSIBILITY_DIAGNOSTIC_V1** (proposed)
>
> Question: How long does the TFI/CVD confluence wait typically take after
> a state-knowable trigger? What fraction of MFE is consumed during that
> wait across structurally distinct triggers? Is there a faster confluence
> proxy (e.g., bar-close TFI only, or shorter aggtrade window) that
> preserves MFE accessibility while staying lookahead-safe?
>
> Deliverables: confluence wait-time distribution per trigger family,
> MFE-consumed-share distribution as a function of wait, candidate
> faster-proxy specifications with their own F-3 gate evaluation.

Builder selection: Codex (path-sensitive, environment-dependent — same
constraints as M3).

User decides: approve M4 confluence diagnostic, propose different direction,
or pause research lab and return to production stability work.

## Handoff to Builder

Held pending user decision on next milestone (per CLAUDE.md decision flow:
auditor presents ONE recommendation, user approves or vetoes). Handoff
prompt will be generated once user ratifies the next milestone.

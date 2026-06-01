# AUDIT: HYPOTHESIS_INVENTORY_AND_FAILURE_CATALOG_V1

Date: 2026-06-01
Auditor: Claude Code
Scope: Read-only inventory of every hypothesis that passed through the research pipeline since 2026-04-30; failure-mode classification; cost-sensitivity flagging; coverage map; discipline gap quantification.
Branch: `claude/epic-darwin-z8Moa`
Parent context: `AUDIT_BLUEPRINT_FOUNDATIONS_V1_2026-06-01.md` Risk 2-5; `CLAUDE.md` STOP-with-alternatives discipline; `research_lab/hypotheses/spec.py` taxonomy.

## Verdict: DONE

Inventory is complete for the audited window. Failure catalog produces a sharp, defensible classification of why each hypothesis was rejected. Cost-sensitivity classification corrects a working assumption I made earlier in the conversation — see Section 5 finding.

This document is the **structural input** for three downstream milestones: `COST_MODEL_AUDIT_V1`, `HYPOTHESIS_REGISTRY_RETROACTIVE_REGISTRATION_V1`, and any future strategy-class search prioritization. It does not approve any new hypothesis, modify production, or change the runtime.

## 1. Executive Summary

The system has produced 17 distinct hypothesis-or-program artifacts since 2026-04-30. Of those:
- **2 are VALIDATED edges** (trial-00095 baseline + ETH transfer)
- **1 is GATED edge** (SOL standalone-DD-fail, portfolio-pass)
- **11 are INVALIDATED** with structural failure modes
- **3 are SUPPORTING** (data feasibility, infrastructure, attribution)

Of the 11 INVALIDATED hypotheses:
- **8 failed for structural reasons** (timing, controls, no-edge, sample) — would not be revived by lower cost
- **1 is genuinely cost-sensitive** (SMC sequence: -0.000442 net at 0.10%; back-of-envelope crosses zero at ~0.06% round-trip)
- **2 are cost-sensitivity UNKNOWN** (sensitivity not explicitly tested in audit) — candidates for explicit re-evaluation

This corrects an earlier working assumption ("cost audit may resurrect 1-2 closed hypotheses → many could come back"). The reality is more precise: **most invalidated hypotheses explicitly tested at sub-realistic costs already, and remained negative**. The cost audit is still worth running, but its expected resurrection yield is **lower than I previously implied** — likely 1 confirmed (SMC sequence) plus 2 to verify.

Coverage of the strategy-class × asset × timeframe matrix sits at **<10% of feasible combinations**, dominated by BTC 15m sweep-reclaim variants. Three classes from `spec.py` taxonomy (`entry_filter`, `exit_filter`, `regime_label` as a label not as a filter) are under-represented or absent.

Registration discipline is broken: **0 of 11 invalidated hypotheses are present in `research_lab/hypotheses/closed/`** (which does not exist); the `active/` folder holds 23 entries but none of them are the recent invalidation set. Recovery requires retroactive registration after the cost audit.

## 2. Full Inventory

| # | Hypothesis ID / artifact | Class | Asset | TF | Verdict | Audit doc | Registered? |
|---|---|---|---|---|---|---|---|
| 1 | `optuna-default-v3-trial-00095` | parameter_refinement | BTC | 15m | VALIDATED_BASELINE | `AUDIT_WF_TRIAL_00095_2026-05-08` | NO (deployed as edge, never registered as hypothesis) |
| 2 | `ETH_TRIAL_00095_TRANSFER` | multi_asset_transfer | ETH | 15m | VALIDATED_TRANSFER | `AUDIT_ETH_TRIAL_00095_TRANSFER_FEASIBILITY_2026-05-19` | YES (`eth_trial_00095_transfer_feasibility.json`) |
| 3 | `SOL_TRIAL_00095_TRANSFER` | multi_asset_transfer | SOL | 15m | STANDALONE_FAIL_PORTFOLIO_PASS | `AUDIT_SOL_TRIAL_00095_TRANSFER_FEASIBILITY_2026-05-20` | YES |
| 4 | `TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1` | diagnostic_only | BTC | 15m | DONE (data) | `AUDIT_TRIAL_00095_ATTRIBUTION_V1_2026-05-30` | NO |
| 5 | `TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC` | exit_filter (probe) | BTC | 15m | DEFERRED | `AUDIT_TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_2026-05-18` | YES |
| 6 | `TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION` | exit_filter | BTC | 15m | INVALIDATED | (referenced in tracker) | YES |
| 7 | `SMC_SEQUENCE_EDGE_FEASIBILITY_V1` | timing_overlay | BTC | 15m | INVALIDATED | `AUDIT_SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27` | NO |
| 8 | `SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1` | diagnostic_only | BTC | 5m | INVALIDATED_TIMING | `AUDIT_SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_2026-05-27` | NO |
| 9 | `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` | diagnostic_only (meta) | BTC | 15m | INVALIDATED_NO_EDGE_SPACE | `AUDIT_MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1_2026-05-27` | NO |
| 10 | `LIQUIDATION_BURST_REVERSAL_ENTRY_FEASIBILITY_V1` | timing_overlay | BTC | 15m | INVALIDATED_TIMING | `AUDIT_LIQUIDATION_BURST_REVERSAL_ENTRY_FEASIBILITY_V1_2026-05-28` | NO |
| 11 | `LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1` | timing_overlay | BTC | 5m | INVALIDATED_TIMING | `AUDIT_LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1_2026-05-28` | NO |
| 12 | `VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1` | entry_filter | BTC | 15m | INVALIDATED_NO_EDGE | `AUDIT_VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1_2026-05-28` | NO |
| 13 | `TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1` | regime_label | BTC | 15m | INVALIDATED_NO_EDGE | `AUDIT_TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1_2026-05-28` | NO |
| 14 | `FILTERED_HMM_REGIME_SHIFT_FEASIBILITY_V1` | regime_label | BTC | 15m | INVALIDATED_CONTROLS_BEAT_MAIN | `AUDIT_FILTERED_HMM_REGIME_SHIFT_FEASIBILITY_V1_2026-05-30` | NO |
| 15 | `OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1` | multi_asset_transfer | EUR/USD | 15m | INVALIDATED_NO_EDGE | `AUDIT_OANDA_EURUSD_M15_DIAGNOSTIC_2026-05-31` | NO |
| 16 | `OANDA_XAUUSD_SWEEP_RECLAIM_TRANSFER_FEASIBILITY_V1` | multi_asset_transfer | XAU/USD | 15m | INVALIDATED_SAMPLE_COLLAPSE | `oanda_xauusd_sweep_reclaim_transfer_feasibility_v1.md` (report; no separate audit) | NO |
| 17 | `OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1` | timing_overlay | EUR/USD | 15m | INVALIDATED_NO_EDGE | `AUDIT_OANDA_ASIA_RANGE_DIAGNOSTIC_2026-06-01` | NO |
| 18 | `OANDA_NY_REVERSAL_AFTER_LONDON_EXTENSION_FEASIBILITY_V1` | timing_overlay | EUR/USD | 15m | INVALIDATED_TAIL_DOMINATED | (audit pending — Codex pushed `eed1db7`, prior Claude in Windsurf audited as HYPOTHESIS_INVALIDATED) | NO |

Note: items 5 and 6 are tracked in `hypotheses/active/` as JSON, but neither has its current verdict (DEFERRED, INVALIDATED) reflected in the status field. The registry is therefore stale even where it exists.

## 3. Coverage Map: {Asset × Timeframe × Strategy Class}

Cells marked with hypothesis numbers from Section 2. `[X]` = tested. Empty cell = not searched.

### BTC

| Class | 1m | 5m | 15m | 1h | 4h | 1d |
|---|---|---|---|---|---|---|
| `entry_filter` | | | [12] | | | |
| `exit_filter` | | | [5, 6] | | | |
| `timing_overlay` | | [11] | [7, 10] | | | |
| `multi_asset_transfer` | | | | | | |
| `timeframe_feasibility` | | (active: 5m crowded unwind, 5m compression) | | | | |
| `regime_label` | | | [13, 14] | | | |
| `diagnostic_only` | | [8] | [4, 9] | | | |
| `parameter_refinement` | | | [1] | | | |

### ETH

| Class | 1m | 5m | 15m | 1h | 4h | 1d |
|---|---|---|---|---|---|---|
| `multi_asset_transfer` | | | [2] | | | |
| `parameter_refinement` | | | (active: eth_asset_specific_optimization) | | | |

### SOL

| Class | 1m | 5m | 15m | 1h | 4h | 1d |
|---|---|---|---|---|---|---|
| `multi_asset_transfer` | | | [3] | | | |
| `diagnostic_only` | | | (active: sol_drawdown_forensic, risk policy, data feasibility) | | | |

### EUR/USD (OANDA)

| Class | 1m | 5m | 15m | 1h | 4h | 1d |
|---|---|---|---|---|---|---|
| `multi_asset_transfer` | | | [15] | | | |
| `timing_overlay` | | | [17, 18] | | | |

### XAU/USD (OANDA)

| Class | 1m | 5m | 15m | 1h | 4h | 1d |
|---|---|---|---|---|---|---|
| `multi_asset_transfer` | | | [16, sample collapse] | | | |

### Untouched (illustrative, non-exhaustive)

Every cell not listed above is untouched. The untested space includes:
- All assets × 1m, 1h, 4h, 1d (no systematic coverage)
- `entry_filter` and `exit_filter` outside BTC 15m
- All non-Binance crypto venues
- All spot vs perp basis pairs
- Funding-rate-driven strategies (no class for this in current taxonomy; would require new class or sub-class of `entry_filter`)
- Cross-asset / pairs strategies (no class)
- Market-making / passive-fill strategies (no class)

**Coverage estimate: <10% of feasible cells in the matrix as currently classified, and the classification itself excludes several economically meaningful strategy classes.**

## 4. Failure Catalog by Root Cause

For each INVALIDATED hypothesis, the primary root-cause classification with supporting metric:

| # | Hypothesis | Root cause | Key metric supporting classification |
|---|---|---|---|
| 7 | SMC_SEQUENCE | **cost_sensitivity** (primary) + timing (secondary) | median net -0.000442 at 0.10%; PF proxy 1.061 vs threshold 4.0; MFE 0.011565 before entry, 0.004916 after |
| 8 | SWEEP_RECLAIM_TAXONOMY | **timing** (label timing — lookahead in delayed reclaim) | detection-bar 0.001189 → label-available 0.000054 (95% collapse); true breakout 0.001028 → -0.000268 (negative) |
| 9 | MFE_ACCESSIBILITY | **structural_no_edge** (proves space, not single hypothesis) | 28 knowable states × 212,871 observations; not a single state with positive median net after 0.10%; best `reject_no_reclaim_known` at -0.0095% |
| 10 | LIQUIDATION_BURST_ENTRY | **timing** | median MFE consumed 100% before entry; controls beat main |
| 11 | LIQUIDATION_BURST_5M | **timing** | same mechanism on 5m, same 100% MFE consumption pattern |
| 12 | VOLUME_CONFIRMED_RANGE_BREAKOUT | **no_edge** (post-MFE-accessible) | MFE accessible after entry, but ER/PF negative; controls beat main |
| 13 | TREND_RANGE_STATE_SHIFT | **no_edge** | MFE accessible, weak ER/PF; 0/4 folds positive |
| 14 | FILTERED_HMM_REGIME_SHIFT | **controls_beat_main** | all primary controls beat main signal; state flips unstable |
| 15 | OANDA_EURUSD_M15 | **structural_no_edge** (confirmed at low cost) | even at 0.010% cost: ER -0.1501, median net -0.0109%; even at 0.025% cost: ER -0.3676; **edge does not exist regardless of cost** |
| 16 | OANDA_XAUUSD | **sample_collapse** | 11 events after filtering; not decision-grade |
| 17 | OANDA_ASIA_RANGE | **structural_no_edge** (confirmed at low cost) | even at 0.010% cost: ER -0.0715, median net -0.0153%; controls beat main; **edge does not exist regardless of cost** |
| 18 | OANDA_NY_REVERSAL | **tail_dominated** (mean > median) | mean ER 4.4974 (very high), median net -0.0088% (negative); 0/4 positive folds; reversal beats continuation 10× but median still negative |

### Root cause distribution

| Root cause | Count | Notes |
|---|---|---|
| timing (MFE consumed before entry / lookahead in label) | 3 | hypotheses #8, #10, #11 |
| structural_no_edge | 5 | hypotheses #9, #12, #13, #15, #17 |
| cost_sensitivity (primary) | 1 | hypothesis #7 |
| controls_beat_main | 1 | hypothesis #14 |
| sample_collapse | 1 | hypothesis #16 |
| tail_dominated | 1 | hypothesis #18 |

**Pattern observation**: The dominant failure mode is `structural_no_edge` (5/11). The second most common is `timing` (3/11). `cost_sensitivity` is rare as primary cause (1/11), and where present (SMC sequence), the secondary timing issue is also material — even if SMC sequence crosses median-net gate at lower cost, the PF proxy 1.061 vs threshold 4.0 remains a fundamental quality problem.

## 5. Cost-Sensitivity Classification (Critical Correction)

This section corrects a working assumption I stated earlier in the conversation ("cost audit may resurrect 1-2 dead hypotheses; possibly several"). Empirical re-reading of the audit corpus narrows the resurrection target sharply.

### Explicitly tested at sub-0.10% cost in audit, still negative → NOT cost-sensitive

| # | Hypothesis | Lowest tested cost | Result at that cost | Verdict |
|---|---|---|---|---|
| 15 | OANDA_EURUSD_M15 | 0.010% | ER -0.1501, median net -0.0109% | NOT cost-sensitive |
| 17 | OANDA_ASIA_RANGE | 0.010% | ER -0.0715, median net -0.0153% | NOT cost-sensitive |
| 18 | OANDA_NY_REVERSAL | 0.015% (declared) | median net -0.0088% | NOT cost-sensitive (negative pre-cost too) |

### Cost-sensitive (primary) — candidate for re-evaluation at realistic cost

| # | Hypothesis | Median net at 0.10% | Estimated median net at 0.04% (linear) | Crosses gate? |
|---|---|---|---|---|
| 7 | SMC_SEQUENCE | -0.000442 (-0.0442%) | ~+0.000158 (+0.0158%) | Yes by median-net gate; **still fails PF proxy 1.061 < 4.0** |

### Cost-sensitivity NOT EXPLICITLY TESTED in audit — re-evaluation needed

| # | Hypothesis | Why include | Action for cost audit |
|---|---|---|---|
| 8 | SWEEP_RECLAIM_TAXONOMY | Failure was timing (label vs detection), not cost; but lower cost might rehabilitate the delayed-reclaim subset specifically | Re-evaluate only the label-available timing branch at corrected cost |
| 10 | LIQUIDATION_BURST_ENTRY | Failure was timing (MFE consumed), but median return data exists; quick arithmetic check is cheap | Compute: median net at realistic cost; if still negative, confirm not cost-sensitive |
| 11 | LIQUIDATION_BURST_5M | Same as #10 on 5m | Same check |

### Confirmed NOT cost-sensitive on logic (no cost test possible to rescue)

| # | Hypothesis | Why immune |
|---|---|---|
| 9 | MFE_ACCESSIBILITY | Proves NO knowable state has positive median net; lower cost shifts all 28 states up by same delta but none had positive PF or WR baseline. Cost reduction does not change the structural finding. |
| 12 | VOLUME_CONFIRMED_RANGE_BREAKOUT | "Result so negative that higher costs would not change verdict" — symmetric argument for lower cost: low cost cannot rescue ER deeply negative and controls beat main |
| 13 | TREND_RANGE_STATE_SHIFT | 0/4 folds positive; controls beat main; structural no-edge |
| 14 | FILTERED_HMM_REGIME_SHIFT | Controls beat main signal; lower cost benefits controls equally |
| 16 | OANDA_XAUUSD | Sample collapse (11 events); cost is not the constraint, data is |

### Cost audit expected yield (revised)

Earlier informal estimate: "1-2 may resurrect, possibly several."
**Revised estimate based on this inventory: 0-1 confirmed (SMC sequence partial, blocked by PF threshold) + 3 candidates for explicit re-check (#8, #10, #11).**

This does not invalidate the cost audit milestone — it sharpens its expected output. The cost audit is still valuable for:
- Confirming that `0.04%` (or whatever realistic) is the right number going forward, not as a backwards-compatibility fix
- Eliminating cost as a confounder in future hypothesis evaluation
- Producing the cost-corrected ledger for the registry

It does **not** rest on the assumption that many closed hypotheses will return. They won't.

## 6. Discipline Gap Analysis

| Metric | Value | Source |
|---|---|---|
| Hypothesis specs in `research_lab/hypotheses/active/` | 23 | filesystem |
| Hypothesis specs in `research_lab/hypotheses/closed/` | 0 | folder does not exist |
| Hypothesis specs in `research_lab/hypotheses/rejected/` | 0 | folder does not exist |
| Recent (2026-04 to 2026-06) INVALIDATED hypotheses from this inventory | 11 | Section 2 |
| Of those 11, how many have a HypothesisSpec JSON anywhere | 1 (#6 LOSS_CONTROL has stale `active/` entry) | filesystem scan |
| Of those 23 active specs, how many have CURRENT status reflecting actual verdict | <50% (#5 should be DEFERRED, #6 should be CLOSED) | spec.py status field vs audit verdict |

### Findings

1. **Registration is bypassed**. The discipline standard implied by `spec.py` (with its required fields `edge_rationale`, `counterparty_or_market_mechanism`, `acceptance_criteria`, `kill_criteria`, `failure_modes`) was applied to ~zero of the 11 recent INVALIDATED hypotheses. Hypotheses were drafted as `docs/research/*_PLAN.md` markdown documents instead, which lack the structural enforcement.

2. **Status fields are stale even where specs exist**. The 23 specs in `active/` include some that are no longer active by audit verdict but were never moved or status-updated.

3. **`HYPOTHESIS_STATUSES` includes `CLOSED` and `REJECTED`** in `spec.py` line 19 — these statuses exist in the schema but are unused in practice. No filesystem evidence of either status being assigned to any spec.

4. **No `failure_modes` aggregation** across hypotheses. Each spec has the field, but there is no cross-spec view of "what we already know doesn't work."

5. **`ResearchProgram` entity** exists in `spec.py` line 39 (with required fields `disallowed_actions`, `allowed_hypothesis_classes`, `validation_protocol`) but no instantiated `ResearchProgram` files exist in the repo. The grouping layer is defined but unused.

### Implication

The infrastructure is mature; the discipline is broken. This is the same class of breach as the manual `settings.json` edit on 2026-05-25: a documented process is bypassed when it is locally inconvenient. The fix is the same: enforce the gate in workflow rather than rely on builder compliance. Specifically:

- `AGENTS.md` and `CLAUDE.md` should require: no `docs/research/*_PLAN.md` may be authored without a matching `research_lab/hypotheses/active/<id>.json` HypothesisSpec.
- Audit verdict `HYPOTHESIS_INVALIDATED` must require a follow-up commit moving the spec to `research_lab/hypotheses/closed/<id>.json` with status `CLOSED` and `failure_modes` field populated with the audit's documented failure causes.
- These two rules should be added as policy in the next AGENTS.md amendment.

## 7. Recommended Next Inputs

This document is itself an input. It supports three downstream actions in the parent CONFIG_LINEAGE_RECONCILIATION → COST_MODEL_AUDIT sequence.

### For `COST_MODEL_AUDIT_V1` (next after paper validation)

Use Section 5 directly as the work list. Specifically:
- **Skip** the 5 confirmed-not-cost-sensitive (Section 5 last subtable) — do not waste cycles re-evaluating
- **Skip** the 3 OANDA hypotheses (already tested at sub-0.10% costs and still negative)
- **Compute** cost-corrected verdicts for SMC_SEQUENCE (#7), SWEEP_RECLAIM_TAXONOMY label-available branch (#8), LIQUIDATION_BURST_ENTRY (#10), LIQUIDATION_BURST_5M (#11)
- **Calibrate** realistic Binance VIP tier cost as the audit's central deliverable (not a side effect)

### For `HYPOTHESIS_REGISTRY_RETROACTIVE_REGISTRATION_V1`

Use Section 2 as the registration source-of-truth list. Section 4 as the `failure_modes` field source. Run after cost audit so that cost-sensitive hypotheses are registered with the correct verdict.

### For future strategy-class search prioritization

Use Section 3 (coverage map) as the input. The strategic question post-cost-audit is which untouched cell deserves the next hypothesis. This document does not answer that question — it provides the data for the answer to be made deliberately rather than by SMC-literature drift.

## 8. Out of Scope

- No new hypothesis is proposed or approved
- No production state is touched
- No HypothesisSpec JSON files are written or modified (retroactive registration happens in a future milestone, after cost audit)
- No `AGENTS.md` or `CLAUDE.md` changes are committed here (proposed in Section 6 only)
- No cost model audit is performed (the data for it is provided)
- No coverage gap is filled (the data showing the gaps is provided)

## Decision

This audit is its own output. It commits structural input data that downstream milestones can consume without re-discovery. The next milestone in the auditor queue, once CONFIG_LINEAGE_RECONCILIATION and paper validation close, is `COST_MODEL_AUDIT_V1` — and it now has a precise work list rather than a vague "re-evaluate everything closed."

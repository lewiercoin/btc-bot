# COST_MODEL_AUDIT_V1 — Plan

Date: 2026-06-01
Auditor: Claude Code
Status: PLAN_AWAITING_DEPENDENCY (blocked on CONFIG_LINEAGE_RECONCILIATION_V1 closure + initial paper performance evidence)
Type: Audit-only milestone. No code changes. No production touch. No new diagnostics implementation.
Branch: `claude/epic-darwin-z8Moa` for the plan; the executed audit will commit on the same branch.
Parent context:
- `AUDIT_BLUEPRINT_FOUNDATIONS_V1_2026-06-01.md` Risk 3 (cost model unaudited vs venue reality)
- `AUDIT_HYPOTHESIS_INVENTORY_AND_FAILURE_CATALOG_V1_2026-06-01.md` Section 5 (precise cost-sensitivity work list)
- `CLAUDE.md` STOP-with-alternatives rule

## Goal

Produce a defensible, evidence-based cost model for all future research diagnostics and runtime evaluation. The current `0.10%` round-trip used across `research_lab/diagnostics/` and `research_lab/analysis_*.py` is uncalibrated against venue reality and inconsistent with the cost model in `execution/paper_execution_engine.py`. This audit corrects both.

Secondary goal: produce cost-corrected verdicts for the 4 hypotheses flagged as cost-sensitive candidates in the inventory audit Section 5.

## Non-Goals

- Do not run new backtests
- Do not modify `research_lab/diagnostics/*.py` cost defaults (that change happens in a follow-up implementation milestone after this audit)
- Do not modify `execution/paper_execution_engine.py`
- Do not run new optimization campaigns
- Do not propose new hypotheses
- Do not touch production runtime, settings, or DB
- Do not resurrect closed hypotheses based on speculation — re-verdict only the ones the inventory identified as cost-sensitive candidates

## Pre-Existing Cost Model Inconsistency (Finding before audit starts)

While drafting this plan I inspected current cost model implementation and found a **decision-grade inconsistency** that the audit must resolve as its first deliverable:

| Source | Cost specification | Effective round-trip |
|---|---|---|
| `execution/paper_execution_engine.py:58` | `fee_rate = 0.0004` (per fill, taker) with comment "match backtest SimpleFillModel" | **0.08%** (0.04% × 2) |
| `research_lab/analysis_smc_sequence_edge_feasibility_v1.py:86` and equivalents in 8 other research diagnostics | `round_trip_cost_pct: float = 0.0010` | **0.10%** |
| Hypothesis acceptance criteria (e.g., `btc_5m_crowded_unwind_reversal.json`) | `cost_sensitivity_er_at_2x` field implies 2× a baseline cost | depends on baseline definition |

The research diagnostics evaluate hypotheses under a **stricter cost model than what the bot actually pays** in paper execution. This means:

- A hypothesis that fails research's `0.10%` gate by less than 0.02% may actually be paper-executable
- The 0.10% / 0.08% gap is 20 bp per round-trip — material on small-edge hypotheses
- Inconsistency is a methodology issue regardless of which number is "right" — both should match or be explicitly differentiated with documented rationale

This finding alone justifies the audit. Calibrating which number to standardize is the audit's central deliverable.

## Methodology

The audit produces a single output document: `docs/analysis/COST_MODEL_AUDIT_V1_2026-XX-XX.md`. The methodology to populate it is decomposed into five phases, in strict order.

### Phase 1: Map current cost model surfaces

Enumerate every location in the repo where a numeric cost or fee constant is encoded.

- `execution/paper_execution_engine.py` (paper fill cost)
- `execution/live_execution_engine.py` (live fill cost — verify it reads from venue commission field, no hardcoded)
- All `research_lab/analysis_*.py` and `research_lab/diagnostics/*.py` (research cost defaults)
- All `research_lab/hypotheses/active/*.json` (`acceptance_criteria.cost_sensitivity_*` fields)
- `backtest/` (any fill model with cost assumption)
- Documentation: `docs/research/*_PLAN.md`, audit reports

Output: an inventory table mapping `(file, line, constant_name, value, role)`.

### Phase 2: Establish ground truth for Binance USDT Futures cost

For each component of trading cost, document the **measured or schedule-defined value** from authoritative source:

| Component | Authoritative source | Notes |
|---|---|---|
| Maker fee | Binance public fee schedule for USDT-M Perpetual Futures | VIP tier-dependent |
| Taker fee | Binance public fee schedule | VIP tier-dependent |
| BNB discount | Binance fee schedule note | If account uses BNB |
| Current account VIP tier | Production server commission field (read-only query) | Requires reading actual recent fills from `trade_log` if available |
| Slippage (taker, market orders) | Measured from the 1 closed PAPER trade we have + ETH/SOL prospective fills as they accumulate | Bounded by half-spread + market impact |
| Funding cost | Binance funding rate history for held positions | Depends on holding period; for ~15m exits typically negligible per trade |

Decision-grade question: **does the bot place market orders (taker) or limit orders (maker)?**

This is determined by reading `execution/paper_execution_engine.py`, `execution/live_execution_engine.py`, and any documented execution policy in `docs/`. If unclear, the audit must answer this before proceeding to Phase 3.

### Phase 3: Compute realistic round-trip cost scenarios

Produce a table of plausible round-trip cost levels with their assumptions explicitly stated:

| Scenario | Maker entry | Taker entry | Maker exit | Taker exit | Slippage | Effective round-trip | Comment |
|---|---|---|---|---|---|---|---|
| Conservative (current research default) | — | — | — | — | — | 0.10% | uncalibrated, status quo |
| Current paper execution model | — | yes (0.04%) | — | yes (0.04%) | 0% (none modeled) | 0.08% | matches SimpleFillModel |
| Realistic taker-taker with slippage | — | yes (0.04%) | — | yes (0.04%) | TBD bp | 0.08% + 2 × TBD bp | most likely realistic for market-order strategies |
| Mix (taker entry, maker exit) | — | yes (0.04%) | yes (0.02%) | — | TBD bp | 0.06% + slippage | requires limit-order exit; not yet implemented |
| Optimistic maker-maker | yes (0.02%) | — | yes (0.02%) | — | TBD bp | 0.04% + slippage | requires limit-order entry + exit |

The audit recommends ONE of these as the new research default, with reasoning.

### Phase 4: Re-verdict the 4 cost-sensitive candidates

From inventory Section 5, the audit re-evaluates exactly these 4 hypotheses at the recommended new cost level **plus 0.08% as a side check**:

| # | Hypothesis | Current verdict | Median net at 0.10% | Cost-corrected re-evaluation |
|---|---|---|---|---|
| 7 | SMC_SEQUENCE | INVALIDATED | -0.000442 | Compute at recommended cost; flag PF proxy 1.061 vs threshold 4.0 as independent blocking issue |
| 8 | SWEEP_RECLAIM_TAXONOMY (label-available branch) | INVALIDATED_TIMING | various | Compute label-available branch metrics at recommended cost; primary failure was timing not cost — note the timing finding is independent |
| 10 | LIQUIDATION_BURST_ENTRY (15m) | INVALIDATED_TIMING | timing failure, cost data exists | Verify cost is not also a confounder |
| 11 | LIQUIDATION_BURST_5M | INVALIDATED_TIMING | timing failure on 5m, cost data exists | Same check |

Re-verdict is **arithmetic**, not new backtests. The diagnostic reports already contain raw metric tables that can be re-evaluated at a different cost constant. Each re-verdict produces a row:

- new_median_net = old_median_net + (old_cost − new_cost)
- whether new_median_net crosses gate at new cost
- whether OTHER gates (PF, controls, sample) still fail independently

If a hypothesis crosses the median-net gate at corrected cost but fails other independent gates, the verdict remains `INVALIDATED` with the failure mode shifted from `cost_sensitivity` to the other gate's failure mode.

### Phase 5: Recommend cost model standardization

Output: a clear recommendation for which cost level should become the **single source of truth** going forward, and what code changes are needed to enforce it. The recommendation must specify:

- The numeric value (e.g., 0.08% round-trip, or 0.06%, etc.)
- Whether it includes a slippage component or is a "fee-only" number
- Where it lives in code (a single constant, imported by both `execution/` and `research_lab/`)
- Migration plan for the 9 research files currently hardcoding `0.0010`
- Migration plan for `execution/paper_execution_engine.py` if value changes
- Backward-compatibility approach for already-stored research reports (no rewrite of historical reports; cost level becomes a metadata field in new reports)

The recommendation does not commit any code. It produces the spec for a follow-up implementation milestone.

## Decision criteria (pre-declared)

The audit succeeds if it produces:

1. A documented authoritative cost value for Binance USDT Futures relevant to this bot's execution profile, with citation/measurement source
2. A recommended single number to use as research default, with rationale
3. Re-verdict for exactly 4 hypotheses (#7, #8, #10, #11) at the corrected cost
4. A migration spec listing every file requiring update with old → new value diff

The audit fails (status `INCONCLUSIVE`) if:

- The execution profile (taker vs maker vs mix) cannot be determined from code and documentation
- Slippage cannot be measured or bounded (would require waiting for more paper fills)
- Public Binance fee schedule diverges from what the production account actually pays (would require reading real `commission` fields from production `trade_log`)

If the audit lands `INCONCLUSIVE`, the next step is data collection (more paper fills, production commission read), not retry.

## Acceptance criteria for the audit document itself

The output document `docs/analysis/COST_MODEL_AUDIT_V1_2026-XX-XX.md` must contain, in order:

- Executive summary (verdict + recommended cost value in one sentence)
- Section 1: Surface inventory (Phase 1 output)
- Section 2: Ground truth (Phase 2 output, with sources cited)
- Section 3: Scenario table (Phase 3 output)
- Section 4: Re-verdicts (Phase 4 output, 4 rows)
- Section 5: Recommendation + migration spec (Phase 5 output)
- Section 6: What this audit does NOT establish (explicit limits)
- Section 7: Follow-up milestones implied (implementation of recommendation, possibly extension of slippage measurement after more paper fills)

## Out of scope

- Slippage measurement beyond what existing 1 closed paper trade + accumulating ETH/SOL fills can provide
- New backtests at corrected cost (only arithmetic re-evaluation of existing reports)
- Funding cost analysis for long-hold strategies (current hypothesis class is mostly intraday)
- Cross-venue cost comparison (Binance only; OANDA cost is a separate concern handled implicitly by OANDA hypotheses already documenting different fees)
- Capital efficiency / margin requirements / liquidation cost (these are sizing concerns, not per-trade cost)
- Tax treatment (not in scope of trading system)

## Dependencies

This audit must NOT begin execution until both of these are true:

1. CONFIG_LINEAGE_RECONCILIATION_V1 closure (A1.deploy + A2 WF complete, audit recorded)
2. At least one of:
   - PAPER_PERFORMANCE_VALIDATION_V2 with ≥10 closed trades per active asset (gives slippage measurement basis), OR
   - Explicit user decision to proceed without per-trade slippage measurement, using public-schedule fee-only ground truth

The first condition prevents working on data from a deployment lineage we don't trust. The second condition acknowledges that slippage measurement may have to be deferred if paper trade frequency remains low.

## Estimated effort

- Phase 1 (inventory): ~30 minutes audit-only
- Phase 2 (ground truth): ~1 hour audit-only (depends on whether real commission read against production DB is available)
- Phase 3 (scenarios): ~30 minutes
- Phase 4 (re-verdicts): ~1 hour audit-only (arithmetic against existing reports)
- Phase 5 (recommendation): ~30 minutes
- Document writeup: ~1 hour

Total: ~4-5 hours of audit work. Zero builder work in this audit; follow-up implementation milestone (Codex/Cascade) for the migration is separate scope, estimated ~1 day.

## Out-of-band note on STOP-with-alternatives discipline

Even if the audit verdict `INCONCLUSIVE`, this audit MUST include the next-step alternatives:

- Slippage data gathering plan (how many paper trades needed, over what window)
- Real-commission read plan (how to query production `trade_log` for commission field if it exists)
- Provisional cost recommendation under uncertainty (lower-bound, upper-bound, midpoint with explicit confidence range)

No bare `INCONCLUSIVE` verdict.

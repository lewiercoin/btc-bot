# Post-Grid Portfolio Plan

Date: 2026-05-12
Context: trial-00095 constrained grid after Campaign V3
Primary audit: `docs/audits/AUDIT_GRID_SEARCH_TRIAL00095_2026-05-12.md`
Roadmap: `docs/ROADMAP_MULTI_SETUP_ARCHITECTURE.md`

## Decision

Keep `optuna-default-v3-trial-00095` as the active PAPER baseline.

Do not promote any constrained-grid candidate. The grid confirmed that sweep-reclaim is already close to its useful parameter boundary. Lowering sweep thresholds increases frequency, but it degrades per-trade edge and introduces blocking safety flags.

Next milestone direction: begin Phase 2 research for a separate `trend_continuation_long` setup. This must remain research-only until the setup independently proves edge and the multi-setup contract exists.

## Grid Result Summary

| Metric | Result |
|---|---:|
| Candidates evaluated | 60 |
| Full-range passes | 12 |
| Walk-forward evaluated | 10 |
| Promotion-qualified | 0 |
| Baseline retained | `trial-00095` / `grid-058` |

| Candidate | Trades | ER | PF | DD | Verdict |
|---|---:|---:|---:|---:|---|
| Baseline / `grid-058` | 271 | 2.129 | 4.662 | 6.51% | Keep active |
| `grid-043` | 463 | 1.727 | 3.636 | 6.13% | Reject: blocking safety flag |
| `grid-037` | 497 | 1.502 | 3.296 | 6.78% | Reject: quality collapse |

The trade-off is not favorable:

- `grid-043`: +71% trades, but ER -18.9% and PF -22.0%.
- `grid-037`: +83% trades, but ER -29.5% and PF -29.3%.
- High-frequency candidates triggered `pnl_sanity_review_required`, treated as a hard rejection criterion.

## Strategic Interpretation

The result is not just a failed parameter search. It is evidence about strategy scope.

Current setup:

- Setup: sweep-reclaim / liquidity hunt.
- Natural context: range, liquidity sweep, stop-run, reclaim.
- Weak context: clean trend continuation.
- Failure mode when loosened: more trades, lower edge, more backtest artifact risk.

Institutional interpretation:

- Sweep-reclaim is a liquidity-response setup. It trades dislocation and reclaim, not directional trend acceptance.
- Clean trend days are structurally different. They are driven by directional participation, pullback absorption, continuation flow, and regime persistence.
- Trying to force a mean-reversion setup to trade trend continuation converts a contextual edge into noise.

Therefore the correct next step is not further loosening. It is setup diversification.

## Portfolio Thesis

The bot should evolve from a single setup into a portfolio of context-specific setups:

| Market structure | Setup role | Current coverage |
|---|---|---|
| Liquidity sweep / reclaim | Fade stop-run and reclaim | Covered by sweep-reclaim |
| Clean uptrend continuation | Join continuation after controlled pullback | Missing |
| Compression breakout | Capture expansion after range compression | Missing |
| Funding/OI unwind | Capture crowded-position relief or liquidation unwind | Missing |
| Mean-reversion extreme | Fade overextension when flow exhaustion appears | Missing |

Each setup must prove edge independently before portfolio integration. No setup may be added to production only because the portfolio has a gap.

## Phase 2 Research Scope

Milestone: `TREND-CONTINUATION-RESEARCH-V1`

Goal: determine whether a deterministic `trend_continuation_long` setup has independent edge in uptrend regimes.

Write scope should remain research-only unless a separate architecture milestone is explicitly opened:

- `research_lab/**`
- `backtest/**` only if needed for isolated research harness support
- `tests/test_research_lab*`
- `docs/**`

No production behavior change in Phase 2:

- Do not modify live execution.
- Do not route trend-continuation signals into the live orchestrator.
- Do not change active `trial-00095` PAPER parameters.
- Do not promote candidate parameters through `settings.py`.

## Candidate Hypothesis

Setup: `trend_continuation_long`

Target context:

- Regime is `uptrend`.
- Price is above long-term trend baseline.
- Trend slope is positive.
- Price performs shallow pullback or controlled retest.
- TFI/CVD confirms continuation after pullback.
- OI/funding context does not show crowded-leverage veto.
- RR passes existing risk gate.

Expected edge:

- Capture continuation days that sweep-reclaim intentionally ignores.
- Improve uptrend regime trade coverage.
- Avoid replacing sweep-reclaim in range/liquidity-reclaim contexts.

## Phase 2 Deliverables

1. Offline research implementation for `trend_continuation_long`.
2. Standalone backtest report for trend-continuation only.
3. Regime-segmented metrics:
   - uptrend
   - range/normal
   - crowded leverage
   - compression
   - downtrend, if applicable
4. Walk-forward validation.
5. Comparison against sweep-reclaim:
   - trade overlap
   - regime coverage
   - per-regime ER/PF/DD
   - whether both setups would request same-cycle entries
6. Claude Code audit and verdict:
   - reject
   - iterate
   - candidate for paper after Phase 2.5 contracts

## Phase 2 Acceptance Criteria

Minimum research gates:

| Gate | Requirement |
|---|---|
| Target regime edge | ER > 1.5 in uptrend regime |
| Trade coverage | materially more uptrend trades than sweep-reclaim |
| Risk | acceptable DD, no uncontrolled range/chop bleed |
| Explainability | every signal has explicit reasons |
| WF | 2/2 windows pass |
| Safety | no blocking safety flags |
| Separation | no live-path side effects |

Soft but important:

- Win rate should remain in a credible range.
- Performance should not depend on one narrow validation window.
- Setup should have a clear institutional market-structure rationale.
- It should improve portfolio coverage, not duplicate sweep-reclaim behavior.

## Phase 2.5 Required Before Production

Even if trend-continuation validates, do not wire it into production until a minimal multi-setup contract exists.

Required contract:

1. `setup_type` is first-class across signal candidate, executable signal, trade log, and metrics.
2. Per-setup `reasons[]` are persisted.
3. Decision outcomes record rejected setup attempts.
4. Candidate pool supports multiple setup candidates per cycle.
5. Arbiter selection is deterministic and auditable.
6. Max-position and conflict rules are explicit.
7. Per-setup performance metrics are queryable.

This prevents trend-continuation from becoming an ad hoc branch inside the current sweep-reclaim signal path.

## Proposed Setup Roadmap

| Phase | Setup / Capability | Purpose |
|---|---|---|
| 1 | Sweep-reclaim stabilization | Keep validated baseline, define limits |
| 2 | Trend-continuation research | Cover clean trend days |
| 2.5 | Multi-setup contracts | Make multiple setups auditable |
| 3 | Arbiter / selector | Deterministic setup conflict resolution |
| 4 | Portfolio evaluation | Measure setup correlation and combined DD |
| 5 | Breakout/compression setup | Cover volatility expansion |
| 6 | Funding/OI unwind setup | Cover crowded-position unwind |
| 7 | Mean-reversion extreme setup | Cover exhaustion reversals |

## Immediate Action List

1. Leave active PAPER deployment on `trial-00095`.
2. Monitor `logs/trial_00095_monitoring.json` until 30-50 trades or 3-4 months, whichever comes first.
3. Open `TREND-CONTINUATION-RESEARCH-V1` as the next research milestone.
4. Build research-only trend-continuation candidate and report.
5. Audit Phase 2 before any production integration.

## Non-Goals

- No manual override to deploy `grid-043` unless the operator explicitly accepts blocking safety flag risk.
- No further sweep-reclaim loosening as a substitute for trend strategy.
- No hidden live-path setup insertion.
- No multi-setup portfolio optimization before each setup has independent evidence.

## Final Position

I agree with Claude Code's grid verdict.

The grid did not just reject candidates. It clarified system design: sweep-reclaim should remain a bounded specialist setup. The next edge should come from additional market-structure-specific setups, beginning with trend continuation, integrated only after research validation and multi-setup architecture contracts.

# Compression Breakout Audit Package

Milestone: `COMPRESSION-BREAKOUT-RESEARCH-V1`  
Builder: Codex  
Branch: `research/compression-breakout-v1`  
Verdict: `ITERATE_REQUIRED`

## Executive Summary

This checkpoint implemented `compression_breakout_long` as a separate research-only setup and ran the full local V3 data range (`2022-01-01` -> `2026-03-29`).

The current strict hypothesis does not qualify for candidate status:

- Full-range trades: `3` (hard gate requires `>= 20`)
- Full-range ER: `-0.298229`
- Profit factor: `0.435318`
- Primary compression-regime trades: `0`
- Breakout follow-through: `1.0`, but from only `3` trades
- Walk-forward: not run due insufficient trade count
- Overlap analysis: not run due insufficient trade count

## Hard Gate Results

| Gate | Requirement | Actual | Result |
|---|---:|---:|---|
| Compression ER | `> 1.5` | `null` | FAIL |
| Breakout follow-through | `>= 50%` | `100%` | PASS, low sample |
| Overlap vs sweep_reclaim | `< 30%` | `not run` | BLOCKED |
| Min trades | `>= 20` | `3` | FAIL |
| Compression trades | `>= 10` | `0` | FAIL |
| Normal secondary ER | `> 0.5` | `-0.298229` | FAIL |
| Walk-forward | `2/2` | `not run` | BLOCKED |
| Safety flags | none blocking | none | PASS |
| Explainability | reasons[] complete | yes | PASS |

## Implementation Notes

- Work is research-only and stayed out of production runtime.
- Scope is long-only because `docs/MILESTONE_TRACKER.md` scopes this milestone to `compression_breakout_long`.
- The setup does not reuse absorption/CVD divergence logic.
- ATR history is attached by the research backtest runner through `snapshot.source_meta["research_atr_4h_norm_history"]`.
- Volatility panic threshold uses the empirical p95 from absorption Iteration A: `0.02885372`.

## Red Flags

- Candidate generation is too sparse: `3 / 148596` cycles.
- No trades occurred in the primary `compression` regime; all 3 trades were in `normal`.
- The 3-trade sample is not statistically valid.
- Secondary-regime ER is negative.

## Recommendation

Do not proceed to Phase 2.5.

Recommended auditor decision: `ITERATE` only if Claude agrees the failure is mainly measurement/scoping related, specifically:

1. verify whether the current `RegimeEngine` labels usable compression as `normal` rather than `compression`;
2. empirically inspect ATR percentile/range-width distributions before any threshold redesign;
3. keep the next attempt to one diagnostic iteration, not parameter rescue.

If the diagnostic iteration still produces `< 20` trades or negative ER, close `COMPRESSION-BREAKOUT-RESEARCH-V1` as failed and move to the next portfolio family.

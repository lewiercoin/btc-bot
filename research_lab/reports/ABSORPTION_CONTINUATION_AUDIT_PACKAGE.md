# Absorption Continuation Audit Package

Milestone: `ABSORPTION-CONTINUATION-RESEARCH-V1`  
Builder: Codex  
Branch: `research/trend-continuation-v1`  
Status: Checkpoint 2 failure analysis  
Verdict: `REJECT`

## Executive Summary

The current `absorption_continuation_long` hypothesis does not qualify for Phase 2.5.

Full local backtest on the V3/grid-compatible dataset completed successfully:

- Source DB: `storage/btc_bot.db`
- Date range: `2022-01-01` to `2026-03-29`
- Decision cycles: `148596`
- Candidates: `4`
- Closed trades: `4`
- Uptrend ER: `0.34088`
- Profit factor: `1.247212`
- Max drawdown: `2.5811%`
- Absorption confirmation hit rate: `0.25`

The setup is far too sparse and does not demonstrate target-regime edge.

## Hard Gate Results

| Gate | Requirement | Actual | Result |
|---|---:|---:|---|
| Uptrend ER | `> 1.5` | `0.34088` | FAIL |
| Uptrend trade coverage | `>= 20` and greater than sweep-reclaim uptrend coverage | `4` | FAIL |
| Trend-day capture | `>= 50%` | Not measured after primary gate failure | FAIL |
| Overlap control | `< 30%` hard gate, `< 20%` preferred | Not measured after primary gate failure | FAIL |
| Range bleed | `> -1.0` or no range trades | No range trades | PASS |
| Walk-forward | `2/2` pass | Not run after primary gate failure | FAIL |
| Safety flags | none blocking | none detected | PASS |
| Explainability | all signals include `reasons[]` | complete | PASS |
| Minimum total trades | `>= 20` | `4` | FAIL |

## Red Flags

| Red Flag | Observation | Action |
|---|---|---|
| Uptrend ER below edge threshold | `0.34088` vs required `> 1.5` | REJECT |
| Absorption confirmation not predictive | `0.25` hit rate | REJECT |
| Sparse signal generation | 4 candidates across 148596 cycles | REJECT |

## Trade Sample

| Timestamp | PnL R | Exit | Pullback Depth | CVD Divergence | TFI | EMA50 Distance ATR |
|---|---:|---|---:|---|---:|---:|
| 2024-10-06T21:45:00Z | `-1.535577` | SL | `0.008215` | true | `0.365961` | `0.036014` |
| 2024-10-28T04:45:00Z | `6.357185` | TIMEOUT | `0.009613` | false | `0.476591` | `0.720070` |
| 2025-06-08T23:30:00Z | `-1.580123` | SL | `0.007959` | false | `0.628765` | `0.715599` |
| 2025-09-17T04:15:00Z | `-1.877966` | SL | `0.005970` | false | `0.546267` | `1.785631` |

The only large winner did not have CVD bullish divergence. The only CVD-divergence trade lost. This directly fails the absorption confirmation thesis.

## Rejection Funnel

Top rejection reasons:

| Reason | Count |
|---|---:|
| volatility_panic | `134649` |
| tfi_below_absorption_threshold | `116244` |
| price_not_above_ema200 | `75428` |
| ema50_not_above_ema200 | `75044` |
| ema200_slope_too_weak | `73648` |
| absorption_not_confirmed | `73163` |
| regime_blocked:downtrend | `60778` |
| pullback_depth_out_of_range | `59214` |
| low_sweep_without_reclaim | `45717` |
| trend_overextended | `38499` |

The filter stack is too restrictive and possibly miscalibrated for ATR-normalized volatility, but the observed accepted trades still do not support the absorption edge.

## Why WF Was Not Run

Walk-forward validation is not useful after the full-range candidate fails primary gates:

- only 4 total trades,
- uptrend ER far below threshold,
- absorption confirmation hit rate below 50%,
- minimum trade coverage fails.

Running WF would add compute cost without changing the verdict. The correct outcome is reject or hypothesis redesign, not parameter rescue.

## 2026-05-11 Limitation

The local V3/grid-compatible replay dataset ends at `2026-03-29`. The specific trend day `2026-05-11` is not available locally and requires a server export or a separate post-V3 backfill milestone.

This limitation does not rescue the current hypothesis because the 2022-2026-03-29 validation already fails hard gates.

## Recommendation

Do not proceed to Phase 2.5 with the current `absorption_continuation_long` definition.

Recommended next decision:

1. `REJECT` current hypothesis as implemented.
2. Decide whether to iterate the hypothesis or switch to the next setup family.
3. If iterating, focus on hypothesis redesign, not broad parameter tuning.

Potential redesign directions:

- replace the crude CVD slope proxy with a real local CVD slope over pullback window,
- recalibrate `atr_4h_norm` panic threshold from empirical distribution,
- separate "pullback to EMA50" from "pullback to equal-low liquidity" cohorts,
- test entry trigger Option B: wait for post-absorption upward turn instead of entering during pullback,
- require winner-like structure discovered from cohort analysis before any new run.

Current result: `REJECT`.

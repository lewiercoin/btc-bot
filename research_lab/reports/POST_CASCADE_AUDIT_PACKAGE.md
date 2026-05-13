# Post Cascade Momentum Audit Package

Milestone: `POST-CASCADE-MOMENTUM-RESEARCH-V1`  
Builder: Codex  
Branch: `research/post-cascade-momentum-v1`  
Verdict: `REJECT_BLOCKED_BY_ABSENT_TARGET_REGIME`

## Executive Summary

Checkpoint 1 implemented research-only `post_cascade_momentum_long` and `post_cascade_momentum_short`, with cascade direction detected from historical force-order lookback rather than real-time force spikes.

The full-range replay used the same research-only backfilled DB created for crowded_unwind:

- Source DB: `research_lab/data/crowded_unwind_backtest.db` (untracked)
- Imported force orders: `146864`
- Date range: `2022-01-01` -> `2026-03-29`
- Decision cycles: `148596`

Result:

- `post_liquidation` cycles: `0`
- Candidates: `0`
- Closed trades: `0`
- Cascade continuation rate: `null`

This means the target regime never occurred in the replay. The setup did not receive a valid edge test.

## Hard Gate Results

| Gate | Requirement | Actual | Result |
|---|---:|---:|---|
| Post-liquidation ER | `> 1.5` | `null` | FAIL |
| Cascade continuation | `>= 60%` | `null` | FAIL |
| Minimum trades | `>= 20` | `0` | FAIL |
| Post-liquidation trades | `>= 10` | `0` | FAIL |
| Overlap vs sweep_reclaim | `< 30%` | not run | BLOCKED |
| Walk-forward | `2/2` | not run | BLOCKED |
| Safety flags | none blocking | none | PASS |
| Explainability | reasons[] complete | yes | PASS |

## Interpretation

This is different from crowded_unwind:

- crowded_unwind had adequate sample after force-order backfill and failed edge validation;
- post_cascade_momentum had no target-regime cycles, so the hypothesis is not empirically tested.

The blocking issue is that current `RegimeEngine` did not emit `post_liquidation` on the V3 replay, even with force-order data present.

## Builder Verdict

`REJECT_BLOCKED_BY_ABSENT_TARGET_REGIME`.

Per handoff, if `post_liquidation` is rare or absent, this requires auditor review before any iteration. A follow-up would need to decide whether the milestone remains valid with a research-only post-cascade detector or whether the setup family should be paused. I did not relax the regime requirement in Checkpoint 1.

# Compression Breakout Iteration A Audit Package

Milestone: `COMPRESSION-BREAKOUT-RESEARCH-V1-ITERATION-A`  
Builder: Codex  
Branch: `research/compression-breakout-v1`  
Verdict: `HYPOTHESIS FAILED`

## Executive Summary

Iteration A tested the regime-classification concern from Claude Code's Checkpoint 1 audit. The diagnostic found that `COMPRESSION` labels are present, but uncommon, and that compression-labeled cycles mostly occur before the breakout trigger. After aligning the evaluator to measure internally detected compression trades, the setup still failed hard gates.

Full-range rerun: `2022-01-01` -> `2026-03-29`

- Total cycles: `148596`
- RegimeEngine `compression` cycles: `2938` (`1.977173%`)
- Closed trades after Iteration A: `3`
- Internal compression closed trades: `3`
- ER: `-0.298229`
- PF: `0.435318`
- Breakout follow-through: `1.0`, but only from `3` trades
- Verdict: `REJECT`

## A1: Regime Distribution

Regime distribution:

| Regime | Count | Percentage |
|---|---:|---:|
| normal | `4199` | `0.02825783` |
| uptrend | `63891` | `0.42996447` |
| downtrend | `63598` | `0.42799268` |
| compression | `2938` | `0.01977173` |
| crowded_leverage | `13970` | `0.0940133` |
| post_liquidation | `0` | `0.0` |

Interpretation: compression labels are not absent. The issue is that compression regime describes the coiling state, while the executable breakout trigger usually appears after that state has begun to transition.

## A2: Regime As Veto

The setup now documents and reports regime as a veto/context layer:

- internal compression detection remains primary: ATR percentile, range width, duration, breakout trigger;
- regime blocks uptrend, downtrend, crowded leverage, and post-liquidation;
- generated candidates include `regime_veto=allowed` and `internal_compression_detected=True` in reasons[].

This did not materially increase the executable sample because Checkpoint 1 already allowed `normal` and `compression`, which are the only non-blocked regimes available in the current enum.

## Compression Rejection Analysis

Compression-labeled cycles generated very few accepted structure events:

- compression cycles: `2938`
- accepted structure events in compression-labeled cycles: `7`
- primary blockers:
  - `breakout_too_small`: `2862`
  - `no_breakout_detected`: `2856`
  - `tfi_below_breakout_threshold`: `2180`
  - `range_width_not_compressed`: `1907`

This means the setup is not primarily blocked by missing `COMPRESSION` labels. It is blocked because most compression-labeled cycles have not broken out.

## Hard Gate Results

| Gate | Requirement | Actual | Result |
|---|---:|---:|---|
| Internal compression ER | `> 1.5` | `-0.298229` | FAIL |
| Breakout follow-through | `>= 40%` | `100%` | PASS, invalid sample |
| Minimum trades | `>= 20` | `3` | FAIL |
| Internal compression trades | `>= 10` | `3` | FAIL |
| Win rate | `> 35%` | low sample / review | FAIL by sample quality |
| WF | required only after sample gate | not run | BLOCKED |
| Overlap | required only after sample gate | not run | BLOCKED |
| Explainability | reasons[] complete | yes | PASS |

## Verdict

`COMPRESSION-BREAKOUT-RESEARCH-V1` should be closed as `HYPOTHESIS FAILED` for the current long-only formulation.

The one diagnostic iteration did not expose a viable sample or positive expectancy. Per the handoff hard stop, no further parameter rescue is recommended. The next portfolio family should be `crowded_unwind` unless the user chooses to pause portfolio research.

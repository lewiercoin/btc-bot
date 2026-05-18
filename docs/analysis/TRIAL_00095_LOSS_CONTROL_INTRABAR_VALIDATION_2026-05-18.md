# Trial-00095 Loss-Control Intrabar Validation

**Milestone:** `TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION_V1`
**Status:** READY_FOR_AUDIT
**Builder verdict:** `FAIL_NO_ROBUST_IMPROVEMENT`
**Scope:** Research Lab offline validation only; frozen trial-00095 entries; no runtime/core changes.

## Methodology

- Replays trial-00095 exact parameters to freeze baseline entries and original entry/stop geometry.
- Applies predeclared loss-side hard stops to the same frozen entries only.
- If a loss-control threshold is touched on any post-entry 15m candle before the original baseline close, the variant exits there.
- The entry candle itself is excluded because BacktestRunner opens the position after close checks for that snapshot.
- If the threshold is not touched, the original baseline trade outcome is preserved, including winner tail behavior.
- This does not add entries, change entry filters, cap winners, alter TP logic, or approve deployment.
- Intrabar assumption is conservative: a touched loss-control threshold is treated as executable before any later recovery inside the same candle.

## Baseline Control

- Frozen replay entries: 274
- Prior diagnostic artifact entries: 274
- Baseline artifact count match: 1
- Baseline ER: 2.121
- Baseline PF: 4.22
- Baseline max DD: 14.68R

## Variant Results

| Variant | Gate Verdict | Trades | ER | Delta ER | Delta % | PF | DD Ratio | Triggered | Saved Losers | Stopped Winners | Folds+ | 2x ER | Missing Candles |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `BASELINE_REPLAY` | `MARGINAL` | 274 | 2.121 | +0.000 | +0.0% | 4.22 | 1.00 | 0 | 0 | 0 | 0/9 | 0.774 | 0 |
| `HARD_STOP_0_90R` | `MARGINAL` | 274 | 1.679 | -0.442 | -20.8% | 3.14 | 1.01 | 128 | 13 | 19 | 0/9 | 0.640 | 0 |
| `HARD_STOP_1_00R` | `MARGINAL` | 274 | 1.664 | -0.457 | -21.5% | 3.02 | 1.06 | 126 | 1 | 18 | 0/9 | 0.620 | 0 |
| `HARD_STOP_1_10R` | `MARGINAL` | 274 | 1.639 | -0.482 | -22.7% | 2.91 | 1.12 | 121 | 0 | 17 | 0/9 | 0.583 | 0 |
| `HARD_STOP_0_75R` | `MARGINAL` | 274 | 1.637 | -0.484 | -22.8% | 3.23 | 0.93 | 134 | 111 | 23 | 2/9 | 0.612 | 0 |

## Builder Interpretation

Best loss-control variant by paired delta ER: `HARD_STOP_0_90R`.
The executable intrabar validation does not provide robust enough evidence to continue toward exit-policy design.

## Audit Questions

1. Does baseline replay faithfully reconstruct trial-00095 entry count and entry/stop geometry?
2. Are entries frozen before variants are applied?
3. Is R computed from original entry/stop distance rather than realized loss?
4. Does each variant preserve baseline winners unless the loss threshold was touched first?
5. Are missing candles reported explicitly and treated as blocking if present?
6. Are all artifacts Research Lab/docs only with no runtime/core/settings changes?
7. Does the report avoid calling the result deployment-ready?

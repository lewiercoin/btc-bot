# PAPER_FREQUENCY_RECALIBRATION_V1 - Variant B Stability Check

## Scope

Offline net-cost stability check for threshold Variant B:
- BTC threshold `0.0055`
- ETH threshold `0.0065`
- SOL threshold `0.0065`

No production settings changes.

## Q1 Per-Symbol Result

| Symbol | Trades | Net ER | Net PnL R | Net PF | Max DD |
|---|---:|---:|---:|---:|---:|
| BTCUSDT | 6 | -0.171 | -1.03R | 0.76 | 1.08% |
| ETHUSDT | 11 | +0.154 | +1.70R | 0.94 | 1.89% |
| SOLUSDT | 10 | +2.016 | +20.16R | 3.99 | 0.69% |

Variant B is not a balanced multi-asset improvement. BTC is net negative, ETH
is not economically convincing after costs, and the entire edge is SOL.

## SOL Monthly Stability

| Month | Trades | Net ER | Net PnL R | Net PF | Max DD |
|---|---:|---:|---:|---:|---:|
| 2026-01 | 10 | +2.016 | +20.16R | 3.99 | 0.69% |
| 2026-02 | 3 | -1.574 | -4.72R | 0.00 | 0.82% |
| 2026-03 | 2 | -1.685 | -3.37R | 0.00 | 0.48% |

SOL Variant B is a January-only cluster. It fails the non-negative-month gate
and does not demonstrate stable behavior across Q1.

## Decision

`NO RECALIBRATION`.

Variant B had the best headline Q1 result in the threshold sweep, but the
stability check rejects it:
- not robust across symbols
- not robust across months
- dominated by one SOL cluster in January
- February and March are both net negative for isolated SOL

## Next Step

Do not lower production thresholds globally.

The useful operational conclusion is narrower:
- current production thresholding is too selective for quiet markets
- naive threshold lowering adds unstable, cluster-dependent exposure
- any future candidate must be validated on net costs with monthly stability
  before PAPER settings change

Recommended next research direction: regime/session-conditioned frequency
work, not global depth-threshold relaxation.

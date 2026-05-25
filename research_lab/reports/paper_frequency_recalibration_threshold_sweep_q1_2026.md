# PAPER_FREQUENCY_RECALIBRATION_V1 - Threshold Sweep Q1 2026

## Scope

Offline runtime-parity net-cost threshold sweep. No production settings changes.

Production profile:
- `--settings-profile live`
- runtime overlay copied from production `settings.json`
- costs enabled: taker entry `0.05%`, maker exit `0.02%`,
  slippage `3 bps` per side, funding from DB/fallback

Variants:

| Variant | BTC threshold | ETH threshold | SOL threshold |
|---|---:|---:|---:|
| Baseline | 0.00649 | 0.0075 | 0.0075 |
| A | 0.0060 | 0.0070 | 0.0070 |
| B | 0.0055 | 0.0065 | 0.0065 |
| C | 0.0050 | 0.0060 | 0.0060 |

## Net Results

| Variant | Trades | Net ER | Net PnL R | Net PF | Max DD | Cost R |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 22 | +0.400 | +8.79R | 1.20 | 3.31% | 14.08R |
| A | 29 | +0.533 | +15.46R | 1.35 | 3.51% | 18.76R |
| B | 27 | +0.767 | +20.72R | 1.56 | 2.38% | 17.44R |
| C | 27 | +0.765 | +20.67R | 1.56 | 2.37% | 17.49R |

Variant B is the best headline result. C adds no economic improvement over B
and creates more candidates plus more governance/portfolio pressure.

## Monthly Stability

| Variant | January | February | March |
|---|---:|---:|---:|
| Baseline | +24.58R | -14.10R | -1.69R |
| A | +36.25R | -15.73R | -5.05R |
| B | +34.80R | -14.09R | n/a |
| C | +34.80R | -14.14R | n/a |

All tested variants fail the negative-month gate. The improvement comes from
increasing January gains, not from creating stable quarter-wide behavior.

## Symbol Stability

| Variant | BTC | ETH | SOL |
|---|---:|---:|---:|
| Baseline | -5.05R | -2.33R | +16.17R |
| A | -4.99R | +1.58R | +18.88R |
| B | -1.03R | +1.58R | +20.16R |
| C | -1.03R | +1.53R | +20.16R |

This contradicts the earlier gross/research-profile attribution where BTC was
the cleanest source of edge. Under production live profile plus net costs, the
threshold sweep is dominated by SOL. That makes direct recalibration risky.

## Concentration Risk

Top-week contribution:
- Baseline: top week +17.50R, greater than total quarter PnL
- A: top week +21.84R, 141% of total PnL
- B: top week +20.15R, 97% of total PnL
- C: top week +20.15R, 98% of total PnL

All variants fail the concentration gate. The result is too dependent on one
profitable January cluster.

## Decision

No threshold variant is deployment-ready.

Variant B is the only useful research lead:
- improves net ER from `+0.400R` to `+0.767R`
- improves net PF from `1.20` to `1.56`
- lowers DD from `3.31%` to `2.38%`

But B fails:
- negative February
- one-week dependency
- SOL-dominated profitability

## Next Step

Do not deploy threshold recalibration globally.

Next research should isolate why production-profile net edge is SOL/January
dominated:
- rerun B per symbol and BTC+ETH-only
- test B on later out-of-sample data if available
- require non-negative monthly net PnL before any PAPER settings change

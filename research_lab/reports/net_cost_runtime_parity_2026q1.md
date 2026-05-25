# Net-Cost Runtime-Parity Baseline Q1 2026

## Scope

Offline parity backtest with production `settings.json` loaded through
`--settings-profile live`. No runtime or production settings changes.

Source artifact:
- `validation/runtime_parity_2026q1_prodconfig_live_w0_netcost.json`

Cost assumptions:
- entry fee: taker `0.05%`
- exit fee: maker `0.02%`
- slippage: `3 bps` per side
- funding: historical funding table when available, otherwise fallback
  `0.01%` per 8h funding period

## Result

| Metric | Gross | Net |
|---|---:|---:|
| Trades | 22 | 22 |
| Expectancy R | +1.040 | +0.400 |
| PnL R | +22.87R | +8.79R |
| Profit factor | 2.20 | 1.20 |
| Max DD | 2.07% | 3.31% |

Cost breakdown:
- fees: `11.5594`
- slippage: `9.9141`
- funding: `0.1061`
- total cost: `21.5795`
- total cost in R: `14.0785R`

## Interpretation

The production W0 edge survives costs, but only narrowly. Costs consume about
`14.08R` over 22 trades and reduce profit factor from `2.20` to `1.20`.
The net model feeds cost-adjusted PnL into the parity runtime state, so
governance can differ from gross-only replay after cost-adjusted losses.

This materially changes the frequency-recalibration decision. Lowering sweep
thresholds may increase trade count, but any additional trades must clear a
high cost hurdle. Gross-only recalibration is not acceptable.

## Decision

Proceed to `PAPER_FREQUENCY_RECALIBRATION_V1` only on net metrics.

Candidate gates should use net results:
- net expectancy must remain positive
- net profit factor must improve materially above `1.20`
- net drawdown must not expand disproportionately
- added trades must not come primarily from SOL or shallow noisy sweeps

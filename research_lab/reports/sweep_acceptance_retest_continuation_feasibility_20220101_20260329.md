# Sweep Acceptance Retest Continuation Feasibility

Research-only checkpoint for `acceptance -> retest -> hold -> second impulse` after a sweep without reclaim.

## Method

- Symbol: `BTCUSDT`
- Timeframe: `15m`
- Date range: `2022-01-01` to `2026-03-29`
- Candles loaded: `148595`
- TFI buckets loaded: `148402`
- Costs: taker entry, maker exit, 3 bps slippage per side; funding excluded in this first pass.

## Results

| Config | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R | Avg Cost R | Max DD R | Acceptance | Retest+Impulse |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `SARC_LIVE_8B` | 682 | -0.1105 | -75.36 | 0.83 | 36.51% | -1.0470 | 0.1300 | 92.96 | 2502 | 682 |
| `SARC_LIVE_12B` | 776 | -0.1104 | -85.70 | 0.83 | 36.47% | -1.0478 | 0.1355 | 96.59 | 2379 | 776 |
| `SARC_LIVE_LONG_8B` | 355 | -0.1309 | -46.45 | 0.80 | 36.90% | -1.0543 | 0.1275 | 56.96 | 1334 | 355 |
| `SARC_LIVE_LONG_TFI_8B` | 185 | -0.0836 | -15.46 | 0.87 | 39.46% | -1.0491 | 0.1309 | 30.60 | 1031 | 185 |
| `SARC_NEARMISS_8B` | 1328 | -0.1384 | -183.73 | 0.79 | 36.14% | -1.0748 | 0.1524 | 184.36 | 4402 | 1328 |
| `SARC_NEARMISS_LONG_8B` | 750 | -0.1115 | -83.64 | 0.83 | 37.87% | -1.0656 | 0.1544 | 87.49 | 2475 | 750 |
| `SARC_STRICT_HOLD_LONG` | 180 | -0.0783 | -14.09 | 0.87 | 40.00% | -1.0484 | 0.1303 | 30.38 | 1033 | 180 |
| `SARC_WIDE_RETEST_LONG` | 463 | -0.1308 | -60.56 | 0.79 | 36.29% | -1.0467 | 0.1293 | 66.98 | 1248 | 463 |

## Best Variant Direction Split: `SARC_STRICT_HOLD_LONG`

| Direction | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R |
|---|---:|---:|---:|---:|---:|---:|
| `LONG` | 180 | -0.0783 | -14.09 | 0.87 | 40.00% | -1.0484 |

## Interpretation

- This is stricter than simple no-reclaim continuation: it waits for market acceptance to be retested and confirmed by a second impulse.
- If this remains negative, the 2026-05-25 BTC move should be treated as an understandable miss, not a reason to weaken sweep-reclaim.
- Promotion would require multi-asset net-cost parity and walk-forward validation.

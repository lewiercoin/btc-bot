# Sweep Acceptance Continuation Feasibility

Research-only checkpoint for the missing setup observed in production: sweep without reclaim followed by acceptance beyond the swept level.

## Method

- Symbol: `BTCUSDT`
- Timeframe: `15m`
- Date range: `2022-01-01` to `2026-03-29`
- Candles loaded: `148595`
- TFI buckets loaded: `148402`
- Costs: taker entry, maker exit, 3 bps slippage per side; funding excluded in this first pass.

## Results

| Config | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R | Avg Cost R | Max DD R | Candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `SAC_LIVE_DEPTH_NEXT_OPEN` | 1941 | -0.0808 | -156.88 | 0.87 | 37.82% | -1.0632 | 0.1340 | 159.10 | 1941 |
| `SAC_LIVE_DEPTH_PULLBACK_HOLD` | 1302 | -0.2100 | -273.36 | 0.73 | 34.79% | -1.1280 | 0.2132 | 276.69 | 1302 |
| `SAC_NEARMISS_NEXT_OPEN` | 3322 | -0.1094 | -363.55 | 0.84 | 37.18% | -1.1031 | 0.1721 | 365.28 | 3322 |
| `SAC_NEARMISS_PULLBACK_HOLD` | 2525 | -0.2502 | -631.64 | 0.69 | 34.34% | -1.1532 | 0.2539 | 633.64 | 2525 |
| `SAC_NEARMISS_TFI_PULLBACK` | 928 | -0.3480 | -322.96 | 0.60 | 31.57% | -1.1878 | 0.2838 | 323.93 | 928 |
| `SAC_LIVE_DEPTH_LONG_ONLY` | 1092 | -0.0498 | -54.43 | 0.92 | 39.29% | -1.0521 | 0.1349 | 59.11 | 1092 |
| `SAC_LIVE_DEPTH_LONG_TFI` | 462 | -0.1379 | -63.72 | 0.78 | 35.71% | -0.7782 | 0.1291 | 69.18 | 462 |
| `SAC_STRICT_TFI_PULLBACK` | 402 | -0.3103 | -124.76 | 0.65 | 27.86% | -1.1688 | 0.2446 | 128.00 | 402 |

## Best Variant Direction Split: `SAC_LIVE_DEPTH_LONG_ONLY`

| Direction | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R |
|---|---:|---:|---:|---:|---:|---:|
| `LONG` | 1092 | -0.0498 | -54.43 | 0.92 | 39.29% | -1.0521 |

## Interpretation

- This is a different setup from sweep-reclaim. It treats failure to reclaim as acceptance, not as a false breakout.
- Immediate entries and pullback-hold entries are separated because impulse closes often retrace before any continuation.
- This checkpoint is a feasibility screen only. Promotion would require multi-asset, net-cost parity and walk-forward validation.

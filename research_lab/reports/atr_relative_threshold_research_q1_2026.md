# ATR Relative Threshold Research Q1 2026

Research-only runtime-parity net-cost sweep. No production settings changes.

Completed variants: `20` of planned `21`.

Formula:

`threshold = clamp(atr_4h_norm * multiplier, floor, ceiling)`

## Gates

- net ER >= baseline `+0.400R`
- net PF >= `1.30`
- no negative month in Q1
- BTC net PnL not negative
- not SOL dominated
- top week <= 40% of total PnL
- trade count between 40 and 100

## Results

| Variant | Symbols | Mode | M | Floor | Ceiling | Trades | Net ER | Net PnL R | Net PF | Gates |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `BASELINE_FULL` | BTCUSDT,ETHUSDT,SOLUSDT | `fixed` |  |  |  | 24 | 0.6955 | 16.69 | 1.54 | FAIL |
| `BASELINE_BTC_ETH` | BTCUSDT,ETHUSDT | `fixed` |  |  |  | 14 | -0.2479 | -3.47 | 0.72 | FAIL |
| `BASELINE_BTC` | BTCUSDT | `fixed` |  |  |  | 3 | -1.6837 | -5.05 | 0.00 | FAIL |
| `ATR4H_BTC_M02_F00025_C00075` | BTCUSDT | `atr_4h_relative` | 0.2 | 0.0025 | 0.0075 | 13 | 1.1555 | 15.02 | 2.27 | FAIL |
| `ATR4H_BTC_M02_F0003_C00075` | BTCUSDT | `atr_4h_relative` | 0.2 | 0.003 | 0.0075 | 12 | 1.6403 | 19.68 | 3.34 | FAIL |
| `ATR4H_BTC_M025_F00025_C00075` | BTCUSDT | `atr_4h_relative` | 0.25 | 0.0025 | 0.0075 | 15 | 1.1518 | 17.28 | 2.14 | FAIL |
| `ATR4H_BTC_M025_F0003_C00075` | BTCUSDT | `atr_4h_relative` | 0.25 | 0.003 | 0.0075 | 13 | 1.4078 | 18.30 | 2.58 | FAIL |
| `ATR4H_BTC_M03_F00025_C00075` | BTCUSDT | `atr_4h_relative` | 0.3 | 0.0025 | 0.0075 | 13 | 1.4078 | 18.30 | 2.58 | FAIL |
| `ATR4H_BTC_M03_F0003_C00075` | BTCUSDT | `atr_4h_relative` | 0.3 | 0.003 | 0.0075 | 12 | 1.6654 | 19.98 | 3.05 | FAIL |
| `ATR4H_BTC_ETH_M02_F00025_C00075` | BTCUSDT,ETHUSDT | `atr_4h_relative` | 0.2 | 0.0025 | 0.0075 | 31 | 1.3448 | 41.69 | 2.64 | FAIL |
| `ATR4H_BTC_ETH_M02_F0003_C00075` | BTCUSDT,ETHUSDT | `atr_4h_relative` | 0.2 | 0.003 | 0.0075 | 29 | 1.6581 | 48.09 | 3.38 | FAIL |
| `ATR4H_BTC_ETH_M025_F00025_C00075` | BTCUSDT,ETHUSDT | `atr_4h_relative` | 0.25 | 0.0025 | 0.0075 | 32 | 1.1542 | 36.93 | 2.29 | FAIL |
| `ATR4H_BTC_ETH_M025_F0003_C00075` | BTCUSDT,ETHUSDT | `atr_4h_relative` | 0.25 | 0.003 | 0.0075 | 30 | 1.2653 | 37.96 | 2.51 | FAIL |
| `ATR4H_BTC_ETH_M03_F00025_C00075` | BTCUSDT,ETHUSDT | `atr_4h_relative` | 0.3 | 0.0025 | 0.0075 | 31 | 1.0893 | 33.77 | 2.04 | FAIL |
| `ATR4H_BTC_ETH_M03_F0003_C00075` | BTCUSDT,ETHUSDT | `atr_4h_relative` | 0.3 | 0.003 | 0.0075 | 30 | 1.1818 | 35.45 | 2.17 | FAIL |
| `ATR4H_FULL_M02_F00025_C00075` | BTCUSDT,ETHUSDT,SOLUSDT | `atr_4h_relative` | 0.2 | 0.0025 | 0.0075 | 47 | 1.0846 | 50.98 | 2.27 | FAIL |
| `ATR4H_FULL_M02_F0003_C00075` | BTCUSDT,ETHUSDT,SOLUSDT | `atr_4h_relative` | 0.2 | 0.003 | 0.0075 | 44 | 1.3423 | 59.06 | 2.67 | FAIL |
| `ATR4H_FULL_M025_F00025_C00075` | BTCUSDT,ETHUSDT,SOLUSDT | `atr_4h_relative` | 0.25 | 0.0025 | 0.0075 | 41 | 1.3857 | 56.81 | 2.70 | FAIL |
| `ATR4H_FULL_M025_F0003_C00075` | BTCUSDT,ETHUSDT,SOLUSDT | `atr_4h_relative` | 0.25 | 0.003 | 0.0075 | 39 | 1.4830 | 57.84 | 2.93 | FAIL |
| `ATR4H_FULL_M03_F00025_C00075` | BTCUSDT,ETHUSDT,SOLUSDT | `atr_4h_relative` | 0.3 | 0.0025 | 0.0075 | 41 | 1.3154 | 53.93 | 2.41 | FAIL |

## Verdict

- Passing variants: `0`
- Best headline variant: `ATR4H_BTC_M03_F0003_C00075` with ER `1.6654` and PF `3.05`.
- Most common failed gates: `no_negative_month=20, trade_count_40_100=16, no_one_week_dependency=7, btc_not_negative=3`.
- No variant is deployment-ready under the predefined gates.

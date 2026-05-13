# Regime Transition Distribution

This report measures whether RegimeEngine transitions are stable enough for 15m state-transition entries.

- Replay cycles: 148596
- Total transitions: 1209
- Quick flip transitions: 288
- Whipsaw rate: 23.82%
- Run length median: 19.0 cycles
- Run length p95: 618.0 cycles

## Transition Pairs

| Pair | Count |
|---|---:|
| downtrend->crowded_leverage | 282 |
| crowded_leverage->downtrend | 280 |
| uptrend->crowded_leverage | 240 |
| crowded_leverage->uptrend | 239 |
| normal->downtrend | 36 |
| downtrend->normal | 34 |
| normal->uptrend | 30 |
| uptrend->normal | 29 |
| crowded_leverage->normal | 21 |
| normal->crowded_leverage | 18 |

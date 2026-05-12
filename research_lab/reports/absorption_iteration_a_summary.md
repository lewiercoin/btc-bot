# Absorption Continuation Iteration A Summary

Iteration A fixed two measurement issues:

- CVD absorption is now calculated from pullback-window CVD slope.
- Volatility panic threshold is now empirical p95 of `atr_4h_norm`, `0.02885372`.

Result:

| Metric | Value |
|---|---:|
| Candidates | `29` |
| Closed trades | `25` |
| Uptrend ER | `-0.480095` |
| PF | `0.554871` |
| Win rate | `0.24` |
| Absorption hit rate | `0.24` |

Verdict: `HYPOTHESIS FAILED`.

Recommendation: stop absorption-continuation work under this milestone and move to `compression_breakout`.

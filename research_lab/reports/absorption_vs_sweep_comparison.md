# Absorption vs Sweep-Reclaim Comparison

Milestone: `ABSORPTION-CONTINUATION-RESEARCH-V1`

## Summary

The current absorption-continuation setup does not yet qualify for a meaningful portfolio comparison against sweep-reclaim.

Primary reason: absorption-continuation produced only 4 closed trades on the full V3/grid-compatible range (`2022-01-01` to `2026-03-29`) and failed hard gates before overlap analysis became decision-useful.

## Absorption-Continuation Result

| Metric | Value |
|---|---:|
| Trades | `4` |
| Uptrend ER | `0.34088` |
| Profit factor | `1.247212` |
| Max drawdown pct | `0.025811` |
| Win rate | `0.25` |
| Absorption confirmation hit rate | `0.25` |

## Sweep-Reclaim Baseline Context

Trial-00095 / grid baseline remains the active PAPER sweep-reclaim baseline.

Known grid baseline facts:

| Metric | Value |
|---|---:|
| Trades | `271` |
| ER | `2.1294` |
| PF | `4.6625` |
| DD | `6.51%` |

## Comparison Verdict

Absorption-continuation currently does not add enough validated trend coverage:

- trade count is too low,
- uptrend ER fails,
- absorption confirmation is not predictive,
- hard gates fail before overlap can support promotion.

No Phase 2.5 candidate should be created from this result.

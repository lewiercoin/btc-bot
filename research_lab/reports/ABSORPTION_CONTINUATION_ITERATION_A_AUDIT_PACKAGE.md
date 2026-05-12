# Absorption Continuation Iteration A Audit Package

Milestone: `ABSORPTION-CONTINUATION-RESEARCH-V1-ITERATION-A`  
Builder: Codex  
Branch: `research/trend-continuation-v1`  
Verdict: `HYPOTHESIS FAILED`  
Recommendation: move to `compression_breakout` research.

## Scope

Iteration A was explicitly limited to two measurement fixes:

1. Replace precomputed `cvd_bullish_divergence` as the absorption gate with CVD slope over the research pullback window.
2. Replace arbitrary `atr_4h_norm > 0.008` panic threshold with an empirical threshold from the 2022-2026 V3/grid-compatible dataset.

No production files were changed. No grid search or parameter rescue was performed.

## A2 ATR Distribution

Source: `storage/btc_bot.db`  
Date range: `2022-01-01` to `2026-03-29`  
Samples: `148596`

| Metric | Value |
|---|---:|
| mean | `0.01552085` |
| p50 | `0.01413720` |
| p75 | `0.01850282` |
| p90 | `0.02471642` |
| p95 | `0.02885372` |
| p99 | `0.04294251` |
| max | `0.06587039` |

Chosen threshold: `p95 = 0.02885372`.

This confirmed the previous `0.008` threshold was miscalibrated because it was below the median and rejected normal BTC volatility.

## Backtest Result After A1 + A2

Source DB: `storage/btc_bot.db`  
Date range: `2022-01-01` to `2026-03-29`

| Metric | Result | Gate |
|---|---:|---:|
| Decision cycles | `148596` | - |
| Candidates | `29` | - |
| Closed trades | `25` | `>= 20` PASS |
| Uptrend ER | `-0.480095` | `> 1.5` FAIL |
| Profit factor | `0.554871` | - |
| Win rate | `0.24` | `> 0.40` FAIL |
| Max drawdown | `0.106361` | - |
| Absorption hit rate | `0.24` | `> 0.50` FAIL |
| Sharpe | `-4.588025` | - |

## Rejection Funnel Change

The empirical volatility threshold fixed the sparsity problem caused by volatility gating:

| Rejection Reason | Checkpoint 2 | Iteration A |
|---|---:|---:|
| `volatility_panic` | `134649` | `7431` |

But the edge did not appear after the measurement fix. Trade count became statistically usable, and performance got worse.

## Absorption Thesis Check

Iteration A uses CVD slope over the pullback-window history attached by the research backtest runner. The final sample still failed:

- closed trades: `25`
- wins: `6`
- losses: `19`
- absorption hit rate: `0.24`
- CVD divergence wins: `0`
- CVD divergence total: `4`

Average feature cohorts:

| Feature | Winners Avg | Losers Avg |
|---|---:|---:|
| pullback depth pct | `0.010728` | `0.008671` |
| price near EMA50 ATR | `0.913033` | `0.728932` |
| TFI 60s | `0.486839` | `0.507784` |
| OI delta pct | `0.000426` | `0.000196` |

TFI was not stronger in winners. CVD divergence remained non-predictive. The setup still does not identify controlled absorption.

## Hard Stop Decision

The handoff required stopping if any of these remained true:

- trades `< 20`,
- uptrend ER `< 1.5`,
- absorption hit rate `< 50%`,
- win rate `< 40%`.

Iteration A passed only the trade-count requirement. It failed ER, hit rate, and win-rate requirements.

Therefore the correct result is:

```text
HYPOTHESIS FAILED
```

No further absorption-continuation iterations should be attempted under this milestone.

## Why WF/Overlap Were Not Run

WF and overlap are only decision-useful after the setup passes primary edge gates. Here:

- uptrend ER is negative,
- PF is below 1,
- hit rate is below 50%,
- win rate is below 40%.

Running WF would only add compute cost to confirm an already failed hypothesis.

## Recommendation

Move to the next setup family: `compression_breakout`.

Reason:

- current trend-pullback absorption did not show edge after measurement fixes,
- CVD/TFI absorption remained non-predictive,
- volatility threshold was fixed and did not rescue the hypothesis,
- compression breakout has a more objective structure: volatility contraction to expansion.

Recommended next milestone:

```text
COMPRESSION-BREAKOUT-RESEARCH-V1
```

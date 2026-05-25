# Runtime-Parity W0 Edge Attribution Q1 2026

## Scope

Offline Research Lab diagnostic only. No runtime, execution, or production
settings changes.

Source runs:
- `validation/runtime_parity_2026q1_w0.json`
- `validation/runtime_parity_2026q1_w0_btc_eth.json`
- `research_lab/analysis_output/runtime_parity_2026q1_w0_attribution.json`
- `research_lab/analysis_output/runtime_parity_2026q1_w0_btc_eth_attribution.json`

Important limitation: runtime-parity harness currently uses zero fees, zero
slippage, and zero funding. Results are hypothesis-screening evidence, not
promotion-grade performance.

Production-frequency follow-up on 2026-05-25 found that exact production
comparisons must run the parity harness with `--settings-profile live` and the
runtime overlay from production `settings.json`. The live profile is materially
more selective than the research profile, with production thresholds
`BTC=0.00649` and `ETH/SOL=0.0075`.

## Baseline W0 Q1

| Scope | Candidates | Trades | ER | PnL R | PF | Win rate | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTC+ETH+SOL | 232 | 63 | +0.985 | +62.05R | 3.07 | 52.4% | 1.14% |
| BTC+ETH only | 145 | 56 | +1.101 | +61.68R | 3.47 | 55.4% | 1.14% |

BTC+ETH only keeps almost all PnL with fewer trades and better quality. SOL
should not be part of the first global refinement search unless later windows
show a different result.

## Symbol Attribution

| Symbol | Trades | ER | PnL R | PF | Median R | MFE/MAE |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 27 | +1.573 | +42.48R | 5.72 | +2.38R | 5.23 |
| ETHUSDT | 29 | +0.662 | +19.21R | 2.20 | -1.00R | 1.90 |
| SOLUSDT | 7 | +0.052 | +0.36R | 1.07 | -1.00R | 1.56 |

BTC is the cleanest edge. ETH contributes, but with a loss-heavy median. SOL is
not decision-grade in this Q1 sample.

## Time Attribution

| Month | Trades | ER | PnL R | PF | Median R |
|---|---:|---:|---:|---:|---:|
| 2026-01 | 27 | +0.682 | +18.41R | 2.31 | -1.00R |
| 2026-02 | 18 | +0.984 | +17.71R | 2.77 | -1.00R |
| 2026-03 | 18 | +1.440 | +25.93R | 5.32 | +2.33R |

The edge is profitable in all three months, but March is materially cleaner.
Any Optuna candidate must avoid simply overfitting to March.

| Session UTC | Trades | ER | PnL R | PF | Median R |
|---|---:|---:|---:|---:|---:|
| US 13-21 | 38 | +1.131 | +42.97R | 3.69 | +1.33R |
| Late 21-24 | 7 | +1.338 | +9.36R | 4.12 | +2.33R |
| Asia 00-08 | 14 | +0.349 | +4.89R | 1.54 | -1.00R |
| EU 08-13 | 4 | +1.206 | +4.83R | 3.41 | +1.09R |

US session is the only session with both material sample and strong quality.
Asia is weak despite positive total PnL.

## Setup Attribution

| Dimension | Bucket | Trades | ER | PnL R | PF | Median R |
|---|---|---:|---:|---:|---:|---:|
| Sweep side | HIGH | 42 | +1.185 | +49.78R | 3.93 | +1.33R |
| Sweep side | LOW | 21 | +0.584 | +12.27R | 1.94 | -1.00R |
| Sweep depth | 0.25-0.50% | 42 | +0.746 | +31.34R | 2.42 | -1.00R |
| Sweep depth | 0.50-1.00% | 19 | +1.428 | +27.13R | 4.88 | +2.34R |
| Regime | downtrend | 29 | +1.126 | +32.65R | 3.18 | -1.00R |
| Regime | uptrend | 31 | +0.967 | +29.98R | 3.31 | +0.61R |
| Regime | crowded_leverage | 3 | -0.196 | -0.59R | 0.71 | -1.00R |

The strongest interpretable quality filters are deeper sweeps and HIGH-side
sweeps. Crowded leverage is too small and negative in this sample.

## Decision

Do not promote delayed reclaim. Do not start broad Optuna.

Next research step should be a small W0 refinement search with strict
anti-overfit gates. The first search should focus on selectivity, not signal
count.

Recommended first-stage search constraints:
- baseline benchmark: W0 BTC+ETH+SOL and BTC+ETH-only reports above
- primary symbols: BTC+ETH, with SOL as a diagnostic mask only
- no delayed reclaim window
- no TP/SL redesign
- no per-regime parameter explosion
- no min-trades relaxation

Recommended first-stage parameters:
- `min_sweep_depth_pct`
- `confluence_min`
- `reclaim_buf_atr`
- `wick_min_atr`
- `duplicate_level_tolerance_pct`
- `max_trades_per_day`
- optional diagnostic symbol mask: BTC+ETH+SOL vs BTC+ETH

Candidate promotion to deeper validation requires:
- validation ER >= 90% of baseline
- validation PF >= 2.0
- validation trades >= 70% of baseline
- max DD <= 125% of baseline
- no catastrophic symbol result
- no dependence on one month or a few outlier trades

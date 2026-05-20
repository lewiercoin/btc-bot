# SOL Drawdown Forensic Diagnostic V1

**Milestone:** `SOL_DRAWDOWN_FORENSIC_DIAGNOSTIC_V1`
**Status:** `FORENSIC_COMPLETE_SOL_RISK_FOLLOWUP_RECOMMENDED`
**Scope:** Research Lab diagnostic only; frozen trial-00095 trade population; no runtime/core/settings changes.

## Methodology

- Regenerate BTC, ETH, and SOL frozen trial-00095 trades from audited datasets.
- Do not change SOL entry logic, sweep thresholds, exits, or trial parameters.
- Analyze SOL drawdown concentration, regime/year splits, loss streaks, daily PnL correlation, portfolio veto impact, and SOL risk-cap sensitivity.
- Risk-cap sensitivity changes only offline portfolio signal risk sizing, not entry selection or thresholds.

## Inputs

- BTC DB: `research_lab/snapshots/replay-optuna-default-v3-trial-00095.db`
- ETH DB: `research_lab/snapshots/ethusdt_2022_2026_dataset_v1.db`
- SOL DB: `research_lab/snapshots/replay-run-sol-historical-2022-2026.db`
- Trial store: `research_lab/research_lab.db`
- Window: 2022-01-01 to 2026-03-28 exclusive
- Pipeline trade counts: `{"BTCUSDT": 271, "ETHUSDT": 544, "SOLUSDT": 1201}`

## SOL Standalone vs Portfolio Gate

| View | Trades | ER | PF | Win Rate | Max DD R | Max Loss Streak |
|---|---:|---:|---:|---:|---:|---:|
| SOL standalone | 1201 | 2.141 | 3.42 | 40.2% | 32.72 | 21 |
| SOL after portfolio gate | 905 | 2.120 | 3.41 | 40.9% | 21.31 | 15 |
| BTC+ETH+SOL portfolio | 1545 | 2.056 | 3.49 | 45.1% | 19.47 | 13 |

## SOL By Year

| Year | Trades | ER | PF | Win Rate | Max DD R | Max Loss Streak |
|---|---:|---:|---:|---:|---:|---:|
| 2022 | 287 | 1.523 | 2.49 | 30.0% | 28.44 | 18 |
| 2023 | 359 | 2.609 | 4.12 | 43.2% | 9.18 | 7 |
| 2024 | 342 | 2.232 | 3.59 | 42.4% | 17.21 | 12 |
| 2025 | 194 | 2.140 | 3.64 | 45.9% | 17.48 | 12 |
| 2026 | 19 | 1.023 | 2.17 | 42.1% | 9.13 | 6 |

## SOL By Regime

| Regime | Trades | ER | PF | Win Rate | Max DD R | Max Loss Streak |
|---|---:|---:|---:|---:|---:|---:|
| crowded_leverage | 30 | -0.699 | 0.47 | 6.7% | 30.51 | 14 |
| downtrend | 250 | 0.693 | 1.60 | 20.8% | 38.38 | 26 |
| normal | 17 | 0.057 | 1.05 | 17.6% | 16.60 | 11 |
| uptrend | 904 | 2.675 | 4.39 | 47.1% | 12.42 | 8 |

## Loss Streaks

| Symbol | Streak Count | Max | Mean | P95 | Histogram |
|---|---:|---:|---:|---:|---|
| BTCUSDT | 56 | 10 | 2.11 | 6 | `{"1": 28, "2": 13, "3": 9, "4": 1, "5": 2, "6": 1, "7": 1, "10": 1}` |
| ETHUSDT | 124 | 9 | 2.37 | 6 | `{"1": 50, "2": 31, "3": 20, "4": 9, "5": 6, "6": 3, "7": 3, "8": 1, "9": 1}` |
| SOLUSDT | 263 | 21 | 2.73 | 7 | `{"1": 96, "2": 60, "3": 47, "4": 23, "5": 10, "6": 10, "7": 6, "8": 4, "9": 2, "10": 1, "12": 3, "21": 1}` |

## Worst SOL Drawdown Points

| Timestamp | Equity R | Peak R | Drawdown R |
|---|---:|---:|---:|
| 2023-01-05T00:30:00+00:00 | 432.74 | 465.46 | 32.72 |
| 2023-01-04T16:45:00+00:00 | 434.19 | 465.46 | 31.27 |
| 2023-01-04T07:15:00+00:00 | 435.66 | 465.46 | 29.80 |
| 2022-12-28T10:00:00+00:00 | 437.02 | 465.46 | 28.44 |
| 2022-12-05T23:00:00+00:00 | 438.44 | 465.46 | 27.02 |
| 2023-01-08T14:15:00+00:00 | 439.35 | 465.46 | 26.11 |
| 2022-11-23T17:30:00+00:00 | 439.99 | 465.46 | 25.47 |
| 2022-11-23T11:15:00+00:00 | 441.38 | 465.46 | 24.09 |
| 2022-11-21T22:15:00+00:00 | 442.88 | 465.46 | 22.58 |
| 2022-11-21T16:45:00+00:00 | 444.30 | 465.46 | 21.16 |

## Portfolio Veto Impact

- Portfolio veto count: 471
- `portfolio_daily_hard_stop`: 66
- `portfolio_emergency_stop`: 8
- `portfolio_loss_streak_pause`: 3
- `portfolio_position_cap_exceeded`: 27
- `portfolio_weekly_hard_stop`: 44
- `symbol_cooldown_active`: 86
- `symbol_daily_hard_stop`: 63
- `symbol_loss_streak_pause`: 9
- `symbol_position_cap_exceeded`: 78
- `symbol_weekly_hard_stop`: 87

## Daily R Correlation Matrix

| Symbol | BTCUSDT | ETHUSDT | SOLUSDT |
|---|---:|---:|---:|
| BTCUSDT | 1.000 | 0.069 | 0.086 |
| ETHUSDT | 0.069 | 1.000 | 0.109 |
| SOLUSDT | 0.086 | 0.109 | 1.000 |

## SOL Risk-Cap Sensitivity

| SOL Risk | Approved | ER | PF | Max DD R | Capital DD | SOL Trades | Vetoes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.20% | 1545 | 2.056 | 3.49 | 19.47 | 5.32% | 905 | 471 |
| 0.25% | 1545 | 2.056 | 3.49 | 19.47 | 5.40% | 905 | 471 |
| 0.30% | 1545 | 2.056 | 3.49 | 19.47 | 6.08% | 905 | 471 |
| 0.35% | 1545 | 2.056 | 3.49 | 19.47 | 6.81% | 905 | 471 |

## Builder Interpretation

SOL drawdown forensic analysis is complete. This report does not approve SOL shadow or runtime. Use the evidence to decide whether a separate SOL-specific risk-policy milestone is justified before any shadow design.

## Audit Questions

1. Does this remain diagnostic-only with no runtime/core/settings changes?
2. Are trial-00095 entries and thresholds frozen with no SOL tuning?
3. Are DD/year/regime/loss-streak calculations deterministic and reproducible?
4. Does risk-cap sensitivity avoid changing entry selection or thresholds?
5. Is the recommended next step supported by the forensic evidence?

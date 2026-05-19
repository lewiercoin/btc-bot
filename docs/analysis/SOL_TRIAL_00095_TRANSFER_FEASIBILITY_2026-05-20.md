# SOL Trial-00095 Transfer Feasibility

**Milestone:** `SOL_TRIAL_00095_TRANSFER_FEASIBILITY_V1`
**Status:** `SOL_TRANSFER_HYPOTHESIS_FAILED`
**Scope:** Research Lab strategy transfer only; frozen BTC trial-00095 parameters replayed on audited SOL dataset; no runtime/core changes.

## Methodology

- Regenerate BTC, ETH, and SOL trial-00095 trades through the existing single-symbol backtest pipeline.
- Use frozen trial-00095 parameters; only the research symbol changes to SOLUSDT for the transfer test.
- Run each symbol on a copied temporary replay DB; source datasets remain read-only.
- Apply the offline portfolio gate to BTC+ETH+SOL trade candidates using symbol-aware recovery state.
- No parameter search, no threshold tuning, no post-hoc rescue, no SOL shadow/PAPER approval.

## Inputs

- BTC DB: `research_lab/snapshots/replay-optuna-default-v3-trial-00095.db`
- ETH DB: `research_lab/snapshots/ethusdt_2022_2026_dataset_v1.db`
- SOL DB: `research_lab/snapshots/replay-run-sol-historical-2022-2026.db`
- Trial store: `research_lab/research_lab.db`
- Window: 2022-01-01 to 2026-03-28 exclusive
- Pipeline trade counts: `{"BTCUSDT": 271, "ETHUSDT": 544, "SOLUSDT": 1201}`

## SOL Standalone Transfer

| Trades | ER | PF | Win Rate | PnL R Sum | Max DD R | Max Loss Streak |
|---:|---:|---:|---:|---:|---:|---:|
| 1201 | 2.141 | 3.42 | 40.2% | 2571.45 | 32.72 | 21 |

## SOL Transfer Gates

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| min_trades | 1201 | 20 | PASS |
| min_er | 2.141 | 1 | PASS |
| min_pf | 3.361 | 1.5 | PASS |
| max_dd | 0.1546 | 0.12 | FAIL |
| wf_positive_folds | 4 | 2 | PASS |
| cost_2x_er | 1.787 | 0.75 | PASS |

## SOL Walk-Forward Stability

| Fold | Window | Trades | ER | PF | Win Rate | Max DD R |
|---|---|---:|---:|---:|---:|---:|
| 2022 | 2022-01-01 to 2023-01-01 | 287 | 1.523 | 2.49 | 30.0% | 28.44 |
| 2023 | 2023-01-01 to 2024-01-01 | 350 | 2.583 | 4.08 | 43.1% | 9.18 |
| 2024 | 2024-01-01 to 2025-01-01 | 344 | 2.268 | 3.64 | 42.7% | 17.21 |
| 2025_to_2026Q1 | 2025-01-01 to 2026-03-28 | 213 | 2.041 | 3.50 | 45.5% | 17.48 |

## SOL Cost Sensitivity

| Cost Multiplier | Trades | ER | PF | Max DD R |
|---:|---:|---:|---:|---:|
| 1.0x | 1201 | 2.141 | 3.42 | 32.72 |
| 1.5x | 1201 | 1.964 | 2.99 | 38.55 |
| 2.0x | 1201 | 1.787 | 2.64 | 44.37 |

## Portfolio Comparison

| Portfolio | Trades | ER | PF | Max DD R |
|---|---:|---:|---:|---:|
| BTC+ETH baseline | 696 | 1.955 | 3.60 | 13.74 |
| BTC+ETH+SOL replay | 1545 | 2.056 | 3.49 | 19.47 |

- Trade delta vs BTC+ETH: +849
- ER delta vs BTC+ETH: +5.2%
- PF delta vs BTC+ETH: -3.0%
- DD delta vs BTC+ETH: +41.7%

## Portfolio Gates

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| min_portfolio_trades | 1545 | 696 | PASS |
| min_portfolio_er | 2.056 | 1.5 | PASS |
| min_portfolio_pf | 3.494 | 2 | PASS |
| max_portfolio_dd_r | 19.47 | 20 | PASS |
| min_sol_approved_trades | 905 | 20 | PASS |

## Per-Symbol Metrics After Portfolio Gate

| Symbol | Trades | ER | PF | Win Rate | PnL R Sum | Max DD R |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 224 | 2.230 | 4.57 | 58.9% | 499.61 | 16.18 |
| ETHUSDT | 416 | 1.823 | 3.24 | 46.9% | 758.38 | 15.28 |
| SOLUSDT | 905 | 2.120 | 3.41 | 40.9% | 1918.19 | 21.31 |

## Portfolio Vetoes And Caps

- Approved trades: 1545
- Vetoed signals: 471
- Max total risk: 0.7000%
- Max gross notional: 0.60x equity
- Max directional notional: 0.60x equity
- Max open positions: 2
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

## Interpretation

Frozen trial-00095 did not produce a complete SOL transfer pass under the predeclared gates. Do not tune SOL thresholds inside this milestone.

## Limitations

- This is offline research and does not approve SOL shadow, SOL PAPER, or runtime integration.
- Portfolio gate is applied to regenerated closed trades, not live intrabar exposures.
- SOL threshold changes remain out of scope and would need a separate audited milestone.
- M4 checkpoint remains the blocker for runtime integration decisions.

## Audit Questions

1. Did the milestone preserve research-only scope and avoid runtime/core/settings changes?
2. Were trial-00095 parameters frozen except for the research-only symbol transfer to SOLUSDT?
3. Did the replay use audited SOL data read-only through a temporary compatibility DB?
4. Are SOL standalone transfer gates and BTC+ETH+SOL portfolio gates predeclared and not relaxed?
5. Is the builder verdict supported by standalone, walk-forward, cost, and portfolio metrics?

# Multi-Asset Full Pipeline Replay V1

**Milestone:** `MULTI_ASSET_FULL_PIPELINE_REPLAY_V1`
**Status:** `PASS_FULL_PIPELINE_REPLAY_FOR_RUNTIME_SCOPING`
**Scope:** Research Lab offline replay only; no runtime, PAPER, LIVE, or production DB changes.

## Methodology

- Regenerate BTC and ETH trial-00095 trades through the existing single-symbol backtest pipeline.
- Use frozen trial-00095 parameters; only the research symbol changes between BTCUSDT and ETHUSDT.
- Run each symbol on a copied temporary replay DB; source datasets remain read-only.
- Apply the offline portfolio gate from Phase 2 to regenerated trade candidates.
- This validates source-pipeline regeneration plus portfolio contracts, not runtime readiness.

## Inputs

- BTC DB: `research_lab\snapshots\replay-run13-regime-aware-trial-00063.db`
- ETH DB: `research_lab\snapshots\ethusdt_2022_2026_dataset_v1.db`
- Trial store: `research_lab\research_lab.db.v3`
- Window: 2022-01-01 to 2026-03-28 exclusive
- Pipeline trade counts: `{"BTCUSDT": 274, "ETHUSDT": 544}`

## Portfolio Metrics

| Trades | ER | PF | Win Rate | PnL R Sum | Max DD R | Max Loss Streak |
|---:|---:|---:|---:|---:|---:|---:|
| 696 | 1.955 | 3.60 | 50.7% | 1360.51 | 13.74 | 9 |

## Per-Symbol Metrics After Portfolio Gate

| Symbol | Trades | ER | PF | Win Rate | PnL R Sum | Max DD R |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 242 | 2.160 | 4.37 | 57.9% | 522.70 | 14.62 |
| ETHUSDT | 454 | 1.845 | 3.28 | 46.9% | 837.80 | 14.67 |

## Veto Breakdown

- Approved trades: 696
- Vetoed signals: 122
- `portfolio_daily_hard_stop`: 18
- `portfolio_weekly_hard_stop`: 5
- `symbol_cooldown_active`: 13
- `symbol_daily_hard_stop`: 16
- `symbol_loss_streak_pause`: 3
- `symbol_position_cap_exceeded`: 23
- `symbol_weekly_hard_stop`: 44

## Cap Utilization

- Max total risk: 0.7000%
- Max gross notional: 0.60x equity
- Max directional notional: 0.60x equity
- Max open positions: 2

## Gates

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| min_portfolio_trades | 696 | 300 | PASS |
| min_portfolio_er | 1.955 | 1.5 | PASS |
| min_portfolio_pf | 3.601 | 2 | PASS |
| max_portfolio_dd_r | 13.74 | 20 | PASS |
| min_btc_trades | 242 | 150 | PASS |
| min_eth_trades | 454 | 300 | PASS |

## Limitations

- This is still offline research and does not approve ETH/BTC PAPER.
- Portfolio gate is applied to regenerated closed trades, not live intrabar exposures.
- Full runtime integration still requires separate implementation, storage migration, recovery, and shadow validation.
- M4 checkpoint remains the blocker for runtime integration decisions.

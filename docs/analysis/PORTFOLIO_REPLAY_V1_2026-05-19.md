# Portfolio Replay V1

**Milestone:** `PORTFOLIO_REPLAY_V1`
**Status:** `READY_FOR_AUDIT`
**Scope:** Research Lab artifact-driven stateful replay; no runtime deployment or production DB writes.

## Methodology

- Inputs are frozen BTC and ETH trial-00095 trade artifacts.
- Each artifact trade is treated as a governance-passed candidate signal.
- The replay maintains open positions, symbol state, portfolio state, cooldowns, caps, and vetoes over time.
- Synthetic hold window: 180 minutes. This is required because BTC artifact lacks close timestamps.
- This is not full feature-engine replay. It validates portfolio state/gate contracts before runtime work.

## Combined Replay Metrics

| Trades | ER | PF | Win Rate | PnL R Sum | Max DD R | Max Loss Streak |
|---:|---:|---:|---:|---:|---:|---:|
| 696 | 1.955 | 3.60 | 50.7% | 1360.51 | 13.74 | 9 |

## Per-Symbol Metrics

| Symbol | Trades | ER | PF | Win Rate | PnL R Sum | Max DD R |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 242 | 2.160 | 4.37 | 57.9% | 522.70 | 14.62 |
| ETHUSDT | 454 | 1.845 | 3.28 | 46.9% | 837.80 | 14.67 |

## Cap Utilization

- Max total risk: 0.7000%
- Max gross notional: 0.60x equity
- Max directional notional: 0.60x equity
- Max open positions: 2

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

## Diagnostic Comparison

| Metric | Delta vs Artifact Stitching Diagnostic |
|---|---:|
| Trades | -122 |
| ER | +2.3% |
| PF | +3.2% |
| Max DD R | -28.5% |

## Interpretation

Stateful portfolio replay preserves decision-grade combined quality while exercising the offline SymbolRiskState, PortfolioRiskState, cap, cooldown, and veto contracts.

## Limitations

- Artifact trades are treated as candidate signals; this does not rerun feature/regime/signal/governance engines.
- BTC artifact has no close timestamps, so synthetic close times are deterministic approximations.
- Results validate portfolio state and gate behavior, not runtime execution readiness.
- ETH/BTC PAPER remains out of scope.

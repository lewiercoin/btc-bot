# Depth Threshold Portfolio Impact Diagnostic V1

**Milestone:** `DEPTH_THRESHOLD_PORTFOLIO_IMPACT_DIAGNOSTIC_V1`
**Status:** `ASSET_SPECIFIC_DEPTH_SUPPORTED_FOR_SHADOW_DECISION`
**Scope:** Research Lab diagnostic only; no runtime, sidecar, PAPER, LIVE, M4, settings, or production DB changes.

## Methodology

- Compare ETH/SOL `min_sweep_depth_pct` profiles on the untouched OOS window.
- Keep all non-depth trial-00095 parameters frozen.
- Keep BTC at frozen trial-00095.
- Apply the existing offline ResearchPortfolioGate to BTC/ETH/SOL candidates.
- Use BTC/ETH risk 0.35% and SOL candidate risk 0.15% for portfolio gate simulation.
- Treat results as threshold decision support only; this does not approve PAPER or LIVE.

## Inputs

- Window: 2025-01-01 to 2026-03-28 exclusive
- BTC DB: `research_lab\snapshots\replay-run13-regime-aware-trial-00063.db`
- ETH DB: `research_lab\snapshots\ethusdt_2022_2026_dataset_v1.db`
- SOL DB: `research_lab\snapshots\replay-run-sol-historical-2022-2026.db`
- Trial store: `research_lab\research_lab.db.v3`
- Risk by symbol: `{"BTCUSDT": 0.0035, "ETHUSDT": 0.0035, "SOLUSDT": 0.0015}`

## Scenario Summary

| Scenario | ETH Depth | SOL Depth | Portfolio Trades | ER | PF | Max DD R | BTC Trades | ETH Trades | SOL Trades | Max Corr | Max Overlap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| both_frozen_transfer | 0.00649 | 0.00649 | 321 | 1.875 | 3.34 | 19.47 | 41 | 162 | 213 | 0.127 | 2.5% |
| current_shadow_profile | 0.00750 | 0.00649 | 303 | 2.048 | 3.70 | 16.47 | 41 | 127 | 213 | 0.119 | 3.1% |
| eth_sol_asset_specific | 0.00750 | 0.00750 | 267 | 2.364 | 4.38 | 8.77 | 41 | 127 | 156 | 0.199 | 3.1% |

## Candidate vs Current

- Portfolio trade delta: -36 (-11.9%)
- Portfolio ER delta: 15.4%
- Portfolio PF delta: 18.3%
- Portfolio DD delta: -46.8%
- ETH standalone trade delta: 0
- SOL standalone trade delta: -57

## Scenario Details

### both_frozen_transfer

ETH and SOL use frozen BTC trial-00095 transfer depth.

| Symbol | Approved Trades | ER | PF | Max DD R | Max Loss Streak |
|---|---:|---:|---:|---:|---:|
| BTCUSDT | 35 | 2.788 | 7.46 | 5.96 | 4 |
| ETHUSDT | 121 | 1.800 | 3.17 | 12.01 | 6 |
| SOLUSDT | 165 | 1.737 | 3.02 | 14.70 | 10 |

Daily R correlation matrix:

| Symbol | BTCUSDT | ETHUSDT | SOLUSDT |
|---|---:|---:|---:|
| BTCUSDT | 1.000 | 0.011 | 0.127 |
| ETHUSDT | 0.011 | 1.000 | -0.041 |
| SOLUSDT | 0.127 | -0.041 | 1.000 |

Same-bar overlap:

- `BTCUSDT_ETHUSDT`: 2 / 154 (1.3%)
- `BTCUSDT_SOLUSDT`: 0 / 200 (0.0%)
- `ETHUSDT_SOLUSDT`: 7 / 279 (2.5%)

Veto breakdown:

- `portfolio_daily_hard_stop`: 11
- `portfolio_position_cap_exceeded`: 5
- `portfolio_weekly_hard_stop`: 14
- `symbol_cooldown_active`: 17
- `symbol_daily_hard_stop`: 4
- `symbol_loss_streak_pause`: 1
- `symbol_position_cap_exceeded`: 19
- `symbol_weekly_hard_stop`: 24

### current_shadow_profile

Current production shadow profile: ETH asset-specific, SOL frozen transfer.

| Symbol | Approved Trades | ER | PF | Max DD R | Max Loss Streak |
|---|---:|---:|---:|---:|---:|
| BTCUSDT | 35 | 2.788 | 7.46 | 5.96 | 4 |
| ETHUSDT | 103 | 2.323 | 4.28 | 9.02 | 6 |
| SOLUSDT | 165 | 1.719 | 3.00 | 14.70 | 10 |

Daily R correlation matrix:

| Symbol | BTCUSDT | ETHUSDT | SOLUSDT |
|---|---:|---:|---:|
| BTCUSDT | 1.000 | 0.016 | 0.119 |
| ETHUSDT | 0.016 | 1.000 | -0.054 |
| SOLUSDT | 0.119 | -0.054 | 1.000 |

Same-bar overlap:

- `BTCUSDT_ETHUSDT`: 4 / 134 (3.0%)
- `BTCUSDT_SOLUSDT`: 0 / 200 (0.0%)
- `ETHUSDT_SOLUSDT`: 8 / 260 (3.1%)

Veto breakdown:

- `portfolio_daily_hard_stop`: 10
- `portfolio_position_cap_exceeded`: 3
- `portfolio_weekly_hard_stop`: 13
- `symbol_cooldown_active`: 15
- `symbol_daily_hard_stop`: 4
- `symbol_loss_streak_pause`: 1
- `symbol_position_cap_exceeded`: 17
- `symbol_weekly_hard_stop`: 15

### eth_sol_asset_specific

Candidate profile: ETH and SOL use audited asset-specific depth.

| Symbol | Approved Trades | ER | PF | Max DD R | Max Loss Streak |
|---|---:|---:|---:|---:|---:|
| BTCUSDT | 35 | 2.788 | 7.46 | 5.96 | 4 |
| ETHUSDT | 105 | 2.145 | 3.91 | 9.02 | 6 |
| SOLUSDT | 127 | 2.428 | 4.27 | 7.71 | 5 |

Daily R correlation matrix:

| Symbol | BTCUSDT | ETHUSDT | SOLUSDT |
|---|---:|---:|---:|
| BTCUSDT | 1.000 | 0.009 | 0.199 |
| ETHUSDT | 0.009 | 1.000 | -0.061 |
| SOLUSDT | 0.199 | -0.061 | 1.000 |

Same-bar overlap:

- `BTCUSDT_ETHUSDT`: 4 / 136 (2.9%)
- `BTCUSDT_SOLUSDT`: 1 / 161 (0.6%)
- `ETHUSDT_SOLUSDT`: 7 / 225 (3.1%)

Veto breakdown:

- `portfolio_daily_hard_stop`: 6
- `portfolio_position_cap_exceeded`: 3
- `portfolio_weekly_hard_stop`: 10
- `symbol_cooldown_active`: 11
- `symbol_daily_hard_stop`: 4
- `symbol_position_cap_exceeded`: 13
- `symbol_weekly_hard_stop`: 10

## Gates

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| min_portfolio_trades | 267 | 250 | PASS |
| min_sol_trade_retention_pct | 0.7324 | 0.65 | PASS |
| max_portfolio_dd_r | 8.771 | 20 | PASS |
| max_daily_corr_abs | 0.1986 | 0.7 | PASS |
| max_same_bar_overlap_share | 0.03111 | 0.1 | PASS |

## Builder Interpretation

The OOS portfolio diagnostic supports using the ETH/SOL asset-specific depth profile as a shadow decision input. This is not PAPER approval; the next step would be an audited shadow-only threshold update or a runtime contract milestone.

## Audit Questions

1. Does this remain research-only with no runtime/sidecar/PAPER/LIVE changes?
2. Are only ETH/SOL depth thresholds varied while all other trial-00095 parameters remain frozen?
3. Is the OOS comparison aligned with the asset-specific optimization reports?
4. Are portfolio correlation, same-bar overlap, vetoes, and DD computed deterministically?
5. Does the verdict avoid approving PAPER or runtime promotion?

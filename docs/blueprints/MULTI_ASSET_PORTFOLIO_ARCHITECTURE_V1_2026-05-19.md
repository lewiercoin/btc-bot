# Multi-Asset Portfolio Architecture V1

**Milestone:** `MULTI_ASSET_PORTFOLIO_ARCHITECTURE_V1`  
**Status:** `READY_FOR_AUDIT_DESIGN_ONLY`  
**Scope:** Design only. No runtime implementation, PAPER deployment, LIVE deployment, or code-path change.  
**Decision date:** 2026-05-19  
**Baseline assets:** `BTCUSDT`, `ETHUSDT` Binance USDT perpetual futures  
**Strategy:** Frozen trial-00095 sweep/reclaim mechanics, no exit changes

## Executive Decision

The architecture path is approved for design because the preceding research
chain is complete and audited:

| Milestone | Verdict | Key Evidence |
|---|---|---|
| `ETH_HISTORICAL_BACKFILL_DATASET_V1` | PASS | ETH dataset complete and audit-ready for strategy research |
| `ETH_TRIAL_00095_TRANSFER_FEASIBILITY_V1` | PASS | ETH ER 1.804, PF 2.81, 544 trades, 4/4 positive folds |
| `MULTI_ASSET_PORTFOLIO_DIAGNOSTIC_V1` | PASS | BTC+ETH ER 1.910, PF 3.49, daily PnL correlation 0.051, same-bar overlap 2.8% |

This document does not approve ETH trading. It defines the contracts required
before a future implementation milestone can safely build multi-asset support.

## Internal Consultation Summary

Two independent internal reviews converged on the same constraints:

- Do not hide multi-asset logic inside `signal_engine`.
- Keep one deterministic per-symbol decision pipeline per asset.
- Add a portfolio gate above per-symbol governance and risk.
- Split state into `PortfolioRiskState` and `SymbolRiskState`.
- Make every persisted signal, decision, position, order, and trade
  unambiguously symbol-aware.
- Require backtest/runtime parity before any PAPER deployment.
- Do not change BTC PAPER or M4 monitoring before the 2026-06-13 checkpoint.

## Non-Goals

This milestone explicitly does not:

- implement multi-symbol runtime;
- modify `core/**`, `execution/**`, `orchestrator.py`, `main.py`,
  `settings.py`, `storage/**`, or `backtest/**`;
- deploy ETH to PAPER or LIVE;
- change BTC trial-00095 parameters;
- change trial-00095 exits;
- add SOL, ETHBTC, forex, or stocks;
- optimize ETH-specific parameters;
- relax M4 monitoring or BTC runtime thresholds.

## Target Runtime Topology

Future multi-asset runtime should be structured as:

```text
for each symbol:
    MarketSnapshot(symbol)
      -> FeatureEngine(symbol-local state)
      -> RegimeEngine
      -> SignalEngine
      -> GovernanceLayer(symbol state)
      -> CandidateExecutableSignal(symbol)

PortfolioGate:
    collect approved per-symbol signals for the same decision cycle
      -> deterministic ordering
      -> portfolio risk budget
      -> conflict policy
      -> final risk veto

Execution:
    route approved executable signals by symbol
      -> exchange symbol rules
      -> order lifecycle
      -> symbol-aware persistence
```

The orchestrator may coordinate this flow, but it must not calculate portfolio
risk ad hoc. Portfolio risk must live behind a clear contract.

## Layer Contracts

| Layer | Multi-Asset Contract |
|---|---|
| Data | Build isolated `MarketSnapshot` per symbol. No mixed candles, OI, funding, or aggtrade state. |
| Features | One `FeatureEngine` rolling state per symbol. Never reuse BTC rolling windows for ETH. |
| Regime | Regime is symbol-local. Portfolio regime is diagnostic only unless separately researched. |
| Signal | `SignalCandidate` must become symbol-explicit before runtime implementation. |
| Governance | Governance gets symbol-local state plus read-only portfolio context. It cannot approve portfolio exposure by itself. |
| Risk | Per-symbol risk gate runs first; portfolio gate has final veto authority. |
| Execution | Execution engine routes by symbol and exchange rules. It does not choose strategy priority. |
| Storage | Persist symbol on all signal, decision, position, trade, order, and decision-outcome records. |
| Monitoring | Metrics must expose both per-symbol and portfolio views. |

## State Model

Future implementation must introduce explicit persistent state:

### `SymbolRiskState`

Required per symbol:

- `symbol`
- `open_positions_count`
- `trades_today`
- `consecutive_losses`
- `daily_pnl_r`
- `weekly_pnl_r`
- `rolling_drawdown_r`
- `last_trade_at`
- `last_loss_at`
- `symbol_paused_until`
- `pause_reason`

### `PortfolioRiskState`

Required portfolio-wide:

- `open_positions_total`
- `gross_notional_pct`
- `directional_notional_pct_long`
- `directional_notional_pct_short`
- `total_risk_pct_open`
- `daily_pnl_r`
- `weekly_pnl_r`
- `rolling_drawdown_r`
- `global_consecutive_losses`
- `portfolio_paused_until`
- `emergency_stop_active`
- `last_portfolio_loss_at`

The global state must never be inferred only from in-memory objects. It must be
recoverable after restart.

## Initial Risk Policy

These are architecture defaults for a future PAPER candidate, not active
runtime settings:

| Risk Item | Design Default |
|---|---:|
| `risk_per_trade_pct_per_symbol` | 0.35% equity |
| `max_total_risk_pct_open` | 0.70% equity |
| `max_open_positions_total` | 2 |
| `max_open_positions_per_symbol` | 1 |
| `max_gross_notional_pct` | 1.00x equity |
| `max_directional_notional_pct` | 0.75x equity |
| Portfolio daily soft stop | -2R |
| Portfolio daily hard stop | -3R |
| Portfolio weekly soft stop | -4R |
| Portfolio weekly hard stop | -6R |
| Portfolio emergency rolling stop | -8R from local high-watermark |
| Per-symbol daily hard stop | -2R |
| Per-symbol weekly hard stop | -4R |
| Per-symbol rolling pause | -6R from symbol high-watermark |
| Per-symbol loss streak pause | 4 consecutive losses |
| Global loss streak pause | 6 consecutive losses |
| Per-symbol post-loss cooldown | trial-00095 value, 125 minutes unless explicitly changed by audited config |

Portfolio-level hard stops override all symbol-level approvals.

## Same-Bar Conflict Policy

The portfolio diagnostic showed same-15m overlap of only 2.8%, and the
`allow_both` policy had the best portfolio metrics. Therefore the design default
is:

1. Allow both BTC and ETH signals in the same 15m bar if all portfolio caps pass.
2. Evaluate signals in deterministic order:
   `timestamp ASC`, then `symbol ASC` with `BTCUSDT` before `ETHUSDT`.
3. The second signal may be reduced or vetoed only by portfolio caps.
4. If both signals point the same direction, `max_directional_notional_pct`
   has priority over `allow_both`.
5. Every veto must persist a machine-readable reason, for example:
   `portfolio_risk_cap_exceeded`, `directional_notional_cap_exceeded`,
   `portfolio_daily_hard_stop`, `symbol_paused`.

## Configuration Contract

Future implementation should split configuration into three concepts:

```text
portfolio:
  enabled: false
  symbols: [BTCUSDT, ETHUSDT]
  max_total_risk_pct_open: 0.007
  max_open_positions_total: 2
  max_gross_notional_pct: 1.0
  max_directional_notional_pct: 0.75

symbols:
  BTCUSDT:
    enabled: true
    strategy_profile: trial_00095
    risk_per_trade_pct: 0.0035
    max_open_positions: 1
  ETHUSDT:
    enabled: false
    strategy_profile: trial_00095_transfer
    risk_per_trade_pct: 0.0035
    max_open_positions: 1
```

`settings.py` must not become an automatic candidate promotion channel.
Configuration changes must still require audit and deployment approval.

## Persistence Contract

Future storage migration must make these records symbol-aware:

| Entity | Required Change |
|---|---|
| `signal_candidates` | Require `symbol`; keep setup type and feature snapshot trace. |
| `executable_signals` | Require `symbol`; include portfolio veto metadata when blocked. |
| `positions` | Already has symbol, but recovery must support multiple open symbols. |
| `trade_log` | Ensure symbol is first-class in reports and summaries. |
| `decision_outcomes` | Require symbol and portfolio decision fields. |
| `bot_state` | Split or supplement with portfolio and symbol state tables. |
| runtime metrics | Add per-symbol last cycle and portfolio-level health metrics. |

No migration may proceed without backup and rollback procedure.

## Recovery Contract

Startup recovery must be idempotent for multiple symbols:

1. Query exchange/account positions for every enabled symbol.
2. Reconcile persisted positions by symbol.
3. Detect orphan exchange positions, phantom DB positions, and unknown orders.
4. Rebuild `PortfolioRiskState` from persisted trades and open positions.
5. Rebuild each `SymbolRiskState` independently.
6. If any symbol is inconsistent, pause that symbol.
7. If portfolio exposure is inconsistent, enter portfolio safe mode.

Safe mode should continue managing open positions but block new entries.

## Backtest Parity Requirement

Before any PAPER implementation, a portfolio backtest milestone must replay the
same rules as the future runtime:

- per-symbol feature engine state;
- per-symbol governance state;
- portfolio risk caps;
- deterministic same-bar conflict policy;
- per-symbol and global cooldowns;
- per-symbol and portfolio drawdown stops;
- portfolio recovery assumptions;
- same fee and slippage assumptions for BTC and ETH unless audited otherwise.

Artifact stitching is no longer sufficient after this design milestone. The next
decision-grade simulation must execute the proposed portfolio contracts.

## Deployment Path

No runtime deployment is allowed from this document.

Required future sequence:

1. Continue BTC PAPER and M4 monitoring unchanged through 2026-06-13.
2. Audit this design milestone.
3. Close M4 checkpoint and decide whether BTC baseline remains unchanged.
4. Implement multi-asset state and portfolio backtest support in a separate
   audited implementation milestone.
5. Run portfolio replay with the new contracts.
6. If replay passes, run ETH shadow/PAPER validation without changing BTC risk.
7. Only after separate audit may BTC+ETH PAPER be considered.

## Acceptance Criteria For Future Implementation

A future implementation milestone must show:

- compileall clean;
- deterministic unit tests for symbol-state isolation;
- deterministic unit tests for portfolio risk caps;
- same-bar conflict tests;
- recovery tests with BTC-only, ETH-only, and BTC+ETH open positions;
- storage migration tests with rollback plan;
- portfolio backtest parity against this design;
- server smoke test showing BTC single-symbol behavior preserved when ETH is
  disabled;
- no change to BTC trial-00095 parameters unless separately audited.

## Audit Questions

1. Is this milestone design-only with no runtime code changes?
2. Does the design preserve layer separation?
3. Are `PortfolioRiskState` and `SymbolRiskState` sufficient to avoid hidden
   global-state coupling?
4. Are the initial risk caps conservative relative to the diagnostic evidence?
5. Is `allow_both` justified while still bounded by portfolio caps?
6. Are persistence and recovery requirements explicit enough for implementation?
7. Is the deployment path blocked until after audit and M4 checkpoint?

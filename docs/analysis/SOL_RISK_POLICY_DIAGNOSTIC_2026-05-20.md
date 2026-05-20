# SOL Risk Policy Diagnostic V1

**Milestone:** `SOL_RISK_POLICY_DIAGNOSTIC_V1`
**Status:** `SOL_APPROVED_AT_RISK_0.0015`
**Scope:** Research Lab risk-policy diagnostic only; frozen trial-00095 entries; no runtime/core/settings changes.

## Methodology

- Regenerate frozen BTC, ETH, and SOL trial-00095 trades from audited datasets.
- Keep BTC and ETH risk at 0.35%.
- Test SOL risk caps: 0.15%, 0.20%, 0.25%, 0.30%, 0.35%.
- Change only offline SOL signal risk sizing, not entry selection, thresholds, exits, or portfolio veto logic.
- Compare each variant against the audited BTC+ETH baseline.

## Inputs

- BTC DB: `research_lab/snapshots/replay-optuna-default-v3-trial-00095.db`
- ETH DB: `research_lab/snapshots/ethusdt_2022_2026_dataset_v1.db`
- SOL DB: `research_lab/snapshots/replay-run-sol-historical-2022-2026.db`
- Trial store: `research_lab/research_lab.db`
- Window: 2022-01-01 to 2026-03-28 exclusive
- Pipeline trade counts: `{"BTCUSDT": 271, "ETHUSDT": 544, "SOLUSDT": 1201}`

## Scenario Frontier

| SOL Risk | Approved | SOL Trades | ER | PF | Capital DD | Incremental PnL | DD Increase | Gates |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0.15% | 1545 | 905 | 2.056 | 3.49 | 5.24% | 251.78% | 0.43% | 6/6 |
| 0.20% | 1545 | 905 | 2.056 | 3.49 | 5.32% | 347.69% | 0.51% | 6/6 |
| 0.25% | 1545 | 905 | 2.056 | 3.49 | 5.40% | 443.60% | 0.59% | 6/6 |
| 0.30% | 1545 | 905 | 2.056 | 3.49 | 6.08% | 539.51% | 1.27% | 5/6 |
| 0.35% | 1545 | 905 | 2.056 | 3.49 | 6.81% | 635.42% | 2.00% | 4/6 |

## Selected Policy

- SOL risk cap: 0.15%
- Approved trades: 1545
- SOL approved trades: 905
- Portfolio ER/PF: 2.056 / 3.49
- Capital DD: 5.24%
- Incremental PnL vs BTC+ETH: 251.78%

## Gate Details

### SOL Risk 0.15%

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| max_capital_dd | 0.05241 | 0.06 | PASS |
| min_portfolio_er | 2.056 | 1.8 | PASS |
| min_portfolio_pf | 3.494 | 3 | PASS |
| min_sol_approved_trades | 905 | 500 | PASS |
| min_incremental_pnl_pct | 2.518 | 0.01 | PASS |
| max_capital_dd_increase_vs_btc_eth | 0.004323 | 0.02 | PASS |

### SOL Risk 0.20%

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| max_capital_dd | 0.05319 | 0.06 | PASS |
| min_portfolio_er | 2.056 | 1.8 | PASS |
| min_portfolio_pf | 3.494 | 3 | PASS |
| min_sol_approved_trades | 905 | 500 | PASS |
| min_incremental_pnl_pct | 3.477 | 0.01 | PASS |
| max_capital_dd_increase_vs_btc_eth | 0.005098 | 0.02 | PASS |

### SOL Risk 0.25%

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| max_capital_dd | 0.05396 | 0.06 | PASS |
| min_portfolio_er | 2.056 | 1.8 | PASS |
| min_portfolio_pf | 3.494 | 3 | PASS |
| min_sol_approved_trades | 905 | 500 | PASS |
| min_incremental_pnl_pct | 4.436 | 0.01 | PASS |
| max_capital_dd_increase_vs_btc_eth | 0.005873 | 0.02 | PASS |

### SOL Risk 0.30%

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| max_capital_dd | 0.06078 | 0.06 | FAIL |
| min_portfolio_er | 2.056 | 1.8 | PASS |
| min_portfolio_pf | 3.494 | 3 | PASS |
| min_sol_approved_trades | 905 | 500 | PASS |
| min_incremental_pnl_pct | 5.395 | 0.01 | PASS |
| max_capital_dd_increase_vs_btc_eth | 0.01269 | 0.02 | PASS |

### SOL Risk 0.35%

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| max_capital_dd | 0.06813 | 0.06 | FAIL |
| min_portfolio_er | 2.056 | 1.8 | PASS |
| min_portfolio_pf | 3.494 | 3 | PASS |
| min_sol_approved_trades | 905 | 500 | PASS |
| min_incremental_pnl_pct | 6.354 | 0.01 | PASS |
| max_capital_dd_increase_vs_btc_eth | 0.02004 | 0.02 | FAIL |

## Builder Interpretation

The predeclared frontier supports SOL at 0.15% risk in offline research. This does not approve SOL shadow or runtime; it supports a later audited shadow-design discussion.

## Audit Questions

1. Does this remain risk-policy diagnostic only with no runtime/core/settings changes?
2. Are trial-00095 entries, exits, and thresholds frozen?
3. Does SOL risk-cap sensitivity change only offline signal risk sizing?
4. Are gates predeclared and applied consistently across all scenarios?
5. Is the selected policy or rejection verdict supported by the frontier?

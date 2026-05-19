# Multi-Asset Portfolio Diagnostic

**Milestone:** `MULTI_ASSET_PORTFOLIO_DIAGNOSTIC_V1`
**Status:** `PASS_PORTFOLIO_DIAGNOSTIC_FOR_ARCHITECTURE_DESIGN`
**Scope:** Research Lab offline portfolio diagnostic only; no runtime architecture or deployment approval.

## Internal Consultation Summary

- Do not design runtime first. Measure portfolio interaction first.
- Use frozen BTC trial-00095 and audited ETH transfer artifacts only.
- Treat same-bar conflicts and daily PnL correlation as architecture inputs, not deployment approval.
- If portfolio gates pass, next step is architecture design for aggregate risk, not immediate PAPER deployment.

## Inputs

- BTC trades: `research_lab/analysis_output/trial_00095_trades.json`
- ETH trades: `research_lab/analysis_output/eth_trial_00095_trades.json`
- Trial store: `research_lab/research_lab.db`

## Standalone Metrics

Metrics in this report are R-based portfolio diagnostics. They may differ from per-asset backtest PF values that use absolute PnL.

| Asset | Trades | ER | PF | Win Rate | PnL R Sum | Max DD R | Max Loss Streak |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | 274 | 2.121 | 4.22 | 56.6% | 581.19 | 14.68 | 10 |
| ETH | 544 | 1.804 | 3.19 | 46.0% | 981.46 | 16.62 | 9 |

## Portfolio Policies

| Policy | Trades | ER | PF | Win Rate | PnL R Sum | Max DD R | Max Loss Streak |
|---|---:|---:|---:|---:|---:|---:|---:|
| allow_both | 818 | 1.910 | 3.49 | 49.5% | 1562.65 | 19.22 | 13 |
| first_signal_only | 796 | 1.865 | 3.41 | 49.1% | 1484.55 | 18.75 | 12 |
| btc_priority | 796 | 1.865 | 3.41 | 49.1% | 1484.55 | 18.75 | 12 |

## Interaction Diagnostics

- Daily PnL correlation: 0.051 across 488 active/zero-filled days
- Both-active days: 115
- Same 15m signal bars: 22 / 796 (2.8%)
- Top month concentration: 2024-03 with 57 trades (7.0%)
- Top quarter concentration: 2024-Q1 with 114 trades (13.9%)

## Gates

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| min_combined_trades | 818 | 300 | PASS |
| min_combined_er | 1.91 | 1.5 | PASS |
| min_combined_pf | 3.488 | 2 | PASS |
| max_drawdown_r | 19.22 | 45 | PASS |
| max_daily_pnl_corr | 0.05104 | 0.7 | PASS |
| max_same_bar_overlap_share | 0.02764 | 0.1 | PASS |
| max_single_month_trade_share | 0.06968 | 0.2 | PASS |

## Interpretation

BTC+ETH trial-00095 artifacts support proceeding to multi-asset architecture design. The next milestone should define aggregate risk, sizing, symbol-level cooldowns, and conflict handling before any runtime implementation.

## Methodology Limits

- BTC artifact is the existing full replay trade list, not the 47-trade WF-only summary.
- Correlation uses trade-open-day PnL buckets because BTC artifact does not include close timestamps.
- Same-bar overlap is a signal-timing proxy, not full exposure overlap.
- This report cannot approve runtime ETH trading or multi-asset execution.

## Audit Questions

1. Does this remain research-only with no runtime/core/settings changes?
2. Are BTC and ETH inputs frozen/audited enough for a portfolio diagnostic?
3. Are correlation, overlap, concentration, and policy metrics computed deterministically?
4. Is the builder verdict supported by the preregistered gates?
5. Are limitations clear enough to prevent accidental deployment interpretation?

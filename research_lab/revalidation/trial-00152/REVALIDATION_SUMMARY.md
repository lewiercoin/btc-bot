# Revalidation Summary: optuna-default-v2-trial-00152

Date: 2026-05-07
Builder: Codex
Milestone: CAMPAIGN-V2-REVALIDATION-ENHANCED-ARTIFACTS

## Verdict

SCREENING_ONLY

The candidate formally passes the current walk-forward protocol, but it is not
promotion-ready because the enhanced safety flags detected insufficient
validation sample size in one validation window.

## Evidence

- Walk-forward: 2/2 windows passed
- Fragile: false
- Mean degradation: 5.14100552577966%
- Safety flags:
  - pnl_sanity_review_required: false
  - pf_hard_review_required: false
  - oos_outperformance_review_required: false
  - low_oos_trade_count_review_required: true

## Window Metrics

| Window | Segment | ER | PF | Trades | Sharpe | Max DD | PnL Abs | Win Rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | train | 1.5089264194 | 3.8526800537 | 79 | 9.1473386966 | 0.0065056909 | 1294.0208804436 | 0.5696202532 |
| 0 | validation | 1.1864980805 | 3.7337530976 | 57 | 10.6227919828 | 0.0058032316 | 720.8701674922 | 0.6140350877 |
| 1 | train | 1.3726438646 | 3.8243817697 | 137 | 9.5339978872 | 0.0065056909 | 2123.3838385758 | 0.5912408759 |
| 1 | validation | 1.5248158683 | 4.1766526597 | 19 | 13.2719387086 | 0.0027844841 | 301.2130511557 | 0.6315789474 |

## Reason

Validation window 1 has only 19 trades, below the required review threshold of
30 validation trades. The result remains useful as screening evidence, but it
does not meet the revalidation standard for paper-trading approval.

## Artifacts

- `summary.json`
- `evaluation.json`
- `walkforward_report.json`
- `recommendation.json`
- `replay_summary_stdout.json`

No settings were changed and no candidate was auto-promoted.

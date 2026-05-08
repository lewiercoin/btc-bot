# WF Validation: optuna-default-v3-trial-00095

Date: 2026-05-08
Builder: Codex
Milestone: WF-VALIDATION-TRIAL-00095

## Scope

Run single-candidate walk-forward validation for `optuna-default-v3-trial-00095`
after the Campaign V3 audit identified it as the top clean pre-audit candidate.

This is a builder validation report, not a Claude Code final promotion audit.

## Execution

Server: `root@204.168.146.253`
Repo path: `/home/btc-bot/btc-bot`

Command executed:

```bash
.venv/bin/python -m research_lab replay-candidate \
  --candidate-id optuna-default-v3-trial-00095 \
  --start-date 2022-01-01 \
  --end-date 2026-03-28 \
  --output-dir research_lab/revalidation/trial-00095-v3
```

Server artifacts written:

- `research_lab/revalidation/trial-00095-v3/summary.json`
- `research_lab/revalidation/trial-00095-v3/evaluation.json`
- `research_lab/revalidation/trial-00095-v3/walkforward_report.json`
- `research_lab/revalidation/trial-00095-v3/recommendation.json`

Experiment store side effects:

- `research_lab/research_lab.db` now contains the refreshed evaluation,
  walk-forward report, and recommendation for `optuna-default-v3-trial-00095`.
- A pre-run server backup was created at
  `research_lab/research_lab.pre_trial_00095_wf_.db`.

## Candidate Full-Range Metrics

| Metric | Value |
|---|---:|
| Expectancy R | 2.1294 |
| Profit factor | 4.6625 |
| Max drawdown | 6.51% |
| Trades | 271 |
| Sharpe | 11.9326 |
| Win rate | 56.46% |
| pnl_abs | 92,324.81 |

## Walk-Forward Result

| Gate | Result |
|---|---|
| WF passed | PASS: 2/2 windows |
| Fragile | PASS: false |
| Protocol hash | `023dc84c2cd8eff7e0226a1cb74cca24ce64a896aacac7f8c4a61199fac9e1b8` |
| Pipeline verdict | `SCREENING_ONLY` |
| Recommendation risks | `pf_hard_review_required`, `oos_outperformance_review_required` |

### Per-Window Metrics

| Window | Passed | Train ER | Val ER | Degradation | Train PF | Val PF | Train DD | Val DD | Train trades | Val trades | Val Sharpe |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | true | 1.7140 | 2.4635 | -43.72% | 3.5439 | 4.8410 | 6.51% | 4.29% | 126 | 106 | 14.2737 |
| 2 | true | 2.0636 | 2.9980 | -45.28% | 4.4504 | 7.5001 | 6.51% | 1.94% | 233 | 33 | 12.2134 |

## Promotion Gate Evaluation

| Gate | Threshold | Result | Assessment |
|---|---|---|---|
| WF windows | 2/2 pass | 2/2 pass | PASS |
| Per-window validation trades | >30 preferred, >25 borderline acceptable | 106, 33 | PASS |
| IS degradation | <20% ordinary degradation; extreme OOS outperformance requires review | -43.72%, -45.28% | REVIEW |
| Fragile flag | false | false | PASS |
| Low OOS trade flag | false preferred | false | PASS |
| pnl sanity flag | false | false | PASS |
| PF hard review flag | false | true | REVIEW |
| OOS outperformance flag | false | true | REVIEW |

## Builder Verdict

`SCREENING_ONLY`

`trial-00095` is materially stronger than the 4 Campaign V3 candidates that were
automatically persisted by the WF/recommendation pipeline:

- It passed both WF windows.
- Validation trade counts are acceptable: 106 and 33.
- It is not fragile.
- It did not trigger low-OOS-trade or pnl-sanity flags.

It is not promotion-ready without Claude Code review because it triggered:

- `pf_hard_review_required`
- `oos_outperformance_review_required`

The main concern is that OOS validation improves too much versus train in both
windows, and validation PF reaches 7.5001 in window 2. That can be real edge, but
under this promotion policy it is an artifact/noise review condition.

## Recommended Next Step

Claude Code should audit the persisted `trial-00095` artifacts before any paper
trading deployment decision.

If Claude Code judges the flags as non-blocking false positives, `trial-00095`
can be considered for paper trading. If the flags are treated as blocking,
proceed to V4 with the Campaign V3 architecture findings:

- freeze `allow_uptrend_continuation=false`
- freeze dependent uptrend-continuation params
- freeze `weight_sweep_detected=0.5`
- reduce active search space from roughly 35 to 30 params

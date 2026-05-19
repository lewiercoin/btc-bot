# ETH Trial-00095 Transfer Feasibility

**Milestone:** `ETH_TRIAL_00095_TRANSFER_FEASIBILITY_V1`
**Status:** `PASS_TRANSFER_CANDIDATE_FOR_AUDIT`
**Scope:** Research Lab strategy transfer only; frozen BTC trial-00095 parameters replayed on audited ETH dataset; no runtime/core changes.

## Methodology

- Symbol: `ETHUSDT`
- Dataset: `research_lab/snapshots/ethusdt_2022_2026_dataset_v1.db`
- Trial params: `optuna-default-v3-trial-00095` from `research_lab/research_lab.db`
- Window: 2022-01-01 to 2026-03-28 exclusive
- 1h candles are derived inside a temporary replay DB from complete 15m ETH candles.
- `force_orders` and `daily_external_bias` are empty optional-context compatibility tables for this replay.
- No parameter search, no threshold tuning, no post-hoc rescue.

## Full Replay

| Trades | ER | PF | Win Rate | Max DD | PnL R Sum | Fees |
|---:|---:|---:|---:|---:|---:|---:|
| 544 | 1.804 | 2.81 | 46.0% | 6.72% | 981.46 | 133946.34 |

## Gates

| Gate | Value | Threshold | Result |
|---|---:|---:|---|
| min_trades | 544 | 20 | PASS |
| min_er | 1.804 | 1 | PASS |
| min_pf | 2.815 | 1.5 | PASS |
| max_dd | 0.06723 | 0.12 | PASS |
| wf_positive_folds | 4 | 2 | PASS |
| cost_2x_er | 1.422 | 0.75 | PASS |

## Walk-Forward Stability

| Fold | Window | Trades | ER | PF | Win Rate | Max DD |
|---|---|---:|---:|---:|---:|---:|
| 2022 | 2022-01-01 to 2023-01-01 | 179 | 1.900 | 2.95 | 42.5% | 6.72% |
| 2023 | 2023-01-01 to 2024-01-01 | 85 | 1.784 | 3.35 | 57.6% | 2.48% |
| 2024 | 2024-01-01 to 2025-01-01 | 120 | 1.785 | 3.02 | 45.8% | 4.44% |
| 2025_to_2026Q1 | 2025-01-01 to 2026-03-28 | 162 | 1.766 | 2.73 | 44.4% | 6.04% |

## Cost Sensitivity

| Cost Multiplier | Trades | ER | PF | Max DD |
|---:|---:|---:|---:|---:|
| 1.0x | 544 | 1.804 | 2.81 | 6.72% |
| 1.5x | 544 | 1.613 | 2.45 | 8.58% |
| 2.0x | 544 | 1.422 | 2.16 | 10.39% |

## Diagnostics

- Direction breakdown: `{"LONG": 488, "SHORT": 56}`
- Regime breakdown: `{"crowded_leverage": {"er": 1.5957040700395817, "trades": 18, "win_rate": 0.3333333333333333}, "downtrend": {"er": 1.366704586070486, "trades": 107, "win_rate": 0.3177570093457944}, "normal": {"er": 1.2263076999867735, "trades": 18, "win_rate": 0.2777777777777778}, "uptrend": {"er": 1.9561801738049431, "trades": 401, "win_rate": 0.5112219451371571}}`

## Interpretation

Frozen trial-00095 shows decision-grade transfer evidence on ETH. This is not runtime approval; it only supports a later audited multi-asset research path.

## Audit Questions

1. Did the milestone preserve research-only scope and avoid runtime/core/settings changes?
2. Were BTC trial-00095 parameters frozen except for the research-only symbol transfer to ETHUSDT?
3. Is temporary replay DB preparation deterministic and non-mutating for the source ETH dataset?
4. Are gates and walk-forward windows predeclared and not relaxed after results?
5. Is the builder verdict supported by the metrics?

# SMC_SEQUENCE_EDGE_FEASIBILITY_V1

## Scope

Research-only SMC sequence diagnostic. No production code, FeatureEngine facts, SignalEngine logic, Governance/Risk rules, settings/profile changes, execution changes, or DB migrations are changed by this report.

V1 taxonomy remains closed/invalidated. This diagnostic tests a separate sequence hypothesis and preserves the V1 timing lesson: delayed labels must be measured from `entry_candidate_bar` or `label_available_bar`, not from `detection_bar`.

## Dataset

- DB: `research_lab\data\crowded_unwind_backtest.db`
- Symbol/timeframe: `BTCUSDT` `15m`
- Rows: 195347
- Range UTC: 2020-09-01T00:00:00+00:00 to 2026-03-28T20:30:00+00:00
- Missing bar gaps: 0
- OHLC violations: 0

## Cohorts

| Cohort | Count | Det 5 Med | Entry 5 Med | Entry 5 Net Med | Entry 5 PF Proxy | Entry 5 Win | Entry 5 MFE | Entry 5 MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full_sequence | 1271 | 0.004348 | 0.000558 | -0.000442 | 1.061059 | 0.549961 | 0.004916 | 0.003660 |
| sweep_only | 14334 | -0.001242 | -0.001242 | -0.002242 | 0.361192 | 0.405219 | 0.002766 | 0.006490 |
| deterministic_control | 1271 | n/a | 0.000243 | -0.000757 | 0.794704 | 0.522423 | 0.004011 | 0.003784 |

PF proxy is computed from 5-bar net event returns after the configured round-trip cost. It is not a full trade-management backtest.

## Timing

- Median bars from sweep detection to entry candidate: 8
- Median MFE before entry candidate: 0.011565

## Trial-00095 / V1 References

- trial-00095 reference ER: 2.1
- trial-00095 reference PF: 4.6
- V1 raw wick-cross median 5-bar reference: 0.000237
- V1 delayed reclaim label-available median 5-bar reference: 5.4e-05

## Invalidation Verdict

- Verdict: `FAIL_OR_INCONCLUSIVE_REVIEW_REQUIRED`
- FAIL: entry-timed median return is worse than detection-bar return.
- FAIL: median MFE before entry is greater than or equal to post-entry 5-bar MFE.
- FAIL: entry-timed 5-bar profit-factor proxy is below trial-00095 PF threshold 4.0.

## Non-Goals

- No FeatureEngine work.
- No SignalEngine work.
- No V1 taxonomy rescue.
- No regime/session filtering.

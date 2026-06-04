# RECLAIM_REJECTION_FEASIBILITY_V1

## Scope

Research-only diagnostic. No production code, execution path, settings, schema, or production database query is changed by this run.

## Dataset

- DB: `F:\crowded_unwind_backtest.db`
- Canonical DB present: `True`
- Fallback used: `False`
- Symbol/timeframe: `BTCUSDT` `15m`
- Study window: `2022-01-01` to `2026-03-01`
- Rows: 145921
- Range UTC: 2022-01-01T00:00:00+00:00 to 2026-03-01T00:00:00+00:00
- Missing bar gaps: 0
- OHLC violations: 0
- Flow source: `aggtrade_buckets_60s_aggregated_to_15m`

## Cohorts

| Cohort | Count | Trades/Day | Net PF | Net Median | MFE Before Med | MFE Post 5 Med |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| reclaim_rejection_with_level_provenance | 2174 | 1.43026 | 0.624337 | -0.00280583 | 0.00345252 | 0.00281699 |
| reclaim_rejection_without_level_provenance | 2219 | 1.45987 | 0.610999 | -0.00282097 | 0.003498 | 0.00282261 |
| reclaim_swing_baseline | 123 | 0.0809211 | 0.741163 | -0.00242762 | n/a | 0.00334721 |
| control_random_wicks | 658 | 0.432895 | 0.711681 | -0.00288395 | 0.00412525 | 0.00316462 |

## Falsification Gates

| Rule | Measurement | Value | Threshold | Status |
| --- | --- | ---: | ---: | --- |
| F-1 | Timing-correct PF from return_start_bar fixed-exit net P&L | 0.624337 | >= 1.5 | FAIL |
| F-2 | Median net expectancy after 0.10% round-trip cost | -0.00280583 | >= 0 | FAIL |
| F-3 | median(mfe_before_entry) / median(mfe_post_entry_5bar) | 1.22561 | <= 0.70 | FAIL |
| F-4 | Throughput increase versus reclaim_swing_baseline | 1.34934 | >= 0.2 trades/day | PASS |
| F-5 | Pearson monthly P&L correlation with reclaim_swing_baseline | -0.11355 | <= 0.5 | PASS |
| F-6 | Detection-bar edge versus timing-correct edge | {'detection_pf': 0.6694369863640183, 'timing_pf': 0.6243370694979216, 'detection_median': -0.0025979140017768853, 'timing_median': -0.002805828928490269} | <= 30% better | PASS |

## Baseline Correlation

- F-5 status: `OK`
- Non-zero overlap months: 45
- Pearson correlation: -0.11355

## Verdict

- Final verdict: `HYPOTHESIS_INVALIDATED`
- F-3 formula used: `median(mfe_before_entry) / median(mfe_post_entry_5bar)`.
- Secondary consumed-share metric is reported but not used as the F-3 gate.
- CVD proxy uses `aggtrade_buckets.cvd`, not `cvd_price_history`.
- Trial-00095 comparison is reference-only; F-5 baseline uses event-study defaults approximated with `level_scanner` equal-cluster facts.

## Artifacts

- JSON SHA256: `CE18C680C2875947A7A74A66E77C8AC71A147B0D2805CA2DA3D4931F16A39F1E`

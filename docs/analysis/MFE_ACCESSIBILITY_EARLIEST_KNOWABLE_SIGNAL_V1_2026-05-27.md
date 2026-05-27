# MFE Accessibility Earliest Knowable Signal V1

Generated: `2026-05-27T20:34:47.489384+00:00`

## Scope

Research-only diagnostic. No production code, FeatureEngine, SignalEngine, Governance, Risk, settings, execution, or DB schema changes.

## Final Decision

`STOP_SMC_RESEARCH_TRIAL_00095_ALREADY_OPTIMAL`

## Dataset

- DB: `research_lab\data\crowded_unwind_backtest.db`
- Symbol/timeframe: `BTCUSDT 15m`
- Candle rows: 195347
- Sweep events: 14438
- State observations: 212871
- Metadata rows: aggtrade=195150, force_orders=146864, funding=6105, OI=524971

## Best State

- State: `reject_no_reclaim_known`
- Count: 2983
- Median k to state: 0
- Entry 5-bar net median: -0.000095
- Entry 5-bar PF proxy: 0.879136
- Entry 5-bar win rate: 0.494804
- MFE consumed before state: 0.595717
- Detection 5-bar net median audit-only: -0.006368

## State Cohorts

| State | Count | k med | Entry 5 net med | Entry 5 PF | Entry 5 win | MFE consumed | Trial overlap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| level_cluster_quality_known | 14438 | 0.000000 | -0.000611 | 0.758224 | 0.452518 | 0.343673 | 0.004848 |
| raw_sweep_known | 14438 | 0.000000 | -0.000611 | 0.758224 | 0.452518 | 0.343673 | 0.004848 |
| direction_resolved_known | 14328 | 2.000000 | -0.000840 | 0.712647 | 0.433098 | 0.523319 | 0.022125 |
| tfi_aligned_known | 14206 | 3.000000 | -0.000959 | 0.679790 | 0.424498 | 0.553571 | 0.022948 |
| cvd_absorption_proxy_known | 13257 | 4 | -0.000818 | 0.728194 | 0.435393 | 0.677934 | 0.000679 |
| confluence_threshold_known | 12882 | 3.000000 | -0.000868 | 0.739789 | 0.433240 | 0.544361 | 0.031284 |
| displacement_known | 12474 | 5.000000 | -0.001040 | 0.719541 | 0.419112 | 0.652435 | 0.021805 |
| close_beyond_level_known | 11325 | 2 | -0.001143 | 0.717607 | 0.411832 | 0.404653 | 0.030728 |
| reject_sweep_too_shallow_known | 11193 | 0 | -0.000691 | 0.691362 | 0.440493 | 0.296327 | 0.000000 |
| no_reclaim_after_1_bar_known | 11118 | 1.000000 | -0.000579 | 0.754511 | 0.455159 | 0.487502 | 0.000000 |
| no_reclaim_after_2_bars_known | 10121 | 2 | -0.000668 | 0.750929 | 0.449956 | 0.572222 | 0.000000 |
| reclaim_known | 10094 | 3.000000 | -0.001140 | 0.720910 | 0.412324 | 0.497380 | 0.051318 |
| no_reclaim_after_3_bars_known | 9172 | 3.000000 | -0.000635 | 0.753371 | 0.452464 | 0.652322 | 0.000000 |
| no_reclaim_after_4_bars_known | 8439 | 4 | -0.000484 | 0.798326 | 0.460600 | 0.743327 | 0.000000 |
| oi_crowding_known | 8090 | 0.000000 | -0.000492 | 0.842561 | 0.468908 | 0.654469 | 0.007664 |
| funding_supportive_known | 7828 | 0.000000 | -0.000806 | 0.728563 | 0.434594 | 0.372850 | 0.004343 |
| cvd_divergence_known | 5817 | 4 | -0.000143 | 0.844501 | 0.488052 | 1.000000 | 0.012721 |
| oi_funding_crowding_known | 4197 | 1 | -0.000656 | 0.833552 | 0.458423 | 0.667470 | 0.006195 |
| shallow_sweep_near_miss_known | 3464 | 0.000000 | -0.000588 | 0.729449 | 0.465935 | 0.375633 | 0.000000 |
| deep_sweep_threshold_known | 3245 | 0 | -0.000117 | 0.890144 | 0.493991 | 0.557079 | 0.021572 |
| reject_no_reclaim_known | 2983 | 0 | -0.000095 | 0.879136 | 0.494804 | 0.595717 | 0.000000 |
| tfi_strong_impulse_known | 2973 | 9 | -0.001238 | 0.486918 | 0.356206 | 0.837860 | 0.003700 |
| force_order_decay_known | 2833 | 4 | -0.000871 | 0.643767 | 0.414755 | 0.758938 | 0.002824 |
| force_order_burst_known | 1567 | 5 | -0.000720 | 0.740904 | 0.454371 | 1.000000 | 0.004467 |
| force_order_directional_burst_known | 1176 | 4.000000 | -0.000412 | 0.656436 | 0.476190 | 1.000000 | 0.000850 |
| trial_00095_candidate_state | 1021 | 7 | -0.000959 | 0.813877 | 0.460333 | 0.703783 | 1.000000 |
| reject_direction_unresolved_known | 192 | 0.000000 | -0.000530 | 0.968582 | 0.479167 | 0.131638 | 0.000000 |

## References

- Trial-00095 PF reference: 4.6625
- V1 raw wick cross median 5-bar: 0.000237
- V1 delayed reclaim label-available median 5-bar: 5.4e-05
- SMC entry 5-bar net median: -0.000442

## Invalidation Checks

- FAIL: no early knowable state has positive median net return after costs.
- FAIL: best state win rate is approximately random after entry timing.
- FAIL: best state PF proxy is too weak after costs.

## Timing Discipline

- Primary returns are measured from `entry_candidate_bar`.
- Detection-bar returns are audit-only.
- Every delayed state has its own `state_known_bar`.

## Non-Goals Confirmed

- No strategy implementation.
- No production code changes.
- No FeatureEngine or SignalEngine changes.
- No rescue of V1 taxonomy or failed SMC mitigation entry.

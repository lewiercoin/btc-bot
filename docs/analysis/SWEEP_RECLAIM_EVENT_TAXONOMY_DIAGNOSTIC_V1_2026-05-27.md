# SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1

## Scope

Research-only event taxonomy diagnostic. No production code, FeatureEngine facts, SignalEngine logic, Governance/Risk rules, settings/profile changes, or DB migrations are changed by this report.

Trial-00095 remains the validated baseline. This diagnostic tests whether the current single-bar sweep/reclaim boolean mixes structurally different event classes.

Regime/session segmentation is metadata only and is not a candidate for entry filtering in this milestone. This follows the May 2026 Singular Edge Assessment: `docs/analysis/SWEEP_RECLAIM_SINGULAR_EDGE_ASSESSMENT_2026-05-13.md`.

## Dataset

- DB: `research_lab\snapshots\btc_5m_2022_2026.db`
- Symbol/timeframe: `BTCUSDT` `5m`
- Rows: 447000
- Range UTC: 2022-01-01T00:00:00+00:00 to 2026-04-02T01:55:00+00:00
- Missing bar gaps: 0
- OHLC violations: 0

## Timing Model

Every row separates `detection_bar`, `label_available_bar`, `return_start_bar_detection`, and `return_start_bar_label_available`. Delayed reclaim and true-breakout labels are evaluated from both timing starts to avoid fake edge from unknowable labels.

## Required Cohorts

| Cohort | Count | Det 5 Med | Label 5 Med | Det 5 Win | Label 5 Win |
| --- | ---: | ---: | ---: | ---: | ---: |
| raw_wick_cross | 117953 | 0.000237 | 0.000237 | 0.546862 | 0.546862 |
| immediate_close_reclaim | 56340 | 0.000184 | 0.000184 | 0.535960 | 0.535960 |
| delayed_close_reclaim | 35368 | 0.001189 | 0.000054 | 0.760688 | 0.509557 |
| close_based_bos | 61370 | -0.000288 | -0.000288 | 0.442676 | 0.442676 |
| true_breakout_no_reclaim_within_window | 26192 | 0.001028 | -0.000268 | 0.717089 | 0.450519 |
| shallow_sweep | 80767 | 0.000211 | 0.000103 | 0.544690 | 0.520633 |
| medium_sweep | 112278 | 0.000333 | 0.000059 | 0.569025 | 0.511320 |
| deep_sweep | 104178 | 0.000412 | 0.000009 | 0.572779 | 0.501344 |
| clustered_equal_level_proxy | 213996 | 0.000315 | 0.000050 | 0.563342 | 0.509393 |
| isolated_pivot | 40499 | 0.000395 | 0.000098 | 0.568310 | 0.517050 |
| current_bot_equal_level_baseline_proxy | 65980 | 0.000587 | 0.000128 | 0.622810 | 0.525326 |

## Control Cohort

- Method: deterministic_shift_control
- Count: 297223
- Detection 5-bar median signed return: 0.000000

## Event Counts

| Event Type | Count |
| --- | ---: |
| confirmed_pivot | 118616 |
| active_liquidity_level | 118616 |
| equal_touch | 1255 |
| wick_crossed_liquidity | 117953 |
| close_based_bos | 61370 |
| immediate_wick_sweep_reclaim | 56340 |
| delayed_close_reclaim | 35368 |
| true_breakout | 26192 |

## Invalidation Verdict

- Verdict: `INVALIDATION_RISK_REVIEW_REQUIRED`
- Primary window: 5 bars
- Risk: Immediate reclaim does not outperform raw wick cross on 5-bar median signed return.
- Risk: Delayed reclaim edge weakens when measured from label-available timing.

## Non-Goals Confirmed

- No regime/session filtering.
- No parameter rescue.
- No new entry logic.
- No CHOCH/MSS, acceptance model, failed_sweep, OB/FVG/RJB/PPDD, or Pine port.

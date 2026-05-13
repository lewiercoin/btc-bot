# REGIME-REVERSAL-RESEARCH-V1 Validation Report

Final 15m portfolio test: state transition entries after RegimeEngine confirms shift.

## Overall Performance

- Trades: 11
- Expectancy R: 0.1131
- Profit factor: 1.2944658733682175
- Win rate: 36.36%
- Max DD: 1.39%

## Decision Funnel

- Replay cycles: 148596
- Transition events: 1210 (0.81%)
- Candidates: 22
- Closed trades: 11
- Average entry delay: 5.82 cycles
- Median entry delay: 5.0 cycles
- P95 entry delay: 12.0 cycles
- False reversal rate: 0.00%
- Whipsaw rate: 23.82%

## Per-Prior-Regime Performance

| Prior Regime | Trades | ER | PF | Win Rate |
|---|---:|---:|---:|---:|
| downtrend | 6 | -0.0176 | 0.958245326270024 | 33.33% |
| uptrend | 5 | 0.2700 | 2.6714523558753447 | 40.00% |

## Per-Direction Performance

| Direction | Trades | ER | PF | Win Rate |
|---|---:|---:|---:|---:|
| LONG | 6 | -0.0176 | 0.958245326270024 | 33.33% |
| SHORT | 5 | 0.2700 | 2.6714523558753447 | 40.00% |

## Top Rejection Reasons

- transition_window_closed: 144690
- no_prior_regime_transition: 111298
- regime_blocked:crowded_leverage: 27940
- not_directional_exhaustion_transition: 10410
- current_regime_not_persistent: 1338
- transition_direction_mismatch: 687
- tfi_not_aligned_with_new_regime: 422
- structure_not_confirmed: 350
- price_overextended_vs_ema: 343
- ema_alignment_failed: 124
- duplicate_transition_candidate: 47
- risk:max_open_positions: 8
- insufficient_regime_history: 4
- governance:duplicate_level: 3

## Gate Results

Verdict: **REJECT**
Reason: `negative_or_weak_edge_hard_stop`

| Gate | Value | Status |
|---|---:|---|
| minimum_total_trades | 11 | FAIL |
| post_transition_er | 0.1131 | REJECT |
| false_reversal_rate | 0.0000 | PASS |
| whipsaw_rate | 0.2382 | PASS |
| entry_delay_cycles | 5.8182 | FAIL |
| transition_entry_rate | 1.0000 | PASS |
| explainability | 1.0000 | PASS |

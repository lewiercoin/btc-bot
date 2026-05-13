# VOLATILITY-BREAKOUT-RESEARCH-V1 Validation Report

## Scope

Research-only validation of volatility_breakout using ATR expansion state, structure break, and aligned TFI momentum.

## Overall Performance

- Trades: 63
- Expectancy R: 0.5230
- Profit factor: 3.305366446376448
- Win rate: 61.90%
- Max DD: 2.53%

## Decision Funnel

- Replay cycles: 148596
- Expansion cycles: 4060 (2.73%)
- Candidates: 73
- Closed trades: 63
- Expansion entry rate: 100.00%
- Compression entry rate: 0.00%
- Expansion continuation rate: 57.14%

## Per-Regime Performance

| Regime | Trades | ER | PF | Win Rate |
|---|---:|---:|---:|---:|
| downtrend | 28 | 0.3650 | 2.1891511041978973 | 67.86% |
| normal | 8 | 0.5174 | 14.460759308192507 | 62.50% |
| uptrend | 27 | 0.6885 | 4.467707326758185 | 55.56% |

## Per-Direction Performance

| Direction | Trades | ER | PF | Win Rate |
|---|---:|---:|---:|---:|
| LONG | 19 | 0.9899 | 6.226869836355629 | 68.42% |
| SHORT | 44 | 0.3213 | 2.3592637806668604 | 59.09% |

## Top Rejection Reasons

- atr_not_rising: 249454
- regime_blocked:crowded_leverage: 27940
- atr_overheated_panic_threshold: 12910
- breakout_too_small: 6490
- tfi_not_aligned: 3739
- ema_alignment_failed: 3360
- price_overextended_vs_ema: 1151
- insufficient_atr_history: 22
- risk:max_open_positions: 9
- governance:duplicate_level: 1

## Gate Results

Verdict: **REJECT**
Reason: `negative_or_weak_edge_hard_stop`

| Gate | Value | Status |
|---|---:|---|
| minimum_total_trades | 63 | PASS |
| expansion_state_er | 0.5230 | REJECT |
| expansion_continuation_rate | 0.5714 | FAIL |
| expansion_entry_rate | 1.0000 | PASS |
| explainability | 1.0000 | PASS |

# AUDIT PACKAGE: VOLATILITY-BREAKOUT-RESEARCH-V1

## Builder Verdict

Verdict: **REJECT**
Reason: `negative_or_weak_edge_hard_stop`

## Key Metrics

- Trades: 63
- ER: 0.5230
- PF: 3.305366446376448
- Expansion continuation: 57.14%
- Expansion entry rate: 100.00%
- Compression entry rate: 0.00%

## Hard Gates

| Gate | Value | Pass | Reject | Status |
|---|---:|---|---|---|
| minimum_total_trades | 63 | >= 20 | < 10 | PASS |
| expansion_state_er | 0.5230 | > 1.5 | < 1.0 | REJECT |
| expansion_continuation_rate | 0.5714 | >= 0.60 | < 0.50 | FAIL |
| expansion_entry_rate | 1.0000 | >= 0.80 | < 0.50 | PASS |
| explainability | 1.0000 | 1.00 | < 1.00 | PASS |

## Scope Boundaries

- Research-only implementation.
- No production modules changed.
- No settings.py promotion.
- Compression regime is blocked to avoid compression_breakout 2.0.
- Walk-forward and overlap analysis were not run because Checkpoint 1 hit the ER hard-stop (`0.5230 < 1.0`).

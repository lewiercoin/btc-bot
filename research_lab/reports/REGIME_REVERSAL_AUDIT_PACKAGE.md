# AUDIT PACKAGE: REGIME-REVERSAL-RESEARCH-V1

## Builder Verdict

Verdict: **REJECT**
Reason: `negative_or_weak_edge_hard_stop`

## Key Metrics

- Trades: 11
- ER: 0.1131
- PF: 1.2944658733682175
- False reversal rate: 0.00%
- Whipsaw rate: 23.82%
- Average entry delay: 5.82 cycles
- Transition entry rate: 100.00%

## Hard Gates

| Gate | Value | Pass | Reject | Status |
|---|---:|---|---|---|
| minimum_total_trades | 11 | >= 20 | < 10 | FAIL |
| post_transition_er | 0.1131 | > 1.5 | < 1.0 | REJECT |
| false_reversal_rate | 0.0000 | < 0.40 | >= 0.50 | PASS |
| whipsaw_rate | 0.2382 | < 0.30 | >= 0.50 | PASS |
| entry_delay_cycles | 5.8182 | <= 3 | > 6 | FAIL |
| transition_entry_rate | 1.0000 | >= 0.70 | < 0.50 | PASS |
| explainability | 1.0000 | 1.00 | < 1.00 | PASS |

## Scope Boundaries

- Research-only implementation.
- No production modules changed.
- No settings.py promotion.
- Entry requires confirmed RegimeEngine transition; no top/bottom anticipation.
- Per final-test framing, failed or marginal gates lead to strategic assessment, not another setup iteration.

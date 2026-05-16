# M4 Near-Miss Monitoring Checkpoint

**Date:** 2026-05-16 11:06 UTC
**Milestone:** PAPER_NEAR_MISS_MONITORING_V1
**Checkpoint type:** EARLY_RUNTIME_CHECKPOINT
**Window:** 2026-05-13T11:06:12Z to 2026-05-16T11:06:12Z
**Source:** Production server `storage/btc_bot.db`
**Command basis:** `scripts/report_near_miss_diagnostics.py --days 3` plus direct read-only SQL validation

> Diagnostic only. No execution change. No parameter change.

## Production Status

Bot state at checkpoint:

| Field | Value |
|---|---|
| Mode | PAPER |
| Healthy | 1 |
| Safe mode | 0 |
| Open positions | 0 |
| Consecutive losses | 0 |
| Daily DD | 0.00% |
| Weekly DD | 0.00% |

Recent trade state:

- Last trade closed: 2026-05-10 22:15:22 UTC
- Trades in last 7 daily metric rows: 1 trade on 2026-05-10, 0 trades from 2026-05-11 through 2026-05-16
- No open position at checkpoint

## Near-Miss Summary

| Metric | Value |
|---|---:|
| Total decision cycles | 464 |
| `sweep_too_shallow` rejections | 260 |
| `sweep_too_shallow` share | 56.0% |
| Signal generated count | 0 |
| Near-miss records (`depth >= 0.004`) | 10 |
| Approx. unique near-miss timestamps | 5 |
| Min depth | 0.004221 |
| Avg depth | 0.004830 |
| Max depth | 0.005795 |

## Threshold Proximity

Baseline threshold remains `min_sweep_depth_pct = 0.00649`.

| Proximity to 0.00649 | Count | Interpretation |
|---|---:|---|
| Within 10% | 0 | No near-miss was very close to qualifying |
| Within 20% | 2 | One duplicated timestamp pair was close-ish |
| Within 30% | 6 | Most actionable records were still materially below threshold |

The strongest observed near-miss was `0.00579466`, about `10.7%` below the active threshold.

## Regime And Session

| Regime | Near-miss records |
|---|---:|
| uptrend | 10 |

| Session UTC | Near-miss records |
|---|---:|
| ASIA | 2 |
| EU | 2 |
| US | 6 |

All near-miss records occurred in `uptrend`. US session contributed the majority of records.

## Notable Runtime Finding

The production payload currently stores `sweep_depth_pct` at top-level `details_json.sweep_depth_pct`, but not inside `details_json.near_miss_diagnostics.sweep_depth_pct`.

This conflicts with the documented M4 query contract in `docs/DATA_SOURCES.md` and `docs/diagnostics/NEAR_MISS_MONITORING_README.md`. The local code has been patched so future payloads include nested `near_miss_diagnostics.sweep_depth_pct`, and the report script now falls back to the top-level field for already-recorded production rows.

## Checkpoint Verdict

`EARLY_MONITORING_CONTINUE_WITH_PAYLOAD_FIX`

Evidence so far confirms the frequency bottleneck remains active:

- `sweep_too_shallow` is still the dominant blocker.
- No signal was generated in the 3-day checkpoint window.
- Near-misses exist, but most are not close enough to justify a parameter change.
- The duplicated record pattern means raw near-miss count should be interpreted cautiously until the full M4 checkpoint.

## Recommendation

Continue M4 monitoring unchanged through the planned 2026-06-13 checkpoint.

Do not relax `min_sweep_depth_pct` based on this early sample. The evidence supports continued diagnostics and a payload/reporting fix, not a trading methodology change.


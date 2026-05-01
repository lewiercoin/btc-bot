# Filter Diagnostics - Duplicate Level + Uptrend Continuation Weak

**Date:** 2026-04-30  
**Operator:** Codex  
**Scope:** Read-only production diagnostics; no live logic/runtime changes.

---

## Source

Queried production directly:

- Server: `root@204.168.146.253`
- DB: `/home/btc-bot/btc-bot/storage/btc_bot.db`
- Service profile: `BOT_SETTINGS_PROFILE=experiment`
- DB integrity from prior funnel: `PRAGMA quick_check = ok`

This report intentionally does **not** compute shortcut PnL for rejected events.

---

## Why This Report Exists

Prior production funnel identified two real bottlenecks:

- pre-candidate: `uptrend_continuation_weak`
- post-candidate: `duplicate_level`

The purpose here is to decompose those filters before any replay or tuning.

---

## Uptrend Continuation Weak

Rows analyzed:

- `uptrend_continuation_weak`: `639`
- Rows with missing joined `feature_snapshots`: `150`
- Rows with full feature data: `489`

### Sub-Reason Breakdown

| Sub-reason | Count | Meaning |
|---|---:|---|
| `sweep_side_not_high` | 560 | Uptrend continuation only accepts HIGH sweep; most rejected cases are LOW sweeps. |
| `high_sweep_tfi_not_bullish` | 48 | HIGH sweep and EMA trend ok, but TFI not above threshold. |
| `high_sweep_ema_gap_weak_and_tfi_not_bullish` | 31 | HIGH sweep but both EMA gap and TFI failed. |

### Interpretation

The dominant issue is not a weak EMA trend. The dominant issue is structural:

```text
regime = uptrend
reclaim_detected = false
sweep_side = LOW
=> blocked as uptrend_continuation_weak
```

That means this filter is mostly rejecting LOW-sweep events in uptrend. Those are not valid for the current continuation path, because `_infer_uptrend_continuation_direction()` requires `sweep_side == "HIGH"`.

This points less to "EMA trend too strict" and more to a missing or disabled setup family:

- pullback continuation,
- retest continuation,
- LOW-sweep reclaim/pullback logic in uptrend.

`allow_uptrend_pullback` is currently disabled in the active runtime profile.

### Feature Distribution

For rows with full feature data:

| Metric | Min | P25 | Median | P75 | Max |
|---|---:|---:|---:|---:|---:|
| EMA gap `(ema50_4h - ema200_4h) / ema200_4h` | 0.0345 | 0.0403 | 0.0467 | 0.0487 | 0.0496 |
| `tfi_60s` | -0.9088 | -0.3373 | 0.0000 | 0.2375 | 0.8544 |

Active thresholds from experiment strategy:

- `ema_trend_gap_pct = 0.0063`
- `direction_tfi_threshold = 0.05`

Since EMA gap is usually far above threshold, EMA trend strength is not the main explanation for most rejects.

---

## Duplicate Level

Important implementation detail:

- `signal_candidates` does not persist `entry_reference`, stop, or TP levels.
- Candidate levels were reconstructed from joined `feature_snapshots.features_json` and active strategy parameters.
- Governance duplicate memory is runtime-only, but it can be approximated by replaying prior governance-passed candidates in timestamp order.
- Risk profile came from systemd/runtime profile: `experiment`.

Active experiment risk values used:

- `duplicate_level_tolerance_pct = 0.0004`
- `duplicate_level_window_hours = 24`
- `min_rr = 1.6`

### Inventory

| Metric | Count |
|---|---:|
| Candidate rows joined from decision outcomes | 106 |
| Rows missing feature snapshots for reconstruction | 31 |
| `duplicate_level` vetoes reconstructed | 48 |
| Duplicate vetoes with reconstructed prior match | 48 |

Confidence:

| Confidence | Count |
|---|---:|
| `HIGH` | 48 |

### Downstream RR Check

This is **not** PnL replay. It only asks whether the vetoed candidate would likely pass the later `min_rr` gate if duplicate governance did not exist.

| Would pass `min_rr=1.6` | Count |
|---|---:|
| False | 34 |
| True | 14 |

Interpretation:

Most duplicate-level vetoes would probably still fail downstream risk due to insufficient RR. This materially weakens the idea that `duplicate_level` alone is suppressing many executable trades.

### Prior Match Source

Nearest reconstructed duplicate prior outcome:

| Prior outcome | Count |
|---|---:|
| `risk_block` | 47 |
| `signal_generated` | 1 |

This is important. Most duplicates are repeats of levels that had already passed governance but then failed risk, usually because RR geometry was poor.

### Duplicate Candidate Distributions

| Metric | Min | P25 | Median | P75 | Max |
|---|---:|---:|---:|---:|---:|
| Reconstructed entry | 76033.84 | 77301.27 | 77302.82 | 77304.44 | 77982.27 |
| Reconstructed RR | 0.589 | 0.883 | 1.099 | 2.081 | 3.191 |
| Confluence score | 7.10 | 8.50 | 8.50 | 12.75 | 17.60 |

The median duplicate candidate has weak RR, despite sometimes having acceptable confluence.

---

## Findings

1. `uptrend_continuation_weak` is mainly a side/structure issue.

Most cases are LOW sweeps in uptrend, not failures of EMA trend strength. This suggests the current continuation definition is narrow rather than merely over-thresholded.

2. `duplicate_level` is not automatically hiding 48 missed trades.

Only 14 of 48 reconstructed duplicate vetoes would pass the active `min_rr=1.6` check. The other 34 would likely still be blocked by risk.

3. Repeated duplicate levels often originate from prior risk-blocked levels.

47 of 48 nearest reconstructed prior matches were prior `risk_block` events. The system repeatedly sees the same level geometry, and governance prevents repeated attempts around it.

4. The next bottleneck behind duplicate is RR geometry.

The practical question is not simply "should duplicate_level be loosened?" It is:

```text
Why do repeated valid-looking candidates around the same level have poor RR geometry?
```

5. Confluence still remains low priority.

These diagnostics reinforce the prior funnel result: confluence score is not the current active blocker.

---

## Recommendations

Do not change live logic yet.

Next read-only steps:

1. Build a dedicated RR geometry report for candidates and risk blocks:
   - entry,
   - stop,
   - TP1,
   - ATR,
   - min stop distance effect,
   - raw RR vs required RR.

2. For uptrend, do not "relax continuation" blindly.

   The observed dominant case is LOW sweep in uptrend. If explored, it should become a separate research-only setup hypothesis such as:

   - `uptrend_pullback_reclaim`,
   - `uptrend_low_sweep_retest`,
   - `pullback_continuation`.

3. If duplicate replay is pursued, replay only the 14 duplicate vetoes that pass reconstructed `min_rr`.

   The other 34 are probably not executable under current risk policy and should not be counted as missed opportunity.

4. Persist candidate levels for future audit.

   Current `signal_candidates` lacks entry/stop/TP fields for vetoed candidates. Future diagnostics would be much stronger if candidate levels were persisted before governance.

---

## Decision

No live strategy change is justified from this report alone.

The highest-value next investigation is RR geometry, not confluence tuning or blanket duplicate-level relaxation.


# RR Geometry Review - Production

**Date:** 2026-04-30  
**Operator:** Codex  
**Scope:** Read-only production analysis; no live logic/runtime changes.

---

## Source

Queried production directly:

- Server: `root@204.168.146.253`
- DB: `/home/btc-bot/btc-bot/storage/btc_bot.db`
- Runtime profile: `BOT_SETTINGS_PROFILE=experiment`
- Relevant active risk threshold: `min_rr = 1.6`

This report reconstructs entry/stop/TP/RR geometry from persisted `feature_snapshots` and `config_snapshots`. It does **not** simulate counterfactual PnL.

---

## Coverage

Candidate outcome rows joined from `decision_outcomes`:

- Total candidate outcomes: `106`
- Missing joined feature snapshots: `31`
- Reconstructable rows: `75`

Reconstructable buckets:

| Bucket | Count |
|---|---:|
| `duplicate_level` | 48 |
| `risk_block` | 22 |
| `executed` | 5 |

Important limitation:

- `feature_snapshots` only cover the later portion of the recent production window, so only `5` executed trades had enough persisted feature data for exact geometry reconstruction here.

---

## Core Finding

All reconstructable candidate buckets had `min_stop_distance_pct` forcing the actual stop distance.

| Bucket | Rows | Min-Stop Forced | Median Raw Stop | Median Actual Stop | Median RR1 |
|---|---:|---:|---:|---:|---:|
| `duplicate_level` | 48 | 48 | 2.86 | 247.37 | 1.10 |
| `risk_block` | 22 | 22 | 2.61 | 247.37 | 1.02 |
| `executed` | 5 | 5 | 4.81 | 248.20 | 1.84 |

The raw signal geometry creates extremely tight stop distances from `entry_offset_atr=0.01` and `invalidation_offset_atr=0.01`. The risk layer then enforces `min_stop_distance_pct`, expanding stops to roughly `245-250` USD.

This expansion is the dominant mechanical reason RR collapses for many candidates.

---

## Bucket Details

### Risk Blocks

Risk-block rows:

- Count: `22`
- `min_stop_forced`: `22/22`
- `pass_min_rr_count`: `0/22`
- Median RR1: `1.02`
- P75 RR1: `1.26`
- Max RR1: `1.57`

Interpretation:

Risk blocks are not caused by low confluence. Median confluence score was `17.2`. They are caused by level geometry after min-stop enforcement.

### Duplicate Level

Duplicate-level rows:

- Count: `48`
- `min_stop_forced`: `48/48`
- `pass_min_rr_count`: `14/48`
- Median RR1: `1.10`
- P75 RR1: `2.08`
- Median confluence score: `8.5`

Interpretation:

Most duplicate-level vetoes would not become executable trades even if duplicate governance were disabled, because the same geometry would fail `min_rr=1.6`.

### Executed

Executed rows with reconstructable geometry:

- Count: `5`
- `min_stop_forced`: `5/5`
- `pass_min_rr_count`: `5/5`
- Median RR1: `1.84`
- RR1 range: `1.72` to `2.44`

Exit outcomes in this reconstructable subset:

| Exit | Count | Avg PnL R |
|---|---:|---:|
| `SL` | 2 | -1.00R |
| `TP` | 2 | +0.63R |
| `TIMEOUT` | 1 | -0.40R |

The executed subset is too small for expectancy conclusions. It is only useful for geometry comparison.

---

## Interpretation

The current active geometry is internally strained:

```text
entry_offset_atr = 0.01
invalidation_offset_atr = 0.01
min_stop_distance_pct = 0.0032
tp1_atr_mult = 1.9
min_rr = 1.6
```

The signal layer places entry/invalidation very close to the sweep level, but the risk contract refuses such a tight stop and expands it to a minimum percentage distance. TP remains ATR-based.

So RR becomes mostly a function of:

```text
ATR-based reward / percentage-based minimum stop
```

This explains why:

- many high-score candidates are risk-blocked,
- many duplicate vetoes are not actually missed executable trades,
- confluence is not the active bottleneck,
- repeated level candidates around the same area often remain poor RR candidates.

---

## Strategic Implication

This supports the current thesis:

- Do not loosen confluence.
- Do not disable `duplicate_level` blindly.
- Do not lower continuation thresholds just to increase frequency.

The next real design question is whether each setup needs its own level geometry:

- reversal sweep/reclaim,
- breakout-style uptrend continuation,
- LOW-sweep uptrend pullback/retest continuation.

The LOW-sweep uptrend cases should not inherit reversal geometry by default. They likely need a separate research-only setup definition with explicit entry, stop, TP, and timeout semantics.

---

## Recommended Next Step

No live strategy change is justified from this report alone.

Recommended research-only next step:

1. Draft a frozen specification for `uptrend_pullback_retest_v1`.
2. Define geometry independently:
   - entry trigger,
   - stop anchor,
   - TP anchor,
   - timeout,
   - max attempts per level,
   - separate risk budget.
3. Replay/walk-forward that setup as a separate candidate stream.

Recommended instrumentation improvement:

- Persist candidate `entry_reference`, `invalidation_level`, `tp_reference_1`, and `tp_reference_2` in `signal_candidates` before governance.

That would remove the need for reconstruction in future audits.


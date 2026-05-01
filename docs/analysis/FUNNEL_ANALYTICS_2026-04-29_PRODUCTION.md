# Funnel Analytics - Production Database

**Date:** 2026-04-29  
**Operator:** Codex  
**Scope:** Read-only production funnel analysis; no live strategy/runtime changes.

---

## Data Source

**Source of truth:** `root@204.168.146.253:/home/btc-bot/btc-bot/storage/btc_bot.db`

Access used:

```powershell
C:\Windows\System32\OpenSSH\ssh.exe -i c:\development\btc-bot\btc-bot-deploy-v2 root@204.168.146.253
```

Production DB integrity:

- `PRAGMA quick_check`: `ok`

Runtime status before query:

- Mode: `PAPER`
- Healthy: `1`
- Safe mode: `0`
- Open positions: `0`
- `btc-bot.service`: active
- `btc-bot-dashboard.service`: active
- RAM available: ~3086 MB
- Disk `/`: 32% used

---

## Window

Readable `decision_outcomes` window:

- Start: `2026-04-20T10:00:00.002987+00:00`
- End: `2026-04-29T20:00:00.003556+00:00`
- Rows: `904`

Readable `feature_snapshots` window:

- Start: `2026-04-23T19:00:00.004217+00:00`
- End: `2026-04-29T20:00:00.003556+00:00`
- Rows: `925`

Trade window:

- Full DB: `791` closed trades from `2022-03-09` to `2026-04-29`
- Since `2026-04-20`: `16` closed trades

---

## Funnel Summary

| Stage | Count | Rate |
|---|---:|---:|
| Decision rows | 904 | 100.0% |
| Safe-mode skips | 73 | 8.1% of rows |
| Evaluated decision rows | 831 | 91.9% of rows |
| No SignalCandidate | 731 | 88.0% of evaluated |
| SignalCandidate created | 100 | 12.0% of evaluated |
| Governance veto | 63 | 63.0% of candidates |
| Risk block | 21 | 21.0% of candidates |
| Executed/opened trade outcome | 16 | 16.0% of candidates |

The largest compression point after candidate generation is governance, specifically duplicate-level vetoes.

---

## No-Candidate Attribution

| Reason | Count | Interpretation |
|---|---:|---|
| `uptrend_continuation_weak` | 580 | Dominant no-signal bottleneck; all rows in `uptrend`. |
| `no_reclaim` | 85 | Sweep present but reclaim missing; all rows in `crowded_leverage`. |
| `direction_unresolved` | 66 | Direction did not resolve after event detection. |
| `confluence_below_min` | 0 | No evidence that `confluence_min` is the active bottleneck. |
| `regime_direction_whitelist` | 0 | No evidence that regime whitelist is currently the active bottleneck. |
| `context_unfavorable` | 0 | No context blocking observed. |

Feature diagnostics from `decision_outcomes.details_json`:

| Flag | Count |
|---|---:|
| `sweep_detected` | 731 |
| `reclaim_detected` | 66 |
| `direction_inferred` | 0 |
| `direction_allowed` | 0 |
| `confluence_evaluated` | 0 |

Interpretation: the bot frequently detects sweep-like events, but most never reach confluence evaluation because they fail earlier gates.

---

## Candidate Attribution

Signal candidates since `2026-04-20`:

| Setup | Regime | Direction | Count | Avg Score |
|---|---|---|---:|---:|
| `liquidity_sweep_reclaim_long` | `uptrend` | `LONG` | 92 | 12.26 |
| `liquidity_sweep_reclaim_long` | `crowded_leverage` | `LONG` | 8 | 17.88 |

Candidate downstream outcomes:

| Outcome | Regime | Count | Avg Score | Min Score | Max Score |
|---|---|---:|---:|---:|---:|
| `governance_veto` | `uptrend` | 63 | 11.08 | 7.10 | 21.10 |
| `risk_block` | `uptrend` | 19 | 14.91 | 8.50 | 17.20 |
| `signal_generated` | `uptrend` | 10 | 14.63 | 12.75 | 17.60 |
| `signal_generated` | `crowded_leverage` | 6 | 18.10 | 17.20 | 19.70 |
| `risk_block` | `crowded_leverage` | 2 | 17.20 | 17.20 | 17.20 |

Governance notes:

| Note | Count |
|---|---:|
| `duplicate_level` | 62 |
| `cooldown_after_loss:1079s` | 1 |

Risk reasons:

- `20` of `21` risk blocks were `rr_below_min:*`.
- `1` risk block was `max_open_positions`.

Interpretation: candidate score is not the primary execution selector. Duplicate-level governance and RR geometry dominate the candidate-to-execution funnel.

---

## Context Status

Context rows:

| Session | Volatility | Eligible | Neutral Mode | Count |
|---|---|---:|---:|---:|
| `NULL` | `NULL` | `NULL` | `NULL` | 679 |
| `ASIA` | `HIGH` | 1 | 1 | 72 |
| `US` | `HIGH` | 1 | 1 | 65 |
| `EU` | `HIGH` | 1 | 1 | 64 |
| `EU_US` | `HIGH` | 1 | 1 | 24 |

Context is not an active blocker in this window. Populated context rows are eligible and neutral-mode active.

---

## Trade Outcomes Since 2026-04-20

| Metric | Value |
|---|---:|
| Trades | 16 |
| Closed | 16 |
| Wins | 8 |
| Win rate | 50.0% |
| Sum R | +5.09R |
| Expectancy | +0.318R |

By exit reason:

| Exit | Count | Sum R | Avg R |
|---|---:|---:|---:|
| `TP` | 10 | +10.49R | +1.049R |
| `SL` | 5 | -5.00R | -1.000R |
| `TIMEOUT` | 1 | -0.40R | -0.401R |

Important limitation:

- `fees_total`, `funding_paid`, and `slippage_bps_avg` are `0.0` in these rows.
- Treat this as paper/runtime accounting, not final post-cost live expectancy.

Full DB context:

- `791` closed trades.
- Full-period expectancy: `-0.118R`.
- Full-period sum: `-93.03R`.

Recent window is positive, but the full historical table is negative. Any promotion decision must use controlled protocol lineage, not this raw aggregate alone.

---

## Key Findings

1. `confluence_min` is not the current observed bottleneck.

There are zero `confluence_below_min` rows in the production decision window. Changing confluence now would be weakly justified.

2. The main pre-candidate issue is uptrend continuation weakness.

`uptrend_continuation_weak` accounts for 580 rows. This supports investigating the uptrend continuation gate or logging more granular reasons inside that gate.

3. The main post-candidate issue is duplicate-level governance.

`duplicate_level` accounts for 62 of 63 governance vetoes. This may be valid anti-overtrading protection, but it is the largest candidate-to-trade compression point.

4. Risk blocks are mostly RR geometry, not signal quality.

`rr_below_min` accounts for 20 of 21 risk blocks. Level construction, entry/stop/TP geometry, and min-RR policy matter more than score threshold in this segment.

5. Context gating is not currently suppressing trades.

Context rows that exist are neutral-mode eligible. Context should remain a telemetry/modeling question, not a suspected live blocker in this window.

---

## Recommended Next Step

Do not change live logic from this funnel alone.

Next highest-value read-only follow-up:

1. Decompose `uptrend_continuation_weak` into exact sub-reasons:
   - non-HIGH sweep,
   - EMA gap too weak,
   - TFI not bullish enough.
2. Decompose `duplicate_level` by price distance and elapsed time from prior candidate/trade.
3. Decompose `rr_below_min` by entry, stop, TP, ATR, and min-RR threshold.

Only after those attributions should any change be proposed.


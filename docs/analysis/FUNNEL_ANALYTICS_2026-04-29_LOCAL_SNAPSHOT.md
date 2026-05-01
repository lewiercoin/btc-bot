# Funnel Analytics - Local Production Snapshot Fallback

**Date:** 2026-04-29  
**Operator:** Codex  
**Scope:** Read-only funnel analysis; no live strategy/runtime changes.

---

## Data Source Status

**Decision-grade production query was blocked.**

- Required source of truth per `docs/DATA_SOURCES.md`: production server `root@204.168.146.253`.
- Local environment does not expose `ssh`, `plink`, or global `python`.
- Fallback interpreter used: `.venv/Scripts/python.exe`.
- Fallback DB used: `storage/btc_bot_prod_snapshot.db`.
- Snapshot file modified: 2026-04-27 local filesystem time.
- `PRAGMA quick_check` failed with `database disk image is malformed`.
- `decision_outcomes`, `signal_candidates`, `executable_signals`, `positions`, and `trade_log` were readable.
- `feature_snapshots` read failed during direct inspection, so this report uses `decision_outcomes.details_json` plus candidate/trade tables.

**Decision-grade status:** NOT_DECISION_GRADE_FOR_CURRENT_PRODUCTION.

This report is still useful as a local snapshot diagnosis of the decision funnel, but it must not be treated as the current live runtime truth.

**Superseded by:** `docs/analysis/FUNNEL_ANALYTICS_2026-04-29_PRODUCTION.md`, created after locating the Windows OpenSSH client at `C:\Windows\System32\OpenSSH\ssh.exe` and querying the production database directly.

---

## Window

Readable `decision_outcomes` window:

- Start: `2026-04-20T10:00:00.002987+00:00`
- End: `2026-04-27T12:30:00.003616+00:00`
- Rows: `1004`

Readable closed trade window in `trade_log`:

- Full DB: `790` closed trades from `2022-03-09` to `2026-04-27`
- Since `2026-04-20`: `15` closed trades

---

## Funnel Summary

| Stage | Count | Rate |
|---|---:|---:|
| Decision rows | 1004 | 100.0% |
| Safe-mode skips | 73 | 7.3% of rows |
| Evaluated decision rows | 931 | 92.7% of rows |
| No SignalCandidate | 847 | 91.0% of evaluated |
| SignalCandidate created | 84 | 9.0% of evaluated |
| Governance veto | 57 | 67.9% of candidates |
| Risk block | 12 | 14.3% of candidates |
| Executed/opened trade outcome | 15 | 17.9% of candidates |

Candidate-to-trade conversion is low primarily because governance vetoed duplicate levels, not because risk rejected most candidates.

---

## No-Candidate Attribution

| Reason | Count | Interpretation |
|---|---:|---|
| `uptrend_continuation_weak` | 627 | Main no-signal bottleneck; all rows in `uptrend`. |
| `direction_unresolved` | 113 | Sweep/reclaim present in some cases, but flow/direction did not resolve. |
| `no_reclaim` | 106 | Sweep present but reclaim missing. |
| `regime_direction_whitelist` | 1 | Not currently a major blocker in this snapshot. |
| `confluence_below_min` | 0 | No observed evidence that `confluence_min` is the active bottleneck. |
| `context_unfavorable` | 0 | No observed context blocking in this snapshot. |

The dominant pre-candidate issue is not a generic lack of events. The bot frequently sees sweep-like conditions, but the uptrend continuation path rejects most of them as weak.

---

## Candidate Attribution

Signal candidates since `2026-04-20`:

| Setup | Regime | Direction | Count | Avg Score |
|---|---|---|---:|---:|
| `liquidity_sweep_reclaim_long` | `uptrend` | `LONG` | 76 | 11.89 |
| `liquidity_sweep_reclaim_long` | `crowded_leverage` | `LONG` | 8 | 17.88 |

Candidate downstream outcomes:

| Outcome | Count | Avg Score | Notes |
|---|---:|---:|---|
| `governance_veto` | 57 | 10.98 | 56 duplicate-level vetoes, 1 cooldown veto |
| `risk_block` | 12 | 15.26 | 11 `rr_below_min`, 1 `max_open_positions` |
| `signal_generated` | 15 | 15.85 | Corresponds to 15 closed trades since `2026-04-20` |

High confluence did not guarantee execution. Several high-score candidates were blocked by RR or duplicate-level governance.

---

## Trade Outcomes Since 2026-04-20

| Metric | Value |
|---|---:|
| Trades | 15 |
| Closed | 15 |
| Wins | 8 |
| Losses/non-wins | 7 |
| Win rate | 53.3% |
| Sum R | +6.09R |
| Expectancy | +0.406R |

By exit reason:

| Exit | Count | Sum R | Avg R |
|---|---:|---:|---:|
| `TP` | 10 | +10.49R | +1.049R |
| `SL` | 4 | -4.00R | -1.000R |
| `TIMEOUT` | 1 | -0.40R | -0.401R |

Important limitation: `fees_total`, `funding_paid`, and `slippage_bps_avg` were all `0.0` in these 15 rows. Treat this as paper/backtest-style accounting, not final post-cost live expectancy.

---

## Key Findings

1. The active blocker is not `confluence_min`.

There were no `confluence_below_min` rows in the readable decision window. Changing confluence before deeper attribution would be weakly justified.

2. The major pre-candidate blocker is uptrend participation quality.

`uptrend_continuation_weak` accounts for 627 rows, all under `uptrend`. This supports the thesis that the bot is often in an uptrend market where continuation logic exists but rejects most cases.

3. The major post-candidate blocker is duplicate-level governance.

56 of 57 governance vetoes were `duplicate_level`. This may be correct anti-overtrading protection, but it is the largest candidate-to-trade compression point.

4. Risk blocks are mostly RR-related.

11 of 12 risk blocks were `rr_below_min`. This suggests level geometry/entry-stop-TP spacing matters more than raw signal score for execution eligibility.

5. Context gating is not currently the observed blocker.

Only 3 rows had populated context fields in this snapshot, all `context_eligible=1` and `context_neutral_mode_active=1`. Context remains a measurement/telemetry path here, not an active suppressor.

6. Snapshot integrity prevents decision-grade closure.

Because production SSH is unavailable locally and the snapshot fails `quick_check`, these results are diagnostic only.

---

## Recommended Next Step

Do not change live logic from this report alone.

Next safe step:

- Run the same funnel directly on production via SSH, or refresh a clean production DB snapshot.
- Add a report query that separates:
  - raw sweep/reclaim diagnostics,
  - uptrend continuation weak reasons,
  - duplicate-level veto clusters,
  - RR-block level geometry,
  - post-cost trade outcomes.

Decision candidates after clean production funnel:

- If `uptrend_continuation_weak` remains dominant, investigate continuation setup quality before adding new setup logic.
- If `duplicate_level` remains dominant, audit whether governance is correctly preventing overtrading or suppressing distinct valid opportunities.
- If `rr_below_min` remains dominant, analyze stop/target geometry rather than score thresholds.

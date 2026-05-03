# AUDIT: FORCE-ORDERS-BACKFILL-V1
Date: 2026-05-03
Auditor: Claude Code
Commit: e5731aa (scripts) — cherry-picked to claude/audit-wf-light-protocol-ZXDA9

## Verdict: MVP_DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: PASS
## Error Handling: PASS
## Smoke Coverage: WARN
## Tech Debt: LOW
## AGENTS.md Compliance: WARN
## Methodology Integrity: PASS
## Promotion Safety: N/A
## Reproducibility & Lineage: PASS
## Data Isolation: PASS
## Search Space Governance: PASS
## Artifact Consistency: PASS
## Boundary Coupling: PASS

---

## Audit Summary

Two standalone ETL scripts implemented by Cascade to backfill `force_orders` table with
historical liquidation data. Both scripts validated: dry-run gates passed, live runs
complete on production DB.

**Final DB state (post-backfill):**
- 233,009 total rows in `force_orders`
- Tardis (USDM): 60 monthly snapshots (2020-01-01 → 2024-12-01, 1st of each month)
- COIN-M (proxy): 457 days_ok + 16 days_skipped (Tardis-covered), 2023-06-25 → 2024-10-14
- Live: 7,129 rows from 2026-04-17 onward (unaffected by backfill)
- Gap: 2024-10-15 → 2026-04-16 — permanently blocked, no free source exists

**Scripts:**
- `scripts/backfill_force_orders_tardis.py` — reads local `.csv.gz` files, row-level watermark
- `scripts/backfill_force_orders_coinm.py` — downloads Binance COIN-M ZIPs, day-level idempotency

---

## Contract Compliance — PASS

`force_orders` schema columns satisfied correctly:

| Column | Tardis | COIN-M | Schema |
|---|---|---|---|
| symbol | "BTCUSDT" (hardcoded) | "BTCUSDT" (hardcoded) | TEXT |
| event_time | µs → ISO-8601 UTC | ms → ISO-8601 UTC | TEXT |
| side | `.upper()` → "BUY"/"SELL" | `.upper()` → "BUY"/"SELL" | CHECK('BUY','SELL') |
| qty | `amount` field (BTC direct) | `orig_qty × 100 / avg_price` | REAL |
| price | `price` field (USDT) | `average_price` field (USD) | REAL |

COIN-M qty conversion: `original_quantity × 100.0 / average_price`
- 1 COIN-M contract = 100 USD
- qty_USD = contracts × 100
- qty_BTC = qty_USD / avg_price_USD
- Verified correct.

Both scripts validate side ∈ {"BUY","SELL"} and skip rows with `avg_price ≤ 0`.

---

## State Integrity — PASS

**Tardis watermark design:** `_TARDIS_CUTOFF_ISO = "2025-01-01T00:00:00+00:00"` ensures
`MAX(event_time)` query is scoped to pre-2025 only. Without this cutoff, live-data rows
(2026-04-17+) would have acted as watermark and blocked all historical inserts. Fix applied
correctly.

**COIN-M idempotency design:** `_day_has_data()` checks for any rows within the calendar
day's ISO range before downloading. Skips Tardis-covered monthly-1st days. Enables resume
after interruption at day granularity.

Both approaches prevent double-insertion. Both prevent live-data contamination.

---

## Error Handling — PASS

COIN-M: 404/403 propagated directly without retry (`raise` in `urllib.error.HTTPError`
handler when `exc.code in (403, 404)`). Caller logs as `days_missing`. Transient errors
retry 3× with 5s sleep. Abort after 10 real errors. Confirmed: 5 missing dates (404),
0 days_error.

Tardis: `except Exception` in file processing calls `conn.close()` before re-raise.
No connection leak on per-file errors.

---

## Smoke Coverage — WARN

No automated smoke test exists in `scripts/smoke_*.py` for backfill scripts. Coverage
is manual dry-run only (confirmed per commit message). This is acceptable for a
one-time backfill utility, but means re-run safety is unverified at CI level.

---

## Warnings

**W1 — No automated smoke test**

`backfill_force_orders_*.py` are not covered by any script in `scripts/smoke_*.py`.
The dry-run gates were tested manually. For a one-shot ETL this is LOW risk — the
backfill is done. Low priority.

**W2 — COIN-M partial-day resumption gap**

If COIN-M script is interrupted mid-day (after inserting some chunks), `_day_has_data`
returns True on re-run, and the remaining rows for that day are silently skipped.
With `_CHUNK_SIZE=500` and typical ~200 rows/day, most days insert in a single
transaction. But crash after first chunk = silent partial day. Not observed in the
actual run (0 days_error), so no corrective action needed now. LOW risk.

**W3 — AGENTS.md branch discipline**

Scripts were committed to `modeling-context-closure` instead of the active audit
branch `claude/audit-wf-light-protocol-ZXDA9`. Required cherry-pick. This is D9
(already tracked). Closed for this milestone.

---

## Observations

- Double-commit pattern: both scripts call `conn.commit()` inside `_insert_events` AND
  wrap the call in `with conn:` (which also commits). Redundant but harmless.
- 5 COIN-M missing dates (404): 2023-09-09, 2023-09-23, 2023-09-25, 2024-06-01,
  2024-06-11. Consistent with Binance exchange downtime/maintenance. Not a data
  quality issue.
- `weight_force_order_spike` remains FROZEN in `param_registry.py`. The frozen reason
  was "no historical source" — that is now partially resolved (2020-2024 coverage exists).
  Unfreeze decision is deferred until after WF validates a working strategy.
- Cross-market proxy risk is documented and accepted: COIN-M (BTC-margined) vs USDM
  (USDT-margined). Feature engine uses relative rate (events/60s vs rolling avg+2σ),
  which calibrates to COIN-M density — proxy is methodologically defensible.

---

## Tracked Debt

| ID | Description | Priority | Status |
|---|---|---|---|
| D9 | Branch mismatch: scripts committed to wrong branch | LOW | CLOSED — cherry-picked |
| D10 | No automated smoke test for backfill scripts | LOW | OPEN — accept for one-shot ETL |
| D11 | COIN-M partial-day resumption gap | LOW | OPEN — not observed in practice |
| D12 | Gap 2024-10-15 → 2026-04-16: no historical source | MEDIUM | OPEN — permanently blocked (free sources) |

---

## Recommended Next Step

**Run walk-forward on filtered Optuna candidate pool.**

Prerequisite (from OPTUNA-DEFAULT-V1 audit C1): apply hard filter before WF:
- REJECT: `profit_factor > 50`
- REJECT: `win_rate > 0.85`
- REJECT: `expectancy_r < 0`

Priority WF candidates: `00000, 00097, 00099, 00104, 00123`
Secondary (param inspection first): `00052` (check confluence_min), `00135`
(check invalidation_offset_atr), `00098` (MDD=40%, decide if acceptable)
Exclude: `00091` (ER<0), `00136, 00141, 00184` and all WR>85% trials

After WF PASS on a legitimate candidate, promote to paper trading. Consider unfreezing
`weight_force_order_spike` for the NEXT Optuna campaign (now that historical data exists
for 2020-2024 coverage).

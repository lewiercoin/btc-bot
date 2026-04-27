# RESEARCH-DATA-INVENTORY

> Read-only data coverage report for offline Optuna research.
> No optimization run. No production config changes.

**Date:** 2026-04-27
**DB:** `storage\btc_bot_prod_snapshot.db`
**Symbol:** `BTCUSDT`

---

## 1. OHLCV Coverage (candles)

Table: `candles` — ✅

| Timeframe | Count | Earliest | Latest | Span (d) | Coverage % | Gaps >2× |
|-----------|-------|----------|--------|----------|------------|----------|
| 15m | 197,262 | 2020-09-01 00:00:00 | 2026-04-17 19:15:00 | 2054 | ✅ 100.0% | ✅ 0 |
| 1h | 49,311 | 2020-09-01 00:00:00 | 2026-04-17 14:00:00 | 2054 | ✅ 100.0% | ✅ 0 |
| 4h | 12,328 | 2020-09-01 00:00:00 | 2026-04-17 12:00:00 | 2054 | ✅ 100.0% | ✅ 0 |

**Total candles (all TF):** 258,901

---

## 2. Funding Coverage

Table: `funding` — ✅

- **Count:** 6,164
- **Earliest:** 2020-09-01 00:00:00
- **Latest:** 2026-04-17 08:00:00
- **Gaps > 16h:** ✅ 0 (max gap: 0.0h, expected ≤ 8h)

---

## 3. Open Interest Coverage

Table: `open_interest` — ✅

- **Count:** 526,496
- **Earliest:** 2020-09-01 00:00:00
- **Latest:** 2026-04-17 14:00:00

---

## 4. CVD / Flow Coverage (aggtrade_buckets)

Table: `aggtrade_buckets` — ✅

| Timeframe | Count | Earliest | Latest | Gaps >2× |
|-----------|-------|----------|--------|----------|
| 15m | 195,175 | 2020-09-01 00:00:00 | 2026-04-17 14:00:00 | ✅ 5 |
| 60s | 2,927,483 | 2020-09-01 00:00:00 | 2026-04-17 14:04:00 | ⚠️ 14 |

---

## 5. Market Truth Snapshots

**market_snapshots** — ✅
- Count: 681 | 2026-04-23 19:00:00 → 2026-04-27 12:30:00

**feature_snapshots** — ✅
- Count: 681 | 2026-04-23 19:00:00 → 2026-04-27 12:30:00

**decision_outcomes** — ✅
- Count: 1,004 | 2026-04-20 10:00:00 → 2026-04-27 12:30:00
- With snapshot_id: 681 (67.8%)
- With feature_snapshot_id: 681 (67.8%)

---

## 6. Trade Log

Table: `trade_log` — ✅

- **Total trades:** 790 (closed: 790)
- **Earliest opened:** 2022-03-09 18:30:00
- **Latest opened:** 2026-04-27 06:45:04
- **With non-zero fees:** 0 / 790 (0.0%)
- **With non-zero funding_paid:** 0 / 790 (0.0%)

---

## 7. Supplementary Tables

**force_orders** — ✅
- Count: 7,129 | 2026-04-17 14:13:16 → 2026-04-23 17:02:10

**daily_external_bias** — ✅
- Count: 1,422 | 2020-09-01 → 2026-04-26
- With ETF bias: 0 | With DXY close: 1,422

---

## 8. Backtest Readiness Assessment

**Proposed range:** `2024-01-01 -> 2026-04-27`
**Recommended range:** `2020-09-01 -> 2026-04-17`
**Verdict:** ✅ **READY** — All required data sources present and coverage looks adequate.

### Next Steps

Based on this report, choose:

- **A)** Run Optuna on full recommended range ← only if READY or READY_WITH_WARNINGS
- **B)** Narrow the search range to well-covered periods
- **C)** Backfill missing data (funding, OI, aggtrade_buckets) before running
- **D)** Smoke research only (1 window, 10 trials) to validate pipeline end-to-end

**Do NOT run full Optuna until this report is reviewed.**

---

*Generated: 2026-04-27 UTC — read-only, no runtime changes.*

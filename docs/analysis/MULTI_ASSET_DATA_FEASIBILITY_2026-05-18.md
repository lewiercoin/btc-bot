# Multi-Asset Data Feasibility

**Milestone:** `MULTI_ASSET_DATA_FEASIBILITY_V1`
**Status:** READY_FOR_AUDIT
**Scope:** Research Lab data-quality diagnostic only; no market data persisted; no runtime/core changes.

## Purpose

Check whether ETH/SOL-style multi-asset research is worth scheduling by validating source availability, sample cleanliness, archive paths, and local DB inventory before any full historical backfill.

## Local Inventory

- Source DB: `research_lab\snapshots\replay-run13-regime-aware-trial-00063.db`
- DB exists: `True`

| Table | BTCUSDT Rows | ETHUSDT Rows | ETHUSDT Range |
|---|---:|---:|---|
| `candles` | 256394 | 0 | - to - |
| `funding` | 6105 | 0 | - to - |
| `open_interest` | 524971 | 0 | - to - |
| `aggtrade_buckets` | 3122272 | 0 | - to - |
| `force_orders` | 0 | 0 | - to - |

## Sample Source Results

### ETHUSDT

**Builder verdict:** `PASS_SAMPLE_SOURCE_FEASIBLE_FULL_BACKFILL_REQUIRED`
**Gate verdict:** `MARGINAL`
**Sample window:** 2026-05-11T11:00:00+00:00 to 2026-05-18T11:00:00+00:00
**Archive probe day:** 2026-05-15

| Dataset | OK | Rows | Expected | Missing Rate | Duplicates | Quality Errors |
|---|---|---:|---:|---:|---:|---:|
| `candles_15m` | `True` | 673 | 672 | 0.00% | 0 | 0 |
| `candles_4h` | `True` | 180 | 180 | 0.00% | 0 | 0 |
| `funding` | `True` | 21 | 21 | 0.00% | 0 | 0 |
| `open_interest_15m` | `True` | 673 | 673 | 0.00% | 0 | 0 |
| `aggtrade_60s` | `True` | 3 | 60 | 95.00% | 0 | 0 |
| `book_ticker` | `True` | 1 | 1 | 0.00% | 0 | 0 |

| Archive Family | OK | Status |
|---|---|---:|
| `klines_15m_daily_zip` | `True` | 200 |
| `metrics_daily_zip` | `True` | 200 |
| `aggtrades_daily_zip` | `True` | 200 |
| `liquidation_snapshot_daily_zip` | `False` | 404 |

| Gate | Threshold | Actual | Status | Severity |
|---|---:|---:|---|---|
| api_families_ok | == 1.0 | 1.0 | PASS | REQUIRED |
| candles_15m_missing_rate | <= 0.01 | 0.0 | PASS | REQUIRED |
| candles_15m_quality_errors | == 0 | 0.0 | PASS | REQUIRED |
| candles_15m_duplicates | == 0 | 0.0 | PASS | REQUIRED |
| candles_4h_missing_rate | <= 0.01 | 0.0 | PASS | REQUIRED |
| funding_rows | >= 10 | 21.0 | PASS | RECOMMENDED |
| open_interest_rows | >= 100 | 673.0 | PASS | RECOMMENDED |
| aggtrade_rows | >= 45 | 3.0 | FAIL | RECOMMENDED |
| archive_families_ok | >= 0.75 | 0.75 | PASS | RECOMMENDED |

Key metrics:
- API families OK: 100%
- Archive families OK: 75%
- Local required tables present: 0/5

## Builder Interpretation

- Local research snapshot is BTC-only for the required trial-00095 data families.
- A clean ETH sample can justify a later historical backfill milestone, but it is not itself enough for ETH strategy research.
- Full transfer research should not start until 2022-2026 ETH 15m/4h candles, funding, OI, and aggtrade/TFI coverage are materialized and audited.
- Force-order/liquidation data should remain diagnostic or disabled unless its archive coverage is proven separately.

## Audit Questions

1. Did the milestone avoid writing market data or modifying runtime/core/settings?
2. Are local DB inventory results separated from external sample-source checks?
3. Are ETH sample quality gates explicit and reproducible?
4. Does the report avoid claiming ETH research is ready without a full historical backfill?
5. Are archive coverage risks documented before scheduling a 2022-2026 backfill?

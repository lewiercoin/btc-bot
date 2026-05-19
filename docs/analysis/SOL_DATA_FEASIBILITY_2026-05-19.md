# SOL Data Feasibility

**Milestone:** `SOL_DATA_FEASIBILITY_V1`
**Status:** `PASS_SOL_ARCHIVE_SOURCE_FEASIBLE_REST_AGGTRADE_SAMPLE_LIMIT_FULL_BACKFILL_REQUIRED`
**Scope:** Research Lab data-quality diagnostic only; no market data persisted; no runtime/core changes.

## Purpose

Check whether SOLUSDT has enough source availability and sample quality to justify a later full historical backfill and frozen trial-00095 transfer test.

## Local Inventory

- Source DB: `research_lab\snapshots\replay-run13-regime-aware-trial-00063.db`
- DB exists: `True`

| Table | BTCUSDT Rows | SOLUSDT Rows | SOLUSDT Range |
|---|---:|---:|---|
| `candles` | 256394 | 0 | - to - |
| `funding` | 6105 | 0 | - to - |
| `open_interest` | 524971 | 0 | - to - |
| `aggtrade_buckets` | 3122272 | 0 | - to - |
| `force_orders` | 0 | 0 | - to - |

## Recent Sample Source Results

**Symbol:** `SOLUSDT`
**Builder verdict:** `PASS_SOL_ARCHIVE_SOURCE_FEASIBLE_REST_AGGTRADE_SAMPLE_LIMIT_FULL_BACKFILL_REQUIRED`
**Sample gate verdict:** `MARGINAL`
**Sample window:** 2026-05-12T16:00:00+00:00 to 2026-05-19T16:00:00+00:00
**Recent archive probe day:** 2026-05-16

| Dataset | OK | Rows | Expected | Missing Rate | Duplicates | Quality Errors | Zero Volume |
|---|---|---:|---:|---:|---:|---:|---:|
| `candles_15m` | `True` | 673 | 672 | 0.00% | 0 | 0 | 0 |
| `candles_4h` | `True` | 181 | 180 | 0.00% | 0 | 0 | 0 |
| `funding` | `True` | 21 | 21 | 0.00% | 0 | 0 | 0 |
| `open_interest_15m` | `True` | 673 | 673 | 0.00% | 0 | 0 | 0 |
| `aggtrade_60s` | `True` | 5 | 60 | 91.67% | 0 | 0 | 0 |
| `book_ticker` | `True` | 1 | 1 | 0.00% | 0 | 0 | 0 |

## Recent Archive Probes

| Archive Family | OK | Status |
|---|---|---:|
| `klines_15m_daily_zip` | `True` | 200 |
| `metrics_daily_zip` | `True` | 200 |
| `aggtrades_daily_zip` | `True` | 200 |
| `liquidation_snapshot_daily_zip` | `False` | 404 |

## Historical Archive Probes

**Historical archive OK share:** 100.0%

| Probe | OK | Status |
|---|---|---:|
| `2022-01-01_klines_15m` | `True` | 200 |
| `2022-01-01_metrics` | `True` | 200 |
| `2022-01-01_aggtrades` | `True` | 200 |
| `2023-01-01_klines_15m` | `True` | 200 |
| `2023-01-01_metrics` | `True` | 200 |
| `2023-01-01_aggtrades` | `True` | 200 |
| `2024-01-01_klines_15m` | `True` | 200 |
| `2024-01-01_metrics` | `True` | 200 |
| `2024-01-01_aggtrades` | `True` | 200 |
| `2025-01-01_klines_15m` | `True` | 200 |
| `2025-01-01_metrics` | `True` | 200 |
| `2025-01-01_aggtrades` | `True` | 200 |

## Gates

| Gate | Threshold | Actual | Status | Severity |
|---|---:|---:|---|---|
| api_families_ok | == 1.0 | 1.0 | PASS | REQUIRED |
| candles_15m_missing_rate | <= 0.01 | 0.0 | PASS | REQUIRED |
| candles_15m_quality_errors | == 0 | 0.0 | PASS | REQUIRED |
| candles_15m_duplicates | == 0 | 0.0 | PASS | REQUIRED |
| candles_4h_missing_rate | <= 0.01 | 0.0 | PASS | REQUIRED |
| funding_rows | >= 10 | 21.0 | PASS | RECOMMENDED |
| open_interest_rows | >= 100 | 673.0 | PASS | RECOMMENDED |
| aggtrade_rows | >= 45 | 5.0 | FAIL | RECOMMENDED |
| archive_families_ok | >= 0.75 | 0.75 | PASS | RECOMMENDED |

## Builder Interpretation

- Recent API families OK: 100%
- Recent archive families OK: 75%
- Historical archive families OK: 100%
- Local required SOL tables present: 0/5
- REST aggtrade sample is limited for SOL activity; daily aggTrades archive availability is the relevant full-backfill signal.
- A clean sample does not approve SOL strategy research.
- Full SOL backfill is required before any SOL trial-00095 transfer test.
- SOL runtime, shadow, PAPER, and threshold changes are out of scope.

## Audit Questions

1. Did the milestone avoid writing market data or modifying runtime/core/settings?
2. Are local DB inventory results separated from external source checks?
3. Are SOL recent sample quality gates explicit and reproducible?
4. Are historical archive probes sufficient to decide whether full SOL backfill is worth scheduling?
5. Does the report avoid claiming SOL research or runtime readiness before full backfill and audit?

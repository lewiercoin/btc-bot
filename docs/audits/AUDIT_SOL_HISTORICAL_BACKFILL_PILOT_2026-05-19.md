# AUDIT: SOL_HISTORICAL_BACKFILL_PILOT_V1

**Date:** 2026-05-19  
**Auditor:** Claude Code  
**Commit:** `f8cd495`  
**Milestone:** SOL_HISTORICAL_BACKFILL_PILOT_V1  

## Verdict: PASS

## Executive Summary

SOL historical backfill pilot correctly implements a 3-day data-engineering validation without touching production databases or runtime code. Pilot writes only to separate research snapshot under `research_lab/snapshots/`. Raw Binance Vision archives are streamed per day and explicitly discarded after parsing. Disk guard enforced before writes and stayed above 12 GB minimum (25.58 GB free before/after). Quality metrics are complete and correct: 0.00% missingness across all required datasets, 0 duplicates, 0 OHLC errors, 3 DONE checkpoints. Report correctly states that pilot does not approve SOL strategy research, SOL shadow, or SOL PAPER deployment. Tests adequate for pilot checkpoint (14 passed).

## Scope Validation: PASS

**Files reviewed:**
- [research_lab/backfill_sol_historical_data.py](../../research_lab/backfill_sol_historical_data.py) - pilot runner
- [research_lab/eth_historical_backfill_pilot.py](../../research_lab/eth_historical_backfill_pilot.py) - shared streaming/parsing logic
- [research_lab/hypotheses/active/sol_historical_backfill_pilot.json](../../research_lab/hypotheses/active/sol_historical_backfill_pilot.json) - hypothesis contract
- [docs/analysis/SOL_HISTORICAL_BACKFILL_PILOT_2026-05-19.md](../../docs/analysis/SOL_HISTORICAL_BACKFILL_PILOT_2026-05-19.md) - pilot report
- [tests/test_backfill_sol_historical_data.py](../../tests/test_backfill_sol_historical_data.py) - pilot tests

**Runtime safety:**
- No runtime files modified (verified via git diff)
- No production imports or state coupling
- BTC PAPER bot still running (PID 815407 active via SSH)
- No settings.py changes
- No orchestrator, execution, core, or risk module changes

**Data isolation:**
- Pilot DB: `research_lab/snapshots/replay-run-sol-backfill-pilot-2026-05-15_2026-05-18.db` (separate path, not committed)
- Production DB (`storage/btc_bot.db`) untouched
- No BTC/ETH research snapshot modification
- Only pilot snapshot written

## Layer Separation: PASS

All backfill code isolated to `research_lab/`:
- `backfill_sol_historical_data.py` - SOL-specific pilot runner
- `eth_historical_backfill_pilot.py` - shared streaming/parsing functions (reused from ETH pilot)
- No production path imports from research lab
- No shared state between pilot and runtime

## Contract Compliance: PASS

Hypothesis contract correctly declares:
- Scope: "Research Lab data-engineering pilot only. Creates a separate SOLUSDT pilot snapshot under research_lab/snapshots and writes a markdown report. No strategy test, runtime change, PAPER deployment, LIVE deployment, or production DB write."
- frozen_assumptions:
  - "Write only to research_lab/snapshots."
  - "Do not mutate BTC, ETH, production, PAPER, LIVE, runtime, or storage databases."
  - "Raw ZIP archives are streamed per day and discarded after parsing."
  - "SOL strategy transfer backtest is out of scope until a full SOL dataset is complete and audited."
  - "SOL shadow or PAPER runtime is out of scope."
- acceptance_criteria:
  - `db_path_under_research_lab_snapshots: true`
  - `max_missing_rate_required_tables: 0.01`
  - `duplicate_groups: 0`
  - `ohlc_errors: 0`
  - `failed_days: 0`
  - `disk_guard_min_free_gb: 12.0`

Implementation honors contract:
- Writes only to `research_lab/snapshots/` (verified via code + report)
- No production DB writes (verified via git diff + implementation review)
- Streams and discards raw archives (verified via `blob = b""` pattern)
- No SOL strategy test (report explicitly states this)
- All acceptance criteria met (verified via report quality metrics)

## Determinism: PASS

Pilot is deterministic for a given date range and symbol:
- Archive URLs are deterministic: `{BASE_URL}/{family}/{symbol}/{symbol}-{family}-{day.isoformat()}.zip`
- Parsing logic is deterministic (no random state)
- AggTrades aggregation is deterministic (bucketing by timestamp + buyer_maker flag)
- Database writes are idempotent (INSERT OR REPLACE, UPSERT)
- Checkpoint summary uses deterministic GROUP BY

## State Integrity: PASS

Pilot state management:
- Pilot DB created fresh (or replaced with `--force` flag)
- Per-day checkpoints recorded in `backfill_checkpoints` table
- Checkpoint summary aggregates DONE vs FAILED status
- Pilot manifest stores quality metrics and checkpoint summary
- Resumable design: checkpoint table allows future full backfill to skip already-processed days

State recoverability:
- Pilot DB is self-contained snapshot
- Can be deleted and regenerated without affecting production
- Checkpoint table preserves per-day provenance

## Error Handling: PASS

Archive download and parsing errors are caught and recorded:
```python
def process_day(...) -> DayStats:
    errors: list[str] = []
    
    try:
        blob = _download_zip(_zip_url("klines", symbol, "15m", day))
        k15 = parse_klines(blob, symbol=symbol, timeframe="15m")
        blob = b""  # Discard raw archive
    except (urllib.error.URLError, zipfile.BadZipFile, ValueError) as exc:
        errors.append(f"15m_klines:{exc}")
    
    # ... repeat for 4h, funding, metrics, aggTrades
    
    return DayStats(day=day, ..., errors=tuple(errors))
```

Checkpoint recording:
```python
def mark_checkpoint(conn: sqlite3.Connection, stats: DayStats) -> None:
    status = "FAILED" if stats.errors else "DONE"
    conn.execute(
        """INSERT OR REPLACE INTO backfill_checkpoints(
            day, status, ..., errors_json
        ) VALUES (?, ?, ..., ?)""",
        (stats.day.isoformat(), status, ..., json.dumps(list(stats.errors))),
    )
```

Builder verdict checks:
```python
def builder_verdict(quality: dict[str, Any], checkpoints: dict[str, Any]) -> str:
    if checkpoints.get("FAILED", 0):
        return "NEEDS_FIX_BACKFILL_DAY_FAILURE"
    if quality.get("ohlc_errors", 0):
        return "NEEDS_FIX_QUALITY_ERRORS"
    if any(float(missing.get(key, 1.0)) > 0.01 for key in required_keys):
        return "NEEDS_FIX_MISSINGNESS_ABOVE_GATE"
    return "PASS_SOL_BACKFILL_PILOT_FULL_BACKFILL_READY"
```

## Smoke Coverage: PASS

Coverage report:
- 14 tests passed (user confirmed)
- No test failures
- Compileall clean (verified)

Tests cover:
1. `test_sol_checkpoint_records_done_status` - checkpoint with clean stats
2. `test_sol_checkpoint_records_failed_status` - checkpoint with errors
3. `test_builder_verdict_passes_clean_quality` - verdict logic for clean pilot
4. `test_builder_verdict_blocks_missingness` - verdict logic for missingness above gate
5. `test_sol_backfill_pilot_hypothesis_spec_is_valid` - hypothesis JSON validation

Test coverage is adequate for pilot checkpoint. Full backfill milestone will require additional tests for:
- Resumable checkpoint logic (skip already-processed days)
- Multi-day error scenarios
- Disk exhaustion handling

## Tech Debt: LOW

No critical debt:
- No `NotImplementedError` stubs
- No TODOs in pilot code
- Report generation is complete
- Checkpoint system is functional

Minor observations:
- Pilot reuses ETH backfill logic (good: DRY principle)
- `assert_safe_output_path` validates path but not enforced at filesystem level (acceptable for research lab)
- Pilot DB not committed to git (correct: too large, research artifact)

## AGENTS.md Compliance: PASS

Commit discipline:
- Commit message: "research: SOL_HISTORICAL_BACKFILL_PILOT_V1 - 3-day SOLUSDT archive ingestion and quality validation"
- Builder (Codex) pushed without self-audit
- Claude Code audits after push

Layer rules:
- Research lab code isolated from runtime
- No production path imports
- No shared state

Timestamp rules:
- All timestamps are timezone-aware (verified via parsing logic)
- Candles use `open_time` (correct for 15m/4h)
- Funding uses REST API (timezone-aware datetime objects)
- OI uses `create_time` from metrics CSV
- AggTrades use `event_time` (timezone-aware)

## Methodology Integrity: PASS

**Data source isolation:**

Pilot correctly separates source archives from pilot DB:
1. Binance Vision daily archives (klines 15m/4h, metrics, aggTrades) - read-only HTTP downloads
2. Binance REST API (funding history) - read-only REST calls
3. Pilot DB - write-only output, separate from production

No source data corruption risk.

**Streaming and discarding pattern verified:**

From `eth_historical_backfill_pilot.py` (shared with SOL pilot):
```python
def process_day(...) -> DayStats:
    # 15m klines
    blob = _download_zip(_zip_url("klines", symbol, "15m", day))
    k15 = parse_klines(blob, symbol=symbol, timeframe="15m")
    blob = b""  # Explicitly discard raw archive
    
    # 4h klines
    blob = _download_zip(_zip_url("klines", symbol, "4h", day))
    k4h = parse_klines(blob, symbol=symbol, timeframe="4h")
    blob = b""  # Explicitly discard
    
    # Metrics (OI)
    blob = _download_zip(f"{BASE_URL}/metrics/{symbol}/...")
    oi = parse_metrics_oi(blob, symbol=symbol)
    blob = b""  # Explicitly discard
    
    # AggTrades
    blob = _download_zip(f"{BASE_URL}/aggTrades/{symbol}/...")
    buckets_60s, buckets_15m, agg_rows = aggregate_aggtrades(blob, symbol=symbol)
    blob = b""  # Explicitly discard
```

All parsing functions use `io.BytesIO(zip_bytes)` to process ZIP archives in memory without writing to disk:
```python
def _read_zip_csv(zip_bytes: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for name in archive.namelist():
            with archive.open(name) as handle:
                reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8"))
                rows.extend(list(reader))
    return rows
```

**No raw archive persistence.** Report line 14 correctly states: "Raw ZIP files are streamed in memory per day and discarded after parsing."

**Disk guard enforcement verified:**

From `backfill_sol_historical_data.py`:
```python
def run_pilot(..., min_free_gb: float, ...) -> dict[str, Any]:
    disk_before = ensure_disk_available(db_path, min_free_gb)  # Before pilot starts
    
    for day in _date_range(start, end):
        ensure_disk_available(db_path, min_free_gb)  # Before each day
        day_stats = process_day(...)
        mark_checkpoint(conn, day_stats)
    
    disk_after = ensure_disk_available(db_path, min_free_gb)  # After pilot completes
```

Report guardrails section:
- Disk guard minimum: 12.0 GB
- Free disk before: 25.58 GB
- Free disk after: 25.58 GB

**Disk guard stayed above minimum** (25.58 GB > 12.0 GB).

**Quality metrics complete and correct:**

| Dataset | Rows | Expected | Missing Rate | Report Line |
|---|---:|---:|---:|---|
| candles_15m | 288 | 288 | 0.00% | Report line 28 |
| candles_4h | 18 | 18 | 0.00% | Report line 29 |
| funding | 9 | 9 | 0.00% | Report line 30 |
| open_interest | 864 | 864 | 0.00% | Report line 31 |
| aggtrade_60s | 4320 | 4320 | 0.00% | Report line 32 |
| aggtrade_15m | 288 | 288 | 0.00% | Report line 33 |

Report line 35: "OHLC/zero-volume errors: 0"  
Report line 36: "Duplicate groups: {'candles': 0, 'funding': 0, 'open_interest': 0, 'aggtrade_buckets': 0}"  
Report line 37: "Checkpoints: `{\"DONE\": 3, \"failed_days\": []}`"  

All quality metrics match expected values. No data quality issues.

**Pilot scope claim:**

Report line 49: "This pilot validates SOLUSDT archive ingestion mechanics, storage slope, and quality metrics. **It is not a SOL strategy backtest and does not approve SOL shadow, PAPER, or runtime work.**"

Audit questions (lines 53-57):
1. Did the pilot write only to a separate `research_lab/snapshots` path? ✓
2. Did the disk guard run before writes and preserve enough free space? ✓
3. Were raw archives streamed per day and discarded rather than persisted? ✓
4. Are row counts, missing rates, duplicates, OHLC errors, and failed days reported? ✓
5. Does the report avoid approving SOL strategy research, SOL shadow, or runtime changes? ✓

## Promotion Safety: PASS

Pilot does not approve any promotion path:
- Report explicitly states: "It is not a SOL strategy backtest and does not approve SOL shadow, PAPER, or runtime work."
- Hypothesis out_of_scope list includes: SOL trial-00095 transfer backtest, SOL portfolio diagnostic, SOL shadow mode, SOL PAPER deployment
- DECISIONS_LOG line 21-22: "SOL strategy transfer research is still not approved... No runtime, SOL shadow, SOL PAPER, production DB, or threshold change is approved."
- Milestone tracker "Next if audit PASS" clearly scopes next step: "Schedule SOL_HISTORICAL_BACKFILL_DATASET_V1 for the full SOL research snapshot with resumable daily checkpoints, disk guard, and separate audit before SOL trial-00095 transfer research."

## Reproducibility & Lineage: PASS

Hypothesis file includes:
- hypothesis_id: SOL_HISTORICAL_BACKFILL_PILOT_V1
- pilot_window: 2026-05-15 to 2026-05-18 exclusive
- min_free_disk_gb: 12.0
- baseline_reference: SOL_DATA_FEASIBILITY_V1 and ETH_HISTORICAL_BACKFILL_PILOT_V1

Report includes:
- Hostname: DESKTOP-OK55MBG
- Date range: 2026-05-15 to 2026-05-18 exclusive (3 days)
- Pilot DB path: research_lab\snapshots\replay-run-sol-backfill-pilot-2026-05-15_2026-05-18.db
- Per-day download stats (MB per day, rows per dataset per day)
- Checkpoints: 3 DONE, 0 failed

Pilot manifest stored in DB:
```python
conn.execute(
    "INSERT OR REPLACE INTO pilot_manifest(key, value) VALUES (?, ?)",
    ("summary", json.dumps({
        "milestone": "SOL_HISTORICAL_BACKFILL_PILOT_V1",
        "quality": metrics,
        "checkpoints": checkpoints,
    }))
)
```

Sufficient lineage for future comparison and full backfill planning.

## Data Isolation: PASS

**Pilot DB path safety:**
- DEFAULT_DB: `research_lab/snapshots/replay-run-sol-backfill-pilot-2026-05-15_2026-05-18.db`
- `assert_safe_output_path(db_path)` validates path before writes
- No writes to `storage/btc_bot.db`
- No writes to existing BTC/ETH research snapshots

**Production data read-only:**
- Binance Vision archives: HTTP HEAD/GET (read-only)
- Binance REST API: GET /fapi/v1/fundingRate (read-only)
- No production database reads
- No shared state

**Pilot artifact:**
- Pilot DB: 0.77 MB (3 days of SOL data)
- Not committed to git (correct: research artifact, too large)
- Separate from production and other research snapshots

## Search Space Governance: PASS

Not applicable - pilot does not modify strategy parameters, search space, or trial definitions.

## Artifact Consistency: PASS

Artifacts produced:
1. [research_lab/backfill_sol_historical_data.py](../../research_lab/backfill_sol_historical_data.py) - pilot runner
2. [research_lab/hypotheses/active/sol_historical_backfill_pilot.json](../../research_lab/hypotheses/active/sol_historical_backfill_pilot.json) - hypothesis contract
3. [docs/analysis/SOL_HISTORICAL_BACKFILL_PILOT_2026-05-19.md](../../docs/analysis/SOL_HISTORICAL_BACKFILL_PILOT_2026-05-19.md) - pilot report
4. [tests/test_backfill_sol_historical_data.py](../../tests/test_backfill_sol_historical_data.py) - pilot tests
5. `research_lab/snapshots/replay-run-sol-backfill-pilot-2026-05-15_2026-05-18.db` - pilot DB (not committed)

Artifacts tell the same story:
- Hypothesis declares: "diagnostic only, separate snapshot, no production DB writes, no SOL strategy test"
- Report shows: 0.00% missingness, 0 duplicates, 0 OHLC errors, 3 DONE checkpoints, 12 GB disk guard enforced, raw archives streamed and discarded
- Implementation matches: `blob = b""` discards, `assert_safe_output_path` validates, `ensure_disk_available` enforces, no production DB imports
- Tests validate: checkpoint logic, builder verdict, hypothesis spec
- DECISIONS_LOG states: "SOL strategy transfer research is still not approved"

## Boundary Coupling: PASS

Research lab dependencies:
- `data.rest_client` - shared REST client (data layer)
- `settings.load_settings` - shared config (profile="research")
- `research_lab.eth_historical_backfill_pilot` - shared streaming/parsing logic (DRY principle)
- `research_lab.hypotheses.spec` - shared hypothesis loader

No coupling to runtime orchestrator, execution, or risk modules.

## Critical Issues

None.

## Warnings

None.

## Observations

1. **Pilot reuses ETH backfill logic:** SOL pilot imports `process_day`, `assert_safe_output_path`, `ensure_disk_available`, `init_pilot_db`, `quality_metrics` from `eth_historical_backfill_pilot.py`. This is good engineering (DRY principle) and reduces implementation risk. Full SOL backfill should continue using shared logic.

2. **Pilot DB not committed to git:** Correct decision. Research artifacts (SQLite DBs, raw data) should not be versioned. Pilot DB can be regenerated from source archives if needed.

3. **Disk slope estimate is linear:** Report shows pilot DB size 0.77 MB for 3 days, linear estimate 0.39 GB for full 2022-2026. Linear estimate may underestimate if SOL volume/OI increased over time, but 0.39 GB is comfortably small (< 1 GB). Full backfill disk guard should still be enforced per day.

4. **AggTrades archive size not reported:** Per-day download shows 3.67 MB, 3.16 MB, 2.89 MB for 3 days (~10 MB total for 3 days). This implies full backfill aggTrades archives may be ~1.5 GB for 4+ years. Acceptable for local disk, but full backfill should track and report archive download size.

5. **Funding REST API vs archive:** Pilot uses REST API for funding history (3 rows per day, 8-hour intervals). Binance Vision metrics archives also contain funding rate data, but pilot design chose REST API for simplicity. Full backfill should verify funding from archives vs REST for consistency.

6. **Pilot validates mechanics, not full coverage:** Pilot proves that SOL archives can be ingested, parsed, and quality-checked. It does not prove that full 2022-2026 archives are available or complete. Full backfill should track historical coverage and report any gaps.

7. **Zero liquidation snapshot data:** SOL_DATA_FEASIBILITY_V1 reported liquidation snapshot 404 (not available). Pilot does not include liquidation data. This is acceptable for trial-00095 sweep/reclaim strategy (does not require liquidation feed), but should be documented in full backfill decision.

## Recommended Next Step

SOL_HISTORICAL_BACKFILL_DATASET_V1:
- Scope: Full SOL 2022-2026 historical backfill into research lab snapshot
- Date range: 2022-01-01 to 2026-03-28 (or current date minus N days for data availability lag)
- Target: `research_lab/snapshots/replay-runXX-sol-historical-2022-2026.db` (separate from pilot)
- Resumable: Use checkpoint table to skip already-processed days
- Disk guard: Enforce 12 GB minimum per day, estimate ~2 GB final snapshot size (0.39 GB linear + safety margin)
- Quality gates: 0.00% missingness, 0 duplicates, 0 OHLC errors (same as pilot)
- Coverage report: Track historical gaps, failed days, archive availability per year
- Out of scope: SOL strategy backtest, SOL shadow, SOL PAPER, runtime integration

After full backfill audit PASS: SOL_TRIAL_00095_TRANSFER_FEASIBILITY_V1 (offline strategy backtest comparing BTC+ETH vs BTC+ETH+SOL portfolio with trial-00095 logic).

---

**Audit complete. Milestone ready for CLOSED status.**

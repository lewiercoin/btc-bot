# AUDIT: ETH_HISTORICAL_BACKFILL_PILOT_V1

**Date:** 2026-05-18  
**Auditor:** Claude Code  
**Commits:** 5d54f5b (implementation), 4fce3c8 (report)  
**Builder:** Codex  

---

## Verdict: PASS

Pilot successfully validates ETH data ingestion mechanics with proper safety guards. Separate research snapshot, streaming archive processing, disk guard enforcement, zero missing data, and no production contamination.

---

## Core Audit Axes

### Layer Separation: PASS

**Scope isolation verified:**
- All code in `research_lab/eth_historical_backfill_pilot.py` (single implementation file)
- No modifications to `core/`, `execution/`, `orchestrator.py`, `main.py`, `runtime/`
- No modifications to `storage/btc_bot.db` or production state
- Imports from `data.rest_client` and `settings` are read-only (REST API config for funding fetch)
- No imports from `storage.repositories`, `storage.state_store`, or execution engines

**Safe path guard:**
```python
def assert_safe_output_path(path: Path) -> None:
    resolved = path.resolve()
    expected = (repo / "research_lab" / "snapshots").resolve()
    if expected not in resolved.parents:
        raise SystemExit(f"Refusing to write outside research_lab/snapshots")
    if "storage" in resolved.parts:
        raise SystemExit(f"Refusing to write pilot data under runtime storage path")
```
- Test verifies: `test_safe_output_path_rejects_runtime_storage()` → SystemExit on `storage/btc_bot.db`

**Output DB:** `research_lab/snapshots/ethusdt_backfill_pilot_2026-05-15_2026-05-18.db` (separate from production)

### Contract Compliance: PASS

**Hypothesis spec:**
- ID: `eth_historical_backfill_pilot_v1`
- Class: `diagnostic_only`
- Status: `ACTIVE`
- Frozen assumptions explicit: "Output must be a separate SQLite database under research_lab/snapshots", "Raw ZIP/CSV archives are not persisted", "ETH strategy backtest is out of scope"
- Acceptance criteria: output path, min_free_disk_gb=12.0, missing rates < 1-5%, ohlc_errors=0, duplicate_groups=0
- Kill criteria: disk_guard_triggered, runtime_db_path, raw_archive_persistence, quality_failure, runtime_change

**Report contract:**
- Scope stated: "Research Lab data-engineering pilot only; separate SQLite snapshot; no runtime DB writes"
- Guardrails documented: hostname, output DB path, disk guard threshold, free disk before/after
- Builder interpretation clear: "This pilot validates mechanics and storage slope... It is not an ETH strategy backtest and does not approve multi-asset runtime work"
- Audit questions explicit and answered

### Determinism: PASS

**Ingestion logic is deterministic:**
- Daily date range iteration: `_date_range(start, end_exclusive)` yields ordered dates
- Day bounds: `datetime(day.year, day.month, day.day, tzinfo=timezone.utc)`
- Timestamp bucketing: `datetime.fromtimestamp(unix - (unix % seconds), tz=timezone.utc)`
- Aggtrade aggregation: deterministic bucket assignment by `transact_time // bucket_seconds`
- No randomness, no sampling, no external state

**Row counts match expectations:**
- 15m candles: 288 = 96/day × 3 days ✓
- 4h candles: 18 = 6/day × 3 days ✓
- Funding: 9 = 3/day × 3 days ✓
- OI (5m): 864 = 288/day × 3 days ✓
- Aggtrade 60s buckets: 4320 = 1440/day × 3 days ✓
- Aggtrade 15m buckets: 288 = 96/day × 3 days ✓

All missing rates: **0.00%**

### State Integrity: PASS

**Separate research snapshot:**
- Schema: `candles`, `funding`, `open_interest`, `aggtrade_buckets`, `pilot_manifest`
- Tables use `UNIQUE` constraints on (symbol, timeframe, timestamp) to prevent duplicates
- PRAGMA journal_mode = WAL (write-ahead log for concurrent reads)
- Pilot DB size: **0.77 MB** for 3 days
- No writes to production `storage/btc_bot.db` (verified by path guard)

**Disk guard enforcement:**
```python
def ensure_disk_available(path: Path, min_free_gb: float) -> dict[str, float]:
    usage = shutil.disk_usage(target)
    free_gb = usage.free / (1024**3)
    if free_gb < min_free_gb:
        raise SystemExit(f"Disk guard blocked pilot: free={free_gb:.2f}GB < required={min_free_gb:.2f}GB")
```
- Called before each daily download
- Min threshold: **12.0 GB**
- Free disk before: **27.07 GB**
- Free disk after: **27.07 GB**
- No disk exhaustion risk

**Production bot unaffected:**
- Report confirms: Bot after pilot = `active`, PAPER process = one (PID 815407)
- No restarts, no interruptions, no state corruption

### Error Handling: PASS

**Per-family error isolation:**
- Each data family (15m klines, 4h klines, funding, OI, aggTrades) wrapped in separate `try/except`
- Errors appended to list: `errors.append(f"15m_klines:{exc}")`
- Failure of one family does not block others
- Report shows: **0 errors** for 3-day pilot window

**Quality validation:**
- OHLC validation: `parse_klines()` checks high >= max(open, close), low <= min(open, close)
- Duplicate detection: SQL UNIQUE constraints + post-hoc duplicate count queries
- Missing rate calculation: `(expected - actual) / expected`
- Zero-volume detection: counted but not rejected (valid market state)

**Network resilience:**
- HTTP timeout: 120 seconds per download
- `urllib.error.URLError` caught per family
- `zipfile.BadZipFile` caught (corrupt archive handling)

### Smoke Coverage: PASS

**5 unit tests, all passing:**
1. `test_parse_klines_skips_header_and_normalizes_rows` - validates kline parsing
2. `test_parse_metrics_oi_reads_sum_open_interest` - validates OI parsing
3. `test_aggregate_aggtrades_builds_60s_and_15m_buckets` - validates TFI/CVD aggregation
4. `test_safe_output_path_rejects_runtime_storage` - validates path guard blocks storage/
5. `test_eth_backfill_pilot_hypothesis_spec_is_valid` - validates hypothesis card structure

**Coverage adequate for pilot scope:**
- Parsing logic tested (klines, OI, aggTrades)
- Aggregation logic tested (60s/15m buckets, TFI/CVD)
- Safety guard tested (storage/ path rejection)
- Hypothesis spec validated

**Compileall:** Clean (no syntax errors)

### Tech Debt: LOW

**No incomplete implementation:**
- No `NotImplementedError` stubs
- No `TODO` comments
- All frozen assumptions implemented
- All acceptance criteria covered

**Acknowledged limitations (by design):**
- Pilot window is 3 days, not full 2022-2026 (intentional - storage slope validation only)
- Funding uses REST API pagination (historical funding requires separate pagination logic for full backfill)
- Linear size estimate may understate peak memory (acknowledged in hypothesis failure_modes)
- SOL deferred until ETH validated (intentional scope boundary)

**Code quality:**
- Type hints throughout (`from __future__ import annotations`)
- Frozen dataclasses for immutability
- Explicit error messages
- Consistent naming conventions

### AGENTS.md Compliance: PASS

**Commit discipline:**
- Implementation commit (5d54f5b): WHAT/WHY/STATUS clear, Co-Authored-By present
- Report commit (4fce3c8): WHAT/WHY/STATUS clear, documents server execution
- No self-audit (Codex delivered READY_FOR_AUDIT, Claude Code audits)

**Layer rules:**
- Research-only changes ✓
- No timestamp manipulation ✓
- No git hook bypass ✓
- Branch: `research/sweep-family-expansion-v1` ✓

---

## Research Lab Audit Axes

### Methodology Integrity: PASS

**Streaming archive processing verified:**
```python
blob = _download_zip(url)         # Downloads to memory
rows = parse_*(blob, ...)          # Processes in-memory
blob = b""                         # Clears memory immediately
```
- No raw ZIP persistence
- No raw CSV persistence
- Memory footprint per day: ~14MB download (largest day), immediately released
- Final DB size: 0.77 MB aggregated data

**Quality metrics honest:**
- Missing rates: all 0.00% (no gaps)
- OHLC errors: 0 (high/low bounds respected)
- Duplicate groups: 0 (UNIQUE constraints enforced)
- Report does not claim full backfill ready - states "pilot validates mechanics"

**Scope boundaries clear:**
- Report: "It is not an ETH strategy backtest"
- Report: "does not approve multi-asset runtime work"
- Hypothesis: "ETH strategy backtest is out of scope until full backfill dataset is audited"

### Promotion Safety: PASS

**No promotion path:**
- Diagnostic milestone only (hypothesis class: `diagnostic_only`)
- No strategy candidate generated
- No approval bundle
- No runtime parameter changes
- Next step clearly stated: full backfill with resumable checkpoints + dataset audit

### Reproducibility & Lineage: PASS

**Pilot parameters explicit:**
- Symbol: ETHUSDT
- Date range: 2026-05-15 to 2026-05-18 exclusive (3 days)
- Disk guard: 12.0 GB minimum free space
- Hostname: ubuntu-btc-bot
- Commit: 5d54f5b (implementation), 4fce3c8 (report)

**Full backfill estimate:**
- Pilot: 0.77 MB for 3 days
- Linear extrapolation: 0.39 GB for 2022-01-01 to 2026-03-28 (~1551 days)
- Calculation: (0.77 MB / 3 days) × 1551 days ≈ 398 MB ≈ 0.39 GB

### Data Isolation: PASS

**Source data read-only:**
- Binance Vision archives: HTTP GET requests (read-only)
- Funding REST API: read-only queries
- No writes to external systems

**Production DB untouched:**
- No `storage/btc_bot.db` writes (verified by path guard)
- No production table modifications
- No runtime state changes

**Separate research snapshot:**
- Output: `research_lab/snapshots/ethusdt_backfill_pilot_2026-05-15_2026-05-18.db`
- Schema independent of production schema
- No foreign key references to production tables

### Search Space Governance: PASS

**Fixed parameters (no search):**
- Symbol: ETHUSDT (no multi-symbol)
- Timeframes: 15m, 4h, 60s, 15m buckets (fixed)
- Disk guard: 12.0 GB (fixed)
- Date range: 3 days (fixed pilot window)

**No optimization:**
- No parameter tuning
- No walk-forward validation
- No strategy search

**Scope: diagnostic data engineering only**

### Artifact Consistency: PASS

**All artifacts tell same story:**
- Hypothesis spec: "diagnostic_only", "ETH strategy backtest out of scope"
- Implementation: separate DB path, streaming logic, disk guard
- Report: "pilot validates mechanics", "not an ETH strategy backtest"
- DECISIONS_LOG: "ETH strategy transfer research remains blocked until full dataset materialized and audited"
- MILESTONE_TRACKER: "data-engineering pilot only", "full backfill still needs... dataset audit before any ETH strategy transfer backtest"

**Metrics consistent:**
- Hypothesis acceptance criteria: missing rates < 1-5%, OHLC errors = 0, duplicates = 0
- Report results: all missing rates 0.00%, OHLC errors 0, duplicates 0
- All criteria met ✓

### Boundary Coupling: PASS

**Minimal production coupling:**
- `data.rest_client.BinanceFuturesRestClient` - read-only REST API calls for funding data
- `settings.load_settings(profile="research")` - read REST API config only
- No imports from `core/`, `execution/`, `orchestrator`, `storage.repositories`, `storage.state_store`

**Research Lab isolated:**
- Self-contained ingestion logic
- Separate schema definition
- No backtest/ dependencies
- No trial registry coupling

---

## Critical Issues

None.

---

## Warnings

None.

---

## Observations

### 1. Full Backfill Storage Estimate: 0.39 GB

**Linear extrapolation from 3-day pilot:**
- 2022-01-01 to 2026-03-28 = 1551 days
- 0.77 MB / 3 days × 1551 days ≈ 398 MB ≈ 0.39 GB

**Assumption risks (acknowledged in hypothesis failure_modes):**
- Archive schema may drift in older historical data
- Peak download/memory pressure during full backfill not measured in pilot
- Funding REST pagination logic needs full implementation for 2022-2026 range

**Mitigation for full backfill:**
- Resumable daily checkpoints (pilot processes day-by-day, easy to resume)
- Disk guard before each day (pilot already implements this)
- Dataset audit after backfill (next milestone deliverable)

### 2. Raw AggTrades Not Persisted

**Key finding:** Streaming + aggregation makes ETH backfill operationally feasible.

**Pilot approach:**
- Download daily aggTrades ZIP (~9-14 MB compressed per day)
- Aggregate to 60s and 15m TFI/CVD buckets in-memory
- Discard raw trades immediately (`blob = b""`)
- Store only bucketed aggregates (~0.26 MB per day)

**Why this matters:**
- Raw aggTrades for 1551 days would be ~15-22 GB compressed, likely 100+ GB uncompressed
- Aggregated buckets for 1551 days: ~0.4 GB total
- 98-99% storage reduction by aggregating at ingestion time

### 3. Production Bot Unaffected

**Report confirms:**
- Bot status after pilot: `active`
- PAPER process: one instance, PID 815407 (no duplicate runtime)
- Disk usage unchanged: 27.07 GB free before and after pilot
- No restarts, no safe mode, no operational impact

**Validation:** Pilot successfully isolated from production runtime.

### 4. Zero Missing Data in Pilot Window

**All families 0.00% missing:**
- 15m candles: 288/288 expected
- 4h candles: 18/18 expected
- Funding: 9/9 expected
- Open interest (5m): 864/864 expected
- Aggtrade 60s buckets: 4320/4320 expected
- Aggtrade 15m buckets: 288/288 expected

**Interpretation:** Recent Binance Vision archives are complete and clean for ETHUSDT. Historical quality requires full backfill validation.

---

## Recommended Next Step

**ACCEPT and CLOSE milestone.** Pilot successfully validates ETH data ingestion mechanics with proper safety guards.

**Next milestone (if ETH direction continues):**
- **Name:** `ETH_HISTORICAL_BACKFILL_DATASET_V1`
- **Scope:** Full 2022-2026 ETHUSDT historical backfill with resumable daily checkpoints
- **Deliverables:**
  - Complete dataset in `research_lab/snapshots/ethusdt_2022_2026.db`
  - Missing rate audit (< 1% for candles, < 5% for aggtrade buckets)
  - OHLC validation audit (zero errors)
  - Duplicate detection audit (zero duplicate groups)
  - Storage footprint report (actual vs pilot estimate)
  - Funding pagination logic for full historical range
- **Safety requirements:**
  - Disk guard enforcement (min 12 GB free)
  - Resumable: daily checkpoint writes, skip already-processed days
  - No production DB writes
  - Streaming + aggregation (no raw archive persistence)
- **Not in scope:** ETH strategy backtest (separate milestone after dataset audit PASS)

**Strategic note:** This pilot removes the main operational blocker for ETH multi-asset research. Storage footprint is small (~0.4 GB), download pressure is manageable (~32 MB/day), and ingestion mechanics are proven. Full backfill is now a data engineering task, not an unknown risk.

---

**Audit Complete**  
**Files Modified:** 0 (audit only)  
**Next Action:** Builder may close milestone; user decides whether to proceed with full ETH backfill

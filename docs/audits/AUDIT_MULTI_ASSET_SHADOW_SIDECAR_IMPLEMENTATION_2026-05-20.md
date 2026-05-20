# AUDIT: MULTI_ASSET_SHADOW_SIDECAR_IMPLEMENTATION_V1

Date: 2026-05-20  
Auditor: Claude Code  
Commit: 7a492df  
Builder: Codex

## Verdict: PASS

## Layer Separation: PASS
- Only `sidecar_main.py`, `research_lab/shadow_*.py`, `tests/test_sidecar_*.py`, `tests/test_shadow_*.py`, `docs/` changed
- No `core/`, `execution/`, `orchestrator.py`, `main.py`, `settings.py`, `storage/btc_bot.db`, `storage/db.py`, `storage/repositories.py`, `storage/state_store.py` changes
- No runtime code contamination
- BTC PAPER bot (PID 815407) still running unaffected

## Methodology Integrity: PASS
- Dry-run only implementation (line 432-433 in shadow_orchestrator.py: `if not args.dry_run: parser.error("Only --dry-run is implemented in this milestone")`)
- Production DB touch detection implemented via signature comparison (lines 193-199, 343, 405, 414)
- Resource guard enforces disk >= 12GB before execution (lines 158-163)
- Order-path import guard uses AST parsing to block `execution/` imports (lines 128-156)
- Lock separation enforced via explicit guard (lines 94-98)

## Promotion Safety: PASS
- Milestone scope explicitly "dry-run only" (MILESTONE_TRACKER line 45)
- DECISIONS_LOG states "This still does not approve systemd deployment, a long-running sidecar process, ETH/SOL PAPER, LIVE trading, runtime integration"
- Runbook states "This runbook does not approve deployment, systemd enablement, PAPER orders, or LIVE orders"
- No systemd service file created
- No long-running process loop implemented

## Reproducibility & Lineage: PASS
- Shadow run ID includes UUID: `shadow-dry-run-{uuid.uuid4().hex[:12]}` (line 356)
- Git commit captured via subprocess (lines 70-80)
- Config hash deterministic from symbols + paths (lines 83-91)
- Shadow runs table records: `shadow_run_id`, `service_start_time_utc`, `git_commit`, `code_version`, `config_hash`, `dry_run`, `lock_path`, `db_path` (lines 57-67)

## Data Isolation: PASS
- **Entrypoint separation:** `sidecar_main.py` (line 1) imports from `research_lab.shadow_orchestrator.main`, not `main.py`
- **Lock separation:** `SIDECAR_LOCK_DEFAULT = Path("/tmp/multi-asset-shadow.lock")` (line 31) vs `BTC_RUNTIME_LOCK_PATH = Path("/tmp/btc-bot-runtime.lock")` (line 30)
- **Lock guard:** `ensure_lock_separation()` (lines 94-98) raises `ShadowGuardError` if paths match
- **DB path guard:** `resolve_shadow_db_path()` (lines 23-40 in shadow_schema.py) uses `resolved.relative_to(root)` to enforce `research_lab/shadow/` boundary, raises `ShadowPathError` if path escapes
- **Production DB isolation:** `production_db_signature()` (lines 193-199) captures size + mtime before/after, compared at line 414 to detect writes
- **Test verification:** `test_dry_run_writes_shadow_db_only_and_leaves_production_db_untouched` (lines 48-84 in test_sidecar_isolation.py) creates sentinel table in production DB, runs dry-run, verifies production DB unchanged and shadow tables separate

## Search Space Governance: N/A
- No parameter tuning, this is infrastructure only
- Stub decisions use hardcoded `min_sweep_depth_pct=0.00649` (line 312) from frozen trial-00095 baseline

## Artifact Consistency: PASS
- MILESTONE_TRACKER describes same deliverables: entrypoint, orchestrator, schema, runbook, tests
- DECISIONS_LOG rationale matches implementation scope
- Runbook commands match implementation (dry-run flag, path defaults)
- No contradictions

## Boundary Coupling: PASS
- **Order-path import guard:** `assert_no_order_path_imports()` (lines 140-156) uses AST parsing to detect `execution` imports
- **Disallowed roots:** `DISALLOWED_IMPORT_ROOTS = {"execution"}` (line 35)
- **Test verification:** `test_order_path_import_guard_rejects_execution_import` (lines 40-45) creates file with `from execution.paper_execution_engine import`, verifies guard raises `ShadowGuardError`
- **Grep verification:** No `from execution` or `import execution` found in `sidecar_main.py` or `research_lab/shadow_*.py`

## Contract Compliance: PASS
- **Six required tables created** (lines 57-161 in shadow_schema.py):
  1. `shadow_runs` (lines 57-67)
  2. `shadow_decision_outcomes` (lines 69-98)
  3. `shadow_signal_candidates` (lines 100-113)
  4. `shadow_portfolio_decisions` (lines 115-130)
  5. `shadow_near_miss_diagnostics` (lines 132-146)
  6. `shadow_resource_samples` (lines 148-160)
- **Test verification:** `test_shadow_schema_creates_all_required_tables` (lines 25-33) checks all 6 tables exist
- **Diagnostic payload fields:** `test_shadow_decision_outcomes_has_required_payload_fields` (lines 36-68) verifies 24 required fields present
- **Nested near-miss structure:** `insert_near_miss()` (lines 174-225) creates nested `near_miss_diagnostics` object with mandatory `sweep_depth_pct` field
- **Payload validation:** `validate_near_miss_payload()` (lines 166-172) enforces `near_miss_diagnostics.sweep_depth_pct is not None`

## Determinism: PASS
- Config hash uses sorted JSON keys (line 90: `json.dumps(payload, sort_keys=True)`)
- Shadow run ID includes timestamp + UUID for uniqueness (line 356)
- Deduplication key defined via UNIQUE constraint: `(shadow_run_id, symbol, timestamp_utc, strategy_profile)` (line 97)
- Resource sample timestamp uses ISO format with explicit timezone (line 67: `isoformat(timespec="seconds").replace("+00:00", "Z")`)

## State Integrity: PASS
- Safe restart support via `shadow_run_id` deduplication (line 97 UNIQUE constraint)
- No persistent state beyond SQLite DB
- Lock acquisition is atomic via `fcntl.flock` (POSIX) or `msvcrt.locking` (Windows) with `LOCK_NB` flag (lines 108-115)

## Error Handling: PASS
- **Path guard:** Raises `ShadowPathError` if DB path escapes `research_lab/shadow/` (lines 33-36 in shadow_schema.py)
- **Lock guard:** Raises `ShadowGuardError` if lock path matches BTC runtime lock (lines 96-98 in shadow_orchestrator.py)
- **Disk guard:** Raises `ShadowGuardError` if disk free < 12GB (lines 160-163)
- **Order-path guard:** Raises `ShadowGuardError` if `execution` imports detected (lines 154-155)
- **Near-miss validation:** Raises `ValueError` if nested `sweep_depth_pct` missing (lines 170-171 in shadow_schema.py)
- **Lock release:** Lock file closed in finally block even if exception occurs (lines 121-125)

## Smoke Coverage: PASS
- **9 tests pass** (verified via pytest run)
- **Isolation tests** (test_sidecar_isolation.py):
  - `test_sidecar_lock_is_distinct_from_btc_runtime_lock` - verifies different paths
  - `test_sidecar_lock_rejects_btc_runtime_lock` - verifies guard raises error
  - `test_shadow_db_path_must_stay_under_research_lab_shadow` - verifies path guard blocks storage/ and research_lab/snapshots/
  - `test_order_path_import_guard_rejects_execution_import` - verifies AST guard blocks execution imports
  - `test_dry_run_writes_shadow_db_only_and_leaves_production_db_untouched` - **critical test** - creates production DB with sentinel table, runs dry-run, verifies production unchanged, shadow tables separate
- **Schema tests** (test_shadow_schema.py):
  - `test_shadow_schema_creates_all_required_tables` - verifies all 6 tables
  - `test_shadow_decision_outcomes_has_required_payload_fields` - verifies 24 required fields
  - `test_near_miss_payload_requires_nested_sweep_depth_pct` - verifies validation raises without depth
  - `test_insert_near_miss_persists_nested_depth_payload` - verifies nested structure persisted correctly
- **Manual dry-run verification:** Executed successfully, output shows `production_db_touched: false`, `decision_rows: 3`, `near_miss_rows: 1`, `resource_rows: 1`

## Tech Debt: LOW
- No `NotImplementedError` stubs
- No TODOs
- Clean AST-based import guard (better than regex)
- Proper use of context managers for lock and DB connection
- Cross-platform lock handling (fcntl for POSIX, msvcrt for Windows)

## AGENTS.md Compliance: PASS
- Commit discipline clean: `feat: add dry-run shadow sidecar infrastructure`
- MILESTONE_TRACKER and DECISIONS_LOG updated
- BTC PAPER bot remained active (PID 815407, 15:58 hours uptime)
- No self-marking as "done" - builder marked as `READY_FOR_AUDIT_IMPLEMENTATION_DRY_RUN_ONLY`

## Critical Issues
None.

## Warnings
None.

## Observations

1. **All 10 verification points confirmed:**
   1. ✓ Sidecar entrypoint `sidecar_main.py` is separate from `main.py`
   2. ✓ Lock path `/tmp/multi-asset-shadow.lock` is separate from `/tmp/btc-bot-runtime.lock`, enforced by `ensure_lock_separation()`
   3. ✓ DB path guard `resolve_shadow_db_path()` only allows `research_lab/shadow/` via `relative_to()` check
   4. ✓ Schema creates all six required tables: `shadow_runs`, `shadow_decision_outcomes`, `shadow_signal_candidates`, `shadow_portfolio_decisions`, `shadow_near_miss_diagnostics`, `shadow_resource_samples`
   5. ✓ Nested `near_miss_diagnostics.sweep_depth_pct` is mandatory (validated) and tested (2 tests verify)
   6. ✓ Dry-run does not write to `storage/btc_bot.db` (production_db_signature before/after comparison + test + manual verification)
   7. ✓ No `execution/` order path imports allowed (AST-based guard + test + grep verification)
   8. ✓ Resource guard implemented (disk >= 12GB check + sampling)
   9. ✓ No runtime/core/orchestrator/main/settings/production storage changes (git diff clean)
   10. ✓ Does not approve systemd deployment or ETH/SOL PAPER (MILESTONE_TRACKER, DECISIONS_LOG, runbook all state this)

2. **Production DB touch detection is robust**  
   - Captures size + mtime before dry-run starts (line 343)
   - Captures size + mtime after dry-run completes (line 405)
   - Compares signatures to detect any modification (line 414)
   - Returns non-zero exit code if touched (line 457: `return 1 if result.production_db_touched else 0`)
   - Test creates sentinel table, runs dry-run, verifies production DB bytes unchanged (lines 48-66)
   - Manual dry-run output shows `production_db_touched: false` ✓

3. **Order-path import guard uses static analysis**  
   - AST parsing of Python source files (line 129: `ast.parse(path.read_text())`)
   - Walks AST to extract import roots (lines 131-136)
   - Checks against `DISALLOWED_IMPORT_ROOTS = {"execution"}` (line 35)
   - Raises `ShadowGuardError` with violations dict (lines 154-155)
   - Guards sidecar_main.py, shadow_orchestrator.py, shadow_schema.py (lines 141-145)
   - Test creates file with forbidden import, verifies guard triggers (lines 40-45)

4. **Lock separation is enforced at multiple layers**  
   - Constant definitions show different paths (lines 30-31)
   - Explicit guard function `ensure_lock_separation()` (lines 94-98)
   - Guard called before lock acquisition (lines 103, 341)
   - Test verifies paths differ (line 20)
   - Test verifies guard rejects BTC lock (lines 24-26)
   - Cross-platform lock implementation (fcntl for POSIX, msvcrt for Windows)

5. **Path guard is strict and well-tested**  
   - Uses `resolve()` to canonicalize path before checking (line 30 in shadow_schema.py)
   - Uses `relative_to(root)` which raises `ValueError` if path escapes (line 32)
   - Catches `ValueError` and wraps in domain-specific `ShadowPathError` (lines 33-36)
   - Rejects file-less paths like `.` and `..` (lines 37-38)
   - Creates parent directories automatically (line 39)
   - Test verifies allowed path works (lines 30-31 in test_sidecar_isolation.py)
   - Test verifies `storage/btc_bot.db` rejected (lines 33-34)
   - Test verifies `research_lab/snapshots/shadow.db` rejected (lines 36-37)

6. **Nested near-miss payload structure is mandatory**  
   - `validate_near_miss_payload()` enforces `near_miss_diagnostics` object exists (line 168 in shadow_schema.py)
   - Enforces `sweep_depth_pct` field exists inside nested object (line 170)
   - `insert_near_miss()` constructs nested structure (lines 188-199)
   - Nested object includes: `symbol`, `sweep_depth_pct`, `threshold`, `depth_gap_pct`, `depth_bucket`, `regime`, `session_hour`, `rejection_reasons` (lines 190-197)
   - Validation called before insert (line 200)
   - Test verifies validation raises without depth (lines 72-73)
   - Test verifies validation passes with depth (lines 75-77)
   - Test verifies nested structure persisted (lines 80-104)

7. **Resource guard is operational**  
   - Checks disk usage via `shutil.disk_usage()` (line 159)
   - Raises `ShadowGuardError` if free < min_disk_free_bytes (lines 160-163)
   - Default 12GB guard (line 32)
   - Collects memory RSS via `resource.getrusage()` with platform-specific handling (lines 165-179)
   - Collects CPU user/system seconds (lines 174-175, 177-179)
   - Persists resource sample to `shadow_resource_samples` table (lines 235-258)
   - Sample includes: `timestamp_utc`, `disk_free_bytes`, `disk_total_bytes`, `memory_rss_bytes`, `cpu_user_seconds`, `cpu_system_seconds`, `process_id`, `guard_status` (lines 42-51)

8. **Dry-run command is simple and documented**  
   - Single entrypoint: `python sidecar_main.py --dry-run` (line 27 in runbook)
   - Optional args: `--db-path`, `--lock-path`, `--min-disk-free-gb`, `--repo-root`, `--symbols` (lines 418-426)
   - Enforces only dry-run mode implemented (lines 432-433)
   - Returns JSON output with all key metrics (lines 442-457)
   - Exit code 0 if production DB untouched, 1 if touched (line 457)
   - Runbook documents expected output (lines 34-41)

9. **Symbol-specific risk profiles implemented**  
   - SOL: `sol_015_shadow_candidate`, 0.15% risk, `shadow_no_orders` mode (line 263)
   - BTC: `btc_035_shadow_compare`, 0.35% risk, `shadow_compare_only` mode (line 265)
   - ETH: `eth_035_shadow_candidate`, 0.35% risk, `shadow_no_orders` mode (line 266)
   - Matches design blueprint candidate risk policies
   - Stub decisions include symbol-explicit fields (lines 269-328)

10. **Implementation is minimal and focused**  
    - Dry-run infrastructure only, no signal generation logic
    - Stub decisions have `signal_blocker="dry_run_no_market_data"` (line 308)
    - Details JSON includes `"dry_run": True, "reason": "infrastructure_validation_no_market_data", "orders_allowed": False` (lines 278-283)
    - No market data fetching implemented
    - No live signal generation
    - No portfolio gate evaluation logic
    - Focused on proving isolation boundaries work

## Recommended Next Step

**Do NOT deploy sidecar to production yet.**

**Blocking gate: Day 0 Pre-Start Check**

Before any deployment milestone can enable a systemd service or start a long-running sidecar process, the following must be verified on the production server:

1. `systemctl is-active btc-bot` → `active`
2. `ps -eo pid,ppid,lstart,cmd | grep "main.py --mode PAPER"` → exactly one process
3. `df -h /` → >= 12 GB free
4. `python sidecar_main.py --dry-run` → exit code 0, `production_db_touched: false`
5. Verify `research_lab/shadow/multi_asset_shadow.db` path resolves correctly
6. Verify lock path `/tmp/multi-asset-shadow.lock` is distinct

**Next milestone: MULTI_ASSET_SHADOW_SIDECAR_DEPLOYMENT_V1** (requires separate audit + user approval)

**Scope:**
- Create systemd service file `multi-asset-shadow.service`
- Configure service properties: `nice`, `ionice`, `MemoryMax=512M`, `CPUQuota=50%`, `Restart=on-failure`
- Add server-side deployment script
- Extend runbook with Day 0 operator checklist, Day 3/14/30 checkpoint procedures
- Implement graceful shutdown handler
- Add sidecar status monitoring script
- Test: systemd service starts/stops cleanly, resource caps enforced, sidecar respects BTC PAPER priority

**Recommended builder:** Codex (sidecar infrastructure continuity, server deployment experience)

**No-touch areas:** BTC PAPER bot (`btc-bot.service`), production config, M4 queries, threshold values

**Critical reminder:** Day 3/14/30 checkpoints remain blocking gates before ETH/SOL PAPER consideration. Deployment does not approve PAPER orders.

---

**Audit complete.** Implementation is sound, all isolation boundaries are enforced and tested, dry-run proves no production contamination. This infrastructure is ready for a separate deployment milestone, but does NOT approve starting a long-running sidecar process yet.

# AUDIT: RUNTIME_CAPACITY_GUARDRAILS_V1
Date: 2026-05-21
Auditor: Claude Code
Commit: 2a7cbc6

## Verdict: DONE

## Layer Separation: PASS
- Standalone operations script (standard library imports only)
- No runtime code imports (orchestrator, settings, core modules)
- Imports: argparse, json, os, re, shutil, sqlite3, subprocess, dataclasses, datetime, pathlib, typing
- Read-only database access (no writes to btc_bot.db or shadow_db)
- No execution, trading, or strategy imports

## Contract Compliance: PASS
- Scope: non-trading capacity checker to gate ETH/SOL PAPER activation
- Read-only: queries runtime_metrics, shadow_resource_samples, /proc, journalctl
- No production settings changes
- No trading behavior changes
- No systemd unit changes

## Determinism: PASS
- Threshold evaluation deterministic (fixed thresholds, arithmetic comparison)
- Snapshot collection deterministic (file system, database, /proc reads)
- Exit code deterministic: 2 on fail, 0 on pass/warn
- JSON output sorted keys

## Backward Compatibility: PASS
- No changes to existing runtime code
- No changes to existing tests (6 new tests added)
- 578 tests pass (24 skipped) — 6 new capacity check tests
- Standalone script does not affect bot behavior

## State Integrity: PASS
- Read-only database access (no INSERT, UPDATE, DELETE)
- No state mutation in runtime code
- No writes to production database or shadow database
- Snapshot collection does not modify system state

## Error Handling: PASS
- Database errors return empty dict (graceful degradation)
- Missing files return None or empty dict
- OSError, subprocess.TimeoutExpired handled
- Subprocess timeout: 10 seconds
- Invalid /proc/meminfo lines skipped
- Invalid datetime parsing returns None

## Smoke Coverage: PASS
- **Evaluation tests (2):**
  - `test_evaluate_capacity_passes_current_server_like_snapshot()` → pass with current production-like values
  - `test_evaluate_capacity_fails_activation_blockers()` → fail with all guardrails exceeded
- **Metric reading tests (4):**
  - `test_read_runtime_metrics_derives_last_cycle_duration()` → duration from started/finished timestamps
  - `test_runtime_metrics_ignores_equal_logical_cycle_timestamps()` → None when started == finished
  - `test_parse_latest_cycle_duration_from_journal_log()` → parse from journal text
  - `test_read_latest_shadow_resource_returns_latest_sample()` → latest row from shadow_resource_samples
- **Total: 6 tests, all pass**

## Tech Debt: LOW
- Clean standalone script
- No magic numbers (constants defined: GB, MB)
- Configurable thresholds via CLI args
- JSON output machine-readable

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message (2a7cbc6)
- Scope purity: operations/readiness only, no trading changes
- Documentation: DECISIONS_LOG and MILESTONE_TRACKER updated

## Premature Activation: BLOCKED
- This milestone does NOT enable ETH/SOL PAPER
- This milestone does NOT change multi_asset.enabled (remains False)
- This milestone does NOT change production settings
- Purpose: readiness gate for future activation, not activation itself
- ETH/SOL activation blocked until: capacity check pass + M4 extension + shadow evidence + operator approval

## Reproducibility & Lineage: PASS
- Addresses capacity concern identified in Phase 4 deployment review
- User inspection: load 0.00, CPU idle 99-100%, RAM 3.1GB available, disk 78%, bot 82MB RSS, shadow 26MB RSS
- Guardrails based on production observations + safety margin
- Documented in DECISIONS_LOG.md (2026-05-21 entry)

## Artifact Consistency: PASS
- Script matches documentation (DECISIONS_LOG, MILESTONE_TRACKER)
- Thresholds match documented guardrails
- Tests verify threshold evaluation logic
- JSON output includes thresholds, snapshot, status, failures, warnings

## Boundary Coupling: PASS
- Standalone script, no coupling to runtime code
- Database reads are read-only queries (SELECT only)
- No imports from orchestrator, settings, core, execution, etc.
- /proc filesystem reads are standard Linux monitoring practice

## Capacity Guardrails Specifics: PASS

**Thresholds (defaults):**
- `max_disk_used_pct`: 85.0% (current: ~78%)
- `min_disk_free_gb`: 12.0 GB (current: ~17 GB)
- `min_memory_available_gb`: 1.0 GB (current: ~3.1 GB)
- `max_load1_per_cpu`: 0.75 (current: ~0.0)
- `max_bot_rss_mb`: 512.0 MB (current: ~82 MB)
- `max_shadow_rss_mb`: 256.0 MB (current: ~26 MB)
- `max_last_cycle_duration_sec`: 60.0 seconds (current: ~8.9 seconds)

**Data sources:**
- Disk: `shutil.disk_usage()`
- Memory: `/proc/meminfo` (MemTotal, MemAvailable)
- Load: `os.getloadavg()[0]`
- Bot RSS: `/proc/<pid>/status` (VmRSS)
- Cycle duration: `runtime_metrics` table (last_decision_cycle_started_at, last_decision_cycle_finished_at)
- Cycle duration fallback: `journalctl -u btc-bot.service -n 200` (parse "duration_ms=...")
- Shadow RSS: `shadow_resource_samples` table (latest row)
- Shadow guard: `shadow_resource_samples.guard_status` (must be "pass" or None)

**Evaluation logic:**
- Status: "fail" if any threshold exceeded, "warn" if any metric unavailable, "pass" otherwise
- Exit code: 2 on fail, 0 on pass/warn
- Failures: list of threshold violations (human-readable)
- Warnings: list of unavailable metrics (non-blocking)

**Production usage:**
```bash
# Dry-run (current state)
python scripts/runtime_capacity_check.py --bot-pid $(systemctl show -p MainPID btc-bot.service | cut -d= -f2)

# Before ETH/SOL activation
python scripts/runtime_capacity_check.py --bot-pid <pid> && echo "PASS" || echo "FAIL"
```

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. Standalone operations script (no runtime coupling)
2. Read-only database access (safe for production execution)
3. Thresholds based on current production observations + safety margin
4. Current production comfortably passes all guardrails (78% disk, 3.1GB RAM, 0.0 load, 82MB bot RSS, 26MB shadow RSS, 8.9s cycle)
5. Disk at 78% is highest risk (17GB free, but growing over time)
6. No swap configured (non-critical with current 3.1GB available RAM)
7. Multi-asset activation will increase: REST/API calls, cycle duration, memory (per-symbol engines)
8. Guardrails designed to catch unsustainable growth before it impacts BTC PAPER
9. Tests verify evaluation logic (pass/fail scenarios)
10. This milestone is a readiness gate, not an activation milestone

## Recommended Next Step

**Capacity guardrails implementation is DONE. Ready for code-only deployment (optional) or proceed to M4 extension.**

### Option A: Deploy capacity checker to production (code-only, non-blocking)

**Goal:** Make capacity checker available on production for pre-activation dry-runs.

**Command:**
```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull origin deploy/multi-asset-paper-v1  # expect: 2a7cbc6
# No restart needed (standalone script)
```

**Post-deployment verification:**
```bash
python scripts/runtime_capacity_check.py --bot-pid $(systemctl show -p MainPID btc-bot.service | cut -d= -f2)
# Expect: status=pass, no failures
```

### Option B: Proceed to M4_MULTI_ASSET_QUERY_EXTENSION_V1 (recommended)

**Goal:** Extend M4 query/reporting from BTC-only to per-symbol.

**Scope:**
- Extend M4 queries to support per-symbol context
- Preserve BTC M4 compatibility (existing queries unchanged)
- No strategy parameter changes
- No ETH/SOL PAPER activation
- Tests: BTC query same result, ETH/SOL reportable separately

**Blocker context:** Multi-asset runtime needs per-symbol M4 context for execution decisions. Current M4 is BTC-only.

**Parallel work:** Shadow evidence collection continues (ETH/SOL depth @ 0.0075 collecting forward evidence).

---

**Next milestone decision required:** Deploy capacity checker (optional) or proceed to M4 extension (recommended)?

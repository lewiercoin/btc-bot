# AUDIT: MULTI_ASSET_SHADOW_EVIDENCE_CHECKPOINT_V1
Date: 2026-05-21
Auditor: Claude Code
Commit: 6b9776b

## Verdict: DONE

**CRITICAL FINDING:** 2 `production_db_touched=true` entries detected in last 24h. Investigation required before MULTI_ASSET_PAPER_APPROVAL_V1. See "Critical Issues" section.

## Layer Separation: PASS
- Standalone reporting script (standard library imports only)
- Read-only database access (shadow DB, production DB)
- Imports: argparse, json, sqlite3, subprocess, dataclasses, datetime, pathlib, typing
- No runtime code imports (orchestrator, settings, core modules)
- Shadow schema import for test seeding only

## Contract Compliance: PASS
- Scope: read-only shadow evidence checkpoint for approval readiness
- Read-only: queries shadow_runs, shadow_decision_outcomes, shadow_resource_samples, production positions, journalctl
- No production settings changes
- No shadow runtime changes
- No strategy parameter changes
- No execution changes

## Determinism: PASS
- Window calculation deterministic (days or hours from now)
- Expected minimum cycles deterministic (window_days * 24 * 4 or hours * 4)
- Symbol evidence deterministic (per-symbol aggregation from shadow_decision_outcomes)
- Complete cycle definition: shadow_run_id with COUNT(DISTINCT symbol) >= 3
- Failure evaluation deterministic (threshold comparisons)

## Backward Compatibility: PASS
- Standalone script (no changes to existing runtime code)
- No changes to existing tests (4 new checkpoint tests added)
- 588 tests pass (24 skipped) — 4 new checkpoint tests
- Shadow sidecar continues running (timer active, ExecMainStatus=0)

## State Integrity: PASS
- Read-only database access (mode=ro for SQLite connections)
- No state mutation in shadow or production DBs
- No writes to any database
- journalctl read-only (--no-pager, stdout capture)

## Error Handling: PASS
- Database connection errors return empty dict (graceful degradation)
- Missing databases return empty dict
- journalctl timeout/OSError/non-zero exit → None (warning, not failure)
- Missing shadow rows for symbol → failure (explicit requirement)
- Division by zero avoided (threshold comparisons guarded)

## Smoke Coverage: PASS
- **Checkpoint tests (4 new):**
  - `test_shadow_evidence_checkpoint_passes_complete_window()` → pass with complete BTC/ETH/SOL cycles
  - `test_shadow_evidence_checkpoint_fails_missing_cycles_and_eth_position()` → fail when cycles < expected or ETH position exists
  - `test_render_markdown_includes_per_symbol_table()` → markdown report includes per-symbol table
  - `test_shadow_evidence_checkpoint_supports_hour_window()` → hour-based window calculation
- **Total: 4 tests, all pass**
- **Full suite: 588 passed (24 skipped)**

## Tech Debt: LOW
- Clean standalone checkpoint script
- Per-symbol aggregation logic clear
- Complete cycle definition explicit (3 symbols required)
- Read-only database connections via URI mode=ro

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message (6b9776b)
- Scope purity: read-only checkpoint, no trading or activation changes
- Documentation: DECISIONS_LOG and MILESTONE_TRACKER updated

## Premature Activation: BLOCKED
- This milestone does NOT enable ETH/SOL PAPER
- This milestone does NOT change multi_asset.enabled (remains False)
- This milestone does NOT change production settings
- Purpose: checkpoint readiness for approval decision, not activation itself
- ETH/SOL activation blocked until: checkpoint pass + operator approval (MULTI_ASSET_PAPER_APPROVAL_V1)

## Reproducibility & Lineage: PASS
- Addresses shadow evidence collection for multi-asset approval
- Multi-asset runtime deployed (dormant @ Phase 4)
- Capacity guardrails deployed (RUNTIME_CAPACITY_GUARDRAILS_V1)
- M4 extension deployed (M4_MULTI_ASSET_QUERY_EXTENSION_V1)
- Documented in DECISIONS_LOG.md (2026-05-21 entry)

## Artifact Consistency: PASS
- Script matches documentation (DECISIONS_LOG, MILESTONE_TRACKER)
- Checkpoint structure matches requirements (per-symbol, production isolation, resource guard)
- Tests verify checkpoint evaluation logic (pass/fail scenarios)
- Markdown and JSON output formats consistent

## Boundary Coupling: PASS
- Standalone script, no coupling to runtime decision logic
- Database reads are read-only queries (mode=ro connections)
- No imports from orchestrator, settings, core, execution
- journalctl read-only (systemd journal query)

## Shadow Evidence Checkpoint Specifics: PASS (with CRITICAL finding)

**Checkpoint structure:**
- **Window:** days (default 3) or hours (opt-in)
- **Expected minimum cycles:** window_days * 24 * 4 or hours * 4 (15min cycle = 4/hour)
- **Complete cycle:** shadow_run_id with COUNT(DISTINCT symbol) >= 3 (BTC, ETH, SOL all present)
- **Failure conditions:**
  - Complete cycles < expected minimum
  - Resource guard failures > 0
  - production_db_touched_true_count > 0
  - Production ETH/SOL positions > 0
  - Production multi-asset tables present (symbol_state, portfolio_state)
  - Any symbol has 0 shadow rows
- **Warning conditions:**
  - journalctl unavailable (production_db_touched check skipped)
  - Production open positions > 0 (BTC positions are expected, not a failure)

**Per-symbol evidence:**
- **BTCUSDT, ETHUSDT, SOLUSDT** (all three required)
- Decision rows, signal_generated rows, near-miss rows
- Portfolio approved rows, portfolio veto rows
- Blocker counts (by blocker type)
- min_sweep_depth_pct range (min/max observed thresholds)

**Production isolation checks:**
- `production_db_touched=true` count from journalctl (CRITICAL: see below)
- ETH/SOL positions in production DB (must be 0)
- Multi-asset tables (symbol_state, portfolio_state) must not exist in production DB
- Resource guard status (must be "pass" in latest sample)

**Production smoke test results:**
- **Last 2h window:** `status=pass`
  - 7 complete cycles
  - 0 `production_db_touched=true` entries
  - 0 resource guard failures
  - 0 ETH/SOL positions
  - No multi-asset tables
- **Last 24h window:** `status=fail`
  - **2 `production_db_touched=true` entries** (CRITICAL FINDING)
  - All other checks pass

## Critical Issues (must fix before next milestone)

### Issue 1: production_db_touched=true entries detected in last 24h

**Finding:** journalctl shows 2 `production_db_touched=true` entries in the last 24h window.

**Impact:** Shadow sidecar may have modified production database, violating isolation contract.

**Root cause hypothesis (user's note):**
> "Może to być false positive guardu przy równoległym zapisie BTC bota do production DB, ale przed approval nie wolno tego ignorować."
> 
> Translation: "This could be a false positive from the guard during concurrent BTC bot writes to production DB, but before approval this cannot be ignored."

**Potential explanations:**
1. **False positive (most likely):** Shadow sidecar's `production_db_touched` guard detects mtime changes from concurrent BTC bot writes during the guard's mtime check window. The BTC bot is actively writing to production DB (decision_outcomes, positions, trade_log), and the shadow guard may detect these legitimate writes as "production DB touched" even though the shadow sidecar itself didn't write.
   
2. **True positive (must rule out):** Shadow sidecar actually wrote to production DB due to a bug in the isolation layer.

**Investigation required before approval:**
1. **Examine the 2 journal entries:**
   ```bash
   journalctl -u multi-asset-shadow.service --since "24 hours ago" | grep "production_db_touched"
   ```
   - Extract timestamps of the 2 occurrences
   - Check if BTC bot had concurrent writes at those exact timestamps
   - Check shadow_runs table for corresponding shadow_run_id entries
   - Review shadow code path to verify no write operations to production DB

2. **Review guard implementation:**
   - Current guard likely uses mtime comparison (before/after shadow run)
   - Concurrent BTC bot writes during shadow run will change mtime
   - Guard will report `production_db_touched=true` even if shadow didn't write
   - **Recommendation:** Enhance guard to distinguish shadow writes from concurrent BTC writes (e.g., row count comparison, transaction log inspection, or separate write lock)

3. **Short-term mitigation:**
   - Run checkpoint during known-quiet window (no BTC trades expected)
   - If `production_db_touched=true` count drops to 0 during quiet window, confirms false positive hypothesis
   - If count remains >0 during quiet window, confirms true positive (shadow write bug)

**Blocking verdict:**
- This issue **BLOCKS** `MULTI_ASSET_PAPER_APPROVAL_V1` until investigation complete
- If false positive confirmed: document in approval milestone, enhance guard (optional)
- If true positive confirmed: fix shadow isolation bug, re-test, re-audit

**Next step:**
- User/operator must investigate the 2 journal entries before proceeding to approval
- Claude Code cannot approve MULTI_ASSET_PAPER_APPROVAL_V1 without resolution of this finding

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. Standalone checkpoint script (no runtime coupling)
2. Read-only database access (mode=ro connections)
3. Complete cycle definition: all 3 symbols (BTC/ETH/SOL) required per shadow run
4. Expected minimum cycles: 4 per hour (15min cycle frequency)
5. Production isolation checks: ETH/SOL positions, multi-asset tables, production_db_touched
6. Resource guard status checked from latest shadow_resource_samples row
7. journalctl query with 20s timeout (graceful degradation if unavailable)
8. Per-symbol evidence includes blocker counts, near-miss counts, portfolio decisions
9. Markdown and JSON output formats both supported
10. Last 2h window passes all checks (0 production_db_touched)
11. **Last 24h window fails due to 2 production_db_touched entries** (requires investigation)

## Recommended Next Step

**Shadow evidence checkpoint implementation is DONE, but deployment and approval BLOCKED pending production_db_touched investigation.**

### Phase 1: Investigate production_db_touched=true Finding

**Goal:** Determine if 2 `production_db_touched=true` entries are false positives (concurrent BTC writes) or true positives (shadow write bug).

**Investigation steps:**
1. Extract journal entries:
   ```bash
   journalctl -u multi-asset-shadow.service --since "24 hours ago" | grep "production_db_touched"
   ```

2. Check timestamps against BTC bot activity:
   ```bash
   # For each timestamp from step 1:
   journalctl -u btc-bot.service --since "<timestamp - 5min>" --until "<timestamp + 5min>" | grep "Decision cycle\|Trade opened\|Trade closed"
   ```

3. Review shadow code for production DB write paths:
   - Verify shadow sidecar uses read-only production DB connection
   - Verify no INSERT/UPDATE/DELETE to production DB
   - Verify guard implementation (mtime-based vs transaction-based)

4. Run checkpoint during quiet window (no BTC trades expected):
   ```bash
   # Wait for quiet period (no positions open, no recent trades)
   python scripts/multi_asset_shadow_evidence_checkpoint.py --hours 2
   # If production_db_touched_true_count == 0, confirms false positive hypothesis
   ```

**Expected outcome:**
- **False positive confirmed:** 2 entries coincide with BTC bot writes, guard detects mtime changes from legitimate BTC operations
- **True positive confirmed:** 2 entries do NOT coincide with BTC bot writes, shadow sidecar has write bug

### Phase 2: Resolution (after investigation)

**If false positive:**
- Document finding in MULTI_ASSET_PAPER_APPROVAL_V1
- Optionally enhance guard to distinguish shadow writes from concurrent writes
- Proceed to approval with caveat: checkpoint windows should avoid concurrent BTC write periods

**If true positive:**
- Fix shadow isolation bug (identify write path, add read-only enforcement)
- Re-test checkpoint (verify 0 production_db_touched in quiet and active windows)
- Re-audit shadow sidecar isolation
- Only then proceed to MULTI_ASSET_PAPER_APPROVAL_V1

### Phase 3: MULTI_ASSET_PAPER_APPROVAL_V1 (future, after resolution)

**Scope:** Operator review and approval decision for ETH/SOL PAPER activation

**Prerequisites:**
- ✅ Multi-asset runtime contracts deployed (dormant)
- ✅ Capacity guardrails pass
- ✅ M4 extension deployed
- ✅ Shadow evidence checkpoint implemented
- ⏳ production_db_touched investigation resolved (BLOCKING)
- ⏳ Shadow evidence accumulation (30-60 days target)

---

**BLOCKING: production_db_touched investigation must complete before approval milestone.**

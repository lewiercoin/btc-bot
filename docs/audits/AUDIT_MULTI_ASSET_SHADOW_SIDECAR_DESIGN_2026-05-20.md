# AUDIT: MULTI_ASSET_SHADOW_SIDECAR_DESIGN_V1

Date: 2026-05-20  
Auditor: Claude Code  
Commit: 6b0b8f1  
Builder: Codex

## Verdict: PASS

## Layer Separation: PASS
- Only `docs/` changed (BLUEPRINT_MULTI_ASSET_SHADOW_SIDECAR.md, MILESTONE_TRACKER.md, DECISIONS_LOG.md)
- No `core/`, `execution/`, `orchestrator.py`, `main.py`, `settings.py`, `data/`, `storage/`, `backtest/` changes
- No runtime code, no configuration files, no production artifacts
- Design-only milestone correctly scoped

## Methodology Integrity: PASS
- Sidecar design preserves BTC M4 as clean BTC-only measurement (lines 23-24, 82, 226-229)
- M4 Contamination Guard section defines 7 hard requirements (lines 224-237)
- BTC M4 continues to use "only rows written by the existing BTC PAPER runtime" (line 227)
- Sidecar rows stored in separate database, never joined into M4 calculations (lines 228-229)
- BTC sidecar rows labeled as "shadow mirror rows and must not be used in the M4 checkpoint" (lines 150-151)

## Promotion Safety: PASS
- Document explicitly states "does not approve sidecar implementation or deployment" (line 32)
- Non-goals section lists 14 prohibited actions (lines 37-50)
- Day 0 "cannot approve PAPER orders" (line 278)
- Day 3 "can only approve continued shadow observation or require pause/fix" (line 293)
- Day 14 "can only approve continued shadow observation, extension, or pause" (line 310)
- Day 30 "may request PAPER consideration... Day 30 itself does not approve PAPER" (lines 327-328)
- Day 30 gate explicit: "No symbol can move to PAPER without a new milestone, audit, and user approval" (line 325)
- Implementation must be "audited before any server process is started" (line 348)

## Reproducibility & Lineage: PASS
- Sidecar DB schema includes lineage fields: `shadow_run_id`, `service_start_time_utc`, `git_commit`, `code_version`, `config_hash` (lines 124-127)
- Safe restart support via deduplication key: `(shadow_run_id, symbol, timestamp_utc, strategy_profile)` (line 128)
- Symbol scope traces to audited evidence: ETH uses "audited ETH transfer evidence", SOL uses "audited SOL risk-policy diagnostic" (lines 147-148)
- BTC mirror rows "not M4 source of truth" (line 146)

## Data Isolation: PASS
- Process isolation: "runs as a separate process" outside btc-bot.service (lines 59, 75)
- Lock isolation: "separate lock path, not /tmp/btc-bot-runtime.lock" (lines 60, 76, 275)
- Storage isolation: "writes only under research_lab/shadow/" (lines 61, 77, 121)
- DB path default: `research_lab/shadow/multi_asset_shadow.db` (line 115)
- Path guard: "reject paths outside research_lab/shadow/" (line 121)
- Production DB write blocked: "may not open storage/btc_bot.db in write mode" (lines 64, 78, 123, 166, 234)
- Day 3 check: "sidecar wrote zero rows to storage/btc_bot.db" (line 286)
- Day 30 gate: "Zero sidecar writes to production DB" (line 320)

## Search Space Governance: PASS
- ETH candidate risk 0.35% documented (line 147)
- SOL candidate risk 0.15% documented (line 148)
- No threshold changes: Non-goal "change min_sweep_depth_pct" (line 47)
- No BTC trial-00095 parameter changes (line 46)

## Artifact Consistency: PASS
- MILESTONE_TRACKER describes same scope: design-only, no runtime approval, sidecar isolation
- DECISIONS_LOG rationale matches blueprint executive decision
- No contradictions between blueprint, tracker, and decisions log

## Boundary Coupling: PASS
- Order isolation: "no order placement API and no execution engine dependency" (lines 63, 79)
- Non-goal: "place PAPER or LIVE orders for any symbol" (line 42)
- Data source contract: "may not subscribe to or submit private order endpoints" (line 164)
- No trading keys: "may not read API keys required for trading" (line 165)
- Day 0 check: "dry-run proves no order/execution import path" (line 276)
- Day 3 check: "sidecar placed zero orders" (line 287)
- Day 30 gate: "Zero ETH/SOL/SOL-sidecar orders" (line 319)
- Implementation requirement: "order-path import guard" (line 338)

## Contract Compliance: PASS
- Hard Isolation Contract table defines 10 boundary requirements (lines 69-85)
- Service shape properties defined with concrete values (lines 90-108)
- Storage contract defines 6 required rules (lines 118-128)
- Diagnostic payload contract specifies 21 required fields (lines 174-200)
- Near-miss payload uses nested structure with mandatory `sweep_depth_pct` field (lines 202-220)
- 6 recommended tables defined with clear purposes (lines 130-138)

## Determinism: PASS
- Implementation requirement: "deterministic per-symbol cycle scheduler" (line 340)
- Deduplication key defined for safe restart: `(shadow_run_id, symbol, timestamp_utc, strategy_profile)` (line 128)
- Symbol-explicit rows required (line 341)
- Day 3 check: "sidecar DB has symbol-explicit rows for enabled symbols" (line 288)
- Day 30 gate: "100% of rows are symbol-explicit" (line 322)

## State Integrity: N/A
- Design-only milestone, no state mutation

## Error Handling: PASS
- Failure mode: "Fail closed and log; do not degrade BTC PAPER" (line 250)
- Service restart policy: "Restart=on-failure only after implementation audit proves recovery is idempotent" (lines 104-105)
- Data unavailable handling: "record a data_stale or data_unavailable outcome and skip signal simulation" (lines 169-171)
- "must not silently fill missing data" (line 171)
- Resource guard disk check: "Refuse start or pause if free disk < 12 GB" (line 244)

## Smoke Coverage: N/A
- Design-only milestone, no implementation to test
- Implementation milestone requirements list 11 required components including tests (lines 330-347)
- Test requirements: "near-miss nested payload tests", "no-production-DB-write tests", "no-runtime-import/execution tests", "dry-run command for Day 0 validation" (lines 342-346)

## Tech Debt: LOW
- No implementation debt (design-only)
- Blueprint is complete and internally consistent
- All 6 audit questions explicitly listed (lines 350-363)

## AGENTS.md Compliance: PASS
- Commit discipline clean: single design commit with clear message
- MILESTONE_TRACKER and DECISIONS_LOG updated
- BTC PAPER bot (PID 815407) remained active (no runtime changes)

## Critical Issues
None.

## Warnings
None.

## Observations

1. **BTC M4 isolation is rigorous**  
   - 7 hard M4 contamination guard requirements (lines 224-237)
   - M4 reads "only rows written by the existing BTC PAPER runtime" (line 227)
   - Sidecar BTC mirror rows are "diagnostic only and cannot replace production BTC M4 rows" (lines 150-151, 230-231)
   - Day 3 check: "BTC M4 config hash unchanged unless separately audited" (line 285)
   - Day 30 gate: "BTC PAPER and M4 metrics unaffected" (line 318)
   - Any sidecar that writes to production DB is "invalid" (line 234)
   - Any sidecar that restarts or changes btc-bot.service is "invalid" (line 236)

2. **Process/lock/storage isolation is explicit and enforceable**  
   - Separate process outside btc-bot.service with distinct service name (line 75)
   - Separate lock path (not /tmp/btc-bot-runtime.lock) verified at Day 0 (lines 76, 275)
   - Separate database at `research_lab/shadow/multi_asset_shadow.db` (line 115)
   - Path guard rejects writes outside research_lab/shadow/ (line 121)
   - Production DB opened in write mode is blocked (lines 78, 123, 234)
   - Day 3 verification: zero rows in storage/btc_bot.db (line 286)
   - Day 30 gate: zero production DB writes (line 320)

3. **Order placement is blocked at 4 layers**  
   - No execution engine dependency (lines 63, 79)
   - No order placement API (line 79)
   - No trading key access (line 165)
   - No private order endpoints (line 164)
   - Order-path import guard required in implementation (line 338)
   - Dry-run must prove no order path before Day 0 start (line 276)
   - Day 3/30 checks verify zero orders (lines 287, 319)

4. **Resource limits are concrete and appropriate for current server**  
   - Server checkpoint: 2 vCPU, 3.1 GiB free RAM, 26 GiB free disk, BTC PAPER uses 0.5% CPU + 116 MB (lines 252-259)
   - Sidecar caps: 50% CPU (1 vCPU max), 512 MB RAM, 12 GB disk guard (lines 101-102, 244-246)
   - Leaves 1 vCPU, ~2.6 GB RAM, 14 GB disk buffer for BTC PAPER and system
   - Lower priority via nice/ionice to protect BTC PAPER (lines 100, 247)
   - Implementation must "re-check resource guards at runtime" (line 261) - not static assumption
   - Failure mode: "Refuse start or pause if free disk < 12 GB" (line 244)

5. **Checkpoint progression is well-gated and measurable**  
   - Day 0 (8 pre-start checks): btc-bot.service active, single PAPER process, disk >= 12 GB, path guards, lock distinct, dry-run proves no order path (lines 265-277)
   - Day 3 (8 operational checks): BTC process count = 1, M4 hash unchanged, zero production DB writes, zero orders, symbol-explicit rows, nested depth, resource within caps, no stale-data streak (lines 280-292)
   - Day 14 (10 behavior metrics): decision cycles, signal counts, vetoes by reason, near-miss distribution, overlap, simulated exposure, data-stale counts, resource events (lines 294-309)
   - Day 30 (8 readiness gates): runtime isolation, zero orders, zero production writes, 100% nested depth, 100% symbol-explicit, no resource breaches, portfolio diagnostics persisted, PAPER block (lines 313-328)
   - All gates measurable from database queries, process checks, or file system queries

6. **ETH/SOL PAPER is explicitly blocked**  
   - Non-goal: "place PAPER or LIVE orders for any symbol" (line 42)
   - Non-goal: "approve ETH or SOL PAPER" (line 49)
   - Symbols start in `shadow_no_orders` mode (lines 147-148)
   - Day 0 "cannot approve PAPER orders" (line 278)
   - Day 3/14 "can only approve continued shadow" (lines 293, 310)
   - Day 30 "may request PAPER consideration... does not approve PAPER" (lines 327-328)
   - Day 30 gate: "No symbol can move to PAPER without a new milestone, audit, and user approval" (line 325)

7. **Sidecar cannot contaminate BTC PAPER runtime**  
   - No write to storage/btc_bot.db (lines 64, 78, 123, 166, 234, 286, 320)
   - No restart/signal/mutation of btc-bot.service (lines 45, 80, 99, 236)
   - No BTC PAPER config mutation (lines 44, 81)
   - No in-memory state dependency from BTC PAPER process (line 167)
   - Service starts without btc-bot.service restart (line 99)
   - Runs at lower priority with resource caps (lines 100-102, 245-247)
   - Fail-closed mode: "do not degrade BTC PAPER" (line 250)

8. **Implementation requirements are concrete**  
   - 11 specific components listed (lines 330-347)
   - Entrypoint: "not main.py" (line 334)
   - Separate lock, DB, schema (lines 335-336)
   - Safe path guard for research_lab/shadow/ (line 337)
   - Order-path import guard (line 338)
   - Resource guard (line 339)
   - Deterministic per-symbol cycle scheduler (line 340)
   - Symbol-explicit payload writer (line 341)
   - Near-miss nested payload tests (line 342)
   - No-production-DB-write tests (line 343)
   - No-runtime-import/execution tests (line 344)
   - Dry-run command for Day 0 (line 345)
   - Operator runbook (line 346)

9. **Near-miss diagnostic payload is consistent with SOL contract**  
   - Uses nested structure: `near_miss_diagnostics.sweep_depth_pct` (lines 202-220)
   - Mandatory nested field enforced (lines 219-220)
   - Day 3 check: "near-miss rows have nested depth" (line 289)
   - Day 30 gate: "100% of near-miss rows have nested depth" (line 321)
   - Matches SOL_SHADOW_CONTRACT_DESIGN_V1 payload structure

10. **Portfolio evaluation determinism is deferred to implementation**  
    - Design requires "deterministic per-symbol cycle scheduler" (line 340)
    - Portfolio decisions table exists: `shadow_portfolio_decisions` (line 136)
    - Diagnostic payload includes `portfolio_shadow_decision` and `portfolio_veto_reason` (lines 196-197)
    - Specific ordering rule (timestamp ASC, symbol rank, symbol, signal id) should be defined in implementation milestone, consistent with SOL_SHADOW_CONTRACT_DESIGN_V1

## Recommended Next Step

**Do NOT implement sidecar yet.**

**User strategic decision required:**

The sidecar design is sound and preserves BTC M4 integrity. However, implementing and deploying the sidecar before BTC M4 completes creates a strategic trade-off:

**Pro:** Early forward evidence for BTC/ETH/SOL portfolio behavior, enables parallel data collection while M4 runs.

**Con:** Adds operational complexity (second service to monitor), consumes server resources (512 MB RAM, 50% CPU), and introduces risk of sidecar bugs affecting server stability before M4 checkpoint completes.

**Recommendation:** Wait for user decision on whether to:
1. **Proceed with sidecar implementation** - accepts operational complexity trade-off in exchange for early multi-asset evidence
2. **Wait until BTC M4 completes** - keeps M4 period operationally simple, implements multi-asset runtime integration directly after M4 instead of sidecar route

If user approves sidecar route, next milestone: `MULTI_ASSET_SHADOW_SIDECAR_IMPLEMENTATION_V1`

**Scope:** Sidecar entrypoint (not main.py), separate lock/DB/schema, safe path guard, order-path import guard, resource guard, deterministic scheduler, symbol-explicit payload writer, near-miss nested tests, no-production-DB-write tests, no-runtime-import tests, dry-run command, operator runbook

**Recommended builder:** Codex (BTC PAPER runtime continuity, storage architecture experience, SOL research chain ownership)

**Target files:** New sidecar entrypoint script, `storage/shadow_schema.py`, `research_lab/shadow_orchestrator.py`, tests for isolation boundaries

**No-touch areas:** `btc-bot.service`, `storage/btc_bot.db`, `main.py`, BTC PAPER config, M4 queries/reports

**After implementation audit passes:** Day 0 pre-start checks, then enable sidecar service. Day 3/14/30 checkpoints follow. ETH/SOL PAPER remains blocked until separate milestone after Day 30 evidence.

---

**Audit complete.** Design is sound, BTC M4 isolation is rigorous, and all boundary contracts are explicit and enforceable. This blueprint does not approve sidecar implementation or deployment - user must decide whether the early evidence trade-off justifies the operational complexity before M4 completes.

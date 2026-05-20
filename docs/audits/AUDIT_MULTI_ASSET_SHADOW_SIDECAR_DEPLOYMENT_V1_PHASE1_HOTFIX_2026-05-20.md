# AUDIT ADDENDUM: MULTI_ASSET_SHADOW_SIDECAR_DEPLOYMENT_V1 Phase 1 Hotfix
Date: 2026-05-20
Auditor: Claude Code
Commit: 041046a
Previous Audit: AUDIT_MULTI_ASSET_SHADOW_SIDECAR_DEPLOYMENT_V1_PHASE1_2026-05-20.md (verdict: DONE)

## Context
Day 0 deployment attempt on production server (commit c770d76) failed during day0_checks() with:
```
sqlite3 storage/btc_bot.db ".dbinfo"
error: no such table: sqlite_dbpage
```

Production server sqlite3 build does not support `.dbinfo` command (requires SQLITE_ENABLE_DBPAGE_VTAB compile flag). Deployment was stopped before timer install. No sidecar running, btc-bot unaffected.

## Hotfix Scope
Replace `.dbinfo` with portable `SELECT COUNT(*) FROM sqlite_master;` check in:
- scripts/deploy_shadow_sidecar.sh (line 53)
- scripts/shadow_sidecar_status.sh (line 37)

## Verdict: DONE

## Portability: PASS
- `SELECT COUNT(*) FROM sqlite_master;` is standard SQLite, no compile flags required
- Returns count of schema objects (tables, indexes, views, triggers)
- Verifies DB is readable and has valid schema
- Tested locally: returns 57 for production DB

## Logic Integrity: PASS
- No change to sidecar logic, timer config, or resource guards
- Only changes: DB readability check in deployment scripts
- deploy_shadow_sidecar.sh: added explicit fail message if check fails
- shadow_sidecar_status.sh: added error path if DB exists but is unreadable

## Test Coverage: PASS
- test_deployment_scripts_preserve_btc_service_boundaries: PASSED
- Test verifies script structure, not sqlite3 command execution (acceptable for this fix)
- Manual verification: `SELECT COUNT(*) FROM sqlite_master;` works on local DB

## Regression Risk: NONE
- No runtime code changed
- No sidecar logic changed
- No timer/service config changed
- No production DB writes (check is read-only query)

## Day 0 Deployment Status
**Ready for retry.**

Previous attempt state:
- Server at commit c770d76 (old version with .dbinfo bug)
- Timer/service NOT installed (deployment stopped before install_units())
- No sidecar running
- BTC PAPER bot: PID 815407, active
- Shadow DB: 1 dry-run row from pre-start check only

Retry requirements:
1. git pull on server to commit 041046a (this fix)
2. Execute scripts/deploy_shadow_sidecar.sh
3. Verify Day 0 acceptance criteria (unchanged from original audit)

## Critical Issues
None.

## Warnings
None.

## Observations
1. `.dbinfo` is a sqlite3 shell built-in, not SQL command - portability varies by build
2. `PRAGMA integrity_check;` would be more thorough but slower on large DBs
3. `SELECT COUNT(*) FROM sqlite_master;` is fast and sufficient for readability check

## Recommended Next Step
Hand back to Codex for Day 0 deployment retry with commit 041046a.

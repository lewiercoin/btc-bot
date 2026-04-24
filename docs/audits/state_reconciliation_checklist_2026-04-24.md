# State Reconciliation Checklist
Date: 2026-04-24

## Code-Path Checks
- [x] Startup recovery entrypoint exists in `execution/recovery.py`
- [x] Inconsistency classes explicitly modeled: `unknown_position`, `phantom_position`, `orphan_orders`
- [x] `safe_mode_events` audit table exists
- [x] `safe_mode_entry_at` exists in persisted bot state
- [x] Kill-switch activation path persists safe mode through `StateStore.set_safe_mode()`
- [x] Decision loop skips new entries while safe mode is active

## Current Production Snapshot Checks
- [x] Current `bot_state.safe_mode = 0`
- [x] Current `bot_state.healthy = 1`
- [x] Current open positions count = 0
- [x] Recent 15m cycles are continuing after restart

## Historical Incident Checks
- [x] `health_check_failure_threshold` safe-mode entry confirmed on 2026-04-23
- [x] 2026-04-24 restart/startup sequence confirmed in journal
- [x] Safe-mode clear events exist in audit trail

## Remaining Confidence Gaps
- [ ] Current production is PAPER mode, so exchange-side reconciliation path is not actively exercised by this runtime
- [ ] Manual recovery operator instructions are stale/incomplete
- [ ] Auxiliary status helper `scripts/query_bot_status.py` is partially inconsistent with current safe-mode event vocabulary

## Manual Operator Recovery Requirements (desired current-state guide)
- [ ] Verify service state (`systemctl status btc-bot`)
- [ ] Verify bot state from production DB
- [ ] Inspect most recent `safe_mode_events`
- [ ] Check open positions vs expected runtime state
- [ ] Inspect recent journal lines around startup / websocket / recovery
- [ ] Only then consider manual clear or restart procedure

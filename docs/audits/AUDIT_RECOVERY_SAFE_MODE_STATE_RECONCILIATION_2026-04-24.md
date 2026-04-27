# AUDIT: Recovery / Safe Mode / State Reconciliation
Date: 2026-04-24
Auditor: Cascade (Builder Mode)
Commit: 2b59bb5

## Verdict: MVP_DONE

## Startup Recovery Logic: PASS
## Safe Mode Trigger Discipline: WARN
## State Persistence / Audit Trail: PASS
## Phantom Position / Reconciliation Risk: WARN
## Startup Log Evidence: PASS
## Manual Recovery Path: FAIL

## Critical Issues (must fix before next milestone)
- Manual/operator recovery documentation is not reliable in its current form:
  - `scripts/diagnostics/check_safe_mode.sh` is stale against current log path and `bot_state` schema
  - the matching operator markdown guide was not present in the repository at the expected diagnostics path
- Reconciliation confidence is limited by mode and evidence surface:
  - in PAPER mode, startup recovery uses `NoOpRecoverySyncSource` and clears technical safe mode triggers optimistically on restart
  - this is acceptable for paper runtime, but it means exchange-side reconciliation is not exercised in the current production mode

## Warnings (fix soon)
- A historical safe-mode event is confirmed on production:
  - `entered|health_check_failure_threshold|health_check_failure_threshold|2026-04-23T16:33:26...`
  - journal evidence shows websocket failure/reconnect shortly before the kill-switch event
- `safe_mode_events` evidence shows multiple `cleared` events with empty reason fields, which is operationally acceptable but reduces forensic clarity for exactly why the clear occurred
- Current paper-mode restart logic clears technical triggers on startup by assumption of operator intervention; this is pragmatic but not equivalent to full in-process recovery proof
- `scripts/query_bot_status.py` is not reliable for safe-mode reason lookup when safe mode is active because it expects `ENTRY` instead of current `entered`

## Observations (non-blocking)
- Recovery implementation is present and structured correctly:
  - startup sync exists in `execution/recovery.py`
  - state persistence exists in `storage/state_store.py`
  - `safe_mode_events` audit trail exists in both schema and state-store migration path
  - `safe_mode_entry_at` exists in schema/state model
- Current production state is healthy:
  - `safe_mode = 0`
  - `healthy = 1`
  - `open_positions = 0`
- `2026-04-24 04:10 UTC` restart window looks clean:
  - graceful shutdown logged
  - systemd restart occurred
  - bootstrap summary logged on startup
  - runtime loop resumed
  - websocket market-path 404 fallback to legacy stream succeeded
  - next decision cycle at `04:15 UTC` completed normally
- Recovery inconsistency categories remain explicitly modeled in code:
  - `unknown_position`
  - `phantom_position`
  - `orphan_orders`
  - isolated/leverage mismatch checks

## Recommended Next Step
Refresh the operator recovery tooling so it matches current log/schema reality, then add a small read-only operator runbook for safe-mode triage that uses the current production DB/log contracts and documents exactly how to verify or clear recovery state safely.

# AUDIT: Recovery Startup Sync

**Date:** 2026-03-26
**Auditor:** Cascade
**Commits:** 436756b (fix), initial implementation pre-commit audited
**Scope:** Blueprint §9 — Recovery Startup Sync

## Verdict: MVP_DONE

## Layer Separation: PASS

- `RecoveryCoordinator` depends on `ExchangeSyncSource` Protocol (not concrete Binance client)
- `BinanceRecoverySyncSource` is a clean adapter
- `NoOpRecoverySyncSource` added for paper mode — no exchange dependency
- Imports are clean: `core.models.Position` (contract), `StateStore` (state), `AuditLogger` (cross-cutting)
- No new layer leaks introduced

## Contract Compliance: PASS

- `RecoveryReport` is a clean output dataclass
- `ExchangePosition` / `ExchangeOrder` are local to recovery module
- `get_open_positions_snapshot()` returns `list[Position]` via `core/models.py` contract
- `set_safe_mode()` updates `BotState` through proper state_store path

## Determinism: PASS

- `_validate_recovery_state` is deterministic: `sorted(set(issues))`
- No randomness or hidden state
- `datetime.now(timezone.utc)` used correctly at boundaries only

## State Integrity: PASS

- `safe_mode` flag persists in SQLite via `StateStore.set_safe_mode()`
- Smoke test verifies persisted state matches report state
- Recovery is idempotent — safe to run multiple times

## Error Handling: WARN

- Exchange sync failure → caught → `safe_mode` ✓
- `set_safe_mode` uses `assert state is not None` — asserts stripped with `-O` flag. Minor for MVP.

## Smoke Coverage: WARN

4 scenarios covered: happy_path, unknown_position, phantom_position, orphan_orders.
Orchestrator path verified: PAPER mode gets `NoOpRecoverySyncSource`.

**Not covered:** exchange_sync_failed, isolated_mode_mismatch, leverage_mismatch, combined inconsistencies, pure cold start (no positions either side).

## Tech Debt: MEDIUM

- `_signed_request` duplicates retry logic from `_request` (refactor opportunity)
- Pre-existing issues #1-#4 remain tracked, correctly out-of-scope

## AGENTS.md Compliance: PASS

- Commit messages follow WHAT/WHY/STATUS format
- Layer separation respected
- UTC timestamps used correctly
- No hidden side effects

## Critical Issues (must fix before next milestone)

*None — Critical #1 (paper mode recovery) was fixed in 436756b.*

## Warnings (fix soon)

1. **Safe mode = exit**: orchestrator returns on safe_mode instead of staying alive to manage existing positions (Blueprint §9.3). Acceptable for MVP — Phase F handles full event loop.
2. **Smoke test gaps**: Missing coverage for exchange_sync_failed, isolated_mode_mismatch, leverage_mismatch, combined issues.

## Observations (non-blocking)

1. Position size/entry_price not cross-validated between local and exchange — acceptable for MVP
2. `_signed_request` retry logic duplication with `_request` — refactor candidate
3. `normalize_position_risk` handles BOTH/LONG/SHORT position sides correctly
4. Signed request timestamp refresh on retry — fixed in 436756b ✓

## Recommended Next Step

Complete Phase D: implement `LiveExecutionEngine` and `OrderManager` (last remaining stubs in Phase D).

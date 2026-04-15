# CLAUDE HANDOFF → CASCADE (BUILDER MODE)

**Date:** 2026-04-15  
**From:** Claude Code (Auditor)  
**Milestone:** SAFE-MODE-AUTO-RECOVERY-MVP  
**Priority:** HIGH (bot stuck 17 days, blocking paper trading)

---

## Checkpoint

- **Last commit:** `dacb110` ("audit: REPO-BRANCH-CONSISTENCY")
- **Branch:** `main`
- **Working tree:** Clean (untracked consultation docs only, not blocking)
- **Server state:** Bot running on commit `0f6c129` (3 commits behind local), stuck in safe_mode for 17 days

---

## Context: Why This Milestone Exists

**Problem:** Bot stuck in safe_mode for 17 days, not generating trades.

**Root cause:** Fix #8 (commit `45c9d3d`) added blanket sticky behavior in `execution/recovery.py:116-129`:
```python
if last_state and last_state.safe_mode:
    return RecoveryReport(healthy=False, safe_mode=True, issues=[])  # ← ONE-WAY DOOR
```

**What happened:**
1. Day 1: Binance unreachable → `health_check_failure_threshold` → safe_mode=TRUE
2. Day 2: Proxy added → problem fixed → bot restarted
3. **Every restart:** Fix #8 preserves safe_mode → bot never exits safe_mode
4. Result: 17 days with NO trading, infrastructure works but bot blocked

**Additional bug:** Fix #8 returns `RecoveryReport(safe_mode=True)` WITHOUT calling `set_safe_mode(True)` → DB shows safe_mode=FALSE, runtime operates with safe_mode=TRUE (divergence).

**What we're fixing:** Remove blanket sticky, add trigger-aware recovery, fix DB divergence.

---

## Before You Code

**Mandatory reads (in order):**
1. `CASCADE.md` — your operating model (builder mode, NO self-audit)
2. `AGENTS.md` — commit discipline, layer rules, determinism requirements
3. `docs/audits/AUDIT_SAFE_MODE_FINAL_DIAGNOSIS.md` — root cause analysis (lines 1-262)
4. `docs/SAFE_MODE_ROUND2_CONSULTATION_SUMMARY.md` — architectural decision rationale
5. `execution/recovery.py` — current Fix #8 code (lines 110-191)
6. `storage/state_store.py` — set_safe_mode() implementation (lines 106-117)
7. `orchestrator.py` — kill switch logic (lines 516-544), health check (lines 499-514)

**Optional context (if you want deeper understanding):**
- `docs/prompts/CONSULTATION_RESPONSES_CASCADE_AND_CODEX.txt` — full Round 1 + Round 2 responses
- Your own Round 2 response (you already know this)

---

## Milestone: SAFE-MODE-AUTO-RECOVERY-MVP

**Scope:** Fix #8 removal + trigger-aware startup recovery + DB divergence fix + foundation for Phase 2

**Blueprint reference:** Not explicitly in blueprint (this is operational bug fix + infrastructure hardening)

**Deliverables:**

### 1. Remove Fix #8 Blanket Sticky Behavior
**File:** `execution/recovery.py` lines 116-129

**Current code (REMOVE):**
```python
if isinstance(self.exchange_sync, NoOpRecoverySyncSource):
    if last_state and last_state.safe_mode:
        self.audit_logger.log_warning(
            "recovery",
            "Paper-mode startup recovery preserved existing safe mode.",
            payload={"previous_safe_mode": True},
        )
        return RecoveryReport(healthy=False, safe_mode=True, issues=[])  # ← BUG: doesn't write DB
    self.state_store.set_safe_mode(False, reason=None, now=now)
```

**New code (IMPLEMENT):**
```python
if isinstance(self.exchange_sync, NoOpRecoverySyncSource):
    if last_state and last_state.safe_mode:
        # Trigger-aware recovery: classify trigger type
        trigger = (last_state.last_error or "").split(":")[0].strip()
        
        # Technical/transient triggers: optimistic clear on restart
        # Rationale: restart usually means operator fixed the problem (added proxy, fixed network)
        if trigger in (
            "snapshot_build_failed",
            "health_check_failure_threshold",
            "feed_start_failed",
            "exchange_sync_failed",
        ):
            self.audit_logger.log_info(
                "recovery",
                "Paper-mode startup: clearing technical safe_mode trigger (optimistic recovery).",
                payload={
                    "trigger": trigger,
                    "previous_safe_mode": True,
                    "rationale": "Restart signals operator intervention; technical issue likely resolved",
                },
            )
            # FIX DB DIVERGENCE: ALWAYS write to DB before return
            self.state_store.set_safe_mode(False, reason=None, now=now)
            return RecoveryReport(healthy=True, safe_mode=False, issues=[])
        
        # Capital-protection / state-consistency triggers: preserve until condition met
        # Rationale: DD/losses/inconsistency require explicit resolution, not just restart
        else:
            self.audit_logger.log_warning(
                "recovery",
                "Paper-mode startup: preserving capital-protection safe_mode trigger.",
                payload={
                    "trigger": trigger,
                    "previous_safe_mode": True,
                    "rationale": "Capital/state triggers require calendar rollover or manual intervention",
                },
            )
            # FIX DB DIVERGENCE: ALWAYS write to DB before return
            self.state_store.set_safe_mode(True, reason=last_state.last_error, now=now)
            return RecoveryReport(healthy=False, safe_mode=True, issues=[])
    
    # No previous safe_mode: clear and proceed
    self.state_store.set_safe_mode(False, reason=None, now=now)
    # ... rest of paper mode path unchanged
```

---

### 2. Add `safe_mode_entry_at` Field to BotState
**Files:** `core/models.py`, `storage/state_store.py`

**core/models.py** — add field to `BotState` dataclass (around line 85):
```python
@dataclass
class BotState:
    # ... existing fields ...
    safe_mode: bool = False
    safe_mode_entry_at: datetime | None = None  # NEW: when safe_mode was last set to True
    last_error: str | None = None
    # ... rest of fields ...
```

**storage/state_store.py** — modify `set_safe_mode()` to populate entry timestamp (lines 106-117):
```python
def set_safe_mode(self, enabled: bool, reason: str | None, now: datetime) -> None:
    """Enable or disable safe mode with audit trail."""
    state = self.refresh_runtime_state()
    assert state is not None
    
    # Determine entry timestamp:
    # - If enabling safe_mode and it was previously off: record now
    # - If enabling safe_mode and it was already on: preserve existing entry_at
    # - If disabling safe_mode: clear entry_at (set to None)
    if enabled and not state.safe_mode:
        new_entry_at = now  # first entry into safe_mode
    elif enabled and state.safe_mode:
        new_entry_at = state.safe_mode_entry_at  # preserve existing
    else:
        new_entry_at = None  # clearing safe_mode
    
    self.save(
        replace(
            state,
            safe_mode=enabled,
            last_error=reason,
            safe_mode_entry_at=new_entry_at,
        )
    )
```

---

### 3. DB Schema Migration
**File:** `storage/state_store.py` in `ensure_initialized()` (lines 41-57)

**Add migration:**
```python
def ensure_initialized(self) -> None:
    """Ensure schema exists and apply migrations."""
    with self.conn:
        cursor = self.conn.cursor()
        
        # ... existing table creation ...
        
        # Migration: add safe_mode_entry_at column if it doesn't exist
        cursor.execute("PRAGMA table_info(bot_state)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if "safe_mode_entry_at" not in columns:
            cursor.execute("ALTER TABLE bot_state ADD COLUMN safe_mode_entry_at TEXT DEFAULT NULL")
            self.logger.info("Migration: added safe_mode_entry_at column to bot_state table")
        
        # ... rest of migrations ...
```

---

### 4. Create `safe_mode_events` Audit Table
**File:** `storage/state_store.py` in `ensure_initialized()`

**Add table creation:**
```python
cursor.execute("""
    CREATE TABLE IF NOT EXISTS safe_mode_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        trigger TEXT,
        reason TEXT,
        probe_successes INTEGER DEFAULT 0,
        probe_failures INTEGER DEFAULT 0,
        remaining_triggers TEXT,
        timestamp TEXT NOT NULL
    )
""")
```

**Optional (Phase 2 prep):** Add event writing in `set_safe_mode()` (wrapped try/except so audit failure doesn't block operational state change):
```python
# After self.save(...) in set_safe_mode():
try:
    cursor = self.conn.cursor()
    cursor.execute(
        """INSERT INTO safe_mode_events 
           (event_type, trigger, reason, timestamp) 
           VALUES (?, ?, ?, ?)""",
        (
            "entered" if enabled else "cleared",
            (reason or "").split(":")[0] if reason else None,
            reason,
            now.isoformat(),
        ),
    )
    self.conn.commit()
except Exception as evt_exc:
    self.logger.warning(f"Failed to write safe_mode event to audit table: {evt_exc}")
    # Operational state change already succeeded — continue
```

---

### 5. Unit Test for Trigger Classification
**File:** `tests/test_recovery_trigger_aware.py` (new file)

**Minimal smoke test:**
```python
"""Test trigger-aware startup recovery logic."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from dataclasses import replace

from execution.recovery import RecoveryCoordinator
from core.models import BotState


UTC = timezone.utc


def test_technical_trigger_clears_on_restart():
    """snapshot_build_failed should clear on restart (optimistic)."""
    state_store = MagicMock()
    state_store.load.return_value = BotState(
        safe_mode=True,
        last_error="snapshot_build_failed:Binance unreachable",
        safe_mode_entry_at=datetime(2026, 4, 13, 14, 0, tzinfo=UTC),
    )
    
    coordinator = RecoveryCoordinator(
        exchange_sync=MagicMock(spec=["NoOpRecoverySyncSource"]),  # PAPER mode
        state_store=state_store,
        audit_logger=MagicMock(),
        settings=MagicMock(),
    )
    
    report = coordinator.startup_recovery(now=datetime(2026, 4, 15, 10, 0, tzinfo=UTC))
    
    assert report.safe_mode is False  # cleared
    state_store.set_safe_mode.assert_called_once_with(False, reason=None, now=...)


def test_capital_trigger_preserves_on_restart():
    """daily_dd trigger should preserve on restart (not calendar-based recovery yet)."""
    state_store = MagicMock()
    state_store.load.return_value = BotState(
        safe_mode=True,
        last_error="daily_dd>0.1850",
        safe_mode_entry_at=datetime(2026, 4, 15, 14, 0, tzinfo=UTC),
    )
    
    coordinator = RecoveryCoordinator(
        exchange_sync=MagicMock(spec=["NoOpRecoverySyncSource"]),
        state_store=state_store,
        audit_logger=MagicMock(),
        settings=MagicMock(),
    )
    
    report = coordinator.startup_recovery(now=datetime(2026, 4, 15, 15, 0, tzinfo=UTC))
    
    assert report.safe_mode is True  # preserved
    state_store.set_safe_mode.assert_called_once_with(True, reason="daily_dd>0.1850", now=...)
```

---

## Target Files (expected changes)

| File | Change Type | Lines (approx) |
|---|---|---|
| `execution/recovery.py` | MODIFY | 116-129 → 116-160 (~40 lines) |
| `core/models.py` | MODIFY | Add 1 field to BotState |
| `storage/state_store.py` | MODIFY | set_safe_mode() + ensure_initialized() |
| `tests/test_recovery_trigger_aware.py` | CREATE | ~60 lines (2 smoke tests) |

**Total scope:** 3 modified files + 1 new test file

---

## Known Issues (from prior audits)

| # | Issue | Blocking for this milestone? | Decision |
|---|---|---|---|
| 1 | Bot stuck in safe_mode for 17 days | **YES** | **IN SCOPE** — this milestone fixes it |
| 2 | DB divergence: RecoveryReport(safe_mode=True) without set_safe_mode(True) | **YES** | **IN SCOPE** — fixed by always calling set_safe_mode() |
| 3 | No runtime recovery logic (only startup) | NO | **OUT OF SCOPE** — Phase 2 |
| 4 | No per-trigger probe state persistence | NO | **OUT OF SCOPE** — Phase 2 |
| 5 | No flapping protection | NO | **OUT OF SCOPE** — Phase 2 |
| 6 | critical_execution_errors LIVE mode = manual-only not enforced | NO | **OUT OF SCOPE** — Phase 2 |

**Critical path:** Issues #1 and #2 MUST be fixed in this milestone. Everything else is Phase 2.

---

## Acceptance Criteria (how we know it's done)

### Functional Requirements

1. **Bot unstucks on deploy:**
   - Deploy to server (currently on commit 0f6c129, stuck in safe_mode)
   - Restart bot
   - Bot detects `safe_mode=True` + `last_error="health_check_failure_threshold"` (or similar technical trigger)
   - Bot calls new trigger-aware logic → classifies as technical → clears safe_mode
   - Bot resumes normal decision cycles
   - Verify: `tail -f logs/btc_bot.log | grep "Cycle complete"` shows cycles running

2. **DB state matches runtime state:**
   - After any startup recovery, query `SELECT safe_mode FROM bot_state` → must match RecoveryReport.safe_mode
   - No more divergence (DB says FALSE, runtime TRUE)

3. **safe_mode_entry_at populated:**
   - When safe_mode enters (via kill switch or health check): `safe_mode_entry_at` = timestamp of entry
   - When safe_mode clears: `safe_mode_entry_at` = NULL

4. **Trigger classification correct:**
   - Technical triggers: `snapshot_build_failed`, `health_check_failure_threshold`, `feed_start_failed`, `exchange_sync_failed` → clear on restart
   - Capital triggers: `daily_dd*`, `weekly_dd*`, `consecutive_losses*` → preserve on restart
   - Unknown triggers: preserve (conservative default)

### Non-Functional Requirements

5. **Migration safe:**
   - `ALTER TABLE` migration runs idempotently (checks column existence)
   - No data loss (existing bot_state rows preserved)
   - Backwards compatible (old rows with NULL safe_mode_entry_at work correctly)

6. **Test coverage:**
   - At least 2 smoke tests (technical trigger clear, capital trigger preserve)
   - Tests are deterministic (use explicit `now` parameter, no `datetime.now()`)

7. **Audit trail:**
   - Every safe_mode state change logs to audit_logger with trigger classification
   - Logs include rationale ("optimistic recovery" vs "preserve capital trigger")

---

## Your First Response Must Contain

Before writing ANY code, your response must include:

### 1. Confirmed Milestone Scope
Restate in your own words what you're implementing. Confirm you understand:
- Fix #8 removal
- Trigger classification logic (technical vs capital)
- DB divergence fix (always call set_safe_mode)
- Migration for safe_mode_entry_at

### 2. Acceptance Criteria
Restate how you'll verify this works. Include:
- Manual test plan (SSH to server, verify stuck bot unsticks)
- Smoke test plan (unit tests to run)

### 3. Known Issues In-Scope vs Out-of-Scope
Confirm which issues you're fixing:
- IN: stuck bot, DB divergence
- OUT: runtime recovery, flapping protection, Phase 2 features

### 4. Implementation Plan (ordered steps)
List the exact order you'll implement this:
```
Step 1: [...]
Step 2: [...]
Step 3: [...]
```

### 5. Only Then: Start Coding
After confirming scope, criteria, plan → proceed with implementation.

---

## Commit Discipline

Every commit message must follow WHAT / WHY / STATUS format:

**Good examples:**
```
feat: add trigger-aware startup recovery logic

WHY: Fix #8 blanket sticky caused 17-day stuck bot. Technical 
     triggers (snapshot, health) should clear on restart when 
     operator fixed infrastructure (added proxy). Capital triggers
     (DD, losses) require calendar rollover.

STATUS: execution/recovery.py modified, smoke tests pass
```

```
fix: always write safe_mode to DB before return

WHY: Fix #8 returned RecoveryReport(safe_mode=True) without calling
     set_safe_mode(True), causing DB/runtime divergence. Dashboard
     showed FALSE while bot operated in safe_mode.

STATUS: recovery.py lines 116-160, DB divergence eliminated
```

**Do NOT:**
- Self-mark as "done" or "MVP complete" — Claude Code audits after push
- Use vague messages like "fix bug" or "update recovery"
- Commit broken code (every commit should be a working state)

---

## Phase 2 Preview (NOT in this milestone)

**What Phase 2 will add** (for context, but DO NOT implement now):
- `execution/safe_mode_recovery.py` — SafeModeRecoveryManager class
- `_run_safe_mode_recovery_check(now)` in orchestrator event loop
- Runtime recovery logic (probe-based for technical, calendar-based for DD/losses)
- `safe_mode_triggers_json` field for per-trigger state
- Flapping protection (reentry counters)
- Full test suite

**This milestone is ONLY the foundation.** Phase 2 will build on top of this.

---

## Deploy Plan (after implementation)

1. **Local testing:**
   - Run smoke tests: `pytest tests/test_recovery_trigger_aware.py -v`
   - Verify migration: create test DB, run ensure_initialized(), check column exists

2. **Commit + push:**
   - Commit with proper WHAT/WHY/STATUS message
   - Push to `main` (or feature branch if you prefer review first)

3. **Server deploy:**
   ```bash
   ssh -i "c:\development\btc-bot\btc-bot-deploy" root@204.168.146.253
   cd /home/btc-bot/btc-bot
   git pull origin main
   systemctl restart btc-bot
   tail -f logs/btc_bot.log | grep -E "Cycle|safe_mode|recovery"
   ```

4. **Verification:**
   - Check logs for "clearing technical safe_mode trigger" message
   - Check logs for "Cycle complete" entries (bot resumed trading)
   - Query DB: `SELECT safe_mode, safe_mode_entry_at FROM bot_state` → should show FALSE, NULL

5. **If verification fails:**
   - Check logs for exceptions
   - DO NOT mark as done
   - Report findings to Claude Code for audit

---

## Notes

- This is a **HIGH PRIORITY** milestone (bot offline 17 days)
- User expects deploy **within 24 hours** (but quality > speed)
- Your Round 2 response already laid out this exact plan — you know this design well
- This is YOUR architecture (you authored it) — implement with confidence
- Claude Code will audit after implementation — do NOT self-audit

---

**STATUS:** Awaiting Cascade's confirmation of scope + implementation plan before coding begins.

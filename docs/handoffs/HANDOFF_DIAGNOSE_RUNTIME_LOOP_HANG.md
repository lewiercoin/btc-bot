# CLAUDE HANDOFF → CASCADE (BUILDER MODE)

**Date:** 2026-04-15  
**From:** Claude Code (Auditor)  
**Milestone:** DIAGNOSE-RUNTIME-LOOP-HANG  
**Priority:** HIGH (bot cannot run decision cycles)

---

## Context: What We Discovered

### MVP Deploy Result: PARTIAL SUCCESS ✅❌

**What worked (MVP fix):**
- ✅ Safe mode sticky bug FIXED — bot no longer enters safe_mode on restart
- ✅ Migration successful (safe_mode_entry_at column added)
- ✅ DB state correct (safe_mode=0, healthy=1)
- ✅ Trigger-aware recovery logic working (no "Startup recovery entered safe mode" in latest logs)

**What failed (pre-existing infrastructure issue):**
- ❌ Bot never reaches "Runtime loop started" log
- ❌ No decision cycles run (no "Cycle complete" logs)
- ❌ Bot hangs after websocket connection

### Critical Finding

**This is NOT caused by MVP changes.** You rolled back to commit `0f6c1298` (before MVP) and the same issue occurred.

**Timeline analysis:**
```
OLD CODE (before MVP):
  Bot started in PAPER mode ✅
  Startup recovery entered safe mode ✅ (Fix #8 sticky - expected)
  Connected websocket stream ✅
  ... SILENCE (no Runtime loop started) ❌

NEW CODE (after MVP):
  Bot started in PAPER mode ✅
  Migration applied ✅
  Connected websocket stream ✅
  ... SILENCE (no "Startup recovery entered safe mode" = MVP fix worked) ✅
  ... SILENCE (no Runtime loop started) ❌
```

**Conclusion:** Bot has been broken for an unknown period (possibly days/weeks). MVP deploy revealed this pre-existing issue.

---

## Problem Statement

**Where bot hangs:**
```python
# orchestrator.py start() method:
Line 286: LOG.info("Bot started in %s mode")          ✅ VISIBLE in logs
Line 287: self.state_store.ensure_initialized()       ✅ Migration runs
Line 288: self.state_store.refresh_runtime_state()    ?
Line 290: recovery_report = self.recovery.run_startup_sync()  ?
Line 291-295: if recovery_report.safe_mode: LOG.warning(...)  ✅ NOT visible (safe_mode=FALSE, MVP fix working)
Line 297: self._start_data_feeds()                    ✅ Websocket connects
Line 298-299: self._initialize_runtime_schedule(now)  ?
Line 302: audit_logger.log_info("Runtime loop started")  ❌ NEVER VISIBLE
Line 306: self._run_event_loop()                      ❌ Never reached
```

**Hypothesis:** Code hangs somewhere between line 297 and line 302.

**Possible causes:**
1. `_start_data_feeds()` does not return (blocking call)
2. `_initialize_runtime_schedule()` hangs (infinite loop, deadlock)
3. `audit_logger.log_info()` hangs (blocking write, deadlock)
4. Uncaught exception between 297-302 (caught but not logged)
5. `self._now()` hangs (line 298 - unlikely but possible)

---

## Your Task: Add Debug Logging

**Goal:** Find the exact line where bot hangs.

**Approach:** Add granular logging between line 286 and line 306 to pinpoint hang location.

**Do NOT attempt to fix the hang** — this is diagnostic only. Report findings to Claude Code.

---

## Deliverable: Debug Logging Patch

### Step 1: Add Debug Logs to orchestrator.py

**File:** `orchestrator.py` method `start()` (lines 284-308)

**Add logs after EVERY statement between "Bot started" and "Runtime loop started":**

```python
def start(self) -> None:
    self._stop_event.clear()
    LOG.info("Bot started in %s mode", self.settings.mode.value)
    
    LOG.info("[DEBUG] Step 1: Calling state_store.ensure_initialized()")  # NEW
    self.state_store.ensure_initialized()
    LOG.info("[DEBUG] Step 2: ensure_initialized() completed")  # NEW
    
    LOG.info("[DEBUG] Step 3: Calling state_store.refresh_runtime_state()")  # NEW
    self.state_store.refresh_runtime_state(self._now())
    LOG.info("[DEBUG] Step 4: refresh_runtime_state() completed")  # NEW

    LOG.info("[DEBUG] Step 5: Calling recovery.run_startup_sync()")  # NEW
    recovery_report = self.recovery.run_startup_sync()
    LOG.info("[DEBUG] Step 6: run_startup_sync() completed, safe_mode=%s", recovery_report.safe_mode)  # NEW
    
    if recovery_report.safe_mode:
        LOG.warning(
            "Startup recovery entered safe mode. New trades are blocked but lifecycle monitoring will continue. issues=%s",
            recovery_report.issues,
        )

    LOG.info("[DEBUG] Step 7: Calling _start_data_feeds()")  # NEW
    self._start_data_feeds()
    LOG.info("[DEBUG] Step 8: _start_data_feeds() completed")  # NEW
    
    LOG.info("[DEBUG] Step 9: Calling _now()")  # NEW
    now = self._now()
    LOG.info("[DEBUG] Step 10: _now() completed, now=%s", now.isoformat())  # NEW
    
    LOG.info("[DEBUG] Step 11: Calling _initialize_runtime_schedule()")  # NEW
    self._initialize_runtime_schedule(now)
    LOG.info("[DEBUG] Step 12: _initialize_runtime_schedule() completed")  # NEW
    
    LOG.info("[DEBUG] Step 13: Calling audit_logger.log_info()")  # NEW
    self.bundle.audit_logger.log_info(
        "orchestrator",
        "Runtime loop started.",
        payload={"mode": self.settings.mode.value, "symbol": self.settings.strategy.symbol},
    )
    LOG.info("[DEBUG] Step 14: audit_logger.log_info() completed")  # NEW
    
    LOG.info("[DEBUG] Step 15: Entering _run_event_loop()")  # NEW
    try:
        self._run_event_loop()
    finally:
        self._shutdown()
```

**Total:** 14 new debug log statements.

---

### Step 2: Add Debug Logs to _start_data_feeds()

**File:** `orchestrator.py` method `_start_data_feeds()` (lines 637-649)

**Add logs to verify websocket start behavior:**

```python
def _start_data_feeds(self) -> None:
    LOG.info("[DEBUG] _start_data_feeds: Entry")  # NEW
    websocket_client = self.bundle.market_data.websocket_client
    if websocket_client is None:
        LOG.info("[DEBUG] _start_data_feeds: websocket_client is None, returning")  # NEW
        return

    try:
        LOG.info("[DEBUG] _start_data_feeds: Calling websocket_client.start()")  # NEW
        websocket_client.start(symbol=self.settings.strategy.symbol)
        LOG.info("[DEBUG] _start_data_feeds: websocket_client.start() returned")  # NEW
        
        self.bundle.audit_logger.log_info("orchestrator", "Market data feeds started.")
        LOG.info("[DEBUG] _start_data_feeds: audit_logger.log_info() completed")  # NEW
    except Exception as exc:
        LOG.error("[DEBUG] _start_data_feeds: Exception caught: %s", exc)  # NEW
        reason = f"feed_start_failed:{exc}"
        self.bundle.audit_logger.log_error("orchestrator", "Failed to start market data feeds.", payload={"error": str(exc)})
        self.state_store.set_safe_mode(True, reason=reason, now=self._now())
        self._send_critical_error_alert("orchestrator", f"Failed to start market data feeds: {exc}")
    
    LOG.info("[DEBUG] _start_data_feeds: Exit")  # NEW
```

---

### Step 3: Add Debug Logs to _initialize_runtime_schedule()

**File:** `orchestrator.py` method `_initialize_runtime_schedule()` (lines 661-669)

```python
def _initialize_runtime_schedule(self, now: datetime) -> None:
    LOG.info("[DEBUG] _initialize_runtime_schedule: Entry, now=%s", now.isoformat())  # NEW
    now_utc = now.astimezone(timezone.utc)
    LOG.info("[DEBUG] _initialize_runtime_schedule: now_utc=%s", now_utc.isoformat())  # NEW
    
    self._current_utc_day = now_utc.date()
    self._next_monitor_at = now_utc
    self._next_health_at = now_utc
    
    LOG.info("[DEBUG] _initialize_runtime_schedule: Checking 15m boundary")  # NEW
    if self._is_15m_boundary(now_utc):
        self._next_decision_at = now_utc
        LOG.info("[DEBUG] _initialize_runtime_schedule: At 15m boundary, next_decision_at=%s", now_utc.isoformat())  # NEW
    else:
        self._next_decision_at = self._next_15m_boundary(now_utc)
        LOG.info("[DEBUG] _initialize_runtime_schedule: Not at 15m boundary, next_decision_at=%s", self._next_decision_at.isoformat())  # NEW
    
    LOG.info("[DEBUG] _initialize_runtime_schedule: Exit")  # NEW
```

---

## Testing Procedure

### Step 1: Apply Debug Logging Patch

```bash
# Local: edit orchestrator.py, add all debug logs above
# Verify syntax:
python -m py_compile orchestrator.py
```

### Step 2: Commit Debug Patch

```bash
git add orchestrator.py
git commit -m "debug: add granular logging to diagnose runtime loop hang

WHY: Bot hangs between 'Bot started' and 'Runtime loop started'. Need to
     find exact line where hang occurs.

WHAT: Add [DEBUG] logs after every statement in start(), _start_data_feeds(),
      and _initialize_runtime_schedule(). 14 new log statements total.

STATUS: Diagnostic patch only. Will revert after root cause found.
"
git push origin main
```

### Step 3: Deploy to Server

```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy" root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull origin main
systemctl restart btc-bot
```

### Step 4: Monitor Logs (Real-Time)

```bash
# Watch logs for 60 seconds
timeout 60 tail -f logs/btc_bot.log | grep --line-buffered -E "Bot started|DEBUG|Runtime loop started"
```

**Expected output (if hang at specific step):**
```
[timestamp] INFO - Bot started in PAPER mode
[timestamp] INFO - [DEBUG] Step 1: Calling state_store.ensure_initialized()
[timestamp] INFO - [DEBUG] Step 2: ensure_initialized() completed
...
[timestamp] INFO - [DEBUG] Step 7: Calling _start_data_feeds()
[timestamp] INFO - [DEBUG] _start_data_feeds: Entry
[timestamp] INFO - [DEBUG] _start_data_feeds: Calling websocket_client.start()
... SILENCE (hang detected at this exact call)
```

### Step 5: Collect Full Debug Output

```bash
# Get last 200 lines (should capture full startup sequence)
tail -n 200 logs/btc_bot.log > /tmp/debug_startup_logs.txt

# Download to local
exit  # exit SSH
scp -i "c:\development\btc-bot\btc-bot-deploy" root@204.168.146.253:/tmp/debug_startup_logs.txt c:/development/btc-bot/debug_startup_logs.txt
```

---

## Analysis Checklist

After collecting logs, answer these questions:

### Q1: What is the LAST debug log that appears?

**Example:** `[DEBUG] Step 7: Calling _start_data_feeds()`

**Conclusion:** Bot hangs in `_start_data_feeds()` call.

---

### Q2: If hang is in _start_data_feeds(), what is the LAST sub-log?

**Example:** `[DEBUG] _start_data_feeds: Calling websocket_client.start()`

**Conclusion:** `websocket_client.start()` never returns (blocking call).

---

### Q3: If hang is NOT in _start_data_feeds(), what is the NEXT missing log?

**Example:** Last visible: `[DEBUG] Step 8: _start_data_feeds() completed`  
Next expected but missing: `[DEBUG] Step 9: Calling _now()`

**Conclusion:** Hang between line 298 (assignment after _start_data_feeds) and _now() call.

---

### Q4: Does the hang occur EVERY restart, or intermittently?

```bash
# Test: restart 3 times, check if hang location is consistent
systemctl restart btc-bot && sleep 15 && grep "DEBUG.*Step" logs/btc_bot.log | tail -10
systemctl restart btc-bot && sleep 15 && grep "DEBUG.*Step" logs/btc_bot.log | tail -10
systemctl restart btc-bot && sleep 15 && grep "DEBUG.*Step" logs/btc_bot.log | tail -10
```

**Deterministic hang:** Same last debug log every time → likely infinite loop or blocking call.  
**Intermittent hang:** Different last logs → likely race condition or timeout.

---

## Report Format

After testing, provide:

```
DIAGNOSTIC REPORT
Milestone: DIAGNOSE-RUNTIME-LOOP-HANG
Timestamp: [when tested]
Executor: Cascade

=== DEBUG LOGS DEPLOYED ===
Commit: [hash of debug patch]
Server pull: SUCCESS / FAIL
Bot restart: SUCCESS / FAIL

=== HANG LOCATION ===
Last visible debug log: [exact log line]
Next expected but missing: [exact log line]

Hang occurs in method: start() / _start_data_feeds() / _initialize_runtime_schedule()
Hang occurs at line: [approximate line number]
Hang occurs in call: [exact function/method call]

=== CONSISTENCY ===
Tested restarts: [3/3]
Deterministic: YES / NO (same hang location every time)

=== HYPOTHESIS ===
[Your analysis of root cause based on hang location]

Possible causes:
1. [Blocking call in X]
2. [Infinite loop in Y]
3. [Deadlock in Z]
4. [Other]

=== ATTACHED LOGS ===
File: c:/development/btc-bot/debug_startup_logs.txt
Lines: [number of lines]
Contains: Full startup sequence from "Bot started" to hang point

=== RECOMMENDED NEXT STEP ===
[What should be investigated next - e.g., "Examine websocket_client.start() implementation", "Check audit_logger for blocking writes", etc.]
```

---

## Acceptance Criteria

| # | Criteria | Verification |
|---|---|---|
| 1 | Debug logs added to start() | 14 [DEBUG] statements in start() method |
| 2 | Debug logs added to _start_data_feeds() | 6 [DEBUG] statements |
| 3 | Debug logs added to _initialize_runtime_schedule() | 5 [DEBUG] statements |
| 4 | Committed to repo | `git log -1` shows debug commit |
| 5 | Deployed to server | `git pull` successful, restart successful |
| 6 | Hang location identified | Last visible debug log documented |
| 7 | Logs collected | debug_startup_logs.txt downloaded |
| 8 | Report delivered | Diagnostic report with hypothesis |

**All 8 must PASS.**

---

## Important Notes

### Do NOT Fix the Hang

**Your task is diagnostic only.** Do NOT attempt to fix the underlying issue. Report findings to Claude Code.

**Why:** The hang may be caused by:
- Architectural issue (blocking call where async needed)
- Library bug (websocket_client implementation)
- Configuration issue (missing API key, invalid setting)
- Race condition (thread synchronization)

Fixing without understanding root cause can mask symptoms and create worse problems.

---

### Revert Debug Logs After Diagnosis

Once root cause is identified, revert debug logging patch:

```bash
git revert [debug_commit_hash]
git push origin main
```

Debug logs are verbose and will pollute production logs. Remove after diagnosis complete.

---

### If Bot Becomes Completely Broken

If debug logging patch causes bot to fail startup (syntax error, import error):

**Rollback immediately:**
```bash
ssh server
cd /home/btc-bot/btc-bot
git reset --hard 93faed5  # last known good commit (MVP audit)
systemctl restart btc-bot
systemctl status btc-bot  # verify running
```

Report rollback + error to Claude Code.

---

## Timeline

| Step | Estimated Time |
|---|---|
| Add debug logs | 15 min |
| Commit + push | 5 min |
| Deploy + restart | 5 min |
| Monitor logs | 10 min |
| Collect logs | 5 min |
| Analyze | 15 min |
| Write report | 10 min |
| **Total** | **~60 min** |

---

## Your First Response Must Contain

1. **Pre-work confirmation:**
   - [ ] Understood task: add debug logging, do NOT fix hang
   - [ ] Understood scope: 25 debug log statements total
   - [ ] Understood report format: identify exact hang location + hypothesis

2. **Implementation plan:**
   ```
   Step 1: Add 14 debug logs to start()
   Step 2: Add 6 debug logs to _start_data_feeds()
   Step 3: Add 5 debug logs to _initialize_runtime_schedule()
   Step 4: py_compile verify syntax
   Step 5: Commit + push
   Step 6: Deploy to server
   Step 7: Monitor logs for 60s
   Step 8: Collect debug_startup_logs.txt
   Step 9: Analyze hang location
   Step 10: Write diagnostic report
   ```

3. **Only then: Execute**

---

**STATUS:** Awaiting Cascade's confirmation + execution plan before diagnostic begins.
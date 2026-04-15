# CLAUDE HANDOFF → CASCADE (BUILDER MODE)

**Date:** 2026-04-15  
**From:** Claude Code (Auditor)  
**Milestone:** SAFE-MODE-AUTO-RECOVERY-MVP-DEPLOY  
**Priority:** HIGH (bot stuck 17 days, ready to unblock)

---

## Checkpoint

- **Last commit:** `93faed5` ("audit: SAFE-MODE-AUTO-RECOVERY-MVP (Claude Code verdict: MVP_DONE)")
- **Branch:** `main`
- **Working tree:** Clean
- **Audit verdict:** **MVP_DONE** ✅
- **Server state:** Bot running commit `0f6c129` (4 commits behind), stuck in safe_mode 17 days
- **Your implementation:** Commit `7a7a743` (ready for deploy)

---

## Context: Why This Task Exists

**Your implementation passed audit.** Claude Code verdict: MVP_DONE.

**What you built:**
- ✅ Removed Fix #8 blanket sticky (execution/recovery.py)
- ✅ Added trigger-aware recovery (technical → clear, capital → preserve)
- ✅ Fixed DB divergence bug (all paths call set_safe_mode)
- ✅ Added safe_mode_entry_at timestamp
- ✅ Created safe_mode_events audit table
- ✅ Migration idempotent and safe
- ✅ 111/111 tests pass

**What needs to happen now:**
1. Deploy to production server
2. Restart bot
3. Verify bot exits safe_mode (17-day stuck problem solved)
4. Verify bot resumes trading (decision cycles running)
5. Monitor for 48h to catch any issues

**This task:** You deploy your own code, verify it works, report results.

---

## Before You Start

**Mandatory reads:**
1. `docs/audits/AUDIT_008_SAFE_MODE_MVP.md` — Claude Code's audit (section "Deploy Procedure")
2. `AGENTS.md` — SSH credentials, server access
3. Your own commit `7a7a743` — refresh on what changed

**Server details:**
- **Host:** `root@204.168.146.253`
- **SSH key:** `c:\development\btc-bot\btc-bot-deploy` (NOT ~/.ssh/id_ed25519)
- **Bot directory:** `/home/btc-bot/btc-bot`
- **Logs:** `/home/btc-bot/btc-bot/logs/btc_bot.log`
- **Service:** `btc-bot` (systemd)

---

## Milestone: SAFE-MODE-AUTO-RECOVERY-MVP-DEPLOY

**Scope:** Deploy commit 7a7a743 to production, verify bot unsticks, monitor initial behavior.

**NOT in scope:**
- Code changes (implementation complete)
- Tests (already passing)
- Phase 2 features (runtime recovery, flapping protection)

---

## Deliverables

### 1. Deploy Code to Server
**Steps:**
```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy" root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull origin main
```

**Expected git output:**
```
Updating 0f6c129..7a7a743
Fast-forward
 core/models.py                       |   1 +
 execution/recovery.py                |  45 ++++++---
 storage/repositories.py              |   8 +-
 storage/schema.sql                   |  14 ++-
 storage/state_store.py               |  65 +++++++++++-
 tests/test_dashboard_db_reader.py    |   1 +
 tests/test_recovery_trigger_aware.py | 190 +++++++++++++++++++++++++++++++++++
 7 files changed, 307 insertions(+), 17 deletions(-)
```

**Verification:**
- `git log -1 --oneline` should show `7a7a743 feat: SAFE-MODE-AUTO-RECOVERY-MVP`
- `git status` should show "Your branch is up to date with 'origin/main'"

---

### 2. Restart Bot Service
**Command:**
```bash
systemctl restart btc-bot
```

**Wait 10 seconds for startup:**
```bash
sleep 10
```

**Verification:**
```bash
systemctl status btc-bot | grep Active
```

**Expected:** `Active: active (running) since ...`

---

### 3. Verify Migration Ran
**Command:**
```bash
tail -n 50 logs/btc_bot.log | grep -i migration
```

**Expected output:**
```
[timestamp] INFO - Migration applied: added safe_mode_entry_at column to bot_state
```

**If missing:** Migration already ran (column exists) OR migration failed. Check:
```bash
tail -n 100 logs/btc_bot.log | grep -i error
```

---

### 4. Verify Safe Mode Trigger Classification
**Command:**
```bash
tail -n 100 logs/btc_bot.log | grep -E "clearing technical|preserving capital"
```

**Expected (bot was stuck with technical trigger):**
```
[timestamp] INFO - Paper-mode startup: clearing technical safe_mode trigger (optimistic recovery).
```

**Trigger details:**
```bash
tail -n 100 logs/btc_bot.log | grep -B2 -A5 "clearing technical"
```

**Expected payload:**
```json
{
  "trigger": "health_check_failure_threshold",  // or snapshot_build_failed
  "previous_safe_mode": true,
  "rationale": "Restart signals operator intervention; technical issue likely resolved"
}
```

---

### 5. Verify Bot Resumed Decision Cycles
**Command (real-time monitoring, run for 2 minutes):**
```bash
timeout 120 tail -f logs/btc_bot.log | grep --line-buffered -E "Cycle complete|Signal generated|Snapshot built"
```

**Expected (entries appearing every ~30 seconds):**
```
[timestamp] INFO - Snapshot built successfully
[timestamp] INFO - Signal generated: ...
[timestamp] INFO - Cycle complete (decision=HOLD, reason=...)
```

**If no cycles appear within 2 minutes:**
```bash
# Check what's blocking
tail -n 200 logs/btc_bot.log | grep -E "safe_mode|healthy|ERROR"
```

---

### 6. Verify Database State
**Command:**
```bash
python3 << 'EOF'
import sqlite3
from datetime import datetime, timezone

conn = sqlite3.connect("storage/btc_bot.db")
cursor = conn.cursor()

print("=== BOT STATE ===")
cursor.execute("SELECT safe_mode, safe_mode_entry_at, last_error, healthy FROM bot_state ORDER BY id DESC LIMIT 1")
safe_mode, entry_at, last_error, healthy = cursor.fetchone()
print(f"safe_mode: {safe_mode} (expected: 0)")
print(f"safe_mode_entry_at: {entry_at} (expected: None)")
print(f"last_error: {last_error} (expected: None)")
print(f"healthy: {healthy} (expected: 1)")

print("\n=== SAFE MODE EVENTS ===")
cursor.execute("SELECT COUNT(*) FROM safe_mode_events")
events_count = cursor.fetchone()[0]
print(f"Total events: {events_count}")

if events_count > 0:
    cursor.execute("""
        SELECT event_type, trigger, reason, timestamp 
        FROM safe_mode_events 
        ORDER BY timestamp DESC 
        LIMIT 5
    """)
    print("\nRecent events:")
    for event_type, trigger, reason, ts in cursor.fetchall():
        print(f"  {event_type:10} | {trigger or 'N/A':35} | {ts}")

# Verify column exists
cursor.execute("PRAGMA table_info(bot_state)")
columns = [row[1] for row in cursor.fetchall()]
if "safe_mode_entry_at" in columns:
    print("\n✅ Migration successful: safe_mode_entry_at column exists")
else:
    print("\n❌ Migration failed: safe_mode_entry_at column missing")

conn.close()
EOF
```

**Expected output:**
```
=== BOT STATE ===
safe_mode: 0 (expected: 0)
safe_mode_entry_at: None (expected: None)
last_error: None (expected: None)
healthy: 1 (expected: 1)

=== SAFE MODE EVENTS ===
Total events: 1

Recent events:
  cleared    | health_check_failure_threshold       | 2026-04-15T10:30:15.123Z

✅ Migration successful: safe_mode_entry_at column exists
```

---

### 7. Verify safe_mode_events Table Schema
**Command:**
```bash
sqlite3 storage/btc_bot.db "PRAGMA table_info(safe_mode_events)"
```

**Expected (Codex's richer schema from your implementation):**
```
0|id|INTEGER|0||1
1|event_type|TEXT|1||0
2|trigger|TEXT|0||0
3|reason|TEXT|0||0
4|probe_successes|INTEGER|0|0|0
5|probe_failures|INTEGER|0|0|0
6|remaining_triggers|TEXT|0||0
7|timestamp|TEXT|1||0
```

**Verify columns:**
- ✅ event_type (NOT NULL)
- ✅ trigger
- ✅ reason
- ✅ probe_successes (Phase 2 ready)
- ✅ probe_failures (Phase 2 ready)
- ✅ remaining_triggers (Phase 2 ready)
- ✅ timestamp (NOT NULL)

---

## Acceptance Criteria (How We Know Deploy Succeeded)

| # | Criteria | Verification Command | Expected Result |
|---|---|---|---|
| 1 | Code deployed | `git log -1 --oneline` | `7a7a743 feat: SAFE-MODE-AUTO-RECOVERY-MVP` |
| 2 | Bot running | `systemctl status btc-bot` | `Active: active (running)` |
| 3 | Migration ran | `tail logs/btc_bot.log \| grep migration` | "Migration applied: added safe_mode_entry_at" |
| 4 | Safe mode cleared | `tail logs/btc_bot.log \| grep clearing` | "clearing technical safe_mode trigger" |
| 5 | Cycles running | `tail logs/btc_bot.log \| grep "Cycle complete"` | Entries appearing every ~30s |
| 6 | DB state correct | `python3 << EOF ... SELECT safe_mode` | safe_mode=0, entry_at=None |
| 7 | Audit event logged | `SELECT * FROM safe_mode_events` | event_type='cleared', trigger='health_check...' |

**All 7 must PASS before reporting success.**

---

## Known Issues to Watch For

### Issue 1: Capital Trigger Preserved (Not a Bug)

**Symptom:**
```
Paper-mode startup: preserving capital-protection safe_mode trigger.
Trigger: daily_dd>0.1850
```

**Analysis:** 
- This is **EXPECTED** if bot was in safe_mode due to DD breach, not technical issue
- Capital triggers (daily_dd, weekly_dd, consecutive_losses) require calendar rollover
- Bot will auto-recover at next UTC day 00:00 + 4h cooldown (Phase 2 feature)

**Action:** Report to Claude Code with trigger name. NOT a deploy failure.

---

### Issue 2: Unknown Trigger Preserved

**Symptom:**
```
Paper-mode startup: preserving capital-protection safe_mode trigger.
Trigger: some_unknown_trigger
```

**Analysis:**
- Conservative default: unknown trigger → preserve
- Might be legitimate (new trigger added in future) or bug (typo in last_error)

**Action:** 
1. Check what `some_unknown_trigger` is
2. Report to Claude Code
3. If legitimate unknown, manual clear:
```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect("storage/btc_bot.db")
conn.execute("UPDATE bot_state SET safe_mode=0, last_error=NULL WHERE id=1")
conn.commit()
EOF
systemctl restart btc-bot
```

---

### Issue 3: Migration Failed (Schema Error)

**Symptom:**
```
ERROR - Failed to execute migration: ...
SQLite error: ...
```

**Action:**
1. Check error details: `tail -n 200 logs/btc_bot.log | grep -A10 ERROR`
2. Check if column already exists (migration might have run partially):
   ```bash
   sqlite3 storage/btc_bot.db "PRAGMA table_info(bot_state)" | grep safe_mode_entry_at
   ```
3. If column exists but error logged → benign (idempotent check failed gracefully)
4. If column missing → report to Claude Code with full error

---

### Issue 4: Bot Crashes on Startup

**Symptom:**
```bash
systemctl status btc-bot
# Active: failed (Result: exit-code)
```

**Action:**
1. Get traceback:
   ```bash
   tail -n 500 logs/btc_bot.log | grep -A50 "Traceback"
   ```
2. **ROLLBACK IMMEDIATELY:**
   ```bash
   git reset --hard 0f6c129  # previous working commit
   systemctl restart btc-bot
   systemctl status btc-bot  # verify running
   ```
3. Report full traceback to Claude Code
4. DO NOT attempt to fix — this is audit-level issue

---

### Issue 5: Cycles Not Running (Bot "Healthy" but Silent)

**Symptom:**
```
safe_mode: 0
healthy: 1
# But no "Cycle complete" logs appearing
```

**Action:**
1. Check orchestrator state:
   ```bash
   tail -n 200 logs/btc_bot.log | grep -E "Runtime loop|Orchestrator|event loop"
   ```
2. Check for exceptions:
   ```bash
   tail -n 200 logs/btc_bot.log | grep ERROR
   ```
3. Report to Claude Code with logs

**DO NOT manually edit DB to force cycles — this is runtime logic issue.**

---

## Rollback Plan (If Deploy Fails)

**Criteria for rollback:**
- Bot crashes on startup (Issue 4)
- Bot enters infinite error loop
- Data corruption (sqlite3 errors)

**Rollback procedure:**
```bash
# 1. Stop bot
systemctl stop btc-bot

# 2. Revert code
git reset --hard 0f6c129

# 3. Restart bot
systemctl start btc-bot

# 4. Verify running
systemctl status btc-bot
tail -n 50 logs/btc_bot.log | grep "Runtime loop started"

# 5. Report rollback reason to Claude Code
```

**Note:** `safe_mode_entry_at` column will remain in DB (benign, nullable). `safe_mode_events` table will remain (benign, empty or with 1 event).

---

## Your First Response Must Contain

Before executing deploy, confirm:

### 1. Pre-Deploy Checklist
- [ ] SSH key location confirmed: `c:\development\btc-bot\btc-bot-deploy`
- [ ] Server access tested: `ssh -i ... root@204.168.146.253 "echo OK"`
- [ ] Local repo is at commit `93faed5` (audit commit)
- [ ] You understand rollback procedure (can revert if deploy fails)

### 2. Deploy Execution Plan
List the exact order you'll execute:
```
Step 1: SSH to server
Step 2: cd /home/btc-bot/btc-bot
Step 3: git pull origin main
Step 4: systemctl restart btc-bot
Step 5: Verify migration (deliverable 3)
Step 6: Verify safe_mode cleared (deliverable 4)
Step 7: Verify cycles running (deliverable 5)
Step 8: Verify DB state (deliverable 6)
Step 9: Report results
```

### 3. Success Criteria
Confirm you'll verify all 7 acceptance criteria before reporting success.

### 4. Failure Handling
Confirm you'll rollback immediately if bot crashes, and report issue to Claude Code without attempting to fix.

### 5. Only Then: Execute Deploy
After confirming plan → execute → report results with full verification outputs.

---

## Post-Deploy Monitoring (48h)

**Your responsibility:** Monitor for first 48 hours after deploy.

**What to check (every 4-6 hours):**

### Check 1: Bot Still Running
```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy" root@204.168.146.253 \
  "systemctl status btc-bot | grep Active"
```
**Expected:** `Active: active (running)`

### Check 2: Cycles Still Processing
```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy" root@204.168.146.253 \
  "cd /home/btc-bot/btc-bot && tail -n 100 logs/btc_bot.log | grep 'Cycle complete' | tail -5"
```
**Expected:** Recent timestamps (within last 10 minutes)

### Check 3: No Unexpected Safe Mode Entries
```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy" root@204.168.146.253 \
  "cd /home/btc-bot/btc-bot && grep 'entered.*safe_mode' logs/btc_bot.log | tail -5"
```
**Expected:** Empty (or only expected entries if DD breach occurs)

### Check 4: Trigger Parsing Working
```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy" root@204.168.146.253 \
  "cd /home/btc-bot/btc-bot && grep 'preserving capital' logs/btc_bot.log"
```
**Expected:** Empty (or only legitimate capital triggers: daily_dd, weekly_dd, consecutive_losses)

**If any check fails:** Report to Claude Code immediately with logs.

---

## Report Format

After deploy execution, provide this exact format:

```
DEPLOY REPORT
Milestone: SAFE-MODE-AUTO-RECOVERY-MVP-DEPLOY
Timestamp: [when you executed]
Executor: Cascade

=== PRE-DEPLOY STATE ===
Server commit before deploy: [git log -1 --oneline output]
Bot status before deploy: [systemctl status]
Safe mode before deploy: [SELECT safe_mode FROM bot_state output]

=== DEPLOY EXECUTION ===
Step 1 - git pull: [SUCCESS/FAIL + output]
Step 2 - restart: [SUCCESS/FAIL + systemctl status output]
Step 3 - migration: [PASS/FAIL + grep output]
Step 4 - safe_mode cleared: [PASS/FAIL + grep output + trigger name]
Step 5 - cycles running: [PASS/FAIL + sample Cycle complete logs]
Step 6 - DB state: [PASS/FAIL + python script output]
Step 7 - events table: [PASS/FAIL + PRAGMA output]

=== ACCEPTANCE CRITERIA ===
1. Code deployed: [PASS/FAIL]
2. Bot running: [PASS/FAIL]
3. Migration ran: [PASS/FAIL]
4. Safe mode cleared: [PASS/FAIL]
5. Cycles running: [PASS/FAIL]
6. DB state correct: [PASS/FAIL]
7. Audit event logged: [PASS/FAIL]

OVERALL: [SUCCESS / PARTIAL / FAIL]

=== ISSUES ENCOUNTERED ===
[None / List any issues from Known Issues section]

=== NEXT STEPS ===
[48h monitoring plan / Rollback executed / Issue escalated to Claude Code]
```

---

## Notes

- This deploy is **production** (paper trading, but live server)
- Bot has been stuck 17 days — user expects this to fix it
- Your implementation passed audit — high confidence it will work
- If anything goes wrong: **rollback first, debug later**
- DO NOT attempt to fix issues during deploy — report to Claude Code
- You are deploying your own code — you know it best

**Timeline expectation:** Deploy + verification should take 15-30 minutes.

**48h monitoring:** Check every 4-6 hours, report any anomalies immediately.

---

**STATUS:** Awaiting Cascade's pre-deploy confirmation + execution plan before deploy begins.
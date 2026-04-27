# Deployment Protocol: Market Truth V3 + Quant-Grade Hardening

**Date:** 2026-04-24  
**Branch:** market-truth-v3  
**Status:** ✅ APPROVED FOR PRODUCTION VALIDATION (ChatGPT)  
**Authorization:** ChatGPT audit acceptance

---

## APPROVAL STATUS

**This approval is for production validation, NOT final source-of-truth closure.**

### Commits Approved for Deploy:
- `147d865` — quant-grade hardening baseline (8 fields)
- `c68d30a` — force_orders_exchange_ts lineage fix
- `6c132e3` — ChatGPT audit response + first snapshot verification script
- `a3ff397` — fix verification script timing logic (ChatGPT-identified bug)

### Status After Deploy:
- Infrastructure: ✅ DEPLOYED
- Production validation: ⏳ IN PROGRESS
- Source-of-truth closure: ⏳ PENDING (requires 200+ cycle validation)

---

## PRE-DEPLOYMENT CHECKLIST

### 1. ✅ Local Verification (DONE)
- [x] All tests pass (219/219)
- [x] Commits pushed to GitHub
- [x] ChatGPT audit acceptance received
- [x] Verification script bug fixed (a3ff397)

### 2. ⏳ Production Backup (REQUIRED)

**CRITICAL: Create database backup before restart.**

```bash
ssh root@204.168.146.253

# Create backup
cd /home/btc-bot/backups/database
BACKUP_FILE="btc_bot_pre_quant_grade_$(date +%Y%m%d_%H%M%S).db.gz"
gzip -c /home/btc-bot/btc-bot/storage/btc_bot.db > $BACKUP_FILE

# Verify backup
ls -lh $BACKUP_FILE
gunzip -t $BACKUP_FILE && echo "✅ Backup verified"
```

**Backup verification:**
- File size > 0
- `gunzip -t` passes
- Timestamp correct

---

## DEPLOYMENT SEQUENCE

### Step 1: Deploy Branch

```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot

# Fetch latest
git fetch origin

# Checkout branch
git checkout market-truth-v3

# Pull commits
git pull origin market-truth-v3

# Verify commits
git log --oneline -4
# Expected output:
# a3ff397 fix: correct timing validation logic
# 6c132e3 docs: add ChatGPT audit response
# c68d30a fix: add force_orders_exchange_ts
# 147d865 feat: quant-grade hardening
```

### Step 2: Restart Bot

```bash
# If using systemd:
sudo systemctl restart btc-bot
sudo systemctl status btc-bot

# If using pm2:
pm2 restart btc-bot
pm2 status btc-bot

# Verify bot is running
ps aux | grep "python.*orchestrator.py"
```

### Step 3: Verify Service Status

```bash
# Check logs for migration messages
tail -100 /home/btc-bot/btc-bot/btc_bot.log | grep -i "migration\|error"

# Expected migration logs:
# INFO Migration applied: added candles_15m_exchange_ts column to market_snapshots
# INFO Migration applied: added candles_1h_exchange_ts column to market_snapshots
# INFO Migration applied: added candles_4h_exchange_ts column to market_snapshots
# INFO Migration applied: added funding_exchange_ts column to market_snapshots
# INFO Migration applied: added oi_exchange_ts column to market_snapshots
# INFO Migration applied: added aggtrades_exchange_ts column to market_snapshots
# INFO Migration applied: added force_orders_exchange_ts column to market_snapshots
# INFO Migration applied: added snapshot_build_started_at column to market_snapshots
# INFO Migration applied: added snapshot_build_finished_at column to market_snapshots

# Check for errors
tail -100 /home/btc-bot/btc-bot/btc_bot.log | grep -i "error\|exception\|traceback"
# Expected: NO errors related to migration
```

### Step 4: Wait for First Decision Cycle

**Timeline:** ~15 minutes (next cycle boundary)

```bash
# Monitor for first cycle completion
tail -f /home/btc-bot/btc-bot/btc_bot.log | grep "Decision cycle\|snapshot"
```

**Expected log pattern:**
```
INFO Decision cycle started at 2026-04-24T...
INFO Building market snapshot...
INFO Market snapshot recorded: ms-xxxxxxxx
INFO Feature snapshot recorded: fs-xxxxxxxx
INFO Decision cycle completed: NO_SIGNAL
```

### Step 5: Run First Snapshot Verification

```bash
# Run verification script
/home/btc-bot/btc-bot/.venv/bin/python /home/btc-bot/btc-bot/scripts/verify_first_snapshot.py
```

---

## ACCEPTANCE CRITERIA (First Snapshot)

### ✅ PASS Conditions:

**Build Timing:**
- ✅ `snapshot_build_started_at` is NOT NULL
- ✅ `snapshot_build_finished_at` is NOT NULL
- ✅ `snapshot_build_started_at < snapshot_build_finished_at`
- ✅ `snapshot_build_finished_at` not from future (< NOW)
- ✅ Build duration between 0.5s and 10s

**Per-Input Timestamps:**
- ✅ `candles_15m_exchange_ts` is NOT NULL
- ✅ `candles_1h_exchange_ts` is NOT NULL
- ✅ `candles_4h_exchange_ts` is NOT NULL
- ✅ `funding_exchange_ts` is NOT NULL
- ✅ `oi_exchange_ts` is NOT NULL
- ✅ `aggtrades_exchange_ts` is NOT NULL
- ⚠️ `force_orders_exchange_ts` may be NULL (OK if no force orders in 60s window)

**Timestamp Validity:**
- ✅ No input timestamps from future (< NOW)
- ✅ Input timestamps < snapshot_build_finished_at (captured before snapshot complete)
- ✅ Staleness reasonable:
  - Candles: <30 minutes
  - OI: <5 minutes
  - AggTrades: <5 minutes

**Service Health:**
- ✅ Bot remains running after restart
- ✅ No exceptions in logs
- ✅ Dashboard accessible
- ✅ WebSocket connected

### ❌ FAIL Conditions (STOP and Investigate):

**Hard Failures:**
- ❌ Build timing fields NULL
- ❌ `snapshot_build_started_at >= snapshot_build_finished_at`
- ❌ Timestamps from future
- ❌ Candles/funding/OI/aggTrades all NULL (indicates API failure)
- ❌ Bot crashes or stops responding
- ❌ Migration errors in logs

**If FAIL:**
1. **DO NOT proceed to 200+ cycle collection**
2. Capture logs: `cp /home/btc-bot/btc-bot/btc_bot.log /tmp/deployment_failure_$(date +%Y%m%d_%H%M%S).log`
3. Check database state: `sqlite3 /home/btc-bot/btc-bot/storage/btc_bot.db "SELECT * FROM market_snapshots ORDER BY cycle_timestamp DESC LIMIT 1"`
4. Consider rollback if critical

---

## POST-DEPLOYMENT: 200+ Cycle Collection

**Timeline:** ~50 hours (200 cycles × 15 min)

### Monitoring During Collection:

```bash
# Check snapshot count periodically
ssh root@204.168.146.253 "sqlite3 /home/btc-bot/btc-bot/storage/btc_bot.db \
  'SELECT COUNT(*) FROM market_snapshots WHERE snapshot_build_started_at IS NOT NULL'"

# Expected progression:
# Hour 0:   0 snapshots (just deployed)
# Hour 12:  48 snapshots
# Hour 24:  96 snapshots
# Hour 48:  192 snapshots
# Hour 50:  200+ snapshots ✅
```

### After 200+ Cycles:

**Generate validation reports:**

```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot

# 1. Feature drift validation
/home/btc-bot/btc-bot/.venv/bin/python validation/recompute_features.py \
  --db storage/btc_bot.db \
  --limit 200 \
  --markdown-out validation/feature_drift_report.md

# 2. Download report
exit
scp -i "c:\development\btc-bot\btc-bot-deploy-v2" \
  root@204.168.146.253:/home/btc-bot/btc-bot/validation/feature_drift_report.md \
  c:\development\btc-bot\validation\

# 3. Review drift report
cat c:\development\btc-bot\validation\feature_drift_report.md
```

**Expected drift report:**
- ATR fields: mean error < 1%
- EMA fields: mean error < 1%
- Overall status: ✅ PASS

**If drift report passes:**
- Status update: INFRASTRUCTURE_DONE → **VALIDATED_IN_PRODUCTION**
- Ready for merge to main
- Unblock MODELING-V1 milestone

**If drift report fails:**
- Investigate root cause
- Do NOT merge to main
- Fix issues or accept limitations (document in known gaps)

---

## ROLLBACK PROCEDURE (if needed)

**Only if critical failure during first snapshot verification.**

```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot

# 1. Checkout previous stable branch
git checkout experiment-v2  # Last known good state

# 2. Restart bot
sudo systemctl restart btc-bot
# OR: pm2 restart btc-bot

# 3. Verify service recovery
tail -100 /home/btc-bot/btc-bot/btc_bot.log | grep -i "error"

# 4. Restore database from backup (if schema corrupted)
cd /home/btc-bot/backups/database
BACKUP_FILE=$(ls -t btc_bot_pre_quant_grade_*.db.gz | head -1)
gunzip -c $BACKUP_FILE > /home/btc-bot/btc-bot/storage/btc_bot.db

# 5. Restart again
sudo systemctl restart btc-bot
```

**Rollback triggers:**
- Bot won't start after migration
- Migration errors in logs
- Database corruption
- Persistent crashes

**Do NOT rollback for:**
- Single NULL timestamp (may be transient API issue)
- High build duration (may be network latency)
- Warnings in verification script (investigate first)

---

## DEPLOYMENT LOG TEMPLATE

**Copy this to track deployment progress:**

```
## Deployment Log: Market Truth V3 + Quant-Grade Hardening

Date: _______________
Deployer: _______________

### Pre-Deployment
- [ ] Database backup created: _______________
- [ ] Backup verified: YES / NO
- [ ] Branch checked out: market-truth-v3
- [ ] Commits verified: 147d865, c68d30a, 6c132e3, a3ff397

### Deployment
- [ ] Bot restarted: TIME: _______________
- [ ] Service status: RUNNING / FAILED
- [ ] Migration logs: PASS / FAIL
- [ ] Errors in logs: YES / NO

### First Snapshot Verification
- [ ] First cycle completed: TIME: _______________
- [ ] Verification script run: TIME: _______________
- [ ] Result: PASS / FAIL

### PASS Checks:
- [ ] Build timing fields: NOT NULL
- [ ] Build timing order: start < finish
- [ ] Candles timestamps: NOT NULL
- [ ] Funding timestamp: NOT NULL
- [ ] OI timestamp: NOT NULL
- [ ] AggTrades timestamp: NOT NULL
- [ ] Force orders: NULL or NOT NULL (both OK)
- [ ] No future timestamps: YES
- [ ] Service healthy: YES

### Decision:
- [ ] PROCEED with 200+ cycle collection
- [ ] ROLLBACK (reason: _______________)

### Post-200+ Cycles (after ~50 hours):
- [ ] Drift report generated: _______________
- [ ] Drift report result: PASS / FAIL
- [ ] Status update: VALIDATED_IN_PRODUCTION / NEEDS_INVESTIGATION
```

---

## FINAL STATUS PROGRESSION

| Stage | Status | Evidence Required |
|---|---|---|
| **1. Pre-Deploy** | ✅ APPROVED FOR PRODUCTION VALIDATION | ChatGPT acceptance |
| **2. Post-Deploy** | ⏳ DEPLOYED, FIRST SNAPSHOT PENDING | Service running, migration logs clean |
| **3. First Snapshot** | ⏳ FIRST SNAPSHOT VERIFIED | verify_first_snapshot.py PASS |
| **4. Collection** | ⏳ COLLECTING 200+ CYCLES | Snapshot count increasing |
| **5. Validation** | ⏳ VALIDATED IN PRODUCTION | Drift report PASS |
| **6. Closure** | ⏳ READY FOR MERGE TO MAIN | All validation criteria met |

**Current stage:** 1 (Pre-Deploy)

**Next action:** Execute deployment sequence → verify first snapshot

---

**Deployment protocol ready. Awaiting execution authorization.**

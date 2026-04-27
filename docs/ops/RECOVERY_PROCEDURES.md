# Recovery Procedures - Quick Reference

## Overview

This document provides step-by-step recovery procedures for common failure scenarios. For comprehensive disaster recovery planning, see `docs/DISASTER_RECOVERY.md`.

**Server:** `root@204.168.146.253`  
**SSH Key:** `c:\development\btc-bot\btc-bot-deploy-v2`  
**Production DB:** `/home/btc-bot/btc-bot/storage/btc_bot.db`

## Pre-Requisites

- SSH access to production server
- Backups available (automated daily backups at `/home/btc-bot/backups/database/`)
- Bot service can be stopped safely

## Recovery Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/backup_production_db.sh` | Create database backup | Manual or automated (cron) |
| `scripts/restore_production_db.sh` | Restore from backup | Manual recovery only |
| `scripts/smoke_recovery.py` | Test recovery coordinator | Verification after schema changes |
| `scripts/check_production_drift.sh` | Detect config drift | Pre-deployment verification |

## Common Recovery Scenarios

### 1. Database Corruption

**Symptoms:**
- Bot crashes with SQLite errors
- "database disk image is malformed"
- Integrity check fails

**Recovery Steps:**

```bash
# 1. Stop bot
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl stop btc-bot.service"

# 2. Check integrity
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "cd /home/btc-bot/btc-bot && sqlite3 storage/btc_bot.db 'PRAGMA integrity_check;'"

# 3. If corrupted, restore from latest backup
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "cd /home/btc-bot/btc-bot && ./scripts/restore_production_db.sh /home/btc-bot/backups/database/btc_bot_latest.db.gz --force"

# 4. Restart bot
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl start btc-bot.service"

# 5. Verify status
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl status btc-bot.service"
```

**Data Loss:** Last backup to corruption time (max 24 hours with daily backups)

---

### 2. Bot Stuck / Not Trading

**Symptoms:**
- Bot running but no new trades
- Safe mode triggered
- Logs show health check failures

**Diagnostic Steps:**

```bash
# 1. Check bot service status
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl status btc-bot.service"

# 2. Check recent logs
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "journalctl -u btc-bot.service -n 100 --no-pager | grep -E 'CRITICAL|ERROR|safe_mode'"

# 3. Check safe mode status
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "python3 /home/btc-bot/btc-bot/scripts/query_bot_status.py --safe-mode"

# 4. Check last decision cycle
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "sqlite3 /home/btc-bot/btc-bot/storage/btc_bot.db \"SELECT timestamp, outcome_group, outcome_reason FROM cycle_outcomes ORDER BY timestamp DESC LIMIT 10;\""
```

**Recovery Steps:**

```bash
# If safe mode is ON, restart bot to trigger recovery coordinator
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl restart btc-bot.service"

# Monitor logs for recovery
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "journalctl -u btc-bot.service -f"
```

**Note:** Recovery coordinator runs on bot startup and reconciles local DB state with exchange state.

---

### 3. Accidental Data Deletion

**Symptoms:**
- Wrong UPDATE/DELETE query executed
- Missing trades or positions
- Data inconsistency detected

**Recovery Steps:**

```bash
# 1. IMMEDIATELY stop bot (prevents further writes)
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl stop btc-bot.service"

# 2. Create safety backup of current (corrupted) state
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "cp /home/btc-bot/btc-bot/storage/btc_bot.db /home/btc-bot/btc-bot/storage/btc_bot.db.before-fix"

# 3. Restore from backup
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "cd /home/btc-bot/btc-bot && ./scripts/restore_production_db.sh /home/btc-bot/backups/database/btc_bot_latest.db.gz --force"

# 4. If recent data lost, download both DBs and merge locally
scp -i btc-bot-deploy-v2 root@204.168.146.253:/home/btc-bot/btc-bot/storage/btc_bot.db.before-fix c:\tmp\corrupted.db
scp -i btc-bot-deploy-v2 root@204.168.146.253:/home/btc-bot/btc-bot/storage/btc_bot.db c:\tmp\restored.db

# Manual merge (advanced):
sqlite3 c:\tmp\restored.db
# > ATTACH DATABASE 'c:\tmp\corrupted.db' AS corrupted;
# > INSERT INTO trade_log SELECT * FROM corrupted.trade_log WHERE opened_at > '2026-04-24T00:00:00Z';
# > DETACH DATABASE corrupted;
```

**Data Loss:** Depends on backup age and merge success

---

### 4. Schema Migration Failure

**Symptoms:**
- Bot fails to start after deployment
- Missing column errors
- FK constraint violations

**Recovery Steps:**

```bash
# 1. Stop bot
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl stop btc-bot.service"

# 2. Check current schema version
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "sqlite3 /home/btc-bot/btc-bot/storage/btc_bot.db \".schema executions\""

# 3. Rollback to previous deployment
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "cd /home/btc-bot/btc-bot && git log -n 5 --oneline"
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "cd /home/btc-bot/btc-bot && git reset --hard <previous_commit>"

# 4. Restart bot
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl start btc-bot.service"
```

**Prevention:** Always run `scripts/smoke_recovery.py` locally before deploying schema changes.

---

### 5. Configuration Drift Detected

**Symptoms:**
- `check_production_drift.sh` reports DRIFT
- Systemd unit file differs between production and repo
- Python version mismatch

**Recovery Steps:**

```bash
# 1. Check what drifted
./scripts/check_production_drift.sh

# 2. If systemd unit drifted, redeploy from repo
scp -i btc-bot-deploy-v2 ops/systemd/btc-bot.service root@204.168.146.253:/etc/systemd/system/
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl daemon-reload && systemctl restart btc-bot.service"

# 3. If Python version drifted, update production
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "pyenv install 3.12.3 && pyenv global 3.12.3"

# 4. Verify drift resolved
./scripts/check_production_drift.sh
```

**Reference:** `docs/ops/SYSTEMD_UNITS.md`

---

### 6. Exchange Position Mismatch

**Symptoms:**
- Recovery coordinator reports `unknown_position` or `phantom_position`
- Local DB shows OPEN position but exchange has no position
- Exchange has position but local DB shows CLOSED

**Recovery Steps:**

```bash
# 1. Bot will trigger safe mode automatically on startup
# 2. Check recovery report in logs
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "journalctl -u btc-bot.service -n 100 | grep -A 5 'RecoveryReport'"

# 3. If unknown_position (exchange has position, DB doesn't):
#    - Manual intervention required
#    - Close position on exchange manually
#    - Restart bot

# 4. If phantom_position (DB has position, exchange doesn't):
#    - Bot will mark position as CLOSED automatically on next restart
#    - Verify via dashboard or query_bot_status.py
```

**Note:** Recovery coordinator is conservative - it enters safe mode rather than making assumptions.

---

## Backup Management

### Create Manual Backup (Before Risky Operation)

```bash
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "/home/btc-bot/btc-bot/scripts/backup_production_db.sh /home/btc-bot/backups/manual/"
```

### Verify Backup Exists

```bash
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "ls -lah /home/btc-bot/backups/database/ | tail -10"
```

### Pull Latest Backup to Local Machine

```bash
scp -i btc-bot-deploy-v2 root@204.168.146.253:/home/btc-bot/backups/database/btc_bot_latest.db.gz c:\development\btc-bot\backups\
gunzip c:\development\btc-bot\backups\btc_bot_latest.db.gz
```

### Test Backup Integrity

```bash
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "gunzip -c /home/btc-bot/backups/database/btc_bot_latest.db.gz | sqlite3 /tmp/test.db 'PRAGMA integrity_check;' && rm /tmp/test.db"
```

---

## Recovery Verification

After any recovery operation:

### 1. Check Bot Health

```bash
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl status btc-bot.service"
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "python3 /home/btc-bot/btc-bot/scripts/query_bot_status.py --summary"
```

### 2. Verify Data Integrity

```bash
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "sqlite3 /home/btc-bot/btc-bot/storage/btc_bot.db 'PRAGMA foreign_key_check;'"
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "sqlite3 /home/btc-bot/btc-bot/storage/btc_bot.db 'PRAGMA integrity_check;'"
```

### 3. Check Recent Activity

```bash
# Last 5 cycle outcomes
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "sqlite3 /home/btc-bot/btc-bot/storage/btc_bot.db \"SELECT timestamp, outcome_group, outcome_reason FROM cycle_outcomes ORDER BY timestamp DESC LIMIT 5;\""

# Last trade
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "sqlite3 /home/btc-bot/btc-bot/storage/btc_bot.db \"SELECT * FROM trade_log ORDER BY opened_at DESC LIMIT 1;\""
```

### 4. Monitor Live Logs

```bash
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "journalctl -u btc-bot.service -f"
```

---

## Escalation

If recovery fails after following these procedures:

1. **Document current state:**
   - Save logs: `journalctl -u btc-bot.service -n 500 > recovery_logs.txt`
   - Export DB schema: `sqlite3 btc_bot.db .schema > schema_dump.sql`
   - List recent backups: `ls -lah /home/btc-bot/backups/database/`

2. **Contact:**
   - Repository: [github.com/lewiercoin/btc-bot/issues](https://github.com/lewiercoin/btc-bot/issues)
   - Email: lewiercoin@gmail.com

3. **Emergency Stop:**
   - If data loss is ongoing, stop bot immediately: `systemctl stop btc-bot.service`
   - Create safety backup before any recovery attempt

---

## Related Documentation

- **Disaster Recovery Plan:** `docs/DISASTER_RECOVERY.md`
- **Systemd Services:** `docs/ops/SYSTEMD_UNITS.md`
- **Database Schema:** `storage/schema.sql`
- **State Reconciliation Audit:** `docs/audits/AUDIT_RECOVERY_SAFE_MODE_STATE_RECONCILIATION_2026-04-24.md`
- **Recovery Smoke Tests:** `scripts/smoke_recovery.py`

---

## Schema Compatibility

**Last verified:** 2026-04-25  
**Schema version:** v1.0  
**Recovery script status:** PASS (smoke_recovery.py)

### Recent Schema Changes

| Date | Change | Migration | Recovery Impact |
|------|--------|-----------|-----------------|
| 2026-04-25 | Added `snapshot_id` to executions | Auto-migration in state_store.py | None (nullable column) |
| 2026-04-19 | Added `funding_paid` to trade_log | Auto-migration in state_store.py | None (default 0.0) |
| 2026-04-24 | Added `governance_notes_json` to executable_signals | Manual migration | Recovery script updated |

**Note:** Recovery scripts (`smoke_recovery.py`) are kept in sync with schema changes and verified before deployment.

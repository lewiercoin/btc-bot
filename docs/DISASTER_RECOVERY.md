# DISASTER RECOVERY PLAN

> **Critical for Experiment v1 and beyond - protect collected data**

## Overview

This document describes backup strategy, disaster recovery procedures, and data protection for the BTC trading bot production environment.

**Server:** `root@204.168.146.253`  
**Critical Data:** `/home/btc-bot/btc-bot/storage/btc_bot.db` (~669MB)

---

## Backup Strategy

### What Gets Backed Up

| Asset | Location | Frequency | Retention |
|-------|----------|-----------|-----------|
| **Production Database** | `/home/btc-bot/btc-bot/storage/btc_bot.db` | Daily | 30 days |
| **Bot Logs** | `/home/btc-bot/btc-bot/logs/` | Weekly | 90 days |
| **Configuration** | Git repository | On change | Infinite |
| **System State** | Deployment snapshots | On deployment | 10 versions |

### Backup Locations

1. **On-server backups:** `/home/btc-bot/backups/database/`
2. **Off-server backups:** Local development machine (manual pull)
3. **Git repository:** Code + docs + configs (not data)

---

## Daily Backup Automation

### Setup Automated Backups

```bash
# On production server as root
ssh root@204.168.146.253

# Install backup script
cd /home/btc-bot/btc-bot
chmod +x scripts/backup_production_db.sh

# Test backup manually
./scripts/backup_production_db.sh

# Setup cron for daily backups (2 AM UTC)
crontab -e

# Add this line:
0 2 * * * /home/btc-bot/btc-bot/scripts/backup_production_db.sh >> /var/log/btc-bot-backup.log 2>&1
```

### Verify Backups

```bash
# List recent backups
ls -lah /home/btc-bot/backups/database/

# Check latest backup
ls -lh /home/btc-bot/backups/database/btc_bot_latest.db.gz

# Verify integrity
gunzip -c /home/btc-bot/backups/database/btc_bot_latest.db.gz | sqlite3 /tmp/test.db "PRAGMA integrity_check;"
rm /tmp/test.db
```

---

## Manual Backup (Before Risky Operations)

```bash
# On server
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
./scripts/backup_production_db.sh /home/btc-bot/backups/manual/
```

**When to run manual backup:**
- Before database schema migrations
- Before major bot upgrades
- Before experiment deployments
- Before parameter changes that affect data integrity

---

## Pull Backup to Local Machine

### One-Time Backup Pull

```bash
# From local machine
scp -i "c:\development\btc-bot\btc-bot-deploy-v2" \
  root@204.168.146.253:/home/btc-bot/backups/database/btc_bot_latest.db.gz \
  c:\development\btc-bot\backups\

# Extract
gunzip c:\development\btc-bot\backups\btc_bot_latest.db.gz
```

### Automated Local Backup Sync (Weekly)

Create `scripts/pull_production_backup.sh` and run weekly:

```bash
#!/bin/bash
# Pull latest production backup to local machine
# Run this weekly for off-server backup

REMOTE="root@204.168.146.253"
KEY="c:\development\btc-bot\btc-bot-deploy-v2"
LOCAL_DIR="c:\development\btc-bot\backups"

mkdir -p "$LOCAL_DIR"

scp -i "$KEY" \
  "$REMOTE:/home/btc-bot/backups/database/btc_bot_latest.db.gz" \
  "$LOCAL_DIR/btc_bot_$(date +%Y%m%d).db.gz"

# Keep only last 4 weekly backups locally
ls -t "$LOCAL_DIR"/btc_bot_*.db.gz | tail -n +5 | xargs -r rm
```

---

## Disaster Recovery Scenarios

### Scenario 1: Server Crash (Total Loss)

**Recovery Steps:**

1. **Spin up new server**
   ```bash
   # Get new VPS with same specs
   # Ubuntu 22.04, 4GB RAM, 80GB disk
   ```

2. **Deploy bot from scratch**
   ```bash
   # Clone repo
   git clone https://github.com/lewiercoin/btc-bot
   cd btc-bot
   
   # Install dependencies
   ./scripts/setup_production.sh
   ```

3. **Restore latest backup**
   ```bash
   # Upload backup from local machine
   scp -i btc-bot-deploy-v2 \
     c:\development\btc-bot\backups\btc_bot_latest.db.gz \
     root@NEW_SERVER:/home/btc-bot/backups/
   
   # SSH to new server
   ssh root@NEW_SERVER
   
   # Stop bot (if running)
   systemctl stop btc-bot.service
   
   # Restore database
   cd /home/btc-bot/btc-bot
   ./scripts/restore_production_db.sh /home/btc-bot/backups/btc_bot_latest.db.gz --force
   
   # Start bot
   systemctl start btc-bot.service
   ```

4. **Verify recovery**
   ```bash
   # Check last trade date
   sqlite3 storage/btc_bot.db "SELECT MAX(opened_at) FROM trade_log;"
   
   # Check bot status
   systemctl status btc-bot.service
   python3 scripts/query_bot_status.py --summary
   ```

**Data Loss:** Last backup to incident time (max 24 hours if daily backups)

---

### Scenario 2: Database Corruption

**Symptoms:**
- SQLite "database disk image is malformed"
- Bot crashes on database operations
- Integrity check fails

**Recovery Steps:**

1. **Stop bot immediately**
   ```bash
   ssh root@204.168.146.253
   systemctl stop btc-bot.service
   ```

2. **Attempt integrity check**
   ```bash
   cd /home/btc-bot/btc-bot
   sqlite3 storage/btc_bot.db "PRAGMA integrity_check;"
   ```

3. **If corrupted, restore from backup**
   ```bash
   # Move corrupted DB
   mv storage/btc_bot.db storage/btc_bot.db.corrupted
   
   # Restore latest backup
   ./scripts/restore_production_db.sh \
     /home/btc-bot/backups/database/btc_bot_latest.db.gz --force
   ```

4. **Restart bot**
   ```bash
   systemctl start btc-bot.service
   ```

**Data Loss:** Last backup to corruption time

---

### Scenario 3: Accidental Data Deletion

**Example:** Accidentally deleted trades, wrong UPDATE query

**Recovery Steps:**

1. **Stop bot immediately**
   ```bash
   systemctl stop btc-bot.service
   ```

2. **Create safety backup of current (corrupted) state**
   ```bash
   cp storage/btc_bot.db storage/btc_bot.db.before-fix
   ```

3. **Restore from backup**
   ```bash
   ./scripts/restore_production_db.sh \
     /home/btc-bot/backups/database/btc_bot_latest.db.gz --force
   ```

4. **If recent data lost, merge from corrupted copy**
   ```bash
   # Attach both databases
   sqlite3 storage/btc_bot.db
   
   ATTACH 'storage/btc_bot.db.before-fix' AS corrupted;
   
   # Copy recent trades (after last backup)
   INSERT INTO trade_log 
   SELECT * FROM corrupted.trade_log 
   WHERE opened_at > (SELECT MAX(opened_at) FROM trade_log);
   
   DETACH corrupted;
   .exit
   ```

5. **Verify and restart**
   ```bash
   sqlite3 storage/btc_bot.db "PRAGMA integrity_check;"
   systemctl start btc-bot.service
   ```

---

### Scenario 4: Experiment v1 Data Loss During Collection

**Critical:** Experiment v1 runs for 14 days (2026-04-20 → 2026-05-04). Losing data means restarting from Day 0.

**Prevention:**

1. **Daily backups MUST be enabled** before Day 1
2. **Manual backup before each risky operation**
3. **Weekly pull to local machine** for off-server copy

**If data lost during experiment:**

1. **Assess data loss extent**
   ```bash
   # Check last trade in backup vs what was expected
   gunzip -c /home/btc-bot/backups/database/btc_bot_latest.db.gz | \
     sqlite3 /tmp/backup.db "SELECT MAX(opened_at) FROM trade_log;"
   ```

2. **Decision matrix:**
   - Lost < 24h of data: Restore backup, continue experiment
   - Lost 24h-72h: Restore backup, note gap in analysis
   - Lost > 72h: Consider restarting experiment (user decision)

3. **Document gap in analysis**
   ```bash
   # Add note to experiment report
   echo "Data gap: [date range] - restored from backup" >> \
     docs/analysis/EXPERIMENT_V1_2026-04-20.md
   ```

---

## Backup Verification

### Daily Verification (Automated)

```bash
# Add to cron after backup (2:30 AM UTC)
30 2 * * * /home/btc-bot/btc-bot/scripts/verify_backup.sh >> /var/log/btc-bot-backup.log 2>&1
```

Create `scripts/verify_backup.sh`:
```bash
#!/bin/bash
LATEST="/home/btc-bot/backups/database/btc_bot_latest.db.gz"

if [[ ! -f "$LATEST" ]]; then
    echo "ERROR: Latest backup not found!"
    exit 1
fi

# Check age (should be < 24 hours)
AGE=$(($(date +%s) - $(stat -c %Y "$LATEST")))
if [[ $AGE -gt 86400 ]]; then
    echo "WARNING: Backup is older than 24 hours!"
fi

# Verify integrity
gunzip -c "$LATEST" | sqlite3 /tmp/verify.db "PRAGMA integrity_check;" || \
    echo "ERROR: Backup integrity check failed!"

rm -f /tmp/verify.db
echo "Backup verification passed: $(date)"
```

### Weekly Manual Verification

```bash
# 1. Check backup size (should be ~100-200MB compressed)
ls -lh /home/btc-bot/backups/database/btc_bot_latest.db.gz

# 2. Verify can decompress
gunzip -t /home/btc-bot/backups/database/btc_bot_latest.db.gz

# 3. Check data freshness
gunzip -c /home/btc-bot/backups/database/btc_bot_latest.db.gz | \
  sqlite3 /tmp/test.db "SELECT MAX(opened_at) FROM trade_log;"

# 4. Count trades
gunzip -c /home/btc-bot/backups/database/btc_bot_latest.db.gz | \
  sqlite3 /tmp/test.db "SELECT COUNT(*) FROM trade_log;"

rm /tmp/test.db
```

---

## Monitoring & Alerts

### Backup Monitoring Checklist

- [ ] Daily backup created (check cron log)
- [ ] Backup size reasonable (~100-200MB compressed)
- [ ] Backup integrity check passes
- [ ] Disk space sufficient (> 10GB free)
- [ ] Weekly pull to local machine completed

### Setup Alerts (Optional)

**Email on backup failure:**
```bash
# Add to backup script
if [[ $? -ne 0 ]]; then
    echo "Backup failed!" | mail -s "BTC Bot Backup FAILED" admin@example.com
fi
```

**Disk space alert:**
```bash
# Add to cron (daily check at 3 AM)
0 3 * * * df -h /home/btc-bot | awk '$5+0 > 80 {print "Disk space low: " $5}'
```

---

## Backup Rotation Policy

| Backup Type | Frequency | Retention | Location |
|-------------|-----------|-----------|----------|
| **Automated daily** | Daily 2 AM UTC | 30 days | `/home/btc-bot/backups/database/` |
| **Pre-deployment** | Before deploy | 10 versions | `/home/btc-bot/deployment-backups/` |
| **Weekly off-server** | Weekly Sunday | 4 weeks | Local machine `c:\development\btc-bot\backups\` |
| **Experiment milestone** | Per experiment | Until analysis done | Separate directory per experiment |

### Disk Space Management

**On server:**
- Database: ~669MB
- Compressed backup: ~100-150MB
- 30 days backups: ~3-4.5GB
- Reserve 10GB for backups

**Local machine:**
- 4 weekly backups × 150MB = ~600MB

---

## Testing Recovery

### Quarterly DR Test

**Every 3 months, run full disaster recovery test:**

1. **Create test environment** (separate VM)
2. **Restore from backup**
3. **Verify bot starts and runs**
4. **Document time to recovery**
5. **Update this document with lessons learned**

### Test Restore on Staging

```bash
# On local machine or staging server
gunzip -c btc_bot_backup.db.gz > /tmp/btc_bot_test.db

# Verify integrity
sqlite3 /tmp/btc_bot_test.db "PRAGMA integrity_check;"

# Check data
sqlite3 /tmp/btc_bot_test.db "SELECT COUNT(*) FROM trade_log;"

# Clean up
rm /tmp/btc_bot_test.db
```

---

## Immediate Action Items

### Setup Checklist (DO NOW for Experiment v1)

- [ ] Deploy backup script to server
- [ ] Enable daily cron backup (2 AM UTC)
- [ ] Create manual backup NOW (before any changes)
- [ ] Test restore on staging/local
- [ ] Pull first backup to local machine
- [ ] Setup weekly local pull reminder
- [ ] Document this in milestone tracker

### Commands to Run

```bash
# 1. Deploy scripts
scp -i "c:\development\btc-bot\btc-bot-deploy-v2" \
  scripts/backup_production_db.sh \
  scripts/restore_production_db.sh \
  root@204.168.146.253:/home/btc-bot/btc-bot/scripts/

# 2. SSH to server
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253

# 3. Make executable
chmod +x /home/btc-bot/btc-bot/scripts/backup_production_db.sh
chmod +x /home/btc-bot/btc-bot/scripts/restore_production_db.sh

# 4. Run first backup
/home/btc-bot/btc-bot/scripts/backup_production_db.sh

# 5. Setup cron
crontab -e
# Add: 0 2 * * * /home/btc-bot/btc-bot/scripts/backup_production_db.sh >> /var/log/btc-bot-backup.log 2>&1

# 6. Exit and pull backup locally
exit
scp -i "c:\development\btc-bot\btc-bot-deploy-v2" \
  root@204.168.146.253:/home/btc-bot/backups/database/btc_bot_latest.db.gz \
  c:\development\btc-bot\backups\
```

---

## Contact & Escalation

**In case of disaster:**
1. Stop bot immediately
2. Assess data loss extent
3. Follow recovery procedure for scenario
4. Document incident in `docs/incidents/`
5. Update DR plan with lessons learned

**Recovery Time Objective (RTO):** < 2 hours  
**Recovery Point Objective (RPO):** < 24 hours (daily backups)

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-04-20 | Initial DR plan created | Claude Code |
| 2026-04-20 | Backup/restore scripts created | Claude Code |

---

## References

- `scripts/backup_production_db.sh` - Automated backup script
- `scripts/restore_production_db.sh` - Restore script
- `scripts/query_bot_status.py` - Status verification tool
- `docs/DATA_SOURCES.md` - Data source reference
# Production Deploy: Observability Runtime vs DB

Date: 2026-04-18  
Target: root@204.168.146.253  
Commits: fb69b7e (checkpoint 1), 61e8dd9 (checkpoint 2)

---

## Pre-Deploy State

**Server commit:** d9e2379 (before observability)  
**Target commit:** 6d851ca (observability milestone DONE)  
**Gap:** 118 commits

**Services:**
- `btc-bot.service` - running, PAPER mode, uptime 11h
- `btc-bot-dashboard.service` - running (dashboard on port 8080)

**Risk:** Low - checkpoint 1+2 are observability only, zero trading logic changes

---

## Deployment Steps

### 1. Pull Latest Code

```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git fetch origin
git log --oneline HEAD..origin/main | head -10  # Preview changes
git pull origin main
```

**Expected:** Fast-forward to 6d851ca

---

### 2. Verify Database Schema

```bash
cd /home/btc-bot/btc-bot
python3 -c "
import sqlite3
conn = sqlite3.connect('storage/btc_bot.db')
cursor = conn.cursor()

# Check if runtime_metrics table exists
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='runtime_metrics'\")
if cursor.fetchone():
    print('✓ runtime_metrics table already exists')
else:
    print('✗ runtime_metrics table missing - will be created on bot start')

conn.close()
"
```

**Note:** `StateStore._apply_migrations()` creates table on first bot start if missing.

---

### 3. Restart Bot Service

```bash
# Check current status
systemctl status btc-bot --no-pager | head -5

# Restart (PAPER mode, safe)
systemctl restart btc-bot

# Verify restart
sleep 3
systemctl status btc-bot --no-pager | head -10
```

**Expected:**
```
Active: active (running) since <timestamp>
Main PID: <new_pid>
```

---

### 4. Restart Dashboard Service

```bash
# Check current status
ps aux | grep uvicorn | grep dashboard

# Restart dashboard
systemctl restart btc-bot-dashboard || {
  # If no systemd service, kill + restart manually
  pkill -f "uvicorn dashboard.server"
  cd /home/btc-bot/btc-bot
  nohup .venv/bin/uvicorn dashboard.server:app --host 0.0.0.0 --port 8080 &
}

# Verify dashboard responds
sleep 2
curl -s http://localhost:8080/api/status | jq '.mode'
```

**Expected:** `"PAPER"`

---

## Smoke Validation

### 5. Verify runtime_metrics Table Created

```bash
cd /home/btc-bot/btc-bot
python3 -c "
import sqlite3
conn = sqlite3.connect('storage/btc_bot.db')
cursor = conn.cursor()

# Check table exists
cursor.execute('SELECT sql FROM sqlite_master WHERE type=\"table\" AND name=\"runtime_metrics\"')
schema = cursor.fetchone()
if schema:
    print('✓ runtime_metrics table exists')
    print()
    cursor.execute('SELECT * FROM runtime_metrics WHERE id=1')
    row = cursor.fetchone()
    if row:
        print('✓ runtime_metrics row populated')
        # Get column names
        cursor.execute('PRAGMA table_info(runtime_metrics)')
        cols = [col[1] for col in cursor.fetchall()]
        print(f'  Columns: {len(cols)}')
        print(f'  Updated at: {dict(zip(cols, row)).get(\"updated_at\", \"N/A\")}')
    else:
        print('✗ runtime_metrics row not yet populated (wait for decision cycle)')
else:
    print('✗ runtime_metrics table missing - check bot logs for migration errors')

conn.close()
"
```

---

### 6. Wait for Next Decision Cycle

Decision cycles run every 15 minutes at :00, :15, :30, :45.

```bash
# Watch logs for next cycle
journalctl -u btc-bot -f --no-pager | grep -E 'Decision cycle|Decision diagnostics|runtime_metrics'
```

**Expected output (checkpoint 1):**
```
Decision cycle started | timestamp=2026-04-18T07:00:00+00:00
Decision diagnostics | timestamp=... | outcome=no_signal | blocked_by=... | sweep_detected=... | reclaim_detected=...
Decision cycle finished | timestamp=... | outcome=no_signal | duration_ms=...
```

**Expected output (checkpoint 2):**
- No explicit "runtime_metrics" log (best-effort silent write)
- Check via validation query below

---

### 7. Verify runtime_metrics Updated

After one decision cycle completes:

```bash
cd /home/btc-bot/btc-bot
python3 -c "
import sqlite3
from datetime import datetime, timezone
conn = sqlite3.connect('storage/btc_bot.db')
cursor = conn.cursor()

cursor.execute('SELECT * FROM runtime_metrics WHERE id=1')
row = cursor.fetchone()

if not row:
    print('✗ runtime_metrics not populated')
else:
    cursor.execute('PRAGMA table_info(runtime_metrics)')
    cols = [col[1] for col in cursor.fetchall()]
    data = dict(zip(cols, row))
    
    print('✓ runtime_metrics populated')
    print(f'  Last cycle started: {data.get(\"last_decision_cycle_started_at\", \"N/A\")}')
    print(f'  Last cycle finished: {data.get(\"last_decision_cycle_finished_at\", \"N/A\")}')
    print(f'  Last outcome: {data.get(\"last_decision_outcome\", \"N/A\")}')
    print(f'  Cycle status: {data.get(\"decision_cycle_status\", \"N/A\")}')
    print(f'  Last snapshot: {data.get(\"last_snapshot_built_at\", \"N/A\")}')
    print(f'  15m candle: {data.get(\"last_15m_candle_open_at\", \"N/A\")}')
    print(f'  Websocket: {data.get(\"last_ws_message_at\", \"N/A\")}')
    print(f'  Config hash: {data.get(\"config_hash\", \"N/A\")[:12]}...')

conn.close()
"
```

**Expected:** All fields populated with recent timestamps.

---

### 8. Verify /api/runtime-freshness Endpoint

```bash
curl -s http://localhost:8080/api/runtime-freshness | jq '.'
```

**Expected response:**
```json
{
  "runtime_available": true,
  "updated_at": "2026-04-18T07:00:01+00:00",
  "config_hash": "e8c7180d829d...",
  "decision_cycle": {
    "status": "idle",
    "last_started_at": "2026-04-18T07:00:00+00:00",
    "last_finished_at": "2026-04-18T07:00:01+00:00",
    "last_outcome": "no_signal",
    "last_snapshot_age_seconds": 15
  },
  "rest_snapshot": {
    "built_at": "2026-04-18T07:00:00+00:00",
    "symbol": "BTCUSDT",
    "timeframes": {
      "15m": {
        "last_candle_open_at": "2026-04-18T06:45:00+00:00",
        "age_seconds": 900
      },
      "1h": {...},
      "4h": {...}
    }
  },
  "websocket": {
    "last_message_at": "2026-04-18T06:59:58+00:00",
    "message_age_seconds": 2,
    "healthy": true
  },
  "collector": null
}
```

---

### 9. Verify Dashboard Runtime Panel

Visit: `http://204.168.146.253:8080/`

**Check:**
- New "Runtime Data" panel exists
- Shows:
  - Process: running
  - Decision cycle: idle / running
  - Last outcome: no_signal (with reason if checkpoint 1 logs visible)
  - Snapshot age: <30s
  - Websocket: healthy

**Note:** Dashboard auto-refreshes every 10s.

---

### 10. Check for Structured Diagnostics in Logs

```bash
journalctl -u btc-bot --since '10 minutes ago' --no-pager | grep 'Decision diagnostics'
```

**Expected (checkpoint 1):**
```
Decision diagnostics | timestamp=... | outcome=no_signal | blocked_by=no_reclaim | 
  sweep_detected=false | reclaim_detected=false | direction_inferred=null | regime=NORMAL
```

**If no diagnostics line:** Wait for next `no_signal` cycle (happens every 15 min currently).

---

## Rollback Plan

If smoke validation fails:

```bash
cd /home/btc-bot/btc-bot
git reset --hard d9e2379  # Revert to pre-observability commit
systemctl restart btc-bot
systemctl restart btc-bot-dashboard  # or kill + restart manually
```

**Note:** `runtime_metrics` table remains in DB (safe, ignored by old code).

---

## Success Criteria

- [✓] Bot restarted successfully
- [✓] Dashboard restarted successfully
- [✓] `runtime_metrics` table created
- [✓] `runtime_metrics` populated after decision cycle
- [✓] `/api/runtime-freshness` returns expected schema
- [✓] Dashboard "Runtime Data" panel visible
- [✓] Structured diagnostics in logs (checkpoint 1)
- [✓] No errors in journalctl

---

## Post-Deploy

After successful smoke validation:

1. Monitor for 1 hour - verify no unexpected errors
2. Check dashboard shows runtime freshness correctly
3. Verify `no_signal` cycles include `blocked_by` reason
4. Return to RUN14 uptrend continuation bug investigation

---

## Monitoring Commands

**Watch decision cycles:**
```bash
journalctl -u btc-bot -f --no-pager | grep -E 'Decision cycle|Decision diagnostics'
```

**Watch runtime_metrics updates:**
```bash
watch -n 10 'sqlite3 /home/btc-bot/btc-bot/storage/btc_bot.db "SELECT last_decision_cycle_finished_at, last_decision_outcome, decision_cycle_status FROM runtime_metrics WHERE id=1"'
```

**Dashboard health:**
```bash
curl -s http://localhost:8080/api/runtime-freshness | jq '.decision_cycle.status'
```

# DATA_SOURCES.md - Where to Find What

> **Quick reference for Claude Code, Cascade, and Codex when querying bot data**

## Critical Rule

**Runtime bot data (trades, status, signals) lives on PRODUCTION SERVER, not in local repository files.**

Local `storage/btc_bot.db` is NOT synchronized with production. Querying local files will give you stale data.

---

## Data Source Map

| What You Need | Where It Lives | How to Access |
|---------------|----------------|---------------|
| **Current bot status** | Server: `storage/btc_bot.db` → `bot_state` | `scripts/query_bot_status.py --summary` |
| **Recent trades** | Server: `storage/btc_bot.db` → `trade_log` | `scripts/query_bot_status.py --trades N` |
| **Open positions** | Server: `storage/btc_bot.db` → `positions` | `scripts/query_bot_status.py --summary` |
| **Signal history** | Server: `storage/btc_bot.db` → `signal_candidates` | `scripts/query_bot_status.py --signals N` |
| **Alerts/errors** | Server: `storage/btc_bot.db` → `alerts_errors` | `scripts/query_bot_status.py --alerts N` |
| **Daily metrics** | Server: `storage/btc_bot.db` → `daily_metrics` | `scripts/query_bot_status.py --summary` |
| **Decision diagnostics** | Server: `logs/btc_bot.log` (text) | SSH + `tail -100 logs/btc_bot.log` |
| **Code/architecture** | Local: `c:\development\btc-bot\` | Direct file read |
| **Blueprints** | Local: `docs/BLUEPRINT_*.md` | Direct file read |
| **Milestones** | Local: `docs/MILESTONE_TRACKER.md` | Direct file read |
| **Audits** | Local: `docs/audits/` | Direct file read |

---

## Standard Queries

### 1. Quick Bot Status Check

```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 \
  "cd /home/btc-bot/btc-bot && python3 scripts/query_bot_status.py --summary"
```

**Returns:**
- Bot state (mode, health, safe mode, open positions)
- Last 5 trades with P&L
- Last 7 days metrics

### 2. Recent Trades Detail

```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 \
  "cd /home/btc-bot/btc-bot && python3 scripts/query_bot_status.py --trades 10 --json"
```

### 3. Recent Signals (Promoted + Blocked)

```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 \
  "cd /home/btc-bot/btc-bot && python3 scripts/query_bot_status.py --signals 20"
```

### 4. Direct SQL Query (Advanced)

```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 \
  "cd /home/btc-bot/btc-bot && python3 -c \"
import sqlite3, json
conn = sqlite3.connect('storage/btc_bot.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM trade_log WHERE date(opened_at) >= date(\"now\", \"-7 days\") ORDER BY opened_at DESC')
cols = [d[0] for d in cursor.description]
for row in cursor.fetchall():
    print(json.dumps(dict(zip(cols, row)), indent=2, default=str))
\""
```

---

## Database Schema Reference

### Key Tables in `storage/btc_bot.db`

#### `bot_state`
Current bot runtime state.

Columns:
- `timestamp`, `mode`, `healthy`, `safe_mode`
- `open_positions_count`, `consecutive_losses`
- `daily_dd_pct`, `weekly_dd_pct`
- `last_trade_at`, `safe_mode_entry_at`

#### `trade_log`
Complete trade history.

Columns:
- `trade_id`, `signal_id`, `position_id`
- `opened_at`, `closed_at`
- `direction`, `regime`, `confluence_score`
- `entry_price`, `exit_price`, `size`
- `pnl_abs`, `pnl_r`
- `mae`, `mfe`, `exit_reason`
- `features_at_entry_json`

#### `signal_candidates`
All signals (promoted + blocked).

Columns:
- `signal_id`, `timestamp`
- `direction`, `promoted`
- `regime`, `confluence_score`
- `entry_price`, `rr_ratio`
- `block_reason` (NULL if promoted)

#### `positions`
Open positions tracking.

Columns:
- `position_id`, `signal_id`
- `opened_at`, `direction`
- `entry_price`, `size`
- `stop_loss`, `take_profit_1`
- `status` (OPEN/CLOSED)

#### `alerts_errors`
Dashboard alerts and errors.

Columns:
- `timestamp`, `type`, `severity`
- `component`, `message`
- `payload_json`

#### `daily_metrics`
Daily performance summary.

Columns:
- `date`
- `trades_count`, `wins`, `losses`
- `pnl_abs`, `pnl_r_sum`
- `expectancy_r`, `daily_dd_pct`

---

## What NOT to Do

### ❌ WRONG: Query Local Files

```bash
# These give STALE DATA (days/weeks old)
python3 -c "import sqlite3; conn = sqlite3.connect('storage/btc_bot.db'); ..."
cat logs/btc_bot.log | grep trade
ls -la storage/
```

**Why wrong:** Local repository is a development workspace. It's not synchronized with production server.

### ❌ WRONG: Grep Text Logs for Trades

```bash
grep 'trade_opened' logs/btc_bot.log  # Won't find anything
grep 'PnL' logs/btc_bot.log           # Incomplete data
```

**Why wrong:** Trade details are stored in SQLite database, not text logs. Text logs only have high-level decision diagnostics.

---

## Architecture: Logging & Persistence

```
Bot Runtime
    ↓
orchestrator.py
    ↓
    ├─→ logs/btc_bot.log (text)
    │   └─ Decision diagnostics
    │   └─ High-level events
    │   └─ Errors/warnings
    │
    └─→ storage/btc_bot.db (SQLite)
        ├─ trade_log (complete trade records)
        ├─ signal_candidates (all signals)
        ├─ positions (position tracking)
        ├─ alerts_errors (dashboard alerts)
        ├─ bot_state (runtime state)
        └─ daily_metrics (performance stats)
```

**Dashboard reads from:** `storage/btc_bot.db` (SQLite)  
**You should read from:** `storage/btc_bot.db` (SQLite) **ON SERVER**

---

## Common Mistakes

### Mistake 1: "Bot is not running"

**Wrong:**
```bash
ps aux | grep python  # Checked local machine
```

**Right:**
```bash
ssh root@204.168.146.253 "systemctl status btc-bot.service"
ssh root@204.168.146.253 "ps aux | grep python"
```

### Mistake 2: "Last trade was 3 weeks ago"

**Wrong:**
```python
# Queried local storage/btc_bot.db
conn = sqlite3.connect('storage/btc_bot.db')  # ❌ Local file
```

**Right:**
```bash
# Query server database
ssh root@204.168.146.253 "cd /home/btc-bot/btc-bot && python3 scripts/query_bot_status.py --trades 10"
```

### Mistake 3: "No trades in logs"

**Wrong:**
```bash
grep 'Trade opened' logs/btc_bot.log  # ❌ Text logs don't have this
```

**Right:**
```bash
# Query database alerts_errors table
ssh root@204.168.146.253 "cd /home/btc-bot/btc-bot && python3 scripts/query_bot_status.py --alerts 20"
```

---

## Verification Checklist

Before reporting bot status to user:

- [ ] **Data queried from production server?** (not local files)
- [ ] **Used `scripts/query_bot_status.py` or direct server SQL?**
- [ ] **Checked actual timestamp to verify data freshness?**
- [ ] **Avoided grep on text logs for structured data?**

If you're not 100% sure your data is current, **say so explicitly** to the user.

---

## SSH Connection Details

**Server:** `root@204.168.146.253`  
**SSH Key:** `c:\development\btc-bot\btc-bot-deploy-v2`  
**Bot Directory:** `/home/btc-bot/btc-bot`  
**Database:** `/home/btc-bot/btc-bot/storage/btc_bot.db`  
**Logs:** `/home/btc-bot/btc-bot/logs/btc_bot.log`

---

## Incident Log

### 2026-04-20: Stale Data Incident

**What happened:**
- Cascade reported bot as "not running", last trade "2026-03-29", safe mode "ACTIVE"
- Reality: Bot was running (PID 300113), had fresh trade "2026-04-20 11:15 UTC" (+134.56 WIN), safe mode OFF

**Root cause:**
- Cascade queried local `c:\development\btc-bot\storage\btc_bot.db`
- Local file was 21 days stale
- Should have queried server `/home/btc-bot/btc-bot/storage/btc_bot.db`

**Fix:**
- Updated CASCADE.md with "Runtime Bot Data Source" section
- Created this DATA_SOURCES.md reference
- Created feedback memory: `feedback_bot_data_source.md`
- Created query helper: `scripts/query_bot_status.py`

**Lesson:** Runtime bot data ALWAYS lives on production server. Local files are for code/docs only, not for runtime state.
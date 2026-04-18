# Backlog: DB Collector Automation

Status: **DEFERRED**  
Priority: Low  
Origin: Observability Milestone Checkpoint 3 (deferred 2026-04-18)

---

## Context

The observability milestone (checkpoints 1+2) solved the false websocket alarm by separating runtime data freshness (live) from DB collector freshness (historical). 

Current state:
- ✅ Bot uses fresh REST snapshots for trading decisions
- ✅ Dashboard shows runtime freshness (live websocket + snapshot ages)
- ⏸️ SQLite `candles` table refreshed manually via `scripts/refresh_candles.py`

Checkpoint 3 (DB Collector Automation) was planned but deferred because:
- Not critical for trading correctness
- Adds operational complexity (systemd timer, collector state, failure modes)
- Manual refresh acceptable for current operator workflow

---

## Problem Statement

**Current workflow:**
```bash
# Operator must manually refresh SQLite candles for dashboard/research
ssh root@server
cd /home/btc-bot/btc-bot
python scripts/refresh_candles.py --symbol BTCUSDT --timeframes 15m 1h 4h
```

**Pain points:**
- Manual process (operator forgets → stale dashboard data)
- No health tracking (collector failures invisible)
- Dashboard shows stale historical candles (confusing, but not critical)

**Impact:** Low - dashboard historical views stale, but runtime trading unaffected.

---

## Proposed Solution

Implement Checkpoint 3 from `docs/plans/OBSERVABILITY_RUNTIME_VS_DB.md` (lines 317-415).

### Components

#### 1. Systemd Timer + Service

**Files:**
- `/etc/systemd/system/btc-bot-candles-collector.service`
- `/etc/systemd/system/btc-bot-candles-collector.timer`

**Cadence:** Hourly (adjustable)

**Invocation:**
```bash
ExecStart=/home/btc-bot/btc-bot/.venv/bin/python /home/btc-bot/btc-bot/scripts/refresh_candles.py --symbol BTCUSDT --timeframes 15m 1h 4h
```

**Isolation:**
- Separate log: `/var/log/btc-bot-collector.log`
- Failures don't affect `btc-bot.service` (trading loop)

#### 2. Collector State Tracking

**DB Table:**
```sql
CREATE TABLE IF NOT EXISTS collector_state (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    collector_name TEXT NOT NULL,
    last_started_at TEXT,
    last_finished_at TEXT,
    last_success_at TEXT,
    last_status TEXT,
    last_error TEXT,
    timeframes TEXT,
    symbol TEXT,
    updated_at TEXT NOT NULL
);
```

**Writer:** `scripts/refresh_candles.py` upserts state on start/finish

#### 3. Dashboard Integration

**Extend `GET /api/runtime-freshness`:**
```json
{
  "runtime_available": true,
  "decision_cycle": {...},
  "rest_snapshot": {...},
  "websocket": {...},
  "collector": {
    "configured": true,
    "last_success_at": "2026-04-18T09:00:03+00:00",
    "last_run_age_minutes": 45,
    "last_status": "success",
    "warning": null
  }
}
```

**Frontend:** "DB Collector" panel (separate from "Runtime Data")
- Shows: `DB Collector: OK / Warning / Failed`
- Clarifies: "Failure does not affect live runtime"

---

## Acceptance Criteria

- [ ] Systemd timer runs hourly, refreshes 15m/1h/4h candles
- [ ] Collector failures logged to separate file
- [ ] `collector_state` table tracks health
- [ ] Dashboard shows "DB Collector" status (separate from runtime)
- [ ] Collector failure does NOT trigger bot safe_mode
- [ ] Smoke test: manual timer trigger → SQLite candles refreshed

---

## Effort Estimate

**Implementation:** Medium (2-3 hours)
- Systemd unit files (20 min)
- `collector_state` table + upsert logic (30 min)
- Dashboard endpoint extension (30 min)
- Frontend "DB Collector" panel (45 min)
- Tests (45 min)

**Deployment:** Low (10 min)
- Deploy systemd units
- Enable + start timer
- No bot restart required

**Risk:** Low
- Isolated from trading critical path
- Rollback: stop timer, leave tables in place

---

## When to Pull Forward

Pull from backlog when **any** of these is true:

1. **Operator pain:** Manual refresh becomes daily toil (>5 min/day wasted)
2. **Research blocker:** Stale SQLite candles block research/analysis workflows
3. **Production SLO:** Collector health becomes monitored metric
4. **Dashboard UX:** Users confused by stale historical data despite fresh runtime

**Current priority:** Low - none of above conditions met.

---

## Alternative Solutions

### Option A: Cron Job (simpler than systemd)
```bash
# /etc/cron.d/btc-bot-candles
0 * * * * btc-bot /home/btc-bot/btc-bot/.venv/bin/python /home/btc-bot/btc-bot/scripts/refresh_candles.py >> /var/log/btc-bot-collector.log 2>&1
```

**Pros:** Simpler, no systemd dependency  
**Cons:** No health tracking, no dashboard integration

### Option B: In-Process Background Thread
Run collector as background thread inside `orchestrator.py`.

**Pros:** No separate service  
**Cons:** Couples collector to bot lifecycle, harder to debug failures

### Option C: Dashboard Reads REST API Directly
Dashboard fetches candles from Binance REST on demand (no SQLite cache).

**Pros:** No collector needed, always fresh  
**Cons:** Rate limits, slower dashboard load, external dependency

**Recommended:** Option A (cron) for quick win, full checkpoint 3 for production-grade solution.

---

## References

- Plan: `docs/plans/OBSERVABILITY_RUNTIME_VS_DB.md` (lines 317-415)
- Milestone Closure: `docs/MILESTONE_CLOSURE_OBSERVABILITY_2026-04-18.md`
- Existing Script: `scripts/refresh_candles.py`

---

## Backlog Metadata

- **Created:** 2026-04-18
- **Priority:** Low
- **Effort:** Medium
- **Dependencies:** None
- **Blocked By:** None
- **Blocks:** None

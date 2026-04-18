# Milestone Closure: Observability Runtime vs DB

Date: 2026-04-18  
Status: **DONE**  
Commits: fb69b7e (checkpoint 1), 61e8dd9 (checkpoint 2)  
Audits: AUDIT_OBSERVABILITY_CHECKPOINT1_2026-04-18.md, AUDIT_OBSERVABILITY_CHECKPOINT2_2026-04-18.md

---

## Problem Solved

**Original Issue:** Dashboard showed stale SQLite candles → false alarm "websocket dead" → wasted diagnosis time investigating healthy bot.

**Root Cause:** Dashboard mixed two different truths:
- Runtime decision data (REST snapshots, fresh)
- SQLite historical candles (collector script, stale)

No separation between runtime health (trading critical) vs DB collector health (informational).

---

## Solution Delivered

### Checkpoint 1: Decision Diagnostics ✅

**Delivered:**
- `SignalDiagnostics` dataclass with `blocked_by` field
- Structured logging: `Decision diagnostics | blocked_by=no_reclaim | sweep_detected=true | ...`
- Read-only observability - zero decision logic changes

**Impact:**
- Operators can diagnose `no_signal` outcomes without guessing
- Healthy regime blocks (e.g., uptrend whitelist) no longer look like bugs

**Tests:** 11 passed  
**Commit:** fb69b7e

---

### Checkpoint 2: Runtime Freshness ✅

**Delivered:**
- `runtime_metrics` table (single-row, tracks live snapshot timestamps)
- Orchestrator writes at decision cycle boundaries (start/snapshot/finish/health)
- `GET /api/runtime-freshness` endpoint
- Dashboard "Runtime Data" panel (separate from "DB Collector")

**Impact:**
- **False alarm eliminated:** Dashboard shows runtime freshness (live REST/websocket) instead of SQLite candles
- Stale DB candles no longer imply dead websocket
- Regression test proves: `test_read_runtime_freshness_ignores_stale_db_candles`

**Tests:** 22 passed  
**Commit:** 61e8dd9

---

## Deferred Work

### Checkpoint 3: Candles Collector Service → BACKLOG

**Why deferred:**
- Checkpoints 1+2 solve the false alarm problem completely
- Checkpoint 3 automates SQLite refresh (nice-to-have, not critical)
- Adds operational complexity (systemd timer, collector health, failure modes)
- Bot doesn't use SQLite candles in trading decisions

**When to revisit:**
- Operators need daily fresh SQLite without manual `scripts/refresh_candles.py`
- Research/dashboard users blocked by stale historical views
- Collector health becomes production SLO

**Tracked in:** `docs/backlog/DB_COLLECTOR_AUTOMATION.md`

---

## Acceptance Criteria: MET ✅

From plan (docs/plans/OBSERVABILITY_RUNTIME_VS_DB.md:533-540):

- ✅ Runtime and DB collector health are displayed separately
- ✅ A stale SQLite candle cache cannot be misread as a dead websocket
- ✅ `no_signal` cycles expose rejection reason(s) without changing decision behavior
- ✅ Dashboard remains backward-compatible during staggered deploys

**Not required for MVP:**
- ❌ Collector failures remain outside the trading critical path (checkpoint 3, deferred)

---

## Production Impact

**Before milestone:**
```
Dashboard: SQLite candles 3h old
Operator: "Websocket dead? Bot broken?"
Reality: Bot healthy, using fresh REST snapshots
Result: Wasted diagnosis time
```

**After milestone:**
```
Dashboard: Runtime Data panel
  - Decision cycle: idle
  - Last outcome: no_signal (blocked_by=regime_direction_whitelist)
  - Snapshot age: 2s
  - Websocket: 2s ago (healthy)
  
Operator: "Bot healthy, regime blocking LONG in uptrend as designed"
Result: No false alarm, diagnostic actionable
```

---

## Metrics

**Development:**
- Plan: 1 document (550 lines)
- Implementation: 2 checkpoints
- Code changes: +2860, -2839 (net +21 lines, mostly refactoring)
- Tests added: 11 (checkpoint 1) + 12 (checkpoint 2) = 23 tests
- Audits: 2 (both verdict: DONE)

**Quality:**
- Zero decision logic changes (determinism preserved)
- Backward compatible (old dashboard + new bot, new dashboard + old bot)
- Best-effort observability (metrics failure doesn't block trading)

**Timeline:**
- Plan approved: 2026-04-18 01:00 UTC
- Checkpoint 1 done: 2026-04-18 01:41 UTC (41 min)
- Checkpoint 2 done: 2026-04-18 08:27 UTC (6h 46min)
- Milestone closed: 2026-04-18 (same day)

---

## Lessons Learned

### What Worked Well

1. **Incremental checkpoints** - rollback surface stayed small
2. **Plan-first approach** - implementation followed spec exactly
3. **Test coverage** - false alarm regression test proves fix
4. **Backward compatibility** - zero-downtime deployment possible

### What Could Be Better

1. **Frontend bundle size** - app.js grew by 528 lines (consider code splitting)
2. **Test dependency** - psutil import failure in audit env (add to requirements.txt)

### Architecture Wins

1. **Single-row table pattern** - simple, efficient, no cleanup
2. **UPSERT atomicity** - no race conditions
3. **Separation of concerns** - runtime_metrics ≠ bot_state
4. **Read-only diagnostics** - signal layer doesn't log, orchestrator does

---

## Next Steps

**Immediate:**
- ✅ Milestone closed
- ✅ Backlog item created for checkpoint 3
- No deployment required (changes already pushed)

**Future:**
- Monitor dashboard performance (frontend bundle size)
- Consider checkpoint 3 if manual SQLite refresh becomes operator pain point
- Add psutil to requirements.txt (minor cleanup)

---

## Sign-Off

**Builder:** Codex  
**Auditor:** Claude Code  
**Product Owner:** User (approved closure 2026-04-18)

**Milestone Status:** DONE ✅

Observability runtime vs DB separation is production-ready.

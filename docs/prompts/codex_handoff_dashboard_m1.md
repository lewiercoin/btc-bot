## CLAUDE HANDOFF -> CODEX

### Checkpoint
- Last commit: `6592376` (`docs: record v1.0-baseline tag in MILESTONE_TRACKER`)
- Branch: `main`
- Working tree: clean

### Before you code
Read these files (mandatory):
1. `docs/BLUEPRINT_V1.md` — bot architecture, layer separation rules
2. `AGENTS.md` — discipline + workflow rules
3. `docs/MILESTONE_TRACKER.md` — current status (DASHBOARD-M1 ACTIVE)
4. `storage/db.py` — current SQLite connection helper (no WAL today)
5. `storage/repositories.py` — `get_bot_state`, `fetch_open_positions`, `fetch_recent_closed_trade_outcomes`
6. `main.py` — log file path: `settings.storage.logs_dir / "btc_bot.log"`
7. `settings.py` — `StorageSettings.db_path`, `StorageSettings.logs_dir`

---

### Milestone: DASHBOARD-M1 — Read-Only Observability + WAL Patch

**Two sub-scopes delivered together:**

#### M2: WAL Patch (prerequisite, small)
- `storage/db.py` — add `PRAGMA journal_mode=WAL;` in `connect()` after existing PRAGMAs
- `storage/db.py` — add helper `connect_readonly(db_path: Path) -> sqlite3.Connection` using URI `?mode=ro` (does NOT init WAL, assumes WAL already set by the main process)
  - URI form: `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, detect_types=sqlite3.PARSE_DECLTYPES)`
  - `row_factory = sqlite3.Row` same as `connect()`
  - No `foreign_keys` pragma needed (read-only)
- No other changes to `storage/db.py`

#### M1: FastAPI Dashboard — Read-Only Observability

**What this milestone IS:**
- Read-only observability panel
- Status from persisted `bot_state` table
- Open positions + recent trades from DB
- Log tail via SSE (Server-Sent Events)
- Bind `127.0.0.1:8080` only

**What this milestone IS NOT:**
- No bot start/stop (M3)
- No terminal (M5)
- No backtest/research job runner (M4)
- No hot config editing
- No authentication (local-only, 127.0.0.1 bind is the boundary)

---

### Deliverables

1. **`storage/db.py`** — WAL pragma in `connect()` + `connect_readonly()` helper
2. **`dashboard/__init__.py`** — empty, marks package
3. **`dashboard/db_reader.py`** — read-only DB queries using `connect_readonly()`
4. **`dashboard/log_streamer.py`** — async SSE tail on `btc_bot.log`
5. **`dashboard/server.py`** — FastAPI app, bind 127.0.0.1:8080
6. **`dashboard/static/index.html`** — single-page dashboard UI
7. **`dashboard/static/app.js`** — polling + SSE client
8. **`dashboard/static/style.css`** — minimal styling
9. **`scripts/run_dashboard.py`** — entrypoint: `uvicorn dashboard.server:app --host 127.0.0.1 --port 8080`
10. **`tests/test_dashboard_db_reader.py`** — unit tests for `db_reader.py` (in-memory SQLite)
11. **`tests/test_dashboard_wal.py`** — smoke: WAL pragma is set after `connect()`

---

### API contracts

All endpoints are read-only. No POST, no mutations.

```
GET /api/status
Response: {
  "bot_state": {                  ← from bot_state table, null if no row
    "mode": "PAPER" | "LIVE",
    "healthy": bool,
    "safe_mode": bool,
    "safe_mode_reason": str | null,   ← last_error field from bot_state
    "open_positions_count": int,
    "consecutive_losses": int,
    "daily_dd_pct": float,
    "weekly_dd_pct": float,
    "last_trade_at": ISO8601 | null,
    "state_timestamp": ISO8601 | null  ← timestamp column from bot_state
  } | null,
  "uptime_seconds": null,           ← always null in M1 (no process tracking yet)
  "dashboard_version": "m1"
}

GET /api/positions
Response: {
  "positions": [
    {
      "position_id": str,
      "direction": "LONG" | "SHORT",
      "entry_price": float,
      "size": float,
      "stop_loss": float | null,
      "take_profit_1": float | null,
      "status": "OPEN" | "PARTIAL",
      "opened_at": ISO8601
    }
  ],
  "data_age_seconds": float   ← seconds since most recent opened_at, or null
}

GET /api/trades?limit=50
Response: {
  "trades": [
    {
      "trade_id": str,
      "direction": str,
      "entry_price": float,
      "exit_price": float | null,
      "pnl_abs": float | null,
      "pnl_r": float | null,
      "outcome": str | null,
      "closed_at": ISO8601 | null
    }
  ]
}

GET /api/logs/stream
Content-Type: text/event-stream (SSE)
- Sends last 100 lines on connect
- Tails file for new lines, sends each as SSE event
- Each event: data: {"line": "...", "ts": ISO8601}
- Reconnect-friendly (client uses EventSource)
```

---

### UI layout (single page)

```
┌─────────────────────────────────────────────────────────┐
│  BTC Bot Dashboard  [status badge]                       │
├──────────────────────┬──────────────────────────────────┤
│  BOT STATUS          │  OPEN POSITIONS                   │
│  mode: PAPER         │  (table: direction, entry, pnl)  │
│  healthy: YES        │                                   │
│  safe_mode: NO       │                                   │
│  dd_daily: 0.0%      │                                   │
│  last_trade: ...     │                                   │
├──────────────────────┴──────────────────────────────────┤
│  RECENT TRADES (last 20)                                 │
│  (table: direction, entry, exit, pnl, outcome)           │
├──────────────────────────────────────────────────────────┤
│  LOG STREAM (SSE, last 100 lines, auto-scroll)           │
│  [ ] ERROR only  [ ] WARN+  [x] ALL                     │
│  14:22:01 | INFO | regime=BULL signal=LONG_RECLAIM       │
│  ...                                                     │
└──────────────────────────────────────────────────────────┘
```

- Status badge: green = `healthy=true, safe_mode=false` | yellow = `safe_mode=true` | red = `healthy=false` | grey = no data
- `/api/status` polled every 5s
- `/api/positions` polled every 10s
- `/api/trades` polled every 30s
- `/api/logs/stream` via EventSource (SSE, persistent)
- No framework (vanilla JS + fetch + EventSource) — zero build step

---

### Known Issues (from Claude Code audit)
| # | Issue | Blocking for this milestone? |
|---|---|---|
| 1 | `storage/db.py` has no WAL — concurrent readers may block | YES — fix is M2 (part of this scope) |
| 2 | `monitoring/health.py` depends on in-process clients — cannot be used by dashboard | NO — `health.py` is out of scope; status comes from DB only |
| 3 | Unrealized PnL requires current price — not available without live data feed | NO — show only entry price and size; note "unrealized PnL not shown" in UI |

---

### Acceptance criteria

M2 (WAL):
- [ ] `connect()` sets WAL mode (`PRAGMA journal_mode=WAL`)
- [ ] `connect_readonly()` opens with `?mode=ro` URI, raises `OperationalError` if DB does not exist
- [ ] `tests/test_dashboard_wal.py` passes: after `connect()`, journal_mode query returns `wal`
- [ ] Existing smoke tests: all 35 tests still green (zero regressions)

M1 (dashboard):
- [ ] `GET /api/status` returns persisted `bot_state` or `{"bot_state": null, ...}` when table is empty
- [ ] `GET /api/positions` returns open/partial positions
- [ ] `GET /api/trades?limit=N` returns last N closed trades
- [ ] `GET /api/logs/stream` streams SSE, reconnectable, serves last 100 lines on connect
- [ ] Server binds `127.0.0.1:8080` only (not `0.0.0.0`)
- [ ] `scripts/run_dashboard.py` starts server without bot running
- [ ] `tests/test_dashboard_db_reader.py` passes: queries against in-memory SQLite with schema applied
- [ ] UI loads in browser, status badge visible, log stream populates

---

### Commit discipline
- WHAT / WHY / STATUS in every commit message
- Separate commit for M2 (WAL patch) and M1 (dashboard) — do not squash
- Do NOT self-mark as "done". Claude Code audits after push.
- Do NOT modify bot logic, orchestrator, settings, or any file outside `dashboard/`, `storage/db.py`, `scripts/run_dashboard.py`, `tests/test_dashboard_*.py`

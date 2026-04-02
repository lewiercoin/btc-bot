## CLAUDE HANDOFF -> CODEX

### Checkpoint
- Last commit: `6592376` (`docs: record v1.0-baseline tag in MILESTONE_TRACKER`) + M1 implementation (uncommitted)
- Branch: `main`
- Working tree: dirty (M1 files added, not yet committed)

### Before you code
Read these files (mandatory):
1. `docs/BLUEPRINT_V1.md` — layer separation rules
2. `AGENTS.md` — discipline + workflow rules
3. `docs/MILESTONE_TRACKER.md` — DASHBOARD-M3 AWAITING_DECISION
4. `main.py` — graceful shutdown contract: `SIGINT`/`SIGTERM` → `orchestrator.stop()`; `KeyboardInterrupt` → `orchestrator.stop()`
5. `dashboard/server.py` — current FastAPI app (lifespan, state.reader)
6. `dashboard/db_reader.py` — two known issues carried from M1 audit (see below)
7. `dashboard/static/app.js` — `innerHTML` issue carried from M1 audit (see below)

---

### Milestone: DASHBOARD-M3 — Managed Start/Stop

**What this milestone IS:**
- POST `/api/bot/start` — launch bot subprocess with process isolation, single-instance guard
- POST `/api/bot/stop` — graceful stop via `CTRL_C_EVENT`, hard timeout fallback
- `uptime_seconds` populated in `/api/status` when process is running
- Operator audit log for start/stop actions
- Fix two M1 carry-over issues: `db_reader.py` OperationalError guard + `app.js` innerHTML

**What this milestone IS NOT:**
- No mode hot-switch (mode is set at launch time from env/arg, not changeable while running)
- No terminal (M5)
- No backtest/research job runner (M4)
- No authentication

---

### Deliverables

1. **`dashboard/process_manager.py`** — new module, all process lifecycle logic
2. **`dashboard/server.py`** — add `/api/bot/start` and `/api/bot/stop` endpoints; wire `ProcessManager` into lifespan
3. **`dashboard/db_reader.py`** — fix: catch `OperationalError` (missing DB file), return safe fallback `null`/empty
4. **`dashboard/static/app.js`** — fix: replace `innerHTML` table rendering with explicit DOM construction
5. **`dashboard/static/index.html`** — add START/STOP buttons wired to new endpoints
6. **`tests/test_process_manager.py`** — unit tests for `ProcessManager` (mock subprocess)

---

### process_manager.py — full contract

```python
class ProcessManager:
    """
    Manages a single bot subprocess. Thread-safe for concurrent API requests.

    Invariants:
    - At most one bot process alive at any time (single-instance guard).
    - Start and stop are idempotent: starting an already-running bot is a no-op with a clear status.
      Stopping an already-stopped bot is a no-op with a clear status.
    - Every start and stop is written to an operator audit log.
    - uptime_seconds is computed from launch timestamp, not from DB state.
    """
```

#### `ProcessManager.__init__(self, *, project_root: Path, operator_log_path: Path)`
- `project_root`: repo root, used to resolve `main.py` entrypoint
- `operator_log_path`: path to append operator audit events (JSONL, one event per line)
- Internal state: `_process: subprocess.Popen | None`, `_mode: str | None`, `_started_at: datetime | None`, `_lock: threading.Lock`

#### `ProcessManager.start(self, *, mode: str) -> dict`
- `mode`: `"PAPER"` or `"LIVE"` — validated, raises `ValueError` if neither
- If process already running → return `{"started": False, "reason": "already_running", "pid": <pid>}`
- Launch: `subprocess.Popen([sys.executable, "main.py", "--mode", mode], cwd=project_root, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)`
- Record `_started_at = datetime.now(timezone.utc)`, `_mode = mode`
- Append to operator audit log: `{"event": "start", "mode": mode, "pid": pid, "ts": ISO8601}`
- Return `{"started": True, "pid": <pid>, "mode": mode, "ts": ISO8601}`

#### `ProcessManager.stop(self, *, reason: str = "operator_stop") -> dict`
- If no process running → return `{"stopped": False, "reason": "not_running"}`
- Send `os.kill(pid, signal.CTRL_C_EVENT)` — graceful signal
- Wait up to **10 seconds** (`process.wait(timeout=10)`)
- If still alive after timeout → `process.terminate()` (hard fallback), append `{"event": "stop_hard", ...}` to operator log
- Clear `_process`, `_started_at`, `_mode`
- Append to operator audit log: `{"event": "stop", "reason": reason, "pid": <pid>, "graceful": bool, "ts": ISO8601}`
- Return `{"stopped": True, "graceful": bool, "pid": <pid>}`

#### `ProcessManager.status(self) -> dict`
- If no process: `{"running": False, "uptime_seconds": None, "pid": None, "mode": None}`
- If process alive (`process.poll() is None`): `{"running": True, "uptime_seconds": float, "pid": int, "mode": str}`
- If process exited (poll returned): auto-clear internal state, return `{"running": False, "uptime_seconds": None, "pid": None, "mode": None, "exit_code": int}`

**Important:** `status()` must detect zombie processes (process exited but `_process` still set). Always call `process.poll()` before reading state.

---

### API additions

```
POST /api/bot/start
Body: {"mode": "PAPER" | "LIVE"}
Response 200: {"started": true, "pid": 1234, "mode": "PAPER", "ts": "..."}
Response 200: {"started": false, "reason": "already_running", "pid": 1234}
Response 422: invalid mode

POST /api/bot/stop
Body: {} (optional: {"reason": "operator_stop"})
Response 200: {"stopped": true, "graceful": true, "pid": 1234}
Response 200: {"stopped": false, "reason": "not_running"}

GET /api/status  (updated)
Response: {
  "bot_state": {...} | null,           ← unchanged from M1, from DB
  "uptime_seconds": float | null,      ← NOW populated from ProcessManager.status()
  "process": {                         ← NEW field
    "running": bool,
    "pid": int | null,
    "mode": str | null,
    "exit_code": int | null            ← populated only if process exited since last status check
  },
  "dashboard_version": "m3"
}
```

**Note:** `bot_state` (from DB) and `process` (from ProcessManager) are intentionally separate. `bot_state` may be stale (from last run). `process` reflects current OS state. UI shows both.

---

### db_reader.py fix (carry from M1)

In `DashboardReader.read_status()`, `read_positions()`, `read_trades()`:
- Catch `sqlite3.OperationalError` (raised by `connect_readonly()` when file doesn't exist)
- Return safe fallback: `{"bot_state": null, "uptime_seconds": null, "dashboard_version": "m3"}` for status; `{"positions": [], "data_age_seconds": null}` for positions; `{"trades": []}` for trades
- Do NOT silently swallow other exceptions — only `OperationalError` with message matching `"unable to open"` is the file-not-found case

---

### app.js fix (carry from M1)

Replace `innerHTML` table rendering in `renderPositions()` and `renderTrades()` with explicit DOM construction:
```js
// Instead of: tbody.innerHTML = rows.map(...).join("")
// Use:
const tbody = document.getElementById("positions-body");
tbody.replaceChildren();  // clear
for (const pos of payload.positions) {
  const tr = document.createElement("tr");
  // td per field via createElement + textContent (NOT innerHTML)
  tbody.appendChild(tr);
}
```
`textContent` assignment auto-escapes — no XSS risk even if bot error strings contain `<` or `>`.

---

### UI additions (index.html + app.js)

Add a **BOT CONTROL** panel between the header and status panel:

```html
<article class="panel panel--control">
  <div class="panel__header">
    <h2>Bot Control</h2>
    <span class="panel__meta" id="process-status">Stopped</span>
  </div>
  <div class="control-row">
    <select id="bot-mode">
      <option value="PAPER">PAPER</option>
      <option value="LIVE">LIVE</option>
    </select>
    <button id="btn-start" class="btn btn--start">Start</button>
    <button id="btn-stop" class="btn btn--stop" disabled>Stop</button>
  </div>
  <p class="panel__note" id="control-message"></p>
</article>
```

UX rules:
- **START button** disabled while process is running
- **STOP button** disabled while process is stopped
- Both buttons show loading state (`disabled` + text change) during the POST request
- `LIVE` mode option shows a confirmation dialog: `"Start LIVE trading with real funds? This will place real orders."` — user must confirm before POST is sent
- `control-message` shows last action result (e.g. `"Started PID 1234"`, `"Stopped gracefully"`, `"Error: already running"`)
- Process status badge (`process-status`) updated from `/api/status` polling (every 5s, already in place)

---

### Known Issues (from Claude Code audit)
| # | Issue | Blocking for this milestone? |
|---|---|---|
| 1 | `db_reader.py` propagates `OperationalError` as HTTP 500 on missing DB | YES — fix is in scope |
| 2 | `app.js` uses `innerHTML` for table rendering | YES — fix is in scope |
| 3 | `process.terminate()` on Windows is hard kill — but this is the correct fallback after 10s graceful timeout | NO — by design |

---

### Acceptance criteria

db_reader fix:
- [ ] `GET /api/status` returns `{"bot_state": null, ...}` (not HTTP 500) when DB file doesn't exist
- [ ] `GET /api/positions` returns `{"positions": [], ...}` when DB file doesn't exist
- [ ] `GET /api/trades` returns `{"trades": []}` when DB file doesn't exist

app.js fix:
- [ ] `renderPositions()` and `renderTrades()` use `createElement` + `textContent` — no `innerHTML`

ProcessManager:
- [ ] `start()` with no running process → process launched, PID returned, operator log appended
- [ ] `start()` with already-running process → `{"started": false, "reason": "already_running"}`
- [ ] `stop()` graceful path: `CTRL_C_EVENT` sent, process exits within 10s, `{"stopped": true, "graceful": true}`
- [ ] `stop()` hard fallback: process doesn't exit in 10s → `terminate()` called, operator log records `stop_hard`
- [ ] `stop()` with no running process → `{"stopped": false, "reason": "not_running"}`
- [ ] `status()` detects zombie (process exited) and auto-clears state
- [ ] `uptime_seconds` in `/api/status` is `null` when stopped, positive float when running
- [ ] LIVE mode in UI requires confirmation before POST
- [ ] All 46 existing tests still pass (zero regressions)
- [ ] `tests/test_process_manager.py` passes with mocked subprocess

---

### Commit discipline
- WHAT / WHY / STATUS in every commit message
- Commit M1 files first (separate commit), then M3 changes (separate commit)
- Do NOT self-mark as "done". Claude Code audits after push.
- Do NOT modify bot logic, orchestrator, settings, or any file outside `dashboard/`, `tests/test_process_manager.py`

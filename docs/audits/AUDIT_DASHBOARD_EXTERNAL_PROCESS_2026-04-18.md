# AUDIT: Dashboard External Process Detection

Date: 2026-04-18  
Auditor: Claude Code  
Commit: 4e7be5d  
Milestone: Dashboard external process status fix

## Verdict: **DONE**

## Layer Separation: **PASS**

✅ **Changes isolated to dashboard:**
- Modified: `dashboard/process_manager.py` (+86, -4)
- Modified: `dashboard/server.py` (+14, -3)
- Modified: `dashboard/static/app.js` (+54, -33)
- Modified: `tests/test_dashboard_server.py` (+2)
- Modified: `tests/test_process_manager.py` (+81, -1)
- Zero changes to `core/**`, `execution/**`, `orchestrator.py`, `data/**`

✅ **No cross-layer dependencies introduced:**
- Uses `psutil` for process discovery (already in requirements.txt)
- No imports from core/execution layers
- Read-only process inspection

## Contract Compliance: **PASS**

✅ **API response contract extended (backward compatible):**

**Before:**
```json
{
  "process": {
    "running": false,
    "pid": null,
    "mode": null,
    "exit_code": null
  }
}
```

**After:**
```json
{
  "process": {
    "running": true,
    "pid": 123456,
    "mode": "PAPER",
    "exit_code": null,
    "managed": false
  }
}
```

**New field:** `managed: bool` — indicates if dashboard can control this process

✅ **Both `/api/status` and `/api/runtime-freshness` updated consistently**

✅ **UI handles new field gracefully:**
- Shows "Running PID xxx (MODE, external)" when `managed=false`
- Shows "Running PID xxx (MODE)" when `managed=true`
- Stop button disabled when `managed=false`

## Determinism: **PASS**

✅ **Process discovery is deterministic:**
- `psutil.process_iter()` scans all processes
- Matches on: `cmdline` contains `main.py` + `cwd` matches `project_root`
- Returns first match (if multiple exist, first wins — deterministic iteration order)

✅ **No randomness, no hidden state mutation**

## State Integrity: **PASS**

✅ **Internal state remains coherent:**

**Managed process lifecycle:**
```python
1. start() → creates subprocess → _process = Popen(...) → managed=True
2. stop() → kills subprocess → _clear_locked() → _process = None
3. status() → poll() == exit_code → _clear_locked() → managed=False
```

**External process lifecycle:**
```python
1. status() → _process == None → _discover_external_process_status()
2. If found: return running=True, managed=False
3. If not found: return running=False, managed=False
```

✅ **No race conditions:**
- All status checks guarded by `self._lock`
- External discovery runs only when `_process is None`

✅ **Invariant preserved:** At most one bot process alive at any time (checked via discovery)

## Error Handling: **PASS**

✅ **External process discovery graceful degradation:**
```python
try:
    # inspect process
except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError, ValueError):
    continue  # Skip to next process
```

✅ **Path comparison defensive:**
```python
def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve(strict=False) == right.resolve(strict=False)
    except OSError:
        return str(left) == str(right)  # Fallback to string comparison
```

✅ **Stop operation safe:**
- Returns `{"stopped": False, "reason": "not_managed"}` when trying to stop external process
- Does NOT attempt to kill process dashboard didn't start

## Smoke Coverage: **PASS**

✅ **29 tests pass (5 new external process tests):**

**New tests:**
1. `test_status_detects_external_bot_process` - discovery works
2. `test_start_refuses_duplicate_when_external_process_is_running` - no duplicate launches
3. `test_stop_rejects_external_process_that_is_not_dashboard_managed` - stop protection

**Existing tests still pass:**
- `test_start_launches_process_and_logs_event` (12 tests)
- `test_dashboard_server.py` (14 tests)
- `test_dashboard_db_reader.py` (3 tests)

✅ **Edge cases covered:**
- External process detected → `running=True, managed=False`
- External process running → `start()` returns `already_running`
- External process running → `stop()` returns `not_managed`
- Managed process exits → `managed=False, exit_code=0`
- No process → `running=False, managed=False`

## Tech Debt: **LOW**

✅ Clean implementation:
- No TODOs
- No NotImplementedError stubs
- Well-factored helper methods (`_looks_like_bot_process`, `_extract_mode`, `_same_path`)
- Type hints complete

✅ Code quality:
- Process matching logic isolated in `_looks_like_bot_process()`
- Mode extraction isolated in `_extract_mode()`
- Path comparison defensive with fallback
- UI logic extracted to `formatProcessLabel()` helper

**Note:** `psutil.process_iter()` scans all processes on every `status()` call when `_process is None`. This is acceptable for dashboard use (10s refresh interval), but if performance becomes an issue, could add caching with TTL.

## AGENTS.md Compliance: **PASS**

✅ **Commit message format (WHAT/WHY/STATUS):**
```
fix: detect external bot runtime in dashboard process status

WHAT: teach the dashboard process manager to detect a bot process started 
      outside the dashboard, expose a managed flag in status/runtime APIs, 
      and update the UI plus tests so external systemd-managed runtimes show 
      as running without enabling invalid stop controls
WHY: production dashboard reported process.running=false even while the bot 
     was healthy because ProcessManager only tracked subprocesses launched 
     from the dashboard itself
STATUS: dashboard process detection and UI contract are updated; compileall 
        plus tests/test_process_manager.py tests/test_dashboard_server.py 
        tests/test_dashboard_db_reader.py passed; ready for audit and deploy
```

✅ **Scope discipline:**
- Focused on dashboard process detection only
- No unrelated changes
- No scope creep

✅ **Tests validated before commit:**
- compileall ✓
- pytest (29 passed) ✓

---

## Critical Issues: **NONE**

## Warnings: **NONE**

## Observations

### 1. Process Discovery Performance

**Current implementation:** `psutil.process_iter()` scans all processes on every `status()` call when no managed process exists.

**Frequency:** Dashboard API calls `/api/status` every 10s.

**Impact:** Low overhead on typical systems (100-500 processes). On high-process-count servers (5000+ processes), could add 10-50ms latency.

**Mitigation (if needed):** Add caching with 30s TTL for external process lookup.

**Current assessment:** Acceptable. Not blocking.

### 2. Multiple External Processes

**Edge case:** If multiple `main.py` processes exist in the same project root (unlikely but possible), discovery returns the first match from `psutil.process_iter()`.

**Current behavior:** Deterministic (iteration order stable within a scan), but may not be the "most recent" process.

**Impact:** Low. Production typically has one systemd-managed bot.

**Alternative (if needed):** Return process with highest `create_time` (most recent).

**Current assessment:** Acceptable for MVP. Monitor production behavior.

### 3. UI Language Mix

**Observation:** UI shows "Running PID xxx (MODE, external)" in English, but production logs may be in Polish.

**Impact:** None (dashboard is operator-facing, English acceptable).

**Note:** If internationalization needed, extract to template strings.

---

## Recommended Next Step

**Milestone: DONE** ✅

**Deploy:** Ready to deploy commit 4e7be5d to production dashboard.

**Deployment steps:**
1. SSH to server: `ssh -i c:\development\btc-bot\btc-bot-deploy root@204.168.146.253`
2. Pull latest: `cd /home/btc-bot/btc-bot && git pull github main`
3. Restart dashboard: `systemctl restart btc-bot-dashboard`
4. Verify: `curl http://localhost:8080/api/status | jq '.process'`
5. Expected: `{"running": true, "pid": <systemd_pid>, "mode": "PAPER", "exit_code": null, "managed": false}`
6. Browser: Check dashboard shows "Running PID xxx (PAPER, external)" + stop button disabled

**No blockers from this audit.**

---

## Sign-Off

**Builder:** Codex  
**Auditor:** Claude Code  
**Commit:** 4e7be5d

**Verdict:** DONE ✅

Dashboard external process detection fix is production-ready. The process discovery, managed flag, and UI contract are clean, well-tested, and properly isolated from core pipeline.

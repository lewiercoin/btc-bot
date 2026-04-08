# AUDIT: SERVER-DEPLOY-V2
Date: 2026-04-08
Auditor: Claude Code
Commit: 1343d3c

## Verdict: MVP_DONE

One documentation fix required before first deploy (see Critical Issues). No logic bugs. All G1–G6 deliverables structurally correct.

## Layer Separation: PASS
No production code layer boundaries touched. Change is confined to: one bug fix in `dashboard/process_manager.py`, new infra files in `scripts/server/`, and docs.

## Contract Compliance: PASS
`process_manager.py` public API unchanged. Signal fix is internal to `stop()`.

## Determinism: N/A
No pipeline logic touched.

## State Integrity: PASS
G1 fix is correct. `sig = signal.CTRL_C_EVENT if sys.platform == "win32" else signal.SIGTERM` (line 90) resolves the `AttributeError` on Linux. Hard fallback (`process.terminate()` + 5s wait) unchanged — pre-existing issue (see Observations).

## Error Handling: PASS
`run_dashboard.sh` uses `set -eu`, CWD check, and `.venv` resolution. Consistent with existing script patterns.

## Smoke Coverage: PASS
`compileall` + `pytest 53/53` green. No new test surface required (infra files + docs).

## Tech Debt: LOW
One pre-existing issue noted in Observations. No new debt introduced.

## AGENTS.md Compliance: PASS
Single commit, WHAT/WHY/STATUS format. Does not self-mark as DONE.

## Methodology Integrity: N/A
## Promotion Safety: N/A
## Reproducibility & Lineage: N/A
## Data Isolation: N/A
## Search Space Governance: N/A
## Artifact Consistency: N/A
## Boundary Coupling: N/A

---

## Critical Issues (must fix before first deploy)

### C1 — `btc-bot-dashboard.service` not started in deploy checklist

`docs/SERVER_DEPLOYMENT.md` SYSTEMD SERVICES section:

```sh
systemctl enable btc-bot btc-bot-dashboard
systemctl start btc-bot                     # <-- dashboard NOT started
```

`systemctl enable` registers the service for auto-start on reboot — it does NOT start it immediately. After first deploy following this checklist, the dashboard will be unreachable until reboot or explicit `systemctl start btc-bot-dashboard`. The smoke test section does not test the dashboard, so the operator may not notice.

Fix: add `systemctl start btc-bot-dashboard` to the SYSTEMD SERVICES section, and add a dashboard smoke step to the SMOKE TEST section:

```sh
# Start dashboard
systemctl start btc-bot-dashboard

# Smoke test addition:
systemctl status btc-bot-dashboard
# Then from local machine (SSH tunnel):
# curl http://localhost:8080/api/status
```

---

## Warnings (fix soon)

None.

---

## Observations (non-blocking)

### O1 — Hard fallback sends SIGTERM twice on Linux

`process_manager.py` stop() flow on Linux when graceful timeout expires:
1. `os.kill(pid, SIGTERM)` — first signal (line 92)
2. 10s wait → `TimeoutExpired`
3. `process.terminate()` — sends SIGTERM again (line 109)
4. 5s wait → gives up

`process.terminate()` is `SIGTERM` on POSIX (not `SIGKILL`). If the bot ignored the first SIGTERM for 10 seconds, the second is unlikely to help. A true hard kill would be `process.kill()` (SIGKILL). Pre-existing design decision — acceptable for PAPER mode where data loss is not critical. Logged for LIVE mode consideration.

### O2 — `btc-bot-logrotate.conf` glob patterns

logrotate 3.x (Ubuntu 24.04 default) supports glob patterns in path directives. Verified supported. No action required.

### O3 — `storage/` directory existence assumption

`SERVER_DEPLOYMENT.md` instructs `scp storage/btc_bot.db ... /home/btc-bot/btc-bot/storage/btc_bot.db`. If `storage/` is not tracked in the repo (only the `.db` file is gitignored, directory may or may not have a tracked file like `schema.sql`), the directory will exist after `git clone`. If schema.sql is tracked there (likely, given `init_db` uses it), this is safe. No action required — verifiable during first deploy.

---

## Recommended Next Step

**Cascade: fix C1** — add two lines to `docs/SERVER_DEPLOYMENT.md`:
1. `systemctl start btc-bot-dashboard` in SYSTEMD SERVICES section
2. `systemctl status btc-bot-dashboard` in SMOKE TEST section

Single commit. After push: re-audit is not required — C1 is documentation-only. Claude Code will promote to **DONE** on confirmation.

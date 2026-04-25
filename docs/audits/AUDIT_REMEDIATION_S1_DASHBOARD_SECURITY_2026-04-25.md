# AUDIT: REMEDIATION-S1-DASHBOARD-SECURITY
Date: 2026-04-25
Auditor: Claude Code
Builder: Codex
Commit: 8c71360

## Verdict: DONE

## Security Hardening: PASS
## Production-Repo Alignment: PASS
## Operator Documentation: PASS
## Validation Coverage: PASS

## Findings

### Evidence reviewed
- `ops/systemd/btc-bot-dashboard.service` — canonical localhost-bound unit file (15 lines)
- `docs/ops/SSH_TUNNEL_ACCESS.md` — SSH tunnel operator runbook (57 lines)
- Production server state verification via SSH:
  - `systemctl cat btc-bot-dashboard` — confirmed `--host 127.0.0.1 --port 8080`
  - `ufw status` — confirmed `8080/tcp` rule removed (only `22/tcp` active)
  - `ss -tlnp` — confirmed listening on `127.0.0.1:8080` (not `0.0.0.0:8080`)
  - `journalctl -u btc-bot-dashboard` — clean startup, no errors
  - Public access test: `curl http://204.168.146.253:8080/api/status` → timeout (blocked as expected)
  - Local server access: `curl http://127.0.0.1:8080/api/status` via SSH → success (JSON response)

### Assessment summary
- **Security incident remediated.** Dashboard no longer exposed to public internet. Unauthenticated control endpoints (`POST /api/bot/start`, `POST /api/bot/stop`) are now localhost-only.
- **Production-repo drift eliminated for dashboard unit.** Deployed unit file now matches canonical repo unit (`ops/systemd/btc-bot-dashboard.service`).
- **Operator access documented.** `docs/ops/SSH_TUNNEL_ACCESS.md` provides complete Windows SSH tunnel procedure with verification steps.
- **All acceptance criteria met:**
  - ✅ Dashboard bound to `127.0.0.1:8080`
  - ✅ UFW rule `8080/tcp` removed
  - ✅ Public access blocked (connection timeout)
  - ✅ Local server access via SSH works (bot state JSON returned)
  - ✅ SSH tunnel documentation complete
  - ✅ Repo unit file canonical and production-aligned
  - ✅ Service restarted cleanly (no errors)

## Critical Issues (must fix before next milestone)
None identified. Security emergency remediated.

## Warnings (fix soon)
- **Main bot service drift remains.** Deployed `btc-bot.service` still differs from repo (uses `BOT_SETTINGS_PROFILE=experiment` vs `.env`-driven config). Out of scope for S1, defer to future milestone.

## Observations (non-blocking)
- **Commit discipline excellent.** Codex followed WHAT/WHY/STATUS format, included production verification in commit message.
- **Validation thorough.** Codex tested both server-side (`systemctl cat`, `ufw status`, `ss`, `journalctl`) and external (public curl timeout) verification.
- **Documentation production-ready.** SSH tunnel runbook is Windows-specific (correct for this operator), includes all verification commands.
- **Firewall rule removal clean.** `ufw --force delete` avoided interactive prompt during automation.

## Recommended Next Step
REMEDIATION-S1-DASHBOARD-SECURITY is DONE. Push immediately. Next milestone: **REMEDIATION-A1-FUNDING-FEES** (Tier A: Blocks Live Readiness).

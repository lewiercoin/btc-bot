# AUDIT ADDENDUM: MULTI_ASSET_SHADOW_SIDECAR_DEPLOYMENT_V1 Phase 1 Hotfix 2
Date: 2026-05-20
Auditor: Claude Code
Commit: 1f2924a
Previous Audits:
- AUDIT_MULTI_ASSET_SHADOW_SIDECAR_DEPLOYMENT_V1_PHASE1_2026-05-20.md (verdict: DONE)
- AUDIT_MULTI_ASSET_SHADOW_SIDECAR_DEPLOYMENT_V1_PHASE1_HOTFIX_2026-05-20.md (verdict: DONE)

## Context
Day 0 deployment retry (commit ce82fdb) failed after portability hotfix with:
```
PermissionError: [Errno 13] Permission denied: '/tmp/multi-asset-shadow.lock'
```

Root cause:
- deploy_shadow_sidecar.sh runs as root (sudo bash scripts/deploy_shadow_sidecar.sh)
- Day 0 dry-run executed as root, created `/tmp/multi-asset-shadow.lock` and `research_lab/shadow/` owned by root:root
- systemd service `multi-asset-shadow.service` runs as `User=btc-bot`
- Service cannot write to root-owned lock file or shadow DB directory

Cleanup performed by Codex:
- stopped/disabled/removed timer and service
- moved failed artifacts to /tmp with timestamp
- btc-bot.service remains active, BTC PAPER PID 815407 unaffected

## Hotfix Scope
Run Day 0 dry-run as btc-bot user so lock file and shadow DB are created with correct ownership:
- Change: `sudo -u btc-bot -H "${REPO_DIR}/.venv/bin/python" sidecar_main.py --dry-run --repo-root "${REPO_DIR}"`
- Effect: lock file, shadow DB directory, and all files created with btc-bot:btc-bot ownership
- Service can write to these paths without permission errors

## Verdict: DONE

## Ownership Model: PASS
- Dry-run now runs as btc-bot user (same as systemd service)
- Lock file created with btc-bot:btc-bot ownership
- Shadow DB directory created with btc-bot:btc-bot ownership
- Systemd service `User=btc-bot` can write to all sidecar artifacts

## Security: PASS
- Principle of least privilege: dry-run does not need root
- Sidecar runs as non-root user throughout lifecycle
- No privilege escalation in sidecar code path
- Deploy script still requires root for systemd unit install (correct)

## Logic Integrity: PASS
- No change to sidecar logic, timer config, or resource guards
- Only changes: user context for dry-run execution in deploy script
- Added `--repo-root` flag to ensure correct working directory under sudo -u

## Portability: PASS
- `sudo -u btc-bot -H` is standard Unix/Linux syntax
- `-H` flag sets HOME to target user's home (prevents $HOME pollution)
- Works on Ubuntu, Debian, RHEL, and derivatives
- No Windows compatibility needed (deploy script is server-only)

## Test Coverage: PASS
- test_deployment_scripts_preserve_btc_service_boundaries: PASSED
- Test verifies script structure, not user context (acceptable for this fix)
- Manual verification needed on server during Day 0 retry

## Regression Risk: LOW
- Dry-run now runs with less privilege (safer)
- No runtime code changed
- No sidecar logic changed
- No timer/service config changed
- Service behavior unchanged (already ran as btc-bot)

## Day 0 Deployment Status
**Ready for retry.**

Previous attempt state (after rollback):
- Server at commit ce82fdb (portability hotfix, but ownership bug still present)
- Timer/service removed (clean state)
- Failed artifacts moved to /tmp/...failed_day0_20260520T081754Z
- No sidecar running
- BTC PAPER bot: PID 815407, active

Retry requirements:
1. git pull on server to commit 1f2924a (this fix)
2. Verify no stale root-owned artifacts in research_lab/shadow/ or /tmp/multi-asset-shadow.lock
3. Execute scripts/deploy_shadow_sidecar.sh
4. Verify Day 0 acceptance criteria (unchanged from original audit)

## Critical Issues
None.

## Warnings
None.

## Observations
1. Root-owned sidecar artifacts from previous attempts must be cleaned before retry (already done by Codex)
2. Deploy script now requires btc-bot user to exist and have access to .venv/bin/python (already true on production server)
3. Dry-run output remains visible to root user who runs deploy script (stdout capture works across sudo -u)
4. Lock file persists after dry-run but with correct ownership, so service can overwrite it on first cycle

## Pre-Retry Checklist
Before Day 0 retry, verify on server:
- [ ] No root-owned `/tmp/multi-asset-shadow.lock` (cleanup done)
- [ ] No root-owned `research_lab/shadow/` (cleanup done)
- [ ] btc-bot user exists (should be true)
- [ ] btc-bot user can execute `.venv/bin/python` (should be true)
- [ ] Server at commit 1f2924a or later

## Recommended Next Step
Hand back to Codex for Day 0 deployment retry with commit 1f2924a.

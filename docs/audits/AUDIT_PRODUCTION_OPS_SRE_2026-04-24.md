# AUDIT: Production Ops / SRE
Date: 2026-04-24
Auditor: Cascade (Builder Mode)
Commit: 2b59bb5

## Verdict: LOOKS_DONE

## Process Manager / Service Topology: PASS
## Auto-Restart Policy: PASS
## Uptime / Crash History: WARN
## Healthcheck / Status Surface: PASS
## Alert Coverage for Crash Events: FAIL
## Runbook Accuracy / Operator Clarity: FAIL

## Critical Issues (must fix before next milestone)
- Production dashboard is exposed publicly on `0.0.0.0:8080` and UFW allows `8080/tcp` from anywhere.
- The public dashboard exposes unauthenticated control endpoints (`/api/bot/start`, `/api/bot/stop`). This is both a security and operations risk because any remote actor can affect bot process state if they know the endpoint.

## Warnings (fix soon)
- Production `btc-bot.service` has drift from repository/service docs:
  - deployed: `Restart=always`, `Environment="BOT_SETTINGS_PROFILE=experiment"`, no `EnvironmentFile`
  - repo: `Restart=on-failure`, `EnvironmentFile=/home/btc-bot/btc-bot/.env`
- Production `btc-bot-dashboard.service` also drifts from repo/docs:
  - deployed binds `0.0.0.0:8080`
  - repo/docs describe loopback-only `127.0.0.1:8080`
- Runbook accuracy is stale:
  - `docs/SERVER_DEPLOYMENT.md` says dashboard is not publicly accessible and should be SSH-tunneled
  - production reality contradicts that
- Safe-mode diagnostic script is stale/broken for current schema/runtime:
  - reads `/home/btc-bot/btc-bot/logs/bot.log` instead of `logs/btc_bot.log`
  - queries `bot_state` as key/value rows, which no longer matches schema
  - no matching operator guide file was found under `docs/diagnostics/`
- Crash alert routing is not independently proven:
  - Telegram alerting exists in code for kill-switch and critical errors
  - no PagerDuty/Slack/email crash route or systemd-level failure notification was evidenced in repo or production outputs

## Observations (non-blocking)
- Service management exists and is active on production:
  - `btc-bot.service` active/running
  - `btc-bot-dashboard.service` active/running
  - force-order collector service and daily collector timer exist in repo
- Current production restart posture:
  - `btc-bot`: `Restart=always`, `NRestarts=1`, active since `2026-04-24 04:10:43 UTC`
  - `btc-bot-dashboard`: `Restart=on-failure`, `NRestarts=0`, active since `2026-04-23 06:56:44 UTC`
- Historical crash evidence exists in systemd journal:
  - repeated `status=203/EXEC` failures on `2026-04-20` with scheduled restart jobs
- Health/status surfaces exist:
  - `/api/status`
  - `/api/runtime-freshness`
  - `/api/server-resources`
  - `scripts/query_bot_status.py`
- Current bot runtime is healthy and producing 15-minute cycles consistently after the `2026-04-24` restart window.

## Recommended Next Step
Treat the dashboard exposure/control-plane issue as an immediate remediation item: close port `8080` publicly or rebind to loopback, then reconcile deployed unit files and operator runbooks so production reality matches documented operations.

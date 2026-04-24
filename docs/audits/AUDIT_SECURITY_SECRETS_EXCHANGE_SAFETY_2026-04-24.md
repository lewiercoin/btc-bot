# AUDIT: Security / Secrets / Exchange Safety
Date: 2026-04-24
Auditor: Cascade (Builder Mode)
Commit: 2b59bb5

## Verdict: NOT_DONE

## Secret Hygiene: PASS
## Git History Leakage Scan: PASS
## Exchange Permission Posture: WARN
## Network Exposure / Control Plane: FAIL
## Kill-Switch / Exchange Safety Controls: PASS
## Secret Management / Ignore Coverage: PASS

## Critical Issues (must fix before next milestone)
- Public dashboard exposure is confirmed on production:
  - server unit binds `uvicorn dashboard.server:app --host 0.0.0.0 --port 8080`
  - `ss -tlnp` shows `0.0.0.0:8080`
  - `ufw status` explicitly allows `8080/tcp`
  - `curl http://204.168.146.253:8080/api/status` returns live bot state publicly
- The public dashboard exposes unauthenticated bot control endpoints in code:
  - `POST /api/bot/start`
  - `POST /api/bot/stop`
  - no authentication, authorization, or IP restriction is implemented in `dashboard/server.py`
- Exchange API permission posture was not independently verified:
  - no operator screenshot or exchange-side permission snapshot was available during this audit
  - withdrawal-disabled / IP whitelist / exact trading permission therefore remain unproven

## Warnings (fix soon)
- Production `btc-bot.service` differs materially from the repo copy:
  - deployed unit uses `Restart=always`
  - repo unit uses `Restart=on-failure`
  - deployed unit sets `Environment="BOT_SETTINGS_PROFILE=experiment"`
  - repo unit uses `EnvironmentFile=/home/btc-bot/btc-bot/.env`
- Production `btc-bot-dashboard.service` differs materially from repo/docs:
  - deployed unit binds `0.0.0.0`
  - repo/docs describe `127.0.0.1` plus SSH tunnel access
- Secret loading depends on process environment only:
  - `settings.py` reads `BINANCE_API_KEY`, `BINANCE_API_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` directly from environment
  - no local dotenv loader is used in runtime code

## Observations (non-blocking)
- `.gitignore` correctly ignores:
  - `.env`
  - SSH deploy keys: `btc-bot-deploy`, `btc-bot-deploy.pub`, `btc-bot-deploy-v2`, `btc-bot-deploy-v2.pub`
  - runtime databases and `logs/`
- `git log --all --name-status -- .env .env.example btc-bot-deploy btc-bot-deploy.pub btc-bot-deploy-v2 btc-bot-deploy-v2.pub` showed only tracked `.env.example`, not real secret files or deploy keys
- Regex-based git patch search found references to secret variable names in docs/tests/code, but no confirmed committed live secret values from the sampled history review
- Kill-switch implementation exists and is wired to both audit logging and Telegram alerts:
  - health failure threshold
  - daily drawdown
  - weekly drawdown
  - consecutive losses
  - critical execution errors
- Recovery and exchange safety controls are present in code:
  - startup sync logic in `execution/recovery.py`
  - safe mode activation in `orchestrator.py`

## Recommended Next Step
Immediately remove public dashboard exposure or add real authentication before any further live-readiness work, then obtain an operator-supplied exchange permission snapshot proving withdrawal disabled, IP restriction enabled, and intended trading scope.

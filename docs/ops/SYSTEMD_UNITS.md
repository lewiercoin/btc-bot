# Systemd Service Units

## Overview

Production services are managed by systemd on Ubuntu server (`204.168.146.253`).

**Canonical unit files:** `ops/systemd/`
- `btc-bot.service` — main trading bot
- `btc-bot-dashboard.service` — web dashboard (localhost-only)

**Production location:** `/etc/systemd/system/`

## btc-bot.service

Main trading bot service.

**Current configuration:**
- **Mode:** PAPER (paper trading validation)
- **Profile:** experiment (via `BOT_SETTINGS_PROFILE=experiment`)
- **Restart policy:** always (auto-restart on any exit)
- **Working directory:** `/home/btc-bot/btc-bot`
- **User:** btc-bot (non-root, restricted permissions)

**Key settings:**
```ini
Environment="BOT_SETTINGS_PROFILE=experiment"
ExecStart=/home/btc-bot/btc-bot/.venv/bin/python main.py --mode PAPER
Restart=always
RestartSec=10
```

**Why `experiment` profile?**

The bot is currently in tuning/validation phase with relaxed risk limits:
- `weekly_dd_limit = 0.30` (vs production 0.063)
- `daily_dd_limit = 0.20` (vs production 0.185)
- `max_consecutive_losses = 15` (vs production 5)

See `docs/MILESTONE_TRACKER.md` → "Open Tech Debt: Kill-Switch Limits".

**Before LIVE mode:** Restore production risk limits and change to `BOT_SETTINGS_PROFILE=live`.

## btc-bot-dashboard.service

Web dashboard service (localhost-only, SSH tunnel access).

**Security hardening (REMEDIATION-S1):**
- **Binding:** `127.0.0.1:8080` (not `0.0.0.0`, localhost-only)
- **Firewall:** Port 8080 NOT exposed publicly
- **Access:** SSH tunnel required (see `docs/ops/SSH_TUNNEL_ACCESS.md`)

**Key settings:**
```ini
ExecStart=/home/btc-bot/btc-bot/.venv/bin/uvicorn dashboard.server:app --host 127.0.0.1 --port 8080
Restart=on-failure
```

## Deployment Procedure

### 1. Update unit file in repo
```bash
nano ops/systemd/btc-bot.service
git commit -m "ops: update btc-bot.service restart policy"
```

### 2. Deploy to production
```bash
# Copy to production
scp -i btc-bot-deploy-v2 ops/systemd/btc-bot.service root@204.168.146.253:/etc/systemd/system/

# Reload systemd + restart service
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl daemon-reload && systemctl restart btc-bot.service"

# Verify status
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl status btc-bot.service"
```

### 3. Verify no drift
```bash
./scripts/check_production_drift.sh
```

## Automated Drift Detection

Run periodically to detect production-repo drift:

```bash
./scripts/check_production_drift.sh
```

This checks:
- `btc-bot.service` (deployed vs repo)
- `btc-bot-dashboard.service` (deployed vs repo)
- Python version (`.python-version` vs production)

**Expected output:**
```
=== Production-Repo Configuration Drift Check ===

Checking btc-bot.service...
  ✅ btc-bot.service: IN SYNC
Checking btc-bot-dashboard.service...
  ✅ btc-bot-dashboard.service: IN SYNC
Checking Python version...
  ✅ Python version: 3.12.3 (IN SYNC)

=== End of Drift Check ===
```

## Service Management

### Check status
```bash
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl status btc-bot.service"
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl status btc-bot-dashboard.service"
```

### View logs
```bash
# Last 50 lines
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "journalctl -u btc-bot.service -n 50 --no-pager"

# Follow live logs
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "journalctl -u btc-bot.service -f"
```

### Restart services
```bash
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl restart btc-bot.service"
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl restart btc-bot-dashboard.service"
```

### Stop services (manual safe mode)
```bash
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl stop btc-bot.service"
```

## Troubleshooting

### Service fails to start
```bash
# Check systemd status
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl status btc-bot.service"

# Check recent logs
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "journalctl -u btc-bot.service -n 100 --no-pager"

# Verify unit file syntax
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemd-analyze verify /etc/systemd/system/btc-bot.service"
```

### Service restarts unexpectedly
Check logs for errors:
```bash
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "journalctl -u btc-bot.service --since '1 hour ago' | grep -E 'ERROR|CRITICAL'"
```

Common causes:
- Unhandled exception in bot code
- Database connection failure
- Exchange API timeout
- Safe mode trigger (check `storage/btc_bot.db` → `safe_mode_events` table)

### Unit file changes not applied
```bash
# Always reload after editing unit file
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl daemon-reload"
ssh -i btc-bot-deploy-v2 root@204.168.146.253 "systemctl restart btc-bot.service"
```

## Future Improvements

- **Blue-green deployment:** Run two versions side-by-side for zero-downtime updates
- **Health check endpoint:** Automated liveness probes
- **Watchdog timer:** systemd `WatchdogSec=` for stuck process detection
- **Resource limits:** `MemoryMax=`, `CPUQuota=` to prevent resource exhaustion

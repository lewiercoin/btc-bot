# Dashboard: Access Guide

## Current Production State

| Item | Value |
|---|---|
| Server | Hetzner VPS `204.168.146.253` |
| Dashboard URL | `http://127.0.0.1:8080` via SSH tunnel |
| Bot user | `btc-bot` |
| Repo path | `/home/btc-bot/btc-bot` |
| SSH key | `btc-bot-deploy-v2` (Windows: `c:\development\btc-bot\btc-bot-deploy-v2`) |
| Bot service | `btc-bot.service` |
| Dashboard service | `btc-bot-dashboard.service` |
| Proxy exit node | Vultr SOCKS5 `80.240.17.161:1080` |

---

## 1. SSH Access

From Windows PowerShell:

```powershell
ssh -i c:\development\btc-bot\btc-bot-deploy-v2 root@204.168.146.253
```

---

## 2. Starting the Dashboard

### Via systemd (production, recommended)

```bash
sudo systemctl start btc-bot-dashboard
sudo systemctl status btc-bot-dashboard
```

Enable on boot:

```bash
sudo systemctl enable btc-bot-dashboard
```

Check logs:

```bash
sudo journalctl -u btc-bot-dashboard -f --lines=50
```

### Via shell script (development/testing)

Run from the repo root:

```bash
sh scripts/server/run_dashboard.sh
```

This starts `uvicorn dashboard.server:app --host 127.0.0.1 --port 8080`. Use an SSH tunnel for browser access.

---

## 3. SSH Tunnel Access

The production dashboard is intentionally bound to `127.0.0.1:8080`. Public access to `http://204.168.146.253:8080` is blocked after the security remediation because the dashboard exposes unauthenticated operator controls.

Open the tunnel from Windows:

```powershell
C:\Windows\System32\OpenSSH\ssh.exe -i c:\development\btc-bot\btc-bot-deploy-v2 -L 8080:127.0.0.1:8080 root@204.168.146.253
```

Keep that SSH session open. Then browse to:

```text
http://127.0.0.1:8080
```

Quick local verification:

```powershell
curl.exe http://127.0.0.1:8080/api/status
curl.exe http://127.0.0.1:8080/api/egress
```

---

## 4. Browser Access

With the tunnel open, browse to:

```text
http://127.0.0.1:8080
```

Dashboard panels:

- Bot Status
- Bot Control
- Open Positions
- Egress Health
- Recent Trades
- Signals
- Daily Metrics
- Alerts
- Log Stream

Safe mode alert banner appears at the top of the page in red when `safe_mode = true` in bot state.

---

## 5. Health Check

Verify the dashboard is running and returning data:

```bash
curl -s http://localhost:8080/api/status | python3 -m json.tool | head -20
curl -s http://localhost:8080/api/egress | python3 -m json.tool
```

Expected `/api/status` response includes `bot_state`, `process`, `dashboard_version: "m4"`.

Expected `/api/egress` response includes fields such as `proxy_enabled`, `proxy_type`, `proxy_host`, `proxy_port`, and `safe_mode`.

If `proxy_enabled` is `false`, check `.env` for `PROXY_ENABLED=true`.

---

## 6. Stopping / Restarting

```bash
sudo systemctl stop btc-bot-dashboard
sudo systemctl restart btc-bot-dashboard
```

Restarting the dashboard does not restart the bot runtime.

---

## 7. Log Rotation

The dashboard is read-only. Its live log stream tails `logs/btc_bot.log` through the SSE endpoint.

If the stream appears stale after log rotation:

```bash
sudo systemctl restart btc-bot-dashboard
```

---

## 8. Server-Side Verification

Use these checks after deployment:

```bash
systemctl cat btc-bot-dashboard
ufw status
ss -tlnp | grep 8080
journalctl -u btc-bot-dashboard -n 50 --no-pager
```

Expected state:

- `ExecStart` uses `--host 127.0.0.1 --port 8080`
- `ufw status` does not list `8080/tcp`
- `ss -tlnp` shows `127.0.0.1:8080`, not `0.0.0.0:8080`
- `journalctl` shows clean startup without binding errors

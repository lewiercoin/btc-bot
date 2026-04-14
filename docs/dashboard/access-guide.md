# Dashboard: Access Guide

## Current Production State

| Item | Value |
|---|---|
| Server | Hetzner VPS — `204.168.146.253` |
| Dashboard URL | `http://204.168.146.253:8080` |
| Bot user | `btc-bot` |
| Repo path | `/home/btc-bot/btc-bot` |
| SSH key | `btc-bot-deploy` (in repo root, Windows: `c:\development\btc-bot\btc-bot-deploy`) |
| Bot service | `btc-bot.service` |
| Dashboard service | `btc-bot-dashboard.service` |
| Proxy exit node | Vultr SOCKS5 `80.240.17.161:1080` |

---

## 1. SSH Access

```bash
ssh -i btc-bot-deploy btc-bot@204.168.146.253
```

From Windows (PowerShell):
```powershell
ssh -i c:\development\btc-bot\btc-bot-deploy btc-bot@204.168.146.253
```

---

## 2. Starting the Dashboard

### Via systemd (production — recommended)

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

This loads `.env`, then starts `uvicorn dashboard.server:app --host 127.0.0.1 --port 8080` (localhost only — use SSH tunnel for access, see §5).

---

## 3. External Access (Production Binding)

The production deployment binds to `0.0.0.0:8080` for direct browser access without an SSH tunnel. The repo default service file uses `127.0.0.1`. To enable external access on the server:

**Override the service binding:**

```bash
sudo systemctl edit btc-bot-dashboard
```

Add:
```ini
[Service]
ExecStart=
ExecStart=/home/btc-bot/btc-bot/.venv/bin/uvicorn dashboard.server:app --host 0.0.0.0 --port 8080
```

Reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart btc-bot-dashboard
```

**Open UFW firewall (if not already open):**

```bash
sudo ufw allow 8080/tcp comment "btc-bot dashboard"
sudo ufw reload
sudo ufw status
```

Verify the rule is present:
```bash
sudo ufw status | grep 8080
```

---

## 4. Browser Access

After §3 is applied, open in browser:

```
http://204.168.146.253:8080
```

**Dashboard panels:**
- **Bot Status** — mode, healthy/safe-mode, open positions, drawdown
- **Bot Control** — start/stop with mode selector (PAPER / LIVE)
- **Open Positions** — live PnL, side, leverage
- **Egress Health** — proxy enabled/type, exit IP, session age, bans/24h, safe mode (10s refresh)
- **Recent Trades** — last 20 closed trades + CSV export
- **Signals** — last 20 signal candidates with reasons
- **Daily Metrics** — PnL, win rate, max drawdown
- **Alerts** — last 20 errors/warnings (24h window)
- **Log Stream** — live tail of `logs/btc_bot.log` via SSE

**Safe mode alert banner** appears at the top of the page in red when `safe_mode = true` in the bot state.

---

## 5. SSH Tunnel (Alternative — No Firewall Change Needed)

If external binding is not desired, access the dashboard via SSH port forwarding:

```bash
ssh -i btc-bot-deploy -L 8080:127.0.0.1:8080 btc-bot@204.168.146.253 -N
```

Then open: `http://localhost:8080`

Keep the tunnel open for the entire session. Use `-f` to background it:
```bash
ssh -i btc-bot-deploy -fNL 8080:127.0.0.1:8080 btc-bot@204.168.146.253
```

---

## 6. Health Check

Verify the dashboard is running and returning data:

```bash
# From the server (or via tunnel)
curl -s http://localhost:8080/api/status | python3 -m json.tool | head -20
curl -s http://localhost:8080/api/egress  | python3 -m json.tool
```

Expected `/api/status` response includes `bot_state`, `process`, `dashboard_version: "m4"`.

Expected `/api/egress` response includes:
```json
{
  "proxy_enabled": true,
  "proxy_type": "socks5",
  "proxy_host": "80.240.17.161",
  "proxy_port": 1080,
  "safe_mode": false
}
```

If `proxy_enabled` is `false`, check `.env` for `PROXY_ENABLED=true`.

---

## 7. Stopping / Restarting

```bash
sudo systemctl stop btc-bot-dashboard
sudo systemctl restart btc-bot-dashboard
```

Restart without taking down the bot:
```bash
sudo systemctl restart btc-bot-dashboard   # dashboard is read-only, bot unaffected
```

---

## 8. Log Rotation

Bot runtime log (`logs/btc_bot.log`) is read by the dashboard's `/api/egress` endpoint (last 256 KB tail) and streamed live via SSE (`/api/logs/stream`).

**Manual rotation if the log grows large:**

```bash
cp /home/btc-bot/btc-bot/logs/btc_bot.log /home/btc-bot/btc-bot/logs/btc_bot.log.$(date +%Y%m%d)
truncate -s 0 /home/btc-bot/btc-bot/logs/btc_bot.log
sudo systemctl restart btc-bot-dashboard   # reconnects SSE tail
```

**Automatic rotation via logrotate:**

The repo ships `scripts/server/btc-bot-logrotate.conf` for research/optimize logs. To add bot log rotation, install the config and create an entry for `btc_bot.log`:

```bash
sudo cp /home/btc-bot/btc-bot/scripts/server/btc-bot-logrotate.conf /etc/logrotate.d/btc-bot
```

Then add to the conf file:
```
/home/btc-bot/btc-bot/logs/btc_bot.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
}
```

Test:
```bash
sudo logrotate --debug /etc/logrotate.d/btc-bot
```

---

## 9. Deploying a Code Update

After merging to `main`, pull and restart on the server:

```bash
cd /home/btc-bot/btc-bot
git pull origin main
pip install -r requirements.txt --quiet          # only if requirements changed
sudo systemctl restart btc-bot-dashboard
```

Bot service (`btc-bot.service`) is **not** restarted unless the bot code itself changed.

---

## 10. Egress Health — Interpreting the Panel

| Field | Healthy state | Action if not healthy |
|---|---|---|
| Proxy enabled | Yes (green) | Check `PROXY_ENABLED=true` in `.env` |
| Exit node | `80.240.17.161:1080` | Check Vultr VPS is running: `ssh root@80.240.17.161` |
| Session age | < sticky_minutes (60 min) | Normal — session reinit is logged |
| Bans detected (24h) | 0 | If > 0: Vultr exit IP may be re-blocked — check `PROXY_FAILOVER_LIST` |
| Safe mode | Off (green) | If Active: trading paused, check bot log for root cause |

---

## Related Docs

- [`docs/infra/egress-vultr.md`](../infra/egress-vultr.md) — Vultr SOCKS5 setup, destroy instructions
- [`docs/dashboard/egress-integration.md`](egress-integration.md) — `/api/egress` API schema + architecture
- [`docs/SERVER_DEPLOYMENT.md`](../SERVER_DEPLOYMENT.md) — full server setup from scratch
- [`scripts/server/btc-bot-dashboard.service`](../../scripts/server/btc-bot-dashboard.service) — systemd unit file
- [`scripts/server/run_dashboard.sh`](../../scripts/server/run_dashboard.sh) — manual start script

# Server Deployment

## Target infrastructure

- **Provider:** Hetzner Cloud
- **Server type:** cpx31 (8 vCPU, 16 GB RAM, 80 GB SSD NVMe)
- **Location:** hel1 (Helsinki)
- **OS:** Ubuntu 24.04
- **Deploy path:** `/home/btc-bot/btc-bot`
- **System user:** `btc-bot` (non-root, no login shell)
- **SSH key:** ed25519 key injected at server creation (`~/.ssh/id_ed25519.pub`)

---

## Deploy Checklist

Complete all steps in order. Do not skip.

### PRE-DEPLOY (locally)

```sh
# Verify BINANCE_API_KEY scope in Binance dashboard:
# Futures Trading permissions ONLY. No withdrawal permissions.

# Build or update the deploy bundle:
git bundle create btc-bot.bundle --all
```

### SERVER SETUP

SSH as root after server creation:

```sh
# Create dedicated system user (no login shell)
useradd --system --shell /usr/sbin/nologin --home /home/btc-bot --create-home btc-bot

# Harden SSH: disable password authentication
# Edit /etc/ssh/sshd_config and set:
#   PasswordAuthentication no
# Then restart SSH:
systemctl restart ssh

# Enable firewall (SSH only — dashboard is NOT exposed)
ufw allow 22/tcp
ufw enable
```

### DEPLOY REPO

From the local machine:

```sh
scp btc-bot.bundle root@<server-ip>:/home/btc-bot/btc-bot.bundle
```

On the server:

```sh
cd /home/btc-bot
git clone btc-bot.bundle btc-bot
chown -R btc-bot:btc-bot /home/btc-bot/btc-bot
chmod 750 /home/btc-bot/btc-bot
cd /home/btc-bot/btc-bot
sh scripts/server/setup.sh
```

### ENVIRONMENT

From the local machine:

```sh
scp .env root@<server-ip>:/home/btc-bot/btc-bot/.env
```

On the server:

```sh
chmod 600 /home/btc-bot/btc-bot/.env
chown btc-bot:btc-bot /home/btc-bot/btc-bot/.env

# Verify BOT_MODE is PAPER before starting
grep BOT_MODE /home/btc-bot/btc-bot/.env
```

### MARKET DATA

From the local machine:

```sh
scp storage/btc_bot.db root@<server-ip>:/home/btc-bot/btc-bot/storage/btc_bot.db
```

On the server:

```sh
chown btc-bot:btc-bot /home/btc-bot/btc-bot/storage/btc_bot.db
cd /home/btc-bot/btc-bot
sh scripts/server/refresh_data.sh
```

### SYSTEMD SERVICES

On the server:

```sh
cd /home/btc-bot/btc-bot

# Install unit files
cp scripts/server/btc-bot.service /etc/systemd/system/btc-bot.service
cp scripts/server/btc-bot-dashboard.service /etc/systemd/system/btc-bot-dashboard.service

# Reload systemd and enable both services
systemctl daemon-reload
systemctl enable btc-bot btc-bot-dashboard

# Start both services
systemctl start btc-bot
systemctl start btc-bot-dashboard
```

### LOG ROTATION

On the server:

```sh
sudo cp /home/btc-bot/btc-bot/scripts/server/btc-bot-logrotate.conf /etc/logrotate.d/btc-bot
```

Rotates: `optimize_*.log`, `autoresearch_*.log`, `refresh_data_*.log`, `autoresearch_cron.log`.
Daily, 14 rotations, compressed. Does NOT rotate `btc_bot.log` (handled by Python `RotatingFileHandler`).

### SMOKE TEST

```sh
# Verify both services are running
systemctl status btc-bot
systemctl status btc-bot-dashboard

# Tail logs for 5 minutes — no crashes expected
tail -f /home/btc-bot/btc-bot/logs/btc_bot.log

# Graceful stop test
systemctl stop btc-bot
# Verify: exit 0, no SIGKILL in logs
```

---

## Dashboard access

The dashboard binds to `127.0.0.1:8080` only — it is not publicly accessible.

Access via SSH tunnel from the local machine:

```sh
ssh -L 8080:127.0.0.1:8080 btc-bot@<server-ip> -N
```

Then open `http://localhost:8080` in the browser.

Recommended: add to `~/.ssh/config` locally:

```
Host btc-bot-server
    HostName <server-ip>
    User btc-bot
    IdentityFile ~/.ssh/id_ed25519
    LocalForward 8080 127.0.0.1:8080
```

Then connect with: `ssh btc-bot-server -N`

### Starting the dashboard

The dashboard is managed by systemd (`btc-bot-dashboard.service`). For manual/tmux use:

```sh
sh scripts/server/run_dashboard.sh
```

---

## Research Lab runs

### Przed każdym runem

Refresh source data:

```sh
sh scripts/server/refresh_data.sh
```

Run Optuna optimization:

```sh
sh scripts/server/run_optimize.sh short-rebuild-v1 50 2022-01-01 2026-03-01
```

Run single-pass autoresearch:

```sh
sh scripts/server/run_autoresearch.sh --max-candidates 10
```

Defaults:
- `run_optimize.sh`: `study-name=short-rebuild-v1`, `n-trials=50`, `start-date=2022-01-01`, `end-date=2026-03-01`
- `run_autoresearch.sh`: `max-candidates=10`, `start-date=2022-01-01`, `end-date=2026-03-01`

Artifacts:
- Optimization report: `research_lab/runs/latest_report.json`
- Autoresearch loop report: `research_lab/runs/<timestamp>/loop_report.json`
- Optional approval bundle: `research_lab/runs/<timestamp>/approval_bundle/`
- Logs: `logs/refresh_data_*.log`, `logs/optimize_*.log`, `logs/autoresearch_*.log`

Note: run `refresh_data.sh` when the bot is stopped or in a low-activity window. Both the bot and refresh script write to `storage/btc_bot.db`; SQLite WAL mode handles concurrent access, but a very long refresh transaction may introduce brief latency.

### Monitorowanie

Attach to the running tmux session:

```sh
tmux attach -t research-lab
```

Quick status without attaching tmux:

```sh
sh scripts/server/status.sh
```

Useful log commands:

```sh
tail -f logs/optimize_<study>_<timestamp>.log
tail -f logs/autoresearch_<timestamp>.log
tail -f logs/refresh_data_<timestamp>.log
```

### Odbieranie wyników

Copy all Research Lab outputs back to the local machine with `rsync`:

```sh
rsync -avz --ignore-existing btc-bot@<server-ip>:/home/btc-bot/btc-bot/research_lab/runs/ ./research_lab/runs/
```

`--ignore-existing` is required — it prevents overwriting locally approved results if the server has a newer version of the same file.

Copy a single run with `scp`:

```sh
scp -r btc-bot@<server-ip>:/home/btc-bot/btc-bot/research_lab/runs/<run_id> ./research_lab/runs/<run_id>
```

### Cron (opcjonalnie)

Example crontab entry for a nightly refresh + autoresearch pass at `02:30` UTC:

```cron
30 2 * * * cd /home/btc-bot/btc-bot && /bin/sh scripts/server/refresh_data.sh && /bin/sh scripts/server/run_autoresearch.sh --max-candidates 10 >> logs/autoresearch_cron.log 2>&1
```

For long runs, keep tmux for manual control and treat cron as optional automation only.

### Czyszczenie snapshotów

Remove snapshot files older than 7 days:

```sh
sh scripts/server/cleanup_snapshots.sh
```

Force cleanup without confirmation:

```sh
sh scripts/server/cleanup_snapshots.sh 14 --force
```

The cleanup script writes an audit log to `logs/cleanup_snapshots_*.log`.

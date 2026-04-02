# Server Deployment

## Initial Setup

1. SSH onto the Hetzner server and clone or update the repo to the target path.
2. Change into the repo root:
   `cd /path/to/btc-bot`
3. Run the one-time setup:
   `sh scripts/server/setup.sh`
4. Copy the local environment file if the server should reuse the same variables:
   `scp .env user@server:/path/to/btc-bot/.env`
5. Copy the source market database used by Research Lab:
   `scp storage/btc_bot.db user@server:/path/to/btc-bot/storage/btc_bot.db`
6. Optional but recommended: create a dedicated tmux session for long runs:
   `tmux new -s research-lab`

Notes:
- `load_settings()` resolves paths from the repo root automatically. No extra path env vars are needed.
- `BOT_MODE` defaults to `PAPER`. Research Lab does not require `LIVE`.
- Current `bootstrap_history.py` uses public Binance REST endpoints, but the wrappers still load `.env` when present for operator consistency.

## Przed każdym runem

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

## Monitorowanie

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

## Odbieranie wyników

Copy all Research Lab outputs back to the local machine with `rsync`:

```sh
rsync -avz user@server:/path/to/btc-bot/research_lab/runs/ ./research_lab/runs/
```

Or copy a single run with `scp`:

```sh
scp -r user@server:/path/to/btc-bot/research_lab/runs/<run_id> ./research_lab/runs/<run_id>
```

## Cron (opcjonalnie)

Example crontab entry for a nightly refresh + autoresearch pass at `02:30` UTC:

```cron
30 2 * * * cd /path/to/btc-bot && /bin/sh scripts/server/refresh_data.sh && /bin/sh scripts/server/run_autoresearch.sh --max-candidates 10 >> logs/cron_autoresearch.log 2>&1
```

For long runs, keep tmux for manual control and treat cron as optional automation only.

## Czyszczenie

Remove snapshot files older than 7 days:

```sh
sh scripts/server/cleanup_snapshots.sh
```

Force cleanup without confirmation:

```sh
sh scripts/server/cleanup_snapshots.sh 14 --force
```

The cleanup script writes an audit log to `logs/cleanup_snapshots_*.log`.

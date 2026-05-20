# Multi-Asset Shadow Sidecar Runbook

**Status:** implementation support document for
`MULTI_ASSET_SHADOW_SIDECAR_IMPLEMENTATION_V1`.
**Scope:** dry-run validation only. This runbook does not approve deployment,
systemd enablement, PAPER orders, or LIVE orders.

## Purpose

The sidecar is an isolated observer for BTC/ETH/SOL forward diagnostics. It is
not the BTC PAPER bot and it is not a trading runtime.

The sidecar must:

- use `sidecar_main.py`, not `main.py`;
- use a lock path different from `/tmp/btc-bot-runtime.lock`;
- write only under `research_lab/shadow/`;
- place zero orders;
- avoid importing `execution/**`;
- leave `storage/btc_bot.db` untouched.

## Dry-Run Command

From the repository root:

```bash
python sidecar_main.py \
  --dry-run \
  --db-path research_lab/shadow/multi_asset_shadow.db \
  --lock-path /tmp/multi-asset-shadow.lock \
  --min-disk-free-gb 12
```

Expected output is a single JSON object with:

- `decision_rows = 3`
- `near_miss_rows = 1`
- `resource_rows = 1`
- `production_db_touched = false`

Any `production_db_touched = true` result is a hard failure.

## Day 0 Operator Checks

Before any future deployment milestone starts a service:

```bash
systemctl is-active btc-bot
ps -eo pid,ppid,lstart,cmd | grep "main.py --mode PAPER" | grep -v grep
df -h /
```

Required:

- `btc-bot` is active;
- exactly one BTC PAPER process exists;
- disk free is at least 12 GB;
- sidecar dry-run exits successfully;
- sidecar DB path resolves under `research_lab/shadow/`;
- sidecar lock is not `/tmp/btc-bot-runtime.lock`.

## Data Inspection

Inspect the dry-run database:

```bash
sqlite3 research_lab/shadow/multi_asset_shadow.db ".tables"
sqlite3 research_lab/shadow/multi_asset_shadow.db \
  "select symbol, shadow_mode, signal_blocker from shadow_decision_outcomes;"
sqlite3 research_lab/shadow/multi_asset_shadow.db \
  "select symbol, json_extract(near_miss_payload_json, '$.near_miss_diagnostics.sweep_depth_pct') from shadow_near_miss_diagnostics;"
```

Required tables:

- `shadow_runs`
- `shadow_decision_outcomes`
- `shadow_signal_candidates`
- `shadow_portfolio_decisions`
- `shadow_near_miss_diagnostics`
- `shadow_resource_samples`

## Production DB Guard

The sidecar must not open or write:

```text
storage/btc_bot.db
```

For dry-run validation, compare size and modification time before and after, or
use the built-in JSON field:

```text
production_db_touched: false
```

## Stop Conditions

Do not proceed to deployment if any of these occur:

- dry-run imports or references `execution/**`;
- sidecar DB path escapes `research_lab/shadow/`;
- sidecar lock equals `/tmp/btc-bot-runtime.lock`;
- disk free is below 12 GB;
- `production_db_touched` is true;
- BTC PAPER process count is not exactly one;
- nested `near_miss_diagnostics.sweep_depth_pct` is missing.

## Promotion Boundary

Passing dry-run validation only means the sidecar infrastructure is ready for
audit. It does not approve:

- systemd deployment;
- a long-running sidecar process;
- ETH PAPER;
- SOL PAPER;
- LIVE trading;
- threshold changes;
- changes to BTC M4 interpretation.

# Multi-Asset PAPER Activation Runbook

This runbook documents the small-step activation path for BTC/ETH/SOL PAPER.
It is not an activation approval by itself.

## Current activation posture

- Proceed consciously without fixed day-count evidence targets.
- Use explicit checkpoint gates immediately before activation.
- Keep activation reversible through the existing rollback tag and verified
  production database backup.
- Do not enable ETH/SOL PAPER by code defaults. Activation must come from the
  production runtime overlay.

## Pre-activation checks

Run these on the production server before changing `settings.json`:

```bash
cd /home/btc-bot/btc-bot
python scripts/runtime_capacity_check.py
python scripts/multi_asset_shadow_evidence_checkpoint.py --hours 2 --expected-min-cycles 6
python scripts/report_near_miss_diagnostics.py --all-symbols --days 1 --output /tmp/m4_multi_asset_pre_activation.md
```

Activation must not proceed if:

- capacity status is not `pass`;
- shadow checkpoint status is not `pass`;
- `production_db_touched_true_count` is non-zero in the fresh checkpoint window;
- production has ETH/SOL positions before activation;
- `multi_asset.enabled` is already true unexpectedly.

## Runtime overlay shape

`settings.json` is the activation surface. Example:

```json
{
  "schema_version": "v1.0",
  "multi_asset": {
    "enabled": true,
    "enabled_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "symbol_overrides": [
      {"symbol": "ETHUSDT", "min_sweep_depth_pct": 0.0075},
      {"symbol": "SOLUSDT", "min_sweep_depth_pct": 0.0075}
    ],
    "max_total_risk_pct_open": 0.007,
    "max_gross_notional_pct": 1.0,
    "max_directional_notional_pct": 0.75,
    "max_open_positions_total": 2,
    "max_open_positions_per_symbol": 1
  }
}
```

BTC inherits the existing production strategy overlay. ETH and SOL use
asset-specific sweep-depth overrides. Other symbol-specific strategy fields are
not supported by this activation contract.

## Rollback anchors

- Rollback tag: `pre-multi-asset-paper-20260521T095342Z`
- Verified quiesced database backup:
  `/home/btc-bot/backups/manual/pre_multi_asset_paper_quiesced_20260521T101101Z/btc_bot.db`

Rollback plan:

```bash
systemctl stop btc-bot.service
git reset --hard pre-multi-asset-paper-20260521T095342Z
# Restore the verified database backup only if runtime writes need reverting.
systemctl start btc-bot.service
```

## Post-activation checks

Immediately after restart:

```bash
systemctl status btc-bot.service --no-pager
python scripts/query_bot_status.py
python scripts/runtime_capacity_check.py
python scripts/report_near_miss_diagnostics.py --all-symbols --days 1 --output /tmp/m4_multi_asset_post_activation.md
```

Expected first state:

- service active with zero restart loop;
- `multi_asset.enabled=true`;
- enabled symbols are exactly BTCUSDT, ETHUSDT, SOLUSDT;
- `symbol_state` and `portfolio_state` tables may exist after the first
  multi-symbol cycle;
- ETH/SOL orders remain subject to execution allowlist, risk, and portfolio
  gate vetoes.

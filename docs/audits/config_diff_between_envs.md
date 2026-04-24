# Config Diff Between Envs

Date: 2026-04-24
Source commit: `5712fbd`

## Profile-Level Overrides From `settings.py`

| Surface | Research | Live | Experiment |
|---|---|---|---|
| `min_sweep_depth_pct` | `0.00286` | `0.0001` | `0.0001` |
| `confluence_min` | `4.5` | `4.5` | `3.6` |
| `allow_uptrend_pullback` | env-toggle allowed | forced `False` | forced `False` |
| `direction_tfi_threshold` | `0.08` | `0.08` | `0.05` |
| `direction_tfi_threshold_inverse` | `-0.05` | `-0.05` | `-0.03` |
| `tfi_impulse_threshold` | `0.13` | `0.13` | `0.10` |
| `crowded_leverage` whitelist | default | default | widened to `LONG,SHORT` |
| `risk.min_rr` | `2.1` | `2.1` | `1.6` |
| `risk.max_open_positions` | `1` | `1` | `2` |
| `risk.max_trades_per_day` | `3` | `3` | `6` |
| `cooldown_minutes_after_loss` | `95` | `95` | `30` |
| `duplicate_level_tolerance_pct` | `0.0007` | `0.0007` | `0.0004` |
| `duplicate_level_window_hours` | `114` | `114` | `24` |

## Entrypoint / Runtime Defaults

| Entrypoint | BOT_MODE behavior | Profile behavior | Notes |
|---|---|---|---|
| `load_settings()` direct call | env/default `PAPER` | default `research` | function default differs from runtime CLI default |
| `main.py` | env or `--mode` | `BOT_SETTINGS_PROFILE` default `live` | accepts only `live` or `experiment` |
| `scripts/run_paper.py` | forces `PAPER` | defaults `BOT_SETTINGS_PROFILE=live` | paper runtime can silently use live profile |
| `scripts/run_live.py` | forces `LIVE` | forces `live` | consistent wrapper |
| repo `scripts/server/btc-bot.service` | `ExecStart ... main.py --mode PAPER` | implicit via `.env` `EnvironmentFile` | no explicit `BOT_SETTINGS_PROFILE` in unit |
| deployed `btc-bot.service` | `ExecStart ... main.py --mode PAPER` | explicit `Environment="BOT_SETTINGS_PROFILE=experiment"` | production drift from repo |

## Repo vs Production Drift (Observed 2026-04-24)

### Bot service

| Surface | Repo unit | Deployed unit |
|---|---|---|
| environment source | `EnvironmentFile=/home/btc-bot/btc-bot/.env` | `Environment="BOT_SETTINGS_PROFILE=experiment"` |
| explicit profile | none | `experiment` |
| restart policy | `Restart=on-failure` | `Restart=always` |
| mode | `PAPER` | `PAPER` |

### Dashboard service

| Surface | Repo unit | Deployed unit |
|---|---|---|
| host binding | `127.0.0.1:8080` | `0.0.0.0:8080` |
| env source | `.env` `EnvironmentFile` | `.env` `EnvironmentFile` |
| restart policy | `on-failure` | `on-failure` |

## Reproducibility Gaps

- `config_hash` does not encode service-unit overrides.
- `config_snapshots` persist only `strategy_json`, not full runtime settings.
- No exact interpreter pin file exists (`.python-version` absent).
- No dependency lockfile exists.
- CI uses Python `3.11`; local audit interpreter was `3.13.1`.

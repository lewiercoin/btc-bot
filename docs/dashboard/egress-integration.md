# Dashboard: Egress Health Integration

## Overview

The Egress Health panel displays live status of the Vultr SOCKS5 proxy (ProxyTransport layer) directly in the dashboard. No changes were made to `ProxyTransport`, `orchestrator.py`, or any core/execution layer.

## Architecture

```
Bot process (systemd)          Dashboard process (uvicorn)
  └── ProxyTransport               └── /api/egress endpoint
        logs events ──→ btc_bot.log ──→ _parse_egress_events()
                                         + settings.proxy (env vars)
                                         + DashboardReader (safe_mode)
```

**Data sources:**
- **Static config** — `settings.proxy` (read from `.env` at dashboard startup): `proxy_enabled`, `proxy_type`, `proxy_url`, `sticky_minutes`
- **Dynamic events** — tail of `logs/btc_bot.log` (last 256 KB): session start/reinit, CloudFront bans, proxy rotations
- **Safe mode** — `bot_state` table via `DashboardReader`

## API

### `GET /api/egress`

```json
{
  "proxy_enabled": true,
  "proxy_type": "socks5",
  "proxy_host": "80.240.17.161",
  "proxy_port": 1080,
  "sticky_minutes": 60,
  "failover_count": 0,
  "last_session_start": "2026-04-14T09:22:35+00:00",
  "session_age_minutes": 68.2,
  "fail_count_24h": 0,
  "last_ban_at": null,
  "last_rotation_at": null,
  "safe_mode": false,
  "safe_mode_reason": null
}
```

**Fields:**

| Field | Source | Description |
|---|---|---|
| `proxy_enabled` | `.env PROXY_ENABLED` | Whether proxy is active |
| `proxy_type` | `.env PROXY_TYPE` | `socks5` or `http` |
| `proxy_host` | `.env PROXY_URL` | Exit node IP |
| `proxy_port` | `.env PROXY_URL` | Port (parsed from `host:port`) |
| `sticky_minutes` | `.env PROXY_STICKY_MINUTES` | Session duration |
| `failover_count` | `.env PROXY_FAILOVER_LIST` | Number of backup proxies |
| `last_session_start` | Log parsing | Last `Proxy transport enabled` or `Proxy session expired, reinitializing` event |
| `session_age_minutes` | Derived | Minutes since `last_session_start` |
| `fail_count_24h` | Log parsing | Count of `CloudFront ban detected` events in last 24h |
| `last_ban_at` | Log parsing | Timestamp of last CloudFront ban |
| `last_rotation_at` | Log parsing | Timestamp of last proxy rotation |
| `safe_mode` | SQLite `bot_state` | Current safe mode status |
| `safe_mode_reason` | SQLite `bot_state` | Last recorded safe mode reason |

## Frontend

### Safe Mode Alert Banner

Appears at top of dashboard when `safe_mode = true`. Red banner with reason text. Updated every 5s via `/api/status` and every 10s via `/api/egress`.

### Egress Health Panel

Positioned between Open Positions and Recent Trades. Multi-column stat grid. Auto-refreshes every **10 seconds**.

**Color coding:**
- `Proxy enabled`: green badge (Yes) / amber badge (No)
- `Bans detected (24h)`: red badge if > 0, plain text if 0
- `Safe mode`: amber badge (Active) / green badge (Off)

## Log Events Parsed

| Log pattern | Action |
|---|---|
| `Proxy transport enabled` | Sets `last_session_start` |
| `Proxy session expired, reinitializing` | Sets `last_session_start` |
| `CloudFront ban detected` | Increments `fail_count_24h`, sets `last_ban_at` |
| `Proxy rotation:` | Sets `last_rotation_at` |

## Files Modified

| File | Change |
|---|---|
| `dashboard/server.py` | Added `_tail_lines()`, `_extract_log_ts()`, `_parse_egress_events()`, `/api/egress` endpoint; stored `settings` in `app.state`; bumped version to m4 |
| `dashboard/static/index.html` | Added safe-mode alert banner, Egress Health panel |
| `dashboard/static/app.js` | Added `renderEgress()`, `refreshEgress()`, `updateSafeModeAlert()`, 10s interval |
| `dashboard/static/style.css` | Added `.safe-mode-alert`, `.panel--egress .stat-list` styles |

## No Changes To

- `data/proxy_transport.py`
- `orchestrator.py`
- `core/**`
- `execution/**`
- `settings.py`
- SQLite schema

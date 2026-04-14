# Egress Node: Vultr SOCKS5 Exit Proxy

## Purpose

Dedicated SOCKS5 exit node to bypass Binance CloudFront IP blocking on the Hetzner server (`204.168.146.253`). All Binance REST API traffic is routed through this Vultr node.

## Infrastructure

| Parameter | Value |
|---|---|
| Provider | Vultr |
| Public IP | `80.240.17.161` |
| SOCKS5 Port | `1080` |
| Daemon | `dante-server` v1.4.2 |
| OS | Ubuntu 22.04 |
| Allowed client | `204.168.146.253` (Hetzner only) |

## Verified Endpoints (2026-04-14)

| Endpoint | Result |
|---|---|
| `GET /fapi/v1/ping` | HTTP 200 ✅ |
| `GET /fapi/v1/time` | HTTP 200 ✅ |
| `GET /fapi/v1/ticker/bookTicker?symbol=BTCUSDT` | HTTP 200 ✅ |
| `GET /fapi/v1/exchangeInfo` | HTTP 404 (CloudFront – non-critical) |

## Configuration

### Vultr Server (`/etc/danted.conf`)

```
logoutput: syslog
internal: 80.240.17.161 port = 1080
external: enp1s0
clientmethod: none
socksmethod: none
user.notprivileged: nobody

client pass {
    from: 204.168.146.253/32 to: 0.0.0.0/0
    log: connect disconnect
}

client block {
    from: 0.0.0.0/0 to: 0.0.0.0/0
    log: connect
}

socks pass {
    from: 0.0.0.0/0 to: 0.0.0.0/0
    protocol: tcp
    log: connect disconnect
}
```

### Vultr UFW Firewall Rules

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow from 204.168.146.253 to any port 1080 proto tcp  # Hetzner SOCKS5
ufw allow 22/tcp                                             # SSH
ufw enable
```

### Hetzner `.env` Configuration

```bash
PROXY_ENABLED=true
PROXY_URL=80.240.17.161:1080
PROXY_TYPE=socks5
PROXY_STICKY_MINUTES=60
PROXY_FAILOVER_LIST=
```

## Verification Commands

Run from Hetzner (`204.168.146.253`):

```bash
# Test SOCKS5 tunnel
curl --socks5-hostname 80.240.17.161:1080 -I https://fapi.binance.com/fapi/v1/ping

# Test bookTicker
curl --socks5-hostname 80.240.17.161:1080 -o /dev/null -w "HTTP %{http_code}\n" \
  "https://fapi.binance.com/fapi/v1/ticker/bookTicker?symbol=BTCUSDT"

# Check danted is running on Vultr
ssh root@80.240.17.161 "systemctl status danted --no-pager"

# Check bot logs for proxy confirmation
journalctl -u btc-bot -n 20 --no-pager | grep -E "(Proxy|proxy|safe mode)"
```

## Health Check

Expected log line on bot startup:
```
INFO | orchestrator | Proxy transport enabled: type=socks5, sticky=60 min, failover_count=0
```

No `REST retry` or `ProxyError` messages = proxy is healthy.

## Daemon Management (on Vultr)

```bash
# Status
systemctl status danted

# Restart
systemctl restart danted

# View logs
journalctl -u danted -n 50 --no-pager

# View live connections
journalctl -u danted -f
```

## Destroy Instructions

If this node is no longer needed:

1. Disable proxy in Hetzner `.env`:
   ```bash
   sed -i 's/PROXY_ENABLED=true/PROXY_ENABLED=false/' /home/btc-bot/btc-bot/.env
   systemctl restart btc-bot
   ```

2. Destroy the Vultr instance from the Vultr dashboard (IP: `80.240.17.161`).

3. Remove this file from the repo if the node is permanently decommissioned.

## Notes

- `exchangeInfo` is still blocked on the Vultr exit IP by CloudFront. This endpoint is not in the bot's critical runtime loop (bookTicker, time, ping all work).
- No bot code was modified as part of this milestone. ProxyTransport handles SOCKS5 natively via `PROXY_TYPE=socks5`.
- UFW allows only `204.168.146.253` on port 1080 — unauthorized IPs will be blocked.

# Safe Mode Diagnostic Guide

This guide provides step-by-step instructions for diagnosing why the BTC bot remains in safe mode.

## Quick Start

Run the diagnostic script on the production server (Hetzner):

```bash
ssh -i btc-bot-deploy root@204.168.146.253
cd /home/btc-bot/btc-bot
bash scripts/diagnostics/check_safe_mode.sh
```

The script will output diagnostic information for:
1. Service status (btc-bot.service, btc-bot-dashboard.service)
2. Bot log (last 100 lines)
3. Dashboard API: Egress Health
4. Dashboard API: Server Resources
5. Database: bot_state table
6. WebSocket URL configuration
7. Recent WebSocket connection attempts

---

## Manual Step-by-Step Diagnostics

If you prefer to run commands individually, copy-paste each section below.

### 1. Check Service Status

```bash
systemctl status btc-bot.service --no-pager -l
systemctl status btc-bot-dashboard.service --no-pager -l
```

**What to look for:**
- Service should be "active (running)"
- If "failed" or "inactive", check the logs
- Look for recent restarts or crash loops

### 2. Check Bot Log

```bash
tail -100 /home/btc-bot/btc-bot/logs/bot.log
```

**What to look for:**
- WebSocket connection errors
- "safe_mode" messages
- Egress proxy errors
- Database connection issues
- Recent error messages

### 3. Check Dashboard Egress Health

```bash
curl -s http://localhost:8080/api/egress | python3 -m json.tool
```

**What to look for:**
- `safe_mode` field: should be `false` for normal operation
- `enabled`: should be `true` if proxy is configured
- `fail_count`: should be low (0-3 is acceptable)
- `last_ban`: check timestamp if not null
- `session_age`: should not be excessively long

### 4. Check Dashboard Server Resources

```bash
curl -s http://localhost:8080/api/server-resources | python3 -m json.tool
```

**What to look for:**
- `cpu_percent`: should be < 80% (warning if >80%, critical if >95%)
- `memory_percent`: should be < 80% (warning if >80%, critical if >95%)
- `disk_percent`: should be < 80% (warning if >80%, critical if >95%)
- High resource usage may cause bot instability

### 5. Check Database bot_state

```bash
sqlite3 /home/btc-bot/btc-bot/storage/btc_bot.db "SELECT key, value, updated_at FROM bot_state ORDER BY key;"
```

**What to look for:**
- `safe_mode` key: value should be `false`
- Check `updated_at` timestamps for stale state
- Look for unexpected keys or values

### 6. Check WebSocket URL Configuration

```bash
grep -A 1 "futures_ws_market_base_url" /home/btc-bot/btc-bot/settings.py
grep -A 1 "futures_ws_stream_base_url" /home/btc-bot/btc-bot/settings.py
```

**What to look for:**
- `futures_ws_market_base_url`: should be `wss://fstream.binance.com/market`
- `futures_ws_stream_base_url`: should be `wss://fstream.binance.com/stream`
- Verify URLs are correct (no typos)

### 7. Check WebSocket Connection Attempts

```bash
tail -100 /home/btc-bot/btc-bot/logs/bot.log | grep -i "websocket\|market\|stream"
```

**What to look for:**
- "Connected websocket stream (market):" — successful connection to new path
- "Connected websocket stream (legacy):" — fallback to old path
- "Falling back to legacy /stream/ path" — new path failed, using fallback
- Connection errors or timeouts

---

## Common Safe Mode Causes

### WebSocket Connection Failure

**Symptoms:**
- Log shows "Websocket stream failure"
- No "Connected websocket stream" messages
- Bot cannot receive live market data

**Diagnosis:**
- Check section 7 (WebSocket connection attempts)
- Verify WebSocket URLs in section 6
- Check if fallback to legacy path was triggered

**Resolution:**
- If new `/market/` path fails, bot should automatically fallback to `/stream/`
- If both fail, check network connectivity to Binance
- Verify firewall rules allow WebSocket connections

### Egress Proxy Issues

**Symptoms:**
- Dashboard shows `safe_mode: true`
- Egress API shows high `fail_count`
- Log shows proxy connection errors

**Diagnosis:**
- Check section 3 (Egress Health)
- Look for `last_ban` timestamp
- Check bot log for proxy errors

**Resolution:**
- Check exit node status
- Verify proxy configuration in `.env`
- Consider switching to backup proxy from `PROXY_FAILOVER_LIST`

### Resource Exhaustion

**Symptoms:**
- High CPU/Memory/Disk usage in section 4
- Bot crashes or becomes unresponsive
- Log shows out-of-memory errors

**Diagnosis:**
- Check section 4 (Server Resources)
- Look for >95% resource usage

**Resolution:**
- Restart bot service to free memory
- Consider upgrading server resources
- Check for memory leaks in logs

### Database Corruption

**Symptoms:**
- Section 5 (bot_state) query fails
- Bot cannot read/write state
- Log shows database errors

**Diagnosis:**
- Check section 5 (Database)
- Verify database file exists and is readable

**Resolution:**
- Restore from backup if available
- Reinitialize database (CAUTION: data loss risk)

---

## Next Steps After Diagnosis

After running diagnostics, share the output with Grok for analysis. The output will help identify:

1. Whether the issue is WebSocket-related
2. Whether the issue is egress proxy-related
3. Whether the issue is resource-related
4. Whether the issue is database-related

Based on the diagnosis, Grok will recommend the appropriate fix milestone.

---

## Important Notes

- This script is **read-only** — it will not modify any state or restart services
- Always run diagnostics before attempting manual fixes
- Share full diagnostic output when requesting help
- Do not restart services without understanding the root cause

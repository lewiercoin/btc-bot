#!/bin/bash
# Safe Mode Diagnostic Script for BTC Bot
# Read-only diagnostic commands to troubleshoot why bot is in safe mode
# Usage: bash scripts/diagnostics/check_safe_mode.sh
# Or copy-paste individual commands from this script

set -e

echo "=========================================="
echo "BTC BOT SAFE MODE DIAGNOSTIC CHECK"
echo "=========================================="
echo ""

# 1. Service Status
echo "=== 1. SERVICE STATUS ==="
echo "btc-bot.service status:"
systemctl status btc-bot.service --no-pager -l || echo "Service not found or failed"
echo ""
echo "btc-bot-dashboard.service status:"
systemctl status btc-bot-dashboard.service --no-pager -l || echo "Service not found or failed"
echo ""

# 2. Bot Log (last 100 lines)
echo "=== 2. BOT LOG (LAST 100 LINES) ==="
if [ -f "/home/btc-bot/btc-bot/logs/bot.log" ]; then
    tail -100 /home/btc-bot/btc-bot/logs/bot.log
else
    echo "Bot log not found at /home/btc-bot/btc-bot/logs/bot.log"
fi
echo ""

# 3. Dashboard API: Egress Health
echo "=== 3. DASHBOARD API: EGRESS HEALTH ==="
curl -s http://localhost:8080/api/egress | python3 -m json.tool 2>/dev/null || echo "Dashboard not running or egress endpoint failed"
echo ""

# 4. Dashboard API: Server Resources
echo "=== 4. DASHBOARD API: SERVER RESOURCES ==="
curl -s http://localhost:8080/api/server-resources | python3 -m json.tool 2>/dev/null || echo "Dashboard not running or server-resources endpoint failed"
echo ""

# 5. Database: bot_state table
echo "=== 5. DATABASE: BOT_STATE TABLE ==="
if [ -f "/home/btc-bot/btc-bot/storage/btc_bot.db" ]; then
    sqlite3 /home/btc-bot/btc-bot/storage/btc_bot.db "SELECT key, value, updated_at FROM bot_state ORDER BY key;" 2>/dev/null || echo "DB query failed"
else
    echo "Database not found at /home/btc-bot/btc-bot/storage/btc_bot.db"
fi
echo ""

# 6. WebSocket URL Configuration
echo "=== 6. WEBSOCKET URL CONFIGURATION ==="
if [ -f "/home/btc-bot/btc-bot/settings.py" ]; then
    echo "Market base URL from settings.py:"
    grep -A 1 "futures_ws_market_base_url" /home/btc-bot/btc-bot/settings.py || echo "Not found"
    echo ""
    echo "Stream base URL from settings.py:"
    grep -A 1 "futures_ws_stream_base_url" /home/btc-bot/btc-bot/settings.py || echo "Not found"
else
    echo "settings.py not found at /home/btc-bot/btc-bot/settings.py"
fi
echo ""

# 7. Recent WebSocket connection attempts (from log)
echo "=== 7. RECENT WEBSOCKET CONNECTION ATTEMPTS ==="
if [ -f "/home/btc-bot/btc-bot/logs/bot.log" ]; then
    echo "Last 20 lines mentioning 'websocket' or 'market' or 'stream':"
    tail -100 /home/btc-bot/btc-bot/logs/bot.log | grep -i "websocket\|market\|stream" || echo "No websocket-related log entries found"
else
    echo "Bot log not found"
fi
echo ""

echo "=========================================="
echo "DIAGNOSTIC CHECK COMPLETE"
echo "=========================================="

#!/usr/bin/env bash
# Check production-repo configuration drift
# Usage: ./scripts/check_production_drift.sh

set -euo pipefail

SSH_KEY="${SSH_KEY:-btc-bot-deploy-v2}"
SSH_HOST="root@204.168.146.253"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Production-Repo Configuration Drift Check ==="
echo

# Check btc-bot.service
echo "Checking btc-bot.service..."
DEPLOYED_UNIT=$(ssh -i "$REPO_ROOT/$SSH_KEY" "$SSH_HOST" "systemctl cat btc-bot.service 2>/dev/null | grep -v '^#' | grep -v '^$'" || echo "NOT_DEPLOYED")
REPO_UNIT=$(grep -v '^#' "$REPO_ROOT/ops/systemd/btc-bot.service" | grep -v '^$')

if [ "$DEPLOYED_UNIT" = "NOT_DEPLOYED" ]; then
    echo "  ❌ btc-bot.service: NOT DEPLOYED on production"
elif [ "$DEPLOYED_UNIT" = "$REPO_UNIT" ]; then
    echo "  ✅ btc-bot.service: IN SYNC"
else
    echo "  ⚠️  btc-bot.service: DRIFT DETECTED"
    echo "     Run: diff <(ssh -i $SSH_KEY $SSH_HOST systemctl cat btc-bot.service) ops/systemd/btc-bot.service"
fi

# Check btc-bot-dashboard.service
echo "Checking btc-bot-dashboard.service..."
DEPLOYED_DASH=$(ssh -i "$REPO_ROOT/$SSH_KEY" "$SSH_HOST" "systemctl cat btc-bot-dashboard.service 2>/dev/null | grep -v '^#' | grep -v '^$'" || echo "NOT_DEPLOYED")
REPO_DASH=$(grep -v '^#' "$REPO_ROOT/ops/systemd/btc-bot-dashboard.service" | grep -v '^$')

if [ "$DEPLOYED_DASH" = "NOT_DEPLOYED" ]; then
    echo "  ❌ btc-bot-dashboard.service: NOT DEPLOYED on production"
elif [ "$DEPLOYED_DASH" = "$REPO_DASH" ]; then
    echo "  ✅ btc-bot-dashboard.service: IN SYNC"
else
    echo "  ⚠️  btc-bot-dashboard.service: DRIFT DETECTED"
    echo "     Run: diff <(ssh -i $SSH_KEY $SSH_HOST systemctl cat btc-bot-dashboard.service) ops/systemd/btc-bot-dashboard.service"
fi

# Check Python version
echo "Checking Python version..."
LOCAL_PYTHON=$(cat "$REPO_ROOT/.python-version" 2>/dev/null || echo "NOT_SET")
PROD_PYTHON=$(ssh -i "$REPO_ROOT/$SSH_KEY" "$SSH_HOST" "python3 --version | awk '{print \$2}'")

if [ "$LOCAL_PYTHON" = "$PROD_PYTHON" ]; then
    echo "  ✅ Python version: $PROD_PYTHON (IN SYNC)"
else
    echo "  ⚠️  Python version: DRIFT DETECTED"
    echo "     .python-version: $LOCAL_PYTHON"
    echo "     Production: $PROD_PYTHON"
fi

echo
echo "=== End of Drift Check ==="

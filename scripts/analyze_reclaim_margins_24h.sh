#!/bin/bash
# Analysis script for RECLAIM-DIAGNOSTICS milestone
# Run after 24-48h of data collection
# Author: Perplexity (2026-04-18)
# Usage: bash analyze_reclaim_margins_24h.sh

ssh -i c:/development/btc-bot/btc-bot-deploy root@204.168.146.253 '
cd /home/btc-bot/btc-bot

echo "=== KUBEŁKI CLOSE_VS_BUF_ATR (no_reclaim cases) ==="
journalctl -u btc-bot.service --since "2026-04-18 22:45:00 UTC" --no-pager \
  | grep "blocked_by=no_reclaim" \
  | grep -oP "close_vs_buf_atr=\K-?[0-9.]+" \
  | awk "{
      if (\$1 >= 0) b[\"pass (>=0)\"]++
      else if (\$1 >= -0.1) b[\"very close (-0.1..0)\"]++
      else if (\$1 >= -0.3) b[\"close (-0.3..-0.1)\"]++
      else if (\$1 >= -0.5) b[\"medium (-0.5..-0.3)\"]++
      else b[\"far (<-0.5)\"]++
    } END { for (k in b) print b[k], k }" \
  | sort -rn

echo ""
echo "=== KUBEŁKI WICK_VS_MIN_ATR (no_reclaim cases) ==="
journalctl -u btc-bot.service --since "2026-04-18 22:45:00 UTC" --no-pager \
  | grep "blocked_by=no_reclaim" \
  | grep -oP "wick_vs_min_atr=\K-?[0-9.]+" \
  | awk "{
      if (\$1 >= 0) b[\"pass (>=0)\"]++
      else if (\$1 >= -0.05) b[\"very close\"]++
      else if (\$1 >= -0.15) b[\"close\"]++
      else b[\"far\"]++
    } END { for (k in b) print b[k], k }" \
  | sort -rn

echo ""
echo "=== CZY JAKIKOLWIEK CYKL MIAŁ OBA MARGIN >= 0 ALE JEDNAK no_reclaim? (BUG SIGNAL) ==="
journalctl -u btc-bot.service --since "2026-04-18 22:45:00 UTC" --no-pager \
  | grep "blocked_by=no_reclaim" \
  | awk -F"|" "{
      close_ok=0; wick_ok=0
      for(i=1;i<=NF;i++){
        if(\$i ~ /close_vs_buf_atr=/){v=\$i; gsub(/.*close_vs_buf_atr=/,\"\",v); if(v+0 >= 0) close_ok=1}
        if(\$i ~ /wick_vs_min_atr=/){v=\$i; gsub(/.*wick_vs_min_atr=/,\"\",v); if(v+0 >= 0) wick_ok=1}
      }
      if (close_ok && wick_ok) print
    }" | head -5

echo ""
echo "=== SWEEP SIDE DISTRIBUTION ==="
journalctl -u btc-bot.service --since "2026-04-18 22:45:00 UTC" --no-pager \
  | grep "Decision diagnostics" | grep -oP "sweep_side=\K\w+" | sort | uniq -c
'

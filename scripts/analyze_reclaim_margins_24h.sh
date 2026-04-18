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

echo ""
echo "=== CLOSE_VS_BUF_ATR BREAKDOWN BY REGIME (no_reclaim cases) ==="
journalctl -u btc-bot.service --since "2026-04-18 22:45:00 UTC" --no-pager \
  | grep "blocked_by=no_reclaim" \
  | awk -F"|" "{
      regime=\"unknown\"; close_margin=\"none\"
      for(i=1;i<=NF;i++) {
        if(\$i ~ /regime=/) {gsub(/.*regime=/,\"\",\$i); gsub(/ .*/,\"\",\$i); regime=\$i}
        if(\$i ~ /close_vs_buf_atr=/) {gsub(/.*close_vs_buf_atr=/,\"\",\$i); gsub(/ .*/,\"\",\$i); close_margin=\$i}
      }
      print regime, close_margin
    }" \
  | awk "{
      regime=\$1; margin=\$2+0
      count[regime]++
      if (margin >= 0) bucket[regime][\"pass\"]++
      else if (margin >= -0.1) bucket[regime][\"very_close\"]++
      else if (margin >= -0.3) bucket[regime][\"close\"]++
      else if (margin >= -0.5) bucket[regime][\"medium\"]++
      else bucket[regime][\"far\"]++
    } END {
      for (r in count) {
        print \"\"
        print \"Regime:\", r, \"(total:\", count[r], \")\"
        for (b in bucket[r]) print \"  \", bucket[r][b], b
      }
    }"

echo ""
echo "=== CLOSE_VS_BUF_ATR BY TIME OF DAY (UTC, no_reclaim cases) ==="
journalctl -u btc-bot.service --since "2026-04-18 22:45:00 UTC" --no-pager \
  | grep "blocked_by=no_reclaim" \
  | awk "{
      timestamp=\$1\" \"\$2\" \"\$3
      cmd=\"date -d \\\"\"timestamp\"\\\" +%H 2>/dev/null\"
      cmd | getline hour
      close(cmd)
      if (hour >= 13 && hour <= 21) period=\"US_hours(13-21UTC)\"
      else if (hour >= 23 || hour <= 6) period=\"Asia_hours(23-06UTC)\"
      else period=\"EU_hours(07-12UTC)\"
    }
    /close_vs_buf_atr=/ {
      gsub(/.*close_vs_buf_atr=/,\"\")
      gsub(/[^-0-9.].*/,\"\")
      margin=\$0+0
      count[period]++
      if (margin >= 0) bucket[period][\"pass\"]++
      else if (margin >= -0.1) bucket[period][\"very_close\"]++
      else if (margin >= -0.3) bucket[period][\"close\"]++
      else if (margin >= -0.5) bucket[period][\"medium\"]++
      else bucket[period][\"far\"]++
    } END {
      for (p in count) {
        print \"\"
        print p, \"(total:\", count[p], \")\"
        for (b in bucket[p]) print \"  \", bucket[p][b], b
      }
    }"
'

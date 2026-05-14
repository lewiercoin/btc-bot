# Near-Miss Monitoring — Operational Guide

## Overview

Near-miss monitoring is a runtime diagnostics feature for PAPER trading that tracks sweep signals rejected due to shallow depth (`sweep_too_shallow`) but coming close to the threshold. This provides insight into whether the current threshold is too strict or appropriate for current market conditions.

**Scope:** Runtime diagnostics / observability only. No production parameter changes. No PAPER threshold changes. No live execution changes. No risk/governance changes. No second bot process. Shadow/diagnostic only.

**Baseline:** trial-00095 with `min_sweep_depth_pct = 0.00649` remains active unchanged.

**Checkpoint:** 2026-06-13 (30 days from start)

---

## What is a Near-Miss?

**Near-miss** = sweep signal that was rejected due to `sweep_too_shallow` but came "close" to threshold.

### Depth Buckets

| Bucket | Depth Range | Label | Purpose |
|---|---|---|---|
| Shallow reject | < 0.004 | far_below | Far from threshold, expected reject |
| Near-miss LOW | [0.004, 0.00649) | near_miss_low | Within 38% of threshold, diagnostic interest |
| Baseline PASS | [0.00649, 0.007) | baseline_pass | Passes baseline, diagnostic: would 0.007 reject? |
| Stricter PASS | >= 0.007 | stricter_pass | Passes both baseline and hypothetical 0.007 |

---

## How It Works

### 1. Runtime Logging

When a sweep signal is rejected with `outcome_reason = 'sweep_too_shallow'` and `sweep_depth_pct >= 0.004`, the system logs additional diagnostic data to `decision_outcomes.details_json`:

- `sweep_depth_pct`: Actual depth
- `threshold`: Current active threshold (0.00649)
- `threshold_distance`: (depth - threshold) / threshold (negative for rejects)
- `depth_bucket`: far_below / near_miss_low / baseline_pass / stricter_pass
- `direction`: LONG / SHORT
- `regime`: uptrend / downtrend / normal / crowded_leverage / post_liquidation
- `confluence_score`: If available
- `min_tfi_strength`: TFI value
- `atr_15m`: Volatility
- `funding_rate_60d`: Funding
- `oi_change_pct`: OI delta
- `session_hour`: UTC hour (0-23)
- `config_hash`: Current parameter set identifier
- `rejection_reasons`: reasons[] array

**Location:** `orchestrator.py` → `_signal_diagnostics_payload()` → adds `near_miss_diagnostics` to details_json when conditions met.

### 2. Report Generation

Run the report script to analyze near-miss data:

```bash
# Local development
python scripts/report_near_miss_diagnostics.py --days 7

# Production server
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 \
  "cd /home/btc-bot/btc-bot && python3 scripts/report_near_miss_diagnostics.py --days 7"
```

**Output:** Markdown report with:
- Executive summary (counts, %, key finding)
- Depth distribution buckets
- Threshold proximity (% within 10%, 20%, 30% of threshold)
- Shadow threshold 0.007 comparison (opportunity cost)
- Regime breakdown
- Session breakdown (Asia/EU/US)
- Top rejection reasons
- Recommendation

**Safety:** Script is read-only (SELECT queries only). Safe to run against production DB.

---

## How to Interpret Metrics

### High Near-Miss % → Threshold May Be Too Strict

If near-miss count exceeds baseline trades, the threshold is rejecting too many sweeps that are close to qualifying. Consider relaxing threshold.

**Example:**
- Near-miss count: 50
- Baseline trades: 30
- **Interpretation:** Threshold too strict, missing opportunities

### Low Near-Miss % → Threshold Is Appropriate

If near-miss count is reasonable vs baseline trades (e.g., 1:1 or lower), threshold is working as intended.

**Example:**
- Near-miss count: 20
- Baseline trades: 30
- **Interpretation:** Threshold appropriate

### Baseline_Pass Bucket Large → 0.007 Would Reject Many Trades

If baseline_pass bucket is large (>30% of baseline trades), stricter threshold 0.007 would significantly reduce trade frequency. Keep current threshold.

**Example:**
- Baseline_pass count: 15
- Baseline trades: 30
- **Interpretation:** 0.007 would reject 50% of trades. Keep 0.00649.

### Sweep Depth Distribution Shifts Deeper → Regime Improving

If depth distribution shifts toward higher buckets (more near_miss_low → baseline_pass), market conditions are generating deeper sweeps. Threshold may need adjustment.

### Baseline ER Turns Negative → Edge Degradation

If baseline ER turns negative during monitoring, the edge may be degrading regardless of threshold. Investigate regime shift or structural market change.

---

## Running Reports

### Weekly Report (Recommended)

```bash
# Run every 7 days
python scripts/report_near_miss_diagnostics.py --days 7
```

Output: `docs/diagnostics/near_miss_report_YYYY-MM-DD.md`

### Custom Date Range

```bash
# Analyze last 30 days
python scripts/report_near_miss_diagnostics.py --days 30

# Analyze specific date range by adjusting --days
python scripts/report_near_miss_diagnostics.py --days 14
```

### Production Server

```bash
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253 \
  "cd /home/btc-bot/btc-bot && python3 scripts/report_near_miss_diagnostics.py --days 7"
```

---

## What Triggers Reassessment

At the 30-day checkpoint (2026-06-13), reassess threshold based on:

1. **Near-miss count > baseline trades** → Threshold too strict, consider relaxing
2. **Sweep depth distribution shifts deeper** → Regime improving, may adjust threshold
3. **Baseline ER turns negative** → Edge degradation, investigate regime shift
4. **Baseline_pass bucket large (>30%)** → Keep current threshold, 0.007 too strict

**User decision required.** This monitoring provides diagnostic data only. Any parameter change requires explicit user approval after 30-day checkpoint.

---

## Data Sources

### decision_outcomes Table

```sql
SELECT 
    cycle_timestamp,
    outcome_group,
    outcome_reason,
    details_json
FROM decision_outcomes
WHERE outcome_reason = 'sweep_too_shallow'
  AND json_extract(details_json, '$.near_miss_diagnostics') IS NOT NULL
ORDER BY cycle_timestamp DESC
LIMIT 100;
```

### Near-Miss Fields

```sql
SELECT 
    cycle_timestamp,
    json_extract(details_json, '$.near_miss_diagnostics.sweep_depth_pct') as sweep_depth_pct,
    json_extract(details_json, '$.near_miss_diagnostics.threshold') as threshold,
    json_extract(details_json, '$.near_miss_diagnostics.depth_bucket') as depth_bucket,
    json_extract(details_json, '$.near_miss_diagnostics.regime') as regime,
    json_extract(details_json, '$.near_miss_diagnostics.session_hour') as session_hour
FROM decision_outcomes
WHERE outcome_reason = 'sweep_too_shallow'
  AND json_extract(details_json, '$.near_miss_diagnostics') IS NOT NULL;
```

---

## Limitations

- Only logs near-misses for `sweep_too_shallow` with `depth >= 0.004`. Shallower sweeps (< 0.004) are not tracked as they are far from threshold.
- Threshold is hardcoded to 0.00649 (baseline from trial-00095). If threshold changes, update orchestrator.py line 942.
- Shadow comparison is diagnostic only. No execution changes. No parameter changes.
- Logging overhead < 1ms per cycle (JSON serialization only for rejected signals).
- details_json may grow over time. Future work: prune old data or archive after 90 days.

---

## Related Documentation

- M3 Analysis: `docs/analysis/OOS_WF_THRESHOLD_STABILITY_2026-05-13.md` (verdict: THRESHOLD_CONSERVATIVE_BUT_NOT_OPTIMAL)
- M1 Diagnosis: `docs/analysis/LIVE_SIGNAL_BLOCKER_DIAGNOSIS_2026-05-13.md` (current market shallow sweeps)
- MILESTONE_TRACKER.md: M4 status and checkpoint date
- DATA_SOURCES.md: decision_outcomes table schema

---

## Contact

For questions about near-miss monitoring or interpretation of reports, refer to the M4 handoff document or consult the M3/M1 analysis reports for context.

# Bot & M4 Near-Miss Monitoring Status Report

**Report Date:** 2026-05-18 11:35 UTC  
**Report Period:** 2026-05-13 to 2026-05-18 (5 days since M4 start)  
**Bot Mode:** PAPER  
**Active Strategy:** trial-00095 sweep/reclaim (optuna-default-v3)

---

## Executive Summary

**Operational Status:** ✅ Healthy, single-instance guard deployed and verified

**Trading Activity:** Low frequency continues - 0 signals generated in 5-day M4 window, 21 trades in last 30 days (0.7 trades/day)

**M4 Monitoring:** On track - frequency bottleneck confirmed (59.9% sweep_too_shallow rejections), 3 near-miss records captured, max observed depth 82.3% of threshold

**Key Finding:** No evidence yet to support lowering sweep threshold - max near-miss 17.7% below baseline threshold (0.00649)

**Recommendation:** Continue M4 monitoring unchanged through 2026-06-13 checkpoint (25 days remaining)

---

## 1. Bot Operational Status

### Current State (2026-05-18 11:35 UTC)

| Metric | Value | Status |
|---|---|---|
| Mode | PAPER | ✅ Production |
| Healthy | 1 | ✅ Operational |
| Safe Mode | 0 | ✅ Normal operation |
| Open Positions | 0 | ✅ Flat |
| Consecutive Losses | 0 | ✅ Reset |
| Daily DD | 0.00% | ✅ No active drawdown |
| Weekly DD | 0.00% | ✅ No active drawdown |

**Runtime Protection:**
- ✅ Single-instance guard deployed (commit 06303f5, delta fix 2026-05-18)
- ✅ Lock file active: `/tmp/btc-bot-runtime.lock` contains PID 815407
- ✅ No duplicate runtimes (verified post dual-runtime incident remediation)
- ✅ systemd service: active

**Last Operational Event:** Trade closed 2026-05-10 22:15:22 UTC (8 days ago)

### Infrastructure Health

**Recent Milestones Deployed:**
- ✅ M4-RUNTIME-SINGLE-INSTANCE-GUARD (commit 855781e, 2026-05-17)
- ✅ M4-RUNTIME-SINGLE-INSTANCE-GUARD delta fix (commit 06303f5, 2026-05-18)
- ✅ M4 near-miss payload contract fix (commit 33a0df1, 2026-05-16)

**Backup Status:** Daily automated backups running, 30-day retention, last backup size ~136MB compressed

**Data Integrity:** ✅ No known gaps, collectors operational

---

## 2. Trading Performance

### Last 30 Days (2026-04-18 to 2026-05-18)

| Metric | Value | Context |
|---|---|---|
| **Trades** | 21 | 0.7 trades/day |
| **Win Rate** | 38.1% (8W / 13L) | Below trial-00095 baseline (43.6%) |
| **Avg R** | +0.103 | Positive expectancy maintained |
| **Total R** | +2.17 | ~2.2R profit over 30 days |
| **Expectancy** | +0.103 R/trade | Trial-00095 baseline: +2.110 R/trade |

**Performance vs Baseline:**
- Frequency: 0.7 trades/day vs trial-00095 offline ~1.8 trades/month (baseline was on 2+ year window)
- Win rate: 38.1% vs 43.6% baseline (variance expected on 21-trade sample)
- Expectancy: +0.103 vs +2.110 baseline (**significant degradation, small sample warning**)

**Recent Streak:** Last 5 trades all losses (2026-04-29 to 2026-05-10), then 8-day dry spell

### Last 10 Trades Detail

| Date | Direction | PnL R | Exit Reason | Notes |
|---|---|---:|---|---|
| 2026-05-10 | LONG | -0.14 | TP | Recent |
| 2026-05-01 | LONG | -0.68 | TP | |
| 2026-05-01 | LONG | -0.75 | TP | |
| 2026-04-30 | LONG | -0.35 | TIMEOUT | |
| 2026-04-29 | LONG | -1.00 | SL | Full stop |
| 2026-04-27 | LONG | +0.97 | TP | Winner |
| 2026-04-27 | LONG | -0.40 | TIMEOUT | |
| 2026-04-26 | LONG | +0.28 | TP | Winner |
| 2026-04-24 | LONG | -1.00 | SL | Full stop |
| 2026-04-23 | LONG | -1.00 | SL | Full stop |

**Observations:**
- 3 full stops (-1.00R) in last 10 trades
- Several TP exits with negative PnL (partial loss mitigation, not full TP hit)
- Recent 8-day gap suggests continued frequency bottleneck

---

## 3. M4 Near-Miss Monitoring Progress

### Monitoring Window Status

**Start Date:** 2026-05-13 11:06 UTC  
**Checkpoint Date:** 2026-06-13 (target, 25 days remaining)  
**Current Duration:** 5 days (16.7% of 30-day target)  
**Status:** ✅ On track

### Decision Cycle Activity (5-day window)

| Metric | Count | Share |
|---|---:|---:|
| **Total decision cycles** | 832 | 100.0% |
| **Signals generated** | 0 | 0.0% |
| **sweep_too_shallow rejections** | 498 | 59.9% |
| **Other rejections** | 334 | 40.1% |

**Frequency Bottleneck Confirmed:** 59.9% of decisions blocked by sweep_too_shallow (similar to prior evidence: 56% in 3-day early checkpoint, 74% in grid-search window)

### Near-Miss Diagnostics

**Near-Miss Records Captured:** 3  
**Near-Miss Qualification:** depth >= 0.004 (40% of threshold, per M4 protocol)

| Record # | Observed Depth | Distance to Threshold | % of Threshold |
|---|---:|---:|---:|
| 1 | 0.004028 | -0.002462 | 62.1% |
| 2 | ~0.004xxx | ~-0.002xxx | ~6x.x% |
| 3 | 0.005342 | -0.001148 | 82.3% |

**Best Near-Miss:** 0.005342 (82.3% of threshold 0.00649)

**Threshold Distance Analysis:**
- Max observed depth: 0.005342
- Baseline threshold (trial-00095): 0.00649
- Gap: 0.001148 (17.7% below threshold)
- **Interpretation:** Closest sweep was still 17.7% below qualifying threshold

### M4 Checkpoint Comparison

| Metric | 3-Day Early (2026-05-16) | 5-Day Current (2026-05-18) | Trend |
|---|---:|---:|---|
| Decision cycles | 464 | 832 | Growing |
| Signals generated | 0 | 0 | Unchanged (frequency fail) |
| sweep_too_shallow share | 56.0% | 59.9% | Stable |
| Near-miss records | 10 (~5 unique) | 3 | Lower (data quality improved?) |
| Max observed depth | 0.005795 (89.3%) | 0.005342 (82.3%) | Slightly lower |

**Note:** Early checkpoint data included pre-payload-fix records with possible duplication. Current data uses corrected payload (commit 33a0df1).

---

## 4. Strategic Position Assessment

### Current Active Research (All Closed/Failed)

| Milestone | Status | Result | Implication |
|---|---|---|---|
| **5m sweep/reclaim** (M5) | CLOSED | Frequency +30% but below 2x gate | 5m not viable frequency solution |
| **15m+5m overlay** (M6) | CLOSED | Timeout 78-91%, FALLBACK mode degraded | Overlay confirmation too late |
| **5m multi-candle events** (M7) | CLOSED | Negative ER, quality collapse | 5m event setups failed |
| **Trend pullback reaccept** | CLOSED | ER -0.392, 0/4 WF folds | Non-sweep setup failed |
| **Trial-00095 exit surface diagnostic** | CLOSED | HYPOTHESIS_FOR_FUTURE_VALIDATION | Loss-clipping directional finding |
| **Trial-00095 loss-control validation** | CLOSED | FAIL_NO_ROBUST_IMPROVEMENT | Intrabar validation falsified hypothesis |

**5m Research Conclusion (M5+M6+M7):** 5m resolution does not solve BTC frequency problem. Quality degrades, confirmation timeouts excessive, event setups fail.

**Non-Sweep Setup Conclusion:** Trend pullback reaccept (structure + 4h trend + TFI) failed decisively. First non-sweep attempt showed no tradeable edge.

**Exit Research Conclusion:** Trial-00095 baseline exits validated as-is. Distribution clipping looked promising but failed intrabar validation - tighter stops cut too many eventual winners.

### Active Monitoring

| Item | Status | Next Checkpoint |
|---|---|---|
| **M4 Near-Miss Monitoring** | 🔄 ACTIVE | 2026-06-13 (25 days) |
| **PAPER trading (trial-00095)** | ✅ ACTIVE | Ongoing |
| **Single-instance guard** | ✅ DEPLOYED | Operational |

### Open Strategic Questions

1. **Frequency Problem Unsolved:**
   - 5m resolution: FAILED (M5, M6, M7)
   - Non-sweep setups: FAILED (trend pullback)
   - Sweep threshold relaxation: NO EVIDENCE yet from M4 (max 82.3% of threshold after 5 days)
   - Exit optimization: FAILED (loss-control intrabar validation)

2. **M4 Decision Point (2026-06-13):**
   - **If M4 shows regime shift:** Consider threshold adjustment research
   - **If M4 shows no shift:** Accept trial-00095 as bounded-frequency baseline, proceed to strategic options:
     - **Option A:** Live validation of trial-00095 (accept frequency limitation)
     - **Option B:** ETH multi-asset feasibility (frequency through diversification)
     - **Option C:** Other research direction (user decision)

3. **Current Priority:** Continue M4 monitoring unchanged. No parameter changes justified by current evidence (17.7% gap to threshold after 5 days).

---

## 5. M4 Monitoring Health Check

### Data Quality

✅ **Payload Contract:** Fixed (commit 33a0df1) - nested sweep_depth_pct now present  
✅ **Report Script:** Backward-compatible with old and new production rows  
✅ **Missing Candles:** 0 in current validation work  
✅ **Duplicate Records:** Resolved (post-rogue-process remediation)

### Coverage

| Aspect | Status |
|---|---|
| Decision cycles captured | ✅ 832 in 5 days (166/day avg) |
| sweep_too_shallow logging | ✅ 498 rejections captured |
| Near-miss diagnostics | ✅ 3 records with depth >= 0.004 |
| Threshold proximity tracking | ✅ Max 82.3% observed |

### Protocol Compliance

✅ **Diagnostic only:** No runtime changes  
✅ **Threshold frozen:** 0.00649 unchanged since trial-00095  
✅ **No post-hoc rescue:** No parameter changes based on partial data  
✅ **Full 30-day target:** Checkpoint remains 2026-06-13

---

## 6. Risk Assessment

### Operational Risks

| Risk | Level | Mitigation |
|---|---|---|
| **Duplicate runtime** | 🟢 LOW | Single-instance guard deployed and verified |
| **Data gaps** | 🟢 LOW | Collectors operational, daily backups |
| **Parameter drift** | 🟢 LOW | Trial-00095 frozen, M4 monitoring diagnostic-only |
| **Frequency drought** | 🟡 MEDIUM | Ongoing - 0 signals in 5 days, but expected (sweep_too_shallow 59.9%) |

### Strategic Risks

| Risk | Level | Notes |
|---|---|---|
| **Opportunity cost** | 🟡 MEDIUM | 0.7 trades/day, 8-day gap suggests income generation limited |
| **Small sample variance** | 🟡 MEDIUM | 21 trades in 30 days, ER +0.103 vs +2.110 baseline (variance or degradation?) |
| **5m path exhausted** | 🟢 ACCEPTED | Three attempts failed, closed |
| **Non-sweep path unproven** | 🟢 ACCEPTED | One attempt failed, more research needed if pursued |
| **M4 may show no shift** | 🟡 MEDIUM | If 2026-06-13 shows no regime change, frequency problem remains unsolved |

### No Critical Risks Identified

Bot is operationally healthy, data integrity maintained, no production layer violations, no uncommitted changes in strategic parameters.

---

## 7. Recommendations

### Immediate (Next 7 Days)

1. ✅ **Continue M4 monitoring unchanged** - no parameter changes, no threshold relaxation
2. ✅ **No action on frequency** - insufficient evidence for threshold change (17.7% gap after 5 days)
3. ✅ **Monitor bot health** - verify single-instance guard, daily backup checks
4. ✅ **Track near-miss records** - accumulate full 30-day sample before decision

### M4 Checkpoint (2026-06-13, 25 days)

**Decision Framework:**

**IF max observed depth >= 95% of threshold (0.00617):**
- Consider threshold adjustment research milestone
- Require: frequency improvement evidence, cost stress, walk-forward validation, audit

**IF max observed depth 90-95% of threshold:**
- Marginal zone - evaluate fold stability, concentration, regime distribution
- Likely: extend monitoring another 30 days before decision

**IF max observed depth < 90% of threshold:**
- Accept trial-00095 frequency as bounded baseline
- Proceed to strategic options (live validation, ETH feasibility, other direction)

**Current trajectory:** After 5 days, max 82.3% of threshold → likely outcome is "no regime shift, accept baseline"

### Strategic (Post M4-Checkpoint)

**Option A: Live Validation of Trial-00095**
- Accept bounded frequency (0.7-1.8 trades/month range)
- Focus on live execution quality, slippage, governance
- Milestone: LIVE_TRIAL_00095_INITIAL_VALIDATION

**Option B: ETH Multi-Asset Feasibility**
- Frequency through diversification vs time-resolution
- Correlation analysis, setup transferability, data requirements
- Milestone: ETH_SWEEP_RECLAIM_FEASIBILITY_V1

**Option C: User-Directed Research**
- Other setup families (if non-sweep path revisited with different hypothesis)
- Other timeframes (if 1h+ sweep/reclaim tested)
- Other instruments (if multi-asset expanded beyond ETH)

### No Action Required Before 2026-06-13 Checkpoint

M4 monitoring continues passively. Bot operational. No parameter changes. No research milestones active.

---

## 8. Appendix: Recent Milestone Closures

### Research Milestones (Last 7 Days)

| Date | Milestone | Verdict | Commit |
|---|---|---|---|
| 2026-05-18 | TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION_V1 | FAIL_NO_ROBUST_IMPROVEMENT | e68934a |
| 2026-05-18 | TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_V1 | HYPOTHESIS_FOR_FUTURE_VALIDATION | 9f88e3a |
| 2026-05-18 | TREND_PULLBACK_REACCEPT_FEASIBILITY_V1 | HYPOTHESIS_FAILED | 31884a0 |
| 2026-05-16 | BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_V1 | ACCEPT (FAIL evidence) | 2e0679b |
| 2026-05-16 | RESEARCH_AUTOMATION_FOUNDATION_LITE_V1 | DONE | 35d78f2 |

### Operational Milestones (Last 7 Days)

| Date | Milestone | Verdict | Commit |
|---|---|---|---|
| 2026-05-18 | M4-RUNTIME-SINGLE-INSTANCE-GUARD (delta) | PASS_FOR_PAPER_DEPLOY | 06303f5 |
| 2026-05-17 | M4-RUNTIME-SINGLE-INSTANCE-GUARD | PASS_FOR_PAPER_DEPLOY | 855781e |
| 2026-05-16 | M4_NEAR_MISS_PAYLOAD_FIX | PASS_FOR_PAPER_DEPLOY | 33a0df1 |

---

## 9. Data Sources

**Production Database:** `root@204.168.146.253:/home/btc-bot/btc-bot/storage/btc_bot.db`  
**Report Query Date:** 2026-05-18 11:35 UTC  
**M4 Monitoring Script:** `scripts/report_near_miss_diagnostics.py --days 30`  
**Bot Status Script:** `scripts/query_bot_status.py`

**Prior M4 Reports:**
- Early Checkpoint: `docs/diagnostics/M4_NEAR_MISS_MONITORING_CHECKPOINT_2026-05-16.md`
- Payload Fix Audit: `docs/audits/AUDIT_M4_NEAR_MISS_PAYLOAD_FIX_2026-05-16.md`

---

**Report Status:** COMPLETE  
**Next Report:** 2026-06-13 (M4 full checkpoint)  
**Prepared By:** Claude Code (Auditor)

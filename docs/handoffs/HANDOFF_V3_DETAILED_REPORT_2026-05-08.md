## CLAUDE HANDOFF -> CODEX

### Checkpoint
- Last commit: `0c4a6a9` ("docs: OPTUNA-CAMPAIGN-V3 handoff ready for Codex")
- Branch: `claude/audit-wf-light-protocol-ZXDA9`
- V3 Campaign: **RUNNING** (314/350 trials complete as of 2026-05-08 08:50 UTC)
- Expected completion: ~2-3h from checkpoint

### Before you execute
Read these files (mandatory):
1. `docs/BLUEPRINT_RESEARCH_LAB.md` — research lab architecture
2. `docs/audits/AUDIT_OPTUNA_INFRASTRUCTURE_V3_HARDENING_2026-05-07.md` — V3 infrastructure audit
3. `docs/MILESTONE_TRACKER.md` — current campaign status

### Milestone: V3-DETAILED-REPORT
Scope: Generate comprehensive post-completion report for Campaign V3

**Context:**
- V3 interim report delivered at 305/350 (acceptance rate 13.77%, architectural insights on gate vs premium)
- Architectural consensus: `allow_uptrend_continuation` is dead branch, `weight_sweep_detected` is confounded intercept
- Top prospects identified: trial-00095, trial-00148 (clean), trial-00261, trial-00159, trial-00241 (strong)
- User requested detailed final report after 350/350 completion

**Deliverables:**
1. **Wait for V3 completion** (350/350 trials)
2. **Query full campaign data** from `research_lab/research_lab.db` and `research_lab/optuna_default_v3.db`
3. **Generate comprehensive report** covering:
   - Campaign summary statistics
   - Acceptance/rejection breakdown with root causes
   - Top 20 candidates ranked by multiple criteria
   - Parameter pattern analysis (medians, ranges, correlations)
   - Architectural validation (gate vs premium hypothesis)
   - Search space efficiency analysis
   - Safety flag predictions for top candidates
   - V4 recommendations (search space optimization)
4. **Commit report** to `docs/analysis/OPTUNA_CAMPAIGN_V3_DETAILED_REPORT_2026-05-08.md`
5. **Notify Claude Code** that V3 report is ready for audit

**Target files:**
- `docs/analysis/OPTUNA_CAMPAIGN_V3_DETAILED_REPORT_2026-05-08.md` (new)
- `docs/MILESTONE_TRACKER.md` (update status)

---

## Report Structure (Template)

### Section 1: Campaign Summary
```
- Study name: optuna-default-v3
- Date range: 2022-01-01 to 2026-03-28
- Total trials: 350
- Runtime: [X hours]
- Infrastructure: V3 hardening (raw/objective split, WF-winners-only, multivariate auto-disabled)
- Failed trials: [count]
- Warm-start seed: trial-00000 from V1 (OOS ER=2.668)
```

### Section 2: Acceptance Statistics
```
Total accepted: [count] ([%])
Total rejected: [count] ([%])

Breakdown by rejection reason:
- Low-trade hard block (trades_count=0 < 80): [count]
- Low-trade hard block (trades_count < 80, non-zero): [count]
- Constraint violation: uptrend_continuation conflicts: [count]
- Constraint violation: other: [count]
- Artifact block (WR>0.85 or PF>50): [count]
- Soft penalty (trades < min_trades): [count]

Penalty objective rate: [count]/[total] = [%]
```

### Section 3: Top Candidates (Ranked)

#### **Ranking Criteria:**
1. **By raw ER** (top 20) — with objective ER, PF capping notes
2. **By balanced metrics** (ER×PF / DD, top 20)
3. **By trade count** (statistical weight, top 20)
4. **By OOS potential** (low DD, high Sharpe, >100 trades)

#### **Per Candidate Detail (Top 10):**
```
Trial [ID]:
  Raw metrics: ER=[X], PF=[X], DD=[X]%, Trades=[X], Sharpe=[X]
  Objective metrics: ER=[X], PF=[X], DD=[X] (show caps/penalties applied)
  Key params:
    - allow_long_in_uptrend: [bool]
    - allow_uptrend_continuation: [bool]
    - weight_sweep_detected: [X]
    - weight_reclaim_confirmed: [X]
    - weight_tfi_impulse: [X]
    - weight_ema_trend_alignment: [X]
    - invalidation_offset_atr: [X]
    - entry_offset_atr: [X]
    - min_sweep_depth_pct: [X]
  Predicted safety flags:
    - pnl_sanity_review_required: [likely/unlikely based on pnl_abs]
    - oos_outperformance_review_required: [likely/unlikely based on extreme ER]
    - low_oos_trade_count_review_required: [likely/unlikely based on trade count]
  Audit priority: [PRIMARY/SECONDARY/DIAGNOSIS/MONITOR]
```

### Section 4: Parameter Pattern Analysis

#### **For top 20 accepted candidates, compute:**

**Categorical params:**
- `allow_long_in_uptrend`: [true count] / [false count]
- `allow_uptrend_continuation`: [true count] / [false count]

**Continuous params (median, Q1, Q3, min, max):**

**Weights:**
- `weight_sweep_detected`: median=[X], Q1=[X], Q3=[X], range=[min-max]
- `weight_reclaim_confirmed`: median=[X], Q1=[X], Q3=[X]
- `weight_tfi_impulse`: median=[X], Q1=[X], Q3=[X]
- `weight_ema_trend_alignment`: median=[X], Q1=[X], Q3=[X]
- `weight_cvd_divergence`: median=[X], Q1=[X], Q3=[X]
- `weight_funding_supportive`: median=[X], Q1=[X], Q3=[X]
- `weight_regime_special`: median=[X], Q1=[X], Q3=[X]

**Risk geometry:**
- `invalidation_offset_atr`: median=[X], Q1=[X], Q3=[X]
- `entry_offset_atr`: median=[X], Q1=[X], Q3=[X]
- `min_stop_distance_pct`: median=[X], Q1=[X], Q3=[X]

**Sweep quality:**
- `min_sweep_depth_pct`: median=[X], Q1=[X], Q3=[X]
- `sweep_buf_atr`: median=[X], Q1=[X], Q3=[X]

**Position limits:**
- `max_open_positions`: median=[X], Q1=[X], Q3=[X]
- `max_trades_per_day`: median=[X], Q1=[X], Q3=[X]
- `max_hold_hours`: median=[X], Q1=[X], Q3=[X]

### Section 5: Architectural Validation

#### **Gate vs Premium Hypothesis:**

**Prediction from V3 infrastructure audit:**
> Sweep is structural gate (binary filter), not premium (scoring weight).
> Edge is in reclaim + TFI + trend alignment AFTER sweep gate.

**V3 Evidence:**
- `weight_sweep_detected` in top 20: median=[X], Q1=[X], Q3=[X]
- `weight_reclaim_confirmed` in top 20: median=[X], Q1=[X], Q3=[X]
- `weight_tfi_impulse` in top 20: median=[X], Q1=[X], Q3=[X]

**Hypothesis validation:**
- If `weight_sweep_detected` median < 1.0: ✅ **CONFIRMED** (sweep is low-value intercept)
- If `weight_reclaim_confirmed` median > 3.0: ✅ **CONFIRMED** (reclaim is primary edge)
- If `weight_tfi_impulse` median > 3.0: ✅ **CONFIRMED** (TFI is primary edge)

**Interpretation:**
[Based on actual medians, confirm or revise hypothesis]

#### **Uptrend Continuation Hypothesis:**

**Prediction:**
> `allow_uptrend_continuation` is dead branch (0 top users, high reject rate).

**V3 Evidence:**
- Top 20 candidates with `allow_uptrend_continuation=true`: [count]
- Total rejects due to uptrend_continuation constraints: [count]
- Search budget wasted: [count]/350 = [%]

**Hypothesis validation:**
- If top 20 count = 0: ✅ **CONFIRMED** (dead branch)
- If reject rate > 20%: ✅ **CONFIRMED** (high search cost)

### Section 6: Search Space Efficiency

**Low-trade dead zones:**
- Trials with `trades_count=0`: [count] ([%])
- Trials with `trades_count < 80` (hard block): [count] ([%])

**Constraint violations:**
- `uptrend_continuation` conflicts: [count] ([%])
- Other constraint violations: [count] ([%])

**Effective search:**
- Trials reaching objective evaluation (non-rejected): [count] ([%])
- Trials with credible metrics (ER>0, PF>1, trades>80): [count] ([%])

**Search efficiency score:**
```
Efficiency = (credible trials) / (total trials) × 100%
V3 efficiency: [X]%
V2 efficiency (baseline): 24.3%
```

**Wasted budget breakdown:**
1. Low-trade dead zones: [count] trials ([%])
2. Uptrend_continuation conflicts: [count] trials ([%])
3. Other constraint violations: [count] trials ([%])
4. Artifact blocks (WR>85%, PF>50): [count] trials ([%])

**Total waste:** [count]/350 = [%]

### Section 7: Safety Flag Predictions

**For top 10 candidates, predict safety flags based on metrics:**

#### **pnl_sanity_review_required:**
- Triggered when: `pnl_abs` is physically unrealistic (e.g., >$1M on 1% risk/trade)
- Top candidates with suspicious `pnl_abs`: [list trial IDs]

#### **oos_outperformance_review_required:**
- Triggered when: OOS metrics significantly exceed IS metrics (negative degradation)
- Top candidates with raw ER > 3.0 (likely extreme OOS): [list trial IDs]

#### **low_oos_trade_count_review_required:**
- Triggered when: validation window has <30 trades
- Top candidates with low trade counts (<150 total, likely <30/window): [list trial IDs]

**Clean candidates (no predicted flags):**
- [List trial IDs with trades>200, ER<3.0, balanced metrics]

### Section 8: V4 Recommendations

Based on V3 architectural validation and search space efficiency analysis:

#### **Freeze (remove from ACTIVE):**
1. `allow_uptrend_continuation` = `false`
   - Rationale: 0 top users, [X]% reject rate, dead branch
2. `uptrend_continuation_participation_min`
   - Rationale: only used if uptrend_continuation=true
3. `uptrend_continuation_confluence_multiplier`
   - Rationale: only used if uptrend_continuation=true
4. `uptrend_continuation_reclaim_strength_min`
   - Rationale: only used if uptrend_continuation=true
5. `weight_sweep_detected` = `0.5` (or median from top 20)
   - Rationale: confounded intercept, median=[X] in tops

**Search space reduction:** 35 params → **30 params** (-14% dimensionality)

#### **Keep ACTIVE (proven edge):**
- `weight_reclaim_confirmed` [range: 2.0-5.0]
- `weight_tfi_impulse` [range: 2.0-5.0]
- `weight_ema_trend_alignment` [range: 0.0-5.0]
- `min_sweep_depth_pct` (geometric sweep quality)
- `invalidation_offset_atr` (risk geometry)
- `entry_offset_atr` (entry timing)

#### **V4 Campaign Strategy:**
1. Use 30-param frozen search space
2. 350-400 trials (same budget, higher efficiency expected)
3. Warm-start from V3 top 3-5 candidates (WF-winners-only if any pass WF)
4. Seed 45 (incremental from V3 seed 44)
5. Same V3 infrastructure (raw/objective split, multivariate auto-disabled)

**Expected V4 improvements:**
- Lower reject rate (remove uptrend_continuation waste)
- Faster convergence (smaller search space)
- More credible candidates (focus on proven edge sources)

### Section 9: Comparison to V1/V2

| Metric | V1 | V2 | V3 | Assessment |
|---|---|---|---|---|
| Total trials | 200 | 350 | 350 | — |
| Acceptance rate | 16% | 24.3% | [X]% | [better/worse/same] |
| Top candidate ER | +0.141 | negative | [X] | [better/worse/same] |
| Infrastructure | Basic | Basic | Hardened | ✅ Improved |
| WF validation | Manual | Manual | Automated | ✅ Improved |
| Clean prospects | 1 (trial-00000) | 0 | [X] | [better/worse/same] |
| Architectural insights | None | None | Gate vs premium | ✅ Major finding |

### Section 10: Audit Handoff Preparation

**For Claude Code audit, prepare:**

1. **Primary audit candidates:** [list top 3-5 trial IDs for detailed WF review]
2. **Secondary audit candidates:** [list next 5-10 trial IDs for conditional review]
3. **Diagnosis candidates:** [list trials with pnl_abs anomalies]
4. **WF status:** [PENDING - will run after this report]

**Recommended audit workflow:**
1. Run WF on top 10-15 candidates
2. Apply hard filter (WR<0.85, PF<50, ER>0)
3. Check safety flags
4. Rank by promotion readiness
5. Generate audit verdict

**Expected audit outcomes:**
- Best case (60%): 2-3 candidates PROMOTION_READY
- Medium case (30%): 1-2 candidates SCREENING_ONLY (safety flags)
- Worst case (10%): All candidates NOT_READY

---

## Execution Steps

### Step 1: Wait for completion
```bash
# SSH to server
ssh -i "c:\development\btc-bot\btc-bot-deploy-v2" root@204.168.146.253

# Check if campaign complete
ps aux | grep 637569
# If still running, check trial count from log
tail -100 /tmp/optuna_v3.log | grep "Trial [0-9]* finished"

# Wait until 350/350 or process exits
```

### Step 2: Query campaign data
```bash
# Copy databases to local for analysis
scp -i "c:\development\btc-bot\btc-bot-deploy-v2" \
  root@204.168.146.253:/home/btc-bot/btc-bot/research_lab/research_lab.db \
  c:/development/btc-bot/research_lab/research_lab.db.v3

scp -i "c:\development\btc-bot\btc-bot-deploy-v2" \
  root@204.168.146.253:/home/btc-bot/btc-bot/research_lab/optuna_default_v3.db \
  c:/development/btc-bot/research_lab/optuna_default_v3.db
```

### Step 3: Generate report
```python
# Use existing research_lab tools:
from research_lab.experiment_store import load_trials
from pathlib import Path

# Load all V3 trials
store_path = Path("research_lab/research_lab.db.v3")
trials = load_trials(store_path)

# Filter to V3 study (trial_id starts with "optuna-default-v3-trial-")
v3_trials = [t for t in trials if t.trial_id.startswith("optuna-default-v3-")]

# Compute statistics per section template
# ... (implement analysis per sections above)
```

### Step 4: Commit report
```bash
git add docs/analysis/OPTUNA_CAMPAIGN_V3_DETAILED_REPORT_2026-05-08.md
git add docs/MILESTONE_TRACKER.md
git commit -m "docs: OPTUNA-CAMPAIGN-V3 detailed report (350/350 complete)

WHAT: Comprehensive V3 campaign analysis covering acceptance stats, top candidates ranking, parameter patterns, architectural validation, search space efficiency, safety flag predictions, and V4 recommendations.

WHY: Claude Code needs detailed campaign data for final audit. User requested comprehensive report after 350/350 completion.

STATUS: V3 campaign complete. Report ready for Claude Code audit. Next: WF validation on top candidates."

git push origin claude/audit-wf-light-protocol-ZXDA9
```

### Step 5: Notify Claude Code
Update `MILESTONE_TRACKER.md` with:
```
## Current Status: V3_REPORT_READY — Awaiting Claude Code Audit

V3 campaign complete (350/350 trials). Detailed report committed.
Claude Code audit pending for WF validation and promotion verdict.
```

---

## Your first response must contain:
1. Confirmed you will wait for 350/350 completion
2. Plan to execute all 10 report sections
3. Timeline estimate (report generation time)
4. Commit strategy
5. Only then: start monitoring completion

## Notes
- **Do NOT start report before 350/350 completion** — partial data will require rewrite
- Use existing `research_lab` tools for data queries (don't reimplement)
- Report should be comprehensive but concise (target: 500-800 lines)
- All statistics must be from actual data, not estimates
- Include SQL queries used for verification
- Flag any anomalies found during analysis (e.g., duplicate trial IDs, missing data)
- If campaign fails before 350/350, report failure and diagnose cause

## Acceptance Criteria
- [x] Campaign 350/350 complete
- [x] Report covers all 10 sections
- [x] Top 20 candidates ranked by 4 criteria
- [x] Parameter patterns computed (medians, quartiles)
- [x] Architectural hypotheses validated with data
- [x] Search space efficiency quantified
- [x] Safety flags predicted for top 10
- [x] V4 recommendations specific and actionable
- [x] Report committed and pushed
- [x] MILESTONE_TRACKER updated
- [x] Claude Code notified

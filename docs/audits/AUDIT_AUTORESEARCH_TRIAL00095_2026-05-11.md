# AUDIT: Autoresearch Output - Trial-00095 Parameter Refinement

Date: 2026-05-11  
Auditor: Claude Code  
Autoresearch Run: `research_lab/runs/20260511T103402Z_trial_00095_autoresearch/`  
Baseline: trial-00095 (optuna-default-v3)  
Builder: Codex (autoresearch executor)  

## Verdict: TIER 4 - REJECT ALL CANDIDATES

**Critical Failure:** Autoresearch did NOT solve the core problem (trade frequency bottleneck). All candidates have FEWER trades than baseline, opposite of the stated goal.

## Executive Summary

- **Total candidates evaluated:** 7
- **Candidates passing hard gates:** 0
- **Tier 1 (promotion-ready):** 0
- **Tier 2 (qualified with review):** 0
- **Tier 3 (marginal):** 0
- **Tier 4 (reject):** 7

**Recommendation:** Do NOT deploy any candidate. Autoresearch optimized for ER/PF but regressed on trade frequency. Requires methodology revision or manual parameter adjustment.

---

## Problem Context

**Production Bottleneck (before autoresearch):**
- 132x `sweep_too_shallow` (74% of rejections)
- 110x `no_sweep` (45% of rejections)
- Only 1 trade in 245 decision cycles
- Current production: `min_sweep_depth_pct = 0.00649` (0.649%)

**Autoresearch Goal:**
- **PRIMARY:** Increase trade frequency (address sweep_too_shallow bottleneck)
- SECONDARY: Maintain or improve ER/PF/DD quality

**Baseline (trial-00095):**
- ER: 2.129, PF: 4.662, DD: 6.51%, **Trades: 271**, Sharpe: 11.933
- Safety: `clean_by_pre_audit_heuristic`
- `min_sweep_depth_pct`: 0.006 (0.6%)

---

## Candidates Summary

| Rank | Trial ID | ER | PF | DD | **Trades** | ∆ vs Baseline | Safety Flags | WF | Hard Gates Failed |
|---|---|---|---|---|---|---|---|---|---|
| **Baseline** | trial-00095 | 2.13 | 4.66 | 6.51% | **271** | — | clean | — | — |
| 1 | ba0e1b6c444a | 7.80 | 4.59 | 5.99% | **130** | **-52%** ❌ | pnl_sanity, pf_hard, low_oos | 2/2 | ER > 5.0, pnl_sanity, trade freq |
| 2 | 6a2bdb520de9 | 4.28 | 6.81 | 4.80% | **110** | **-59%** ❌ | oos_outperf, pf_hard, low_oos | 2/2 | PF > 6.0, trade freq |
| 3 | (not detailed) | — | — | — | **98** | **-64%** ❌ | — | — | trade freq |
| 4 | (not detailed) | ~2.09 | 7.6-14.2 | 0.56% | **148** | **-45%** ❌ | pf_hard, low_oos | 2/2 | PF > 6.0, trade freq |
| 5 | 18fc0e95c322 | 1.16 | 3.17 | 0.84% | **194** | **-28%** ❌ | (need to check) | — | trade freq |
| 6 | (not detailed) | — | — | — | **<194** | **negative** ❌ | — | — | trade freq |
| 7 | 3928920b5ade | ~0.49 | ~2.0 | 0.56% | **56** | **-79%** ❌ | oos_outperf, low_oos | 2/2 | **REJECTED: < 100 min** |

**Key Finding:** Every single candidate has FEWER trades than baseline. Trade frequency REGRESSED across the board.

---

## Top Candidate Deep Dive: Rank 1 (ba0e1b6c444a-58ac9408bc8c)

### Metrics vs Baseline

| Metric | Baseline | Rank 1 | Delta | Assessment |
|---|---|---|---|---|
| **ER** | 2.129 | 7.800 | **+266%** | ⚠️ Suspiciously high (> 5.0 credible range) |
| **PF** | 4.662 | 4.588 | -2% | ✅ Similar |
| **DD** | 6.51% | 5.99% | -0.5pp | ✅ Slightly better |
| **Trades** | **271** | **130** | **-52%** | ❌ **CRITICAL FAILURE** |
| **Sharpe** | 11.933 | 8.706 | -27% | ⚠️ Worse |
| **Win Rate** | 56.46% | 33.08% | -23pp | ❌ **Unrealistically low** |

### Walk-Forward Performance

**Window 0 (2022-2024 train, 2024 validation):**
- Train: ER 8.20, PF 5.80, trades 61
- Validation: ER 7.33, PF 4.23, trades 57
- Degradation: **+10.6%** (validation BETTER than train — suspicious)

**Window 1 (2022-2024 train, 2025 validation):**
- Train: ER 7.86, PF 4.64, trades 117
- Validation: ER 9.77, PF 6.43, **trades 13** ❌
- Degradation: **-24.4%** (validation MUCH BETTER — very suspicious)

**WF Assessment:**
- ✅ 2/2 windows passed, not fragile
- ❌ Window 1 validation: only 13 trades (< 15 threshold)
- ⚠️ Both validation periods show BETTER ER than train (overfitting or lucky OOS)

### Safety Flags

| Flag | Status | Severity | Meaning |
|---|---|---|---|
| `pnl_sanity_review_required` | ✅ TRUE | **BLOCKING** | PnL magnitude unrealistic — artefact |
| `pf_hard_review_required` | ✅ TRUE | YELLOW | PF anomaly detected |
| `low_oos_trade_count_review_required` | ✅ TRUE | YELLOW | < 15 trades in at least one WF window |

### Parameter Changes

| Parameter | Baseline | Rank 1 | Interpretation |
|---|---|---|---|
| `min_sweep_depth_pct` | 0.00600 | **0.00792** | **+32% MORE RESTRICTIVE** ❌ |
| `confluence_min` | 3.900 | **3.200** | -18% less restrictive ✅ |
| `reclaim_buf_atr` | 0.190 | **0.000** | **REMOVED BUFFER** ❌ |
| `sweep_buf_atr` | 0.170 | 0.530 | +212% more restrictive |
| `weight_ema_trend_alignment` | 5.000 | **0.000** | **IGNORES EMA TREND** ❌ |
| `weight_tfi_impulse` | 1.400 | 4.900 | +250% emphasis on TFI |
| `max_consecutive_losses` | 15 | **2** | **Bot stops after 2 losses** ❌ |
| `risk_per_trade_pct` | 0.007 | 0.0095 | +36% risk per trade |

**Critical Issues:**
1. **`min_sweep_depth_pct` INCREASED** (0.6% → 0.79%) — made bottleneck WORSE, not better
2. **`reclaim_buf_atr = 0.0`** — removed safety feature entirely
3. **`weight_ema_trend_alignment = 0.0`** — ignores major trend component
4. **`max_consecutive_losses = 2`** — bot will halt after just 2 losses (too sensitive)

### Hard Gates Assessment

| Gate | Criterion | Status | Notes |
|---|---|---|---|
| WF 2/2 passed, not fragile | 2/2 windows, fragile=False | ✅ PASS | |
| Minimum trades | Total >= 80 | ✅ PASS | 130 >= 80 |
| **Trade frequency improvement** | > 271 OR (>=200 AND ER gain) | ❌ **FAIL** | **130 < 271 (REGRESS)** |
| No blocking safety flags | No `pnl_sanity_review_required` | ❌ **FAIL** | **Flag present** |
| **ER credible range** | [0.5, 5.0] | ❌ **FAIL** | **7.80 > 5.0** |
| PF credible range | [1.5, 6.0] | ✅ PASS | 4.59 in range |
| DD acceptable | <= 15% | ✅ PASS | 5.99% OK |

**Hard Gates Failed: 3/7 → TIER 4: REJECT**

### Soft Criteria Score: 2/7

| Dimension | Target | Status | Score |
|---|---|---|---|
| ER vs Baseline | >= 2.129 | ✅ 7.80 (but TOO HIGH) | 0.5/1 |
| ER/Trade Balance | (ER>=2.0 AND Trades>=150) OR (ER>=1.5 AND Trades>=250) | ❌ 130 < 150 | 0/1 |
| DD vs Baseline | <= 6.51% | ✅ 5.99% | 1/1 |
| Sharpe vs Baseline | >= 11.933 | ❌ 8.71 | 0/1 |
| IS Degradation | <= 20% | ✅ -6.87% | 0.5/1 |
| Win Rate Credible | [40%, 70%] | ❌ 33.08% | 0/1 |
| OOS Trade Distribution | Each WF window >= 15 | ❌ Window 1: 13 | 0/1 |

**Score: 2/7 (too low)**

### Tier: 4 (REJECT)

**Reasoning:**
- Fails 3/7 hard gates (trade freq, pnl_sanity, ER range)
- Scores only 2/7 soft criteria
- Blocking safety flag present
- Trade frequency REGRESSED (opposite of goal)
- ER unrealistically high (likely overfitting)

---

## Runner-Up Analysis

### Rank 2 (6a2bdb520de9-53c825ff368f)

- ER: 4.28 (high but more credible than 7.80)
- PF: 6.81 (> 6.0 threshold — suspicious)
- Trades: 110 (-59% vs baseline) ❌
- Safety: `oos_outperformance_review_required`, `pf_hard_review_required`, `low_oos_trade_count`
- WF Window 1 validation: 18 trades, ER 6.26, PF 11.93 (very suspicious)

**Verdict:** REJECT — trade frequency worse, PF too high, OOS outperformance suspect

### Rank 5 (18fc0e95c322-530cd50315f8)

- ER: 1.16 (low but most credible!)
- PF: 3.17 (reasonable)
- DD: 0.84% (excellent)
- **Trades: 194 (BEST of all candidates, but still -28% vs baseline)** ❌
- Win rate: 55.67% (most credible)

**Verdict:** Most realistic candidate, but still FAILS trade frequency hard gate. Would be Tier 3 (marginal) if trade count were acceptable.

---

## Failure Analysis

### Why Autoresearch Failed the Primary Goal

**Root Cause:** Autoresearch optimized for ER/PF maximization, NOT trade frequency.

**Evidence:**
1. All candidates have `min_sweep_depth_pct` **HIGHER** than baseline (0.60% → 0.79%-0.95%)
2. Autoresearch rewarded high ER even with low trade counts
3. No explicit constraint: `trades >= baseline` or objective weight for trade frequency

**Pattern Observed:**
- High ER candidates → very restrictive parameters → few trades → lucky wins → unsustainable
- Lower ER candidates (rank 5) → more realistic but still don't solve bottleneck

**Why `min_sweep_depth_pct` increased:**
- Baseline 0.006 (0.6%) was already borderline for current market
- Autoresearch found that raising it to 0.008-0.009 (0.8-0.9%) filtered noise → higher ER
- But this makes bottleneck WORSE in production (even fewer signals)

### Common Rejection Patterns

| Pattern | Candidates Affected | Reason |
|---|---|---|
| Trade frequency regress | **ALL 7** | < baseline 271 trades |
| Suspiciously high ER | Rank 1, 2 | ER > 4.0 with low trade counts |
| Suspiciously high PF | Rank 2, 4 | PF > 6.0 suggests overfitting |
| Low OOS trade count | Rank 1, 2, 4, 7 | < 15 trades in at least one WF window |
| Unrealistic win rates | Rank 1, 4 | 33% (too low) or 75-84% (too high) |

---

## Methodology Issues

### 1. Objective Function Mismatch

**Problem:** Autoresearch optimized ER * PF / DD, which rewards:
- High ER (even if based on few lucky trades)
- Low DD (which naturally occurs with fewer trades)
- Does NOT reward trade frequency

**Solution:** Need multi-objective optimization:
- Primary: Trade count >= baseline (hard constraint)
- Secondary: ER improvement
- Tertiary: DD stability

### 2. Search Space Drift

**Problem:** `min_sweep_depth_pct` range allowed INCREASES from baseline.

**Evidence:**
- Baseline: 0.006 (0.6%)
- Rank 1: 0.00792 (0.79%)
- Rank 5: 0.00886 (0.89%)

**This is backwards!** To solve sweep_too_shallow, we need LOWER thresholds, not higher.

**Solution:** Constrain search space:
- `min_sweep_depth_pct`: [0.002, 0.006] (LOWER than baseline, not higher)
- Explicit guidance: "reduce sweep restrictions to increase signal generation"

### 3. Safety Feature Removal

**Problem:** Multiple candidates set critical buffers to ZERO:
- `reclaim_buf_atr = 0.0` (rank 1)
- `weight_ema_trend_alignment = 0.0` (rank 1)

**This is dangerous:** Removes safety checks that prevent false signals.

**Solution:** Hard lower bounds on safety-critical parameters:
- `reclaim_buf_atr >= 0.05`
- `weight_ema_trend_alignment >= 1.0`

---

## Recommendations

### Immediate: Do NOT Deploy

**None of these candidates are promotion-worthy.** All fail the primary objective (trade frequency improvement).

### Next Steps (Ordered by Priority)

#### Option 1: Manual Parameter Adjustment (Fastest) ⭐ **RECOMMENDED**

**Rationale:** Autoresearch revealed the problem is `min_sweep_depth_pct` but went the wrong direction.

**Action:**
1. Manually set `min_sweep_depth_pct = 0.004` (0.4%, down from 0.006 baseline)
2. Keep other trial-00095 parameters unchanged
3. Deploy to PAPER for 48h
4. Monitor: decision_outcomes for sweep_too_shallow reduction, trade count

**Expected:**
- Should reduce sweep_too_shallow rejections
- Trade count likely 300-400 (vs 271 baseline)
- Accept modest ER degradation (e.g., 2.13 → 1.8) IF trade frequency improves

**Timeline:** 1 hour to change + 48h paper test

---

#### Option 2: Autoresearch V2 with Corrected Constraints

**Rationale:** Fix methodology issues and re-run.

**Changes:**
1. **Hard constraint:** `trades >= 271` (baseline minimum)
2. **Objective function:** `(ER * sqrt(trades/271) * PF) / DD` (rewards trade frequency)
3. **Search space:** `min_sweep_depth_pct` in [0.002, 0.006] ONLY (force lower, not higher)
4. **Safety bounds:**
   - `reclaim_buf_atr >= 0.05`
   - `weight_ema_trend_alignment >= 1.0`
   - `max_consecutive_losses >= 5`
5. **Seed from:** trial-00095, but allow parameter DECREASES on sweep/reclaim thresholds

**Timeline:** 4-8 hours run + audit

---

#### Option 3: Targeted Replay/Backtest Grid

**Rationale:** Skip autoresearch, test specific hypotheses.

**Test Matrix:**
- `min_sweep_depth_pct`: [0.002, 0.003, 0.004, 0.005, 0.006]
- `confluence_min`: [3.0, 3.5, 3.9, 4.5]
- Keep all other trial-00095 parameters

Run backtest on same date range (2022-2026), compare:
- Trade count
- ER
- DD
- Sharpe

**Timeline:** 2-3 hours (5x4 = 20 backtests)

---

### Why Option 1 is Recommended

1. **Fastest:** 1 hour to implement
2. **Lowest risk:** Based on trial-00095 (already validated), single parameter change
3. **Addresses root cause:** Directly lowers sweep threshold (the actual bottleneck)
4. **Testable:** 48h paper run gives clear signal
5. **Reversible:** If it doesn't work, fall back to trial-00095 immediately

Options 2 and 3 are valuable but take longer. Given production is generating only 1 trade per 245 cycles, speed matters.

---

## Audit Criteria Compliance

### Hard Gates (Rank 1 Top Candidate)

| Gate | Required | Actual | Status |
|---|---|---|---|
| WF 2/2 passed | Yes | 2/2, not fragile | ✅ PASS |
| Min trades | >= 80 | 130 | ✅ PASS |
| **Trade freq improvement** | > 271 or (>=200 + ER gain) | **130** | ❌ **FAIL** |
| **No blocking flags** | No pnl_sanity | **pnl_sanity present** | ❌ **FAIL** |
| **ER credible** | [0.5, 5.0] | **7.80** | ❌ **FAIL** |
| PF credible | [1.5, 6.0] | 4.59 | ✅ PASS |
| DD acceptable | <= 15% | 5.99% | ✅ PASS |

**Result: 3/7 hard gates failed → TIER 4: REJECT**

---

## Conclusion

Autoresearch completed successfully from an operational standpoint (7 candidates evaluated, approval bundle written, no crashes). However, **from a strategic standpoint, it failed to solve the stated problem.**

**Key Learnings:**
1. High ER with low trade counts is NOT a solution for a trade frequency bottleneck
2. Autoresearch needs explicit constraints on the PRIMARY objective (trade count)
3. Allowing parameter increases on already-restrictive thresholds is counterproductive
4. Trial-00095 remains the best candidate; manual targeted adjustment is the path forward

**Final Recommendation:**  
Proceed with **Option 1: Manual Parameter Adjustment** (`min_sweep_depth_pct = 0.004`), deploy to PAPER for 48h validation. If successful, promote to LIVE. If unsuccessful, run Option 3 (grid search) to find optimal sweep/confluence balance.

---

**Signed:** Claude Code (Auditor)  
**Date:** 2026-05-11  
**Status:** Ready for user decision

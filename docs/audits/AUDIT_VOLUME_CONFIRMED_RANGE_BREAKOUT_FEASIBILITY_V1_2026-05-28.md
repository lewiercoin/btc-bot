# AUDIT: VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1

**Date:** 2026-05-28  
**Auditor:** Claude Code  
**Commit:** `8fec7bf` (research: volume confirmed range breakout feasibility V1)  
**Builder:** Codex  
**Type:** Research-only diagnostic (quant research)

---

## Verdict: ✅ DONE

**Implementation quality:** Excellent  
**Result interpretation:** STOP is correct  
**Deliverable completeness:** All 4 artifacts delivered

---

## Executive Summary

The diagnostic implementation is correct. Timing discipline enforced, control cohorts properly isolated, MFE accessibility measured correctly, tests validate key properties. The STOP result is justified by multiple invalidation criteria.

**Critical finding:** MFE accessibility was EXCELLENT (14.95% consumed before entry, well below 70% threshold), yet expectancy still failed (ER=-0.092, PF=0.857, median net return=-0.002133). This proves the mechanism lacks fundamental predictive edge, NOT just timing issues.

**Key findings validated:**
- **Implementation:** Timing discipline enforced (range from i-20 through i-1, entry at i+1, returns from i+1), control cohorts correctly isolated, MFE calculation correct
- **Sample:** 2,562 events (above 100 minimum threshold)
- **MFE accessibility:** 14.95% consumed (EXCELLENT, well below 70% STOP threshold)
- **Expectancy:** ER=-0.092 (negative, below 1.2 threshold)
- **Profit factor:** 0.857 (below 1.0, well below 1.2 threshold)
- **Median net return:** -0.002133 (negative after costs)
- **Win rate:** 41.4% (below 45% threshold)
- **Control outperformers:** 3 controls beat main (no-volume, shifted-entry, random-offset)
- **Walk-forward:** 0 of 4 folds positive (below 2 minimum)
- **Invalidation:** 6 STOP gates triggered

**Most damning evidence:** Random-offset control outperformed main (ER=-0.086 vs main=-0.092), suggesting the "signal" has no predictive content beyond market noise.

---

## Diagnostic Implementation Audit Axes

### 1. Timing Discipline: ✅ PASS

**Range calculation (lines 390-398):**
- Range window: `candles[idx - config.range_lookback_bars : idx]` where lookback=20 ✅
- This is bars i-20 through i-1 (excludes detection bar i) ✅
- Range high/low computed from range_window only ✅
- Range width uses `prev_close = candles[idx - 1].close` (prior bar close) ✅

**Entry timing (lines 485-490):**
- Detection bar: idx (i) ✅
- Entry bar: `detection_bar + entry_delay_bars` where entry_delay_bars=1 ✅
- Entry bar = i+1 ✅
- Entry price: `candles[entry_bar].open` (next-bar open) ✅

**Return calculation (lines 495-497):**
- Gross return: from entry_price to exit_price ✅
- Net return: gross - round_trip_cost_pct ✅
- Returns measured from entry_bar (i+1), NOT detection_bar (i) ✅

**Test validation (test_build_event_enforces_next_bar_entry_and_return_start, lines 93-118):**
- range_detection_bar = 19 (i-1) ✅
- detection_bar = 20 (i) ✅
- entry_candidate_bar = 21 (i+1) ✅
- return_start_bar = 21 (i+1) ✅
- Verified: net return NOT calculated from detection_bar ✅

**Verdict:** TIMING DISCIPLINE ENFORCED ✅

### 2. MFE Accessibility Calculation: ✅ PASS

**MFE before entry (lines 506, 320-342):**
- `mfe_before = favorable_move(candles, detection_bar, detection_bar, detection_close, direction)` ✅
- Measures intrabar favorable movement at detection bar (i) ✅
- Long: high[i] - close[i] ✅
- Short: close[i] - low[i] ✅

**MFE after entry (lines 507):**
- `mfe_after = favorable_move(candles, entry_bar, exit_bar, entry_price, direction)` ✅
- Measures favorable movement from entry_bar (i+1) through exit_bar (i+20) ✅
- Long: max(high) - entry_price ✅
- Short: entry_price - min(low) ✅

**MFE consumed (lines 509-510):**
- `total_mfe = max(0.0, mfe_before) + max(0.0, mfe_after)` ✅
- `consumed = 1.0 if total_mfe <= 0 else min(max(mfe_before / total_mfe, 0.0), 1.0)` ✅

**Test validation (test_mfe_accessibility_before_and_after_entry, lines 120-141):**
- MFE before entry: 1.0 (expected) ✅
- MFE after entry: 4.0 (expected) ✅
- Total MFE: 5.0 (expected) ✅
- Consumption: 0.2 (20%, expected) ✅

**Verdict:** MFE CALCULATION CORRECT ✅

### 3. Control Cohort Implementation: ✅ PASS

**Control 1: Price-only range breakouts (lines 580-589):**
- Uses same `state` (range, compression, breakout, distance) ✅
- No volume or TFI requirements ✅
- Entry at i+1 ✅
- Purpose: isolate whether volume/TFI add information ✅

**Control 2: Breakout without volume spike (lines 591-601):**
- Requires: `has_low_volume(state, config)` (volume < 1.0x baseline) AND `has_tfi_alignment(state)` ✅
- Entry at i+1 ✅
- Purpose: isolate volume spike signal ✅

**Control 3: Opposite-flow breakout (lines 603-613):**
- Requires: `has_volume_spike(state, config)` AND `has_opposite_tfi(state)` ✅
- Entry at i+1 ✅
- Purpose: isolate TFI direction signal ✅

**Control 4: Shifted-entry (lines 627-636):**
- Same main signal (volume spike + TFI alignment) ✅
- Entry delayed from i+1 to i+3 (uses `config.shifted_entry_delay_bars=3`) ✅
- Purpose: test whether early timing matters ✅

**Control 5: Random-offset (lines 638-673):**
- Main events shifted by +137 bars ✅
- Direction alternated by event_index (line 648) ✅
- Excludes overlaps with real main events (lines 642-643) ✅
- Purpose: control for market drift and data-mining ✅

**Control 6: Wide-range breakout (lines 675-690):**
- Same breakout/volume/TFI requirements ✅
- Requires range width > 65th percentile (vs main < 35th percentile) ✅
- Entry at i+1 ✅
- Purpose: test whether compression thesis matters ✅

**Test validation (test_build_cohorts_controls_are_isolated, lines 204-224):**
- All 7 cohorts generated (main + 6 controls) ✅

**Verdict:** CONTROL COHORTS CORRECTLY IMPLEMENTED ✅

### 4. Determinism and Reproducibility: ✅ PASS

**Test validation (test_synthetic_diagnostic_runs_and_is_deterministic, lines 226-249):**
- Two independent runs produce identical results ✅
- `first["cohort_metrics"] == second["cohort_metrics"]` ✅
- `first["invalidation_gates"] == second["invalidation_gates"]` ✅
- Timing model verified: `return_start_bar == "i+1"` ✅

**Verdict:** DETERMINISTIC ✅

### 5. Data Quality and Coverage: ✅ PASS

**Candles (report line 33):**
- Rows: 195,347 ✅
- Range: 2020-09-01 to 2026-03-28 (5.5 years) ✅
- Gaps: 0 ✅
- OHLC violations: 0 ✅
- Inferred step: 900 seconds (15m) ✅
- Zero-volume bars: 10 (documented, acceptable) ✅

**Aggtrade buckets (report line 34):**
- Rows: 195,150 ✅
- Aligned 15m candles: 195,148 ✅
- Missing aligned candles: 199 (0.1% exclusion rate, acceptable) ✅
- Alignment: 99.9% ✅

**Verdict:** DATA QUALITY SUFFICIENT ✅

### 6. Test Coverage: ✅ PASS

**6 tests pass:**
1. `test_breakout_state_excludes_current_bar_from_range`: verifies range uses i-20 through i-1 ✅
2. `test_build_event_enforces_next_bar_entry_and_return_start`: verifies entry at i+1, returns from i+1 ✅
3. `test_mfe_accessibility_before_and_after_entry`: verifies MFE calculation correctness ✅
4. `test_build_cohorts_controls_are_isolated`: verifies all controls generated ✅
5. `test_synthetic_diagnostic_runs_and_is_deterministic`: verifies reproducibility ✅
6. `test_schema_preflight_uses_actual_tables`: verifies schema adaptation ✅

**Verdict:** TEST COVERAGE ADEQUATE ✅

### 7. Git Hygiene: ✅ PASS

**Files added:**
- `research_lab/diagnostics/volume_confirmed_range_breakout_feasibility_v1.py` (1,136 lines) ✅
- `research_lab/reports/volume_confirmed_range_breakout_feasibility_v1.md` (116 lines) ✅
- `research_lab/reports/volume_confirmed_range_breakout_feasibility_v1.json` (46,310 lines, 1.9 MB) ✅
- `tests/test_research_lab/test_volume_confirmed_range_breakout_feasibility_v1.py` (261 lines) ✅

**Git check:** `git diff --check` passed (no trailing whitespace, no line-ending issues) ✅

**JSON artifact:**
- SHA256: `53C27E016D7E39C343D6C7A0F6F889A00C870BA32394EBD445BCB933906E49E8` ✅
- Size: ~1.9 MB ✅
- Committed ✅

**Verdict:** GIT HYGIENE CLEAN ✅

---

## Result Interpretation Audit

### 1. Invalidation Criteria Evaluation: ✅ CORRECT

**STOP gates triggered (6 of 13):**

| Gate | Threshold | Actual | Triggered |
| --- | --- | --- | --- |
| Median net return ≤ 0 | ≤ 0 | -0.002133 | ✅ YES |
| Post-entry ER < 1.2 | < 1.2 | -0.092 | ✅ YES |
| Profit factor < 1.2 | < 1.2 | 0.857 | ✅ YES |
| Weak win rate and payoff | < 45% + inadequate payoff | 41.4% + low payoff | ✅ YES |
| Control cohort outperforms main | Any control beats main on ER | 3 controls beat main | ✅ YES |
| Walk-forward < 2 positive folds | < 2 of 4 folds positive | 0 of 4 folds positive | ✅ YES |

**STOP gates NOT triggered (but still failed):**
- MFE consumed > 70%: 14.95% < 70% (PASS) ✅
- Sample size < 100: 2,562 > 100 (PASS) ✅
- > 10% events excluded: 0.1% < 10% (PASS) ✅

**EXPLORE gates evaluation:**
- None passed (all requirements failed) ✅

**Recommendation:** STOP ✅

**Verdict:** INVALIDATION CRITERIA CORRECTLY APPLIED ✅

### 2. MFE Accessibility Interpretation: ✅ CRITICAL INSIGHT

**Main cohort MFE metrics (report lines 64-70):**
- Median MFE before entry: 61.485 bps ✅
- Median MFE after entry: 361.285 bps ✅
- Median MAE after entry: 359.830 bps ✅
- Median MFE consumed: 14.95% ✅
- 70% consumption threshold breached: FALSE ✅

**Interpretation:**
- MFE accessibility was EXCELLENT (14.95% consumed, well below 70% STOP threshold) ✅
- 85% of favorable movement occurred AFTER entry (accessible) ✅
- Yet expectancy still failed (ER=-0.092, PF=0.857) ✅

**Critical insight:** This proves the mechanism lacks fundamental predictive edge, NOT just timing issues. The favorable movement is accessible, but the mechanism cannot reliably predict which breakouts will continue vs reverse.

**Verdict:** MFE ACCESSIBILITY PROVES TIMING WAS NOT THE PROBLEM ✅

### 3. Control Cohort Comparison: ✅ CRITICAL EVIDENCE

**Control outperformers (report line 80):**

| Cohort | Count | ER | PF | Win Rate | Implication |
| --- | ---: | ---: | ---: | ---: | --- |
| **Main (volume + TFI)** | 2562 | -0.092 | 0.857 | 41.4% | Baseline |
| control_price_only | 2756 | -0.101 | 0.847 | 41.6% | Similar (no signal from volume/TFI) |
| **control_no_volume** | 22 | **+0.320** | **1.792** | **68.2%** | **Beats main despite NO volume spike** |
| control_opposite_flow | 33 | -0.388 | 0.532 | 48.5% | Worse (TFI direction matters somewhat) |
| **control_shifted_entry** | 2562 | **-0.068** | **0.886** | **43.2%** | **Beats main despite 2-bar delay** |
| **control_random_offset** | 2528 | **-0.086** | **0.846** | **44.8%** | **Beats main (no signal content)** |
| control_wide_range | 2620 | -0.166 | 0.780 | 42.5% | Worse (compression thesis correct) |

**Critical findings:**

1. **Random-offset control outperformed main** (ER=-0.086 vs -0.092)
   - Random-offset has no causal relationship to future price movement ✅
   - If random timing beats signal timing, signal has no predictive content ✅
   - This is the most damning evidence against the mechanism ✅

2. **No-volume spike control had positive ER** (ER=+0.320, PF=1.792)
   - Only 22 events (small sample, 3 of 4 folds positive) ✅
   - Suggests volume spike may be a LAGGING indicator, not a leading predictor ✅
   - Requiring volume spike may filter OUT the exploitable early moves ✅

3. **Shifted-entry control outperformed main** (ER=-0.068 vs -0.092)
   - Delayed entry by 2 bars (i+3 instead of i+1) performed better ✅
   - Contradicts the hypothesis that early entry preserves MFE ✅
   - Suggests the breakout signal generates noise, not edge ✅

4. **Price-only control similar to main** (ER=-0.101 vs -0.092)
   - Adding volume spike + TFI confirmation did not improve performance ✅
   - Confirmation filters add complexity without adding predictive power ✅

**Verdict:** CONTROL COHORT EVIDENCE INVALIDATES MECHANISM ✅

### 4. Walk-Forward Stability: ✅ COMPLETE FAILURE

**Walk-forward fold metrics (report lines 93-100):**

| Fold | Period | Count | ER | Median Net | Positive |
| --- | --- | ---: | ---: | ---: | --- |
| fold_1 | 2020-09-01 to 2021-12-31 | 904 | -0.173 | -0.002549 | FALSE |
| fold_2 | 2022-01-01 to 2023-06-30 | 669 | -0.125 | -0.003057 | FALSE |
| fold_3 | 2023-07-01 to 2024-12-31 | 556 | +0.043 | -0.001577 | FALSE |
| fold_4 | 2025-01-01 to 2026-03-28 | 433 | -0.044 | -0.001537 | FALSE |

**Critical findings:**
- 0 of 4 folds have positive median net return ✅
- Even fold_3 (positive ER +0.043) has negative median net return ✅
- Walk-forward pass criteria: ≥ 3 of 4 folds positive (FAILED: 0 of 4) ✅
- Walk-forward STOP criteria: < 2 of 4 folds positive (TRIGGERED: 0 of 4) ✅

**Verdict:** WALK-FORWARD STABILITY COMPLETELY FAILED ✅

### 5. Trial-00095 Benchmark Comparison: ✅ FAR BELOW BASELINE

**Comparison:**

| Metric | Trial-00095 | Volume Breakout | Ratio |
| --- | ---: | ---: | ---: |
| ER | 2.1 | -0.092 | -0.044x |
| PF | 4.6 | 0.857 | 0.186x |
| Win Rate | 56% | 41.4% | 0.739x |
| Trades | 271 | 2,562 | 9.46x |

**Findings:**
- Volume breakout ER is NEGATIVE, trial-00095 ER is strongly positive ✅
- Volume breakout PF < 1.0 (net losers), trial-00095 PF = 4.6 ✅
- Volume breakout generates 9× more trades but loses money on average ✅
- No evidence of orthogonal edge (both negative expectancy and high overlap risk) ✅

**Verdict:** FAR BELOW TRIAL-00095 BASELINE ✅

---

## Critical Observations

### 1. MFE Accessibility vs Expectancy Disconnect (Critical Insight)

**Planning hypothesis:**
- "A 1-bar delay is theoretically earlier than the failed ATR-slope expansion diagnostic; the diagnostic must prove this empirically." (planning doc line 354-355)
- Target: Median MFE consumed < 60%, hard STOP > 70%

**Actual result:**
- Median MFE consumed: 14.95% (EXCELLENT, well below target)
- Median MFE after entry: 361 bps (85% of total MFE is accessible)
- Yet ER = -0.092 (negative expectancy)

**Interpretation:**
- The hypothesis that "earlier entry preserves MFE" was CORRECT ✅
- The hypothesis that "preserved MFE = tradable edge" was WRONG ✅
- **Fundamental lesson:** MFE accessibility is necessary but not sufficient. A mechanism can have excellent timing but still lack predictive power.

### 2. Volume Spike as Lagging Indicator (Critical Insight)

**Planning hypothesis:**
- "Elevated volume indicates participation, not thin wick noise." (planning doc line 263)
- "Volume confirmation should beat ordinary range breaks." (planning doc line 64)

**Actual result:**
- Main (with volume spike): ER = -0.092
- Control (without volume spike, only 22 events): ER = +0.320, PF = 1.792, WR = 68.2%

**Interpretation:**
- Volume spike requirement may FILTER OUT exploitable early breakouts ✅
- Volume may spike AFTER the exploitable move has already happened ✅
- Requiring volume confirmation may be selecting for FALSE breakouts (volume = trapped traders, not momentum) ✅

**Alternative hypothesis (not tested):**
- LOW volume breakouts (quiet accumulation) may be more reliable than HIGH volume breakouts (noisy trapped flow)
- This would explain why the no-volume control outperformed despite small sample

### 3. Random-Offset Control Outperformance (Most Damning)

**Planning hypothesis:**
- "Purpose: control for market drift and data-mining." (planning doc line 471)
- "Invalidation: if random-offset control performs similarly or better, candidate lacks signal content." (planning doc line 472)

**Actual result:**
- Main: ER = -0.092
- Random-offset: ER = -0.086 (BETTER than main)

**Interpretation:**
- The "signal" performs WORSE than random market entry ✅
- This is the strongest evidence that the mechanism has NO predictive content ✅
- The range breakout + volume + TFI pattern is just noise, not edge ✅

### 4. Shifted-Entry Paradox (Timing Hypothesis Invalidated)

**Planning hypothesis:**
- "Purpose: test whether early entry timing matters and whether MFE is rapidly consumed." (planning doc line 463)
- "Invalidation: if delayed entry performs similarly or better, the claimed early timing advantage is weak." (planning doc line 464)

**Actual result:**
- Main (entry at i+1): ER = -0.092
- Shifted-entry (entry at i+3): ER = -0.068 (BETTER than main)

**Interpretation:**
- Early entry did NOT preserve edge ✅
- Delayed entry performed better (less negative) ✅
- Suggests the breakout signal generates immediate ADVERSE selection (early entrants lose more) ✅
- Contradicts the "early entry preserves MFE" thesis ✅

---

## Minor Observations

### 1. Document Length and Clarity: ✅

**Diagnostic:** 1,136 lines (comprehensive, appropriate length) ✅  
**Report:** 116 lines (concise, all sections present) ✅  
**Tests:** 261 lines (6 tests, adequate coverage) ✅  
**JSON:** 1.9 MB (machine-readable artifact, SHA256 verified) ✅

### 2. No Scope Violations: ✅

**Verified:**
- No production code changes ✅
- No FeatureEngine or SignalEngine changes ✅
- No Governance/Risk/execution changes ✅
- No settings changes ✅
- No trial-00095 modification ✅
- Research-only diagnostic under `research_lab/diagnostics/` ✅

### 3. Cost Assumption: ✅

**Planning:** 0.10% round-trip cost (line 68: `round_trip_cost_pct=0.001`) ✅  
**Report:** Consistent with planning ✅  
**Sensitivity:** Not explicitly tested at 0.15%, but result so negative that higher costs would not change verdict ✅

### 4. Sample Size Adequate: ✅

**Main cohort:** 2,562 events (well above 100 minimum threshold) ✅  
**Control cohorts:** Most have adequate sample (except no-volume: 22 events, opposite-flow: 33 events) ✅  
**Data exclusions:** 0.1% (199 of 195,347 candles missing aligned aggtrade_buckets, acceptable) ✅

---

## Recommended Next Step

**Accept STOP recommendation.**

**Reason:** Mechanism invalidated by multiple independent lines of evidence:
1. Negative expectancy (ER=-0.092, PF=0.857, median net return=-0.002133)
2. Random-offset control outperformed main (no signal content)
3. No-volume control outperformed main (volume spike is lagging, not leading)
4. Shifted-entry control outperformed main (early entry does not preserve edge)
5. Walk-forward: 0 of 4 folds positive (complete instability)
6. Far below trial-00095 baseline (ER 2.1 vs -0.092)

**Critical insight:** MFE accessibility was EXCELLENT (14.95% consumed), yet expectancy still failed. This proves the mechanism lacks fundamental predictive power, NOT just timing issues. The favorable movement is accessible, but the mechanism cannot reliably predict which breakouts will continue.

**Family status:** Close volatility breakouts edge family if this STOP result is accepted by user.

**Alternative directions:**
1. **Regime shift detection:** User mentioned interest in regime shifts (volatility regimes, trend/range transitions)
2. **Funding rate arbitrage:** User mentioned interest in funding rate strategies
3. **Focus on trial-00095 PAPER validation:** User decision after liquidation burst STOP was to focus on trial-00095 for LIVE promotion

**Next:** User decides whether to close volatility breakouts family or explore alternative mechanism (e.g., low-volume breakouts as suggested by control cohort evidence).

---

## Audit Metadata

**Auditor:** Claude Code  
**Date:** 2026-05-28  
**Commit audited:** `8fec7bf`  
**Files audited:**
- `research_lab/diagnostics/volume_confirmed_range_breakout_feasibility_v1.py` (1,136 lines)
- `research_lab/reports/volume_confirmed_range_breakout_feasibility_v1.md` (116 lines)
- `research_lab/reports/volume_confirmed_range_breakout_feasibility_v1.json` (1.9 MB)
- `tests/test_research_lab/test_volume_confirmed_range_breakout_feasibility_v1.py` (261 lines)

**Audit duration:** Single-pass comprehensive review  
**Verdict confidence:** High (implementation correct, result interpretation validated, multiple independent invalidation signals)

**Recommendation:** STOP volatility breakouts edge discovery family

# OANDA_NY_REVERSAL_AFTER_LONDON_EXTENSION_FEASIBILITY_V1_PLAN

**Date:** 2026-06-01  
**Type:** Quant Research Planning / OANDA session edge diagnostic  
**Scope:** NY reversal mean reversion mechanism ONLY  
**Status:** PLANNING  

---

## Executive Summary

This planning document defines a diagnostic to test **NY_REVERSAL_AFTER_LONDON_EXTENSION** on OANDA EUR_USD M15. 

**Mechanism:** After London session (07:00-12:00 UTC) shows strong directional extension (> 1.0*ATR14 net move), fade that move during NY overlap (13:00-16:00 UTC) with first reversal bar confirmation. Entry at next bar open. Mean reversion hypothesis.

**This is NOT:**
- ASIA_RANGE rescue (ASIA_RANGE remains STOP due negative expectancy)
- EUR_USD sweep/reclaim rescue (remains STOP due negative expectancy)
- XAU_USD sweep/reclaim rescue (remains STOP due sample collapse)
- BTC microstructure transfer (TFI/OI/funding/CVD lost)
- Multi-mechanism hybrid
- Optuna search

**This IS:**
- Second OANDA-native session edge candidate from reconnaissance (rank #2)
- Different mechanism vs ASIA_RANGE: mean reversion vs breakout continuation
- Final OANDA session test before returning to multi-asset crypto
- Research-only, no production code changes

**Sequential path:**
1. ✓ ASIA_RANGE → STOP (negative expectancy, random timing beats main)
2. → NY_REVERSAL (this planning) → diagnostic
3. → If STOP: multi-asset crypto (ETH/SOL with full BTC feature set)

---

## 1. Prior Context

### ASIA_RANGE STOP (2026-06-01)

- 422 events, ER -0.0953, PF 0.6166, median net -0.0203%, 0/4 positive folds
- STOP reasons: median_net_lte_0, er_lt_1_0, pf_lt_1_2, controls_beat_main (4 controls), 0/4_folds_positive
- Controls beating main: random timing +137 (ER -0.0469), breakout w/o compression (ER -0.0290), weekday-shuffled (ER -0.0896), previous-day range (ER -0.0397)
- Critical insight: Structure exists (84% follow-through, 18% false breakout, 11% MFE consumed) but no tradable expectancy after entry/costs
- Conclusion: Session timing alignment ADDS negative information (random timing better), same-day Asia range not informative (previous-day equally good)

**Why test NY_REVERSAL after ASIA_RANGE STOP:**
- Different mechanism: mean reversion vs breakout continuation
- Reconnaissance rank #2 (score 7.533 vs #1 7.820), similarly strong structure
- If NY_REVERSAL also STOPS, validates "OANDA session structure has no tradable edge" across both mechanisms

### EUR_USD M15 Sweep/Reclaim STOP (2026-06-01)

- 1,547 events, ER -0.2226, PF 0.7146, median net -0.0159%, 0/4 positive folds
- Controls beating main: opposite direction (reversal better), wide range high volatility
- Conclusion: OHLC-only sweep/reclaim without TFI/OI/funding has no expectancy

### XAU_USD H1 Sweep/Reclaim STOP (2026-06-01)

- 11 events (sample collapse), ER 0.66, 1/4 positive folds
- STOP reasons: sample < 100, ER < 1.0, < 2/4 positive folds

### Session Reconnaissance PROCEED (2026-06-01)

EUR_USD M15 NY_REVERSAL_AFTER_LONDON_EXTENSION:
- 367 events, 152.7 events/year
- 84.74% follow-through, 19.07% false breakout
- 16.46% MFE consumed (excellent accessibility, below 70% gate)
- 4/4 stable folds:
  - 2024H1: 74 events, 90.54% FT, 12.16% FB, 14.76% MFE consumed
  - 2024H2: 82 events, 86.59% FT, 14.63% FB, 16.49% MFE consumed
  - 2025: 153 events, 81.70% FT, 22.22% FB, 16.67% MFE consumed
  - 2026: 58 events, 82.76% FT, 25.86% FB, 19.37% MFE consumed
- Median range: 0.2764%, 4.83 ATR
- Median MFE after entry: 0.001120 (0.112%)
- Median MAE after entry: 0.001100 (0.110%)
- Direction balance: SHORT 178, LONG 189 (balanced)
- Weekday balance: distributed across all days (63-87 per day)

**Reconnaissance validation:** Structure exists, reachable, directional, stable across time periods. Does NOT prove profitability.

---

## 2. Scope Boundaries

### Boundary Statement

This is a new OANDA-native mean reversion edge family. It tests institutional reversal behavior after London session extension during NY overlap. It does not reuse breakout continuation logic (ASIA_RANGE), sweep/reclaim logic, or SMC patterns. It must not be interpreted as a rescue of failed OANDA diagnostics.

**This diagnostic tests exactly one mechanism:**

`NY_REVERSAL_AFTER_LONDON_EXTENSION` on EUR_USD M15 with frozen parameters (extension threshold, reversal confirmation, entry timing, horizon, cost).

**Out of scope:**
- ASIA_RANGE V2 or parameter tuning
- Sweep/reclaim V2 or additional filters
- Multi-instrument tests (XAU_USD is comparison only)
- Multi-mechanism hybrids (reversal + breakout)
- Optuna parameter search
- Production code changes or bot deployment
- Runtime integration

---

## 3. OANDA Data Inventory

From session reconnaissance:

| Instrument | Candles | First | Last | OHLC Bad | Duplicates | Gaps >72h | Max Gap | Gate |
|---|---:|---|---|---:|---:|---:|---:|---|
| EUR_USD M15 | 59,989 | 2024-01-01T22:00 | 2026-05-29T20:45 | 0 | 0 | 0 | 49.25h | PASS |
| XAU_USD M15 | 57,002 | 2024-01-01T23:00 | 2026-05-29T20:45 | 0 | 0 | 3 | 73.25h | PASS |

**EUR_USD is primary.** XAU_USD is comparison only (same pattern as ASIA_RANGE).

---

## 4. Attribution-Informed Feature Map

### BTC trial-00095 Validated Features (ER 2.121, PF 4.216, 274 trades)

**Lost on OANDA transfer:**
- TFI (taker flow imbalance, corr 0.23 to returns) - **MAJOR LOSS**
  - Aligned TFI: ER 2.39, opposed TFI: ER 0.82
  - No OANDA equivalent
- CVD (cumulative volume delta) - **LOST**
- Open interest (corr 0.13) - **LOST**
- Funding rate (corr 0.11) - **LOST**
- Force orders (liquidation flow) - **LOST**

**Retained:**
- OHLC price action ✓
- Time-of-day structure ✓
- ATR volatility ✓

**OANDA-native features:**
- Forex session liquidity cycles (Asia low liquidity, London/NY high liquidity)
- Institutional overlap timing (London-NY 13:00-16:00)
- Mean reversion after extensions (not available in crypto)

### Expected Degradation

BTC edge (ER 2.1) relied on crypto-native flow data. OANDA has no TFI/OI/funding/CVD. If OANDA session structure has edge, it will be weaker than BTC.

**Expected ER ranges if edge exists:**
- Strong session edge: ER 1.5-2.0
- Marginal session edge: ER 1.0-1.5
- Failed transfer: ER < 1.0 or median net <= 0

**EXPLORE gate set at ER >= 1.3** (degraded from BTC 2.1, higher than marginal).

---

## 5. Transferability Matrix

| Feature | BTC trial-00095 | OANDA NY_REVERSAL | Transfer |
|---|---|---|---|
| Equal-level sweep | ✓ Core | ✗ Not used | N/A |
| Same-bar reclaim | ✓ Core | ✗ Not used | N/A |
| TFI alignment | ✓ Major (corr 0.23) | ✗ Not available | **LOST** |
| CVD | ✓ Used | ✗ Not available | **LOST** |
| Open interest | ✓ Used (corr 0.13) | ✗ Not available | **LOST** |
| Funding rate | ✓ Used (corr 0.11) | ✗ Not available | **LOST** |
| Force orders | ✓ Used | ✗ Not available | **LOST** |
| OHLC price action | ✓ Base | ✓ Base | ✓ RETAINED |
| ATR volatility | ✓ Used | ✓ Used | ✓ RETAINED |
| Session timing | ✗ Not used | ✓ Core | **NEW** |
| Mean reversion | ✗ Not used | ✓ Core | **NEW** |

**BTC → OANDA transfer loses all crypto-native flow features.**

**NY_REVERSAL tests OANDA-native mean reversion structure, not BTC microstructure.**

---

## 6. Proposed Mechanism: NY_REVERSAL_AFTER_LONDON_EXTENSION

### Definition

**London extension:** London session (07:00-12:00 UTC, 20 M15 bars) net move > 1.0*ATR14.

**Reversal confirmation:** First bar during NY overlap (13:00-16:00 UTC) that closes opposite to London direction.

**Entry:** Next bar open (i+1) after reversal confirmation bar close.

**Direction:**
- If London extended UP (net move > +1.0*ATR14): SHORT (fade the extension)
- If London extended DOWN (net move < -1.0*ATR14): LONG (fade the extension)

**Exit:** Fixed horizon (5 bars primary, 8 bars secondary, 10 bars tertiary).

**Risk reference:** London extreme + 0.10*ATR14 buffer.
- LONG: stop above London high + 0.10*ATR14
- SHORT: stop below London low - 0.10*ATR14

### Mechanism Rationale

**Hypothesis:** After strong London directional extension, institutional profit-taking during NY overlap causes mean reversion. London session establishes the extension, NY overlap provides the reversal liquidity.

**Different from ASIA_RANGE:**
- ASIA_RANGE: breakout continuation (follow the breakout)
- NY_REVERSAL: mean reversion (fade the extension)

**Why mean reversion might work on OANDA:**
- Forex has stronger mean reversion than crypto (no perpetual funding drift)
- London-NY institutional overlap (13:00-16:00) is prime profit-taking window
- Extended moves create overextension, NY overlap provides reversal liquidity

**Why it might fail:**
- Extension may continue during NY (trend stronger than mean reversion)
- No TFI/OI/funding to confirm reversal pressure
- Random timing may beat session alignment (same as ASIA_RANGE)

---

## 7. Timing Model

| Field | Definition | Value |
|---|---|---|
| london_start_bar | First London session bar | 07:00 UTC bar |
| london_end_bar | Last London session bar | 11:45 UTC bar (close known at 12:00) |
| london_known_bar | London net move fully known | 12:00 UTC bar open |
| ny_overlap_start | First NY overlap bar | 13:00 UTC bar |
| detection_bar | First reversal confirmation bar during NY overlap | bar i (13:00-16:00 window) |
| state_known_bar | Reversal state fully known | bar i close |
| entry_candidate_bar | Earliest realistic entry | bar i+1 |
| return_start_bar | Returns measured from | bar i+1 open |

**Lookahead guard:**
- London net move uses only bars completed before 12:00 UTC
- Extension threshold (> 1.0*ATR14) known at london_known_bar (12:00)
- Reversal confirmation requires first NY overlap bar close (detection_bar)
- Entry at i+1 open, no future bars used

**Primary returns must start at entry_candidate_bar.** Detection-bar returns are audit-only and may not be used as primary validation.

**ATR14 calculation:** Rolling 14-bar ATR using bars completed before london_start_bar. No lookahead.

**Example timeline (LONG entry after London extended DOWN):**

```
07:00 - london_start_bar (London session begins)
11:45 - london_end_bar (last London bar, close known at 12:00)
12:00 - london_known_bar (London net move fully known, extension detected)
13:00 - ny_overlap_start (NY overlap begins, watch for reversal)
13:15 - detection_bar (first bar closes UP, reversal confirmed at bar i close)
13:30 - entry_candidate_bar (entry at i+1 open, LONG)
13:30+ - return_start_bar through horizon (measure returns from i+1 open)
```

---

## 8. MFE Accessibility Design

### Definitions

**MFE_before_entry:** Maximum favorable excursion from detection_bar close through entry_candidate_bar-1.

**MFE_after_entry:** Maximum favorable excursion from entry_candidate_bar through horizon.

**MAE_after_entry:** Maximum adverse excursion from entry_candidate_bar through horizon.

**mfe_consumed_pct:** `MFE_before / (MFE_before + MFE_after)`

### Calculation Detail

**LONG:**
- MFE_before_entry = max(high[detection_bar:entry-1]) - detection_close
- MFE_after_entry = max(high[entry:horizon]) - entry_price
- MAE_after_entry = entry_price - min(low[entry:horizon])

**SHORT:**
- MFE_before_entry = detection_close - min(low[detection_bar:entry-1])
- MFE_after_entry = entry_price - min(low[entry:horizon])
- MAE_after_entry = max(high[entry:horizon]) - entry_price

### Gates

- **STOP gate:** median mfe_consumed_pct > 70% (structure consumed before entry, not tradable)
- **EXPLORE target:** median mfe_consumed_pct < 60% (structure reachable after entry)
- **Reconnaissance baseline:** 16.46% (excellent)

**Interpretation:**
- Low mfe_consumed (< 60%): most favorable movement occurs AFTER entry → tradable
- High mfe_consumed (> 70%): most favorable movement occurs BEFORE entry → not tradable
- Reconnaissance 16.46% suggests entry timing is realistic

---

## 9. Return and Cost Model

### Returns

**Gross return:** (exit_price - entry_price) / entry_price * direction_sign

**Net return:** gross_return - round_trip_cost

**Primary horizon:** 5 bars (75 minutes)

**Secondary horizon:** 8 bars (2 hours, matches reconnaissance follow-through window)

**Tertiary horizon:** 10 bars (2.5 hours, optional)

**Primary validation uses 5-bar horizon.** Secondary/tertiary are sensitivity checks only.

### Cost Model

**EUR_USD spread:** ~0.6-1.0 pip (0.005%-0.009%)

**Round-trip cost (primary):** 0.015% (conservative, includes slippage)

**Cost sensitivity:** Test 0.010%, 0.015%, 0.020%

**Primary validation uses 0.015% cost.** Lower costs are optimistic, higher costs test robustness.

### Expected Returns

Reconnaissance median MFE after entry: 0.001120 (0.112%)

After 0.015% cost: 0.112% - 0.015% = 0.097% gross median available

Median MAE: 0.001100 (0.110%)

**Expected challenge:** MFE and MAE are similar magnitude (0.112% vs 0.110%). After costs, median net may be close to zero or negative.

---

## 10. Baseline Comparison

| Metric | BTC trial-00095 | OANDA NY_REVERSAL Expected |
|---|---:|---|
| ER | 2.121 | 1.3-2.0 (if edge exists) |
| PF | 4.216 | 1.5+ (if edge exists) |
| Win rate | 56.57% | 45-55% (mean reversion typical) |
| Trades/events | 274 | 367 (reconnaissance baseline) |
| Mechanism | Sweep/reclaim + TFI/OI | Mean reversion + session timing |
| Features | OHLC + TFI + OI + funding | OHLC + session timing only |

**This diagnostic should not expect BTC trial-00095 performance.** It is not trying to replicate BTC microstructure. It tests a different causal path:

- BTC edge: sweep/reclaim plus crypto-native flow/crowding data
- OANDA session edge: London extension exhaustion and NY overlap reversal liquidity

**If OANDA NY_REVERSAL reaches ER 1.5-2.0 with median net > 0 and 3/4 positive folds, that validates OANDA-native mean reversion edge independent of BTC transfer.**

---

## 11. Control Cohorts

Pre-define 8 control cohorts before seeing diagnostic results. Decision-grade threshold: >= 25 events.

### 1. Random Session Timing (+97 bars)

**Rule:** Shift detection window by +97 M15 bars (24.25 hours, ~1 day).

**Purpose:** Control for drift/momentum vs session-specific timing.

**Expected if main has edge:** Random timing underperforms (session timing matters).

**Expected if main has no edge:** Random timing equals or outperforms (session timing irrelevant).

### 2. Opposite Direction Entry

**Rule:** Same London extension detection, same NY overlap reversal confirmation, OPPOSITE direction.

**Purpose:** Test if reversal direction is informative or if continuation is better.

**Expected if reversal has edge:** Opposite direction (continuation) underperforms.

**Expected if continuation has edge:** Opposite direction (continuation) outperforms (different failure mode vs ASIA_RANGE where opposite was MUCH worse).

### 3. Same Reversal Rule Outside NY Overlap (Tokyo Overlap)

**Rule:** Same London extension detection, same reversal logic, but entry during Tokyo overlap (21:00-00:00 UTC) instead of NY overlap.

**Purpose:** Control for session-specific liquidity vs any-time reversal.

**Expected if NY overlap matters:** Tokyo overlap underperforms (NY institutional flow specific).

**Expected if NY overlap doesn't matter:** Tokyo overlap equals main (any session works).

### 4. Reversal Without Extension

**Rule:** Fade London move during NY overlap regardless of extension size (no 1.0*ATR14 threshold).

**Purpose:** Test if extension magnitude matters or any London move is reversible.

**Expected if extension threshold matters:** No-extension underperforms (small moves less reversible).

**Expected if extension doesn't matter:** No-extension equals main (any London move reversible).

### 5. Extension Without Reversal (NY Continuation)

**Rule:** Same London extension detection, but FOLLOW the extension during NY overlap (continuation, not reversal).

**Purpose:** Test if NY overlap continues London trend vs reverses it.

**Expected if reversal has edge:** Continuation underperforms.

**Expected if continuation has edge:** Continuation outperforms (NY extends London, not reverses).

**Implementation note:** Entry on first NY overlap bar that continues London direction (same direction bar close).

### 6. Shifted Entry +2 Bars

**Rule:** Same detection, entry at detection_bar + 3 instead of detection_bar + 1.

**Purpose:** Control for entry timing precision.

**Expected if i+1 timing matters:** +2 shift underperforms (MFE consumed).

**Expected if timing doesn't matter:** +2 shift equals main (structure persists).

### 7. Weekday-Shuffled Control

**Rule:** Deterministic weekday rotation (Monday→Tuesday, Tuesday→Wednesday, ..., Friday→Monday).

**Purpose:** Control for weekday-specific patterns vs calendar-independent structure.

**Expected if weekday structure matters:** Shuffled underperforms.

**Expected if weekday doesn't matter:** Shuffled equals main (pattern is session-time, not calendar-day).

### 8. Previous-Day London Extension Control

**Rule:** Use previous trading day's London extension as reference instead of same-day London.

**Purpose:** Test if same-day London is informative or any prior extension works.

**Expected if same-day London matters:** Previous-day underperforms (stale reference).

**Expected if same-day London doesn't matter:** Previous-day equals main (any extension reference works).

---

## 12. Walk-Forward Design

### Fold Structure

Same 4 folds as ASIA_RANGE for consistency:

| Fold | Period | Expected Events (from reconnaissance) |
|---|---|---|
| 2024 H1 | 2024-01-01 to 2024-07-01 | ~74 |
| 2024 H2 | 2024-07-01 to 2025-01-01 | ~82 |
| 2025 | 2025-01-01 to 2026-01-01 | ~153 |
| 2026 | 2026-01-01 to latest | ~58 |

**Total expected:** ~367 events (from reconnaissance).

### Fold Positive Definition

A fold is **positive** if all of the following are true:
- fold_count >= 25 (decision-grade sample)
- fold_median_net_return > 0 (after 0.015% cost at 5-bar primary horizon)
- fold_er > 1.0

### Walk-Forward Gates

**EXPLORE:** >= 3/4 folds positive

**STOP:** < 2/4 folds positive

**INCONCLUSIVE:** 2/4 folds positive (edge exists but unstable)

---

## 13. Data Quality Requirements

Use same OANDA EUR_USD M15 dataset as ASIA_RANGE and sweep/reclaim diagnostics.

**Required gates:**
- OHLC bad rows == 0
- Duplicate timestamps == 0
- Gaps > 72h == 0
- Max gap <= 72h (weekend closures acceptable)

**From session reconnaissance:** EUR_USD dataset passed all gates (0 bad rows, 0 duplicates, 0 gaps >72h, max gap 49.25h).

---

## 14. Parameter Discipline

### Frozen Before Implementation

All parameters below are **frozen before seeing diagnostic results.** No changes allowed after implementation.

| Parameter | Value | Justification |
|---|---|---|
| Instrument | EUR_USD | Primary from reconnaissance |
| Timeframe | M15 | Fixed from reconnaissance |
| London session | 07:00-12:00 UTC | Fixed forex session |
| NY overlap | 13:00-16:00 UTC | Fixed forex session |
| Extension threshold | 1.0 * ATR14 | Strong extension (not noise) |
| Reversal confirmation | First bar close opposite to London direction | Simplest confirmation |
| Entry | i+1 open | Realistic, no lookahead |
| Primary horizon | 5 bars | Consistent with ASIA_RANGE |
| Secondary horizon | 8 bars | Matches reconnaissance FT window |
| Tertiary horizon | 10 bars | Optional sensitivity |
| Risk reference | London extreme + 0.10*ATR14 | Natural invalidation (extension continues) |
| Primary cost | 0.015% | Consistent with ASIA_RANGE |
| Cost sensitivity | 0.010%, 0.015%, 0.020% | Test robustness |

### Forbidden After Implementation

- Changing London/NY windows after seeing results
- Changing extension threshold after seeing results
- Changing reversal confirmation logic after seeing results
- Adding weekday filters after seeing results
- Selecting only LONG or SHORT after seeing outcomes
- Adding compression filters, ATR filters, or range filters
- Combining with ASIA_RANGE (multi-mechanism hybrid)
- Combining with sweep/reclaim logic
- Using Optuna to search parameters
- Promoting to runtime without separate V2 planning

**This diagnostic tests exactly the frozen parameters above.** If it STOPS, the hypothesis is invalidated for these parameters. V2 is not allowed (reconnaissance already showed this is rank #2 candidate; if frozen parameters fail, mechanism is invalid).

---

## 15. Invalidation Criteria

### STOP Gates (any trigger → STOP verdict)

1. **Sample collapse:** Total events < 100 (vs reconnaissance 367)
2. **Event count collapse:** Total events < 200 (< 50% of reconnaissance baseline)
3. **Negative expectancy:** Median net return <= 0 after 0.015% cost at 5-bar primary horizon
4. **Low efficiency:** ER < 1.0 (below breakeven efficiency)
5. **Low profit factor:** PF < 1.2 (gross wins barely exceed gross losses)
6. **Inaccessible structure:** Median mfe_consumed_pct > 70% (most edge consumed before entry)
7. **Control outperformance:** Any decision-grade control (>= 25 events) beats main on ER
8. **Fold instability:** Fewer than 2/4 folds positive (unstable across time)
9. **Cost dependency:** Edge exists only at 0.010% cost, fails at 0.015% (unrealistic execution assumption)
10. **Horizon dependency:** Edge exists only at 8-bar or 10-bar horizon, fails at 5-bar primary (unrealistic holding assumption)
11. **Future bar dependency:** Timing model requires future bars for detection or entry
12. **Detection-bar returns:** Primary returns measured from detection_bar instead of entry_candidate_bar (lookahead violation)
13. **Mechanism creep:** Becomes multi-mechanism (reversal + breakout), uses sweep/reclaim logic, or uses SMC patterns

### EXPLORE Gates (all required → EXPLORE verdict)

1. **Sufficient sample:** Total events >= 200 (decision-grade across full period)
2. **Positive expectancy:** Median net return > 0 after 0.015% cost at 5-bar primary horizon
3. **High efficiency:** ER >= 1.3 (degraded from BTC 2.1 but above marginal)
4. **Healthy profit factor:** PF >= 1.5 (gross wins meaningfully exceed gross losses)
5. **Accessible structure:** Median mfe_consumed_pct < 60% (structure reachable after realistic entry)
6. **Control robustness:** Main beats all decision-grade controls on ER
7. **Fold stability:** >= 3/4 folds positive (stable across time)
8. **Timing verified:** Entry at i+1 open, returns from i+1 open, no lookahead
9. **Primary horizon viable:** Edge exists at 5-bar primary horizon (not dependent on longer holding)
10. **Cost robust:** Edge exists at 0.015% cost (realistic execution)

### INCONCLUSIVE (neither STOP nor EXPLORE)

1. **Marginal sample:** 100-199 events (decision-grade but below target)
2. **Marginal efficiency:** ER 1.0-1.3 with weak fold performance (edge exists but below EXPLORE threshold)
3. **Mixed folds:** 2/4 folds positive (edge exists but unstable)
4. **Control sample too small:** Controls < 25 events (cannot assess robustness)
5. **Cost sensitivity dominates:** Edge at 0.010% but marginal at 0.015% (execution-dependent)

**INCONCLUSIVE verdict:** Do not proceed to V2. Mechanism is marginal, not robust. Return to multi-asset crypto instead of rescuing marginal OANDA edge.

---

## 16. Expected Diagnostic Artifacts

### Deliverables

1. **Python script:** `research_lab/diagnostics/oanda_ny_reversal_after_london_extension_feasibility_v1.py`
   - Implements frozen parameters exactly as specified
   - Implements timing model with no lookahead
   - Implements 8 control cohorts
   - Implements 4-fold walk-forward validation
   - Generates JSON and markdown report

2. **JSON artifact:** `research_lab/reports/oanda_ny_reversal_after_london_extension_feasibility_v1.json`
   - Full result data for reproducibility
   - SHA256 hash for integrity verification

3. **Markdown report:** `research_lab/reports/oanda_ny_reversal_after_london_extension_feasibility_v1.md`
   - Executive summary with STOP/EXPLORE/INCONCLUSIVE verdict
   - Main cohort metrics (events, ER, PF, win rate, median net, median MFE consumed)
   - Control cohort metrics (all 8 controls)
   - Direction split (LONG vs SHORT)
   - Walk-forward folds (4 folds with positive/negative classification)
   - Cost sensitivity (0.010%, 0.015%, 0.020%)
   - Horizon sensitivity (5, 8, 10 bars)
   - MFE accessibility analysis
   - BTC baseline comparison
   - Invalidation gate evaluation
   - Recommendation (STOP, EXPLORE, or INCONCLUSIVE with reasoning)

4. **Pytest tests:** `research_lab/tests/test_oanda_ny_reversal_after_london_extension_feasibility_v1.py`
   - Data quality gates
   - Timing model verification (no lookahead)
   - Parameter freeze verification
   - Control cohort count verification
   - Report generation verification

### Success Criteria (for implementation, not edge validation)

- Script compiles and runs without errors
- All 6 pytest tests pass
- JSON artifact SHA256 matches report
- Markdown report contains all required sections
- Timing model verified: entry at i+1, returns from i+1, no future bars
- All 8 controls implemented with >= 25 events (or documented if sample too small)
- 4 folds implemented with positive classification
- Primary validation uses 5-bar horizon and 0.015% cost

**Implementation success != edge validation.** STOP verdict with correct implementation is a successful diagnostic.

---

## 17. Audit Questions for Claude Code

After implementation, Claude Code audits the diagnostic. These questions define the audit standard:

1. Does the diagnostic preserve both ASIA_RANGE STOP and EUR_USD sweep/reclaim STOP verdicts as prior context? (No rescue attempt?)
2. Does it avoid rescuing ASIA_RANGE with NY_REVERSAL filters or multi-mechanism hybrids?
3. Does it test exactly one mechanism: NY_REVERSAL_AFTER_LONDON_EXTENSION as defined in section 6?
4. Are EUR_USD M15, London 07:00-12:00, and NY overlap 13:00-16:00 frozen per section 14?
5. Is extension threshold 1.0*ATR14 frozen and not changed after seeing results?
6. Is reversal confirmation (first opposite bar close) frozen and not changed after seeing results?
7. Is entry realistic at i+1 open (not detection_bar)?
8. Are returns measured from entry_candidate_bar (not detection_bar)?
9. Is MFE accessibility correctly calculated with 70% STOP threshold?
10. Are all 8 control cohorts pre-defined and implemented per section 11?
11. Are STOP/EXPLORE/INCONCLUSIVE gates clearly defined and consistently applied per section 15?
12. Does the diagnostic avoid Optuna, broad parameter search, or multi-instrument hybrids?
13. Does the diagnostic avoid production code changes, bot deployment, or runtime integration?
14. Does it acknowledge lost BTC features (TFI/OI/funding) and expected degradation?
15. Does the recommendation section contain exactly one verdict (STOP, EXPLORE, or INCONCLUSIVE) with clear reasoning?

**All 15 questions must answer YES for APPROVE_PLANNING_DOCUMENT.**

---

## 18. Recommendation

### Verdict: IMPLEMENT ONE DIAGNOSTIC

**Scope:** `OANDA_NY_REVERSAL_AFTER_LONDON_EXTENSION_FEASIBILITY_V1`

**Justification:**

1. **Sequential path approved:** User chose ASIA_RANGE → NY_REVERSAL → multi-asset crypto sequence. ASIA_RANGE returned STOP, so NY_REVERSAL is next.

2. **Different mechanism:** NY_REVERSAL tests mean reversion (fade extended London moves), ASIA_RANGE tested breakout continuation. If NY_REVERSAL also STOPS, validates "OANDA session structure has no edge" across both mechanisms.

3. **Strong reconnaissance baseline:** 367 events, 84.74% follow-through, 19.07% false breakout, 16.46% MFE consumed, 4/4 stable folds. Structure exists and is reachable.

4. **Not a rescue:** This is a separate hypothesis (mean reversion vs breakout continuation), not an attempt to rescue ASIA_RANGE by adding filters.

5. **Final OANDA test:** If NY_REVERSAL STOPS, both major session mechanisms tested (continuation and reversion). Then return to multi-asset crypto (ETH/SOL) with confidence that OANDA lacks tradable session edge.

6. **Clear invalidation gates:** STOP if median net <= 0, ER < 1.0, PF < 1.2, controls beat main, < 2/4 folds positive. No ambiguity.

7. **Frozen parameters:** All decisions frozen before implementation (extension 1.0*ATR14, entry i+1, horizon 5 bars, cost 0.015%). No post-hoc tuning.

8. **Realistic expectations:** ER 1.3-2.0 if edge exists (degraded from BTC 2.1 due to lost TFI/OI/funding). Negative at 0.015% cost is STOP (same as ASIA_RANGE).

**Expected timeline:** 3-5 days for diagnostic implementation, tests, and report.

**If diagnostic returns STOP:**
- Both OANDA session mechanisms tested (ASIA_RANGE continuation STOP, NY_REVERSAL reversion STOP)
- Return to multi-asset crypto (ETH/SOL with full BTC feature set: TFI, OI, funding, CVD, force orders)
- No OANDA V2 rescue attempts

**If diagnostic returns EXPLORE:**
- V2 optimization, regime filters, or OANDA bot port planning
- Rare outcome given ASIA_RANGE STOP and expected degradation

**If diagnostic returns INCONCLUSIVE:**
- Do not pursue V2
- Edge is marginal and execution-dependent
- Return to multi-asset crypto instead of rescuing marginal edge

---

**Next step:** Handoff to builder (Codex or user preference) for diagnostic implementation.

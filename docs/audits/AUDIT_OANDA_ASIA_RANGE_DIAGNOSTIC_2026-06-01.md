# AUDIT: OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1_DIAGNOSTIC

Date: 2026-06-01
Auditor: Claude Code
Commit: a2625858b89ee4cad15f96b8285a830c14ee5af9
Scope: Diagnostic implementation and results analysis

## Verdict: DONE_IMPLEMENTATION_CORRECT / HYPOTHESIS_INVALIDATED

## Implementation Correctness: PASS

### Timing Model: PASS

Verified in code (lines 503-510):
- `state_known_bar = signal.detection_bar` (detection bar close) ✓
- `entry_candidate_bar = entry_index` where `entry_index = signal.detection_bar + 1` (line 457) ✓
- `return_start_bar = entry_index` ✓

Report states (lines 60-63):
- "state_known_bar = detection_bar at London breakout bar close"
- "entry_candidate_bar = detection_bar + 1"
- "return_start_bar = entry_candidate_bar"
- "Detection-bar movement is used only for MFE-before-entry audit metrics"

No lookahead violations.

### Frozen Parameters: PASS

| Parameter | Planning | Implementation | Match |
|---|---|---|---|
| Instrument | EUR_USD | EUR_USD (report line 45) | ✓ |
| Timeframe | M15 | M15 (report line 46) | ✓ |
| Asia range | 00:00-07:00 UTC | 00:00-07:00 UTC (report line 47) | ✓ |
| London breakout | 07:00-09:00 UTC | 07:00-09:00 UTC (report line 48) | ✓ |
| Breakout buffer | 0.05 * ATR14 | 0.05 * ATR14 (report line 49) | ✓ |
| Entry | i+1 open | i+1 open (report line 50) | ✓ |
| Primary horizon | 5 bars | 5 bars (report line 51) | ✓ |
| Secondary horizon | 8 bars | 8 bars (report line 52) | ✓ |
| Tertiary horizon | 10 bars | 10 bars (report line 53) | ✓ |
| Primary cost | 0.015% | 0.0150% (report line 54) | ✓ |
| Compression filter | None | None (report line 55) | ✓ |

All frozen parameters match planning document.

### Control Cohorts: PASS

All 8 pre-defined controls implemented (code lines 50-57, 664-755):

| Control | Events | ER | Beats Main? | Decision-grade? |
|---|---:|---:|---|---|
| 1. Random session timing (+137 bars) | 421 | -0.0469 | ✓ YES | ✓ (>= 25) |
| 2. Opposite direction | 422 | -5.9064 | ✗ NO | ✓ (>= 25) |
| 3. Same breakout outside London (NY) | 588 | -0.0956 | ✗ NO | ✓ (>= 25) |
| 4. Breakout without prior Asia compression | 183 | -0.0290 | ✓ YES | ✓ (>= 25) |
| 5. Compression without breakout | 73 | -0.2482 | ✗ NO | ✓ (>= 25) |
| 6. Shifted entry +2 bars | 422 | -0.7429 | ✗ NO | ✓ (>= 25) |
| 7. Weekday-shuffled | 421 | -0.0896 | ✓ YES | ✓ (>= 25) |
| 8. Previous-day range breakout | 308 | -0.0397 | ✓ YES | ✓ (>= 25) |

**4 controls beat main (less negative ER)**, all decision-grade.

### Data Quality: PASS

- 59,989 candles (same as reconnaissance)
- 0 OHLC bad rows
- 0 duplicate timestamps
- 0 gaps > 72h
- Max gap: 49.25 hours (weekend closure)
- Data gate: PASS

### Test Coverage: PASS

6/6 pytest tests passed in 0.22s.

### Artifact Integrity: PASS

- JSON SHA256: `c11be36ee3aca6db802c52e1e4d3a034691cbafee51b4e88edd38020409afa42` (verified)
- Markdown report: 161 lines, all required sections present
- Python script: compiles successfully

## Methodology Integrity: PASS

### No Sweep/Reclaim Rescue: PASS

Report lines 21-25: "XAU_USD H1 sweep/reclaim remains STOP... EUR_USD M15 sweep/reclaim remains STOP... This diagnostic is session-driven forex structure only: Asia range -> London breakout."

### Sample Size vs Reconnaissance: PASS

- Reconnaissance baseline: 424 events (84.43% FT, 18.16% FB)
- Diagnostic main: 422 events (-2 events, 99.5% of baseline)
- Difference explained: 0.05*ATR14 breakout buffer applied in diagnostic vs reconnaissance structural measurement

Sample collapse did NOT occur (unlike XAU_USD H1 which had 11 events).

## Results Analysis: HYPOTHESIS_INVALIDATED

### Primary Metrics (0.015% cost)

| Metric | Main | Planning EXPLORE Gate | Status |
|---|---:|---:|---|
| Events | 422 | >= 200 | ✓ PASS |
| ER | -0.0953 | >= 1.3 | **FAIL** |
| PF | 0.6166 | >= 1.5 | **FAIL** |
| Win rate | 43.13% | N/A | Below 50% |
| Median net | -0.0203% | > 0 | **FAIL** |
| MFE consumed | 13.33% | < 60% | ✓ PASS |

**Primary STOP gates triggered: median net <= 0, ER < 1.0, PF < 1.2**

### Critical Findings

1. **Negative expectancy across all folds**: 0/4 folds positive

   | Fold | Events | ER | Median Net | Positive? |
   |---|---:|---:|---:|---|
   | 2024 H1 | 96 | -0.2030 | -0.0201% | False |
   | 2024 H2 | 101 | -0.0364 | -0.0007% | False |
   | 2025 | 160 | -0.0621 | -0.0310% | False |
   | 2026 | 65 | -0.1097 | -0.0287% | False |

   All folds have negative median net. No temporal period shows profitability.

2. **Control outperformance** (4 controls beat main, all decision-grade):

   | Control | Events | ER | vs Main ER |
   |---|---:|---:|---|
   | Random timing +137 | 421 | -0.0469 | -0.0469 vs -0.0953 (BEATS MAIN) |
   | Breakout w/o compression | 183 | -0.0290 | -0.0290 vs -0.0953 (BEATS MAIN) |
   | Weekday-shuffled | 421 | -0.0896 | -0.0896 vs -0.0953 (BEATS MAIN) |
   | Previous-day range | 308 | -0.0397 | -0.0397 vs -0.0953 (BEATS MAIN) |

   All beating controls have >= 25 events (decision-grade threshold). This indicates:
   - Random timing (shifted +137 bars) is LESS negative than session-aligned timing
   - Previous-day range is LESS negative than same-day Asia range
   - Weekday shuffling is LESS negative than calendar-aligned weekdays
   - Compression/expansion distinction doesn't matter (breakout w/o compression beats main)

3. **MFE accessibility is excellent but returns are negative**:
   - Median MFE consumed: 13.33% (vs reconnaissance 11.54%)
   - This proves entry timing is NOT the problem
   - Structure exists and is reachable, but price does not move favorably after entry
   - Similar to EUR_USD M15 sweep/reclaim (11.63% MFE consumed, still negative expectancy)

4. **Cost sensitivity**:
   - Even at 0.010% cost: ER -0.0715, median net -0.0153% (still negative)
   - At 0.020% cost: ER -0.1192, median net -0.0253% (worse)

   Edge does not exist even at unrealistically low costs.

5. **Horizon sensitivity**:
   - 5 bars: ER -0.0953, median net -0.0203%
   - 8 bars: ER -0.0977, median net -0.0173%
   - 10 bars: ER -0.0898, median net -0.0127%

   Longer horizons slightly less negative but still unprofitable. The reconnaissance follow-through window (8 bars) does not improve results.

### Invalidation Gates Triggered

All major STOP gates fired:
- ✓ median_net_return_lte_0_at_0_015pct_cost (-0.0203%)
- ✓ er_lt_1_0 (-0.0953)
- ✓ profit_factor_lt_1_2 (0.6166)
- ✓ control_cohort_outperforms_main (4 controls beat main)
- ✓ walk_forward_fewer_than_2_positive_folds (0/4)

## Critical Issues

None. Implementation is correct and results are valid.

## Warnings

None.

## Observations

1. **Sample size preserved**: 422 events vs reconnaissance 424 (99.5% retention). The 0.05*ATR14 breakout buffer did NOT collapse the sample. This is different from XAU_USD H1 strict BTC transfer which collapsed to 11 events.

2. **Structure exists but no edge**: Reconnaissance showed 84.43% follow-through and 18.16% false breakout. The diagnostic confirms the structure is real and accessible (MFE 13.33% consumed). But after realistic entry (i+1 open) and costs (0.015%), the returns are negative.

3. **Different controls beat main vs sweep/reclaim**: 
   - **ASIA_RANGE controls beating main**: random timing, breakout w/o compression, weekday-shuffled, previous-day range
   - **EUR_USD M15 sweep/reclaim controls beating main**: opposite direction, wide range high volatility
   
   Different failure modes. Sweep/reclaim: opposite direction was less negative (reversal better). Session breakout: random timing and previous-day range are less negative (timing/reference doesn't matter).

4. **Random timing beats session timing**: control_random_session_timing_137 (ER -0.0469) beats main (ER -0.0953). This suggests the Asia→London timing alignment adds NEGATIVE information, not positive. A random offset is better.

5. **Previous-day range beats same-day Asia range**: control_previous_day_range_breakout (ER -0.0397) beats main (ER -0.0953). This suggests the same-day Asia range is not the informative reference. Any prior range would work equally well (or poorly).

6. **Weekday shuffling beats calendar alignment**: control_weekday_shuffled (ER -0.0896) beats main (ER -0.0953). This suggests the weekday calendar structure doesn't matter. Shuffled weekdays perform equally well.

7. **Compression doesn't matter**: control_breakout_without_prior_asia_compression (ER -0.0290) beats main (ER -0.0953). This suggests the Asia range compression/expansion distinction is not informative. Breakouts from any Asia range (compressed or not) have similar (or better) negative expectancy.

8. **Opposite direction is MUCH worse**: control_opposite_direction (ER -5.9064) is dramatically worse than main (ER -0.0953). This is different from sweep/reclaim where opposite direction was BETTER. Session breakout: direction matters, but in the wrong way (following breakout direction loses money, but reversing loses MORE money).

9. **Cost-independent failure**: Negative at 0.010%, 0.015%, 0.020%. Structure has no expectancy regardless of execution quality.

10. **All folds negative**: Unlike reconnaissance which had 4/4 stable folds showing consistent structure, the diagnostic has 0/4 positive folds showing consistent negative expectancy across all time periods.

## Interpretation

This is a clean STOP result with multiple independent invalidation signals:

- **Negative expectancy** across all time periods (0/4 folds positive)
- **Control outperformance** (4 controls beat main, all decision-grade)
- **Cost-independent failure** (negative even at 0.010% cost)
- **Timing/reference doesn't matter** (random timing, previous-day range, weekday-shuffled all beat main)

The reconnaissance finding that structure exists (424 events, 84% FT, 18% FB, 11% MFE consumed, 4/4 stable folds) remains true. The diagnostic finding that structure has no tradable expectancy is also true. These findings do not contradict - structure can exist without edge.

**Critical insight**: The reconnaissance measured structure (breakout frequency, follow-through rate, false breakout rate, MFE accessibility). All of these metrics were excellent. But they measured GROSS directional movement, not NET profitability after entry/costs/controls. The diagnostic measured NET profitability and found none.

**Why reconnaissance looked promising but diagnostic failed:**
- Reconnaissance: "84.43% of breakouts continue in breakout direction for at least 0.5*ATR within 8 bars"
- Diagnostic: "After entry at i+1 open and 0.015% cost, median net return is -0.0203%"

The follow-through exists, but it's not large enough or fast enough to overcome entry slippage and costs. The median post-entry MFE is only 0.000740 (0.074%), and median cost is 0.000150 (0.015%), leaving only 0.000590 (0.059%) gross return. After inevitable MAE (0.000745), the net is negative.

## Research Verdict: HYPOTHESIS_INVALIDATED

**Hypothesis tested:** OANDA EUR_USD M15 Asia range (00:00-07:00 UTC) → London breakout (07:00-09:00 UTC) with 0.05*ATR14 buffer has tradable expectancy after realistic entry (i+1 open) and costs (0.015%).

**Result:** INVALIDATED

**Evidence:**
- ER: -0.0953 (< 1.0 STOP gate)
- Median net: -0.0203% (negative STOP gate)
- PF: 0.6166 (< 1.2 STOP gate)
- Positive folds: 0/4 (< 2/4 STOP gate)
- Control outperformance: 4 controls beat main (STOP gate)

**Boundary**: This invalidates ASIA_RANGE_LONDON_BREAKOUT on EUR_USD M15 with the tested parameters. It does not test:
- NY_REVERSAL_AFTER_LONDON_EXTENSION (rank #2 from reconnaissance, mean reversion not breakout)
- Multi-asset crypto (ETH/SOL with full BTC feature set, no degradation)
- Different OANDA instruments (XAU already STOP on sweep/reclaim)
- Alternative session windows (tested windows frozen in planning)

## Sequential Research Path

User-approved sequence:
1. **ASIA_RANGE_LONDON_BREAKOUT** → **STOP** (this diagnostic)
2. **NY_REVERSAL_AFTER_LONDON_EXTENSION** → next if user approves
3. **Multi-asset crypto (ETH/SOL)** → fallback if both OANDA session mechanisms STOP

## Recommended Next Step

**Do not pursue ASIA_RANGE V2 or parameter tuning.**

**Reason:**
- Controls beat main (random timing, previous-day range, weekday-shuffled, breakout w/o compression)
- This suggests the session timing, Asia range reference, weekday structure, and compression distinction are NOT informative
- Parameter tuning cannot rescue a hypothesis where random timing beats session alignment
- 0/4 positive folds with consistent negative expectancy across all periods

**Next options:**

### Option A: NY_REVERSAL_AFTER_LONDON_EXTENSION (recommended next if continuing OANDA)

**Why:**
- Rank #2 from reconnaissance (367 events, 84.74% FT, 19.07% FB, 16.46% MFE consumed, 4/4 stable folds)
- **Different mechanism**: mean reversion (fade extended London moves during NY overlap) vs breakout continuation
- **Different control profile**: if NY_REVERSAL succeeds where ASIA_RANGE failed, it would show the difference between continuation vs reversal edges on OANDA

**Timeline:** Planning 2-3 days, diagnostic 3-5 days, total ~1 week

**Risk:** May also STOP (OANDA lacks TFI/OI/funding, controls may beat main again)

**Justification for one more attempt:**
- ASIA_RANGE tested breakout continuation, NY_REVERSAL tests mean reversion
- Reconnaissance showed NY_REVERSAL has similar strong structure (84.74% FT vs 84.43%)
- If NY_REVERSAL also STOPS, we've tested both major session mechanisms (continuation and reversion)

### Option B: Multi-asset crypto (ETH/SOL) - recommended if skipping NY_REVERSAL

**Why:**
- BTC trial-00095 validated (ER 2.121, PF 4.216, 274 trades)
- ETH/SOL have FULL BTC feature set (TFI, OI, funding, CVD, force orders)
- NO degraded transfer (OANDA lost all crypto-native features)
- Binance infrastructure exists for ETH/SOL (same API as BTC)
- **Profit impact**: 3× instruments = potentially 3× trade frequency

**Timeline:** Planning 1-2 days, diagnostic 3-5 days, total ~1 week

**Risk:** Low (validated edge, established infrastructure, only question is whether BTC edge transfers to ETH/SOL)

**If multi-asset crypto diagnostic passes:**
- Immediate PAPER setup for 3-asset portfolio
- Potential 3× trade frequency vs BTC-only
- Diversification across crypto assets

---

## User Decision Required

A) **NY_REVERSAL_AFTER_LONDON_EXTENSION** planning (one more OANDA attempt, different mechanism)  
B) **Multi-asset crypto (ETH/SOL)** planning (skip OANDA, validated edge transfer)  
C) **Both in sequence** (NY_REVERSAL first, multi-asset crypto if NY STOPS)  
D) **Stop research** (focus on BTC trial-00095 PAPER validation, no expansion)

**My recommendation:** Option C (NY_REVERSAL → multi-asset crypto if STOP)

**Reasoning:**
- Reconnaissance showed 2 strong candidates (ASIA breakout #1, NY reversal #2)
- We tested continuation (ASIA), should test reversion (NY) before concluding "OANDA has no session edge"
- If NY also STOPS: move to multi-asset crypto with confidence that OANDA session structure (both mechanisms) is not profitable
- Total additional time: ~1 week (NY planning+diagnostic), then multi-asset crypto if needed

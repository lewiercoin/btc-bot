# AUDIT: OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1_DIAGNOSTIC

Date: 2026-05-31
Auditor: Claude Code
Commit: e36a440f0e2f9833fc86a437dea24a2f7e7a216e
Scope: Diagnostic implementation and results analysis

## Verdict: DONE_IMPLEMENTATION_CORRECT / HYPOTHESIS_INVALIDATED

## Implementation Correctness: PASS

### Timing Model: PASS

Verified in code (lines 517-525):
- level_known_bar = detection_bar - 1 ✓
- detection_bar = i ✓
- state_known_bar = detection_bar (bar i close) ✓
- entry_candidate_bar = detection_bar + 1 ✓
- return_start_bar = entry_candidate_bar ✓

Entry price: bar i+1 open (line 460) ✓
Returns measured from entry only (lines 469-509) ✓
MFE before entry vs after entry correctly separated (lines 477-507) ✓

No lookahead violations.

### Frozen Parameters: PASS

| Parameter | Planning | Implementation | Match |
|---|---|---|---|
| min_sweep_depth_pct | 0.03% | 0.00030 (line 83) | ✓ |
| reclaim_buf_atr | 0.07 | 0.07 (line 79) | ✓ |
| primary_cost_pct | 0.015% | 0.00015 (line 90) | ✓ |
| primary_horizon_bars | 5 | 5 (line 88) | ✓ |
| entry_delay_bars | 1 | 1 (line 85) | ✓ |

All frozen parameters match planning document.

### Control Cohorts: PASS

8 control cohorts implemented as planned:
1. control_sweep_without_reclaim (20,503 events)
2. control_reclaim_without_equal_level_sweep (0 events)
3. control_random_offset_137 (1,544 events)
4. control_shifted_entry_plus2 (1,547 events)
5. control_shifted_entry_plus3 (1,547 events)
6. control_opposite_direction (1,547 events) - **BEATS MAIN**
7. control_shallow_sweep (1,814 events)
8. control_wide_range_high_volatility (348 events) - **BEATS MAIN**

Control implementation verified (lines 573-656):
- control_opposite_direction: enters opposite direction at same timing
- control_wide_range_high_volatility: filters main events by range_width_pct >= 75th percentile

Both outperforming controls have >= 25 events (decision-grade threshold).

### Data Quality: PASS

- 59,989 candles from 2024-01-01 to 2026-05-29
- 0 OHLC bad rows
- 0 duplicate timestamps
- 0 gaps > 72h
- Max gap: 49.25 hours (weekend closure)

### Test Coverage: PASS

5/5 pytest tests passed in 0.12s.

## Methodology Integrity: PASS

- Prior XAU_USD H1 STOP verdict preserved (report line 11)
- No SMC rescue
- No post-result parameter tuning
- Sample size: 1,547 events (above 200 EXPLORE threshold, below reconnaissance 3,419 baseline)
- MFE accessibility: 11.63% consumed (excellent, well below 70% STOP gate)
- Walk-forward: 4 folds tested, 0/4 positive
- Cost sensitivity: tested at 0.010%, 0.015%, 0.025%

## Results Analysis: HYPOTHESIS_INVALIDATED

### Primary Metrics (0.015% cost)

| Metric | Main | BTC trial-00095 | Delta |
|---|---:|---:|---|
| Events | 1,547 | 274 | +463% |
| ER | -0.2226 | 2.121 | -2.34 |
| PF | 0.7146 | 4.216 | -3.50 |
| Win rate | 42.79% | 56.57% | -13.78pp |
| Median net | -0.0159% | N/A | negative |

### Critical Findings

1. **Negative expectancy across all folds**: 0/4 folds positive, all folds have median net < 0
   - fold_1_2024H1: -0.0076%
   - fold_2_2024H2: -0.0094%
   - fold_3_2025: -0.0202%
   - fold_4_2026: -0.0163%

2. **Control outperformance** (decision-grade):
   - control_opposite_direction: ER -0.0926 vs main -0.2226 (1,547 events)
   - control_wide_range_high_volatility: ER -0.1719 vs main -0.2226 (348 events)

   Both controls are less negative than main, indicating the sweep/reclaim signal adds negative information.

3. **MFE accessibility is excellent but returns are negative**:
   - Median MFE consumed: 11.63% (well below 70% STOP gate, below 60% EXPLORE target)
   - This proves the edge is NOT lost to delayed entry
   - The structure exists and is reachable, but price does not move favorably after entry

4. **Cost sensitivity**:
   - Even at 0.010% cost: ER -0.1501, median net -0.0109% (still negative)
   - At 0.025% cost: ER -0.3676, median net -0.0259% (worse)

   The edge does not exist even at unrealistically low costs.

### Invalidation Gates Triggered

All major STOP gates fired:
- ✓ median_net_return_lte_0_at_0_015pct_cost (-0.0159%)
- ✓ er_lt_1_0 (-0.2226)
- ✓ profit_factor_lt_1_2 (0.7146)
- ✓ control_cohort_outperforms_main (2 controls beat main)
- ✓ walk_forward_fewer_than_2_positive_folds (0/4)

## Artifact Integrity: PASS

- JSON SHA256: `ea592327ced64afc316a57381149b5e7afcd23b9ba8e26efce7465be5e6a8750` (verified)
- Markdown report: complete, all sections present
- Test suite: 5/5 passed
- No credentials in committed code

## Critical Issues

None. Implementation is correct and results are valid.

## Warnings

None.

## Observations

1. **Structure exists but no edge**: The reconnaissance baseline of 3,419 candidates reduced to 1,547 after the 0.03% depth threshold, but this is still a decision-grade sample. The MFE accessibility is excellent (11.63% consumed). The structure is real and reachable, but it has no tradable expectancy.

2. **Opposite direction beats main**: control_opposite_direction has ER -0.0926 vs main -0.2226. This suggests the sweep/reclaim signal is negatively informative - the opposite trade would be better (though still negative).

3. **High volatility context beats main**: control_wide_range_high_volatility (348 events, top quartile range width) has ER -0.1719 vs main -0.2226. This suggests the edge deteriorates further in normal volatility conditions.

4. **Degraded transfer confirmed**: Loss of TFI (corr 0.23), OI (0.13), funding (0.11), CVD, and force orders means the OHLC-only structure cannot replicate BTC trial-00095 performance. The diagnostic correctly validates this hypothesis: OANDA sweep/reclaim alone is not tradable.

5. **Not a data quality issue**: 59,989 clean candles over 2.4 years, 0 OHLC violations, 1,547 events. The sample is sufficient to validate the STOP verdict.

6. **Not an entry timing issue**: Median MFE consumed 11.63% proves the entry is not too late. The favorable move exists after entry but does not persist to the horizon.

## Interpretation

This is a clean STOP result with multiple independent invalidation signals:

- **Negative expectancy** across all time periods (0/4 folds positive)
- **Control outperformance** (opposite direction and high volatility beat main)
- **Cost-independent failure** (negative even at 0.010% cost)

The reconnaissance finding that structure exists (3,419 candidates, 11.96% MFE consumed) remains true. The diagnostic finding that structure has no tradable expectancy is also true. These findings do not contradict - structure can exist without edge.

The degraded transfer hypothesis is validated: removing TFI, OI, funding, CVD, and force orders from the BTC trial-00095 signal removes the expectancy. OHLC-only sweep/reclaim on OANDA is not tradable.

## Research Verdict: HYPOTHESIS_INVALIDATED

**Hypothesis tested:** OHLC-only sweep/reclaim structure transfers from BTC to OANDA EUR_USD M15 with tradable expectancy after realistic costs.

**Result:** INVALIDATED

**Evidence:**
- ER: -0.2226 (< 1.0, STOP gate)
- Median net: -0.0159% (negative, STOP gate)
- PF: 0.7146 (< 1.2, STOP gate)
- Positive folds: 0/4 (< 2, STOP gate)
- Control outperformance: 2 controls beat main (STOP gate)

**Boundary:** This invalidates OHLC-only sweep/reclaim on OANDA EUR_USD M15 with the tested parameters. It does not test:
- OANDA with alternative hypotheses (not sweep/reclaim)
- Multi-asset crypto (ETH/SOL) with full BTC feature set
- Different OANDA instruments (XAU already tested and STOP)
- Alternative reclaim windows (0-bar same-close tested only)

## Recommended Next Step

**Do not pursue OANDA sweep/reclaim V2.**

**Reason:**
- Both XAU_USD H1 (11 events) and EUR_USD M15 (1,547 events) diagnostics returned STOP
- Different failure modes: XAU had insufficient sample; EUR had decision-grade sample but negative expectancy and control outperformance
- OHLC-only structure is not sufficient without crypto-native features (TFI, OI, funding, CVD, force orders)
- No parameter tuning can rescue a hypothesis where controls beat main

**Next:**

Option A: **Multi-asset crypto expansion (ETH/SOL)** - recommended
- Preserves full BTC feature set (TFI, OI, funding, CVD, force orders)
- No degraded transfer
- Validated edge applied to additional instruments
- Planning document already exists (pending from prior milestone tracker)

Option B: **Focus on trial-00095 PAPER validation**
- Current BTC bot is working (ER 2.121, PF 4.216)
- Milestone tracker shows PAPER_NEAR_MISS_MONITORING_V1 is ACTIVE
- Complete 30-day PAPER monitoring before live promotion

**Do not:**
- Tune OANDA sweep/reclaim parameters
- Add SMC filters to rescue OANDA hypothesis
- Test other OANDA instruments without a new hypothesis
- Combine OANDA with crypto signals

---

**User decision required:** Which direction to pursue next?

A. Multi-asset crypto expansion (ETH/SOL)
B. Focus on trial-00095 PAPER validation
C. Other (user specifies)

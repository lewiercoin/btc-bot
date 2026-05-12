# CLAUDE HANDOFF → CODEX

## Checkpoint

- **Last commit:** `bf5543f` - "research: report absorption continuation rejection"
- **Branch:** `research/trend-continuation-v1`
- **Working tree:** Clean (only untracked artifacts)
- **Phase 2 status:** Checkpoint 2 REJECT verdict confirmed

## Iteration Context

**Milestone:** ABSORPTION-CONTINUATION-RESEARCH-V1-ITERATION-A

**Type:** Diagnostic iteration (ONE ATTEMPT ONLY)

**Purpose:** Fix two obvious measurement errors before abandoning trend-continuation hypothesis:
1. CVD calculation may be broken (relying on pre-calculated boolean instead of actual pullback window)
2. Volatility panic threshold miscalibrated (rejects 90% of cycles with arbitrary 0.008 constant)

**NOT:** Parameter rescue, gate loosening, or grid search to "make it work"

**Hard constraint:** If after these fixes we still get <20 trades or uptrend ER <1.5, hypothesis is FAILED → move to compression_breakout (Option B)

## Why This Iteration Is Justified

### Problem 1: CVD Measurement

**Current implementation:**
```python
# Relies on pre-calculated boolean from features
cvd_bullish_divergence = features.cvd_bullish_divergence
```

**Why this may be wrong:**
- Boolean is calculated on some unspecified lookback period
- Not aligned with actual pullback window
- May be backward-looking (stale signal)
- "Divergence" definition may not match our absorption hypothesis

**Evidence of problem:**
- Only CVD divergence trade: **LOST** (-1.5R)
- Only large winner: **NO CVD divergence** (+6.4R)
- 25% hit rate (anti-predictive)

**Fix:** Calculate CVD change over actual pullback window

### Problem 2: Volatility Panic Threshold

**Current implementation:**
```python
# Arbitrary constant
volatility_panic = atr_4h_norm > 0.008  # 0.8%
```

**Why this may be wrong:**
- Rejects 134,649 / 148,596 cycles (90.6%)
- Threshold appears to be guessed, not empirically derived
- May be excluding normal volatility as "panic"

**Fix:** Calculate empirical distribution, set threshold at meaningful percentile (90th or 95th)

## Scope: Two Changes ONLY

### Change A1: CVD Slope Calculation

**Implementation:**

```python
def calculate_cvd_absorption(
    features: Features,
    snapshot: MarketSnapshot,
    pullback_window_bars: int = 12  # e.g., 3 hours at 15m bars
) -> tuple[bool, float]:
    """
    Calculate CVD slope over pullback window.
    
    Absorption = CVD rising while price falling during pullback.
    
    Returns:
        (absorption_confirmed, cvd_slope)
    """
    # Get CVD history for pullback window
    cvd_history = get_recent_cvd(snapshot, lookback_bars=pullback_window_bars)
    
    # Calculate slope (linear regression or simple delta)
    cvd_start = cvd_history[0]
    cvd_end = cvd_history[-1]
    cvd_slope = (cvd_end - cvd_start) / pullback_window_bars
    
    # Absorption = CVD rising (slope > threshold)
    # Threshold: e.g., 0.0 (any positive slope) or small positive value
    absorption_confirmed = cvd_slope > cvd_slope_threshold
    
    return (absorption_confirmed, cvd_slope)
```

**Required data:**
- CVD 15m history (available in features as `cvd_15m`)
- Need to store recent CVD values or calculate from aggtrade_buckets

**If CVD history not readily available:**
- Use simple proxy: `cvd_15m` current vs recent_low
- Compare CVD at pullback_start vs CVD at current bar
- Slope = (cvd_current - cvd_pullback_start) / pullback_duration

**Parameter to test:**
- `cvd_slope_threshold`: Start with 0.0 (any positive slope)
- If too noisy, try 0.01 or 0.05 (small positive slope required)

**Add to reasons[]:**
```python
f"cvd_slope_pullback_window={cvd_slope:.4f}",
f"cvd_absorption_confirmed={absorption_confirmed}",
```

### Change A2: Empirical Volatility Panic Threshold

**Step 1: Calculate empirical distribution**

```python
def analyze_atr_norm_distribution(
    data_range: tuple[str, str] = ("2022-01-01", "2026-03-29")
) -> dict:
    """
    Calculate empirical distribution of atr_4h_norm.
    
    Returns percentiles: 50th, 75th, 90th, 95th, 99th
    """
    # Load all feature snapshots in range
    atr_norm_values = []
    
    for snapshot in iterate_snapshots(data_range):
        features = calculate_features(snapshot)
        atr_norm_values.append(features.atr_4h_norm)
    
    # Calculate percentiles
    percentiles = {
        "p50": np.percentile(atr_norm_values, 50),
        "p75": np.percentile(atr_norm_values, 75),
        "p90": np.percentile(atr_norm_values, 90),
        "p95": np.percentile(atr_norm_values, 95),
        "p99": np.percentile(atr_norm_values, 99),
        "mean": np.mean(atr_norm_values),
        "std": np.std(atr_norm_values),
    }
    
    return percentiles
```

**Step 2: Set panic threshold**

**Recommended:** Use 90th or 95th percentile

**Why:** "Panic" should be rare, not 90% of the time

**Example:**
```python
# Run analysis
atr_distribution = analyze_atr_norm_distribution()

# Set threshold
volatility_panic_threshold = atr_distribution["p90"]  # or p95

# Use in filter
volatility_panic = features.atr_4h_norm > volatility_panic_threshold
```

**Document in report:**
- Empirical percentiles
- Chosen threshold (p90 or p95)
- Rejection rate after recalibration

**Add to reasons[]:**
```python
f"atr_4h_norm={atr_4h_norm:.6f}",
f"volatility_panic_threshold={volatility_panic_threshold:.6f}",
f"volatility_panic={atr_4h_norm > volatility_panic_threshold}",
```

## Implementation Plan

### Step 1: Empirical Analysis (0.5 day)

**A. Calculate ATR norm distribution**
- Script: `research_lab/analyze_atr_distribution.py`
- Output: Percentiles table
- Document in: `research_lab/reports/atr_norm_distribution_2022_2026.md`

**B. Validate CVD availability**
- Check: Can we reconstruct CVD history for pullback window?
- If yes: Implement full CVD slope calculation
- If no: Use simple proxy (cvd_current vs cvd_recent_low)

### Step 2: Update Setup Logic (0.5 day)

**Modify:** `research_lab/setups/absorption_continuation.py`

**Changes:**
1. Replace `cvd_bullish_divergence` boolean with CVD slope calculation
2. Replace `atr_4h_norm > 0.008` with empirical threshold (p90 or p95)
3. Update reasons[] to include new metrics

**No other changes:** All other filters remain identical

### Step 3: Re-run Backtest (0.5 day)

**Same protocol as Checkpoint 2:**
- Date range: 2022-01-01 → 2026-03-29
- Setup: absorption_continuation_long ONLY
- Output: Full metrics, rejection funnel, trade list

**Success criteria (HARD GATES):**
- Minimum trades: **≥ 20** (statistical validity)
- Uptrend ER: **> 1.5** (edge threshold)
- Absorption hit rate: **> 50%** (CVD slope predictive)
- Win rate: **> 40%** (credible)

**If any gate fails → STOP, verdict = FAILED**

### Step 4: Analysis & Verdict (0.5 day)

**If success criteria met:**
- Run walk-forward (2 windows)
- Calculate overlap vs sweep-reclaim
- Measure trend day capture
- Prepare updated audit package
- Verdict: ITERATE SUCCESSFUL → CANDIDATE FOR PHASE 2.5

**If success criteria NOT met:**
- Document failure analysis
- Verdict: HYPOTHESIS FAILED → recommend compression_breakout (Option B)
- Do NOT attempt further iterations
- Do NOT loosen gates
- Do NOT grid search parameters

### Step 5: Commit & Push (checkpoint)

**If successful:**
```
research: iteration A successful - absorption validated

WHAT: Fixed CVD slope calculation + empirical volatility threshold
WHY: Original measurement errors corrected
RESULT: [trades] trades, uptrend ER [X.XX], ready for Phase 2.5
```

**If failed:**
```
research: iteration A failed - abandon absorption hypothesis

WHAT: Fixed CVD + volatility threshold, re-run backtest
WHY: Validate if measurement errors caused rejection
RESULT: Still <20 trades / ER <1.5, hypothesis fundamentally flawed
RECOMMENDATION: Move to compression_breakout (Option B)
```

## Hard Stop Conditions

### STOP if any of these true after re-run:

1. **Total trades < 20** → Statistical validity failed
2. **Uptrend ER < 1.5** → No edge in target regime
3. **Absorption hit rate < 50%** → CVD slope not predictive
4. **Win rate < 40%** → Below credible threshold

### Do NOT:

- ❌ Loosen gates ("maybe 15 trades is enough")
- ❌ Grid search other parameters
- ❌ Try additional iterations ("maybe if we also change...")
- ❌ Mix with sweep-reclaim to boost metrics
- ❌ Cherry-pick favorable sub-periods

### DO:

- ✅ Document exact failure reason
- ✅ Recommend compression_breakout as next setup
- ✅ Prepare handoff for Option B (if user approves)

## Timeline

**Total: ~2 days**

| Step | Time |
|---|---|
| Empirical analysis (ATR distribution, CVD validation) | 0.5 day |
| Update setup logic (CVD slope, volatility threshold) | 0.5 day |
| Re-run backtest | 0.5 day |
| Analysis & verdict | 0.5 day |

**Then:** Claude Code audit (0.5 day) → User decision (proceed or switch)

## Expected Outcomes

### Scenario 1: SUCCESS (20-30% probability)

**Metrics after fixes:**
- Trades: 50-100 (reasonable sample)
- Uptrend ER: 1.8-2.5 (valid edge)
- Absorption hit rate: 55-65% (CVD slope predictive)
- Win rate: 45-55% (credible)

**Next:** WF validation, overlap analysis, trend day capture, Phase 2.5

### Scenario 2: MARGINAL IMPROVEMENT (30-40% probability)

**Metrics:**
- Trades: 20-40 (minimal sample)
- Uptrend ER: 1.2-1.5 (borderline)
- Absorption hit rate: 45-55% (weak)

**Verdict:** Still REJECT - edge too weak, not worth Phase 2.5 complexity

### Scenario 3: STILL FAILED (40-50% probability)

**Metrics:**
- Trades: <20 OR uptrend ER <1.5
- Absorption hit rate: <50%

**Verdict:** HYPOTHESIS FAILED - CVD/volatility fixes didn't help

**Conclusion:** Trend-continuation/absorption angle is wrong for BTC perps

**Next:** Move to compression_breakout (different structure, different data)

## Why Stop After One Iteration

**Reason 1:** Two measurement issues identified, both fixed → fair test

**Reason 2:** If CVD slope + correct volatility threshold don't expose edge, edge likely doesn't exist

**Reason 3:** Avoid "endless parameter tuning" trap:
- First iteration: "fix CVD"
- Second iteration: "fix volatility"
- Third iteration: "fix pullback definition"
- Fourth iteration: "fix trend structure"
- → Never ends, no learning

**Discipline:** One iteration to fix measurement, then hard decision (keep or abandon)

## Deliverables (Same as Checkpoint 2)

1. ✅ `research_lab/analyze_atr_distribution.py` (new)
2. ✅ `research_lab/reports/atr_norm_distribution_2022_2026.md` (new)
3. ✅ Updated `absorption_continuation.py` (CVD slope, empirical threshold)
4. ✅ Re-run backtest output
5. ✅ Updated validation report (metrics, verdict)
6. ✅ Updated audit package (CANDIDATE or FAILED)

**If FAILED:**
7. ✅ Failure analysis document
8. ✅ Recommendation: compression_breakout specification

## No-Touch Areas (Unchanged)

- `orchestrator.py`
- `core/signal_engine.py`
- `execution/**`
- `governance/**`
- `risk/**`
- `settings.py`

All work stays in `research_lab/**`, `tests/**`, `docs/**`

## Critical Reminders

### This Is NOT Parameter Optimization

**We are fixing measurement errors, not tuning for results:**
- CVD slope: Calculate correctly (not guess at threshold)
- Volatility panic: Use empirical percentile (not guess at 0.008)

**If edge exists, correct measurement will expose it.**
**If edge doesn't exist, no amount of tuning will create it.**

### One Iteration = One Chance

**After A1 + A2:**
- Edge validates → proceed
- Edge fails → stop

**No:**
- "Maybe try different CVD threshold"
- "Maybe try different percentile"
- "Maybe add another confirmation"

**This prevents endless parameter search.**

### Prepare for Option B

**If iteration fails:**
- User will likely choose compression_breakout next
- Start thinking about compression setup hypothesis
- Review available data (ATR compression, OI, funding)

**Don't:**
- Start implementing Option B preemptively
- Assume iteration will fail

**Do:**
- Give absorption hypothesis fair chance with corrected measurement
- Be ready to pivot if it fails

## Questions Before Starting?

**Expected:** None - scope is narrow, changes are specific

**If questions:**
- CVD history availability? → Check aggtrade_buckets or features table
- Percentile choice (p90 vs p95)? → Start with p90, document both
- Pullback window size? → 12 bars (3 hours at 15m) is reasonable default

## Start Implementation

**Your first response should confirm:**
1. Scope understood (A1 + A2 only, no other changes)
2. Success criteria clear (≥20 trades, ER >1.5, hit rate >50%)
3. Hard stop understood (if fails → compression_breakout, no further iterations)
4. Timeline reasonable (~2 days)

**Then:** Begin with empirical analysis (ATR distribution), proceed to setup updates, re-run, verdict.

---

**Handoff complete. Branch `research/trend-continuation-v1` is ready for iteration A.**

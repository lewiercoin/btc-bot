# CLAUDE HANDOFF → CODEX

## Checkpoint

- **Last commit:** `9dcf45f` - "audit: COMPRESSION-BREAKOUT-CHECKPOINT-1 — ITERATE (regime classification issue)"
- **Branch:** `research/compression-breakout-v1`
- **Working tree:** Clean (continue on same branch)
- **Checkpoint 1 status:** ITERATE (0 compression regime trades, regime classification suspect)

## Iteration Context

**Milestone:** COMPRESSION-BREAKOUT-RESEARCH-V1-ITERATION-A

**Type:** Diagnostic iteration (ONE ATTEMPT ONLY)

**Purpose:** Fix regime classification measurement error before abandoning compression_breakout hypothesis:
1. Regime distribution analysis (empirical count of COMPRESSION-labeled cycles 2022-2026)
2. If COMPRESSION labels rare/absent: adjust setup to use regime as VETO (not main trigger), rely on internal compression detection

**NOT:** Parameter rescue, gate loosening, or grid search to "make it work"

**Hard constraint:** If after these fixes we still get <20 trades or compression ER <1.5 or breakout follow-through <40%, hypothesis is FAILED → move to crowded_unwind (Option B)

---

## Why This Iteration Is Justified

### Problem: 0 Compression Regime Trades

**Current result:**
- Total trades: 3
- Compression regime trades: **0** (target regime)
- Normal regime trades: 3 (all trades)
- Cannot validate compression → breakout hypothesis without compression regime data

**Why this may be wrong:**
- RegimeEngine may not label COMPRESSION states (classification gap)
- COMPRESSION labels may be extremely rare (<1% of cycles)
- Setup allows `{COMPRESSION, NORMAL}` but trades only happen in `NORMAL`

**Evidence of problem:**
- Setup has internal compression detection (ATR percentile, range width)
- Tests pass (compression logic is sound)
- But regime filter may be too restrictive if RegimeEngine doesn't label COMPRESSION

**This is analogous to absorption's volatility threshold issue:**
- Absorption: Arbitrary threshold (0.008) rejected 90% cycles → Fixed with empirical p95
- Compression: Regime filter blocks compression trades if COMPRESSION labels absent → Fix by using regime as veto

---

## Scope: Two Changes ONLY

### Change A1: Regime Distribution Analysis

**Implementation:**

```python
# File: research_lab/analyze_regime_distribution.py

def analyze_regime_distribution(
    db_path: str = "storage/btc_bot.db",
    start_date: str = "2022-01-01",
    end_date: str = "2026-03-29"
) -> dict:
    """
    Count how many decision cycles were labeled as each regime.
    
    Returns:
        {
            "total_cycles": int,
            "regime_counts": {
                "normal": int,
                "uptrend": int,
                "downtrend": int,
                "compression": int,
                "crowded_leverage": int,
                "post_liquidation": int,
            },
            "regime_percentages": {
                "normal": float,
                ...
            }
        }
    """
    # Query decision_outcomes table for regime distribution
    # Count cycles per regime
    # Calculate percentages
    pass
```

**Expected outcome:**
- If COMPRESSION < 1% of cycles → RegimeEngine doesn't detect compression well
- If COMPRESSION > 5% → Setup filters may be too strict
- Document findings in report

**Output:** `research_lab/reports/regime_distribution_2022_2026.md`

**Report format:**
```markdown
# Regime Distribution Analysis

Date range: 2022-01-01 to 2026-03-29
Total cycles: 148,596

## Regime Counts

| Regime | Count | Percentage |
|---|---:|---:|
| normal | X | XX.X% |
| uptrend | X | XX.X% |
| downtrend | X | XX.X% |
| compression | X | XX.X% |
| crowded_leverage | X | XX.X% |
| post_liquidation | X | XX.X% |

## Interpretation

- If compression < 1%: RegimeEngine rarely labels compression states
- If compression 1-5%: Compression is rare but present
- If compression > 5%: Compression labels exist, setup filters may block

## Recommendation

[Based on findings, recommend regime filter adjustment or setup logic review]
```

---

### Change A2: Regime Filter Adjustment (If COMPRESSION Labels Rare)

**Current regime filter:**
```python
def check_regime_allowed(self, regime: RegimeState | str) -> bool:
    return _regime_value(regime) in {RegimeState.COMPRESSION.value, RegimeState.NORMAL.value}
```

**Problem:** If RegimeEngine never labels COMPRESSION, setup never activates in target regime.

**Solution:** Use regime as **VETO** (block wrong regimes), not main trigger. Let setup's internal compression detection (ATR percentile, range width, breakout) drive activation.

**New regime filter:**
```python
def check_regime_allowed(self, regime: RegimeState | str) -> bool:
    """
    Use regime as veto: block trending/crowded regimes where compression setup should NOT activate.
    Accept any other regime (normal, compression) and rely on setup's internal compression detection.
    
    Rationale: If RegimeEngine doesn't label COMPRESSION consistently, setup's ATR percentile
    and range width detection is more reliable for identifying compression states.
    """
    blocked_regimes = {
        RegimeState.UPTREND.value,      # Trending moves (separate setup)
        RegimeState.DOWNTREND.value,    # Trending moves (separate setup)
        RegimeState.CROWDED_LEVERAGE.value,  # Crowded extreme (veto)
        RegimeState.POST_LIQUIDATION.value,  # Liquidation cascade (veto)
    }
    return _regime_value(regime) not in blocked_regimes
```

**Reasoning:**
- Setup has objective compression detection (ATR percentile < p20, range width < threshold)
- If this detects compression correctly, but RegimeEngine doesn't label it, use internal detection
- Regime becomes safety veto: "Don't activate during trends/crowded", not "Only activate when labeled compression"

**Trade-off:**
- Pro: Can test compression → breakout hypothesis even if RegimeEngine labeling incomplete
- Con: May activate in "normal" periods that aren't true compression
- Mitigation: Setup's internal filters (ATR percentile, range width, compression duration) provide compression confirmation

**Add to reasons[]:**
```python
f"regime={_regime_value(regime)}",
f"regime_veto={'blocked' if not check_regime_allowed(regime) else 'allowed'}",
f"internal_compression_detected={metrics['atr_percentile'] < threshold}",
```

**Update documentation:**
```python
# In compression_breakout.py docstring:
"""
Regime usage:
- Primary: Internal compression detection (ATR percentile, range width, duration)
- Regime: Veto only (blocks uptrend/downtrend/crowded, accepts normal/compression)
- Rationale: RegimeEngine may not consistently label compression states
"""
```

---

### Alternative: If COMPRESSION Labels Exist (>5%)

**If empirical analysis shows COMPRESSION labels are present:**
- Do NOT change regime filter
- Instead: Review setup filters to identify what blocks activation when regime=COMPRESSION
- Check rejection reasons for compression-regime cycles
- May need to adjust compression detection thresholds (e.g., ATR percentile p20 → p30)

**But:** This is less likely. Checkpoint 1 had 0 compression regime trades, suggesting labels are rare/absent.

---

## Implementation Plan

### Step 1: Empirical Analysis (0.5 day)

**A. Calculate regime distribution**
- Script: `research_lab/analyze_regime_distribution.py`
- Query `decision_outcomes` table for regime field (2022-2026)
- Count cycles per regime
- Calculate percentages
- Output: `research_lab/reports/regime_distribution_2022_2026.md`

**B. Interpret findings**
- If COMPRESSION < 1%: Proceed to A2 (regime filter adjustment)
- If COMPRESSION > 5%: Review setup filters for compression-regime blocking
- Document interpretation in report

---

### Step 2: Update Setup Logic (0.5 day)

**If COMPRESSION labels rare (<1%):**

**Modify:** `research_lab/setups/compression_breakout.py`

**Changes:**
1. Update `check_regime_allowed()` to use regime as veto (block trends/crowded, accept others)
2. Add regime veto documentation in docstring
3. Update reasons[] to include regime veto status + internal compression detection
4. Update tests to reflect new regime logic

**Test updates:**
- `test_compression_breakout_blocks_wrong_regime` → ensure uptrend/downtrend/crowded blocked
- `test_compression_breakout_accepts_normal_if_compressed` → ensure normal accepted if internal compression detected

**No other changes:** All other filters (ATR percentile, range width, breakout confirmation, TFI/OI) remain identical.

---

### Step 3: Re-run Backtest (0.5 day)

**Same protocol as Checkpoint 1:**
- Date range: 2022-01-01 → 2026-03-29
- Setup: compression_breakout_long ONLY
- Output: Full metrics, rejection funnel, per-regime breakdown, trade list

**Success criteria (HARD GATES):**
- Minimum trades: **≥ 20** (statistical validity)
- Compression-detected trades: **≥ 10** (using internal detection, not regime label)
- Compression ER (or low-volatility ER): **> 1.5** (edge threshold)
- Breakout follow-through: **> 40%** (thesis validation - breakouts must follow through)
- Win rate: **> 35%** (credible)

**If any gate fails → STOP, verdict = FAILED**

---

### Step 4: Analysis & Verdict (0.5 day)

**If success criteria met:**
- Run walk-forward (2 windows)
- Overlap vs sweep_reclaim analysis (<30% gate)
- Breakout follow-through cohort analysis (TFI/OI confirmation effectiveness)
- Prepare updated audit package
- Verdict: ITERATE SUCCESSFUL → CANDIDATE FOR PHASE 2.5

**If success criteria NOT met:**
- Document failure analysis
- Verdict: HYPOTHESIS FAILED → recommend crowded_unwind (Option B)
- Do NOT attempt further iterations
- Do NOT loosen gates
- Do NOT grid search parameters

---

### Step 5: Commit & Push (checkpoint)

**If successful:**
```
research: iteration A successful - compression validated

WHAT: Fixed regime classification (regime as veto + internal compression detection)
WHY: RegimeEngine rarely labels COMPRESSION (<1% of cycles), setup's ATR/range detection more reliable
RESULT: [X] trades, compression ER [X.XX], breakout follow-through [XX%], ready for Phase 2.5
```

**If failed:**
```
research: iteration A failed - abandon compression hypothesis

WHAT: Fixed regime classification, re-run backtest
WHY: Validate if regime labeling was the blocker
RESULT: Still <20 trades / ER <1.5 / follow-through <40%, hypothesis fundamentally flawed
RECOMMENDATION: Move to crowded_unwind (Option B)
```

---

## Hard Stop Conditions

### STOP if any of these true after re-run:

1. **Total trades < 20** → Statistical validity failed
2. **Compression-detected trades < 10** → Internal detection not finding compression either
3. **Compression ER < 1.5** → No edge in target structure
4. **Breakout follow-through < 40%** → Thesis invalid (breakouts don't follow through)
5. **Win rate < 35%** → Below credible threshold

### Do NOT:

- ❌ Loosen gates ("maybe 15 trades is enough")
- ❌ Grid search other parameters
- ❌ Try additional iterations ("maybe if we also change...")
- ❌ Mix with sweep-reclaim to boost metrics
- ❌ Cherry-pick favorable sub-periods

### DO:

- ✅ Document exact failure reason
- ✅ Recommend crowded_unwind as next setup
- ✅ Prepare handoff for Option B (if user approves)

---

## Timeline

**Total: ~2 days**

| Step | Time |
|---|---|
| Empirical analysis (regime distribution) | 0.5 day |
| Update setup logic (regime veto) | 0.5 day |
| Re-run backtest | 0.5 day |
| Analysis & verdict | 0.5 day |

**Then:** Claude Code audit (0.5 day) → User decision (proceed or switch)

---

## Expected Outcomes

### Scenario 1: SUCCESS (30-40% probability)

**Metrics after regime fix:**
- Trades: 30-60 (reasonable sample)
- Compression-detected trades: 20-40 (internal detection works)
- Compression ER: 1.8-2.5 (valid edge)
- Breakout follow-through: 55-65% (thesis confirmed)
- Win rate: 45-55% (credible)

**Next:** WF validation, overlap analysis, breakout cohort analysis, Phase 2.5

---

### Scenario 2: MARGINAL IMPROVEMENT (30% probability)

**Metrics:**
- Trades: 20-30 (minimal sample)
- Compression ER: 1.0-1.5 (borderline)
- Follow-through: 40-50% (weak)

**Verdict:** Still MARGINAL - edge too weak, not worth Phase 2.5 complexity

**Next:** Close compression_breakout, move to crowded_unwind

---

### Scenario 3: STILL FAILED (30-40% probability)

**Metrics:**
- Trades: <20 OR compression ER <1.5 OR follow-through <40%

**Verdict:** HYPOTHESIS FAILED - regime classification fix didn't help

**Conclusion:** Compression → breakout angle is wrong for BTC perps (like absorption was)

**Next:** Move to crowded_unwind (funding/OI exhaustion → forced unwind)

---

## Why Stop After One Iteration

**Reason 1:** One measurement issue identified (regime classification), fixed → fair test

**Reason 2:** If internal compression detection + regime veto don't expose edge, edge likely doesn't exist

**Reason 3:** Avoid "endless parameter tuning" trap:
- First iteration: "fix regime classification"
- Second iteration: "fix compression threshold"
- Third iteration: "fix breakout confirmation"
- → Never ends, no learning

**Discipline:** One iteration to fix measurement, then hard decision (keep or abandon)

---

## Deliverables (Same as Checkpoint 1 + regime analysis)

1. ✅ `research_lab/analyze_regime_distribution.py` (new)
2. ✅ `research_lab/reports/regime_distribution_2022_2026.md` (new)
3. ✅ Updated `compression_breakout.py` (regime as veto if needed)
4. ✅ Re-run backtest output
5. ✅ Updated validation report (metrics, verdict)
6. ✅ Updated audit package (CANDIDATE or FAILED)

**If FAILED:**
7. ✅ Failure analysis document
8. ✅ Recommendation: crowded_unwind specification

---

## No-Touch Areas (Unchanged)

**Production code:**
- `core/regime_engine.py` (do NOT modify - production component)
- `orchestrator.py`
- `core/signal_engine.py`
- `execution/**`
- `governance/**`
- `risk/**`
- `settings.py`

**Research-only changes:**
- `research_lab/setups/compression_breakout.py` (regime filter adjustment)
- `research_lab/analyze_regime_distribution.py` (new analysis script)
- `research_lab/reports/**` (new reports)
- `tests/test_research_lab_compression_breakout.py` (test updates)

All work stays in `research_lab/**`, `tests/**`, `docs/**`

**Zero production changes** - RegimeEngine stays untouched, all adjustments are research-only.

---

## Critical Reminders

### This Is NOT Parameter Optimization

**We are fixing measurement error (regime classification), not tuning for results:**
- Compression detection: Use setup's internal metrics (ATR percentile, range width, duration)
- Regime: Use as veto (block wrong regimes), not main trigger

**If edge exists, correct measurement will expose it.**  
**If edge doesn't exist, no amount of tuning will create it.**

---

### One Iteration = One Chance

**After regime classification fix:**
- Edge validates → proceed to WF/Phase 2.5
- Edge fails → stop, move to crowded_unwind

**No:**
- "Maybe try different ATR percentile"
- "Maybe loosen breakout confirmation"
- "Maybe add another compression metric"

**This prevents endless parameter search.**

---

### Regime as Veto vs Trigger

**Original approach (Checkpoint 1):**
- Regime = trigger: "Only activate when regime=COMPRESSION"
- Problem: If RegimeEngine doesn't label COMPRESSION, setup never activates

**New approach (Iteration A):**
- Regime = veto: "Don't activate in uptrend/downtrend/crowded"
- Trigger = internal detection: ATR percentile, range width, compression duration
- More robust: Setup can find compression even if RegimeEngine doesn't label it

**Trade-off:**
- Pro: Tests hypothesis even with incomplete regime labeling
- Con: May activate in "normal" periods that aren't true compression
- Mitigation: Setup's strict internal filters provide compression confirmation

---

### Prepare for Option B

**If iteration fails:**
- User will likely choose crowded_unwind next
- Start thinking about crowded_unwind hypothesis (funding/OI exhaustion → forced unwind)
- Review available data (funding extremes, OI peaks, force orders)

**Don't:**
- Start implementing Option B preemptively
- Assume iteration will fail

**Do:**
- Give compression hypothesis fair chance with corrected measurement
- Be ready to pivot if it fails

---

## Questions Before Starting?

**Expected:** None - scope is narrow, changes are specific

**If questions:**
- Regime distribution query? → Check decision_outcomes.regime field
- Percentile threshold for "rare"? → <1% is rare, >5% is present
- Internal compression detection already implemented? → Yes (ATR percentile, range width in setup)

---

## Start Implementation

**Your first response should confirm:**
1. Scope understood (A1: regime distribution analysis, A2: regime as veto if needed)
2. Success criteria clear (≥20 trades, ER >1.5, follow-through >40%)
3. Hard stop understood (if fails → crowded_unwind, no further iterations)
4. Timeline reasonable (~2 days)

**Then:** Begin with regime distribution analysis, interpret findings, update setup if needed, re-run, verdict.

---

**Handoff complete. Branch `research/compression-breakout-v1` is ready for iteration A.**

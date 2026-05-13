# HANDOFF: REGIME-REVERSAL-RESEARCH-V1
## FINAL 15M PORTFOLIO TEST

**From:** Claude Code (Auditor)  
**To:** Codex (Builder)  
**Date:** 2026-05-13  
**Milestone:** `REGIME-REVERSAL-RESEARCH-V1`  
**Type:** Research-only (no production changes)  
**Classification:** **FINAL TEST OF 15M PORTFOLIO VIABILITY**

---

## CRITICAL: This Is the Final 15M Portfolio Test

### What this milestone decides:

**If regime_reversal FAILS:**
- Conclusive evidence: 15m frequency insufficient for setup portfolio diversification
- 6 setup families tested, 6 failed or blocked (100% failure rate)
- Pattern proven: 15m can classify states, but enters profitable phases too late
- **Next milestone: Strategic assessment** (15m limitation, sweep_reclaim expansion, frequency upgrade)
- **NOT: Another setup attempt** (rescue cycle ends here)

**If regime_reversal PASSES (CANDIDATE):**
- First success: Multi-setup portfolio viable at 15m (1/6 success rate)
- Validates: Slower structure transitions (regime shifts) compatible with 15m
- **Next milestone: Walk-forward + Phase 2.5 integration planning**
- Continue portfolio research with validated template

### Why this is the final test:

**5 setups tested, 5 failures/blocks:**
1. absorption: Interpretive signals (CVD) not predictive
2. compression: Sequential event timing incompatible
3. crowded_unwind: Cascade catching too fast (seconds-minutes)
4. post_cascade: Infrastructure blocked (regime definition mismatch)
5. volatility_breakout: **Expansion mid-phase entry** (detection latency)

**Pattern across failures:**
> 15m frequency can classify market states correctly, but enters profitable sub-phases too late. Early high-profit windows (cascade start, expansion start, exhaustion peak) pass before detection and entry occur.

**Why regime_reversal might be different:**
- Regime transitions evolve on **hours-to-days timescale** (vs minutes-hours for expansions)
- RegimeEngine already detects shifts (infrastructure exists, validated)
- Entry AFTER shift confirms (not anticipating shift, not during transition)
- Slower structure changes give 15m cycles longer entry window

**Why regime_reversal might also fail:**
- Exhaustion detection might be mid-to-late phase (same as volatility)
- Entry delay from shift confirmation might miss early reversal momentum
- False reversals / whipsaws might dominate (regime flips then reverts)
- Counter-trend entries inherently riskier than trend-following

**This test provides conclusive evidence either way.**

---

## Checkpoint

- **Last commit:** `14ecefd` - `docs: close post_cascade (BLOCKED), start volatility_breakout`
- **Branch:** `main`
- **Working tree:** clean

---

## Before You Code

Read these files (mandatory):

1. **Relevant blueprints:**
   - `docs/BLUEPRINT_V1.md` — bot/runtime architecture, RegimeEngine (Section 4.3)
   - `docs/BLUEPRINT_RESEARCH_LAB.md` — research lab architecture and workflow
2. **`AGENTS.md`** — discipline + your workflow rules
3. **`docs/MILESTONE_TRACKER.md`** — current status + known issues
4. **All five prior failure audits (CRITICAL):**
   - `docs/audits/AUDIT_ABSORPTION_CONTINUATION_ITERATION_A_2026-05-12.md`
   - `docs/audits/AUDIT_COMPRESSION_BREAKOUT_ITERATION_A_2026-05-12.md`
   - `docs/audits/AUDIT_CROWDED_UNWIND_CHECKPOINT_1_2026-05-13.md`
   - `docs/audits/AUDIT_POST_CASCADE_MOMENTUM_CHECKPOINT_1_2026-05-13.md`
   - `docs/audits/AUDIT_VOLATILITY_BREAKOUT_CHECKPOINT_1_2026-05-13.md`

---

## Milestone: REGIME-REVERSAL-RESEARCH-V1

**Scope:** Research-only validation of regime_reversal setup (regime exhaustion → RegimeEngine confirms shift → counter-trend entry after transition).

**Blueprint reference:** `docs/BLUEPRINT_V1.md` Section 4.3 (RegimeEngine: uptrend, downtrend, normal classifications)

---

## Setup Definition: State Transition, NOT Top/Bottom Guessing

### What regime_reversal IS:

**State transition-based counter-trend entry:**
1. Market in established regime (uptrend or downtrend)
2. Exhaustion signs appear (momentum slowing, structure weakening)
3. **RegimeEngine confirms regime shift** (uptrend → downtrend OR downtrend → uptrend)
4. Entry AFTER shift confirmed (counter-trend to prior regime)
5. Risk/reward valid (stop at prior regime structure, target in new regime direction)

**Example (SHORT after uptrend exhaustion):**
- RegimeEngine: uptrend (ema50 > ema200, ATR elevated)
- Exhaustion: Price losing momentum, ema50 declining toward ema200
- **Shift confirmed:** RegimeEngine changes to downtrend OR normal (uptrend ended)
- Entry: SHORT (counter to prior uptrend)
- Stop: Above prior uptrend structure
- Target: Downside continuation in new regime

**Example (LONG after downtrend exhaustion):**
- RegimeEngine: downtrend (ema50 < ema200, ATR elevated)
- Exhaustion: Price losing downward momentum, ema50 rising toward ema200
- **Shift confirmed:** RegimeEngine changes to uptrend OR normal (downtrend ended)
- Entry: LONG (counter to prior downtrend)
- Stop: Below prior downtrend structure
- Target: Upside continuation in new regime

### What regime_reversal is NOT:

**NOT top/bottom anticipation:**

❌ **WRONG (anticipatory, no state confirmation):**
```
IF uptrend AND rsi > 70 AND funding > 85th percentile
   THEN short (anticipating top)
```

❌ **WRONG (indicator extremes without regime shift):**
```
IF price > ema200 * 1.05 AND atr_percentile > 90
   THEN short (price extended, anticipating reversal)
```

❌ **WRONG (pattern-based guessing):**
```
IF double_top OR head_and_shoulders
   THEN short (chart pattern predicts reversal)
```

✅ **CORRECT (state transition confirmation):**
```
IF prior_regime == uptrend 
   AND current_regime IN {downtrend, normal}
   AND regime_transition_recent (< N cycles ago)
   AND momentum_aligned_with_new_direction
   AND structure_supports_entry
   THEN enter counter-trend (SHORT after uptrend → downtrend/normal)
```

**Key distinction:**
- Anticipatory: Enter during established regime, predicting reversal will happen
- State transition: Enter AFTER RegimeEngine confirms regime already changed

---

## Why This Setup Might Work at 15m

### Lessons from prior failures applied:

1. **Objective state classification (not interpretive):**
   - RegimeEngine regime labels (uptrend/downtrend/normal) are objective
   - EMA crossover, ATR levels, measurable thresholds
   - No CVD divergence interpretation (absorption failure)

2. **State transition timing (not anticipation):**
   - Entry AFTER shift confirms (not before it)
   - Not trying to catch top/bottom during established regime
   - Not sequential event anticipation (compression failure)

3. **Slower timescale (not split-second):**
   - Regime shifts persist across multiple cycles (hours-to-days)
   - Not cascade catching (crowded_unwind failure: seconds-minutes)
   - Not expansion catching (volatility failure: mid-phase entry)

4. **Existing infrastructure (not blocked):**
   - RegimeEngine already detects uptrend/downtrend/normal
   - No infrastructure gaps (post_cascade failure)

### Why detection latency might still be a problem:

**Similar to volatility_breakout:**
- Regime exhaustion begins → Early reversal move (high profit) → RegimeEngine confirms shift (latency) → 15m enters → Late reversal move (low profit)
- By the time RegimeEngine flips regime classification, early reversal momentum might be exhausted

**Entry delay measurement (CRITICAL gate):**
- Measure cycles between regime shift and entry
- If average delay > 6 cycles (1.5 hours), entry is likely mid-to-late reversal phase
- This would replicate volatility_breakout failure (correct state, late phase)

---

## Hypothesis

**Market Structure:**
Regimes (uptrend, downtrend) eventually exhaust:
- Uptrend: Buyers exhaust, momentum slows, structure weakens → shifts to downtrend/normal
- Downtrend: Sellers exhaust, downside momentum slows, structure weakens → shifts to uptrend/normal

**Edge Thesis:**
When RegimeEngine confirms regime shift (prior regime exhausted, new regime beginning), counter-trend entry captures early phase of new regime direction. Entry AFTER shift confirms (not during transition, not anticipating shift).

**Entry Timing:**
AFTER RegimeEngine classifies new regime (shift confirmed), within N cycles of shift (early new regime phase, not late).

**Why this edge might exist:**
- Regime shifts mark structural changes (EMA crossovers, volatility shifts)
- Early new regime phase has continuation (new direction establishing)
- Counter-trend entries benefit from prior regime exhaustion clearing opposing positions
- 15m-compatible: Regime shifts persist longer than expansions/cascades

**What makes this 15m-compatible (potentially):**
- Regime labels persist across multiple decision cycles (hours-to-days)
- Entry window: Multiple cycles after shift confirmation (not split-second)
- Shift detection is state-based (not event-based)

---

## Target Regimes

**Entry regimes (post-transition):**
- Enter **uptrend or normal** AFTER prior downtrend exhaustion (LONG)
- Enter **downtrend or normal** AFTER prior uptrend exhaustion (SHORT)

**Prior regime tracking:**
- Track regime history (last N cycles)
- Detect regime transitions (uptrend → downtrend/normal, downtrend → uptrend/normal)
- Entry within window after transition (e.g., 2-12 cycles = 30min-3 hours)

**Regime transition definition:**
```python
def detect_regime_transition(
    current_regime: RegimeState,
    prior_regime: RegimeState,
    cycles_since_transition: int,
    max_entry_delay_cycles: int = 12  # 3 hours
) -> tuple[bool, str | None]:
    """
    Detect if regime recently transitioned and entry window is still open.
    
    Returns:
        (transition_active, direction)
        direction: 'LONG' (after downtrend → uptrend/normal)
                  'SHORT' (after uptrend → downtrend/normal)
                  None (no valid transition)
    """
    if cycles_since_transition > max_entry_delay_cycles:
        return False, None  # Too late, transition window closed
    
    # LONG: Enter uptrend/normal after downtrend ended
    if prior_regime == RegimeState.DOWNTREND:
        if current_regime in {RegimeState.UPTREND, RegimeState.NORMAL}:
            return True, 'LONG'
    
    # SHORT: Enter downtrend/normal after uptrend ended
    if prior_regime == RegimeState.UPTREND:
        if current_regime in {RegimeState.DOWNTREND, RegimeState.NORMAL}:
            return True, 'SHORT'
    
    return False, None
```

---

## Setup Directions

### Long Setup: `regime_reversal_long`

**Entry conditions (ALL must be true):**

1. **Regime transition confirmed:**
   - Prior regime: downtrend (tracked via regime history)
   - Current regime: uptrend OR normal (shift confirmed)
   - Cycles since transition: <= 12 (entry window open, within 3 hours)

2. **Momentum aligned with new direction:**
   - TFI_60s > threshold (e.g., +0.05 = buy pressure)
   - Price > recent structure (e.g., EMA_50 15m or swing low from downtrend)
   - Momentum not exhausted (not late new-regime phase)

3. **Structure supports entry:**
   - Stop placement: Below downtrend structure (prior regime support)
   - RR >= 2.0 minimum
   - Entry not overextended (price within reasonable distance from ema)

4. **Not false reversal:**
   - Regime shift persistent (not one-cycle flip)
   - E.g., current regime held for >= 2 cycles (30 min minimum)

5. **No conflicting regime veto:**
   - Not crowded_leverage (avoid cascade complexity)
   - Not compression (avoid range-bound chop)
   - Not post_liquidation (avoid aftermath complexity)

**Exit:**
- Stop: Below downtrend structure (recent swing low from prior regime)
- Target 1: 2.5R
- Target 2: 3.5R

**Invalidation (block entry):**
- Regime transition too old (> 12 cycles, window closed)
- Momentum not aligned (TFI negative or weak)
- Structure broken (price below stop level already)
- False reversal (regime flipped back within 2 cycles)

### Short Setup: `regime_reversal_short`

**Entry conditions (ALL must be true):**

1. **Regime transition confirmed:**
   - Prior regime: uptrend
   - Current regime: downtrend OR normal
   - Cycles since transition: <= 12

2. **Momentum aligned with new direction:**
   - TFI_60s < threshold (e.g., -0.05 = sell pressure)
   - Price < recent structure (EMA_50 15m or swing high from uptrend)
   - Momentum not exhausted

3. **Structure supports entry:**
   - Stop: Above uptrend structure (prior regime resistance)
   - RR >= 2.0 minimum

4. **Not false reversal:**
   - Regime shift persistent (>= 2 cycles)

5. **No conflicting regime veto:**
   - Not crowded_leverage, compression, post_liquidation

**Exit:**
- Stop: Above uptrend structure
- Target 1: 2.5R
- Target 2: 3.5R

**Invalidation:**
- Transition too old (> 12 cycles)
- Momentum not aligned
- Structure broken
- False reversal

---

## Key Metrics and Thresholds

### Regime Transition Detection

**Regime history tracking:**
- Lookback: 24 cycles (6 hours) minimum
- Detect when regime changes from uptrend/downtrend to different regime
- Track cycles_since_transition (entry delay measurement)

**Entry window:**
- Maximum delay: 12 cycles (3 hours) after transition
- Rationale: Early new-regime phase (not late)
- If delay > 12 cycles, reject (window closed, late phase)

### Entry Delay Measurement (CRITICAL GATE)

**Purpose:** Detect if 15m frequency enters mid-to-late reversal phase (like volatility failure)

**Measurement:**
For each trade, record:
- Transition cycle: When RegimeEngine confirmed shift
- Entry cycle: When trade opened
- Delay: entry_cycle - transition_cycle

**Gate:**
- Average entry delay: Report in audit package
- If average delay > 6 cycles (1.5 hours) → likely mid-to-late phase entry
- Compare to volatility_breakout pattern (entered mid-expansion)

### False Reversal Control (CRITICAL GATE)

**Definition:** Regime flips (uptrend → downtrend), entry occurs, then regime flips back (downtrend → uptrend) before target hit.

**Measurement:**
- For each losing trade, check if regime reverted to prior regime during trade
- False reversal rate = (false reversal losses) / (total trades)

**Gate:**
- False reversal rate < 40% (most losses should NOT be whipsaws)
- If >= 40%, regime shifts too noisy for reliable trading

### Whipsaw Control

**Definition:** Multiple regime flips in short period (regime instability)

**Measurement:**
- Count cycles with regime flips (current != prior)
- Whipsaw cycles = cycles with flip
- Whipsaw rate = whipsaw_cycles / total_cycles

**Gate:**
- Whipsaw rate < 30% of transition cycles
- If >= 30%, regime classifications too unstable

### Momentum Validation

**TFI threshold:**
- LONG: TFI_60s > +0.05
- SHORT: TFI_60s < -0.05

**Structure:**
- LONG: price > EMA_50 (15m) OR price > recent swing low
- SHORT: price < EMA_50 (15m) OR price < recent swing high

### Risk/Reward

**Minimum RR:** 2.0  
**Stop placement:** 0.35 * ATR_15m beyond prior regime structure  
**Targets:** 2.5R (T1), 3.5R (T2)

---

## Implementation Deliverables

### Checkpoint 1 (Target: 1 week)

1. **Setup contract:**
   - `research_lab/setups/regime_reversal.py`
   - Classes: `RegimeReversalLong`, `RegimeReversalShort`
   - Inherit from `BaseSetup`
   - Config dataclass with thresholds (entry delay max, TFI, etc.)
   - **Regime transition detection function** (history tracking, shift confirmation)

2. **Backtest runner:**
   - `research_lab/backtest_regime_reversal.py`
   - Full-range replay (2022-01-01 → 2026-03-29)
   - **Regime history tracking** (per cycle)
   - Decision funnel tracking
   - Per-regime breakdown (post-transition regimes)
   - **Entry delay measurement** (explicit per trade)

3. **Hard gate evaluator:**
   - `research_lab/evaluate_regime_gates.py`
   - Gates (see Hard Gates section below)
   - Output: `research_lab/reports/regime_gate_results.json`

4. **Hypothesis document:**
   - `research_lab/research/REGIME_REVERSAL_HYPOTHESIS.md`
   - State transition definition (RegimeEngine shift confirmation)
   - NOT top/bottom anticipation (distinction from indicator extremes)
   - Why 15m-compatible (regime shift timescale)

5. **Tests:**
   - `tests/test_research_lab_regime_reversal.py`
   - Setup instantiation, config validation
   - Regime transition detection (history tracking, shift logic)
   - Entry timing validation (within window after shift)
   - False reversal detection
   - Edge cases: Immediate regime flip-back, stale transition

6. **Validation report:**
   - `research_lab/reports/regime_reversal_validation_report.md`
   - Full-range metrics (ER, PF, DD, Sharpe)
   - Per-prior-regime breakdown (entries after uptrend exhaustion vs downtrend exhaustion)
   - Per-direction breakdown (LONG vs SHORT)
   - Decision funnel (cycles → transitions → candidates → trades)
   - **Entry delay distribution** (histogram: cycles from transition to entry)
   - **False reversal rate**
   - **Whipsaw rate**

7. **Audit package:**
   - `research_lab/reports/REGIME_REVERSAL_AUDIT_PACKAGE.md`
   - Executive summary
   - Hard gate results table
   - Direction breakdown
   - Entry delay analysis (CRITICAL: mid-phase entry check)
   - Builder verdict with reasoning

8. **Smoke tests:**
   - Full-range backtest on local V3 data
   - `pytest tests/test_research_lab_regime_reversal.py` (all pass)
   - `compileall` clean
   - Gate evaluation runs without errors

9. **Regime transition analysis (CRITICAL for audit):**
   - Report: `research_lab/reports/regime_transition_distribution.md`
   - Questions to answer:
     - How often do regime transitions occur? (uptrend → downtrend/normal, downtrend → uptrend/normal)
     - What is typical transition persistence? (cycles in new regime before next flip)
     - What % of transitions are false reversals? (flip back within N cycles)
     - What is average entry delay from transition? (if > 6 cycles, likely mid-phase like volatility)

10. **Milestone tracker update:**
    - Update `docs/MILESTONE_TRACKER.md` with Checkpoint 1 results

---

## Hard Gates

| Gate | Requirement | Rejection Criterion | Measurement |
|---|---|---|---|
| **Post-transition ER** | `> 1.5` | `< 1.0` | Expectancy R for trades in post-transition regimes |
| **False reversal rate** | `< 40%` | `>= 50%` | % of trades where regime reverted to prior before target |
| **Whipsaw rate** | `< 30%` | `>= 50%` | % of transition cycles that flip back quickly |
| **Entry delay (diagnostic)** | Report | `> 6 cycles avg` | Average cycles from transition to entry (latency check) |
| **Minimum total trades** | `>= 20` | `< 10` | Total closed trades in full-range backtest |
| **Transition entry rate** | `>= 70%` | `< 50%` | % of entries within window after transition (not stale) |
| **Overlap vs sweep_reclaim** | `< 30%` | `> 50%` | Candidate-level temporal overlap (run if >=20 trades) |
| **Walk-forward** | `2/2` windows pass | Any window fail | WF validation (run only if Checkpoint 1 ER >1.5) |
| **Safety flags** | No blocking flags | Any blocking flag | Fragility, concentration, extreme metrics |
| **Explainability** | All signals have `reasons[]` | Any missing | Signal transparency |

### Entry Delay (Diagnostic Gate - CRITICAL)

**Purpose:** Detect if 15m frequency enters mid-to-late reversal phase (volatility_breakout pattern)

**Measurement:**
- For each trade, compute: entry_cycle - transition_cycle
- Report: min, median, p95, average delay
- Compare to volatility_breakout pattern (entered mid-expansion)

**Interpretation:**
- Average delay <= 3 cycles (45 min): Early new-regime entry (good)
- Average delay 3-6 cycles (45min-1.5h): Mid-regime entry (marginal)
- Average delay > 6 cycles (1.5h+): Late regime entry (bad - same as volatility failure)

**If average delay > 6 cycles:**
- Root cause: "15m detection latency" (same as volatility_breakout)
- Verdict: HYPOTHESIS FAILED (correct state, late phase)
- No iteration (pattern proven)

### False Reversal Rate (Critical for Counter-Trend)

**Definition:** Regime flips (e.g., uptrend → downtrend), entry SHORT, regime flips back (downtrend → uptrend) before target.

**Why critical:**
Counter-trend entries are inherently vulnerable to false reversals. If regime classifications are noisy (frequent flips), counter-trend trades will whipsaw.

**Gate:**
- < 40% of trades should be false reversals
- If >= 40%, regime shifts too unstable

### Whipsaw Rate (Regime Stability Check)

**Measures:** How often RegimeEngine flips regime classification

**Calculation:**
- Count transition cycles (regime != prior_regime)
- Whipsaw rate = transition_cycles / total_cycles

**Gate:**
- < 30% whipsaw rate (regime classifications stable)
- If >= 50%, RegimeEngine too noisy for reliable transition trading

---

## Rejection Criteria

**Hard stop if any of these conditions at Checkpoint 1:**

1. **Insufficient sample:** `< 10` total trades (cannot validate)
2. **Negative edge:** Post-transition ER `< 1.0` (loses money, hard stop)
3. **High false reversal rate:** >= 50% (regime shifts too noisy)
4. **High whipsaw rate:** >= 50% (regime classifications unstable)
5. **Late entry timing:** Average entry delay > 6 cycles (mid-to-late phase, same as volatility failure)

**If hard stop triggered:**
- Do NOT attempt Iteration A (parameter rescue)
- Deliver audit package with verdict: `HYPOTHESIS FAILED` or `TIMING_VIOLATION_15M_LATENCY` (if delay > 6)
- **Next milestone: Strategic assessment** (NOT another setup)

**Marginal case (iteration NOT allowed per final test framing):**
- Post-transition ER between 1.0 and 1.5 (positive but below gate)
- False reversal 40-50% (marginal noise)
- Entry delay 4-6 cycles (marginal latency)

**Per final test framing:** If any gate fails or is marginal, close as FAILED and move to strategic assessment. No iteration for this milestone (conclusive test).

---

## Known Issues

| # | Issue | Blocking for this milestone? |
|---|---|---|
| 1 | Regime transitions might be rare (need to verify frequency) | YOU ASSESS - analyze % of cycles with transitions |
| 2 | Entry delay might replicate volatility failure (mid-phase entry) | YES - entry delay gate MUST pass |
| 3 | False reversals might dominate (regime flips too noisy) | YES - false reversal rate gate MUST pass |
| 4 | Whipsaws might be frequent (RegimeEngine unstable) | YES - whipsaw rate gate MUST pass |

**If Issue #1 (transitions rare):**
- If `< 2%` of cycles are transitions → sample size might be < 10 trades
- Rare transitions would mean insufficient test (inconclusive, not failed)
- Report frequency in audit package

**If Issue #2 (entry delay > 6 cycles):**
- Same as volatility_breakout failure (correct state, late phase)
- Root cause: "15m detection latency"
- Verdict: HYPOTHESIS FAILED (timing violation)
- Pattern proven: Even slow structure changes (regime shifts) enter too late at 15m

**If Issue #3 (false reversals >= 50%):**
- Regime shifts too noisy for reliable counter-trend trading
- Verdict: HYPOTHESIS FAILED (state instability)

**If Issue #4 (whipsaws >= 50%):**
- RegimeEngine classifications too unstable
- Not a setup failure, but infrastructure limitation
- Verdict: BLOCKED or HYPOTHESIS FAILED (depending on interpretation)

---

## Your First Response Must Contain

1. **Acknowledged final test framing** (this decides 15m portfolio viability)
2. **Confirmed milestone scope** (state transition, not top/bottom guessing)
3. **Regime transition detection approach** (history tracking, shift confirmation logic)
4. **Entry delay measurement plan** (how to detect mid-phase entry)
5. **False reversal detection plan** (how to identify whipsaws)
6. **Implementation plan** (ordered steps)
7. **Only then: start coding**

---

## Commit Discipline

- **WHAT / WHY / STATUS** in every commit message
- Do NOT self-mark as "done". Claude Code audits after push.
- Research-only: no changes to `settings.py`, `orchestrator.py`, or production modules

---

## Expected Timeline

**Checkpoint 1:** 1 week
- Implementation: 2-3 days (including regime history tracking)
- Backtest + validation: 1-2 days
- Regime transition analysis: 1 day
- Testing + audit package: 1 day

**No Iteration allowed:** This is final test, hard stop only

**If Checkpoint 1 hard stop:** Close immediately, move to strategic assessment

**If Checkpoint 1 promising (ER >1.5, false reversal <40%, delay <=6):** Walk-forward + overlap analysis (3-5 days), then Phase 2.5 planning

**Total:** 1-2 weeks to conclusive verdict, then strategic assessment regardless of outcome

---

## Success Looks Like

**Checkpoint 1 CANDIDATE result (first success):**
- Post-transition ER: 2.1 (above 1.5 gate)
- PF: 3.8
- False reversal rate: 32% (below 40% gate)
- Whipsaw rate: 18% (below 30% gate)
- **Entry delay: avg 3.2 cycles** (early new-regime entry, NOT mid-phase)
- Trades: 28 (adequate sample)
- Decision funnel: 1,200 transitions → 35 candidates → 28 trades
- Regime transition distribution: Transitions occur 0.8% of cycles (rare but sufficient)
- Verdict: **CANDIDATE_READY** → proceed to walk-forward → Phase 2.5 integration
- **Proves:** 15m portfolio viable for slower structure changes

**Checkpoint 1 FAILED result (edge failure):**
- Post-transition ER: 0.48 (below 1.0 hard stop)
- False reversal rate: 38% (marginal but acceptable)
- Entry delay: avg 4.5 cycles (mid-regime, marginal)
- Trades: 22 (adequate sample)
- Verdict: **HYPOTHESIS FAILED** (weak edge despite correct timing)
- **Next:** Strategic assessment (NOT another setup)

**Checkpoint 1 FAILED result (timing violation - most likely):**
- Post-transition ER: 0.65 (below 1.0)
- **Entry delay: avg 7.8 cycles** (late new-regime entry, same as volatility)
- False reversal rate: 42% (marginal noise)
- Trades: 26
- Verdict: **TIMING_VIOLATION_15M_LATENCY** (detection latency causes mid-to-late phase entry)
- **Root cause:** Even regime shifts (slowest structure changes) are detected too late by 15m cycles
- **Pattern conclusive:** 15m insufficient for any state-based entries (expansions, transitions, cascades all fail)
- **Next:** Strategic assessment → frequency upgrade OR sweep_reclaim focus

**Checkpoint 1 BLOCKED result (infrastructure):**
- Regime transitions: 0.1% of cycles (extremely rare, < 10 trades)
- Insufficient sample to validate hypothesis
- Verdict: **BLOCKED** (inconclusive, not failed)
- But: Pattern across 5 prior failures still conclusive (15m limitation proven)
- **Next:** Strategic assessment

---

## Research Context

**Portfolio status after five setups (6 days):**
- absorption_continuation: FAILED (interpretive CVD)
- compression_breakout: FAILED (sequential timing)
- crowded_unwind: FAILED (cascade too fast)
- post_cascade_momentum: BLOCKED (infrastructure gap)
- volatility_breakout: FAILED (**15m enters mid-phase**)
- **regime_reversal: FINAL TEST** (this milestone)

**Pattern across failures:**
> 15m frequency can classify market states correctly, but enters profitable sub-phases too late. Early high-profit windows pass before detection and entry occur.

**Why regime_reversal is the final test:**
- Tests slowest structure changes (regime shifts: hours-to-days)
- If this also fails due to entry delay → pattern proven (15m insufficient for ALL state-based entries)
- If this succeeds → 15m viable for slow transitions (template for future setups)

**Fast failure discipline:** 6 setups, 6 days, conclusive verdicts. No parameter rescue. Clean decisions.

**Estimated success probability:** 20-30% (unproven, but addresses timing by using slowest structure changes)

**Next milestone rule (CRITICAL):**
> If regime_reversal fails: Next milestone is strategic assessment (15m limitation, sweep_reclaim expansion, frequency upgrade), NOT another setup.

---

## Questions for Claude Code Before Starting

If any of these unknowns block your implementation plan, ask Claude Code BEFORE coding:

1. **Regime transition frequency:** Are regime shifts common enough for adequate sample size?
2. **Regime history tracking:** How many cycles lookback for reliable transition detection?
3. **Entry window definition:** Is 12-cycle window (3 hours) appropriate, or too wide/narrow?
4. **False reversal vs normal loss:** How to distinguish regime whipsaw from normal stop-out?

Do NOT proceed with implementation if you're unsure about regime transition detection logic. Ask first.

---

## Final Note

**This is the FINAL 15M PORTFOLIO TEST.**

Your job:
1. Confirm you understand this is a conclusive test (not another rescue attempt)
2. Implement Checkpoint 1 deliverables (regime transition tracking, entry delay measurement)
3. Validate entry timing (prove early new-regime entry OR expose late-phase entry like volatility)
4. Push results for Claude Code audit
5. Do NOT self-audit or self-approve

Claude Code will audit your work and deliver verdict: HYPOTHESIS FAILED / TIMING_VIOLATION_15M_LATENCY / BLOCKED / CANDIDATE_READY.

**If any gate fails:** Next milestone is strategic assessment, NOT another setup.

**If all gates pass:** First portfolio success → walk-forward → Phase 2.5 integration.

This milestone decides whether 15m frequency is viable for multi-setup portfolio diversification. 6 families tested. This is the 6th and final.

Good luck. The pattern is clear. This test provides conclusive evidence either way.

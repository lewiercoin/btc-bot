# HANDOFF: VOLATILITY-BREAKOUT-RESEARCH-V1

**From:** Claude Code (Auditor)  
**To:** Codex (Builder)  
**Date:** 2026-05-13  
**Milestone:** `VOLATILITY-BREAKOUT-RESEARCH-V1`  
**Type:** Research-only (no production changes)

---

## Checkpoint

- **Last commit:** `c978921` - `docs: close crowded_unwind (FAILED), start post_cascade_momentum`
- **Branch:** `main`
- **Working tree:** clean

---

## CRITICAL: This Is NOT Compression_Breakout Repeat

### What compression_breakout tried (and FAILED):

**Entry timing:** During compression state, anticipating breakout will happen soon

**Logic:**
```
IF compression_state AND range_consolidation
   THEN enter, expecting breakout
```

**Why it failed:** Compression and breakout are **SEQUENTIAL EVENTS**:
- Phase 1: Compression (ATR low, range tight, price coiling)
- Phase 2: Transition (compression ends)
- Phase 3: Breakout (ATR expands, price breaks range)

Entry during Phase 1 (compression) cannot catch Phase 3 (breakout) because they don't overlap temporally. By the time breakout occurs, compression state has ended.

### What volatility_breakout tests (DIFFERENT timing):

**Entry timing:** AFTER expansion begins, DURING active breakout, NOT before it

**Logic:**
```
IF expansion_state_active AND structure_already_breaking AND momentum_aligned
   THEN enter, riding continuation
```

**Why this might work:** Entry occurs in Phase 3 (expansion in progress), not Phase 1 (compression). The setup doesn't anticipate future state; it detects current state and acts.

### The Critical Distinction

| Aspect | compression_breakout (FAILED) | volatility_breakout (THIS MILESTONE) |
|---|---|---|
| **Entry state** | Compression (low ATR) | Expansion (rising ATR) |
| **Timing** | Anticipatory (before breakout) | Confirmatory (during breakout) |
| **ATR requirement** | ATR low (< 0.0055) | ATR rising (slope positive) |
| **Structure** | Range-bound (no breakout yet) | Breaking structure (breakout happening) |
| **Edge thesis** | "Compression → breakout will follow" | "Expansion started → continuation likely" |
| **Event sequence** | Concurrent (impossible) | Current state (observable) |

**If this setup tries to enter during compression, it is compression_breakout 2.0 and will fail the same way.**

---

## Before You Code

Read these files (mandatory):

1. **Relevant blueprints:**
   - `docs/BLUEPRINT_V1.md` — bot/runtime architecture
   - `docs/BLUEPRINT_RESEARCH_LAB.md` — research lab architecture and workflow
2. **`AGENTS.md`** — discipline + your workflow rules
3. **`docs/MILESTONE_TRACKER.md`** — current status + known issues
4. **Prior failure audits (CRITICAL - understand what NOT to do):**
   - `docs/audits/AUDIT_COMPRESSION_BREAKOUT_ITERATION_A_2026-05-12.md` — sequential event timing failure
   - `docs/audits/AUDIT_CROWDED_UNWIND_CHECKPOINT_1_2026-05-13.md` — cascade timing incompatibility
   - `docs/audits/AUDIT_POST_CASCADE_MOMENTUM_CHECKPOINT_1_2026-05-13.md` — infrastructure blocker
   - `docs/audits/AUDIT_ABSORPTION_CONTINUATION_ITERATION_A_2026-05-12.md` — interpretive signal failure

---

## Milestone: VOLATILITY-BREAKOUT-RESEARCH-V1

**Scope:** Research-only validation of volatility_breakout setup (ATR expansion state + structure break + momentum continuation).

**Blueprint reference:** `docs/BLUEPRINT_V1.md` Section 4.3 (Regime Engine), Section 3.2 (Signal generation)

---

## Why This Setup is Different (Lessons Applied)

### Four consecutive setups taught us:

1. **Absorption (FAILED):** Interpretive signals (CVD divergence) not predictive
   - **Lesson:** Use objective metrics only
   - **Applied:** This setup uses ATR (objective), price structure (observable), momentum indicators (TFI, measurable)

2. **Compression (FAILED):** Sequential events (compression → breakout) cannot be caught simultaneously
   - **Lesson:** Entry state and edge thesis must coincide temporally
   - **Applied:** This setup enters DURING expansion (not before it), breakout ALREADY happening (not anticipated)

3. **Crowded Unwind (FAILED):** Force spike catching requires sub-minute timing, 15m too slow
   - **Lesson:** Avoid setups requiring split-second event timing
   - **Applied:** This setup uses ATR expansion state (persists for hours-to-days, not seconds-minutes)

4. **Post-Cascade (BLOCKED):** Aftermath detection infrastructure missing
   - **Lesson:** Rely on existing infrastructure, avoid cascade dependencies
   - **Applied:** This setup uses RegimeEngine states (normal/uptrend/downtrend), no cascade detection needed

---

## Hypothesis

**Market Structure:**
Volatility cycles through contraction and expansion phases:
- **Contraction phase:** ATR declines, range narrows, market consolidates (indecision)
- **Expansion phase:** ATR rises, range expands, directional move begins (decision made)

**Edge Thesis:**
When expansion phase begins (ATR rising from low base) AND structure breaks (price exits range) AND momentum aligns (directional pressure), the expansion continues long enough for 15m decision cycles to capture continuation.

**Entry Timing:**
AFTER expansion state confirms (ATR slope positive, not ATR absolute low). This is NOT compression-state entry.

**Why this edge might exist:**
- Volatility expansion from low base has momentum (traders waking up, volume increasing)
- Early expansion phase has room to run (not yet overheated like late expansion)
- Structural break confirms direction (not false breakout from compression)
- 15m-compatible: Expansion persists for hours-to-days (enough time for multiple decision cycles)

**What makes this 15m-compatible:**
- Expansion state is slow-moving (ATR doesn't spike in one cycle, it rises gradually)
- Entry window is wide (early-to-mid expansion, not spike moment)
- State persists across multiple cycles (not split-second opportunity)

---

## Target Regimes

**Primary:** normal, uptrend, downtrend (expansion occurs across regimes)

**Not compression:** Entry during compression violates the setup distinction. If ATR is compressed (low), the setup should NOT enter (that's compression_breakout logic).

**Regime usage:** Regime provides context (trend direction for LONG vs SHORT), but expansion state is primary filter.

---

## Setup Directions

### Long Setup: `volatility_breakout_long`

**Entry conditions (ALL must be true):**

1. **Expansion state confirmed:**
   - ATR_4h_norm is RISING (not low, not stable - RISING)
   - ATR percentile (60d) increasing (e.g., was p20, now p40+)
   - ATR slope positive (current > recent average)

2. **Structure breaking upward:**
   - Price > recent range high (e.g., 12-candle 15m high)
   - Price > key EMA (e.g., EMA_50 4h or EMA_200 4h)
   - Breakout size meaningful (> 0.5 * ATR_15m minimum)

3. **Momentum aligned:**
   - TFI_60s > threshold (e.g., +0.05 = buy pressure)
   - Price momentum positive (not exhausted)
   - Volume/participation elevated (optional: aggtrades spike)

4. **Expansion not overheated:**
   - ATR_4h_norm < panic threshold (e.g., < 0.029 = not extreme volatility)
   - Expansion in early-to-mid phase (not late parabolic)
   - Price not extended (e.g., < 2σ from EMA_50)

5. **Regime context supports:**
   - Regime NOT compression (ATR must be expanding, not compressed)
   - Regime NOT post_liquidation (avoid cascade aftermath complexity)
   - Regime uptrend/normal preferred (trend or neutral breakout)

6. **Risk/reward valid:**
   - Stop: Below breakout structure (recent range low)
   - RR >= 2.0 minimum
   - Target: 2.5R (T1), 3.5R (T2)

**Exit:**
- Stop: Below recent structural support (range low from consolidation before expansion)
- Target 1: 2.5R
- Target 2: 3.5R
- Trail: Optional (if expansion continues strongly)

**Invalidation (block entry):**
- ATR not rising (flat or declining = not expansion)
- Structure not breaking (price still in range)
- Momentum weak or opposing (TFI negative)
- Expansion overheated (ATR extreme, price extended)
- Regime is compression (violates setup distinction)

### Short Setup: `volatility_breakout_short`

**Entry conditions (ALL must be true):**

1. **Expansion state confirmed:**
   - ATR_4h_norm is RISING
   - ATR percentile increasing
   - ATR slope positive

2. **Structure breaking downward:**
   - Price < recent range low (12-candle 15m low)
   - Price < key EMA (EMA_50 4h or EMA_200 4h)
   - Breakout size meaningful (> 0.5 * ATR_15m)

3. **Momentum aligned:**
   - TFI_60s < threshold (e.g., -0.05 = sell pressure)
   - Price momentum negative
   - Volume/participation elevated

4. **Expansion not overheated:**
   - ATR_4h_norm < panic threshold
   - Expansion early-to-mid phase
   - Price not extended (e.g., > -2σ from EMA_50)

5. **Regime context supports:**
   - Regime NOT compression
   - Regime NOT post_liquidation
   - Regime downtrend/normal preferred

6. **Risk/reward valid:**
   - Stop: Above breakout structure (recent range high)
   - RR >= 2.0 minimum

**Exit:**
- Stop: Above recent structural resistance
- Target 1: 2.5R
- Target 2: 3.5R

**Invalidation:**
- ATR not rising
- Structure not breaking
- Momentum weak or opposing
- Expansion overheated
- Regime is compression

---

## Key Metrics and Thresholds

### ATR Expansion Detection (CRITICAL)

**Do NOT use absolute ATR level:**
- compression_breakout failed because it used ATR < 0.0055 (absolute low)
- This setup uses ATR SLOPE (rate of change), not absolute level

**Recommended approach:**

```python
def detect_expansion_state(
    atr_current: float,
    atr_history: list[float],  # last 12-24 cycles (3-6 hours)
    atr_percentile_60d: float
) -> bool:
    """
    Detect if ATR is in expansion state (rising).
    
    Returns True if:
    - ATR slope positive (rising over recent cycles)
    - ATR percentile increasing (was low, now higher)
    - NOT if ATR is just low (that's compression, not expansion)
    """
    if len(atr_history) < 12:
        return False
    
    # ATR slope: recent > older
    recent_avg = mean(atr_history[-6:])   # last 1.5 hours
    older_avg = mean(atr_history[-12:-6]) # 1.5-3 hours ago
    atr_rising = recent_avg > older_avg * 1.05  # 5% rise minimum
    
    # ATR percentile increasing (from low base)
    # e.g., was < 30th percentile, now > 40th percentile
    percentile_rising = atr_percentile_60d > 30  # above low compression zone
    
    return atr_rising and percentile_rising
```

**Alternative: ATR slope calculation:**

```python
atr_slope = (atr_current - atr_6_cycles_ago) / atr_6_cycles_ago
expansion_state = atr_slope > 0.10  # 10% rise over 1.5 hours
```

**Key point:** Measure CHANGE (rising), not LEVEL (low).

### Structure Breakout Confirmation

**Recent range:**
- Lookback: 12 candles (15m) = 3 hours (captures consolidation before expansion)
- High: max(candles[-12:].high)
- Low: min(candles[-12:].low)
- Breakout: price > high (LONG) or price < low (SHORT)

**Breakout size:**
- Minimum: 0.5 * ATR_15m (meaningful move, not noise)
- Measure: (price - range_high) for LONG, (range_low - price) for SHORT

### Momentum Validation

**TFI threshold:**
- LONG: TFI_60s > +0.05 (buy pressure)
- SHORT: TFI_60s < -0.05 (sell pressure)

**Price momentum:**
- LONG: price > EMA_50 (4h) or price > recent swing low
- SHORT: price < EMA_50 (4h) or price < recent swing high

### Expansion Overheating Protection

**ATR panic threshold:**
- ATR_4h_norm < 0.029 (below extreme volatility spike)
- Protects against entering at peak expansion (late stage)

**Price extension:**
- Optional: Bollinger Bands (price within 2σ of EMA_50)
- Or: ATR percentile < 85 (not extreme)

### Risk/Reward

**Minimum RR:** 2.0  
**Stop placement:** 0.35 * ATR_15m beyond structure (range low/high)  
**Targets:** 2.5R (T1), 3.5R (T2)

---

## Implementation Deliverables

### Checkpoint 1 (Target: 1 week)

1. **Setup contract:**
   - `research_lab/setups/volatility_breakout.py`
   - Classes: `VolatilityBreakoutLong`, `VolatilityBreakoutShort`
   - Inherit from `BaseSetup`
   - Config dataclass with thresholds (ATR slope, breakout size, TFI, etc.)
   - **ATR expansion detection function** (slope-based, NOT absolute level)

2. **Backtest runner:**
   - `research_lab/backtest_volatility_breakout.py`
   - Full-range replay (2022-01-01 → 2026-03-29)
   - Decision funnel tracking
   - Per-regime breakdown
   - Expansion state distribution analysis

3. **Hard gate evaluator:**
   - `research_lab/evaluate_volatility_gates.py`
   - Gates (see Hard Gates section below)
   - Output: `research_lab/reports/volatility_gate_results.json`

4. **Hypothesis document:**
   - `research_lab/research/VOLATILITY_BREAKOUT_HYPOTHESIS.md`
   - Expansion state definition (rising ATR, not low ATR)
   - Clear distinction from compression_breakout
   - Why 15m-compatible

5. **Tests:**
   - `tests/test_research_lab_volatility_breakout.py`
   - Setup instantiation, config validation
   - Expansion state detection (ATR slope calculation)
   - Structure breakout logic
   - Entry timing validation (NOT during compression)
   - Edge cases: flat ATR (no expansion), compression regime (reject)

6. **Validation report:**
   - `research_lab/reports/volatility_breakout_validation_report.md`
   - Full-range metrics (ER, PF, DD, Sharpe)
   - Per-regime breakdown
   - Per-direction breakdown (LONG vs SHORT)
   - Decision funnel (cycles → expansion states → candidates → trades)
   - Expansion continuation rate (% of trades where expansion continued)

7. **Audit package:**
   - `research_lab/reports/VOLATILITY_BREAKOUT_AUDIT_PACKAGE.md`
   - Executive summary
   - Hard gate results table
   - Direction breakdown
   - Builder verdict with reasoning
   - Checkpoint reference

8. **Smoke tests:**
   - Full-range backtest on local V3 data
   - `pytest tests/test_research_lab_volatility_breakout.py` (all pass)
   - `compileall` clean
   - Gate evaluation runs without errors

9. **ATR analysis (CRITICAL for audit):**
   - Report: `research_lab/reports/atr_expansion_distribution.md`
   - Questions to answer:
     - How often does ATR expansion state occur? (% of cycles)
     - What is typical expansion duration? (cycles)
     - What % of expansions are entered during compression vs expansion state?
     - If most entries occur during compression, setup is compression_breakout 2.0 (FAIL)

10. **Milestone tracker update:**
    - Update `docs/MILESTONE_TRACKER.md` with Checkpoint 1 results

---

## Hard Gates

| Gate | Requirement | Rejection Criterion | Measurement |
|---|---|---|---|
| **Expansion state ER** | `> 1.5` | `< 1.0` | Expectancy R for trades entered during expansion state |
| **Expansion continuation rate** | `>= 60%` | `< 50%` | % of trades where ATR continued rising after entry (validated at T1 or exit) |
| **Minimum total trades** | `>= 20` | `< 10` | Total closed trades in full-range backtest |
| **Expansion entry rate** | `>= 80%` | `< 50%` | % of entries that occurred during expansion state (NOT compression) |
| **Overlap vs sweep_reclaim** | `< 30%` | `> 50%` | Candidate-level temporal overlap (run if >=20 trades) |
| **Walk-forward** | `2/2` windows pass | Any window fail | WF validation (run only if Checkpoint 1 ER >1.5) |
| **Safety flags** | No blocking flags | Any blocking flag | Fragility, concentration, extreme metrics |
| **Explainability** | All signals have `reasons[]` | Any missing | Signal transparency |

### Expansion Continuation Rate (CRITICAL)

**Definition:** For each trade, check if ATR continued rising from entry to T1 (or exit if stopped out earlier).

**Measurement:**
1. ATR at entry: `atr_entry`
2. ATR at T1 (or exit): `atr_exit`
3. Continuation = `atr_exit > atr_entry` (expansion continued)
4. Rate = (continuation trades) / (total trades)

**Why this metric matters:**
Validates the hypothesis: "Expansion continues after entry." If continuation rate < 60%, expansion exhausts quickly (not tradeable at 15m frequency).

### Expansion Entry Rate (PREVENTS COMPRESSION_BREAKOUT 2.0)

**Definition:** % of entries that occurred during confirmed expansion state (NOT compression state).

**Measurement:**
1. For each candidate, check ATR state at entry time
2. Expansion state: ATR rising (slope positive)
3. Compression state: ATR low or flat
4. Entry rate = (expansion entries) / (total entries)

**Why this metric matters:**
If most entries occur during compression (low ATR), the setup is compression_breakout 2.0 (entering before expansion, anticipating it). This MUST be >= 80% to prove setup enters during expansion.

**Red flag:** If expansion entry rate < 50%, the setup is entering during compression (wrong timing). This triggers REJECT verdict.

---

## Rejection Criteria

**Hard stop if any of these conditions at Checkpoint 1:**

1. **Insufficient sample:** `< 10` total trades (cannot validate)
2. **Negative edge:** Expansion state ER `< 1.0` (loses money)
3. **Low continuation rate:** Expansion continuation `< 50%` (expansion exhausts too fast)
4. **Wrong entry timing:** Expansion entry rate `< 50%` (entering during compression = compression_breakout 2.0)
5. **Compression state entries:** If analysis shows most entries during compression regime or low ATR (violates setup distinction)

**If hard stop triggered:**
- Do NOT attempt Iteration A (parameter rescue)
- Deliver audit package with verdict: `HYPOTHESIS FAILED` or `TIMING_VIOLATION` (if compression entries)
- No diagnostic iteration unless concrete measurement flaw identified

**Marginal case (iteration allowed):**
- Expansion state ER between 1.0 and 1.5 (positive but below gate)
- Continuation rate between 50% and 60% (marginal support)
- Expansion entry rate between 50% and 80% (some compression leak)
- Sample size adequate (>= 20 trades)
- ONE diagnostic iteration to investigate: ATR slope calculation accuracy, expansion state definition tuning, entry timing window

---

## Known Issues

| # | Issue | Blocking for this milestone? |
|---|---|---|
| 1 | ATR expansion state definition untested (new logic) | YOU ASSESS - validate with historical ATR distribution |
| 2 | Expansion state might be rare (need to verify frequency) | YOU ASSESS - analyze % of cycles in expansion |
| 3 | Risk of compression entry leak (setup might collapse to compression_breakout) | YES - expansion entry rate gate MUST pass |
| 4 | Expansion continuation might be short-lived (< 15m window) | YOU ASSESS - measure typical expansion duration |

**If Issue #1 (ATR expansion definition unclear):**
- Start with simple slope calculation: `(atr_current - atr_6_cycles_ago) / atr_6_cycles_ago > 0.10`
- Validate with manual spot checks (visual ATR chart review)
- Report in audit package: how often expansion detected, typical duration

**If Issue #2 (expansion rare):**
- If `< 5%` of cycles are expansion state → discuss with Claude Code before full implementation
- Rare state might mean insufficient sample
- May need to relax expansion definition (e.g., lower slope threshold)

**If Issue #3 (compression entry leak):**
- Expansion entry rate gate < 80% triggers audit review
- If most entries during compression, setup is compression_breakout 2.0 (FAIL)
- This is the most critical gate for this setup

**If Issue #4 (expansion too short):**
- Measure typical expansion duration in cycles
- If most expansions last < 6 cycles (1.5 hours), entry window is too narrow
- 15m frequency might still be too slow

---

## Your First Response Must Contain

1. **Confirmed milestone scope** (what you will implement)
2. **Acceptance criteria** (how we know it is done)
3. **Known issues assessment** (which need investigation first)
4. **ATR expansion detection approach** (slope calculation method)
5. **Expansion entry rate validation plan** (how to prove no compression leak)
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
- Implementation: 2-3 days (including ATR expansion logic)
- Backtest + validation: 1-2 days
- ATR distribution analysis: 1 day
- Testing + audit package: 1 day

**If Checkpoint 1 hard stop:** Close immediately (no iteration)

**If Checkpoint 1 marginal:** ONE diagnostic iteration (2-3 days) - only if expansion entry rate issue, not edge failure

**If Checkpoint 1 promising (ER >1.5, continuation >=60%, expansion entry >=80%):** Walk-forward + overlap analysis (3-5 days)

**Total:** 1-2 weeks to conclusive verdict

---

## Success Looks Like

**Checkpoint 1 CANDIDATE result:**
- Expansion state ER: 2.0
- PF: 3.5
- Expansion continuation rate: 65%
- **Expansion entry rate: 85%** (most entries during expansion, not compression)
- Trades: 30 (adequate sample)
- Decision funnel: 7,500 expansion cycles → 45 candidates → 30 trades
- ATR distribution: Expansion state occurs 5% of cycles, lasts average 18 cycles (4.5 hours)
- Verdict: CANDIDATE_READY → proceed to walk-forward

**Checkpoint 1 REJECT result (edge failure):**
- Expansion state ER: -0.15 (negative)
- Continuation rate: 40% (expansion exhausts too fast)
- Expansion entry rate: 82% (timing correct, but no edge)
- Trades: 28 (adequate sample)
- Verdict: HYPOTHESIS FAILED (expansion continuation not profitable)

**Checkpoint 1 REJECT result (timing violation):**
- Expansion state ER: 1.8 (looks good)
- **Expansion entry rate: 35%** (most entries during compression)
- ATR analysis: 65% of entries had ATR slope negative or flat at entry time
- Verdict: TIMING_VIOLATION (compression_breakout 2.0 - enters before expansion)

---

## Research Context

**Portfolio status after four setups:**
- absorption_continuation: FAILED (CVD not predictive)
- compression_breakout: FAILED (sequential timing incompatible)
- crowded_unwind: FAILED (cascade catching too fast)
- post_cascade_momentum: BLOCKED (infrastructure gap)
- **volatility_breakout: ACTIVE** (this milestone)
- Remaining: regime_reversal

**Pattern identified:** Cascade-based setups (catching OR aftermath) incompatible with 15m frequency. Expansion-based setups use slower state transitions (hours-to-days).

**Fast failure discipline continues:** ONE checkpoint to prove basic edge. If hard stop triggers, close immediately. No parameter rescue.

**Why this setup has reasonable success probability:**
1. Applies all four failure lessons (objective, temporal alignment, timing compatible, no infrastructure gaps)
2. Expansion state persists longer than cascade events (hours vs minutes)
3. Entry during active state (not anticipating future state)
4. No cascade dependencies (uses ATR, structure, momentum only)

**Estimated success probability:** 30-40% (unproven, but addresses known failure patterns)

---

## Questions for Claude Code Before Starting

If any of these unknowns block your implementation plan, ask Claude Code BEFORE coding:

1. **ATR expansion frequency:** Is expansion state common enough for adequate sample size?
2. **ATR slope calculation:** Which method preferred (slope over N cycles, percentile change, or other)?
3. **Compression leak prevention:** Besides expansion entry rate gate, any other validation needed?
4. **Regime filter:** Should compression regime be hard-blocked, or use ATR slope as primary filter?

Do NOT proceed with implementation if you're unsure about ATR expansion detection logic. Ask first.

---

## Final Note

**This handoff is NOT a suggestion.** It is a tested, scoped, research-only milestone with clear gates and rejection criteria.

**The most important gate:** Expansion entry rate >= 80%. If this fails, the setup is compression_breakout 2.0 (entering during compression, anticipating expansion). That timing violation is immediate REJECT, not iteration.

Your job:
1. Confirm scope and plan
2. Implement Checkpoint 1 deliverables (including ATR expansion detection)
3. Validate expansion entry rate (prove no compression leak)
4. Push results for Claude Code audit
5. Do NOT self-audit or self-approve

Claude Code will audit your work and deliver verdict: HYPOTHESIS FAILED / TIMING_VIOLATION / ITERATE / CANDIDATE_READY.

Good luck. We've learned from four failures. This setup applies those lessons. Entry timing distinction is critical.

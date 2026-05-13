# HANDOFF: POST-CASCADE-MOMENTUM-RESEARCH-V1

**From:** Claude Code (Auditor)  
**To:** Codex (Builder)  
**Date:** 2026-05-13  
**Milestone:** `POST-CASCADE-MOMENTUM-RESEARCH-V1`  
**Type:** Research-only (no production changes)

---

## Checkpoint

- **Last commit:** `0930440` - `audit: CROWDED-UNWIND-CHECKPOINT-1 — HYPOTHESIS FAILED`
- **Branch:** `main`
- **Working tree:** clean

---

## Before You Code

Read these files (mandatory):

1. **Relevant blueprints:**
   - `docs/BLUEPRINT_V1.md` — bot/runtime architecture
   - `docs/BLUEPRINT_RESEARCH_LAB.md` — research lab architecture and workflow
2. **`AGENTS.md`** — discipline + your workflow rules
3. **`docs/MILESTONE_TRACKER.md`** — current status + known issues
4. **Prior failure audits (CRITICAL - read all three):**
   - `docs/audits/AUDIT_ABSORPTION_CONTINUATION_ITERATION_A_2026-05-12.md`
   - `docs/audits/AUDIT_COMPRESSION_BREAKOUT_ITERATION_A_2026-05-12.md`
   - `docs/audits/AUDIT_CROWDED_UNWIND_CHECKPOINT_1_2026-05-13.md`

---

## Milestone: POST-CASCADE-MOMENTUM-RESEARCH-V1

**Scope:** Research-only validation of post_cascade_momentum setup (aftermath state after liquidation cascade → momentum continuation).

**Blueprint reference:** `docs/BLUEPRINT_V1.md` Section 4.3 (Regime Engine: `post_liquidation` regime), Section 3.2 (Signal generation)

---

## Why This Setup is Different (Lessons Applied)

### Three consecutive failures taught us:

1. **Absorption (FAILED):** Interpretive signals (CVD divergence) are not predictive in BTC perps
   - **Lesson:** Use objective, measurable metrics only
   - **Applied:** This setup uses regime state, force order history (counts, not real-time spikes), momentum indicators

2. **Compression (FAILED):** Sequential events (compression → breakout) cannot be caught simultaneously
   - **Lesson:** Entry trigger and edge thesis must coincide temporally
   - **Applied:** This setup trades aftermath state (post-cascade), not event transition

3. **Crowded Unwind (FAILED):** Force spikes + crowding require sub-minute timing, but 15m decision cycle is too slow
   - **Lesson:** Avoid setups requiring split-second reaction when decision frequency is 15m
   - **Applied:** This setup enters AFTER cascade confirms (post_liquidation regime), not DURING cascade event

### The Critical Distinction: Post-Event State vs Late Event Catching

**This is NOT "late crowded_unwind"**:
- crowded_unwind tried to catch cascade in progress (concurrent force spike + crowding)
- post_cascade_momentum waits for cascade to COMPLETE, then trades the cleaned aftermath

**Timing compatibility:**
- Cascade event: seconds-to-minutes (too fast for 15m cycles)
- Post-cascade state: minutes-to-hours (compatible with 15m cycles)
- Entry trigger: Regime transitions to `post_liquidation` (state-based, not event-based)

**Edge thesis:**
- NOT: "catch liquidations as they happen"
- YES: "after overleveraged positions clear, market structure is cleaner and momentum continues"

---

## Hypothesis

**Market Structure:**
After a liquidation cascade forces overleveraged traders to exit:
1. Weak hands are cleared from the market
2. Supply/demand imbalance reduces
3. Directional momentum continues in cascade direction (clean structure allows trend to persist)
4. `post_liquidation` regime marks this aftermath state

**Counterparty:**
Traders who survived the cascade and continue in the cascade direction (not the liquidated traders).

**Entry Timing:**
AFTER `post_liquidation` regime confirms, with momentum validation in cascade direction.

**Why this edge might exist:**
- Liquidations remove resistance (forced exits clear counter-trend positions)
- Surviving participants have stronger hands (not overleveraged)
- Order flow becomes more directional (less chop from forced exits)
- Cascade direction often continues as market finds new equilibrium

**What makes this 15m-compatible:**
- Entry is state-based (`post_liquidation` regime), not event-based (force spike)
- Regime persists for multiple decision cycles (minutes-to-hours)
- No need to catch the cascade moment (already happened)
- Aftermath structure evolves slowly enough for 15m decisions

---

## Target Regimes

**Primary:** `post_liquidation` (entry only in this regime)

**Regime context:** Post-liquidation regime is detected by `RegimeEngine` when:
- Recent force order activity (last N cycles) exceeded threshold
- Volatility spike occurred
- Market is in aftermath phase (not active cascade)

**Critical:** Do NOT enter during active cascade (crowded_leverage with real-time force spike). Only enter AFTER regime transitions to `post_liquidation`.

---

## Setup Directions

### Long Setup: `post_cascade_momentum_long`

**Entry conditions (ALL must be true):**
1. **Regime:** `post_liquidation` (required)
2. **Cascade direction:** Recent force orders were predominantly SHORT liquidations (upward cascade)
3. **Momentum validation:**
   - Price above recent structure (e.g., above 15m EMA or recent swing low)
   - TFI showing continued buy pressure (TFI_60s > threshold, e.g., 0.05)
   - Or: ATR expansion continuing (not contracting)
4. **Timing confirmation:** Cascade occurred recently (e.g., within last 4-12 decision cycles = 1-3 hours)
5. **Structure invalidation:** Clear structural support (recent low for stop placement)
6. **Risk/reward:** RR ratio >= 2.0 minimum

**Exit:**
- Stop: Below recent structural low (from post-cascade range)
- Target 1: 2.5R
- Target 2: 3.5R

**Invalidation (block entry):**
- Cascade direction unclear (mixed long/short liquidations)
- Momentum already exhausted (price near resistance, TFI negative)
- Regime already exited `post_liquidation` (too late)
- Volatility contracting (cascade energy dissipated)

### Short Setup: `post_cascade_momentum_short`

**Entry conditions (ALL must be true):**
1. **Regime:** `post_liquidation` (required)
2. **Cascade direction:** Recent force orders were predominantly LONG liquidations (downward cascade)
3. **Momentum validation:**
   - Price below recent structure (e.g., below 15m EMA or recent swing high)
   - TFI showing continued sell pressure (TFI_60s < threshold, e.g., -0.05)
   - Or: ATR expansion continuing (not contracting)
4. **Timing confirmation:** Cascade occurred recently (e.g., within last 4-12 decision cycles = 1-3 hours)
5. **Structure invalidation:** Clear structural resistance (recent high for stop placement)
6. **Risk/reward:** RR ratio >= 2.0 minimum

**Exit:**
- Stop: Above recent structural high (from post-cascade range)
- Target 1: 2.5R
- Target 2: 3.5R

**Invalidation (block entry):**
- Cascade direction unclear (mixed long/short liquidations)
- Momentum already exhausted (price near support, TFI positive)
- Regime already exited `post_liquidation` (too late)
- Volatility contracting (cascade energy dissipated)

---

## Key Metrics and Thresholds

**Force Order History:**
- Look back: 4-12 decision cycles (1-3 hours)
- Direction detection: Count long vs short force orders in lookback window
- Threshold: >= 70% in one direction to classify cascade direction
- Source: `force_orders` table (historical, not real-time spike detection)

**Momentum Indicators:**
- TFI_60s threshold: ±0.05 (directional pressure confirmation)
- Price vs structure: EMA (50 on 15m) or recent swing high/low
- ATR behavior: Not contracting (ATR_4h_norm not declining)

**Timing:**
- Entry window: Within 4-12 cycles after cascade (1-3 hours)
- Late entry rejection: If post_liquidation regime already old (e.g., >12 cycles = 3+ hours)

**Risk/Reward:**
- Minimum RR: 2.0
- Stop offset: 0.35 * ATR_15m from structure (same as other setups)
- Targets: 2.5R (T1), 3.5R (T2)

---

## Implementation Deliverables

### Checkpoint 1 (Target: 1 week)

1. **Setup contract:**
   - `research_lab/setups/post_cascade_momentum.py`
   - Classes: `PostCascadeMomentumLong`, `PostCascadeMomentumShort`
   - Inherit from `BaseSetup`
   - Implement `evaluate_structure()` and `generate_signal_candidate()`
   - Config dataclass with thresholds (force lookback, TFI threshold, RR minimum, etc.)

2. **Backtest runner:**
   - `research_lab/backtest_post_cascade.py`
   - Post-liquidation-only replay (filter to `post_liquidation` regime)
   - Decision funnel tracking: cycles → candidates → trades
   - Per-regime breakdown
   - Cascade direction detection logic (force order history analysis)

3. **Hard gate evaluator:**
   - `research_lab/evaluate_post_cascade_gates.py`
   - Gates (see Hard Gates section below)
   - Output: `research_lab/reports/post_cascade_gate_results.json`

4. **Hypothesis document:**
   - `research_lab/research/POST_CASCADE_MOMENTUM_HYPOTHESIS.md`
   - Market structure, edge thesis, why it's different from crowded_unwind
   - Cascade direction detection logic
   - Aftermath state definition

5. **Tests:**
   - `tests/test_research_lab_post_cascade.py`
   - Setup instantiation, config validation
   - Entry logic (regime check, cascade direction, momentum validation)
   - Force order history analysis (direction detection from lookback window)
   - Stop/target calculation
   - Edge cases: mixed cascade direction, stale post_liquidation regime

6. **Validation report:**
   - `research_lab/reports/post_cascade_validation_report.md`
   - Full-range metrics (ER, PF, DD, Sharpe)
   - Per-regime breakdown (post_liquidation should be 100% of trades)
   - Per-direction breakdown (LONG vs SHORT)
   - Decision funnel (cycles → candidates → trades)
   - Cascade direction accuracy (% of trades where momentum continued in cascade direction)

7. **Audit package:**
   - `research_lab/reports/POST_CASCADE_AUDIT_PACKAGE.md`
   - Executive summary (results, verdict, interpretation)
   - Hard gate results table
   - Direction breakdown
   - Builder verdict with reasoning
   - Checkpoint reference (commit, branch, date)

8. **Smoke tests:**
   - Full-range backtest on local V3 data (2022-01-01 → 2026-03-29)
   - `pytest tests/test_research_lab_post_cascade.py` (all pass)
   - `compileall` clean
   - Gate evaluation runs without errors

9. **Force order data:**
   - If local `storage/btc_bot.db` has insufficient force orders, create research DB copy
   - Backfill from production server (same process as crowded_unwind)
   - Document backfill metadata (source, count, time range)
   - Keep research DB untracked, do not mutate production DB

10. **Milestone tracker update:**
    - Update `docs/MILESTONE_TRACKER.md` with Checkpoint 1 results
    - Include: trade count, ER, PF, cascade continuation rate, builder verdict

---

## Hard Gates

| Gate | Requirement | Rejection Criterion | Measurement |
|---|---|---|---|
| **Post-liquidation regime ER** | `> 1.5` | `< 1.0` | Expectancy R in `post_liquidation` regime only |
| **Cascade continuation rate** | `>= 60%` | `< 50%` | % of trades where momentum continued in cascade direction (validated at exit) |
| **Minimum total trades** | `>= 20` | `< 10` | Total closed trades in full-range backtest |
| **Post-liquidation trade count** | `>= 10` | `< 5` | Trades in target regime (should be 100% if logic correct) |
| **Overlap vs sweep_reclaim** | `< 30%` | `> 50%` | Candidate-level temporal overlap with sweep_reclaim (run if >=20 trades) |
| **Walk-forward** | `2/2` windows pass | Any window fail | Walk-forward validation (run if Checkpoint 1 ER >1.5) |
| **Safety flags** | No blocking flags | Any blocking flag | Fragility, concentration, or extreme metrics |
| **Explainability** | All signals have `reasons[]` | Any signal missing reasons | Signal transparency |

### Cascade Continuation Rate (CRITICAL)

**Definition:** For each closed trade, check if the trade's direction matched the cascade direction AND if the trade was profitable (captured continuation).

**Measurement:**
1. Determine cascade direction at entry (from force order history lookback)
2. Trade direction (LONG or SHORT)
3. Trade outcome (win or loss)
4. Continuation = (direction matches cascade) AND (trade won)
5. Rate = (continuation wins) / (total trades)

**Why this metric matters:**
This directly validates the hypothesis: "momentum continues in cascade direction after cleanup." If continuation rate < 60%, the aftermath momentum thesis is not supported.

**Distinguish from liquidation capture:**
- Liquidation capture (crowded_unwind): Did we enter during ongoing liquidations?
- Cascade continuation (post_cascade_momentum): Did momentum continue AFTER cascade ended?

---

## Rejection Criteria

**Hard stop if any of these conditions at Checkpoint 1:**

1. **Insufficient sample:** `< 10` total trades (cannot validate with tiny sample)
2. **Negative edge:** Post-liquidation ER `< 1.0` (setup loses money in target regime)
3. **Low continuation rate:** Cascade continuation `< 50%` (momentum thesis fails)
4. **Wrong regime:** Trades occur outside `post_liquidation` regime (logic bug, not hypothesis failure)

**If hard stop triggered:**
- Do NOT attempt Iteration A (parameter rescue)
- Deliver audit package with verdict: `HYPOTHESIS FAILED` or `IMPLEMENTATION_BUG` (if wrong regime)
- No diagnostic iteration unless concrete measurement flaw identified (not just weak results)

**Marginal case (iteration allowed):**
- Post-liquidation ER between 1.0 and 1.5 (positive but below gate)
- Continuation rate between 50% and 60% (marginal thesis support)
- Sample size adequate (>= 20 trades)
- ONE diagnostic iteration to investigate: cascade direction detection accuracy, momentum validation logic, entry timing window

---

## Cascade Direction Detection Logic

**Critical implementation requirement:**

The setup must correctly identify cascade direction from force order history. This is NOT real-time spike detection (crowded_unwind failed at that). This is historical analysis at entry time.

**Suggested approach:**

```python
def detect_cascade_direction(
    force_orders: list[ForceOrder],  # from last 4-12 cycles
    threshold: float = 0.70  # 70% in one direction
) -> str | None:
    """
    Analyze force order history to determine cascade direction.
    
    Returns:
        'up': cascade was upward (short liquidations dominated)
        'down': cascade was downward (long liquidations dominated)
        None: direction unclear (mixed or insufficient data)
    """
    if not force_orders:
        return None
    
    long_liq_count = sum(1 for fo in force_orders if fo.side == 'LONG')  # longs liquidated = downward pressure
    short_liq_count = sum(1 for fo in force_orders if fo.side == 'SHORT')  # shorts liquidated = upward pressure
    total = long_liq_count + short_liq_count
    
    if total == 0:
        return None
    
    if short_liq_count / total >= threshold:
        return 'up'  # shorts liquidated → upward cascade → enter LONG
    elif long_liq_count / total >= threshold:
        return 'down'  # longs liquidated → downward cascade → enter SHORT
    else:
        return None  # mixed, no clear direction
```

**Entry logic:**
- If cascade direction = 'up' AND regime = post_liquidation → consider LONG
- If cascade direction = 'down' AND regime = post_liquidation → consider SHORT
- If cascade direction = None → reject entry (unclear)

**Validation at exit:**
- For cascade continuation metric, use the cascade direction determined at entry
- Compare to trade outcome (did LONG after upward cascade win?)

---

## Momentum Validation (Not CVD)

**DO NOT use CVD as primary momentum indicator.** Absorption failure proved CVD divergence is not predictive.

**Recommended momentum indicators:**

1. **TFI (Taker Flow Imbalance):**
   - LONG: TFI_60s > +0.05 (buy pressure)
   - SHORT: TFI_60s < -0.05 (sell pressure)

2. **Price vs structure:**
   - LONG: price > EMA_50 (15m) OR price > recent swing low
   - SHORT: price < EMA_50 (15m) OR price < recent swing high

3. **ATR behavior (optional):**
   - ATR_4h_norm not declining (cascade energy not dissipating)

**Why these work:**
- TFI: Objective, directional, no interpretation needed
- Price vs structure: Observable, no divergence interpretation
- ATR: Volatility context, not predictive signal

**Confluence scoring (optional):**
- Cascade direction clear: +2
- TFI aligns with direction: +1
- Price structure supports: +1
- ATR elevated: +0.5
- RR >= 2.5: +1
- Total >= 4.0 for entry

---

## Known Issues (from Claude Code audit history)

| # | Issue | Blocking for this milestone? |
|---|---|---|
| 1 | Local DB may have 0 or insufficient force orders | YES - backfill from server if needed |
| 2 | `post_liquidation` regime may be rare (need to verify frequency) | YOU ASSESS - check regime distribution first |
| 3 | Cascade direction detection accuracy unknown (new logic) | YOU ASSESS - validate with historical data |
| 4 | Aftermath state duration unknown (how long does post_liquidation last?) | YOU ASSESS - analyze regime persistence |

**If Issue #1 (force order sparsity):**
- Create research DB copy (untracked)
- Backfill from production server: `ssh root@204.168.146.253` (query `force_orders` table)
- Document backfill metadata in audit package
- Do NOT mutate `storage/btc_bot.db`

**If Issue #2 (post_liquidation rare):**
- If `< 1%` of cycles are post_liquidation → discuss with Claude Code before building
- Rare regime may mean insufficient sample size
- May need to relax regime requirement (allow normal regime if recent cascade detected)

**If Issue #3 (cascade direction unclear):**
- Validate direction detection logic with manual spot checks
- Report % of cycles where direction was clear vs unclear
- If most cycles are "unclear" → tighten threshold or change logic

**If Issue #4 (post_liquidation too short):**
- If regime only lasts 1-2 cycles (15-30 min), entry window is very narrow
- Consider expanding entry window: allow `normal` regime if recent cascade (within lookback)

---

## Your First Response Must Contain

1. **Confirmed milestone scope** (what you will implement)
2. **Acceptance criteria** (how we know it is done)
3. **Known issues assessment** (which are in-scope, which need investigation first)
4. **Implementation plan** (ordered steps)
5. **Only then: start coding**

---

## Commit Discipline

- **WHAT / WHY / STATUS** in every commit message
- Do NOT self-mark as "done". Claude Code audits after push.
- Research-only: no changes to `settings.py`, `orchestrator.py`, or production modules

---

## Expected Timeline

**Checkpoint 1:** 1 week
- Implementation: 2-3 days
- Backtest + validation: 1-2 days
- Testing + audit package: 1 day
- Buffer for force order backfill or regime investigation: 1 day

**If Checkpoint 1 hard stop:** Close immediately (no iteration)

**If Checkpoint 1 marginal:** ONE diagnostic iteration (2-3 days)

**If Checkpoint 1 promising (ER >1.5, continuation >=60%):** Walk-forward + overlap analysis (3-5 days)

**Total:** 1-2 weeks to conclusive verdict

---

## Success Looks Like

**Checkpoint 1 CANDIDATE result:**
- Post-liquidation ER: 2.1
- PF: 3.8
- Cascade continuation rate: 68%
- Trades: 35 (all in post_liquidation or recent-cascade context)
- Decision funnel: 1,500 post_liquidation cycles → 42 candidates → 35 trades (logical funnel)
- Regime distribution: post_liquidation regime exists, covers 1-2% of cycles
- Cascade direction: 95% of candidates had clear direction (>70% threshold)
- Verdict: CANDIDATE_READY → proceed to walk-forward

**Checkpoint 1 REJECT result (hard stop):**
- Post-liquidation ER: -0.20 (negative)
- Continuation rate: 35% (random, not predictive)
- Trades: 28 (adequate sample, but no edge)
- Verdict: HYPOTHESIS FAILED (aftermath momentum does not persist)

**Checkpoint 1 ITERATE result (marginal):**
- Post-liquidation ER: 1.2 (positive but below 1.5)
- Continuation rate: 55% (marginal support)
- Trades: 32 (adequate sample)
- Issue identified: Cascade direction detection too aggressive (many "unclear" rejected as "clear")
- ONE iteration to tighten direction threshold or analyze entry timing window

---

## Research Context

**Portfolio status after three failures:**
- absorption_continuation: FAILED (CVD not predictive)
- compression_breakout: FAILED (sequential timing incompatible)
- crowded_unwind: FAILED (decision frequency incompatible)
- **post_cascade_momentum: ACTIVE** (this milestone)
- Remaining: volatility_breakout, regime_reversal

**Fast failure discipline:**
Three setups tested in 4 days (2026-05-09 → 2026-05-13). Each got fair validation with diagnostic iterations where warranted. All failed conclusively, not prematurely.

This discipline continues: post_cascade_momentum gets ONE checkpoint to prove basic edge. If hard stop triggers, close immediately. No parameter rescue.

**Why this setup has higher success probability:**
1. Applies all three failure lessons (objective metrics, timing compatibility, 15m-compatible state)
2. Post-event state is slower-moving (minutes-to-hours vs seconds-to-minutes)
3. Edge thesis is aftermath-based (cleaned structure), not event-catching
4. RegimeEngine already detects post_liquidation (infrastructure exists)

**Estimated success probability:** 35-45% (higher than prior three, but still unproven)

---

## Questions for Claude Code Before Starting

If any of these unknowns block your implementation plan, ask Claude Code BEFORE coding:

1. **Regime frequency:** Is `post_liquidation` regime common enough for adequate sample size?
2. **Force order access:** Is force order history accessible in backtest replay, or do we need special query logic?
3. **Cascade timing:** Should we allow `normal` regime if recent cascade detected (relaxed regime requirement)?
4. **Momentum indicator:** Is TFI_60s sufficient, or do we need additional momentum confirmation?

Do NOT proceed with implementation if you're unsure about architecture or data availability. Ask first.

---

## Final Note

**This handoff is NOT a suggestion.** It is a tested, scoped, research-only milestone with clear gates and rejection criteria.

Your job:
1. Confirm scope and plan
2. Implement Checkpoint 1 deliverables
3. Push results for Claude Code audit
4. Do NOT self-audit or self-approve

Claude Code will audit your work and deliver verdict: HYPOTHESIS FAILED / ITERATE / CANDIDATE_READY.

Good luck. We've learned a lot from three failures. This setup applies those lessons.

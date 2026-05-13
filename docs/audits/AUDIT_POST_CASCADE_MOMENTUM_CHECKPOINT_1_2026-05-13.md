# AUDIT: POST-CASCADE-MOMENTUM-CHECKPOINT-1

Date: 2026-05-13  
Auditor: Claude Code  
Commit: `9990194` - `research: add post cascade momentum checkpoint 1`  
Branch: `research/post-cascade-momentum-v1`

## Verdict: BLOCKED_BY_INFRASTRUCTURE

## Layer Separation: PASS
- Research-only setups isolated in `research_lab/setups/post_cascade_momentum.py`
- No production path contamination
- Clean imports, research DB copy used (no mutation of `storage/btc_bot.db`)

## Contract Compliance: PASS
- `PostCascadeMomentumLong` and `PostCascadeMomentumShort` inherit from `BaseSetup`
- Implements `evaluate_structure()` and `generate_signal_candidate()` correctly
- Returns `SignalCandidate` with all required fields
- Cascade direction detection logic implemented (force order history analysis)

## Determinism: PASS
- Setup logic is deterministic
- Cascade direction from historical force order counts
- No random state

## State Integrity: PASS
- Research DB copy used, production DB untouched
- No persistent state between runs

## Error Handling: PASS
- Defensive checks: price > 0, ATR floor, safe min/max on empty lists
- Handles missing force orders gracefully

## Smoke Coverage: PASS
- Tests: `tests/test_research_lab_post_cascade.py` (48 passed, 2 skipped)
- `compileall` OK
- Backtest runs without errors (produces 0 trades, not crash)

## Tech Debt: LOW
- Implementation clean, follows handoff specification
- Config dataclass with sensible defaults
- Cascade direction detection logic well-structured

## AGENTS.md Compliance: PASS
- Commit message follows WHAT/WHY/STATUS format
- Research-only work isolated
- No production changes

## Methodology Integrity: PASS
- Hypothesis documented clearly
- Setup correctly implements post-event state logic (NOT late crowded_unwind)
- Cascade direction detection uses historical lookback (NOT real-time spike catching)
- Implementation matches handoff specification

## Promotion Safety: PASS
- No promotion artifacts generated (correctly - no trades)
- Hard gates evaluated
- Red flags correctly identify REJECT

## Reproducibility & Lineage: PASS
- Commit hash, branch, date range recorded
- Force order source documented (same research DB as crowded_unwind: 146,864 rows)

## Data Isolation: PASS
- Research DB copy used (untracked)
- Production DB untouched

## Search Space Governance: PASS
- Parameters use config defaults
- No parameter tuning attempted

## Artifact Consistency: PASS
- Audit package, gate results, hypothesis doc all consistent
- Builder verdict (REJECT_BLOCKED_BY_ABSENT_TARGET_REGIME) matches reality

## Boundary Coupling: PASS
- Dependencies on `backtest/`, `core/models`, `RegimeEngine` explicit
- No leaked ownership

---

## Critical Issues

### 1. Infrastructure blocker: `post_liquidation` regime definition mismatch

**Evidence:**
- 148,596 decision cycles
- 0 cycles classified as `post_liquidation`
- 0 candidates, 0 trades
- Force order data present (146,864 rows backfilled from production)

**Root cause: Blueprint vs Reality mismatch**

**What the handoff assumed:**
`post_liquidation` regime marks **aftermath state** after cascade completes:
- Cascade happened recently (1-3 hours ago)
- Force orders have calmed down (no current spike)
- Market is in post-cascade cleanup phase
- Entry window: minutes to hours after cascade

**What `RegimeEngine` actually implements:**

```python
def _is_post_liquidation(self, features: Features) -> bool:
    if not features.force_order_spike:           # Active spike NOW
        return False
    if abs(features.tfi_60s) < 0.2:              # Strong directional flow
        return False
    return features.force_order_decreasing        # Spike declining (last 3 cycles)
```

Requirements:
1. `force_order_spike` = True (current rate > mean + 2σ)
2. `abs(tfi_60s)` >= 0.2
3. `force_order_decreasing` = True (rate[-1] < rate[-2] < rate[-3])

This detects: **"Cascade tail"** (spike active but winding down), NOT aftermath state.

**Timeline comparison:**

| Phase | Duration | Current `post_liquidation` | Handoff needed |
|---|---|---|---|
| Cascade ramp-up | Seconds | ❌ No (no spike yet) | ❌ No (too early) |
| Cascade peak | Seconds-minutes | ❌ No (spike rising, not decreasing) | ❌ No (trying to catch this failed in crowded_unwind) |
| **Cascade tail** | **Seconds-minutes** | **✅ Detects HERE** | **❌ No (still too fast for 15m)** |
| **Aftermath** | **Minutes-hours** | **❌ No (no active spike)** | **✅ Needs HERE** |

**Why 0 cycles triggered:**

The triple condition (active spike AND declining AND strong TFI) is extremely rare:
- Active spike: uncommon (maybe 0.5-1% of cycles)
- AND declining for 3 consecutive cycles: very narrow window (cascade tail lasts seconds to minutes)
- AND strong TFI >= 0.2: adds another filter

Combined probability at 15m decision frequency: near zero.

**Why this is BLOCKED, not FAILED:**

- absorption/compression/crowded_unwind: **Tested hypothesis, found no edge** (hypothesis failed)
- post_cascade_momentum: **Did not test hypothesis** (infrastructure missing)

The setup logic is correct. The cascade direction detection is implemented. But the target regime never occurs, so the hypothesis gets 0 test cases.

---

## Options Analysis

### Option A: Build research-only post-cascade detector (ONE iteration)

**Scope:**
- Create research-only function to detect "cascade occurred in last 4-12 cycles, now calmed"
- Logic: Query force order history, check for past spike, verify current rate is low
- Relax regime requirement: Allow `normal` or other regimes if recent cascade detected
- Timeline: 2-3 days

**Pros:**
- Tests the hypothesis properly (aftermath state, not cascade tail)
- Research-only (doesn't touch production `RegimeEngine`)
- Could work if cascades are frequent enough

**Cons:**
- Scope creep: Adds new infrastructure just for one research hypothesis
- If hypothesis passes, still need to rebuild in production `RegimeEngine` (double work)
- Cascades might still be rare (low trade count risk persists)
- Violates fast-failure discipline (rescuing with infrastructure additions)

### Option B: Close milestone as BLOCKED (RECOMMENDED)

**Rationale:**
1. **Infrastructure gap is fundamental:** `post_liquidation` as implemented doesn't match what we need. It detects cascade tail (still too fast for 15m), not aftermath (slow enough for 15m).

2. **Fast-failure discipline:** Don't rescue hypotheses with infrastructure additions. The setup was designed assuming `post_liquidation` existed as described. It doesn't. That's a blocker.

3. **Different from prior failures:** absorption/compression/crowded_unwind tested hypotheses and found no edge (hypothesis failures). This didn't get to test because infrastructure is missing (blocker).

4. **Scope discipline:** Building a research-only cascade detector is new infrastructure work, not parameter tuning. If we wanted real post-cascade trading, we'd fix `RegimeEngine` in production (out of scope for research portfolio).

5. **Portfolio research pressure:** 4 setups in 5 days, 3 failed hypotheses + 1 blocked. Continuing to invest in marginal infrastructure for untested hypotheses is not fast-failure approach.

6. **Lesson is clear:** Cascade-timing setups (whether catching cascade or catching aftermath) are incompatible with 15m decision frequency. Cascades evolve on seconds-to-minutes scales; aftermath detection needs sub-15m precision to catch the entry window.

### Option C: Investigate `RegimeEngine` tuning

**Scope:**
Lower thresholds in `RegimeEngine` to make `post_liquidation` trigger more often:
- Reduce `post_liq_tfi_abs_min` from 0.2 to 0.05
- Relax `force_order_decreasing` condition

**Cons:**
- Still parameter rescue (violates fast-failure)
- Changes production `RegimeEngine` (out of scope for research)
- Doesn't solve fundamental mismatch (cascade tail vs aftermath)

---

## Recommended Next Step

**Close POST-CASCADE-MOMENTUM-RESEARCH-V1 as BLOCKED_BY_INFRASTRUCTURE**

**Rationale:**
1. `post_liquidation` regime as implemented is cascade tail, not aftermath state
2. Building research-only detector is scope creep (new infrastructure for one hypothesis)
3. Fast-failure discipline: don't rescue with infrastructure additions
4. If cascade-aftermath trading is strategic priority, fix `RegimeEngine` in production (separate milestone)
5. If not strategic priority, move to setups using existing infrastructure

**Portfolio research status after closure:**
- absorption_continuation: FAILED (CVD not predictive)
- compression_breakout: FAILED (sequential timing incompatible)
- crowded_unwind: FAILED (decision frequency incompatible - cascade catching)
- post_cascade_momentum: **BLOCKED (decision frequency incompatible - cascade aftermath)**
- Remaining: volatility_breakout, regime_reversal

**Pattern identified:**
All cascade-related setups (crowded_unwind, post_cascade_momentum) are incompatible with 15m decision frequency:
- Cascade catching: too fast (seconds-minutes active event)
- Cascade aftermath: too fast (minutes-scale entry window after event)

Both require sub-15m timing precision. Avoid cascade-based setups until decision frequency improves.

**Key lesson:**
> Liquidation cascade signals (spike detection, aftermath detection) require timing precision incompatible with 15m decision cycles. The profitable windows (cascade middle, aftermath entry) occur on seconds-to-minutes scales. By the time 15m decision engine detects the state, opportunity is gone.

**Next milestone options:**

1. **volatility_breakout:** Expansion from low volatility → directional move (uses ATR, not cascade timing)
2. **regime_reversal:** Regime shift detection → counter-trend entry (uses regime transitions, not event timing)
3. **Pause research portfolio:** 4 setups in 5 days, all failed or blocked. Assess whether 15m decision frequency is fundamentally limiting.

---

## Observations

### Implementation Quality: Professional

Codex correctly:
- Followed handoff specification exactly (strict `post_liquidation` regime requirement)
- Implemented cascade direction detection from historical force orders (NOT real-time spike)
- Used research DB copy with backfilled force orders (no production mutation)
- Delivered clean audit package with clear builder verdict
- Did NOT attempt scope creep (no research-only detector without authorization)

### Handoff Assumption: Reasonable but Wrong

The handoff assumed `post_liquidation` regime existed as described in some blueprint references. This was reasonable based on:
- `RegimeState.POST_LIQUIDATION` exists in `core/models.py`
- `RegimeEngine._is_post_liquidation()` exists in `core/regime_engine.py`
- Blueprint references mention post-liquidation context

But the actual implementation (cascade tail, not aftermath) was not verified before handoff generation. This is a blueprint-vs-reality gap, not a handoff error.

### Data Quality: Adequate

Force order backfill (146,864 rows) was adequate. The 0 cycles result is not data sparsity; it's regime definition mismatch.

### Fast Failure Discipline: Maintained

5 days, 4 setups (3 FAILED, 1 BLOCKED). Each got fair validation:
- absorption: diagnostic iteration (CVD fix), then FAILED
- compression: diagnostic iteration (regime analysis), then FAILED
- crowded_unwind: no iteration (deeply negative, clear verdict)
- post_cascade: no iteration (infrastructure blocker, clear verdict)

No parameter rescue. No scope creep. Clean decisions.

---

## Audit Classification

**Research Lab Bug:** No implementation violations found. Codex implemented the handoff correctly.

**Strategy Methodology Debt:** The 15m decision frequency limitation is known and documented. Cascade-timing setups are incompatible with this constraint.

**Infrastructure Gap:** `RegimeEngine.post_liquidation` detects cascade tail (active spike declining), not aftermath state (post-cascade, spike ended). This mismatch blocks the hypothesis test.

**Final Verdict:** BLOCKED_BY_INFRASTRUCTURE - regime definition mismatch prevents hypothesis testing. Close without iteration per fast-failure discipline.

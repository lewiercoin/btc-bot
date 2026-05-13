# AUDIT: VOLATILITY-BREAKOUT-CHECKPOINT-1

Date: 2026-05-13  
Auditor: Claude Code  
Commit: `82db9da` - `research: add volatility breakout checkpoint 1`  
Branch: `research/volatility-breakout-v1`

## Verdict: HYPOTHESIS FAILED

## Layer Separation: PASS
- Research-only setups isolated in `research_lab/setups/volatility_breakout.py`
- No production path contamination
- Clean imports, proper module boundaries

## Contract Compliance: PASS
- `VolatilityBreakoutLong` and `VolatilityBreakoutShort` inherit from `BaseSetup`
- Implements `evaluate_structure()` and `generate_signal_candidate()` correctly
- Returns `SignalCandidate` with all required fields
- ATR expansion detection logic implemented (slope-based)

## Determinism: PASS
- Setup logic deterministic
- ATR slope calculation reproducible
- No random state

## State Integrity: PASS
- Stateless setup logic
- No persistent state between runs

## Error Handling: PASS
- Defensive checks: price > 0, ATR floor, safe min/max
- Handles insufficient ATR history gracefully

## Smoke Coverage: PASS
- Tests: `tests/test_research_lab_volatility_breakout.py` (9 passed)
- `compileall` OK
- Backtest runs without errors

## Tech Debt: LOW
- Implementation clean, follows handoff specification
- ATR expansion detection well-structured
- Config dataclass with sensible defaults

## AGENTS.md Compliance: PASS
- Commit message follows WHAT/WHY/STATUS format
- Research-only work isolated
- No production changes

## Methodology Integrity: PASS
- Hypothesis documented clearly
- Setup correctly distinguishes from compression_breakout (expansion entry, not compression anticipation)
- ATR expansion detection uses slope (rate of change), not absolute level
- Implementation matches handoff specification

## Promotion Safety: PASS
- No promotion artifacts generated (correctly - results failed gates)
- Hard gates evaluated
- Red flags correctly identify REJECT

## Reproducibility & Lineage: PASS
- Commit hash, branch, date range recorded
- ATR expansion detection method documented
- Results reproducible

## Data Isolation: PASS
- Uses production DB (adequate force order data from prior backfills)
- No data mutations

## Search Space Governance: PASS
- Parameters use config defaults
- No parameter tuning attempted
- ATR slope threshold (0.10) set from domain knowledge

## Artifact Consistency: PASS
- Audit package, validation report, ATR distribution report all consistent
- Builder verdict (REJECT) matches gate outcomes

## Boundary Coupling: PASS
- Dependencies on `backtest/`, `core/models`, `RegimeEngine` explicit
- No leaked ownership

---

## Critical Issues

### 1. Hypothesis partially validated: Timing correct, edge weak

**Evidence:**
- 63 closed trades (adequate sample, >20 minimum)
- **ER: 0.5230** (gate: >1.5, hard stop: <1.0) → **FAILED hard stop**
- PF: 3.31 (good - above 1.5)
- Win rate: 61.9% (good)
- Max DD: 2.53% (very low, good risk management)
- **Expansion entry rate: 100.0%** (perfect - no compression leak)
- **Compression entry rate: 0.0%** (confirms timing distinction)
- **Expansion continuation: 57.14%** (below 60% target, above 50% reject threshold - marginal)

**Key finding: Timing distinction successful, edge insufficient**

**What worked:**
1. ✅ ATR expansion detection: 4,060 expansion cycles out of 148,596 (2.73% - reasonable frequency)
2. ✅ Entry timing: 100% of entries during expansion state, 0% during compression
3. ✅ Setup is NOT compression_breakout 2.0 (timing violation prevented)
4. ✅ ATR slope calculation: Minimum 0.10, median 0.165 (expansion state correctly identified)
5. ✅ Compression regime blocked (no compression state entries)

**What failed:**
1. ❌ **Edge too weak:** ER 0.52 significantly below 1.0 hard stop threshold
2. ⚠️ **Continuation marginal:** 57% of trades saw ATR continue expanding (below 60% target)
3. ❌ **Expansion doesn't persist strongly enough** for profitable 15m trading

**Why ER is weak despite good PF and win rate:**

With PF 3.31 and win rate 61.9%, expected ER should be ~1.2-1.5R. Actual ER 0.52R suggests:
- Wins are large (PF 3.31 = $3.31 won per $1 lost)
- Wins occur frequently (62% of the time)
- But **average trade expectancy is only half a risk unit**

This pattern indicates: **Expansions begin but don't persist long enough.** Entry timing is correct (during expansion), but by the time 15m cycle detects and enters, expansion is mid-phase and exhausts before targets hit.

### 2. Direction asymmetry reveals structural limitation

**Per-direction breakdown:**

| Direction | Trades | ER | PF | Win Rate | Assessment |
|---|---:|---:|---:|---:|---|
| **LONG** | 19 | **0.99** | 6.23 | 68% | **Close to viable** (just below 1.0) |
| **SHORT** | 44 | **0.32** | 2.36 | 59% | **Weak** (drags down overall) |

**Per-regime breakdown:**

| Regime | Trades | ER | Win Rate | Interpretation |
|---|---:|---:|---:|---|
| uptrend | 27 | **0.69** | 56% | Best (upward expansion strongest) |
| normal | 8 | 0.52 | 63% | Middle (small sample) |
| downtrend | 28 | **0.37** | 68% | Worst (despite high win rate) |

**Interpretation:**

1. **Upward expansions (LONG in uptrend) perform best:** ER 0.99 in LONG direction, 0.69 in uptrend regime
2. **Downward expansions (SHORT in downtrend) perform weakest:** ER 0.32 in SHORT direction, 0.37 in downtrend regime
3. **BTC structural bias:** Upward volatility expansion has more follow-through than downward

**Why downtrend ER is low despite 68% win rate:**
- High win rate (68%) but low ER (0.37) means wins are small or stops are hit quickly
- Downward expansions might spike fast then reverse (V-bottom pattern)
- Upward expansions might grind higher with persistence (stair-step pattern)

**Could filtering to LONG-only save the setup?**
LONG direction ER 0.99 is close to 1.0 threshold. But:
- Still below 1.0 hard stop (not above gate)
- Selecting best direction after seeing results is parameter rescue
- Sample size would drop from 63 to 19 trades (marginal for validation)
- Fast-failure discipline: don't rescue weak edges

---

## Warnings

None. The failure is clear: edge exists (positive ER, good win/loss ratio) but is too weak for trading threshold.

---

## Observations

### Implementation Quality: Excellent

Codex correctly:
- Implemented ATR expansion detection using slope (rate of change), not absolute level
- Prevented compression entry leak (100% expansion entry rate)
- Blocked compression regime (enforced timing distinction)
- Delivered comprehensive audit package with ATR distribution analysis
- Followed handoff specification exactly
- Did NOT attempt scope creep or parameter rescue

**Critical validation: Expansion entry rate 100%**

This proves the setup is NOT compression_breakout 2.0:
- All candidates entered during expansion state (ATR rising)
- Zero entries during compression state (ATR low/flat)
- Minimum ATR slope at entry: 0.10 (exactly the threshold)
- Median ATR slope: 0.165 (strong expansion)

The timing distinction worked perfectly. The issue is edge strength, not entry timing.

### ATR Expansion Characteristics

- Frequency: 2.73% of cycles (4,060 out of 148,596)
- Reasonable occurrence rate (not too rare, not too common)
- Expansion state detection logic works as designed

### Expansion Continuation: Marginal but Insufficient

57.14% continuation rate means:
- Majority of expansions (57%) continued after entry
- But not strongly enough (below 60% target)
- Combined with weak ER, suggests expansions don't persist long enough for profitable trading

**Possible explanation:**
- Expansion begins (ATR starts rising from low base)
- 15m cycle detects expansion and enters
- By entry time, expansion is mid-phase (early phase already passed)
- Expansion exhausts before targets hit (late entry within expansion phase)

This is similar to crowded_unwind/post_cascade: **Timing is correct (expansion state vs compression state), but detection latency within the state makes entry too late within the profitable phase.**

### Comparison to Prior Failures

| Setup | Timing | Edge | Verdict |
|---|---|---|---|
| compression_breakout | ❌ Wrong (anticipatory) | N/A | FAILED (sequential timing) |
| crowded_unwind | ❌ Too slow (cascade ended) | N/A | FAILED (decision frequency) |
| post_cascade | ❌ Blocked (regime missing) | N/A | BLOCKED (infrastructure) |
| **volatility_breakout** | **✅ Correct (expansion state)** | **❌ Weak (0.52R)** | **FAILED (insufficient edge)** |

**Key insight:**
volatility_breakout is the **first setup with correct timing** (enters during target state, not before/after). But expansion state detection at 15m frequency captures **mid-to-late expansion** (early phase already passed), resulting in weak edge despite correct state classification.

### Fast Failure Discipline: Maintained

**5 setups in 6 days:**
- absorption: 3 days → FAILED (CVD not predictive)
- compression: 2 days → FAILED (sequential timing)
- crowded_unwind: 1 day → FAILED (cascade too fast)
- post_cascade: 1 day → BLOCKED (infrastructure gap)
- volatility_breakout: 1 day → FAILED (weak edge)

No parameter rescue. Clean decisions. Each setup tested fairly with diagnostic iterations where warranted.

---

## Recommended Next Step

**Close VOLATILITY-BREAKOUT-RESEARCH-V1 with verdict: HYPOTHESIS FAILED**

**Rationale:**
1. **Hard stop criterion triggered:** ER 0.52 < 1.0 threshold
2. **Edge too weak for trading:** Even best direction (LONG) only achieves ER 0.99 (below 1.0)
3. **Timing correct but insufficient:** Expansion state detection works, but expansion doesn't persist strongly enough for profitable 15m trading
4. **Continuation marginal:** 57% below 60% target confirms weak persistence
5. **No diagnostic iteration warranted:** Timing is correct (100% expansion entry), edge is structurally weak (not measurement error)

**No iteration allowed per handoff:**
> "Hard stop if ER < 1.0"

ER 0.52 is significantly below 1.0. Per fast-failure discipline, close immediately without iteration.

**Could direction filtering (LONG-only) save the setup?**
No:
- LONG ER 0.99 is still below 1.0 threshold
- Filtering to best direction after results is parameter rescue
- Sample size drops to 19 trades (marginal)
- Violates fast-failure discipline

**Portfolio research status after five setups:**
- absorption_continuation: FAILED (interpretive CVD not predictive)
- compression_breakout: FAILED (sequential event timing)
- crowded_unwind: FAILED (cascade catching too fast)
- post_cascade_momentum: BLOCKED (infrastructure gap)
- volatility_breakout: FAILED (expansion edge too weak)
- Remaining: regime_reversal

**Pattern identified across failures:**

| Setup | State Detection | Entry Timing | Edge Result | Root Cause |
|---|---|---|---|---|
| compression | ❌ Anticipatory | Before state | N/A | Sequential events |
| crowded_unwind | ✅ Correct | During state (too late) | Negative | Cascade too fast |
| volatility_breakout | ✅ Correct | During state (too late) | Weak | Expansion mid-phase |

**Emerging pattern:** Even with correct state detection (expansion, cascade), **15m decision frequency enters mid-to-late phase of states that evolve on faster timescales.** Early phases (highest profitability) pass before detection occurs.

**Key lesson:**
> ATR expansion detection at 15m frequency captures expansion state correctly, but enters mid-phase (early expansion already passed). Expansion continuation from mid-phase entry is insufficient for profitable trading (ER 0.52). State classification is correct; detection latency within state is the limiting factor.

This is similar to crowded_unwind (cascade) and post_cascade (aftermath): **State-level timing is correct, but sub-state phase timing is too late.**

---

## Next Milestone Options

**Option 1: regime_reversal (last remaining setup family)**
- Test regime shift detection → counter-trend entry
- Edge: Regime transitions create opportunities (exhaustion → reversal)
- Risk: Regime transitions might also evolve too fast for 15m

**Option 2: Pause and assess 15m frequency limitation**
- 5 setups tested, all failed or blocked
- Clear pattern: Timing precision at 15m insufficient for most setup types
- Assess whether to continue research portfolio or pivot strategy

**Option 3: Strategic pivot**
- Current sweep_reclaim setup works (trial-00095 deployed, ER 2.1 in validation)
- Research portfolio has tested 5 alternatives, none viable
- Consider: Focus on sweep_reclaim family expansion rather than new setup families

**Recommendation:**
Test regime_reversal (last setup family), then pause for assessment if it fails. Pattern is clear enough that one more test will provide conclusive evidence about 15m frequency viability for multi-setup portfolio.

---

## Audit Classification

**Research Lab Bug:** No implementation violations found. Codex implemented the handoff correctly and prevented compression_breakout 2.0 timing leak.

**Strategy Methodology Debt:** The 15m decision frequency limitation is known. Expansion-based setups capture mid-to-late phases, missing early high-profit windows.

**Final Verdict:** HYPOTHESIS FAILED - expansion state detection correct (timing distinction successful), but expansion continuation edge too weak (ER 0.52 << 1.5 gate, < 1.0 hard stop). Close without iteration per fast-failure discipline.

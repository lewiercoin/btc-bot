# CLAUDE HANDOFF → CODEX

## Checkpoint

- **Last commit:** (on main branch, will create new branch)
- **Branch:** Create new branch `research/crowded-unwind-v1` from `main`
- **Working tree:** Clean start for new setup family
- **Prior setup status:** 
  - absorption_continuation: FAILED (CVD not predictive)
  - compression_breakout: FAILED (sequential timing incompatibility)

## Before You Code

Read these files (mandatory):
1. `docs/BLUEPRINT_RESEARCH_LAB.md` - research lab architecture and workflow
2. `AGENTS.md` - discipline + your workflow rules
3. `docs/MILESTONE_TRACKER.md` - current status + lessons from absorption/compression failures
4. `docs/analysis/STRATEGIC_SETUP_PORTFOLIO_CONSULTATION_2026-05-12.md` - setup portfolio strategy (crowded_unwind is Setup #4)

## Milestone: CROWDED-UNWIND-RESEARCH-V1

**Type:** Research-only setup validation (Phase 2, Setup Family #4)

**Timeline:** 1-2 weeks

**Hypothesis:** Funding rate extremes + OI peaks + force order spikes indicate unsustainable crowded leverage → enter opposite direction to catch forced unwind/liquidation cascade.

---

## Why This Setup is Different (Lessons Applied)

### What Failed: absorption_continuation

- **Structure:** Trend pullback + CVD absorption
- **Why it failed:** CVD divergence not predictive (24% hit rate, ER -0.48)
- **Lesson:** **Interpretive signals (CVD) don't work** - need objective metrics

### What Failed: compression_breakout

- **Structure:** Volatility compression → breakout trigger
- **Why it failed:** Compression/breakout are sequential, not concurrent (ER -0.30, 97% blocked by no_breakout)
- **Lesson:** **Sequential events don't work** - entry trigger and edge thesis must coincide temporally

### What We're Testing: crowded_unwind

- **Structure:** Funding/OI extremes (crowding) → force order spike (unwind beginning) → reversal/retracement
- **Why it's different:**
  - **Objective metrics:** Funding rate, OI levels, force order rate (NOT interpretive like CVD)
  - **Concurrent events:** Crowding and unwind happen TOGETHER (funding extreme + force spike = unwind starting NOW)
  - **Proven edge:** Liquidation cascades are real, measurable, documented phenomena in crypto
  - **Clear counterparty:** Overleveraged longs (funding >p95) forced to close/liquidate
- **Data dependency:** Funding (8h, SMAs, percentiles), OI (value, Z-score, delta), force orders (rate, spike), TFI (directional confirmation)

**This is a fundamentally different hypothesis from absorption/compression.**

---

## Market Structure Hypothesis

### Setup Identity

**Name:** `crowded_unwind_long` (enter long when crowded shorts unwind) and `crowded_unwind_short` (enter short when crowded longs unwind)

**Regime target:** `crowded_leverage` (primary), with veto for other conditions

**Counterparty:**
- **For long entries:** Crowded shorts (funding rate very negative) forced to cover when cascade begins
- **For short entries:** Crowded longs (funding rate very positive) forced to close/liquidate when leverage breaks

**Edge timing:**
- Enter WHEN force order spike begins (unwind starting NOW)
- NOT before crowding (too early)
- NOT after unwind complete (too late)
- Entry = early phase of forced liquidation cascade

### Participant Behavior Model

**Who is trapped / forced:**

1. **Overleveraged traders (long side example):**
   - Funding rate > p95 (e.g., >0.08% / 8h = 36% APR annualized)
   - OI at elevated levels (Z-score >2.0)
   - Position becomes unsustainable (funding costs + adverse price move)
   - Forced to close OR liquidated

2. **Late momentum chasers:**
   - Enter after move is extended
   - Add to already-crowded side
   - Get caught when reversal/retracement begins

3. **Liquidation cascade mechanics:**
   - Initial liquidations → price moves against crowded side
   - More positions hit liquidation threshold
   - Cascade feeds on itself (forced selling begets more forced selling)
   - Creates sharp, tradeable retracements

**Structural components:**

1. **Crowding phase (setup):**
   - Funding rate at extreme (p95 or p99)
   - OI elevated (Z-score >2.0)
   - TFI may be one-sided
   - Position is CROWDED but not yet unwinding

2. **Unwind trigger (entry):**
   - Force order rate spikes (>threshold, e.g., p90 of force_order_rate_60s)
   - Price begins to move against crowded side
   - Early phase of liquidation cascade
   - TFI may flip (directional shift as unwind accelerates)

3. **Cascade phase (follow-through):**
   - Forced liquidations continue
   - Price retraces against prior move
   - Unwind completes when funding normalizes OR OI drops significantly

4. **Invalidation:**
   - Force spike was false alarm (no sustained unwind)
   - Crowding re-intensifies (funding goes more extreme)
   - Stop out

---

## Required Data / Proxies

### Crowding Detection

1. **Funding rate extremes:**
   - `funding_8h` > p95 threshold (long crowding) OR < p5 threshold (short crowding)
   - `funding_sma_24h`, `funding_sma_72h` for trend confirmation
   - Percentiles from empirical distribution (2022-2026)
   - Example thresholds: p95 ≈ 0.0008-0.001 for long crowding

2. **OI extremes:**
   - `oi_zscore_60d` > 2.0 (elevated open interest)
   - `oi_delta_pct` trend (OI building up)
   - OI at local peaks indicates accumulated positioning

3. **Directional flow:**
   - `tfi_60s` heavily one-sided (confirms crowded direction)
   - Example: TFI >0.6 for long crowding, TFI <-0.6 for short crowding

### Unwind Trigger

1. **Force order spike:**
   - `force_order_rate_60s` > spike threshold (e.g., p90 of historical distribution)
   - `force_order_spike` boolean (already calculated in features)
   - Indicates liquidations beginning

2. **Price action:**
   - Price moving against crowded side
   - For long crowding (funding >p95): price starts dropping
   - For short crowding (funding <p5): price starts rising

3. **TFI flip (confirmation):**
   - TFI begins shifting opposite to crowded direction
   - For long crowding: TFI was >0.5, now dropping or flipping negative
   - Confirms directional shift as unwind accelerates

### Invalidation / Veto

1. **No force spike:**
   - Crowding present but no liquidation trigger → wait

2. **Funding normalizing:**
   - Funding already returned to normal range → unwind may be over

3. **Volatility panic:**
   - ATR_4h_norm > p95 (0.02885372 from empirical analysis)
   - General market chaos, not clean crowding unwind

4. **Regime veto:**
   - May want to veto during other special regimes (e.g., post_liquidation already active)

---

## Deliverables

### 1. Crowded Unwind Setup Implementation

**File:** `research_lab/setups/crowded_unwind.py`

**Classes:**
- `CrowdedUnwindLong` (enter long when crowded shorts forced to cover)
- `CrowdedUnwindShort` (enter short when crowded longs forced to liquidate)

**Methods:**
- `get_setup_type() -> str` → `"crowded_unwind_long"` or `"crowded_unwind_short"`
- `check_regime_allowed(regime) -> bool` → Allow crowded_leverage, maybe normal; block others
- `evaluate_structure(...) -> dict` → filters, metrics, confluence
- `generate_signal_candidate(...) -> SignalCandidate | None` → entry construction

**Structure filters (Long example):**

1. **Crowding detection (short crowding for long entry):**
   - `funding_8h` < funding_short_crowding_threshold (e.g., p5 = very negative)
   - OR `funding_sma_24h` < threshold (sustained negative funding)
   - `oi_zscore_60d` > oi_elevated_threshold (e.g., 1.5 or 2.0)
   - Optional: `tfi_60s` < -0.5 (heavy short-side flow)

2. **Unwind trigger:**
   - `force_order_spike` = True (liquidations beginning)
   - `force_order_rate_60s` > force_spike_threshold (e.g., p90)
   - Price action: recent price drop (for short crowding → reversal up expected)

3. **Confirmation:**
   - `tfi_60s` beginning to flip (was negative, now rising toward positive)
   - OR OI_delta_pct negative (OI unwinding)

4. **Veto conditions:**
   - `atr_4h_norm` > volatility_panic_threshold (0.02885372)
   - Funding already normalized (crowding dissipated)
   - Regime blocked (if not allowing current regime)

**Entry construction (Long example):**

```python
entry_price = current_price  # Enter at unwind trigger
stop_loss = recent_low - invalidation_offset_atr * atr_15m  # Below recent swing
initial_target = entry + (entry - stop) * rr_ratio  # e.g., 2.0-2.5 RR
```

**Confluence scoring:**

```python
score = 0.0
score += 2.0  # Base: crowding + unwind trigger
if funding_extreme_percentile < p5 or > p95: score += 1.5  # Very extreme crowding
if force_order_rate > p95: score += 1.0  # Strong liquidation spike
if oi_zscore > 2.5: score += 1.0  # Very elevated OI
if tfi_flip_detected: score += 1.0  # Directional shift confirmation
if funding_sma_trend confirms: score += 0.5  # Sustained crowding
if rr_ratio >= 2.5: score += 1.0  # Good risk-reward
# Min confluence: e.g., 5.0
```

**Reasons taxonomy:**

```python
reasons = [
    f"setup_type=crowded_unwind_long",  # or _short
    f"regime={regime}",
    f"funding_8h={funding_8h:.6f}",
    f"funding_percentile={funding_pct:.3f}",
    f"funding_sma_24h={funding_sma_24h:.6f}",
    f"oi_zscore_60d={oi_zscore:.3f}",
    f"oi_delta_pct={oi_delta_pct:.6f}",
    f"force_order_spike={force_order_spike}",
    f"force_order_rate_60s={force_order_rate:.4f}",
    f"tfi_60s={tfi_60s:.4f}",
    f"tfi_flip_detected={tfi_flip}",
    f"price={price:.2f}",
    f"atr_4h_norm={atr_4h_norm:.6f}",
    f"rr_ratio={rr:.2f}",
    f"confluence_score={score:.2f}",
]
```

**Rejection reasons (examples):**

```python
"regime_blocked:uptrend"  # Wrong regime
"funding_not_extreme"  # Funding not at p5/p95
"oi_not_elevated"  # OI Z-score < threshold
"no_force_spike"  # No liquidation trigger
"force_rate_below_threshold"  # Spike not strong enough
"tfi_not_confirming"  # No directional shift
"funding_already_normalized"  # Unwind may be over
"volatility_panic"  # ATR norm > p95
"rr_below_minimum"  # RR < 2.0
"confluence_too_low"  # Score < min threshold
```

---

### 2. Backtest Runner

**File:** `research_lab/backtest_crowded_unwind.py`

**Purpose:** Replay crowded_unwind (both long and short) over full date range, collect metrics

**Command:**
```bash
python research_lab/backtest_crowded_unwind.py \
  --start-date 2022-01-01 \
  --end-date 2026-03-29 \
  --output-dir research_lab/reports/
```

**Outputs:**
- `crowded_unwind_validation_report.md` - metrics summary
- `crowded_gate_results.json` - rejection funnel
- Trade list with reasons[] for each candidate

**Metrics to collect:**
- Full-range: ER, PF, DD, trades, Sharpe, win rate
- Per-direction: long entries vs short entries
- Per-regime: crowded_leverage vs others
- Liquidation capture rate: % of force spikes that led to profitable unwind trades
- Average unwind duration (how long from entry to TP/SL)

---

### 3. Per-Regime Breakdown

**File:** `research_lab/analyze_crowded_by_regime.py`

**Purpose:** Understand which regime crowded_unwind has edge

**Output:** `research_lab/reports/crowded_by_regime.md`

**Analysis:**

| Regime | Candidates | Trades | ER | PF | Win Rate | Assessment |
|---|---:|---:|---:|---:|---:|---|
| `crowded_leverage` | X | Y | A.AA | B.BB | CC% | Target regime |
| `normal` | X | Y | A.AA | B.BB | CC% | Secondary |
| `uptrend` | X | Y | A.AA | B.BB | CC% | Should be blocked/minimal |
| `downtrend` | X | Y | A.AA | B.BB | CC% | Should be blocked/minimal |

**Goal:**
- ER > 1.5 in `crowded_leverage` regime (primary)
- Minimal trades in uptrend/downtrend (setup should focus on crowding, not general trends)

---

### 4. Overlap Analysis

**File:** `research_lab/analyze_crowded_overlap.py`

**Purpose:** Measure overlap vs existing setups

**Comparisons:**

1. **vs sweep_reclaim (active baseline):**
   - How many trades would conflict?
   - Portfolio overlap rate (< 30% gate)
   - Regime distribution differences

2. **vs absorption_continuation (failed, for learning):**
   - Compare to show crowded_unwind is NOT just absorption retry

3. **vs compression_breakout (failed, for learning):**
   - Compare to show crowded_unwind is different structure

**Output:** `research_lab/reports/crowded_overlap_analysis.md`

**Metrics:**
- Overlap rate: `overlap_trades / total_trades`
- Correlation: Daily PnL correlation between setups
- Regime divergence: Which regime each setup dominates

**Gate:** Overlap rate < 30% vs sweep_reclaim (hard gate)

---

### 5. Liquidation Capture Analysis

**File:** `research_lab/analyze_liquidation_capture.py`

**Purpose:** Validate liquidation cascade hypothesis

**Output:** `research_lab/reports/liquidation_capture.md`

**Metrics:**

1. **Liquidation capture rate:**
   - How many force spikes led to profitable trades?
   - How many force spikes were false alarms?
   - Target: > 50% capture rate

2. **Crowding quality:**
   - Win rate when funding > p95 vs p90-p95
   - Win rate when OI Z-score > 2.5 vs 2.0-2.5
   - Feature cohort: winners vs losers

3. **TFI flip confirmation:**
   - Win rate when TFI flip detected vs not detected
   - Validate TFI as confirmation filter

---

### 6. Walk-Forward Validation

**File:** `research_lab/validate_crowded_walkforward.py`

**Purpose:** Test OOS stability (same protocol as absorption/compression)

**Windows:**
- Window 0: Train 2022-2024, validate 2024
- Window 1: Train 2022-2024, validate 2025

**Command:**
```bash
python research_lab/validate_crowded_walkforward.py \
  --output-dir research_lab/reports/
```

**Output:** `research_lab/reports/crowded_walkforward.json`

**Hard gates:**
- 2/2 windows passed (ER > threshold in both validation periods)
- Not fragile (ER degradation < fragility threshold)
- Min trades per window >= 15
- No blocking safety flags

---

### 7. Crowded Unwind Audit Package

**File:** `research_lab/reports/CROWDED_UNWIND_AUDIT_PACKAGE.md`

**Purpose:** Summary report for Claude Code audit

**Structure:**

```markdown
# Crowded Unwind Audit Package

Milestone: CROWDED-UNWIND-RESEARCH-V1
Builder: Codex
Branch: research/crowded-unwind-v1
Verdict: [CANDIDATE / ITERATE / REJECT]

## Executive Summary
- Full-range metrics: ER, PF, DD, trades, Sharpe
- Crowded_leverage regime ER: X.XX
- Liquidation capture rate: XX%
- Overlap vs sweep_reclaim: XX%
- WF validation: 2/2 pass [yes/no]

## Hard Gate Results
| Gate | Requirement | Actual | Result |
|---|---|---|---|
| Crowded_leverage ER | > 1.5 | X.XX | PASS/FAIL |
| Liquidation capture | >= 50% | XX% | PASS/FAIL |
| Overlap vs sweep_reclaim | < 30% | XX% | PASS/FAIL |
| Min trades | >= 20 | X | PASS/FAIL |
| WF 2/2 pass | Yes | Yes/No | PASS/FAIL |
| Safety flags | None blocking | [list] | PASS/FAIL |

## Red Flags
[List any issues]

## Recommendation
[REJECT / ITERATE / CANDIDATE FOR PHASE 2.5]
```

**Hard gates (crowded_unwind specific):**

1. **Crowded_leverage regime ER > 1.5** (primary target regime)
2. **Liquidation capture rate >= 50%** (confirms unwind thesis)
3. **Overlap vs sweep_reclaim < 30%** (portfolio diversification)
4. **Min trades >= 20** (statistical validity)
5. **WF 2/2 pass** (OOS stability)
6. **No blocking safety flags** (pnl_sanity, etc.)

**Red flags:**

- PF > 6.0 (overfitting suspect)
- ER > 5.0 (too good to be true)
- Win rate < 35% or > 70% (unrealistic)
- Liquidation capture < 40% (thesis not validated)
- Overlap > 40% (too similar to sweep_reclaim)
- OOS outperformance in WF (suspicious)
- Low OOS trade count (< 15 per window)

---

### 8. Test Suite

**File:** `tests/test_research_lab_crowded_unwind.py`

**Coverage:**

1. `test_crowded_unwind_long_generates_explained_candidate`
   - Happy path: short crowding (negative funding) + force spike + TFI flip → long candidate
   - Reasons[] complete and specific

2. `test_crowded_unwind_short_generates_explained_candidate`
   - Happy path: long crowding (positive funding) + force spike + TFI flip → short candidate

3. `test_crowded_unwind_blocks_wrong_regime`
   - Blocks regimes that shouldn't have crowded_unwind activation

4. `test_crowded_unwind_requires_force_spike`
   - Rejects if crowding present but no force spike (no liquidation trigger)

5. `test_crowded_unwind_requires_extreme_funding`
   - Rejects if funding not at p5/p95 extremes

6. `test_crowded_unwind_requires_elevated_oi`
   - Rejects if OI Z-score not elevated (no accumulated positioning)

7. `test_crowded_unwind_blocks_volatility_panic`
   - Uses empirical volatility threshold (0.02885372 from absorption/compression)

8. `test_crowded_unwind_not_absorption_retry`
   - Ensures setup doesn't use CVD divergence logic

9. `test_crowded_unwind_not_compression_retry`
   - Ensures setup doesn't require compression + breakout simultaneously

10. `test_overlap_analysis_strict_portfolio_thresholds`
    - Overlap calculation correct (< 30% gate)

11. `test_liquidation_capture_validator`
    - Capture rate calculation correct

12. `test_gate_evaluator_blocks_missing_crowded_validation`
    - Blocks if crowded_leverage regime results missing
    - Blocks if liquidation capture not measured

13. `test_gate_evaluator_rejects_high_overlap_with_sweep_reclaim`
    - Hard gate: overlap > 30% → reject

**Target:** All tests pass before push

---

### 9. Hypothesis Document

**File:** `research_lab/research/CROWDED_UNWIND_HYPOTHESIS.md`

**Content:**

```markdown
# Crowded Unwind Hypothesis

## Market Structure

Funding rate extremes + OI peaks indicate unsustainable crowded leverage. Force order spikes signal liquidation cascade beginning. Enter opposite crowded direction to catch forced unwind.

## Edge

- Counterparty: Overleveraged traders forced to close/liquidate
- Timing: Enter WHEN force spike begins (concurrent with unwind starting)
- Structure: Objective metrics (funding, OI, force orders - NOT interpretive like CVD)
- Events: Concurrent (crowding + unwind happen together, NOT sequential like compression/breakout)

## Why This is NOT absorption_continuation

- absorption: CVD divergence (interpretive, FAILED - not predictive)
- crowded_unwind: Force order spike (objective, measurable)

## Why This is NOT compression_breakout

- compression: Compression + breakout (sequential events, FAILED - timing incompatible)
- crowded_unwind: Crowding + unwind (concurrent events, happening together)

## Required Signals

1. Funding rate at extreme (p5 for short crowding, p95 for long crowding)
2. OI elevated (Z-score >2.0, accumulated positioning)
3. Force order spike (liquidations beginning NOW)
4. TFI flip (directional shift confirmation)

## Invalidation

- Force spike false alarm (no sustained unwind)
- Funding normalizes (crowding dissipates before unwind)
- Volatility panic (general chaos, not clean crowding unwind)

## Target Regimes

- Primary: `crowded_leverage`
- Allow: maybe `normal` if crowding metrics present
- Block: `uptrend`, `downtrend` (separate setups)
```

---

### 10. Milestone Tracker Update

**File:** `docs/MILESTONE_TRACKER.md`

**Add section:**

```markdown
## Current Active Milestone: CROWDED-UNWIND-RESEARCH-V1

**Status:** RESEARCH_ACTIVE  
**Builder:** Codex  
**Decision date:** 2026-05-12  
**Branch:** `research/crowded-unwind-v1`  
**Handoff:** `docs/handoffs/HANDOFF_CROWDED_UNWIND_RESEARCH_V1_2026-05-12.md`

**Scope:** Research-only validation of crowded_unwind (long and short) setup.

**Hypothesis:** Funding/OI extremes + force spike → enter opposite direction for forced unwind.

**Target regimes:** `crowded_leverage` (primary)

**Timeline:** 1-2 weeks

**Success criteria:**
- Crowded_leverage ER > 1.5
- Liquidation capture >= 50%
- Overlap vs sweep_reclaim < 30%
- Min trades >= 20
- WF 2/2 pass
- No blocking safety flags

**Next:** Backtest validation → audit → decision (REJECT / ITERATE / CANDIDATE FOR PHASE 2.5)
```

---

## Hard Gates (Acceptance Criteria)

### Gate 1: Crowded_Leverage Regime Edge (CRITICAL)

**Requirement:** ER > 1.5 in `crowded_leverage` regime

**Why:** This is the target regime for forced liquidation captures.

**Measured from:** `crowded_by_regime.md` report

**Verdict:**
- ER > 1.5 → PASS
- ER 1.0-1.5 → MARGINAL
- ER < 1.0 → FAIL

---

### Gate 2: Liquidation Capture Rate (CRITICAL)

**Requirement:** >= 50% of force spikes led to profitable unwind trades

**Why:** Validates the liquidation cascade hypothesis. If most force spikes are false alarms, thesis is invalid.

**Measured from:** `liquidation_capture.md` report

**Verdict:**
- >= 50% → PASS
- 40-50% → MARGINAL
- < 40% → FAIL

---

### Gate 3: Portfolio Overlap (HARD)

**Requirement:** Overlap rate vs sweep_reclaim < 30%

**Why:** Crowded_unwind must offer diversification.

**Measured from:** `crowded_overlap_analysis.md` report

**Verdict:**
- < 30% → PASS
- 30-40% → MARGINAL
- > 40% → FAIL

---

### Gate 4: Statistical Validity (HARD)

**Requirement:** Total trades >= 20, min 15 per WF validation window

**Why:** Need sufficient sample for credible statistics.

**Measured from:** Full-range backtest + WF validation

**Verdict:**
- >= 20 total, >= 15 per WF window → PASS
- < 20 total OR < 15 in any window → FAIL

---

### Gate 5: Walk-Forward Stability (HARD)

**Requirement:** 2/2 windows passed, not fragile

**Why:** OOS validation, same protocol as absorption/compression.

**Measured from:** `crowded_walkforward.json`

**Verdict:**
- 2/2 pass, not fragile → PASS
- 1/2 pass OR fragile → MARGINAL
- 0/2 pass → FAIL

---

### Gate 6: Safety Flags (HARD)

**Requirement:** No blocking safety flags (pnl_sanity, etc.)

**Why:** Standard research lab quality gates.

**Measured from:** Backtest validation

**Verdict:**
- No blocking flags → PASS
- Yellow flags only → SCRUTINIZE
- Blocking flags → FAIL

---

## Red Flags (Disqualifying or High-Scrutiny)

| Red Flag | Meaning | Action |
|---|---|---|
| PF > 6.0 | Overfitting suspect | **SCRUTINIZE** |
| ER > 5.0 | Too good to be true | **SCRUTINIZE** |
| Win rate < 35% or > 70% | Unrealistic extremes | **SCRUTINIZE** |
| Liquidation capture < 40% | Thesis not validated | **REJECT** |
| Overlap > 40% | Too similar to sweep_reclaim | **REJECT** |
| OOS outperformance | Validation better than train | **SCRUTINIZE** |
| Low OOS trade count | < 15 in any WF window | **SCRUTINIZE** |
| pnl_sanity_review_required | Unrealistic PnL magnitude | **REJECT** |
| Negative crowded_leverage ER | No edge in target regime | **REJECT** |

---

## Rejection Criteria (STOP Conditions)

**REJECT hypothesis immediately if ANY of these after initial backtest:**

1. **Crowded_leverage regime ER < 0.5** → No edge in target regime
2. **Liquidation capture < 40%** → Thesis invalid (force spikes not predictive)
3. **Overlap > 40%** → No portfolio diversification
4. **Total trades < 20** → Insufficient sample
5. **Blocking safety flag present** → Quality issue

**MARGINAL (consider ONE diagnostic iteration) if:**

1. **Crowded_leverage ER 1.0-1.5** (weak edge, but positive)
2. **Liquidation capture 40-50%** (marginal validation)
3. **Overlap 30-40%** (high but not disqualifying)
4. **WF 1/2 pass** (OOS instability)

**CANDIDATE (proceed to Phase 2.5) if:**

1. **All hard gates PASS**
2. **No blocking red flags**
3. **Crowded_leverage ER > 1.5, liquidation capture >= 50%, overlap < 30%**

---

## No-Touch Areas (UNCHANGED)

Same as absorption/compression:

- `orchestrator.py`
- `core/signal_engine.py`
- `execution/**`
- `governance/**`
- `risk/**`
- `settings.py`
- `core/regime_engine.py` (production component)

**All work stays in:**
- `research_lab/setups/crowded_unwind.py` (new)
- `research_lab/backtest_crowded_unwind.py` (new)
- `research_lab/analyze_*.py` (new analysis scripts)
- `research_lab/reports/crowded_*.md` (new reports)
- `tests/test_research_lab_crowded_unwind.py` (new tests)
- `docs/**` (handoffs, audits, milestone tracker)

**Zero production changes until Phase 2.5 contracts exist.**

---

## Critical Reminders

### 1. This is NOT absorption_continuation_v2 or compression_breakout_v2

**Crowded_unwind is fundamentally different:**
- **NOT interpretive:** Funding, OI, force orders are objective (vs CVD divergence in absorption)
- **NOT sequential:** Crowding + unwind are concurrent (vs compression → breakout sequential)
- **Proven edge:** Liquidation cascades are documented phenomena in crypto
- **Clear counterparty:** Overleveraged traders forced to exit (vs vague "absorption" or "compression")

### 2. Apply Lessons from Absorption/Compression Failures

**Lesson 1 (absorption):** Interpretive signals (CVD divergence) don't work
- **Application:** Use ONLY objective metrics (funding rate numbers, OI Z-scores, force order counts)

**Lesson 2 (compression):** Sequential events don't work (compression → breakout)
- **Application:** Ensure crowding + unwind are CONCURRENT (force spike = unwind starting NOW, not "unwind will happen later")

**Lesson 3 (both):** Fast failure discipline works
- **Application:** ONE checkpoint, ONE diagnostic iteration if marginal, then hard stop

### 3. Liquidation Capture is the Key Metric

Unlike absorption (CVD hit rate) or compression (breakout follow-through), crowded_unwind's thesis validation metric is:

**Liquidation capture rate = (profitable force spike trades) / (total force spike triggers)**

If < 50%, hypothesis is invalid (force spikes are not predictive of tradeable unwinds).

### 4. Regime as Context, Not Strict Trigger

**Learning from compression:**
- RegimeEngine may not label `crowded_leverage` frequently
- Setup should have internal crowding detection (funding percentile, OI Z-score)
- Use regime as VETO (block wrong regimes), not strict trigger

### 5. Research-Only Until Phase 2.5

Same discipline:
- No production integration until Phase 2.5 contracts exist
- No `setup_type` field in production SignalCandidate yet
- No multi-setup dispatcher yet

**After validation:** If crowded_unwind passes gates, THEN build Phase 2.5 contracts (multi-setup architecture) before deploying any portfolio.

---

## Timeline (Target: 1-2 weeks)

| Step | Time | Deliverable |
|---|---|---|
| 1. Setup implementation (long + short) | 2-3 days | `crowded_unwind.py`, tests pass |
| 2. Backtest runner + reports | 1 day | Full-range metrics, rejection funnel |
| 3. Per-regime analysis | 0.5 day | Crowded_leverage vs others |
| 4. Overlap analysis | 0.5 day | vs sweep_reclaim, vs failed setups |
| 5. Liquidation capture analysis | 0.5 day | Capture rate, feature cohorts |
| 6. Walk-forward validation | 0.5 day | 2 windows, OOS stability |
| 7. Audit package | 0.5 day | Summary report, gate results |
| 8. Push + request audit | - | Commit, push, handoff to Claude |

**Total:** ~5-7 days (with buffer for iteration if needed)

---

## Expected Outcomes

### Scenario 1: SUCCESS (40-50% probability - HIGHER than absorption/compression)

**Why higher probability:**
- Liquidation cascades are proven phenomena (not unproven like CVD absorption)
- Objective metrics (not interpretive)
- Concurrent events (not sequential timing issue)

**Metrics after validation:**
- Crowded_leverage regime ER: 1.8-2.5
- Liquidation capture: 55-65%
- Overlap vs sweep_reclaim: 20-30%
- Total trades: 30-60
- WF: 2/2 pass

**Verdict:** CANDIDATE FOR PHASE 2.5

**Next:** Build multi-setup contracts, integrate crowded_unwind + sweep_reclaim into portfolio architecture.

---

### Scenario 2: MARGINAL (30% probability)

**Metrics:**
- Crowded_leverage ER: 1.0-1.5 (weak edge)
- Liquidation capture: 40-50% (marginal)
- Overlap: 30-40% (high)

**Verdict:** ITERATE (one diagnostic iteration, similar to absorption/compression)

**Potential fixes:**
- Tighter crowding thresholds (p99 instead of p95)
- Stricter force spike threshold
- Add TFI flip as required (not optional)

**Decision:** User approval required for iteration

---

### Scenario 3: FAILED (20-30% probability)

**Metrics:**
- Crowded_leverage ER < 0.5 OR total trades < 20
- Liquidation capture < 40%
- Overlap > 40%

**Verdict:** HYPOTHESIS FAILED

**Conclusion:** Even forced liquidations don't provide tradeable edge in BTC perps (surprising but possible).

**Next:** Pause portfolio research, reassess strategy, OR try different setup family (mean reversion extreme, post-liquidation recovery)

---

## Your First Response Must Contain

1. **Confirmed milestone scope** (crowded_unwind long+short research, zero production changes)
2. **Acceptance criteria clear** (crowded ER >1.5, capture >=50%, overlap <30%)
3. **Hypothesis understanding** (funding/OI extremes + force spike → concurrent unwind)
4. **Lessons applied** (objective metrics, concurrent events, fast failure)
5. **Data requirements** (funding percentiles, OI Z-score, force spike threshold, TFI flip)
6. **Implementation plan** (ordered steps, file structure, timeline)
7. **Only then: start coding**

---

## Commit Discipline

**Format:**
```
research: <what>

WHAT: <concise description of files/changes>
WHY: <hypothesis being tested, phase context>
RESULT: <metrics if validation complete, or "in progress">
STATUS: <checkpoint state>
```

**Example (after backtest):**
```
research: crowded unwind backtest validation

WHAT: Implement crowded_unwind (long+short) setups, backtest runner, per-regime analysis
WHY: Test crowded leverage → forced liquidation hypothesis (Phase 2, Setup #4 after absorption/compression FAILED)
RESULT: 42 trades, crowded ER 2.1, liquidation capture 58%, overlap 25%
STATUS: Validation complete, awaiting Claude audit
```

**Do NOT self-mark as "done". Claude Code audits after push.**

---

## Questions Before Starting?

**Expected:** Minimal - scope is clear, lessons from absorption/compression are incorporated

**If questions:**
- Funding percentile thresholds (p95 vs p99)? → Start with p95, document sensitivity
- Force spike threshold? → p90 of force_order_rate_60s is reasonable default
- TFI flip required or optional? → Start optional (confluence), can tighten if needed
- Both long AND short in first checkpoint? → Yes, test both directions (they're mirror logic)

---

## Start Implementation

Confirm scope, acceptance criteria, hypothesis understanding, and lessons applied in your first response.

Then proceed: setup implementation (long+short) → backtest → analysis → validation → audit package → push.

---

**Handoff complete. Branch `research/crowded-unwind-v1` ready for crowded_unwind research.**

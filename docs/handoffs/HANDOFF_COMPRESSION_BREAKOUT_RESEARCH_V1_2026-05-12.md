# CLAUDE HANDOFF → CODEX

## Checkpoint

- **Last commit:** `94f1495` - "audit: ABSORPTION-CONTINUATION-ITERATION-A — HYPOTHESIS FAILED"
- **Branch:** Create new branch `research/compression-breakout-v1` from `main`
- **Working tree:** Clean start for new setup family
- **Prior setup status:** absorption_continuation FAILED and archived

## Before You Code

Read these files (mandatory):
1. `docs/BLUEPRINT_RESEARCH_LAB.md` - research lab architecture and workflow
2. `AGENTS.md` - discipline + your workflow rules
3. `docs/MILESTONE_TRACKER.md` - current status + absorption closure
4. `docs/analysis/STRATEGIC_SETUP_PORTFOLIO_CONSULTATION_2026-05-12.md` - setup portfolio strategy (compression_breakout is Setup #3)

## Milestone: COMPRESSION-BREAKOUT-RESEARCH-V1

**Type:** Research-only setup validation (Phase 2, Setup Family #2)

**Timeline:** 1-2 weeks

**Hypothesis:** Volatility compression followed by directional breakout with volume/OI confirmation captures explosive moves that sweep-reclaim (range specialist) and absorption_continuation (pullback specialist, FAILED) cannot.

---

## Why This Setup is Different

### What Failed: absorption_continuation

- **Structure:** Trend pullback + CVD absorption
- **Entry trigger:** CVD divergence during pullback
- **Why it failed:** CVD absorption not predictive in BTC perps (24% hit rate, negative ER)
- **Data dependency:** CVD interpretation (subjective, unreliable)

### What We're Testing: compression_breakout

- **Structure:** Volatility compression → range contraction → explosive breakout
- **Entry trigger:** Breakout of consolidation + volume/TFI surge + directional OI
- **Why it's different:** 
  - Objective structure (ATR compression is measurable, not interpretive)
  - Clear invalidation (failed breakout = stop)
  - Different market regime (compression, not trend continuation)
  - Does NOT rely on CVD divergence
- **Data dependency:** ATR, range width, breakout level (objective metrics)

**This is a separate hypothesis, not a variant of absorption.**

---

## Market Structure Hypothesis

### Setup Identity

**Name:** `compression_breakout_long` (and `compression_breakout_short`)

**Regime target:** `compression` (primary), `range` (secondary)

**Counterparty:** 
- Range traders who fade the breakout (trapped when breakout holds)
- Late entries who chase after breakout already extended

**Edge timing:**
- Enter ON breakout confirmation (volume + TFI + OI surge)
- BEFORE breakout becomes obvious to retail (avoid chasing extended moves)

### Participant Behavior Model

**Who is trapped / forced:**

1. **Range faders (shorts on upside breakout):**
   - Sold into resistance thinking range will hold
   - Breakout invalidates their thesis → forced to cover
   - Their stops add fuel to breakout momentum

2. **Passive holders waiting for "confirmation":**
   - Wait for breakout to "prove itself" before entering
   - By the time they enter, first wave has already captured clean risk-reward
   - Our edge: enter at breakout, not after extension

3. **Algo mean-reversion systems:**
   - Trained on range behavior (fade extremes)
   - Compression → expansion transition breaks their assumptions
   - Get run over when volatility regime shifts

**Structural components:**

1. **Compression phase (setup):**
   - ATR at multi-day/week low
   - Price range contracts (lower highs, higher lows)
   - Volume often declines (coiling)
   - OI may build (participants accumulating positions)

2. **Breakout trigger (entry):**
   - Price breaks above resistance (long) or below support (short)
   - Volume/TFI surge (directional conviction)
   - OI increases (new participants, not just stops)
   - Breakout is decisive (not just a probe/fake)

3. **Expansion phase (follow-through):**
   - Volatility expands (ATR increases)
   - Directional momentum (not chop)
   - Failed breakout → invalidation → stop out

---

## Required Data / Proxies

### Compression Detection

1. **ATR compression:**
   - `atr_15m`, `atr_4h` vs recent history (e.g., 20-day rolling)
   - ATR percentile (e.g., p10 or p5 indicates tight compression)
   - Duration of compression (longer = more energy)

2. **Range width:**
   - High-low range over lookback (e.g., 48h, 7d)
   - Range width vs ATR (normalized)
   - Bollinger Band width (optional proxy)

3. **Price structure:**
   - Recent high/low levels (consolidation bounds)
   - Higher lows + lower highs = compression triangle
   - Equal highs/lows = consolidation box

### Breakout Confirmation

1. **Price action:**
   - Price > recent_high (long) or price < recent_low (short)
   - Breakout size: must exceed threshold (e.g., 0.5 ATR minimum)
   - Decisiveness: not just a wick, close beyond level

2. **Volume / Flow:**
   - TFI surge (e.g., TFI_60s > 0.4 for long breakout)
   - Volume spike (if available, else TFI proxy)
   - Directional buying/selling intensity

3. **OI / Participation:**
   - OI delta positive (new positions opening, not just stops)
   - OI not at exhaustion extreme (avoid blow-off tops)

4. **Funding / Crowd:**
   - Funding not at extreme (avoid crowded breakouts)
   - OI Z-score not at panic levels

### Invalidation / Veto

1. **Failed breakout:**
   - Price re-enters consolidation range quickly (e.g., within 1-2 bars)
   - Indicates false breakout / stop hunt

2. **Volatility panic:**
   - ATR norm > p95 (use same empirical threshold as absorption, 0.02885372)
   - Indicates liquidation cascade, not clean breakout

3. **Crowded leverage:**
   - Funding > 0.08% (too crowded long)
   - OI Z-score > 2.5 (exhaustion)

4. **Liquidation cascade:**
   - Force order spike active
   - Breakout is driven by stops, not conviction

---

## Deliverables

### 1. Compression Breakout Setup Implementation

**File:** `research_lab/setups/compression_breakout.py`

**Class:** `CompressionBreakoutLong` (inherits from `BaseSetup`)

**Methods:**
- `get_setup_type() -> str` → `"compression_breakout"`
- `check_regime_allowed(regime) -> bool` → `True` for `compression`, `range`; `False` for `uptrend`, `downtrend`
- `evaluate_structure(...) -> dict` → filters, metrics, confluence
- `generate_signal_candidate(...) -> SignalCandidate | None` → entry construction

**Structure filters:**

1. **Regime:**
   - `regime in ["compression", "range"]`
   - Block `uptrend`, `downtrend` (those are for other setups)

2. **Compression detection:**
   - ATR percentile < threshold (e.g., p20 or p10)
   - Range width < compression threshold (e.g., 1.5 * ATR_4h)
   - Duration of compression >= min_bars (e.g., 12-24 bars = 3-6 hours)

3. **Breakout trigger:**
   - Price > recent_high + breakout_offset_atr * ATR (long)
   - Breakout size >= min_breakout_atr (e.g., 0.5 ATR minimum)
   - Close beyond level (not just wick)

4. **Confirmation:**
   - TFI_60s > tfi_breakout_threshold (e.g., 0.4 for long)
   - OI_delta_pct > 0 (participation, not just stops)
   - Volume surge (proxy: TFI magnitude)

5. **Veto conditions:**
   - Funding > funding_extreme (e.g., 0.0008)
   - OI Z-score > oi_extreme_zscore (e.g., 2.5)
   - ATR_4h_norm > volatility_panic_atr_norm (0.02885372 from empirical distribution)
   - Force order spike active + rate > threshold
   - Failed breakout (price re-enters range within lookback)

**Entry construction:**

```python
entry_price = current_price  # Enter at breakout
stop_loss = consolidation_low - invalidation_offset_atr * atr_4h  # Below range
initial_target = entry + (entry - stop) * rr_ratio  # e.g., 2.0-3.0 RR
```

**Confluence scoring:**

```python
score = 0.0
score += 2.0  # Base: regime + setup identity
if atr_percentile < p10: score += 1.5  # Strong compression
if breakout_size > 1.0 * atr: score += 1.0  # Decisive breakout
if tfi_60s > 0.5: score += 1.0  # Strong directional flow
if oi_delta_pct > 0.001: score += 0.5  # Participation
if range_duration > 24: score += 0.5  # Long compression = more energy
if rr_ratio >= 2.5: score += 1.0  # Good risk-reward
# Min confluence: e.g., 5.0
```

**Reasons taxonomy:**

```python
reasons = [
    "setup_type=compression_breakout",
    "regime=compression",  # or "range"
    f"atr_percentile={atr_pct:.3f}",
    f"range_width_atr={range_width_atr:.3f}",
    f"compression_duration_bars={duration}",
    f"breakout_size_atr={breakout_size_atr:.3f}",
    f"recent_high={recent_high:.2f}",
    f"recent_low={recent_low:.2f}",
    f"price={price:.2f}",
    f"tfi_60s={tfi_60s:.4f}",
    f"oi_delta_pct={oi_delta_pct:.6f}",
    f"funding_8h={funding_8h:.6f}",
    f"oi_zscore_60d={oi_zscore:.3f}",
    f"atr_4h_norm={atr_4h_norm:.6f}",
    f"volatility_panic={atr_4h_norm > threshold}",
    f"rr_ratio={rr:.2f}",
    f"confluence_score={score:.2f}",
]
```

**Rejection reasons (examples):**

```python
"regime_blocked:uptrend"  # Wrong regime
"atr_not_compressed"  # ATR > compression threshold
"compression_duration_too_short"  # Not coiled enough
"no_breakout_detected"  # Price still in range
"breakout_too_small"  # Breakout < min threshold
"tfi_below_breakout_threshold"  # No directional flow
"oi_unwind_not_participation"  # OI delta negative
"funding_crowded_long"  # Funding extreme
"oi_crowded"  # OI Z-score > 2.5
"volatility_panic"  # ATR norm > p95
"liquidation_cascade_active"  # Force orders spiking
"failed_breakout_detected"  # Price re-entered range
"rr_below_minimum"  # RR < 2.0
"confluence_too_low"  # Score < min threshold
```

---

### 2. Backtest Runner

**File:** `research_lab/backtest_compression_breakout.py`

**Purpose:** Replay compression_breakout_long over full date range, collect metrics

**Command:**
```bash
python research_lab/backtest_compression_breakout.py \
  --start-date 2022-01-01 \
  --end-date 2026-03-29 \
  --output-dir research_lab/reports/
```

**Outputs:**
- `compression_breakout_validation_report.md` - metrics summary
- `compression_gate_results.json` - rejection funnel
- Trade list with reasons[] for each candidate

**Metrics to collect:**
- Full-range: ER, PF, DD, trades, Sharpe, win rate
- Per-regime: compression vs range vs uptrend vs downtrend
- Breakout confirmation hit rate (did breakout follow through?)
- Average compression duration before breakout
- Average breakout size (ATR-normalized)

---

### 3. Per-Regime Breakdown

**File:** `research_lab/analyze_compression_by_regime.py`

**Purpose:** Understand which regime compression_breakout has edge

**Output:** `research_lab/reports/compression_by_regime.md`

**Analysis:**

| Regime | Candidates | Trades | ER | PF | Win Rate | Assessment |
|---|---:|---:|---:|---:|---:|---|
| `compression` | X | Y | A.AA | B.BB | CC% | Target regime |
| `range` | X | Y | A.AA | B.BB | CC% | Secondary regime |
| `uptrend` | X | Y | A.AA | B.BB | CC% | Should be blocked |
| `downtrend` | X | Y | A.AA | B.BB | CC% | Should be blocked |

**Goal:** 
- ER > 1.5 in `compression` regime (primary)
- ER > 1.0 in `range` regime (acceptable secondary)
- ER near 0 or negative in `uptrend`/`downtrend` (confirms regime blocking works)

---

### 4. Overlap Analysis

**File:** `research_lab/analyze_compression_overlap.py`

**Purpose:** Measure overlap vs existing setups

**Comparisons:**

1. **vs sweep_reclaim (active baseline):**
   - How many trades would conflict? (both want entry on same bar)
   - Portfolio overlap rate (< 30% gate)
   - Regime distribution differences

2. **vs absorption_continuation (failed baseline):**
   - Compare structure overlap
   - Prove compression_breakout is NOT just "absorption retry"
   - Show different candidate sets

**Output:** `research_lab/reports/compression_overlap_analysis.md`

**Metrics:**
- Overlap rate: `overlap_trades / total_trades`
- Correlation: Daily PnL correlation between setups
- Regime divergence: Which regime each setup dominates

**Gate:** Overlap rate < 30% vs sweep_reclaim (hard gate, same as absorption)

---

### 5. Breakout Follow-Through Analysis

**File:** `research_lab/analyze_breakout_followthrough.py`

**Purpose:** Validate breakout confirmation hypothesis

**Output:** `research_lab/reports/breakout_followthrough.md`

**Metrics:**

1. **Breakout success rate:**
   - How many breakouts followed through (price stayed beyond level)?
   - How many failed (re-entered range)?
   - Target: > 50% follow-through rate

2. **Compression quality:**
   - Does longer compression → better breakout?
   - Does tighter ATR → stronger expansion?
   - Feature cohort: winners vs losers

3. **TFI/OI confirmation:**
   - Win rate when TFI > 0.5 vs < 0.5
   - Win rate when OI delta > 0 vs < 0
   - Validate confirmation filters

---

### 6. Walk-Forward Validation

**File:** `research_lab/validate_compression_walkforward.py`

**Purpose:** Test OOS stability (same protocol as absorption)

**Windows:**
- Window 0: Train 2022-2024, validate 2024
- Window 1: Train 2022-2024, validate 2025

**Command:**
```bash
python research_lab/validate_compression_walkforward.py \
  --output-dir research_lab/reports/
```

**Output:** `research_lab/reports/compression_walkforward.json`

**Hard gates:**
- 2/2 windows passed (ER > threshold in both validation periods)
- Not fragile (ER degradation < fragility threshold)
- Min trades per window >= 15
- No blocking safety flags

---

### 7. Compression Audit Package

**File:** `research_lab/reports/COMPRESSION_BREAKOUT_AUDIT_PACKAGE.md`

**Purpose:** Summary report for Claude Code audit

**Structure:**

```markdown
# Compression Breakout Audit Package

Milestone: COMPRESSION-BREAKOUT-RESEARCH-V1
Builder: Codex
Branch: research/compression-breakout-v1
Verdict: [CANDIDATE / ITERATE / REJECT]

## Executive Summary
- Full-range metrics: ER, PF, DD, trades, Sharpe
- Compression regime ER: X.XX
- Breakout follow-through rate: XX%
- Overlap vs sweep_reclaim: XX%
- WF validation: 2/2 pass [yes/no]

## Hard Gate Results
| Gate | Requirement | Actual | Result |
|---|---|---|---|
| Compression ER | > 1.5 | X.XX | PASS/FAIL |
| Breakout follow-through | >= 50% | XX% | PASS/FAIL |
| Overlap vs sweep_reclaim | < 30% | XX% | PASS/FAIL |
| Min trades | >= 20 | X | PASS/FAIL |
| WF 2/2 pass | Yes | Yes/No | PASS/FAIL |
| Safety flags | None blocking | [list] | PASS/FAIL |

## Red Flags
[List any issues]

## Recommendation
[REJECT / ITERATE / CANDIDATE FOR PHASE 2.5]
```

**Hard gates (compression_breakout specific):**

1. **Compression regime ER > 1.5** (primary target regime)
2. **Breakout follow-through rate >= 50%** (confirms breakout thesis)
3. **Overlap vs sweep_reclaim < 30%** (portfolio diversification)
4. **Range regime ER > 0.5** (acceptable secondary, not required to be high)
5. **Uptrend/downtrend regime ER near 0** (confirms blocking works)
6. **Min trades >= 20** (statistical validity)
7. **WF 2/2 pass** (OOS stability)
8. **No blocking safety flags** (pnl_sanity, etc.)

**Red flags:**

- PF > 6.0 (overfitting suspect)
- ER > 5.0 (too good to be true)
- Win rate < 35% or > 70% (unrealistic)
- Breakout follow-through < 40% (thesis not validated)
- Overlap > 40% (too similar to sweep_reclaim)
- OOS outperformance in WF (suspicious)
- Low OOS trade count (< 15 per window)

---

### 8. Test Suite

**File:** `tests/test_research_lab_compression_breakout.py`

**Coverage:**

1. `test_compression_breakout_generates_explained_long_candidate`
   - Happy path: compression + breakout + TFI surge → candidate generated
   - Reasons[] complete and specific

2. `test_compression_breakout_blocks_wrong_regime`
   - Blocks uptrend/downtrend (setup only for compression/range)
   - Blocks crowded leverage (funding/OI extreme)

3. `test_compression_breakout_requires_breakout_confirmation`
   - Rejects if price still in range (no breakout)
   - Rejects if breakout too small (< min threshold)
   - Rejects if TFI below threshold (no directional flow)

4. `test_compression_breakout_detects_failed_breakout`
   - Rejects if price re-entered range (failed breakout veto)

5. `test_compression_breakout_blocks_no_compression`
   - Rejects if ATR not compressed (percentile > threshold)
   - Rejects if compression duration too short

6. `test_compression_breakout_uses_empirical_volatility_threshold`
   - Uses same p95 threshold as absorption (0.02885372)
   - Blocks volatility panic correctly

7. `test_overlap_analysis_strict_portfolio_thresholds`
   - Overlap calculation correct (< 30% gate)

8. `test_breakout_followthrough_validator`
   - Follow-through rate calculation correct
   - Winners vs losers cohort analysis

9. `test_gate_evaluator_blocks_missing_compression_validation`
   - Blocks if compression regime results missing
   - Blocks if breakout follow-through not measured

10. `test_gate_evaluator_rejects_high_overlap_with_sweep_reclaim`
    - Hard gate: overlap > 30% → reject

**Target:** All tests pass before push

---

### 9. Hypothesis Document

**File:** `research_lab/research/COMPRESSION_BREAKOUT_HYPOTHESIS.md`

**Content:**

```markdown
# Compression Breakout Hypothesis

## Market Structure

Compression phase (ATR contraction, range coiling) followed by decisive breakout with volume/OI surge captures explosive moves.

## Edge

- Counterparty: range faders and late chasers
- Timing: enter ON breakout confirmation, BEFORE obvious to retail
- Structure: objective (ATR compression measurable, not subjective like CVD)

## Why This is NOT absorption_continuation

- absorption: CVD divergence during trend pullback (FAILED - not predictive)
- compression: ATR compression → breakout with TFI/OI surge (separate structure)

## Required Signals

1. ATR compression (percentile < p20 or p10)
2. Range contraction (consolidation bounds)
3. Decisive breakout (price beyond level + min size)
4. TFI surge (directional conviction)
5. OI participation (new positions, not just stops)

## Invalidation

- Failed breakout (re-enters range)
- Volatility panic (liquidation cascade)
- Crowded leverage (funding/OI extreme)

## Target Regimes

- Primary: `compression`
- Secondary: `range`
- Block: `uptrend`, `downtrend` (separate setups)
```

---

### 10. Milestone Tracker Update

**File:** `docs/MILESTONE_TRACKER.md`

**Changes:**

1. **Close absorption_continuation:**

```markdown
## Completed: ABSORPTION-CONTINUATION-RESEARCH-V1

**Status:** HYPOTHESIS FAILED  
**Builder:** Codex  
**Decision date:** 2026-05-12  
**Branch:** `research/trend-continuation-v1`  
**Audit:** `docs/audits/AUDIT_ABSORPTION_CONTINUATION_ITERATION_A_2026-05-12.md`

**Result:**
- Checkpoint 2: 4 trades, ER 0.34 → REJECT
- Iteration A: Fixed CVD slope + volatility threshold
- Post-fix: 25 trades, ER -0.48, PF 0.55 → HYPOTHESIS FAILED
- Verdict: Absorption thesis invalid for BTC perps (CVD not predictive)

**Learning:** Fast failure (5 days to conclusive verdict) prevented wasted effort on invalid hypothesis.
```

2. **Add compression_breakout:**

```markdown
## Current Active Milestone: COMPRESSION-BREAKOUT-RESEARCH-V1

**Status:** RESEARCH_ACTIVE  
**Builder:** Codex  
**Decision date:** 2026-05-12  
**Branch:** `research/compression-breakout-v1`  
**Handoff:** `docs/handoffs/HANDOFF_COMPRESSION_BREAKOUT_RESEARCH_V1_2026-05-12.md`

**Scope:** Research-only validation of compression_breakout_long setup (volatility compression → explosive breakout).

**Hypothesis:** ATR compression + range consolidation → decisive breakout with TFI/OI confirmation captures moves that sweep_reclaim (range specialist) cannot.

**Target regimes:** `compression` (primary), `range` (secondary)

**Timeline:** 1-2 weeks

**Success criteria:**
- Compression regime ER > 1.5
- Breakout follow-through >= 50%
- Overlap vs sweep_reclaim < 30%
- Min trades >= 20
- WF 2/2 pass
- No blocking safety flags

**Next:** Backtest validation → audit → decision (REJECT / ITERATE / CANDIDATE FOR PHASE 2.5)
```

---

## Hard Gates (Acceptance Criteria)

### Gate 1: Compression Regime Edge (CRITICAL)

**Requirement:** Uptrend ER > 1.5 in `compression` regime

**Why:** This is the target regime. If no edge here, hypothesis fails.

**Measured from:** `compression_by_regime.md` report

**Verdict:**
- ER > 1.5 → PASS
- ER 1.0-1.5 → MARGINAL (consider iterate)
- ER < 1.0 → FAIL (reject hypothesis)

---

### Gate 2: Breakout Follow-Through Rate (CRITICAL)

**Requirement:** >= 50% of breakouts followed through (stayed beyond level)

**Why:** Validates the breakout confirmation hypothesis. If most breakouts fail, setup is not capturing real expansions.

**Measured from:** `breakout_followthrough.md` report

**Verdict:**
- >= 50% → PASS
- 40-50% → MARGINAL
- < 40% → FAIL (breakout thesis invalid)

---

### Gate 3: Portfolio Overlap (HARD)

**Requirement:** Overlap rate vs sweep_reclaim < 30%

**Why:** Compression_breakout must offer diversification. If overlap > 30%, it's just a variant of sweep_reclaim.

**Measured from:** `compression_overlap_analysis.md` report

**Verdict:**
- < 30% → PASS
- 30-40% → MARGINAL (high correlation risk)
- > 40% → FAIL (too similar, no portfolio benefit)

---

### Gate 4: Range Regime Credibility (SOFT)

**Requirement:** Range regime ER > 0.5 (not required to be high, but should not lose money)

**Why:** Compression can occur in range regime. Should not blow up there.

**Measured from:** `compression_by_regime.md` report

**Verdict:**
- ER > 1.0 → BONUS (range is also strong)
- ER 0.5-1.0 → ACCEPTABLE (secondary regime, weak edge OK)
- ER < 0.5 → CONCERN (bleeding in range)

---

### Gate 5: Regime Blocking Validation (SOFT)

**Requirement:** Uptrend/downtrend ER near 0 or negative (confirms setup blocks wrong regimes)

**Why:** Setup should NOT activate in trend regimes (those are for other setups like failed absorption or future trend pullback setup).

**Measured from:** `compression_by_regime.md` report

**Verdict:**
- ER near 0 → PASS (correctly blocked)
- ER > 1.0 → CONCERN (maybe regime filter too loose?)

---

### Gate 6: Statistical Validity (HARD)

**Requirement:** Total trades >= 20, min 15 per WF validation window

**Why:** Same as absorption. Need sufficient sample for credible statistics.

**Measured from:** Full-range backtest + WF validation

**Verdict:**
- >= 20 total, >= 15 per WF window → PASS
- < 20 total OR < 15 in any window → FAIL

---

### Gate 7: Walk-Forward Stability (HARD)

**Requirement:** 2/2 windows passed, not fragile

**Why:** OOS validation. Same protocol as absorption.

**Measured from:** `compression_walkforward.json`

**Verdict:**
- 2/2 pass, not fragile → PASS
- 1/2 pass OR fragile → MARGINAL
- 0/2 pass → FAIL

---

### Gate 8: Safety Flags (HARD)

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
| Breakout follow-through < 40% | Thesis not validated | **REJECT** |
| Overlap > 40% | Too similar to sweep_reclaim | **REJECT** |
| OOS outperformance | Validation better than train | **SCRUTINIZE** |
| Low OOS trade count | < 15 in any WF window | **SCRUTINIZE** |
| pnl_sanity_review_required | Unrealistic PnL magnitude | **REJECT** |
| Negative compression ER | No edge in target regime | **REJECT** |

---

## Rejection Criteria (STOP Conditions)

**REJECT hypothesis immediately if ANY of these after initial backtest:**

1. **Compression regime ER < 0.5** → No edge in target regime
2. **Breakout follow-through < 40%** → Thesis invalid
3. **Overlap > 40%** → No portfolio diversification
4. **Total trades < 20** → Insufficient sample
5. **Blocking safety flag present** → Quality issue

**MARGINAL (consider ONE diagnostic iteration) if:**

1. **Compression ER 1.0-1.5** (weak edge, but positive)
2. **Breakout follow-through 40-50%** (marginal validation)
3. **Overlap 30-40%** (high but not disqualifying)
4. **WF 1/2 pass** (OOS instability)

**CANDIDATE (proceed to Phase 2.5) if:**

1. **All hard gates PASS**
2. **No blocking red flags**
3. **Compression ER > 1.5, breakout follow-through >= 50%, overlap < 30%**

---

## No-Touch Areas (UNCHANGED)

Same as absorption_continuation:

- `orchestrator.py`
- `core/signal_engine.py`
- `execution/**`
- `governance/**`
- `risk/**`
- `settings.py`
- `backtest/**` (unless adding compression-specific tooling)

**All work stays in:**
- `research_lab/setups/compression_breakout.py` (new)
- `research_lab/backtest_compression_breakout.py` (new)
- `research_lab/analyze_*.py` (new analysis scripts)
- `research_lab/reports/compression_*.md` (new reports)
- `tests/test_research_lab_compression_breakout.py` (new tests)
- `docs/**` (handoffs, audits, milestone tracker)

**Zero production changes until Phase 2.5 contracts exist.**

---

## Critical Reminders

### 1. This is NOT absorption_continuation_v2

Compression_breakout is a **separate hypothesis** with different structure:
- Different market regime (compression, not trend pullback)
- Different entry trigger (breakout, not pullback absorption)
- Different data (ATR compression, not CVD divergence)
- Different counterparty (range faders, not pullback sellers)

**Do NOT:**
- Reuse absorption_continuation code (start fresh)
- Try to "rescue" absorption logic
- Mix CVD absorption with compression breakout

---

### 2. Compression is Objective, Not Interpretive

Unlike CVD divergence (subjective, FAILED), compression metrics are objective:
- ATR percentile: measurable
- Range width: measurable
- Breakout size: measurable
- TFI surge: measurable

**This is an advantage.** Setup should be deterministic and auditable.

---

### 3. Breakout Follow-Through is Critical

If breakout confirmation does not predict follow-through (< 50% success rate), hypothesis is invalid.

**Monitor:**
- How many breakouts held?
- How many failed (re-entered range)?
- Is there a pattern (TFI/OI confirmation improves follow-through)?

---

### 4. Overlap Must Be Low

If compression_breakout overlaps > 30% with sweep_reclaim, it does NOT offer portfolio diversification.

**Goal:** Compression captures moves sweep_reclaim misses (clean expansions after coiling, not liquidity hunts).

---

### 5. Research-Only Until Phase 2.5

Same discipline as absorption:
- No production integration until Phase 2.5 contracts exist
- No `setup_type` field in production SignalCandidate yet
- No multi-setup dispatcher yet
- No per-setup metrics in production yet

**After validation:** If compression_breakout passes gates, THEN build Phase 2.5 contracts (multi-setup architecture) before deploying either setup.

---

## Timeline (Target: 1-2 weeks)

| Step | Time | Deliverable |
|---|---|---|
| 1. Setup implementation | 1-2 days | `compression_breakout.py`, tests pass |
| 2. Backtest runner + reports | 1 day | Full-range metrics, rejection funnel |
| 3. Per-regime analysis | 0.5 day | Compression vs range vs trend breakdown |
| 4. Overlap analysis | 0.5 day | vs sweep_reclaim, vs absorption |
| 5. Breakout follow-through analysis | 0.5 day | Success rate, feature cohorts |
| 6. Walk-forward validation | 0.5 day | 2 windows, OOS stability |
| 7. Audit package | 0.5 day | Summary report, gate results |
| 8. Push + request audit | - | Commit, push, handoff to Claude |

**Total:** ~5-6 days (with buffer for iteration if needed)

---

## Expected Outcomes

### Scenario 1: SUCCESS (40-50% probability)

**Metrics after validation:**
- Compression regime ER: 2.0-3.0
- Breakout follow-through: 55-65%
- Overlap vs sweep_reclaim: 15-25%
- Total trades: 30-60
- WF: 2/2 pass

**Verdict:** CANDIDATE FOR PHASE 2.5

**Next:** Build multi-setup contracts, integrate compression_breakout + sweep_reclaim into portfolio architecture.

---

### Scenario 2: MARGINAL (30-40% probability)

**Metrics:**
- Compression ER: 1.0-1.5 (weak but positive)
- Breakout follow-through: 40-50% (marginal)
- Overlap: 30-40% (high)

**Verdict:** ITERATE (one diagnostic iteration, similar to absorption)

**Potential fixes:**
- Tighter compression threshold (p10 instead of p20)
- Stricter breakout confirmation (higher TFI/OI thresholds)
- Failed breakout veto (more aggressive)

**Decision:** User approval required for iteration (no automatic retry)

---

### Scenario 3: FAILED (20-30% probability)

**Metrics:**
- Compression ER < 0.5 (no edge)
- Breakout follow-through < 40% (thesis invalid)
- Overlap > 40% (no diversification)

**Verdict:** HYPOTHESIS FAILED

**Conclusion:** Compression_breakout does not have edge in BTC perps. Breakout confirmation is not predictive.

**Next:** Move to Setup #4 (e.g., `crowded_unwind` - funding/OI exhaustion → reversal)

---

## Your First Response Must Contain

1. **Confirmed milestone scope** (compression_breakout research, zero production changes)
2. **Acceptance criteria clear** (compression ER >1.5, breakout follow-through >=50%, overlap <30%)
3. **Hypothesis understanding** (compression → expansion, NOT pullback absorption)
4. **Data requirements** (ATR compression, range bounds, breakout level, TFI/OI confirmation)
5. **Implementation plan** (ordered steps, file structure, timeline)
6. **Only then: start coding**

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
research: compression breakout backtest validation

WHAT: Implement compression_breakout_long setup, backtest runner, per-regime analysis
WHY: Test compression → expansion hypothesis (Phase 2, Setup #2 after absorption FAILED)
RESULT: 42 trades, compression ER 2.3, breakout follow-through 58%, overlap 22%
STATUS: Validation complete, awaiting Claude audit
```

**Do NOT self-mark as "done". Claude Code audits after push.**

---

## Questions Before Starting?

**Expected:** Minimal - scope is clear, structure follows absorption pattern

**If questions:**
- ATR compression threshold (p10 vs p20)? → Start with p20, document sensitivity
- Breakout offset (how far beyond level)? → 0.3-0.5 ATR is reasonable default
- Failed breakout lookback? → 4-8 bars (1-2 hours at 15m) is typical
- TFI breakout threshold? → 0.4-0.5 for decisive moves (vs 0.3 for absorption)

---

## Start Implementation

Confirm scope, acceptance criteria, and hypothesis understanding in your first response.

Then proceed: setup implementation → backtest → analysis → validation → audit package → push.

---

**Handoff complete. Branch `research/compression-breakout-v1` ready for compression_breakout research.**

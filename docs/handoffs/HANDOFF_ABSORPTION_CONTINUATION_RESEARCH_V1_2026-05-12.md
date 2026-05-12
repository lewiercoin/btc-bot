# CLAUDE HANDOFF → CODEX

## Checkpoint

- **Last commit:** `4ce27f5` - "docs: Phase 1 closure and Phase 2 readiness"
- **Branch:** `main` (synced, pushed to GitHub)
- **Target branch:** `research/trend-continuation-v1` (created, clean)
- **Working tree:** Clean (only untracked artifacts: research_lab.db.v3, ad-hoc scripts)

## Before You Code

**Mandatory reads (in order):**

1. **Workflow & discipline:**
   - `AGENTS.md` - your workflow rules, commit discipline, layer separation
   - `CASCADE.md` (your operating model, builder mode section)
   - `docs/MILESTONE_TRACKER.md` - current status, known issues

2. **Strategic context:**
   - `docs/analysis/STRATEGIC_SETUP_PORTFOLIO_CONSULTATION_2026-05-12.md` - institutional setup portfolio design, Phase 2 hypothesis
   - `docs/analysis/POST_GRID_PORTFOLIO_PLAN_2026-05-12.md` - grid closure decision, multi-setup rationale
   - `docs/audits/AUDIT_GRID_SEARCH_TRIAL00095_2026-05-12.md` - why grid failed, why sweep-reclaim is bounded

3. **Research Lab workflow:**
   - `docs/BLUEPRINT_RESEARCH_LAB.md` - research lab architecture, boundaries
   - `docs/RESEARCH_LAB_WORKFLOW.md` - optimize/autoresearch protocol
   - `docs/DECISIONS_LOG.md` (2026-05-12 entry) - Phase 1 closure decision

4. **Technical blueprints:**
   - `docs/BLUEPRINT_V1.md` - bot architecture (for context, but no changes to live path)
   - `core/models.py` - Features, SignalCandidate, dataclass contracts

## Milestone: ABSORPTION-CONTINUATION-RESEARCH-V1

**Type:** Research-only  
**Scope:** Hypothesis validation for `absorption_continuation_long` setup  
**Timeline:** 6-10 days  
**Goal:** Prove or disprove edge hypothesis, NOT "deliver setup at all costs"

### Strategic Context

**Problem identified:**
- 2026-05-11: BTC +2k USD trend day → bot generated 0 trades
- Sweep-reclaim is mean-reversion specialist (range/liquidity days)
- Cannot be forced to capture trend days without quality collapse (grid proof)

**Solution approach:**
- Build separate setup for trend structure: `absorption_continuation_long`
- NOT generic "buy EMA pullback" (retail)
- YES "enter on controlled pullback absorption before continuation obvious" (institutional)

**Critical mindset:**
- This is **hypothesis testing**, not feature delivery
- If edge doesn't exist → outcome is REJECT or ITERATE, not rescue through loosening gates
- Better to reject weak setup than build portfolio of noise

## Setup Hypothesis (Institutional-Grade)

### NOT This (Retail)

"Buy when price pulls back to 50 EMA in uptrend"

### YES This (Institutional)

**Market Structure:** Established uptrend → controlled pullback to liquidity level → absorption confirmed → continuation resumes

**Who Is Trapped/Late:**
- Pullback sellers who fade trend without confirmation
- Early shorts who assume reversal before support tested  
- Late buyers who wait for "breakout confirmation" (we enter earlier, better RR)

**What We Exploit:**
- Liquidity-supported pullback (smart money accumulates during retest)
- Absorption timing (CVD/TFI shows buyers stepping in, not distribution)
- Entry BEFORE continuation obvious to retail

**Why Edge Exists:**
- Retail waits for breakout confirmation → enters late, worse RR
- We enter on pullback absorption → early, good RR
- If absorption fails → structure invalidates → exit with small loss
- If absorption succeeds → trend resumes → capture move with asymmetric risk

**Data Proxies:**
- Trend structure: EMA50, EMA200, slopes
- Pullback: depth %, proximity to liquidity levels (EMA50, equal_lows)
- Absorption: CVD bullish divergence, TFI impulse, OI delta
- Risk: funding extremes, OI Z-score, force_order spikes

## Deliverables

### 1. BaseSetup Interface (Shared)

**File:** `research_lab/setups/base_setup.py`

**Purpose:** Shared interface for all future setups (not just absorption_continuation)

**Required methods:**
```python
class BaseSetup(ABC):
    @abstractmethod
    def get_setup_type(self) -> str:
        """Return setup identifier (e.g., 'absorption_continuation_long')"""
    
    @abstractmethod
    def check_regime_allowed(self, regime: str) -> bool:
        """Return True if regime is valid for this setup"""
    
    @abstractmethod
    def evaluate_structure(
        self, 
        features: Features, 
        snapshot: MarketSnapshot
    ) -> tuple[bool, list[str]]:
        """
        Evaluate if market structure matches setup hypothesis.
        Returns: (structure_valid, reasons_if_rejected)
        """
    
    @abstractmethod
    def generate_signal_candidate(
        self,
        features: Features,
        snapshot: MarketSnapshot,
        config: StrategyConfig
    ) -> SignalCandidate | None:
        """
        Generate signal candidate if all conditions met.
        Returns None if any condition fails.
        Signal must include full reasons[].
        """
    
    def get_metrics_tags(self) -> dict[str, str]:
        """Return setup-specific metric tags for tracking"""
        return {"setup_type": self.get_setup_type()}
```

### 2. AbsorptionContinuation Implementation

**File:** `research_lab/setups/absorption_continuation.py`

**Class:** `AbsorptionContinuationLong(BaseSetup)`

**Logic components:**

#### A. Regime Filters (Hard Gates)

```python
regime_allowed = ["uptrend"]
# Optional: "normal" if trend structure present (secondary)

regime_blocked = [
    "crowded_leverage",  # Too risky
    "compression",       # Wrong structure
    "downtrend",         # Wrong direction
    "post_liquidation",  # Chaotic
]
```

#### B. Trend Structure Filters

```python
# Trend established
price > ema200_4h
ema50_4h > ema200_4h
ema200_slope > min_trend_slope  # e.g., 0.0001 (positive)

# Trend not overextended
price < ema200_4h * (1 + max_extension_pct)  # e.g., 1.05 (within 5%)

# NOT crowded/parabolic
funding_8h < funding_extreme  # e.g., 0.0005 (not too crowded long)
oi_zscore_60d < oi_extreme    # e.g., 2.0 (not blow-off top)
```

#### C. Pullback Structure

```python
# Controlled pullback depth
pullback_depth_pct = (recent_high - current_price) / recent_high
pullback_depth_pct in [pullback_min, pullback_max]  # e.g., [0.005, 0.03] (0.5-3%)

# Pullback to liquidity level (structural, not arbitrary)
price_near_ema50 = abs(price - ema50_4h) / atr_4h < proximity_atr  # e.g., 0.5 ATR
OR
price_near_equal_low = any(
    abs(price - lvl) / atr_4h < level_proximity_atr 
    for lvl in recent_equal_lows
)

# Structure intact (higher lows maintained)
price > prior_swing_low
```

#### D. Absorption Confirmation (CRITICAL)

```python
# CVD shows buying during pullback
(cvd_bullish_divergence == True)  # Price down, CVD up = absorption
OR
(cvd_15m > recent_cvd_low AND cvd_15m_slope > 0)  # Buyers stepping in

# TFI confirms directional interest
tfi_60s > tfi_threshold  # e.g., 0.3 (bullish flow)

# OI shows participation, not unwind
oi_delta_pct >= 0  # OI stable or rising
```

#### E. Veto Conditions (Override - NO ENTRY)

```python
# Crowded leverage risk
funding_8h > funding_crowd  # e.g., 0.0008
OR
oi_zscore_60d > oi_crowd    # e.g., 2.5

# Volatility panic (loss of control)
atr_4h_norm > volatility_panic  # e.g., 0.008 (8bps = panic)

# Liquidation cascade active
force_order_spike == True AND force_order_rate_60s > liquidation_threshold

# Sweep without reclaim (failed support test)
sweep_detected == True AND sweep_side == "LOW" AND reclaim_detected == False
```

#### F. Entry Construction

```python
# Entry: at or slightly above pullback low (support confirmed)
entry_price = pullback_low + (entry_offset_atr * atr_15m)

# Stop: below pullback low OR structural level (whichever is closer)
stop_loss = min(
    pullback_low - (invalidation_offset_atr * atr_15m),
    prior_swing_low - (invalidation_offset_atr * atr_15m)
)

# TP1: next resistance or ATR-based
take_profit_1 = entry_price + (tp1_atr_mult * atr_15m)

# TP2: trend target (extended)
take_profit_2 = entry_price + (tp2_atr_mult * atr_15m)

# RR gate
rr_ratio = (take_profit_1 - entry_price) / (entry_price - stop_loss)
require: rr_ratio >= min_rr  # e.g., 2.5
```

#### G. Reasons[] Taxonomy

Every signal MUST include structured reasons:

```python
reasons = [
    # Setup identity
    "setup_type=absorption_continuation_long",
    
    # Regime context
    f"regime={regime_state}",
    
    # Trend structure
    f"price_above_ema200={price > ema200_4h}",
    f"ema50_above_ema200={ema50_4h > ema200_4h}",
    f"ema200_slope={ema200_slope:.6f}",
    f"trend_extension_pct={(price / ema200_4h - 1):.4f}",
    
    # Pullback structure
    f"pullback_depth_pct={pullback_depth_pct:.4f}",
    f"price_near_ema50_atr={abs(price - ema50_4h) / atr_4h:.2f}",
    f"maintains_higher_lows={price > prior_swing_low}",
    f"prior_swing_low={prior_swing_low:.2f}",
    
    # Absorption confirmation
    f"cvd_bullish_divergence={cvd_bullish_divergence}",
    f"cvd_15m={cvd_15m:.2f}",
    f"tfi_60s={tfi_60s:.3f}",
    f"oi_delta_pct={oi_delta_pct:.4f}",
    
    # Risk checks
    f"funding_8h={funding_8h:.6f}",
    f"oi_zscore_60d={oi_zscore_60d:.2f}",
    f"atr_4h_norm={atr_4h_norm:.6f}",
    f"force_order_spike={force_order_spike}",
    
    # Entry quality
    f"rr_ratio={rr_ratio:.2f}",
    f"entry={entry_price:.2f}",
    f"stop={stop_loss:.2f}",
    f"tp1={take_profit_1:.2f}",
]
```

**Parameter defaults (hypothesis-driven, NOT optimized):**

```python
# Start with these values (iterate hypothesis if edge weak, don't blindly optimize)
pullback_min = 0.005          # 0.5% minimum pullback
pullback_max = 0.03           # 3% maximum pullback
proximity_atr = 0.5           # Within 0.5 ATR of EMA50
level_proximity_atr = 0.3     # Within 0.3 ATR of equal low
tfi_threshold = 0.3           # TFI > 0.3 = bullish flow
min_trend_slope = 0.0001      # Positive EMA200 slope
max_extension_pct = 0.05      # Price < EMA200 * 1.05
funding_extreme = 0.0005      # Funding < 0.05% per 8h
funding_crowd = 0.0008        # Funding > 0.08% = too crowded
oi_extreme = 2.0              # OI Z-score < 2.0
oi_crowd = 2.5                # OI Z-score > 2.5 = blow-off
volatility_panic = 0.008      # ATR norm > 0.8% = panic
entry_offset_atr = 0.1        # Entry 0.1 ATR above pullback low
invalidation_offset_atr = 0.15  # Stop 0.15 ATR below structural level
tp1_atr_mult = 2.5            # TP1 = 2.5 ATR
tp2_atr_mult = 6.0            # TP2 = 6.0 ATR
min_rr = 2.5                  # Minimum risk:reward ratio
```

### 3. Backtest Harness (Research-Only)

**File:** `research_lab/backtest_absorption_continuation.py`

**Purpose:** Run backtest with **absorption_continuation ONLY** (not mixed with sweep-reclaim)

**Logic:**
1. Load historical data (2022-01-01 → 2026-03-29, same range as grid)
2. For each bar:
   - Calculate features
   - Classify regime
   - Call `absorption_continuation.generate_signal_candidate()`
   - If signal generated → simulate trade (same execution/risk logic as sweep-reclaim)
   - Track per-regime metrics
3. Output:
   - Overall metrics: ER, PF, DD, trades, Sharpe, win rate
   - Per-regime breakdown
   - Trade list with reasons[]
   - Signal rejection reasons (per filter)

**Key requirement:** Do NOT mix absorption_continuation with sweep-reclaim signals in same backtest. Test independently.

### 4. Overlap Analysis vs Sweep-Reclaim

**File:** `research_lab/analyze_setup_overlap.py`

**Purpose:** Measure how often absorption_continuation and sweep-reclaim generate signals on same decision cycle

**Logic:**
1. Load baseline trial-00095 signals (sweep-reclaim)
2. Run absorption_continuation backtest (generates own signals)
3. For each timestamp:
   - Check if both setups generated signal
   - If yes → mark as overlap
4. Calculate:
   - `overlap_rate = overlap_count / total_signals_either`
   - Per-regime overlap rate
   - Conflict cases (both want entry at same time)

**Target:** overlap_rate < 30%  
**Red flag:** overlap_rate > 50% (setups too similar → REJECT)

### 5. Trend Day Capture Analysis

**File:** `research_lab/analyze_trend_day_capture.py`

**Purpose:** Measure if absorption_continuation captures clean trend days (e.g., 2026-05-11)

**Logic:**
1. Define "trend day":
   - Price moves > 1.5% in one direction
   - Funding stable (not crowded)
   - OI stable or rising (participation, not unwind)
   - No major liquidation spikes
2. Identify all trend days in backtest range
3. Check: Did absorption_continuation generate signal on these days?
4. Calculate:
   - `capture_rate = days_captured / total_trend_days`
   - Capture rate by regime
   - Missed trend days (why no signal?)

**Target:** capture_rate ≥ 50%  
**Red flag:** capture_rate < 30% (setup misses target structure → REJECT)

### 6. Validation Metrics Report

**File:** `research_lab/reports/absorption_continuation_validation_report.md`

**Contents:**

#### A. Overall Performance

| Metric | Value | vs Baseline (sweep-reclaim) |
|---|---|---|
| Total trades | X | +Y% |
| ER | X.XX | +Y% |
| PF | X.XX | +Y% |
| Max DD | X.X% | +Y pp |
| Sharpe | XX.XX | +Y% |
| Win rate | XX.X% | +Y pp |

#### B. Per-Regime Performance

| Regime | Trades | ER | PF | DD | Sharpe | Expected? |
|---|---|---|---|---|---|---|
| uptrend | X | X.XX | X.XX | X.X% | XX.X | Primary edge ✅ |
| normal | X | X.XX | X.XX | X.X% | XX.X | Secondary / neutral |
| range | X | X.XX | X.XX | X.X% | XX.X | Acceptable bleed |
| crowded_leverage | 0 | - | - | - | - | Hard veto ✅ |
| compression | 0 | - | - | - | - | Hard veto ✅ |
| downtrend | 0 | - | - | - | - | Long-only ✅ |

**Key validation:** ER > 1.5 in uptrend? Trades in uptrend >> sweep-reclaim in uptrend?

#### C. Structural Validation

**Pullback depth distribution:**
- Histogram of pullback_depth_pct for winning vs losing trades
- Expected: winners cluster at specific depths (structural edge)
- Red flag: uniform distribution (no structure, random noise)

**Absorption confirmation hit rate:**
- When `cvd_bullish_divergence=True`, how often does trade win?
- Target: > 55%
- Red flag: < 50% (confirmation is noise)

**Trend day capture:**
- Trend days identified: X
- Trend days captured: Y
- Capture rate: Z%
- Target: ≥ 50%

#### D. Overlap Analysis

| Overlap Type | Count | Rate |
|---|---|---|
| Both generate signal (same cycle) | X | Y% |
| Only absorption_continuation | X | Y% |
| Only sweep-reclaim | X | Y% |

**Target:** overlap < 30%  
**Red flag:** overlap > 50%

#### E. Specific Case Analysis

**2026-05-11 (trend day, +2k USD):**
- Did absorption_continuation generate signal? YES / NO
- If YES: entry, exit, PnL, reasons[]
- If NO: why not? (rejection reasons)

**Expected:** At least 1-2 high-quality entries on this day.

### 7. Walk-Forward Validation

**File:** Walk-forward outputs in `research_lab/` (standard WF protocol)

**Protocol:**
- 2 windows:
  - Window 0: train 2022-2024, validate 2024-2025
  - Window 1: train 2022-2025, validate 2025-2026
- Each window:
  - Run backtest on train period
  - Run backtest on validation period
  - Compare ER, PF, DD, trades
  - Check if validation passes (ER > threshold, trades > minimum)
- Overall:
  - Both windows pass? Not fragile?
  - IS degradation < 30%?

**Required:** 2/2 windows pass, not fragile

### 8. Comparison Report vs Sweep-Reclaim

**File:** `research_lab/reports/absorption_vs_sweep_comparison.md`

**Contents:**

#### Side-by-Side Metrics

| Metric | Sweep-Reclaim (baseline) | Absorption-Continuation | Delta |
|---|---|---|---|
| Trades (total) | 271 | X | +Y% |
| ER | 2.129 | X.XX | +Y% |
| PF | 4.662 | X.XX | +Y% |
| DD | 6.51% | X.X% | +Y pp |
| Sharpe | 11.933 | XX.X | +Y% |

#### Per-Regime Comparison

Focus on uptrend (key differentiation):

| Setup | Uptrend Trades | Uptrend ER | Uptrend PF |
|---|---|---|---|
| Sweep-reclaim | ~30 (estimate) | ~0.8 (weak) | ~2.5 (weak) |
| Absorption-continuation | X | X.XX | X.XX |

**Expected:** Absorption shows strong ER in uptrend where sweep-reclaim is weak.

#### Structural Differences

| Dimension | Sweep-Reclaim | Absorption-Continuation |
|---|---|---|
| Primary regime | range, post_liquidation | uptrend |
| Market structure | liquidity sweep → reversal | controlled pullback → continuation |
| Entry timing | After sweep + reclaim | During pullback absorption |
| Edge hypothesis | Fade late breakout chasers | Join early trend continuation |

### 9. Smoke Tests

**File:** `tests/test_research_lab_absorption_continuation.py`

**Required tests:**
1. **test_absorption_setup_instantiation**: Setup creates successfully
2. **test_regime_filters**: Only uptrend allowed, others blocked
3. **test_trend_structure_filters**: Price > EMA200, EMA50 > EMA200, slope > 0
4. **test_pullback_structure**: Pullback depth in range, near liquidity level
5. **test_absorption_confirmation**: CVD divergence OR TFI > threshold
6. **test_veto_conditions**: Crowded funding/OI blocks entry
7. **test_entry_construction**: Entry/stop/TP levels logical
8. **test_reasons_completeness**: Every signal has full reasons[]
9. **test_known_trend_day_2026_05_11**: Generates signal on 2026-05-11 (or explains why not)
10. **test_no_live_path_side_effects**: Running setup does NOT touch orchestrator/execution

**Coverage target:** > 80% of `absorption_continuation.py` logic

### 10. Final Audit Package for Claude Code

**File:** `research_lab/reports/ABSORPTION_CONTINUATION_AUDIT_PACKAGE.md`

**Contents:**

#### Executive Summary
- Setup hypothesis (one paragraph)
- Key results (ER, trades, regime performance)
- Verdict recommendation: REJECT / ITERATE / CANDIDATE FOR PHASE 2.5

#### Metrics Summary
- Table of overall metrics
- Table of per-regime metrics
- Overlap rate vs sweep-reclaim
- Trend day capture rate
- Absorption confirmation hit rate

#### Hard Gate Results

| Gate | Requirement | Actual | Pass? |
|---|---|---|---|
| Uptrend ER | > 1.5 | X.XX | ✅ / ❌ |
| Uptrend trades | >> sweep-reclaim | X vs Y | ✅ / ❌ |
| Trend day capture | ≥ 50% | Z% | ✅ / ❌ |
| Overlap control | < 30% | X% | ✅ / ❌ |
| Range bleed | > -1.0 | X.XX | ✅ / ❌ |
| Walk-forward | 2/2 pass | Y/2 | ✅ / ❌ |
| Safety flags | None blocking | Clean / Flags | ✅ / ❌ |
| Explainability | Reasons[] complete | Yes / No | ✅ / ❌ |

#### Red Flag Analysis

| Red Flag | Present? | Severity | Notes |
|---|---|---|---|
| Uniform pullback distribution | Yes / No | REJECT / OK | ... |
| High overlap (> 50%) | Yes / No | REJECT / OK | ... |
| Absorption confirmation < 50% | Yes / No | REJECT / OK | ... |
| Trend day capture < 30% | Yes / No | REJECT / OK | ... |
| OOS ER >> IS ER | Yes / No | WARN / OK | ... |

#### Verdict & Next Steps

**Verdict:** REJECT / ITERATE / CANDIDATE FOR PHASE 2.5

**If REJECT:**
- Why: (specific reasons)
- Root cause: (hypothesis flaw, data insufficient, wrong structure)
- Recommendation: Do not proceed to Phase 2.5

**If ITERATE:**
- Issues identified: (list)
- Proposed changes: (hypothesis refinement, not parameter rescue)
- Expected improvement: (how will this prove edge)

**If CANDIDATE:**
- Edge validated: (how)
- Ready for: Phase 2.5 (multi-setup contracts implementation)
- Next steps: (specific actions)

#### Appendix: Raw Data
- Link to backtest outputs
- Link to WF reports
- Link to overlap analysis
- Link to trend day analysis

## Target Files (Expected Codex Creates/Modifies)

### New files (research-only):

```
research_lab/setups/__init__.py
research_lab/setups/base_setup.py
research_lab/setups/absorption_continuation.py
research_lab/backtest_absorption_continuation.py
research_lab/analyze_setup_overlap.py
research_lab/analyze_trend_day_capture.py
research_lab/reports/absorption_continuation_validation_report.md
research_lab/reports/absorption_vs_sweep_comparison.md
research_lab/reports/ABSORPTION_CONTINUATION_AUDIT_PACKAGE.md
tests/test_research_lab_absorption_continuation.py
docs/research/ABSORPTION_CONTINUATION_HYPOTHESIS.md
```

### Modified files (if needed):

```
research_lab/types.py (if setup-specific types needed)
research_lab/constants.py (if setup-specific constants needed)
```

### NO-TOUCH files (production):

```
core/signal_engine.py
orchestrator.py
execution/**
governance/**
risk/**
settings.py
```

## Acceptance Criteria (How We Know It's Done)

### Phase 2 is complete when:

1. ✅ **BaseSetup interface** implemented and documented
2. ✅ **AbsorptionContinuation setup** implemented with all filters, reasons[], tests
3. ✅ **Backtest** runs successfully (2022-2026 range), outputs metrics
4. ✅ **Per-regime metrics** calculated and reported
5. ✅ **Overlap analysis** completed (vs sweep-reclaim / trial-00095)
6. ✅ **Trend day capture analysis** completed (including 2026-05-11)
7. ✅ **Walk-forward validation** executed (2 windows)
8. ✅ **Comparison report** written (absorption vs sweep-reclaim)
9. ✅ **Smoke tests** written and passing (> 80% coverage)
10. ✅ **Audit package** prepared for Claude Code

**AND:**

11. ✅ **No live-path changes** (orchestrator, execution, settings.py untouched)
12. ✅ **Hypothesis validation** performed (not just "delivered setup")
13. ✅ **Verdict rendered**: REJECT / ITERATE / CANDIDATE (based on hard gates)

### Phase 2 is NOT done when:

- Setup "exists" but no validation metrics
- Backtest runs but no per-regime breakdown
- Metrics present but no overlap analysis vs sweep-reclaim
- WF validation skipped or incomplete
- Trend day capture not measured
- Audit package missing or incomplete
- Hard gates not checked
- Red flags not analyzed
- Verdict is "it looks good" without data proof

## Known Issues (from Prior Work)

| # | Issue | Blocking for Phase 2? | Action |
|---|---|---|---|
| K1-K5 | (from MILESTONE_TRACKER) | NO | Phase 2 is research-only, doesn't touch these areas |
| Grid | All candidates rejected | Context only | Informs why we need absorption_continuation |
| Autoresearch | Optimized wrong objective | Context only | Don't repeat: validate hypothesis, not optimize blindly |

**No blocking issues for Phase 2 research work.**

## Your First Response Must Contain

1. **Confirmed milestone scope**
   - What you will implement (files, logic, tests)
   - What you will NOT touch (live path boundaries)

2. **Acceptance criteria confirmation**
   - How you will validate edge hypothesis
   - What metrics prove/disprove edge
   - What verdict outcomes are possible (REJECT / ITERATE / CANDIDATE)

3. **Known risks and mitigation**
   - Risk: Hypothesis is wrong (edge doesn't exist)
   - Mitigation: Render REJECT verdict, propose iteration or alternate setup
   - Risk: Overlap with sweep-reclaim too high
   - Mitigation: Measure overlap, reject if > 50%
   - Risk: Trend day capture too low
   - Mitigation: Analyze why missed, iterate hypothesis

4. **Implementation plan** (ordered steps)
   - Step 1: Read mandatory docs
   - Step 2: Implement BaseSetup interface
   - Step 3: Implement AbsorptionContinuation logic
   - Step 4: Build backtest harness
   - Step 5: Run validation metrics
   - Step 6: WF validation
   - Step 7: Overlap + trend day analysis
   - Step 8: Write reports
   - Step 9: Prepare audit package
   - Step 10: Smoke tests
   - Step 11: Push for audit

5. **Timeline estimate**
   - Days expected per step
   - Checkpoint commits
   - When ready for Claude Code audit

6. **Only then: start coding**

## Commit Discipline

- Commit at logical checkpoints:
  - BaseSetup interface complete
  - AbsorptionContinuation logic complete
  - Backtest harness working
  - Metrics reports ready
  - Audit package complete

- Every commit must include:
  - **WHAT:** Files changed, logic implemented
  - **WHY:** Purpose, hypothesis being tested
  - **STATUS:** What's done, what's pending
  - Co-Authored-By: Claude Code <noreply@anthropic.com> (for consultation credit)

- Do NOT commit:
  - Incomplete logic fragments
  - Commented-out code experiments
  - Unvalidated backtest outputs
  - "Work in progress" placeholders

## Critical Reminders

### This Is Hypothesis Testing, Not Feature Delivery

- **Good outcome:** Edge validated → CANDIDATE FOR PHASE 2.5
- **Also good outcome:** Edge rejected → ITERATE or try different setup
- **Bad outcome:** "Delivered setup" without proving edge exists

### If Edge Doesn't Exist

- Do NOT rescue by loosening gates
- Do NOT grid-search parameters blindly
- Do NOT mix with sweep-reclaim to "boost metrics"
- DO analyze why hypothesis failed
- DO propose iteration (refined hypothesis, different confirmation logic)
- DO consider alternate setup (compression_breakout, crowded_unwind)

### If Overlap Rate > 50%

- Setups are too similar (not orthogonal)
- Do NOT proceed to Phase 2.5
- Either: refine absorption_continuation to reduce overlap
- Or: reject and try different setup family

### If Trend Day Capture < 30%

- Setup misses target structure (doesn't solve 2026-05-11 problem)
- Do NOT proceed to Phase 2.5
- Either: refine hypothesis (why not capturing?)
- Or: reject and try different setup

### No Production Changes

- Zero changes to orchestrator, execution, governance, risk, settings
- Research work stays in research_lab/**, tests/test_research_lab*, docs/**
- If you need to understand live logic, READ it, don't MODIFY it

## After Phase 2 Complete

1. **Push research branch**
2. **Notify user + Claude Code**: "Phase 2 complete, ready for audit"
3. **Claude Code audits** using audit package
4. **Verdict rendered**: REJECT / ITERATE / CANDIDATE
5. **If CANDIDATE:** User approves Phase 2.5 (multi-setup contracts)
6. **If ITERATE:** User approves iteration scope
7. **If REJECT:** User approves alternate setup or strategic pivot

## Questions Before Starting?

None expected - scope is clear, hypothesis is defined, acceptance criteria are explicit.

If you have questions about:
- **Hypothesis logic:** See STRATEGIC_SETUP_PORTFOLIO_CONSULTATION_2026-05-12.md section C
- **Data availability:** See core/models.py Features dataclass
- **Acceptance gates:** See section "Acceptance Criteria" above
- **Workflow:** See AGENTS.md, RESEARCH_LAB_WORKFLOW.md

**Start by confirming scope, acceptance criteria, risks, plan, timeline. Then code.**

---

**Handoff complete. Branch `research/trend-continuation-v1` is ready. Awaiting your response.**

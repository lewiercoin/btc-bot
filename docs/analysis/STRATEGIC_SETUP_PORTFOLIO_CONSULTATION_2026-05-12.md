# Strategic Setup Portfolio Consultation

Date: 2026-05-12  
Consultant: Claude Code  
Context: Pre-Phase 2 TREND-CONTINUATION-RESEARCH-V1  
Purpose: Define institutional-grade setup portfolio architecture before implementation

---

## A. Executive Verdict

**RECOMMENDATION: PROCEED with Phase 2 trend-continuation, BUT reframe hypothesis from retail "EMA pullback" to institutional "absorption after controlled retest in liquidity-supported trend"**

**Key findings:**
1. Current sweep-reclaim is correctly bounded as liquidity-response specialist
2. Final portfolio should target 5-7 setup families, not 10+
3. Trend-continuation must exploit **controlled pullback absorption** + **liquidity confirmation**, not generic "price > EMA"
4. Phase 2 is correct next step, but hypothesis needs institutional grounding
5. Multi-setup architecture must support **setup conflict detection** and **regime-aware activation**, not just simple arbiter

**Critical insight:**  
The grid didn't just fail to improve sweep-reclaim—it validated that **each setup has natural bounds**. This means portfolio edge comes from **regime coverage**, not parameter stretching.

---

## B. Proposed Final Setup Portfolio

Target: **6 core setup families** mapped to market microstructure

### Setup Portfolio Table

| Setup Family | Market Structure | Participant Behavior | Who Is Trapped/Late | Data Proxies | Regime Activation | Phase |
|---|---|---|---|---|---|---|
| **1. sweep_reclaim** | Liquidity sweep → reclaim | Stop hunt → reversal | Late breakout chasers | sweep/reclaim detection, equal levels, TFI flip | range, post_liquidation | DONE |
| **2. absorption_continuation** | Controlled pullback in trend | Trend absorption → continuation | Pullback sellers, early fade | CVD divergence, TFI impulse, OI stability, EMA structure | uptrend, downtrend | Phase 2 ✅ |
| **3. compression_breakout** | Volatility squeeze → expansion | Range compression → directional explosion | Range traders, late entries | ATR compression, funding normalization, OI buildup | compression | Phase 4 |
| **4. crowded_unwind** | Funding/OI stress → relief | Forced liquidations → counter-move | Overleveraged crowd | funding extremes, OI Z-score, force_order spike | crowded_leverage | Phase 5 |
| **5. failed_breakout_trap** | False breakout → reversal | Breakout trap → squeeze opposite | Breakout chasers | sweep without reclaim, volume exhaustion, CVD divergence | range boundaries | Phase 6 |
| **6. exhaustion_reversal** | Overextension → mean revert | Parabolic exhaustion → capitulation | Late trend followers | price > 2-3 ATR from EMA, funding > 90th %ile, OI exhaustion | trend extremes | Phase 7 |

**NOT INCLUDED (defer or reject):**
- **Range rotation** - too similar to sweep_reclaim, marginal add
- **Session effects** - useful as modifier, not standalone setup
- **News/macro** - offline analysis only, too slow for decision loop
- **Generic "trend following"** - retail, no edge hypothesis

### Setup Priority Ranking for Development

| Rank | Setup | Why This Order | Complexity | Edge Plausibility | Data Ready |
|---|---|---|---|---|---|
| 1 | absorption_continuation | Complements sweep-reclaim (trend vs range), high plausibility, moderate complexity | Medium | High | ✅ Yes |
| 2 | compression_breakout | Clear structure hypothesis (ATR compression), high edge if executed correctly | Medium | High | ✅ Yes |
| 3 | crowded_unwind | Strong data (funding, OI, liquidations), but timing is hard | High | Medium | ✅ Yes |
| 4 | failed_breakout_trap | Requires precise sweep detection refinement, similar to sweep-reclaim | Medium | Medium | ⚠️ Needs work |
| 5 | exhaustion_reversal | Counter-trend risk high, needs strong confirmation | High | Medium | ✅ Yes |

---

## C. Recommended Phase 2 Setup Definition

### Setup Name: `absorption_continuation_long`

**NOT:** "Buy when price pulls back to EMA in uptrend"  
**YES:** "Enter on controlled pullback absorption after liquidity confirms trend participation"

### Institutional Hypothesis

**Market Structure Context:**
- Established uptrend (price > EMA200, EMA50 > EMA200, positive slope)
- Price performs **controlled retest** (not distribution) to value zone / liquidity level
- Pullback does NOT trigger crowded leverage unwind (funding stable, OI stable or rising)
- Absorption occurs: sellers absorbed by buyers at support (CVD/TFI confirms)
- Continuation trigger: price resumes upward after successful test

**Who Is Trapped/Late:**
- **Pullback sellers** who fade the trend without confirmation
- **Early shorts** who assume reversal before support tested
- **Late trend buyers** who chase after continuation already resumed (we enter BEFORE obvious move)

**What We Exploit:**
- **Liquidity-supported pullback**: Smart money accumulates during controlled retest
- **Absorption confirmation**: TFI/CVD shows buyers stepping in, not distribution
- **Structural invalidation**: Clear level below which trend hypothesis fails

**Why Edge Exists:**
- Retail waits for "breakout confirmation" (enters late, worse RR)
- We enter on **controlled pullback**, not after obvious continuation
- If absorption fails → structure invalidates → we exit with small loss
- If absorption succeeds → trend resumes → we capture early move with good RR

### Setup Logic (Institutional-Grade)

#### Regime Filters (HARD GATES)

```python
regime_allowed = [
    "uptrend",  # Primary target
    # "normal" if trend structure present (secondary)
]

regime_blocked = [
    "crowded_leverage",  # Too much risk
    "compression",       # Wrong structure
    "downtrend",         # Wrong direction
]
```

#### Trend Structure Filters

```python
# Trend established
price > ema200_4h
ema50_4h > ema200_4h
ema200_slope > threshold  # e.g., 0.0001 (positive slope)

# Trend not overextended (room to run)
price < ema200_4h * (1 + max_extension_pct)  # e.g., 1.05 (within 5%)

# NOT parabolic exhaustion
funding_8h < funding_extreme_threshold  # e.g., 0.0005 (not crowded long)
oi_zscore_60d < oi_extreme_threshold    # e.g., 2.0 (not blow-off top)
```

#### Pullback Structure

```python
# Controlled pullback to value zone
pullback_depth_pct = (recent_high - current_price) / recent_high
pullback_depth_pct in [pullback_min, pullback_max]  # e.g., [0.005, 0.03] (0.5-3%)

# Pullback to liquidity level (NOT arbitrary)
price_near_ema50 = abs(price - ema50_4h) / atr_4h < proximity_threshold  # e.g., 0.5 ATR
OR
price_near_equal_low = any(abs(price - lvl) / atr_4h < 0.3 for lvl in recent_equal_lows)

# Pullback did NOT break structure
price > prior_swing_low  # Maintains higher lows
```

#### Absorption Confirmation (CRITICAL)

```python
# CVD shows buying pressure during pullback
cvd_15m_slope > 0  # Buyers stepping in
OR
cvd_bullish_divergence == True  # Price down, CVD up = absorption

# TFI confirms directional interest
tfi_60s > tfi_threshold  # e.g., 0.3 (bullish flow)

# Volume/OI shows participation, not exhaustion
oi_delta_pct >= 0  # OI stable or rising (not unwinding)
```

#### Continuation Trigger

```python
# Price resumes upward after successful test
price > entry_trigger_price  # e.g., recent_swing_high or ema50 + buffer

# OR wait for retest completion signal
# (price touches support, then starts rising with TFI confirmation)
```

#### Veto Conditions (OVERRIDE - No Entry)

```python
# Crowded leverage risk
funding_8h > funding_crowd_threshold  # e.g., 0.0008 (too crowded long)
OR
oi_zscore_60d > oi_crowd_threshold    # e.g., 2.5 (OI blow-off)

# Volatility explosion (loss of control)
atr_4h_norm > volatility_panic_threshold  # e.g., 0.008 (8bps norm ATR = panic)

# Liquidation cascade active
force_order_spike == True AND force_order_rate_60s > liquidation_threshold

# Sweep without reclaim (failed support test)
sweep_detected == True AND sweep_side == "LOW" AND reclaim_detected == False
```

#### Entry Construction

```python
# Entry: at or slightly above pullback low (support confirmed)
entry_price = pullback_low + (entry_offset_atr * atr_15m)

# Stop: below pullback low OR below structural level
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

### Reasons[] Taxonomy

Every signal must include structured reasons:

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
    
    # Pullback structure
    f"pullback_depth_pct={pullback_depth_pct:.4f}",
    f"price_near_ema50_atr={abs(price - ema50_4h) / atr_4h:.2f}",
    f"maintains_higher_lows={price > prior_swing_low}",
    
    # Absorption confirmation
    f"cvd_bullish_divergence={cvd_bullish_divergence}",
    f"tfi_60s={tfi_60s:.3f}",
    f"oi_delta_pct={oi_delta_pct:.4f}",
    
    # Risk checks
    f"funding_8h={funding_8h:.6f}",
    f"oi_zscore_60d={oi_zscore_60d:.2f}",
    f"atr_4h_norm={atr_4h_norm:.6f}",
    
    # Entry quality
    f"rr_ratio={rr_ratio:.2f}",
]
```

### Metrics That Prove/Disprove Edge

#### Per-Regime Performance (PRIMARY)

| Regime | Expected Behavior |
|---|---|
| **uptrend** | ER > 1.5, trades >> sweep-reclaim in uptrend, primary edge source |
| **normal** | ER > 1.0 IF trend structure present, otherwise avoid |
| **range** | ER ~ 0.0 to -0.5 (acceptable bleed, should NOT be primary edge) |
| **crowded_leverage** | Zero trades (hard veto) |
| **compression** | Zero trades (hard veto) |
| **downtrend** | Zero trades (long-only setup) |

#### Overlap Analysis with Sweep-Reclaim

```python
# Measure per decision cycle:
overlap_signals = count(absorption_continuation AND sweep_reclaim both generate signal)
total_signals = count(either generates signal)
overlap_rate = overlap_signals / total_signals

# Target: overlap_rate < 20%
# If > 50%, setups are too similar (reject)
```

#### Pullback Structure Distribution

```python
# Are we entering on controlled pullbacks or random noise?
histogram(pullback_depth_pct for winning_trades)
histogram(pullback_depth_pct for losing_trades)

# Expect: winning trades cluster at specific pullback depths (structure)
# Reject if: uniform distribution (no structure edge)
```

#### Absorption Confirmation Hit Rate

```python
# How often does CVD/TFI confirmation actually predict continuation?
absorption_confirmed_wins = count(cvd_bullish_divergence==True AND pnl_r > 0)
absorption_confirmed_total = count(cvd_bullish_divergence==True)
absorption_hit_rate = absorption_confirmed_wins / absorption_confirmed_total

# Target: > 55%
# If < 50%, absorption confirmation is noise
```

#### Trend Day Capture

```python
# Did we catch the 2026-05-11 trend day?
# Define "trend day": price moves > 1.5% in one direction, funding/OI stable
trend_days = identify_trend_days(date_range)
trend_days_captured = count(absorption_continuation generated signal on trend_day)
capture_rate = trend_days_captured / len(trend_days)

# Target: > 50%
# This is THE success metric for Phase 2
```

### Comparison Requirements vs Sweep-Reclaim

| Dimension | Sweep-Reclaim | Absorption-Continuation | Test |
|---|---|---|---|
| **Primary regime** | range, post_liquidation | uptrend | Orthogonal ✅ |
| **Market structure** | liquidity sweep → reversal | controlled pullback → continuation | Opposite ✅ |
| **Entry timing** | After sweep reclaim confirmed | During pullback absorption | Different ✅ |
| **Edge hypothesis** | Fade late breakout chasers | Join early trend continuation | Complementary ✅ |
| **Overlap rate** | — | Target < 20% | Measure in backtest |
| **Regime coverage** | Weak in uptrend | Strong in uptrend | Fills gap ✅ |

**Key validation question:**  
On 2026-05-11 (BTC +2k USD trend day), sweep-reclaim generated 0 trades. Would absorption-continuation have generated 1-2 high-quality entries?

---

## D. Institutional Edge Filter Framework

### Three-Tier Signal Classification

#### Tier 1: Retail/Common Signal (AVOID)

**Characteristics:**
- Indicator-only logic ("RSI oversold, buy")
- No market structure context
- No participant behavior hypothesis
- No liquidity awareness
- Entry after move is obvious

**Examples:**
- "Price crosses above 50 EMA → buy"
- "MACD crossover → buy"
- "Price makes new high → buy breakout"

**Why retail:**
- Everyone sees it at same time
- No edge (crowd entry = liquidity provider exit)
- No structural invalidation level

#### Tier 2: Valid But Weak Signal (USE WITH CAUTION)

**Characteristics:**
- Has structure hypothesis, but weak confirmation
- Some liquidity awareness, but incomplete
- Entry timing still late or imprecise
- Acceptable for diversification, not primary edge

**Examples:**
- "Price pulls back to EMA in uptrend → buy" (without absorption confirmation)
- "ATR compresses below threshold → await breakout" (without OI/funding context)
- "Funding rate extreme → fade" (without liquidation cascade timing)

**Why weak:**
- Structure hypothesis exists, but missing critical confirmation
- Timing too generic (retail can copy)
- No clear "who is trapped" answer

#### Tier 3: Institutional-Grade Signal (TARGET)

**Characteristics:**
- Clear market structure hypothesis
- Explicit participant behavior model ("who is trapped/late")
- Liquidity-confirmed entry (CVD, TFI, OI, funding)
- Entry BEFORE move is obvious to retail
- Structural invalidation level (stop is logical, not arbitrary)
- Timing exploits asymmetry

**Examples:**
- **Absorption-continuation:** "Controlled pullback to liquidity level + CVD divergence + TFI confirms → enter before continuation obvious"
- **Sweep-reclaim:** "Liquidity sweep below equal lows + reclaim above + TFI flip → fade late breakout chasers"
- **Crowded-unwind:** "Funding > 90th percentile + OI Z-score > 2.5 + liquidation spike starts → fade overleveraged crowd"

**Why institutional:**
- Exploits information asymmetry (we see absorption before retail sees "breakout")
- Clear counterparty (we fade trapped participants)
- Entry timing is structural, not obvious
- Stop level is structural (not arbitrary ATR)

### Formalizing Institutional Signal Checklist

Every setup must answer these questions:

| Question | Purpose | Reject if... |
|---|---|---|
| **1. What is the market structure context?** | Defines when setup is valid | "Any market" (too generic) |
| **2. Who is trapped, forced, or late?** | Identifies counterparty | "No clear counterparty" |
| **3. What confirms the setup?** | Proves hypothesis before entry | "Indicator only, no liquidity confirmation" |
| **4. Why is our entry timing better than retail?** | Defines edge | "We enter after obvious to everyone" |
| **5. What invalidates the hypothesis?** | Defines structural stop | "Arbitrary ATR stop" |
| **6. What data proxies prove/disprove this?** | Enables measurement | "No measurable hypothesis" |

**Example Application: Trend-Continuation**

| Question | Retail Answer (REJECT) | Institutional Answer (ACCEPT) |
|---|---|---|
| **Structure context?** | "Uptrend" | "Uptrend + price near EMA50/liquidity level + funding not crowded" |
| **Who is trapped?** | "Not specified" | "Pullback sellers who fade without confirmation" |
| **What confirms?** | "Price crosses EMA" | "CVD bullish divergence + TFI impulse (absorption proof)" |
| **Why better timing?** | "We buy breakout with everyone" | "We enter during pullback absorption, before continuation obvious" |
| **What invalidates?** | "Price goes down" | "Price breaks prior swing low (structure failed)" |
| **Measurable proxy?** | "EMA only" | "CVD divergence rate, TFI hit rate, pullback depth distribution" |

---

## E. Research Acceptance Gates

### Hard Gates (MUST PASS ALL)

| Gate | Criterion | Measurement | Blocking if... |
|---|---|---|---|
| **Regime Edge** | ER > 1.5 in uptrend | Per-regime ER calculation | ER < 1.5 in target regime |
| **Trade Coverage** | Trades in uptrend >> sweep-reclaim in uptrend | Count signals per regime | Uptrend trades < 20 |
| **Trend Day Capture** | Captures ≥50% of clean trend days | Define trend day (price > 1.5%, funding stable), measure capture | Capture < 50% |
| **Overlap Control** | Overlap with sweep-reclaim < 30% | Count dual-signal cycles / total | Overlap > 30% (too similar) |
| **Range Bleed** | ER in range regime > -1.0 | Per-regime ER in range/normal | ER < -1.0 (bleeds too much) |
| **Walk-Forward Pass** | 2/2 windows pass, not fragile | Standard WF protocol | Any window fails |
| **Safety Flags** | No blocking flags | Standard safety checks | `pnl_sanity_review_required=True` |
| **Explainability** | Every signal has reasons[] | Validate reasons present | Empty reasons or generic |
| **Structural Stop** | Stop levels are structure-based, not arbitrary | Verify stop logic | All stops = entry ± fixed ATR |

### Soft Criteria (Prefer Higher Score)

| Criterion | Target | Weight |
|---|---|---|
| Uptrend ER | > 2.0 | High |
| Uptrend Sharpe | > 8.0 | Medium |
| Uptrend DD | < 8% | Medium |
| Win rate | 50-65% | Low |
| Absorption confirmation hit rate | > 55% | High |
| OOS degradation | < 30% | Medium |
| Trade count per validation window | > 20 | Medium |
| Pullback depth distribution | Clear clustering | Medium |

### Red Flags (Scrutiny or Reject)

| Flag | Meaning | Action |
|---|---|---|
| **Uniform pullback distribution** | No structure edge | REJECT - edge is noise |
| **High overlap with sweep-reclaim** | Setups are too similar | REJECT - not orthogonal |
| **Range ER positive** | Edge is not regime-specific | WARN - may be overfitting |
| **Absorption confirmation < 50%** | CVD/TFI not predictive | REJECT - confirmation is noise |
| **Trend day capture < 30%** | Setup misses target structure | REJECT - doesn't solve problem |
| **OOS ER >> IS ER** | Lucky validation period | SCRUTINIZE - possibly fragile |

---

## F. What Codex Should Implement Next

### Phase 2 Scope (Research-Only)

**Target files:**
- `research_lab/setups/` (new directory)
  - `research_lab/setups/__init__.py`
  - `research_lab/setups/absorption_continuation.py`
  - `research_lab/setups/base_setup.py` (shared interface)
- `research_lab/backtest_setup_comparison.py` (new script)
- `tests/test_research_lab_absorption_continuation.py`
- `docs/research/ABSORPTION_CONTINUATION_HYPOTHESIS.md`

**Implementation checklist:**

1. **BaseSetup Interface** (shared across future setups)
```python
class BaseSetup:
    def check_regime_allowed(self, regime: str) -> bool
    def evaluate_structure(self, features: Features, snapshot: MarketSnapshot) -> bool
    def generate_signal_candidate(self, ...) -> SignalCandidate | None
    def get_reasons(self) -> list[str]
    def get_setup_type(self) -> str
```

2. **AbsorptionContinuation Implementation**
- Implement all filters from section C above
- Generate signal candidates with full reasons[]
- **DO NOT** integrate into live orchestrator (research-only)

3. **Backtest Harness**
- Run backtest with **absorption_continuation ONLY** (not mixed with sweep-reclaim)
- Date range: 2022-01-01 → 2026-03-29 (same as grid)
- Output per-regime metrics
- Output overlap analysis vs sweep-reclaim (load sweep-reclaim signals from baseline trial-00095)

4. **Validation**
- Walk-forward: 2 windows (2022-2024 train, 2024-2025 test; 2022-2025 train, 2025-2026 test)
- Trend day capture analysis (identify trend days, measure capture rate)
- Pullback depth distribution histogram
- Absorption confirmation hit rate

5. **Comparison Report**
- Side-by-side: absorption_continuation vs sweep-reclaim
- Per-regime: ER, PF, DD, trades, Sharpe
- Overlap rate
- Trend day capture comparison
- Structural differences (entry timing, market context)

6. **Smoke Tests**
- Test setup logic on known trend days (e.g., 2026-05-11)
- Verify reasons[] completeness
- Verify no live-path side effects

### Timeline Estimate

- **BaseSetup + AbsorptionContinuation implementation:** 2-3 days
- **Backtest harness + metrics:** 2-3 days
- **Walk-forward + validation:** 1-2 days
- **Comparison report + analysis:** 1-2 days
- **Total:** 6-10 days (research-only, no production changes)

### Builder Note

Focus on **hypothesis quality**, not parameter tuning. If initial parameters don't show edge, **iterate hypothesis** (e.g., refine absorption confirmation logic), don't grid-search parameters blindly.

---

## G. What Must Explicitly Remain Out of Scope

### DO NOT IMPLEMENT in Phase 2

1. **Live orchestrator integration**
   - No changes to `orchestrator.py`
   - No changes to `signal_engine.py`
   - No routing absorption_continuation signals to live execution

2. **Multi-setup dispatcher/arbiter**
   - Phase 2 is research-only for ONE setup
   - Dispatcher comes in Phase 2.5 (after validation)

3. **Production parameter promotion**
   - No changes to `settings.py`
   - No `--promote` or auto-application of parameters

4. **Short-side logic**
   - Phase 2 is `absorption_continuation_LONG` only
   - Short variant (if needed) comes later after long validates

5. **Advanced features not yet available**
   - Orderbook imbalance (not in current Features)
   - Tick-level data (not in current pipeline)
   - Session-specific logic (can note as future enhancement, but don't block on it)

6. **Premature optimization**
   - Don't grid-search 50 parameters
   - Start with hypothesis-driven defaults
   - Iterate hypothesis if edge is weak, don't optimize blindly

### Research Lab Boundary

Phase 2 work stays in:
- `research_lab/**`
- `tests/test_research_lab*`
- `docs/research/**`
- `docs/audits/**` (after Claude Code audit)

Phase 2 does NOT touch:
- `core/signal_engine.py`
- `orchestrator.py`
- `execution/**`
- `governance/**`
- `risk/**`
- `settings.py`

---

## H. Open Questions & Missing Data Dependencies

### Questions Requiring User/Codex Decision

1. **Pullback depth range**: What is "controlled" pullback?
   - Proposed: 0.5-3% retracement
   - Needs: Empirical validation from historical trend days
   - Decision: Codex can start with proposal, iterate based on backtest

2. **Absorption confirmation threshold**: How strong must CVD/TFI signal be?
   - Proposed: `tfi_60s > 0.3` AND (`cvd_bullish_divergence` OR `cvd_15m_slope > 0`)
   - Needs: Backtest to measure hit rate
   - Decision: Start conservative, relax if too restrictive

3. **Trend overextension limit**: How far above EMA200 is "too far"?
   - Proposed: `price < ema200 * 1.05` (within 5%)
   - Needs: Distribution analysis of winning vs losing trades
   - Decision: Start with 5%, adjust if data shows different threshold

4. **Entry trigger timing**: Enter during pullback or wait for continuation signal?
   - Option A: Enter when absorption confirmed (during pullback)
   - Option B: Wait for price to start rising after pullback
   - Decision: Start with Option A (better RR), measure vs Option B

5. **Overlap tolerance**: How much overlap with sweep-reclaim is acceptable?
   - Proposed: < 30%
   - Rationale: Some overlap expected (both exploit liquidity), but should be minority
   - Decision: Measure actual overlap, adjust if pathological

### Missing Data Dependencies (Future, Not Blocking Phase 2)

1. **Orderbook imbalance**: Not currently in Features
   - Would improve absorption confirmation
   - Future enhancement, not required for Phase 2

2. **Session/time-of-day effects**: Not currently tracked
   - May improve edge (e.g., avoid illiquid hours)
   - Future enhancement, start agnostic

3. **Tick-level force orders**: Currently 60s aggregated
   - Higher resolution may improve liquidation cascade timing
   - Future enhancement for crowded_unwind setup

4. **Historical equal levels database**: Currently computed per cycle
   - Pre-computed level map may improve liquidity zone identification
   - Future optimization, not blocking

5. **Volatility regime transitions**: Currently static bucketing
   - Dynamic compression/expansion detection may improve breakout setup
   - Future enhancement for Phase 4

### Data Available and Sufficient for Phase 2

✅ **ATR** (15m, 4h, normalized) - volatility context  
✅ **EMAs** (50, 200) - trend structure  
✅ **CVD** (15m, divergences) - absorption confirmation  
✅ **TFI** (60s) - flow direction  
✅ **Funding** (8h, SMAs, percentile) - crowding risk  
✅ **OI** (value, Z-score, delta) - participation/exhaustion  
✅ **Force orders** (rate, spike, decreasing) - liquidation context  
✅ **Equal levels** (highs, lows) - liquidity structure  

**Verdict: Current data is SUFFICIENT for Phase 2 absorption_continuation research.**

---

## I. Final Recommendations

### Phase 2 Approval: YES, with Hypothesis Refinement

**PROCEED with TREND-CONTINUATION-RESEARCH-V1, renamed to ABSORPTION-CONTINUATION-RESEARCH-V1**

**Why:**
1. Fills strategic gap (uptrend regime coverage)
2. Orthogonal to sweep-reclaim (different structure, different regime)
3. Data is available and sufficient
4. Hypothesis is testable and measurable
5. Research-only approach is low-risk

**Critical success factor:**  
Setup must answer "who is trapped" and "why is our timing better than retail". If backtest shows edge is generic "buy pullback" without absorption confirmation, **REJECT and iterate hypothesis**, don't just optimize parameters.

### Builder Handoff Ready

After this consultation, Codex has:
- Clear setup hypothesis (absorption_continuation_long)
- Institutional-grade logic (section C)
- Acceptance gates (section E)
- Implementation scope (section F)
- Out-of-scope boundaries (section G)
- Measurable validation criteria (section D, E)

**Next step: Generate formal Codex handoff for ABSORPTION-CONTINUATION-RESEARCH-V1**

### Long-Term Portfolio Vision

Target state (12-18 months):
1. **sweep_reclaim** - range/liquidity specialist (DONE)
2. **absorption_continuation** - trend specialist (Phase 2)
3. **compression_breakout** - volatility expansion (Phase 4)
4. **crowded_unwind** - funding/OI stress relief (Phase 5)
5. **failed_breakout_trap** - false breakout fade (Phase 6)
6. **exhaustion_reversal** - overextension mean revert (Phase 7)

Each setup:
- Has independent edge hypothesis
- Targets specific market structure
- Generates own reasons[]
- Validated through WF + safety gates
- Managed by deterministic arbiter (Phase 3)
- Measured in portfolio context (Phase 4)

**This is not a collection of "strategies", it is a microstructure-aware trading system.**

---

**Consultation complete. Ready for Codex handoff generation.**

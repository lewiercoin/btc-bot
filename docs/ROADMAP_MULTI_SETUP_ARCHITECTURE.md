# Roadmap: Multi-Setup Portfolio Architecture

Date: 2026-05-11  
Architect: Codex  
Auditor: Claude Code  
Status: Approved, Phase 1 closed, Phase 2 ready  

## Vision

Evolve bot from **single-strategy** (sweep-reclaim only) to **portfolio of setups**, each optimized for specific market regimes.

**Core Principle:**
> "Each setup must prove edge independently before we optimize the portfolio."

---

## Current State (Before Roadmap)

**What We Have:**
- ✅ Infrastructure: regime detection, data pipeline, feature engine, governance, risk, storage, audit
- ✅ Setup #1: sweep-reclaim (liquidity hunt, range days)

**What's Missing:**
- ❌ Setup for trend days (like 2026-05-11: +2k USD, 0 trades)
- ❌ Setup for breakout/compression
- ❌ Setup for mean reversion extremes
- ❌ Multi-setup architecture (selector, per-setup metrics, conflict resolution)

**Problem Identified (2026-05-11):**
- BTC trend day +2k USD → bot generated 0 trades
- Not a bug, but **strategic mismatch**: sweep-reclaim has no edge in clean trend days
- Grid search optimizes sweep-reclaim but won't solve trend days

---

## Phases

### Phase 1: Sweep-Reclaim Stabilization

**Status:** Closed 2026-05-12  
**Audit:** `docs/audits/AUDIT_GRID_SEARCH_TRIAL00095_2026-05-12.md`  
**Decision record:** `docs/analysis/POST_GRID_PORTFOLIO_PLAN_2026-05-12.md`  

**Goal:**
- Complete constrained grid search
- Decide: keep baseline trial-00095 OR deploy improved candidate
- **DO NOT** over-tune sweep-reclaim for trend days (wrong strategy)

**Deliverables:**
1. **Decision:** Keep baseline OR PAPER candidate (after audit)
2. **Trade-off map:** Frequency vs ER/DD for sweep-reclaim parameter space
3. **Audit report:** Claude Code evaluates grid output with hard gates

**Acceptance Criteria:**
- Candidate must pass: trades ≥271, ER [1.5-5.0], DD ≤7.5%, PF ≤6.0, no blocking flags
- If no clean candidate → baseline trial-00095 stays
- Sweep-reclaim strategy understood and bounded (we know its limits)

---

**Outcome:**
- Grid evaluated 60 constrained combinations around `trial-00095`.
- 12 candidates passed full-range gates; 10 were walk-forward evaluated.
- 0 candidates qualified for promotion.
- High-frequency candidates increased trades by roughly 70-83%, but triggered blocking `pnl_sanity_review_required` and degraded ER/PF.
- Baseline `trial-00095` remains active in PAPER.
- Strategic conclusion: sweep-reclaim is a bounded liquidity-reclaim setup. It should not be over-tuned to trade clean trend-continuation days.

---

### Phase 2: Trend-Continuation Research

**Status:** Ready to start  
**Timeline:** 1-2 weeks  

**Goal:**
- Research-only setup #2 (trend-continuation)
- Separate backtest, separate WF validation
- **Zero impact on production** initially

**Hypothesis (Starting Point):**
```python
Setup: trend_continuation_long

Conditions:
- regime = "uptrend"
- price > EMA/SMA baseline (e.g., EMA200)
- EMA/SMA slope > 0 (positive trend)
- shallow pullback OR continuation trigger (price retraces to support, then resumes)
- TFI/CVD confirmation (flow returns positive, momentum confirmed)
- RR >= min_rr (risk-reward gate)
- NOT crowded_leverage_veto (governance unchanged)

Entry:
- On pullback retest + TFI/CVD flip positive

Exit:
- Stop: below swing low / ATR-based
- TP: trend target / trailing stop

Risk/Position Sizing:
- Same risk engine as sweep-reclaim
- Governance/risk gates unchanged
```

**Deliverables:**
1. **Candidate:** `trend_continuation_long` in Research Lab
2. **Report:** ER/PF/DD/trades per regime (especially uptrend vs others)
3. **Metrics:**
   - Does trend-continuation have edge in uptrend regime?
   - How many trend days would it catch? (e.g., 2026-05-11)
   - Does it lose money in range/chop?
   - WF validation: stable OOS?
4. **Decision (Claude Code):** reject / iterate / paper candidate

**Test Separately from Sweep-Reclaim:**
- Backtest trend-continuation alone (not mixed)
- Compare to sweep-reclaim:
  - Which regime does each win?
  - Are they negatively correlated? (good for portfolio)
  - Do they conflict? (both want entry on same bar?)

**Success Criteria:**
- ER > 1.5 in uptrend regime (at minimum)
- Trades in uptrend regime >> sweep-reclaim in uptrend
- Doesn't blow up in range/chop (acceptable DD)
- WF 2/2 pass, no blocking flags
- No production behavior change during research
- Signal reasons are explicit and setup-specific
- Results are compared against active sweep-reclaim baseline by regime and by overlap

---

### Phase 2.5: Minimal Multi-Setup Contract ⭐ **CRITICAL**

**Status:** Not started (after Phase 2 research, before production deploy)  
**Timeline:** Few days  

**Goal:**
- Prepare architecture so setup #2 is **not a hack**
- Define contracts, metrics, selector skeleton
- **Without this, second setup will be ad-hoc mess**

**What to Build:**

#### 1. `setup_type` as First-Class Field
```python
# In signal candidate, execution, trade_log:
setup_type: Literal["sweep_reclaim", "trend_continuation", ...]

# Not just a tag, but:
- Used in signal generation (dispatcher knows which logic to call)
- Stored in DB (queryable)
- Used in metrics (per-setup performance)
```

#### 2. Per-Setup `reasons[]`
```python
# For audit/debugging:
signal_candidate.reasons = [
    "setup_type=trend_continuation",
    "regime=uptrend",
    "price_above_ema200",
    "ema_slope_positive=0.0023",
    "pullback_depth_pct=0.012",
    "tfi_flip_positive",
    "cvd_confirms",
    "rr=2.8"
]

# Allows:
- Understanding WHY setup triggered
- Comparing rejection reasons across setups
- Auditing per-setup logic
```

#### 3. Per-Setup Metrics
```python
# Track separately:
- sweep_reclaim: ER, PF, DD, trades, win_rate, Sharpe
- trend_continuation: ER, PF, DD, trades, win_rate, Sharpe

# Per regime:
- sweep_reclaim in range vs trend
- trend_continuation in uptrend vs downtrend vs range

# Stored in DB:
setup_performance_metrics table
```

#### 4. Signal Candidates Pool
```python
# Each cycle:
candidates = []

# Setup #1 generates candidate (if conditions met):
if sweep_reclaim_conditions():
    candidates.append(sweep_reclaim_candidate)

# Setup #2 generates candidate (if conditions met):
if trend_continuation_conditions():
    candidates.append(trend_continuation_candidate)

# Arbiter selects:
selected = arbiter.select(candidates, context)

# Governance/risk can still veto:
if governance.veto(selected) or risk.veto(selected):
    selected = None
```

#### 5. Deterministic Conflict Rule
```python
# Minimal rule for Phase 2.5:
Rule: Max 1 BTC position at a time.

If multiple candidates:
- Rank by priority (e.g., regime-specific priority)
- OR rank by confluence score
- OR first-come-first-served (deterministic order)
- Select highest ranked

If position already open:
- No new entries (wait for close)

# More sophisticated rules in Phase 3.
```

**Deliverables:**
1. **Code:** Multi-setup dispatcher skeleton
2. **Schema:** DB changes (setup_type field, per-setup metrics table)
3. **Tests:** Smoke tests for multi-setup flow
4. **Docs:** Architecture doc (how to add setup #3, #4, etc.)

**Success Criteria:**
- Setup #2 integrates cleanly (no hacks)
- Per-setup metrics work
- Conflict rule is deterministic and auditable
- System is ready for setup #3, #4, etc. (extensible)

---

### Phase 3: Setup Selector / Arbiter

**Status:** Not started (after Phase 2.5, when setup #2 is validated)  
**Timeline:** 1-2 weeks after valid setup #2  

**Goal:**
- Multiple setups can generate candidates
- Arbiter selects best candidate OR rejects all
- Governance/risk remain final authority

**Selector Rules:**

#### Rule 1: Max 1 New Position per Symbol per Cycle
- No opening 2 positions on same symbol in one cycle
- If multiple candidates, choose one

#### Rule 2: No Duplicate Longs from Different Setups
- If sweep_reclaim says LONG and trend_continuation says LONG:
  - Choose one (by priority or score)
  - Don't double up

#### Rule 3: Regime-Based Priority
```python
priority_matrix = {
    "uptrend": ["trend_continuation", "sweep_reclaim"],
    "range": ["sweep_reclaim", "trend_continuation"],
    "downtrend": ["sweep_reclaim", "trend_continuation"],  # or add reversal setup
    "compression": ["breakout"],  # future setup #3
    # etc.
}
```

#### Rule 4: Every Reject is Auditable
```python
decision_outcome.setup_rejections = [
    {"setup": "sweep_reclaim", "reason": "no_sweep"},
    {"setup": "trend_continuation", "reason": "not_in_uptrend"}
]

# OR if candidates conflict:
decision_outcome.arbiter_decision = {
    "candidates": ["sweep_reclaim_long", "trend_continuation_long"],
    "selected": "trend_continuation_long",
    "reason": "regime_priority: uptrend favors trend_continuation"
}
```

**Deliverables:**
1. **Arbiter logic:** Production-grade selector
2. **Priority rules:** Configurable per regime
3. **Conflict resolution:** Deterministic, auditable
4. **Metrics:** Track arbiter decisions (how often each setup wins)
5. **Tests:** Multi-setup scenarios (conflicts, priorities, vetos)

**Success Criteria:**
- No arbitrary choices (all deterministic)
- No silent failures (all rejections logged)
- Governance/risk can still veto after selection
- Arbiter doesn't degrade single-setup performance (if only one candidate, no overhead)

---

### Phase 4: Portfolio-Level Evaluation

**Status:** Future (after multiple setups operational)  
**Timeline:** After 2-3 setups deployed, ongoing  

**Goal:**
- Evaluate strategy as **portfolio**, not individual setups
- Understand interactions, correlations, portfolio DD

**Metrics:**

#### 1. Correlation Between Setups
```python
# Are setups independent?
correlation_matrix = {
    ("sweep_reclaim", "trend_continuation"): -0.15,  # slightly negative = good
    ("sweep_reclaim", "breakout"): 0.32,
    ("trend_continuation", "breakout"): 0.58,
}

# Goal: negative or low positive correlation = diversification
```

#### 2. Portfolio Drawdown
```python
# Is portfolio DD < max(individual setup DD)?
individual_DD = {
    "sweep_reclaim": 6.5%,
    "trend_continuation": 8.2%,
    "breakout": 7.1%,
}

portfolio_DD = 5.8%  # < max(individual) due to diversification

# Goal: portfolio DD should be lower than worst setup (if uncorrelated)
```

#### 3. Performance by Regime
```python
# Which setup wins in which regime?
regime_performance = {
    "uptrend": {
        "trend_continuation": {"ER": 2.5, "trades": 45},
        "sweep_reclaim": {"ER": 0.8, "trades": 12},
    },
    "range": {
        "sweep_reclaim": {"ER": 2.1, "trades": 78},
        "trend_continuation": {"ER": -0.3, "trades": 8},  # loses in range
    },
}

# Goal: each setup wins in its regime, doesn't blow up in others
```

#### 4. Setup Contribution
```python
# How much does each setup contribute to total PnL?
contribution = {
    "sweep_reclaim": {"pnl": 45230, "share": 52%},
    "trend_continuation": {"pnl": 38120, "share": 43%},
    "breakout": {"pnl": 4350, "share": 5%},
}

# Goal: no single setup dominates (if one is 90%, others are noise)
```

#### 5. Does One Setup Hurt Another?
```python
# Counterfactual: what if we removed setup X?
portfolio_with_all = {"ER": 2.3, "DD": 5.8%, "Sharpe": 10.2}
portfolio_without_trend = {"ER": 1.9, "DD": 6.1%, "Sharpe": 8.5}

# Conclusion: trend_continuation improves portfolio (keeps it)
```

**Deliverables:**
1. **Dashboard:** Portfolio-level metrics (not just per-setup)
2. **Reports:** Regime breakdown, correlation matrix, contribution analysis
3. **Optimization:** Adjust setup weights/priorities based on portfolio metrics
4. **Research:** Identify gaps (which regimes are underserved?)

**Success Criteria:**
- Portfolio Sharpe > any individual setup Sharpe (diversification benefit)
- Portfolio DD < worst setup DD (uncorrelated helps)
- Each setup contributes meaningfully (no dead weight)
- Regime coverage: bot has edge in most regimes

---

### Phase 5+: Add More Setups (Iterative)

**Status:** Future, ongoing  
**Timeline:** Iterative, as needed  

**Candidate Setups:**

#### Setup #3: Breakout After Compression
```python
Conditions:
- regime = "compression"
- ATR at multi-week low (tight range)
- Volume/OI building
- Breakout of consolidation range
- TFI/CVD confirms direction
- Expansion of volatility

Edge: Catching explosive moves after consolidation
```

#### Setup #4: Mean Reversion Extreme
```python
Conditions:
- Price > 2-3 ATR from mean
- Funding rate extreme (> 90th percentile)
- OI exhaustion (Z-score peak)
- TFI reversal signal
- Opposite of momentum (fade the move)

Edge: Catching reversals after overextension
```

#### Setup #5: Funding/OI Unwind
```python
Conditions:
- Funding rate reset / normalization
- OI drop after peak
- Crowded position unwind
- Liquidation cascade

Edge: Catching the relief/counter-move after crowd capitulation
```

#### Setup #6: Trend Pullback
```python
Conditions:
- Strong trend (EMA slope high)
- Price pulls back to EMA/support
- NOT a reversal (trend still intact)
- TFI/CVD recovers
- Buy the dip in uptrend

Edge: Lower-risk entry in established trend
```

#### Future (Maybe): News/Offline Analysis
```python
# NOT in live decision loop, but:
- Macro events (FOMC, CPI, etc.)
- Onchain signals (exchange flows, whale moves)
- Sentiment shifts

# These could inform:
- Regime override (switch to defensive mode)
- Setup enable/disable (turn off momentum in risk-off)
- Position sizing adjustment (reduce size before FOMC)

# But NOT direct signals (too slow, not tick-by-tick)
```

**Process for Adding Setup #N:**
1. **Hypothesis:** Define edge, conditions, regime
2. **Research:** Backtest alone, measure ER/PF/DD/trades
3. **WF Validation:** Stable OOS?
4. **Audit:** Claude Code evaluates
5. **Integration:** Add to multi-setup dispatcher (uses Phase 2.5 contracts)
6. **Paper Test:** Monitor in PAPER mode
7. **LIVE Deploy:** After audit pass
8. **Monitor:** Track contribution, correlations, portfolio impact

---

## Key Principles

### 1. Each Setup Must Prove Edge Independently

**Before optimization:**
- Setup must have logical hypothesis (why it should work)
- Backtest shows positive ER in target regime
- WF validation confirms OOS stability
- No blocking safety flags

**After validation:**
- THEN optimize parameters (Optuna, grid, autoresearch)
- Don't search for "magic" - tune an existing edge

### 2. Don't Mix Setups Prematurely

**Wrong:**
- "Let's add trend-continuation AND breakout AND mean-reversion all at once"
- Can't tell which setup has edge, which is noise

**Right:**
- Add setup #2, test alone, validate
- Add setup #3, test alone, validate
- Then measure portfolio

### 3. Architecture Before Scale

**Phase 2.5 is critical:**
- Setup #2 could be "hacked in" without contracts
- But setup #3, #4, #5 would become unmaintainable
- Invest in clean architecture early

### 4. Regime-Specific Edge

**Each setup optimized for specific regime:**
- sweep_reclaim → range, liquidity hunt
- trend_continuation → uptrend, downtrend momentum
- breakout → compression → expansion
- mean_reversion → extremes, exhaustion

**Goal:** Portfolio has edge in ALL regimes (not just one)

---

## Success Metrics (Long-Term)

### System-Level:
- **Regime coverage:** Bot has positive ER in >=4 regimes
- **Portfolio Sharpe:** > 10 (better than any single setup)
- **Portfolio DD:** < 8% (diversification benefit)
- **Trade frequency:** 2-5 trades/day (not too sparse, not overtrading)

### Per-Setup:
- **ER > 1.5** in target regime
- **Win rate:** 40-65% (credible range)
- **Edge explainable:** Not black-box magic
- **OOS stable:** WF validation passes

### Architecture:
- **Extensible:** Adding setup #N takes days, not weeks (clean contracts)
- **Auditable:** Every decision traceable (setup, reason, arbiter choice)
- **Maintainable:** No spaghetti code, clean separation

---

## Timeline Summary

Update 2026-05-12: Phase 1 is closed. The constrained grid rejected all promotion candidates and retained baseline `trial-00095`. Phase 2 is ready to start.

Current status:

| Phase | Status | Timeline | Deliverable |
|---|---|---|---|
| **Phase 1** | Closed | Complete | Grid search -> keep baseline trial-00095 |
| **Phase 2** | Ready | 1-2 weeks | Trend-continuation research candidate |
| **Phase 2.5** | After research | Few days | Multi-setup contracts + dispatcher |
| **Phase 3** | After #2 valid | 1-2 weeks | Setup selector/arbiter production |
| **Phase 4** | Ongoing | After 2-3 setups | Portfolio-level evaluation |
| **Phase 5+** | Iterative | Ongoing | Add more setups as needed |

---

## Roles

| Role | Responsibility |
|---|---|
| **Codex (Builder)** | Implement setups, dispatcher, contracts, research |
| **Claude Code (Auditor)** | Audit each phase, WF validation, promotion decisions |
| **User (Product Owner)** | Approve milestones, decide on deployment, strategic veto |

---

## Current Status (2026-05-12)

- Phase 1 closed: constrained grid rejected all candidates; baseline `trial-00095` remains active.
- Phase 2 scoped: trend-continuation research is the next milestone.
- Production remains single-setup PAPER on sweep-reclaim until a new setup independently validates and Phase 2.5 contracts exist.
- Goal: multi-setup portfolio operational in 6-8 weeks after Phase 2 start, assuming at least one additional setup validates.

Historical status from 2026-05-11:

- ✅ Phase 1 in progress (grid search running)
- ⏳ Waiting for grid results
- 📋 Phase 2 scoped (trend-continuation hypothesis defined)
- 🎯 Goal: Multi-setup portfolio operational in 6-8 weeks

---

**Approved by:** Codex (Architect), Claude Code (Auditor)  
**Date:** 2026-05-11  
**Status:** Active Roadmap

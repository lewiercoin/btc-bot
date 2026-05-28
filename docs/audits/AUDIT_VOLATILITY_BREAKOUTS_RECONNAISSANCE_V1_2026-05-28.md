# AUDIT: VOLATILITY_BREAKOUTS_RECONNAISSANCE_V1

**Date:** 2026-05-28  
**Auditor:** Claude Code  
**Commit:** `fa5d774` (research: volatility breakouts reconnaissance V1)  
**Builder:** Codex  
**Type:** Quick reconnaissance (data + literature + metrics assessment)

---

## Verdict: ✅ DONE

**Reconnaissance quality:** Excellent  
**Recommendation validity:** PROCEED is justified  
**Deliverable completeness:** All 6 sections delivered

---

## Executive Summary

The reconnaissance report correctly identifies volatility breakouts as a viable direction for full planning, with important caveats about expected performance and prior failures. The data assessment is thorough, literature review is comprehensive, and recommendation is appropriately cautious.

**Key findings validated:**
- **Data:** SUFFICIENT (195,347 BTCUSDT 15m candles, 2020-2026, zero gaps, zero OHLC violations)
- **Literature:** MIXED (19 sources, 11 model-quality, supports planning not implementation)
- **Metrics:** MARGINAL (expected ER 1.2-2.0 vs trial-00095 ER 2.1, orthogonality potential)
- **Blockers:** NONE (prior failure documented as constraint, not blocker)
- **Recommendation:** PROCEED to planning (not diagnostic implementation)

**Critical finding:** Prior `VOLATILITY-BREAKOUT-RESEARCH-V1` failure (ER 0.52, 2026-05-13) documented. Creates constraint against ATR-slope rescue, but does not close broader family.

---

## Reconnaissance Audit Axes

### 1. Data Availability Assessment: ✅ PASS

**Coverage verification:**
- Primary database: `research_lab/data/crowded_unwind_backtest.db` inspected ✅
- BTCUSDT 15m candles: 195,347 rows (2020-09-01 to 2026-03-28) ✅
- Quality metrics: 0 gaps, 0 OHLC violations ✅
- Supporting data: aggtrade_buckets (195,150 rows), funding (6,105 rows), open_interest (524,971 rows) ✅

**Indicator feasibility:**
- Donchian Channels: ✅ (rolling high/low from candles)
- Bollinger Bands/BandWidth: ✅ (close + SMA + std dev)
- Keltner Channels: ✅ (EMA + ATR)
- ATR: ✅ (high/low/close)
- Volume confirmation: ✅ (candles.volume or aggtrade_buckets)
- TFI/CVD: ✅ (aggtrade_buckets)

**Missing data documented:**
- Tick data: not required ✅
- Order book: not required ✅
- Sentiment/news: not required ✅

**Verdict:** SUFFICIENT ✅

### 2. Literature Review: ✅ PASS

**Source count:** 19 sources inspected ✅

**Source classification:**
- Model-quality / benchmark: 11 sources ✅
- Opinion / vocabulary: 8 sources ✅
- Code implementations: 4 sources ✅
- Sources with metrics: 8 sources ✅

**Quality of sources:**

**Academic (strong):**
- Gerritsen et al. (Bitcoin range breakout forecasting power, Sharpe outperformance) ✅
- Arda (Bollinger regime-dependent) ✅
- Day et al. (Bollinger futures AHPR > 20-50%) ✅
- Poluri (Donchian + ATR risk management) ✅
- Low-volatility crypto strategies ✅

**Industry/Benchmark (useful):**
- Gate Research (Bollinger: 11 trades, PF 6.345, WR 81.82%) ✅
- Boring Edge (Donchian: 41 trades, PF 5.3, CAGR 48.2%, DD -53.7%) ✅
- Fractiz (Donchian: PF 0.97-1.56, WR 33-38%) ✅
- trustdan (trend-following: PF 1.47, failed fast breakout PF 0.131) ✅

**Code (directly inspectable):**
- richkuo/go-trader (Donchian implementation, shifted rolling high/low) ✅
- LazyBear BB/KC squeeze gist ✅
- TradingView scripts (Donchian breakout, BB squeeze) ✅

**Negative evidence documented:**
- CoinQuant ETH (Bollinger: 14 trades, PF 0.46, DD -27.79%, negative Sharpe) ✅
- trustdan failed variants (fast breakout PF 0.131, Keltner PF 0.744) ✅

**URLs embedded:** Yes ✅

**Lookahead risk assessed:** Yes (documented for each source) ✅

**Consensus:** MIXED (supports planning, not implementation) ✅

### 3. Mechanism Extraction: ✅ PASS

**Common patterns identified:**
- Donchian range breakout ✅
- Bollinger Band breakout ✅
- Bollinger BandWidth squeeze release ✅
- BB/KC squeeze release ✅
- ATR expansion breakout ✅
- Volume-confirmed range breakout ✅

**Timing model preliminary:**
- `range_detection_bar`: i-1 (last completed bar for range state) ✅
- `breakout_bar`: i (close breaks prior range) ✅
- `state_known_bar`: i (at breakout-bar close) ✅
- `entry_candidate_bar`: i+1 (first realistic bar after confirmation) ✅
- `return_start_bar`: i+1 ✅

**Critical timing note:** "Primary returns must never start from range start or intrabar breakout price unless that entry is explicitly tradable." ✅

**Preliminary candidates:**
1. `DONCHIAN_COMPRESSION_BREAKOUT_CONTINUATION` ✅
2. `BOLLINGER_BANDWIDTH_SQUEEZE_RELEASE` ✅
3. `BB_KC_SQUEEZE_DONCHIAN_BREAKOUT` ✅
4. `VOLUME_CONFIRMED_RANGE_BREAKOUT` ✅

**Most promising (report recommendation):**
- `VOLUME_CONFIRMED_RANGE_BREAKOUT` ✅
- `BB_KC_SQUEEZE_DONCHIAN_BREAKOUT` ✅

**Rationale:** Deterministic, locally testable, materially different from failed ATR-slope implementation ✅

### 4. Metrics Assessment: ✅ PASS

**Realistic ER/PF expectations documented:**
- Naive ER: 0.8-1.3 ✅
- Well-filtered ER: 1.2-2.0 ✅
- Optimistic ER: > 2.0 (selective only) ✅
- Realistic PF: 1.1-1.8 ✅
- PF > 4.0: suspicious until walk-forward validated ✅
- Win rate: 30-50% (trend continuation) ✅

**Sources for expectations:**
- Fractiz: PF 0.97-1.56 ✅
- Gate Research: PF 6.345 (short sample) ✅
- trustdan: PF 1.47 (best variants) ✅
- CoinQuant: PF 0.46 (negative example) ✅

**Comparison to trial-00095:**
- trial-00095: ER 2.1, PF 4.6, 271 trades, WR 56% ✅
- Volatility breakouts: likely lower WR, lower PF, potentially orthogonal ✅

**Assessment:** MARGINAL BUT POTENTIALLY ORTHOGONAL ✅

**Honesty:** Report explicitly states "unlikely to beat trial-00095 on raw PF without strict filtering" ✅

**Trade frequency expectations:**
- Daily Donchian: ~5 trades/year (industry source) ✅
- 15m squeeze + breakout + volume: ~2-8 events/month (to validate) ✅
- Strict BB/KC squeeze: ~1-4 events/month (to validate) ✅

**Risk characteristics documented:**
- False breakouts in choppy regimes ✅
- Lower win rate than reversal systems ✅
- Long losing streaks ✅
- Large drawdowns if stops wide + entries late ✅
- Regime dependence (trend/volatility) ✅
- Cost sensitivity if high frequency ✅

### 5. Data Gaps / Blockers: ✅ PASS

**Critical data gaps:** NONE ✅

**Available data sufficient for:**
- Donchian ranges ✅
- Bollinger Bands/BandWidth ✅
- Keltner Channels ✅
- ATR ✅
- Volume spikes ✅
- TFI/CVD confirmation ✅
- MFE/MAE accessibility ✅

**Not required initially:**
- Tick data ✅
- Order book ✅
- Force-order liquidation stream ✅
- Sentiment/news/on-chain ✅

**Computational complexity:** Acceptable (O(N) offline, O(1) online per bar) ✅

**Regulatory/exchange limitations:** None for offline research ✅

**Prior failure boundary documented:**
- `VOLATILITY-BREAKOUT-RESEARCH-V1` failed (2026-05-13, ER 0.52) ✅
- Failure reason: 15m ATR expansion detection entered mid-to-late expansion ✅
- Constraint: do NOT rerun ATR-slope as same hypothesis ✅
- Not a blocker: broader family includes distinct mechanisms ✅

**Overall assessment:** NO BLOCKERS ✅

### 6. Recommendation: ✅ PASS

**Verdict:** PROCEED ✅

**Rationale quality:** Excellent
- Acknowledges data is sufficient ✅
- Acknowledges literature supports planning (not implementation) ✅
- Acknowledges expected metrics weaker than trial-00095 ✅
- Acknowledges prior failure as constraint ✅
- Recommends cautious proceeding ✅

**Next milestone specified:** `VOLATILITY_BREAKOUTS_EDGE_DISCOVERY_V1_PLANNING` ✅

**Timeline estimated:** 3-5 days ✅

**Output specified:** Planning document only (no diagnostic code) ✅

**Key focus areas listed:**
1. Mechanism selection (one deterministic rule, reject ATR-slope rescue) ✅
2. Timing discipline (explicit bars, returns from realistic entry) ✅
3. MFE accessibility (70% threshold) ✅
4. Controls (4-5 deterministic controls) ✅
5. Benchmark comparison (vs trial-00095) ✅

**Boundaries clear:** "This report does not approve implementation, diagnostic code, production changes, trial-00095 modification, or promotion." ✅

---

## Critical Observations

### 1. Honesty About Prior Failure (Excellent)

**Report correctly identifies:**
- `VOLATILITY-BREAKOUT-RESEARCH-V1` failed on 2026-05-13 with ER 0.52
- Failure reason: 15m ATR expansion entered too late (mid-to-late expansion)
- Prior failure creates constraint: cannot rescue ATR-slope implementation
- Prior failure does NOT close broader family: Donchian/Bollinger/KC squeeze remain distinct

**This is model research discipline:** Acknowledge failure, extract lesson, avoid rescue, explore orthogonal mechanisms.

### 2. Realistic Metrics Expectations (Excellent)

**Report avoids optimism bias:**
- Expected ER 1.2-2.0 (below trial-00095 ER 2.1)
- Expected PF 1.1-1.8 (below trial-00095 PF 4.6)
- "unlikely to beat trial-00095 on raw PF without strict filtering"
- Orthogonality as potential value (different regimes, different holding periods)

**This is appropriate caution:** Don't oversell edge family before planning.

### 3. Literature Balance (Excellent)

**Report includes positive AND negative evidence:**
- Positive: Gerritsen (forecasting power), Day (AHPR 20-50%), Gate Research (PF 6.3)
- Negative: CoinQuant (PF 0.46), trustdan failed variants (PF 0.13)
- Mixed: Fractiz (PF 0.97-1.56, realistic whipsaw/risk)

**This is unbiased research:** Present full evidence, not cherry-picked successes.

### 4. Timing Discipline Awareness (Excellent)

**Report explicitly states:**
- "Primary returns must never start from range start or intrabar breakout price"
- "use prior/completed values only"
- "next-bar entry, not same-bar fill without evidence"
- Timing model: entry at i+1, returns from i+1 (not i or range start)

**This prevents lookahead:** Lessons from liquidation burst reversal applied.

### 5. Control Cohort Planning (Excellent)

**Report proposes 5 controls:**
1. Non-compression breakouts (isolate compression signal)
2. Compression without breakout (isolate breakout signal)
3. Breakout without volume confirmation (isolate volume signal)
4. Shifted-entry control (test timing)
5. Weak-close or opposite-flow breakout (test quality)

**This is strong experimental design:** Isolate each signal component.

---

## Minor Observations

### 1. Report Length: 496 Lines

**Target:** 300-500 lines ✅  
**Actual:** 496 lines ✅  
**Assessment:** Appropriate length for comprehensive reconnaissance.

### 2. ASCII-Only: ✅

**No unicode issues:** ✅  
**Git diff --check passed:** ✅  

### 3. URLs Embedded: ✅

**All 19 sources include URLs:** ✅  
**Accessible for audit:** ✅  

### 4. No Implementation Code: ✅

**Report is research only:** ✅  
**No diagnostic code:** ✅  
**No backtest code:** ✅  
**Boundary respected:** ✅  

---

## Recommended Next Step

**Accept PROCEED recommendation.**

**Next milestone:** `VOLATILITY_BREAKOUTS_EDGE_DISCOVERY_V1_PLANNING`

**Type:** Quant Research Planning (full planning document)

**Timeline:** 3-5 days

**Deliverables:**
1. Source research (20+ sources, mechanism extraction, lookahead assessment)
2. Mechanism selection (ONE deterministic rule: likely `VOLUME_CONFIRMED_RANGE_BREAKOUT` or `BB_KC_SQUEEZE_DONCHIAN_BREAKOUT`)
3. Repo data surface inspection (confirm coverage, gaps)
4. Extracted mechanism (deterministic rules, no future bars)
5. Timing model (6-bar model: range_detection/breakout/state_known/entry/return_start)
6. MFE accessibility design (before/after entry, 70% threshold)
7. Baseline comparison (vs trial-00095: ER/PF/trades/overlap)
8. Control cohorts (4-5 deterministic controls)
9. Pre-result invalidation criteria (STOP/EXPLORE/INCONCLUSIVE gates)
10. ONE recommendation (IMPLEMENT ONE DIAGNOSTIC or STOP)

**Constraints:**
- Do NOT rescue ATR-slope expansion (failed mechanism)
- Do NOT reopen `VOLATILITY-BREAKOUT-RESEARCH-V1` result
- Do NOT relax timing discipline (returns from realistic entry only)
- ONE mechanism per planning document (focus)

**Expected outcome:**
- If planning approved: Proceed to diagnostic implementation
- If planning rejected: Mechanism insufficiently justified, pivot to alternative

---

## Audit Metadata

**Auditor:** Claude Code  
**Date:** 2026-05-28  
**Commit audited:** `fa5d774`  
**File audited:** `docs/research/VOLATILITY_BREAKOUTS_RECONNAISSANCE_V1_REPORT.md` (496 lines)

**Audit duration:** Single-pass comprehensive review  
**Verdict confidence:** High (all reconnaissance criteria met, recommendation justified)

**Recommendation:** PROCEED to `VOLATILITY_BREAKOUTS_EDGE_DISCOVERY_V1_PLANNING`

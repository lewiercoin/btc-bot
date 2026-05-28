# AUDIT: REGIME_SHIFT_DETECTION_RECONNAISSANCE_V1

**Date:** 2026-05-28  
**Auditor:** Claude Code  
**Commit:** `72f5838` (research: regime shift detection reconnaissance V1 report)  
**Builder:** Codex  
**Type:** Quick reconnaissance (data + literature + metrics assessment)

---

## Verdict: ✅ DONE

**Reconnaissance quality:** Excellent  
**Recommendation validity:** PROCEED is justified  
**Deliverable completeness:** All 6 sections delivered

---

## Executive Summary

The reconnaissance report correctly identifies regime shift detection as having sufficient data and literature foundation for full planning, with appropriate methodology cautions. The data assessment is thorough, literature review is comprehensive (26 sources), and recommendation appropriately flags timing/leakage risks.

**Key findings validated:**
- **Data:** SUFFICIENT (195,347 BTCUSDT 15m candles, 195,150 aggtrade_buckets, funding/OI/force_orders, 0 gaps, 0 OHLC violations)
- **Literature:** STRONGER FOUNDATION THAN PRIOR FAMILIES (26 sources, 10 academic/model-quality, explicit HMM/GARCH support)
- **Mechanisms:** 5 regime families identified (volatility, trend/range, flow dominance, crowding/stress, HMM/GARCH)
- **Metrics:** PROMISING BUT HIGH METHODOLOGY RISK (standalone ER 0.8-1.5, filter lift approach recommended)
- **Blockers:** NONE for deterministic; tooling/methodology caution for HMM/GARCH
- **Recommendation:** PROCEED to planning with constraints (one mechanism, strict online knowability)

**Critical strength:** Report explicitly warns against post-hoc regime labeling, full-sample HMM smoothing, and state relabeling - the primary methodological risks in regime detection research.

---

## Reconnaissance Audit Axes

### 1. Data Availability Assessment: ✅ PASS

**Database inspection:**
- Primary database: `research_lab/data/crowded_unwind_backtest.db` inspected ✅
- Secondary database: `storage/btc_bot.db` inspected ✅
- Inspection method: read-only Python `sqlite3`, no diagnostic code ✅

**Coverage verification:**
- BTCUSDT 15m candles: 195,347 rows (2020-09-01 to 2026-03-28) ✅
- Quality: 0 gaps, 0 OHLC violations, 10 zero-volume bars ✅
- Aggtrade buckets 15m: 195,150 rows ✅
- Aggtrade buckets 60s: 2,927,122 rows ✅
- Funding: 6,105 rows ✅
- Open interest: 524,971 rows ✅
- Force orders: 146,864 rows (2022-2024 only, documented as partial) ✅

**Indicator feasibility (lines 62-82):**
- Deterministic: ATR, BB width, ADX, CHOP, realized vol, EMA slope ✅
- Flow: TFI, CVD, flow volatility, dominance shifts ✅
- Derivatives: funding extremes, OI z-score, liquidation stress ✅
- Model-based: HMM, GARCH, Markov-switching regression (tooling not installed, documented) ✅

**Package check (lines 84-93):**
- Installed: numpy, pandas ✅
- NOT installed: hmmlearn, arch, statsmodels, sklearn (documented) ✅
- Implication: deterministic feasible, HMM/GARCH requires dependency decision ✅

**Missing data documented (lines 95-99):**
- Order book: not required ✅
- Sentiment/search: not required ✅
- Force orders: partial (2022-2024 only) ✅
- Stored runtime labels: empty (raw data sufficient) ✅

**Verdict:** SUFFICIENT ✅

### 2. Literature Review: ✅ PASS

**Source count:** 26 sources inspected (exceeds 10-20 target) ✅

**Source classification (lines 144-150):**
- Academic/model-quality: 10 sources ✅
- Implementation/package references: 6 sources ✅
- TradingView/industry concept: 7 sources ✅
- Industry examples: 3 sources ✅
- Crypto-relevant sources: 9 sources ✅
- HMM/MS-GARCH sources: 12 sources ✅

**Quality of sources:**

**Academic (strong):**
- Hamilton (1989) Markov switching framework (JSTOR classic) ✅
- Dynamic volatility modelling of Bitcoin with TV-MS-GARCH (ScienceDirect) ✅
- Exploring predictability of cryptocurrencies via Bayesian HMMs (arXiv) ✅
- Modelling and predicting Bitcoin conditional variance (arXiv) ✅
- Hierarchical HMMs for bearish/bullish markets (arXiv) ✅
- Regime-Aware Adaptive Forecasting for Bitcoin (Springer) ✅
- Bitcoin Price Regime Shifts: Bayesian MCMC and HMM (MDPI) ✅

**Implementation (useful):**
- hmmlearn documentation (readthedocs) ✅
- statsmodels MarkovRegression docs (statsmodels.org) ✅
- arch volatility docs (readthedocs) ✅
- R MSGARCH package (rdocumentation) ✅
- hidden-regime Python package (GitHub) ✅

**TradingView/Industry (concept):**
- CHOP Filter ADX + Choppiness ✅
- Market Regime Detector Trend + Volatility ✅
- HMM Market Regimes LuxAlgo ✅
- K-Means Regime Detector ✅
- Market Regime Lite ✅
- Volatility Regime Classifier ✅

**Quant blogs (useful caution):**
- QuantStart HMM regime detection (R example) ✅
- PyMC Labs Bayesian HMM market regimes (explicit hindsight validation warning) ✅

**URLs embedded:** Yes, all 26 sources ✅

**Lookahead risk assessed:** Yes, for each source ✅

**Examples of lookahead assessment:**
- Hamilton: "high if smoothed states used as live labels" ✅
- TV-MS-GARCH: "model fit may be in-sample" ✅
- Bayesian HMMs: "must avoid smoothed hindsight states" ✅
- PyQuantLab HMM: "backtest setup needs audit" ✅
- TradingView HMM: "Pine implementation must be audited for repaint" ✅
- PyMC Labs: "explicitly separates validation from live accuracy" ✅

**Negative/mixed evidence included:**
- "Evidence that it creates a standalone tradable entry edge is weaker" (line 161) ✅
- "The safest research direction is regime as a conditional filter or transition event, not a direct price prediction label" (line 162) ✅

**Consensus:** MIXED BUT STRONGER FOUNDATION THAN PRIOR FAMILIES ✅

### 3. Mechanism Extraction: ✅ PASS

**Common regime families identified (lines 168-178):**
1. Volatility regime shift (ATR, realized vol, BB width) ✅
2. Trend/range transition (ADX, CHOP, EMA slope) ✅
3. Flow dominance shift (TFI, CVD) ✅
4. Crowding/stress regime shift (OI, funding, force_orders) ✅
5. Probabilistic HMM/GARCH state shift ✅

**Detection signals (lines 180-196):**
- Deterministic: ATR percentile, ADX/CHOP thresholds, EMA slope, TFI z-score, OI/funding extremes ✅
- Model-based: HMM filtered probability, GARCH forecast, Markov-switching filtered probability, K-means cluster ✅

**Timing model (lines 198-224):**

Deterministic (lines 199-207):
- detection_bar: i (metric crosses threshold) ✅
- state_known_bar: i at close ✅
- confirmation_bar: i or i+k if persistence required ✅
- entry_candidate_bar: state_known_bar + 1 ✅
- return_start_bar: same as entry_candidate_bar ✅

HMM/GARCH (lines 209-217):
- training_cutoff_bar: last bar in model fit ✅
- observation_bar: i (appended to feature stream) ✅
- state_known_bar: i (after online filtered probability computed) ✅
- entry_candidate_bar: i+1 ✅
- return_start_bar: i+1 ✅

**Forbidden practices (lines 220-224):**
- Full-sample HMM states as live labels ✅
- Smoothed probability P(state_t | data_0:T) for trading ✅
- Relabeling hidden states after seeing future returns ✅

**Preliminary candidates (lines 226-246):**
1. VOLATILITY_REGIME_TRANSITION_FILTER ✅
2. TREND_RANGE_STATE_SHIFT ✅
3. FLOW_DOMINANCE_REGIME_SHIFT ✅
4. FILTERED_HMM_REGIME_SHIFT ✅

**Most promising:** TREND_RANGE_STATE_SHIFT (deterministic) or FILTERED_HMM_REGIME_SHIFT (model-based with dependency) ✅

**Verdict:** COMPREHENSIVE MECHANISM EXTRACTION ✅

### 4. Metrics Assessment: ✅ PASS

**Realistic ER/PF expectations (lines 252-266):**
- Standalone regime-transition entry ER: 0.8-1.5 ✅
- Regime filter lift on another edge: meaningful if reduces drawdown without killing sample ✅
- Direct HMM strategy PF: likely unstable unless strict walk-forward ✅
- Deterministic trend/range filters: robust as filters, weaker as standalone alpha ✅

**Comparison to trial-00095 (lines 268-283):**
- Trial-00095: ER ~2.1, PF ~4.6, 271 trades, WR ~56% ✅
- Regime shift: likely cannot beat trial-00095 standalone ✅
- Best path: orthogonal edge, filter for trial-00095, risk sizing, setup selector ✅
- Assessment: POTENTIALLY USEFUL, NOT YET COMPETITIVE ✅

**Trade frequency expectations (lines 285-296):**
- Deterministic volatility/trend transitions: weekly to monthly ✅
- HMM state changes: potentially too frequent without persistence threshold ✅
- Funding/OI stress shifts: episodic, leverage cycles ✅
- Flow-dominance shifts: frequent but noisy at 15m ✅
- Expected sample: 100-400 high-confidence transitions ✅

**Risk characteristics (lines 298-308):**
- Detection lag, full-sample lookahead, state relabeling, overfitting thresholds/state count ✅
- Unstable hidden-state identity across retrains ✅
- Crypto regime instability ✅
- Sample-size collapse under high-confidence filters ✅
- Lesson from volume breakout: "good MFE accessibility does not prove predictive power" (lines 305-306) ✅

**Assessment:** PROMISING BUT HIGH METHODOLOGY RISK ✅

### 5. Data Gaps / Blockers: ✅ PASS

**Critical data gaps (lines 318-329):**
- None for deterministic OHLCV/flow regime research ✅
- Missing tools: hmmlearn, arch, statsmodels, sklearn (documented) ✅
- Missing data: order book, sentiment/search (not required) ✅
- Stored runtime labels: empty (raw data sufficient) ✅

**Blocker assessment:** NO for deterministic; PARTIAL for HMM/GARCH (dependency decision) ✅

**Missing indicators (lines 331-345):**
- Custom calculation required: ADX/DI, CHOP, realized vol, BB width, ATR percentile, Hurst, rolling flow, OI/funding z-scores ✅
- Feasible: YES ✅

**Computational complexity (lines 347-361):**
- Deterministic indicators: O(N), feasible online ✅
- ADX/CHOP/ATR percentiles: O(N) offline, incremental possible ✅
- HMM rolling fit: potentially expensive, caution online ✅
- GARCH rolling fit: expensive, offline first only ✅
- Real-time feasibility: deterministic YES, HMM/GARCH periodic retrain only ✅

**Overfitting and lookahead risks (lines 363-371):**
- High-risk patterns documented: choosing state count after results, mapping states with future returns, using smoothed states, threshold tuning after failure ✅
- Mitigations documented: define mechanism before results, train on past only, freeze state interpretation, use deterministic controls, measure MFE ✅

**Overall assessment:** NO DATA BLOCKERS, TOOLING/METHODOLOGY CAUTION ✅

### 6. Recommendation: ✅ PASS

**Verdict:** PROCEED ✅

**Rationale quality (lines 385-390):** Excellent
- Data sufficient ✅
- Literature foundation stronger than prior families ✅
- Acknowledges methodological risks ✅
- Caution about post-hoc regime labels ✅
- Timing discipline required ✅

**Next milestone specified:** REGIME_SHIFT_DETECTION_EDGE_DISCOVERY_V1_PLANNING ✅

**Timeline estimated:** 3-5 days ✅

**Output specified:** Planning document only (no diagnostic code) ✅

**Key focus areas (lines 398-408):**
1. Mechanism selection: ONE of deterministic TREND_RANGE_STATE_SHIFT, VOLATILITY_REGIME_TRANSITION_FILTER, or online-filtered FILTERED_HMM_REGIME_SHIFT ✅
2. Timing discipline: define bars, use filtered probabilities only for HMM/GARCH ✅
3. Control cohorts: volatility percentile baseline, ADX-only/CHOP-only baseline, shifted timing, same-state non-transition, opposite-regime transition ✅
4. Invalidation gates: STOP if state labels require future data, controls match/beat candidate, MFE consumed > 70%, weak standalone ER/PF ✅
5. Benchmark comparison: vs trial-00095, decide if standalone/filter/risk-regime before implementation ✅

**Boundaries clear (lines 426-429):** "This report does not approve implementation, diagnostic code, production changes, trial-00095 modification, dependency installation, or promotion. It recommends only a full planning milestone for one regime-shift mechanism." ✅

**Verdict:** RECOMMENDATION JUSTIFIED ✅

---

## Critical Observations

### 1. Honest About Methodology Risk (Excellent)

**Report explicitly warns (lines 13-16):**
- "The key feasibility issue is not data availability. It is timing and leakage."
- "Full-sample HMM smoothing, in-sample state relabeling, and post-hoc regime interpretation are not acceptable as trading signals."
- "If this family proceeds, the planning document must select one concrete mechanism and explicitly separate online-filtered regime probability from audit-only smoothed labels."

**This is model research discipline:** Identify the primary risk (lookahead) before proceeding, not after failing.

### 2. Forbidden Practices Explicit (Excellent)

**Lines 220-224 define forbidden practices:**
- Using full-sample HMM states as if known live
- Using smoothed probability P(state_t | data_0:T) for trading labels
- Relabeling hidden states after seeing future returns and measuring from the original bar

**This prevents the most common regime detection failures:** Post-hoc regime labeling is attractive (explains history beautifully) but invalid (not knowable live).

### 3. Lessons From Prior Failures Applied (Excellent)

**Lines 305-306:**
- "Important lesson from volume-confirmed breakout: good MFE accessibility does not prove predictive power; regime shift diagnostics must test whether the state adds information beyond ordinary volatility/trend controls."

**This shows learning:** The reconnaissance incorporates lessons from the STOP result 2 hours ago.

### 4. Literature Balance (Excellent)

**Report includes:**
- Positive: Hamilton classic, Bitcoin HMM papers, GARCH support
- Negative: "Evidence that it creates a standalone tradable entry edge is weaker" (line 161)
- Mixed: "The safest research direction is regime as a conditional filter or transition event, not a direct price prediction label" (line 162)
- Caution: PyMC Labs explicitly warns about hindsight validation (line 140)

**This is unbiased research:** Present full evidence, not cherry-picked successes.

### 5. Control Cohort Planning (Excellent)

**Lines 403-404 propose controls:**
- Simple volatility percentile baseline (isolate regime vs simple vol)
- ADX-only or CHOP-only baseline (isolate combination value)
- Shifted transition timing (test early detection value)
- Same-state non-transition control (isolate transition signal)
- Opposite-regime transition control (test directional hypothesis)

**This is strong experimental design:** Isolate each regime component, test against simple baselines.

### 6. Dependency Question Handled Appropriately (Good)

**Lines 84-93, 326-344:**
- hmmlearn, arch, statsmodels, sklearn NOT installed (documented)
- Blocker? NO for deterministic; PARTIAL for HMM/GARCH
- Deferred to planning: dependency decision is planning constraint, not reconnaissance blocker

**This is correct scoping:** Reconnaissance identifies dependency question, planning addresses it.

---

## Minor Observations

### 1. Report Length: 428 Lines

**Target:** 300-500 lines ✅  
**Actual:** 428 lines ✅  
**Assessment:** At upper end but appropriate for comprehensive reconnaissance with 26 sources.

### 2. ASCII-Only: ✅

**Builder reported:** ASCII-only check passed ✅  
**Git diff --check:** Builder reported passed ✅  

### 3. No Implementation Code: ✅

**Report is research only:** ✅  
**No diagnostic code:** ✅  
**No backtest code:** ✅  
**Boundary respected (line 29):** "no diagnostic code or backtests were implemented" ✅  

### 4. Source URL Quality: ✅

**All 26 sources include URLs:** ✅  
**Accessible for audit:** ✅  
**Mix of academic, implementation, industry:** ✅  

### 5. Mechanism Count: 4 Candidates

**Preliminary candidates:**
1. VOLATILITY_REGIME_TRANSITION_FILTER
2. TREND_RANGE_STATE_SHIFT
3. FLOW_DOMINANCE_REGIME_SHIFT
4. FILTERED_HMM_REGIME_SHIFT

**Planning guidance:** Choose ONE mechanism (line 400) ✅  
**Appropriate:** Reconnaissance identifies candidates, planning selects one ✅

---

## Recommended Next Step

**Accept PROCEED recommendation.**

**Next milestone:** `REGIME_SHIFT_DETECTION_EDGE_DISCOVERY_V1_PLANNING`

**Type:** Quant Research Planning (full planning document)

**Timeline:** 3-5 days

**Deliverables:**
1. Source research (20+ sources, mechanism extraction, lookahead assessment)
2. Mechanism selection (ONE mechanism: likely TREND_RANGE_STATE_SHIFT or FILTERED_HMM_REGIME_SHIFT)
3. Repo data surface inspection (confirm coverage, gaps)
4. Extracted mechanism (deterministic rules or online-filtered HMM, no future bars)
5. Timing model (explicit bars: detection/state_known/confirmation/entry/return_start)
6. MFE accessibility design (before/after entry, 70% threshold)
7. Baseline comparison (vs trial-00095: ER/PF/trades/overlap or filter lift design)
8. Control cohorts (5+ deterministic controls including simple baseline)
9. Pre-result invalidation criteria (STOP/EXPLORE/INCONCLUSIVE gates)
10. ONE recommendation (IMPLEMENT ONE DIAGNOSTIC or STOP)

**Constraints:**
- ONE mechanism only (TREND_RANGE_STATE_SHIFT or FILTERED_HMM_REGIME_SHIFT recommended)
- If HMM/GARCH: dependency decision required, strict walk-forward training, filtered probabilities only, smoothed labels audit-only
- If deterministic: ADX lag risk, threshold overfitting risk, simple baseline controls required
- Do NOT combine all regime ideas into one diagnostic
- Do NOT use full-sample HMM smoothing as trading signal
- Do NOT relabel hidden states after seeing outcomes
- Returns from realistic entry only (entry_candidate_bar, not detection_bar)

**Expected outcome:**
- If planning approved: Proceed to diagnostic implementation
- If planning rejected: Mechanism insufficiently justified or methodology risk too high, pivot to alternative

---

## Audit Metadata

**Auditor:** Claude Code  
**Date:** 2026-05-28  
**Commit audited:** `72f5838`  
**File audited:** `docs/research/REGIME_SHIFT_DETECTION_RECONNAISSANCE_V1_REPORT.md` (428 lines)

**Audit duration:** Single-pass comprehensive review  
**Verdict confidence:** High (all reconnaissance criteria met, recommendation justified, methodology risks explicitly flagged)

**Recommendation:** PROCEED to `REGIME_SHIFT_DETECTION_EDGE_DISCOVERY_V1_PLANNING`

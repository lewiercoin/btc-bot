# SMC SOURCE COVERAGE AND REVERSE ENGINEERING REVIEW

**Date:** 2026-05-27  
**Scope:** Research audit and decision memo only — no implementation  
**Context:** Post-mortem of V1 taxonomy + SMC sequence invalidations

---

## 1. Executive Verdict

**Did V1 taxonomy + SMC sequence fully exploit the source ideas?**

**NO.** The two completed diagnostics tested specific interpretations of SMC concepts, but did NOT exhaust the source space.

**What was tested:**

| Diagnostic | Tested Concepts | Entry Timing |
|------------|----------------|--------------|
| **V1 Taxonomy** | Confirmed pivots, liquidity levels, wick crossing, close-based BoS, immediate reclaim, delayed reclaim, true breakout | `detection_bar` and `label_available_bar` |
| **SMC Sequence** | Liquidity sweep → displacement → structure shift → FVG → mitigation/retest → entry | `entry_candidate_bar = mitigation_bar + 1` |

**What was NOT tested:**

1. **Early displacement entry** — entering at the impulse after sweep, not waiting for mitigation
2. **Flow-confirmed sweep classification** — using TFI/CVD/force-orders to distinguish absorption vs continuation sweeps
3. **Order block entry** — order block identification and entry timing separate from FVG mitigation
4. **Consequent encroachment (CE) / FVG midpoint** — entering at 50% FVG fill, not full mitigation
5. **Liquidity cluster quality** — not every equal level is equal; quality-based sweep filtering
6. **Multi-timeframe liquidity map** — HTF liquidity as context without regime filtering
7. **Breaker blocks / failed mitigation** — what happens when mitigation fails
8. **CHOCH vs MSS distinction** — true change of character vs minor structure shift
9. **Premium/discount entry timing** — HTF dealing range context for entry selection
10. **Session/killzone timing without filtering** — metadata correlation, not hard gates
11. **Recursive fractal hierarchy** — nested swing levels and priority ranking
12. **Sweep continuation vs reversal split** — directional classification post-sweep

**Which ideas are probably not worth testing:**

- **Detection-bar returns** (already proven to contain lookahead bias in V1)
- **Regime/session hard filters** (failed in May 2026 Singular Edge Assessment)
- **Parameter rescue of failed mitigation entry** (timing is structural, not parametric)
- **Discretionary visual patterns** (not algorithmic, not reproducible)

**Which ideas could still be worth a separate research plan:**

1. **Early displacement entry diagnostic** — test whether the impulse after sweep (displacement bar or displacement+1) is the accessible edge, not mitigation
2. **Flow-confirmed sweep continuation/reversal** — classify sweeps by TFI/CVD/force-order behavior at detection
3. **MFE accessibility meta-study** — reverse-engineer where in time the move occurs and what was knowable before it
4. **Liquidity cluster quality model** — test whether sweep edge varies by cluster characteristics (age, hits, span, proximity to HTF levels)

**Is there evidence-based reason to continue searching?**

**YES, with conditions:**

- The SMC sequence failure was NOT a blanket invalidation of all post-sweep edge
- The failure was SPECIFICALLY: "realistic mitigation entry arrives too late"
- Median MFE before entry (0.011565) >> MFE after entry (0.004916) proves the move exists but is inaccessible at mitigation
- The question is: **where in the sequence does the move become accessible, and where does it decay?**

This is NOT "Claude said stop." This is: **the tested entry timing failed, but the accessibility problem is not fully diagnosed.**

---

## 2. Source Coverage Matrix

| Source Idea | Source Origin | Tested V1? | Tested SMC? | Fully Tested? | Result | Notes |
|-------------|---------------|------------|-------------|---------------|--------|-------|
| **High/low pivot crossover** | Makuchaku/eFe, PyIndicators | ✅ YES | ✅ YES | ✅ YES | Event exists, no standalone edge | V1: wick cross median 0.000237; SMC: sweep detection works |
| **Close-based BoS** | Makuchaku/eFe, smart-money-concepts | ✅ YES | ✅ YES | ✅ YES | FAIL | V1: median -0.000288 NEGATIVE; SMC: structure shift used |
| **Immediate wick reclaim** | LuxAlgo, V1 plan | ✅ YES | ❌ NO | ⚠️ PARTIAL | FAIL | V1: 0.000184, underperformed raw wick cross |
| **Delayed reclaim** | LuxAlgo, V1 plan | ✅ YES | ❌ NO | ⚠️ PARTIAL | FAIL (lookahead) | V1: detection 0.001189, label-available 0.000054 (95% collapse) |
| **True breakout / no reclaim** | V1 plan | ✅ YES | ❌ NO | ⚠️ PARTIAL | FAIL | V1: detection 0.001028, label-available -0.000268 (negative) |
| **Sweep area as reaction zone** | LuxAlgo | ❌ NO | ❌ NO | ❌ NO | Not tested | Could be early entry alternative to mitigation |
| **Displacement / impulse** | Makuchaku/eFe, ICT, PyIndicators | ❌ NO (only detection) | ✅ YES (detection only) | ❌ NO | Component works, entry NOT tested | SMC: displacement detected, but NOT used as entry |
| **FVG / imbalance** | Makuchaku/eFe, ICT, smart-money-concepts | ❌ NO | ✅ YES | ⚠️ PARTIAL | Component works, mitigation timing failed | SMC: FVG detected, mitigation used for entry (too late) |
| **Mitigation / retest entry** | Makuchaku/eFe, ICT | ❌ NO | ✅ YES | ✅ YES | FAIL (too late) | SMC: mitigation+1 entry arrives after most MFE consumed |
| **CHOCH / MSS** | PyIndicators, smart-money-concepts, ICT | ❌ NO | ⚠️ PROXY | ❌ NO | Proxy only | SMC: simple structure shift proxy, not full CHOCH semantics |
| **Order block** | Makuchaku/eFe, ICT, smart-money-concepts | ❌ NO | ❌ NO | ❌ NO | Not tested | Separate from FVG; could have different timing |
| **Rejection block / RJB / PPDD** | Makuchaku/eFe | ❌ NO | ❌ NO | ❌ NO | Not tested | Breaker block / failed mitigation continuation |
| **Recursive fractal hierarchy** | PyIndicators | ❌ NO | ❌ NO | ❌ NO | Not tested | Nested swing priority; warned about lookahead risk |
| **HTF bias / dealing range** | ICT | ❌ NO | ❌ NO | ❌ NO | Not tested | Premium/discount context for entry selection |
| **Session / killzone timing** | ICT, May 2026 assessment | ❌ NO (metadata only) | ❌ NO (metadata only) | ⚠️ CORRELATION ONLY | Not viable as filter | May 2026 Singular Edge: context specialization degrades edge |
| **Liquidity cluster quality** | Inferred from sources | ❌ NO | ❌ NO | ❌ NO | Not tested | Not every equal level is equal; age/hits/span/HTF proximity |
| **Volume / CVD / TFI / force-order confirmation** | Current bot, research DB | ❌ NO (exists as feature) | ⚠️ METADATA | ❌ NO | Available but not tested for sweep classification | TFI at detection/entry collected but not used for directional split |
| **Continuation vs reversal split** | LuxAlgo, inference | ❌ NO | ❌ NO | ❌ NO | Not tested | Post-sweep directional classification |
| **Early entry vs confirmation entry** | ICT aggressive/conservative | ❌ NO (mitigation only) | ⚠️ CONSERVATIVE ONLY | ❌ NO | Only mitigation+1 tested | Aggressive: displacement bar; conservative: mitigation bar |
| **MFE-before-entry decay diagnostic** | SMC result observation | ❌ NO | ⚠️ MEASURED | ⚠️ DIAGNOSTIC ONLY | KEY FINDING | SMC: 0.011565 before vs 0.004916 after — accessibility problem identified |
| **Consequent encroachment (CE) / FVG midpoint** | ICT 2026 concept | ❌ NO | ❌ NO | ❌ NO | Not tested | Entering at 50% FVG fill instead of full mitigation |

**Coverage summary:**

- **Fully tested:** 5 concepts (high/low cross, close BoS, immediate reclaim, delayed reclaim, mitigation entry)
- **Partially tested:** 6 concepts (displacement detection, FVG detection, CHOCH proxy, session metadata, TFI metadata, MFE decay)
- **Not tested:** 11 concepts (early displacement entry, order blocks, breaker blocks, fractal hierarchy, HTF bias, cluster quality, flow classification, continuation/reversal split, aggressive entry, CE midpoint, sweep area reaction)

**Verdict:** ~50% source coverage. Significant untested surface remains.

---

## 3. What Exactly Failed?

### A. Event Taxonomy Failure (V1)

**What failed:**

- Immediate reclaim did not outperform raw wick cross
- Delayed reclaim edge collapsed from detection-bar to label-available timing (0.001189 → 0.000054)
- True breakout reversed negative when measured from knowable timing (0.001028 → -0.000268)

**Why it failed:**

1. **Lookahead bias:** Detection-bar returns measured the move BEFORE it was knowable
2. **Timing reality:** By the time delayed reclaim or true breakout was confirmed, most favorable excursion was consumed
3. **Event classification insufficient:** Knowing an event occurred does not predict tradable direction or timing

**Was the idea wrong?**

- The taxonomy itself is correct (events ARE structurally different)
- The tradability assumption was wrong (label-available timing kills edge)

**Conclusion:** Event labels are diagnostic, not predictive. Classification does not equal edge.

---

### B. SMC Sequence Failure

**What failed:**

- Full sequence (sweep → displacement → structure → FVG → mitigation → entry) produced **PF 1.061 vs threshold 4.0**
- Entry-timed median net return **-0.000442** (negative after 0.10% costs)
- Median MFE before entry **0.011565** >> post-entry MFE **0.004916** (2.4× decay)
- Median 8 bars from sweep detection to entry candidate

**Why it failed:**

- **Mitigation entry timing:** Waiting for FVG mitigation consumed 58% of the favorable move
- **Sequence completion delay:** Each confirmation step (displacement, structure, FVG, mitigation) added bars
- **Entry accessibility:** The edge exists in the sequence, but realistic entry cannot access it

**Did full SMC fail?**

**NO.** A specific version of SMC failed: **mitigation-based confirmation entry.**

The sequence itself shows signal:
- Detection-bar median: 0.004348 (positive)
- Full sequence beats sweep-only: 0.000558 vs -0.001242
- Sequence filters 14,334 sweeps → 1,271 events (8.9% conversion = quality filter works)

**What part of SMC failed?**

The **confirmation-based entry timing** failed, not the **detection components**.

---

### C. Timing Failure Cascade

**Where did tradability disappear?**

| Stage | Bar Offset | MFE Status | Expectancy Status | Notes |
|-------|-----------|------------|-------------------|-------|
| **Sweep detection** | 0 | MFE begins | Detection: 0.004348 ✅ | Move starts here |
| **Displacement** | +1 to +6 | MFE accumulating | NOT TESTED | Impulse bar — could be accessible |
| **Structure shift** | +1 to +10 | MFE peak likely here | NOT TESTED | Close breaks structure |
| **FVG creation** | +2 to +8 | MFE decaying | NOT TESTED | 3-candle gap forms |
| **Mitigation/retest** | +1 to +20 | MFE mostly consumed | Median: 8 bars from detection | Most move happened |
| **Entry candidate** | Mitigation + 1 | MFE 0.004916 (42% left) | Net: -0.000442 ❌ | Too late |
| **After costs** | Entry + 5 bars | MFE further decayed | PF 1.061 ❌ | Below threshold |

**Critical observation:**

The accessible edge is NOT at mitigation. It's somewhere between **displacement** and **structure shift**.

By waiting for FVG mitigation confirmation, we entered after the institutional move completed.

---

## 4. Reverse Quant Engineering: Where Is The Tradable Edge?

**Do not ask whether the SMC pattern exists visually. Ask whether any part of it is knowable early enough to trade with positive expectancy after costs.**

### The Accessibility Problem

**Observation from SMC results:**

- Median MFE before entry: **0.011565** (1.16% favorable move)
- Median MFE after entry: **0.004916** (0.49% favorable move)
- Ratio: **2.4×** — most edge consumed before entry

**Question:** At which bar does MFE begin, and which earliest observable facts existed before most MFE was consumed?

### Reverse-Engineering the Edge Decay

**Hypothesis:** The tradable edge is in the **displacement impulse**, not the **mitigation retest**.

**Reasoning:**

1. **Sweep detection bar (bar 0):**
   - Equal-level liquidity swept
   - Wick crosses level, close may or may not reclaim
   - Detection-bar forward return: **0.004348** (positive)
   - This is the START of institutional absorption

2. **Displacement bar (bar +1 to +6):**
   - Large body candle in reversal direction
   - Body ≥ 0.50 ATR, range ≥ 1.00 ATR, close ≥ 65th percentile of range
   - This is the EXECUTION of the institutional move
   - **NOT TESTED as entry bar**

3. **Structure shift bar (bar +1 to +10):**
   - Close breaks prior swing high/low
   - This CONFIRMS the reversal
   - **NOT TESTED as entry bar**

4. **FVG creation bar (bar +2 to +8):**
   - 3-candle gap forms
   - This is the AFTERMATH of the move
   - **NOT TESTED as entry bar**

5. **Mitigation bar (bar +1 to +20 from FVG):**
   - Price retraces to FVG zone
   - This is the RETEST, after institutions already filled
   - Median 8 bars from sweep detection
   - **TESTED — failed, too late**

### Where Is the Knowable Signal?

**Key insight:** Displacement itself is deterministic and knowable at bar close.

At the close of the displacement bar, we know:
- ✅ Sweep occurred (prior bar)
- ✅ Large reversal body formed (current bar OHLC)
- ✅ Direction is clear (close vs sweep level)
- ✅ Magnitude exceeds threshold (body/range vs ATR)

**What we DON'T know yet:**
- ❌ Whether structure will shift (needs future bars)
- ❌ Whether FVG will form (needs 2 more bars)
- ❌ Whether mitigation will occur (needs 1-20 more bars)

**Question:** Is displacement bar + 1 (next bar open) tradable?

**Answer from current data:** **NOT TESTED.** SMC diagnostic entered at mitigation+1, not displacement+1.

### Does TFI/CVD/Force-Order Flow Provide Earlier Confirmation?

**Current bot context:**

- TFI (trade flow imbalance) available at 15m candle close
- CVD (cumulative volume delta) available
- Force orders available
- These are ALREADY FEATURES in `core/feature_engine.py`

**Question:** Can flow metrics at displacement bar distinguish successful reversals from failed sweeps?

**Answer:** **NOT TESTED.** SMC diagnostic collected TFI at detection and entry as metadata, but did NOT use it for directional classification.

**Hypothesis:** Displacement + confirming flow (TFI reversal, CVD divergence, force-order spike) might be the accessible entry, not mitigation.

### Is Trial-00095 Already Capturing the Accessible Part?

**Trial-00095 parameters:**

- Sweep + reclaim (same-bar or immediate)
- TFI impulse threshold: 0.31
- Direction TFI threshold: 0.10
- Entry: next bar after sweep/reclaim confirmation

**Trial-00095 results:**

- ER: 2.1
- PF: 4.6
- Validated baseline

**Question:** Is trial-00095 entry timing closer to displacement than mitigation?

**Answer:** **YES.** Trial-00095 enters at sweep+reclaim bar + 1, which is 1-2 bars from sweep, NOT 8 bars.

**Implication:** The current bot MAY already be capturing the early displacement edge that SMC sequence missed by waiting for mitigation.

### Is the "SMC Pattern" Visually Correct But Operationally Late?

**YES.**

The SMC sequence is a **post-hoc explanation** of institutional behavior:
1. Sweep liquidity (absorb stops)
2. Displace price (execute position)
3. Leave imbalance (rapid execution)
4. Retest imbalance (profit-taking or late entries)

By the time retail sees mitigation confirmation, institutions already filled at displacement.

**Mitigation is where retail SEES the pattern. Displacement is where institutions TRADE the pattern.**

---

## 5. Was Claude Too Conservative?

**User concern:** Claude may be too strict / suppressing exploration.

### Necessary and Correct Constraints

✅ **V1 timing discipline:** Measuring delayed labels from `label_available_bar`, not `detection_bar`
   - This was CORRECT. V1 proved lookahead bias is real (delayed reclaim: 0.001189 → 0.000054)
   - Without this discipline, we would ship fake edges

✅ **Hard invalidation gates:** PF < 4.0 threshold, net expectancy after costs, trial-00095 benchmark
   - This was CORRECT. PF 1.061 is not production-viable
   - Protecting against weak edges is Claude's job as auditor

✅ **No production changes before research validation:**
   - This was CORRECT. FeatureEngine/SignalEngine changes without proven edge would destabilize trial-00095

✅ **No regime/session filtering without evidence:**
   - This was CORRECT. May 2026 Singular Edge Assessment proved context specialization degrades edge

### Possibly Over-Narrowed Constraints

⚠️ **Mitigation-based entry assumption:**
   - Claude (me) accepted the planning document's assumption that mitigation is the "earliest plausible entry candidate"
   - This assumption came from external sources (Makuchaku/eFe: "retest/mitigation" as entry)
   - **QUESTION:** Should Claude have challenged this assumption and proposed displacement-based entry as alternative?
   - **ANSWER:** Yes. In hindsight, the planning phase should have included TWO entry timing variants: aggressive (displacement+1) and conservative (mitigation+1)

⚠️ **Flow confirmation not tested:**
   - TFI/CVD/force-order features exist in the bot and research DB
   - SMC diagnostic collected them as metadata but did NOT test them for sweep directional classification
   - **QUESTION:** Should Claude have insisted on flow-based sweep classification in the planning phase?
   - **ANSWER:** Arguable. The planning document explicitly said "no new FeatureEngine facts" to keep SMC isolated. But flow features already exist, so testing them would not violate isolation.

⚠️ **Order blocks not tested:**
   - Order blocks are conceptually different from FVG (last down-candle before displacement vs gap after displacement)
   - **QUESTION:** Should Claude have required order block testing alongside FVG?
   - **ANSWER:** No. One sequence test at a time is appropriate. Order blocks can be a separate diagnostic.

### Did Claude Reject Ideas Prematurely?

**NO.** Claude (me) approved both planning documents and only invalidated results after implementation and testing.

- V1 taxonomy: implementation PASS, hypothesis invalidated by data
- SMC sequence: implementation PASS, hypothesis invalidated by data

Neither was rejected prematurely. Both were tested rigorously and failed on merit.

### Are There Source Ideas Claude's Methodology Did Not Test?

**YES.** See Section 2 coverage matrix.

The methodology tested specific interpretations, not the full source space.

**Specifically NOT tested:**

1. **Early displacement entry** (aggressive timing)
2. **Flow-confirmed sweep classification** (directional split using existing features)
3. **Order block separate from FVG** (different zone definition)
4. **Consequent encroachment (50% FVG fill)** (partial mitigation)
5. **Liquidity cluster quality model** (not every equal level is equal)

**Verdict:** Claude's (my) methodology was rigorous but NOT exhaustive. The approved plans were narrow by design to maintain isolation and minimize lookahead risk. This was correct for research discipline, but it means the source space is not fully explored.

---

## 6. Are We Too Attached to Trial-00095?

**Is trial-00095 a sacred edge that must not be challenged?**

**NO.** Trial-00095 is the current validated baseline, not a religion.

**What is trial-00095?**

- Walk-forward validated strategy
- ER 2.1, PF 4.6
- Currently in PAPER validation (1 trade so far, target 30-50)
- Uses: sweep + reclaim, TFI impulse, confluence scoring, regime direction whitelist

**What evidence would justify challenging it?**

- A new edge with **decisively better OOS performance** (ER > 2.5, PF > 5.0)
- **Passing the same walk-forward validation** trial-00095 passed
- **Orthogonal to trial-00095** (not a parameter tweak, a different edge family)
- **Lower correlation** (diversifies, not replaces)

**What evidence does NOT justify challenging it?**

- Detection-bar returns (lookahead)
- In-sample optimization (overfitting)
- Parameter rescue of failed edges
- Regime/session filtering without OOS proof

**Should future research benchmark against trial-00095 but not be constrained to copy its logic?**

**YES.** Trial-00095 is the **quality bar**, not the **only architecture**.

Future research should:
- ✅ Use trial-00095 PF/ER thresholds as invalidation gates
- ✅ Test on the same walk-forward methodology
- ✅ Compare to trial-00095 as baseline
- ❌ NOT copy trial-00095's exact logic (that would be parameter rescue, not new edge discovery)

**Could reverse quant engineering find a different edge family?**

**MAYBE.** The SMC results suggest the accessible edge might be at displacement, not mitigation.

If displacement+flow entry beats trial-00095, it would be a legitimate challenge.

If displacement+flow IS what trial-00095 already captures (sweep+reclaim+TFI is structurally similar), then SMC research confirms trial-00095 is optimal, not challenges it.

**What minimum evidence is needed to justify pausing or modifying trial-00095?**

- **Live PAPER trades:** Minimum 30-50 trades to confirm walk-forward results
- **Statistically significant underperformance:** ER < 1.5 or PF < 3.0 after 50 trades
- **Better alternative validated:** New edge passes walk-forward with ER > 2.5, PF > 5.0

Until then, trial-00095 remains active.

**Framing:** Trial-00095 is the benchmark, not a religion. Research challenges are welcome if they meet the same validation standard.

---

## 7. Open-Source / Article Research Gap

### Current External Research (2026)

Based on web searches conducted 2026-05-27:

#### A. Backtest Performance Claims

**Source:** Medium article "I Backtested 2,600 Trades Using Smart Money Concepts"

- 26-month backtest (Jan 2024 - Mar 2026)
- 2,600 trades across 10 assets (Gold, BTC, ETH, EUR/USD, GBP/USD, NAS100, SOL, USD/JPY, SPX500, XRP)
- **Results:** 61% win rate, 2.17 PF, +2.27R average return
- **Assessment:** ⚠️ PF 2.17 is BELOW our trial-00095 threshold (4.6). If accurate, confirms SMC is NOT superior to our baseline.

#### B. AI-Powered SMC Automation

**Source:** GPTrader blog "Smart Money Concepts Automated by AI Trading Agents"

- Claims 20-30% higher returns using AI agents (DeepSeek, GPT-4) for real-time adaptation
- **Assessment:** ❌ Discretionary/adaptive, not deterministic. Not applicable to our research.

#### C. Liquidity Sweep Strategy Patterns

**Sources:** XBTFX, ThinkMarkets, DailyPriceAction

- Liquidity sweep = price raid into clustered stops → reversal
- Two types: wick-through-and-retrace (bullish sweep) vs close-through-and-reverse (bearish sweep)
- Multi-timeframe confirmation: sweep on lower TF, bias from higher TF
- **Assessment:** ✅ Aligns with our V1 taxonomy. Our V1 tested this (wick cross + immediate reclaim) and it underperformed raw wick cross. External sources don't solve our timing problem.

#### D. FVG Backtesting

**Sources:** Medium "Automating FVGs in Python" by Ziad Francis, ForexTester

- FVG = 3-candle gap where candle 1 high < candle 3 low (bullish) or candle 1 low > candle 3 high (bearish)
- Backtest claims: 62% success on 4H charts
- Python implementation: detect gap, filter by momentum candle > average
- **Assessment:** ⚠️ 62% win rate is borderline. No PF reported. Our SMC diagnostic used FVG correctly but mitigation timing failed. External sources don't address entry timing decay.

#### E. Order Block Mitigation Entry Timing

**Sources:** ICT Mitigation Block guide, XS.com, Phemex Academy

- Mitigation block = retest of order block after displacement
- Entry approaches:
  - **Aggressive:** Limit order at block level (high risk, precise entry)
  - **Conservative:** Wait for confirmation candle within zone (lower risk, worse fill)
- Recommended TFs: 1H/4H for identification, 5m/3m for entry
- **Assessment:** ✅ This is EXACTLY what our SMC diagnostic tested (conservative mitigation entry). External sources confirm this is the standard approach. Our results prove it's too late.

#### F. ICT Displacement and Imbalance

**Sources:** Inner Circle Trader tutorials, AronGroups

- Displacement = aggressive, quick, strong price move that breaks structure and creates imbalance
- Imbalance (FVG) often rebalances only to **Consequent Encroachment (CE)** = 50% FVG midpoint, not full mitigation
- Framework: Liquidity → Imbalance → Displacement FIRST, then structure/OB/FVG, then entry refinement
- **Assessment:** ✅ CE (50% FVG) is an UNTESTED variant. Could be earlier than full mitigation. Worth investigating.

#### G. Market Microstructure Academic Research

**Source:** arXiv "Explainable Patterns in Cryptocurrency Microstructure"

- Dataset: Binance Futures perpetual contract order books + trades, 1-second frequency, Jan 2022 - Oct 2025
- **Assessment:** ⚠️ Academic microstructure research. Could provide theoretical foundation for stop-run reversal mechanics. NOT immediately actionable for our strategy.

### Gap Analysis

| External Claim | Our Test Status | Gap |
|----------------|-----------------|-----|
| SMC backtest PF 2.17 | Our SMC PF 1.061 | ✅ Consistent — both below trial-00095 4.6 |
| FVG 62% win rate | Our SMC 54.9% win rate | ✅ Consistent — borderline, not decisive |
| Mitigation entry timing (1H ID, 5m entry) | Our mitigation+1 entry | ✅ We tested standard approach — failed |
| Consequent encroachment (50% FVG) | NOT TESTED | ⚠️ GAP — could be earlier than full mitigation |
| Aggressive displacement entry | NOT TESTED | ⚠️ GAP — could be the accessible edge |
| Flow confirmation (TFI/CVD at displacement) | Collected but NOT TESTED | ⚠️ GAP — existing features, not used |
| Liquidity cluster quality model | NOT TESTED | ⚠️ GAP — not every equal level is equal |
| Order blocks separate from FVG | NOT TESTED | ⚠️ GAP — different zone definition |

### Credible Open-Source Implementations

| Repository | Concepts | Assessment |
|-----------|----------|------------|
| **joshyattridge/smart-money-concepts** | FVG, swing highs/lows, BOS/CHOCH, OB, liquidity (Python) | ✅ Useful — deterministic reference implementations |
| **coding-kitties/PyIndicators** | Fractal swing, liquidity sweeps, liquidity voids, recursive hierarchy | ⚠️ Useful but warns about lookahead/repainting risk |
| **Makuchaku/eFe TradingView script** | OB, FVG, BoS, PPDD/RJB | ❌ Discretionary/visual — not algorithmic |
| **LuxAlgo Liquidity Sweeps** | Wick/close sweep patterns, reaction zones | ⚠️ Useful concept, but no algorithmic backtest |

### Open Questions for External Research

1. **Does any credible backtest show PF > 4.0 for SMC mitigation entry?**
   - Search result: NO. Best claim is PF 2.17 (Medium article), which is below our threshold.

2. **Does ICT or any source recommend displacement-based entry over mitigation?**
   - Search result: YES. ICT framework says "Liquidity → Imbalance → Displacement FIRST" and mentions aggressive entry at block level vs conservative entry at confirmation.

3. **Is consequent encroachment (50% FVG) documented as viable entry?**
   - Search result: YES. ICT sources say "algorithm often rebalances only to CE (midpoint), not full gap."

4. **Do any sources address MFE decay problem explicitly?**
   - Search result: NO. External sources describe patterns but not accessibility timing.

**Verdict:** External research CONFIRMS our SMC failure (mitigation entry is too late) and SUGGESTS untested alternatives (displacement entry, CE midpoint, flow confirmation).

---

## 8. Possible Alternative Research Directions

Maximum 5 concrete directions, each with hypothesis, differentiation, earliest signal bar, lookahead risk, data required, complexity, pass/fail criteria.

### Direction 1: Early Displacement Entry Diagnostic

**Hypothesis:**

The tradable edge is at the displacement impulse after sweep, not at mitigation retest. Entering at displacement+1 captures the institutional execution, not the retail confirmation.

**Why different from failed SMC sequence:**

- SMC sequence entered at mitigation+1 (median 8 bars from sweep)
- This enters at displacement+1 (1-6 bars from sweep, typically 2-3)
- Tests whether earlier timing accesses the MFE that mitigation missed

**Earliest realistic signal bar:**

- Displacement bar close (bar +1 to +6 from sweep detection)
- Entry: displacement bar + 1 (next bar open)

**Expected risk of lookahead:**

- **LOW.** Displacement is deterministic at bar close (body/range vs ATR, close percentile).
- No future bars needed to confirm (unlike mitigation which needs FVG + retest).

**Data required:**

- Same DB as SMC: `research_lab/data/crowded_unwind_backtest.db`
- BTCUSDT 15m, 2020-09-01 to 2026-03-28
- Already has sweep events from SMC diagnostic

**Implementation complexity:**

- **LOW.** Reuse SMC sweep detection, displacement detection, ATR calculation.
- Change: entry_candidate_bar = displacement_bar + 1 (instead of mitigation_bar + 1)
- Forward metrics from entry_candidate_bar only (no need for FVG/mitigation)

**Pass/fail criteria:**

- Entry-timed 5-bar median net return > 0 after 0.10% costs
- Entry-timed 5-bar PF proxy ≥ 4.0 (trial-00095 threshold)
- Entry-timed median return ≥ trial-00095 reference
- Entry-timed MFE median ≥ 50% of detection-bar MFE (prove early entry captures edge)

**Reason to reject now:**

- **NONE.** This is the most direct test of the accessibility hypothesis.
- If this fails, we definitively know the edge is NOT accessible at any point in the SMC sequence.
- If this passes, we found the accessible entry timing.

**Recommendation:** **APPROVE for planning phase.**

---

### Direction 2: Flow-Confirmed Sweep Continuation/Reversal Classification

**Hypothesis:**

Not all sweeps reverse. Some are absorption (reversal edge), some are continuation (no edge or inverse edge). TFI/CVD/force-orders at sweep detection can classify sweep type, improving edge separation.

**Why different from failed V1/SMC:**

- V1 tested event taxonomy without flow confirmation
- SMC tested sequence without flow-based directional classification
- This tests whether existing flow features (TFI/CVD/force-orders) separate successful sweeps from failed sweeps

**Earliest realistic signal bar:**

- Sweep detection bar (bar 0)
- Entry: sweep detection bar + 1 OR displacement bar + 1 (depends on classification result)

**Expected risk of lookahead:**

- **LOW.** TFI/CVD/force-orders are available at 15m candle close.
- Classification is deterministic at detection bar.

**Data required:**

- Same DB: `research_lab/data/crowded_unwind_backtest.db`
- Must have `aggtrade_buckets` table with TFI
- SMC diagnostic already collected TFI at detection/entry as metadata

**Implementation complexity:**

- **MEDIUM.** Requires:
  - Sweep detection (already exists from SMC)
  - TFI/CVD calculation at sweep bar (already in FeatureEngine)
  - Directional classification logic (new: "reversal" if TFI opposes sweep direction, "continuation" if TFI aligns)
  - Separate cohort analysis for reversal vs continuation sweeps

**Pass/fail criteria:**

- Reversal sweeps: entry-timed 5-bar PF ≥ 4.0, net return > 0
- Continuation sweeps: entry-timed 5-bar PF < 1.0 or negative return (proves they should be avoided)
- Separation: reversal median - continuation median ≥ 0.001 (0.10%)

**Reason to reject now:**

- **NONE.** Flow features already exist. This tests whether they add value for sweep classification.
- If this fails, we know flow doesn't help.
- If this passes, we found a flow-based filter that improves trial-00095.

**Recommendation:** **APPROVE for planning phase.**

---

### Direction 3: MFE Accessibility Meta-Study

**Hypothesis:**

Systematically study WHERE in the sequence the favorable move occurs and WHAT was knowable before it. This is not a trading strategy — it's a diagnostic to guide future research.

**Why different from failed V1/SMC:**

- V1 and SMC tested specific entry timings
- This tests NO entry timing — it's pure measurement
- Goal: identify the bar offset where MFE peaks and map what was knowable at that bar

**Earliest realistic signal bar:**

- N/A — this is a measurement study, not an entry strategy

**Expected risk of lookahead:**

- **NONE.** This is explicitly a lookahead study to understand edge accessibility.

**Data required:**

- Same DB: `research_lab/data/crowded_unwind_backtest.db`
- Sweep events from SMC diagnostic
- Bar-by-bar MFE measurement from sweep detection through +20 bars

**Implementation complexity:**

- **LOW.** Measure MFE at each bar offset, correlate with knowable facts (displacement occurred, structure shifted, FVG formed, etc.)

**Pass/fail criteria:**

- Diagnostic only — no pass/fail
- Output: "MFE peaks at bar +X, at which point facts A, B, C were knowable"
- Guides decision on whether Direction 1 (displacement entry) or Direction 4 (CE midpoint) is viable

**Reason to reject now:**

- **Possible.** This is a meta-study, not a strategy. If we're confident Direction 1 (displacement entry) is the right next test, we can skip the meta-study and go straight to testing.

**Recommendation:** **OPTIONAL — only if Direction 1 result is ambiguous.**

---

### Direction 4: Consequent Encroachment (50% FVG Fill) Entry

**Hypothesis:**

Entering at 50% FVG fill (consequent encroachment) instead of full mitigation captures more of the favorable move while still having confirmation.

**Why different from failed SMC sequence:**

- SMC sequence waited for full FVG mitigation (price enters FVG zone, confirms with midpoint cross or bullish candle)
- This enters when price reaches 50% FVG midpoint (earlier than full mitigation)

**Earliest realistic signal bar:**

- FVG creation bar + 1 to + mitigation window
- Entry: bar where price first touches FVG midpoint

**Expected risk of lookahead:**

- **LOW.** FVG midpoint is calculable at FVG creation (bar +2 from displacement).
- Entry is deterministic when price reaches midpoint.

**Data required:**

- Same DB: `research_lab/data/crowded_unwind_backtest.db`
- Sweep/displacement/FVG detection from SMC diagnostic
- New: detect when price first touches 50% FVG level

**Implementation complexity:**

- **MEDIUM.** Reuse SMC FVG detection, change mitigation logic to 50% fill instead of zone entry + confirmation.

**Pass/fail criteria:**

- Entry-timed 5-bar PF ≥ 4.0, net return > 0
- Entry earlier than full mitigation (median bars from sweep < 8)
- Entry-timed MFE > SMC full-mitigation MFE (0.004916)

**Reason to reject now:**

- **POSSIBLE.** If Direction 1 (displacement entry) passes, CE is redundant.
- If Direction 1 fails, CE is a fallback (still later than displacement but earlier than full mitigation).

**Recommendation:** **CONDITIONAL — only if Direction 1 fails but shows partial signal.**

---

### Direction 5: Liquidity Cluster Quality Model

**Hypothesis:**

Not every equal-level sweep is equal. Cluster quality (age, hits, span, proximity to HTF levels, prior sweep recency) predicts sweep edge strength.

**Why different from failed V1/SMC:**

- V1 tested event types without cluster quality filtering
- SMC tested sequence without cluster quality filtering
- Current bot uses `min_hits`, `level_min_age_bars` as basic quality gates, but not comprehensive quality scoring

**Earliest realistic signal bar:**

- Sweep detection bar (cluster quality is knowable at detection)
- Entry: depends on which entry timing is validated (displacement+1 or mitigation+1)

**Expected risk of lookahead:**

- **LOW.** Cluster quality features are historical (age, hits, span computed from prior bars).

**Data required:**

- Same DB: `research_lab/data/crowded_unwind_backtest.db`
- New: compute cluster quality metrics at sweep detection

**Implementation complexity:**

- **HIGH.** Requires:
  - Cluster age (bars since first touch)
  - Cluster hits (number of touches within tolerance)
  - Cluster span (bars between first and last touch)
  - HTF level proximity (distance to nearest 1H/4H swing)
  - Prior sweep recency (duplicate-level window)
  - Quality scoring function
  - Cohort split by quality quartiles

**Pass/fail criteria:**

- Top-quality quartile: entry-timed 5-bar PF ≥ 4.0, net return > 0
- Bottom-quality quartile: PF < 2.0 (proves low-quality sweeps should be avoided)
- Monotonic relationship: quality ↑ → expectancy ↑

**Reason to reject now:**

- **HIGH COMPLEXITY.** This is an enhancement to an existing edge, not a new edge discovery.
- Should only pursue if Direction 1 or 2 shows promising signal but needs filtering.

**Recommendation:** **DEFER — only if Direction 1 or 2 passes but has high variance.**

---

## 9. Decision Recommendation

**ONE RECOMMENDATION:**

## **PLAN ONE MORE RESEARCH DIAGNOSTIC: DISPLACEMENT ENTRY ACCESSIBILITY TEST**

### Rationale

1. **SMC sequence failure was SPECIFIC, not blanket:**
   - Mitigation entry timing failed (PF 1.061)
   - Detection-bar returns were positive (0.004348)
   - MFE before entry >> MFE after entry (2.4× decay)
   - This proves the edge EXISTS but mitigation entry CANNOT ACCESS IT

2. **Displacement entry is the logical next test:**
   - Earlier timing (displacement+1 vs mitigation+1)
   - Still deterministic (no lookahead)
   - Matches institutional execution timing (not retail confirmation timing)
   - External sources (ICT) recommend aggressive entry at displacement

3. **Low implementation cost:**
   - Reuse SMC sweep/displacement detection
   - Change entry_candidate_bar = displacement_bar + 1
   - 1-day implementation, same test framework as SMC

4. **Decisive test:**
   - If displacement entry PASSES (PF ≥ 4.0), we found the accessible edge
   - If displacement entry FAILS, we definitively know SMC sequence has no accessible entry timing
   - Either outcome closes the SMC research question

5. **No risk to trial-00095:**
   - Research-only diagnostic
   - No production changes
   - Trial-00095 PAPER validation continues independently

6. **Data staleness is acceptable for invalidation:**
   - 59-day-old data is a concern, but:
   - SMC mitigation entry failed decisively (PF 1.061 vs 4.0)
   - If displacement entry also fails on 59-day-old data, fresh data won't reverse it
   - If displacement entry PASSES on old data, THEN we rerun on fresh data before production

### Recommended Next Steps

1. **User approves displacement entry diagnostic planning**
2. **Codex creates planning document:** `DISPLACEMENT_ENTRY_ACCESSIBILITY_V1_PLAN.md`
3. **Claude Code audits planning document** (check for lookahead, timing discipline, invalidation gates)
4. **User approves implementation**
5. **Codex implements diagnostic** (1-day estimate)
6. **Claude Code audits results**
7. **Decision:**
   - If PASS → rerun on fresh data, then consider FeatureEngine integration
   - If FAIL → STOP SMC research, trial-00095 remains optimal

### Alternative Recommendation If User Rejects Displacement Test

**STOP RESEARCH. Trial-00095 validation only.**

If displacement entry is not worth testing, then the SMC research question is answered:
- Mitigation entry is too late
- Earlier timings are not worth testing
- Trial-00095 already captures the accessible edge
- Focus on trial-00095 PAPER validation (target 30-50 trades)

---

## 10. Strict Non-Goals

Do NOT recommend:

- ❌ **Detection-bar returns as success** — V1 proved this is lookahead
- ❌ **Delayed labels without entry timing** — SMC proved this kills edge
- ❌ **Rescuing V1 taxonomy** — immediate/delayed reclaim failed, stop rescuing
- ❌ **Rescuing failed SMC mitigation-entry** — mitigation+1 failed, stop rescuing
- ❌ **Adding CHOCH/FVG/OB blindly** — SMC tested FVG, failed at entry timing, not detection
- ❌ **Relaxing invalidation thresholds** — PF 4.0 threshold is correct, protects trial-00095
- ❌ **Adding regime/session filters** — May 2026 Singular Edge proved this degrades edge
- ❌ **Production changes before validation** — no FeatureEngine/SignalEngine work before audited plan
- ❌ **Discretionary/visual patterns** — not algorithmic, not reproducible
- ❌ **Parameter rescue of failed edges** — changing thresholds won't fix timing problems
- ❌ **Ignoring data staleness** — 59-day gap is a limitation; fresh data rerun needed if displacement entry passes

---

## Final Framing

**The question is not: "Does SMC work?"**

**The question is: "Where in the SMC sequence does the move become accessible?"**

We tested mitigation — it's too late.

We have not tested displacement — the most likely accessible entry.

One more diagnostic closes the question.

---

**Sources:**

External research references:
- [I Backtested 2,600 Trades Using Smart Money Concepts](https://medium.com/@space.garaa/i-backtested-2-600-trades-using-smart-money-concepts-heres-what-actually-works-bb3c671098c6)
- [Revolutionize Trading: Smart Money Concepts Automated by AI](https://gptrader.app/blog/smart-money-concepts-smc-automated-by-ai-trading-agents)
- [Liquidity Sweep in Trading Explained](https://xbtfx.com/blog/liquidity-sweeps-in-trading-explained/)
- [Automating Fair Value Gaps in Python](https://medium.com/@ziad.francis/automating-fair-value-gaps-fvg-in-python-0768d3f382e6)
- [ICT Mitigation Block Explained](https://innercircletrader.net/tutorials/ict-mitigation-block-explained/)
- [Displacement in ICT: Smart Money Price Moves](https://arongroups.co/technical-analyze/displacement-in-ict/)
- [Most Important ICT Concepts](https://innercircletrader.net/tutorials/most-important-ict-concepts-to-conquer-market-complete-list/)
- [joshyattridge/smart-money-concepts GitHub](https://github.com/joshyattridge/smart-money-concepts)

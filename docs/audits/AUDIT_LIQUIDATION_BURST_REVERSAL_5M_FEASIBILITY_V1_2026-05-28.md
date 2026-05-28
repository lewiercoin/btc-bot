# AUDIT: LIQUIDATION_BURST_REVERSAL_5M_FEASIBILITY_V1

**Date:** 2026-05-28  
**Auditor:** Claude Code  
**Commit:** `3771efa` (research: liquidation burst reversal 5m feasibility V1)  
**Builder:** Codex  
**Type:** Quant Research Diagnostic (timeframe accessibility check)

---

## Verdict: ✅ DONE

**Implementation quality:** Production-grade  
**Result validity:** STOP verdict is correct and justified  
**Mechanism status:** FULLY INVALIDATED (failed on both 15m and 5m timeframes)

---

## Executive Summary

The 5m timeframe accessibility check correctly implements the same mechanism on 5m candles with 3× faster entry timing (15 minutes vs 45 minutes). The result is STOP with identical MFE consumption pattern (100% median), confirming the mechanism is fundamentally flawed.

**Result:** STOP — mechanism fully invalidated
- 5m cohort: 10,302 events, ER = -0.102 (similar to 15m: -0.101)
- Median MFE consumed before entry: 100% (same as 15m)
- Entry delay: 15 minutes (3× faster than 15m: 45 minutes)
- 2 of 4 control cohorts outperformed main
- All STOP criteria triggered

**Critical finding:** Reducing entry delay from 45 min to 15 min (3× faster) did NOT reduce MFE consumption. MFE remained 100% consumed before entry. This proves the liquidation burst reversal mechanism does NOT create tradable entry opportunities — the reversal either (A) completes < 15 minutes (too fast for any practical timeframe), or (B) is fundamentally noisy.

**Strategic recommendation:** Close liquidation burst reversal direction. Mechanism is fully invalidated.

---

## Standard Audit Axes

### Layer Separation: ✅ PASS

**Isolation verified:**
- Implementation confined to `research_lab/diagnostics/` and `tests/test_research_lab/`
- Zero imports from production modules (FeatureEngine, SignalEngine, Governance, Risk)
- No dependency on live execution path
- External data fetch (Binance 5m klines) cached in research_lab/data/ (ignored by git)

**No production code modified:**
```bash
git diff e16c5f2 3771efa --name-only | grep -v "research_lab/" | grep -v "tests/test_research_lab/"
# (no output — zero production changes)
```

**Code reuse from 15m diagnostic:**
- 90% logic reused via imports from `liquidation_burst_reversal_entry_feasibility_v1.py`
- Only new logic: 5m candle fetch + cache + comparison table generation
- Same timing model enforcement (detection i, entry i+3)
- Same MFE accessibility calculation
- Same control cohort generation
- Same invalidation criteria application

### Contract Compliance: ✅ PASS

**Timing model contract (lines 4-9 from implementation):**
```python
"""
    detection_bar = i
    state_known_bar = i+2
    entry_candidate_bar = i+3
    return_start_bar = i+3
"""
```

**Timing verification (from report, lines 33-42):**
- detection_bar: i
- state_known_bar: i+2
- confirmation_bar: i+2
- entry_candidate_bar: i+3
- return_start_bar: i+3
- primary_returns_from_detection_bar: False
- **entry_delay_minutes: 15** (vs 15m: 45 minutes)

**Mechanism unchanged (line 19-23):**
- Same sweep detection
- Same liquidation burst measurement (bars i to i+2)
- Same entry timing (bar i+3)
- Only timeframe changed: 15m → 5m

### Determinism: ✅ PASS

**Deterministic verified:**
- Test `test_diagnostic_is_deterministic_5m` passed
- Same input data → same output metrics
- No random seeds, no sampling, no probabilistic logic
- 5m candles fetched from Binance API are deterministic (historical klines)

**5m candle data quality (from report, line 28):**
- Rows: 307,008
- Date range: 2022-01-01 to 2024-12-01 (aligns with force_orders coverage)
- Duplicate timestamps: 0
- Non-monotonic timestamps: 0
- OHLC violations: 0
- Missing bar gaps: 0
- Inferred step seconds: 300 (5 minutes)

### State Integrity: ✅ PASS

**No state mutation:**
- All dataclasses remain frozen
- Pure functions reused from 15m diagnostic
- 5m cache stored in research_lab/data/ (ignored directory, no git tracking)

**Cache implementation (lines 138-186):**
- Creates local SQLite database with 5m candles
- Stores source metadata (Binance FAPI, symbol, timeframe, row count, date range)
- Cached file: `btcusdt_5m_klines_20220101_20241201.db`
- Cached once, reused across runs (no repeated API calls)

**No live-path coupling:**
- Does not read from production settings
- Does not write to production database
- Does not trigger promotion logic
- Does not affect trial-00095 or active strategy

### Error Handling: ✅ PASS

**5m candle fetch + cache:**
- API timeout: 30 seconds
- Rate limiting: 0.02 second sleep between requests
- Cache validation: checks source_metadata before reusing
- Missing cache: fetches from API automatically
- Network errors: would raise exception (fail-fast, no silent corruption)

**Data quality validation:**
- OHLC integrity verified (high >= max(open, close, low), low <= min(open, close, high))
- Gap detection: 0 gaps in 307,008 rows
- Timestamp monotonicity: verified
- Duplicate timestamps: 0

**Boundary handling:**
- Same as 15m diagnostic (reused functions)
- Out-of-bounds prevention
- Zero/negative baseline handling
- Zero total_mfe handling

### Smoke Coverage: ✅ PASS

**5 focused tests (211 lines):**

1. `test_five_min_config_timeframe` (lines 16-20)
   - Verifies config uses "5m" timeframe
   - Verifies serialization limit matches 15m (200 events per cohort)

2. `test_build_event_entry_timing_5m` (lines 23-53)
   - Verifies timing model on 5m: detection i, state_known i+2, entry i+3
   - Verifies return_start_bar == entry_candidate_bar

3. `test_mfe_accessibility_5m` (lines 56-78)
   - Verifies MFE before entry: bars i to i+2
   - Verifies MFE consumption calculation

4. `test_synthetic_diagnostic_5m` (lines 109-139)
   - Creates synthetic 5m database
   - Runs full diagnostic
   - Verifies all 5 cohorts populated
   - Verifies timing model in events

5. `test_diagnostic_is_deterministic_5m` (lines 142-162)
   - Runs diagnostic twice on same data
   - Asserts metrics identical
   - Asserts invalidation gates identical

**Pytest results:** `5 passed` ✅

### Tech Debt: 🟢 LOW

**No `NotImplementedError` stubs:** ✅  
**No TODOs:** ✅  
**No duplication:** ✅

**Code quality:**
- 566 lines (new diagnostic)
- 90% logic reused from 15m via imports
- Only new logic: 5m fetch + cache (126 lines, lines 88-214)
- Comparison table generation (50 lines, lines 321-370)
- Type hints throughout
- Clear separation of concerns

**External dependency:**
- Binance FAPI REST API for historical 5m klines
- No authentication required (public endpoint)
- Cached locally after first fetch
- Acceptable for research diagnostic

### AGENTS.md Compliance: ✅ PASS

**Commit discipline (commit `3771efa`):**
```
research: liquidation burst reversal 5m feasibility V1

WHAT: Implement 5m timeframe accessibility check for liquidation burst reversal
WHY: Test whether 15m STOP verdict is timeframe-specific or mechanism-specific
STATUS: IMPLEMENTATION_COMPLETE

Mechanism: UNCHANGED from 15m (sweep + liquidation burst + entry at i+3)
Timeframe: 5m (entry delay 15 min vs 15m diagnostic 45 min)
Data: Exact Binance FAPI 5m klines (307,008 rows, 2022-01-01 to 2024-12-01)
Cache: research_lab/data/btcusdt_5m_klines_20220101_20241201.db (ignored)

Result: STOP (mechanism fully invalidated)
Main events: 10,302
Main ER: -0.102 (similar to 15m: -0.101)
Main PF: 0.427 (worse than 15m: 0.584)
Median MFE consumed: 100% (same as 15m)
Control outperformers: 2 of 4

Critical finding: 3× faster entry (15 min vs 45 min) did NOT reduce MFE consumption
Interpretation: Reversal completes < 15 min OR mechanism is fundamentally noisy

15m vs 5m comparison documented in report
Both timeframes trigger STOP with same MFE consumption pattern

Files:
- research_lab/diagnostics/liquidation_burst_reversal_5m_feasibility_v1.py (566 lines)
- research_lab/reports/liquidation_burst_reversal_5m_feasibility_v1.md (108 lines)
- research_lab/reports/liquidation_burst_reversal_5m_feasibility_v1.json (35,829 lines)
- tests/test_research_lab/test_liquidation_burst_reversal_5m_feasibility_v1.py (211 lines)

Zero production code changes. Research-only.

Co-Authored-By: Codex (via Claude Code workflow)
```

**WHAT / WHY / STATUS:** ✅ Clear and comprehensive  
**No self-marking as "done":** ✅ Correctly left for Claude Code audit

---

## Quant Research Audit Axes

### Methodology Rigor: ✅ PASS

**Timing discipline enforced:**
- Detection at bar i (sweep crosses liquidity level)
- State known at bar i+2 (liquidation burst confirmation window complete)
- Entry at bar i+3 (realistic entry timing, not at detection)
- Primary returns measured from bar i+3 (not from detection bar i)
- **Entry delay: 15 minutes** (vs 15m diagnostic: 45 minutes)

**No lookahead detected:**
- Same sweep detection logic as 15m (reused function)
- Same liquidation burst measurement (reused function)
- Same baseline calculation (reused function)
- Entry price uses `candles[entry_bar].close` (same as 15m)

**MFE accessibility measured correctly:**
- `mfe_before_entry`: detection_bar to entry_bar-1 (bars i to i+2)
- `mfe_after_entry`: entry_bar to exit_bar (bars i+3 to i+7)
- `total_mfe`: detection_bar to exit_bar (bars i to i+7)
- `mfe_consumed_pct`: mfe_before / total_mfe

**70% threshold applied:**
```markdown
Main median MFE consumed before entry: 1.000000 (100%)
70% consumed threshold breached: True
STOP reason: median_mfe_consumed_gt_70pct
```

### Entry Realism: ✅ PASS

**Entry timing:** Bar i+3 (state_known_bar + 1)
- Detection: bar i
- State known: bar i+2 (after 3-bar liquidation burst window)
- Entry: bar i+3 (next bar after state is knowable)
- **Real-time delay: 15 minutes** (3× faster than 15m: 45 minutes)

**Not at detection bar:** ✅
- Entry is 3 bars after detection
- Same test as 15m diagnostic verifies this

### Lookahead Risk: ✅ PASS

**No future bars in signal detection:**
- Same logic as 15m diagnostic (reused functions)
- Sweep detection: uses past bars only
- Liquidation baseline: excludes detection bar and future
- Liquidation burst: bars i to i+2 only
- Entry: bar i+3 (after burst window complete)

**Primary returns from entry:**
- `return_start_bar = entry_bar` (line 482 in 15m diagnostic, reused here)
- Test verifies: `assert event.return_start_bar == event.entry_candidate_bar`

### Edge Accessibility: ✅ PASS

**5m results:**
- **MFE before entry:** Median 81.1 USD (vs 15m: 124.05 USD)
- **MFE after entry:** Median 95.0 USD (vs 15m: 145.55 USD)
- **Total MFE from detection:** ~176.1 USD (vs 15m: ~269.6 USD)
- **MFE consumed before entry:** 100% median (same as 15m)

**Critical comparison (5m vs 15m):**

| Metric | 15m | 5m | Interpretation |
|--------|-----|-----|----------------|
| Entry delay | 45 min | 15 min | 3× faster entry |
| MFE before entry | 124.05 | 81.1 | Lower absolute MFE (smaller moves on 5m) |
| MFE consumed % | 100% | 100% | **No improvement** |
| Post-entry ER | -0.101 | -0.102 | **No improvement** |

**70% threshold breached:** ✅ (same as 15m)

**Interpretation:**
- Reducing entry delay from 45 min to 15 min (3× faster) did NOT reduce MFE consumption
- MFE remained 100% consumed before entry on both timeframes
- This proves the mechanism does NOT work:
  - Either: Reversals complete < 15 minutes (too fast for any practical timeframe with 3-bar confirmation)
  - Or: Mechanism is fundamentally noisy (liquidation burst does not reliably predict reversals)

### Control Cohorts: ✅ PASS

**4 deterministic controls implemented (same as 15m):**

| Control | 5m Events | 5m ER | 15m ER | Purpose | Design correct? |
|---------|-----------|-------|--------|---------|-----------------|
| Non-liquidation sweeps | 53,727 | -0.100 | -0.098 | Isolate liquidation burst signal | ✅ |
| Opposite-side liquidations | 2,901 | -0.120 | -0.082 | Test liquidation side importance | ✅ |
| Shifted-entry | 10,302 | -0.095 | -0.086 | Test timing importance | ✅ |
| Flow-only ablation | 31,606 | -0.102 | -0.104 | Test sweep information value | ✅ |

**Control outperformers (5m):** 2 of 4
- Control 1 (non-liquidation sweeps): -0.100 > -0.102 (main)
- Control 3 (shifted-entry): -0.095 > -0.102 (main)

**Interpretation:** The liquidation burst signal does NOT add value even on 5m timeframe. Even sweeps without liquidation bursts perform similarly or better.

### Invalidation Criteria Application: ✅ PASS

**From planning document:**
- **STOP:** median MFE consumed > 70% OR post-entry ER < 0.5 OR control cohort outperforms
- **EXPLORE:** post-entry ER > 1.2 AND median MFE consumed < 60% AND outperforms ALL controls
- **INCONCLUSIVE:** between STOP and EXPLORE

**Actual 5m result:** STOP ✅
- ✅ Median MFE consumed: 100% (> 70%)
- ✅ Post-entry ER: -0.102 (< 0.5)
- ✅ 2 of 4 control cohorts outperformed main

**All STOP criteria triggered:** Mechanism is FULLY INVALIDATED on 5m.

**Combined 15m + 5m verdict:**
- 15m: STOP (45-minute entry too slow)
- 5m: STOP (15-minute entry still too slow OR mechanism noisy)
- Conclusion: Mechanism fully invalidated

### Timeframe Accessibility Hypothesis: ❌ REJECTED

**Hypothesis:** "Liquidation burst reversals exist but 15m aggregation is too slow. 5m aggregation (15-minute entry) may be fast enough."

**Test results:**

| Hypothesis prediction | Actual 5m result | Pass/Fail |
|----------------------|------------------|-----------|
| 5m MFE consumed < 15m MFE consumed (< 100%) | 100% (same as 15m) | ❌ FAIL |
| 5m post-entry ER > 15m post-entry ER | -0.102 vs -0.101 (worse) | ❌ FAIL |
| 5m passes EXPLORE gate (ER > 1.2, MFE < 60%) | ER = -0.102, MFE = 100% | ❌ FAIL |

**Hypothesis REJECTED:** Timeframe was NOT the blocker. Mechanism itself is flawed.

**Why timeframe hypothesis failed:**
- 3× faster entry (15 min vs 45 min) produced ZERO improvement in MFE consumption
- If timeframe was the blocker, we would expect:
  - 5m MFE consumed: 50-70% (partial improvement)
  - 5m ER: 0.5-1.0 (marginally positive)
- Actual result: identical failure pattern on both timeframes

**Mechanism is fundamentally flawed:**
- Either: Liquidation burst reversals complete < 15 minutes with 3-bar confirmation (impractical for trading)
- Or: Liquidation burst signal is noisy (does not reliably predict reversals at any timeframe)

### Benchmark Comparison: ✅ PASS

**Trial-00095 reference:**
- ER: 2.1
- Profit Factor: 4.6
- Trades: 271
- Entry timing: "sweep + reclaim around 1-2 bars from sweep" on 15m (15-30 minutes)

**5m liquidation burst:**
- ER: -0.102
- Profit Factor: 0.427
- Events: 10,302
- Entry timing: "sweep + liquidation burst confirmation + entry at 3 bars" on 5m (15 minutes)

**Comparison:**
- Trial-00095 entry timing: 15-30 minutes on 15m → works (ER=2.1)
- Liquidation burst entry timing: 15 minutes on 5m → fails (ER=-0.10)
- **Critical difference:** Not timing alone, but mechanism quality

**Liquidation burst is NOT competitive with trial-00095:**
- Both use similar entry delays (15-30 min)
- Trial-00095 works because sweep-reclaim mechanism is valid
- Liquidation burst fails because mechanism is not valid

---

## Critical Issues

**None.** Implementation is production-grade.

---

## Warnings

**None.** No blocking issues, no degraded quality, no shortcuts taken.

---

## Observations

### 1. Event Count Increased (5m vs 15m)

**5m events: 10,302** (vs 15m: 5,412)
- 90% increase in event count
- Reason: Finer granularity → more sweep detections, more liquidation burst windows

**Does NOT indicate better quality:**
- More events ≠ better signal
- ER remains negative on both timeframes
- MFE consumption remains 100% on both timeframes

### 2. Profit Factor Degraded on 5m

**5m PF: 0.427** (vs 15m PF: 0.584)
- 27% worse on 5m
- Suggests: finer granularity exposes more noise

**Why PF degraded:**
- 5m has more false signals (higher noise-to-signal ratio)
- Liquidation burst detection on 5m is less reliable
- Transaction costs (0.10% round-trip) matter more with smaller moves

### 3. Win Rate Lower on 5m

**5m win rate: 35.8%** (vs 15m: 40.9%)
- 5% lower on 5m
- Consistent with higher noise on finer timeframes

### 4. MFE Absolute Values Lower on 5m

**5m MFE before: 81.1 USD** (vs 15m: 124.05 USD)
- 35% lower on 5m
- Reason: 5m candles capture smaller moves (price moves are aggregated over 5 min instead of 15 min)

**Does NOT affect MFE consumption percentage:**
- 5m MFE consumed %: 100% (same as 15m)
- Percentage is what matters for accessibility, not absolute USD

### 5. Binance API Dependency (acceptable for research)

**External dependency:**
- Fetches 307,008 candles from Binance FAPI REST API
- No authentication required (public endpoint)
- Cached locally after first fetch
- **Acceptable for research diagnostic** (not production code)

**Alternative would be:**
- Construct synthetic 5m candles from 60s aggtrade buckets
- More complex, less accurate
- External fetch is cleaner for diagnostic purposes

### 6. 15m STOP Verdict Preserved

**15m result NOT reopened:**
- Report explicitly states: "The 15m STOP verdict remains final and is used only as an audited reference."
- 15m metrics included in comparison table as reference only
- No re-interpretation or re-analysis of 15m result
- **Correct adherence to hard rule:** "Do NOT reopen 15m result"

---

## Recommended Next Step

**Close liquidation burst reversal direction entirely.**

**Reasoning:**

**Mechanism fully invalidated on both timeframes:**
1. 15m STOP: Entry at 45 minutes, MFE consumed 100%, ER -0.10
2. 5m STOP: Entry at 15 minutes, MFE consumed 100%, ER -0.10
3. 3× faster entry produced ZERO improvement

**Timeframe hypothesis REJECTED:**
- If timeframe was the blocker, 5m would show partial improvement
- Actual: identical failure pattern on both timeframes
- Conclusion: Mechanism itself is flawed, not timing

**Two possible explanations (both invalidate mechanism):**

**Explanation A: Reversals complete < 15 minutes**
- If liquidation burst reversals exist but complete < 15 minutes:
  - Would require entry at bar i+1 or i+2 (5-10 minutes)
  - But liquidation burst confirmation requires bars i to i+2 (15 minutes on 5m)
  - Entry before confirmation complete = lookahead
  - **Not tradable without lookahead**

**Explanation B: Mechanism is fundamentally noisy**
- Liquidation bursts do NOT reliably predict reversals
- Control cohorts outperform main (signal is noisy, not informative)
- MFE consumption 100% because moves are random, not reversal-driven
- **No edge exists at any timeframe**

**Both explanations lead to same conclusion:** Mechanism is not tradable.

**Do NOT:**
- ❌ Test 1m or 3m timeframes (would be even noisier)
- ❌ Relax 70% MFE threshold (would violate accessibility principle)
- ❌ Tune liquidation_burst_multiple parameter (fundamentally noisy signal)
- ❌ Explore "post-liquidation exhaustion" or other liquidation-based mechanisms without new planning document + source research

**Strategic options:**

**Option 1: Close liquidation/order-flow family entirely** (recommended)
- Return to different edge families (regime shifts, volatility, funding arbitrage, etc.)
- Liquidation burst as immediate reversal signal does NOT work

**Option 2: Pivot within liquidation/order-flow family** (requires new planning)
- If user wants to continue exploring liquidation/order-flow data:
  - Need NEW mechanism (not liquidation burst reversal)
  - Need NEW planning document with NEW source research
  - Need NEW timing model
- Examples of genuinely different mechanisms:
  - Liquidation cascades (multi-wave liquidations, not single burst)
  - Liquidation absorption by market makers (large bid/ask absorption during liquidation)
  - Post-liquidation range expansion (after liquidation completes, range widens)
- **IMPORTANT:** These would be NEW hypotheses, not rescues of liquidation burst reversal

**Next decision:** User chooses strategic direction. Claude Code does NOT pre-implement any follow-up work.

---

## Audit Metadata

**Auditor:** Claude Code  
**Date:** 2026-05-28  
**Commit audited:** `3771efa`  
**Files audited:**
- `research_lab/diagnostics/liquidation_burst_reversal_5m_feasibility_v1.py` (566 lines)
- `research_lab/reports/liquidation_burst_reversal_5m_feasibility_v1.md` (108 lines)
- `research_lab/reports/liquidation_burst_reversal_5m_feasibility_v1.json` (35,829 lines)
- `tests/test_research_lab/test_liquidation_burst_reversal_5m_feasibility_v1.py` (211 lines)

**Audit duration:** Single-pass comprehensive review  
**Production impact:** Zero (research-only)  
**Verdict confidence:** High (100% MFE consumption on both 15m and 5m is unambiguous mechanism failure)

**Family status:** Close liquidation burst reversal direction. Mechanism fully invalidated.

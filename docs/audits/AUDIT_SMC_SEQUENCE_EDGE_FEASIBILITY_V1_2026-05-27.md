# AUDIT: SMC_SEQUENCE_EDGE_FEASIBILITY_V1

Date: 2026-05-27  
Auditor: Claude Code  
Commit: c2ee10d76b1a6f24f61391c88cbbf5ac973cdeec  
Builder: Codex  

## Verdict: DONE

**Implementation quality:** Production-grade, tested, no issues.  
**Research hypothesis:** INVALIDATED per approved invalidation criteria.  
**Recommendation:** STOP SMC sequence work. Trial-00095 remains optimal baseline.

---

## Layer Separation: PASS

- ✅ Research script isolated in `research_lab/`
- ✅ Zero imports from production paths (FeatureEngine, SignalEngine, Governance, Risk, execution, storage)
- ✅ Commit c2ee10d touched only 4 files: research script, tests, report, milestone tracker
- ✅ No coupling to live trading path

## Contract Compliance: PASS

- ✅ `run_analysis()` returns structured dict payload
- ✅ Writes JSON + markdown outputs to expected paths
- ✅ Candle dataclass matches expected format (index, open_time, OHLCV)
- ✅ Manifest includes research_only: true, production_changes: false

## Determinism: PASS

- ✅ Timing model explicit: detection_bar, entry_candidate_bar, label_available_bar
- ✅ Entry timing rule: `entry_candidate_bar = mitigation_bar + 1` ([analysis_smc_sequence_edge_feasibility_v1.py:593](c:/development/btc-bot/research_lab/analysis_smc_sequence_edge_feasibility_v1.py#L593))
- ✅ Forward metrics calculated from both detection and entry starts ([analysis_smc_sequence_edge_feasibility_v1.py:636-656](c:/development/btc-bot/research_lab/analysis_smc_sequence_edge_feasibility_v1.py#L636-L656))
- ✅ Control cohort: deterministic shift (137 bars)
- ✅ No random seeds, no stochastic optimization
- ✅ Reproducible from same input data

## State Integrity: PASS

- ✅ SQLite operations read-only (SELECT only, no INSERT/UPDATE/DELETE)
- ✅ Immutable dataclasses (`frozen=True`)
- ✅ No state mutation bugs
- ✅ Source DB: `research_lab/data/crowded_unwind_backtest.db` (correct path, not production DB)

## Error Handling: PASS

- ✅ OHLC validation with hard failure on violations ([analysis_smc_sequence_edge_feasibility_v1.py:1010-1011](c:/development/btc-bot/research_lab/analysis_smc_sequence_edge_feasibility_v1.py#L1010-L1011))
- ✅ Empty candles check ([analysis_smc_sequence_edge_feasibility_v1.py:1008](c:/development/btc-bot/research_lab/analysis_smc_sequence_edge_feasibility_v1.py#L1008))
- ✅ None checks for ATR before division
- ✅ Explicit logging via exceptions (ValueError)

## Smoke Coverage: PASS

**Tests:** 6 passed, 0 failed  
**Test file:** [test_research_lab_smc_sequence_edge_feasibility_v1.py](c:/development/btc-bot/tests/test_research_lab_smc_sequence_edge_feasibility_v1.py)

Critical tests:
- ✅ `test_full_sequence_timing_uses_entry_candidate_after_mitigation` - verifies entry_candidate_bar = mitigation_bar + 1 timing discipline ([test_research_lab_smc_sequence_edge_feasibility_v1.py:123-141](c:/development/btc-bot/tests/test_research_lab_smc_sequence_edge_feasibility_v1.py#L123-L141))
- ✅ `test_fvg_detection_is_known_on_third_candle_close` - timing verification
- ✅ `test_swing_not_available_before_right_side_confirmation` - right-side delay
- ✅ `test_displacement_requires_direction_body_range_and_close_location` - component logic
- ✅ `test_duplicate_sweep_inflation_is_prevented_by_retired_level_window` - inflation prevention
- ✅ `test_synthetic_sqlite_integration` - end-to-end pipeline

## Tech Debt: LOW

- ✅ No `NotImplementedError` stubs
- ✅ No TODO comments
- ✅ Clean, focused implementation (1113 lines)
- ✅ No code duplication

## AGENTS.md Compliance: PASS

- ✅ Commit message format: WHAT / WHY / STATUS
- ✅ No self-marking as "done" - states "ready for Claude audit"
- ✅ Timing discipline preserved (V1 lesson: measure from entry_candidate_bar, not detection_bar)

## Methodology Integrity: PASS

**Planning document:** [SMC_SEQUENCE_EDGE_FEASIBILITY_V1_PLAN.md](c:/development/btc-bot/docs/research/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_PLAN.md)

- ✅ Minimal deterministic proxies implemented: displacement, structure-shift, FVG, mitigation
- ✅ Entry timing: mitigation_bar + 1 (conservative, knowable)
- ✅ Timing model: dual returns from detection_bar AND entry_candidate_bar
- ✅ MFE before entry measured correctly ([analysis_smc_sequence_edge_feasibility_v1.py:657-662](c:/development/btc-bot/research_lab/analysis_smc_sequence_edge_feasibility_v1.py#L657-L662))
- ✅ V1 taxonomy timing lesson preserved: no fake edge from unknowable labels
- ✅ No V1 rescue attempt
- ✅ No regime/session filtering (metadata only, noted explicitly)

## Promotion Safety: PASS

**Invalidation function:** [analysis_smc_sequence_edge_feasibility_v1.py:863-913](c:/development/btc-bot/research_lab/analysis_smc_sequence_edge_feasibility_v1.py#L863-L913)

Hard invalidation gates (no soft warnings):
- ✅ Sample size < 100 → INCONCLUSIVE
- ✅ Entry return < detection return → FAIL
- ✅ Entry win rate ≤ 0.52 → FAIL
- ✅ Entry return ≤ sweep-only baseline → FAIL
- ✅ Entry return ≤ deterministic control → FAIL
- ✅ Entry return ≤ V1 raw wick-cross reference → FAIL
- ✅ MFE before entry ≥ MFE after entry → FAIL
- ✅ PF proxy < 4.0 (trial-00095 threshold) → FAIL
- ✅ Net expectancy ≤ 0 after costs → FAIL

Verdict logic: if any risk → `FAIL_OR_INCONCLUSIVE_REVIEW_REQUIRED` (no soft pass allowed)

## Reproducibility & Lineage: PASS

- ✅ Dataset: BTCUSDT 15m, 195,347 candles, 2020-09-01 to 2026-03-28
- ✅ Data quality: 0 missing gaps, 0 OHLC violations
- ✅ Config parameters in JSON manifest
- ✅ Generated timestamp: included
- ✅ Milestone name in manifest: SMC_SEQUENCE_EDGE_FEASIBILITY_V1
- ✅ JSON SHA256: 8CA802FD610DFE552225C9318A455345D8917D688ABBD2B3647CA69C4B6A78A4
- ✅ Reproducible from committed script

## Data Isolation: PASS

- ✅ Source DB: read-only research snapshot (not production `storage/btc_bot.db`)
- ✅ No write operations to source DB
- ✅ Output written to `research_lab/analysis_output/` only

## Search Space Governance: PASS

- ✅ DiagnosticConfig class with documented defaults ([analysis_smc_sequence_edge_feasibility_v1.py:62-87](c:/development/btc-bot/research_lab/analysis_smc_sequence_edge_feasibility_v1.py#L62-L87))
- ✅ Parameters appropriate for research (ATR multiples, windows, thresholds)
- ✅ No parameter rescue attempted
- ✅ No silent methodology widening

## Artifact Consistency: PASS

All artifacts tell the same story:

- ✅ Report verdict: `FAIL_OR_INCONCLUSIVE_REVIEW_REQUIRED` ([SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md:42](c:/development/btc-bot/docs/analysis/SMC_SEQUENCE_EDGE_FEASIBILITY_V1_2026-05-27.md#L42))
- ✅ MILESTONE_TRACKER verdict: same ([MILESTONE_TRACKER.md:31](c:/development/btc-bot/docs/MILESTONE_TRACKER.md#L31))
- ✅ Commit message: "results indicate STOP/FAIL_OR_INCONCLUSIVE_REVIEW_REQUIRED"
- ✅ JSON invalidation_checks payload: same verdict

## Boundary Coupling: PASS

- ✅ No imports from backtest/ (verified via grep)
- ✅ No imports from live path (FeatureEngine, SignalEngine, Governance, Risk)
- ✅ Standalone offline research tool
- ✅ Zero coupling to production settings or profiles

---

## Research Outcome: HYPOTHESIS INVALIDATED

**Dataset:** BTCUSDT 15m, 195,347 candles  
**Events detected:**
- Sweep-only: 14,334
- Full SMC sequence: 1,271 (8.9% conversion rate)

**Results (from entry_candidate_bar timing):**

| Metric | Full Sequence | Sweep-only | Control | Trial-00095 Ref |
|---|---|---|---|---|
| Count | 1,271 | 14,334 | 1,271 | - |
| Entry 5-bar median return | 0.000558 | -0.001242 | 0.000243 | - |
| Entry 5-bar median net return | **-0.000442** | -0.002242 | -0.000757 | - |
| Entry 5-bar PF proxy | **1.061** | 0.361 | 0.795 | **4.0 threshold** |
| Entry 5-bar win rate | 0.550 | 0.405 | 0.522 | - |
| Entry 5-bar MFE median | 0.004916 | 0.002766 | 0.004011 | - |
| Median MFE before entry | **0.011565** | - | - | - |

**Invalidation criteria met:**

1. ✅ **FAIL:** Entry-timed median return (0.000558) is worse than detection-bar return (0.004348)
2. ✅ **FAIL:** Median MFE before entry (0.011565) is 2.4× greater than post-entry 5-bar MFE (0.004916)
3. ✅ **FAIL:** Entry-timed 5-bar PF proxy (1.061) is far below trial-00095 threshold (4.0)
4. ✅ **FAIL:** Entry-timed median net return (-0.000442) is NEGATIVE after 0.10% round-trip costs

**Timing analysis:**
- Median bars from sweep detection to entry candidate: 8
- Most favorable excursion occurs BEFORE realistic entry
- Mitigation entry arrives too late to capture edge

**Interpretation:**

The full SMC sequence DOES improve over sweep-only baseline (0.000558 vs -0.001242), confirming that displacement + structure + FVG + mitigation filters contain signal. However:

- **Entry timing is fatal.** By the time mitigation confirms and entry_candidate_bar opens, the median favorable move (MFE 0.011565) has already occurred. Post-entry MFE is only 0.004916, indicating the realistic entry captures 42% of the total move.
- **Net expectancy negative.** After realistic 0.10% round-trip costs, median net return is -0.000442.
- **PF proxy 1.061 vs trial-00095 threshold 4.0.** This is not close. It's 74% below the quality bar.

The hypothesis is invalidated: full SMC sequence with realistic mitigation+1 entry timing does not beat trial-00095.

---

## Critical Issues: NONE

Implementation is production-grade. Hypothesis failed on merit, not implementation bugs.

## Warnings: NONE

## Observations

1. **V1 timing lesson correctly applied.** Codex measured entry metrics from entry_candidate_bar, not detection_bar. This avoided the lookahead bias that invalidated V1 delayed reclaim.

2. **Sequence filter quality confirmed.** The 8.9% conversion rate (1,271 from 14,334 sweeps) and positive detection-bar median (0.004348) prove the sequence components contain signal. The failure is entry timing, not signal detection.

3. **MFE timing diagnostic is decisive.** The median MFE before entry (0.011565) vs post-entry (0.004916) ratio is the clearest invalidation signal. The edge exists, but realistic entry cannot access it.

4. **No parameter rescue justified.** Tightening mitigation criteria or widening FVG thresholds would be rescue work. The approved invalidation criteria are met. STOP is correct.

5. **Trial-00095 quality bar is appropriate.** PF 1.061 is not production-viable. The 4.0 threshold protects against weak edges.

---

## Recommended Next Step

**STOP SMC sequence work.**

- Do NOT pursue V2 FeatureEngine facts for SMC sequence
- Do NOT pursue V3 SignalEngine interpretation
- Do NOT attempt mitigation-timing parameter rescue
- Do NOT add regime/session/flow filtering to rescue the edge

Trial-00095 remains the validated baseline (ER 2.1, PF 4.6). Current PAPER validation continues (target 30-50 trades, currently 1 trade).

**Boundary:** This invalidates the full post-sweep SMC sequence with realistic entry timing. It does NOT test or invalidate other hypotheses (e.g., pre-sweep imbalance detection, limit-order entry at FVG creation, alternative structure definitions).

**Preserved lesson:** MFE before entry vs MFE after entry is a decisive diagnostic for delayed-entry edges. If most favorable excursion occurs before realistic entry timing, the edge is not tradeable.

---

## Audit Signature

Claude Code  
2026-05-27  
Commit: c2ee10d76b1a6f24f61391c88cbbf5ac973cdeec

**Implementation verdict:** DONE  
**Research hypothesis verdict:** INVALIDATED  
**Production recommendation:** STOP, trial-00095 remains optimal

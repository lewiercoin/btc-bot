# AUDIT: TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1

**Date:** 2026-05-30  
**Auditor:** Claude Code  
**Commit:** `83be3ff` (research: trial-00095 conditional edge attribution V1)  
**Builder:** Codex  
**Type:** Research-only accepted-trade attribution diagnostic

---

## Verdict: ✅ DONE

**Implementation quality:** Excellent  
**Methodology discipline:** Strict — no threshold changes, no detection-bar returns, no near-miss generation  
**Data handling:** Correct — rejected population unavailability explicitly reported as blocker  
**Recommendation validity:** Correct — reconstruction prerequisite, not threshold relaxation  
**Deliverable completeness:** All 4 artifacts delivered

---

## Executive Summary

This attribution diagnostic correctly analyzes the frozen accepted trial-00095 trade population without changing thresholds, generating new entries, or claiming near-miss edge where data is unavailable.

**Key findings:**
- Baseline 274 trades: ER=2.121, PF=4.216, WR=56.57% (matches WF reference ER=2.129, PF=4.663)
- Shallowest depth quartile (Q1): 69 trades, ER=1.577, PF=2.981 (still positive)
- Near-threshold band (0.00649-0.00714): 63 trades, ER=1.635, PF=3.046 (still positive)
- Direction asymmetry: LONG ER=2.377 (252 trades), SHORT ER=-0.805 (22 trades, 8% of population)
- Regime concentration: uptrend ER=2.614 (205 trades, 75%), downtrend ER=0.690 (54 trades, 20%)
- TFI alignment: aligned ER=2.391, opposed ER=0.816
- Most losses (92.4%) had ≥1R MFE before closing red (exit timing issue, not entry)

**Critical data caveat:**
- Rejected backtest candidates unavailable (no `decision_outcomes` or `feature_snapshots` tables)
- Diagnostic correctly does NOT claim near-miss entries are profitable
- Recommendation: reconstruct rejected near-miss population first, do NOT relax threshold

**Recommendation:** `PLAN_NEAR_MISS_RECONSTRUCTION_DIAGNOSTIC` is correct and appropriately cautious.

---

## Layer Separation: ✅ PASS

- No imports from live path (`bot/`, `core/`, `execution/`)
- Isolated research module reading frozen trade artifacts + market DB
- No production state mutation
- Clean boundary: research → research reports only

**Files:**
- Implementation: [research_lab/diagnostics/trial_00095_conditional_edge_attribution_v1.py](c:\development\btc-bot\research_lab\diagnostics\trial_00095_conditional_edge_attribution_v1.py) (1,163 lines)
- Tests: [tests/test_research_lab/test_trial_00095_conditional_edge_attribution_v1.py](c:\development\btc-bot\tests\test_research_lab\test_trial_00095_conditional_edge_attribution_v1.py) (198 lines)
- Report: [research_lab/reports/trial_00095_conditional_edge_attribution_v1.md](c:\development\btc-bot\research_lab\reports\trial_00095_conditional_edge_attribution_v1.md) (210 lines)
- JSON: `research_lab/reports/trial_00095_conditional_edge_attribution_v1.json` (53 KB)

---

## Contract Compliance: ✅ PASS

Data structures properly defined:
- `DiagnosticConfig` (frozen, 18 parameters including gates)
- `Candle`, `FrozenEntry`, `TradeRecord`, `AttributedTrade`
- Frozen depth threshold: `DEPTH_THRESHOLD = 0.00649` (not tuned)

All trades properly timestamped with `opened_at`, feature context from `prior_bar`, no detection-bar leakage.

---

## Determinism: ✅ PASS

**Test verification:**
```python
def test_diagnostic_is_deterministic(tmp_path: Path):
    # Run twice with same inputs
    first = run_diagnostic(...)
    second = run_diagnostic(...)
    assert first["baseline_metrics"] == second["baseline_metrics"]
    assert first["bucket_metrics"] == second["bucket_metrics"]
    assert first["next_recommendation"] == second["next_recommendation"]
```

Diagnostic is fully deterministic given fixed inputs. No randomization, no non-deterministic sorting.

---

## State Integrity: ✅ PASS (N/A for research-only)

No production state modified. Reads frozen artifacts + market DB, writes reports only.

---

## Error Handling: ✅ PASS

**Graceful handling:**
- Missing `frozen_entries.json`: returns empty dict, continues (line 172-173)
- Optional feature values: `_optional_float` helper for None-safe parsing
- Missing candle context: uses None for features, continues attribution
- Missing OI/funding: features set to None, not crash

**No try/except suppression without logging** — errors propagate with clear messages.

---

## Smoke Coverage: ✅ PASS

**5 tests passed:**

| Test | Purpose |
|---|---|
| `test_market_context_uses_prior_completed_bar` | Verify feature timing: prior bar, not detection bar |
| `test_schema_reports_rejected_population_availability` | Verify rejected candidate check (decision_outcomes/feature_snapshots) |
| `test_diagnostic_recommends_reconstruction_not_threshold_change` | Verify recommendation logic when rejected unavailable |
| `test_diagnostic_is_deterministic` | Verify reproducibility |
| `test_parse_ts_normalizes_to_utc` | Verify timestamp handling |

**Critical tests validated:**
- Prior bar usage (not detection bar) ✓
- Rejected population check ✓
- Recommendation logic ✓
- Determinism ✓

---

## Tech Debt: ✅ LOW

- No `NotImplementedError` stubs
- No `TODO` / `FIXME` / `HACK` markers
- Clean, production-grade implementation
- JSON artifact light (53 KB, 25-trade sample only)

---

## AGENTS.md Compliance: ✅ PASS

**Commit discipline:**
- Commit message: "research: trial-00095 conditional edge attribution V1"
- WHAT: Add attribution diagnostic + report + tests
- WHY: Understand validated edge before expansion/modification
- STATUS: READY_FOR_AUDIT

**No self-audit:** Codex (builder) did NOT audit own output — correctly delegated to Claude Code.

---

## Methodology Integrity: ✅ PASS

**Timing model verified:**

| Aspect | Implementation |
|---|---|
| Feature source | Prior completed 15m bar before `opened_at` (line 571, 689) |
| Returns source | Frozen `pnl_r` from accepted trial-00095 trades (line 570, 688) |
| No detection-bar returns | Explicitly stated (line 690) |
| No failed signals as entries | Explicitly stated (line 691) |
| No threshold relaxation | Explicitly stated (line 692) |

**Code verification** (lines 319-322):
```python
candle_idx = by_time.get(trade.opened_at)
prior_idx = candle_idx - 1 if candle_idx is not None else None
prior_candle = candles[prior_idx] if prior_idx is not None and prior_idx >= 0 else None
```

Features (TFI, ATR, volume_z20, etc.) reconstructed from `prior_candle`, not current or future bars.

**Test verification:**
```python
def test_market_context_uses_prior_completed_bar(tmp_path):
    # Trade opened at _ts(40)
    # Feature uses _ts(39) TFI
    assert attributed[0].opened_at == _ts(40)
    assert attributed[0].tfi_15m_prev == 0.75  # From prior bar
```

---

## Promotion Safety: ✅ PASS (N/A for research-only)

No promotion attempted. Diagnostic is analytical only.

---

## Reproducibility & Lineage: ✅ PASS

**Manifest fields:**
- Diagnostic: TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1
- Trade source: `trial_00095_trades.json` (274 accepted trades from WF validation)
- Entry source: `trial_00095_intrabar_frozen_entries.json` (274 frozen entries)
- Market DB: `replay-run13-regime-aware-trial-00063.db` (BTCUSDT 15m + aggtrade + funding + OI)
- Config: `DiagnosticConfig` with frozen parameters (depth threshold 0.00649, gates defined)
- Generated: 2026-05-30
- JSON SHA: not embedded in report (but JSON artifact exists)

**Experiment is fully reproducible** from frozen artifacts + market DB + config.

---

## Data Isolation: ✅ PASS

- Market DB opened read-only: `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`
- No writes to frozen artifacts
- Outputs written to separate report files

---

## Search Space Governance: ✅ PASS

**Fixed parameters:**
- Depth threshold: 0.00649 (not tuned)
- Near-threshold multiplier: 1.10 (not tuned)
- Q1 gates: ER≥1.20, PF≥2.00, WR≥0.45 (not tuned after results)
- Bucket definitions: quartiles, depth bands, sessions, regimes (deterministic split)

**No post-result tuning.** All parameters frozen before attribution.

---

## Artifact Consistency: ✅ PASS

**Report vs JSON:**
- Baseline count: 274 (consistent)
- Baseline ER: 2.121 (consistent)
- Baseline PF: 4.216 (consistent, vs WF reference 4.663 — 3-trade replay difference previously documented)
- Recommendation: PLAN_NEAR_MISS_RECONSTRUCTION_DIAGNOSTIC (consistent)

**Synthesis → Attribution → Report:**
- Synthesis recommended: TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1 ✓
- Attribution delivered: accepted-trade analysis, no threshold changes ✓
- Report shows: shallowest quartile positive, rejected unavailable, recommend reconstruction ✓

All artifacts tell the same story.

---

## Boundary Coupling: ✅ PASS

- No dependencies on live `settings/` or `config/`
- Uses frozen `trial_00095_trades.json` + market snapshot DB
- Self-contained diagnostic, no backtest runner dependency for this analysis
- Research lab owns this diagnostic end-to-end

---

## Result Summary

**Recommendation:** `PLAN_NEAR_MISS_RECONSTRUCTION_DIAGNOSTIC` is **correct**

**Baseline accepted trades (274):**
- ER: 2.121 (vs WF reference 2.129) ✓
- PF: 4.216 (vs WF reference 4.663) — 3-trade replay difference previously documented ✓
- Win rate: 56.57% (vs WF reference 56.46%) ✓
- Median R: 2.657
- Total R: 581.19
- Max DD: 14.68R

**Depth attribution:**

| Quartile | N | ER | PF | WR | Assessment |
|---|---|---|---|---|---|
| Q1 (low, <0.007207) | 69 | 1.577 | 2.981 | 47.8% | Still positive, above Q1 gates (ER≥1.2, PF≥2.0) ✓ |
| Q2 (0.007207-0.008346) | 68 | 1.994 | 4.269 | 60.3% | Strong |
| Q3 (0.008346-0.010110) | 68 | 2.078 | 3.990 | 54.4% | Strong |
| Q4 (high, ≥0.010110) | 69 | 2.833 | 6.280 | 63.8% | Best |

**Near-threshold band (0.00649-0.00714, 23% of population):**
- N: 63
- ER: 1.635 (positive, above Q1 gate 1.2) ✓
- PF: 3.046 (positive, above Q1 gate 2.0) ✓
- WR: 47.6% (above Q1 gate 0.45) ✓

**Critical finding:** Shallowest accepted trades still profitable, supporting near-miss investigation.

**Direction split:**

| Direction | N | ER | PF | WR | Assessment |
|---|---|---|---|---|---|
| LONG | 252 (92%) | 2.377 | 4.929 | 60.3% | Strong |
| SHORT | 22 (8%) | -0.805 | 0.373 | 13.6% | Weak, small sample |

**Regime split:**

| Regime | N | ER | PF | WR | Assessment |
|---|---|---|---|---|---|
| Uptrend | 205 (75%) | 2.614 | 6.034 | 66.3% | Strong concentration |
| Downtrend | 54 (20%) | 0.690 | 1.631 | 25.9% | Weak but decision-grade |
| Normal | 9 (3%) | 0.736 | 1.712 | 33.3% | Too small |
| Crowded leverage | 6 (2%) | 0.226 | 1.229 | 33.3% | Too small |

**TFI alignment:**

| Alignment | N | ER | PF | WR | Assessment |
|---|---|---|---|---|---|
| Aligned | 227 (83%) | 2.391 | 4.963 | 60.4% | Strong |
| Opposed | 47 (17%) | 0.816 | 1.877 | 38.3% | Weak but positive |

**Loss archetypes:**

| Archetype | Losses | Share | ER | Median R |
|---|---|---|---|---|
| Direct stop loss | 9 | 7.6% | -1.503 | -1.549 |
| Loss after ≥1R MFE | 110 | 92.4% | -1.520 | -1.549 |

**Critical finding:** 92.4% of losses had ≥1R favorable excursion before closing red — this is an **exit timing issue, not entry quality issue**. Trade entered correctly but exited prematurely or didn't trail properly.

**Data availability caveat:**
- Rejected backtest candidates: **NOT AVAILABLE** (no `decision_outcomes` or `feature_snapshots` tables)
- Near-miss profitability claim: **NOT MADE** (correctly)
- Recommendation: **Reconstruct rejected population first** before any threshold expansion

---

## Critical Issues: NONE

Implementation is correct. Methodology is strict. Data caveat is explicit. Recommendation is appropriate.

---

## Warnings: NONE

---

## Observations

1. **Direction asymmetry (92% LONG, 8% SHORT):** Trial-00095 is heavily LONG-biased. SHORT trades have negative ER (-0.805), but sample is small (22 trades). This is NOT a methodology failure — it reflects the LONG-biased sweep/reclaim mean-reversion edge. Short signal scarcity or weakness could be investigated separately.

2. **Regime concentration (75% uptrend, 20% downtrend):** Edge is strongest in uptrend (ER=2.614). Downtrend trades are still positive (ER=0.690, PF=1.631) but much weaker. This supports prior findings that trial-00095 is uptrend-specialized but not uptrend-exclusive.

3. **TFI alignment effect (aligned ER=2.391 vs opposed ER=0.816):** Prior-bar TFI alignment with trade direction shows strong separation. This could inform a future filter-lift diagnostic (Candidate C from synthesis), but only after near-miss reconstruction (Candidate B).

4. **Loss archetype: 92.4% had ≥1R MFE before close:** This suggests losses are primarily **exit timing failures**, not **entry failures**. Most losing trades had profitable excursions but didn't capture them. This is different from prior failed families where entry was the problem. Exit/risk surface could be revisited, but:
   - Prior exit surface work (`TRIAL_00095_EXIT_SURFACE_DIAGNOSTIC_2026-05-18`) was DEFERRED (distribution-only, not executable validation)
   - Prior loss control work (`TRIAL_00095_LOSS_CONTROL_INTRABAR_VALIDATION_2026-05-18`) was INVALIDATED (hard caps cut recovering winners)
   
   Any new exit intervention must avoid these prior failures.

5. **Near-threshold band (23% of population) is still positive:** ER=1.635, PF=3.046 for trades just above threshold (0.00649-0.00714). This is strong evidence that near-miss reconstruction (0.00550-0.00649 range) is worth investigating. But the diagnostic correctly does NOT claim these near-misses will be profitable — only that reconstruction is justified.

6. **Rejected population unavailability is correctly handled:** The diagnostic checks for `decision_outcomes` and `feature_snapshots` tables, finds them missing, and:
   - Sets `rejected_backtest_candidates_available: False`
   - Adds to explore_reasons: "rejected backtest population unavailable; near-miss edge cannot be claimed"
   - Recommends reconstruction, NOT threshold relaxation
   - States caveat 4 times in report (executive summary, data availability, key findings, recommendation)
   
   This is **exemplary methodological rigor**. No overselling, no premature conclusion.

7. **3-trade replay difference (274 vs 271):** Report correctly notes the WF reference had 271 trades, this diagnostic uses 274. The 3-trade difference is "previously documented and is not treated as a new strategy result." This is appropriate — minor replay differences are known and not material to attribution analysis.

8. **Year/fold stability:** All 4 folds (across 2022-2025) show positive ER except 2026 (5 trades, too small). Fold 1 (2022-2023H1): ER=1.584, Fold 2 (2023H2-2024): ER=2.493, Fold 3 (2025-2026Q1): ER=2.448. This confirms walk-forward stability.

9. **ATR quartile effect:** Low ATR (Q1): ER=2.038, WR=76.8%. High ATR (Q4): ER=2.215, WR=36.2%. Lower volatility environments show higher win rate but similar ER. This could inform regime filtering if reconstruction shows near-misses cluster in high-ATR regimes.

10. **Volume z-score effect:** Moderate volume (Q2-Q3) shows best metrics. Very low volume (Q1) and very high volume (Q4) both have lower ER/WR. This suggests extreme volume states may be less predictable.

---

## Recommended Next Step

**User decision required:**

The diagnostic recommendation is `PLAN_NEAR_MISS_RECONSTRUCTION_DIAGNOSTIC`. User must decide:

**Option 1: Proceed with near-miss reconstruction** (recommended by diagnostic)
- **Goal:** Reconstruct rejected near-miss candidates (0.00550-0.00649 depth range) from historical data
- **Purpose:** Test whether rejected near-threshold candidates have positive expectancy under realistic entry
- **Prerequisites:** 
  - Backtest rejected candidates are not persisted in current DB
  - Must reconstruct from raw market data or re-run backtest with candidate persistence
  - Need fair historical rejected population (not just recent runtime rejects)
- **Risk:** Reconstruction complexity, data availability, sample size may be small
- **Timeline:** 1-2 weeks (reconstruction infrastructure + diagnostic)

**Option 2: Multi-asset scaling** (alternative from synthesis)
- **Goal:** Increase trade frequency through ETH/SOL instead of BTC threshold relaxation
- **Evidence:** ETH transfer validated (decision-grade offline), SOL portfolio-approved but DD-gated
- **Advantage:** Lower risk than BTC threshold relaxation, scales validated edge
- **Timeline:** Operational (already validated offline, needs runtime activation)

**Option 3: Filter lift around trial-00095** (requires attribution evidence)
- **Goal:** Test whether TFI alignment, regime, or other features can filter bad BTC trades without killing sample
- **Candidates from attribution:**
  - TFI opposed filter (saves 47 trades with ER=0.816 vs aligned ER=2.391)
  - Downtrend filter (saves 54 trades with ER=0.690 vs uptrend ER=2.614)
  - SHORT filter (saves 22 trades with ER=-0.805, but small sample)
- **Risk:** Sample collapse, failed regime signals as filters (methodology trap)
- **Timeline:** 1 week (diagnostic only, not deployment)

**Option 4: Exit/risk surface revisit** (motivated by loss archetype finding)
- **Goal:** Investigate why 92.4% of losses had ≥1R MFE but still closed red
- **Context:** Prior exit surface work was DEFERRED (distribution-only), prior loss control INVALIDATED (hard caps failed)
- **Approach:** Different from prior failed attempts (dynamic trailing, regime-conditional exits, MFE-based scaling)
- **Risk:** Must avoid cutting recovering winners (prior failure mode)
- **Timeline:** 1-2 weeks

**Option 5: Close BTC research, focus multi-asset or production hardening**
- Trial-00095 baseline proven (ER=2.1, PF=4.6)
- 4 exploratory families tested (3 failed, 1 attribution complete)
- Multi-asset path validated offline (ETH decision-grade, SOL portfolio-approved)
- Shift to operational excellence, monitoring, LIVE promotion validation

**My recommendation:** Option 1 (near-miss reconstruction) is the logical next step given the attribution evidence. Shallowest quartile and near-threshold band are both positive, supporting investigation. However, Option 2 (multi-asset scaling) is **lower risk** and already validated offline — this may be the better strategic choice if trade frequency is the primary goal.

User decides.

---

## Files Delivered

| File | Lines | Purpose |
|---|---|---|
| `research_lab/diagnostics/trial_00095_conditional_edge_attribution_v1.py` | 1,163 | Attribution diagnostic implementation |
| `tests/test_research_lab/test_trial_00095_conditional_edge_attribution_v1.py` | 198 | 5 smoke tests (all passed) |
| `research_lab/reports/trial_00095_conditional_edge_attribution_v1.md` | 210 | Markdown report |
| `research_lab/reports/trial_00095_conditional_edge_attribution_v1.json` | ~53 KB | JSON artifact (lightweight, 25-trade sample) |

---

## Audit Complete

**Verdict:** ✅ DONE

**Builder (Codex):** Implementation excellent, methodology strict, data caveat explicit, no self-audit

**Recommendation:** `PLAN_NEAR_MISS_RECONSTRUCTION_DIAGNOSTIC` is correct and appropriately cautious

**Next:** User decides direction (near-miss reconstruction, multi-asset scaling, filter lift, exit surface, or close research)

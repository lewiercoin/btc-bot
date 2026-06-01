# AUDIT: OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1_PLAN

Date: 2026-06-01
Auditor: Claude Code
Commit: d283da71beb7fb5dba1e6982bd0f6e12bdbcc88a
Document: docs/research/OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1_PLAN.md
Type: Quant Research Planning / OANDA session edge diagnostic

## Verdict: APPROVE_PLANNING_DOCUMENT

## Document Completeness: PASS

All 19 required sections present:
1. Executive Summary ✓
2. Prior Context (section 1) ✓
3. Scope Boundaries (section 2) ✓
4. OANDA Data Inventory (section 3) ✓
5. Attribution-Informed Feature Map (section 4) ✓
6. Transferability Matrix (section 5) ✓
7. Proposed Mechanism (section 6) ✓
8. Timing Model (section 7) ✓
9. MFE Accessibility Design (section 8) ✓
10. Return and Cost Model (section 9) ✓
11. Baseline Comparison (section 10) ✓
12. Control Cohorts (section 11) ✓
13. Walk-Forward Design (section 12) ✓
14. Data Quality Requirements (section 13) ✓
15. Parameter Discipline (section 14) ✓
16. Invalidation Criteria (section 15) ✓
17. Expected Diagnostic Artifacts (section 16) ✓
18. Audit Questions for Claude (section 17) ✓
19. Recommendation ✓

## Frozen Decisions: PASS (Match User Specifications)

| Decision | User-Specified | Planning Document | Match |
|---|---|---|---|
| Breakout buffer | 0.05 * ATR14 | 0.05 * ATR14 (line 269) | ✓ |
| Entry | i+1 open | i+1 open (line 270) | ✓ |
| Primary horizon | 5 bars | 5 bars (line 271) | ✓ |
| Secondary horizon | 8 bars | 8 bars (line 272) | ✓ |
| Tertiary horizon | 10 bars (optional) | 10 bars (line 273) | ✓ |
| Risk reference | Asia extreme + 0.05*ATR14 | Asia extreme + 0.05*ATR14 (line 274) | ✓ |
| Primary cost | 0.015% | 0.015% (line 275) | ✓ |
| Cost sensitivity | 0.010%, 0.015%, 0.020% | 0.010%, 0.015%, 0.020% (line 276) | ✓ |
| Compression filter | None | None (line 277) | ✓ |

All frozen decisions match user specifications exactly.

## Methodology Integrity: PASS

### Prior Context Preserved: PASS

**XAU_USD H1 sweep/reclaim STOP (lines 53-65):**
- 11 events, ER 0.66, 1/4 positive folds
- STOP reasons: sample < 100, ER < 1.0, < 2 positive folds

**EUR_USD M15 sweep/reclaim STOP (lines 67-84):**
- 1,547 events, ER -0.2226, PF 0.7146, WR 42.79%
- Median net -0.0159%, MFE consumed 11.63%
- 0/4 positive folds
- Controls beat main (opposite direction, wide range)
- Conclusion: "timing was not the problem. The structure was accessible, but expectancy was negative after costs"

**Session reconnaissance PROCEED (lines 86-106):**
- 4 candidates tested, all structurally viable
- ASIA_RANGE ranked #1: 424 events, 84.43% FT, 18.16% FB, 11.54% MFE consumed, 4/4 stable folds

### No Sweep/Reclaim Rescue: PASS

Lines 16-21: "The mechanism is not a sweep/reclaim rescue. Prior OANDA sweep/reclaim diagnostics remain invalidated."

Lines 147-152 "Boundary Statement": "This is a new OANDA-native session edge family. It tests time-of-day liquidity expansion from the Asia range into the London open. It does not reuse equal-level sweep/reclaim logic and must not be interpreted as a rescue of failed OANDA sweep/reclaim diagnostics."

Lines 231-243 "Transferability Matrix": Explicitly excludes equal-level sweep, same-bar reclaim, TFI/CVD, funding/OI, force orders.

### OANDA-Native Edge Family: PASS

Lines 12-29 "Executive Summary": "forex-native session structure... Build the full Asia range from 00:00-07:00 UTC, wait for a close-confirmed London breakout during 07:00-09:00 UTC, enter at the next bar open"

Lines 213-218: "This diagnostic should not expect BTC trial-00095 performance. It is not trying to replicate BTC microstructure. It tests a different causal path: BTC edge: sweep/reclaim plus crypto-native flow/crowding data. OANDA session edge: Asia range compression and London institutional expansion."

This is genuinely a different edge family: session-driven forex structure, not a BTC transfer.

## Timing Discipline: PASS

Lines 313-338 "Timing Model":

| Field | Definition | Value |
|---|---|---|
| range_start_bar | First Asia M15 bar | 00:00 UTC |
| range_end_bar | Final Asia M15 bar | Last before 07:00 UTC |
| range_known_bar | Full Asia range known | 07:00 UTC open |
| detection_bar | London breakout close | bar i |
| state_known_bar | Breakout state knowable | bar i close |
| entry_candidate_bar | Earliest realistic entry | bar i+1 |
| return_start_bar | Returns measured from | bar i+1 open |

Lines 327-336:
- "Primary returns must start at entry_candidate_bar. Detection-bar returns are audit-only and may not be used as primary validation."
- "Lookahead guard: Asia range uses only bars completed before 07:00 UTC. Breakout is known only at the close of bar i. No future bars may affect detection, direction, entry, or risk reference."

No lookahead violations.

## MFE Accessibility: PASS

Lines 340-379 "MFE Accessibility Design":

**LONG:**
- MFE_before_entry: max favorable from detection close through entry-1
- MFE_after_entry: max high minus entry price from entry through horizon
- MAE_after_entry: entry minus min low over post-entry horizon

**SHORT:**
- MFE_before_entry: max favorable from detection close through entry-1
- MFE_after_entry: entry minus min low from entry through horizon
- MAE_after_entry: max high minus entry over post-entry horizon

**Consumption metric:**
- mfe_consumed_pct = MFE_before / (MFE_before + MFE_after)
- STOP gate: median > 70%
- EXPLORE target: median < 60%
- Reconnaissance baseline: 11.54%

Correct definition and gates.

## Control Cohorts: PASS

Lines 504-584 "Control Cohorts" - all 8 pre-defined from reconnaissance section 13:

1. **Random Session Timing** (line 515): shift +137 M15 bars, control for drift
2. **Opposite Direction Entry** (line 522): same detection, opposite direction
3. **Same Breakout Rule Outside London** (line 528): NY overlap 13:00-16:00 instead of London
4. **Breakout Without Prior Asia Range Compression** (line 535): top/bottom half range width buckets
5. **Compression Without Breakout** (line 545): Asia compression but no London breakout
6. **Shifted Entry +2 Bars** (line 560): entry at i+3 instead of i+1
7. **Weekday-Shuffled Control** (line 566): deterministic weekday rotation
8. **Previous-Day Range Breakout Control** (line 577): prior trading day range instead of same-day Asia

Decision control rule (lines 510-513): min 25 events for decision-grade outperformance gate.

All 8 controls match reconnaissance specification.

## Walk-Forward Design: PASS

Lines 587-614:

**4 folds:**
- 2024-01-01 to 2024-07-01 (2024 H1)
- 2024-07-01 to 2025-01-01 (2024 H2)
- 2025-01-01 to 2026-01-01 (2025)
- 2026-01-01 to latest (2026)

**Fold positive definition (lines 598-602):**
- fold count >= 25
- fold median net > 0 after 0.015% cost
- fold ER > 1.0

**Gates:**
- EXPLORE requires 3/4 folds positive
- STOP triggers if < 2/4 folds positive

Correct and consistent with prior OANDA diagnostics.

## Invalidation Criteria: PASS

**STOP Gates (lines 692-710):**
- sample < 100
- event count collapses below 200 (vs reconnaissance 424)
- median net <= 0 after 0.015% cost
- ER < 1.0
- PF < 1.2
- MFE consumed > 70%
- decision-grade control beats main
- < 2/4 folds positive
- depends on 0.010% cost or non-primary horizon
- future bars required
- returns from detection bar
- becomes sweep/reclaim/SMC/multi-mechanism

**EXPLORE Gates (lines 711-724):**
- sample >= 200
- median net > 0 after 0.015% cost
- ER > 1.3 (degraded from BTC 2.1)
- PF > 1.5
- MFE consumed < 60%
- main beats all decision-grade controls
- 3/4 folds positive
- timing verified at i+1 open
- primary 5-bar horizon viable

**INCONCLUSIVE (lines 725-735):**
- event count 100-199
- ER 1.0-1.3 with weak folds
- mixed folds but no hard STOP
- controls too small
- cost sensitivity dominates

Gates are appropriate and conservative.

## Parameter Discipline: PASS

Lines 648-689 "Parameter Discipline":

**Frozen parameters (lines 650-667):**
- All user-specified decisions frozen
- Asia range 00:00-07:00 UTC
- Breakout window 07:00-09:00 UTC
- Breakout buffer 0.05 * ATR14
- Entry i+1 open
- Primary 5 bars, secondary 8 bars, tertiary 10 bars
- Risk Asia extreme + 0.05 * ATR14
- Cost 0.015% primary, 0.010%/0.020% sensitivity
- No compression filter

**Forbidden (lines 677-689):**
- Changing Asia/London windows after results
- Changing breakout buffer after results
- Adding compression filter after results
- Adding weekday filter after results
- Selecting only long/short after outcomes
- Adding sweep/reclaim/SMC filters
- Switching to NY reversal inside this diagnostic
- Using Optuna
- Promoting to runtime

Correct discipline.

## Expected Degradation: PASS

Lines 184-224 "Attribution-Informed Feature Map":

**Lost BTC features:**
- TFI (corr 0.23, aligned ER 2.39 vs opposed 0.82) - MAJOR LOSS
- CVD - LOST
- Open interest (corr 0.13) - LOST
- Funding (corr 0.11) - LOST
- Force orders - LOST

**Expected ER ranges if edge exists (lines 219-223):**
- Strong: ER 1.5-2.0
- Marginal: ER 1.0-1.5
- Failed: ER < 1.0 or median net <= 0

Realistic expectations given degraded transfer.

## Audit Questions (Section 17): ALL PASS

1. ✓ Preserves both OANDA sweep/reclaim STOP results (lines 16-21, 53-84)
2. ✓ Avoids rescuing sweep/reclaim with session filters (lines 147-152)
3. ✓ Mechanism exactly one: ASIA_RANGE_LONDON_BREAKOUT (lines 12-14, 250-251)
4. ✓ EUR_USD M15 frozen (lines 265-266, 654-655)
5. ✓ Asia/London windows frozen (lines 267-268, 656-657)
6. ✓ 0.05*ATR14 breakout buffer justified (line 269 "Small noise filter")
7. ✓ Entry realistic at i+1 open (line 270, 659, 781)
8. ✓ Returns from entry_candidate_bar (lines 325, 327-330, 782)
9. ✓ MFE accessibility with 70% STOP threshold (lines 340-379, 703)
10. ✓ 8 control cohorts pre-defined (lines 504-584)
11. ✓ STOP/EXPLORE/INCONCLUSIVE gates clear (lines 692-735)
12. ✓ Avoids Optuna and broad search (lines 138, 687, 786)
13. ✓ Avoids production changes and OANDA bot port (lines 134-136, 787)
14. ✓ Acknowledges lost BTC features (lines 189-198)
15. ✓ Recommendation narrow: one diagnostic (line 793)

All 15 audit questions answered YES.

## Critical Issues

None.

## Warnings

None.

## Observations

1. **User-specified decisions perfectly implemented**: All 9 frozen decisions (breakout buffer, entry, horizons, risk, cost, no compression filter) match user specifications exactly. No deviation.

2. **Reconnaissance baseline preserved**: Planning document correctly references reconnaissance findings (424 events, 84.43% FT, 18.16% FB, 11.54% MFE consumed, 4/4 stable folds) without overstating them as proof of profitability.

3. **Breakout buffer justification**: 0.05*ATR14 is justified as "small noise filter, avoids exact micro-breaks" (line 269). This is reasonable - EUR_USD spread is tight, exact breakout (0 buffer) may catch micro-violations, but too large buffer (0.1*ATR) may miss valid breakouts. 0.05*ATR is a middle ground.

4. **5-bar primary + 8-bar secondary horizons**: Primary 5 bars (75 minutes) aligns with prior diagnostics and provides consistency. Secondary 8 bars matches reconnaissance follow-through measurement window. This allows comparison: does edge persist at reconnaissance window, or does it decay?

5. **No compression filter**: Correctly avoids adding post-reconnaissance filters. Reconnaissance already measured range_pct and range_atr as metadata. Adding a compression requirement now would be parameter tuning after seeing structure. Control 4 (breakout without compression) and Control 5 (compression without breakout) will test this without biasing the main cohort.

6. **Risk model natural for range breakout**: Asia opposite extreme + 0.05*ATR14 is the natural invalidation point for a range breakout. LONG stop below Asia low, SHORT stop above Asia high. This is more defensible than an arbitrary fixed % like the sweep/reclaim 0.05*ATR buffer.

7. **Cost model realistic**: 0.015% primary for EUR_USD is conservative (EUR spread is typically 0.6-1.0 pip = 0.005%-0.009%, so 0.015% round-trip includes slippage). Reconnaissance median MFE after entry ~0.0855%, so 0.015% cost is ~18% of median MFE - meaningful enough to reject weak structure.

8. **Control 5 implementation note**: Lines 555-558 acknowledge that "compression without breakout" may have lookahead risk if entry direction cannot be defined deterministically. The plan correctly states this control should be "structure-only and excluded from ER outperformance" if lookahead cannot be avoided. This is honest and prevents forcing an invalid control.

9. **Expected degradation honest**: Planning document does not claim OANDA will match BTC ER 2.1. It sets realistic expectations (ER 1.5-2.0 strong, 1.0-1.5 marginal, < 1.0 failed) given loss of TFI/OI/funding/CVD. This prevents disappointment if OANDA returns ER 1.5 - that would still be EXPLORE if gates pass.

10. **Sequential research path preserved**: Lines 107-111 correctly state the sequential approach: test ASIA_RANGE first, if STOP consider NY_REVERSAL, if both STOP return to multi-asset crypto. This matches user decision.

## Interpretation

This planning document is methodologically sound and ready for implementation. It:

- Preserves prior OANDA STOP verdicts (XAU H1, EUR M15 sweep/reclaim)
- Defines a new OANDA-native session edge family (not sweep/reclaim rescue)
- Freezes all user-specified decisions exactly as requested
- Pre-declares 8 control cohorts from reconnaissance
- Defines correct timing model (entry i+1, returns from i+1, no lookahead)
- Includes MFE accessibility design with correct gates
- Sets appropriate STOP/EXPLORE gates given degraded transfer
- Acknowledges expected degradation from lost crypto-native features
- Provides one narrow recommendation (implement diagnostic)

The mechanism is deterministic, falsifiable, and has clear invalidation criteria. If the diagnostic returns STOP, the verdict will be honest. If it returns EXPLORE, the structure will be proven tradable after realistic costs and controls.

**Critical boundary preserved**: This does NOT claim OANDA has edge. It claims reconnaissance found structure (424 events, 84% FT, 18% FB, 11% MFE consumed, 4/4 stable). The diagnostic will test whether that structure survives entry/exit rules, costs, controls, and walk-forward validation.

## Research Verdict: APPROVE_PLANNING_DOCUMENT

**Planning scope:** OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1

**Frozen decisions:**
- EUR_USD M15, Asia 00:00-07:00 UTC, London 07:00-09:00 UTC
- Breakout buffer 0.05*ATR14, entry i+1 open, primary 5 bars
- Cost 0.015%, risk Asia extreme + 0.05*ATR14
- 8 pre-defined controls, 4 folds (3/4 for EXPLORE)
- No compression filter

**Recommendation:** IMPLEMENT ONE DIAGNOSTIC

**Expected timeline:** 3-5 days for diagnostic implementation, tests, and report

**If diagnostic returns STOP:**
- Consider NY_REVERSAL_AFTER_LONDON_EXTENSION (2nd ranked from reconnaissance)
- Or return to multi-asset crypto (ETH/SOL with full BTC feature set)

**If diagnostic returns EXPLORE:**
- V2 optimization, regime filters, or OANDA bot port planning

---

**User decision required:** Approve diagnostic implementation?

A) Yes, handoff to builder for ASIA_RANGE diagnostic
B) Wait / revise planning document
C) Skip to multi-asset crypto now

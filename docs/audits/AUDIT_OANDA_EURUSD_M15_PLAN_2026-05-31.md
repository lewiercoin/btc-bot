# AUDIT: OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1_PLAN

Date: 2026-05-31
Auditor: Claude Code
Commit: d12aa4a69a48caaaeb00a823122ddf8ae53f3972
Document: docs/research/OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1_PLAN.md

## Verdict: APPROVE_PLANNING_DOCUMENT

## Methodology Integrity: PASS

- Prior XAU_USD H1 STOP verdict preserved (lines 15, 43-60)
- No attempt to reinterpret or rescue failed diagnostic
- Reconnaissance findings correctly referenced (3,419 candidates, 11.96% MFE consumed)
- Boundary statement explicitly rejects SMC rescue (lines 114-119)
- Planning scope limited to EUR_USD M15 same-bar reclaim only

## Frozen Parameter Justification: PASS

| Parameter | Value | Justification | Verdict |
|---|---|---|---|
| Sweep depth | 0.03% | EUR p25 from reconnaissance (median 0.04%, p25 0.03%); selected from structure only, before returns | JUSTIFIED |
| Reclaim buffer | 0.07 ATR | Matches reconnaissance measurement | JUSTIFIED |
| Cost | 0.015% | Conservative EUR_USD spread estimate; sensitivity at 0.010%/0.025% | JUSTIFIED |
| Entry | i+1 open | State known at i close; realistic next-bar entry | JUSTIFIED |
| Horizon | 5 bars | 75 minutes; comparable to reversal test | JUSTIFIED |

All frozen decisions are pre-declared and justified from reconnaissance structure, not from returns.

## Timing Discipline: PASS

- level_known_bar = i-1
- detection_bar = i
- state_known_bar = i close
- entry_candidate_bar = i+1
- return_start_bar = i+1

Line 345-348: "Primary returns must start at entry_candidate_bar. Detection-bar movement may be used only for MFE-before-entry audit metrics."

No lookahead violations.

## MFE Accessibility: PASS

- MFE_before_entry vs MFE_after_entry correctly separated
- mfe_consumed_pct = before / total
- STOP gate: > 70%
- EXPLORE target: < 60%
- Reconnaissance baseline: 11.96%

Design is correct and consistent with prior diagnostics.

## Control Cohorts: PASS

8 control cohorts pre-defined (section 11):
1. Sweep without reclaim
2. Reclaim without equal-level sweep
3. Random offset +137 bars
4. Shifted entry +2 bars
5. Shifted entry +3 bars
6. Opposite direction
7. Shallow sweep (depth < 0.03%)
8. Wide-range / high-volatility

Decision control rule: min 25 events for decision-grade outperformance.

## Walk-Forward Design: PASS

- 4 chronological folds over 2024-2026
- EXPLORE requires 3/4 positive
- STOP triggers if fewer than 2/4 positive
- Fold positive definition: count >= 25, median net > 0, ER > 1.0

## Invalidation Gates: PASS

STOP gates (lines 599-612):
- sample < 100
- median net <= 0 after 0.015% cost
- ER < 1.0
- PF < 1.2
- MFE consumed > 70%
- control beats main
- fewer than 2/4 folds positive
- other technical gates

EXPLORE gates (lines 614-625):
- sample >= 200
- median net > 0 after 0.015% cost
- ER > 1.3
- PF > 1.5
- MFE consumed < 60%
- main beats all controls
- 3/4 folds positive
- timing verified

Gates match prior diagnostic standards.

## Degraded Transfer Acknowledgment: PASS

Lines 159-190: Attribution-Informed Feature Map shows lost features:
- TFI (corr 0.2268 with returns) - not available
- OI (corr 0.1270) - not available
- Funding (corr 0.1111) - not available
- CVD - not available
- Force orders - not available

Lines 185-189: Expected degradation section explicitly states not to expect BTC trial-00095 performance (ER 2.121).

Strong OANDA transfer defined as ER > 1.3, not ER > 2.0.

## Parameter Discipline: PASS

Lines 584-593 explicitly forbid:
- changing min_sweep_depth_pct after results
- changing reclaim buffer after results
- selecting different windows for higher counts
- adding SMC filters
- adding session filters after outcomes
- switching instruments/timeframes after outcomes
- promoting to runtime without separate diagnostic approval

## Document Completeness: PASS

All 19 required sections present:
1. Executive Summary
2. Prior Context
3. Scope Boundaries
4. OANDA Data Inventory
5. Attribution-Informed Feature Map
6. Transferability Matrix
7. Proposed Mechanism
8. Timing Model
9. MFE Accessibility Design
10. Return and Cost Model
11. Baseline Comparison
12. Control Cohorts
13. Walk-Forward Design
14. Data Quality Requirements
15. Parameter Discipline
16. Invalidation Criteria
17. Expected Diagnostic Artifacts
18. Audit Questions for Claude
19. Recommendation

## Critical Issues

None.

## Warnings

None.

## Observations

1. **Expected sample size uncertainty**: Reconnaissance baseline shows 3,419 same-bar reclaim candidates before the 0.03% depth threshold. The frozen threshold may reduce this count, but the plan correctly pre-declares the STOP gate at sample < 100 and EXPLORE requirement at sample >= 200.

2. **8 controls vs typical 7**: This planning document defines 8 control cohorts. The additional control (wide-range/high-volatility) was also present in the prior XAU_USD diagnostic, so this is consistent. The control tests whether high-volatility context dominates the signal, which is a valid structural question for OANDA.

3. **Degraded transfer risk**: The plan correctly acknowledges that loss of TFI, OI, funding, CVD, and force orders represents major degradation. Expected ER 1.0-1.8 is realistic given the feature loss. If the diagnostic returns ER < 1.0 or fails walk-forward, the correct recommendation is STOP, not V2 tuning.

## Recommended Next Step

**Implement the diagnostic.**

Milestone: `OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1_IMPLEMENTATION`

Expected timeline: 3-5 days

Expected deliverables:
- research_lab/diagnostics/oanda_eurusd_m15_sweep_reclaim_feasibility_v1.py
- research_lab/reports/oanda_eurusd_m15_sweep_reclaim_feasibility_v1.md
- research_lab/reports/oanda_eurusd_m15_sweep_reclaim_feasibility_v1.json
- tests/test_research_lab/test_oanda_eurusd_m15_sweep_reclaim_feasibility_v1.py

Builder (Codex) should implement the diagnostic with the frozen parameters defined in this planning document. No parameter tuning is allowed after seeing results.

# AUDIT: OANDA_SESSION_EDGE_RECONNAISSANCE_V1

Date: 2026-06-01
Auditor: Claude Code
Commit: a5a1494860446393c539afcc98de91de5459fddf
Scope: OANDA session edge reconnaissance implementation and results

## Verdict: DONE_IMPLEMENTATION_CORRECT / PROCEED_JUSTIFIED

## Implementation Correctness: PASS

### Document Completeness: PASS

All 14 required sections present (planning section 13):
1. Executive Summary ✓
2. Prior OANDA Research Boundary ✓
3. Data Inventory ✓
4. Fixed Session Definitions ✓
5. Candidate Mechanism Definitions ✓
6. Structural Frequency Matrix ✓
7. Range and Volatility Analysis ✓
8. Breakout / Reversal Behavior ✓
9. MFE Accessibility ✓
10. False Breakout and Follow-Through ✓
11. Direction / Weekday / Session Splits ✓
12. Candidate Ranking ✓
13. Future Controls ✓
14. Recommendation ✓

### Timing Model: PASS

Verified in code (lines 333-335):
- `state_known_bar = detection.index` (detection bar close)
- `entry_candidate_bar = entry_index` (detection + 1)
- `return_start_bar = entry_index` (same as entry_candidate)

MFE calculation (lines 271-272):
- `mfe_before_entry` (detection to entry-1)
- `mfe_after_entry` (entry to horizon)

No lookahead violations.

### Frozen Parameters: PASS

| Parameter | Planning | Implementation | Match |
|---|---|---|---|
| Sessions | UTC fixed (planning section 7) | Lines 33-39 | ✓ |
| False breakout N | 4 bars | Line 42 | ✓ |
| Follow-through bars | 8 bars | Line 41 | ✓ |
| ATR multiple | 0.5 * ATR14 | Line 43 | ✓ |
| MFE gate | < 70% | Line 44 | ✓ |
| Min events | 200 total, 100/year | Lines 46-47 | ✓ |
| Max false breakout | < 50% | Line 48 | ✓ |

All frozen parameters match planning document.

### Candidate Mechanisms: PASS

All 4 pre-declared candidates measured (planning section 8):
1. ASIA_RANGE_LONDON_BREAKOUT (424 events EUR, 277 XAU)
2. LONDON_OPEN_RANGE_BREAKOUT (587 events EUR, 587 XAU)
3. NY_REVERSAL_AFTER_LONDON_EXTENSION (367 events EUR, 368 XAU)
4. ROLLOVER_FADE_OR_AVOIDANCE (228 events EUR, 197 XAU)

### Data Quality: PASS

| Instrument | Candles | OHLC Bad | Duplicates | Gaps >72h | Gate |
|---|---:|---:|---:|---:|---|
| EUR_USD M15 | 59,989 | 0 | 0 | 0 | PASS |
| XAU_USD M15 | 57,002 | 0 | 0 | 3 | PASS |

Same clean datasets as prior OANDA diagnostics.

### Artifact Integrity: PASS

- JSON SHA256: `eb5870b447f2ce7a12c9594ac7f069cf83116625a9ca7c4bd75bfd429d258bc3` (verified)
- Markdown report: 198 lines, all sections complete
- Python script: 853 lines, compiles successfully

## Methodology Integrity: PASS

### No Sweep/Reclaim Rescue: PASS

- Line 10: "does not rescue sweep/reclaim"
- Lines 18-19: Prior XAU/EUR sweep/reclaim diagnostics remain STOP
- Line 20: "This milestone tests session-driven forex structure only"

No attempt to rescue failed sweep/reclaim hypothesis.

### OANDA-Native Edge Family: PASS

Fixed UTC sessions tested (report section 4):
- Asia Range: 00:00-07:00 (compression)
- London Open: 07:00-09:00 (expansion)
- London Continuation: 09:00-12:00 (follow-through)
- New York Overlap: 13:00-16:00 (reversal/continuation)
- Rollover: 21:00-23:00 (liquidity gap)

These are forex-specific structures that crypto does not have. This is a legitimate new edge family.

### EUR_USD Primary, XAU_USD Comparison: PASS

- Report section 6 shows EUR_USD first in all tables
- Ranking (section 12) uses EUR_USD metrics only
- XAU_USD shown as comparison in section 6 but not used for ranking
- Recommendation (section 14) specifies EUR_USD implicitly via ranking

Correct scope discipline.

## Results Analysis: PROCEED_JUSTIFIED

### Recommended Candidate: ASIA_RANGE_LONDON_BREAKOUT (EUR_USD M15)

Metrics vs planning gates (planning section 11):

| Gate | Required | ASIA_RANGE Result | Status |
|---|---|---|---|
| Total events | >= 200 | 424 | ✓ PASS |
| Events/year | >= 100 preferred | 176.4 | ✓ PASS |
| MFE consumed | < 70% | 11.54% | ✓ PASS (< 60% preferred) |
| Follow-through | > random (50%) | 84.43% | ✓ PASS |
| False breakout | < 50% | 18.16% | ✓ PASS |
| Stable folds | >= 3/4 | 4/4 | ✓ PASS |
| Weekday independence | Not one day only | Balanced (76-93 per day) | ✓ PASS |
| Timing model | No lookahead | Verified in code | ✓ PASS |

**All PROCEED gates pass.**

### Fold Stability (Critical)

EUR_USD ASIA_RANGE_LONDON_BREAKOUT folds (report lines 113-119):

| Fold | Count | Follow-through | False breakout | MFE consumed | Stable |
|---|---:|---:|---:|---:|---|
| 2024H1 | 98 | 83.67% | 17.35% | 9.25% | True |
| 2024H2 | 101 | 89.11% | 13.86% | 10.61% | True |
| 2025 | 160 | 82.50% | 20.00% | 13.94% | True |
| 2026 | 65 | 83.08% | 21.54% | 12.37% | True |

**4/4 folds stable with consistent metrics.**

- Follow-through: 82.50% - 89.11% (narrow range)
- False breakout: 13.86% - 21.54% (low variance)
- MFE consumed: 9.25% - 13.94% (excellent accessibility across all periods)

No single fold dominates the result. Structure is persistent across 2.4 years.

### Alternative Candidates

Three other candidates also passed PROCEED gates:

**NY_REVERSAL_AFTER_LONDON_EXTENSION:**
- 367 events, 84.74% follow-through, 19.07% false breakout, 16.46% MFE consumed
- 4/4 stable folds
- Rank #2 (score 7.533)

**LONDON_OPEN_RANGE_BREAKOUT:**
- 587 events, 79.90% follow-through, 25.21% false breakout, 14.12% MFE consumed
- 4/4 stable folds
- Rank #3 (score 7.305)

**ROLLOVER_FADE_OR_AVOIDANCE:**
- 228 events, 82.46% follow-through, 28.51% false breakout, 36.36% MFE consumed
- 4/4 stable folds
- Rank #4 (score 5.971)
- Higher MFE consumed but still < 70% gate

All 4 candidates are structurally viable. Ranking correctly selects ASIA_RANGE based on combined score.

### XAU_USD Comparison

XAU_USD ASIA_RANGE_LONDON_BREAKOUT:
- 277 events, 85.92% follow-through, 18.41% false breakout, 12.55% MFE consumed
- 4/4 stable folds

XAU structure is similar to EUR. Report correctly uses EUR as primary per planning document.

## Critical Issues

None. Implementation is correct and recommendation is justified.

## Warnings

None.

## Observations

1. **Multiple viable candidates**: All 4 candidates passed PROCEED gates. This is a strong signal - OANDA session structure is real and persistent. The ranking correctly selects the best overall candidate (ASIA_RANGE) but notes that NY_REVERSAL is very close (7.533 vs 7.820).

2. **Excellent MFE accessibility**: ASIA_RANGE median MFE consumed 11.54% is exceptional. This is even better than EUR_USD M15 sweep/reclaim (11.63%), and FAR better than the 70% STOP gate. Entry timing is realistic.

3. **High follow-through rate**: 84.43% follow-through (vs 50% random) is a strong directional signal. The breakout continuation is not random noise.

4. **Low false breakout rate**: 18.16% false breakout is excellent. Most breakouts (81.84%) either follow-through or close back inside without triggering the 0.5*ATR threshold.

5. **Fold stability is decisive**: Unlike sweep/reclaim (EUR_USD M15: 0/4 positive folds), session structure is stable across all 4 time periods. This suggests the pattern is structural, not regime-dependent.

6. **Weekday balance**: Events distributed across all weekdays (76-93 per day). Not dependent on a single day's anomaly.

7. **Not a sweep/reclaim rescue**: This is genuinely a different edge family. Session breakout tests time-of-day liquidity expansion, not equal-level sweeps. No overlap with failed sweep/reclaim hypothesis.

8. **Asia→London is classic forex pattern**: ASIA_RANGE_LONDON_BREAKOUT is a well-documented forex setup (Asia consolidation → London expansion). This is OANDA-native structure, not a BTC transfer.

9. **NY_REVERSAL also strong**: NY_REVERSAL_AFTER_LONDON_EXTENSION has slightly higher follow-through (84.74%) and similar false breakout (19.07%). If ASIA_RANGE diagnostic fails, NY_REVERSAL is a strong backup candidate.

10. **ROLLOVER higher MFE consumed**: 36.36% MFE consumed suggests entry timing is later (more MFE occurs before entry). Still passes 70% gate but is weaker than the top 3 candidates.

## Interpretation

This reconnaissance validates that OANDA has session-driven structure independent of sweep/reclaim. The recommended candidate (ASIA_RANGE_LONDON_BREAKOUT) meets all PROCEED gates with strong metrics:

- **Sample size**: 424 events over 2.4 years (176.4/year) - decision-grade
- **Timing**: 11.54% MFE consumed - excellent accessibility
- **Signal quality**: 84.43% follow-through vs 18.16% false breakout - strong directional information
- **Stability**: 4/4 folds consistent - not regime-dependent
- **Independence**: Balanced across weekdays and directions - not anomaly-driven

The structure is real, reachable, directional, and persistent.

**Critical boundary**: This does NOT prove the structure is profitable. It proves the structure exists and is measurable. A full diagnostic with entry/exit rules, cost model, control cohorts, and walk-forward validation is required before any edge claim.

## Research Verdict: PROCEED_JUSTIFIED

**Hypothesis tested:** OANDA has session-driven structure (Asia range → London breakout) that is measurable, accessible, directional, and stable across time periods.

**Result:** VALIDATED (structure measurement only, not profitability)

**Evidence:**
- 424 events (>= 200 gate)
- 84.43% follow-through (>> 50% random)
- 18.16% false breakout (<< 50% gate)
- 11.54% MFE consumed (<< 70% gate)
- 4/4 stable folds

**Next step:** PROCEED_TO_FULL_PLANNING

**Recommended planning document:**

`OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1_PLAN`

**Scope:**
- Instrument: EUR_USD
- Timeframe: M15
- Mechanism: Asia range (00:00-07:00 UTC) → London breakout (07:00-09:00 UTC close confirmation) → entry at next bar open
- Entry/exit rules: freeze breakout confirmation, entry price, exit horizon
- Cost model: EUR_USD spread (0.010%-0.015% round-trip)
- Control cohorts: 8 pre-defined (section 13 of reconnaissance)
- Walk-forward: 4 folds, require 3/4 positive for EXPLORE
- Invalidation gates: sample, ER, PF, MFE, controls, folds

**Expected timeline:**
- Planning: 2-3 days
- Diagnostic implementation: 3-5 days
- Total: ~1 week to STOP/EXPLORE verdict

**If diagnostic returns STOP:**
- Consider NY_REVERSAL as backup (2nd ranked, similar metrics)
- Or return to multi-asset crypto (ETH/SOL with full BTC feature set)

**If diagnostic returns EXPLORE:**
- V2 optimization, regime filters, or direct OANDA bot port

---

**User decision required:** Approve planning for ASIA_RANGE_LONDON_BREAKOUT diagnostic?

A) Yes, proceed to planning
B) Test NY_REVERSAL instead (2nd ranked)
C) Test multiple candidates in parallel (not recommended - dilutes focus)
D) Return to multi-asset crypto (ETH/SOL)

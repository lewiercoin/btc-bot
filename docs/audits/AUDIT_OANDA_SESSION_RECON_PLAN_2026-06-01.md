# AUDIT: OANDA_SESSION_EDGE_RECONNAISSANCE_V1_PLAN

Date: 2026-06-01
Auditor: Claude Code
Document: User-submitted planning document (not yet committed)
Type: Quant Research Planning / OANDA session-based edge reconnaissance

## Verdict: APPROVE_PLANNING_DOCUMENT

## Methodology Integrity: PASS

### Prior Context Preserved: PASS

- Section 1 correctly states XAU_USD H1 STOP (sample collapse)
- Section 1 correctly states EUR_USD M15 STOP (negative expectancy, control outperformance)
- Section 3 "Critical Boundary" explicitly forbids sweep/reclaim rescue
- States: "OANDA sweep/reclaim transfer is invalidated, but OANDA itself is not invalidated"
- Section 5 requires reading all 5 prior OANDA documents

### No Sweep/Reclaim Rescue: PASS

Section 3 lists forbidden interpretations:
- "Sweep/reclaim failed, so tune it with sessions."
- "Add London filter to make failed sweep/reclaim pass."
- "Use session filter on the previous OANDA diagnostic."
- "Try to rescue EUR_USD M15 sweep/reclaim."

Explicitly states: "This is a new edge family: Session-driven forex structure."

### Edge Family Justification: PASS

Section 1 correctly identifies OANDA-native structure:
- Asia range compression
- London open liquidity expansion
- New York overlap
- Rollover liquidity gaps
- Day-of-week and session-specific behavior

These are forex-specific features that crypto does not have. This is a legitimate new edge family, not a BTC transfer.

## Frozen Decisions: PASS

### Sessions Pre-Declared: PASS

Section 7 "Fixed Session Definitions" (all UTC):
- Asia Range: 00:00-07:00
- London Open: 07:00-09:00
- London Continuation: 09:00-12:00
- New York Overlap: 13:00-16:00
- Rollover: 21:00-23:00

States: "No session boundaries may be changed after seeing results."

### Candidate Mechanisms Pre-Declared: PASS

Section 8 defines 4 candidates before implementation:
1. **ASIA_RANGE_LONDON_BREAKOUT** - Build Asia range, detect London breakout, measure follow-through
2. **LONDON_OPEN_RANGE_BREAKOUT** - Opening hour range, breakout during 08:00-12:00
3. **NY_REVERSAL_AFTER_LONDON_EXTENSION** - Fade extended London moves during NY overlap
4. **ROLLOVER_FADE_OR_AVOIDANCE** - Measure noise/gaps during 21:00-23:00

Each candidate has clear definition and structure questions.

### Metrics Pre-Declared: PASS

Section 9 pre-declares:
- False breakout definition: N=4 bars, 0.5*ATR threshold
- Follow-through definition: 0.5*ATR14 excursion within 8 bars
- MFE gate: median consumed < 70% (preferred < 60%)
- Minimum sample: 100 events/year or 200 total

No parameter tuning allowed after results.

## Timing Discipline: PASS

Section 10 "Timing Model" defines:

**Breakout candidates:**
- range_known_bar → detection_bar → state_known_bar → entry_candidate_bar → return_start_bar

**Reversal candidates:**
- extension_known_bar → detection_bar → state_known_bar → entry_candidate_bar → return_start_bar

States: "Primary returns, if later diagnostic is built, must start at entry_candidate_bar, not detection."

## MFE Accessibility: PASS

Section 9 "MFE / MAE Accessibility":
- MFE before entry
- MFE after entry
- MAE after entry
- MFE consumed %
- Time from entry to max MFE

MFE gate:
- Structure timing-viable if median MFE consumed < 70%
- Preferred candidate has median MFE consumed < 60%

## Decision Gates: PASS

Section 11 "Decision Criteria":

**PROCEED_TO_FULL_PLANNING:**
- >= 200 total events
- >= 100 events/year preferred
- Median MFE consumed < 70% (preferably < 60%)
- Follow-through/reversal rate above random baseline
- False breakout rate < 50%
- Consistent across 3/4 folds
- Not dependent on one weekday/period
- Clear timing model, no lookahead

**STOP_SESSION_EDGE:**
- No candidate reaches 200 events
- False breakout >= 50%
- MFE consumed > 70%
- Structures random/contradictory
- No stable fold behavior
- Only useful as avoidance, not entry

**DATA_BLOCKED / INCONCLUSIVE:**
- Data missing/gaps
- < 18 months data
- 100-199 events (borderline)
- Mixed structure

Gates are appropriate and conservative.

## Scope Discipline: PASS

**In scope (Section 4):**
- EUR_USD M15 primary, XAU_USD M15 comparison only
- Fixed UTC session windows
- Structure measurement (range, breakout, follow-through, false breakout, MFE, direction, weekday)
- One recommendation

**Out of scope:**
- No production code
- No OANDA bot port
- No Optuna
- No full PnL diagnostic
- No SMC logic
- No sweep/reclaim rescue
- No parameter tuning after results
- No promotion/settings changes

Scope is tight and clear.

## Controls Pre-Defined: PASS

Section 12 "Controls For Future Diagnostic" lists 8 potential controls:
1. Random session timing
2. Opposite direction entry
3. Same breakout rule outside target session
4. Breakout without compression
5. Compression without breakout
6. Shifted entry +2 bars
7. Weekday-shuffled control
8. Previous-day range breakout control

States: "These must be documented now to prevent post-hoc diagnostic design."

## Data Quality Requirements: PASS

Section 6 "Data Requirements":
- Primary: EUR_USD M15
- Comparison: XAU_USD M15 (not to be selected unless EUR fails structurally)
- Date range: 2024-01-01 to latest (reuse prior OANDA inventory)
- Minimum: 18 months, 30,000 M15 candles
- Data gate: PASS / PARTIAL / BLOCKED
- Quality checks: candle count, timestamps, OHLC integrity, gaps

## Deliverable Structure: PASS

Section 13 "Deliverable Format":

Required markdown report with 14 sections:
1. Executive Summary
2. Prior OANDA Research Boundary
3. Data Inventory
4. Fixed Session Definitions
5. Candidate Mechanism Definitions
6. Structural Frequency Matrix
7. Range and Volatility Analysis
8. Breakout / Reversal Behavior
9. MFE Accessibility
10. False Breakout and Follow-Through
11. Direction / Weekday / Session Splits
12. Candidate Ranking
13. Future Controls
14. Recommendation

Optional JSON with SHA256 if large (not committed).

## Interpretation Language: PASS

Section 14 forbids overstated claims:
- ❌ "OANDA has edge"
- ❌ "London breakout works"
- ❌ "Proceed to production"
- ❌ "Use Optuna to tune until it passes"
- ❌ "Add session filter to rescue sweep/reclaim"

Only allows:
- ✓ "OANDA sweep/reclaim transfer is invalidated"
- ✓ "This candidate is structurally viable for planning"
- ✓ "A separate diagnostic is required"

## Expected Outcome: PASS

Section 15 requires exactly one recommendation:
- PROCEED_TO_FULL_PLANNING (specify one mechanism)
- STOP_SESSION_EDGE
- DATA_BLOCKED
- INCONCLUSIVE

## Critical Issues

None.

## Warnings

None.

## Observations

1. **Comprehensive reconnaissance scope**: This planning document is more detailed than the prior sweep/reclaim reconnaissance. This is appropriate because it's testing a new edge family (session-based) rather than just measuring an existing BTC hypothesis. The 4 candidate mechanisms are well-defined and cover the main forex session patterns.

2. **XAU_USD as comparison**: The plan correctly states XAU is "comparison only" and "must not become the selected diagnostic target unless the report explicitly justifies why EUR failed structurally and XAU is materially better." This prevents scope creep while allowing structural comparison.

3. **Rollover as candidate**: Candidate D (ROLLOVER_FADE_OR_AVOIDANCE) is explicitly testing whether rollover 21:00-23:00 is tradable or should be avoided. This is good - it may find that rollover is metadata (avoidance window) rather than entry signal. The plan allows for this outcome.

4. **False breakout pre-declared**: N=4 bars, 0.5*ATR threshold is frozen. This is appropriate for M15 (60 minutes lookback). Builder should not tune this.

5. **Follow-through pre-declared**: 0.5*ATR14 excursion within 8 bars (2 hours). This is reasonable for session-driven moves. Builder should not tune this.

6. **External source review optional**: Section 5 states "Optional external source review is recommended but not mandatory for this reconnaissance." This is reasonable - session-based forex edges are well-documented in literature (London open, Asia range, etc.), but reconnaissance should measure OANDA structure independently, not just cite papers.

7. **Fold stability required**: PROCEED gate requires "consistent behavior across at least 3 of 4 chronological folds." This prevents cherry-picking one good period.

8. **No Optuna in this milestone**: Explicitly out of scope. If reconnaissance returns STOP, user can consider Optuna as separate milestone with hardened protocol.

## Audit Questions (Section 16)

1. Does the plan avoid rescuing failed sweep/reclaim? **YES** (Section 3)
2. Are sessions fixed before results? **YES** (Section 7, no changes allowed)
3. Are candidate mechanisms pre-declared? **YES** (Section 8, 4 candidates)
4. Is this reconnaissance, not diagnostic implementation? **YES** (Section 2, 4)
5. Are MFE accessibility and timing discipline included? **YES** (Sections 9, 10)
6. Are false breakout and follow-through definitions pre-declared? **YES** (Section 9)
7. Are data quality gates explicit? **YES** (Section 6)
8. Is Optuna explicitly out of scope? **YES** (Section 4)
9. Does the report require exactly one recommendation? **YES** (Section 15)
10. Does it avoid production changes? **YES** (Section 4)

All 10 audit questions: **PASS**

## Recommended Next Step

**Approve planning document and proceed to implementation.**

Milestone: `OANDA_SESSION_EDGE_RECONNAISSANCE_V1`

Expected deliverable:
- `docs/research/OANDA_SESSION_EDGE_RECONNAISSANCE_V1_REPORT.md`

Optional artifact:
- `research_lab/reports/oanda_session_edge_reconnaissance_v1.json` (local if large)

Expected timeline: 3-5 days

Builder (Codex recommended - similar to prior reconnaissance structure) should:
1. Read all 5 prior OANDA documents (Section 5)
2. Implement structure measurement for 4 pre-declared candidates (Section 8)
3. Measure all required metrics (Section 9)
4. Deliver exactly one recommendation (Section 15)

After reconnaissance:
- **If PROCEED:** Create planning document for selected mechanism (e.g., `OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1_PLAN`)
- **If STOP:** Consider Optuna framework or return to multi-asset crypto
- **If INCONCLUSIVE:** User decision on whether to proceed with weak evidence or stop
- **If DATA_BLOCKED:** Fix data issues or stop OANDA research

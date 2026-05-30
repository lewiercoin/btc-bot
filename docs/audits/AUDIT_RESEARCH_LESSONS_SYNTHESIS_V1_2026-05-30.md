# AUDIT: RESEARCH_LESSONS_SYNTHESIS_AND_TRIAL_00095_REVERSE_ENGINEERING_V1_PLAN

**Date:** 2026-05-30  
**Auditor:** Claude Code  
**Commit:** `e6962b6` (research: trial-00095 lessons synthesis and reverse engineering plan)  
**Builder:** Cascade  
**Type:** Research Synthesis / Planning Document

---

## Verdict: ✅ APPROVE PLANNING DOCUMENT

**Planning quality:** Excellent  
**Synthesis completeness:** Comprehensive (24 milestones inventoried)  
**Failure taxonomy:** Clear and decisive  
**Recommended diagnostic:** Correct (analytical, not speculative)  
**Scope discipline:** Strict boundaries, no rescue disguise

---

## Executive Summary

This synthesis document correctly identifies the research program's current state: trial-00095 is the only validated BTCUSDT 15m edge, and three exploratory families (liquidation, volatility breakouts, regime shifts) have been invalidated with clear failure modes.

**The recommended next step is correct:** `TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1` — an analytical diagnostic to understand the validated edge before attempting expansion, filtering, or modification.

**Key strengths:**
- Comprehensive inventory: 24 prior milestones with accurate classification
- Clear failure taxonomy: timing vs predictive vs control-cohort failures
- Treats trial-00095 as benchmark to understand, not religion to defend
- Single narrow recommendation (not a menu)
- Explicit data caveats (rejected populations may be unavailable)
- Strict scope boundaries preventing threshold rescue and post-hoc filtering
- Runtime data sourcing correctly specified (production server, not local stale DB)

**No critical issues found.** This planning document is ready for user decision.

---

## Audit Questions (From Planning Spec)

### 1. Does this synthesis include the relevant prior milestones?

✅ **YES** — Comprehensive inventory of **24 milestones/artifacts** (lines 42-66):

**Coverage verified:**
- ✓ trial-00095 baseline validation (WF, conditional edge, grid search, exit surface)
- ✓ SMC research (sequence, MFE accessibility, sweep taxonomy)
- ✓ Liquidation family (15m + 5m follow-up)
- ✓ Volatility breakouts (volume-confirmed range breakout)
- ✓ Regime shifts (deterministic ADX/CHOP + probabilistic HMM filtered)
- ✓ Timeframe experiments (5m standalone, 15m+5m overlay, 5m multi-candle)
- ✓ Multi-asset transfers (ETH validated, SOL DD-gated, portfolio replay)

**Classifications used:**
- `VALIDATED_BASELINE` — trial-00095, sweep/reclaim singular edge
- `INVALIDATED_TIMING` — SMC mitigation, liquidation burst, delayed labels, 15m+5m overlay
- `INVALIDATED_NO_EDGE` — volume breakout, regime shifts (despite good MFE accessibility)
- `INVALIDATED_CONTROL_BEAT_MAIN` — HMM all controls beat main
- `INVALIDATED_CONTROLLED_RELAXATION` — grid search threshold relaxation
- `DEFERRED` — conditional edge (incomplete), exit surface (needs executable validation), SOL (DD risk)
- `INCONCLUSIVE_TIMEFRAME_VALUE` — 5m quality pass but frequency fail
- `VALIDATED_TRANSFER_CANDIDATE` — ETH transfer
- `VALIDATED_PORTFOLIO_PATH` — multi-asset full pipeline

All classifications are accurate and evidence-based.

---

### 2. Does it separate timing failures from no-edge failures?

✅ **YES** — Explicit taxonomy section (lines 68-129) with clear definitions:

**Timing Failures** (lines 70-84):
> "Timing failures mean the market pattern may exist, but the actionable state is known too late."

Examples:
- SMC mitigation: median entry 8 bars after sweep, MFE consumed before entry
- Liquidation burst: 100% MFE consumed on both 15m and 5m
- 15m+5m overlay: confirmation arrives after useful entry window
- Delayed sweep labels: detection-bar returns attractive, label-available returns collapsed

Rule: "Do not rescue these with detection-bar returns. Only an earlier deterministic signal can reopen the family."

**Predictive Failures** (lines 86-100):
> "Predictive failures mean timing was acceptable, but the signal did not forecast profitable movement."

Examples:
- Volume breakout: 14.95% MFE consumed (good timing), ER=-0.092 (no edge), controls beat main
- Regime shift deterministic: 21.5% MFE consumed (excellent timing), ER=-0.027, 0/4 folds positive
- Regime shift HMM: 22.8% MFE consumed (excellent timing), ER=-0.122, ALL controls beat main

Rule: "Do not add filters to rescue these as standalone entries. If reused at all, they must be controls or attribution features around trial-00095, not entry signals."

**This distinction is critical** and correctly applied throughout the document.

---

### 3. Does it avoid rescuing closed families?

✅ **YES** — Multiple explicit constraints:

**In failure taxonomy** (lines 99-100):
> "If reused at all, they must be controls or attribution features around trial-00095, not entry signals."

**In candidate C description** (lines 243-250):
> "failed standalone regime signals may be misused as rescue filters"

**In scope boundaries** (line 345):
> "use failed families as standalone entries" — MUST NOT

**In invalidation criteria** (line 307):
> "failed standalone HMM/regime/breakout/liquidation signals are used as entry signals" → STOP

**In executive summary** (line 34):
> "The correct next step is not another speculative standalone edge family."

**Verdict:** The document explicitly and repeatedly forbids reopening closed families as entry signals. The only permitted reuse is as attribution features or filters around trial-00095, and even that requires Candidate A (attribution) first to show plausible evidence.

---

### 4. Does it treat trial-00095 as benchmark rather than untouchable doctrine?

✅ **YES** — Analytical framing, not dogmatic:

**Working hypothesis** (lines 143-145):
> "trial-00095 works because it captures a specific liquidity mean-reversion response that persists long enough for 15m entry, while its depth/flow/confluence thresholds reject shallow noise."

This is an **analytical claim** (mechanism hypothesis), not religious doctrine.

**Unknown questions** (lines 147-154):
- Which exact feature combinations separate winners from losers?
- Whether near-miss populations have any stable positive expectancy?
- Whether current PAPER/runtime distribution matches historical?
- Whether BTC trade count should be expanded through near-misses or multi-asset?
- Whether any filter can improve drawdown without destroying sample?

These are **critical questions about trial-00095**, not defensive assertions.

**In recommended diagnostic** (lines 277-278):
> "It treats trial-00095 as benchmark, not religion: the goal is to understand where it is strong, where it is weak, and what claims remain unsupported."

**Verdict:** The document frames trial-00095 as a validated edge that should be understood deeply before modification. This is the correct scientific stance — respect the evidence, but interrogate it analytically.

---

### 5. Does it honestly document timeframe coverage?

✅ **YES** — Comprehensive table (lines 156-171) and honest interpretation (lines 173-178):

**Table structure:**
- Columns: 15m, 5m, 1h/4h, MTF entry, MTF context, Verdict
- 12 research items mapped

**Key findings documented:**
- Most validated evidence comes from 15m BacktestRunner trial-00095
- 5m standalone tested: quality improved, frequency failed (INCONCLUSIVE_TIMEFRAME_VALUE)
- 15m+5m overlay tested: hybrid failed (INVALIDATED_TIMING)
- 5m multi-candle tested: frequency improved, quality collapsed (INVALIDATED_NO_EDGE)
- 1h/4h features exist in strategy context but most recent diagnostics were single-timeframe for methodological clarity

**Interpretation** (lines 173-178):
> "The project has not been purely 15m. It has tested 5m standalone, 15m+5m overlays, and 5m follow-ups for timing accessibility."

> "The most promising MTF evidence is not a new 5m signal; it is the observation that 5m sweep/reclaim quality improved but did not solve frequency. The subsequent 15m+5m energy overlay failed."

**Verdict:** Honest accounting of timeframe experiments. Does not oversell 5m results, does not hide failures.

---

### 6. Is the recommended diagnostic narrow enough?

✅ **YES** — Single diagnostic, purely analytical:

**Recommendation** (line 270):
> `TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1`

**Scope** (lines 272-278):
- Analyze existing validated trial-00095 population
- Reconstruct pre-entry features
- Explain winners/losers
- Do NOT change thresholds
- Do NOT generate new entries
- Do NOT apply failed regime/HMM signals as entries

**Research questions** (lines 280-287):
1. Which pre-entry features separate winners from losers?
2. Are losses concentrated in specific regimes/sessions/volatility states?
3. Is trade scarcity caused by depth gate, reclaim gate, flow/confluence gates, risk/governance vetoes, or market regime?
4. Are near-threshold accepted trades still profitable enough to justify near-miss reconstruction?
5. Are worst losses structurally different from ordinary losers?
6. Do findings support expanding BTC entries, filtering, changing exits/risk, or scaling through ETH?

**Expected output** (line 369):
> "attribution report, feature bucket tables, loss archetype map, trade scarcity map, and exactly one next recommendation"

**Verdict:** This is **analytical reverse engineering**, not speculative exploration. Narrow scope, clear questions, no implementation in same milestone. Correct.

---

### 7. Are invalidation criteria defined before results?

✅ **YES** — Section 9 (lines 302-326) defines STOP/EXPLORE/INCONCLUSIVE upfront:

**STOP criteria** (lines 304-311):
- Requires changing trial-00095 thresholds before attribution
- Primary returns measured from detection rather than actual trial entry
- Failed standalone signals used as entry signals
- Attribution cannot reconstruct enough features
- Reduces to post-hoc filter selected after seeing outcomes
- Runtime data sourced from stale local DB
- Sample size falls below decision-grade after segmentation

**EXPLORE criteria** (lines 313-319):
- Stable feature bucket explains meaningful share of losses
- Candidate filter improves PF/DD without killing sample
- Near-threshold accepted trades show monotonic quality gradient
- Loss archetypes suggest exit/risk intervention different from failed hard caps
- Multi-asset scaling stronger than BTC threshold relaxation

**INCONCLUSIVE criteria** (lines 321-326):
- Accepted-trade features incomplete
- Winner/loser patterns weak or contradictory
- Segmentation leaves too few trades per bucket
- Runtime sample too small for anything beyond hypothesis generation

**Verdict:** All criteria are measurable, defined upfront, and appropriate for an attribution diagnostic.

---

### 8. Does it correctly handle runtime data sourcing?

✅ **YES** — Multiple explicit mentions:

**In scope section** (line 126):
> "runtime recent-trade analysis must query the production server, not local `storage/btc_bot.db`."

**In candidate D** (line 261):
> "must query production server, not local DB"

**In required data** (line 295):
> "optional production server recent trades only if explicitly included as a separate runtime context section"

**In STOP criteria** (line 310):
> "runtime data is sourced from local `storage/btc_bot.db` rather than production server" → STOP

**In scope boundaries** (line 347):
> "query stale local runtime DB for live status/trades" → MUST NOT

**Verdict:** Runtime data sourcing is correctly specified in 5 separate locations. The document explicitly references `docs/DATA_SOURCES.md` and forbids using stale local data. This is critical for operational accuracy.

---

### 9. Does it prevent threshold tuning and post-hoc filtering?

✅ **YES** — Explicit constraints throughout:

**In STOP criteria** (line 305):
> "the proposed diagnostic requires changing trial-00095 thresholds before attribution" → STOP

**In STOP criteria** (line 309):
> "the diagnostic reduces to a post-hoc filter selected after seeing outcomes" → STOP

**In scope boundaries** (line 343):
> "tune thresholds after seeing results" → MUST NOT

**In scope boundaries** (line 344):
> "implement near-miss expansion inside the same milestone" → MUST NOT

**In candidate B warning** (line 235):
> "can easily become threshold rescue"

**Verdict:** The document explicitly prevents both threshold tuning and post-hoc filtering. Attribution must explain existing trades without changing the strategy. Near-miss expansion and filter lift are deferred to separate diagnostics that require attribution evidence first.

---

## Section-by-Section Assessment

| Section | Lines | Required? | Quality | Assessment |
|---|---|---|---|---|
| Scope | 8-20 | ✅ | Excellent | Clear allowed/not-allowed, cleanup items deferred appropriately |
| Executive Summary | 22-41 | ✅ | Excellent | Concise, accurate, single recommendation |
| Prior Research Inventory | 42-66 | ✅ | Excellent | 24 milestones, accurate classifications, comprehensive coverage |
| Failure Mode Taxonomy | 68-129 | ✅ | Excellent | Critical timing vs predictive distinction, control-cohort section strong |
| Trial-00095 Success Hypothesis | 131-154 | ✅ | Excellent | Analytical framing, known facts + unknowns, not dogmatic |
| Timeframe Coverage Audit | 156-178 | ✅ | Excellent | Honest accounting, 5m experiments documented accurately |
| Open Research Gaps | 180-212 | ✅ | Excellent | 6 gaps identified, all evidence-based, filter lift warning appropriate |
| Candidate Next Diagnostics | 214-264 | ✅ | Excellent | 4 candidates (A/B/C/D), risks noted, dependencies specified |
| Recommended Next Diagnostic | 266-300 | ✅ | Excellent | Single choice (A), 6 research questions, data caveat critical |
| Pre-Result Invalidation Criteria | 302-326 | ✅ | Excellent | STOP/EXPLORE/INCONCLUSIVE defined upfront, all measurable |
| Scope Boundaries | 328-347 | ✅ | Excellent | Strict may/must-not lists, no ambiguity |
| Audit Questions For Claude | 349-362 | ✅ | Complete | All 9 questions answered above |
| Recommendation | 363-371 | ✅ | Excellent | PLAN ONE DIAGNOSTIC, clear mechanism, expected output |

**All required sections present and well-executed.**

---

## Critical Strengths

1. **Comprehensive inventory:** 24 prior milestones with accurate failure classifications
2. **Clear failure taxonomy:** Timing vs predictive vs control-cohort, with explicit rescue-prevention rules
3. **Analytical framing:** Treats trial-00095 as validated edge to understand, not untouchable doctrine
4. **Single narrow recommendation:** Attribution first, expansion/filtering only after evidence
5. **Data integrity:** Explicit caveats about rejected populations, runtime data sourcing
6. **Scope discipline:** Strict boundaries preventing threshold rescue, post-hoc filtering, same-milestone expansion
7. **Dependency ordering:** B and C candidates explicitly require A (attribution) first

---

## Critical Issues: NONE

No bugs, no methodological flaws, no scope creep, no rescue disguise.

---

## Warnings: NONE

---

## Observations

1. **HMM `explore_gate_passed` handling:** Correctly described as "clarity issue only, not a result bug" (line 20). This was questioned in the planning spec but is actually correct — the field is metadata, STOP gates take precedence. No action needed.

2. **Dependency tracking deferred:** hmmlearn dependency not in manifest (line 18). Correctly deferred to cleanup milestone. Recommendation: add to `research_lab/requirements-research.txt` in next cleanup pass.

3. **Rejected population caveat:** Lines 298-299 explicitly note that backtest rejected-sweep population may not be persisted, limiting fair near-miss claims. This is **critical honesty** — the document does not oversell what the attribution can deliver.

4. **Multi-asset path preserved:** ETH transfer validated, SOL DD-gated but portfolio-approved. Attribution may recommend multi-asset scaling instead of BTC threshold relaxation. This is the correct prioritization — scale validated edge rather than rescue failed signals.

5. **Runtime forensic candidate (D):** Described as hypothesis generation only, not statistically decisive (lines 255-264). Correct framing — small sample, operational context, production server query required.

6. **Filter lift candidate (C):** Explicitly warned about misusing failed regime signals (lines 243-250). Requires attribution evidence first. Sample collapse risk noted. This is the correct defensive posture — don't rescue failed standalone signals by calling them "filters."

---

## Recommended Next Step

**APPROVE** this planning document.

**Next milestone:** `TRIAL_00095_CONDITIONAL_EDGE_ATTRIBUTION_V1`

**User decision required:**
1. Approve synthesis and proceed to attribution diagnostic?
2. Select builder (Codex or Cascade) for attribution implementation?
3. Or pivot to different direction (multi-asset scaling, runtime forensic, close research program)?

**If user approves attribution diagnostic:**
- Builder implements research-only attribution diagnostic
- No code changes to trial-00095
- No threshold tuning
- Output: attribution report + ONE next recommendation (near-miss, filter, exit, multi-asset, or STOP)
- Claude Code audits attribution results before any follow-up work

**Timeline:** 1-2 weeks (attribution requires reconstructing features for 271 frozen trades and analyzing segmentation)

---

## Files Delivered

| File | Lines | Purpose |
|---|---|---|
| `docs/research/RESEARCH_LESSONS_SYNTHESIS_AND_TRIAL_00095_REVERSE_ENGINEERING_V1_PLAN.md` | 371 | Research synthesis + attribution planning |

---

## Audit Complete

**Verdict:** ✅ APPROVE PLANNING DOCUMENT

**Synthesis quality:** Excellent — comprehensive, honest, analytically rigorous

**Recommended diagnostic:** Correct — understand success before attempting expansion

**Next:** User decision on direction

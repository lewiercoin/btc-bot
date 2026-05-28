# AUDIT FRAMEWORK: REVERSE QUANT EDGE REVIEW

**Date:** 2026-05-27  
**Auditor:** Claude Code  
**Target:** Codex reverse quant engineering review  
**Expected deliverable:** `docs/research/REVERSE_QUANT_EDGE_REVIEW_2026-05-27.md`

---

## Context

User is frustrated with potentially conservative research stance. Wants deeper, more creative, independent review to determine whether V1 taxonomy + SMC sequence truly exhausted the SMC/sweep-reclaim source space, or whether a more fundamental reverse-engineered edge remains undiscovered.

**User's explicit instruction:** "Be strict, but do not be reflexively conservative. Do not suppress exploration just because two hypotheses failed."

**Audit stance:**

- ✅ Invalidated research must stay invalidated
- ✅ Trial-00095 remains the benchmark
- ✅ Benchmark is NOT religion
- ✅ Genuinely new edge families can be proposed if testable, timing-safe, and source/code-grounded
- ❌ Do NOT suppress exploration reflexively
- ❌ Do NOT approve sloppy/cherry-picked directions

---

## Audit Checklist

### 1. Code Inspection vs Document Summarization

**Question:** Did Codex inspect actual code, or just summarize existing docs?

**PASS criteria:**
- ✅ References specific code files: `core/feature_engine.py`, `core/signal_engine.py`, `research_lab/analysis_smc_sequence_edge_feasibility_v1.py`
- ✅ Cites specific line numbers or function implementations
- ✅ Compares implemented logic against source descriptions
- ✅ Identifies gaps between current implementation and external sources

**FAIL criteria:**
- ❌ Only references planning documents and audit reports
- ❌ No code file paths or line numbers
- ❌ Vague statements like "the bot uses sweep/reclaim" without implementation details

**Weight:** HIGH — can't reverse-engineer without inspecting actual implementation

---

### 2. Independent Research vs Repeated References

**Question:** Did Codex perform independent open-source/source research, or just repeat prior references?

**PASS criteria:**
- ✅ NEW external sources beyond Makuchaku/LuxAlgo/joshyattridge/PyIndicators
- ✅ Specific GitHub repos, papers, or articles with URLs
- ✅ Assessment of each source (useful / bad repainting / discretionary / not applicable)
- ✅ Evidence of web search or repository inspection

**FAIL criteria:**
- ❌ Only repeats the 4 sources from planning documents
- ❌ No new repos, papers, or articles
- ❌ No classification of source quality

**Weight:** MEDIUM — independent research shows initiative, but not strictly required if code inspection is thorough

---

### 3. Invalidation Boundary Clarity

**Question:** Did Codex clearly separate what V1 invalidated, what SMC invalidated, and what remains untested?

**PASS criteria:**
- ✅ Explicit statement: "V1 invalidated: immediate reclaim, delayed reclaim, true breakout from label-available timing"
- ✅ Explicit statement: "SMC invalidated: mitigation+1 entry timing (PF 1.061 vs 4.0)"
- ✅ Explicit statement: "NOT invalidated: displacement+1 entry, flow-confirmed classification, etc."
- ✅ Clear boundary: "mitigation entry failed, not the entire SMC sequence"

**FAIL criteria:**
- ❌ Vague: "SMC doesn't work"
- ❌ Conflates V1 and SMC failures
- ❌ Does not list what was NOT tested

**Weight:** HIGH — clarity on boundaries prevents over-generalization

---

### 4. MFE Accessibility Analysis

**Question:** Did Codex identify where MFE becomes inaccessible?

**PASS criteria:**
- ✅ Bar-by-bar MFE decay analysis (where does MFE peak?)
- ✅ Comparison: MFE before entry (0.011565) vs MFE after entry (0.004916)
- ✅ Identification: "Most MFE consumed between bar X and bar Y"
- ✅ Hypothesis: "Accessible edge is likely at bar offset Z"

**FAIL criteria:**
- ❌ No MFE timing analysis
- ❌ Only states "mitigation is late" without quantifying when edge decays

**Weight:** CRITICAL — this is the core reverse-engineering task

---

### 5. Earliest Knowable Signal Identification

**Question:** Did Codex identify earliest knowable signal candidates?

**PASS criteria:**
- ✅ Bar-by-bar knowability analysis: "At sweep detection bar, we know X. At displacement bar, we know X+Y."
- ✅ Lookahead check: "Displacement is knowable at bar close because body/range/close are determined"
- ✅ Identification of earliest realistic entry bar (e.g., displacement+1, structure+1)
- ✅ Comparison to trial-00095 entry timing

**FAIL criteria:**
- ❌ No knowability timeline
- ❌ Proposes signals that require future bars (lookahead)

**Weight:** CRITICAL — knowability is what separates tradable from visual patterns

---

### 6. Best-Practice Quant Comparison

**Question:** Did Codex compare current bot design against best-practice quant research?

**PASS criteria:**
- ✅ Comparison to external backtest results (e.g., "External SMC PF 2.17 vs our 1.061 vs trial-00095 4.6")
- ✅ Assessment of trial-00095's entry timing vs SMC mitigation timing
- ✅ Evaluation: "Is trial-00095 already capturing the displacement edge?"
- ✅ Industry pattern comparison (aggressive vs conservative entry, limit vs market orders)

**FAIL criteria:**
- ❌ No external benchmarks
- ❌ No comparison to trial-00095 timing
- ❌ Treats trial-00095 as black box

**Weight:** MEDIUM — provides context for whether we're missing something obvious

---

### 7. Trial-00095 Challenge Without Dismissal

**Question:** Did Codex challenge trial-00095 without dismissing it?

**PASS criteria:**
- ✅ Acknowledges trial-00095 as validated baseline (ER 2.1, PF 4.6)
- ✅ Questions: "Could a different edge family beat trial-00095?"
- ✅ States criteria for legitimate challenge (ER > 2.5, PF > 5.0, walk-forward validated)
- ✅ Does NOT propose replacing trial-00095 without evidence

**FAIL criteria:**
- ❌ Treats trial-00095 as sacred (no challenges allowed)
- ❌ Proposes replacing trial-00095 without meeting validation bar
- ❌ Ignores trial-00095 entirely

**Weight:** MEDIUM — balance between respect for validated work and openness to improvement

---

### 8. Lookahead / Detection-Bar Trap Avoidance

**Question:** Did Codex avoid detection-bar / lookahead traps?

**PASS criteria:**
- ✅ Explicit rejection of detection-bar returns as success
- ✅ All proposed entry timings use entry_candidate_bar or label_available_bar
- ✅ No "delayed reclaim rescue" or "true breakout rescue" proposals
- ✅ Timing discipline preserved from V1 lesson

**FAIL criteria:**
- ❌ Proposes "let's measure delayed reclaim differently"
- ❌ Suggests using detection-bar returns
- ❌ Ignores V1 timing lesson

**Weight:** CRITICAL — lookahead violations ship fake edges

---

### 9. Concrete Direction Limit (≤5)

**Question:** Did Codex propose at most 5 concrete next research directions?

**PASS criteria:**
- ✅ Maximum 5 directions
- ✅ Each direction has: hypothesis, differentiation, earliest signal bar, lookahead risk, data, complexity, pass/fail criteria
- ✅ Prioritization: which to test first, which are conditional, which to defer
- ✅ Each direction is DIFFERENT from V1/SMC (not parameter tweaks)

**FAIL criteria:**
- ❌ Lists 10+ vague ideas
- ❌ Directions lack specifications
- ❌ No prioritization (everything is equally important)
- ❌ Directions are V1/SMC parameter rescues

**Weight:** HIGH — focus matters, menus don't

---

### 10. Rejection of Weak Ideas

**Question:** Did Codex reject weak ideas instead of listing everything?

**PASS criteria:**
- ✅ Explicit "DO NOT pursue" list (e.g., regime filters, detection-bar returns, visual patterns)
- ✅ Reasoning for each rejection
- ✅ Clear distinction: "This is worth testing" vs "This is not worth testing"

**FAIL criteria:**
- ❌ Every idea is "could be useful"
- ❌ No rejections, only caveats
- ❌ Menu of options without filtering

**Weight:** MEDIUM — shows judgment, not just brainstorming

---

### 11. External Source Classification

**Question:** Did Codex include external repos/articles/queries and classify their usefulness?

**PASS criteria:**
- ✅ List of repos/articles with URLs
- ✅ Classification: useful concept / benchmark candidate / bad repainting / discretionary / not applicable
- ✅ Specific assessment: "This source recommends X, which aligns/conflicts with our findings"

**FAIL criteria:**
- ❌ No external sources beyond planning document references
- ❌ Sources listed but not classified
- ❌ Uncritical acceptance of external claims

**Weight:** LOW — nice to have, not required if reverse-engineering is strong

---

### 12. Hard Final Recommendation

**Question:** Did Codex give a hard final recommendation?

**PASS criteria:**
- ✅ ONE recommendation (not a menu)
- ✅ Clear next step: "PLAN X" or "STOP research, validate trial-00095"
- ✅ Reasoning for recommendation
- ✅ If "PLAN X", includes builder selection (Codex or Cascade) and timeline estimate

**FAIL criteria:**
- ❌ "Here are 5 options, user decides"
- ❌ Ambiguous: "could pursue X or Y or Z"
- ❌ No recommendation at all

**Weight:** HIGH — research needs direction, not menus

---

## Special Focus: Reverse Quant Engineering Quality

**The core test:** "Do not ask whether a pattern exists visually. Ask whether any part of it is knowable early enough to trade with positive expectancy after costs."

**Evidence of GOOD reverse quant engineering:**

1. ✅ **Accessibility timeline:** "MFE peaks at bar +X. At bar +X, facts A, B, C were knowable. Entry at bar +X+1 would access Y% of total MFE."

2. ✅ **Knowability analysis:** "Displacement is knowable at bar close because OHLC are determined. Structure shift requires waiting for next bar's close to confirm breakout."

3. ✅ **Edge decay quantification:** "Detection-bar return: 0.004348. Displacement+1 return: UNTESTED. Mitigation+1 return: 0.000558. Net after costs: -0.000442."

4. ✅ **Institutional timing hypothesis:** "Institutions execute at displacement (absorption phase). Retail sees confirmation at mitigation (late entry)."

5. ✅ **Trial-00095 comparison:** "Trial-00095 enters at sweep+reclaim+1 (1-2 bars from sweep). SMC mitigation entry is 8 bars from sweep. Displacement+1 would be 2-3 bars from sweep."

**Evidence of POOR reverse quant engineering:**

1. ❌ **Pattern listing:** "CHOCH, MSS, OB, FVG, PPDD, RJB could all be useful"
2. ❌ **Vague timing:** "Earlier entry might help"
3. ❌ **No quantification:** "SMC patterns contain signal"
4. ❌ **Visual description:** "Institutional footprints are visible in the chart"
5. ❌ **No accessibility analysis:** "We should test order blocks next"

---

## Verdict Scale

### APPROVE MEMO

**Criteria:**
- All CRITICAL checklist items PASS
- At least 8/12 total items PASS
- Hard final recommendation given
- Clear next step identified
- Evidence of reverse quant engineering quality

**Action:**
- Document approved as-is
- Proceed to next step if user approves recommendation

---

### APPROVE WITH REQUIRED CHANGES

**Criteria:**
- 6-7/12 items PASS
- At least 1 CRITICAL item FAIL but fixable
- Useful content but incomplete
- Clear gaps that can be filled

**Required changes list:**
- Specific missing elements
- Code inspection needed if not done
- MFE analysis needed if missing
- Hard recommendation needed if ambiguous

**Action:**
- Return to Codex with specific fix list
- Re-audit after fixes

---

### REJECT

**Criteria:**
- Multiple CRITICAL items FAIL
- Less than 6/12 items PASS
- No reverse quant engineering evidence
- Repeated old docs without code inspection
- Sloppy/cherry-picked directions (detection-bar returns, lookahead bias)
- No hard recommendation

**Rejection reasons:**
- Failed to inspect code
- Failed to reverse-engineer accessibility
- Proposed lookahead-biased directions
- Listed patterns without timing analysis
- No independent thinking, just document summarization

**Action:**
- Reject memo
- Do NOT proceed to implementation
- Consider whether research should STOP entirely if Codex can't deliver quality review

---

## Post-Audit Actions

### If APPROVE or APPROVE WITH CHANGES:

1. Update MILESTONE_TRACKER.md with review status
2. If recommendation is "PLAN displacement entry diagnostic":
   - User approves or vetoes
   - If approved, generate handoff to Codex for planning document
3. If recommendation is "STOP research":
   - User confirms decision
   - Close SMC research question
   - Focus on trial-00095 PAPER validation

### If REJECT:

1. Deliver rejection verdict to user
2. Explain why reverse quant engineering failed
3. Recommend: STOP research if quality review is not achievable

---

## Audit Signature Placeholder

**Auditor:** Claude Code  
**Date:** 2026-05-27  
**Verdict:** [To be filled after Codex delivers review]  
**Critical issues:** [To be filled]  
**Required changes:** [To be filled]  
**Recommendation:** [To be filled]

---

## Key Principles for This Audit

1. **Be strict on methodology, open to ideas:**
   - ✅ Strict: no lookahead, no detection-bar, no vague patterns
   - ✅ Open: displacement entry, flow classification, accessibility studies

2. **Benchmark is not religion:**
   - Trial-00095 is the quality bar, not the only architecture
   - New edge families can challenge it IF they meet validation standard

3. **Reverse-engineering is the test:**
   - Good review: "Edge accessible at bar X because Y was knowable"
   - Bad review: "Let's try CHOCH next"

4. **Invalidation boundaries matter:**
   - V1 invalidated: delayed labels from label-available timing
   - SMC invalidated: mitigation+1 entry timing
   - NOT invalidated: displacement+1, flow classification, cluster quality

5. **Focus over menus:**
   - ONE recommendation, not options
   - ≤5 directions, prioritized
   - Weak ideas rejected explicitly

---

**This audit framework will be applied when Codex delivers `docs/research/REVERSE_QUANT_EDGE_REVIEW_2026-05-27.md`.**

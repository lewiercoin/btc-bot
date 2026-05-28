# AUDIT: QUANT_RESEARCH_OPERATING_MODEL_V1

**Date:** 2026-05-28  
**Auditor:** Claude Code  
**Commit:** `1eb9c27921167a1342a1fa0de574c5a9c18d1c15`  
**Branch:** `deploy/multi-asset-paper-v1`  
**Milestone Type:** Documentation-only (role extension)

---

## Verdict: DONE

**Implementation:** Production-grade documentation correctly implements approved proposal.

**Scope compliance:** Documentation-only, no production code or strategy changes.

---

## Audit Summary

| Criterion | Status | Notes |
|---|---|---|
| **Deliverables Complete** | ✅ PASS | All Phase 1 files delivered |
| **Content Complete** | ✅ PASS | All required sections present |
| **Documentation Quality** | ✅ PASS | Clear, actionable, well-structured |
| **AGENTS.md Integration** | ✅ PASS | Workflow modes section added, link added |
| **CLAUDE.md Integration** | ✅ PASS | Quant research challenger mode added |
| **CASCADE.md Integration** | ✅ PASS | Quant research builder mode added |
| **Key Principle Included** | ✅ PASS | "Dangerous in research, safe in production" prominently placed |
| **Permanent Lessons Codified** | ✅ PASS | V1/SMC/MFE lessons included |
| **No Production Code Changes** | ✅ PASS | Zero Python, JSON, or production files modified |
| **Optional Files Deferred** | ✅ PASS | CODEX.md and templates intentionally deferred |
| **Commit Message Quality** | ✅ PASS | WHAT/WHY/STATUS format followed |

---

## Deliverables Compliance (4/4 PASS)

### 1. `docs/QUANT_RESEARCH_OPERATING_MODEL.md` (CREATE)
✅ **PASS**

**File created:** 315 lines

**Required sections present:**
1. ✅ Role in Project Workflow (lines 7-26)
2. ✅ Workflow Modes (lines 27-53)
3. ✅ Quant Research Builder Mode (lines 54-136)
4. ✅ Quant Research Auditor Mode (lines 137-165)
5. ✅ Timing Discipline (lines 166-197)
6. ✅ Source Research Requirements (lines 198-209)
7. ✅ Reverse Engineering Protocol (lines 210-227)
8. ✅ Benchmark Rule: Trial-00095 (lines 228-244)
9. ✅ STOP / Exploration Balance (lines 245-258)
10. ✅ Research Verdict Scale (lines 259-286)

**Additional sections (bonus):**
- Production Safety Boundary (lines 287-297)
- Documentation and Artifact Rules (lines 298-300)
- Summary Rules (lines 301-315)

**Key principle placement:** Line 5 (prominent, near top) ✅

**Content quality:**
- Clear, actionable language ✅
- Concrete examples (e.g., "MFE consumed > 70%") ✅
- Permanent lessons codified (V1, SMC, MFE) ✅
- Timing bar definitions explicit ✅
- Source research requirements detailed ✅
- Benchmark rules balanced (trial-00095 as standard, not religion) ✅
- STOP/explore rules prevent both over-conservative and endless rescue ✅

**Authority chain preserved:**
- `AGENTS.md` remains top authority ✅
- This doc is canonical for quant research ✅
- No role confusion (builder builds, Claude audits, user decides) ✅

---

### 2. `AGENTS.md` (UPDATE)
✅ **PASS**

**Section added:** "Workflow Modes" (36 lines, after "Workflow: Generator-Evaluator Model")

**Five modes defined:**
1. ✅ Implementation Mode
2. ✅ Research Lab Infrastructure Mode
3. ✅ Quant Research / Edge Discovery Mode ⭐ (with link to `docs/QUANT_RESEARCH_OPERATING_MODEL.md`)
4. ✅ Promotion Mode
5. ✅ Live Operations / Incident Mode

**Link added in "Source of Truth Files" section:**
- ✅ `docs/QUANT_RESEARCH_OPERATING_MODEL.md` — quant research / edge discovery workflow

**Preservation check:**
- ✅ `AGENTS.md` remains top authority
- ✅ No rewrite of existing sections
- ✅ Focused addition only

---

### 3. `CLAUDE.md` (UPDATE)
✅ **PASS**

**Section added:** "Quant Research Challenger Mode" (43 lines, after "Research Lab Audit Standard")

**Content includes:**
- ✅ Additional audit axes table (10 axes: methodology rigor, source coverage, repo inspection, timing discipline, entry realism, lookahead risk, edge accessibility, novelty vs rescue, exploration suppression, creativity vs cherry-picking)
- ✅ Research verdict scale:
  - Planning verdicts (4 types)
  - Diagnostic implementation verdicts (3 types)
  - Research result verdicts (3 types)
- ✅ Link to full guidance: `docs/QUANT_RESEARCH_OPERATING_MODEL.md`
- ✅ Reminder: Claude remains auditor (not builder), user retains veto

**Preservation check:**
- ✅ Claude's core auditor role unchanged
- ✅ Builder/auditor separation maintained
- ✅ No role confusion

---

### 4. `CASCADE.md` (UPDATE)
✅ **PASS**

**Section added:** "Quant Research Builder Mode" (48 lines, after "Implementation Checklist")

**Content includes:**
- ✅ Required steps before coding (6 steps):
  1. Source research (if new edge family)
  2. Mechanism extraction
  3. Timing model
  4. Baseline comparison
  5. Invalidation criteria
  6. Minimal research plan (first response)
- ✅ After diagnostic runs: result summary with ONE recommendation
- ✅ Link to full guidance: `docs/QUANT_RESEARCH_OPERATING_MODEL.md`
- ✅ Reminder: Cascade NEVER audits own output, Claude Code exclusive auditor, user approves direction

**Preservation check:**
- ✅ Cascade's builder-only role unchanged
- ✅ Self-audit ban preserved
- ✅ No role confusion

---

## Content Quality Analysis

### Key Principle Prominence
✅ **PASS**

Line 5 of `docs/QUANT_RESEARCH_OPERATING_MODEL.md`:
> "The goal is not to make agents more cautious. The goal is to make them more dangerous in research while remaining safe in production."

Placement: Immediately after header, before section 1. Highly visible. ✅

### Permanent Lessons Codified
✅ **PASS**

Lines 188-197 of `docs/QUANT_RESEARCH_OPERATING_MODEL.md`:

**From V1 Taxonomy Diagnostic:**
- ✅ Delayed labels measured from `detection_bar` create fake edge
- ✅ Measure from `entry_candidate_bar` or `label_available_bar`, not detection

**From SMC Sequence Diagnostic:**
- ✅ Median MFE before entry: 0.011565
- ✅ Median MFE after entry: 0.004916
- ✅ If MFE consumed before entry, edge not tradable

**From MFE Accessibility Diagnostic:**
- ✅ No post-sweep knowable state had positive expectancy
- ✅ Question shifted from pattern existence to early knowability

All three lessons explicitly codified. ✅

### Timing Discipline Codification
✅ **PASS**

**Bar definitions (lines 169-178):**
- ✅ `detection_bar` — first bar where raw event occurs
- ✅ `state_known_bar` — first bar where state knowable without future data
- ✅ `confirmation_bar` — bar that confirms state
- ✅ `entry_candidate_bar` — earliest realistic entry bar
- ✅ `label_available_bar` — bar where outcome label known
- ✅ `return_start_bar` — bar from which primary returns measured

**Primary return rule (line 178):**
> "`return_start_bar` must equal `entry_candidate_bar` for primary metrics."

Clear and explicit. ✅

**MFE accessibility rule (line 186):**
> "If MFE consumed before entry is greater than 70%, the edge is not tradable."

Quantified threshold. ✅

### Source Research Requirements
✅ **PASS**

**When mandatory (lines 199-202):**
- New edge families ✅
- External named mechanisms ✅
- GitHub/TradingView/Pine/paper-derived ideas ✅
- Explicit user requests ✅
- Benchmark challenges based on external evidence ✅

**Required source fields (lines 203-204):**
- Source name, URL, type, inspected artifact ✅
- Extracted mechanism ✅
- Classification ✅
- Determinism assessment ✅
- Lookahead/repainting assessment ✅
- Data availability ✅
- Applicability conclusion ✅

**Source classification (lines 66-73):**
- ✅ Useful concept
- ✅ Benchmark candidate
- ✅ Needs validation
- ✅ Bad/repainting
- ✅ Discretionary
- ✅ Not applicable

Comprehensive and actionable. ✅

### Reverse Engineering Protocol
✅ **PASS**

**Core question (lines 212-213):**
> "Where does opportunity become knowable, and is there tradable movement left?"

**Required questions (lines 214-221):**
- ✅ Did pattern fail because no edge or late confirmation?
- ✅ Did MFE occur before entry?
- ✅ Is there earlier knowable state?
- ✅ Is earlier state deterministic?
- ✅ Is earlier state tradable after costs?
- ✅ Is next proposal genuinely new or rescue?

**Move earlier or stop (lines 222-223):**
- ✅ If opportunity knowable too late, move earlier or stop
- ✅ Do NOT rescue same failed hypothesis with looser parameters

**New vs rescue classification (lines 224-227):**
- ✅ New hypothesis: different mechanism, data, state, causal path
- ✅ Rescue: relaxed thresholds, detection-bar returns, new filters on invalidated signal

Explicit and operational. ✅

### Benchmark Rules
✅ **PASS**

**Trial-00095 status (lines 229-233):**
- ✅ Active validated baseline (ER ~2.1, PF ~4.6, walk-forward validated)
- ✅ Benchmark, rollback point, comparison standard
- ✅ Evidence that known edge exists
- ✅ NOT proof no other edge exists
- ✅ NOT permission to skip source research
- ✅ NOT permission to reject all exploration

**Legitimate challenge criteria (lines 236-243):**
- ✅ ER > 2.1
- ✅ PF > 4.0
- ✅ Walk-forward validated
- ✅ Timing realistic (entry at `state_known_bar+1` or later)
- ✅ MFE accessibility (< 70% consumed before entry)
- ✅ Control cohort beaten

Balanced: trial-00095 as standard, not religion. ✅

### STOP / Exploration Balance
✅ **PASS**

**When to STOP (lines 247-249):**
- ✅ Invalidation criteria met
- ✅ Accessible state space exhausted
- ✅ Rescue attempts detected
- ✅ Research ROI negative
- ✅ Benchmark already captures earliest accessible state
- ✅ No earlier deterministic signal exists

**When to OPEN new family (lines 250-252):**
- ✅ Mechanism genuinely new
- ✅ External evidence supports testing
- ✅ Reverse engineering indicates earlier signal
- ✅ Data source orthogonal to failed work
- ✅ Hypothesis not parameter tweak
- ✅ Expected edge has different causal basis

**Examples of new families (line 252):**
- Order-flow imbalance after price-action failures ✅
- Liquidation cascade signals using force-order data ✅
- Funding/OI stress mechanisms ✅
- Volatility contraction regimes ✅

Concrete examples prevent ambiguity. ✅

### Research Verdict Scale
✅ **PASS**

**Planning verdicts (lines 261-269):**
- ✅ `APPROVE_PLANNING_DOCUMENT`
- ✅ `REJECT_LOOKAHEAD`
- ✅ `REJECT_NOT_NEW_HYPOTHESIS`
- ✅ `REJECT_SOURCE_COVERAGE_INSUFFICIENT`
- ✅ `REJECT_CHERRY_PICKING`
- ✅ `INCONCLUSIVE_DATA_GAP`

**Diagnostic implementation verdicts (lines 270-277):**
- ✅ `DONE_IMPLEMENTATION_CORRECT`
- ✅ `REJECT_TIMING_VIOLATION`
- ✅ `REJECT_NO_CONTROL_COHORT`
- ✅ `REJECT_LOOKAHEAD`
- ✅ `REJECT_CHERRY_PICKING`

**Research result verdicts (lines 278-286):**
- ✅ `HYPOTHESIS_PASSED`
- ✅ `HYPOTHESIS_INVALIDATED`
- ✅ `INCONCLUSIVE_DATA_GAP`
- ✅ `REJECT_LOOKAHEAD`
- ✅ `REJECT_NOT_NEW_HYPOTHESIS`

Comprehensive verdict vocabulary. ✅

---

## Production Code Safety Check
✅ **PASS**

**Files changed (commit 1eb9c27):**
```
AGENTS.md                              |  36 ++++
CASCADE.md                             |  48 +++++
CLAUDE.md                              |  43 +++++
docs/QUANT_RESEARCH_OPERATING_MODEL.md | 315 +++++++++++++++++++++++++++++++++
4 files changed, 442 insertions(+)
```

**Python files modified:** 0 ✅  
**JSON files modified:** 0 ✅  
**Production code paths touched:** 0 ✅

**Verified safe paths:**
- ❌ `core/` — not modified ✅
- ❌ `execution/` — not modified ✅
- ❌ `orchestrator.py` — not modified ✅
- ❌ `settings.py` — not modified ✅
- ❌ `research_lab/` — not modified ✅
- ❌ `backtest/` — not modified ✅

**Only documentation modified:**
- ✅ `AGENTS.md`
- ✅ `CASCADE.md`
- ✅ `CLAUDE.md`
- ✅ `docs/QUANT_RESEARCH_OPERATING_MODEL.md`

Documentation-only milestone confirmed. ✅

---

## Optional Files Deferred
✅ **PASS**

**Per handoff instructions, the following files were intentionally NOT created:**
- `CODEX.md` — deferred to follow-up milestone if needed ✅
- `docs/templates/QUANT_RESEARCH_PLAN_TEMPLATE.md` — deferred ✅
- `docs/templates/QUANT_RESEARCH_AUDIT_TEMPLATE.md` — deferred ✅

**Rationale:** Phase 1 core documentation only. Templates can be added later if workflow shows they are useful. Prevents premature bureaucracy.

Deferral was correct decision. ✅

---

## Commit Message Quality
✅ **PASS**

**Message:**
```
docs: add quant research operating model

WHY: Current role files govern implementation and audit workflow well, but edge-discovery work requires formal rules for source research, reverse engineering, timing discipline, MFE accessibility, and STOP/explore decisions.

WHAT:

- Created docs/QUANT_RESEARCH_OPERATING_MODEL.md (canonical authority)

- Updated AGENTS.md (workflow modes section)

- Updated CLAUDE.md (quant research challenger mode)

- Updated CASCADE.md (quant research builder mode)

STATUS: Documentation-only, no production code or strategy changes
```

**Compliance:**
- ✅ WHAT / WHY / STATUS format
- ✅ Clear scope statement
- ✅ Accurate file list
- ✅ Documentation-only confirmation

Message quality: excellent. ✅

---

## Authority Chain Preservation
✅ **PASS**

**Top authority:**
- `AGENTS.md` remains top authority for workflow, role assignment, source-of-truth hierarchy ✅

**Quant research authority:**
- `docs/QUANT_RESEARCH_OPERATING_MODEL.md` is canonical for quant research ✅

**Role boundaries:**
- Claude Code: independent auditor/evaluator/technical selector ✅
- Codex: default builder ✅
- Cascade: alternative builder ✅
- User: strategic decision and veto ✅

**Audit discipline:**
- Builders build ✅
- Claude audits ✅
- User decides ✅
- Builder output never self-audited ✅

No role confusion. ✅

---

## Critical Issues

**NONE.**

---

## Warnings

**NONE.**

---

## Observations

### 1. Documentation Density: High Value

The new `docs/QUANT_RESEARCH_OPERATING_MODEL.md` is 315 lines but extremely dense with actionable rules:
- 13 sections
- 6 tables
- ~40 explicit rules
- 10+ concrete examples
- 3 permanent lessons codified

This is a reference document, not a narrative. It will be heavily used during research milestones.

### 2. Timing Discipline Now Non-Negotiable

Lines 167-197 make timing discipline as non-negotiable as layer separation is for implementation:
- Bar definitions explicit
- Return measurement rule explicit
- MFE accessibility threshold quantified (70%)
- Permanent lessons codified

Future research milestones will be audited against this standard.

### 3. Source Research Formalized

Lines 198-209 make source research a first-class requirement:
- When mandatory (new edge families, external mechanisms)
- What to inspect (implementation code, not README)
- How to classify (useful/bad/discretionary/N/A)
- How to extract mechanisms

External intelligence is now part of the workflow, not ad-hoc.

### 4. Reverse Engineering Protocol Established

Lines 210-227 prevent endless rescue attempts:
- Core question: "Where does opportunity become knowable?"
- Move earlier or stop (do NOT rescue)
- New vs rescue classification explicit

This will prevent parameter-rescue cycles.

### 5. Trial-00095 as Benchmark, Not Religion

Lines 228-244 balance respect for validated work with openness to new edges:
- Trial-00095 is the benchmark ✅
- New edges can challenge with validated evidence ✅
- Challenge criteria explicit (ER > 2.1, PF > 4.0, etc.) ✅

This prevents both:
- Ignoring trial-00095 (over-aggressive)
- Treating trial-00095 as unbeatable (over-conservative)

### 6. STOP / Explore Balance Codified

Lines 245-258 prevent both extremes:
- STOP criteria explicit (invalidation met, state space exhausted, rescue attempts, etc.)
- OPEN criteria explicit (genuinely new mechanism, external evidence, earlier signal, etc.)

This gives Claude and builders clear guidance for when to stop vs when to explore.

### 7. Research Verdict Vocabulary Expanded

Lines 259-286 add research-specific verdicts:
- `APPROVE_PLANNING_DOCUMENT` ✅
- `HYPOTHESIS_PASSED` / `HYPOTHESIS_INVALIDATED` ✅
- `REJECT_LOOKAHEAD` / `REJECT_NOT_NEW_HYPOTHESIS` / `REJECT_SOURCE_COVERAGE_INSUFFICIENT` ✅

This vocabulary will appear in future research audits.

### 8. Optional Files Correctly Deferred

Codex correctly deferred:
- `CODEX.md` (symmetry with `CASCADE.md` nice but not urgent)
- Research plan template (can add later if workflow shows need)
- Research audit template (can add later if workflow shows need)

Phase 1 focused on core rules. Templates can be added in Phase 2 if workflow shows they prevent errors or save time.

---

## Recommended Next Step

**Next milestone options:**

### Option 1: Documentation Audit Complete — Return to Research (RECOMMENDED)

**Status:** Documentation milestone DONE.

**Next:** Resume research work using the new operating model.

**Candidate milestone:** `ORDER_FLOW_LIQUIDATION_EDGE_DISCOVERY_V1_PLANNING`

**Why recommended:**
- Documentation is production-grade
- Timing discipline now codified
- Source research requirements formalized
- Reverse engineering protocol established
- STOP/explore balance explicit
- New operating model should be tested in real research before adding templates

**How it would work:**
1. User approves next research direction
2. Builder (Codex or Cascade) receives handoff tagged "quant research planning"
3. Builder follows new operating model:
   - Source research (GitHub, papers, repos)
   - Mechanism extraction
   - Timing model definition
   - MFE accessibility design
   - Baseline comparison
   - Control cohort
   - Invalidation criteria
   - Minimal research plan before code
4. Claude audits using new research verdict scale:
   - `APPROVE_PLANNING_DOCUMENT` or
   - `REJECT_LOOKAHEAD` / `REJECT_SOURCE_COVERAGE_INSUFFICIENT` / etc.
5. If approved, builder implements diagnostic
6. Claude audits diagnostic implementation
7. Builder runs diagnostic, delivers result summary with ONE recommendation
8. Claude audits research result: `HYPOTHESIS_PASSED` / `HYPOTHESIS_INVALIDATED` / etc.

This will test whether the new operating model is:
- Clear enough to guide builder
- Rigorous enough to prevent lookahead/rescue
- Balanced enough to allow exploration without suppression

---

### Option 2: Add Phase 2 Templates (Lower Priority)

**Status:** Core documentation DONE. Templates optional.

**Next:** Create optional templates if user wants them before next research milestone.

**Files:**
- `CODEX.md` — Codex-specific builder guidance (parallel to `CASCADE.md`)
- `docs/templates/QUANT_RESEARCH_PLAN_TEMPLATE.md` — research plan template
- `docs/templates/QUANT_RESEARCH_AUDIT_TEMPLATE.md` — research audit template

**Why lower priority:**
- Core rules already in `docs/QUANT_RESEARCH_OPERATING_MODEL.md`
- Templates may feel bureaucratic if added before workflow is tested
- Better to test workflow first, then add templates if they prevent errors

**Recommendation:** Defer Phase 2 until after at least one research milestone using new operating model.

---

### Option 3: Audit Recent Research Against New Standard (Lower Priority)

**Status:** Documentation DONE. Recent research milestones were audited under old standard.

**Next:** Retrospectively audit recent research (V1, SMC, MFE) against new operating model to verify lessons are codified.

**Why lower priority:**
- Recent research already audited and closed
- Lessons already incorporated into new operating model
- Retrospective audit adds no new information
- Better to apply new standard to future research

**Recommendation:** Skip retrospective audit. Apply new standard prospectively.

---

## Final Recommendation

**DONE. Apply new operating model to next research milestone.**

**Next step:**
1. User approves next research direction (e.g., order flow / liquidation edge discovery)
2. Claude Code generates handoff tagged "quant research planning"
3. Builder follows new operating model
4. Claude audits using new research verdict scale

**Estimated timeline for next milestone:**
- Planning document: 1-2 days
- Source research + planning audit: 1 day
- Diagnostic implementation: 3-5 days
- Diagnostic audit: 1 day
- Diagnostic run + result summary: 1 day
- Result audit: 1 day
- **Total: 8-11 days for complete research milestone with new operating model**

**Optional Phase 2 (templates):** Can be added later if workflow shows need.

---

## Audit Signature

**Auditor:** Claude Code  
**Date:** 2026-05-28  
**Verdict:** DONE  
**Blocking issues:** None  
**Required changes:** None  
**Next milestone:** User decision (research or optional templates)

---

**AUDIT COMPLETE.**

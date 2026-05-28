# QUANT RESEARCH OPERATING MODEL V1 — Role Extension Proposal

**Date:** 2026-05-28  
**Author:** Claude Code  
**Status:** PROPOSAL (not yet approved for implementation)

---

## Executive Summary

### Verdict

**Do current role files adequately cover implementation workflow?**  
✅ YES. `AGENTS.md`, `CLAUDE.md`, `CASCADE.md` effectively govern builder/auditor workflow for implementation milestones.

**Do they adequately cover edge-discovery workflow?**  
⚠️ PARTIALLY. Current files support research lab *infrastructure* (optimization, walk-forward, promotion gates) but lack formal guidance for:
- Reverse edge engineering
- Source research and external intelligence
- Earliest-knowable-signal analysis
- Edge accessibility auditing
- When to explore vs when to stop
- Designing new edge families beyond existing bot mechanisms

**What is missing?**

1. **Formal quant research mode definition** — distinct from implementation and research-lab-infra modes
2. **Builder duties for edge discovery** — not just coding, but source research, mechanism extraction, timing analysis
3. **Claude auditor duties for research quality** — beyond code correctness to methodology rigor, source coverage, timing discipline
4. **Timing discipline codification** — detection/state_known/entry/label separation as permanent research rules
5. **Source research requirements** — when external research is mandatory, how to assess source quality
6. **Reverse engineering protocol** — starting from failure points, MFE accessibility, earliest knowable signals
7. **Benchmark challenge rules** — trial-00095 as standard, not religion
8. **STOP/explore balance** — preventing both over-conservative blocking and endless parameter rescue

**Should we modify existing files or add a new operating model document?**  
**BOTH.**

- **Add** `docs/QUANT_RESEARCH_OPERATING_MODEL.md` as the canonical quant research authority
- **Update** `AGENTS.md` to link the new document and define quant research as a distinct workflow mode
- **Update** `CLAUDE.md` to add "Quant Research Challenger Mode" section
- **Update** `CASCADE.md` to add "Quant Research Builder Mode" section  
- **Optional:** Add `CODEX.md` for consistency (currently Codex duties only defined in `AGENTS.md`)

**What exact files should be updated later?**

| File | Change Type | Purpose |
|---|---|---|
| `docs/QUANT_RESEARCH_OPERATING_MODEL.md` | CREATE | Canonical quant research authority |
| `AGENTS.md` | UPDATE | Add mode definition, link to quant research doc |
| `CLAUDE.md` | UPDATE | Add "Quant Research Challenger Mode" section |
| `CASCADE.md` | UPDATE | Add "Quant Research Builder Mode" section |
| `CODEX.md` | CREATE (optional) | Codex-specific builder guidance |
| `docs/templates/QUANT_RESEARCH_PLAN_TEMPLATE.md` | CREATE (optional) | Research plan template |
| `docs/templates/QUANT_RESEARCH_AUDIT_TEMPLATE.md` | CREATE (optional) | Research audit template |

---

## 1. Executive Verdict

*See Executive Summary above.*

---

## 2. Current Workflow Analysis

### `AGENTS.md` — Engineering Discipline Authority

**What it handles well:**
- Commit discipline (WHAT/WHY/STATUS)
- Layer separation enforcement
- Deterministic core pipeline rules
- Data integrity (UTC timestamps, no silent data drops)
- State recoverability
- Builder workflow (read blueprint → implement → smoke test → push)
- Research Lab Phase Rules (scope boundaries, no `settings.py` promotion)
- Source-of-truth hierarchy

**Where it is insufficient for quant research / edge discovery:**
- No guidance on **source research** (GitHub, papers, open-source intelligence)
- No guidance on **mechanism extraction** from external sources
- No guidance on **timing analysis** (detection vs knowable vs entry)
- No guidance on **MFE/MAE accessibility** as edge validation criteria
- No guidance on **when to stop** vs **when to explore** a research direction
- No guidance on **reverse engineering failure points**
- No distinction between "implementation milestone" vs "quant research milestone"

**Whether it should remain the top authority:**  
✅ YES. `AGENTS.md` should remain the top-level workflow authority.

**Where a new Quant Research section should be linked:**  
Add a new "Workflow Modes" section in `AGENTS.md` that defines:
- Implementation Mode
- Research Lab Infrastructure Mode
- **Quant Research / Edge Discovery Mode** (links to `docs/QUANT_RESEARCH_OPERATING_MODEL.md`)
- Promotion Mode
- Live Operations / Incident Mode

---

### `CLAUDE.md` — Independent Auditor Role

**Current auditor strengths:**
- Layer separation auditing
- Contract compliance auditing
- Determinism auditing
- State integrity auditing
- Error handling auditing
- Smoke test coverage auditing
- Research Lab Audit Standard (methodology integrity, promotion safety, reproducibility)
- Explicit verdict scale (DONE / MVP_DONE / LOOKS_DONE / NOT_DONE)
- Handoff protocol to builders

**Where Claude may become too conservative or too implementation-audit focused:**
- Current audit checklist is code-quality focused, not edge-discovery focused
- No explicit "Quant Research Challenger" mode
- No audit axis for **source coverage** (did builder inspect external repos/papers?)
- No audit axis for **timing discipline** (detection vs entry separation)
- No audit axis for **MFE accessibility** (is remaining MFE tradable?)
- No audit axis for **edge novelty** (is this truly new, or a disguised rescue?)
- No verdict options for research outcomes:
  - `APPROVE_PLANNING_DOCUMENT`
  - `HYPOTHESIS_PASSED`
  - `HYPOTHESIS_INVALIDATED`
  - `REJECT_LOOKAHEAD`
  - `REJECT_CHERRY_PICKING`
  - `REJECT_SOURCE_COVERAGE_INSUFFICIENT`

**How to extend Claude into Quant Research Challenger:**

Add a new section to `CLAUDE.md`:

```markdown
## Quant Research Challenger Mode

When milestone is tagged as "quant research" or "edge discovery", Claude Code operates as:
- Methodology auditor (not just code auditor)
- Source coverage challenger (did builder research external intelligence?)
- Timing discipline enforcer (detection vs entry separation)
- Edge accessibility auditor (is remaining MFE tradable after costs?)
- Reverse engineering reviewer (did builder start from failure point?)
- Novelty classifier (new hypothesis vs invalidated rescue)
```

---

### `CASCADE.md` — Alternative Builder Role

**Current builder strengths:**
- Clear builder/auditor separation (no self-audit)
- Layer separation enforcement during implementation
- Smoke test execution before push
- Research Lab Phase Rules (no production code changes in research milestones)
- Mandatory builder exit protocol (smoke → push → report)
- SSH key initialization protocol for server operations

**How to extend Cascade as alternative research builder without allowing self-audit:**

Add a new section to `CASCADE.md`:

```markdown
## Quant Research Builder Mode

When assigned a quant research milestone, Cascade must:

1. **Source Research** (if new edge family):
   - Search GitHub, TradingView, papers for related mechanisms
   - Document repos/sources with URLs
   - Classify each source: useful concept / bad repainting / discretionary only / not applicable
   
2. **Mechanism Extraction**:
   - Extract testable mechanism from source (not copy code blindly)
   - Define earliest knowable signal bar
   - Assess lookahead/repainting risk
   
3. **Timing Model**:
   - Define: detection_bar, state_known_bar, entry_candidate_bar, label_available_bar
   - Measure: MFE before entry, MFE after entry, % MFE consumed before entry
   
4. **Baseline Comparison**:
   - Always compare to trial-00095 as benchmark
   - Propose invalidation criteria BEFORE results
   
5. **Minimal Research Plan** (before code):
   - What is the mechanism?
   - What data proves/disproves it?
   - What is earliest realistic entry?
   - What would make us stop?
```

**What boundaries must stay unchanged:**
- ❌ Cascade NEVER audits its own output (Claude Code exclusive)
- ❌ Cascade does NOT decide what to research next (Claude Code decides, user approves)
- ❌ Cascade does NOT self-mark research as "hypothesis validated" (Claude Code verdict only)

---

### Codex Role — No Explicit `CODEX.md`

**Current state:**
- Codex duties are defined only in `AGENTS.md` section "Rules for Builder"
- No Codex-specific operating model document

**Should one be created?**  
**OPTIONAL BUT RECOMMENDED for consistency.**

If `CASCADE.md` exists and defines Cascade-specific builder duties, then `CODEX.md` should also exist to define Codex-specific builder duties.

**What should Codex be required to do in research mode?**  
Same as Cascade (see above), with Codex-specific notes:
- Codex has access to file-system search, web browsing
- Codex should leverage these for source research (GitHub repo inspection, paper searches)
- Codex should use `grep`, `find`, or similar for repo code inspection

**Where should Codex duties be defined?**

**Option A:** Create `CODEX.md` parallel to `CASCADE.md`  
**Option B:** Keep Codex duties in `AGENTS.md` under "Rules for Builder (Codex)"  
**Recommended:** Option A (symmetry with Cascade)

---

## 3. Problem Statement

### Why This Extension Is Needed Now

The btc-bot has evolved through three distinct phases:

**Phase 1 (2023-2025): Implementation**  
- Built bot architecture (phases A-H)
- Built research lab infrastructure (v0.1 → v3 → hardening)
- Trial-00095 became validated baseline (ER 2.1, PF 4.6, walk-forward validated)
- **Operating model coverage:** ✅ ADEQUATE

**Phase 2 (Q1 2026): Research Lab Infrastructure**  
- Optimization harness, walk-forward, promotion gates
- Nested optimization, protocol lineage, autoresearch loop
- **Operating model coverage:** ✅ ADEQUATE

**Phase 3 (Q2 2026): Edge Discovery / Reverse Engineering**  
- Sweep/reclaim taxonomy diagnostic → invalidated (timing lesson learned)
- SMC sequence feasibility → invalidated (mitigation too late)
- MFE accessibility diagnostic → invalidated (no accessible state has positive expectancy)
- Reverse quant edge review → source research required
- **Operating model coverage:** ⚠️ INSUFFICIENT

### The Lesson from Recent Research History

**V1 Taxonomy Diagnostic:**
- **Finding:** Delayed labels measured from `detection_bar` create fake edge
- **Lesson:** Timing discipline required — measure from `entry_candidate_bar` or `label_available_bar`
- **Gap:** Timing rules were ad-hoc, not codified in operating model

**SMC Sequence Diagnostic:**
- **Finding:** Mitigation entry (8 bars from sweep) too late; median MFE before entry (0.011565) > MFE after entry (0.004916)
- **Lesson:** Edge accessibility is the decisive test — if MFE consumed before entry, edge is not tradable
- **Gap:** MFE accessibility analysis not required by operating model

**MFE Accessibility Diagnostic:**
- **Finding:** No post-sweep knowable state has positive expectancy; trial-00095 is already optimal
- **Lesson:** Shift question from "does a pattern exist?" to "is decisive information knowable early enough to trade?"
- **Gap:** Earliest-knowable-signal analysis not required by operating model

**Reverse Quant Edge Review (in progress):**
- **Need:** External source research, mechanism extraction, repo code inspection
- **Lesson:** Builder must research external intelligence, not just implement requests
- **Gap:** Source research not required by operating model

### The Operating Model Should Enforce This Lesson Permanently

Current operating model focuses on:
- ✅ Layer separation
- ✅ Determinism
- ✅ State integrity
- ✅ Smoke test coverage

But does not codify:
- ❌ Timing discipline (detection vs entry)
- ❌ MFE accessibility analysis
- ❌ Earliest knowable signal identification
- ❌ Source research requirements
- ❌ Reverse engineering protocol
- ❌ When to stop vs when to explore

**Goal:** Extend operating model to make timing discipline, accessibility analysis, and source research as non-negotiable as layer separation is for implementation.

---

## 4. Proposed Role Model

### Preserve Current Workflow

**Do NOT create a new agent role.** Preserve the existing workflow:

| Role | Authority | Agent |
|---|---|---|
| Strategic decision / veto | User | — |
| Independent auditor / evaluator / technical selector | Claude Code | — |
| Default builder / research implementer | Codex | — |
| Alternative builder / research implementer | Cascade | — |

### Define Workflow Modes

Instead of creating new roles, define **modes** within the existing workflow:

#### 1. Implementation Mode

**When:** Blueprint phases (A-H), bot runtime features, execution engine, orchestrator

**Builder duties:**
- Read blueprint
- Implement code
- Write tests
- Smoke test before push
- Commit with WHAT/WHY/STATUS

**Claude duties:**
- Audit layer separation
- Audit contract compliance
- Audit determinism
- Audit state integrity
- Verdict: DONE / MVP_DONE / LOOKS_DONE / NOT_DONE

**User duties:**
- Approve or veto next milestone

---

#### 2. Research Lab Infrastructure Mode

**When:** Research lab workflow improvements (optimization harness, walk-forward, store schema, autoresearch loop)

**Builder duties:**
- Implement research lab modules
- Follow research lab scope rules (no live-path changes)
- Smoke test offline workflow
- Commit with WHAT/WHY/STATUS

**Claude duties:**
- Audit layer separation
- Audit methodology integrity
- Audit promotion safety
- Audit reproducibility & lineage
- Audit data isolation
- Verdict: DONE / MVP_DONE / LOOKS_DONE / NOT_DONE

**User duties:**
- Approve or veto next milestone

---

#### 3. Quant Research / Edge Discovery Mode ⭐ NEW

**When:** Exploring new edge families, reverse engineering failure points, validating hypotheses, source research

**Builder duties (see Section 5 for detail):**
1. Source research (if new edge family)
2. Mechanism extraction
3. Timing model definition (detection/state_known/entry/label bars)
4. Earliest knowable signal analysis
5. MFE/MAE accessibility design
6. Baseline comparison design
7. Control cohort design
8. Invalidation criteria before results
9. Minimal research plan before code
10. Result summary with ONE recommendation

**Claude duties (see Section 6 for detail):**
- Audit methodology (not just code)
- Audit source coverage
- Audit timing discipline
- Audit entry realism
- Audit lookahead risk
- Audit edge novelty (new hypothesis vs rescue)
- Classify research proposal type
- Research verdicts: APPROVE_PLANNING_DOCUMENT / HYPOTHESIS_PASSED / HYPOTHESIS_INVALIDATED / REJECT_LOOKAHEAD / etc.

**User duties:**
- Approve or veto research direction
- Decide when to stop vs when to explore
- Strategic veto if research ROI is negative

---

#### 4. Promotion Mode

**When:** Promoting research lab candidate to paper/live settings

**Builder duties:**
- Generate approval bundle
- Apply parameter diffs to settings (manual)
- Backup production database before deployment
- Deploy to paper, monitor for N days

**Claude duties:**
- Audit promotion gate (blocking risks absent)
- Audit backup existence
- Audit deployment checklist
- Verdict: READY_FOR_PAPER / BLOCKED

**User duties:**
- Final approval before live deployment

---

#### 5. Live Operations / Incident Mode

**When:** Production issues, zombie processes, data corruption, disaster recovery

**Builder duties:**
- Diagnose issue
- Implement fix
- Verify fix on server
- Document incident

**Claude duties:**
- Audit fix (no data loss risk)
- Audit rollback readiness
- Verify backup availability

**User duties:**
- Incident approval (destructive operations require explicit user approval)

---

## 5. Quant Research Builder Mode (Detailed)

### When This Mode Applies

Builder receives handoff from Claude Code tagged as:
- "Quant Research Planning"
- "Edge Discovery Diagnostic"
- "Hypothesis Validation"
- "Source Research Review"
- "Reverse Engineering Analysis"

### Builder Must Not Merely Implement the Requested Idea

**Anti-pattern:**
- User: "Test order block mitigation entry"
- Builder: *writes code for order block detection and mitigation entry*
- Builder: "Done, here are results"

**Correct pattern:**
- User: "Test order block mitigation entry"
- Builder: "Before coding, I will research external sources, extract testable mechanism, define timing model, propose invalidation criteria. Then I will present a research plan for approval."

### Required Steps Before Coding

#### 1. Repo Inspection (if external source mentioned)

**Required:**
- Clone or browse external repo
- Read implementation code (not just README)
- Identify core mechanism (not just pattern names)
- Assess determinism (is indicator deterministic or discretionary?)
- Assess lookahead risk (does code reference future bars?)
- Document findings in research plan

**Example:**
```
Source: LuxAlgo/SMC-Trading
Repo: https://github.com/LuxAlgo/SMC-Trading
Implementation: indicators/fvg.pine (lines 42-88)
Mechanism: Fair Value Gap = 3-candle imbalance where candle[i-1].high < candle[i+1].low
Determinism: ✅ Deterministic (OHLC only)
Lookahead: ⚠️ Requires candle[i+1] close, so earliest detection is i+2
Applicability: FVG detection is knowable at bar+2, but does remaining MFE justify entry?
```

#### 2. Data Availability Check

**Required:**
- Confirm required data exists in market database
- If data missing, propose data collection milestone first

**Example:**
```
Mechanism: Liquidation cascade detection
Required data: force_orders (liquidations), funding_rate, open_interest
Data availability: 
  - force_orders: ✅ 146,864 rows in research DB
  - funding_rate: ✅ 6,105 rows
  - open_interest: ✅ 524,971 rows
Data coverage: 2020-09-01 to 2026-03-28 (5.6 years)
Conclusion: Data sufficient for diagnostic
```

#### 3. External Source / GitHub / Paper Search (if required)

**When required:**
- New edge family (not extension of existing sweep/reclaim work)
- Mechanism from external source (e.g., "SMC order blocks")
- User explicitly requests source research

**Required deliverables:**
- List of repos/papers with URLs
- Classification of each source:
  - ✅ Useful concept
  - ✅ Benchmark candidate
  - ⚠️ Implementation candidate (needs validation)
  - ❌ Bad/repainting
  - ❌ Discretionary only
  - ❌ Not applicable

**Example:**
```
Source Research: Order Block (OB) mechanisms

1. LuxAlgo/SMC-Trading
   URL: https://github.com/LuxAlgo/SMC-Trading
   Classification: ⚠️ Implementation candidate (needs timing validation)
   Notes: Defines OB as last opposite-direction candle before displacement
   
2. joshyattridge/smart-money-concepts
   URL: https://github.com/joshyattridge/smart-money-concepts
   Classification: ❌ Discretionary only (visual patterns, no quantified entry)
   
3. "Smart Money Concepts" (Makuchaku YouTube)
   Classification: ❌ Not applicable (no code, visual teaching only)
```

#### 4. Source Coverage Matrix

**Required:**
- Map external sources to mechanisms
- Identify which mechanisms are testable
- Identify which mechanisms are NOT testable (discretionary, lookahead, visual-only)

**Template:**
```
| Source | Mechanism | Testable? | Lookahead risk? | Data available? |
|---|---|---|---|---|
| LuxAlgo | FVG (imbalance) | ✅ Yes | ⚠️ Requires i+2 | ✅ Yes (OHLC) |
| joshyattridge | Order Block | ✅ Yes | ⚠️ Displacement requires i+1 | ✅ Yes (OHLC) |
| Makuchaku | CHOCH | ❌ No (visual, no quantified rule) | N/A | N/A |
```

#### 5. Mechanism Extraction

**Required:**
- Extract ONE testable mechanism (not a list of patterns)
- Define mechanism in code-ready terms
- Identify dependencies (what must happen before mechanism is valid?)

**Anti-pattern:**
```
Mechanism: Order blocks work in SMC
```

**Correct pattern:**
```
Mechanism: Order Block Mitigation Entry
- Definition: Last opposite-direction candle before displacement (body > 2x ATR)
- Detection bar: Displacement confirmed at bar i (body > 2x ATR, closes beyond prior high/low)
- Order block bar: Last opposite-direction candle before displacement = bar i-k (k = bars since last opposite candle)
- State known bar: i (displacement confirmed)
- Entry candidate bar: When price returns to OB range and shows rejection (e.g., wick into OB + close beyond OB in continuation direction)
- Earliest entry: Bar at which rejection candle closes (OB mitigation bar + 1)
```

#### 6. Timing Model Definition

**MANDATORY for every quant research milestone.**

**Required bars:**
- `detection_bar`: First bar where pattern is detected (may be lookahead if detection requires future bars)
- `state_known_bar`: First bar where ALL required facts are knowable (no future bars required)
- `confirmation_bar` (if applicable): Bar where confirmation occurs (e.g., displacement, reclaim)
- `entry_candidate_bar`: Earliest realistic entry bar (state_known_bar + 1, or confirmation_bar + 1)
- `label_available_bar` (if delayed): Bar where delayed outcome is known (e.g., reclaim after 5 bars)
- `return_start_bar`: Bar from which returns are measured (usually entry_candidate_bar)

**Anti-pattern:**
```
Entry timing: After order block is detected
```

**Correct pattern:**
```
Timing model:
- detection_bar: i (displacement confirmed, closes beyond prior high/low with body > 2x ATR)
- state_known_bar: i (same as detection; displacement is knowable at bar close)
- order_block_identified: i-k (last opposite-direction candle before displacement)
- mitigation_detection_bar: j (price returns to OB range)
- mitigation_confirmation_bar: j+m (rejection candle closes beyond OB in continuation direction)
- entry_candidate_bar: j+m+1 (next bar after rejection confirmation)
- return_start_bar: j+m+1 (measure from entry, not detection)

Example: Displacement at bar 100, OB at bar 95, mitigation at bar 108, entry at bar 109.
```

#### 7. Earliest Knowable Signal Analysis

**Required:**
- Bar-by-bar knowability analysis
- What is known at detection_bar?
- What is known at state_known_bar?
- What is known at entry_candidate_bar?
- What is NOT known until later?

**Example:**
```
Knowability timeline:
- At detection_bar (i=100): Displacement confirmed (body > 2x ATR, close beyond high). Order block bar identified (i=95).
- At state_known_bar (i=100): Same as detection. No additional confirmation required.
- At entry_candidate_bar (j+m+1=109): Mitigation confirmed (price returned to OB, rejection candle closed).

What is NOT known at detection_bar:
- Whether price will return to OB (mitigation may not occur)
- When mitigation will occur (could be 5 bars or 50 bars later)
- Whether rejection will be strong enough to justify entry

Earliest realistic entry: Bar 109 (mitigation + rejection confirmation + 1)
```

#### 8. MFE/MAE Accessibility Design

**Required:**
- Define how MFE/MAE will be measured
- Measure MFE before entry (from detection_bar to entry_candidate_bar)
- Measure MFE after entry (from entry_candidate_bar to future)
- Calculate % MFE consumed before entry

**Template:**
```
MFE/MAE measurement:
- MFE before entry: max(high - detection_bar.close) from detection_bar to entry_candidate_bar-1
- MFE after entry: max(high - entry_candidate_bar.close) from entry_candidate_bar to entry_candidate_bar+20
- % MFE consumed before entry: (MFE_before / (MFE_before + MFE_after)) * 100

Invalidation: If MFE consumed before entry > 70%, edge is not accessible.
```

#### 9. Baseline Comparison Design

**Required:**
- Always compare to trial-00095 as benchmark
- Define what "better" means:
  - Higher expectancy (ER > 2.1)?
  - Higher profit factor (PF > 4.6)?
  - Different risk profile (lower DD, different frequency)?
- Propose criteria for legitimate challenge to trial-00095

**Example:**
```
Baseline comparison:
- Trial-00095: ER 2.1, PF 4.6, 271 trades, entry at sweep+reclaim+1 (1-2 bars from sweep)
- OB mitigation entry: entry at mitigation confirmation (8-15 bars from displacement)
- Hypothesis: OB mitigation captures later confirmation, trades less frequently but with higher quality

Success criteria:
- ER > 2.5 (25% better than trial-00095)
- PF > 5.0 (higher quality)
- Walk-forward validated (4/4 folds pass protocol thresholds)
- Positive expectancy after 0.10% round-trip costs

If OB mitigation does NOT meet these criteria, trial-00095 remains benchmark.
```

#### 10. Control Cohort Design

**Required:**
- Define deterministic control cohort (shifted entry, random entry, etc.)
- Purpose: Verify that observed edge is not data-mining artifact

**Example:**
```
Control cohort:
- Method: Shift all entry bars by +137 bars (deterministic offset, prime number to avoid cycle alignment)
- Purpose: If control cohort also shows positive returns, edge is likely data-mining artifact
- Invalidation: If control cohort beats candidate, candidate is INVALID
```

#### 11. Invalidation Criteria Before Results

**MANDATORY.**

**Required:**
- Define STOP criteria before running diagnostic
- What results would invalidate the hypothesis?
- What results would require further exploration?

**Example:**
```
Invalidation criteria (defined BEFORE results):

STOP (hypothesis invalidated):
1. Median net return after costs ≤ 0
2. Win rate < 51% (approximately random)
3. Profit factor < 1.2 (too weak after costs)
4. MFE consumed before entry > 70%
5. Control cohort beats candidate
6. Walk-forward: fewer than 2 of 4 folds positive

EXPLORE (hypothesis shows promise):
1. Median net return after costs > 0
2. Win rate > 55%
3. Profit factor > 1.5
4. MFE consumed before entry < 50%
5. Candidate beats control cohort
6. Walk-forward: at least 3 of 4 folds positive

INCONCLUSIVE (data gap):
1. Sample size < 100 events
2. Data coverage < 2 years
```

#### 12. Minimal Research Plan Before Code

**MANDATORY first response before any code is written.**

Builder's first response must contain:

```markdown
# Research Plan: [Hypothesis Name]

## 1. Hypothesis
[One-sentence hypothesis]

## 2. Mechanism
[Detailed mechanism description]

## 3. Source Research
[External sources, classification]

## 4. Timing Model
[detection_bar, state_known_bar, entry_candidate_bar]

## 5. Data Requirements
[Required tables, data coverage check]

## 6. MFE Accessibility Design
[How MFE before/after entry will be measured]

## 7. Baseline Comparison
[How candidate will be compared to trial-00095]

## 8. Control Cohort
[Deterministic control method]

## 9. Invalidation Criteria
[STOP criteria defined before results]

## 10. Scope
[No production code changes, research-only]

## 11. Estimated Timeline
[1 week / 2 weeks / 1 month]

## 12. Approval Request
[Request user approval before coding]
```

User approves or vetoes this plan. If approved, builder proceeds to implementation.

#### 13. Result Summary with ONE Recommendation

**After diagnostic runs, builder delivers:**

```markdown
# Results: [Hypothesis Name]

## 1. Dataset
[Candles, events, date range]

## 2. Best Result
[Median return, PF, win rate, MFE consumed]

## 3. Invalidation Checks
[Which STOP criteria were triggered?]

## 4. Control Cohort
[Control result vs candidate result]

## 5. Walk-Forward
[Fold-by-fold results]

## 6. Verdict
[HYPOTHESIS_PASSED / HYPOTHESIS_INVALIDATED / INCONCLUSIVE]

## 7. ONE Recommendation
[STOP research / PLAN next diagnostic / PROMOTE to feature engineering]
```

**Builder must answer:**
- What exactly is the mechanism?
- What data proves or disproves it?
- What is known at detection?
- What is known at state_known_bar?
- What is the earliest realistic entry?
- What is the benchmark?
- What would make us stop?
- Is this new, or a disguised rescue of an invalidated idea?

---

## 6. Quant Research Auditor Mode for Claude

### When This Mode Applies

Claude Code receives audit request for:
- Quant research planning document
- Edge discovery diagnostic implementation
- Hypothesis validation code
- Source research review
- Reverse engineering analysis

### Audit Beyond Normal Code Quality

**Standard implementation audit (still required):**
- ✅ Layer separation
- ✅ Contract compliance
- ✅ Determinism
- ✅ State integrity
- ✅ Error handling
- ✅ Smoke test coverage

**Additional quant research audit (new):**
- ✅ Methodology rigor
- ✅ Source coverage
- ✅ Repo/code inspection (if external source)
- ✅ Timing discipline
- ✅ Entry realism
- ✅ Lookahead risk
- ✅ Data source validity
- ✅ Control cohorts
- ✅ Invalidation gates
- ✅ Source-to-mechanism translation
- ✅ Novelty vs rescue classification
- ✅ Exploration vs premature suppression balance
- ✅ Creativity vs cherry-picking balance

### Claude Must Not Be Only a Brake

**Anti-pattern:**
- Builder: "Here's a new edge hypothesis"
- Claude: "Two hypotheses already failed, STOP all research"

**Correct pattern:**
- Builder: "Here's a new edge hypothesis"
- Claude: "Is this truly new, or a disguised rescue? Let me classify it."
- Claude: "This is a new edge family (order flow, not sweep/reclaim). Methodology is sound. APPROVE planning document."

**Correct pattern (valid rejection):**
- Builder: "Let's measure delayed reclaim from detection_bar with looser timing"
- Claude: "This is a rescue of invalidated hypothesis. Timing lesson from V1 applies. REJECT."

### Proposal Classification System

Claude should classify every research proposal as:

| Classification | Meaning | Action |
|---|---|---|
| **Valid New Hypothesis** | Genuinely new edge family, testable, timing-safe, source-grounded | APPROVE planning |
| **Invalidated Hypothesis Rescue** | Prior failed hypothesis with relaxed criteria or different measurement | REJECT |
| **Source Research Only** | External intelligence gathering, no diagnostic yet | APPROVE research |
| **Meta-Diagnostic** | Methodology study (e.g., MFE accessibility), not edge proposal | APPROVE diagnostic |
| **Strategy Feasibility** | Timing/entry realism study, not performance optimization | APPROVE diagnostic |
| **Premature Implementation** | No research plan, jumps to code | REJECT, require plan first |
| **Production Promotion Candidate** | Research validated, ready for feature engineering | APPROVE promotion |

### Research Verdict Scale

**For planning documents:**
- `APPROVE_PLANNING_DOCUMENT`: Methodology sound, proceed to implementation
- `APPROVE_WITH_REQUIRED_CHANGES`: Useful but incomplete, specific changes listed
- `REJECT_INSUFFICIENT_SOURCE_RESEARCH`: Builder did not inspect external repos/papers
- `REJECT_LOOKAHEAD`: Timing model violates lookahead discipline
- `REJECT_NOT_NEW_HYPOTHESIS`: Disguised rescue of invalidated hypothesis
- `REJECT_TOO_BROAD`: Scope too large, must be decomposed

**For diagnostic implementations:**
- `DONE_IMPLEMENTATION_CORRECT`: Code correct, ready for results analysis
- `MVP_DONE_IMPLEMENTATION_CORRECT`: Code correct, smoke tests pass, minor gaps
- `REJECT_TIMING_VIOLATION`: detection_bar used as return_start_bar (lookahead)
- `REJECT_NO_CONTROL_COHORT`: Control cohort missing or broken
- `REJECT_CHERRY_PICKING`: Selective filtering after results

**For research results:**
- `HYPOTHESIS_PASSED`: Invalidation criteria NOT triggered, edge shows promise
- `HYPOTHESIS_INVALIDATED`: Invalidation criteria triggered, STOP this direction
- `INCONCLUSIVE_DATA_GAP`: Sample size too small or data coverage insufficient
- `REJECT_RESULTS_METHOD_INVALID`: Control cohort violated, method is broken

### Audit Axes for Quant Research

| Axis | What Claude Code Must Verify |
|---|---|
| **Methodology Rigor** | Timing discipline enforced, MFE accessibility measured, control cohort exists |
| **Source Coverage** | Builder inspected external repos/papers if new edge family; sources classified |
| **Repo/Code Inspection** | Builder read implementation code (not just README), assessed lookahead risk |
| **Timing Discipline** | 4-bar separation (detection/state_known/entry/return_start), no detection-bar primary metrics |
| **Entry Realism** | Entry is at state_known_bar+1 or later, not at detection_bar |
| **Lookahead Risk** | No future bars referenced in signal detection; confirmation bars explicitly modeled |
| **Data Source Validity** | Required tables exist, data coverage sufficient, no missing critical data |
| **Control Cohorts** | Deterministic control cohort implemented (shifted entry or random entry) |
| **Invalidation Gates** | STOP criteria defined before results; hard gates correctly implemented |
| **Source-to-Mechanism Translation** | External source translated to testable mechanism (not copied blindly) |
| **Novelty vs Rescue** | Is this a new hypothesis, or a rescue of failed hypothesis with relaxed criteria? |
| **Exploration Suppression** | Is Claude blocking valid exploration because prior hypotheses failed? |
| **Creativity vs Cherry-Picking** | Is builder generating creative hypotheses, or selectively filtering after results? |

### Audit Report Template for Research

```markdown
# AUDIT: [Research Milestone Name]

Date: YYYY-MM-DD
Auditor: Claude Code
Commit: <hash>
Milestone Type: QUANT_RESEARCH

## Verdict: [Research Verdict]

## Standard Audit Axes
- Layer Separation: PASS / WARN / FAIL
- Contract Compliance: PASS / WARN / FAIL
- Determinism: PASS / WARN / FAIL
- State Integrity: PASS / WARN / FAIL
- Error Handling: PASS / WARN / FAIL
- Smoke Coverage: PASS / WARN / FAIL
- Tech Debt: LOW / MEDIUM / HIGH

## Quant Research Audit Axes
- Methodology Rigor: PASS / WARN / FAIL
- Source Coverage: PASS / WARN / FAIL / N/A
- Repo/Code Inspection: PASS / WARN / FAIL / N/A
- Timing Discipline: PASS / WARN / FAIL
- Entry Realism: PASS / WARN / FAIL
- Lookahead Risk: PASS / WARN / FAIL
- Data Source Validity: PASS / WARN / FAIL
- Control Cohorts: PASS / WARN / FAIL
- Invalidation Gates: PASS / WARN / FAIL
- Source-to-Mechanism Translation: PASS / WARN / FAIL / N/A
- Novelty vs Rescue: NEW_HYPOTHESIS / RESCUE / UNCLEAR
- Exploration Suppression Check: VALID_EXPLORATION / PREMATURE_BLOCK
- Creativity vs Cherry-Picking: CREATIVE / CHERRY_PICKED / ACCEPTABLE

## Research Result (if applicable)
- Hypothesis: [hypothesis statement]
- Invalidation criteria triggered: [list]
- Result: HYPOTHESIS_PASSED / HYPOTHESIS_INVALIDATED / INCONCLUSIVE

## Critical Issues
[Must fix before next milestone]

## Warnings
[Fix soon]

## Observations
[Non-blocking]

## Recommended Next Step
[ONE recommendation]
```

---

## 7. Quant Research Timing Rules (Codified)

### Permanent Timing Lessons

For every sequential or delayed setup, the following bars MUST be explicitly defined:

| Bar | Definition | Knowability |
|---|---|---|
| `detection_bar` | First bar where pattern is detected | May involve lookahead if detection requires future bars |
| `state_known_bar` | First bar where ALL required facts are knowable (no future bars) | Earliest lookahead-free bar |
| `confirmation_bar` | Bar where confirmation occurs (e.g., displacement, reclaim) | May be same as state_known_bar or later |
| `entry_candidate_bar` | Earliest realistic entry bar | Usually state_known_bar + 1 or confirmation_bar + 1 |
| `label_available_bar` | Bar where delayed outcome is known (if delayed label) | Only for delayed-sequence setups |
| `return_start_bar` | Bar from which returns are measured | Usually entry_candidate_bar |

### Primary Return Measurement Rule

**Primary returns MUST be measured from the earliest realistic entry bar.**

- ✅ **Correct:** `return_start_bar = entry_candidate_bar`
- ❌ **Wrong:** `return_start_bar = detection_bar` (unless signal was fully knowable at detection)

**Detection-bar returns are audit-only.**

Detection-bar returns may be computed for comparison purposes (to measure MFE before entry), but they are NOT primary metrics for hypothesis validation.

### Required Reporting Metrics

For every diagnostic, builder must report:

| Metric | Purpose |
|---|---|
| **MFE before entry** | Max favorable excursion from detection_bar to entry_candidate_bar-1 |
| **MFE after entry** | Max favorable excursion from entry_candidate_bar onward |
| **MAE after entry** | Max adverse excursion from entry_candidate_bar onward |
| **% MFE consumed before entry** | (MFE_before / (MFE_before + MFE_after)) * 100 |
| **Time from detection to entry** | Bars between detection_bar and entry_candidate_bar |
| **Time from entry to MFE** | Bars between entry_candidate_bar and peak MFE |
| **Cost-adjusted returns** | Median return after round-trip costs (e.g., 0.10%) |

### Invalidation Rule: Edge Exists Only Before Entry

**If MFE consumed before entry > 70%, the edge is NOT tradable.**

Even if detection-bar returns are positive, if remaining MFE after realistic entry is insufficient, the hypothesis is INVALIDATED.

**Example (SMC mitigation):**
- Detection-bar return: +0.004348 (positive)
- MFE before entry: 0.011565 (69.8% of total MFE)
- MFE after entry: 0.004916 (30.2% of total MFE)
- Median return from entry: +0.000558 (positive but weak)
- Net return after costs: -0.000442 (NEGATIVE)
- **Verdict:** INVALIDATED (edge consumed before entry)

---

## 8. Source Research Requirements

### When External Research Is Mandatory

External source research (GitHub, papers, TradingView, open-source repos) is **MANDATORY** when:

1. **New edge family** (not an extension of existing sweep/reclaim work)
2. **Mechanism from external source** (e.g., "SMC order blocks", "liquidation cascades")
3. **User explicitly requests source research**

External research is **OPTIONAL** when:
- Extending existing validated work (e.g., trial-00095 parameter tuning)
- Internal diagnostic (e.g., MFE accessibility meta-study)
- Infrastructure work (e.g., research lab optimization harness)

### Required Deliverables

For each new edge family, builder must include:

#### 1. Source List

**Format:**
```
| Source | Type | URL |
|---|---|---|
| LuxAlgo/SMC-Trading | GitHub repo | https://github.com/LuxAlgo/SMC-Trading |
| Makuchaku SMC Course | YouTube series | https://youtube.com/... |
| "Smart Money Concepts" paper | Academic | https://arxiv.org/... |
```

#### 2. Source Classification

For each source, classify as:

| Classification | Meaning | Action |
|---|---|---|
| ✅ **Useful concept** | Provides testable mechanism or insight | Extract mechanism, design diagnostic |
| ✅ **Benchmark candidate** | External backtest results for comparison | Compare to our results |
| ⚠️ **Implementation candidate** | Code exists, but needs validation | Inspect code, assess lookahead, design diagnostic |
| ❌ **Bad/repainting** | Code contains lookahead or repainting | Reject source, document why |
| ❌ **Discretionary only** | Visual patterns, no quantified entry | Reject source, not testable |
| ❌ **Not applicable** | Mechanism incompatible with our architecture | Reject source, document why |

#### 3. Mechanism Extracted

For each useful source, extract testable mechanism:

**Anti-pattern:**
```
Source: LuxAlgo SMC
Mechanism: Order blocks work
```

**Correct pattern:**
```
Source: LuxAlgo SMC (github.com/LuxAlgo/SMC-Trading)
File: indicators/orderblock.pine (lines 58-102)
Mechanism extracted:
- Order block = last opposite-direction candle before displacement
- Displacement = body > 2x ATR, closes beyond prior high/low
- Mitigation = price returns to OB range, rejection candle closes beyond OB
- Entry = mitigation bar + 1
Lookahead assessment:
- Displacement confirmation requires current bar close (no lookahead)
- Mitigation rejection requires current bar close (no lookahead)
- Earliest entry: mitigation bar + 1 (lookahead-free)
Determinism assessment:
- ✅ Fully deterministic (OHLC + ATR only, no discretion)
Applicability:
- ⚠️ Needs validation — does remaining MFE after mitigation justify entry?
```

#### 4. Data Required

For each mechanism, list required data:

**Example:**
```
Mechanism: Liquidation cascade detection
Data required:
- force_orders (liquidations) — table: force_orders
- funding_rate — table: funding_rate
- open_interest — table: open_interest
- OHLC candles — table: candles
Data availability:
- force_orders: ✅ 146,864 rows
- funding_rate: ✅ 6,105 rows
- open_interest: ✅ 524,971 rows
Data coverage: 2020-09-01 to 2026-03-28 (5.6 years)
Conclusion: Data sufficient
```

#### 5. Determinism Assessment

For each source, assess determinism:

| Assessment | Meaning |
|---|---|
| ✅ **Fully deterministic** | Uses only OHLC, volume, or derived indicators; no discretion |
| ⚠️ **Partially deterministic** | Core logic deterministic, but includes optional discretionary filters |
| ❌ **Discretionary** | Requires visual interpretation or subjective judgment |

**Reject discretionary sources** — not testable in automated backtest.

#### 6. Lookahead/Repainting Risk Assessment

For each source, assess lookahead risk:

| Risk | Meaning | Action |
|---|---|---|
| ✅ **No lookahead** | Uses only current and past bars, no future references | Safe to implement |
| ⚠️ **Confirmation lookahead** | Detection requires future bar to confirm (e.g., displacement at bar i requires bar i+1 close) | Explicitly model confirmation bar |
| ❌ **Structural lookahead** | Uses future bars in signal logic (e.g., "highest high in next 10 bars") | Reject source, document why |

**Reject sources with structural lookahead** — creates fake edge.

#### 7. Applicability to BTC Bot

For each source, assess applicability:

| Applicability | Meaning |
|---|---|---|
| ✅ **Directly applicable** | Mechanism fits bot architecture, data available, timing realistic |
| ⚠️ **Needs adaptation** | Core mechanism sound, but requires modification for bot (e.g., timeframe change) |
| ❌ **Not applicable** | Mechanism incompatible with bot architecture or data constraints |

### Builder Must Use Sources as Maps, Not Truth

**Anti-pattern:**
- Builder: "LuxAlgo says order blocks work, so I'll implement exactly as shown"

**Correct pattern:**
- Builder: "LuxAlgo defines order block as last opposite-direction candle before displacement. I will extract this mechanism, design timing model, measure MFE accessibility, and validate with control cohort."

**TradingView/Pine/GitHub code must NOT be copied blindly.**

Sources provide:
- ✅ Mechanism concepts
- ✅ Pattern definitions
- ✅ External benchmark results

Sources do NOT provide:
- ❌ Validated edge (must be tested independently)
- ❌ Timing discipline (builder must design timing model)
- ❌ Entry realism (builder must measure MFE accessibility)

---

## 9. Reverse Engineering Requirements

### Starting from Failure Points

**For failed hypotheses, the next research step must begin from the failure point.**

**Anti-pattern (rescue attempt):**
- V1 delayed reclaim failed → "Let's try delayed reclaim with looser threshold"

**Correct pattern (reverse engineering):**
- V1 delayed reclaim failed → "Delayed reclaim edge collapsed from detection-bar to label-available timing. Where does edge become inaccessible? What was knowable BEFORE the delay?"

### Examples of Reverse Engineering

#### Example 1: SMC Mitigation Entry Failed

**Failure:**
- Mitigation entry (8 bars from sweep) too late
- Median MFE before entry (0.011565) > MFE after entry (0.004916)
- Net return after costs: -0.000442 (negative)

**Reverse engineering question:**
"Where does MFE become inaccessible?"

**Answer:**
- MFE peaks at displacement (5 bars from sweep)
- By mitigation (8 bars), 69.8% of MFE consumed
- Hypothesis: **Displacement entry (bar 5+1) may still have accessible MFE**

**Next research step:**
"PLAN displacement entry diagnostic" (NOT "rescue mitigation entry with different parameters")

#### Example 2: Delayed Reclaim Failed

**Failure:**
- Delayed reclaim (5+ bars after sweep) showed positive detection-bar returns
- But label-available timing returns were negative
- Edge existed only before realistic entry

**Reverse engineering question:**
"What was knowable BEFORE delayed reclaim confirmation?"

**Answer:**
- At detection bar: sweep occurred, but reclaim timing unknown
- At reclaim bar+1: immediate reclaim confirmed (1-2 bars), entry possible
- Hypothesis: **Immediate reclaim is the accessible edge, not delayed reclaim**

**Next research step:**
Trial-00095 already captures immediate reclaim (sweep+reclaim at 1-2 bars). No further work needed.

#### Example 3: Post-Sweep States All Failed

**Failure:**
- MFE accessibility diagnostic tested 28 post-sweep states
- Not a single state had positive expectancy after costs
- Best state: -0.000095 net (still negative)

**Reverse engineering question:**
"If post-sweep states all fail, where does opportunity become knowable?"

**Answer:**
- Post-sweep confirmation (displacement, reclaim, flow) arrives too late
- By the time ANY confirmation is knowable, MFE is consumed
- Hypothesis: **Flow data may become knowable BEFORE price-action confirmation**

**Next research step:**
"PLAN order flow classification diagnostic" — test whether high-volume sweep + directional CVD is knowable earlier than displacement/reclaim

**Alternative:**
"STOP SMC research, trial-00095 already optimal" (if no pre-confirmation signal exists)

### Required Reverse Engineering Question

**For every failed hypothesis, builder must answer:**

> "Where does the opportunity become knowable, and is there still enough tradable move left after costs?"

**If answer is "opportunity becomes knowable too late", then:**
- ❌ Do NOT rescue with different parameters
- ✅ Move EARLIER in the sequence (what was knowable before confirmation?)
- ✅ Or STOP the research family (no earlier signal exists)

---

## 10. Benchmark Rule (Trial-00095)

### Trial-00095 Is:

- ✅ **Active validated baseline** — ER 2.1, PF 4.6, 271 historical trades, walk-forward validated
- ✅ **Benchmark** — new candidates compared against trial-00095 performance
- ✅ **Rollback point** — if new candidate fails, trial-00095 remains active
- ✅ **Comparison standard** — new edge must beat trial-00095 to justify deployment effort

### Trial-00095 Is NOT:

- ❌ **Religion** — can be challenged with validated evidence
- ❌ **Design prison** — new edge families can use different architectures
- ❌ **Proof no other edge exists** — trial-00095 is one edge, not the only edge

### Challenging Trial-00095

New research may challenge trial-00095 **ONLY with**:

| Requirement | Threshold |
|---|---|
| **Cost-adjusted expectancy** | ER > 2.1 (match or beat trial-00095) |
| **Profit factor** | PF > 4.0 (match or beat trial-00095) |
| **Sample size** | ≥ 100 events (minimum for statistical confidence) |
| **Walk-forward validation** | At least 3 of 4 folds pass protocol thresholds |
| **Timing realism** | Entry at state_known_bar+1 or later (no lookahead) |
| **Reproducible methodology** | Protocol, seed, date range documented |

**If new candidate meets ALL requirements above**, it is a **legitimate challenge** to trial-00095.

**User decides** whether to:
- Replace trial-00095 with new candidate
- Run both in parallel (if risk profile is orthogonal)
- Keep trial-00095, archive new candidate for future consideration

### Comparison Modes

#### Mode 1: Better Performance

**New candidate is strictly better:**
- ER > 2.5 (25% better)
- PF > 5.0 (higher quality)
- Same or lower DD
- Same or higher frequency

**Action:** Strong case for replacement

#### Mode 2: Different Risk Profile

**New candidate is not strictly better, but different:**
- ER 1.8 (slightly lower)
- PF 6.0 (higher quality, lower frequency)
- DD 15% (lower)
- Frequency 50% lower (fewer trades, higher win rate)

**Action:** User decides based on strategy goals (aggressive vs conservative)

#### Mode 3: Comparable Performance

**New candidate matches trial-00095:**
- ER 2.0-2.2 (similar)
- PF 4.5-4.8 (similar)
- Same DD, frequency

**Action:** Keep trial-00095 (no deployment justification for equal performance)

#### Mode 4: Worse Performance

**New candidate underperforms:**
- ER < 2.0
- PF < 4.0
- Higher DD or lower frequency without offsetting quality

**Action:** STOP, trial-00095 remains benchmark

---

## 11. STOP / Exploration Balance

### The Dual Risk

**Bad extreme 1: Over-conservative**
- Claude blocks everything because two hypotheses failed
- Builder cannot propose new ideas without Claude rejecting
- Research stops prematurely

**Bad extreme 2: Endless exploration**
- Builder keeps inventing new filters after invalidation
- Every failed hypothesis becomes "let's try parameter X"
- Research never stops, no validated edge emerges

### Rules for When to STOP

**STOP a research family when:**

1. **Invalidation criteria met**
   - Hypothesis tested, STOP gates triggered
   - Example: Delayed reclaim negative from label-available timing → STOP delayed reclaim

2. **Accessible state space exhausted**
   - All knowable states tested, none have positive expectancy
   - Example: MFE accessibility tested 28 states, all negative → STOP SMC research

3. **Rescue attempts detected**
   - Builder proposes relaxed criteria or different measurement of same hypothesis
   - Example: "Let's measure delayed reclaim from detection bar with 0.05% cost" → STOP, this is rescue

4. **Research ROI negative**
   - Multiple diagnostics completed, no positive findings
   - Diminishing returns on research effort
   - Example: 3 SMC diagnostics, all invalidated → STOP SMC family

5. **Benchmark already optimal**
   - Trial-00095 captures earliest accessible state
   - No earlier knowable signal exists
   - Example: MFE accessibility shows trial-00095 timing optimal → STOP, validate trial-00095

### Rules for When to OPEN a New Family

**OPEN a new research family when:**

1. **Genuinely new mechanism**
   - Not a parameter tweak or filter addition
   - Different data source or detection logic
   - Example: Order flow classification (uses CVD/volume burst, not price-action sweep/reclaim)

2. **External source evidence**
   - GitHub repo shows validated backtest results
   - Paper demonstrates mechanism with data
   - Example: Liquidation cascade research shows PF 3.2 in external study

3. **Reverse engineering indicates earlier signal**
   - Failed hypothesis reveals earlier knowable state
   - Builder proposes diagnostic for earlier state
   - Example: Mitigation failed at bar 8, displacement may work at bar 5

4. **Orthogonal to failed family**
   - Uses different data, different timing, different logic
   - Not a subset or superset of failed family
   - Example: Mean-reversion (volatility contraction) is orthogonal to sweep/reclaim (momentum breakout)

### Rules for When to Run Meta-Diagnostic

**Run a meta-diagnostic when:**

1. **Methodology question**
   - Need to understand WHY a family failed
   - Example: MFE accessibility diagnostic (WHERE does edge become inaccessible?)

2. **Timing discipline study**
   - Need to quantify earliest knowable signal across a family
   - Example: V1 taxonomy diagnostic (detection vs label-available timing comparison)

3. **Source coverage review**
   - Need to map external sources to testable mechanisms
   - Example: Reverse quant edge review (inspect repos, extract mechanisms)

4. **Edge exhaustion check**
   - Need to confirm accessible state space is exhausted before STOP
   - Example: Test ALL post-sweep states to confirm none work

### Rules for When to Promote to Implementation

**Promote to feature engineering ONLY when:**

1. **Hypothesis validated**
   - Invalidation criteria NOT triggered
   - Walk-forward validated
   - ER > 2.0, PF > 4.0 (or meets benchmark threshold)

2. **Timing realistic**
   - Entry at state_known_bar+1 or later
   - MFE accessible after entry (< 70% consumed before entry)

3. **Control cohort passed**
   - Candidate beats deterministic control
   - Not a data-mining artifact

4. **User approval**
   - User approves promotion milestone
   - User accepts deployment effort vs expected ROI

### Rules for When to Refuse Implementation

**Refuse implementation when:**

1. **Hypothesis invalidated**
   - STOP gates triggered
   - Net expectancy negative after costs

2. **Lookahead detected**
   - Detection requires future bars
   - Confirmation not explicitly modeled

3. **Rescue attempt**
   - Relaxed criteria after invalidation
   - Different measurement of same failed hypothesis

4. **Premature optimization**
   - No research plan approved
   - Builder jumps to parameter tuning before diagnostic

---

## 12. Proposed File Changes

### File 1: `docs/QUANT_RESEARCH_OPERATING_MODEL.md` (NEW)

**Purpose:** Canonical quant research authority

**Structure:**
```markdown
# Quant Research Operating Model

## 1. Role in Project Workflow
## 2. Quant Research Builder Mode (detailed)
## 3. Quant Research Auditor Mode (detailed)
## 4. Timing Discipline (codified rules)
## 5. Source Research Requirements
## 6. Reverse Engineering Protocol
## 7. Benchmark Rules (trial-00095)
## 8. STOP / Exploration Balance
## 9. Research Verdict Scale
## 10. Templates (optional links)
```

**Content:** Comprehensive expansion of Sections 5-11 from this proposal

---

### File 2: `AGENTS.md` (UPDATE)

**Add new section after "Workflow: Generator-Evaluator Model":**

```markdown
## Workflow Modes

This project operates in five distinct modes:

### 1. Implementation Mode
- **When:** Blueprint phases, bot runtime features, execution engine
- **Builder:** Implements code, writes tests, smoke tests
- **Claude:** Audits layer separation, determinism, state integrity
- **Output:** Production code, committed to repo

### 2. Research Lab Infrastructure Mode
- **When:** Research lab workflow improvements (optimization harness, walk-forward, store schema)
- **Builder:** Implements research lab modules, no live-path changes
- **Claude:** Audits methodology integrity, promotion safety, reproducibility
- **Output:** Research lab infrastructure, committed to repo

### 3. Quant Research / Edge Discovery Mode ⭐
- **When:** Exploring new edge families, reverse engineering failure points, validating hypotheses
- **Builder:** Source research, mechanism extraction, timing analysis, diagnostic implementation
- **Claude:** Audits methodology rigor, source coverage, timing discipline, edge accessibility
- **Output:** Research reports, diagnostic code, invalidation verdicts
- **Authority:** `docs/QUANT_RESEARCH_OPERATING_MODEL.md`

### 4. Promotion Mode
- **When:** Promoting research lab candidate to paper/live settings
- **Builder:** Generates approval bundle, applies diffs, deploys to paper
- **Claude:** Audits promotion gate, backup existence, deployment checklist
- **Output:** Deployed candidate in paper environment

### 5. Live Operations / Incident Mode
- **When:** Production issues, zombie processes, disaster recovery
- **Builder:** Diagnoses issue, implements fix, verifies on server
- **Claude:** Audits fix (no data loss), rollback readiness
- **Output:** Incident resolved, documented in logs
```

**Add link to quant research doc in "Source of Truth Files" section:**

```markdown
- `docs/QUANT_RESEARCH_OPERATING_MODEL.md` — quant research / edge discovery workflow
```

---

### File 3: `CLAUDE.md` (UPDATE)

**Add new section after "Audit Standard":**

```markdown
## Quant Research Challenger Mode

When milestone is tagged as **quant research** or **edge discovery**, Claude Code extends standard audit with:

### Additional Audit Axes

| Axis | What Claude Code Must Verify |
|---|---|
| **Methodology Rigor** | Timing discipline enforced, MFE accessibility measured, control cohort exists |
| **Source Coverage** | Builder inspected external repos/papers if new edge family; sources classified |
| **Repo/Code Inspection** | Builder read implementation code (not just README), assessed lookahead risk |
| **Timing Discipline** | 4-bar separation (detection/state_known/entry/return_start), no detection-bar primary metrics |
| **Entry Realism** | Entry at state_known_bar+1 or later, not at detection_bar |
| **Lookahead Risk** | No future bars in signal detection; confirmation bars explicitly modeled |
| **Edge Accessibility** | MFE after entry is tradable (< 70% consumed before entry) |
| **Novelty vs Rescue** | New hypothesis, or disguised rescue of invalidated hypothesis? |
| **Exploration Suppression** | Valid exploration, or premature blocking due to prior failures? |
| **Creativity vs Cherry-Picking** | Creative hypothesis, or selective filtering after results? |

### Research Verdict Scale

**Planning documents:**
- `APPROVE_PLANNING_DOCUMENT` — Methodology sound, proceed
- `REJECT_LOOKAHEAD` — Timing model violates lookahead discipline
- `REJECT_NOT_NEW_HYPOTHESIS` — Disguised rescue of invalidated hypothesis
- `REJECT_INSUFFICIENT_SOURCE_RESEARCH` — Builder did not inspect repos/papers

**Diagnostic implementations:**
- `DONE_IMPLEMENTATION_CORRECT` — Code correct, ready for results
- `REJECT_TIMING_VIOLATION` — detection_bar used as return_start_bar
- `REJECT_NO_CONTROL_COHORT` — Control cohort missing

**Research results:**
- `HYPOTHESIS_PASSED` — Invalidation criteria NOT triggered, edge shows promise
- `HYPOTHESIS_INVALIDATED` — Invalidation criteria triggered, STOP
- `INCONCLUSIVE_DATA_GAP` — Sample size too small

### Full Guidance

See `docs/QUANT_RESEARCH_OPERATING_MODEL.md` for complete quant research audit standard.
```

---

### File 4: `CASCADE.md` (UPDATE)

**Add new section after "Implementation Checklist":**

```markdown
## Quant Research Builder Mode

When assigned a **quant research milestone**, Cascade must deliver a **research plan** before any code.

### Required Steps Before Coding

1. **Source Research** (if new edge family):
   - Search GitHub, TradingView, papers for related mechanisms
   - Document repos/sources with URLs
   - Classify: useful concept / bad repainting / discretionary / not applicable

2. **Mechanism Extraction**:
   - Extract testable mechanism (not copy code)
   - Define earliest knowable signal bar
   - Assess lookahead/repainting risk

3. **Timing Model**:
   - Define: detection_bar, state_known_bar, entry_candidate_bar
   - Measure: MFE before/after entry, % MFE consumed

4. **Baseline Comparison**:
   - Compare to trial-00095
   - Define success criteria

5. **Invalidation Criteria**:
   - Define STOP gates BEFORE results

6. **Minimal Research Plan** (first response):
   - Hypothesis, mechanism, timing model, data requirements
   - MFE accessibility design, baseline comparison
   - Invalidation criteria, scope, timeline
   - Request user approval before coding

### After Diagnostic Runs

Deliver result summary with:
- Dataset, best result, invalidation checks
- Control cohort, walk-forward
- Verdict: HYPOTHESIS_PASSED / INVALIDATED / INCONCLUSIVE
- **ONE recommendation** (STOP / PLAN next / PROMOTE)

### Full Guidance

See `docs/QUANT_RESEARCH_OPERATING_MODEL.md` for complete quant research builder duties.
```

---

### File 5: `CODEX.md` (CREATE — OPTIONAL)

**Purpose:** Codex-specific builder guidance (parallel to `CASCADE.md`)

**Structure:**
```markdown
# CODEX.md — Codex Operating Model

## Role
- Default builder/generator (Windsurf extension)
- Production code implementer
- Research implementer (with web/file-system access)

## Operating Rules
[Same as CASCADE.md Implementation Mode section]

## Quant Research Builder Mode
[Same as CASCADE.md Quant Research section]

## Codex-Specific Capabilities
- File-system search (grep, find)
- Web browsing for source research
- GitHub repo inspection
- Paper/article search

## Full Guidance
See `docs/QUANT_RESEARCH_OPERATING_MODEL.md` for complete quant research builder duties.
```

---

### File 6: `docs/templates/QUANT_RESEARCH_PLAN_TEMPLATE.md` (CREATE — OPTIONAL)

**Purpose:** Template for research planning documents

**Structure:**
```markdown
# Research Plan: [Hypothesis Name]

Date: YYYY-MM-DD
Builder: Codex / Cascade
Status: AWAITING_APPROVAL

## 1. Hypothesis
[One-sentence hypothesis]

## 2. Mechanism
[Detailed mechanism description]

## 3. Source Research
| Source | Type | URL | Classification |
|---|---|---|---|
| ... | ... | ... | ... |

## 4. Timing Model
- detection_bar: ...
- state_known_bar: ...
- entry_candidate_bar: ...

## 5. Data Requirements
[Tables, coverage, availability]

## 6. MFE Accessibility Design
[How MFE before/after entry measured]

## 7. Baseline Comparison
[Trial-00095 comparison criteria]

## 8. Control Cohort
[Deterministic control method]

## 9. Invalidation Criteria
**STOP (hypothesis invalidated):**
1. ...
2. ...

**EXPLORE (hypothesis shows promise):**
1. ...
2. ...

## 10. Scope
[No production code, research-only]

## 11. Estimated Timeline
[1 week / 2 weeks / 1 month]

## 12. Approval Request
[Request user approval before coding]
```

---

### File 7: `docs/templates/QUANT_RESEARCH_AUDIT_TEMPLATE.md` (CREATE — OPTIONAL)

**Purpose:** Template for research audit reports

**Structure:**
```markdown
# AUDIT: [Research Milestone Name]

Date: YYYY-MM-DD
Auditor: Claude Code
Commit: <hash>
Milestone Type: QUANT_RESEARCH

## Verdict: [Research Verdict]

## Standard Audit Axes
- Layer Separation: PASS / WARN / FAIL
- Contract Compliance: PASS / WARN / FAIL
...

## Quant Research Audit Axes
- Methodology Rigor: PASS / WARN / FAIL
- Source Coverage: PASS / WARN / FAIL / N/A
- Timing Discipline: PASS / WARN / FAIL
- Entry Realism: PASS / WARN / FAIL
- Lookahead Risk: PASS / WARN / FAIL
- Edge Accessibility: PASS / WARN / FAIL
- Novelty vs Rescue: NEW_HYPOTHESIS / RESCUE
...

## Research Result
- Hypothesis: [statement]
- Invalidation criteria triggered: [list]
- Result: HYPOTHESIS_PASSED / INVALIDATED / INCONCLUSIVE

## Critical Issues
## Warnings
## Observations
## Recommended Next Step
```

---

## 13. Minimal Patch Plan

### If Approved, Implementation Steps:

**Phase 1: Documentation Core**
1. Create `docs/QUANT_RESEARCH_OPERATING_MODEL.md` (comprehensive, from Sections 5-11 of this proposal)
2. Update `AGENTS.md`:
   - Add "Workflow Modes" section
   - Link to quant research doc in "Source of Truth Files"
3. Update `CLAUDE.md`:
   - Add "Quant Research Challenger Mode" section
4. Update `CASCADE.md`:
   - Add "Quant Research Builder Mode" section

**Phase 2: Templates (Optional)**
5. Create `CODEX.md` (if symmetry desired)
6. Create `docs/templates/QUANT_RESEARCH_PLAN_TEMPLATE.md`
7. Create `docs/templates/QUANT_RESEARCH_AUDIT_TEMPLATE.md`

**Phase 3: Validation**
8. Run markdown lint (if available)
9. Verify all links resolve
10. Check for consistency across files

**Phase 4: Integration**
11. Update `docs/MILESTONE_TRACKER.md` only if this becomes an active milestone
12. Commit documentation-only change with message:
    ```
    docs: add quant research operating model
    
    WHY: Codify timing discipline, source research, reverse engineering
    protocol learned from V1/SMC/MFE diagnostics. Current role files
    cover implementation but lack formal quant research guidance.
    
    WHAT:
    - Created QUANT_RESEARCH_OPERATING_MODEL.md (canonical authority)
    - Updated AGENTS.md (workflow modes)
    - Updated CLAUDE.md (quant research challenger mode)
    - Updated CASCADE.md (quant research builder mode)
    - Optional: Created CODEX.md, research plan/audit templates
    
    STATUS: Documentation-only, no code changes
    ```

**Estimated Effort:**
- Phase 1: 2-3 hours (core documentation)
- Phase 2: 1 hour (templates)
- Phase 3: 30 minutes (validation)
- Phase 4: 15 minutes (commit)
- **Total: ~4 hours**

---

## 14. Risks

### Risk 1: Bureaucracy Overhead

**Risk:** Templates and checklists become bureaucratic chores, slowing research without improving quality.

**Mitigation:**
- Templates are **guides**, not **mandatory forms**
- Builder may skip template if research plan is clear in prose
- Claude audits for **substance** (timing discipline, MFE analysis), not **template compliance**
- User can veto excessive process: "Skip the template, just tell me the hypothesis"

### Risk 2: Role Confusion

**Risk:** Builder/auditor boundaries blur. Cascade starts auditing, or Claude starts deciding what to research.

**Mitigation:**
- **Explicit reminder in handoffs:** "Do NOT audit your own output"
- **Decision authority table** remains unchanged (Claude selects, user approves, builder implements)
- **Verdict scale** clear: builder delivers, Claude audits, user decides

### Risk 3: Claude Becomes Strategic Owner

**Risk:** Claude starts deciding "we should STOP SMC research" instead of "SMC hypothesis invalidated, user decides next step".

**Mitigation:**
- **Claude recommends**, user decides
- **ONE recommendation** (not a menu), but user can veto
- **Strategic veto** remains with user (time budget, ROI, priorities)
- **Wording discipline:** "Recommend STOP" not "STOP approved"

### Risk 4: Builder Loses Creativity

**Risk:** Builder becomes robotic, follows templates without thinking.

**Mitigation:**
- **Templates are examples**, not mandates
- **Creativity is audited positively:** "Builder proposed novel mechanism extraction" earns PASS
- **Claude audits for creativity vs cherry-picking balance:** not all deviation is bad
- **Exploration is valued:** "Genuinely new hypothesis" classification exists

### Risk 5: Research Becomes Endless

**Risk:** Every failed hypothesis becomes "let's try one more diagnostic", research never stops.

**Mitigation:**
- **STOP rules codified** (Section 11)
- **Rescue attempts explicitly rejected** by Claude audit
- **Research ROI question:** User asks "have we spent enough time on this?"
- **User has strategic veto:** Can stop research at any time

### Risk 6: Templates Become Checklists Without Thinking

**Risk:** Builder fills template mechanically: "MFE accessibility: yes" without actual analysis.

**Mitigation:**
- **Claude audits substance:** Did builder ACTUALLY measure MFE before/after entry, or just claim it?
- **Evidence required:** Claude checks code, not just planning doc
- **Verdict FAIL if checklist empty:** "Planning doc says MFE analysis, but code shows no MFE metrics → FAIL"

---

## 15. Final Recommendation

### ONE Recommendation

**Add `docs/QUANT_RESEARCH_OPERATING_MODEL.md` and update role files (`AGENTS.md`, `CLAUDE.md`, `CASCADE.md`).**

### Reasoning

1. **Current role files are strong for implementation, weak for edge discovery.**
   - Layer separation, determinism, state integrity are well-covered.
   - Timing discipline, MFE accessibility, source research are ad-hoc, not codified.

2. **Recent research history proves the need.**
   - V1, SMC, MFE diagnostics taught timing discipline, accessibility analysis, reverse engineering.
   - These lessons should be permanent operating rules, not session-specific context.

3. **Preserve existing workflow, add mode distinction.**
   - Do NOT create new agent roles.
   - Define "Quant Research Mode" alongside "Implementation Mode".
   - Builder/auditor separation preserved.

4. **Make dangerous research safe, not suppress it.**
   - Goal: "More dangerous in research, safe in production"
   - Timing discipline prevents lookahead (safety).
   - Novelty classification prevents over-conservative blocking (dangerous).
   - STOP rules prevent endless rescue attempts (safety).
   - Source research enables external intelligence (dangerous).

5. **Documentation-only change, low risk.**
   - No code changes.
   - No strategy changes.
   - No live operations impact.
   - Reversible if user finds it too bureaucratic.

### If User Approves

**Next step:** User says "YES, implement this"

**Then:** Codex receives handoff to implement Phase 1 (core documentation):
- Create `docs/QUANT_RESEARCH_OPERATING_MODEL.md`
- Update `AGENTS.md`, `CLAUDE.md`, `CASCADE.md`
- Commit documentation-only change

**Estimated timeline:** 4 hours (see Section 13)

**Builder selection:** Codex (documentation milestone, file-system intensive)

**User approval required:** YES (strategic decision to extend role model)

---

## Appendix: Key Phrase

**"The goal is not to make agents more cautious. The goal is to make them more dangerous in research while remaining safe in production."**

- **Dangerous in research:**
  - Explore new edge families without over-conservative blocking
  - Challenge trial-00095 with validated evidence
  - Use external intelligence (GitHub, papers) to discover mechanisms
  - Propose genuinely new hypotheses (not parameter tweaks)

- **Safe in production:**
  - Timing discipline prevents lookahead (no fake edges)
  - MFE accessibility prevents late-entry edges (no consumed MFE)
  - Control cohorts prevent data-mining artifacts (no false positives)
  - Invalidation gates prevent promotion of weak candidates (no bad strategies)
  - STOP rules prevent endless rescue attempts (no research quicksand)

**This operating model extension enables both.**

---

**END OF PROPOSAL**

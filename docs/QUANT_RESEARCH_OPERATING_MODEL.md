# Quant Research Operating Model
**Status:** Canonical quant research authority
**Applies to:** Quant research, edge discovery, source research, reverse engineering, and hypothesis validation
**Parent authority:** `AGENTS.md`
> The goal is not to make agents more cautious. The goal is to make them more dangerous in research while remaining safe in production.
This document formalizes Quant Research / Reverse Edge Engineering Mode as a distinct workflow mode. It preserves the existing builder/auditor/user authority chain while adding rules for edge discovery: source research, mechanism extraction, timing discipline, MFE accessibility, benchmark comparison, and STOP/explore decisions.
## 1. Role in Project Workflow
`AGENTS.md` remains the top authority for workflow, role assignment, source-of-truth hierarchy, and commit discipline.
This document is the canonical authority for:
- external source research
- reverse edge engineering
- earliest-knowable-signal analysis
- timing discipline
- MFE/MAE accessibility
- benchmark challenge rules
- STOP versus exploration balance
- quant research verdicts
`CLAUDE.md` defines Claude Code as the independent auditor/challenger. `CASCADE.md` defines Cascade as an alternative builder. Codex uses `AGENTS.md` builder rules plus this document when assigned quant research work.
No new agent role is introduced. The role model remains:
| Role | Authority | Agent |
|---|---|---|
| Strategic decision and veto | User | Product owner |
| Independent evaluator and technical selector | Claude Code | Auditor/challenger |
| Default builder and research implementer | Codex | Builder |
| Alternative builder and research implementer | Cascade | Builder |
Builders build. Claude audits. The user decides. Builder output is never self-audited.
## 2. Workflow Modes
This project operates in five modes.
### 2.1 Implementation Mode
**When:** Blueprint phases, bot runtime features, execution engine, orchestrator, storage, governance, risk, and live-path behavior.
**Builder:** Implements scoped code, writes tests, runs validation, commits with WHAT / WHY / STATUS.
**Claude:** Audits layer separation, determinism, state integrity, contract compliance, and smoke coverage.
**Output:** Production code committed to the repository.
### 2.2 Research Lab Infrastructure Mode
**When:** Offline optimization infrastructure, walk-forward workflow, store schema, autoresearch loop, promotion gates, and research lab tooling.
**Builder:** Implements research lab modules, preserves live-path isolation, validates reproducibility and artifact consistency.
**Claude:** Audits methodology integrity, promotion safety, reproducibility, lineage, data isolation, and boundary coupling.
**Output:** Research lab infrastructure committed to the repository.
### 2.3 Quant Research / Edge Discovery Mode
**When:** Exploring new edge families, reverse engineering failure points, inspecting external sources, or validating hypotheses.
**Builder:** Performs source research, extracts mechanisms, defines timing model, designs MFE accessibility analysis, compares baseline, defines controls, and sets invalidation criteria before results.
**Claude:** Audits methodology rigor, source coverage, timing discipline, entry realism, lookahead risk, edge accessibility, novelty versus rescue, and exploration suppression risk.
**Output:** Research plans, reports, diagnostics, result summaries, and invalidation verdicts.
### 2.4 Promotion Mode
**When:** Promoting a validated research candidate to paper or live settings.
**Builder:** Generates approval bundle, applies approved diffs, verifies backups, deploys only when approved.
**Claude:** Audits promotion gate, backup existence, deployment checklist, and rollback readiness.
**Output:** Candidate deployed to paper or promotion blocked.
### 2.5 Live Operations / Incident Mode
**When:** Production issues, zombie processes, database recovery, deployment failures, or live bot health incidents.
**Builder:** Diagnoses from production runtime data, implements scoped fix, verifies on server, documents incident.
**Claude:** Audits no-data-loss risk, rollback path, and backup awareness.
**Output:** Incident resolved and documented.
## 3. Quant Research Builder Mode
Quant research builders must not merely implement the requested idea. They must convert the idea into a testable mechanism, define when information becomes knowable, and prove whether tradable movement remains after realistic entry.
### 3.1 When This Mode Applies
This mode applies to quant research planning, edge discovery diagnostics, hypothesis validation, source research review, reverse engineering analysis, new edge family exploration, timing feasibility, and MFE accessibility work.
### 3.2 Source Research
Source research is mandatory when:
- the milestone introduces a new edge family
- the mechanism comes from GitHub, TradingView, Pine, papers, articles, or another external source
- the user requests source research
- existing diagnostics have invalidated a local family and the next idea depends on external intelligence
The builder must inspect implementation code when available, not only README files or marketing claims. GitHub, TradingView, Pine scripts, and papers are maps, not truth. The builder extracts mechanisms from them, then validates independently.
Each source must be classified:
| Classification | Meaning |
|---|---|
| Useful concept | Contains a mechanism worth extracting and testing |
| Benchmark candidate | Contains performance evidence worth comparing |
| Needs validation | Plausible implementation, but timing or data risk remains |
| Bad/repainting | Uses future bars, discretionary relabeling, or impossible signals |
| Discretionary | Useful for human context, not directly testable |
| Not applicable | Does not map to available data or the current research question |
### 3.3 Mechanism Extraction
The builder must extract one testable mechanism at a time. Pattern names are not mechanisms. "Order block", "liquidity sweep", "fair value gap", and "SMC" are labels until translated into code-ready rules.
A valid mechanism definition includes:
- observable inputs
- deterministic rule
- earliest knowable bar
- required confirmation bars
- required data tables
- invalidation condition
- expected edge behavior
The builder must identify whether the rule is deterministic, whether it repaints, whether it requires future bars, whether the signal can be known before the move is consumed, and whether available data can reproduce the rule.
### 3.4 Timing Model
Before coding, the builder must define:
- `detection_bar`
- `state_known_bar`
- `confirmation_bar`
- `entry_candidate_bar`
- `label_available_bar`
- `return_start_bar`
The builder must state which bar is used for primary returns. Primary returns must be measured from `entry_candidate_bar`, not from `detection_bar`. Detection-bar returns are audit-only: they measure how much opportunity existed before realistic entry.
### 3.5 MFE Accessibility
Every timing-sensitive edge diagnostic must measure:
- MFE before entry
- MFE after entry
- MAE after entry when relevant
- percent of MFE consumed before entry
- time from detection to entry
- time from entry to MFE
If more than 70% of total MFE is consumed before realistic entry, the edge is not tradable even if the pattern exists. If decisive information becomes knowable only after the move is mostly consumed, the hypothesis is invalidated or must move earlier.
### 3.6 Baseline Comparison
Every candidate must compare against trial-00095 as the active validated baseline. The comparison must include expectancy ratio, profit factor, win rate, drawdown behavior, trade count, walk-forward validation, timing realism, and control cohort.
Trial-00095 is the benchmark, not religion. New research can challenge it with validated evidence.
### 3.7 Control Cohort
The builder must define a deterministic control cohort before results whenever possible. Controls can include same-regime non-signal cohorts, shuffled labels for offline analysis, adjacent state cohorts, or naive threshold baselines. Any stochastic control must stay isolated outside the deterministic core.
The control must answer whether the proposed mechanism adds information beyond ordinary market movement.
### 3.8 Invalidation Criteria
STOP gates must be defined before running diagnostics. Examples:
- net expectancy below benchmark after costs
- profit factor below required threshold
- walk-forward failure
- control cohort performs similarly or better
- MFE consumed before entry above 70%
- sample size too small for the claim
- signal requires future bars
- result depends on relaxed constraints after failure
The builder must not rescue a failed hypothesis by relaxing thresholds after seeing results.
### 3.9 Minimal Research Plan Before Code
Before coding, the builder must present:
- hypothesis
- extracted mechanism
- source coverage summary
- timing model
- data requirements
- MFE accessibility design
- baseline comparison
- control cohort
- invalidation criteria
- scope boundaries
- expected artifacts
The builder requests user approval before implementation when the milestone is a planning milestone or when scope is not already approved.
### 3.10 Result Summary After Diagnostics
After diagnostic runs, the builder must report dataset and coverage, source data used, best result, baseline comparison, control cohort result, walk-forward result where applicable, timing validation, MFE accessibility result, invalidation checks, and one recommendation: STOP, PLAN next diagnostic, or PROMOTE.
The builder may recommend. The builder does not issue the final audit verdict.
## 4. Quant Research Auditor Mode
Claude Code audits quant research as methodology, not only code. The auditor verifies whether the research would still be valid if implemented perfectly.
### 4.1 Audit Axes
| Axis | What Claude Code verifies |
|---|---|
| Methodology rigor | Timing discipline, MFE accessibility, and control cohort exist |
| Source coverage | Required repos, papers, or scripts were inspected and classified |
| Repo/code inspection | Builder read implementation code, not only README text |
| Timing discipline | Detection, known state, entry, and return start are separated |
| Entry realism | Entry occurs at `state_known_bar+1` or later |
| Lookahead risk | No future bars are used in detection or primary returns |
| Edge accessibility | Tradable MFE remains after entry |
| Novelty vs rescue | Hypothesis is genuinely new or rejected as rescue |
| Exploration suppression | Valid new mechanisms are not blocked solely by prior failures |
| Creativity vs cherry-picking | Creative hypotheses are allowed; post-result filtering is rejected |
| Baseline honesty | trial-00095 is treated as benchmark, not ignored or worshiped |
| Invalidation gates | STOP rules were defined before results and enforced after results |
### 4.2 Auditor Responsibilities
Claude Code must challenge whether the plan tests the stated hypothesis, whether entry is realistically knowable, whether metrics are measured from the correct bar, whether source research was sufficient, whether the builder is disguising a rescue attempt as a new idea, whether a failed family still contains an earlier knowable state worth testing, and whether the recommendation follows from evidence.
Claude Code does not become the strategic owner. Claude recommends one next step. The user decides.
### 4.3 Planning Documents
Planning documents are approved only when they define hypothesis, source coverage, extracted mechanism, timing model, data requirements, MFE accessibility method, baseline comparison, control cohort, and invalidation criteria.
Missing timing discipline is a rejection condition. Missing source coverage is a rejection condition when the milestone requires external research.
### 4.4 Diagnostic Implementations
Diagnostic code is audited for correct data usage, deterministic calculations, no production-path leakage, no future bars in signal detection, correct `return_start_bar`, explicit label availability, control cohort implementation, and reproducible output.
Correct implementation does not mean the hypothesis passed.
### 4.5 Research Results
Research results are audited for whether invalidation criteria triggered, whether benchmark comparison is honest, whether walk-forward was used when required, whether sample size supports the claim, whether MFE accessibility remains tradable, and whether the conclusion is overstated.
Claude verdicts classify the research outcome. They do not automatically authorize production promotion.
## 5. Timing Discipline
Timing discipline is mandatory for quant research. Recent research established that delayed labels measured from `detection_bar` create fake edge.
The decisive question is not "does the pattern exist?" The decisive question is "is decisive information knowable early enough to trade?"
### 5.1 Bar Definitions
| Bar | Definition |
|---|---|
| `detection_bar` | First bar where a raw event occurs |
| `state_known_bar` | First bar where the required state is knowable without future data |
| `confirmation_bar` | Bar that confirms the state, if confirmation is required |
| `entry_candidate_bar` | Earliest bar where an order could realistically be placed |
| `label_available_bar` | Bar where outcome label becomes known for analysis |
| `return_start_bar` | Bar from which primary returns are measured |
`return_start_bar` must equal `entry_candidate_bar` for primary metrics. It may equal `label_available_bar` only when label availability is the earliest realistic entry condition. It must not equal `detection_bar` unless the signal is fully knowable and tradable on that same bar, which must be explicitly justified.
### 5.2 Required Separation
Primary research must separate event detection, state knowledge, confirmation, entry, label availability, and return measurement.
If a source requires candle `i+1` or later to confirm a pattern on candle `i`, the signal is not knowable on candle `i`. If entry is executed on the same bar that provides confirmation, the builder must prove order timing is realistic.
### 5.3 MFE Before and After Entry
MFE before entry measures opportunity consumed between detection and realistic entry. MFE after entry measures opportunity still accessible to the strategy.
Percent MFE consumed before entry:
`MFE_before / (MFE_before + MFE_after) * 100`
If MFE consumed before entry is greater than 70%, the edge is not tradable. Detection-bar returns may be computed only as audit metrics. They cannot be used as primary validation.
### 5.4 Permanent Lessons
From V1 Taxonomy Diagnostic:
- delayed labels measured from `detection_bar` create fake edge
- measure from `entry_candidate_bar` or `label_available_bar`, not detection
From SMC Sequence Diagnostic:
- median MFE before entry was 0.011565
- median MFE after entry was 0.004916
- if MFE is consumed before entry, the edge is not tradable
From MFE Accessibility Diagnostic:
- no post-sweep knowable state had positive expectancy
- the question shifted from pattern existence to early knowability
## 6. Source Research Requirements
External source research is not optional when research claims a new external mechanism. The builder must document source coverage in enough detail for Claude Code to audit.
### 6.1 When Source Research Is Mandatory
Source research is mandatory for new edge families, external named mechanisms, GitHub/TradingView/Pine/paper/repo-derived ideas, explicit user source research requests, and benchmark challenges based on external evidence.
Source research may be optional for internal bugfixes, trial-00095 parameter comparison, research lab infrastructure, and meta-diagnostics using already approved local definitions.
### 6.2 Required Source Fields
Each source entry must include source name, URL or citation, source type, inspected artifact, extracted mechanism, classification, determinism assessment, lookahead/repainting assessment, data availability assessment, and applicability conclusion.
### 6.3 Source Anti-Patterns
The builder must avoid treating README claims as proof, copying Pine code without lookahead review, using visual discretionary patterns as deterministic signals, ignoring source code because the concept name is familiar, using future bars without explicit confirmation timing, or accepting backtest screenshots without reproducible logic.
### 6.4 Mechanism Extraction Standard
A source-derived mechanism is acceptable only when it can be expressed as deterministic inputs, deterministic rule, earliest knowable state, realistic entry, measurable outcome, and invalidation criteria.
If those cannot be stated, the source may inform exploration but cannot drive implementation.
## 7. Reverse Engineering Protocol
Reverse engineering starts from the failure point.
Core question:
> Where does opportunity become knowable, and is there tradable movement left?
For every failed or suspicious hypothesis, ask:
- Did the pattern fail because it has no edge?
- Did it fail because confirmation arrives too late?
- Did MFE occur before entry?
- Is there an earlier knowable state?
- Is the earlier state deterministic?
- Is the earlier state tradable after costs?
- Is the next proposal genuinely new or a rescue?
### 7.1 Move Earlier or Stop
If opportunity is knowable too late, move earlier to a deterministic earlier state or stop the research family. Do not rescue the same failed hypothesis with looser parameters. Do not move return measurement backward to detection. Do not redefine labels after seeing results.
### 7.2 New Hypothesis Versus Rescue
A new hypothesis uses a different mechanism, data source, earliest knowable state, causal path, or information family.
A rescue attempt uses relaxed thresholds after invalidation, detection-bar returns after entry-timing failure, new filters on the same invalidated late signal, different costs to make weak expectancy appear viable, or sample selection after seeing results.
Rescue attempts are rejected.
## 8. Benchmark Rule: Trial-00095
Trial-00095 is the active validated baseline:
- ER approximately 2.1
- PF approximately 4.6
- walk-forward validated
Trial-00095 is a benchmark, rollback point, comparison standard, and evidence that a known edge exists. It is not proof that no other edge exists, permission to skip source research, permission to reject all exploration, or a reason to promote weaker candidates.
### 8.1 Legitimate Challenge Criteria
A new edge can challenge trial-00095 only with validated evidence:
| Requirement | Threshold |
|---|---|
| Cost-adjusted expectancy | ER > 2.1 |
| Profit factor | PF > 4.0 |
| Walk-forward | Validated out of sample |
| Timing realism | Entry at `state_known_bar+1` or later |
| MFE accessibility | Less than 70% MFE consumed before entry |
| Control cohort | Candidate beats control |
If a candidate beats trial-00095 with realistic timing, it deserves promotion planning. If a candidate matches trial-00095 but adds complexity, trial-00095 remains preferred. If a candidate beats trial-00095 only from detection-bar returns, it is rejected.
## 9. STOP / Exploration Balance
The operating model must prevent endless rescue of invalidated ideas and premature suppression of genuinely new mechanisms. Dangerous research is encouraged. Unsafe production promotion is not.
### 9.1 When to STOP
STOP a research family when invalidation criteria are met, accessible state space is exhausted, rescue attempts are detected, research ROI is negative, the benchmark already captures the earliest accessible state, no earlier deterministic signal exists, or external sources are repainting/discretionary/not testable.
STOP means stop that direction. It does not mean stop all research.
### 9.2 When to OPEN a New Family
OPEN a new research family when the mechanism is genuinely new, external evidence supports testing, reverse engineering indicates an earlier signal, the data source is orthogonal to failed work, the hypothesis is not a parameter tweak, or the expected edge has a different causal basis.
Examples: order-flow imbalance after price-action failures, liquidation cascade signals using force-order data, funding/open-interest stress mechanisms, or volatility contraction regimes unrelated to sweep/reclaim logic.
### 9.3 When to Run a Meta-Diagnostic
Run a meta-diagnostic when the methodology question matters more than immediate performance: where edge becomes inaccessible, what the earliest knowable state is, which labels create lookahead, which sources are deterministic, or whether accessible state space is exhausted.
Meta-diagnostics should clarify STOP versus OPEN.
### 9.4 When to Promote to Implementation
Promote to feature engineering only when the hypothesis passed invalidation gates, timing is realistic, MFE remains accessible, control cohort is beaten, walk-forward validates, candidate beats or justifies replacing benchmark, and user approves promotion.
Research promise is not deployment approval.
## 10. Research Verdict Scale
Research verdicts classify planning quality, implementation correctness, and research outcomes.
### 10.1 Planning Verdicts
| Verdict | Meaning |
|---|---|
| `APPROVE_PLANNING_DOCUMENT` | Methodology sound; proceed to implementation |
| `REJECT_LOOKAHEAD` | Timing model violates lookahead discipline |
| `REJECT_NOT_NEW_HYPOTHESIS` | Disguised rescue of invalidated hypothesis |
| `REJECT_SOURCE_COVERAGE_INSUFFICIENT` | Required source research missing or shallow |
| `REJECT_CHERRY_PICKING` | Plan depends on selective post-result filtering |
| `INCONCLUSIVE_DATA_GAP` | Required data is absent or insufficient |
### 10.2 Diagnostic Implementation Verdicts
| Verdict | Meaning |
|---|---|
| `DONE_IMPLEMENTATION_CORRECT` | Code correctly implements approved diagnostic |
| `REJECT_TIMING_VIOLATION` | Detection bar used as return start or entry |
| `REJECT_NO_CONTROL_COHORT` | Required control cohort missing or broken |
| `REJECT_LOOKAHEAD` | Future data used in signal detection |
| `REJECT_CHERRY_PICKING` | Implementation filters after seeing outcomes |
### 10.3 Research Result Verdicts
| Verdict | Meaning |
|---|---|
| `HYPOTHESIS_PASSED` | Invalidation criteria not triggered; edge shows promise |
| `HYPOTHESIS_INVALIDATED` | Invalidation criteria triggered; stop this direction |
| `INCONCLUSIVE_DATA_GAP` | Sample size or coverage insufficient |
| `REJECT_LOOKAHEAD` | Result depends on unavailable future information |
| `REJECT_NOT_NEW_HYPOTHESIS` | Result is a rescue attempt, not new evidence |
Builder result summaries and Claude audits should end with one recommendation: STOP, PLAN next diagnostic, PROMOTE to feature engineering, or COLLECT data first. Claude recommends. The user decides.
## 11. Production Safety Boundary
Quant research may be aggressive, exploratory, and externally informed. Production behavior remains governed by the deterministic core and existing safety rules.
Quant research must not:
- modify live strategy parameters
- modify `settings.py` as a candidate promotion channel
- change execution behavior
- bypass governance or risk
- introduce LLMs into the decision loop
- use stochastic logic in the core path
- promote candidates without approval
Research code and documents may explore. Production code must remain deterministic, auditable, and recoverable.
## 12. Documentation and Artifact Rules
A complete research trail should include approved plan, source coverage, diagnostic implementation, result report, audit verdict, recommendation, and user decision.
Do not commit generated databases, snapshots, ad hoc reports, or approval bundles unless the milestone explicitly includes them. Do not mix bugfix work with methodology redesign. Do not modify production code during documentation-only or research-planning milestones.
## 13. Summary Rules
Permanent rules:
- source research is required for new external mechanisms
- source code must be inspected when available
- mechanisms must be extracted, not copied blindly
- timing bars must be defined before code
- primary returns must start at `entry_candidate_bar`
- detection-bar returns are audit-only
- MFE before and after entry must be measured for timing-sensitive edges
- if more than 70% of MFE is consumed before entry, the edge is not tradable
- failed hypotheses are stopped, not rescued
- genuinely new mechanisms may be opened
- trial-00095 is the benchmark, not religion
- Claude audits; builders build; user decides
This makes agents more dangerous in research while remaining safe in production.

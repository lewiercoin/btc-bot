# BLUEPRINT_MODELING_V1_SYNTHESIS

Status: draft blueprint for independent audit by Claude / Cascade / Codex / Perplexity
Date: 2026-04-21
Scope position in roadmap: after DATA-INTEGRITY-V1, before EXECUTION-REALISM-V1 and OPTUNA-RECALIBRATION-V1

---

## Purpose of this document

This blueprint is a **synthetic architectural proposal** for `MODELING-V1` prepared from multi-source reasoning and current project context.
It is **not** yet a builder handoff.
It is intended to be audited independently by multiple models before finalizing the milestone contract.

Primary design constraint:
- preserve the existing reclaim edge
- add a deterministic context layer above it
- do not introduce runtime LLM decision-making
- do not leak modeling into governance, risk, or execution

---

## Full project context

### Current confirmed state

The bot already has:
- deterministic market snapshot ingestion
- feature computation
- regime classification
- signal generation around liquidity sweep + reclaim logic
- governance layer
- risk layer
- execution layer
- audit and diagnostics infrastructure

The project has already identified:
- the reclaim edge is alive
- throughput improved significantly under Experiment v1
- diagnostics currently contain a polluted bucket (`uptrend_continuation_weak`)
- time-of-day / session effects appear relevant
- data quality / persistence / readiness must be hardened in DATA-INTEGRITY-V1

### Known roadmap order

1. DATA-INTEGRITY-V1
2. MODELING-V1
3. EXECUTION-REALISM-V1
4. OPTUNA-RECALIBRATION-V1

### Hard constraints for MODELING-V1

- Do **not** rebuild the trading system from scratch
- Do **not** remove or replace reclaim edge logic
- Do **not** put LLM into runtime decision loop
- Do **not** add black-box runtime ML as primary decision-maker
- Maintain determinism, replayability, auditability, and layer separation
- MODELING-V1 must consume outputs of DATA-INTEGRITY-V1 (feature quality / maturity / coverage truth)
- MODELING-V1 must not secretly mutate execution, risk, or governance semantics

---

## Problem statement

The current system appears to have an existing edge, but it likely treats too many contexts as equivalent.
Specifically, the bot needs a way to answer:

> In which contexts should the existing reclaim edge be allowed, reduced, or blocked?

This is not a new alpha-generation milestone.
This is a **contextual eligibility milestone**.

MODELING-V1 should therefore answer questions such as:
- Does the same reclaim mean the same thing in EU, US, and Asian hours?
- Does high volatility change reclaim reliability?
- Should some contexts allow normal execution while others require stricter eligibility?
- How do we distinguish “valid edge in weak context” from “not actually this pattern”?

---

## Core thesis of MODELING-V1

MODELING-V1 should be implemented as a **deterministic context eligibility layer** above the existing reclaim edge.

It should:
- classify context
- consume data-quality truth from DATA-INTEGRITY-V1
- produce explicit, replayable context decisions
- influence whether an already-detected reclaim setup is eligible
- improve audit clarity and contextual discrimination

It should **not**:
- replace reclaim detection
- become a black-box predictor
- directly perform execution logic
- absorb governance/risk responsibilities

---

## Architectural proposal (synthetic)

### Recommended direction

The most likely correct shape is a **small, deterministic context-policy layer** built on top of:
- timestamp/session information
- volatility bucket
- existing regime output
- feature-quality flags from DATA-INTEGRITY-V1
- existing setup metadata from signal path

This layer should emit a **context decision / context policy result** rather than a new trading signal.

### Working name candidates

Any of the following could be valid, depending on repo fit and final audit verdict:
- `ContextPolicy`
- `MarketContext`
- `ContextDecision`
- `EligibilityContext`
- small `ContextLayer`

This document intentionally does **not** freeze the final class/module name.
That choice should be made after independent audits.

---

## Candidate pipeline shapes to audit

This blueprint proposes **three plausible implementation shapes** that must be independently audited.

### Variant A — Regime extension

Concept:
- extend existing `RegimeEngine` so it also emits richer context semantics
- session-aware and volatility-aware interpretation is folded into regime-related output

Advantages:
- minimal additional moving parts
- reuses an existing context-bearing layer
- fewer new modules

Risks:
- regime may become overloaded
- calendar/session semantics may get mixed with market-structure semantics
- danger of combinatorial explosion in regime labels
- may reduce clarity between “market state” and “policy state”

### Variant B — Thin context-policy layer (preferred candidate)

Concept:
- keep `FeatureEngine` and `RegimeEngine` as they are conceptually
- add a thin deterministic layer that consumes:
  - timestamp/session bucket
  - volatility bucket
  - regime
  - feature quality truth
  - optional setup metadata
- emit a context result such as:
  - `ALLOW`
  - `ALLOW_REDUCED`
  - `BLOCK`
  - plus reason codes and context labels

Advantages:
- preserves existing edge
- keeps modeling as eligibility rather than new signal generation
- easier to audit and replay
- lower risk of overengineering than full engine rewrite

Risks:
- still requires precise contract placement in pipeline
- if done sloppily, can leak into governance/risk
- builder may be tempted to hide threshold changes here

### Variant C — Standalone context engine

Concept:
- introduce a more explicit module that computes a structured `MarketContext`
- this module is separate from regime and signal but remains deterministic and stateless

Advantages:
- strongest separation of concerns if designed well
- explicit contracts and interfaces
- easier long-term extensibility

Risks:
- possible duplication with existing regime semantics
- may be too heavy for V1
- higher implementation cost
- strong risk that builder turns it into a mini-decision engine

### Current synthetic recommendation

At this stage, this document leans toward:
- **Variant B as the safest implementation target**
- with **Variant C concepts used selectively only if they do not duplicate regime responsibilities**
- and **Variant A accepted only if audits prove regime extension remains clean and bounded**

---

## Proposed functional responsibilities of MODELING-V1

### In scope (proposed)

1. **Session-aware context classification**
- classify session or session phase from UTC time
- examples: `ASIA`, `EU`, `US`, `OVERLAP`, or more precise phase buckets if justified

2. **Volatility-aware context classification**
- classify volatility state deterministically from existing features
- examples: `LOW`, `NORMAL`, `HIGH`, `EXTREME`

3. **Quality-aware context consumption**
- consume feature-quality states from DATA-INTEGRITY-V1
- if context depends on immature/incomplete data, mark this explicitly

4. **Eligibility / abstention logic**
- do not predict price direction from scratch
- instead decide whether the existing reclaim setup is contextually eligible
- likely output family:
  - `ALLOW`
  - `ALLOW_REDUCED`
  - `BLOCK`

5. **Reason-code-rich diagnostics**
- every context decision must be explainable
- logs and artifacts must show context state and decision reason

6. **Signal-path semantics cleanup support**
- clean distinction between:
  - true setup in weak context
  - off-pattern case
  - geometry issue
  - data-quality issue
- improve polluted diagnostic buckets where applicable

### Should-have candidates

1. **Explicit state labels / finite-state logic for setup lifecycle**
- sequence-aware state handling for reclaim lifecycle if repo fit allows it cleanly

2. **Hierarchical gating structure**
- order of evaluation should be explicit
- e.g. data validity → context validity → edge validity → governance → risk

3. **Per-session / per-context metrics**
- candidate counts, allow/block counts, expectancy, reject reasons by context

### Too early for V1

1. runtime probabilistic classifier as primary gate
2. HMM as core runtime controller
3. mixture-of-experts or neural gating
4. new external data sources
5. session-specific execution/risk templates
6. adaptive self-updating thresholds in production

---

## Proposed out-of-scope contract

The following should stay out of MODELING-V1 unless later audits prove otherwise:

- execution realism (spread, slippage, fill model)
- risk sizing changes
- leverage changes
- new live risk caps
- Optuna / parameter tuning
- new alpha generation logic
- replacing reclaim detection
- runtime ML/LLM decision loop
- cross-venue order book intelligence
- long/short ratio / liquidation clustering as new dependencies

---

## Proposed decision philosophy

MODELING-V1 should follow **negative permissioning**:

A trade is only eligible if successive layers do not block it.

Illustrative logical order:
1. feature/data validity
2. session eligibility
3. volatility/context eligibility
4. existing edge validity
5. governance
6. risk
7. execution

This blueprint does **not** yet freeze the exact insertion point in code.
That is one of the main questions for independent audit.

---

## Proposed context output contract (draft)

This is a conceptual contract for audit, not a frozen implementation spec.

```text
ContextLabel:
- session_bucket
- volatility_bucket
- optional context_phase

ContextDecision:
- action: ALLOW | ALLOW_REDUCED | BLOCK
- reason_code
- context_version
- quality_flags_consumed
- optional policy_label
```

Possible reason-code families:
- `context_session_unfavorable`
- `context_volatility_unfavorable`
- `context_quality_unavailable`
- `context_quality_degraded`
- `context_transition_window`
- `context_policy_reduce`
- `context_policy_allow`
- `context_policy_block`

This document intentionally leaves final naming flexible.
The key is: **discrete, deterministic, auditable output**.

---

## Proposed anti-patterns / forbidden moves

Independent auditors should test this blueprint specifically against the following anti-patterns:

1. **Rebuilding the system from scratch**
- replacing the edge instead of layering context on top

2. **Runtime LLM decision-making**
- any live prompt-based trading eligibility or threshold setting

3. **Black-box runtime ML controller**
- context decided by opaque model with poor auditability

4. **Layer leak into Governance**
- modeling decisions hidden as governance vetoes

5. **Layer leak into Risk**
- context-dependent leverage or sizing introduced prematurely

6. **SignalEngine contamination**
- session if/else logic scattered directly inside signal rules without explicit context contract

7. **Regime overload**
- turning `RegimeEngine` into a bucket for every kind of context and policy

8. **Silent edge rewrite**
- changing reclaim detection or core thresholds under the label of “context adaptation”

9. **Dynamic self-rewriting thresholds**
- online adaptation without frozen versioning and replay guarantees

10. **Reason-code ambiguity**
- inability to say why a candidate was allowed or blocked

---

## Proposed acceptance criteria for future implementation

These are blueprint-level targets, not final builder ACs.

1. **Determinism**
- same input snapshot and same configuration produce same context result

2. **Replayability**
- historical runs can reconstruct context decisions exactly

3. **Auditability**
- every context decision emits reason code(s), context labels, and version id

4. **Backward compatibility under neutral mode**
- if context layer is neutral/disabled, behavior should match pre-modeling baseline closely

5. **No hidden edge rewrite**
- reclaim detection and execution semantics remain intact unless explicitly approved elsewhere

6. **Per-context observability**
- logs / analytics can show performance by session and context bucket

7. **Quality-truth compliance**
- context logic respects DATA-INTEGRITY-V1 feature readiness and does not fake maturity

---

## Open architectural questions for independent audit

The following questions are intentionally left open and should be answered independently by Claude / Cascade / Codex / Perplexity:

1. Should session and volatility semantics live inside `RegimeEngine`, beside it, or above it?
2. Should context decision happen before candidate generation, after candidate generation, or between signal and governance?
3. Should the layer emit threshold modifiers, discrete eligibility decisions, or both?
4. Is `ALLOW_REDUCED` appropriate in V1, or should V1 remain binary (`ALLOW/BLOCK`) for simplicity?
5. Should volatility context be derived from existing ATR features only, or can it incorporate regime semantics directly?
6. How should signal-path cleanup relate to context modeling versus separate diagnostics cleanup?
7. Is a finite-state lifecycle for reclaim setup necessary in V1, or should that wait?
8. Should a neutral context mode be mandatory for regression validation?
9. Should context outputs be persisted in existing `decision_outcomes`, or modeled through new storage structure later?
10. Is a thin context-policy layer enough, or does repo architecture justify a more explicit `ContextEngine` contract?

---

## Draft roadmap interpretation

This blueprint assumes the following sequencing logic:

- DATA-INTEGRITY-V1 hardens truthfulness of inputs
- MODELING-V1 adds deterministic context eligibility
- EXECUTION-REALISM-V1 addresses costs / fill realism
- OPTUNA-RECALIBRATION-V1 tunes on a more trustworthy system

This means MODELING-V1 should **not** attempt to solve problems that belong to execution realism or tuning.

---

## How this blueprint should be used

This document should be given to:
- Claude
- Cascade
- Codex
- Perplexity

with a request for **independent audit**, not compliance.

Each auditor should answer:
1. Which variant is best for this repo?
2. What is wrong or incomplete in this blueprint?
3. What would they change in scope, contract, or placement?
4. What anti-patterns are still insufficiently guarded against?
5. Should the next artifact be a final `BLUEPRINT_MODELING_V1.md` or a builder handoff?

---

## Bottom line for operator

This synthetic blueprint proposes that MODELING-V1 should be:
- a deterministic context eligibility milestone
- layered on top of existing reclaim edge
- session-aware
- volatility-aware
- quality-aware
- rich in reason codes and diagnostics
- strict about replayability and separation of concerns

It should **not** become:
- a new trading strategy
- a runtime ML/LLM controller
- a hidden rewrite of reclaim logic
- or a leak of context logic into governance / risk / execution.

Current recommendation before implementation:
**run independent audits of this blueprint first, then synthesize a final repo-grounded `BLUEPRINT_MODELING_V1.md`.**

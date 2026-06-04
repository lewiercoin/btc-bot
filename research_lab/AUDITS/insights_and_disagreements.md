# Insights and Disagreements — Codex Deliverables Audit

**Auditor:** Claude Code (Windsurf)  
**Date:** 2026-06-04

---

## INSIGHTS (Things Codex Got Right That Were Not Obvious)

### I1 — MFE Accessibility Applied As First-Principle Filter

**Deliverable:** `smc_libraries_mining.md` (line 126-127)

Codex correctly identified that SMC breaker/mitigation/OTE concepts are "delayed-confirmation" by nature, and therefore inherit the same MFE accessibility problem that invalidated prior btc-bot SMC research.

**Why this is valuable:**  
This is NOT cargo-culting "SMC is bad." This is **applying institutional memory** (prior `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` results) to pre-filter candidates. Codex didn't need to test breaker/mitigation to know they're high-risk — prior falsification already covered the timing class.

**Operator should note:**  
Codex confidence ratings (reclaim_rejection 3/5, reclaim_mitigation 1/5) are well-reasoned, not arbitrary.

---

### I2 — Informational-Only V1 Contract Is Rigorous Defensive Design

**Deliverable:** `microstructure_context_v1_blueprint.md` (line 80-114)

V1 contract (line 80-96) forbids:
- Confluence weight
- Governance veto
- Risk veto
- Execution sizing
- Candidate direction inference
- Threshold rescue

8-step promotion gate (line 102-114) requires:
- DATA-INTEGRITY-V1 complete
- Deterministic tests
- Replay parity
- Independent lift over baseline (not subset filtering)
- MFE accessibility proof
- Walk-forward validation
- Claude audit
- Operator approval

**Why this is valuable:**  
This is institutional-grade gate discipline. It prevents "informational context" from silently becoming "decision-relevant signal" through scope creep. Many projects fail here — feature starts as "just logging," ends up in production decision path without audit.

**Operator should note:**  
If V1 contract is honored, `MicrostructureContext` is low-risk speculation. If V1 contract is violated (e.g., F010 finding — adding to `Features` dataclass), it becomes production risk.

---

### I3 — Level Scanner As Portfolio Factory (Not Monolithic Engine)

**Deliverable:** `level_scanner_spec.md` (line 4-5, 173-188)

Codex designed `level_scanner` as **facts-only factory**, explicitly NOT a signal engine. Line 182-188 enforces:
- Scanner emits facts
- Setup modules interpret facts into candidates
- Governance/risk veto AFTER candidate exists
- Scanner never places trades or modifies runtime

**Why this is valuable:**  
This is clean setup portfolio architecture. Monolithic engines (one giant `if/elif/elif` cascade) are unmaintainable. Factory pattern allows independent testing of level detection (scanner) vs entry logic (setup modules).

**Operator should note:**  
If this pattern is followed, adding new setup candidates (`reclaim_breaker`, `ote_pullback`) is low-coupling, high-cohesion work. If violated (scanner starts making entry decisions), it becomes spaghetti.

---

## DISAGREEMENTS WITH CLAUDE IN BROWSER

### D1 — joshyattridge Is Reference Implementation, Not "Gold"

**Deliverable:** `smc_libraries_mining.md` + `codex_self_audit.md` (line 22-24 of self-audit)

**Codex position:**  
Claude in browser ranked joshyattridge/smart-money-concepts as "gold" for `reclaim_session`. Codex disagrees: *"The existing btc-bot session-sweep specialist already failed, and joshyattridge's session implementation is a fixed-clock helper with timezone edge cases, not an edge source. It is useful as a cross-validation reference for session labels, but not 'gold' as a setup generator unless the new candidate is explicitly level-provenance-based and passes MFE accessibility."*

**My (auditor) assessment:**  
Codex is **likely correct**. Evidence:
1. `SESSION_SWEEP_SPECIALIST_AUDIT_PACKAGE.md` exists (prior failure)
2. joshyattridge `sessions()` is 300-line timezone-handling helper, not edge-discovery research
3. 1.7k GitHub stars != edge quality (popularity != profitability)

**Operator decision point:**  
Is `reclaim_session` a:
- **Level provenance tag** (extends existing `reclaim_swing`) → lower risk, may be worth exploring
- **New setup family** (session-time-gated entries) → repeats prior failure, reject

If Claude in browser framed it as latter, Codex correction is valuable.

---

### D2 — GMADL Introduction May Be Premature

**Deliverable:** `bieganowski_slepaczuk_2026.md` (line 174-200) + Finding F004

**Codex position:**  
Introduce GMADL as offline ranking metric for microstructure candidates (line 193-200).

**My (auditor) concern:**  
btc-bot historically resisted new metrics (prior `min_stop_relief_only` rejected). Adding GMADL introduces:
- Another metric to track
- Hyperparameters (a, b in formula)
- Metric-shopping risk (try PF, try IR, try GMADL until pass)

**Disagreement with implicit Claude brief assumption:**  
If Claude brief assumed GMADL is useful "because paper uses it," that's authority appeal. Codex should have pushed back harder: "Only introduce GMADL if PF/expectancy/max_dd proven insufficient." (Codex did caveat this, line 199-200, but could be stronger.)

**Operator decision point:**  
Before approving GMADL, require diagnostic: "Show example where GMADL ranks candidate A > B, but PF ranks B > A, and GMADL is correct." If no such example exists, GMADL is redundant.

---

## UNDER-DEVELOPED ARGUMENTS (Where Codex Had Right Instinct But Didn't Elaborate)

### U1 — Data Availability Diagnostic Is Prerequisite, Not Nice-To-Have

**Deliverable:** `bieganowski_slepaczuk_2026.md` (line 245, Q1) + `microstructure_context_v1_blueprint.md` (line 132, Q2)

Codex correctly asks:
- Q1 (bieganowski): "Do we have reliable bid/ask quantity in `book_ticker` across historical replay?"
- Q2 (microstructure blueprint): "Does the historical source DB preserve bid/ask quantities or only prices?"

**Under-development:**  
These are framed as "open questions," but they're **blocking prerequisites**. If bid/ask qty coverage < 80%, entire `MicrostructureContext` is DOA.

**What Codex should have said (but didn't):**  
"Before approving `MicrostructureContext` blueprint, operator MUST run data availability diagnostic. If coverage < 80%, defer implementation until Tardis backfill complete."

**Operator action:**  
Treat F003/F011 findings as **go/no-go gate**, not advisory.

---

### U2 — `reclaim_session` Needs Explicit Falsification Criteria

**Deliverable:** `smc_libraries_mining.md` (line 251-253) + Finding F008

Codex flags session-sweep repetition risk (confidence 2/5), but doesn't prescribe falsification criteria.

**What Codex should have added:**  
"If operator approves `reclaim_session` exploration, require upfront falsification criteria:
- If session-level subset PF < 1.5 on 6m walk-forward → reject
- If session levels don't increase throughput vs non-session levels → reject
- If entry timing is later than existing `reclaim_swing` → reject"

**Operator action:**  
If greenlighting `reclaim_session`, define "what would make us stop" before starting.

---

## THINGS BOTH CODEX AND CLAUDE MISSED (Third-Party Perspective)

### M1 — Portfolio Expansion May Not Solve Throughput Bottleneck

**Context:**  
System-reminder states: *"Bieżący sprint: throughput bottleneck (1.5-1.7 trades/day target increase)."*

Both Codex deliverables and (presumably) Claude brief focus on **adding more setup candidates** (reclaim_session, reclaim_rejection, breaker, OTE).

**What both may have missed:**  
Throughput bottleneck could be:
1. **Setup scarcity** (not enough valid setups) → portfolio expansion helps ✅
2. **Governance veto rate** (setups exist but are rejected) → portfolio expansion doesn't help ❌
3. **Regime coverage gap** (no setups in certain regimes) → need regime expansion, not setup expansion ❌

**Pre-mortem:**  
We implement 5 new setup candidates. Throughput stays 1.5-1.7 trades/day. Why? Because governance was rejecting 60% of existing `reclaim_swing` signals due to regime mismatch, and new candidates hit same veto. Root cause was regime engine, not setup scarcity.

**Recommendation:**  
Before approving setup portfolio expansion, operator should answer:
- What % of `reclaim_swing` candidates are vetoed by governance/risk?
- If > 40%, is veto reason regime-related or setup-quality-related?
- If regime-related, MODELING-V1 (RegimeEngine V2) may be higher ROI than setup expansion

**Operator decision point:**  
Run diagnostic: `SELECT COUNT(*) FROM signal_candidates WHERE veto_reason IS NOT NULL GROUP BY veto_reason` (or equivalent). If regime veto dominates, setup expansion is wrong lever.

---

### M2 — Flash-Crash Overweighting Risk in Paper Not Adequately Flagged

**Deliverable:** `bieganowski_slepaczuk_2026.md` (line 38, 251)

Codex mentions flash-crash (line 38): *"Flash-crash profitability may overweight rare stress events and may not improve ordinary throughput."*

And Q7 (line 251): "Should flash-crash periods be included in optimization, held out as stress tests, or both?"

**What both Codex and Claude may have missed:**  
Paper's "primary novelty" (arXiv abstract) is flash-crash divergence between taker/maker strategies. This means **paper optimized for stress-event performance**, not ordinary-regime edge.

If btc-bot ports features optimized for flash-crash regime to steady-state 15m reclaim, we're importing the WRONG feature set.

**Recommendation:**  
Before implementing `MicrostructureContext`, operator should:
1. Check paper Section 07 (backtest): what % of taker profit came from flash-crash dates?
2. If > 30%, paper features are stress-regime specialists, not transferable to ordinary throughput
3. Require separate ordinary-regime vs flash-crash performance split in any btc-bot microstructure diagnostic

**Operator decision point:**  
Is goal to improve **average-day throughput** or **survive flash crashes**? If former, paper may be wrong source.

---

# Summary

**INSIGHTS (positive):** 3  
**DISAGREEMENTS (Codex vs Claude):** 2  
**UNDER-DEVELOPED (Codex correct but incomplete):** 2  
**MISSED (both Codex and Claude):** 2

**Key takeaway:**  
Codex deliverables are strongest on **boundary discipline** (ML offline, informational-only contracts, layer separation) and **institutional memory** (MFE accessibility, prior session failure). Weakest on **empirical validation** (no BTC data tests) and **root-cause diagnosis** (assumes setup scarcity without verifying).

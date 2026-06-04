# Findings Register — Codex Research Mining Deliverables

**Auditor:** Claude Code (Windsurf)  
**Date:** 2026-06-04  
**Scope:** 6 deliverables in `research_lab/`

---

## CRITICAL Findings

**None detected.**

---

## HIGH Severity Findings

### F001 — Formula Reconstruction From SHAP Image (Not Source Table)

**Deliverable:** `bieganowski_slepaczuk_2026.md`  
**Layer:** L2 Factual Verification  
**Severity:** HIGH  
**Confidence:** 4/5

**Description:**  
Codex reconstructed 10 microstructure feature formulas from SHAP summary image labels, not from an explicit formula table in the paper source. Formula #7 (`concentration_of_volume`, lines 154-160) is marked as "least certain reconstructed formula."

**Evidence:**  
Line 113: *"Important caveat: the paper source does not expose a clean table of all formulas. The following feature names are reconstructed from the BTC SHAP summary image..."*

**Risk:**  
If formula differs from authors' actual implementation, `MicrostructureContext` outputs will not be comparable to paper results.

**Recommendation:**  
Before implementing `MicrostructureContext`:
1. Operator downloads arXiv source package
2. Verifies SHAP image contains listed feature names
3. Cross-checks formulas against LaTeX in paper sections 04_methodology.tex / 05_models.tex
4. If formula #7 ambiguous, contacts authors or implements with "local interpretation" flag

---

### F003 — 1s/3s to 15m Transfer Assumption Weakly Justified

**Deliverable:** `bieganowski_slepaczuk_2026.md`  
**Layer:** L4 Logic & Science  
**Severity:** HIGH  
**Confidence:** 3/5

**Description:**  
Paper studies 1-second/3-second prediction horizon. btc-bot edge is 15-minute reclaim. Codex flags transfer gap (line 30), but then recommends attribution with confidence 4/5 (line 100). Logic gap: if features don't map to 15m, why is attribution confidence high?

**Evidence:**  
- Line 30: "Transfer from 'predict next 3 seconds' to 'classify a 15m setup context' is not automatic."
- Line 100: "Use paper features to improve offline attribution of trial-00095 trades. Confidence 4/5."

**Pre-mortem:**  
Implement `MicrostructureContext`. Six months later, discover bid/ask quantities unavailable in 90% of historical data. All context fields perpetually `None`. Implementation cost wasted.

**Recommendation:**  
Before implementing, run data availability diagnostic:
- Query 6 months `MarketSnapshot` parquet: % rows with `bid_qty`/`ask_qty` populated
- If < 80% coverage, defer or require Tardis backfill first

---

### F006 — No Actual Repo Mapping (Future Modules Only)

**Deliverable:** `smc_libraries_mining.md`  
**Layer:** L3 Repo Mapping  
**Severity:** HIGH  
**Confidence:** 4/5

**Description:**  
SMC candidate touchpoints reference `research_lab/level_scanner.py` and `RegimeContext`, neither of which exist yet. No integration path until `level_scanner` implemented.

**Evidence:**  
Line 49-54 lists future modules. Verified: `research_lab/level_scanner.py` does not exist in repo.

**Recommendation:**  
If operator approves SMC setup portfolio, `level_scanner` MUST be milestone #1. No `reclaim_*` candidate work until scanner foundation exists. This aligns with Codex recommendation (line 323-326).

---

### F008 — `reclaim_session` Risks Repeating Failed Session-Sweep Specialist

**Deliverable:** `smc_libraries_mining.md`  
**Layer:** L6 Consistency With Prior  
**Severity:** HIGH  
**Confidence:** 5/5

**Description:**  
`reclaim_session` candidate risks repeating already-invalidated session-sweep specialist. Codex acknowledges (line 251-253, confidence 2/5), but doesn't fully resolve distinction between "session level provenance" (allowed) vs "session time filter" (rejected).

**Evidence:**  
- Codex self-audit (line 5): "I may be too conservative about `reclaim_session`; if new implementation uses session levels as provenance rather than time filter, it may not repeat failed specialist."
- Prior decision: `SESSION_SWEEP_SPECIALIST_AUDIT_PACKAGE.md` exists (rejected)

**Critical distinction:**
- OLD (rejected): "only trade during Asia session" (time filter)
- NEW (proposed): "tag reclaim level as 'session high/low' for attribution" (provenance)

**Recommendation:**  
Before approving `reclaim_session`, operator must confirm:
1. Is this a NEW setup, or level-provenance metadata for existing `reclaim_swing`?
2. If NEW, require explicit falsification criteria (e.g., "PF < 1.5 on 6m WF → reject") to avoid past failure repetition

---

### F010 — Insertion Point Adds Production Field, Conflicts With V1 Contract

**Deliverable:** `microstructure_context_v1_blueprint.md`  
**Layer:** L3 Repo Mapping  
**Severity:** HIGH  
**Confidence:** 4/5

**Description:**  
Blueprint line 74-78 recommends adding `Features.microstructure_context` field to production dataclass. This conflicts with V1 "informational-only" contract (line 80-96), which should be research_lab-only.

**Evidence:**  
- Line 78: "Add it as `Features.microstructure_context: MicrostructureContext | None`"
- Line 90-96: "V1 forbidden behavior: no confluence weight, no governance veto, ..."

**Problem:**  
Adding field to `core/models.py` `Features` dataclass IS a production change, even if downstream ignores it.

**Recommendation:**  
Revise blueprint:
- V1: Compute `MicrostructureContext` ONLY in `research_lab/` replay scripts
- V1: Store in separate parquet or JSON sidecar, NOT in `Features` dataclass
- V2: After promotion gate passes (line 102-114), THEN add to `Features`

---

### F014 — `level_id` Hash Function Underspecified

**Deliverable:** `level_scanner_spec.md`  
**Layer:** L4 Logic & Science  
**Severity:** HIGH  
**Confidence:** 4/5

**Description:**  
Output schema (line 23) specifies `level_id` as "deterministic hash of source, category, symbol, timeframe, level price, formed_at" but does not specify hash function (MD5? SHA256? Custom?).

**Risk:**  
If hash is not reproducible across runs, joins/deduplication break.

**Recommendation:**  
Add to spec: "Use `SHA256(f'{source}|{category}|{symbol}|{timeframe}|{price:.8f}|{formed_at.isoformat()}')[:16]` for deterministic 16-char hex ID."

---

## MEDIUM Severity Findings

### F002 — Integration Point Mapping Conflict

**Deliverable:** `bieganowski_slepaczuk_2026.md` | **Layer:** L3 | **Severity:** MEDIUM | **Confidence:** 4/5

Line 239-241 states "after line 319, before quality defaults" but line 319 IS quality assignment. Actual flow: 308-317 sweep/reclaim, 319 quality, 320-356 flow reads, 358-393 return. Revise: "Build context after line 356 (after all feature computation), before line 358 (return)."

---

### F004 — GMADL Metric Addition Risks Metric-Shopping

**Deliverable:** `bieganowski_slepaczuk_2026.md` | **Layer:** L6 | **Severity:** MEDIUM | **Confidence:** 3/5

Introducing GMADL (line 174-200) adds metric/hyperparameter overhead. btc-bot historically rejected non-profitability metrics. Only introduce if PF/expectancy/max_dd proven insufficient.

---

### F005 — Timezone Critique Correct But Not Exhaustively Verified

**Deliverable:** `smc_libraries_mining.md` | **Layer:** L2 | **Severity:** MEDIUM | **Confidence:** 3/5

Codex critiques `Etc/GMT` sign inversion (line 35-37). I verified source code, but did NOT test DST edge cases. If btc-bot reimplements, add unit test: "Sydney session on UTC data = 21:00-06:00 UTC, not inverted."

---

### F009 — Dataclass Has 14 Fields, Not 10

**Deliverable:** `microstructure_context_v1_blueprint.md` | **Layer:** L2 | **Severity:** MEDIUM | **Confidence:** 3/5

Schema shows 10 metrics + 4 metadata = 14 total fields. Brief may have meant "10 total." Confirm with operator if metadata overhead acceptable.

---

### F011 — Graceful Fallback Untestable Without Data Coverage

**Deliverable:** `microstructure_context_v1_blueprint.md` | **Layer:** L4 | **Severity:** MEDIUM | **Confidence:** 3/5

Fallback design (line 45-63) is solid, but if bid/ask qty coverage < 80%, entire context may be perpetually unavailable. Same recommendation as F003: run diagnostic first.

---

### F012 — Six Open Questions Should Be Answered Before Approval

**Deliverable:** `microstructure_context_v1_blueprint.md` | **Layer:** L6 | **Severity:** MEDIUM | **Confidence:** 4/5

Blueprint ends with 6 open questions (line 127-135). Questions 1-5 are design decisions affecting implementation scope, not edge cases. Operator should answer before blueprint approval.

---

### F015 — Liquidation Category #6 Placeholder Behavior Underspecified

**Deliverable:** `level_scanner_spec.md` | **Layer:** L4 | **Severity:** MEDIUM | **Confidence:** 3/5

Category 6 (liquidation clusters) is placeholder until Tardis backfill. Spec should clarify: if Tardis unavailable, `scan_levels()` returns empty DataFrame for `BID_LIQ`/`ASK_LIQ` categories (no error raised).

---

### F017 — Confidence Ratings Are Methodological, Not Empirical

**Deliverable:** `codex_self_audit.md` | **Layer:** L4 | **Severity:** MEDIUM | **Confidence:** 4/5

Codex honestly discloses (line 8): "I did not run empirical comparisons on BTC data. All setup candidate confidence ratings are methodological, not measured expectancy." Treat ratings as "priority ranking for which to test first," not "probability of success."

---

## LOW Severity Findings

### F013 — Spec References Future Modules (Expected)

**Deliverable:** `level_scanner_spec.md` | **Layer:** L3 | **Severity:** LOW | **Confidence:** 3/5

Line 173-181 references `reclaim_rejection`, `reclaim_breaker`, etc. — none exist yet. Expected for spec work. Confirms `level_scanner` is milestone #1 dependency.

---

## INSIGHTS (Positive Findings)

### F007 — Codex Correctly Applies MFE Accessibility Prior Knowledge

**Deliverable:** `smc_libraries_mining.md` | **Layer:** L4 | **Severity:** INSIGHT+ | **Confidence:** 5/5

Line 126-127: *"btc-bot's recent `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` found that post-sweep confirmations usually arrive after favorable excursion is consumed. Breaker, mitigation, and OTE are delayed-confirmation concepts, so they begin under suspicion."*

**This is exactly correct.** Codex applies institutional memory properly. Confidence ratings well-calibrated: `reclaim_rejection` 3/5 (earliest-knowable), `reclaim_mitigation` 1/5 (delayed).

**Operator attention:** This demonstrates Codex is integrating prior research, not cargo-culting SMC literature.

---

### F016 — Codex Disagreement With Claude Is Valuable Independent Perspective

**Deliverable:** `codex_self_audit.md` | **Layer:** L4-6 | **Severity:** INSIGHT+ | **Confidence:** 3/5

Line 22-24: Codex disagrees with Claude in browser ranking of joshyattridge as "gold." Codex correctly cites prior session-sweep specialist failure. **This is exactly what multi-agent workflow is designed for:** independent perspectives catching over-optimism.

**Operator attention:** Weigh this disagreement. If Claude ranked joshyattridge higher and Codex cites prior failure, Codex likely correct.

---

# Finding Count Summary

- **CRITICAL:** 0
- **HIGH:** 6 (F001, F003, F006, F008, F010, F014)
- **MEDIUM:** 8 (F002, F004, F005, F009, F011, F012, F015, F017)
- **LOW:** 1 (F013)
- **INSIGHT+:** 2 (F007, F016)

**Total findings:** 17  
**Blocking findings (CRITICAL + HIGH with confidence ≥4/5):** 5 (F001, F006, F008, F010, F014)


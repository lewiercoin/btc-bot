# Per-Deliverable Audit — Layers 2-7

**Auditor:** Claude Code (Windsurf instance)  
**Date:** 2026-06-04  
**Framework:** Adversarial brief sections 5-9  
**Scope:** 6 deliverables from Codex research mining session

---

## DELIVERABLE #1: `bieganowski_slepaczuk_2026.md`

### Layer 2: Factual Verification

**Verified facts (confidence 5/5):**
- arXiv paper exists: https://arxiv.org/abs/2602.00776 ✅
- Authors: Bartosz Bieganowski, Robert Ślepaczuk ✅
- Date range: January 1, 2022 to October 12, 2025 ✅
- Assets: BTC, LTC, ETC, ENJ, ROSE ✅
- CatBoost + GMADL + SHAP methodology ✅

**Finding F001 — HIGH severity, 4/5 confidence:**  
**Formula reconstruction from SHAP image labels, not from source table**

Codex states (line 113): *"Important caveat: the paper source does not expose a clean table of all formulas. The following feature names are reconstructed from the BTC SHAP summary image in the source package and formulas are standard interpretations consistent with the paper text."*

**Evidence:** I downloaded arXiv abstract page (verified paper exists), but did NOT download full source package to verify SHAP image. Codex claim is plausible (papers often omit formula tables in favor of figures), but **operator must approve reconstructed formulas before implementation**.

**Risk:** If formula #7 `concentration_of_volume` (line 156-160) differs from authors' actual implementation, btc-bot microstructure context will produce non-comparable outputs.

**Recommendation:** Before implementing `MicrostructureContext`, operator should:
1. Download arXiv source package
2. Verify SHAP summary image contains feature names Codex listed
3. Compare Codex formulas to any LaTeX formula blocks in paper sections 04_methodology.tex / 05_models.tex
4. If formula #7 is ambiguous, either contact authors or implement with explicit "local interpretation" flag

---

### Layer 3: Repo Mapping Verification

**Verified mappings (confidence 5/5):**
- `core/feature_engine.py:281` — `compute()` start ✅ (actual: line 281)
- `core/feature_engine.py:308-317` — sweep/reclaim detection ✅ (actual: lines 308-317)
- `core/feature_engine.py:319` — quality defaults ✅ (actual: line 319)
- `core/feature_engine.py:358-393` — return `Features` ✅ (actual: lines 358-393)

**Finding F002 — MEDIUM severity, 4/5 confidence:**  
**Missing explicit insertion point for MicrostructureContext in future integration**

Codex states (line 239-241): "Integration point: `core/feature_engine.py:319` after sweep/reclaim detection and before quality defaults/flow calculations."

**Issue:** Line 319 is `quality = dict(snapshot.quality)`, which occurs AFTER sweep/reclaim (line 308-317). The description conflicts with "before quality defaults." The actual flow is:
1. Lines 308-317: sweep/reclaim
2. Line 319: quality assignment
3. Lines 320-356: CVD/TFI/force-order reads
4. Lines 358-393: return

**Recommendation:** Revise mapping to state: "Build `MicrostructureContext` after line 356 (after all existing feature computation), before line 358 (return construction). Add as optional field in `Features` dataclass only after operator approval."

---

### Layer 4: Logic & Science Audit

**Finding F003 — HIGH severity, 3/5 confidence:**  
**Ultra-short horizon (1s/3s) to 15m reclaim transfer assumption is weakly justified**

Codex correctly flags (line 30): *"Strongest critique: the paper studies ultra-short-horizon 1s/3s prediction, while btc-bot's current edge is a 15m liquidity sweep/reclaim process. Transfer from 'predict next 3 seconds' to 'classify a 15m setup context' is not automatic."*

**But then recommends (line 99):**
- "Build `MicrostructureContext` as logged, informational telemetry only. Confidence 3/5."
- "Use paper features to improve offline attribution of trial-00095 trades and near-misses. Confidence 4/5."

**Logic gap:** If 1s/3s features don't map to 15m edge, why is attribution confidence 4/5? Attribution assumes relevance.

**Steelman (Layer 5):** Microstructure may explain *execution quality* (spread/slippage degradation) even if it doesn't predict 15m direction. That's valuable for risk context, not alpha.

**Attack (Layer 5):** If spread/imbalance are noise at 15m scale, this becomes expensive telemetry with no actionable value. Before implementing, need hypothesis: "spread > X bps predicts trial-00095 stop-out" or similar.

**Pre-mortem (Layer 5):** In 3 months, operator discovers microstructure context is always `unavailable` because historical `book_ticker` lacks bid/ask quantities, and Tardis backfill is incomplete. Implementation cost: wasted. Root cause: assumed data availability without verifying.

**Recommendation:** Before implementing `MicrostructureContext`, run data availability diagnostic:
- Query 6 months of `MarketSnapshot` parquet: how many rows have `bid_qty` / `ask_qty`?
- If < 95% coverage, downgrade priority or require Tardis backfill first.

---

### Layer 5: Adversarial Thinking

**Steelman:** Paper provides robust, peer-reviewed (preprint, but rigorous) feature vocabulary. Even if 1s/3s edge doesn't transfer, spread/imbalance/flow are standard microstructure observables. Logging them as context can't hurt and may help future research.

**Attack:** "Can't hurt" is false. It CAN hurt:
1. Implementation cost (10-16h Codex + 3-5h audit)
2. Ongoing storage cost (10 fields × parquet × 15m × multi-year)
3. Cognitive load (another telemetry layer to interpret)
4. Opportunity cost (what else could 20h buy?)

If we're logging things "just in case," we're not prioritizing ruthlessly.

**Pre-mortem:** We implement it. Six months later, no one looks at it. It's inert telemetry. Lesson: don't implement speculative infrastructure in a throughput bottleneck sprint.

**Verdict:** Codex recommendation is defensible IF operator has explicit hypothesis (e.g., "spread predicts stop-out"). Otherwise, defer until trial-00095 attribution need is proven, not assumed.

---

### Layer 6: Consistency With Prior Decisions

**Finding F004 — MEDIUM severity, 3/5 confidence:**  
**GMADL as research metric conflicts with "no new metrics without promotion gate" policy**

Codex recommends (line 193-200): *"Use GMADL in btc-bot research only: as an offline ranking/diagnostic metric for candidate microstructure models; never as live `SignalCandidate` logic; always compared with PF/expectancy/trade accessibility, not as a standalone approval metric."*

**Issue:** btc-bot historically rejected new metrics that aren't directly tied to profitability (e.g., `min_stop_relief_only` was rejected). Introducing GMADL creates:
- Another metric to track
- Another hyperparameter (a, b in formula line 177-180)
- Risk of metric-shopping (try PF, try IR, try GMADL until something "passes")

**Recommendation:** Only introduce GMADL if:
1. Existing metrics (PF, max_dd, expectancy) are proven insufficient for microstructure candidate ranking
2. GMADL demonstrates independent discriminative power in offline diagnostic
3. Operator explicitly approves metric addition

Otherwise, stick to PF/expectancy/max_dd.

---

### Verdict for Deliverable #1

**APPROVE WITH MAJOR REVISIONS**

**Required changes:**
1. Add explicit caveat to all 10 formulas: "Reconstructed from SHAP image; operator must verify before implementation."
2. Revise integration point mapping (line 239-241) to correct location after line 356.
3. Add data availability prerequisite: "Check bid/ask qty coverage before implementing."
4. Downgrade GMADL recommendation to "optional, only if PF/expectancy insufficient."

**Rationale:** Paper analysis is thorough and boundary-aware (ML offline, informational-only V1). Formula reconstruction is honest about uncertainty. Mapping is precise. Logic is mostly sound but over-optimistic about attribution value without data verification.

---

## DELIVERABLE #2: `smc_libraries_mining.md`

### Layer 2: Factual Verification

**Verified facts (confidence 5/5):**
- joshyattridge repo exists: https://github.com/joshyattridge/smart-money-concepts ✅
- MIT license ✅
- `sessions()` function exists (verified in `/tmp/joshyattridge_smc/smartmoneyconcepts/smc.py`) ✅
- `liquidity()` function exists ✅
- PyIndicators repo exists: https://github.com/coding-kitties/PyIndicators ✅

**Finding F005 — MEDIUM severity, 3/5 confidence:**  
**joshyattridge timezone handling critique is correct but not exhaustively verified**

Codex states (line 35-37): *"`sessions()` uses fixed UTC-style clock windows and does not model exchange holidays, weekends, DST transitions, or regional market calendar reality. Timezone conversion uses `Etc/GMT` string replacement. `Etc/GMT` signs are counterintuitive and this can easily invert offsets if used carelessly."*

I verified `sessions()` source (lines extracted from clone). The `Etc/GMT` replacement logic is visible (line 66-67 of extracted function). Codex critique is plausible, but I did NOT test DST edge cases or sign inversion scenarios.

**Recommendation:** If btc-bot reimplements sessions, add unit test: "Sydney session on UTC data should label candles 21:00-06:00 UTC, not inverted."

---

### Layer 3: Repo Mapping Verification

**Finding F006 — HIGH severity, 4/5 confidence:**  
**No mapping to actual btc-bot modules for SMC candidates**

Codex states (line 49-54): *"Potential btc-bot touchpoints in a future implementation: `research_lab/level_scanner.py` or equivalent offline module for sessions, PDH/PDL/PWH/PWL, EQH/EQL. `core/regime_engine.py` or future `RegimeContext` only after DATA-INTEGRITY-V1 and MODELING-V1 scope."*

**Issue:** These files don't exist yet:
- `research_lab/level_scanner.py` — future placeholder
- `RegimeContext` — mentioned in `microstructure_context_v1_blueprint.md` but not defined in `core/models.py`

**This is not necessarily a flaw** (Codex is spec'ing future work), but it means **no integration path exists until `level_scanner` is implemented first**.

**Recommendation:** If operator approves SMC setup portfolio, `level_scanner` MUST be milestone #1 before any `reclaim_*` candidate work. Codex already recommends this (line 323-326), so this is a **consistency check PASS**.

---

### Layer 4: Logic & Science Audit

**Finding F007 — CRITICAL insight (positive), 5/5 confidence:**  
**Codex correctly identifies MFE accessibility as the primary SMC risk**

Line 126-127: *"btc-bot's recent `MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1` found that post-sweep confirmations usually arrive after favorable excursion is consumed. Breaker, mitigation, and OTE are delayed-confirmation concepts, so they begin under suspicion."*

This is **exactly correct** and aligns with prior btc-bot research. Codex is applying institutional memory properly.

**Recommendation confidence ratings are well-calibrated:**
- `reclaim_rejection`: 3/5 (earliest-knowable, wick-based)
- `reclaim_mitigation`: 1/5 (delayed entry, already problematic)
- `ote_pullback`: 2/5 (separate strategy family, delayed)

**Verdict:** Logic is sound. No finding needed; this is a **strength** of the deliverable.

---

### Layer 5: Adversarial Thinking

**Steelman:** joshyattridge `sessions()` + `liquidity().Swept` provide battle-tested, 1.7k-star reference implementations. Even if btc-bot reimplements, having cross-validation targets reduces implementation risk.

**Attack:** 1.7k stars != correctness. joshyattridge is stagnated (last update Mar 2025 per Codex line 5). If it has bugs, using it as validation oracle propagates bugs into btc-bot.

**Pre-mortem:** We implement `reclaim_session`, cross-validate against joshyattridge, get 95% match. Ship it. Three months later, discover joshyattridge had an off-by-one error in session boundary logic. Our "validated" implementation inherited the bug.

**Mitigation:** Cross-validate against joshyattridge AND independent hand-calculation on 10-day sample. If they disagree, investigate before declaring either correct.

---

### Layer 6: Consistency With Prior Decisions

**Finding F008 — HIGH severity, 5/5 confidence:**  
**`reclaim_session` risks repeating invalidated `session-sweep specialist`**

Codex acknowledges (line 251-253): *"`reclaim_session` risks: Repeating already invalidated session-sweep specialist. Confidence 2/5 because prior session-sweep specialist failed."*

And self-critique (line 5 of `codex_self_audit.md`): *"I may be too conservative about `reclaim_session`; if the new implementation uses session levels as provenance rather than a time filter, it may not repeat the failed session-sweep specialist."*

**Prior decision context (from git log in system-reminder):**
- `SESSION_SWEEP_SPECIALIST_AUDIT_PACKAGE.md` exists in repo (referenced by Codex line 7)
- That specialist was REJECTED

**Logic question:** If session-sweep specialist failed, why allow `reclaim_session` back?

**Codex answer (line 241-248):** Session extreme as **level provenance**, not as **time filter**.

**Critical distinction:**
- OLD (rejected): "only trade during Asia session" (time filter)
- NEW (proposed): "trade reclaim against any level, but tag level as 'session high/low' for attribution" (provenance)

**Verdict:** This distinction is valid IF:
1. `reclaim_session` is NOT a separate signal family, just a level-tagging extension of existing `reclaim_swing`
2. No session-time-based entry gating is added
3. Research diagnostic explicitly compares `reclaim_swing` (no session tags) vs `reclaim_swing` (with session-level subset) to prove session levels add value

**Recommendation:** Before approving `reclaim_session`, operator must confirm: "Is this a NEW setup, or is this level-provenance metadata for existing reclaim logic?" If NEW setup, require explicit falsification criteria to avoid repeating past failure.

---

### Verdict for Deliverable #2

**APPROVE WITH MINOR REVISIONS**

**Required changes:**
1. Clarify `reclaim_session` scope: level provenance vs new setup family.
2. Add cross-validation mitigation: "Validate against joshyattridge AND hand-calculation, not just library."
3. Add prerequisite: "`level_scanner` must be implemented before any `reclaim_*` candidate."

**Rationale:** SMC library mining is thorough, correctly identifies MFE accessibility risk, and applies institutional memory (prior session failure). Timezone critique is sound. Candidate confidence ratings are defensible. Main risk is session-sweep repetition, which Codex flags but doesn't fully resolve.

---

## DELIVERABLE #3: `microstructure_context_v1_blueprint.md`

### Layer 2: Factual Verification

**Verified facts (confidence 5/5):**
- Integration point lines (68-72) match actual `core/feature_engine.py` ✅
- `Features` dataclass return (line 358-393 in actual code) ✅

**Finding F009 — MEDIUM severity, 3/5 confidence:**  
**Dataclass schema includes metadata fields not in "10 features" brief**

Blueprint line 8-26 shows dataclass with:
- `timestamp`, `schema_version`, `source_window_seconds`, `quality` (metadata, 4 fields)
- 10 metric fields

**Total: 14 fields, not 10.**

Codex states (line 28): *"The brief asks for 10 fields; the signature includes metadata plus the 10 metric fields below."*

**Issue:** This is honest disclosure, but **operator brief may have meant "10 total fields" not "10 metrics + metadata"**. Ambiguity should be resolved before implementation.

**Recommendation:** Confirm with operator: is metadata overhead acceptable, or should it be reduced (e.g., `quality` as single enum instead of `dict[str, FeatureQuality]`)?

---

### Layer 3: Repo Mapping Verification

**Finding F010 — HIGH severity, 4/5 confidence:**  
**Insertion point (line 76) conflicts with V1 informational-only contract**

Blueprint states (line 74-78): *"Recommended future insertion point: Build `MicrostructureContext` after line 319, using existing snapshot bid/ask/book/aggTrades, before return construction. Add it either as `Features.microstructure_context: MicrostructureContext | None` or as an audited `features_json["microstructure_context"]` extension only after operator approval."*

**Contradiction:**
- Line 78: "Add it as `Features.microstructure_context`" → this means **adding a field to production `Features` dataclass**
- Line 80-96: "V1 forbidden behavior: no confluence score weight; no governance veto; ..." → informational-only contract

**Problem:** Adding a field to `Features` dataclass IS a production code change. Even if downstream modules ignore it, it's NOT "research_lab only."

**Correct V1 implementation:**
- Compute `MicrostructureContext` in `research_lab/` offline replay scripts ONLY
- Do NOT add field to `core/models.py` `Features` dataclass
- Store in separate parquet table or as JSON sidecar

**Recommendation:** Revise blueprint line 74-78: "V1 computes `MicrostructureContext` ONLY in `research_lab/` replay. Do NOT add to `Features` dataclass. After V2 promotion gate passes, then add as optional field."

---

### Layer 4: Logic & Science Audit

**Finding F011 — MEDIUM severity, 3/5 confidence:**  
**Graceful fallback design (line 45-63) is solid, but untestable without data coverage diagnostic**

Blueprint correctly specifies:
- Missing bid/ask price → mark spread/VWAP unavailable ✅
- No trades in window → volume=0, VWAP unavailable ✅
- Gaps in aggTrades → quality degraded ✅

**Issue:** Without knowing historical data coverage, we can't assess whether "graceful fallback" means "works 95% of the time" or "unavailable 95% of the time."

**Recommendation (same as F003):** Run data availability diagnostic before implementing. If `bid_qty`/`ask_qty` coverage < 80%, entire `MicrostructureContext` may be perpetually unavailable.

---

### Layer 5: Adversarial Thinking

**Steelman:** V1 informational-only contract (line 80-96) is rigorous. 8-step promotion gate (line 102-114) is institutional-grade. This is well-designed defensive architecture.

**Attack:** If V1 is truly informational-only and won't be used for 6+ months, why implement it now? In a throughput bottleneck sprint, this is speculative infrastructure.

**Pre-mortem:** We implement `MicrostructureContext`. It sits unused for 9 months. Meanwhile, `level_scanner` + `reclaim_rejection` could have shipped 3 months earlier and added 0.3 trades/day. Opportunity cost: measurable.

**Verdict:** If operator priority is throughput, `MicrostructureContext` should be DEFERRED until after `level_scanner` + one candidate setup ships and proves incremental value.

---

### Layer 6: Consistency With Prior Decisions

**Finding F012 — MEDIUM severity, 4/5 confidence:**  
**Open questions (line 127-135) should be ANSWERED before blueprint approval, not left open**

Blueprint ends with 6 open questions:
1. 60s vs 10s/3s windows?
2. Does historical DB have bid/ask quantities?
3. Should `MicrostructureContext` be in `core/models.py` or research-only?
4. Unavailable metrics: `None` vs sentinels?
5. Use case: trial-00095 attribution vs near-miss reconstruction?
6. Flash-crash held-out?

**Problem:** These aren't edge cases. These are **design decisions that affect implementation scope**. A blueprint with 6 unanswered questions is not ready for handoff.

**Recommendation:** Operator should answer questions 1-5 before approving blueprint. Question 6 (flash-crash) can remain open (research decision, not architecture).

---

### Verdict for Deliverable #3

**REVISE BEFORE APPROVAL**

**Required changes:**
1. Remove `Features.microstructure_context` field addition from V1 scope (conflicts with informational-only contract).
2. Answer 5 out of 6 open questions (or explicitly defer if not blocking).
3. Add data availability prerequisite (same as F003).

**Rationale:** Blueprint is architecturally sound (promotion gate, graceful fallback, determinism), but scope creep (production dataclass modification) conflicts with V1 contract, and open questions make it unready for direct handoff.

---

## DELIVERABLE #4: `level_scanner_spec.md`

### Layer 2: Factual Verification

**Verified facts (confidence 5/5):**
- `core/feature_engine.py` equal-level logic exists (line 90 references it) ✅
- joshyattridge `sessions()`, `previous_high_low()`, `liquidity().Swept` functions exist (verified in prior fact-check) ✅

**No factual errors detected.**

---

### Layer 3: Repo Mapping Verification

**Finding F013 — LOW severity, 3/5 confidence:**  
**Spec references future modules that don't exist**

Line 173-181: *"`level_scanner` is the level factory for setup portfolio research: `reclaim_swing`, `reclaim_session`, `reclaim_rejection`, `reclaim_breaker`, `ote_pullback`, future liquidation setup."*

**None of these setup modules exist yet** except `reclaim_swing` (implicitly in `signal_engine.py`).

**This is expected** (spec is for future work), but confirms: **`level_scanner` is milestone #1 dependency for ALL subsequent setup work.**

**Recommendation:** If operator approves setup portfolio direction, `level_scanner` must be prioritized above any individual candidate setup.

---

### Layer 4: Logic & Science Audit

**Finding F014 — HIGH severity, 4/5 confidence:**  
**Output schema (line 20-41) is rigorous, but `level_id` deterministic hash is underspecified**

Schema includes (line 23): *"`level_id`: deterministic hash of source, category, symbol, timeframe, level price, formed_at"*

**Issue:** Hash function not specified. Is it:
- MD5 of concatenated string?
- SHA256?
- Custom reproducible hash?

**Why it matters:** If two runs of `scan_levels()` produce different `level_id` for same level, joins/deduplication break.

**Recommendation:** Add to spec: "Use SHA256(f'{source}|{category}|{symbol}|{timeframe}|{price:.8f}|{formed_at.isoformat()}')[:16] for deterministic 16-char hex ID."

---

### Layer 4 (continued): Logic & Science Audit

**Finding F015 — MEDIUM severity, 3/5 confidence:**  
**Six categories (line 43-148) mix static, dynamic, and placeholder types**

Categories:
1. Session Extremes — dynamic, per-session instance ✅
2. PDH/PDL/PWH/PWL — static (one per day/week), deterministic ✅
3. EQH/EQL Clusters — dynamic, confirmation-dependent ✅
4. Anchored VWAP — dynamic, one per HH/LL ✅
5. Round Numbers — static, trivial ✅
6. Liquidation Clusters — **placeholder** until Tardis backfill ❌

**Issue:** Mixing placeholder category #6 with implemented categories #1-5 creates ambiguity. If `scan_levels()` is called before Tardis backfill, does it:
- Return empty rows for category=`BID_LIQ`/`ASK_LIQ`?
- Raise error?
- Skip category silently?

**Recommendation:** Add to spec: "Category 6 (liquidation clusters) returns empty DataFrame if Tardis data unavailable. No error raised. Caller checks row count."

---

### Layer 5: Adversarial Thinking

**Steelman:** `level_scanner` is clean factory pattern: **facts-only, no decisions**. Layer separation is explicit (line 182-188). This is textbook setup portfolio architecture.

**Attack:** Factory pattern assumes **all setups need same level types**. What if `reclaim_rejection` needs wick zones (high/low + top/bottom), but `ote_pullback` needs impulse-leg start/end (different schema)? Schema may not be universal.

**Pre-mortem:** We implement `level_scanner` with 6 categories. Implement `reclaim_rejection`. Works great. Start `ote_pullback`. Discover OTE needs "impulse_start_bar" and "impulse_end_bar" fields that don't exist in schema. Either:
1. Add fields (breaks schema for non-OTE categories)
2. Add 7th category (OTE-specific) → factory becomes category-per-setup, defeats purpose

**Mitigation:** Schema line 29-30 already has `top`/`bottom` nullable for zones. Add `metadata_json` (line 41) as escape hatch for setup-specific fields. Document: "Use `metadata_json` for setup-specific extensions; do not add schema columns per-setup."

**Verdict:** Spec is defensible. Attack is theoretical; not blocking.

---

### Layer 6: Consistency With Prior Decisions

**No findings.** Spec correctly references existing equal-level logic and respects layer separation.

---

### Verdict for Deliverable #4

**APPROVE WITH MINOR REVISIONS**

**Required changes:**
1. Specify `level_id` hash function (SHA256 with format string).
2. Clarify liquidation category #6 behavior when Tardis unavailable.
3. Add note: "Use `metadata_json` for setup-specific fields; avoid per-setup schema columns."

**Rationale:** Best deliverable of the 6. Clean factory pattern, rigorous schema, explicit validation plan (line 149-170), layer separation enforced. Minor underspecification (hash function, placeholder behavior) is easily fixed.

---

## DELIVERABLE #5: `nautilus_tardis_pattern_notes.md`

### Layer 2: Factual Verification

**Verified facts (confidence 4/5):**
- Nautilus Tardis docs exist: https://nautilustrader.io/docs/latest/integrations/tardis/ (not fetched during audit, assumed from Codex claim)
- LGPL licensing issue flagged (line 48-50) ✅

**No factual errors, but minimal verification depth** (stub deliverable, as intended).

---

### Layer 3-6: Abbreviated Audit

**This is explicitly a stub** (line 3-5): *"This is a time-boxed stub for later exploration. Full Nautilus source download was intentionally not pursued because the core deliverables are Materials #1-#3 and Nautilus is optional."*

**Verdict:** No findings. Codex correctly scoped this as optional and time-boxed it.

---

### Verdict for Deliverable #5

**APPROVE AS-IS**

**Rationale:** Stub deliverable. Explicitly optional. Bounded scope. No implementation claims. Provides value as future reference without over-investment.

---

## DELIVERABLE #6: `codex_self_audit.md`

### Layer 2-6: Meta-Audit of Self-Audit

**Self-audit strengths:**
- **5 reasons for error** (line 4-9): honest, specific, falsifiable ✅
- **Risk register** (line 26-39): concrete probability/impact/mitigation ✅
- **Effort estimates** (line 51-76): realistic ranges (10-16h, not "2h" wishful thinking) ✅
- **Disagreement with Claude in browser** (line 22-24): independent perspective ✅

**Finding F016 — LOW severity, 3/5 confidence (positive finding):**  
**Codex disagreement with Claude brief is VALUABLE, not a flaw**

Line 22-24: *"Claude's ranking put joshyattridge/smart-money-concepts as high-value mainly because `smc.sessions()` is 'gold' for `reclaim_session`. I disagree with the strength of that framing. The existing btc-bot session-sweep specialist already failed..."*

**This is exactly what multi-agent workflow is designed for:** independent perspectives catching over-optimism.

**Recommendation:** Operator should weigh this disagreement. If Claude in browser ranked joshyattridge higher than Codex does, and Codex correctly cites prior failure, Codex is likely correct.

---

**Finding F017 — MEDIUM severity, 4/5 confidence:**  
**Codex confidence ratings are methodological, not empirical (line 8)**

Self-audit line 8: *"I did not run empirical comparisons on BTC data. All setup candidate confidence ratings are methodological, not measured expectancy."*

**This is honest disclosure.** But it means:
- `reclaim_rejection: 3/5` is based on "looks earliest-knowable" not "tested on 6m BTC, PF=1.9"
- Confidence ratings are **hypotheses**, not evidence

**Recommendation:** Treat all setup confidence ratings as "priority ranking for which to test first," not "probability of success."

---

### Verdict for Deliverable #6

**APPROVE AS-IS**

**Rationale:** Self-audit is rigorous, honest about limitations, and demonstrates independent thinking (disagreement with Claude). No revisions needed.

---

# SUMMARY OF ALL FINDINGS

| ID | Deliverable | Layer | Severity | Confidence | Description |
|---|---|---|---|---|---|
| F001 | #1 bieganowski | L2 | HIGH | 4/5 | Formula reconstruction from SHAP image, not source table — operator must verify |
| F002 | #1 bieganowski | L3 | MEDIUM | 4/5 | Integration point mapping conflict (line 319 vs "before quality defaults") |
| F003 | #1 bieganowski | L4 | HIGH | 3/5 | 1s/3s to 15m transfer assumption weakly justified; requires data availability check |
| F004 | #1 bieganowski | L6 | MEDIUM | 3/5 | GMADL metric addition risks metric-shopping without clear necessity |
| F005 | #2 smc_libraries | L2 | MEDIUM | 3/5 | Timezone critique correct but not exhaustively verified |
| F006 | #2 smc_libraries | L3 | HIGH | 4/5 | No actual btc-bot mapping (future modules); `level_scanner` is prerequisite |
| F007 | #2 smc_libraries | L4 | INSIGHT+ | 5/5 | Codex correctly applies MFE accessibility prior knowledge (positive finding) |
| F008 | #2 smc_libraries | L6 | HIGH | 5/5 | `reclaim_session` risks repeating failed session-sweep specialist |
| F009 | #3 microstructure | L2 | MEDIUM | 3/5 | Dataclass has 14 fields (10 metrics + 4 metadata), not 10 total |
| F010 | #3 microstructure | L3 | HIGH | 4/5 | Insertion point adds production `Features` field, conflicts with V1 informational-only |
| F011 | #3 microstructure | L4 | MEDIUM | 3/5 | Graceful fallback untestable without data coverage diagnostic |
| F012 | #3 microstructure | L6 | MEDIUM | 4/5 | 6 open questions should be answered before blueprint approval |
| F013 | #4 level_scanner | L3 | LOW | 3/5 | References future setup modules (expected for spec) |
| F014 | #4 level_scanner | L4 | HIGH | 4/5 | `level_id` hash function underspecified |
| F015 | #4 level_scanner | L4 | MEDIUM | 3/5 | Liquidation category #6 placeholder behavior underspecified |
| F016 | #6 self_audit | L4 | INSIGHT+ | 3/5 | Codex disagreement with Claude is valuable independent perspective |
| F017 | #6 self_audit | L4 | MEDIUM | 4/5 | Confidence ratings are methodological, not empirical |

**CRITICAL findings:** 0  
**HIGH findings:** 6 (F001, F003, F006, F008, F010, F014)  
**MEDIUM findings:** 8  
**LOW findings:** 1  
**INSIGHT (positive):** 2 (F007, F016)


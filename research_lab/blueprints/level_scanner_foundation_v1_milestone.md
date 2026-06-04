# Milestone Brief — LEVEL_SCANNER_FOUNDATION_V1

**Milestone ID:** LEVEL_SCANNER_FOUNDATION_V1  
**Status:** AWAITING_IMPLEMENTATION  
**Active Builder:** Codex (default)  
**Estimated Effort:** 10-16h implementation + 3-5h validation  
**Priority:** P0 (blocks all setup portfolio work)  
**Decision Date:** 2026-06-04  
**Approved By:** Greg (operator), Claude Code (auditor), Claude (browser meta-audit)

---

## Context — Why This Milestone

**M1 Diagnostic Result (production data, last 60 days):**
- 97.9% of decision cycles: `signal_engine_no_candidate`
- 74.9% `no_sweep` (waiting for equal level sweep)
- 21.8% `sweep_too_shallow` (sweep detected but insufficient depth)
- Only 1 signal generated in 3,120 cycles (0.03% hit rate)

**Root Cause:** Setup scarcity. Current `reclaim_swing` is extremely selective.

**Strategic Decision:** Setup portfolio expansion is correct lever (NOT regime veto, NOT risk calibration).

**Architectural Decision:** Avoid monolithic signal engine. Build factory pattern:
- `level_scanner` emits level facts (sessions, PDH/PDL, EQH/EQL, etc.)
- Setup modules (reclaim_rejection, reclaim_session, etc.) interpret facts into candidates
- Clean separation: scanner never places trades, setup modules never detect levels

**This milestone is PREREQUISITE for:**
- `reclaim_rejection` diagnostic (M3)
- `reclaim_session` level-provenance extension
- Future `reclaim_breaker`, `ote_pullback` candidates

---

## Scope — What We're Building

**Module:** `research_lab/level_scanner.py`

**Interface:**
```python
def scan_levels(ohlcv_df: pd.DataFrame, config: ScannerConfig) -> pd.DataFrame:
    """
    Convert OHLCV + sessions + future Tardis data into auditable level facts.
    
    Returns DataFrame with schema:
    - level_id (deterministic SHA256 hash)
    - symbol, timeframe, category, side, price, top, bottom
    - formed_at, available_at, expired_at, swept_at
    - source, lookback_bars, tolerance_abs, tolerance_atr
    - quality_score, is_hpz, metadata_json
    """
```

**Six Level Categories:**
1. **Session Extremes** — Asia, London, NY, kill zones (UTC-defined)
2. **PDH/PDL/PWH/PWL** — previous day/week high/low
3. **EQH/EQL Clusters** — equal highs/lows with ATR tolerance
4. **Anchored VWAP** — from swing HH/LL
5. **Round Numbers** — 1k, 5k, 10k intervals
6. **Liquidation Clusters** — placeholder (empty DataFrame until Tardis backfill)

---

## Success Criteria — How We Know It's Done

### 1. Implementation Complete
- ✅ `research_lab/level_scanner.py` exists
- ✅ All 6 categories implemented (category #6 as placeholder stub)
- ✅ Output schema matches spec (26 columns)
- ✅ Deterministic `level_id` hash (SHA256, F014 fix applied)

### 2. Tests Pass
- ✅ `research_lab/tests/test_level_scanner.py` with ≥80% coverage
- ✅ Unit tests: timezone boundaries, period rollover, ATR tolerance, deterministic hash
- ✅ Fixture tests: synthetic OHLCV with known expected levels

### 3. Cross-Validation Report Complete
- ✅ `research_lab/validation_report_level_scanner.md` exists
- ✅ Compared local vs joshyattridge on 6m BTC sample (2025-06-01 to 2025-12-01)
- ✅ Sessions: exact active flags/high/low match (after UTC normalization)
- ✅ Liquidity clusters: tolerance-based comparison (ATR vs global range difference documented)
- ✅ PDH/PDL: exact match after UTC boundary normalization
- ✅ Mismatches < 5% or explained with evidence

### 4. Audit Pass
- ✅ Claude Code adversarial review: compliance, factual, repo mapping, logic, adversarial thinking
- ✅ No CRITICAL or HIGH findings unresolved
- ✅ Layer separation enforced (scanner emits facts only, no trade decisions)

---

## Known Issues — Resolved in This Milestone

**F014 (HIGH):** `level_id` hash function underspecified in original spec  
**Resolution:** Use `SHA256(f'{source}|{category}|{symbol}|{timeframe}|{price:.8f}|{formed_at.isoformat()}')[:16]`

**F015 (MEDIUM):** Liquidation category #6 placeholder behavior underspecified  
**Resolution:** If Tardis unavailable, return empty DataFrame for `BID_LIQ`/`ASK_LIQ` categories (no error raised)

**F013 (LOW):** Spec references future setup modules that don't exist  
**Acknowledged:** This is foundation milestone; setups come later

---

## Non-Goals — What We're NOT Doing

❌ **NOT implementing setup logic** (reclaim_rejection, reclaim_session, etc.) — that's M3+  
❌ **NOT modifying `signal_engine.py`** — research lab only  
❌ **NOT adding dependencies** to `requirements.txt` (joshyattridge used for cross-check only)  
❌ **NOT implementing Tardis liquidation backfill** — category #6 is placeholder stub  
❌ **NOT creating production code** — all work in `research_lab/`

---

## Integration Points — Where This Connects

**Upstream (data sources):**
- OHLCV DataFrames (15m, 4h, 1D, 1W resampled)
- Future: Tardis liquidation data (category #6, deferred)

**Downstream (consumers, future milestones):**
- M3: `reclaim_rejection` diagnostic (reads EQH/EQL + rejection zones)
- Future: `reclaim_session` (reads session extremes + PDH/PDL as level-provenance metadata)
- Future: `reclaim_breaker`, `ote_pullback` (read various level categories)

**Cross-validation (external references):**
- joshyattridge/smart-money-concepts (MIT, sessions + liquidity clustering)
- PyIndicators (reference only, no direct integration)

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| joshyattridge validation oracle has bugs | 3/5 | 3/5 | Cross-validate against joshyattridge AND independent hand-calculation on 10-day sample |
| Timezone/DST handling errors create false levels | 3/5 | 4/5 | UTC-only sessions, unit tests for boundary cases, explicit `[start, end)` intervals |
| ATR tolerance vs global range mismatch masks issues | 3/5 | 3/5 | Document ATR vs global range difference in validation report, show examples |
| Scope creep: scanner starts making entry decisions | 2/5 | 5/5 | Enforce layer separation in code review: scanner emits facts only, no `SignalCandidate` construction |
| Category #6 stub forgotten, later causes crash | 3/5 | 3/5 | Explicit empty DataFrame return + docstring warning + test case for unavailable Tardis |

---

## Acceptance Checklist

Before marking milestone DONE:

- [ ] All 6 categories implemented (category #6 as stub)
- [ ] Output schema matches spec (26 columns, deterministic `level_id`)
- [ ] Tests pass: unit (timezone, rollover, ATR, hash) + fixture (synthetic OHLCV)
- [ ] Validation report complete: 6m BTC cross-check vs joshyattridge
- [ ] Sessions: exact match (after UTC normalization)
- [ ] Liquidity: tolerance-based match (ATR vs global range documented)
- [ ] PDH/PDL: exact match (after UTC boundary normalization)
- [ ] Mismatches < 5% or explained
- [ ] Claude Code audit: no unresolved CRITICAL/HIGH findings
- [ ] Layer separation verified: scanner emits facts only, no trade logic
- [ ] Commit messages: WHAT/WHY/STATUS in each
- [ ] No self-marking as "done" (auditor verifies)

---

## Next Milestone After This

**M2 (parallel):** F010 fix — `MicrostructureContext` blueprint revision (1h, non-blocking)

**M3 (sequential):** `reclaim_rejection` diagnostic (14-24h, depends on M1 complete)

**Future:** `reclaim_session` level-provenance extension (2-4h, depends on M1 complete)

---

## References

**Specs:**
- `research_lab/blueprints/level_scanner_spec.md` (Codex deliverable #4)
- `research_lab/RESEARCH_NOTES/smc_libraries_mining.md` (external library analysis)

**Audit:**
- `research_lab/AUDITS/per_deliverable_audit.md` (findings F013, F014, F015)
- `research_lab/AUDITS/findings_register.md` (full findings list)

**Architecture:**
- `docs/BLUEPRINT_RESEARCH_LAB.md` (research lab workflow)
- `AGENTS.md` (builder discipline + commit rules)

**Strategic:**
- M1 diagnostic query result (setup scarcity confirmed: 97.9% `signal_engine_no_candidate`)
- Multi-agent reconciliation: joshyattridge = reference implementation, NOT "gold edge"

---

**Status:** Ready for builder handoff (Codex).

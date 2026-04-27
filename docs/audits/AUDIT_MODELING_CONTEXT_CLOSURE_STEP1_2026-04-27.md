# AUDIT: MODELING-CONTEXT-CLOSURE (Step 1: Telemetry Fix)

**Date:** 2026-04-27  
**Auditor:** Claude Code  
**Builder:** Codex  
**Branch:** `modeling-context-closure`  
**Commits:** `e6ef52f` (docs), `ab64a9b` (fix)  
**Status:** MVP_DONE

---

## Executive Summary

**Verdict: MVP_DONE** ✅

Step 1 of MODELING-CONTEXT-CLOSURE is complete: volatility feature telemetry is now decision-grade.

Signal entry payloads (`SignalCandidate.features_json` → `trade_log.features_at_entry_json`) now persist the fields required for prospective modeling validation:
- `atr_4h` / `atr_4h_norm` (volatility bucket classification)
- `ema50_4h` / `ema200_4h` (HTF trend context)

This unblocks the next validation step: re-running `MODELING-V1-VALIDATION` on post-deploy data to measure whether `UNKNOWN volatility` share drops below 20%.

---

## Scope Verification

**Milestone deliverables (from MILESTONE_TRACKER.md):**

| # | Deliverable | Status |
|---|---|---|
| 1 | Ensure decision-grade context telemetry (atr_4h_norm reconstructable) | ✅ DONE (this audit) |
| 2 | Re-run MODELING-V1-VALIDATION on clean post-deploy window | ⏳ PENDING (next step) |
| 3 | Reduce UNKNOWN volatility <= 20% | ⏳ PENDING (verification after step 2) |
| 4 | Produce activation verdict (keep_neutral / activate / redesign) | ⏳ PENDING (after step 3) |
| 5 | Strategy conclusion on context work vs uptrend research | ⏳ PENDING (after step 4) |

**This audit covers deliverable #1 only.**

---

## Audit Dimensions

### Layer Separation: PASS ✅
- `_build_candidate_features_payload()` is a static method in `SignalEngine`
- Reads from `Features` model (core contract)
- Returns plain dict (serializable JSON payload)
- No cross-layer leakage

### Contract Compliance: PASS ✅
- All exported fields exist in `Features` dataclass:
  - `atr_4h`, `atr_4h_norm`, `ema50_4h`, `ema200_4h` (HTF volatility/trend)
  - `atr_15m`, `sweep_depth_pct`, `funding_pct_60d`, etc. (existing)
- Type signature matches: `dict[str, float | bool | str | None]`

### Determinism: PASS ✅
- Function is pure: `@staticmethod`, no side effects, no hidden state
- Output deterministic given `Features` input

### State Integrity: PASS ✅
- Payload persisted to `SignalCandidate.features_json` (immutable after creation)
- Copied to `trade_log.features_at_entry_json` via `record_trade_open()`
- No mutation risk after entry

### Error Handling: PASS ✅
- No error paths in this function (pure data extraction)
- Missing fields handled by `Features` dataclass defaults

### Smoke Coverage: PASS ✅
**Test: `test_generate_persists_modeling_fields_in_candidate_payload`**
- Verifies `atr_4h_norm`, `ema50_4h`, `ema200_4h` presence in candidate payload
- Confirms payload structure matches expected schema

**Test: `test_record_trade_open_persists_modeling_features_payload`**
- Verifies features propagate from `SignalCandidate` → `trade_log.features_at_entry_json`
- End-to-end coverage: signal generation → trade entry persistence

**Regression suite: 26 tests passing**
- `tests/test_signal_engine.py` (20 tests)
- `tests/test_paper_fill_fix.py` (6 tests)

### Tech Debt: LOW ✅
- Clean implementation, no TODOs
- No `NotImplementedError` stubs
- No duplication (old inline dict replaced with shared helper)

### AGENTS.md Compliance: PASS ✅
**Commit message quality:**
- `e6ef52f`: WHAT/WHY/STATUS format ✅
- `ab64a9b`: WHAT/WHY/STATUS format ✅

**Timestamp discipline:**
- Not applicable (no timestamp manipulation in this change)

### Methodology Integrity: N/A
- Not a research lab change

---

## Code Quality Observations

### What Changed

**Before (`e6ef52f^`):**
```python
features_json={
    "atr_15m": features.atr_15m,
    "sweep_depth_pct": features.sweep_depth_pct,
    # ... 7 fields total (no HTF features)
}
```

**After (`ab64a9b`):**
```python
@staticmethod
def _build_candidate_features_payload(features: Features) -> dict[str, float | bool | str | None]:
    return {
        "atr_15m": features.atr_15m,
        "atr_4h": features.atr_4h,
        "atr_4h_norm": features.atr_4h_norm,
        "ema50_4h": features.ema50_4h,
        "ema200_4h": features.ema200_4h,
        # ... 13 fields total (HTF features added)
    }

features_json=self._build_candidate_features_payload(features),
```

**Impact:**
- DRY improvement: inline dict extraction replaced with reusable helper
- Payload enrichment: +5 fields (atr_4h, atr_4h_norm, ema50_4h, ema200_4h, + atr_15m was implicit)
- Test coverage: regression suite verifies end-to-end propagation

---

## Critical Issues

None.

---

## Warnings

None.

---

## Observations (Non-Blocking)

### Documentation Update: MILESTONE_TRACKER.md
**Commit `e6ef52f`:**
- Refocused tracker on single active path: `MODELING-CONTEXT-CLOSURE`
- Deferred `RESEARCH-OPTUNA-V1` (infrastructure exists, no run approved)
- Marked `MODELING-V1-VALIDATION` as checkpoint (partial, not active)

**Missing in MILESTONE_TRACKER.md:**
- `Builder: TBD` should be updated to `Builder: Codex` (Codex authored both commits)

### Validation Timing
**Cannot verify success until post-deploy:**
- Current fix ensures `atr_4h_norm` is **written** to entry payloads
- But no closed trades exist yet with enriched payloads (deploy hasn't happened)
- Must collect new sample (24-48h post-deploy) before re-running validation

---

## Recommended Next Step

**AUTO-PUSH + DEPLOY + COLLECT + VALIDATE**

1. **Push branch to origin** (auto-push per CLAUDE.md policy for MVP_DONE)
2. **Deploy to production** (systemd restart)
3. **Wait 24-48h** for new closed trades with enriched `features_at_entry_json`
4. **Re-run validation:**
   ```bash
   ssh root@204.168.146.253
   cd /home/btc-bot/btc-bot
   python scripts/modeling_v1_validation.py
   ```
5. **Check UNKNOWN volatility share:**
   - If `<= 20%` → proceed to deliverable #4 (activation decision)
   - If `> 20%` → investigate remaining data quality gaps

---

## Verdict

**MVP_DONE** ✅

Logic is correct, tests pass, telemetry gap is closed. Ready for production deployment.

Remaining work (deliverables #2-#5) requires post-deploy data collection and validation rerun.

# AUDIT: M4 Near-Miss Payload Contract Fix

Date: 2026-05-16
Auditor: Claude Code
Commit: 33a0df1
Branch: research/sweep-family-expansion-v1
Milestone: PAPER_NEAR_MISS_MONITORING_V1 / M4 early checkpoint

## Verdict: PASS_FOR_PAPER_DEPLOY

Diagnostic payload fix is safe for PAPER production deployment. Runtime behavior preserved except diagnostic payload shape. Early checkpoint conclusion is sound: continue monitoring unchanged.

## Change Summary

**What changed:**
- Added `"sweep_depth_pct": depth,` to nested `near_miss_diagnostics` payload in orchestrator.py
- Made report parser backward-compatible with existing production rows (fallback to top-level field)
- Added 3 new tests (2 for report compatibility, 1 for orchestrator payload shape)
- Recorded M4 early checkpoint report

**Why:**
- Production rows showed `sweep_depth_pct` only at top-level `details_json`, not inside `details_json.near_miss_diagnostics`
- This conflicted with documented M4 query contract
- Could undercount threshold-proximity diagnostics
- Fix standardizes payload structure for future queries

**Files changed (6):**
1. `orchestrator.py` - added nested sweep_depth_pct to near_miss_data dict
2. `scripts/report_near_miss_diagnostics.py` - backward-compatible fallback
3. `tests/test_near_miss_diagnostics.py` - 2 new report compatibility tests
4. `tests/test_orchestrator_runtime_logging.py` - 1 new payload shape test
5. `docs/diagnostics/M4_NEAR_MISS_MONITORING_CHECKPOINT_2026-05-16.md` - early checkpoint report
6. `docs/MILESTONE_TRACKER.md` - updated M4 status

## Audit Questions

### 1. Does this preserve runtime behavior except diagnostic payload shape?

**YES - PASS**

**Evidence:**
- Only change in orchestrator.py: add `"sweep_depth_pct": depth,` to `near_miss_data` dict
- Method `_signal_diagnostics_payload` is @staticmethod, pure data transformation
- No execution/risk/governance method changes (verified by git diff grep)
- No changes to core/, execution/, data/, settings directories (verified by git diff --stat)
- Tests confirm behavior preserved: 24/24 passed

**Code analysis:**
```python
# BEFORE (33a0df1^)
near_miss_data = {
    "threshold": threshold,
    "threshold_distance": round(threshold_distance, 3),
    "depth_bucket": depth_bucket,
    # ... other fields
}

# AFTER (33a0df1)
near_miss_data = {
    "sweep_depth_pct": depth,  # <-- ONLY ADDITION
    "threshold": threshold,
    "threshold_distance": round(threshold_distance, 3),
    "depth_bucket": depth_bucket,
    # ... other fields (unchanged)
}
```

**Payload already contained top-level sweep_depth_pct:**
- Line 928: `"sweep_depth_pct": diagnostics.sweep_depth_pct,` (unchanged)
- Top-level field preserved for backward compatibility
- Nested field added for query convenience

**No execution path changes:**
- `_signal_diagnostics_payload` is only called for logging/diagnostics
- Result is stored in `decision_outcomes.details_json` (SQLite)
- No decision logic reads from this payload
- Execution flow: signal detection → risk evaluation → governance → order placement (unchanged)

### 2. Is adding nested sweep_depth_pct to near_miss_diagnostics contract-safe?

**YES - PASS**

**Additive change:**
- No existing fields removed
- No field types changed
- No field semantics changed
- Only adds one field to nested dict

**Backward compatibility:**
- Old code reading top-level `details_json.sweep_depth_pct` still works
- Old code not expecting nested field ignores it safely (JSON parsing tolerates extra fields)
- New code can use nested `details_json.near_miss_diagnostics.sweep_depth_pct` for cleaner queries

**Contract consistency:**
- Documented M4 query contract in docs/DATA_SOURCES.md expected nested field
- Documented query in docs/diagnostics/NEAR_MISS_MONITORING_README.md expected nested field
- Implementation now matches documentation

**SQLite schema:**
- `decision_outcomes.details_json` is TEXT column storing JSON
- Schema unchanged
- JSON structure flexibility allows nested field addition

### 3. Is the backward-compatible report parser correct for existing production records?

**YES - PASS**

**Fallback logic:**
```python
# BEFORE
depth = near_miss.get("sweep_depth_pct", 0)

# AFTER
depth = near_miss.get("sweep_depth_pct", details.get("sweep_depth_pct", 0))
```

**Evaluation order:**
1. Try nested: `near_miss.get("sweep_depth_pct", ...)`
2. Fall back to top-level: `details.get("sweep_depth_pct", 0)`
3. Default to 0 if neither exists

**Correctness:**
- For NEW rows (after this deploy): nested field exists → use nested value ✓
- For OLD rows (before this deploy): nested field missing → fall back to top-level ✓
- For CORRUPT rows (both missing): default to 0 (safe, won't crash) ✓

**Test coverage:**
- `test_report_uses_nested_sweep_depth_pct` - verifies new payload shape works
- `test_report_falls_back_to_top_level_sweep_depth_pct` - verifies old payload shape works
- Both tests passed (24/24)

**Production impact:**
- Report script can now query both new and old production rows
- No data loss
- No reprocessing required
- Historical rows remain queryable

### 4. Is the early checkpoint conclusion sound?

**YES - PASS**

**Evidence summary (M4_NEAR_MISS_MONITORING_CHECKPOINT_2026-05-16.md):**

| Metric | Value | Interpretation |
|---|---|---|
| Window | 3 days (2026-05-13 to 2026-05-16) | Early checkpoint, not final |
| Decision cycles | 464 | Healthy runtime activity |
| sweep_too_shallow rejections | 260 (56%) | Dominant blocker confirmed |
| Signals generated | 0 | Frequency bottleneck remains |
| Near-miss records | 10 (~5 unique timestamps) | Small sample |
| Max observed depth | 0.005795 | **10.7% below 0.00649 threshold** |
| Within 10% of threshold | 0 | **No very close misses** |
| Within 20% of threshold | 2 | One duplicated timestamp pair |
| Regime distribution | 100% uptrend | All near-misses in uptrend |
| Session distribution | US 6, EU 2, ASIA 2 | US contributed majority |

**Checkpoint verdict:** `EARLY_MONITORING_CONTINUE_WITH_PAYLOAD_FIX`

**Conclusion soundness:**
- **Correct decision: continue monitoring unchanged**
  - Max depth 10.7% below threshold → not close enough to justify parameter change
  - Zero near-misses within 10% → no strong signal for threshold relaxation
  - Small sample (10 records, ~5 unique timestamps) → insufficient for decision
  - Duplicated timestamp pattern → raw count inflated, true event count lower
  - No generated signals in 3 days → confirms frequency bottleneck remains active

- **Correct decision: no parameter change**
  - Trial-00095 baseline (min_sweep_depth_pct=0.00649) remains appropriate
  - Evidence does NOT support relaxing to 0.006 or lower
  - Evidence does NOT support tightening to 0.007
  - Wait for full 30-day checkpoint (2026-06-13) for larger sample

- **Correct decision: payload/reporting fix only**
  - Contract alignment is operational hygiene, not strategy change
  - Backward compatibility preserves historical data utility
  - No execution logic modified

**Risk assessment:**
- Risk of premature parameter change: MITIGATED (no change made)
- Risk of missing actionable signal: LOW (no close misses observed)
- Risk of monitoring continuation: ACCEPTABLE (bot healthy, PAPER mode, no open positions)

### 5. Is this safe to deploy to PAPER production server after audit?

**YES - PASS**

**Safety checklist:**

✓ **Runtime behavior preserved**
- Only diagnostic payload shape changed
- No execution/risk/governance logic modified
- Tests confirm behavior preserved (24/24 passed)

✓ **Backward compatible**
- Report parser handles both old and new payload shapes
- Historical production rows remain queryable
- No data migration required

✓ **Tests pass**
- Focused tests: 24/24 passed in 0.32s
- New tests cover both payload shapes
- Existing tests unchanged and passing

✓ **Compileall clean**
- All changed Python files compile without syntax errors
- Verified: orchestrator.py, scripts/report_near_miss_diagnostics.py, test files

✓ **No production layer violations**
- core/ unchanged
- execution/ unchanged
- data/ unchanged
- settings unchanged
- Only orchestrator.py diagnostic logic touched

✓ **PAPER mode appropriate**
- Change is diagnostic only
- PAPER mode suitable for validating new payload shape
- No risk to live capital (PAPER uses simulated fills)
- Easy rollback if issues discovered

✓ **Monitoring in place**
- M4 checkpoint established (2026-05-16)
- Next checkpoint: 2026-06-13 (30-day milestone)
- Report script ready to analyze new payload format

**Deployment steps:**
1. Git pull on production server
2. Restart bot service (systemd or manual)
3. Verify first decision_outcome row has nested sweep_depth_pct
4. Run report script to confirm backward compatibility
5. Monitor logs for errors
6. Continue M4 monitoring through 2026-06-13 checkpoint

**Rollback plan (if needed):**
1. Git checkout previous commit (be69576)
2. Restart bot service
3. Report script already backward-compatible, no changes needed
4. Old payload format continues working

---

## Layer Separation: PASS

**Production boundary respected:**
- No changes to core/, execution/, data/, settings
- orchestrator.py is execution orchestration layer (allowed to change for diagnostics)
- Diagnostic payload is logged data, not execution decision input
- Report script is read-only analysis tool (scripts/ layer)

**No strategy parameter changes:**
- min_sweep_depth_pct remains 0.00649 (trial-00095 baseline)
- No threshold relaxation or tightening
- No governance rule changes
- No risk parameter changes

## Contract Compliance: PASS

**Payload contract:**
- Before: top-level sweep_depth_pct only
- After: top-level sweep_depth_pct (preserved) + nested sweep_depth_pct (added)
- Aligns with documented M4 query contract

**Report contract:**
- Backward-compatible fallback logic
- Handles both old and new production rows
- No breaking changes to existing queries

## Determinism: PASS

**Diagnostic payload generation is deterministic:**
- Input: SignalDiagnostics, Features
- Output: dict with consistent fields
- No randomness, no external API calls
- Same inputs → same payload

**Report analysis is deterministic:**
- Input: SQLite query results
- Output: aggregated statistics
- No randomness, no LLM calls
- Same data → same report

## State Integrity: PASS

**SQLite integrity:**
- decision_outcomes table schema unchanged
- details_json column remains TEXT (JSON string)
- No schema migration required
- Historical rows preserved

**No state corruption risk:**
- Additive change only
- No data deletion
- No data modification of existing rows
- New rows have additional nested field

## Error Handling: PASS

**Fallback logic:**
- Report parser defaults to 0 if sweep_depth_pct missing at both levels
- No crash risk
- Safe degradation

**Validation:**
- near_miss_data dict construction has explicit field assignments
- No undefined variable references
- Type safety via Python dict literals

## Smoke Coverage: PASS

**Test results:**
- 24/24 passed in 0.32s
- 100% pass rate
- Fast execution

**New tests (3):**
1. `test_near_miss_payload_includes_nested_sweep_depth_pct` - verifies orchestrator payload shape
2. `test_report_uses_nested_sweep_depth_pct` - verifies report parser handles new shape
3. `test_report_falls_back_to_top_level_sweep_depth_pct` - verifies report parser handles old shape

**Existing tests (21) still passing:**
- orchestrator runtime logging tests
- near-miss diagnostics logic tests
- Confirms no regression

## Tech Debt: LOW

**No new debt introduced:**
- No TODOs added
- No NotImplementedError stubs
- No placeholder logic
- Complete implementation

**Existing limitation acknowledged:**
- Checkpoint report notes "duplicated record pattern" (multiple near-miss records per unique timestamp)
- Not a bug, just a characteristic of the diagnostic logging (multiple rejections can occur in same decision cycle)
- Recommendation correctly accounts for this ("raw count inflated, true event count lower")

## AGENTS.md Compliance: PASS

**Commit discipline:**
- Commit message: "diagnostics: fix M4 near-miss payload contract"
- WHAT: clear
- WHY: clear
- STATUS: clear (pending audit)
- Co-Authored-By: present (Cascade is builder for this milestone)

**Layer rules:**
- Diagnostic change only (allowed)
- No production/PAPER parameter changes (compliant)
- No git hook bypass
- Branch strategy correct (research/sweep-family-expansion-v1)

---

## M4 Early Checkpoint Assessment

**Production health:** ✓
- Mode: PAPER
- Healthy: 1
- Safe mode: 0
- Open positions: 0
- No runtime warnings

**Frequency bottleneck status:** Confirmed active
- 56% rejections due to sweep_too_shallow
- 0 signals generated in 3-day window
- Consistent with prior evidence (M5, M6, M7 all showed frequency issues)

**Threshold regime evidence:** Insufficient for change
- Max depth 10.7% below threshold (not close)
- No near-misses within 10% (no strong signal)
- Small sample (~5 unique events)
- Duplicated timestamp pattern inflates raw count

**Strategic alignment:**
- M4 purpose: diagnose whether sweep_depth_pct regime is improving
- Finding: no improvement detected in 3-day early checkpoint
- Conclusion: continue monitoring through full 30-day window (2026-06-13)
- This aligns with milestone acceptance criteria (diagnostic only, no parameter change unless clear regime shift)

**Operational finding:**
- Payload contract mismatch discovered (top-level vs nested sweep_depth_pct)
- Fix is pure operational hygiene (align implementation with documentation)
- No strategy implication
- Backward-compatible deployment

---

## Critical Issues

None.

## Warnings

None.

## Observations

### Duplicated Timestamp Pattern in Near-Miss Records

**What:** Checkpoint report shows 10 near-miss records but ~5 unique timestamps.

**Why:** A single decision cycle can produce multiple rejections if:
- Initial sweep detection triggers near-miss logging
- Subsequent checks (direction, confluence, risk gates) also reject
- Each rejection may log a near-miss record if depth >= 0.004

**Impact:** Raw near-miss count can overestimate unique sweep events.

**Mitigation:** Checkpoint report correctly interprets this ("Approx. unique near-miss timestamps: 5"). Final M4 checkpoint (2026-06-13) should aggregate by timestamp or event_id for accurate event count.

**Not a bug:** This is characteristic of diagnostic logging. Each rejection reason is independently valuable for analysis.

### Early Checkpoint Timing

**What:** Checkpoint performed at 3 days (2026-05-16) instead of 30 days (2026-06-13).

**Why:** Builder discovered payload contract mismatch during report analysis. Early checkpoint validates:
1. Bot healthy after initial M4 deploy
2. Diagnostic logging working
3. Payload fix needed
4. No urgent threshold change required

**Appropriate:** Early checkpoints are good practice for long-running monitoring milestones. Confirms monitoring infrastructure works before full 30-day wait.

**Next:** Continue monitoring unchanged through 2026-06-13 for full 30-day sample.

---

## Recommended Next Step

**APPROVE for PAPER deployment.** Payload fix is safe, backward-compatible, and operationally correct. Early checkpoint conclusion is sound: continue M4 monitoring unchanged through 2026-06-13.

**Deployment:**
1. Merge to main or deploy directly from research branch (user decision)
2. Deploy to production server (git pull + systemd restart)
3. Verify first new decision_outcome row has nested sweep_depth_pct
4. Run report script to confirm backward compatibility works
5. Continue M4 monitoring (no parameter change, no execution change)

**Next milestone checkpoint:** 2026-06-13 (30-day M4 full checkpoint)

**If M4 final checkpoint shows actionable evidence:**
- Threshold regime shift (sweep depths consistently closer to threshold)
- Multiple near-misses within 5-10% of threshold
- Clear uptrend or session pattern
→ Then consider parameter adjustment research (new milestone, not automatic change)

**If M4 final checkpoint shows no regime shift:**
- Proceed to strategic options:
  - **Option A:** Close M4, accept frequency bottleneck, focus on trial-00095 live validation
  - **Option B:** ETH multi-asset feasibility study
  - **Option C:** Other research direction (user decision)

---

**Audit status:** DONE
**Deployment verdict:** PASS_FOR_PAPER_DEPLOY
**Milestone status:** M4 monitoring continues (early checkpoint complete)

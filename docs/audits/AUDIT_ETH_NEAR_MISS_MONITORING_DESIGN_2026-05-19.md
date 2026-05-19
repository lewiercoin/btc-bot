# AUDIT: ETH_NEAR_MISS_MONITORING_DESIGN_V1

**Date:** 2026-05-19  
**Auditor:** Claude Code  
**Commit:** 275b6eb  
**Builder:** Codex  
**Scope:** Design-only checkpoint for future ETH shadow monitoring

---

## Verdict: PASS

Design-only contract for future ETH shadow/no-order near-miss monitoring. Clear BTC M4 blocker preservation, ETH/BTC separation, concrete checkpoints, threshold change blocker, and no runtime approval. Ready to guide post-M4 ETH shadow implementation if user proceeds.

---

## Core Audit Axes

### Layer Separation: PASS (Design-Only)

**Files changed:**
- `docs/blueprints/ETH_NEAR_MISS_MONITORING_DESIGN_V1_2026-05-19.md` (new: +271 lines)
- `research_lab/hypotheses/active/eth_near_miss_monitoring_design.json` (new: +61 lines)
- `docs/` (MILESTONE_TRACKER, DECISIONS_LOG updates)

**Runtime verification:**
- **No runtime files changed:** Zero modifications to core/, execution/, orchestrator.py, main.py, settings.py, storage/, backtest/
- **BTC PAPER bot unchanged:** PID 815407 active on server (verified via SSH)
- **M4 monitoring unchanged:** No runtime behavior changes

**Design-only scope:**
- Status: `READY_FOR_AUDIT_DESIGN_ONLY` ✓
- Scope: "Design only. No runtime implementation, PAPER deployment, LIVE deployment, or code-path change." ✓
- Non-goals explicit: "does not implement ETH shadow runtime; does not modify core/**, execution/**, orchestrator.py, main.py, settings.py, storage/**, or backtest/**" ✓

### Contract Compliance: PASS

**BTC M4 as blocker (preserved):**

Design: "ETH monitoring may only start after these gates:"
1. ✓ "BTC M4 checkpoint completed and audited"
2. ✓ "User approves continuing the multi-asset path"
3. ✓ "Multi-asset runtime implementation is built and audited with ETH in shadow_no_orders mode"
4. ✓ "BTC PAPER behavior remains unchanged during initial ETH shadow collection"

Design: "Keep BTC PAPER and BTC M4 monitoring unchanged through 2026-06-13."

**BTC M4 blocker explicit in required deployment sequence.** ETH shadow cannot start before BTC M4 completes.

**ETH/BTC monitoring separation (non-contamination):**

Design section "Separation From BTC M4":
- ✓ "separate symbol field in every decision outcome"
- ✓ "separate reports"
- ✓ "separate config hashes by symbol/profile"
- ✓ "separate near-miss bucket counts"
- ✓ "separate threshold recommendations"
- ✓ **"no aggregation of BTC and ETH near-misses into one threshold conclusion"**

Design: "BTC M4 can recommend a BTC action only. ETH shadow can recommend an ETH action only."

**Separation contract is clear and prevents BTC M4 contamination.**

**ETH near-miss payload contract:**

Required fields (symbol-explicit):
- `symbol = ETHUSDT`
- `timestamp_utc`
- `config_hash`
- `strategy_profile = trial_00095_transfer`
- `shadow_mode = true`
- `signal_generated`, `signal_blocker`
- `sweep_detected`, `reclaim_detected`, `sweep_side`, `sweep_level`, `sweep_depth_pct`
- `min_sweep_depth_pct`
- Regime, context, confluence, governance, portfolio diagnostics

**Critical requirement:**
"If `signal_blocker = sweep_too_shallow` and `sweep_depth_pct` is above the ETH near-miss floor, include:"
```json
{
  "near_miss_diagnostics": {
    "symbol": "ETHUSDT",
    "sweep_depth_pct": 0.0,
    "threshold": 0.00649,
    "depth_gap_pct": 0.0,
    "depth_bucket": "near_miss_low",
    "regime": "uptrend",
    "session_hour": 0,
    "rejection_reasons": []
  }
}
```

Design: "The nested `near_miss_diagnostics.sweep_depth_pct` field is mandatory. This copies the corrected BTC M4 contract and prevents a second parser mismatch."

**Nested payload requirement explicit.** Matches corrected BTC M4 contract to prevent repeat of BTC M4 parser issue.

**ETH near-miss buckets defined:**

| Bucket | Condition | Purpose |
|---|---|---|
| `far_below` | `depth < 0.00400` | Too shallow for threshold discussion |
| `near_miss_low` | `0.00400 <= depth < 0.00519` | Below 80% of baseline threshold |
| `near_miss_mid` | `0.00519 <= depth < 0.00584` | Within 20% of baseline threshold |
| `near_miss_high` | `0.00584 <= depth < 0.00649` | Within 10% of baseline threshold |
| `baseline_pass` | `depth >= 0.00649` | Passes frozen trial-00095 sweep depth |

Design: "The floor `0.00400` is diagnostic only. It is not an alternate trading threshold."

**Buckets parallel BTC M4 structure. Floor is diagnostic, not a trading threshold.**

### Determinism: PASS (Design)

**Shadow mode state contract:**

| State | Behavior |
|---|---|
| `disabled` | No data collection, no signals, no diagnostics |
| `shadow_no_orders` | Build ETH snapshots, features, regime, signal diagnostics, governance/risk diagnostics, near-miss payloads; **never open positions** |
| `paper_enabled` | ETH may place PAPER orders **only after separate audit and user approval** |

Design: "The first ETH runtime milestone must use `shadow_no_orders`."

**Shadow mode is deterministic: no orders while shadow_no_orders.**

**Checkpoint determinism:**

**Day 3 Operational Check:**
- exactly one BTC PAPER runtime process
- ETH shadow mode does not open positions
- no ETH orders in paper/live tables
- ETH decision outcomes have `symbol = ETHUSDT`
- nested `near_miss_diagnostics.sweep_depth_pct` present for near-misses
- BTC M4 rows remain symbol-separated and unchanged
- no duplicate active config hashes for the same symbol

**Day 3 cannot approve ETH PAPER.**

**Day 14 Shadow Check (required metrics):**
- decision cycles
- generated shadow signals
- `sweep_too_shallow` count and share
- near-miss records by bucket
- max, median, and p90 `sweep_depth_pct`
- governance shadow pass/veto counts
- portfolio shadow pass/veto counts
- same-bar overlap with BTC PAPER signals
- simulated approved ETH signal count before order placement
- missing-data or stale-feature count

**Day 14 can only approve continuing shadow collection or scheduling a longer checkpoint.**

**Day 30 Shadow Check (required gates):**

| Gate | Requirement |
|---|---|
| Runtime safety | 0 ETH orders while in shadow mode |
| Payload integrity | 100% of near-miss records have nested depth |
| Data freshness | No persistent stale ETH features across decision cycles |
| Process integrity | Single runtime instance; no duplicate symbol workers |
| Signal availability | At least 10 ETH shadow signals or a documented low-frequency explanation |
| Near-miss clarity | Threshold-proximate near-misses are quantified; no undocumented threshold change |
| Portfolio safety | ETH shadow approvals do not breach portfolio caps |
| BTC isolation | BTC M4/PAPER metrics are unaffected by ETH shadow collection |

Design: "If these gates pass, the next milestone may request ETH PAPER approval. If they fail, ETH remains shadow-only or the multi-asset path is deferred."

**Checkpoints are concrete, auditable, and have clear pass/fail criteria.**

### State Integrity: PASS (Design)

**ETH threshold change blocked:**

Design: "ETH shadow monitoring may not directly change `min_sweep_depth_pct`."

Design: "If ETH shows many `near_miss_high` records but few baseline passes, create a separate offline milestone: `ETH_SWEEP_DEPTH_THRESHOLD_STABILITY_V1`"

**Required for threshold change:**
- Replay ETH with ceteris-paribus threshold variants
- Preserve frozen non-depth trial-00095 parameters
- Use chronological walk-forward gates
- Compare against the frozen ETH transfer baseline
- **Require Claude Code audit before any runtime setting changes**

Design: "If ETH shadow shows shallow sweeps far below threshold, do not lower the threshold. Treat it as no actionable threshold evidence."

**Threshold change requires separate offline milestone with audit. Shadow monitoring cannot directly authorize threshold changes.**

**No ETH PAPER approval in design:**

Design: "This document does not approve ETH trading."

Design: "ETH PAPER orders remain blocked until the ETH shadow checkpoint passes audit."

Design: "Day 30 Shadow Check... If these gates pass, the next milestone may request ETH PAPER approval."

**ETH PAPER requires:**
1. Day 30 gates pass
2. Separate milestone requests PAPER approval
3. Audit of shadow results
4. User approval

**No backdoor to ETH PAPER. Explicit audit + user approval required.**

### Error Handling: PASS (Design)

**Shadow mode failure handling:**

**Day 3 catches:**
- Payload shape errors (missing nested depth)
- Parser issues (symbol field missing or wrong)
- Process errors (duplicate workers, multiple BTC PAPER processes)
- Data errors (missing features, stale timestamps)

**Day 14 catches:**
- Signal frequency far from offline replay expectations
- Near-miss distribution anomalies
- Governance/portfolio shadow veto patterns
- BTC/ETH same-bar overlap issues

**Day 30 catches:**
- Runtime safety violations (ETH orders while in shadow mode)
- Payload integrity failures (near-miss records without nested depth)
- Data freshness failures (persistent stale features)
- Process integrity failures (duplicate symbol workers)
- Signal availability failures (< 10 signals without explanation)
- Portfolio safety failures (ETH shadow approvals breach caps)
- BTC isolation failures (BTC M4 metrics affected by ETH)

**Checkpoint failure paths:**
- Day 3 fail → Fix operational issues before Day 14
- Day 14 fail → Continue shadow longer or defer multi-asset
- Day 30 fail → ETH remains shadow-only or multi-asset path deferred

**Explicit failure handling at each checkpoint.**

### Smoke Coverage: N/A (Design-Only)

**No runtime implementation, no smoke tests required for design.**

**JSON hypothesis validation:**
- Hypothesis file is valid JSON ✓
- All required fields present ✓
- Frozen assumptions explicit ✓
- Acceptance criteria clear ✓
- Kill criteria clear ✓

**User reported:** "targeted multi-asset tests: 18 passed" (presumably hypothesis validation + related unit tests).

### Tech Debt: NONE (Design-Only)

**No code, no debt.**

**Design completeness:**
- ✓ Shadow mode states defined
- ✓ Payload contract specified
- ✓ Near-miss buckets defined
- ✓ Checkpoint requirements explicit
- ✓ Threshold change blocker clear
- ✓ BTC/ETH separation requirements clear
- ✓ ETH PAPER approval path defined

**Design is implementation-ready.**

### AGENTS.md Compliance: PASS

**Commit discipline:**
- Commit message: "docs: define ETH near-miss monitoring design"
- WHAT: clear (adds design-only ETH monitoring contract)
- WHY: clear (ETH needs shadow before PAPER, BTC M4 must not be contaminated)
- STATUS: READY_FOR_AUDIT_DESIGN_ONLY
- Co-Authored-By: present ✓

**Layer rules:**
- Design-only changes (docs/, research_lab/ hypothesis) ✓
- No runtime modifications ✓
- Branch: `research/sweep-family-expansion-v1` ✓

---

## Audit Questions (from Blueprint)

### 1. Does this design preserve design-only scope and avoid runtime approval?

**YES.**

- Status: `READY_FOR_AUDIT_DESIGN_ONLY`
- Scope: "Design only. No runtime implementation, PAPER deployment, LIVE deployment, or code-path change."
- Non-goals: "does not implement ETH shadow runtime; does not modify core/**, execution/**, orchestrator.py, main.py, settings.py, storage/**, or backtest/**"
- No runtime files changed (verified via git diff grep)
- No runtime approval: "This document does not approve ETH trading"

### 2. Does it correctly keep BTC M4 as a blocker for multi-asset runtime changes?

**YES.**

Required deployment sequence:
1. "BTC M4 checkpoint completed and audited" ← **blocker explicit**
2. "User approves continuing the multi-asset path"
3. "Multi-asset runtime implementation is built and audited with ETH in shadow_no_orders mode"
4. "BTC PAPER behavior remains unchanged during initial ETH shadow collection"

Design: "Keep BTC PAPER and BTC M4 monitoring unchanged through 2026-06-13."

BTC M4 must complete before ETH shadow can start. No bypass path.

### 3. Does it define an ETH-specific near-miss payload compatible with the fixed BTC M4 contract?

**YES.**

ETH near-miss payload includes:
- `symbol = ETHUSDT` (explicit)
- All standard decision outcome fields
- **Nested `near_miss_diagnostics.sweep_depth_pct`** (mandatory)
- Near-miss bucket classification
- Regime, session, TFI, OI, funding context

Design: "The nested `near_miss_diagnostics.sweep_depth_pct` field is mandatory. This copies the corrected BTC M4 contract and prevents a second parser mismatch."

ETH payload matches BTC M4 structure with symbol differentiation.

### 4. Are ETH threshold decisions blocked behind a separate offline stability milestone?

**YES.**

Design: "ETH shadow monitoring may not directly change `min_sweep_depth_pct`."

Required path for threshold change:
1. Create separate milestone: `ETH_SWEEP_DEPTH_THRESHOLD_STABILITY_V1`
2. Replay ETH with ceteris-paribus threshold variants
3. Preserve frozen non-depth trial-00095 parameters
4. Use chronological walk-forward gates
5. Compare against frozen ETH transfer baseline
6. **Require Claude Code audit before any runtime setting changes**

Design: "If ETH shadow shows shallow sweeps far below threshold, do not lower the threshold. Treat it as no actionable threshold evidence."

Threshold change requires offline research + audit. Shadow monitoring alone cannot authorize changes.

### 5. Are Day 3, Day 14, and Day 30 checkpoints concrete and auditable?

**YES.**

**Day 3 Operational Check:**
- 7 specific requirements (runtime process count, no ETH orders, symbol fields, nested depth, BTC M4 separation, config hashes)
- Cannot approve ETH PAPER
- Purpose: catch payload, parser, process, and data issues early

**Day 14 Shadow Check:**
- 11 specific metrics (decision cycles, signals, near-misses, governance, portfolio, overlap, data quality)
- Can only approve continuing shadow or scheduling longer checkpoint
- Purpose: evaluate whether ETH behavior resembles offline evidence

**Day 30 Shadow Check:**
- 8 specific gates (runtime safety, payload integrity, data freshness, process integrity, signal availability, near-miss clarity, portfolio safety, BTC isolation)
- If gates pass → next milestone may request ETH PAPER approval
- If gates fail → ETH remains shadow-only or multi-asset deferred
- Purpose: decide whether ETH can move from shadow to PAPER

All checkpoints have concrete pass/fail criteria, explicit purposes, and clear next-step constraints.

### 6. Does the design prevent ETH shadow from contaminating BTC M4 conclusions?

**YES.**

Design section "Separation From BTC M4":
- ✓ "separate symbol field in every decision outcome"
- ✓ "separate reports"
- ✓ "separate config hashes by symbol/profile"
- ✓ "separate near-miss bucket counts"
- ✓ "separate threshold recommendations"
- ✓ **"no aggregation of BTC and ETH near-misses into one threshold conclusion"**

Design: "BTC M4 can recommend a BTC action only. ETH shadow can recommend an ETH action only."

Day 3 checkpoint verifies: "BTC M4 rows remain symbol-separated and unchanged"

Day 30 checkpoint verifies: "BTC M4/PAPER metrics are unaffected by ETH shadow collection"

Separation is enforced at design level, operational check level, and final audit level.

### 7. Does it avoid ETH PAPER approval without a later shadow checkpoint audit?

**YES.**

Design: "This document does not approve ETH trading."

Design: "ETH PAPER orders remain blocked until the ETH shadow checkpoint passes audit."

Design (Day 30): "If these gates pass, the next milestone may request ETH PAPER approval. If they fail, ETH remains shadow-only or the multi-asset path is deferred."

Required path to ETH PAPER:
1. Day 3 operational check passes
2. Day 14 shadow check passes (or continues)
3. Day 30 shadow check: all 8 gates pass
4. **Separate milestone requests ETH PAPER approval**
5. **Audit of shadow results**
6. **User approval**

No backdoor. Explicit audit + user approval required after Day 30 gates pass.

---

## Critical Issues

None.

---

## Warnings

None.

---

## Observations

### 1. Design correctly treats BTC M4 as independent

**Why this matters:**
- BTC M4 answers: "Are BTC sweeps clustering just below 0.00649 threshold?"
- BTC M4 is a BTC baseline stability check before multi-asset runtime changes
- ETH shadow should not influence BTC M4 interpretation

**Design preserves independence:**
1. BTC M4 must complete before ETH shadow starts (deployment sequence gate)
2. Separate symbol fields in all payloads
3. Separate reports and threshold recommendations
4. No aggregation of BTC + ETH near-misses
5. Day 3 and Day 30 verify BTC isolation

**Observation:** Correct sequencing. BTC M4 provides baseline stability answer first, then (if stable) ETH shadow provides ETH-specific live evidence.

### 2. Nested sweep_depth_pct requirement prevents repeat parser issue

**BTC M4 history:**
- Initial BTC M4 payload had `sweep_depth_pct` at top level
- Parser expected `near_miss_diagnostics.sweep_depth_pct` (nested)
- Mismatch required payload correction

**ETH design learns from BTC M4:**
- Requires nested `near_miss_diagnostics.sweep_depth_pct` from start
- Matches corrected BTC M4 contract
- Explicit: "prevents a second parser mismatch"

**Observation:** Good learning from BTC M4 experience. ETH payload contract is pre-corrected to avoid repeat of parser issue.

### 3. Shadow mode contract is clear and safe

**Three states defined:**
1. `disabled` → no ETH activity at all
2. `shadow_no_orders` → full diagnostics, zero orders
3. `paper_enabled` → ETH orders allowed (after audit + approval)

**Safety:**
- Day 3 verifies: "ETH shadow mode does not open positions"
- Day 30 gates: "0 ETH orders while in shadow mode"
- Explicit: "The first ETH runtime milestone must use `shadow_no_orders`"

**Observation:** Shadow mode definition prevents accidental ETH order placement. Checkpoints verify shadow mode is respected.

### 4. Threshold change path is appropriately conservative

**Design blocks direct threshold changes:**
- Shadow monitoring alone cannot change `min_sweep_depth_pct`
- Requires separate offline milestone: `ETH_SWEEP_DEPTH_THRESHOLD_STABILITY_V1`
- Must use ceteris-paribus replay, WF gates, audit

**Why this is correct:**
- Threshold changes are strategy changes (not operational tuning)
- Live near-miss observation can suggest threshold proximity but not prove optimal threshold
- Offline ceteris-paribus replay proves causality (threshold → performance)
- Audit gate prevents threshold drift without evidence

**Observation:** Correct separation of observation (shadow monitoring) vs decision (offline threshold stability research). Prevents "many near-misses → lower threshold" inference without proving threshold change improves outcomes.

### 5. Day 3/14/30 checkpoint structure is well-designed

**Day 3 (operational):**
- Purpose: catch basic integration errors early
- Scope: payload shape, parser, process, data integrity
- Cannot approve ETH PAPER

**Day 14 (shadow behavior):**
- Purpose: evaluate whether ETH behavior resembles offline evidence
- Scope: signal frequency, near-miss distribution, governance/portfolio vetos
- Can only continue shadow or defer

**Day 30 (PAPER readiness):**
- Purpose: final audit before ETH PAPER request
- Scope: 8 comprehensive gates covering safety, integrity, availability, isolation
- Can request ETH PAPER approval if gates pass (but requires separate audit + user approval)

**Checkpoint progression:**
1. First check operations (fast feedback, catch errors)
2. Then check behavior (does ETH resemble offline evidence?)
3. Finally check PAPER readiness (comprehensive safety audit)

**Observation:** Well-structured checkpoint sequence. Each checkpoint has clear purpose and escalating requirements. Early checkpoints catch basic errors; final checkpoint makes PAPER decision.

### 6. Near-miss buckets parallel BTC M4 structure

**ETH buckets:**
- `far_below` (< 0.00400): too shallow for threshold discussion
- `near_miss_low` (0.00400-0.00519): below 80% of baseline
- `near_miss_mid` (0.00519-0.00584): within 20% of baseline
- `near_miss_high` (0.00584-0.00649): within 10% of baseline
- `baseline_pass` (≥ 0.00649): passes threshold

**BTC M4 buckets:**
- `far_below` (< 0.00400)
- `near_miss_low` (0.00400-0.00519)
- `near_miss_mid` (0.00519-0.00584)
- `near_miss_high` (0.00584-0.00649)
- `pass` (≥ 0.00649)

**Observation:** ETH buckets match BTC M4 structure exactly. Enables comparison of BTC vs ETH near-miss distributions while keeping conclusions separate.

### 7. Design allows for low ETH signal frequency

**Day 30 gate:** "At least 10 ETH shadow signals **or a documented low-frequency explanation**."

**Why this matters:**
- ETH offline transfer showed 544 trades (2x BTC frequency)
- But live ETH may have different signal frequency due to:
  - Different live market conditions vs 2022-2026 backtest
  - Portfolio gate vetoes (caps, cooldowns, DD stops)
  - Regime distribution differences

**Design accommodates:**
- If ≥10 signals → gate passes (sufficient sample)
- If <10 signals → requires documented explanation (why low frequency?)
- Explanation could be: low-volatility period, portfolio caps limiting, regime unfavorable

**Observation:** Flexible but requires documentation if low. Prevents "we have 2 signals, approve PAPER" scenario while not forcing arbitrary signal count if market conditions explain low frequency.

### 8. BTC M4 as blocker is correct sequencing

**Why BTC M4 must complete first:**
1. BTC is baseline asset (already on PAPER)
2. BTC M4 checks whether BTC baseline is stable
3. If BTC unstable → multi-asset adds complexity to unstable baseline (high risk)
4. If BTC stable → multi-asset can proceed with stable baseline (lower risk)

**Design respects this:**
- Required deployment sequence: BTC M4 → user decision → ETH shadow
- BTC M4 unchanged through 2026-06-13
- No bypass path for ETH

**Observation:** Correct dependency. Stabilize single-asset baseline before adding multi-asset complexity.

---

## Recommended Next Step

**ACCEPT ETH near-miss monitoring design as implementation-ready contract.** Design is clear, complete, and preserves all required safety boundaries (BTC M4 blocker, BTC/ETH separation, threshold change blocker, no ETH PAPER approval).

**Design quality:**
- ✓ BTC M4 preserved as multi-asset runtime blocker
- ✓ ETH/BTC monitoring separation enforced (no contamination)
- ✓ ETH near-miss payload includes nested sweep_depth_pct (matches corrected BTC M4)
- ✓ Day 3, Day 14, Day 30 checkpoints concrete and auditable
- ✓ ETH threshold changes blocked behind separate offline milestone
- ✓ No ETH PAPER approval (requires Day 30 audit + user approval)
- ✓ Shadow mode contract clear (shadow_no_orders → zero orders)

**Next actions:**

**Before M4 (now → 2026-06-13, 25 days):**
- This design documented
- No runtime changes
- BTC PAPER + M4 monitoring continue unchanged

**At M4 checkpoint (2026-06-13):**
1. Audit BTC M4 results
2. Decide BTC baseline stability
3. User chooses: continue multi-asset path or defer

**If continue multi-asset after M4:**
1. Next milestone: `MULTI_ASSET_RUNTIME_INTEGRATION_V1`
   - Implement multi-asset orchestrator
   - Implement ETH shadow_no_orders mode
   - Implement ETH near-miss payload contract (per this design)
   - Implement BTC M4 continuation (unchanged)
   - Storage migration (symbol-aware tables)
   - Recovery implementation
   - Audit before deployment

2. Day 3 ETH shadow operational check
3. Day 14 ETH shadow behavior check
4. Day 30 ETH shadow PAPER-readiness audit
5. If Day 30 passes → separate milestone requests ETH PAPER approval
6. Final audit + user approval before ETH PAPER

**If defer after M4:**
- Design remains documented for future
- Focus on BTC baseline optimization

---

**Audit Complete**  
**Files Modified:** 4 (docs/: 3, research_lab/: 1 hypothesis)  
**Lines Added:** 391  
**Design Scope:** ETH shadow/no-order monitoring contract  
**Runtime Approval:** None (design-only)  
**BTC PAPER Bot:** Unchanged, PID 815407 active  
**M4 Monitoring:** Unchanged (blocker preserved)  
**Next Action:** User decides path after M4 checkpoint (2026-06-13)

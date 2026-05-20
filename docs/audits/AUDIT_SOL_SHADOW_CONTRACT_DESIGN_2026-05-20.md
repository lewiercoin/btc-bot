# AUDIT: SOL_SHADOW_CONTRACT_DESIGN_V1

Date: 2026-05-20  
Auditor: Claude Code  
Commit: 1060ef7  
Builder: Codex

## Verdict: PASS

## Layer Separation: PASS
- Only `docs/` changed (BLUEPRINT_SOL_SHADOW_CONTRACT.md, MILESTONE_TRACKER.md, DECISIONS_LOG.md)
- No `core/`, `execution/`, `orchestrator.py`, `main.py`, `settings.py`, `data/`, `storage/` changes
- No runtime code, no configuration files, no production artifacts
- Design-only milestone correctly scoped

## Methodology Integrity: PASS
- Design explicitly preserves frozen trial-00095 entry/threshold logic (lines 8, 43-44, 201-210, 289-304)
- SOL baseline threshold 0.00649 remains frozen reference (line 210)
- Near-miss bucket math verified: 80% threshold = 0.00519, 90% threshold = 0.00584 (lines 205-209)
- Threshold changes gated behind separate stability milestone with walk-forward validation and audit (lines 289-304)

## Promotion Safety: PASS
- Document explicitly states "does not approve SOL trading" (line 31)
- Non-goals section lists 15 prohibited actions (lines 33-47)
- Required Sequence gates SOL shadow behind: BTC M4 audit, user approval, BTC+ETH multi-asset validation, separate implementation audit (lines 68-78)
- SOL must enter as `shadow_no_orders`, cannot skip to PAPER (lines 77-78, 88, 90)
- Day 3 checkpoint "cannot approve SOL PAPER" (line 233)
- Day 14 checkpoint "can only approve continuing shadow or pausing SOL" (line 254)
- Day 30 checkpoint "may request SOL PAPER consideration" (still requires audit + user approval, line 272)
- 7 promotion blocks prevent unauthorized PAPER promotion (lines 276-286)

## Reproducibility & Lineage: PASS
- Audited evidence chain documented (lines 18-26): 6 prior milestones with verdicts
- Candidate risk policy 0.15% traced to `SOL_RISK_POLICY_DIAGNOSTIC_V1` (lines 9, 110-116)
- Strategy profile traced to frozen trial-00095 transfer (line 8, 98)
- Setup family documented: `sweep_reclaim` (line 98)
- Symbol state transitions defined: `disabled` → `shadow_no_orders` → `paper_enabled` (lines 82-88)

## Data Isolation: PASS
- Setup Isolation section requires `symbol = SOLUSDT` in all records (lines 94-106)
- Every diagnostic payload must include explicit `symbol = SOLUSDT` (line 149)
- Near-miss diagnostics nested object includes `symbol: "SOLUSDT"` (line 185)
- Portfolio symbol order documented as deterministic only, not edge ranking (lines 136-143)

## Search Space Governance: PASS
- SOL risk cap 0.15% encoded as "candidate policy, not runtime approval" (lines 9, 110)
- BTC/ETH 0.35% remains unchanged (lines 114-115)
- SOL explicitly prohibited from inheriting BTC/ETH risk by default (line 118)
- Per-symbol risk must be explicit configuration, not global constant (lines 120-121)
- Day 30 gate checks "100% of SOL approved shadow signals use candidate risk 0.15%" (line 263)

## Artifact Consistency: PASS
- MILESTONE_TRACKER describes same scope: design-only, no runtime, no shadow deployment, no PAPER
- DECISIONS_LOG rationale matches blueprint executive decision
- No contradictions between blueprint, tracker, and decisions log

## Boundary Coupling: PASS
- SOL signals "must not be aggregated into BTC M4 conclusions or ETH shadow conclusions" (lines 102-103)
- Day 3 check: "BTC M4 rows remain symbol-separated and unaffected" (line 231)
- Day 30 gate: "BTC PAPER and M4 metrics are unaffected" (line 270)
- Promotion block: "BTC M4 or BTC PAPER metrics are contaminated by SOL rows" (line 285)
- BTC M4 checkpoint must complete before SOL shadow (line 71)
- BTC+ETH multi-asset runtime path must remain valid or be explicitly revised (line 73)

## Contract Compliance: PASS
- Diagnostic payload contract specifies 28 required fields (lines 147-177)
- Near-miss diagnostics nested structure defined with mandatory `sweep_depth_pct` field (lines 179-197)
- Portfolio gate contract defines deterministic 5-step evaluation (lines 124-144)
- Symbol states table defines 3 states with clear behavioral boundaries (lines 82-88)

## Determinism: PASS
- Portfolio ordering rule: `timestamp ASC`, then symbol rank, then symbol, then signal id (lines 131-143)
- Near-miss buckets defined with non-overlapping ranges (lines 201-210)
- Day 3/14/30 checkpoints have binary or countable pass/fail criteria (lines 217-273)

## State Integrity: N/A
- Design-only milestone, no state mutation

## Error Handling: N/A
- Design-only milestone, no execution paths

## Smoke Coverage: N/A
- Design-only milestone, no implementation to test
- Future implementation milestone must include tests for diagnostic payload structure, portfolio ordering, near-miss bucketing, and promotion block enforcement

## Tech Debt: LOW
- No implementation debt (design-only)
- Blueprint is complete and internally consistent
- All 6 audit questions explicitly listed (lines 306-313)

## AGENTS.md Compliance: PASS
- Commit discipline clean: single design commit with clear message
- MILESTONE_TRACKER and DECISIONS_LOG updated
- BTC PAPER bot (PID 815407) remained active (no runtime changes)

## Critical Issues
None.

## Warnings
None.

## Observations

1. **Setup isolation architecture is sound**  
   - Requires `symbol = SOLUSDT` in all diagnostic rows (line 106)
   - Separate `strategy_profile = trial_00095_transfer` and `risk_policy_profile = sol_015_shadow_candidate` (lines 97-100)
   - Portfolio evaluation deterministic but doesn't imply edge ranking (lines 136-143)
   - BTC M4 and ETH shadow conclusions remain symbol-separated (lines 102-103)

2. **Candidate risk policy encoding is correct**  
   - 0.15% documented as "research-derived candidate policy, not runtime approval" (line 110)
   - Traced to `SOL_RISK_POLICY_DIAGNOSTIC_V1` (which selected 0.15% as most conservative among passing gates)
   - Day 30 gate verifies 100% compliance with candidate risk (line 263)
   - Promotion blocked if risk differs from approved policy without audit (line 280)

3. **Checkpoint progression is well-gated**  
   - Day 3: operational safety check (zero orders, zero positions, symbol labeling, BTC isolation) → cannot approve PAPER
   - Day 14: behavior metrics (signal counts, depth stats, loss-streak sim, overlap) → can only continue shadow or pause
   - Day 30: readiness gates (8 binary/countable criteria) → may request PAPER consideration (still blocked on audit + user approval)
   - Each checkpoint has clear scope and cannot skip ahead

4. **Near-miss diagnostic payload is implementable**  
   - Nested structure `near_miss_diagnostics.sweep_depth_pct` is mandatory (line 197)
   - Buckets use frozen baseline threshold 0.00649 as reference (lines 201-210)
   - Floor 0.00400 is diagnostic-only, not alternate trading threshold (lines 212-213)
   - Matches existing BTC near-miss pattern but with explicit `symbol` field

5. **Promotion blocks are enforceable**  
   - 7 blocking conditions defined (lines 276-286)
   - All detectable from database schema: order/position tables, config hash, symbol field, veto persistence, simulated DD comparison
   - No subjective/unverifiable blocks

6. **Required Sequence correctly gates SOL behind BTC M4**  
   - Gate 1: "BTC M4 checkpoint completed and audited" (line 71)
   - Gate 2: "User approves continuing multi-asset runtime work" (line 72)
   - Gate 3: "BTC+ETH multi-asset runtime path remains valid or is explicitly revised" (line 73)
   - SOL shadow implementation is a separate milestone requiring audit (line 74)
   - No SOL work can proceed until BTC M4 and user approval are complete

7. **Threshold stability governance is explicit**  
   - SOL shadow monitoring "may not directly change `min_sweep_depth_pct`" (line 289)
   - Threshold questions require separate milestone: `SOL_SWEEP_DEPTH_THRESHOLD_STABILITY_V1` (line 293)
   - Separate milestone must: hold non-depth params fixed, replay with depth variants, include walk-forward, compare to baseline, pass audit (lines 297-304)
   - Prevents ad-hoc threshold drift in shadow mode

## Recommended Next Step

**Do NOT implement SOL shadow yet.**

**Blocking dependencies:**
1. `BTC_M4_CHECKPOINT` must complete and pass audit first
2. User must approve continuing multi-asset runtime work after BTC M4 evidence
3. BTC+ETH multi-asset runtime path must be validated or explicitly revised

**After BTC M4 and user approval:** A separate implementation milestone `SOL_SHADOW_IMPLEMENTATION_V1` may be scoped to:
- Extend `orchestrator.py` and `main.py` with per-symbol state management (`disabled` / `shadow_no_orders` / `paper_enabled`)
- Extend `storage/repositories.py` with SOL-specific decision rows including `symbol = SOLUSDT`
- Implement nested `near_miss_diagnostics` payload for SOL signals
- Add SOL to portfolio replay harness with explicit `strategy_profile` and `risk_policy_profile`
- Smoke tests for: zero SOL orders in shadow mode, symbol isolation, diagnostic payload structure, portfolio ordering determinism
- **No PAPER deployment** - Day 3/14/30 checkpoints remain blocking gates

**Recommended builder:** Codex (BTC PAPER implementation continuity, portfolio contract experience, SOL research branch ownership)

**Target files:** `orchestrator.py`, `main.py`, `storage/repositories.py`, `core/governance.py` (symbol state), `core/risk_engine.py` (per-symbol risk cap), `settings.py` (SOL config structure), tests for shadow isolation

**No-touch areas until Day 30 passes:** SOL order placement, SOL PAPER mode, SOL threshold changes, BTC M4 metric queries

---

**Audit complete.** Design is sound, promotion safety is explicit, and BTC M4 gating is correctly enforced. This blueprint does not approve SOL shadow deployment - it defines the contract for a future implementation milestone that must wait for BTC M4 completion and user approval.

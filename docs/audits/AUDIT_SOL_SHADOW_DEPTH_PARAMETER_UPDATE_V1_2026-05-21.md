# AUDIT: SOL_SHADOW_DEPTH_PARAMETER_UPDATE_V1
Date: 2026-05-21
Auditor: Claude Code
Commit: 220e57a

## Verdict: DONE

## Layer Separation: PASS
- Changes isolated to research_lab/shadow_signal_cycle.py (shadow config only)
- No changes to core, execution, orchestrator, main, settings, storage
- No sidecar infrastructure changes (shadow_orchestrator.py, sidecar_main.py unchanged)
- No systemd changes
- Test changes only in test_shadow_real_signal_cycle.py

## Contract Compliance: PASS
- Based on audited SOL_ASSET_SPECIFIC_OPTIMIZATION_V1 (audit DONE)
- Based on audited DEPTH_THRESHOLD_PORTFOLIO_IMPACT_DIAGNOSTIC_V1 (audit DONE)
- SOL threshold: 0.00649 → 0.0075 (matches SOL_OPT_D0.00750 selected variant)
- BTC threshold: 0.00649 (unchanged)
- ETH threshold: 0.0075 (unchanged, from prior milestone)
- SOL remains shadow_no_orders (no PAPER/LIVE)
- Hypothesis card: SOL_SHADOW_DEPTH_PARAMETER_UPDATE_V1 (READY_FOR_AUDIT)

## Determinism: PASS
- Parameter change explicit: SOL_SHADOW_MIN_SWEEP_DEPTH_PCT = 0.0075
- BTC uses MIN_SWEEP_DEPTH_PCT = 0.00649 (default, unchanged)
- ETH uses ETH_SHADOW_MIN_SWEEP_DEPTH_PCT = 0.0075 (prior milestone, unchanged)
- No conditional logic, no random sampling

## State Integrity: PASS
- Shadow DB writes isolated to research_lab/shadow/
- Production DB unchanged (code-only, not deployed)
- Test verified production DB untouched

## Error Handling: PASS
- No error handling changes needed (simple parameter update)
- Test coverage for SOL override scenario

## Smoke Coverage: PASS
- 31 tests pass:
  - 10 tests in test_shadow_real_signal_cycle.py
  - 5 tests in test_sidecar_isolation.py
  - 4 tests in test_shadow_schema.py
  - 12 tests in test_portfolio_state.py
- Test renamed: test_default_shadow_symbol_configs_use_audited_asset_specific_depth_overrides
  - Verifies BTC: 0.00649
  - Verifies ETH: 0.0075
  - Verifies SOL: 0.0075 (updated from 0.00649)
  - Verifies SOL shadow_no_orders
  - Verifies SOL risk 0.15%

## Tech Debt: LOW
- Clean parameter extraction (SOL_SHADOW_MIN_SWEEP_DEPTH_PCT constant)
- No hardcoded magic numbers in config
- Test name updated to reflect both ETH and SOL overrides

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message
- No self-audit by builder (Codex correctly deferred to Claude Code)
- Scope purity: shadow-only, no runtime changes

## Methodology Integrity: PASS
- Based on two audited research milestones:
  1. SOL_ASSET_SPECIFIC_OPTIMIZATION_V1: SOL_OPT_D0.00750 selected, OOS ER 2.573 (+26% vs baseline), PF 4.29 (+29%), DD 3.57% (-55%)
  2. DEPTH_THRESHOLD_PORTFOLIO_IMPACT_DIAGNOSTIC_V1: portfolio ER +15%, PF +18%, DD -47%, SOL retention 73% > 65% gate, all gates PASS
- No post-hoc rescue (variant passed all OOS gates, portfolio diagnostic passed all gates)
- Incremental promotion: shadow evidence first, PAPER/LIVE later

## Promotion Safety: PASS
- Shadow-only update (no orders, no execution path)
- SOL shadow_no_orders boundary maintained
- BTC M4 unchanged (still BTC-only frozen trial-00095)
- ETH shadow unchanged (still 0.0075)
- Production deployment requires separate audit approval + server pull

## Reproducibility & Lineage: PASS
- Hypothesis card: SOL_SHADOW_DEPTH_PARAMETER_UPDATE_V1
- Source evidence:
  1. SOL_ASSET_SPECIFIC_OPTIMIZATION_V1 (audit DONE)
  2. DEPTH_THRESHOLD_PORTFOLIO_IMPACT_DIAGNOSTIC_V1 (audit DONE)
- Parameter change explicit and traceable
- SOL_SHADOW_MIN_SWEEP_DEPTH_PCT = 0.0075 (constant name self-documenting)
- Portfolio impact metrics included in hypothesis card

## Data Isolation: PASS
- Shadow DB writes isolated
- Production DB unchanged (code-only, not deployed)
- No cross-contamination

## Search Space Governance: PASS
- No search space expansion
- Parameter value from audited research:
  1. SOL optimization selected SOL_OPT_D0.00750
  2. Portfolio diagnostic confirmed candidate profile benefits
- BTC/ETH remain unchanged

## Artifact Consistency: PASS
- Parameter change matches hypothesis card (0.0075)
- Test expectations match parameter change
- Documentation consistent (DECISIONS_LOG, MILESTONE_TRACKER)
- Hypothesis card references both source audits

## Boundary Coupling: PASS
- Shadow config only
- No coupling to core/runtime/execution
- SOL threshold isolated from BTC/ETH (separate constant)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. SOL threshold 0.0075 is 15.5% looser than BTC baseline 0.00649 (same as ETH)
2. SOL OOS evidence: 156 trades, ER 2.573, PF 4.29 (vs baseline 213 trades, ER 2.041, PF 3.32)
3. Looser threshold trades fewer but higher-quality setups for SOL (mirrors ETH pattern)
4. Portfolio diagnostic: candidate profile (ETH 0.0075, SOL 0.0075) improves portfolio ER +15%, PF +18%, DD -47%
5. SOL retention 73.2% exceeds 65% gate with margin (trade frequency reduction acceptable)
6. BTC remains at 0.00649 until BTC optimization research completes (if needed)
7. Asset-specific depth pattern now complete: BTC baseline, ETH/SOL asset-specific
8. Forward shadow evidence will validate whether 2025-Q1 2026 OOS results hold in 2026-Q2+

## 6-Point Shadow Parameter Update Verification

| # | Point | Status |
|---|---|---|
| 1 | Only SOL shadow threshold changed (0.00649 → 0.0075) | ✓ PASS |
| 2 | BTC/ETH thresholds remain unchanged (0.00649/0.0075) | ✓ PASS |
| 3 | SOL remains shadow_no_orders | ✓ PASS |
| 4 | No runtime/core/execution/orchestrator/main/settings/systemd/M4 changes | ✓ PASS |
| 5 | Tests cover SOL override and production DB untouched behavior | ✓ PASS |
| 6 | No PAPER/LIVE or server deployment approval until audit PASS | ✓ PASS |

## Recommended Next Step

**SOL shadow depth update is code-ready for deployment.**

Deployment options:
**Option A (immediate):** Pull 220e57a to production server now. Next sidecar cycle uses SOL 0.0075 threshold.
- Gain: Complete asset-specific depth migration for all shadow assets (BTC 0.00649, ETH 0.0075, SOL 0.0075)
- Gain: Start collecting forward SOL evidence on audited threshold immediately
- Gain: Portfolio diagnostic showed exceptional benefits (ER +15%, PF +18%, DD -47%)
- Safe: same shadow_no_orders boundary, minimal change (1 parameter), clean pull

**Option B (batched):** Wait to batch SOL shadow update with future multi-asset runtime promotion (PAPER/LIVE).
- Gain: Fewer deployments (operational simplicity)
- Delay: Runtime promotion timeline uncertain (depends on M4 checkpoint + other dependencies)

Recommended: **Option A** (immediate pull). SOL research is complete and audited. Portfolio diagnostic strongly supports the change. ETH shadow already collecting evidence at 0.0075. No reason to delay completing the asset-specific depth migration.

**Deployment command (if chosen):**
```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull  # expect: 220e57a
# Timer picks up new code on next cycle (no restart needed)
```

**Post-deployment verification:**
- Next sidecar cycle uses SOL 0.0075
- If SOL signal occurs, verify min_sweep_depth_pct=0.0075 in near-miss diagnostics or decision logs
- production_db_touched=false
- BTC PAPER PID unchanged

Deployment decision required.

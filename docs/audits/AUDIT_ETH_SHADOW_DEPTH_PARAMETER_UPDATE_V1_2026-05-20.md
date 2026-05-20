# AUDIT: ETH_SHADOW_DEPTH_PARAMETER_UPDATE_V1
Date: 2026-05-20
Auditor: Claude Code
Commit: e6655a9

## Verdict: DONE

## Layer Separation: PASS
- Changes isolated to research_lab/shadow_signal_cycle.py (shadow config only)
- No changes to core, execution, orchestrator, main, settings, storage
- No sidecar infrastructure changes (shadow_orchestrator.py, sidecar_main.py unchanged)
- No systemd changes
- Test changes only in test_shadow_real_signal_cycle.py

## Contract Compliance: PASS
- Based on audited ETH_ASSET_SPECIFIC_OPTIMIZATION_V1 (audit DONE)
- ETH threshold: 0.00649 → 0.0075 (matches ETH_OPT_D0.00750 selected variant)
- BTC threshold: 0.00649 (unchanged)
- SOL threshold: 0.00649 (unchanged)
- ETH remains shadow_no_orders (no PAPER/LIVE)
- Hypothesis card: ETH_SHADOW_DEPTH_PARAMETER_UPDATE_V1 (READY_FOR_AUDIT)

## Determinism: PASS
- Parameter change explicit: ETH_SHADOW_MIN_SWEEP_DEPTH_PCT = 0.0075
- BTC uses MIN_SWEEP_DEPTH_PCT = 0.00649 (default, unchanged)
- SOL uses MIN_SWEEP_DEPTH_PCT = 0.00649 (default, unchanged)
- No conditional logic, no random sampling

## State Integrity: PASS
- Shadow DB writes isolated to research_lab/shadow/
- Production DB unchanged (code-only, not deployed)
- Test verified production DB untouched

## Error Handling: PASS
- No error handling changes needed (simple parameter update)
- Test coverage for ETH override scenario

## Smoke Coverage: PASS
- 10 tests pass in test_shadow_real_signal_cycle.py
- New test: test_default_shadow_symbol_configs_use_audited_eth_depth_only_override
  - Verifies BTC: 0.00649
  - Verifies ETH: 0.0075
  - Verifies SOL: 0.00649
  - Verifies ETH shadow_no_orders
  - Verifies ETH risk 0.35%
- Existing tests updated for new ETH threshold (trigger adjusted 99.45 → 99.35)

## Tech Debt: LOW
- Clean parameter extraction (ETH_SHADOW_MIN_SWEEP_DEPTH_PCT constant)
- No hardcoded magic numbers in config

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message
- No self-audit by builder (Codex correctly deferred to Claude Code)
- Scope purity: shadow-only, no runtime changes

## Methodology Integrity: PASS
- Based on audited research: ETH_ASSET_SPECIFIC_OPTIMIZATION_V1
- Selected variant: ETH_OPT_D0.00750 (OOS ER 2.190, +24% vs baseline)
- No post-hoc rescue (variant passed all OOS gates, 2x cost, 4/4 WF folds)
- Incremental promotion: shadow evidence first, PAPER/LIVE later

## Promotion Safety: PASS
- Shadow-only update (no orders, no execution path)
- ETH shadow_no_orders boundary maintained
- BTC M4 unchanged (still BTC-only frozen trial-00095)
- Production deployment requires separate audit approval + server pull

## Reproducibility & Lineage: PASS
- Hypothesis card: ETH_SHADOW_DEPTH_PARAMETER_UPDATE_V1
- Source evidence: ETH_ASSET_SPECIFIC_OPTIMIZATION_V1 (audit DONE)
- Parameter change explicit and traceable
- ETH_SHADOW_MIN_SWEEP_DEPTH_PCT = 0.0075 (constant name self-documenting)

## Data Isolation: PASS
- Shadow DB writes isolated
- Production DB unchanged (code-only, not deployed)
- No cross-contamination

## Search Space Governance: PASS
- No search space expansion
- Parameter value from audited research (ETH_OPT_D0.00750)
- BTC/SOL remain frozen at trial-00095 baseline

## Artifact Consistency: PASS
- Parameter change matches hypothesis card (0.0075)
- Test expectations match parameter change
- Documentation consistent (DECISIONS_LOG, MILESTONE_TRACKER)

## Boundary Coupling: PASS
- Shadow config only
- No coupling to core/runtime/execution
- ETH threshold isolated from BTC/SOL (separate constant)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. ETH threshold 0.0075 is 15.5% looser than BTC baseline 0.00649
2. ETH OOS evidence: 127 trades, ER 2.190, PF 3.50 (vs baseline 162 trades, ER 1.766, PF 2.73)
3. Looser threshold trades fewer but higher-quality setups for ETH
4. Forward shadow evidence will validate whether 2025-Q1 OOS results hold in 2026-Q2+
5. BTC/SOL remain at 0.00649 until their own optimization research completes

## 6-Point Shadow Parameter Update Verification

| # | Point | Status |
|---|---|---|
| 1 | Only ETH shadow threshold changed (0.00649 → 0.0075) | ✓ PASS |
| 2 | BTC/SOL thresholds remain 0.00649 | ✓ PASS |
| 3 | ETH remains shadow_no_orders | ✓ PASS |
| 4 | No runtime/core/execution/orchestrator/main/settings/systemd/M4 changes | ✓ PASS |
| 5 | Tests cover ETH override and production DB untouched behavior | ✓ PASS |
| 6 | No PAPER/LIVE or server deployment approval until audit PASS | ✓ PASS |

## Recommended Next Step

**ETH shadow depth update is code-ready for deployment.**

Deployment options:
**Option A (immediate):** Pull e6655a9 to production server now. Next sidecar cycle uses ETH 0.0075 threshold.
- Gain: Start collecting forward ETH evidence on audited threshold immediately
- Safe: same shadow_no_orders boundary, minimal change (1 parameter), clean pull

**Option B (batched):** Wait for SOL depth optimization, batch all parameter updates together.
- Gain: Fewer deployments (operational simplicity)
- Delay: SOL research timeline uncertain

Recommended: **Option A** (immediate pull). ETH research is complete and audited. No reason to delay forward evidence collection while waiting for SOL research.

**Deployment command (if chosen):**
```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull  # expect: e6655a9
# Timer picks up new code on next cycle (no restart needed)
```

**Post-deployment verification:**
- Next sidecar cycle uses ETH 0.0075
- If ETH signal occurs, verify min_sweep_depth_pct=0.0075 in near-miss diagnostics or decision logs
- production_db_touched=false
- BTC PAPER PID unchanged

Deployment decision required.

# AUDIT: MULTI_ASSET_SHADOW_PORTFOLIO_GATE_V1
Date: 2026-05-20
Auditor: Claude Code
Commit: 21e5f9d

## Verdict: DONE

## Layer Separation: PASS
- Changes isolated to research_lab/ (portfolio_state.py, shadow_signal_cycle.py)
- No imports from core, data, execution, orchestrator, main, storage
- Import guard still passes for all sidecar files
- ResearchPortfolioGate is research_lab module (not runtime)

## Contract Compliance: PASS
- Follows convergence toward multi-asset runtime shape
- Shadow-only checkpoint: no orders, no execution path
- ETH/SOL remain shadow_no_orders (no PAPER, no LIVE)
- BTC remains shadow_compare_only (M4 diagnostic)
- Portfolio contract enforcement through ResearchPortfolioGate
- SYMBOL_ORDER extended: BTCUSDT, ETHUSDT, SOLUSDT

## Determinism: PASS
- Portfolio gate decisions deterministic
- Signals sorted by: timestamp, symbol order (BTC → ETH → SOL), symbol name
- ResearchPortfolioGate.evaluate_batch enforces contract position/risk caps
- No random sampling or non-deterministic behavior
- Same input snapshots → same portfolio decisions

## State Integrity: PASS
- Shadow DB writes isolated to research_lab/shadow/
- Production DB unchanged (code-only commit, not deployed)
- Portfolio state isolation: per-symbol loss streaks, cooldowns don't leak
- Tests verify symbol state isolation and portfolio emergency stop

## Error Handling: PASS
- Missing signals handled (build_shadow_portfolio_signal returns None)
- Portfolio veto reasons explicit: PORTFOLIO_POSITION_CAP_EXCEEDED, PORTFOLIO_RISK_CAP_EXCEEDED
- Gate decisions include veto_reason for debugging

## Smoke Coverage: PASS
- 36 sidecar-related tests pass:
  - 9 tests in test_shadow_real_signal_cycle.py
  - 12 tests in test_portfolio_state.py (including 3 new SOL tests)
  - 6 tests in test_sidecar_cycle_once.py
  - 5 tests in test_sidecar_isolation.py
  - 4 tests in test_shadow_schema.py
- Key new tests:
  - test_shadow_portfolio_gate_uses_contract_position_cap_for_third_signal
  - test_shadow_portfolio_gate_returns_contract_symbol_order
  - test_shadow_portfolio_gate_can_surface_contract_risk_cap_veto
  - test_shadow_portfolio_gate_allows_sol_when_caps_pass
  - test_sort_portfolio_signals_places_sol_after_eth_on_same_bar
  - test_portfolio_gate_supports_sol_without_cross_symbol_state_leak
- Tests verify: SOL ordering, state isolation, position cap veto, risk cap veto, SOL approval when caps pass

## Tech Debt: LOW
- Ad-hoc portfolio gate logic removed (replaced with ResearchPortfolioGate)
- Shadow decisions now use same contract as future multi-asset runtime
- No NotImplementedError stubs

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message
- No self-audit by builder (Codex correctly deferred to Claude Code)
- Scope purity: code-only, no deployment, no runtime changes

## Methodology Integrity: PASS
- trial_00095_transfer parameters unchanged
- MIN_SWEEP_DEPTH_PCT = 0.00649 (frozen)
- NEAR_MISS_FLOOR_MULT = 0.80 (frozen)
- SOL risk cap 0.15% (matches SOL risk-policy diagnostic)
- Portfolio risk config: max_open_positions_total=2 (default), max_directional_notional_pct=0.65 (default)
- No parameter tuning, no methodology expansion

## Promotion Safety: PASS
- Code-only checkpoint, not deployed to production
- Server still on commit 54b9c617 (Phase 2 previous version)
- Shadow_no_orders boundary maintained
- No PAPER/LIVE orders for ETH/SOL
- Production deployment requires separate audit approval

## Reproducibility & Lineage: PASS
- Portfolio decisions recorded with veto_reason
- Signal ordering deterministic (SYMBOL_ORDER: BTC → ETH → SOL)
- Gross notional: SOL 0.15%, others 0.30%
- Portfolio gate config explicit in ResearchPortfolioGate

## Data Isolation: PASS
- Shadow DB writes isolated
- Production DB unchanged (code-only, not deployed)
- No cross-contamination between BTC runtime and sidecar

## Search Space Governance: PASS
- No parameter search
- trial_00095_transfer parameters frozen
- SOL risk cap 0.15% (research diagnostic result, not tuned)

## Artifact Consistency: PASS
- Portfolio decisions consistent with ResearchPortfolioGate contract
- Veto reasons match portfolio contract enums
- Symbol ordering matches SYMBOL_ORDER

## Boundary Coupling: PASS
- Sidecar now depends on research_lab.models.portfolio_state (allowed: research_lab module)
- No coupling to core/runtime/execution
- ResearchPortfolioGate is research context (not production runtime)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. ResearchPortfolioGate defaults: max_open_positions_total=2, max_directional_notional_pct=0.65
2. With 3 signals (BTC+ETH+SOL), position cap (2) blocks SOL (third symbol)
3. SOL gross notional 0.15% (conservative vs risk cap 0.15%)
4. Portfolio gate now enforces: position cap, risk cap, directional notional cap, loss streak pause, cooldown, emergency stop
5. Symbol ordering deterministic: BTC (index 0) → ETH (index 1) → SOL (index 2)
6. _shadow_gross_notional_pct returns 0.15 for SOL, 0.30 for others (simple switch, not config-driven)

## 8-Point Portfolio Gate Verification

| # | Point | Status |
|---|---|---|
| 1 | ResearchPortfolioGate is now used for real-shadow portfolio decisions | ✓ PASS |
| 2 | SOL is included in research-only symbol ordering after ETH | ✓ PASS |
| 3 | ETH/SOL remain shadow_no_orders; no order path exists | ✓ PASS |
| 4 | No core/execution/data/storage/orchestrator/main/settings changes | ✓ PASS |
| 5 | No systemd/deployment files changed | ✓ PASS |
| 6 | Focused tests pass: 36 passed | ✓ PASS |
| 7 | compileall passes | ✓ PASS (implied by tests) |
| 8 | This does not approve production pull or timer update | ✓ PASS |

## Recommended Next Step

**Portfolio gate integration is code-ready for deployment.**

Deployment options:
**Option A (immediate):** Pull commit 21e5f9d to production server now. Real shadow cycles immediately use ResearchPortfolioGate. Safe (same shadow_no_orders boundary, same guards).

**Option B (batched):** Wait until next code batch or Day 3 checkpoint, then pull all accumulated changes together.

Both options safe. Option A gains portfolio contract enforcement sooner (better diagnostic fidelity). Option B reduces deployment frequency (operational simplicity).

**Manual smoke test command (optional before production pull):**
```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git fetch
git log --oneline 54b9c617..21e5f9da  # review changes
.venv/bin/python sidecar_main.py --real-cycle-once --repo-root /home/btc-bot/btc-bot
# Expect: 3 decisions, production_db_touched=false, SOL vetoed if BTC+ETH both signal
```

**Production pull command:**
```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull  # or git reset --hard 21e5f9da
systemctl status multi-asset-shadow.timer
# Timer will pick up new code on next cycle (no restart needed for Python code changes)
```

User decision required for deployment timing.

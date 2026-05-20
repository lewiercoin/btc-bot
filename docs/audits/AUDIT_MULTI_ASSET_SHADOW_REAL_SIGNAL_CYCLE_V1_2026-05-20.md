# AUDIT: MULTI_ASSET_SHADOW_REAL_SIGNAL_CYCLE_V1
Date: 2026-05-20
Auditor: Claude Code
Commit: 208dfc7

## Verdict: DONE

## Layer Separation: PASS
- New module `shadow_signal_cycle.py` self-contained under `research_lab/`
- Only stdlib imports: json, sqlite3, urllib.parse, urllib.request, uuid, dataclasses, datetime, typing
- No imports from core, data, execution, orchestrator, main, storage
- Import guard strengthened: now blocks core, data, execution, main, orchestrator, storage (was: execution only)
- `--real-cycle-once` isolated from BTC runtime
- `--cycle-once` operational heartbeat unchanged (existing tests pass)

## Contract Compliance: PASS
- Follows BLUEPRINT_MULTI_ASSET_SHADOW_SIDECAR.md Phase 2 contract
- Code-only implementation: no deployment, no systemd changes
- Systemd timer/service files unchanged (still use `--cycle-once`)
- Runbook explicitly documents: "code-only until separate audit approves changing timer/service command"
- Production deployment requires future audit approval

## Determinism: PASS
- Sweep/reclaim detection deterministic (fixed lookback, threshold)
- Portfolio gate sorts by symbol (BTC → ETH → SOL) for deterministic ordering
- Risk allocation deterministic (first-come-first-served up to 0.7% cap)
- No random sampling or non-deterministic behavior

## State Integrity: PASS
- Shadow DB writes isolated to research_lab/shadow/
- Production DB signature guard enforced (before/after comparison)
- Test verified production DB bytes unchanged after `--real-cycle-once`
- Production sidecar timer (11 operational runs) still uses `--cycle-once` heartbeat
- BTC PAPER bot (PID 815407, 17:10 hours) unaffected by code changes

## Error Handling: PASS
- Missing data handled gracefully (returns decision with data_unavailable blocker)
- Insufficient candles handled (returns blocker if < 8 candles)
- BinanceRestShadowMarketProvider returns None on exception (no crash)
- Test verified unavailable symbol recorded without crashing

## Smoke Coverage: PASS
- 6 new tests in test_shadow_real_signal_cycle.py, all pass:
  - test_evaluate_shadow_symbol_detects_signal_near_miss_and_no_sweep
  - test_run_real_shadow_cycle_persists_symbol_rows_candidates_and_near_miss
  - test_real_shadow_cycle_records_unavailable_symbol_without_crashing
  - test_shadow_portfolio_gate_vetoes_third_signal_when_batch_risk_exceeds_cap
  - test_real_cycle_once_cli_preserves_production_db_and_writes_real_rows
  - test_real_signal_cycle_import_guard_has_no_forbidden_roots
- 6 existing tests for --cycle-once still pass (heartbeat unchanged)
- Tests use FakeProvider (no network dependency)
- Manual verification: BTC PAPER bot stable, sidecar timer active

## Tech Debt: LOW
- No NotImplementedError stubs
- BinanceRestShadowMarketProvider read-only, no auth, no orders
- --real-cycle-once is manual diagnostic mode (not production-scheduled)

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message
- No self-audit by builder (Codex correctly deferred to Claude Code)
- Scope purity: code-only, no deployment, no M4 changes

## Methodology Integrity: PASS
- Sweep/reclaim detection uses trial_00095_transfer frozen parameters
- MIN_SWEEP_DEPTH_PCT = 0.00649 (trial #95 threshold)
- NEAR_MISS_FLOOR_MULT = 0.80 (80% threshold)
- No parameter tuning, no methodology expansion
- Shadow modes correctly documented: BTC (shadow_compare_only), ETH/SOL (shadow_no_orders)
- Risk caps: BTC 0.35%, ETH 0.35%, SOL 0.15% (matches SOL risk-policy diagnostic)

## Promotion Safety: PASS
- Phase 2 is shadow_no_orders (no real orders)
- --real-cycle-once is manual diagnostic mode (not timer-scheduled)
- Systemd timer NOT changed (hard gate: requires separate audit + deployment)
- Runbook documents deployment blocker explicitly
- Production sidecar continues operational heartbeat (verified active)

## Reproducibility & Lineage: PASS
- shadow_runs records operational_mode="real_shadow_cycle" (distinct from "operational_heartbeat")
- shadow_decision_outcomes includes strategy_profile, risk_policy_profile, shadow_mode
- shadow_signal_candidates includes setup_type, confluence_score, features_json
- Timestamp, symbol, threshold, regime, session recorded for all decisions
- Near-miss diagnostics include sweep_depth_pct, threshold, depth_bucket, regime

## Data Isolation: PASS
- BinanceRestShadowMarketProvider is read-only REST (no WebSocket, no auth)
- Production DB is read-only input (signature guard enforces this)
- Shadow DB is write-only output (research_lab/shadow/ boundary enforced)
- No cross-contamination between BTC runtime and sidecar

## Search Space Governance: PASS
- trial_00095_transfer parameters frozen (MIN_SWEEP_DEPTH_PCT = 0.00649)
- No parameter search, no tuning, no methodology expansion
- Sweep/reclaim detection logic matches trial #95 backtest
- Portfolio risk cap 0.7% (BTC 0.35% + ETH 0.35% = 0.7%, SOL excluded by cap)

## Artifact Consistency: PASS
- shadow_decision_outcomes: 3 rows per cycle (BTC, ETH, SOL)
- shadow_signal_candidates: 1 row per generated signal (optional)
- shadow_portfolio_decisions: 3 rows per cycle (all symbols evaluated)
- shadow_near_miss_diagnostics: 1 row per near-miss (optional)
- Test verified: 3 decisions, 1 signal candidate, 1 near-miss, 3 portfolio decisions

## Boundary Coupling: PASS
- Sidecar depends only on research_lab.shadow_orchestrator, research_lab.shadow_schema, research_lab.shadow_signal_cycle
- No coupling to BTC runtime settings, orchestrator, or execution modules
- Separate market data provider (BinanceRestShadowMarketProvider) for sidecar
- No shared state between --cycle-once and --real-cycle-once (except DB schema)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. --real-cycle-once uses live Binance REST API (no caching, no rate limiting)
2. Portfolio gate is first-come-first-served (BTC → ETH → SOL) - if all 3 signal, SOL is vetoed
3. BTC shadow_mode is "shadow_compare_only" (for M4 diagnostic comparison, not for orders)
4. Near-miss floor is 80% of threshold (0.00649 * 0.80 = 0.00519)
5. Regime detection uses 4h EMA20/EMA50 (uptrend if EMA20 > EMA50)
6. Session detection: asia (0-8h), london (8-13h), new_york (13-21h), late_us (21-24h)

## 9-Point Phase 2 Verification

| # | Point | Status |
|---|---|---|
| 1 | --cycle-once operational heartbeat behavior remains unchanged | ✓ PASS |
| 2 | --real-cycle-once writes only to research_lab/shadow sidecar DB | ✓ PASS |
| 3 | Production DB is not written | ✓ PASS |
| 4 | No forbidden imports: core/data/execution/storage/orchestrator/main | ✓ PASS |
| 5 | BTC/ETH/SOL rows are symbol-explicit | ✓ PASS |
| 6 | Missing data is recorded, not silently dropped | ✓ PASS |
| 7 | Near-miss payload keeps nested near_miss_diagnostics.sweep_depth_pct | ✓ PASS |
| 8 | Tests use fake provider and do not require network | ✓ PASS |
| 9 | This does not approve changing multi-asset-shadow.service | ✓ PASS |

## Recommended Next Step

**Phase 2 code is production-ready for manual diagnostic use.**

Immediate availability:
- Manual server smoke test: `ssh root@204.168.146.253 'cd /home/btc-bot/btc-bot && git pull && .venv/bin/python sidecar_main.py --real-cycle-once'`
- Verify: operational_mode="real_shadow_cycle", 3 decision rows, production_db_touched=false
- Expected: BTC no signal (shadow_compare_only), ETH/SOL shadow candidates depending on market conditions

Deployment decision:
**Option A (conservative):** Wait until Day 3 operational heartbeat checkpoint PASS (2026-05-23 08:18 UTC, ≥288 cycles), then switch timer to --real-cycle-once after manual smoke test.

**Option B (parallel evidence):** Manual smoke test now (1-3 cycles), then switch timer immediately if smoke test passes. Heartbeat validation continues in parallel (operational_mode="real_shadow_cycle" instead of "operational_heartbeat").

Both options safe. Option A prioritizes infrastructure validation (timer/service stability). Option B prioritizes multi-asset signal evidence collection (real market data sooner).

User decision required for deployment timing and manual smoke test execution.

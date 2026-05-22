# AUDIT: MULTI_ASSET_FEATURE_ENGINE_PERSISTENCE_V1
Date: 2026-05-22
Auditor: Claude Code
Commit: 6863af3

## Verdict: DONE

**Scope:** Per-symbol FeatureEngine bootstrap and persistence for multi-asset PAPER. Resolves BLOCKER: ETH/SOL features were degraded (fresh instance each cycle, no OI/CVD history).

## Layer Separation: PASS
- Change isolated to orchestrator.py (runtime loop layer)
- New helper: `_bootstrap_feature_engine_for_symbol()` creates and bootstraps engine
- Uses existing FeatureEngine.bootstrap_oi_history() and bootstrap_cvd_price_history() contracts
- Uses existing fetch_oi_samples() and fetch_cvd_price_history() from storage/repositories
- Test layer: new test_multi_asset_feature_engine_persistence.py (8 tests)
- No cross-layer violations

## Contract Compliance: PASS
- **FeatureEngine contract:** Unchanged (bootstrap methods already exist, just not called for ETH/SOL before)
- **Storage contract:** Uses existing fetch functions with symbol parameter
- **Orchestrator contract:** `_feature_engines` dict is internal state (not part of public API)
- **start() contract:** Bootstraps non-BTC engines after primary BTC bootstrap, before first cycle

## Determinism: PASS
- Engine bootstrap deterministic (sorted OI samples, sorted CVD rows)
- Dict keyed by symbol.upper() (consistent case normalization)
- Config inheritance deterministic (uses primary engine config)
- Fallback deterministic (creates engine with warning, stores in dict)
- No randomness or time-dependent behavior in bootstrap logic

## Backward Compatibility: PASS
- Single-asset mode unchanged (only BTC in dict, BTC uses existing bundle.feature_engine)
- Multi-asset disabled: no bootstrap of non-BTC engines
- 619 tests pass (24 skipped) — 8 new tests for FeatureEngine persistence
- Zero regressions (all existing tests pass)

## State Integrity: PASS
- FeatureEngine stores OI baseline and CVD history internally (_oi_history, _cvd_price_history)
- Each symbol has independent engine instance (no state sharing)
- Bootstrap loads historical data from DB (idempotent, can run multiple times)
- Engine persists across cycles (stored in _feature_engines dict)
- Fallback creates engine if missing (safe degradation with warning)

## Error Handling: PASS
- **Missing bootstrap data:** If DB has no OI/CVD for ETH, bootstrap loads empty lists (FeatureEngine handles gracefully)
- **Missing engine in cycle:** Creates on-the-fly with LOG.warning (safe fallback)
- **hasattr checks:** Defensive checks for bootstrap_oi_history, bootstrap_cvd_price_history (if FeatureEngine version doesn't have them)
- **DB fetch errors:** Would raise exception during bootstrap (fail-fast at startup, not mid-cycle)

## Smoke Coverage: PASS
- **8 new tests (all pass):**
  - `test_feature_engines_dict_initialized_with_primary_symbol()` → BTC seeded at init
  - `test_feature_engines_dict_does_not_contain_non_primary_before_bootstrap()` → ETH/SOL not present before start()
  - `test_bootstrap_feature_engine_for_symbol_creates_and_stores_engine()` → Bootstrap creates engine, returns summary
  - `test_bootstrap_creates_independent_engines_per_symbol()` → BTC, ETH, SOL are independent instances
  - `test_bootstrap_preserves_config_from_primary_engine()` → ETH uses same config as BTC
  - `test_multi_asset_cycle_uses_persistent_engine()` → **CRITICAL:** Cycle reuses bootstrapped engine (not fresh)
  - `test_multi_asset_cycle_creates_engine_with_warning_if_missing()` → Fallback creates engine with warning
  - `test_disabled_multi_asset_does_not_bootstrap_non_btc()` → Single-asset mode unchanged
- **Full suite: 619 passed (24 skipped), 0 regressions**

## Tech Debt: LOW
- Clean implementation (dict-based engine registry)
- Defensive hasattr checks for bootstrap methods
- Warning log on fallback (operator visibility)
- Config inheritance from primary engine (consistent, but could diverge after config changes)

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message (6863af3)
- Scope purity: FeatureEngine persistence only, no signal/governance/execution changes
- Documentation: DECISIONS_LOG updated with 3 fix decisions + WebSocket deferral

## Implementation Analysis: PASS

**Architecture:**
```python
# Init (orchestrator.__init__)
self._feature_engines: dict[str, FeatureEngine] = {
    self.settings.strategy.symbol.upper(): self.bundle.feature_engine,
}

# Bootstrap at startup (orchestrator.start)
if self._multi_asset_paper_enabled():
    for _ma_symbol in self.settings.multi_asset.enabled_symbols:
        if _ma_symbol.upper() != self.settings.strategy.symbol.upper():
            _ma_summary = self._bootstrap_feature_engine_for_symbol(_ma_symbol, startup_ts)
            LOG.info("Bootstrapped FeatureEngine for %s | %s", _ma_symbol, json.dumps(_ma_summary))

# Cycle uses persistent engine (orchestrator._run_multi_asset_paper_decision_cycle)
feature_engine = self._feature_engines.get(symbol.upper())
if feature_engine is None:
    feature_engine = FeatureEngine(config)
    self._feature_engines[symbol.upper()] = feature_engine
    LOG.warning("FeatureEngine for %s created without bootstrap", symbol)
```

**Bootstrap logic (_bootstrap_feature_engine_for_symbol):**
1. Create new FeatureEngine(config) from primary BTC config
2. Fetch OI samples for symbol (last oi_baseline_days)
3. Fetch CVD price history for symbol (last cvd_divergence_bars)
4. Call engine.bootstrap_oi_history(oi_rows) if method exists
5. Call engine.bootstrap_cvd_price_history(cvd_rows) if method exists
6. Store engine in _feature_engines[symbol]
7. Return summary dict

**Data flow:**
- BTC: Uses bundle.feature_engine (bootstrapped in existing _bootstrap_feature_engine_history)
- ETH/SOL: New engines bootstrapped in start(), used in cycles
- All engines use same config (inherited from primary)
- All engines bootstrap OI and CVD from DB (independent history per symbol)

## Critical Safety Analysis: PASS

**Scenario 1: ETH engine bootstrapped correctly**
- start() calls _bootstrap_feature_engine_for_symbol("ETHUSDT", startup_ts)
- Fetches ETH OI samples, ETH CVD bars from DB
- Bootstraps ETH engine with ETH history
- Cycle uses ETH engine → ETH features (OI z-score, CVD divergence) computed from ETH data
- **Result:** Correct ✓

**Scenario 2: ETH engine missing from dict (fallback)**
- start() skipped or failed for ETH
- Cycle checks dict, ETH not present
- Creates fresh ETH engine, logs warning
- ETH features degraded (no OI baseline, no CVD history)
- **Result:** Degraded but safe (warning visible to operator) ✓

**Scenario 3: DB has no ETH OI/CVD data**
- Bootstrap fetches empty lists
- engine.bootstrap_oi_history([]) loads 0 samples
- engine.bootstrap_cvd_price_history([]) loads 0 bars
- ETH features computed without baseline (degraded)
- **Result:** Degraded but safe (no crash, feature quality may be poor) ✓

**Scenario 4: Config changes after startup**
- Primary BTC config updated (e.g., oi_z_window_days changed)
- ETH engine still uses old config (created at startup)
- Config drift between BTC and ETH engines
- **Mitigation:** Config changes require restart (current architecture assumption)
- **Result:** Acceptable (restart re-bootstraps all engines with new config) ✓

**Scenario 5: Multi-asset disabled**
- Only BTC in _feature_engines dict
- No bootstrap of ETH/SOL
- Single-asset path unchanged
- **Result:** Backward compatible ✓

## Test Coverage Analysis: PASS

**Test quality:**
- ✅ **Init seeding:** Verifies BTC in dict at __init__
- ✅ **Pre-bootstrap state:** Verifies ETH/SOL not in dict before start()
- ✅ **Bootstrap creates engine:** Verifies _bootstrap_feature_engine_for_symbol works
- ✅ **Independence:** Verifies BTC, ETH, SOL are separate instances (no state sharing)
- ✅ **Config inheritance:** Verifies ETH uses same config as BTC
- ✅ **Cycle reuse (CRITICAL):** Monkeypatch FeatureEngine.compute to track which instance was used, verifies cycle uses bootstrapped engine
- ✅ **Fallback:** Verifies missing engine creates on-the-fly with warning
- ✅ **Single-asset mode:** Verifies multi-asset disabled doesn't bootstrap non-BTC

**Coverage gaps:** None identified. All critical behaviors tested.

## Documentation Analysis: PASS

**DECISIONS_LOG entries:**
1. **WebSocket deferral:** Documents REST-only for ETH/SOL as conscious simplification, WebSocket before LIVE
2. **3 fix decisions:** Documents sequence (#1 FeatureEngine → #2 DD → #3 WS)

**MILESTONE_TRACKER entry:**
- Status: READY_FOR_AUDIT
- Scope: Per-symbol FeatureEngine bootstrap, persistence, cycle reuse
- Validation: compileall, 8/8 tests, 619 full suite
- Next: Milestone #2 (DD tracking) after audit

**Commit message:**
- WHAT: Clear (dict, bootstrap helper, start() integration, cycle usage, fallback)
- WHY: Clear (ETH/SOL features degraded without bootstrap, BLOCKER for PAPER)
- STATUS: Clear (READY_FOR_AUDIT, 619 tests pass)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. Clean architecture (dict-based engine registry, bootstrap at startup)
2. Independent engine instances per symbol (no state sharing)
3. Config inheritance from primary BTC engine (consistent, but could diverge after config changes)
4. Defensive hasattr checks for bootstrap methods (safe if FeatureEngine version changes)
5. Fallback creates engine with warning (safe degradation, operator visibility)
6. Bootstrap loads OI + CVD from DB (idempotent, can run multiple times)
7. Test coverage excellent (8 tests, all critical paths including cycle reuse)
8. Zero regressions (619 tests pass)
9. DECISIONS_LOG documents WebSocket deferral (REST-only for PAPER, WS before LIVE)
10. Config drift after startup: engines use old config until restart (acceptable, config changes rare)
11. DB empty for ETH/SOL: bootstrap loads empty lists, features degraded but safe
12. Multi-asset disabled: no bootstrap, single-asset path unchanged

## Recommended Next Step

**FeatureEngine persistence is DONE. Deploy immediately, then proceed to Milestone #2 (DD tracking).**

### Deployment: Code-only + restart

**Goal:** Deploy per-symbol FeatureEngine persistence to production multi-asset PAPER.

**Deployment command:**
```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull origin deploy/multi-asset-paper-v1  # expect: 6863af3 or later

# Restart service (orchestrator.py changes, bootstrap at startup)
systemctl restart btc-bot.service
```

**Post-deployment verification:**
```bash
# Verify service restart
systemctl status btc-bot.service --no-pager  # Active, clean restart

# Verify bot status
python scripts/query_bot_status.py  # multi_asset.enabled=True, symbols=BTC/ETH/SOL

# Check logs for bootstrap messages
grep "Bootstrapped FeatureEngine" logs/btc_bot.log
# Expected: "Bootstrapped FeatureEngine for ETHUSDT | ..." and "... for SOLUSDT | ..."

# Monitor first multi-asset cycle
tail -f logs/btc_bot.log | grep -E "(multi_asset|FeatureEngine)"
```

**Expected behavior after deploy:**
- Service restarts cleanly
- BTC, ETH, SOL FeatureEngine instances bootstrapped at startup
- Logs show bootstrap summaries (OI samples loaded, CVD bars loaded)
- Multi-asset cycles use persistent engines (no "created without bootstrap" warnings)
- ETH/SOL features computed with OI baseline and CVD history (no longer degraded)

**Verification scenario (wait for next 15-min cycle):**
1. Check logs for multi-asset decision cycle
2. Verify no "FeatureEngine for ... created without bootstrap" warnings
3. Query decision_outcomes for ETH/SOL feature quality
4. Compare ETH/SOL OI z-score, CVD divergence to BTC (should be populated, not empty)

**M4 quality check (after 24h of new cycles):**
```bash
python scripts/report_near_miss_diagnostics.py \
  --all-symbols \
  --since 2026-05-22T20:30:00Z \
  --output /tmp/m4_post_feature_persistence.md
```
- Expected: ETH/SOL signal quality improves (OI context, CVD divergence now available)
- Compare to pre-persistence M4 (should see more valid ETH/SOL candidates)

---

**Next milestone:** After successful deploy and verification, proceed with `MULTI_ASSET_DD_TRACKING_V1` (per-symbol DD in governance/risk + true high-watermark).

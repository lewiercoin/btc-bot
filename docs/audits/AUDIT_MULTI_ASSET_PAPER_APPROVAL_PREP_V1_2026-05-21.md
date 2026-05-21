# AUDIT: MULTI_ASSET_PAPER_APPROVAL_PREP_V1
Date: 2026-05-21
Auditor: Claude Code
Commit: fd558a8

## Verdict: DONE

**Scope:** Activation preparation ONLY. NO activation in this commit. Production `settings.json` unchanged, services NOT restarted.

## Layer Separation: PASS
- Settings overlay mechanism in settings.py (runtime configuration layer)
- No changes to orchestrator, core, execution, or trading logic
- Runbook in docs/operations (operational guidance, not code)
- No runtime code imports in settings overlay parsing

## Contract Compliance: PASS
- Scope: add validated runtime overlay for `multi_asset` in `settings.json`
- NO production `settings.json` changes (activation surface prepared, not activated)
- NO service restarts (preparation only)
- NO code default changes (enabled=False remains default)
- BTC required in `enabled_symbols` when `multi_asset.enabled=true` (enforced by validation)

## Determinism: PASS
- Overlay loading deterministic (`settings.json` → JSON parse → validation → dataclass replace)
- Validation deterministic (`validate_multi_asset_config()` enforces invariants)
- Symbol normalization deterministic (uppercase, tuple conversion)
- Config hash includes multi_asset overlay (activation changes hash, audit trail)

## Backward Compatibility: PASS
- Default behavior unchanged (no `settings.json` → no overlay → enabled=False)
- Existing runtime_overlay mechanism extended (strategy, risk already supported)
- 593 tests pass (24 skipped) — 7 new tests for multi_asset overlay
- Production BTC PAPER unchanged (no activation, no restart)

## State Integrity: PASS
- Settings overlay applied at load time (before runtime starts)
- Invalid overlays fail fast (ValueError at settings load, before any order path)
- No state mutation during overlay parsing (read-only JSON load → validation → immutable dataclass)

## Error Handling: PASS
- Invalid JSON → JSONDecodeError at load time
- Non-dict payload → ValueError ("must be a JSON object")
- Schema version mismatch → ValueError (explicit error message)
- Invalid `enabled_symbols` (not list/tuple) → ValueError
- Invalid `symbol_overrides` (not list/tuple) → ValueError
- Unknown symbol override keys → validation error
- `validate_multi_asset_config()` enforces all invariants (duplicate symbols, disabled with >1 symbols, missing BTCUSDT, unknown overrides)

## Smoke Coverage: PASS
- **Settings overlay tests (7 new):**
  - `test_load_settings_experiment_profile_applies_multi_asset_runtime_overlay()` → enabled=True, symbols normalized, overrides applied
  - `test_load_settings_experiment_profile_multi_asset_overlay_changes_config_hash()` → config hash changes when overlay applied
  - `test_load_settings_experiment_profile_rejects_invalid_multi_asset_overlay()` → validation errors raised
  - `test_load_settings_experiment_profile_rejects_unknown_symbol_override_key()` → unknown override keys rejected
  - Existing validation tests verify duplicate symbols, disabled multi-symbol, missing BTCUSDT, unknown overrides
- **Total settings tests: 24 passed**
- **Full suite: 593 passed (24 skipped)**

## Tech Debt: LOW
- Clean overlay mechanism (extends existing strategy/risk overlay pattern)
- Validation at load time (fail fast before runtime)
- Immutable dataclasses (no mutable state in overlay application)
- No magic numbers (overlay keys match dataclass field names)

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message (fd558a8)
- Scope purity: preparation only, NO activation, NO production changes
- Documentation: DECISIONS_LOG, MILESTONE_TRACKER, runbook all updated

## Premature Activation: BLOCKED
- This milestone does NOT enable ETH/SOL PAPER
- This milestone does NOT change multi_asset.enabled (remains False by default)
- This milestone does NOT change production `settings.json`
- This milestone does NOT restart production services
- Purpose: prepare activation surface (settings overlay mechanism + runbook), NOT activate
- ETH/SOL activation requires: separate explicit operator action (create/edit `settings.json` → restart → post-checks)

## Reproducibility & Lineage: PASS
- Addresses activation gap: existing overlay supports strategy/risk, now extended to multi_asset
- All technical milestones complete (runtime, capacity, M4, shadow, guard fix)
- Activation remains explicit operator step (edit production `settings.json` → restart)
- Documented in DECISIONS_LOG.md (2026-05-21 entry)

## Artifact Consistency: PASS
- Runbook matches overlay mechanism (settings.json structure, validation rules)
- Tests verify overlay parsing and validation (enabled, symbols, overrides)
- DECISIONS_LOG documents boundaries (no activation, no production changes)
- Runbook includes pre-activation checks, rollback plan, post-activation checks

## Boundary Coupling: PASS
- Settings overlay isolated to settings.py (runtime configuration layer)
- No coupling to orchestrator, core, execution (overlay parsed before runtime starts)
- Runbook is operational guidance (docs/operations), not code
- No imports from runtime decision logic in overlay parsing

## Runtime Overlay Specifics: PASS

**Overlay mechanism (`_apply_runtime_overlay`):**
- **Scope:** live and experiment profiles only (research profile unaffected)
- **Source:** `settings.json` (or `BOT_SETTINGS_PATH` env var)
- **Sections:** strategy, risk, multi_asset (extended in this milestone)
- **Validation:** schema_version must match, section overrides validated, `validate_multi_asset_config()` enforces invariants
- **Config hash:** includes overlay (activation changes hash → audit trail)

**multi_asset overlay parsing (`_multi_asset_overrides`):**
```python
def _multi_asset_overrides(payload: dict[str, Any]) -> dict[str, Any]:
    overrides = _section_overrides(payload, "multi_asset", MultiAssetConfig)
    if not overrides:
        return {}
    
    # Normalize enabled_symbols: list → tuple, uppercase
    if "enabled_symbols" in overrides:
        raw_symbols = overrides["enabled_symbols"]
        if not isinstance(raw_symbols, list | tuple):
            raise ValueError("multi_asset.enabled_symbols must be a JSON array.")
        overrides["enabled_symbols"] = tuple(str(symbol).upper() for symbol in raw_symbols)
    
    # Normalize symbol_overrides: list of dicts → tuple of SymbolStrategyOverride
    if "symbol_overrides" in overrides:
        raw_overrides = overrides["symbol_overrides"]
        if not isinstance(raw_overrides, list | tuple):
            raise ValueError("multi_asset.symbol_overrides must be a JSON array.")
        overrides["symbol_overrides"] = tuple(
            _coerce_symbol_strategy_override(item) for item in raw_overrides
        )
    
    return overrides
```

**Validation enforced:**
- `enabled_symbols` must be JSON array
- `symbol_overrides` must be JSON array
- `validate_multi_asset_config()` enforces:
  - No duplicate symbols
  - enabled=False → only 1 symbol allowed
  - enabled=True → BTCUSDT required
  - Unknown override symbols → error
  - Negative/zero risk/notional caps → error

**Activation surface example (runbook):**
```json
{
  "schema_version": "v1.0",
  "multi_asset": {
    "enabled": true,
    "enabled_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "symbol_overrides": [
      {"symbol": "ETHUSDT", "min_sweep_depth_pct": 0.0075},
      {"symbol": "SOLUSDT", "min_sweep_depth_pct": 0.0075}
    ],
    "max_total_risk_pct_open": 0.007,
    "max_gross_notional_pct": 1.0,
    "max_directional_notional_pct": 0.75,
    "max_open_positions_total": 2,
    "max_open_positions_per_symbol": 1
  }
}
```

**Runbook structure:**
1. **Current activation posture:** Conscious, explicit, reversible, no code defaults
2. **Pre-activation checks:** Capacity, shadow checkpoint, M4 report
3. **Activation blockers:** Capacity fail, shadow checkpoint fail, production_db_touched >0, ETH/SOL positions exist, multi_asset.enabled already true
4. **Overlay shape:** Example settings.json with BTC/ETH/SOL
5. **Rollback anchors:** Tag `pre-multi-asset-paper-20260521T095342Z`, backup `/home/btc-bot/backups/manual/pre_multi_asset_paper_quiesced_20260521T101101Z/btc_bot.db`
6. **Post-activation checks:** Service status, bot status, capacity, M4 multi-symbol report

**Key safety properties:**
- Activation requires explicit production `settings.json` edit (no code default change)
- Invalid overlay fails at load time (before any order path)
- Config hash changes when overlay applied (audit trail)
- Rollback plan documented (git tag + verified backup)
- Pre/post-activation checks explicit (capacity, shadow checkpoint, M4 report)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. Activation surface prepared (settings overlay + runbook)
2. NO activation in this commit (enabled=False default unchanged)
3. Production `settings.json` unchanged (activation requires explicit operator edit)
4. Services NOT restarted (no deployment, preparation only)
5. Overlay mechanism extends existing strategy/risk overlay pattern
6. Validation at load time (fail fast before runtime starts)
7. Config hash includes overlay (activation changes hash → audit trail)
8. Runbook documents pre-activation checks, rollback plan, post-activation checks
9. Tests verify overlay parsing, validation, config hash change
10. All technical readiness milestones complete (runtime, capacity, M4, shadow, guard fix)
11. Activation remains explicit operator step (future milestone, separate decision)
12. Rollback plan clear (git tag + verified backup)

## Recommended Next Step

**Activation preparation is DONE. Ready for future activation decision (separate milestone).**

### Current State Summary

**Technical readiness: ALL MILESTONES COMPLETE**
- ✅ Multi-asset runtime contracts deployed (dormant)
- ✅ Capacity guardrails deployed and passing
- ✅ M4 extension deployed (per-symbol reporting ready)
- ✅ Shadow evidence checkpoint implemented and passing
- ✅ production_db_touched blocker resolved (guard fix deployed)
- ✅ Activation surface prepared (settings overlay + runbook)

**Shadow evidence accumulation: ONGOING**
- ETH/SOL depth @ 0.0075 collecting forward evidence
- Latest checkpoint: PASS (production_db_touched_true_count=0, 4 complete cycles in 1h)
- Accumulation period: ~5 days (target 30-60 days for high confidence, but activation posture is conscious and explicit)

**Activation decision: DEFERRED TO OPERATOR**

No fixed day-count requirement. Activation proceeds when operator decides based on:
- Shadow evidence quality (checkpoint pass, signal distribution, portfolio gate behavior)
- Resource consumption trends (capacity check pass, RSS/disk/CPU stable)
- M4 multi-symbol report (BTC/ETH/SOL signal quality)
- Business readiness (operator confidence in ETH/SOL activation)

### Future Activation Milestone (Separate, Explicit)

**Milestone name:** `MULTI_ASSET_PAPER_ACTIVATION_V1` (future, not started)

**Scope:** Explicit operator activation of BTC/ETH/SOL PAPER

**Prerequisites (all complete):**
- ✅ All technical readiness milestones
- ✅ Activation surface prepared (this milestone)
- ⏳ Shadow evidence accumulation (ongoing, no fixed target)
- ⏳ Operator decision to activate (future)

**Activation steps (when operator decides):**
1. Run pre-activation checks on production server:
   ```bash
   python scripts/runtime_capacity_check.py  # Must be PASS
   python scripts/multi_asset_shadow_evidence_checkpoint.py --hours 2 --expected-min-cycles 6  # Must be PASS
   python scripts/report_near_miss_diagnostics.py --all-symbols --days 1 --output /tmp/m4_pre_activation.md
   ```

2. Create production `settings.json`:
   ```bash
   # On production server: /home/btc-bot/btc-bot/settings.json
   cat > settings.json <<'EOF'
   {
     "schema_version": "v1.0",
     "multi_asset": {
       "enabled": true,
       "enabled_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
       "symbol_overrides": [
         {"symbol": "ETHUSDT", "min_sweep_depth_pct": 0.0075},
         {"symbol": "SOLUSDT", "min_sweep_depth_pct": 0.0075}
       ],
       "max_total_risk_pct_open": 0.007,
       "max_gross_notional_pct": 1.0,
       "max_directional_notional_pct": 0.75,
       "max_open_positions_total": 2,
       "max_open_positions_per_symbol": 1
     }
   }
   EOF
   ```

3. Restart service:
   ```bash
   systemctl restart btc-bot.service
   ```

4. Run post-activation checks:
   ```bash
   systemctl status btc-bot.service --no-pager  # Active, no restart loop
   python scripts/query_bot_status.py  # enabled=True, symbols=BTC/ETH/SOL
   python scripts/runtime_capacity_check.py  # Still PASS
   python scripts/report_near_miss_diagnostics.py --all-symbols --days 1 --output /tmp/m4_post_activation.md
   ```

**Rollback (if needed):**
```bash
systemctl stop btc-bot.service
git reset --hard pre-multi-asset-paper-20260521T095342Z
# Restore backup if needed
systemctl start btc-bot.service
```

---

**Next step:** Wait for operator activation decision. No code changes required. Activation is operational step (edit `settings.json` → restart → verify).

# AUDIT: PAPER_SIMULATION_ACCOUNT_FOUNDATION_V1
Date: 2026-05-22
Auditor: Claude Code
Commit: 1a37c7c

## Verdict: DONE

**Scope:** Persistent PAPER simulation account foundation for investor-style BTC/ETH/SOL sizing with compounding. Disabled by default, no dashboard controls in this milestone.

## Layer Separation: PASS
- Config layer: `PaperSimulationConfig` in settings.py with validation
- Storage layer: `paper_simulation_account` table in schema.sql, state_store.py methods
- Orchestrator layer: Risk equity integration, PnL application after trade close
- Test layer: Coverage across settings, state_store, orchestrator dispatch
- No cross-layer violations or unexpected dependencies

## Contract Compliance: PASS
- **Risk sizing contract:** Uses current equity (simulation balance when enabled, else REFERENCE_EQUITY)
- **Storage contract:** Persistent singleton account (id=1), deterministic reads/writes
- **Config contract:** Runtime overlay with validation at load time, config hash includes paper_simulation
- **Activation surface:** settings.json `paper_simulation` section (same pattern as multi_asset)
- **Backward compatibility:** Default disabled (enabled=False), existing PAPER behavior unchanged

## Determinism: PASS
- Account initialization deterministic (starting_balance → current_balance, realized_pnl=0)
- PnL application deterministic:
  - `compound_pnl=True`: current_balance += pnl, realized_pnl += pnl
  - `compound_pnl=False`: realized_pnl += pnl only (balance unchanged)
- Equity calculation deterministic (`max(current_balance, 1e-8)` floor)
- Singleton enforcement deterministic (id=1 PRIMARY KEY constraint)
- Account preserved across restarts (existing balance not reset by config change)

## Backward Compatibility: PASS
- Default `enabled=False` (no production impact until activated)
- Only affects PAPER mode (not LIVE or RESEARCH)
- Existing PAPER behavior unchanged (fixed 10000 USD when disabled)
- 619 tests pass (24 skipped) — 7 new tests for simulation account
- No changes to signal generation, governance, execution routing, or thresholds

## State Integrity: PASS
- **Singleton guarantee:** id=1 PRIMARY KEY CHECK constraint prevents duplicates
- **Account persistence:** Survives restarts (DB table, not memory-only)
- **Balance preservation:** `ensure_paper_simulation_account()` preserves existing balance (doesn't reset on restart)
- **PnL consistency:** Always updates realized_pnl, conditionally updates current_balance
- **Recovery:** Account initialized at startup if enabled, recoverable from DB after crash
- **Timestamp tracking:** updated_at recorded on every balance change

## Error Handling: PASS
- **Invalid starting_balance (≤0):** ValueError at config validation (load-time fail-fast)
- **Invalid config types:** ValueError at overlay parsing (enabled/compound_pnl must be bool)
- **Uninitialized account:** RuntimeError in `apply_paper_simulation_pnl` (explicit error)
- **Zero/negative balance:** Floor at 1e-8 in `_risk_equity()` prevents division by zero
- **Account initialization:** `ensure_paper_simulation_account` called at startup (`start()` → `_sync_simulation_reference_equity()`)

## Smoke Coverage: PASS
- **Config overlay tests (3 new):**
  - `test_load_settings_experiment_profile_applies_paper_simulation_overlay()` → enabled, starting_balance, compound_pnl applied
  - `test_load_settings_experiment_profile_paper_simulation_overlay_changes_config_hash()` → config hash changes when enabled
  - `test_load_settings_experiment_profile_rejects_invalid_paper_simulation_overlay()` → starting_balance=0 rejected
- **State store tests (3 new):**
  - `test_paper_simulation_account_initializes_and_preserves_balance()` → ensure preserves existing balance (doesn't reset)
  - `test_paper_simulation_account_compounds_realized_pnl()` → win +37.5, loss -12.5 → balance 1025.0, realized_pnl 25.0
  - `test_paper_simulation_account_can_track_pnl_without_compounding()` → compound_pnl=False tracks but doesn't apply to balance
- **Orchestrator integration test (1 new):**
  - `test_paper_simulation_account_balance_overrides_reference_equity_for_sizing()` → _risk_equity returns 1000.0 initially, 875.0 after -125 PnL
- **Focused: 25 passed, Wider: 50 passed, Full suite: 619 passed (24 skipped)**

## Tech Debt: LOW
- Clean implementation (extends runtime overlay pattern)
- No NotImplementedError stubs
- No magic numbers (1e-8 floor documented)
- Dashboard controls explicitly deferred to separate milestone (documented in DECISIONS_LOG)
- No duplication (reuses overlay validation, state persistence patterns)

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message (1a37c7c)
- Scope purity: foundation only, no dashboard, no AI/ML, no signal/governance changes
- Documentation: DECISIONS_LOG and MILESTONE_TRACKER updated with boundaries and consequences

## Investor-Style Sizing Flow: PASS

**Compounding example (compound_pnl=True, starting_balance=1000 USD):**
1. Start: balance $1000, risk 0.7% → $7 position size
2. Win: +$2 PnL → balance $1002
3. Next position: risk 0.7% of $1002 → $7.014 (larger)
4. Loss: -$50 PnL → balance $952
5. Next position: risk 0.7% of $952 → $6.664 (smaller after loss)

**Non-compounding example (compound_pnl=False):**
- Balance stays at starting_balance ($1000)
- realized_pnl tracks cumulative P&L for reporting
- Position size constant at risk 0.7% of $1000 = $7

**Shared capital (BTC/ETH/SOL):**
- All symbols use same simulation account
- BTC loss reduces available capital for ETH/SOL
- ETH win increases available capital for BTC/SOL
- Portfolio gate and per-symbol risk limits still apply

## Critical Safety Analysis: PASS

**Negative balance scenario:**
- If losses exceed starting balance → balance could go negative
- Mitigation: `_risk_equity()` returns `max(current_balance, 1e-8)` (floor prevents division by zero)
- Behavior: Very small positions after heavy losses, runtime continues
- Future enhancement: Could add balance <= threshold → stop trading (not in this milestone)

**Account initialization:**
- Risk: `apply_paper_simulation_pnl` called before account initialized
- Mitigation: RuntimeError raised (explicit fail)
- Runtime guarantee: `start()` calls `_sync_simulation_reference_equity()` → `ensure_paper_simulation_account()`
- Account initialized at startup before any decision cycle

**Balance preservation across restarts:**
- Risk: Config starting_balance changes → account reset
- Mitigation: `ensure_paper_simulation_account` preserves existing balance (only updates enabled flag)
- Config starting_balance only used on FIRST initialization
- Correct behavior: Restarting doesn't reset account (persistent state)

**Config mismatch:**
- Scenario: DB starting_balance $1000, config starting_balance $2500, restart
- Behavior: DB starting_balance preserved at $1000 (config ignored)
- Implication: Config starting_balance is "initial" not "reset"
- To reset: DELETE row or use future dashboard control

**Shared capital risk:**
- Scenario: BTC loses $100, ETH wants to trade
- Behavior: ETH position sizes from reduced balance (correct for shared capital account)
- Documented: This is the design (realistic investor-style simulation)

## Production Activation Surface: PASS

**Example settings.json:**
```json
{
  "schema_version": "v1.0",
  "paper_simulation": {
    "enabled": true,
    "starting_balance_usd": 1000.0,
    "compound_pnl": true
  }
}
```

**Activation sequence:**
1. Code-only deploy (feature code deployed, enabled=False, no account initialized)
2. Create/edit production `settings.json` with enabled=True, starting_balance
3. Restart `btc-bot.service`
4. Account initialized at startup with starting_balance
5. Decision cycles use simulation balance for risk sizing
6. Closed trades apply PnL to balance

**Deactivation/rollback:**
```json
{
  "schema_version": "v1.0",
  "paper_simulation": {
    "enabled": false
  }
}
```
- Risk sizing reverts to REFERENCE_EQUITY (10000 USD)
- Account preserved in DB (can re-enable later without reset)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None. Dashboard controls explicitly deferred to separate milestone.

## Observations (non-blocking)
1. Clean foundation for investor-style PAPER simulation (realistic account balance)
2. Disabled by default (no production impact until activated)
3. Singleton account (id=1 constraint) shared across BTC/ETH/SOL
4. Compounding: losses reduce next position, wins increase available balance
5. Persistent: survives restarts, recoverable from DB
6. Config starting_balance only used on first initialization (not reset on restart)
7. Balance floor at 1e-8 prevents division by zero (allows runtime to continue after heavy losses)
8. Dashboard controls deferred to separate milestone (foundation first, UI later)
9. Config hash includes paper_simulation (activation changes hash → audit trail)
10. Tests cover initialization, preservation, compounding, non-compounding, orchestrator integration
11. 619 tests pass (7 new tests for simulation account)
12. No changes to signal/governance/execution (pure risk sizing enhancement)

## Recommended Next Step

**Foundation is DONE. Ready for code-only deployment. Activation is separate operational decision.**

### Deployment: Code-only (no activation)

**Goal:** Deploy simulation account foundation to production without activating.

**Deployment command:**
```bash
ssh root@204.168.146.253
cd /home/btc-bot/btc-bot
git pull origin deploy/multi-asset-paper-v1  # expect: 1a37c7c or later

# Restart service (orchestrator.py and state_store.py changes)
systemctl restart btc-bot.service
```

**Post-deployment verification:**
```bash
# Verify service restart
systemctl status btc-bot.service --no-pager  # Active, no restart loop

# Verify bot status (paper_simulation should be disabled by default)
python scripts/query_bot_status.py  # paper_simulation.enabled=False

# Check account NOT initialized (feature disabled)
sqlite3 storage/btc_bot.db "SELECT * FROM paper_simulation_account WHERE id=1;"  # No rows

# Monitor first cycle (should use REFERENCE_EQUITY 10000 as before)
tail -f logs/btc_bot.log | grep -E "(multi_asset|risk_equity|simulation)"
```

**Expected first state:**
- Service active with clean restart
- paper_simulation.enabled=False (default, not activated)
- No paper_simulation_account row (account not initialized)
- Risk sizing uses REFERENCE_EQUITY=10000 (unchanged behavior)

### Future Activation (Separate Operational Decision)

**When ready to activate realistic simulation account:**

1. Create production `settings.json`:
   ```bash
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
     },
     "paper_simulation": {
       "enabled": true,
       "starting_balance_usd": 1000.0,
       "compound_pnl": true
     }
   }
   EOF
   ```

2. Restart service:
   ```bash
   systemctl restart btc-bot.service
   ```

3. Verify activation:
   ```bash
   python scripts/query_bot_status.py  # paper_simulation.enabled=True
   sqlite3 storage/btc_bot.db "SELECT * FROM paper_simulation_account WHERE id=1;"
   # Expected: enabled=1, starting_balance_usd=1000.0, current_balance_usd=1000.0, realized_pnl_usd=0.0
   ```

4. Monitor first decision cycle with simulation balance:
   - Risk sizing should use 1000 USD (not 10000 USD)
   - Position sizes 10x smaller than before
   - After first closed trade, balance updates with PnL

---

**Next milestone decision:** Code-only deploy foundation → verify clean restart → defer activation to future operational decision → plan dashboard controls milestone.

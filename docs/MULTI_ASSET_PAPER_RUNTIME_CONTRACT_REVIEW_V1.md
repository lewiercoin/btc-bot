# Multi-Asset PAPER Runtime Contract Review V1

**Date:** 2026-05-21
**Status:** DRAFT - awaiting review and approval
**Scope:** Design/contract review only. No implementation.

## 1. Executive Summary

Multi-asset PAPER runtime requires architectural changes to support BTC/ETH/SOL while:
- **Maintaining BTC-only backward compatibility** (existing behavior unchanged)
- **Blocking ETH/SOL orders** until separate approval milestone
- **Preparing contracts** for future multi-asset promotion
- **Avoiding state migration** through smart design

**Key principle:** Runtime becomes multi-symbol-aware, but **BTC-only mode remains the default and only enabled path** until ETH/SOL receive explicit approval.

---

## 2. Architecture Questions & Answers

### Q1: How to represent symbol configs without breaking StrategyConfig?

**Current state:**
- `settings.StrategyConfig` contains single `symbol: str = "BTCUSDT"` field
- All params are symbol-agnostic (ATR period, confluence, etc.)
- `AppSettings.strategy` is single `StrategyConfig` instance

**Problem:**
- Multi-asset needs per-symbol overrides (ETH/SOL may have different depth thresholds)
- Cannot break existing `StrategyConfig` API (used everywhere)

**Proposed solution:**
```python
# settings.py - NEW

@dataclass(frozen=True)
class SymbolStrategyOverride:
    """Per-symbol parameter overrides for multi-asset runtime."""
    symbol: str
    min_sweep_depth_pct: float | None = None
    # Add more overrides as research validates them
    # confluence_min: float | None = None
    # direction_tfi_threshold: float | None = None

@dataclass(frozen=True)
class MultiAssetConfig:
    """Multi-asset portfolio runtime config."""
    enabled: bool = False  # MUST be False until approval milestone
    enabled_symbols: tuple[str, ...] = ("BTCUSDT",)  # Only BTC until approval
    symbol_overrides: tuple[SymbolStrategyOverride, ...] = ()
    
    # Portfolio risk caps
    max_total_risk_pct: float = 0.007  # Sum of all open position risks
    max_gross_notional_pct: float = 1.0
    max_directional_notional_pct: float = 1.0
    max_open_positions: int = 2  # Portfolio-wide, not per-symbol

# AppSettings modification
@dataclass
class AppSettings:
    strategy: StrategyConfig  # Baseline config, unchanged
    multi_asset: MultiAssetConfig = field(default_factory=MultiAssetConfig)  # NEW
    # ... rest unchanged
```

**Symbol-specific config resolution:**
```python
def resolve_symbol_config(
    baseline: StrategyConfig,
    symbol: str,
    multi_asset: MultiAssetConfig,
) -> StrategyConfig:
    """Apply per-symbol overrides to baseline config."""
    override = next((o for o in multi_asset.symbol_overrides if o.symbol == symbol), None)
    if override is None:
        return baseline
    
    # Apply only non-None overrides
    return replace(
        baseline,
        symbol=symbol,
        min_sweep_depth_pct=override.min_sweep_depth_pct or baseline.min_sweep_depth_pct,
        # ... other overrides as added
    )
```

**Backward compatibility:**
- `multi_asset.enabled = False` by default → single-symbol BTC path (current behavior)
- `AppSettings.strategy` remains baseline → all existing code works
- `orchestrator.py` resolves per-symbol config only when `multi_asset.enabled = True`

**No state migration required:** Old settings files work unchanged.

---

### Q2: Where does portfolio gate go? core/ or new runtime-safe module?

**Current state:**
- `research_lab/models/portfolio_state.py` contains `ResearchPortfolioGate`
- `research_lab/` is offline-only, cannot be imported by runtime

**Problem:**
- Runtime needs portfolio gate for multi-asset risk management
- `research_lab/` is not runtime-safe (contains backtest/replay dependencies)

**Proposed solution:**

**Option A (recommended): Extract to core/portfolio_gate.py**
```python
# core/portfolio_gate.py - NEW

from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True)
class PortfolioRiskConfig:
    """Runtime-safe portfolio risk configuration."""
    max_total_risk_pct: float = 0.007
    max_gross_notional_pct: float = 1.0
    max_directional_notional_pct: float = 1.0
    max_open_positions: int = 2
    symbol_order: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")

@dataclass(frozen=True)
class PortfolioSignal:
    """Runtime signal representation for portfolio evaluation."""
    symbol: str
    signal_id: str
    direction: str  # "LONG" | "SHORT"
    entry_price: float
    stop_loss: float
    risk_pct: float  # e.g. 0.0035 for BTC, 0.0015 for SOL
    timestamp: datetime

@dataclass(frozen=True)
class PortfolioState:
    """Current portfolio state for gate evaluation."""
    open_positions: tuple[PortfolioSignal, ...]  # Already open
    total_risk_pct: float
    gross_notional_pct: float
    directional_notional_pct: float

@dataclass(frozen=True)
class PortfolioDecision:
    """Portfolio gate decision for a candidate signal."""
    signal_id: str
    approved: bool
    veto_reason: str | None

class RuntimePortfolioGate:
    """Runtime-safe portfolio gate (extracted from research_lab)."""
    
    def __init__(self, config: PortfolioRiskConfig):
        self.config = config
    
    def evaluate(
        self,
        candidate: PortfolioSignal,
        current_state: PortfolioState,
    ) -> PortfolioDecision:
        """Evaluate single candidate against portfolio state."""
        # Priority ordering by symbol (BTC > ETH > SOL)
        # Position cap check
        # Risk cap check
        # Notional cap check
        # Return PortfolioDecision
        pass
```

**Why core/ not research_lab/:**
- `core/` contains runtime-safe deterministic logic (feature_engine, signal_engine, governance, risk_engine)
- Portfolio gate is runtime risk management, not offline research
- Extraction allows research_lab to depend on core, not vice versa

**Research lab alignment:**
- `research_lab/models/portfolio_state.py` becomes a wrapper/adapter around `core/portfolio_gate.py`
- Research uses same logic runtime uses (determinism + consistency)

---

### Q3: How does orchestrator.py maintain BTC-only compatibility?

**Current state:**
- `orchestrator.py` has single decision cycle
- Calls `signal_engine.generate_candidate()` for `settings.strategy.symbol`
- Risk/governance check single candidate
- Execution single position

**Problem:**
- Multi-asset needs loop over symbols
- But BTC-only must remain unchanged (no behavior regression)

**Proposed solution:**

**orchestrator.py decision cycle topology:**
```python
def _run_decision_cycle(self):
    """Main 15m decision cycle."""
    start_time = time.monotonic()
    
    # Mode selection based on multi_asset.enabled
    if self.settings.multi_asset.enabled and len(self.settings.multi_asset.enabled_symbols) > 1:
        self._run_multi_symbol_cycle()
    else:
        self._run_single_symbol_cycle()  # Current BTC-only path, UNCHANGED
    
    CYCLE_DURATION_MS.set((time.monotonic() - start_time) * 1000)

def _run_single_symbol_cycle(self):
    """Single-symbol decision cycle (BTC-only, current behavior)."""
    # Existing code, ZERO changes
    # - market_data.snapshot(symbol=self.settings.strategy.symbol)
    # - feature_engine.compute()
    # - regime_engine.update()
    # - signal_engine.generate_candidate()
    # - governance.filter()
    # - risk_engine.evaluate()
    # - execution_engine.submit_signal()
    pass

def _run_multi_symbol_cycle(self):
    """Multi-symbol decision cycle with portfolio gate."""
    # NEW path, only executed when multi_asset.enabled=True
    # - Loop over self.settings.multi_asset.enabled_symbols
    # - Gather candidates per symbol
    # - Apply portfolio gate
    # - Submit approved signals
    pass
```

**Backward compatibility guarantee:**
- `multi_asset.enabled = False` → `_run_single_symbol_cycle()` → **exact current behavior**
- No code path changes for BTC-only
- Multi-symbol path is separate, gated, tested independently

**Testing strategy:**
- Existing BTC-only tests unchanged (must pass)
- New multi-asset tests cover `_run_multi_symbol_cycle()` path only

---

### Q4: How to block ETH/SOL orders despite runtime contracts?

**Problem:**
- Runtime will have ETH/SOL contracts (SymbolStrategyOverride, portfolio gate, etc.)
- But ETH/SOL orders must be blocked until approval milestone
- Need hard gate, not soft warning

**Proposed solution:**

**Multi-level blocking:**

**Level 1: Config gate (settings.py)**
```python
@dataclass(frozen=True)
class MultiAssetConfig:
    enabled: bool = False  # HARD GATE: Must be True to enable multi-asset
    enabled_symbols: tuple[str, ...] = ("BTCUSDT",)  # Only BTC until approval
    
    def validate(self):
        """Validation at settings load time."""
        if not self.enabled and len(self.enabled_symbols) > 1:
            raise ValueError("multi_asset.enabled must be True when enabled_symbols > 1")
        if self.enabled and "BTCUSDT" not in self.enabled_symbols:
            raise ValueError("BTCUSDT must be in enabled_symbols")
```

**Level 2: Orchestrator gate**
```python
def _run_multi_symbol_cycle(self):
    """Multi-symbol cycle with runtime assertion."""
    if not self.settings.multi_asset.enabled:
        raise RuntimeError("multi_asset.enabled is False, cannot run multi-symbol cycle")
    
    # Only process symbols in enabled_symbols list
    for symbol in self.settings.multi_asset.enabled_symbols:
        # ... generate candidates ...
```

**Level 3: Execution engine gate**
```python
class PaperExecutionEngine:
    def __init__(self, ..., allowed_symbols: tuple[str, ...]):
        self.allowed_symbols = allowed_symbols
    
    def submit_signal(self, signal: ExecutableSignal):
        if signal.symbol not in self.allowed_symbols:
            raise ValueError(f"Symbol {signal.symbol} not in allowed_symbols {self.allowed_symbols}")
        # ... execute ...
```

**Default production settings (until approval):**
```toml
[multi_asset]
enabled = false
enabled_symbols = ["BTCUSDT"]
```

**Approval milestone will:**
1. Audit multi-asset runtime implementation
2. Set `enabled = true`
3. Set `enabled_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]` (or subset)
4. Deploy with explicit approval

**No accidental ETH/SOL orders possible:**
- Config validation fails at startup if misconfigured
- Orchestrator refuses to run multi-symbol cycle if disabled
- Execution engine rejects non-allowed symbols

---

### Q5: How does state/recovery handle per-symbol without blind migration?

**Current state:**
- `storage/state_store.py` tracks single symbol state
- `bot_state` table has `open_positions_count: int` (no symbol breakdown)
- Recovery coordinator assumes single symbol

**Problem:**
- Multi-asset needs per-symbol position tracking
- But cannot break existing `bot_state` schema (BTC-only deployments must keep working)

**Proposed solution:**

**Option A (recommended): Extend schema, maintain compatibility**

**New table: `symbol_state`**
```sql
CREATE TABLE IF NOT EXISTS symbol_state (
    symbol TEXT PRIMARY KEY,
    last_trade_at TEXT,
    consecutive_losses INTEGER DEFAULT 0,
    daily_dd_pct REAL DEFAULT 0.0,
    open_positions_count INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);
```

**Migration strategy:**
- If `symbol_state` table doesn't exist → create it (forward compatible)
- If BTC-only → populate `symbol_state` with single "BTCUSDT" row (derived from `bot_state`)
- If multi-asset → track per-symbol state independently

**StateStore changes:**
```python
class StateStore:
    def get_symbol_state(self, symbol: str) -> SymbolRuntimeState:
        """Get per-symbol state (new method)."""
        # Query symbol_state table
        # Fallback to bot_state for BTC if symbol_state doesn't exist
        pass
    
    def update_symbol_state(self, symbol: str, state: SymbolRuntimeState):
        """Update per-symbol state (new method)."""
        # Upsert symbol_state table
        pass
    
    # Existing methods unchanged for backward compatibility
    def get_bot_state(self) -> BotState:
        """Get global bot state (unchanged)."""
        pass
```

**Recovery:**
```python
class RecoveryCoordinator:
    def recover_positions(self, symbols: tuple[str, ...]):
        """Recover positions for all enabled symbols."""
        for symbol in symbols:
            # Per-symbol recovery
            positions = self.position_persister.load_open_positions(symbol)
            # ... sync with exchange if LIVE ...
```

**No migration required for BTC-only:**
- If `multi_asset.enabled = False` → use existing `bot_state` table
- If `multi_asset.enabled = True` → use `symbol_state` table + portfolio aggregates

---

### Q6: What tests gate implementation?

**Test hierarchy:**

**Level 1: Contract tests (prerequisite for implementation)**
```python
# tests/test_multi_asset_contracts.py - NEW

def test_multi_asset_config_validation():
    """Verify config validation blocks invalid states."""
    # multi_asset.enabled=False with >1 symbols → ValueError
    # multi_asset.enabled=True without BTCUSDT → ValueError
    pass

def test_symbol_config_resolution():
    """Verify per-symbol overrides apply correctly."""
    # Baseline BTC uses 0.00649
    # ETH override uses 0.0075
    # SOL override uses 0.0075
    # Unspecified symbol uses baseline
    pass

def test_portfolio_gate_priority_ordering():
    """Verify BTC > ETH > SOL priority."""
    # If 2 signals, BTC approved first
    # If position cap reached, lower priority vetoed
    pass

def test_portfolio_gate_risk_caps():
    """Verify risk/notional caps enforced."""
    # Total risk cap
    # Gross notional cap
    # Directional notional cap
    pass
```

**Level 2: Runtime integration tests**
```python
# tests/test_multi_asset_orchestrator.py - NEW

def test_single_symbol_cycle_unchanged():
    """BTC-only cycle produces identical results to baseline."""
    # Run cycle with multi_asset.enabled=False
    # Verify decisions match pre-multi-asset behavior
    # Zero regressions
    pass

def test_multi_symbol_cycle_blocked_when_disabled():
    """Multi-symbol cycle raises error when disabled."""
    # multi_asset.enabled=False
    # Attempt multi-symbol cycle → RuntimeError
    pass

def test_multi_symbol_cycle_respects_enabled_symbols():
    """Only enabled_symbols processed."""
    # enabled_symbols=["BTCUSDT", "ETHUSDT"]
    # SOL not processed
    pass
```

**Level 3: Execution gate tests**
```python
# tests/test_execution_symbol_gates.py - NEW

def test_execution_engine_blocks_non_allowed_symbols():
    """Execution rejects signals for non-allowed symbols."""
    # allowed_symbols=["BTCUSDT"]
    # Submit ETH signal → ValueError
    pass
```

**Level 4: State/recovery tests**
```python
# tests/test_multi_asset_state_recovery.py - NEW

def test_symbol_state_table_created_on_init():
    """symbol_state table created if missing."""
    pass

def test_symbol_state_isolated():
    """Per-symbol state updates don't cross-contaminate."""
    # BTC consecutive_losses=2
    # ETH consecutive_losses=0
    # Verify isolation
    pass

def test_recovery_handles_multi_symbol_positions():
    """Recovery coordinator syncs all enabled symbols."""
    # 1 BTC position, 1 ETH position
    # Recovery loads both
    # State correct per symbol
    pass
```

**Gate criteria:**
- **All Level 1 tests must pass** before implementation PR merged
- **All Level 2-4 tests must pass** before deployment consideration
- **BTC-only regression tests must pass** (existing test suite unchanged)

---

## 3. Module Changes Summary

### New modules
- `core/portfolio_gate.py` - Runtime-safe portfolio gate (extracted from research_lab)

### Modified modules
- `settings.py` - Add `MultiAssetConfig`, `SymbolStrategyOverride`, `resolve_symbol_config()`
- `orchestrator.py` - Add `_run_multi_symbol_cycle()`, keep `_run_single_symbol_cycle()` unchanged
- `storage/state_store.py` - Add `get_symbol_state()`, `update_symbol_state()`
- `storage/schema.sql` - Add `symbol_state` table
- `execution/execution_engine.py` - Add `allowed_symbols` gate

### Unchanged modules (backward compatibility)
- `core/models.py` - No breaking changes
- `core/feature_engine.py` - No changes
- `core/signal_engine.py` - No changes (already symbol-aware)
- `core/governance.py` - No changes (already symbol-aware)
- `core/risk_engine.py` - Portfolio risk moved to portfolio_gate, existing risk_engine unchanged

---

## 4. Explicitly Out of Scope

**This milestone does NOT include:**
- ❌ Enabling ETH/SOL trading (blocked until approval milestone)
- ❌ M4 query changes (remains BTC-only)
- ❌ Multi-symbol market data streaming (add in future milestone if needed)
- ❌ Per-symbol telegram alerts (use existing single-channel alerts)
- ❌ Dashboard multi-asset UI (add in future milestone)
- ❌ Backtest multi-asset support (separate research milestone)
- ❌ Research lab portfolio replay changes (already compatible)

**What IS in scope:**
- ✅ Runtime contracts for multi-asset (disabled by default)
- ✅ BTC-only backward compatibility (zero regressions)
- ✅ Portfolio gate in runtime path (core/portfolio_gate.py)
- ✅ Symbol-specific config resolution
- ✅ Per-symbol state tracking (symbol_state table)
- ✅ Test coverage for multi-asset paths

---

## 5. Rollback & Deploy Path

### Rollback strategy
**Tag:** `pre-multi-asset-paper-20260521T095342Z` @ 1e08686
**Backup:** `/home/btc-bot/backups/manual/pre_multi_asset_paper_quiesced_20260521T101101Z/btc_bot.db`

**Rollback triggers:**
- BTC-only behavior regression (any change to existing decisions/trades)
- Runtime crash/error from multi-asset contracts
- State corruption or loss

**Rollback procedure:**
1. Stop `btc-bot.service` and `multi-asset-shadow.timer`
2. `git reset --hard pre-multi-asset-paper-20260521T095342Z`
3. Restore DB from backup if needed
4. Restart services
5. Verify BTC PAPER behavior matches pre-change

### Deploy path
**Branch:** `deploy/multi-asset-paper-v1`

**Phase 1: Implementation + audit**
1. Builder implements runtime contracts per this review
2. All tests pass (Level 1-4)
3. Claude Code audits implementation
4. Verdict: DONE → proceed to Phase 2

**Phase 2: Code-only deployment (ETH/SOL still blocked)**
1. Pull `deploy/multi-asset-paper-v1` to production
2. Verify `multi_asset.enabled = false` in production settings
3. Restart `btc-bot.service`
4. Verify BTC PAPER behavior unchanged (PID, decisions, positions)
5. Multi-asset contracts present but dormant

**Phase 3: Approval milestone (future, separate)**
1. Separate milestone: `MULTI_ASSET_PAPER_APPROVAL_V1`
2. Set `multi_asset.enabled = true`
3. Set `enabled_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]`
4. Deploy with explicit approval
5. Monitor ETH/SOL signals

---

## 6. Success Criteria

**Contract review approved when:**
- ✅ All architecture questions answered
- ✅ No breaking changes to BTC-only path
- ✅ Clear module boundaries (core/portfolio_gate.py location decided)
- ✅ Execution gates prevent accidental ETH/SOL orders
- ✅ State/recovery strategy avoids blind migration
- ✅ Test hierarchy defined with clear gate criteria
- ✅ Rollback path documented and tested

**Implementation ready when:**
- ✅ This document approved by user
- ✅ Handoff generated for builder (Codex)
- ✅ Acceptance criteria clear
- ✅ Out-of-scope items explicit

---

## 7. Open Questions (require user decision)

1. **Portfolio gate location:** Approve `core/portfolio_gate.py` or propose alternative?
2. **Symbol config resolution:** Approve `resolve_symbol_config()` pattern or propose alternative?
3. **State migration:** Approve `symbol_state` table approach or propose alternative?
4. **Test gate criteria:** Level 1-4 hierarchy sufficient or add more gates?
5. **Deploy timing:** Code-only deployment first (Phase 2), then approval milestone (Phase 3)?

---

## 8. Next Step

**If this contract review is approved:**
Generate `MULTI_ASSET_PAPER_RUNTIME_FOUNDATION_V1` implementation handoff for Codex with:
- Detailed module-by-module changes
- Test requirements from Level 1-4
- Acceptance criteria
- Claude Code audit gate

**If modifications needed:**
Discuss specific concerns, revise contract review, re-submit for approval.

---

**Review status:** AWAITING USER APPROVAL

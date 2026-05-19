# AUDIT: MULTI_ASSET_PORTFOLIO_ARCHITECTURE_V1

**Date:** 2026-05-19  
**Auditor:** Claude Code  
**Commit:** 6ff896c  
**Builder:** Codex  

---

## Verdict: PASS

Design-only blueprint for multi-asset portfolio architecture. Clear per-symbol pipeline + portfolio gate topology, explicit state contracts, conservative risk defaults, bounded conflict policy, and strong parity/deployment requirements. Ready to guide future implementation milestone.

---

## Core Audit Axes

### Layer Separation: PASS (Design)

**Design-only verification:**
- **Files modified:** Only docs (blueprint + DECISIONS_LOG + MILESTONE_TRACKER)
- **No code changes:** Zero modifications to `core/`, `execution/`, `orchestrator.py`, `main.py`, `settings.py`, `storage/`, `backtest/`
- **Status:** `READY_FOR_AUDIT_DESIGN_ONLY`
- **Explicit non-goals:** Lists all runtime/code changes as out of scope

**Layer contract design:**
| Layer | Multi-Asset Contract | Separation Quality |
|---|---|---|
| Data | Isolated `MarketSnapshot` per symbol, no mixed state | ✓ CLEAR |
| Features | One `FeatureEngine` rolling state per symbol | ✓ CLEAR |
| Regime | Symbol-local regime, portfolio regime diagnostic only | ✓ CLEAR |
| Signal | Symbol-explicit `SignalCandidate` before runtime | ✓ CLEAR |
| Governance | Symbol-local state + read-only portfolio context | ✓ CLEAR |
| Risk | Per-symbol gate first, portfolio gate final veto | ✓ CLEAR |
| Execution | Routes by symbol, does not choose strategy priority | ✓ CLEAR |
| Storage | Symbol on all records (signal/decision/position/trade/order) | ✓ CLEAR |
| Monitoring | Per-symbol and portfolio views | ✓ CLEAR |

**Architecture topology:**
```
Per-symbol pipeline (BTC, ETH separate):
  MarketSnapshot(symbol)
    -> FeatureEngine(symbol-local state)
    -> RegimeEngine
    -> SignalEngine
    -> GovernanceLayer(symbol state)
    -> CandidateExecutableSignal(symbol)

Portfolio Gate (coordinates approved signals):
  collect per-symbol signals
    -> deterministic ordering
    -> portfolio risk budget
    -> conflict policy
    -> final risk veto

Execution (routes by symbol):
  approved executable signals
    -> exchange symbol rules
    -> order lifecycle
    -> symbol-aware persistence
```

**Separation verdict:** Design clearly separates per-symbol logic from portfolio coordination. No hidden coupling.

### Contract Compliance: PASS (Design)

**State model contracts:**

**`SymbolRiskState` (per symbol):**
- `symbol`, `open_positions_count`, `trades_today`, `consecutive_losses`
- `daily_pnl_r`, `weekly_pnl_r`, `rolling_drawdown_r`
- `last_trade_at`, `last_loss_at`, `symbol_paused_until`, `pause_reason`
- **Coverage:** Sufficient for per-symbol risk decisions ✓
- **Persistence:** Recoverable after restart ✓

**`PortfolioRiskState` (portfolio-wide):**
- `open_positions_total`, `gross_notional_pct`, `directional_notional_pct_long/short`
- `total_risk_pct_open`, `daily_pnl_r`, `weekly_pnl_r`, `rolling_drawdown_r`
- `global_consecutive_losses`, `portfolio_paused_until`, `emergency_stop_active`, `last_portfolio_loss_at`
- **Coverage:** Sufficient for portfolio risk caps and emergency stops ✓
- **Persistence:** "Must never be inferred only from in-memory objects. Must be recoverable after restart" ✓

**Persistence contract:**
| Entity | Required Change | Completeness |
|---|---|---|
| `signal_candidates` | Require `symbol`, keep setup type and feature trace | ✓ EXPLICIT |
| `executable_signals` | Require `symbol`, include portfolio veto metadata | ✓ EXPLICIT |
| `positions` | Already has symbol, recovery must support multiple open | ✓ EXPLICIT |
| `trade_log` | Ensure symbol is first-class in reports | ✓ EXPLICIT |
| `decision_outcomes` | Require symbol and portfolio decision fields | ✓ EXPLICIT |
| `bot_state` | Split or supplement with portfolio/symbol state tables | ✓ EXPLICIT |
| runtime metrics | Add per-symbol and portfolio-level health metrics | ✓ EXPLICIT |

**Recovery contract (7-step):**
1. Query exchange positions for every enabled symbol
2. Reconcile persisted positions by symbol
3. Detect orphan/phantom/unknown positions
4. Rebuild `PortfolioRiskState` from trades + open positions
5. Rebuild each `SymbolRiskState` independently
6. If symbol inconsistent → pause that symbol
7. If portfolio inconsistent → enter safe mode

**Contract quality:** Recovery is idempotent for multiple symbols, with explicit failure handling ✓

### Determinism: PASS (Design)

**Same-bar conflict policy (deterministic):**
1. Allow both BTC and ETH signals in same 15m bar if portfolio caps pass
2. Evaluate in deterministic order: `timestamp ASC`, then `symbol ASC` (`BTCUSDT` before `ETHUSDT`)
3. Second signal reduced/vetoed only by portfolio caps
4. If same direction → `max_directional_notional_pct` priority
5. Veto reasons must be machine-readable: `portfolio_risk_cap_exceeded`, `directional_notional_cap_exceeded`, etc.

**Determinism properties:**
- Signal ordering: `(timestamp ASC, symbol ASC)` → deterministic ✓
- Policy rules: explicit priority (directional notional over allow_both) ✓
- Veto reasons: machine-readable, traceable ✓

**Configuration determinism:**
- Portfolio and per-symbol settings explicit
- `portfolio.enabled: false` default (opt-in, not automatic)
- Per-symbol `enabled` flags independent
- **No automatic promotion:** "settings.py must not become an automatic candidate promotion channel" ✓

### State Integrity: PASS (Design)

**State split design:**
- **SymbolRiskState:** Per-symbol isolation, prevents cross-symbol coupling
- **PortfolioRiskState:** Aggregate view, final veto authority
- **No hidden global state:** "Must be recoverable after restart" requirement ✓

**Persistence requirements:**
- Symbol on all signal/decision/position/trade/order records
- Portfolio veto metadata on blocked signals
- Machine-readable veto reasons
- **Migration safety:** "No migration may proceed without backup and rollback procedure" ✓

**Recovery safety:**
- Safe mode: "continue managing open positions but block new entries"
- Symbol-level pause vs portfolio-level safe mode (independent failure handling)
- Orphan/phantom detection explicit

### Error Handling: PASS (Design)

**Failure modes addressed:**

**Symbol-level failures:**
- Inconsistent position → pause that symbol (continues other symbols)
- Symbol-level loss streak (4 consecutive) → symbol pause
- Symbol daily/weekly hard stops → symbol-specific
- Post-loss cooldown: 125 minutes (trial-00095 default)

**Portfolio-level failures:**
- Inconsistent portfolio exposure → safe mode (manage open, block new)
- Global loss streak (6 consecutive) → portfolio pause
- Portfolio daily/weekly hard stops → override all symbol approvals
- Emergency rolling stop: -8R from high-water mark

**Error handling hierarchy:**
1. Portfolio hard stops override symbol approvals
2. Symbol-level issues don't stop other symbols
3. Safe mode continues risk management while blocking new trades

**Machine-readable veto reasons:**
- `portfolio_risk_cap_exceeded`
- `directional_notional_cap_exceeded`
- `portfolio_daily_hard_stop`
- `symbol_paused`

**Audit trail:** Every veto must be persisted with reason ✓

### Smoke Coverage: N/A (Design-Only)

**Test requirements for future implementation:**
- Deterministic unit tests for symbol-state isolation
- Deterministic unit tests for portfolio risk caps
- Same-bar conflict tests
- Recovery tests (BTC-only, ETH-only, BTC+ETH)
- Storage migration tests with rollback plan
- Portfolio backtest parity tests
- Server smoke test (BTC behavior preserved when ETH disabled)

**Coverage specification:** Explicit list of required tests for implementation milestone ✓

### Tech Debt: NONE (Design-Only)

**No code debt** - this is a design document only.

**Deferred by design:**
- SOL support (out of scope)
- ETH parameter optimization (frozen trial-00095 only)
- Exit changes (trial-00095 exits unchanged)
- Multi-asset regime modeling (diagnostic only)

**Design completeness:**
- All major contracts defined (state, persistence, recovery, configuration)
- Risk defaults specified
- Conflict policy specified
- Deployment path specified

### AGENTS.md Compliance: PASS

**Commit discipline:**
- Commit message: "docs: design multi-asset portfolio architecture"
- WHAT: clear (adds design-only blueprint)
- WHY: clear (audited diagnostic supports architecture, but needs contracts first)
- STATUS: clear (ready for audit, no runtime changes)
- Co-Authored-By: present

**Layer rules:**
- Design-only changes ✓
- No runtime/core/settings modifications ✓
- Branch: `research/sweep-family-expansion-v1` ✓

---

## Research Lab Audit Axes

### Methodology Integrity: PASS (Design)

**Evidence-based design:**
- Built on audited research chain:
  - ETH dataset: PASS (1547 days complete)
  - ETH transfer: PASS (544 trades, ER 1.804)
  - Portfolio diagnostic: PASS (0.051 correlation, 2.8% overlap)

**Design decisions justified by evidence:**

**1. allow_both conflict policy:**
- Evidence: 2.8% same-bar overlap (portfolio diagnostic)
- Design: Allow both signals if portfolio caps pass
- Justification: Low overlap means conflict policy is low-stakes ✓

**2. Risk defaults (conservative):**
- Per-trade risk: 0.35% per symbol (0.70% total if both active)
- Max open: 2 positions total, 1 per symbol
- Portfolio DD stops: -2R soft, -3R hard daily; -4R soft, -6R hard weekly
- Symbol DD stops: -2R daily, -4R weekly, -6R rolling pause
- **Comparison to diagnostic:**
  - Diagnostic combined DD: 19.22R on 1562.65R profit (1.2% DD ratio)
  - Design portfolio emergency stop: -8R from high-water mark
  - **Conservative:** 8R stop is much tighter than 19.22R observed max DD ✓

**3. Per-symbol pipeline design:**
- Evidence: 0.051 daily PnL correlation (near-zero)
- Design: Separate deterministic pipelines per symbol
- Justification: Uncorrelated signals support independent processing ✓

### Promotion Safety: PASS (Design)

**No runtime approval:**
- Status: `READY_FOR_AUDIT_DESIGN_ONLY`
- Executive decision: "This document does not approve ETH trading"
- Non-goals: "implement multi-symbol runtime", "deploy ETH to PAPER or LIVE"

**Deployment path blocked:**
```
Required sequence:
1. Continue BTC PAPER + M4 through 2026-06-13 ✓ (no changes to BTC)
2. Audit this design milestone (current)
3. Close M4 checkpoint, decide BTC baseline
4. Implement multi-asset state + portfolio backtest (separate audited milestone)
5. Run portfolio replay with new contracts
6. If replay passes → ETH shadow/PAPER validation (no BTC risk change)
7. Only after separate audit → consider BTC+ETH PAPER
```

**Safety gates:**
- Design audit required (current)
- M4 checkpoint decision required (2026-06-13)
- Implementation milestone audit required
- Portfolio backtest parity required
- Separate shadow/PAPER validation required
- Final deployment audit required

**No automatic promotion:** "settings.py must not become an automatic candidate promotion channel. Configuration changes must still require audit and deployment approval" ✓

### Reproducibility & Lineage: PASS (Design)

**Design lineage explicit:**
- Baseline: "Frozen trial-00095 sweep/reclaim mechanics, no exit changes"
- Assets: `BTCUSDT`, `ETHUSDT` Binance USDT perpetual futures
- Decision date: 2026-05-19
- Evidence chain: ETH dataset → ETH transfer → Portfolio diagnostic (all PASS)

**Configuration versioning:**
- Per-symbol strategy profiles: `trial_00095`, `trial_00095_transfer`
- Explicit enable/disable flags per symbol and portfolio-level
- Audit requirement for configuration changes

**Risk defaults documented:**
- All risk caps specified with exact values (0.35% per trade, 0.70% total, etc.)
- Cooldown times explicit (125 minutes post-loss)
- DD stops explicit (soft/hard daily/weekly, emergency rolling)

### Data Isolation: PASS (Design)

**Per-symbol data isolation:**
- "Build isolated MarketSnapshot per symbol. No mixed candles, OI, funding, or aggtrade state"
- "One FeatureEngine rolling state per symbol. Never reuse BTC rolling windows for ETH"
- Feature state independence prevents cross-symbol contamination ✓

**Storage isolation:**
- Symbol required on all records (signal/decision/position/trade/order)
- Per-symbol and portfolio state tables separate
- Recovery can rebuild each symbol state independently

**Configuration isolation:**
- Per-symbol settings (strategy profile, risk, max positions)
- Portfolio settings (aggregate caps, global limits)
- Symbol enable/disable independent

### Search Space Governance: PASS (Design)

**No parameter search in design:**
- Risk defaults are specified, not optimized
- Conflict policy is evidence-based, not searched
- Configuration structure defined, not tuned

**Frozen baseline:**
- "Frozen trial-00095 sweep/reclaim mechanics, no exit changes"
- "no change to BTC trial-00095 parameters unless separately audited"
- ETH uses trial-00095 transfer (audited PASS)

**Optimization out of scope:**
- "optimize ETH-specific parameters" listed in non-goals
- "relax M4 monitoring or BTC runtime thresholds" listed in non-goals

### Artifact Consistency: PASS (Design)

**All artifacts align:**
- Blueprint: design-only, no runtime approval
- DECISIONS_LOG: "runtime implementation needs explicit contracts first"
- MILESTONE_TRACKER: status should be READY_FOR_AUDIT (design-only)
- Executive decision: "does not approve ETH trading"

**Evidence consistency:**
- Diagnostic showed 0.051 correlation → design uses per-symbol pipelines ✓
- Diagnostic showed 2.8% overlap → design uses allow_both policy ✓
- Diagnostic showed 19.22R max DD → design uses -8R emergency stop (conservative) ✓

**Risk defaults vs diagnostic:**
| Metric | Diagnostic Evidence | Design Default | Conservative? |
|---|---|---|---|
| Combined DD | 19.22R on 1562.65R (1.2%) | -8R emergency stop | ✓ YES (4x tighter) |
| Correlation | 0.051 (near-zero) | Independent pipelines | ✓ JUSTIFIED |
| Overlap | 2.8% | allow_both + caps | ✓ JUSTIFIED |
| Max open | N/A (diagnostic offline) | 2 total, 1 per symbol | ✓ CONSERVATIVE |
| Per-trade risk | N/A (R-based backtest) | 0.35% per symbol | ✓ CONSERVATIVE |

### Boundary Coupling: PASS (Design)

**Layer boundaries explicit:**
- Per-symbol pipeline: data → features → regime → signal → governance → candidate
- Portfolio gate: coordinates approved signals, final veto
- Execution: routes by symbol, no strategy decisions

**No hidden coupling:**
- "Orchestrator may coordinate flow, but must not calculate portfolio risk ad hoc. Portfolio risk must live behind a clear contract"
- State contracts (SymbolRiskState, PortfolioRiskState) prevent ad-hoc global queries
- Recovery rebuilds state explicitly, no inference from memory

**Configuration coupling:**
- Settings structure defined, but not implementation
- "settings.py must not become automatic promotion channel"
- Audit required for config changes

---

## Critical Issues

None.

---

## Warnings

None.

---

## Observations

### 1. Risk defaults are very conservative

**Design defaults:**
- Per-trade risk: **0.35%** per symbol (0.70% total if both active)
- Max open: **2** positions total, **1** per symbol
- Emergency stop: **-8R** from high-water mark

**Diagnostic evidence:**
- Combined max DD: **19.22R** on 1562.65R profit (1.2% DD ratio)
- Correlation: 0.051 (near-zero)
- Overlap: 2.8%

**Observation:**
- -8R stop is **~2.4x tighter** than observed 19.22R max DD
- 0.35% per trade is much smaller than typical 1-2% single-asset risk
- Max 1 position per symbol prevents concentration

**Why this is appropriate:**
- First multi-asset deployment should be cautious
- Unknown unknowns: execution complexity, correlation drift, extreme events
- Can relax after PAPER validation if evidence supports
- **Fail-safe design:** Easier to relax than tighten after losses

**Recommendation:** Accept conservative defaults for first implementation. Consider relaxation milestone after 3-6 months PAPER validation if risk metrics allow.

### 2. allow_both policy is justified but bounded

**Design choice:** Allow both BTC and ETH signals in same 15m bar if portfolio caps pass.

**Evidence support:**
- Same-bar overlap: 2.8% (22 of 796 unique signal bars)
- Both-active days: 23.6% (115 of 488 days)
- Diagnostic showed allow_both had slight edge advantage (+2.4% ER vs first_signal_only)

**Bounds:**
- Portfolio risk cap: 0.70% max total open risk
- Max positions: 2 total
- Directional notional cap: 0.75x equity
- If second signal violates caps → veto with machine-readable reason

**Safety features:**
- Deterministic ordering: `(timestamp ASC, symbol ASC)`
- Priority rules: directional notional cap before allow_both
- Every veto persisted with reason
- Can switch to first_signal_only or btc_priority if evidence changes

**Observation:** Design correctly balances diagnostic evidence (low overlap, slight edge benefit) with risk management (bounded by caps, traceable vetoes).

### 3. State contracts prevent hidden global coupling

**Problem addressed:** Multi-asset systems often have hidden global state that breaks determinism and recovery.

**Design solution:**
- **SymbolRiskState:** Explicit per-symbol state (positions, PnL, DD, consecutive losses)
- **PortfolioRiskState:** Explicit portfolio state (total positions, notional, aggregate PnL/DD)
- **Persistence requirement:** "Must never be inferred only from in-memory objects. Must be recoverable after restart"

**Benefits:**
- Recovery can rebuild from persisted state deterministically
- Symbol failures don't corrupt portfolio state
- Portfolio failures don't corrupt symbol state
- Testing can verify state transitions explicitly

**Observation:** State contract design is architecturally sound. Prevents common multi-asset bugs (orphan positions, phantom risk, inconsistent recovery).

### 4. Backtest parity requirement is strong

**Design requirement:** "Artifact stitching is no longer sufficient after this design milestone. The next decision-grade simulation must execute the proposed portfolio contracts."

**What this means:**
- Can't just combine BTC artifact + ETH artifact as proxy
- Must implement portfolio backtest with:
  - Per-symbol feature state
  - Per-symbol governance state
  - Portfolio risk caps
  - Same-bar conflict policy
  - Cooldowns, DD stops
  - Recovery assumptions
  - Same fee/slippage for BTC and ETH

**Why this matters:**
- Offline diagnostic (current) used simple artifact stitching
- Real runtime has state coupling, ordering effects, caps interactions
- Backtest must prove runtime contracts work before PAPER deployment

**Acceptance criteria for future milestone:**
- Portfolio backtest parity against this design
- Deterministic unit tests for conflict policy
- Recovery tests with multiple symbols
- Server smoke test (BTC preserved when ETH disabled)

**Observation:** Strong parity requirement reduces risk of runtime surprises. Design correctly identifies that artifact stitching was sufficient for diagnostic but insufficient for deployment.

### 5. Per-symbol cooldowns preserve trial-00095 discipline

**Design default:** Per-symbol post-loss cooldown: **125 minutes** (trial-00095 value).

**Why this matters:**
- Trial-00095 has post-loss cooldown to prevent revenge trading
- In multi-asset portfolio, need to decide: per-symbol or global cooldown?
- Design chooses per-symbol: BTC loss → BTC cooldown, ETH can still trade

**Justification:**
- Diagnostic showed 0.051 correlation (uncorrelated PnL)
- If losses are uncorrelated, per-symbol cooldown is appropriate
- Prevents BTC loss from blocking unrelated ETH opportunity

**Global loss streak (6 consecutive):**
- Design also has portfolio-level pause after 6 global consecutive losses
- Catches pathological "both assets failing simultaneously" scenario
- Conservative: 6 is higher than typical 3-4 single-asset streak threshold

**Observation:** Cooldown design correctly balances per-symbol independence (justified by low correlation) with portfolio-level circuit breaker (6 global losses).

### 6. Recovery contract is implementation-ready

**7-step recovery procedure:**
1. Query exchange positions for all symbols
2. Reconcile persisted positions by symbol
3. Detect orphan/phantom/unknown positions
4. Rebuild `PortfolioRiskState`
5. Rebuild each `SymbolRiskState`
6. Symbol inconsistent → pause symbol
7. Portfolio inconsistent → safe mode

**Quality indicators:**
- **Idempotent:** Same inputs → same recovery state
- **Independent failure handling:** Symbol pause vs portfolio safe mode
- **Explicit detection:** Orphan, phantom, unknown positions named
- **Safe mode behavior:** Continue managing open, block new entries

**Missing detail:** How to handle partial exchange data (e.g., BTC positions retrieved, ETH API timeout)?
- Current spec doesn't explicitly address this
- Recommendation: Future implementation should define timeout/retry policy and fail-safe behavior

**Observation:** Recovery contract is 90% implementation-ready. Minor refinement needed for partial-failure handling, but core structure is sound.

### 7. Configuration structure prevents accidental promotion

**Design pattern:**
```
portfolio:
  enabled: false  # Opt-in, not default
symbols:
  ETHUSDT:
    enabled: false  # Explicitly disabled
    strategy_profile: trial_00095_transfer
```

**Safety features:**
- Portfolio disabled by default
- ETH disabled by default
- Explicit strategy profile naming
- "settings.py must not become automatic promotion channel"
- "Configuration changes must still require audit and deployment approval"

**Contrast with unsafe pattern:**
```
symbols: [BTCUSDT, ETHUSDT]  # ETH auto-enabled if listed
```

**Observation:** Configuration design correctly uses opt-in flags and audit gates to prevent accidental ETH deployment.

### 8. Deployment path has 7 gates before BTC+ETH PAPER

**Full path:**
1. BTC PAPER + M4 continue through 2026-06-13 (no changes)
2. **Audit this design milestone** ← current gate
3. Close M4 checkpoint, decide BTC baseline
4. **Implement + audit multi-asset state + portfolio backtest**
5. **Run + audit portfolio replay with contracts**
6. **Run + audit ETH shadow/PAPER validation** (no BTC risk change)
7. **Final deployment audit** → consider BTC+ETH PAPER

**Gates per phase:**
- Design: 1 audit (current)
- Implementation: 1 audit (code)
- Backtest: 1 audit (replay results)
- Shadow: 1 audit (ETH PAPER validation)
- Deployment: 1 audit (final approval)
- **Total: 5 audits** + M4 decision + portfolio replay evidence

**Observation:** Deployment path is appropriately cautious. 7 gates before BTC+ETH PAPER gives multiple opportunities to catch issues before production risk.

---

## Recommended Next Step

**ACCEPT and CLOSE design milestone.** Architecture blueprint is complete, sound, and ready to guide future implementation.

**Design quality:**
- ✓ Clear layer separation (per-symbol pipelines + portfolio gate)
- ✓ Explicit state contracts (SymbolRiskState, PortfolioRiskState)
- ✓ Conservative risk defaults (0.35% per trade, -8R emergency stop)
- ✓ Evidence-based conflict policy (allow_both, bounded by caps)
- ✓ Strong parity requirement (no artifact stitching, must implement contracts)
- ✓ Idempotent recovery (7-step procedure with failure handling)
- ✓ Safe configuration (opt-in, audit gates)
- ✓ Cautious deployment path (7 gates before BTC+ETH PAPER)

**Next actions:**

**Immediate (before implementation):**
1. **M4 checkpoint (2026-06-13, 25 days):**
   - Close M4 near-miss monitoring
   - Decide whether BTC trial-00095 baseline changes
   - If BTC baseline stable → proceed with multi-asset implementation
   - If BTC baseline changes → re-evaluate multi-asset direction

2. **User decision:**
   - Accept this architecture design (current audit)
   - Commit to multi-asset implementation path (or defer)
   - If committed → schedule next milestone after M4 checkpoint

**After M4 checkpoint (if proceed):**

**Next milestone: `MULTI_ASSET_STATE_AND_BACKTEST_IMPLEMENTATION_V1`**

**Scope:** Implement multi-asset state contracts and portfolio backtest support (offline, no runtime deployment).

**Deliverables:**
1. **State implementation:**
   - `SymbolRiskState` and `PortfolioRiskState` dataclasses/models
   - Persistence layer (symbol-aware tables)
   - Recovery logic (7-step procedure)

2. **Portfolio backtest harness:**
   - Per-symbol feature state tracking
   - Per-symbol governance state
   - Portfolio risk caps
   - Same-bar conflict policy
   - Cooldowns, DD stops
   - Fee/slippage for BTC and ETH

3. **Tests:**
   - Symbol-state isolation tests
   - Portfolio risk cap tests
   - Same-bar conflict tests
   - Recovery tests (BTC-only, ETH-only, BTC+ETH)
   - Storage migration tests with rollback

4. **Portfolio replay:**
   - Run BTC+ETH full 2022-2026 replay with new contracts
   - Compare to diagnostic artifact stitching (validation)
   - Generate trade-level audit trail

**Acceptance criteria:**
- compileall clean
- All unit tests deterministic and passing
- Portfolio replay produces decision-grade results
- Storage migration tested with rollback plan
- No change to BTC trial-00095 parameters

**Not in scope:**
- Runtime orchestrator changes
- PAPER deployment
- Settings.py changes
- Core/execution layer changes

**Subsequent milestones (if implementation passes):**
1. `ETH_SHADOW_PAPER_VALIDATION_V1` - Deploy ETH PAPER without changing BTC risk, shadow-only
2. `MULTI_ASSET_PORTFOLIO_PAPER_AUDIT_V1` - Audit shadow results, decide BTC+ETH PAPER
3. `MULTI_ASSET_PORTFOLIO_RUNTIME_INTEGRATION_V1` - If approved, integrate BTC+ETH PAPER

**Strategic context:**
- M4 monitoring: continues unchanged through 2026-06-13
- BTC PAPER bot: continues unchanged
- Design audit: PASS (current)
- Implementation: blocked until M4 checkpoint + user decision
- PAPER deployment: blocked until implementation + shadow validation audits

**Timeline estimate:**
- M4 checkpoint: 2026-06-13 (25 days)
- Implementation milestone: 2-4 weeks after M4 decision
- Shadow PAPER validation: 2-4 weeks
- Final deployment decision: ~2-3 months from now

Architecture is ready. Implementation can begin after M4 checkpoint and user decision.

---

**Audit Complete**  
**Files Modified:** 0 (audit only)  
**Next Action:** User decides whether to commit to multi-asset implementation path after M4 checkpoint (2026-06-13)
